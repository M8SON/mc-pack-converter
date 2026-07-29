# mc_pack_converter/stages/pack_meta.py
from __future__ import annotations
import json
import time
from ..pipeline import ConversionContext, Severity, FatalConversionError
from ..data import load_table

def pack_meta(ctx: ConversionContext) -> None:
    meta = ctx.root / "pack.mcmeta"
    data = json.loads(meta.read_text())
    new_fmt = load_table("pack_format").get(ctx.target)
    if not new_fmt:
        raise FatalConversionError(f"no pack_format for target {ctx.target}")
    old_fmt = data["pack"].get("pack_format")
    # Minecraft 1.21.9+ (all 26.x) replaced the single `pack_format` int with
    # `min_format`/`max_format`. Emitting the legacy field makes the pack show
    # as red "incompatible"; the modern fields make it compatible.
    data["pack"].pop("pack_format", None)
    data["pack"]["min_format"] = new_fmt
    data["pack"]["max_format"] = new_fmt
    # Append a build tag to the description so the user can confirm in-game which
    # converted build they actually loaded (distinguishes a stale copy).
    base_desc = str(data["pack"].get("description", "")).split(" [conv ")[0]
    tag = f"{ctx.target} {time.strftime('%m%d-%H%M')}"
    data["pack"]["description"] = f"{base_desc} [conv {tag}]"
    meta.write_text(json.dumps(data, indent=2))
    ctx.add("pack_meta", Severity.INFO,
            f"pack_format {old_fmt} -> min/max_format {new_fmt} (modern schema); build tag {tag}")
