from __future__ import annotations
import re
from pathlib import Path
from ..pipeline import ConversionContext, Severity
from ..data import load_table

_NUMERIC_VALUE_RE = re.compile(r"^[\d\s]+$")

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

def _replace_match_line(text: str, key: str, value: str) -> str:
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            newline = "\n" if line.endswith("\n") else ""
            lines[i] = f"{key}={value}{newline}"
            break
    return "".join(lines)

def _fix_ctm(ctx: ConversionContext, ctm_dir: Path) -> None:
    table = load_table("ctm_blocks")
    for prop in ctm_dir.rglob("*.properties"):
        text = prop.read_text()
        props = parse_properties(text)
        if "method" not in props:
            continue
        folder = prop.parent.relative_to(ctm_dir).as_posix()
        block = table.get(folder) or table.get(prop.parent.name)
        match_key = "matchBlocks" if "matchBlocks" in props else (
            "matchTiles" if "matchTiles" in props else None)

        if match_key is None:
            if not block:
                ctx.add("optifine", Severity.WARNING,
                        f"no matchBlocks mapping for ctm folder '{folder}'", str(prop))
                continue
            prop.write_text(text.rstrip() + f"\nmatchBlocks={block}\n")
            ctx.add("optifine", Severity.INFO, f"ctm matchBlocks={block}", str(prop))
            continue

        value = props[match_key]
        if not _NUMERIC_VALUE_RE.match(value):
            continue  # already modern block names; idempotent no-op

        if not block:
            ctx.add("optifine", Severity.WARNING,
                    f"legacy numeric {match_key}='{value}' in ctm folder '{folder}' "
                    "has no modern mapping; left unchanged", str(prop))
            continue

        new_text = _replace_match_line(text, match_key, block)
        prop.write_text(new_text)
        ctx.add("optifine", Severity.INFO,
                f"ctm {match_key} translated from legacy numeric ids to {block}", str(prop))

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
