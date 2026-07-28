# tests/test_ingest.py
import json, pytest, zipfile
from pathlib import Path
from mc_pack_converter.pipeline import ConversionContext, Severity, FatalConversionError
from mc_pack_converter.stages.ingest import ingest, prepare_working_copy

def test_ingest_accepts_format_1(mini_pack):
    root = mini_pack()
    ctx = ConversionContext(root=root)
    ingest(ctx)
    assert any(f.severity is Severity.INFO for f in ctx.findings)

def test_ingest_rejects_non_pack(tmp_path):
    ctx = ConversionContext(root=tmp_path)
    with pytest.raises(FatalConversionError):
        ingest(ctx)

def test_prepare_working_copy_from_folder(mini_pack, tmp_path):
    root = mini_pack()
    work = tmp_path/"work"
    out = prepare_working_copy(root, work)
    assert (out/"pack.mcmeta").exists()

def test_zip_slip_rejected(tmp_path):
    zip_path = tmp_path/"evil.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("pack.mcmeta", '{"pack":{"pack_format":1}}')
        zf.writestr("../evil.txt", "pwned")
    work = tmp_path/"work"
    with pytest.raises(FatalConversionError):
        prepare_working_copy(zip_path, work)
    assert not (tmp_path/"evil.txt").exists()
