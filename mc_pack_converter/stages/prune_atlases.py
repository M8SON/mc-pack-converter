"""Prune legacy atlases that modern Minecraft no longer reads.

The slice stage cuts atlases like widgets.png, icons.png, particles.png and the
paintings sheet into per-sprite files. The sources then sit in the output doing
nothing: 26.x has no code path that loads them. Deleting them after slicing
keeps the converted pack honest about what it actually overrides — and in the
proving-ground pack reclaims ~620KB, over half of it icons.png and the paintings
atlas.

Membership in data/dead_atlases.json is a checked fact, not a judgement: each
path was requested from the version-pinned vanilla mirror at 1.21.4 and 404'd,
so modern vanilla does not ship it and nothing can load it from a pack either.

Runs after slice and derive_sprites, and never deletes a path the slice stage
wrote this run. That guard is load-bearing: three entries are also slicer
`copy()` outputs, where the record's input and output are the same path.
"""
from __future__ import annotations
from ..pipeline import ConversionContext, Severity
from ..data import load_table


def prune_atlases(ctx: ConversionContext) -> None:
    produced = {out for _, out in ctx.sliced}
    removed = 0
    freed = 0
    for rel in load_table("dead_atlases")["dead"]:
        full = f"assets/minecraft/{rel}"
        if full in produced:
            continue                       # the slicer wrote this; it is not dead
        p = ctx.root / full
        if not p.exists():
            continue
        try:
            freed += p.stat().st_size
            p.unlink()
            meta = p.with_name(p.name + ".mcmeta")
            if meta.exists():
                meta.unlink()
            removed += 1
        except OSError as exc:             # fail-soft; a leftover file is harmless
            ctx.add("prune_atlases", Severity.WARNING,
                    f"could not remove: {exc!r}", rel)
    ctx.add("prune_atlases", Severity.INFO,
            f"removed {removed} sliced-and-dead atlases ({freed // 1024} KB)")
