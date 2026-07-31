from __future__ import annotations
import json, shutil, zipfile
from pathlib import Path
from ..pipeline import ConversionContext, Severity, FatalConversionError

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

def prepare_working_copy(source: Path, workdir: Path) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)
    if source.is_file() and source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as zf:
            _check_no_zip_slip(zf, workdir)
            zf.extractall(workdir)
        return _find_pack_root(workdir)
    dest = workdir / source.name
    shutil.copytree(source, dest)
    return _find_pack_root(dest)

def ingest(ctx: ConversionContext) -> None:
    meta = ctx.root / "pack.mcmeta"
    if not meta.exists():
        raise FatalConversionError(f"no pack.mcmeta at {ctx.root}")
    try:
        # utf-8-sig: pack.mcmeta is routinely saved by Windows editors with a
        # UTF-8 BOM, which json.loads rejects outright. Strips it if present,
        # no-op otherwise.
        fmt = json.loads(meta.read_text(encoding="utf-8-sig"))["pack"]["pack_format"]
    except Exception as exc:
        raise FatalConversionError(f"unreadable pack.mcmeta: {exc}")
    ctx.add("ingest", Severity.INFO, f"detected pack_format={fmt}")
    if fmt != 1:
        ctx.add("ingest", Severity.WARNING,
                f"pack_format is {fmt}, expected 1; may already be converted")
