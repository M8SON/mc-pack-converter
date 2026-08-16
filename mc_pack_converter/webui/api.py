"""The object pywebview exposes to JavaScript.

No HTTP server and no port: a listening socket triggers a Windows Defender
Firewall prompt on first run, and users already have to click through
SmartScreen. Two frightening dialogs before the app opens would undo the point
of the exercise.
"""
from __future__ import annotations
import base64
import queue
import subprocess
import sys
import zipfile
from pathlib import Path

from ..job import validate_source
from .sheet import build_sheet

EMPTY_SHEET = {"sections": [], "excluded": [], "total": 0}


class Api:
    def __init__(self, state, q: queue.Queue, on_start=None):
        self._state = state
        self._queue = q
        self._sheet = None
        self._on_start = on_start   # starts the worker; set by gui.main()
        self.window = None          # the pywebview window, for the file dialog

    def start(self, path: str) -> str:
        """Begin converting a dropped or chosen pack.

        Returns the reason it cannot be converted, or "" to mean started. The
        page shows that reason in place, which is why this returns a message
        rather than raising: a windowed exe has nowhere to raise to.
        """
        if self._state.screen not in ("idle", "error"):
            return ""                      # already working; ignore the drop
        source = Path(path)
        problem = validate_source(source)
        if problem:
            return problem
        self._state.start(source)
        if self._on_start is not None:
            self._on_start(source)
        return ""

    def pick(self) -> str:
        """The file dialog, opened from the window rather than from Tk."""
        if self.window is None:
            return ""
        import webview   # imported here so the module loads without pywebview
        chosen = self.window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("Resource pack (*.zip)", "All files (*.*)"),
        )
        # pywebview returns a tuple of paths, or None when cancelled.
        return chosen[0] if chosen else ""

    def poll(self) -> dict:
        """Drain the worker's messages and hand the page the whole model."""
        while True:
            try:
                self._state.handle(self._queue.get_nowait())
            except queue.Empty:
                break
        d = self._state.to_dict()
        bg = self._pack_background()
        if bg:
            d["background"] = bg
        return d

    _BG = "assets/minecraft/textures/gui/options_background.png"

    def _pack_background(self) -> str:
        """The converted pack's own gui background, as a data URI.

        The app wears the pack you just converted. Cached, and absent rather
        than fatal when a pack does not ship one.
        """
        if getattr(self, "_bg", None) is not None:
            return self._bg
        self._bg = ""
        if self._state.screen == "result":
            try:
                with zipfile.ZipFile(self._state.result.out_path) as z:
                    raw = z.read(self._BG)
                self._bg = ("data:image/png;base64,"
                            + base64.b64encode(raw).decode("ascii"))
            except (OSError, KeyError, zipfile.BadZipFile):
                self._bg = ""
        return self._bg

    def sheet(self) -> dict:
        """The QA sheet, built once. Roughly 1.75s and 1.72MB on a real pack."""
        # Already built, on the worker thread. This call must stay cheap:
        # pywebview runs it on the UI thread, and anything slow here shows up
        # to the user as the window not responding.
        return getattr(self._state, "sheet", None) or EMPTY_SHEET

    def texture(self, path: str) -> str:
        """One full-size texture, on demand.

        The originals total 22.5MB on the reference pack, so they are never
        bundled into the page. `path` comes from JavaScript and is honoured
        only if it is literally an entry of this zip -- there is no filesystem
        read reachable from the page.
        """
        if self._state.screen != "result":
            return ""
        out = self._state.result.out_path
        try:
            with zipfile.ZipFile(out) as z:
                if path not in z.namelist():
                    return ""
                raw = z.read(path)
        except (OSError, zipfile.BadZipFile, KeyError):
            return ""
        return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")

    def open_folder(self) -> None:
        if self._state.screen != "result":
            return
        folder = self._state.result.out_path.parent
        if sys.platform == "win32":
            subprocess.run(["explorer", str(folder)])
        else:  # so the window is usable when developing off Windows
            subprocess.run(["xdg-open", str(folder)])
