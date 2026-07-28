# mc_pack_converter/stages/pack_meta.py
from __future__ import annotations
import json
from ..pipeline import ConversionContext, Severity, FatalConversionError
from ..data import load_table

def pack_meta(ctx: ConversionContext) -> None:
    meta = ctx.root / "pack.mcmeta"
    data = json.loads(meta.read_text())
    new_fmt = load_table("pack_format").get(ctx.target)
    if not new_fmt:
        raise FatalConversionError(f"no pack_format for target {ctx.target}")
    old_fmt = data["pack"].get("pack_format")
    data["pack"]["pack_format"] = new_fmt
    meta.write_text(json.dumps(data, indent=2))
    ctx.add("pack_meta", Severity.INFO, f"pack_format {old_fmt} -> {new_fmt}")
