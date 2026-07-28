"""Drop stage: remove textures that cannot survive the version jump, so modern
Minecraft falls back to its own correct rendering.

Currently the 1.8.9 chest textures: Mojang rearranged the chest model's UV faces
between 1.8.9 and modern (verified — the texture content moved while the alpha
silhouette stayed identical), so an unmodified 1.8.9 chest texture mis-maps
(e.g. a dark square on the lid top). A full per-face remap is complex; dropping
these yields a correct chest and is ideal for faithful-style packs. The drop
list lives in data/drop_list.json so it can be curated without code changes.
"""
from __future__ import annotations
from ..pipeline import ConversionContext, Severity
from ..data import load_table


def drop_textures(ctx: ConversionContext) -> None:
    mc = ctx.root / "assets" / "minecraft"
    dropped = 0
    for rel in load_table("drop_list").get("drop", []):
        p = mc / rel
        if p.exists():
            p.unlink()
            dropped += 1
    ctx.add("drop", Severity.INFO,
            f"dropped {dropped} version-incompatible textures (chest -> vanilla fallback)")
