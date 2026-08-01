"""The corpus harness is a tool, but its pack_format read is load-bearing.

A pack misread as "not pack_format 1" is silently skipped, so a corpus run
would under-report — the same silent-skip failure mode as the validate stage
crash (docs/known-issues.md #6).
"""
import importlib.util, json, zipfile
from pathlib import Path
import pytest

TOOL = Path(__file__).parent.parent / "tools" / "run_corpus.py"


@pytest.fixture(scope="module")
def rc():
    spec = importlib.util.spec_from_file_location("run_corpus", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pack(tmp_path, name, mcmeta: bytes):
    z = tmp_path / name
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("pack.mcmeta", mcmeta)
    return z


def test_reads_a_plain_pack_format(rc, tmp_path):
    z = _pack(tmp_path, "a.zip", b'{"pack":{"pack_format":1}}')
    assert rc.pack_format(z) == 1


def test_reads_through_a_bom(rc, tmp_path):
    z = _pack(tmp_path, "b.zip", "﻿".encode() + b'{"pack":{"pack_format":1}}')
    assert rc.pack_format(z) == 1


def test_reads_through_a_stray_backslash(rc, tmp_path):
    """The same GSON-tolerated sloppiness the converter itself accepts."""
    z = _pack(tmp_path, "c.zip", b'{"pack":{"pack_format":1,"description":"\\ x"}}')
    assert rc.pack_format(z) == 1


def test_modern_pack_is_reported_not_guessed(rc, tmp_path):
    z = _pack(tmp_path, "d.zip", b'{"pack":{"pack_format":34}}')
    assert rc.pack_format(z) == 34


def test_unreadable_pack_returns_none(rc, tmp_path):
    z = tmp_path / "e.zip"
    z.write_bytes(b"not a zip")
    assert rc.pack_format(z) is None


def test_compare_flags_a_regression(rc, tmp_path, capsys):
    old = tmp_path / "old.jsonl"; new = tmp_path / "new.jsonl"
    old.write_text(json.dumps({"pack": "p", "findings": [
        {"stage": "x", "sev": "warning", "msg": "alpha"}]}) + "\n")
    new.write_text(json.dumps({"pack": "p", "findings": [
        {"stage": "x", "sev": "warning", "msg": "beta"},
        {"stage": "x", "sev": "warning", "msg": "beta"}]}) + "\n")
    rc.compare(old, new)
    out = capsys.readouterr().out
    assert "got WORSE" in out
