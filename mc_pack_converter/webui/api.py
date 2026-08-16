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

from .sheet import build_sheet

EMPTY_SHEET = {"sections": [], "excluded": [], "total": 0}


class Api:
    def __init__(self, state, q: queue.Queue):
        self._state = state
        self._queue = q
        self._sheet = None

    def poll(self) -> dict:
        """Drain the worker's messages and hand the page the whole model."""
        while True:
            try:
                self._state.handle(self._queue.get_nowait())
            except queue.Empty:
                break
        return self._state.to_dict()

    def sheet(self) -> dict:
        """The QA sheet, built once. Roughly 1.75s and 1.72MB on a real pack."""
        if self._sheet is None:
            if self._state.screen != "result":
                return EMPTY_SHEET
            self._sheet = build_sheet(self._state.result.out_path)
        return self._sheet

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
