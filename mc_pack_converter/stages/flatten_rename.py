from __future__ import annotations
from ..pipeline import ConversionContext, Severity
from ..data import load_table

def _move(src, dst, ctx):
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    # move sibling .mcmeta if present
    m = src.with_name(src.name + ".mcmeta")
    if m.exists():
        m.rename(dst.with_name(dst.name + ".mcmeta"))
    ctx.add("flatten_rename", Severity.INFO, f"{src.name} -> {dst.name}")

def flatten_rename(ctx: ConversionContext) -> None:
    mc = ctx.root / "assets" / "minecraft"
    for old_rel, new_rel in load_table("flattening").items():
        old, new = mc / old_rel, mc / new_rel
        if not old.exists():
            continue
        if new.exists():
            ctx.add("flatten_rename", Severity.WARNING,
                    f"target exists, skipping {old_rel}", str(old_rel))
            continue
        _move(old, new, ctx)
