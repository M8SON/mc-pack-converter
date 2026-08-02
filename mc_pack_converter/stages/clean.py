from __future__ import annotations
from pathlib import Path
from ..pipeline import ConversionContext, Severity

_EXACT = {"Thumbs.db", ".DS_Store", "desktop.ini"}

def _is_junk(name: str) -> bool:
    return (name.endswith(":Zone.Identifier")
            or name.endswith(".png~")
            or name in _EXACT
            or name.startswith("._"))


# `._foo.png` is an AppleDouble resource fork, written by macOS when a pack is
# zipped from a non-HFS volume. It carries the name of a real texture but its
# contents are a binary metadata blob, not a PNG. Left in place it is shipped as
# a texture the game cannot decode: 63 of the 64 'corrupt or empty png' errors
# across the 173-pack corpus were these, and one pack's `._pumpkinblur.png`
# even came with its own `._pumpkinblur.png.mcmeta`.

def clean(ctx: ConversionContext) -> None:
    removed = 0
    for p in list(ctx.root.rglob("*")):
        if p.is_file() and _is_junk(p.name):
            p.unlink()
            removed += 1
    ctx.add("clean", Severity.INFO, f"removed {removed} junk files")
