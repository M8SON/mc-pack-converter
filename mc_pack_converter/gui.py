"""Front end: converts, writes a self-contained HTML report beside the
output zip, and opens it in the browser.
"""
from __future__ import annotations
import sys
import webbrowser
from pathlib import Path

from .job import DEFAULT_TARGET, out_path_beside_source, run_job, validate_source


def parse_drop(argv: list[str]) -> tuple[Path | None, list[Path]]:
    """The first dropped path, plus any extras Windows passed alongside it.

    Dropping several files onto an exe hands them all over at once. We convert
    the first and say so; silently ignoring the rest would be worse.
    """
    paths = [Path(a) for a in argv]
    if not paths:
        return None, []
    return paths[0], paths[1:]


def write_report(result, sheet: dict, update: str | None, path: Path) -> Path:
    """The report, beside the output zip and named after it."""
    from .webui.report import build_model, render_html
    path.write_text(render_html(build_model(result, sheet, update)),
                    encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    source, extras = parse_drop(sys.argv[1:] if argv is None else argv)
    if source is None:
        print("Drag a 1.8.9 resource pack onto this file, or run:\n"
              "  mc-pack-converter convert <pack>", file=sys.stderr)
        return 2
    problem = validate_source(source)
    if problem:
        print(problem, file=sys.stderr)
        return 2

    # There is no UI thread to keep free any more, but the check still must
    # not delay the conversion and still must never raise -- both guaranteed
    # by start_update_check/run_update_check (tests/webui/test_update.py:145).
    # Duck-typed: it only ever assigns .update_notice, so a bare holder does.
    from types import SimpleNamespace
    from .webui.update import TIMEOUT_S, start_update_check
    holder = SimpleNamespace(update_notice=None)
    t = start_update_check(holder)

    out = out_path_beside_source(source, DEFAULT_TARGET)
    # on_stage is (name, i, total) -- the same callback cli.py uses, printed
    # in the same format so both front ends look identical (cli.py:63).
    # write_reports=False: findings are rendered into the HTML report below,
    # so the old *-report.md and *-null-textures.md would just be litter
    # beside the zip -- the same reason the windowed code passed this before
    # it. The HTML report does not carry the null-textures content either;
    # neither did the window, so nothing is lost that the window had.
    result = run_job(source, out, DEFAULT_TARGET, write_reports=False,
                     on_stage=lambda name, i, total: print(f"[{i}/{total}] {name}"))

    from .webui.sheet import EMPTY_SHEET, build_sheet
    sheet = build_sheet(out) if result.wrote_zip else EMPTY_SHEET

    t.join(timeout=TIMEOUT_S)
    update = holder.update_notice
    if update:
        print(update)

    report = write_report(result, sheet, update,
                          out.with_name(f"{out.stem}-report.html"))
    try:
        webbrowser.open(report.as_uri())
    except Exception:
        pass                      # the path below is the guarantee
    print(f"report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
