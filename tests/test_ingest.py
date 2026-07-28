# tests/test_ingest.py
import json, pytest
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
