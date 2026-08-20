"""The page's JS, exercised for real against jsdom -- the only test in the
suite that RUNS app.js rather than grepping its text.

boot_check.mjs replaces the deleted pywebview-era test_boot.py/boot_check.mjs
(git history: the bridge-boot-order test removed in the commit that dropped
the bridge). Every substring check in test_report.py would pass on a page
whose render() throws; this would not.
"""
import io
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest
from PIL import Image

CHECK = Path(__file__).parent / "boot_check.mjs"


def _node_can_resolve_jsdom() -> bool:
    if shutil.which("node") is None:
        return False
    r = subprocess.run(["node", "-e", "require.resolve('jsdom')"],
                       cwd=Path(__file__).parent, capture_output=True)
    return r.returncode == 0


pytestmark = pytest.mark.skipif(not _node_can_resolve_jsdom(),
                                reason="node or jsdom not available")


def _png(colour=(255, 0, 0, 255)):
    buf = io.BytesIO()
    Image.new("RGBA", (16, 16), colour).save(buf, "PNG")
    return buf.getvalue()


def test_the_page_boots_and_renders_tiles_without_throwing(tmp_path):
    """Renders a real report -- real findings, a real sheet built from a
    real zip -- and hands it to jsdom exactly the way boot_check.mjs would
    hand it to a browser."""
    from mc_pack_converter.job import JobResult
    from mc_pack_converter.pipeline import ConversionContext, Severity
    from mc_pack_converter.webui.report import build_model, render_html
    from mc_pack_converter.webui.sheet import build_sheet

    A = "assets/minecraft/"
    zpath = tmp_path / "MyPack-26.1.2.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr(A + "textures/block/stone.png", _png())
        z.writestr(A + "textures/item/apple.png", _png((0, 255, 0, 255)))
        z.writestr("pack.mcmeta", b"{}")
    sheet = build_sheet(zpath)

    ctx = ConversionContext(root=tmp_path)
    ctx.add("validate", Severity.WARNING, "a finding for the page to show")
    result = JobResult(ctx=ctx, out_path=zpath, reports={}, report_texts={},
                       wrote_zip=True)
    report = tmp_path / "report.html"
    report.write_text(render_html(build_model(result, sheet)), encoding="utf-8")

    r = subprocess.run(["node", str(CHECK), str(report)],
                       cwd=Path(__file__).parent,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
