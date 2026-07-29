"""GUI remap stage: rearrange GUI textures whose layout drifted between 1.8.9
and modern, preserving the pack's custom art (instead of dropping to vanilla).

Data-driven via data/gui_remap.json, using the same proportional per-region op
engine as the chest stage. Currently remaps the survival inventory (ported from
agentdid127/ResourcePackConverter InventoryConverter). Ops are proportional to
'ref', so any pack resolution works.
"""
from __future__ import annotations
from PIL import Image
from ..pipeline import ConversionContext, Severity
from ..data import load_table
from .chest import _apply


def gui_remap(ctx: ConversionContext) -> None:
    mc = ctx.root / "assets" / "minecraft"
    count = 0
    for rel, spec in load_table("gui_remap").items():
        if rel.startswith("_"):
            continue
        p = mc / rel
        if not p.exists():
            continue
        img = Image.open(p).convert("RGBA")
        ref = spec["ref"]
        _apply(img, spec["ops"], ref, tuple(ref)).save(p)
        count += 1
    ctx.add("gui_remap", Severity.INFO, f"remapped {count} gui textures (custom art preserved)")
