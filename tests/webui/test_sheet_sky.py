import io
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


def test_the_sky_is_shown_composited_at_a_time_of_day(tmp_path):
    """A layer is never seen alone in game -- the sky is every layer whose
    fade window is open, stacked. The per-layer tiles answer "what is this
    layer"; only the composite answers "what does my sky look like"."""
    zip_path = _pack(tmp_path, {
        SKY + "sky1.properties": DAY_LAYER,
        SKY + "cloud1.png": _skybox(),
    })
    tiles = _composites(build_sheet(zip_path))
    assert any("Noon" in t["name"] for t in tiles), \
        "a daytime layer must appear in the noon composite"


def test_a_composite_names_the_layers_it_contains(tmp_path):
    zip_path = _pack(tmp_path, {
        SKY + "sky1.properties": DAY_LAYER,
        SKY + "cloud1.png": _skybox(),
    })
    noon = [t for t in _composites(build_sheet(zip_path)) if "Noon" in t["name"]]
    assert noon and "sky1" in noon[0]["name"]


def test_a_time_with_no_layer_open_gets_no_tile(tmp_path):
    """Rather than a black square that says nothing. A daytime-only pack has
    nothing to show at midnight, and should not pretend otherwise."""
    zip_path = _pack(tmp_path, {
        SKY + "sky1.properties": DAY_LAYER,
        SKY + "cloud1.png": _skybox(),
    })
    assert not any("Midnight" in t["name"] for t in _composites(build_sheet(zip_path)))


def test_a_night_layer_reaches_the_midnight_composite(tmp_path):
    """Its window is written 18:00-5:25, which wraps past midnight -- the case
    that reads as a nineteen-hour gap if the wrap is handled wrongly."""
    zip_path = _pack(tmp_path, {
        SKY + "sky1.properties": DAY_LAYER,
        SKY + "sky2.properties": NIGHT_LAYER,
        SKY + "cloud1.png": _skybox(),
        SKY + "stars.png": _skybox(),
    })
    tiles = _composites(build_sheet(zip_path))
    midnight = [t for t in tiles if "Midnight" in t["name"]]
    assert midnight and "sky2" in midnight[0]["name"]
    assert "sky1" not in midnight[0]["name"], "the day layer is shut at midnight"


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


def test_the_composites_run_in_day_order(tmp_path):
    """Dawn, noon, dusk, midnight -- which is tick order, since Minecraft's day
    starts at 6:00. Sorting the clock strings instead gives 0:00, 12:00, 18:00,
    6:00, i.e. midnight first and dawn last."""
    zip_path = _pack(tmp_path, {
        SKY + "sky1.properties": b"startFadeIn=5:00\nendFadeIn=5:30\n"
                                 b"endFadeOut=4:00\nblend=add\nsource=./cloud1.png\n",
        SKY + "cloud1.png": _skybox(),
    })
    names = [t["name"].split()[0] for t in _composites(build_sheet(zip_path))]
    assert names == ["Dawn", "Noon", "Dusk", "Midnight"]


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
    zip_path = _pack(tmp_path, {
        SKY + "sky1.properties": DAY_LAYER,
        SKY + "cloud1.png": _skybox(),
        SKY + "sky2.properties": (b"startFadeIn=5:30\nendFadeIn=6:00\n"
                                  b"endFadeOut=18:20\nblend=add\n"
                                  b"source=./flare.png\n"),
        SKY + "flare.png": _palette_skybox_with_clear_background(),
    })
    noon = [t for t in _composites(build_sheet(zip_path)) if "Noon" in t["name"]]
    assert noon and "sky2" in noon[0]["name"], "the add layer must be in it"

    from PIL import Image
    import base64
    raw = base64.b64decode(noon[0]["full"].split(",", 1)[1])
    px = list(Image.open(io.BytesIO(raw)).convert("RGB").getdata())
    white = sum(1 for p in px if min(p) > 245)
    assert white < len(px) // 2, \
        f"{white}/{len(px)} pixels blown to white by a transparent layer"
