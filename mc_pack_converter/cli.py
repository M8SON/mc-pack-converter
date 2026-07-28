from __future__ import annotations
import argparse, shutil, tempfile
from pathlib import Path
from .pipeline import ConversionContext, Severity, run_pipeline
from .stages import STAGES
from .stages.ingest import prepare_working_copy
from .stages.package import write_output
from .report import render_conversion_report, render_null_texture_report

def convert(source: Path, out_path: Path, target: str,
            report_only: bool) -> ConversionContext:
    workroot = Path(tempfile.mkdtemp(prefix="mcpc_"))
    try:
        root = prepare_working_copy(source, workroot)
        ctx = ConversionContext(root=root, target=target)
        stages = STAGES if not report_only else [
            s for s in STAGES if s[0] in ("ingest", "clean", "restructure",
            "flatten_rename", "atlas_remap", "optifine", "validate")]
        run_pipeline(ctx, stages)
        reports = {
            "conversion-report.md": render_conversion_report(ctx.findings),
            "null-texture-report.md": render_null_texture_report(ctx.findings),
        }
        if not report_only:
            write_output(ctx, out_path, reports)
        return ctx
    finally:
        shutil.rmtree(workroot, ignore_errors=True)

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="mc-pack-converter")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("convert")
    c.add_argument("source", type=Path)
    c.add_argument("-o", "--out", type=Path, default=Path("converted.zip"))
    c.add_argument("--target", default="26.2")
    c.add_argument("--report-only", action="store_true")
    args = ap.parse_args(argv)
    ctx = convert(args.source, args.out, args.target, args.report_only)
    print(render_conversion_report(ctx.findings))
    print(render_null_texture_report(ctx.findings))
    if any(f.severity is Severity.ERROR for f in ctx.findings):
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
