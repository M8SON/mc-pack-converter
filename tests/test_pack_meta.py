# tests/test_pack_meta.py
import json
import pytest
from mc_pack_converter.pipeline import ConversionContext, FatalConversionError
from mc_pack_converter.stages.pack_meta import pack_meta
from mc_pack_converter.data import load_table
import mc_pack_converter.stages.pack_meta as mod

def test_pack_format_bumped(mini_pack, monkeypatch):
    root = mini_pack()
    monkeypatch.setattr(mod, "load_table", lambda n: {"26.2": 99})
    ctx = ConversionContext(root=root, target="26.2")
    pack_meta(ctx)
    data = json.loads((root/"pack.mcmeta").read_text())
    assert data["pack"]["pack_format"] == 99
    assert data["pack"]["description"] == "test"

def test_pack_format_26_2_is_real_value():
    assert load_table("pack_format")["26.2"] > 1

def test_pack_meta_unknown_target_raises_fatal_error(mini_pack, monkeypatch):
    root = mini_pack()
    monkeypatch.setattr(mod, "load_table", lambda n: {"26.2": 88})
    ctx = ConversionContext(root=root, target="99.9")
    with pytest.raises(FatalConversionError):
        pack_meta(ctx)
