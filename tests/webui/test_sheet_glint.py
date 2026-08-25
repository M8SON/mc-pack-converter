import io
import zipfile

from PIL import Image

from mc_pack_converter.webui.sheet import build_sheet

A = "assets/minecraft/"


def _png(size, colour) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", size, colour).save(buf, format="PNG")
    return buf.getvalue()


def _pack(tmp_path, entries):
    p = tmp_path / "pack.zip"
    with zipfile.ZipFile(p, "w") as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return p


def _tiles(sheet):
    return [t for s in sheet["sections"] for t in s["tiles"]]


def test_the_sheet_shows_the_glint_on_the_pack_s_own_sword(tmp_path):
    """Flat, a glint is diagonal streaks on a square and says nothing about
    whether an enchanted item will read in game."""
    zip_path = _pack(tmp_path, {
        A + "textures/misc/enchanted_glint_item.png": _png((64, 64), (255, 255, 255, 255)),
        A + "textures/item/diamond_sword.png": _png((16, 16), (90, 200, 220, 255)),
    })

    sheet = build_sheet(zip_path)

    enchanted = [t for t in _tiles(sheet) if t["name"].endswith("(enchanted)")]
    assert enchanted, "no glint preview tile in the sheet"
    tile = enchanted[0]
    assert tile["frames"], "the glint preview does not move"
    assert len(tile["frames"]) > 1


def test_a_pack_with_no_glint_gets_no_preview(tmp_path):
    zip_path = _pack(tmp_path, {
        A + "textures/item/diamond_sword.png": _png((16, 16), (90, 200, 220, 255)),
    })

    sheet = build_sheet(zip_path)

    assert not [t for t in _tiles(sheet) if t["name"].endswith("(enchanted)")]
