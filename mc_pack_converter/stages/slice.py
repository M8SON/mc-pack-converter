"""Slice stage: apply Mojang's official resource-pack slicer migration.

Splits legacy atlases (widgets.png, icons.png, container/*, particles.png,
paintings, entity/explosion.png, etc.) into the modern per-file
`gui/sprites/...` / `particle/...` / `painting/...` layout, using definitions
extracted from Mojang's open-source `slicer` tool (see tools/gen_slices.py ->
data/slices.json).

Each record: {"input", "output", "box":[x,y,w,h,totalW,totalH], "op"}.
Boxes are proportional (scaled by totalW/totalH), so this works at any pack
resolution. Ops:
  crop  - write the proportional sub-rectangle as its own sprite
  copy  - relocate/keep the whole file (box is the full image)
  clip  - full-size canvas keeping only the box region (blank elsewhere)
  special - a slicer case using custom Java logic; skipped (recorded as a note)
"""
from __future__ import annotations
import json
from pathlib import Path
from PIL import Image
from ..pipeline import ConversionContext, Severity
from ..data import load_table

PARTICLES_PNG = "assets/minecraft/textures/particle/particles.png"


def _scaled_rect(box: list[int], w: int, h: int) -> tuple[int, int, int, int]:
    x, y, bw, bh, tw, th = box
    return (x * w // tw, y * h // th, bw * w // tw, bh * h // th)


def _is_empty(im: Image.Image) -> bool:
    """True if the region has no visible pixels.

    A 1.8.9 atlas has nothing where sprites added in later versions live.
    Writing that empty region out would OVERRIDE vanilla's sprite rather than
    fall back to it, making the element invisible in-game.

    Alpha-only by design: an atlas with no alpha channel converts to fully
    opaque, so a blank region there would NOT be caught here and would ship
    as opaque black over vanilla. That gap is accepted, not an oversight —
    real 1.8.9 atlases in scope always carry alpha, and broadening this to a
    "uniform colour" check would wrongly suppress legitimate solid-colour
    sprites.
    """
    if im.width == 0 or im.height == 0:
        return True
    return im.getchannel("A").getbbox() is None


def _pack_format(root: Path) -> int | None:
    """Read pack_format from pack.mcmeta; None if missing or unparseable.

    None means "not gated" — never a new failure path for this check. That
    fail-open is why the encoding matters here: a BOM (common from Windows
    editors) used to land in this except branch and silently ungate a 1.13+
    pack, which is exactly the mis-cut docs/known-issues.md #0 guards against.
    """
    try:
        return json.loads((root / "pack.mcmeta").read_text(
            encoding="utf-8-sig"))["pack"]["pack_format"]
    except Exception:
        return None


def _copy_meta(src: Path, dst: Path) -> None:
    meta = src.with_name(src.name + ".mcmeta")
    if meta.exists():
        dst.with_name(dst.name + ".mcmeta").write_bytes(meta.read_bytes())


def slice_atlases(ctx: ConversionContext) -> None:
    root = ctx.root
    made = 0
    skipped_special = 0
    left_to_vanilla = 0
    fmt = _pack_format(root)
    gate_particles = fmt is not None and fmt >= 4
    warned_particles_gate = False
    for rec in load_table("slices"):
        src = root / rec["input"]
        if not src.exists():
            continue
        if gate_particles and rec["input"] == PARTICLES_PNG:
            if not warned_particles_gate:
                ctx.add("slice", Severity.WARNING,
                        f"pack_format {fmt} declares a 1.13+ pack; its "
                        "particles.png is a 256x256 atlas with 8px cells at "
                        "the same layout as 1.8.9 (the canvas grew, cells did "
                        "not scale up), so the 128,128-referenced particle "
                        "boxes would mis-cut it into wrong-rectangle sprites; "
                        "skipping particles.png, sprites fall back to vanilla",
                        rec["input"])
                warned_particles_gate = True
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
                    if _is_empty(sub):
                        left_to_vanilla += 1
                        ctx.add("slice", Severity.INFO,
                                "source region empty; left to vanilla", rec["output"])
                        continue
                    if op == "clip":
                        canvas = Image.new("RGBA", im.size, (0, 0, 0, 0))
                        canvas.paste(sub, (px, py))
                        canvas.save(dst)
                    else:  # crop
                        sub.save(dst)
            _copy_meta(src, dst)
            ctx.sliced.append((rec["input"], rec["output"]))
            made += 1
        except Exception as exc:  # fail-soft per sprite
            ctx.add("slice", Severity.WARNING, f"slice failed: {exc!r}", rec["output"])
    ctx.add("slice", Severity.INFO,
            f"produced {made} sprites"
            + (f"; {left_to_vanilla} left to vanilla (empty source region)"
               if left_to_vanilla else "")
            + (f"; {skipped_special} special skipped" if skipped_special else ""))
