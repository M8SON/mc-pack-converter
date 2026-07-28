from pathlib import Path
import zipfile

import pytest

from mc_pack_converter.cli import convert

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
        assert meta["pack"]["pack_format"] == 88
