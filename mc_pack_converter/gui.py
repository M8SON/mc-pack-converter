"""Front end: converts, writes a self-contained HTML report beside the
output zip, and opens it in the browser.

GuiState is unused by main() now but stays: api.py (Task 6's to retire) and
its tests still depend on it.
"""
from __future__ import annotations
import sys
import time
import traceback
import webbrowser
from pathlib import Path

from .job import DEFAULT_TARGET, out_path_beside_source, run_job, validate_source
from .pipeline import FatalConversionError, Severity

# Severity decides whether the user acts, so it decides the order. Python's
# sort is stable, so findings keep pipeline order within a severity.
_SEVERITY_RANK = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}


def parse_drop(argv: list[str]) -> tuple[Path | None, list[Path]]:
    """The first dropped path, plus any extras Windows passed alongside it.

    Dropping several files onto an exe hands them all over at once. We convert
    the first and say so; silently ignoring the rest would be worse.
    """
    paths = [Path(a) for a in argv]
    if not paths:
        return None, []
    return paths[0], paths[1:]


class GuiState:
    """What the window should be showing, driven by worker-thread messages."""

    def __init__(self, source: Path | None, target: str,
                 extras: list[Path] | None = None):
        self.source = source
        self.target = target
        self.extras = extras or []
        # No pack yet means the window opens on the drop screen and waits,
        # instead of demanding one before it will even appear.
        self.screen = "progress" if source is not None else "idle"
        self.stage = ""
        self.done = 0
        self.total = 0
        self.result = None
        self.sheet = None
        self.error: BaseException | None = None

    def start(self, source: Path) -> None:
        """A pack arrived -- by drop, by picker, or on the command line.

        Forgets the previous run. Without this a second pack is converted
        while the window still wears the first one's result and sheet.
        """
        self.source = source
        self.screen = "progress"
        self.stage = ""
        self.done = 0
        self.total = 0
        self.result = None
        self.sheet = None
        self.error = None

    def handle(self, msg) -> None:
        try:
            kind = msg[0]
            if kind == "stage":
                _, self.stage, self.done, self.total = msg
            elif kind == "done":
                self.result = msg[1]
                self.screen = "result"
            elif kind == "sheet":
                self.sheet = msg[1]
            elif kind == "failed":
                self.error = msg[1]
                self.screen = "error"
            # any other kind: ignore
        except (IndexError, ValueError, TypeError):
            # A malformed message must never kill the window. This runs inside
            # the Tk event loop of a windowed exe with no console, so an
            # exception here would take the UI down with nothing to show for it.
            return

    def headline(self) -> str:
        if self.screen == "idle":
            return "MC Pack Converter"
        if self.screen == "progress":
            return f"{self.source.name} → {self.target}"
        if self.screen == "error":
            # A rejected pack is the user's problem to fix; anything else is
            # ours, and saying so tells them which it is.
            if isinstance(self.error, FatalConversionError):
                return "This pack could not be converted"
            return "Something went wrong"
        errors = self.result.counts[Severity.ERROR]
        if errors:
            return f"Finished with {errors} errors"
        return "Done"

    def detail_lines(self) -> list[str]:
        lines: list[str] = []
        if self.screen == "idle":
            return [f"Converts a 1.8.9 pack to {self.target}"]
        if self.screen == "progress":
            if self.total:
                lines.append(f"{self.done}/{self.total}  {self.stage}")
            else:
                lines.append(self.stage)
        elif self.screen == "error":
            if isinstance(self.error, FatalConversionError):
                lines.append(str(self.error))
            else:
                lines.append(f"{type(self.error).__name__}: {self.error}")
                lines.append("Use Copy details to report this.")
        else:
            counts = self.result.counts
            lines.append(
                f"{counts[Severity.ERROR]} errors, "
                f"{counts[Severity.WARNING]} warnings, "
                f"{counts[Severity.INFO]} notes"
            )
            if self.result.wrote_zip:
                lines.append(f"Wrote {self.result.out_path.name}")
            for path in self.result.reports.values():
                lines.append(path.name)
        if self.extras:
            names = ", ".join(p.name for p in self.extras)
            lines.append(f"Converted {self.source.name} only; ignored {names}")
        return lines

    def error_details(self) -> str:
        """The full traceback, for the Copy details button."""
        if self.error is None:
            return ""
        return "".join(traceback.format_exception(
            type(self.error), self.error, self.error.__traceback__))

    def to_dict(self) -> dict:
        """The whole model the page renders. JSON-serialisable by construction."""
        d = {
            "screen": self.screen,
            "headline": self.headline(),
            "details": self.detail_lines(),
            "source": self.source.name if self.source else "",
            "target": self.target,
            "stage": self.stage,
            "done": self.done,
            "total": self.total,
            # Not per-pack, so start() does not clear it: whether this copy is
            # stale has nothing to do with which pack was dropped.
            "update": getattr(self, "update_notice", None),
        }
        if self.screen == "error":
            d["error_details"] = self.error_details()
        elif self.screen == "result":
            counts = self.result.counts
            d["counts"] = {s.value: counts[s] for s in Severity}
            d["findings"] = [
                {"severity": f.severity.value, "stage": f.stage,
                 "message": f.message, "path": f.path}
                for f in sorted(self.result.ctx.findings,
                                key=lambda f: _SEVERITY_RANK[f.severity])
            ]
            d["out_path"] = str(self.result.out_path)
            d["out_name"] = self.result.out_path.name
        return d


_diag_file: "Path | None" = None


def _diag(msg: str) -> None:
    """Append one line to the launch log, rewritten fresh on every launch.

    A windowed exe has no console. When the window comes up dead -- no version
    list, no background, an unresponsive close button -- this file is the only
    record of how far startup actually got, and in particular whether the page
    ever reached Python at all.
    """
    global _diag_file
    try:
        if _diag_file is None:
            from .webui.wall import cache_dir
            _diag_file = cache_dir() / "last-run.log"
            _diag_file.parent.mkdir(parents=True, exist_ok=True)
            _diag_file.write_text("", encoding="utf-8")
        with _diag_file.open("a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except OSError:
        pass          # diagnostics must never be the thing that breaks a launch


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
    result = run_job(source, out, DEFAULT_TARGET,
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
