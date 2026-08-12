# mc_pack_converter/stages/pack_meta.py
from __future__ import annotations
import json
import time
from ..pipeline import ConversionContext, Severity, FatalConversionError
from ..data import INPUT_FORMAT, load_table
from ..mcmeta import read_mcmeta

def pack_meta(ctx: ConversionContext) -> None:
    meta = ctx.root / "pack.mcmeta"
    data = read_mcmeta(meta)
    new_fmt = load_table("pack_format").get(ctx.target)
    if not new_fmt:
        raise FatalConversionError(f"no pack_format for target {ctx.target}")
    old_fmt = data["pack"].get("pack_format")
    # Minecraft 1.21.9+ (all 26.x) replaced the single `pack_format` int with
    # `min_format`/`max_format`. Emitting the legacy field makes the pack show
    # as red "incompatible"; the modern fields make it compatible.
    #
    # Declare the whole supported RANGE, not a single point. Nothing outside
    # this file reads ctx.target — no stage produces different textures for
    # 26.1 than for 26.2 — so a pack converted to 26.2 really is valid on
    # 26.1.2 as well, and claiming only 88 made Minecraft 26.1.2 flag a pack
    # red that it then loaded and rendered perfectly (Mason, 2026-08-11).
    # max stays at the requested target so converting to an older one does
    # not over-claim.
    table = load_table("pack_format")
    oldest = min(v for k, v in table.items() if k != INPUT_FORMAT)
    data["pack"].pop("pack_format", None)
    data["pack"]["min_format"] = min(oldest, new_fmt)
    data["pack"]["max_format"] = new_fmt
    # Append a build tag to the description so the user can confirm in-game which
    # converted build they actually loaded (distinguishes a stale copy).
    base_desc = str(data["pack"].get("description", "")).split(" [conv ")[0]
    tag = f"{ctx.target} {time.strftime('%m%d-%H%M')}"
    data["pack"]["description"] = f"{base_desc} [conv {tag}]"
    meta.write_text(json.dumps(data, indent=2))
    ctx.add("pack_meta", Severity.INFO,
            f"pack_format {old_fmt} -> min/max_format {new_fmt} (modern schema); build tag {tag}")
