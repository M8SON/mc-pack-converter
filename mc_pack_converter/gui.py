"""Windows front end: drag a pack zip onto the executable.

The interaction logic lives in GuiState, which never touches Tk, so it can be
tested on a headless runner. The widgets only render what GuiState says.
"""
from __future__ import annotations
import traceback
from pathlib import Path

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
