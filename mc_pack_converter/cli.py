from __future__ import annotations
import argparse, sys
from pathlib import Path
from .pipeline import ConversionContext, Severity
from .report import render_conversion_report, render_null_texture_report
from .data import load_table
from .job import DEFAULT_TARGET, convert, validate_source

def default_out_path(source: Path, target: str) -> Path:
    """Name the output after the source and target, in the cwd.

    A fixed default overwrites the previous run without saying so.
    """
    stem = source.stem if source.suffix.lower() == ".zip" else source.name
    return Path(f"{stem}-{target}.zip")

# pack_format.json's "1.8.9" entry describes the format a pack is READ as,
# not a valid conversion output; excluded so --target 1.8.9 is rejected.
INPUT_FORMAT = "1.8.9"
TARGETS = sorted(k for k in load_table("pack_format") if k != INPUT_FORMAT)

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
    c.add_argument("--target", default=DEFAULT_TARGET, choices=TARGETS,
                   help="Minecraft version to convert to (default: %(default)s)")
    c.add_argument("--report-only", action="store_true",
                   help="analyse the pack and write reports without producing a converted pack")
    c.add_argument("-v", "--verbose", action="store_true",
                   help="also print the full reports to the terminal")
    return ap

def summary_lines(ctx: ConversionContext, out_path: Path,
                  reports: dict[str, Path], wrote_zip: bool) -> list[str]:
    counts = {s: 0 for s in Severity}
    for f in ctx.findings:
        counts[f.severity] += 1
    lines = [
        "",
        f"{counts[Severity.ERROR]} errors, {counts[Severity.WARNING]} warnings, "
        f"{counts[Severity.INFO]} notes",
    ]
    # Whether THIS run produced the zip, not whether a file of that name is on
    # disk: a leftover zip from a previous run made --report-only claim it had
    # written one.
    if wrote_zip:
        lines.append(f"wrote {out_path}")
    lines += [f"{label}: {path}" for label, path in reports.items()]
    return lines

def main(argv=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    out = args.out or default_out_path(args.source, args.target)

    problem = validate_source(args.source)
    if problem:
        print(problem, file=sys.stderr)
        return 1

    def on_stage(name, i, total):
        print(f"[{i}/{total}] {name}")

    ctx = convert(args.source, out, args.target, args.report_only,
                  on_stage=on_stage,
                  on_sheet=lambda path, n: print(f"contact sheet: {path} ({n} sprites)"))

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
    for line in summary_lines(ctx, out, written, wrote_zip=not args.report_only):
        print(line)

    if any(f.severity is Severity.ERROR for f in ctx.findings):
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
