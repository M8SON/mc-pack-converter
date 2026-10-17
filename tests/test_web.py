"""The browser page's Python glue, run natively.

web/worker.js carries a block of Python that calls into this package by name
(run_job, validate_source, out_path_beside_source, STAGES, ...). Pyodide only
runs it in a browser, so a rename here would break the page with nothing in
CI noticing. These tests run that exact block under CPython instead.
"""
import json
import re
import shutil
import zipfile
from pathlib import Path

import pytest

WORKER = Path(__file__).resolve().parent.parent / "web" / "worker.js"


@pytest.fixture
def glue():
    src = re.search(r"const GLUE = `(.*?)`;", WORKER.read_text(), re.S).group(1)
    ns: dict = {}
    exec(src, ns)
    return ns


def test_info_offers_every_target_newest_first_and_the_default(glue):
    from mc_pack_converter.job import DEFAULT_TARGET
    from mc_pack_converter.stages import STAGES
    info = json.loads(glue["info"]())
    assert info["default"] == DEFAULT_TARGET
    assert info["targets"][0] == DEFAULT_TARGET
    assert "1.8.9" not in info["targets"]
    assert info["stages"] == [name for name, _ in STAGES]


def test_convert_reports_every_stage_and_writes_the_zip(glue, mini_pack, tmp_path):
    root = mini_pack()
    pack = tmp_path / "in" / "MyPack.zip"
    pack.parent.mkdir()
    shutil.make_archive(str(pack.with_suffix("")), "zip", root)
    seen = []
    res = json.loads(glue["convert"](str(pack), "26.3",
                                     lambda name, i, total: seen.append((name, i, total)),
                                     lambda: seen.append("report")))
    assert "problem" not in res, res
    assert seen.pop() == "report"
    assert [i for _, i, _ in seen] == list(range(1, len(seen) + 1))
    assert seen[-1][1] == seen[-1][2]
    assert Path(res["out"]).name == "MyPack-26.3.zip"
    assert zipfile.is_zipfile(res["out"])
    assert set(res["counts"]) == {"info", "warning", "error"}


def test_convert_returns_the_desktop_s_html_report(glue, mini_pack, tmp_path):
    """The same report gui.py writes, naming the download, not a path."""
    root = mini_pack({"assets/minecraft/textures/blocks/stone.png": _png()})
    pack = tmp_path / "in" / "MyPack.zip"
    pack.parent.mkdir()
    shutil.make_archive(str(pack.with_suffix("")), "zip", root)
    res = json.loads(glue["convert"](str(pack), "26.3", lambda *a: None, lambda: None))
    model = json.loads(re.search(r"window.MODEL = (.*?);</script>", res["html"]).group(1))
    assert model["out_path"] == "MyPack-26.3.zip"
    assert model["sheet"]["total"] >= 1
    assert "stone" in res["html"]


def _png() -> bytes:
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGBA", (16, 16), (120, 120, 120, 255)).save(buf, format="PNG")
    return buf.getvalue()


def test_convert_refuses_a_non_zip_in_the_desktop_s_words(glue, tmp_path):
    bad = tmp_path / "notes.zip"
    bad.write_text("not a zip")
    res = json.loads(glue["convert"](str(bad), "26.3", lambda *a: None, lambda: None))
    assert res == {"problem": f"not a readable zip: {bad}"}
