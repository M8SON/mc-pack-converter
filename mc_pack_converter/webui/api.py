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
from .wall import (build_wall, build_grass, remember_wall, remembered_wall,
                   remember_grass, remembered_grass, tile_size)

EMPTY_SHEET = {"sections": [], "excluded": [], "total": 0}



def _data_uri(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


class Api:
    def __init__(self, state, q: queue.Queue, on_start=None):
        self._state = state
        self._queue = q
        self._sheet = None
        self._on_start = on_start   # starts the worker; set by gui.main()
        # PRIVATE, and it must stay private. pywebview builds the JavaScript
        # bridge by walking dir() on this object and recursing into every
        # public attribute, running property getters as it goes. Window's
        # width/height/x/y each wait up to 15 seconds on its "shown" event, so
        # a public name here stalled the bridge for up to a minute on startup
        # -- a live window, wired to nothing. It also exposed destroy(),
        # run_js() and load_url() to the page.
        self._window = None         # the pywebview window, for the file dialog

    def ready(self) -> bool:
        """Called by the page the instant its bridge works.

        The launch log is the only way to tell a window that came up inert
        from one that never got a working bridge at all: if there is no "page
        ready" line, JavaScript never reached Python.
        """
        from ..gui import _diag          # lazy: gui imports this module
        _diag("page ready")
        return True

    def targets(self) -> dict:
        """The versions this converter can produce, and the current pick."""
        from ..cli import TARGETS
        return {"targets": TARGETS, "current": self._state.target}

    def start(self, path: str, target: str = "") -> str:
        """Begin converting a dropped or chosen pack.

        Returns the reason it cannot be converted, or "" to mean started. The
        page shows that reason in place, which is why this returns a message
        rather than raising: a windowed exe has nowhere to raise to.
        """
        # A finished run may be replaced -- dropping a second pack is how you
        # convert two of them without restarting the app. A drop while the
        # worker is still going is ignored, since two conversions would race
        # each other onto the same output zip.
        if self._state.screen not in ("idle", "error", "result"):
            return ""                      # already working; ignore the drop
        source = Path(path)
        problem = validate_source(source)
        if problem:
            return problem
        if target:
            from ..cli import TARGETS
            if target not in TARGETS:
                return f"unknown version: {target}"
            self._state.target = target
        self._state.start(source)
        if self._on_start is not None:
            self._on_start(source)
        return ""

    def pick(self) -> str:
        """The file dialog, opened from the window rather than from Tk."""
        if self._window is None:
            return ""
        import webview   # imported here so the module loads without pywebview
        chosen = self._window.create_file_dialog(
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
        d.update(self._pack_dressing())
        return d

    def _pack_dressing(self) -> dict:
        """The converted pack's own ground and grass layer, as data URIs.

        The app wears the pack you just converted, and remembers it for next
        launch. Absent rather than fatal when a pack ships no usable texture.

        Cached against the SCREEN, not merely "have I run once": polling on
        the drop screen used to store the empty answer, and because "" is not
        None it was then returned forever -- so the wall was never built when
        the conversion finished, and never written to the cache either.
        """
        if getattr(self, "_bg_for", None) == self._state.screen:
            return self._bg
        self._bg_for = self._state.screen
        self._bg = {}

        if self._state.screen != "result":
            ground, grass = remembered_wall(), remembered_grass()
        else:                              # and keep them for the NEXT launch
            out = self._state.result.out_path
            ground, grass = build_wall(out), build_grass(out)
            if ground:
                remember_wall(ground)
            if grass:
                remember_grass(grass)

        if ground:
            self._bg["background"] = _data_uri(ground)
            # The ground is a whole field of blocks, not one tile, so the page
            # cannot assume a size -- it is measured here and sent along.
            self._bg["backgroundSize"] = tile_size(ground)
        if grass:
            self._bg["grass"] = _data_uri(grass)
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
        return _data_uri(raw)

    def open_folder(self) -> None:
        if self._state.screen != "result":
            return
        folder = self._state.result.out_path.parent
        if sys.platform == "win32":
            subprocess.run(["explorer", str(folder)])
        else:  # so the window is usable when developing off Windows
            subprocess.run(["xdg-open", str(folder)])
