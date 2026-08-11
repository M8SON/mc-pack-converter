"""Windows front end: drag a pack zip onto the executable.

The interaction logic lives in GuiState, which never touches Tk, so it can be
tested on a headless runner. The widgets only render what GuiState says.
"""
from __future__ import annotations
import queue
import subprocess
import sys
import threading
import traceback
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:  # a headless box without Tk; the logic half still imports
    tk = filedialog = messagebox = ttk = None

from .job import DEFAULT_TARGET, out_path_beside_source, run_job, validate_source
from .pipeline import FatalConversionError, Severity


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

    def __init__(self, source: Path, target: str, extras: list[Path] | None = None):
        self.source = source
        self.target = target
        self.extras = extras or []
        self.screen = "progress"
        self.stage = ""
        self.done = 0
        self.total = 0
        self.result = None
        self.error: BaseException | None = None

    def handle(self, msg) -> None:
        try:
            kind = msg[0]
            if kind == "stage":
                _, self.stage, self.done, self.total = msg
            elif kind == "done":
                self.result = msg[1]
                self.screen = "result"
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
        if self.screen == "progress":
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
            if self.result.sheet is not None:
                lines.append(self.result.sheet.name)
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


POLL_MS = 50


class App:
    """The window. Owns every widget; the worker thread owns none of them."""

    def __init__(self, root: tk.Tk, state: GuiState):
        self.root = root
        self.state = state
        self.queue: queue.Queue = queue.Queue()

        root.title("MC Pack Converter")
        root.geometry("460x220")
        root.resizable(False, False)

        self.headline = ttk.Label(root, font=("Segoe UI", 12, "bold"))
        self.headline.pack(anchor="w", padx=16, pady=(16, 8))

        self.bar = ttk.Progressbar(root, length=428, mode="determinate")
        self.bar.pack(padx=16)

        self.detail = ttk.Label(root, justify="left", font=("Segoe UI", 9))
        self.detail.pack(anchor="w", padx=16, pady=8)

        self.buttons = ttk.Frame(root)
        self.buttons.pack(side="bottom", anchor="e", padx=16, pady=12)

        self.render()

    def start(self) -> None:
        threading.Thread(target=self._work, daemon=True).start()
        self.root.after(POLL_MS, self._drain)

    def _work(self) -> None:
        """Runs OFF the Tk thread. Only ever puts messages on the queue."""
        try:
            out = out_path_beside_source(self.state.source, self.state.target)
            result = run_job(
                self.state.source, out, self.state.target,
                on_stage=lambda name, i, total: self.queue.put(("stage", name, i, total)),
            )
            self.queue.put(("done", result))
        except BaseException as exc:  # a windowed exe has no console to print to
            self.queue.put(("failed", exc))

    def _drain(self) -> None:
        changed = False
        while True:
            try:
                self.state.handle(self.queue.get_nowait())
                changed = True
            except queue.Empty:
                break
        if changed:
            self.render()
        if self.state.screen == "progress":
            self.root.after(POLL_MS, self._drain)

    def render(self) -> None:
        self.headline.config(text=self.state.headline())
        self.detail.config(text="\n".join(self.state.detail_lines()))
        if self.state.total:
            self.bar.config(maximum=self.state.total, value=self.state.done)
        for child in self.buttons.winfo_children():
            child.destroy()
        if self.state.screen == "progress":
            return
        if self.state.screen == "error":
            ttk.Button(self.buttons, text="Copy details",
                       command=self._copy_details).pack(side="left", padx=4)
        else:
            ttk.Button(self.buttons, text="Open folder",
                       command=self._open_folder).pack(side="left", padx=4)
        ttk.Button(self.buttons, text="Close",
                   command=self.root.destroy).pack(side="left", padx=4)

    def _copy_details(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(self.state.error_details())
        messagebox.showinfo("Copied", "Error details copied to the clipboard.")

    def _open_folder(self) -> None:
        folder = self.state.result.out_path.parent
        if sys.platform == "win32":
            subprocess.run(["explorer", str(folder)])
        else:  # so the window is usable when developing off Windows
            subprocess.run(["xdg-open", str(folder)])


def main(argv: list[str] | None = None) -> int:
    if tk is None:
        print("The graphical interface needs Python's tkinter module, which is "
              "not installed. Use the command line instead:\n"
              "    mc-pack-converter convert <pack>", file=sys.stderr)
        return 1

    source, extras = parse_drop(sys.argv[1:] if argv is None else argv)

    root = tk.Tk()
    if source is None:
        root.withdraw()
        chosen = filedialog.askopenfilename(
            title="Choose a 1.8.9 resource pack",
            filetypes=[("Resource pack", "*.zip"), ("All files", "*.*")],
        )
        if not chosen:
            root.destroy()
            return 0  # cancelling the picker is not an error
        source = Path(chosen)
        root.deiconify()

    problem = validate_source(source)
    if problem:
        root.withdraw()
        messagebox.showerror("MC Pack Converter", problem)
        root.destroy()
        return 1

    app = App(root, GuiState(source, DEFAULT_TARGET, extras))
    app.start()
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
