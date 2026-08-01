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

Only the values inside a model's `textures` map are rewritten. `parent` names
another MODEL, and the model folder layout (`models/block/...`) did not change
between 1.8.9 and modern, so touching it would break working references.
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
    ctx.add("model_refs", Severity.INFO,
            f"rewrote {rewrote} model files to the converted texture paths")
