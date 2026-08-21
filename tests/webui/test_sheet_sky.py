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


def test_a_layer_after_a_numbering_gap_is_marked_dead(tmp_path):
    """OptiFine loads sky<n> "until a .properties file is not found" -- its own
    documentation. A gap silently kills every higher layer, and the converter
    creates gaps when it removes a layer whose source image is missing.
    """
    zip_path = _pack(tmp_path, {
        SKY + "sky1.properties": b"blend=add\nsource=./cloud1.png\n",
        SKY + "sky3.properties": b"blend=add\nsource=./cloud1.png\n",
        SKY + "cloud1.png": _skybox(),
    })

    tiles = _sky_tiles(build_sheet(zip_path))
    by_name = {t["name"]: t for t in tiles if t.get("size") == "sky layer"}

    assert any("sky1" in n and "never loads" not in n for n in by_name)
    assert any("sky3" in n and "never loads" in n for n in by_name), \
        "a layer OptiFine will never load must say so"
