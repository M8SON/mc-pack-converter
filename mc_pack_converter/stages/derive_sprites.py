"""Derive sprites the slicer cannot cut correctly from a 1.8.9 atlas.

A slice record is a single sub-rectangle. That is enough whenever the modern
sprite exists somewhere in the 1.8.9 atlas as one rectangle — but not when
Mojang later reused a region for something else, or when the modern sprite has
no 1.8.9 counterpart at all and must be composed from pieces the pack does ship.

Data-driven via data/derived_sprites.json. Each entry names a source atlas, a
proportional `ref`, an output `size` in ref units, and the `pieces` to paste:

    {"from": [x, y, w, h], "to": [dstX, dstY]}     # all in ref units

Runs AFTER the slice stage and overwrites what it wrote, so a record the slicer
gets wrong for 1.8.9 input is corrected rather than gated — `slice.py` stays a
generic executor of Mojang's records and the version-specific knowledge lives
here, in the data layer, with the rest of it.

Currently: container/inventory/effect_background_small. 1.8.9 has one effect
panel, a 120x32 rounded box at (0,166); the 32x32 "small" variant is a later
Mojang addition with no 1.8.9 art. Mojang put it at (0,198) — the slot the
effect ICON grid vacated when 1.14 moved icons to mob_effect/*.png — so the
1.20.2 slicer record reads a 1.8.9 pack's icon strip and produces four potion
icons stitched together. Composing the small box from the large panel's left and
right 16 columns keeps the pack's own border art, including its corner notches.

Fix and format, never create art: every pixel written here is the pack's own.
"""
from __future__ import annotations
from PIL import Image
from ..pipeline import ConversionContext, Severity
from ..data import load_table


def derive_sprites(ctx: ConversionContext) -> None:
    made = 0
    for out_rel, spec in load_table("derived_sprites").items():
        if out_rel.startswith("_"):
            continue
        src = ctx.root / spec["source"]
        if not src.exists():
            continue
        dst = ctx.root / out_rel
        try:
            with Image.open(src) as im:
                im = im.convert("RGBA")
                rw, rh = spec["ref"]
                sw, sh = im.width / rw, im.height / rh
                ow, oh = spec["size"]
                canvas = Image.new("RGBA", (round(ow * sw), round(oh * sh)), (0, 0, 0, 0))
                for piece in spec["pieces"]:
                    x, y, w, h = piece["from"]
                    dx, dy = piece["to"]
                    part = im.crop((round(x * sw), round(y * sh),
                                    round((x + w) * sw), round((y + h) * sh)))
                    canvas.paste(part, (round(dx * sw), round(dy * sh)))
            if canvas.getchannel("A").getbbox() is None:
                # Every source piece was blank. Writing this would OVERRIDE
                # vanilla with an invisible sprite rather than fall back to it —
                # the defect in docs/known-issues.md #1, reachable here because
                # a pack's source region may be empty even when the file exists.
                ctx.add("derive_sprites", Severity.INFO,
                        "all source pieces empty; left to vanilla", out_rel)
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            canvas.save(dst)
            made += 1
        except Exception as exc:  # fail-soft per sprite, like the slice stage
            ctx.add("derive_sprites", Severity.WARNING,
                    f"derive failed: {exc!r}", out_rel)
    ctx.add("derive_sprites", Severity.INFO,
            f"derived {made} sprites from pieces the pack ships")
