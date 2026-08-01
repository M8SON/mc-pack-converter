"""GUI remap stage: realign GUI elements that Mojang repositioned between 1.8.9
and modern, preserving the pack's custom art (instead of dropping to vanilla).

Data-driven via data/gui_remap.json. Each "move" crops a region (proportional
to 'ref', so any resolution works), heals the vacated spot by filling it with
the pack's own background (sampled from a ring just outside the region — dominant
colour), then pastes the region at the new location. Sampling the background
makes this work for BOTH see-through inventories (fills transparent) and solid
panel inventories (fills the panel colour), rather than assuming transparency.

Currently: the survival inventory's 2x2 crafting grid + arrow + result, which
shifted (-10,+8) between 1.8.9 and modern (derived by matching Mojang's vanilla
1.8.9 vs modern inventory.png), so it lines up with the modern functional slots.
"""
from __future__ import annotations
from collections import Counter
from PIL import Image
from ..pipeline import ConversionContext, Severity
from ..data import load_table


def _sample_bg(img: Image.Image, box: tuple[int, int, int, int], m: int = 3):
    """Dominant colour of a ring just outside `box` — the local background."""
    x0, y0, x1, y1 = box
    w, h = img.size
    px = img.load()
    ring = []
    for x in range(max(0, x0 - m), min(w, x1 + m)):
        for y in range(max(0, y0 - m), y0):
            ring.append(px[x, y])
        for y in range(y1, min(h, y1 + m)):
            ring.append(px[x, y])
    for y in range(max(0, y0 - m), min(h, y1 + m)):
        for x in range(max(0, x0 - m), x0):
            ring.append(px[x, y])
        for x in range(x1, min(w, x1 + m)):
            ring.append(px[x, y])
    if not ring:
        return (0, 0, 0, 0)
    return Counter(ring).most_common(1)[0][0]


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
        rw, rh = spec["ref"]
        sw, sh = img.width / rw, img.height / rh
        for mv in spec.get("moves", []):
            fx, fy, fw, fh = mv["from"]
            tx, ty = mv["to"]
            box = (round(fx * sw), round(fy * sh), round((fx + fw) * sw), round((fy + fh) * sh))
            piece = img.crop(box)
            img.paste(_sample_bg(img, box), box)   # heal old spot with local background
            img.paste(piece, (round(tx * sw), round(ty * sh)))
        # A copy duplicates a region instead of relocating it: modern added a
        # slot where 1.8.9 has bare panel, and the pack's own slot art is the
        # only honest thing to put there. The source is left intact.
        for cp in spec.get("copies", []):
            fx, fy, fw, fh = cp["from"]
            tx, ty = cp["to"]
            piece = img.crop((round(fx * sw), round(fy * sh),
                              round((fx + fw) * sw), round((fy + fh) * sh)))
            img.paste(piece, (round(tx * sw), round(ty * sh)))
        img.save(p)
        count += 1
    ctx.add("gui_remap", Severity.INFO, f"remapped {count} gui textures (custom art preserved)")
