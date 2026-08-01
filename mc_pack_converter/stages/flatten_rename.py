from __future__ import annotations
from ..pipeline import ConversionContext, Severity
from ..data import load_table

def _move(src, dst, ctx, note=None):
    dst.parent.mkdir(parents=True, exist_ok=True)
    # A stale .mcmeta on the target would outlive its texture, so clear it first.
    dst_meta = dst.with_name(dst.name + ".mcmeta")
    dst_meta.unlink(missing_ok=True)
    src.replace(dst)
    m = src.with_name(src.name + ".mcmeta")
    if m.exists():
        m.replace(dst_meta)
    ctx.add("flatten_rename", Severity.INFO, note or f"{src.name} -> {dst.name}")

def flatten_rename(ctx: ConversionContext) -> None:
    mc = ctx.root / "assets" / "minecraft"
    for old_rel, new_rel in load_table("flattening").items():
        old, new = mc / old_rel, mc / new_rel
        if not old.exists():
            continue
        if new.exists():
            # Some packs ship BOTH names. The source is pack_format 1, so the
            # 1.8.9 name is the file the game actually rendered and the author
            # maintained; the modern-named one is inert there — a leftover from
            # a newer edit of the pack. Preferring the modern name silently
            # dropped animated textures whose .mcmeta was attached to the old
            # name: 4OTF EUM3's fire shipped as one stretched still image
            # because fire_0.png had no .mcmeta while fire_layer_0.png did.
            _move(old, new, ctx,
                  note=f"{old.name} replaced {new.name} (pack ships both names; "
                       "the 1.8.9 name is the one it renders)")
            continue
        _move(old, new, ctx)
