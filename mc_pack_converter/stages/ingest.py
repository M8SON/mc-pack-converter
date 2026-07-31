from __future__ import annotations
import shutil, zipfile
from pathlib import Path
from ..pipeline import ConversionContext, Severity, FatalConversionError
from ..mcmeta import read_mcmeta

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
        fmt = read_mcmeta(meta)["pack"]["pack_format"]
    except Exception as exc:
        raise FatalConversionError(f"unreadable pack.mcmeta: {exc}")
    ctx.add("ingest", Severity.INFO, f"detected pack_format={fmt}")
    if fmt != 1:
        ctx.add("ingest", Severity.WARNING,
                f"pack_format is {fmt}, expected 1; may already be converted")
