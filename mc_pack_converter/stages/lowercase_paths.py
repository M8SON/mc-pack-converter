"""Lowercase resource paths, because Minecraft refuses the rest.

A ResourceLocation must match `[a-z0-9_.-/]`. A file whose path contains a
capital letter is rejected by the loader outright, so its art silently never
appears — no warning to the player, and nothing wrong with the file itself.

1.8.9 packs are full of them: `unicode_page_0A.png` was the vanilla spelling
back then, and pack authors leave `tripWire.png` or `cobblestone_mossyOLD.png`
lying around. 130 of the 170 in-scope corpus packs ship at least one; the worst
ships 172, including 49 block textures that simply never load.

**The OptiFine trees are deliberately excluded.** OptiFine loads
`optifine/` and `mcpatcher/` itself rather than through Minecraft's resource
manager, and its `.properties` files reference tiles by name — lowercasing a
folder there would break references this converter has just spent effort
getting right.

Runs before `restructure`, so every later stage sees paths it can match: the
flattening table and the slice records are all lowercase.
"""
from __future__ import annotations
from ..pipeline import ConversionContext, Severity

# Trees Minecraft itself loads. Everything else under assets/ is left alone.
_MANAGED = ("textures", "models", "blockstates", "sounds", "lang", "font",
            "particles", "shaders", "texts")
_SKIP = ("optifine", "mcpatcher")


def _managed(rel_parts: tuple[str, ...]) -> bool:
    """rel_parts is the path under assets/<namespace>/."""
    if not rel_parts:
        return False
    head = rel_parts[0]
    return head not in _SKIP and head in _MANAGED


def lowercase_paths(ctx: ConversionContext) -> None:
    assets = ctx.root / "assets"
    if not assets.is_dir():
        return
    renamed = 0
    dropped = 0
    # Deepest first, so a file moves before the directory holding it does.
    for path in sorted(assets.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        try:
            rel = path.relative_to(assets).parts
        except ValueError:
            continue
        if len(rel) < 2 or not _managed(rel[1:]):
            continue
        if path.name == path.name.lower():
            continue
        target = path.with_name(path.name.lower())
        if target.exists():
            if path.is_dir():
                # Both spellings of a folder ship. Merge into the lowercase one
                # rather than skip, or everything under the capitalised folder
                # stays unreachable. Files already handled deeper in this loop.
                for child in list(path.iterdir()):
                    dest = target / child.name
                    if dest.exists():
                        if child.is_file():
                            child.unlink()
                            dropped += 1
                    else:
                        child.rename(dest)
                if not any(path.iterdir()):
                    path.rmdir()
                    renamed += 1
                continue
            # Both spellings of a file ship. The lowercase one is what Minecraft
            # loads today, so it wins and the unreachable variant goes.
            path.unlink()
            dropped += 1
            ctx.add("lowercase_paths", Severity.WARNING,
                    f"dropped '{path.name}': '{target.name}' already exists and "
                    "is the one Minecraft can load",
                    str(path.relative_to(ctx.root)))
            continue
        path.rename(target)
        renamed += 1
    ctx.add("lowercase_paths", Severity.INFO,
            f"lowercased {renamed} paths Minecraft would otherwise refuse"
            + (f"; dropped {dropped} unreachable case-variants" if dropped else ""))
