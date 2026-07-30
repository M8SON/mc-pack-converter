from pathlib import Path
import zipfile

import pytest

from mc_pack_converter.cli import convert, main

PACK = Path("/home/daedalus/linux/M8SON 1.8 PVP PACK")


@pytest.mark.skipif(not PACK.exists(), reason="golden pack absent")
def test_golden_conversion(tmp_path):
    out = tmp_path / "converted.zip"
    ctx = convert(PACK, out, target="26.2", report_only=False)

    assert out.exists()

    from mc_pack_converter.pipeline import Severity

    errors = [f for f in ctx.findings if f.severity is Severity.ERROR]
    assert errors == [], f"unexpected errors: {errors}"

    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
        assert "assets/minecraft/textures/block/fire_0.png" in names
        assert any(n.startswith("assets/minecraft/optifine/sky/world0/") for n in names)
        assert "conversion-report.md" in names

        import json

        meta = json.loads(zf.read("pack.mcmeta"))
        assert meta["pack"]["min_format"] == 88  # 26.2, modern min/max schema
        assert meta["pack"]["max_format"] == 88


def test_convert_cleans_temp_dir(mini_pack, tmp_path):
    root = mini_pack()
    out = tmp_path / "converted.zip"
    ctx = convert(root, out, target="26.2", report_only=False)
    assert not ctx.root.exists()


def test_main_returns_1_on_error(mini_pack, tmp_path):
    bad_root = mini_pack({"assets/minecraft/textures/block/stone.png": b""})
    bad_out = tmp_path / "bad.zip"
    assert main(["convert", str(bad_root), "-o", str(bad_out)]) == 1


def test_main_returns_0_on_clean_pack(mini_pack, tmp_path):
    clean_root = mini_pack()
    clean_out = tmp_path / "clean.zip"
    assert main(["convert", str(clean_root), "-o", str(clean_out)]) == 0


def test_contact_sheet_written_beside_archive(tmp_path, mini_pack):
    from PIL import Image
    root = mini_pack()
    atlas = root / "assets/minecraft/textures/painting/paintings_kristoffer_zetterstrand.png"
    atlas.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (256, 256), (10, 120, 200, 255)).save(atlas)
    out = tmp_path / "converted.zip"
    convert(root, out, target="26.1.2", report_only=False)
    sheet = tmp_path / "converted-slices.png"
    assert sheet.exists(), "contact sheet not written next to the archive"
    with zipfile.ZipFile(out) as zf:
        assert "converted-slices.png" not in zf.namelist()
        assert not any(n.endswith("-slices.png") for n in zf.namelist())


def test_no_contact_sheet_when_nothing_sliced(tmp_path, mini_pack):
    root = mini_pack()
    out = tmp_path / "plain.zip"
    convert(root, out, target="26.1.2", report_only=False)
    assert not (tmp_path / "plain-slices.png").exists()


def test_contact_sheet_failure_does_not_abort_conversion(tmp_path, mini_pack, monkeypatch):
    # The archive is already written by the time the sheet is rendered; a
    # cosmetic review artifact must never fail an otherwise-successful
    # conversion (fail-soft).
    from mc_pack_converter import cli as cli_mod
    from mc_pack_converter.pipeline import Severity

    def _boom(*a, **kw):
        raise OSError("disk full")

    monkeypatch.setattr(cli_mod, "build_contact_sheet", _boom)
    root = mini_pack()
    out = tmp_path / "converted.zip"
    ctx = convert(root, out, target="26.1.2", report_only=False)
    assert out.exists()
    assert any(f.severity is Severity.WARNING and "contact sheet" in f.message
               for f in ctx.findings)
