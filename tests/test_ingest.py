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


BOM = "﻿"


def test_ingest_reads_a_bom_prefixed_mcmeta(mini_pack):
    """Windows editors save pack.mcmeta with a UTF-8 BOM.

    5 of the 173 packs in the test corpus do. read_text() leaves the BOM in
    place and json.loads rejects it, which made the whole pack unconvertible.
    """
    root = mini_pack()
    (root / "pack.mcmeta").write_text(
        BOM + '{"pack":{"pack_format":1,"description":"bom"}}', encoding="utf-8")
    ctx = ConversionContext(root=root)
    ingest(ctx)                                   # must not raise
    assert any("pack_format=1" in f.message for f in ctx.findings)


def test_zip_with_a_directory_entry_stored_as_a_file(tmp_path):
    """Some packs' zips store 'a/b' with no trailing slash, then 'a/b/c.png'.

    extractall writes the first as a zero-length FILE and then dies with
    NotADirectoryError creating anything inside it. 2 of the 173 corpus packs
    are built this way (bPantone, #Pvpmen — both at textures/models/armor).
    """
    z = tmp_path / "pack.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("pack.mcmeta", '{"pack":{"pack_format":1,"description":"d"}}')
        zf.writestr("assets/minecraft/textures/models/armor", b"")   # no slash
        zf.writestr("assets/minecraft/textures/models/armor/iron_layer_1.png", b"x")
    work = tmp_path / "work"
    root = prepare_working_copy(z, work)                # must not raise
    assert (root / "assets/minecraft/textures/models/armor/iron_layer_1.png").exists()


def _pack_with_mcmeta(tmp_path, text):
    root = tmp_path / "pack"
    (root / "assets/minecraft/textures/blocks").mkdir(parents=True)
    (root / "pack.mcmeta").write_text(text)
    return root


def _run_ingest(root):
    from mc_pack_converter.pipeline import ConversionContext
    from mc_pack_converter.stages.ingest import ingest
    ctx = ConversionContext(root=root, target="26.2")
    ingest(ctx)
    return ctx


def test_a_pack_with_no_pack_format_is_converted_anyway(tmp_path):
    """Mason hit this on a real pack: pack.mcmeta had a pack block with no
    pack_format, and the converter refused the whole pack with a KeyError
    dressed up as a fatal error. Refusing over one missing field is the wrong
    trade -- the same one mcmeta.py already declined to make."""
    from mc_pack_converter.pipeline import Severity
    root = _pack_with_mcmeta(tmp_path, '{"pack":{"description":"my pack"}}')
    ctx = _run_ingest(root)
    warns = [f for f in ctx.findings if f.severity is Severity.WARNING]
    assert any("no usable pack_format" in f.message for f in warns)
    assert any("detected pack_format=1" in f.message for f in ctx.findings)


def test_a_quoted_pack_format_is_read_as_a_number(tmp_path):
    ctx = _run_ingest(_pack_with_mcmeta(tmp_path, '{"pack":{"pack_format":"1"}}'))
    assert any("detected pack_format=1" in f.message for f in ctx.findings)


def test_a_missing_pack_block_is_survivable(tmp_path):
    ctx = _run_ingest(_pack_with_mcmeta(tmp_path, '{"description":"no pack block"}'))
    assert any("detected pack_format=1" in f.message for f in ctx.findings)


def test_a_real_pack_format_is_still_honoured(tmp_path):
    from mc_pack_converter.pipeline import Severity
    ctx = _run_ingest(_pack_with_mcmeta(tmp_path, '{"pack":{"pack_format":34}}'))
    assert any("detected pack_format=34" in f.message for f in ctx.findings)
    assert any("may already be converted" in f.message
               for f in ctx.findings if f.severity is Severity.WARNING)


def test_a_structurally_broken_mcmeta_is_still_fatal(tmp_path):
    """Leniency has a limit: garbage is still garbage."""
    import pytest
    from mc_pack_converter.pipeline import FatalConversionError
    root = _pack_with_mcmeta(tmp_path, '{"pack": ')
    with pytest.raises(FatalConversionError):
        _run_ingest(root)
