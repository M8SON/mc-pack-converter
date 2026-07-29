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

def _opaque_black_fraction(path: Path) -> float:
    """Fraction of pixels that are opaque AND near-black (downsampled estimate)."""
    from PIL import Image
    try:
        with Image.open(path) as im:
            im = im.convert("RGBA")
            im.thumbnail((128, 128))
            data = im.tobytes()
    except Exception:
        return 0.0
    n = len(data) // 4
    if n == 0:
        return 0.0
    black = sum(1 for i in range(0, len(data), 4)
                if data[i + 3] > 250 and max(data[i], data[i + 1], data[i + 2]) < 30)
    return black / n


def _check_sky(ctx: ConversionContext, sky_dir: Path) -> None:
    for prop in sky_dir.rglob("*.properties"):
        text = prop.read_text()
        props = parse_properties(text)
        src = props.get("source")
        if not src:
            continue
        target = (prop.parent / src).resolve()
        if not target.exists():
            # A sky layer pointing at a missing image renders as the magenta
            # missing-texture. Remove the broken layer so the rest of the sky
            # still shows (the source file is absent from the pack itself).
            prop.unlink()
            ctx.add("optifine", Severity.INFO,
                    f"removed sky layer with missing source {src}", str(prop))
            continue
        # blend=replace with a fully-opaque texture that has large black regions
        # paints a black square over the sky. Switch to blend=add so black
        # becomes invisible while bright pixels (clouds/stars) still show.
        if props.get("blend") == "replace" and _opaque_black_fraction(target) > 0.10:
            prop.write_text(re.sub(r"(?m)^\s*blend\s*=\s*replace\s*$", "blend=add", text))
            ctx.add("optifine", Severity.INFO,
                    f"sky {prop.name}: blend replace->add (opaque-black {src})", str(prop))

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
