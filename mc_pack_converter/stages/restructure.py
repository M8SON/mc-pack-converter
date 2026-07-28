from __future__ import annotations
from ..pipeline import ConversionContext, Severity

_RENAMES = [
    ("textures/blocks", "textures/block"),
    ("textures/items", "textures/item"),
    ("mcpatcher", "optifine"),
]

def restructure(ctx: ConversionContext) -> None:
    mc = ctx.root / "assets" / "minecraft"
    for old_rel, new_rel in _RENAMES:
        old, new = mc / old_rel, mc / new_rel
        if old.is_dir() and not new.exists():
            old.rename(new)
            ctx.add("restructure", Severity.INFO, f"{old_rel} -> {new_rel}")
