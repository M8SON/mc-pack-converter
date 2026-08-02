"""Ship the scaling metadata that a resized GUI sprite needs.

Modern Minecraft draws many GUI sprites with nine-slice scaling, declared in a
`.mcmeta` beside the texture: `widget/button.png.mcmeta` says
`{"gui":{"scaling":{"type":"nine_slice","width":200,"height":20,"border":3}}}`
and vanilla's `button.png` is exactly 200x20. The metadata describes the
texture it sits beside.

A converted pack ships those sprites at its OWN resolution — 400x40 at 2x,
800x80 at 4x. Metadata is a separate resource, so a pack that overrides the
texture but not the `.mcmeta` keeps vanilla's, which still claims 200x20.
Nine-slice sampling against a texture several times that size fails, and the
sprite renders as the missing texture: magenta buttons, sliders, tabs and
toasts. It affected every pack above 1x — 72 of 170 in the test corpus — and
produced no warning, because nothing was wrong with the texture itself.

So for each sprite the pack actually overrides, rewrite the pixel fields by the
factor between the produced texture and vanilla's declared size, and write the
`.mcmeta` alongside it.
"""
from __future__ import annotations
import json
from ..pipeline import ConversionContext, Severity
from ..data import load_table
from ..imaging import png_size

SPRITES = "assets/minecraft/textures/gui/sprites"


def _scale_border(border, fx: float, fy: float):
    """Borders are an int (all edges) or a dict of named edges."""
    if isinstance(border, (int, float)):
        return max(1, round(border * min(fx, fy)))
    if isinstance(border, dict):
        horiz = ("left", "right")
        return {k: max(1, round(v * (fx if k in horiz else fy)))
                for k, v in border.items()}
    return border


def gui_scaling(ctx: ConversionContext) -> None:
    written = 0
    for name, scaling in load_table("gui_scaling")["scaling"].items():
        png = ctx.root / SPRITES / f"{name}.png"
        if not png.exists():
            continue
        try:
            size = png_size(png)
        except Exception:
            continue
        dw, dh = scaling.get("width"), scaling.get("height")
        if not size or not dw or not dh:
            continue
        w, h = size
        out = dict(scaling)
        out["width"], out["height"] = w, h
        if "border" in scaling:
            out["border"] = _scale_border(scaling["border"], w / dw, h / dh)
        png.with_name(png.name + ".mcmeta").write_text(
            json.dumps({"gui": {"scaling": out}}, indent=2))
        written += 1
    ctx.add("gui_scaling", Severity.INFO,
            f"wrote gui scaling metadata for {written} sprites")
