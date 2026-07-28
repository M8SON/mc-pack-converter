from __future__ import annotations
from pathlib import Path
from ..pipeline import ConversionContext, Severity

_EXACT = {"Thumbs.db", ".DS_Store", "desktop.ini"}

def _is_junk(name: str) -> bool:
    return (name.endswith(":Zone.Identifier")
            or name.endswith(".png~")
            or name in _EXACT)

def clean(ctx: ConversionContext) -> None:
    removed = 0
    for p in list(ctx.root.rglob("*")):
        if p.is_file() and _is_junk(p.name):
            p.unlink()
            removed += 1
    ctx.add("clean", Severity.INFO, f"removed {removed} junk files")
