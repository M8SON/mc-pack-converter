import io
import re
import zipfile

from PIL import Image

from mc_pack_converter.webui.sheet import build_sheet

A = "assets/minecraft/"
SKY = A + "optifine/sky/world0/"


def _skybox(cell: int = 32) -> bytes:
    im = Image.new("RGB", (cell * 3, cell * 2), (60, 90, 200))
    im.paste(Image.new("RGB", (cell, cell), (10, 10, 10)), (0, 0))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _pack(tmp_path, entries):
    p = tmp_path / "pack.zip"
    with zipfile.ZipFile(p, "w") as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return p


def _sky_tiles(sheet):
    for s in sheet["sections"]:
        if s["label"] == "Sky":
            return s["tiles"]
    return []


def test_each_sky_layer_is_previewed_from_the_ground(tmp_path):
    zip_path = _pack(tmp_path, {
        SKY + "sky1.properties": b"startFadeIn=5:30\nendFadeIn=6:00\n"
                                 b"endFadeOut=18:20\nblend=replace\nsource=./cloud1.png\n",
        SKY + "cloud1.png": _skybox(),
    })

    tiles = _sky_tiles(build_sheet(zip_path))

    previews = [t for t in tiles if t.get("size") == "sky layer"]
    assert previews, "no sky preview tile"
    tile = previews[0]
    assert "sky1" in tile["name"]
    assert "replace" in tile["name"], "the blend mode is what decides what you see"
    assert len(tile["frames"]) > 1, "the preview does not turn"


def test_a_layer_after_a_numbering_gap_still_loads(tmp_path):
    """MEASURED, against the claim in OptiFine's own documentation.

    The doc says OptiFine reads sky<n> "until a .properties file is not
    found". The shipped code does not: in CustomSky.readCustomSkies the
    `countMissing` counter is initialised INSIDE the loop body, so the
    `if (countMissing > 10) break` can never fire, and the loop runs 0..999
    regardless of gaps.

    Confirmed in game on 26.1.2_HD_U_K1_pre2 with a probe pack carrying
    sky1/sky3/sky15 as solid red/green/magenta at blend=replace: the log
    reported reading all three, and the sky rendered MAGENTA -- sky15, across
    an eleven-layer gap. So a gap strands nothing and the sheet must not claim
    it does.
    """
    zip_path = _pack(tmp_path, {
        SKY + "sky1.properties": b"blend=add\nsource=./cloud1.png\n",
        SKY + "sky3.properties": b"blend=add\nsource=./cloud1.png\n",
        SKY + "cloud1.png": _skybox(),
    })

    tiles = _sky_tiles(build_sheet(zip_path))
    by_name = {t["name"]: t for t in tiles if t.get("size") == "sky layer"}

    assert any("sky1" in n for n in by_name)
    assert any("sky3" in n for n in by_name)
    assert not any("never loads" in n for n in by_name), \
        "a layer above a gap loads fine; saying otherwise is a false warning"


# --- the composite: what the sky actually looks like -------------------------

DAY_LAYER = (b"startFadeIn=5:30\nendFadeIn=6:00\nstartFadeOut=17:30\n"
             b"endFadeOut=18:20\nblend=replace\nsource=./cloud1.png\n")
NIGHT_LAYER = (b"startFadeIn=18:00\nendFadeIn=19:00\nendFadeOut=5:25\n"
               b"blend=screen\nsource=./stars.png\n")


def _composites(sheet):
    return [t for t in _sky_tiles(sheet) if t.get("size", "").startswith("sky at")]


def _shown(sheet):
    """Every layer named by any composite."""
    out = set()
    for t in _composites(sheet):
        out |= set(re.findall(r"sky\d+", t["name"].split(" - ", 1)[-1]))
    return out


def test_the_sky_is_shown_composited(tmp_path):
    """A layer is never seen alone in game -- the sky is every layer whose fade
    window is open, stacked. The per-layer tiles answer "what is this layer";
    only the composite answers "what does my sky look like"."""
    zip_path = _pack(tmp_path, {
        SKY + "sky1.properties": DAY_LAYER,
        SKY + "cloud1.png": _skybox(),
    })
    assert _composites(build_sheet(zip_path))


def test_a_composite_names_the_layers_it_contains(tmp_path):
    zip_path = _pack(tmp_path, {
        SKY + "sky1.properties": DAY_LAYER,
        SKY + "cloud1.png": _skybox(),
    })
    assert _shown(build_sheet(zip_path)) == {"sky1"}


