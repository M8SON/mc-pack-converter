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


def _dead_paths(dead: list[str]):
    """Each dead atlas, plus the misfiled block/ copy some packs also ship.

    9XethaFaith ships textures/blocks/widgets.png beside the real
    gui/widgets.png — an author's stray that restructure faithfully renames to
    block/widgets.png, where it sits in the block atlas doing nothing. Vanilla
    has no block texture by any of these names, so the copy is as unloadable as
    the original. Scoped to known atlas names on purpose: a pack's other custom
    block textures are referenced by its own models and must not be touched.
    """
    for rel in dead:
        yield rel
        if rel.startswith("textures/gui/") and rel.count("/") == 2:
            yield "textures/block/" + rel.rsplit("/", 1)[1]


def prune_atlases(ctx: ConversionContext) -> None:
    produced = {out for _, out in ctx.sliced}
    removed = 0
    freed = 0
    for rel in _dead_paths(load_table("dead_atlases")["dead"]):
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
    _prune_unloadable_gui(ctx, produced)


def _prune_unloadable_gui(ctx: ConversionContext, produced: set[str]) -> None:
    """Drop legacy gui/*.png at paths modern Minecraft has no code path to load.

    26.x moved most GUI art into gui/sprites/, but a handful of whole-texture
    paths survive (container backgrounds, the title screen, realms). Anything
    else under textures/gui/ outside gui/sprites/ is unreachable: 1.8.9 names
    Mojang retired — achievement/, options_background, title/mojang — and pack
    authors' own scratch copies, like the container/in2ventory.png and
    inven2tory.png that ship beside a real inventory.png in 9XethaFaith.

    data/vanilla_gui_legacy.json is the checked list, read out of the vanilla
    client jar rather than judged. Same standard as dead_atlases.json.
    """
    live = set(load_table("vanilla_gui_legacy")["live"])
    gui = ctx.root / "assets" / "minecraft" / "textures" / "gui"
    if not gui.exists():
        return
    removed = 0
    freed = 0
    for p in sorted(gui.rglob("*.png")):
        rel = p.relative_to(ctx.root / "assets" / "minecraft").as_posix()
        if rel.startswith("textures/gui/sprites/") or rel in live:
            continue
        if f"assets/minecraft/{rel}" in produced:
            continue                       # the slicer wrote this; it is not dead
        try:
            freed += p.stat().st_size
            p.unlink()
            meta = p.with_name(p.name + ".mcmeta")
            if meta.exists():
                meta.unlink()
            removed += 1
        except OSError as exc:
            ctx.add("prune_atlases", Severity.WARNING,
                    f"could not remove: {exc!r}", rel)
    if removed:
        ctx.add("prune_atlases", Severity.INFO,
                f"removed {removed} gui textures 26.x cannot load ({freed // 1024} KB)")
