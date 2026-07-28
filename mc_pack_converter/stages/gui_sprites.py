from __future__ import annotations
import json
from ..pipeline import ConversionContext, Severity
from ..data import load_table
from ..imaging import slice_sheet

def gui_sprites(ctx: ConversionContext) -> None:
    mc = ctx.root / "assets" / "minecraft"
    for sheet_rel, spec in load_table("gui_sprites").items():
        sheet = mc / sheet_rel
        if not sheet.exists():
            continue
        out_dir = mc / spec["dir"]
        slice_sheet(sheet, out_dir, spec["sprites"])
        for name, border in spec.get("ninepatch", {}).items():
            meta = out_dir / f"{name}.png.mcmeta"
            l, t, r, b = border
            meta.write_text(json.dumps({
                "gui": {"scaling": {"type": "nine_slice",
                        "width": 0, "height": 0,
                        "border": {"left": l, "top": t, "right": r, "bottom": b}}}
            }, indent=2))
        ctx.add("gui_sprites", Severity.INFO,
                f"sliced {sheet_rel} -> {len(spec['sprites'])} sprites")