def test_every_layer_reaches_some_composite(tmp_path):
    """The bug Mason caught: with fixed samples at 6:00/12:00/18:00, all three
    fell inside sky1's 5:30-18:20 replace, so every tile was the same picture
    and the night layer was never shown. The times are taken from the pack now,
    so each layer gets a moment where it is actually visible."""
    zip_path = _pack(tmp_path, {
        SKY + "sky1.properties": DAY_LAYER,
        SKY + "sky2.properties": NIGHT_LAYER,
        SKY + "cloud1.png": _skybox(),
        SKY + "stars.png": _skybox(),
    })
    assert _shown(build_sheet(zip_path)) == {"sky1", "sky2"}


def test_no_two_composites_show_the_same_set_of_layers(tmp_path):
    """Three identical blue tiles was the whole complaint."""
    zip_path = _pack(tmp_path, {
        SKY + "sky1.properties": DAY_LAYER,
        SKY + "sky2.properties": NIGHT_LAYER,
        SKY + "cloud1.png": _skybox(),
        SKY + "stars.png": _skybox(),
    })
    sets = [t["name"].split(" - ", 1)[-1] for t in _composites(build_sheet(zip_path))]
    assert len(sets) == len(set(sets))


def test_the_composites_run_in_day_order(tmp_path):
    zip_path = _pack(tmp_path, {
        SKY + "sky1.properties": DAY_LAYER,
        SKY + "sky2.properties": NIGHT_LAYER,
        SKY + "cloud1.png": _skybox(),
        SKY + "stars.png": _skybox(),
    })
    from mc_pack_converter.webui.sky_composite import parse_time
    tiles = _composites(build_sheet(zip_path))
    ticks = [parse_time(t["path"].split(" at ", 1)[1]) for t in tiles]
    assert ticks == sorted(ticks), "day order, not the order clock strings sort in"
    assert len(set(ticks)) == len(ticks), "one composite per moment"


def test_the_composites_come_before_the_per_layer_tiles(tmp_path):
    zip_path = _pack(tmp_path, {
        SKY + "sky1.properties": DAY_LAYER,
        SKY + "cloud1.png": _skybox(),
    })
    kinds = [t.get("size", "") for t in _sky_tiles(build_sheet(zip_path))]
    # The Sky bucket also holds the raw source PNG as an ordinary texture
    # tile, so "not first" is not the assertion -- "before the layer tiles" is.
    first_composite = next(i for i, k in enumerate(kinds) if k.startswith("sky at"))
    first_layer = next(i for i, k in enumerate(kinds) if k == "sky layer")
    assert first_composite < first_layer


def _palette_skybox_with_clear_background(cell: int = 32) -> bytes:
    """A sky whose transparency lives in a palette tRNS chunk, not an alpha
    band -- the shape of M8SON's sky_sunflare.png (mode P, tRNS=0, 83.6%
    clear). Index 0 is transparent white, index 1 an opaque colour.
    """
    from PIL import Image
    im = Image.new("P", (cell * 3, cell * 2), 0)
    im.putpalette([255, 255, 255] + [10, 200, 10] * 255)
    im.paste(1, (0, cell, cell, cell * 2))          # one opaque patch
    buf = io.BytesIO()
    im.save(buf, format="PNG", transparency=0)
    return buf.getvalue()


def test_a_palette_transparent_sky_does_not_blow_the_composite_white(tmp_path):
    """convert("RGB") on such a file turns every clear pixel into the palette
    colour sitting at that index -- white, for the reference pack -- so an
    `add` layer painted the entire sky white instead of a flare over nothing.
    """
    import base64
    from PIL import Image
    zip_path = _pack(tmp_path, {
        SKY + "sky1.properties": DAY_LAYER,
        SKY + "cloud1.png": _skybox(),
        SKY + "sky2.properties": (b"startFadeIn=5:30\nendFadeIn=6:00\n"
                                  b"endFadeOut=18:20\nblend=add\n"
                                  b"source=./flare.png\n"),
        SKY + "flare.png": _palette_skybox_with_clear_background(),
    })
    with_flare = [t for t in _composites(build_sheet(zip_path))
                  if "sky2" in t["name"]]
    assert with_flare, "the add layer must reach a composite"
    raw = base64.b64decode(with_flare[0]["full"].split(",", 1)[1])
    px = list(Image.open(io.BytesIO(raw)).convert("RGB").getdata())
    white = sum(1 for p in px if min(p) > 245)
    assert white < len(px) // 2, \
        f"{white}/{len(px)} pixels blown to white by a transparent layer"
