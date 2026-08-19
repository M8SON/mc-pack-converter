"""Windows front end: drag a pack zip onto the executable.

The interaction logic lives in GuiState, which never touches Tk, so it can be
tested on a headless runner. The widgets only render what GuiState says.
"""
from __future__ import annotations
import queue
import sys
import threading
import time
import traceback
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
except ImportError:  # a headless box without Tk; the logic half still imports
    tk = filedialog = messagebox = None

from .job import DEFAULT_TARGET, out_path_beside_source, run_job, validate_source
from .webui.sheet import build_sheet
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


def _work(state: GuiState, q: queue.Queue) -> None:
    """Runs OFF the UI thread. Only ever puts messages on the queue."""
    try:
        out = out_path_beside_source(state.source, state.target)
        result = run_job(
            state.source, out, state.target,
            on_stage=lambda name, i, total: q.put(("stage", name, i, total)),
            write_reports=False,   # the page shows the findings; no .md litter
        )
        # Build the QA sheet HERE, on the worker, not when JavaScript asks
        # for it. pywebview runs js_api calls on the UI thread, so building
        # 1021 tiles and 480 rotation frames inside api.sheet() froze the
        # whole window -- Windows shows that as "not responding".
        q.put(("stage", "building the texture sheet", 0, 0))
        try:
            sheet = build_sheet(result.out_path)
        except BaseException:
            sheet = None      # the findings are still worth showing
        q.put(("sheet", sheet))
        q.put(("done", result))
    except BaseException as exc:  # a windowed exe has no console to print to
        q.put(("failed", exc))


def _fallback(state: GuiState, q: queue.Queue) -> int:
    """No WebView2. Wait for the job already running and write its reports.

    It WAITS rather than re-running: the worker thread started before the
    window was attempted, and a second run_job would convert the same pack
    twice and race the first one writing the same zip.

    A silent exit is the one outcome that must not happen: the exe is windowed,
    so an unreported failure looks like nothing happened at all.
    """
    while state.screen == "progress":
        state.handle(q.get())          # blocks until the worker speaks
    if state.screen == "error":
        print(f"conversion failed: {state.error!r}", file=sys.stderr)
        return 1
    result = state.result
    print(f"wrote {result.out_path}")
    # The worker passed write_reports=False for the page's benefit; with no
    # page, the sidecars are the only output the user can read.
    for label, text in result.report_texts.items():
        p = result.out_path.with_name(f"{result.out_path.stem}-{label}.md")
        p.write_text(text)
        print(p)
    return 0


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


def main(argv: list[str] | None = None) -> int:
    source, extras = parse_drop(sys.argv[1:] if argv is None else argv)

    # A pack on the command line (dropped onto the exe icon) still works, but
    # it is no longer required: with no argument the window opens on its drop
    # screen and waits, instead of ambushing the user with a file dialog.
    if source is not None and validate_source(source):
        source = None   # the page will say why, where the user can see it

    _diag(f"launch: argv={sys.argv[1:]!r} source={source!r}")

    state = GuiState(source, DEFAULT_TARGET, extras)
    q: queue.Queue = queue.Queue()

    # Off the UI thread, and started before the window so the answer is
    # usually there by the time the page first polls. Advisory only: it sets
    # one string on the state and never installs anything.
    from .webui.update import start_update_check
    start_update_check(state)

    def begin(pack: Path) -> None:
        threading.Thread(target=_work, args=(state, q), daemon=True).start()

    try:
        import webview
        _diag(f"webview {getattr(webview, '__version__', '?')} imported")
        from .webui.api import Api
        api = Api(state, q, on_start=begin)
        index = Path(__file__).parent / "webui" / "assets" / "index.html"
        window = webview.create_window("MC Pack Converter", str(index),
                                       js_api=api, width=1040, height=800)
        api._window = window
        _diag("window created")
        if source is not None:
            begin(source)
        webview.start()
        _diag("window closed; exiting")
    except Exception as exc:
        # WebView2 absent, or pywebview failed to make a window at all. A
        # windowed exe has no console, so say so where it can be seen.
        note = f"no window available ({exc!r})"
        _diag(note)
        print(note, file=sys.stderr)
        if source is None:
            if tk is not None:
                root = tk.Tk(); root.withdraw()
                messagebox.showerror("MC Pack Converter", note)
                root.destroy()
            return 1
        threading.Thread(target=_work, args=(state, q), daemon=True).start()
        return _fallback(state, q)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
