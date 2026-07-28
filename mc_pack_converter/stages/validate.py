from __future__ import annotations
import json
from ..pipeline import ConversionContext, Severity
from ..imaging import is_valid_png, png_size
from .optifine import parse_properties

def _check_pngs(ctx, mc):
    for png in mc.rglob("*.png"):
        if not is_valid_png(png):
            ctx.add("validate", Severity.ERROR, "corrupt or empty png",
                    str(png.relative_to(mc)))

def _check_mcmeta(ctx, mc):
    for meta in mc.rglob("*.png.mcmeta"):
        try:
            data = json.loads(meta.read_text())
        except Exception:
            ctx.add("validate", Severity.WARNING, "unparseable mcmeta",
                    str(meta.relative_to(mc)))
            continue
        if "animation" not in data:
            continue
        png = meta.with_suffix("")  # drop .mcmeta -> foo.png
        if not png.exists():
            continue
        w, h = png_size(png)
        # square-frame assumption: frame height == width; height must be a multiple
        if w and h % w != 0:
            ctx.add("validate", Severity.WARNING,
                    f"animation frame height mismatch ({w}x{h})",
                    str(png.relative_to(mc)))

def _check_optifine(ctx, mc):
    of = mc / "optifine"
    if not of.is_dir():
        return
    for prop in of.rglob("*.properties"):
        props = parse_properties(prop.read_text())
        src = props.get("source")
        if src and not (prop.parent / src).resolve().exists():
            ctx.add("validate", Severity.WARNING, f"missing source {src}",
                    str(prop.relative_to(mc)))

def validate(ctx: ConversionContext) -> None:
    mc = ctx.root / "assets" / "minecraft"
    if not mc.is_dir():
        return
    _check_pngs(ctx, mc)
    _check_mcmeta(ctx, mc)
    _check_optifine(ctx, mc)
