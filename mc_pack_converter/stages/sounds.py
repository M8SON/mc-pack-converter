from __future__ import annotations
from ..pipeline import ConversionContext, Severity
from ..data import load_table

def sounds(ctx: ConversionContext) -> None:
    base = ctx.root / "assets" / "minecraft" / "sounds"
    if not base.is_dir():
        return
    for old_rel, new_rel in load_table("sound_map").items():
        old, new = base / old_rel, base / new_rel
        if not old.exists() or new.exists():
            continue
        new.parent.mkdir(parents=True, exist_ok=True)
        old.rename(new)
        ctx.add("sounds", Severity.INFO, f"{old_rel} -> {new_rel}")
