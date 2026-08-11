import zipfile
from pathlib import Path

from mc_pack_converter.job import (
    DEFAULT_TARGET, out_path_beside_source, validate_source,
)


def test_default_target_is_a_real_target():
    from mc_pack_converter.cli import TARGETS
    assert DEFAULT_TARGET in TARGETS


def test_validate_source_accepts_a_directory(mini_pack):
    assert validate_source(mini_pack()) is None


def test_validate_source_accepts_a_real_zip(tmp_path):
    p = tmp_path / "ok.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("pack.mcmeta", "{}")
    assert validate_source(p) is None


def test_validate_source_reports_a_missing_pack(tmp_path):
    p = tmp_path / "nope.zip"
    assert validate_source(p) == f"no such pack: {p}"


def test_validate_source_rejects_a_renamed_rar(tmp_path):
    p = tmp_path / "broken.zip"
    p.write_bytes(b"Rar!\x1a\x07\x00 not a zip at all")
    assert validate_source(p) == f"not a readable zip: {p}"


def test_out_path_beside_source_uses_the_source_folder(tmp_path):
    src = tmp_path / "Downloads" / "MyPack.zip"
    assert out_path_beside_source(src, "26.2") == tmp_path / "Downloads" / "MyPack-26.2.zip"


def test_out_path_beside_source_handles_a_folder_source(tmp_path):
    src = tmp_path / "packs" / "My Pack"
    assert out_path_beside_source(src, "26.1.2") == tmp_path / "packs" / "My Pack-26.1.2.zip"


def test_convert_reports_the_sheet_through_the_callback(tmp_path, mini_pack):
    from PIL import Image
    from mc_pack_converter.job import convert

    root = mini_pack()
    atlas = root / "assets/minecraft/textures/painting/paintings_kristoffer_zetterstrand.png"
    atlas.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (256, 256), (10, 120, 200, 255)).save(atlas)

    seen = []
    out = tmp_path / "converted.zip"
    convert(root, out, "26.1.2", False, on_sheet=lambda p, n: seen.append((p, n)))
    assert seen, "on_sheet was never called"
    path, count = seen[0]
    assert path == tmp_path / "converted-slices.png"
    assert count > 0


def test_convert_does_not_print_the_sheet_line(tmp_path, mini_pack, capsys):
    """The library layer must not print; the front end decides how to show it."""
    from PIL import Image
    from mc_pack_converter.job import convert

    root = mini_pack()
    atlas = root / "assets/minecraft/textures/painting/paintings_kristoffer_zetterstrand.png"
    atlas.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (256, 256), (10, 120, 200, 255)).save(atlas)

    convert(root, tmp_path / "converted.zip", "26.1.2", False)
    assert capsys.readouterr().out == ""
