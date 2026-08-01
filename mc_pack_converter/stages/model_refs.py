"""Point model JSONs at where the textures actually ended up.

A 1.8.9 pack's models reference textures as `blocks/anvil_base` and
`items/apple`. Two earlier stages move those files: `restructure` renames
`textures/blocks` -> `textures/block` and `textures/items` -> `textures/item`,
and `flatten_rename` applies the 376 flattening renames on top. Nothing was
updating the references inside the models, so every block and item with a
custom model pointed at a path that no longer existed and drew the
missing-texture placeholder.

Found by in-game testing of `7[9bluefault7]`, which ships 1595 models: all 578
texture paths they referenced were missing from the output. 4 of the 170
in-scope corpus packs ship models with legacy paths, and for them the failure
is total rather than cosmetic.

Two rewrites happen here.

**Model `textures` values.** `parent` is deliberately left alone: it names
another MODEL, and the model folder layout did not change between 1.8.9 and
modern, so rewriting it would break working references.

**Blockstate `model` values.** 1.8.9 resolved these relative to `models/block/`,
so `"model": "oak_stairs"` meant `models/block/oak_stairs.json`. Modern requires
the full path (`minecraft:block/oak_stairs`), so a bare name sends it looking in
`models/` and it draws the missing model — a magenta cube. One corpus pack had
2596 references in that state, and prefixing resolves every one of them, because
a pack's blockstates reference the pack's own models.
"""
from __future__ import annotations
import json
from ..pipeline import ConversionContext, Severity
from ..data import load_table
from ..mcmeta import loads_lenient

_FOLDER = {"blocks": "block", "items": "item"}


def _rewrite_ref(ref: str, flat: dict[str, str]) -> str:
    """Map one texture reference onto its post-conversion path."""
    if not ref or ref.startswith("#"):
        return ref                      # '#side' points at another key, not a file
    ns, _, path = ref.rpartition(":")   # keep an optional 'minecraft:' prefix
    head, slash, tail = path.partition("/")
    if not slash or head not in _FOLDER:
        return ref                      # already modern, or not a folder we moved
    new_head = _FOLDER[head]
    renamed = flat.get(f"textures/{new_head}/{tail}.png")
    if renamed:
        tail = renamed.split("/", 1)[1].rsplit("/", 1)[1][:-4]
    out = f"{new_head}/{tail}"
    return f"{ns}:{out}" if ns else out


def _qualify_model(ref: str) -> str:
    """Give a bare blockstate model name its modern `block/` path."""
    if not isinstance(ref, str) or not ref:
        return ref
    ns, _, path = ref.rpartition(":")
    if "/" in path:
        return ref                      # already qualified
    out = f"block/{path}"
    return f"{ns}:{out}" if ns else out


def _qualify_entries(entry) -> bool:
    """Qualify `model` on a variant entry, or a list of them. True if changed."""
    changed = False
    for e in (entry if isinstance(entry, list) else [entry]):
        if isinstance(e, dict) and isinstance(e.get("model"), str):
            new = _qualify_model(e["model"])
            if new != e["model"]:
                e["model"] = new
                changed = True
    return changed


def _rewrite_blockstates(ctx: ConversionContext) -> int:
    rewrote = 0
    for states in (ctx.root / "assets").glob("*/blockstates"):
        for path in states.rglob("*.json"):
            try:
                data = loads_lenient(path.read_text(encoding="utf-8-sig"))
            except Exception as exc:
                ctx.add("model_refs", Severity.WARNING,
                        f"unparseable blockstate: {exc!r}",
                        str(path.relative_to(ctx.root)))
                continue
            if not isinstance(data, dict):
                continue
            changed = False
            for entry in (data.get("variants") or {}).values():
                changed |= _qualify_entries(entry)
            for part in (data.get("multipart") or []):
                if isinstance(part, dict) and "apply" in part:
                    changed |= _qualify_entries(part["apply"])
            if changed:
                path.write_text(json.dumps(data, indent=2))
                rewrote += 1
    return rewrote


def model_refs(ctx: ConversionContext) -> None:
    flat = load_table("flattening")
    rewrote = 0
    for models in (ctx.root / "assets").glob("*/models"):
        for path in models.rglob("*.json"):
            try:
                data = loads_lenient(path.read_text(encoding="utf-8-sig"))
            except Exception as exc:
                # Genuinely broken, not merely sloppy — loads_lenient already
                # tolerates the comments and stray escapes Minecraft accepts.
                ctx.add("model_refs", Severity.WARNING,
                        f"unparseable model: {exc!r}",
                        str(path.relative_to(ctx.root)))
                continue
            textures = data.get("textures") if isinstance(data, dict) else None
            if not isinstance(textures, dict):
                continue
            changed = False
            for key, ref in textures.items():
                if not isinstance(ref, str):
                    continue
                new = _rewrite_ref(ref, flat)
                if new != ref:
                    textures[key] = new
                    changed = True
            if changed:
                path.write_text(json.dumps(data, indent=2))
                rewrote += 1
    states = _rewrite_blockstates(ctx)
    ctx.add("model_refs", Severity.INFO,
            f"rewrote {rewrote} model files to the converted texture paths; "
            f"qualified model paths in {states} blockstates")
