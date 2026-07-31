# tests/test_pack_meta.py
import json
import pytest
from mc_pack_converter.pipeline import ConversionContext, FatalConversionError
from mc_pack_converter.stages.pack_meta import pack_meta
from mc_pack_converter.data import load_table
import mc_pack_converter.stages.pack_meta as mod

def test_pack_meta_uses_modern_min_max_schema(mini_pack, monkeypatch):
    root = mini_pack()
    monkeypatch.setattr(mod, "load_table", lambda n: {"26.2": 99})
    ctx = ConversionContext(root=root, target="26.2")
    pack_meta(ctx)
    data = json.loads((root/"pack.mcmeta").read_text())
    # 26.x uses min_format/max_format; the legacy single pack_format is removed
    assert data["pack"]["min_format"] == 99
    assert data["pack"]["max_format"] == 99
    assert "pack_format" not in data["pack"]
    assert data["pack"]["description"].startswith("test")
    assert "[conv " in data["pack"]["description"]  # build tag for freshness check

def test_pack_format_26_2_is_real_value():
    assert load_table("pack_format")["26.2"] > 1

def test_pack_meta_unknown_target_raises_fatal_error(mini_pack, monkeypatch):
    root = mini_pack()
    monkeypatch.setattr(mod, "load_table", lambda n: {"26.2": 88})
    ctx = ConversionContext(root=root, target="99.9")
    with pytest.raises(FatalConversionError):
        pack_meta(ctx)


def test_pack_meta_reads_a_bom_prefixed_mcmeta(mini_pack):
    """Same BOM as test_ingest — this stage re-reads pack.mcmeta itself."""
    root = mini_pack()
    (root / "pack.mcmeta").write_text(
        "﻿" + '{"pack":{"pack_format":1,"description":"bom"}}',
        encoding="utf-8")
    ctx = ConversionContext(root=root, target="26.1.2")
    pack_meta(ctx)                                # must not raise
    data = json.loads((root / "pack.mcmeta").read_text())
    assert data["pack"]["min_format"] == 84
    assert "[conv 26.1.2 " in data["pack"]["description"]
