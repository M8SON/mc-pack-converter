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
