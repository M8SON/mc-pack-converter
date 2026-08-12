from __future__ import annotations
import argparse, sys
from pathlib import Path
from .pipeline import Severity
from .data import INPUT_FORMAT, load_table
from .job import DEFAULT_TARGET, convert, run_job, validate_source

def default_out_path(source: Path, target: str) -> Path:
    """Name the output after the source and target, in the cwd.

    A fixed default overwrites the previous run without saying so.
    """
    stem = source.stem if source.suffix.lower() == ".zip" else source.name
    return Path(f"{stem}-{target}.zip")

# INPUT_FORMAT is re-exported from .data, where pack_meta also reads it: the
# "1.8.9" entry describes the format a pack is READ as, not a valid conversion
# output, so it is excluded here and --target 1.8.9 is rejected.
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

def summary_lines(result) -> list[str]:
    counts = result.counts
    lines = [
        "",
        f"{counts[Severity.ERROR]} errors, {counts[Severity.WARNING]} warnings, "
        f"{counts[Severity.INFO]} notes",
    ]
    if result.wrote_zip:
        lines.append(f"wrote {result.out_path}")
    lines += [f"{label}: {path}" for label, path in result.reports.items()]
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

    result = run_job(args.source, out, args.target, args.report_only,
                     on_stage=on_stage,
                     on_sheet=lambda path, n: print(f"contact sheet: {path} ({n} sprites)"))

    if args.verbose:
        for text in result.report_texts.values():
            print(text)
    for line in summary_lines(result):
        print(line)

    if result.has_errors:
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
