from __future__ import annotations
import shutil, zipfile
from pathlib import Path
from ..pipeline import ConversionContext, Severity, FatalConversionError
from ..mcmeta import read_mcmeta

# 1.8.9's pack_format. What this converter is built to read, and so what a
# pack that declares nothing is taken to be.
ASSUMED_FORMAT = 1

def _find_pack_root(base: Path) -> Path:
    if (base / "pack.mcmeta").exists():
        return base
    for child in base.iterdir():
        if child.is_dir() and (child / "pack.mcmeta").exists():
            return child
    return base

def _check_no_zip_slip(zf: zipfile.ZipFile, workdir: Path) -> None:
    base = workdir.resolve()
    for member in zf.infolist():
        target = (workdir / member.filename).resolve()
        if target != base and base not in target.parents:
            raise FatalConversionError(
                f"zip entry escapes working dir: {member.filename}")

def _dirs_stored_as_files(zf: zipfile.ZipFile) -> set[str]:
    """Entry names that other entries treat as a directory.

    Some packs' zips store a directory without its trailing slash, e.g.
    'assets/minecraft/textures/models/armor' alongside '.../armor/iron_layer_1.png'.
    extractall writes the first as a zero-length FILE and then dies with
    NotADirectoryError creating anything inside it. Extracting these entries is
    never useful — the real content is the members underneath them.
    """
    names = {i.filename.rstrip("/") for i in zf.infolist()}
    parents: set[str] = set()
    for n in names:
        parts = n.split("/")
        for k in range(1, len(parts)):
            parents.add("/".join(parts[:k]))
    return names & parents


def prepare_working_copy(source: Path, workdir: Path) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)
    if source.is_file() and source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as zf:
            _check_no_zip_slip(zf, workdir)
            shadowed = _dirs_stored_as_files(zf)
            for member in zf.infolist():
                if (not member.filename.endswith("/")
                        and member.filename.rstrip("/") in shadowed):
                    continue
                zf.extract(member, workdir)
        return _find_pack_root(workdir)
    dest = workdir / source.name
    shutil.copytree(source, dest)
    return _find_pack_root(dest)

def ingest(ctx: ConversionContext) -> None:
    meta = ctx.root / "pack.mcmeta"
    if not meta.exists():
        raise FatalConversionError(f"no pack.mcmeta at {ctx.root}")
    try:
        data = read_mcmeta(meta)
    except Exception as exc:
        raise FatalConversionError(f"unreadable pack.mcmeta: {exc}")

    pack = data.get("pack")
    fmt = pack.get("pack_format") if isinstance(pack, dict) else None
    if isinstance(fmt, str) and fmt.strip().lstrip("-").isdigit():
        fmt = int(fmt.strip())          # quoted numbers appear in real packs
    if not isinstance(fmt, int) or isinstance(fmt, bool):
        # Refusing the whole pack over one missing decorative-ish field is the
        # wrong trade, and the same one mcmeta.py already declined to make for
        # GSON sloppiness. A pack reaching this converter is a 1.8.9 pack by
        # assumption; say so loudly and convert it.
        ctx.add("ingest", Severity.WARNING,
                f"pack.mcmeta declares no usable pack_format ({fmt!r}); "
                f"assuming {ASSUMED_FORMAT} and converting anyway")
        fmt = ASSUMED_FORMAT
    ctx.add("ingest", Severity.INFO, f"detected pack_format={fmt}")
    if fmt != 1:
        ctx.add("ingest", Severity.WARNING,
                f"pack_format is {fmt}, expected 1; may already be converted")
