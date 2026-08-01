from __future__ import annotations
import re
from pathlib import Path
from ..pipeline import ConversionContext, Severity
from ..data import load_table

_NUMERIC_VALUE_RE = re.compile(r"^[\d\s]+$")

def read_properties_text(path) -> str:
    """Read a .properties file without exploding on its encoding.

    OptiFine .properties files in the wild are UTF-8 or ISO-8859-1. latin-1
    decodes any byte sequence, so this never raises — which matters because
    every caller only needs the ASCII keys (method, matchBlocks, source) and a
    decode error used to take down the whole enclosing stage.
    """
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def iter_properties(base):
    """Every real .properties file under `base`.

    Skips macOS AppleDouble sidecars ('._foo.properties'), which are binary
    resource forks that happen to match the glob.
    """
    return (p for p in base.rglob("*.properties") if not p.name.startswith("._"))


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
    for prop in iter_properties(sky_dir):
        text = read_properties_text(prop)
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

def _norm_folder(name: str) -> str:
    """Normalise a CTM folder name for table lookup.

    Pack authors spell the same folder as 'glass gray', 'glass_gray',
    'glass/Grey Glass' or 'Glass/Light Grey Glass'. Lowercasing and collapsing
    _ - / to single spaces makes those one key. data/ctm_blocks.json is
    generated with the same normalisation.
    """
    for ch in "_-/":
        name = name.replace(ch, " ")
    return " ".join(name.lower().split())


def _lookup_block(table: dict, folder: str, leaf: str,
                  prop_name: str | None = None) -> str | None:
    """Folder name first, then the properties filename.

    Folder order: the last path component before the whole relative path, since
    the leaf is the more specific signal ('hardened_clay_black' under
    'hardened_clay/stained/').

    The properties FILENAME is the last resort, and it is a real signal rather
    than a guess: old MCPatcher inferred the target from that filename when a
    file carried no matchBlocks, so terrain.png-era packs name them after the
    texture. 'cloth_15.properties' means black wool, and one folder often holds
    several colours ('wools-b-w' is black-through-white), which is exactly the
    case a folder-name lookup cannot resolve.

    Tried last so it can only ADD resolutions, never change one the folder name
    already made.
    """
    return (table.get(_norm_folder(leaf))
            or table.get(_norm_folder(folder))
            or (table.get(_norm_folder(prop_name)) if prop_name else None))


def _fix_ctm(ctx: ConversionContext, ctm_dir: Path) -> None:
    """Give every CTM folder a matchBlocks= line, without double-claiming a block.

    Two passes, because a folder cannot be judged alone. Packs commonly ship
    more than one folder aiming at the same block — a dormant `glass_gray`
    alongside the real `glass_stained/glass_gray`, or `glass` alongside
    `glass_clear`. Old MCPatcher tolerated that; modern OptiFine picks one
    arbitrarily, so writing both means the pack's glass renders with whichever
    art won the coin toss.

    Conflicts are only counted ACROSS folders. Several .properties inside one
    folder are complementary by design — different faces (melon.properties plus
    melon_top.properties) or different methods (bookshelf with horizontal and
    random) — and OptiFine applies them together. Treating those as rivals drops
    legitimate definitions; it accounted for 45 of 176 corpus conflicts.

    Rule: an EXPLICIT claim (the file names its own matchBlocks/matchTiles)
    beats an INFERRED one (we supplied it from the folder name). Where only
    inferred claims collide, the first by sorted path wins and the rest are
    reported — deterministic, and visible in the findings either way. That
    tiebreak is arbitrary among equals; nothing measurable in the corpus
    distinguishes the survivors, so it is at least stable and recorded.
    """
    table = load_table("ctm_blocks")["blocks"]
    entries = []
    for prop in sorted(iter_properties(ctm_dir)):
        text = read_properties_text(prop)
        props = parse_properties(text)
        if "method" not in props:
            continue
        folder = prop.parent.relative_to(ctm_dir).as_posix()
        block = _lookup_block(table, folder, prop.parent.name, prop.stem)
        match_key = ("matchBlocks" if "matchBlocks" in props else
                     "matchTiles" if "matchTiles" in props else None)
        entries.append((prop, text, props, folder, block, match_key))

    # what each file will end up claiming, and whether it said so itself
    explicit: dict[str, str] = {}          # block -> folder that named it
    for _, _, props, folder, block, match_key in entries:
        if match_key is None:
            continue
        value = props[match_key]
        claimed = block if _NUMERIC_VALUE_RE.match(value) else value
        for b in (claimed or "").split():
            explicit.setdefault(b, folder)

    taken_by_inferred: dict[str, str] = {}

    for prop, text, props, folder, block, match_key in entries:
        if match_key is None:
            if not block:
                ctx.add("optifine", Severity.WARNING,
                        f"no matchBlocks mapping for ctm folder '{folder}'", str(prop))
                continue
            clash = [b for b in block.split()
                     if explicit.get(b) not in (None, folder)]
            if clash:
                ctx.add("optifine", Severity.INFO,
                        f"ctm folder '{folder}' left alone; {' '.join(clash)} "
                        "already claimed by a folder that names it explicitly",
                        str(prop))
                continue
            dup = [b for b in block.split()
                   if taken_by_inferred.get(b) not in (None, folder)]
            if dup:
                ctx.add("optifine", Severity.WARNING,
                        f"ctm folder '{folder}' left alone; {' '.join(dup)} already "
                        f"claimed by '{taken_by_inferred[dup[0]]}'", str(prop))
                continue
            prop.write_text(text.rstrip() + f"\nmatchBlocks={block}\n")
            for b in block.split():
                taken_by_inferred[b] = folder
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

        prop.write_text(_replace_match_line(text, match_key, block))
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
