"""Repair, or drop, .mcmeta files Minecraft refuses to parse.

An unparseable .mcmeta is not a cosmetic problem. Minecraft throws while
building the atlas and DROPS THE WHOLE TEXTURE:

    ERROR: Unable to parse metadata from minecraft:item/ender_pearl
    com.google.gson.stream.MalformedJsonException: ... path $.animation.frames[13]
    WARN : Missing textures in model minecraft:item/ender_pearl

The converter used to detect exactly this and ship the file anyway with a
warning, which leaves the user to decide — the one thing the pack converter is
not supposed to do. Now it reaches a definite outcome: repair the file if the
damage is recoverable, otherwise drop the texture so vanilla renders instead.

Two recoverable defects, both common in hand-edited 1.8.9 packs and both purely
syntactic — no judgement about the pack's art:

- a trailing comma before ] or }, which gson rejects outright
- single-quoted values, which are Python/JS habits and not JSON
- a fractional `frametime`, where the animation codec requires an integer
- `interpolate` given as a string, where the codec requires a boolean

Dropping takes the .png with the .mcmeta on purpose. These files are animation
strips: a 512x9728 ender_pearl with no valid frame metadata is not a still
image, it is 19 frames stacked, and shipping it as one sprite would both look
wrong and drag the item atlas far out of shape.

Runs early, before the atlas stages read any of this metadata.
"""
from __future__ import annotations
import json
import re
from ..pipeline import ConversionContext, Severity

_TRAILING_COMMA = re.compile(r",(\s*[}\]])")
_SINGLE_QUOTED = re.compile(r"'([^'\"]*)'")


def _repair(text: str):
    """Return parsed data if the text can be made valid, else None."""
    fixed = _TRAILING_COMMA.sub(r"\1", text)
    fixed = _SINGLE_QUOTED.sub(r'"\1"', fixed)
    try:
        data = json.loads(fixed)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    anim = data.get("animation")
    if isinstance(anim, dict):
        # Quoting a value also changes its TYPE, and the animation codec is
        # strict: Conquest's `"interpolate": 'true'` becomes the string "true",
        # which is still not the boolean the codec wants.
        if isinstance(anim.get("frametime"), (float, str)):
            try:
                anim["frametime"] = max(1, round(float(anim["frametime"])))
            except (TypeError, ValueError):
                del anim["frametime"]
        if isinstance(anim.get("interpolate"), str):
            anim["interpolate"] = anim["interpolate"].strip().lower() == "true"
    return data


def repair_mcmeta(ctx: ConversionContext) -> None:
    mc = ctx.root / "assets" / "minecraft"
    if not mc.exists():
        return
    repaired = dropped = 0
    for meta in sorted(mc.rglob("*.png.mcmeta")):
        text = meta.read_text(encoding="utf-8", errors="replace")
        try:
            json.loads(text)
            continue                       # already valid, leave it alone
        except Exception:
            pass
        rel = str(meta.relative_to(mc))
        data = _repair(text)
        if data is None:
            png = meta.with_suffix("")     # foo.png.mcmeta -> foo.png
            meta.unlink()
            if png.exists():
                png.unlink()
            dropped += 1
            ctx.add("repair_mcmeta", Severity.WARNING,
                    "unrepairable mcmeta; dropped the texture to vanilla", rel)
        else:
            meta.write_text(json.dumps(data, indent=2) + "\n")
            repaired += 1
            ctx.add("repair_mcmeta", Severity.INFO, "repaired malformed mcmeta", rel)
    ctx.add("repair_mcmeta", Severity.INFO,
            f"repaired {repaired} mcmeta files; dropped {dropped}")
