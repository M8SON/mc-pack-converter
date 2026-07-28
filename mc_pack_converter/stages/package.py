from __future__ import annotations
import shutil, zipfile
from pathlib import Path
from ..pipeline import ConversionContext, FatalConversionError

def write_output(ctx: ConversionContext, out_path: Path,
                 reports: dict[str, str]) -> None:
    for name, text in reports.items():
        (ctx.root / name).write_text(text)
    parent = out_path.parent
    if not parent.exists() or not parent.is_dir():
        raise FatalConversionError(f"output dir not writable: {parent}")
    if out_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in ctx.root.rglob("*"):
                if p.is_file():
                    zf.write(p, p.relative_to(ctx.root))
    else:
        shutil.copytree(ctx.root, out_path, dirs_exist_ok=True)
