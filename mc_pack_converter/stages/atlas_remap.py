from __future__ import annotations
from ..pipeline import ConversionContext, Severity
from ..data import load_table
from ..imaging import crop_paste


def atlas_remap(ctx: ConversionContext) -> None:
    mc = ctx.root / "assets" / "minecraft"
    for rel, spec in load_table("region_remap").items():
        asset = mc / rel
        if not asset.exists():
            continue
        tmp = asset.with_suffix(".remap.png")
        crop_paste(asset, tmp, spec["regions"], tuple(spec["out_size"]))
        tmp.replace(asset)
        ctx.add("atlas_remap", Severity.INFO, f"remapped {rel}", rel)
