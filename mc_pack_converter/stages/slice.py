"""Slice stage: apply Mojang's official resource-pack slicer migration.

Splits legacy GUI atlases (widgets.png, icons.png, container/*, etc.) into the
modern per-file `gui/sprites/...` layout, using definitions extracted from
Mojang's open-source `slicer` tool (see tools/gen_slices.py -> data/slices.json).

Each record: {"input", "output", "box":[x,y,w,h,totalW,totalH], "op"}.
Boxes are proportional (scaled by totalW/totalH), so this works at any pack
resolution. Ops:
  crop  - write the proportional sub-rectangle as its own sprite
  copy  - relocate/keep the whole file (box is the full image)
  clip  - full-size canvas keeping only the box region (blank elsewhere)
  special - a slicer case using custom Java logic; skipped (recorded as a note)
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image
from ..pipeline import ConversionContext, Severity
from ..data import load_table


def _scaled_rect(box: list[int], w: int, h: int) -> tuple[int, int, int, int]:
    x, y, bw, bh, tw, th = box
    return (x * w // tw, y * h // th, bw * w // tw, bh * h // th)


def _copy_meta(src: Path, dst: Path) -> None:
    meta = src.with_name(src.name + ".mcmeta")
    if meta.exists():
        dst.with_name(dst.name + ".mcmeta").write_bytes(meta.read_bytes())


def slice_atlases(ctx: ConversionContext) -> None:
    root = ctx.root
    made = 0
    skipped_special = 0
    for rec in load_table("slices"):
        src = root / rec["input"]
        if not src.exists():
            continue
        dst = root / rec["output"]
        op = rec["op"]
        if op == "special":
            skipped_special += 1
            ctx.add("slice", Severity.WARNING,
                    f"slicer 'special' case not ported; sprite left to vanilla",
                    rec["output"])
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            if op == "copy":
                dst.write_bytes(src.read_bytes())
            else:
                with Image.open(src) as im:
                    im = im.convert("RGBA")
                    px, py, pw, ph = _scaled_rect(rec["box"], im.width, im.height)
                    sub = im.crop((px, py, px + pw, py + ph))
                    if op == "clip":
                        canvas = Image.new("RGBA", im.size, (0, 0, 0, 0))
                        canvas.paste(sub, (px, py))
                        canvas.save(dst)
                    else:  # crop
                        sub.save(dst)
            _copy_meta(src, dst)
            made += 1
        except Exception as exc:  # fail-soft per sprite
            ctx.add("slice", Severity.WARNING, f"slice failed: {exc!r}", rec["output"])
    ctx.add("slice", Severity.INFO,
            f"produced {made} gui sprites"
            + (f"; {skipped_special} special skipped" if skipped_special else ""))
