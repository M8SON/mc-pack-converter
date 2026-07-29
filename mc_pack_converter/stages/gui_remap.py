"""GUI remap stage: realign GUI elements that Mojang repositioned between 1.8.9
and modern, preserving the pack's custom art (instead of dropping to vanilla).

Data-driven via data/gui_remap.json. Each "move" crops a region (proportional
to 'ref', so any resolution works), clears the old location to transparent, and
pastes it at the new location. Currently: the survival inventory's 2x2 crafting
grid + result, which shifted (-10,+8) — derived by matching Mojang's vanilla
1.8.9 vs modern inventory.png — so it lines up with the modern functional slots.
"""
from __future__ import annotations
from PIL import Image
from ..pipeline import ConversionContext, Severity
from ..data import load_table


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
            img.paste((0, 0, 0, 0), box)          # clear old spot (transparent bg)
            img.paste(piece, (round(tx * sw), round(ty * sh)))
        img.save(p)
        count += 1
    ctx.add("gui_remap", Severity.INFO, f"remapped {count} gui textures (custom art preserved)")
