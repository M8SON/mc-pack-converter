"""Legacy-texture fixups ported from agentdid127/ResourcePackConverter:

- Water (WaterConverter1_13): modern Minecraft applies a biome tint to GRAYSCALE
  water, so a pre-coloured 1.8.9 water texture renders wrong-coloured. Grayscale
  water_still/water_flow/water_overlay so the tint works.
- Compass & clock (CompassConverter1_9): 1.8.9 shipped these as a single vertical
  animation strip (compass.png 16xN) + a .mcmeta. Modern items expect individual
  frame files (compass_00.png..compass_31.png, clock_00.png..clock_63.png). Split
  the strip into frames and drop the .mcmeta.

Runs after flatten_rename, so paths are already block/ and item/ (singular).
"""
from __future__ import annotations
from PIL import Image
from ..pipeline import ConversionContext, Severity

_GRAYSCALE = [
    "textures/block/water_still.png",
    "textures/block/water_flow.png",
    "textures/block/water_overlay.png",
]
_SPLIT = ["textures/item/compass.png", "textures/item/clock.png"]


def _grayscale_keep_alpha(img: Image.Image) -> Image.Image:
    r, g, b, a = img.split()
    gray = Image.merge("RGB", (r, g, b)).convert("L")
    return Image.merge("RGBA", (gray, gray, gray, a))


def legacy_textures(ctx: ConversionContext) -> None:
    mc = ctx.root / "assets" / "minecraft"
    water = 0
    for rel in _GRAYSCALE:
        p = mc / rel
        if p.exists():
            _grayscale_keep_alpha(Image.open(p).convert("RGBA")).save(p)
            water += 1
    frames = 0
    for rel in _SPLIT:
        p = mc / rel
        if not p.exists():
            continue
        img = Image.open(p).convert("RGBA")
        w, h = img.size
        if w == 0 or h <= w or h % w != 0:   # not a vertical animation strip
            continue
        name = p.stem
        for i in range(h // w):
            img.crop((0, i * w, w, (i + 1) * w)).save(p.with_name(f"{name}_{i:02d}.png"))
            frames += 1
        p.unlink()
        meta = p.with_name(p.name + ".mcmeta")
        if meta.exists():
            meta.unlink()
    ctx.add("legacy", Severity.INFO,
            f"grayscaled {water} water textures; split {frames} compass/clock frames")
