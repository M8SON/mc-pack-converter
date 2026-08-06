from __future__ import annotations
import argparse, shutil, tempfile
from pathlib import Path
from .pipeline import ConversionContext, Severity, run_pipeline
from .stages import STAGES
from .stages.ingest import prepare_working_copy
from .stages.package import write_output
from .report import render_conversion_report, render_null_texture_report
from .contact_sheet import ATLAS_1_14, build_contact_sheet
from .data import load_table

def _announce(stages, on_stage):
    """Wrap each stage so the caller is told before it runs."""
    total = len(stages)
    return [
        (name, lambda ctx, fn=fn, name=name, i=i: (on_stage(name, i, total), fn(ctx))[1])
        for i, (name, fn) in enumerate(stages, start=1)
    ]

def convert(source: Path, out_path: Path, target: str,
            report_only: bool, on_stage=None) -> ConversionContext:
    workroot = Path(tempfile.mkdtemp(prefix="mcpc_"))
    try:
        root = prepare_working_copy(source, workroot)
        ctx = ConversionContext(root=root, target=target)
        stages = STAGES if not report_only else [
            s for s in STAGES if s[0] in ("ingest", "clean", "restructure",
            "flatten_rename", "atlas_remap", "optifine", "validate")]
        if on_stage is not None:
            stages = _announce(stages, on_stage)
        run_pipeline(ctx, stages)
        reports = {
            "conversion-report.md": render_conversion_report(ctx.findings),
            "null-texture-report.md": render_null_texture_report(ctx.findings),
        }
        if not report_only:
            write_output(ctx, out_path, reports)
            sheet = out_path.with_name(out_path.stem + "-slices.png")
            rels = [out for src, out in ctx.sliced if src in ATLAS_1_14]
            try:
                n = build_contact_sheet(ctx.root, rels, sheet)
                if n:
                    print(f"contact sheet: {sheet} ({n} sprites)")
            except Exception as exc:  # fail-soft: a review artifact, not the product
                ctx.add("contact_sheet", Severity.WARNING,
                        f"contact sheet failed: {exc!r}")
        return ctx
    finally:
        shutil.rmtree(workroot, ignore_errors=True)

def default_out_path(source: Path, target: str) -> Path:
    """Name the output after the source and target, in the cwd.

    A fixed default overwrites the previous run without saying so.
    """
    stem = source.stem if source.suffix.lower() == ".zip" else source.name
    return Path(f"{stem}-{target}.zip")

TARGETS = sorted(load_table("pack_format"))

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="mc-pack-converter",
        description="Convert a Minecraft Java 1.8.9 resource pack to a modern version.",
        epilog="example:  mc-pack-converter convert MyPack.zip --target 26.2",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("convert", help="convert a pack")
    c.add_argument("source", type=Path,
                   help="the 1.8.9 pack to convert: a .zip or an unpacked folder")
    c.add_argument("-o", "--out", type=Path, default=None,
                   help="output zip (default: <pack>-<target>.zip in the current directory)")
    c.add_argument("--target", default="26.2", choices=TARGETS,
                   help="Minecraft version to convert to (default: %(default)s)")
    c.add_argument("--report-only", action="store_true",
                   help="analyse the pack and write reports without producing a converted pack")
    c.add_argument("-v", "--verbose", action="store_true",
                   help="also print the full reports to the terminal")
    return ap

def summary_lines(ctx: ConversionContext, out_path: Path,
                  reports: dict[str, Path]) -> list[str]:
    counts = {s: 0 for s in Severity}
    for f in ctx.findings:
        counts[f.severity] += 1
    lines = [
        "",
        f"{counts[Severity.ERROR]} errors, {counts[Severity.WARNING]} warnings, "
        f"{counts[Severity.INFO]} notes",
    ]
    if out_path.exists():
        lines.append(f"wrote {out_path}")
    lines += [f"{label}: {path}" for label, path in reports.items()]
    return lines

def main(argv=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    out = args.out or default_out_path(args.source, args.target)

    def on_stage(name, i, total):
        print(f"[{i}/{total}] {name}")

    ctx = convert(args.source, out, args.target, args.report_only,
                  on_stage=on_stage)

    texts = {
        "report": render_conversion_report(ctx.findings),
        "null-textures": render_null_texture_report(ctx.findings),
    }
    written = {}
    for label, text in texts.items():
        p = out.with_name(f"{out.stem}-{label}.md")
        p.write_text(text)
        written[label] = p

    if args.verbose:
        for text in texts.values():
            print(text)
    for line in summary_lines(ctx, out, written):
        print(line)

    if any(f.severity is Severity.ERROR for f in ctx.findings):
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
