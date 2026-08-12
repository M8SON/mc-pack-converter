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


def test_declared_range_spans_every_target_the_converter_supports():
    """One output, valid on every modern version this tool targets.

    Nothing but pack_meta reads ctx.target — no stage produces different
    textures for 26.1 than for 26.2 — so a pack converted to 26.2 is
    genuinely byte-identical to one converted to 26.1 apart from this file.
    Declaring min_format 84 / max_format 88 is therefore the truth, not a
    fudge, and it stops Minecraft 26.1.2 flagging a 26.2 pack as
    incompatible (red) when it loads and renders it perfectly.
    """
    from mc_pack_converter.data import INPUT_FORMAT
    table = load_table("pack_format")
    targets = {k: v for k, v in table.items() if k != INPUT_FORMAT}
    assert min(targets.values()) == 84
    assert max(targets.values()) == 88


def test_pack_meta_declares_the_oldest_target_as_min(mini_pack):
    root = mini_pack()
    ctx = ConversionContext(root=root, target="26.2")
    pack_meta(ctx)
    data = json.loads((root / "pack.mcmeta").read_text())
    assert data["pack"]["min_format"] == 84   # 26.1 / 26.1.2
    assert data["pack"]["max_format"] == 88   # 26.2


def test_pack_meta_never_declares_a_max_below_its_min(mini_pack):
    """Converting to the OLDEST target must not invert the range."""
    root = mini_pack()
    ctx = ConversionContext(root=root, target="26.1")
    pack_meta(ctx)
    data = json.loads((root / "pack.mcmeta").read_text())
    assert data["pack"]["min_format"] == 84
    assert data["pack"]["max_format"] == 84

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
