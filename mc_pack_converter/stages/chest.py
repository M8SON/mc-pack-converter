"""Chest remap stage: rearrange 1.8.9 chest textures to the modern chest model's
UV layout, and split old 128x64 double-chest textures into modern _left/_right.

The chest model was re-unwrapped in 1.15, so a 1.8.9 chest texture mis-maps
(dark square on the lid). This ports the per-face remap from the open-source
agentdid127/ResourcePackConverter (ChestConverter1_15) via data/chest_remap.json,
preserving the pack's custom chest art. Ops are proportional so any resolution
works. Applied only to power-of-two textures (matching the reference), else the
texture is left untouched.
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image
from ..pipeline import ConversionContext, Severity
from ..data import load_table

_FLIP = {"v": Image.FLIP_TOP_BOTTOM, "180": Image.ROTATE_180}


def _pow2(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def _apply(src: Image.Image, ops: list, ref: list, out_ref=(64, 64)) -> Image.Image:
    sw = src.width / ref[0]
    sh = src.height / ref[1]
    out = Image.new("RGBA", (round(out_ref[0] * sw), round(out_ref[1] * sh)), (0, 0, 0, 0))
    for x1, y1, x2, y2, dx, dy, flip in ops:
        part = src.crop((round(x1 * sw), round(y1 * sh), round(x2 * sw), round(y2 * sh)))
        if flip:
            part = part.transpose(_FLIP[flip])
        out.paste(part, (round(dx * sw), round(dy * sh)))
    return out


def chest_remap(ctx: ConversionContext) -> None:
    base = ctx.root / "assets" / "minecraft" / "textures" / "entity" / "chest"
    if not base.is_dir():
        return
    cfg = load_table("chest_remap")
    single, double = cfg["single"], cfg["double"]
    count = 0
    for name in ("normal", "trapped", "christmas", "ender"):
        p = base / f"{name}.png"
        if not p.exists():
            continue
        img = Image.open(p).convert("RGBA")
        if not (_pow2(img.width) and _pow2(img.height)):
            continue
        _apply(img, single["ops"], single["ref"]).save(p)
        count += 1
    for name in ("normal", "trapped", "christmas"):
        p = base / f"{name}_double.png"
        if not p.exists():
            continue
        img = Image.open(p).convert("RGBA")
        if not (_pow2(img.width) and _pow2(img.height)):
            continue
        _apply(img, double["left"], double["ref"]).save(base / f"{name}_left.png")
        _apply(img, double["right"], double["ref"]).save(base / f"{name}_right.png")
        p.unlink()
        count += 2
    ctx.add("chest", Severity.INFO, f"remapped {count} chest textures to modern UV")
