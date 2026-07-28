from __future__ import annotations
from pathlib import Path
from ..pipeline import ConversionContext, Severity
from ..data import load_table

def parse_properties(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out

def _check_sky(ctx: ConversionContext, sky_dir: Path) -> None:
    for prop in sky_dir.rglob("*.properties"):
        props = parse_properties(prop.read_text())
        src = props.get("source")
        if not src:
            continue
        target = (prop.parent / src).resolve()
        if not target.exists():
            ctx.add("optifine", Severity.WARNING,
                    f"sky source missing: {src}", str(prop))

def _fix_ctm(ctx: ConversionContext, ctm_dir: Path) -> None:
    table = load_table("ctm_blocks")
    for prop in ctm_dir.rglob("*.properties"):
        text = prop.read_text()
        props = parse_properties(text)
        if "matchBlocks" in props or "matchTiles" in props:
            continue
        folder = prop.parent.relative_to(ctm_dir).as_posix()
        block = table.get(folder) or table.get(prop.parent.name)
        if not block:
            ctx.add("optifine", Severity.WARNING,
                    f"no matchBlocks mapping for ctm folder '{folder}'", str(prop))
            continue
        prop.write_text(text.rstrip() + f"\nmatchBlocks={block}\n")
        ctx.add("optifine", Severity.INFO, f"ctm matchBlocks={block}", str(prop))

def optifine_translate(ctx: ConversionContext) -> None:
    of = ctx.root / "assets" / "minecraft" / "optifine"
    if not of.is_dir():
        return
    sky = of / "sky"
    if sky.is_dir():
        _check_sky(ctx, sky)
    ctm = of / "ctm"
    if ctm.is_dir():
        _fix_ctm(ctx, ctm)
