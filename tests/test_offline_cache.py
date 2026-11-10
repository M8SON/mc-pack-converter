"""The deployed cache covers every file and changes with its contents."""
import hashlib
import json
from pathlib import Path

import runpy

write_service_worker = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "tools" / "build_web.py")
)["write_service_worker"]


def manifest(out):
    lines = (out / "service-worker.js").read_text().splitlines()
    return json.loads(lines[0].removeprefix("const VERSION = ").removesuffix(";")), json.loads(
        lines[1].removeprefix("const FILES = ").removesuffix(";"))


def test_cache_tracks_all_files_and_changed_wheel(tmp_path):
    (tmp_path / "py").mkdir()
    wheel = tmp_path / "py" / "converter.whl"
    wheel.write_bytes(b"first wheel")
    (tmp_path / "index.html").write_text("page")
    write_service_worker(tmp_path)
    version, files = manifest(tmp_path)
    assert files == {"py/converter.whl": hashlib.sha256(b"first wheel").hexdigest(),
                     "index.html": hashlib.sha256(b"page").hexdigest()}
    write_service_worker(tmp_path)
    assert manifest(tmp_path) == (version, files)
    wheel.write_bytes(b"new wheel")
    write_service_worker(tmp_path)
    changed_version, changed_files = manifest(tmp_path)
    assert changed_version != version
    assert changed_files["py/converter.whl"] != files["py/converter.whl"]
    assert changed_files["index.html"] == files["index.html"]


def test_cache_version_tracks_page_and_service_worker_changes(tmp_path, monkeypatch):
    source = tmp_path / "source" / "web"
    source.mkdir(parents=True)
    script = source / "service-worker.js"
    script.write_text("// first worker")
    monkeypatch.setitem(write_service_worker.__globals__, "REPO", source.parent)
    out = tmp_path / "out"
    out.mkdir()
    page = out / "index.html"
    page.write_text("first page")
    write_service_worker(out)
    first, _ = manifest(out)
    page.write_text("changed page")
    write_service_worker(out)
    second, _ = manifest(out)
    assert second != first
    script.write_text("// changed worker")
    write_service_worker(out)
    third, _ = manifest(out)
    assert third != second
