"""Dress the window in the converted pack's own background texture.

Nothing is composed and nothing is invented: this lifts ONE texture out of the
pack and tiles it, which is exactly what Minecraft does behind its own menus.
gui/options_background.png is that texture; dirt and stone stand in when a
pack does not ship one.
"""
from __future__ import annotations
import base64, io, zipfile
from pathlib import Path

from PIL import Image

T = "assets/minecraft/textures/"

# In preference order. The first is the texture vanilla itself tiles behind
# the options screen, so a pack that customises it has already decided what
# its own menus should look like -- use that decision.
CANDIDATES = (
    T + "gui/options_background.png",
    T + "block/dirt.png",
    T + "block/stone.png",
)


def build_wall(zip_path: Path) -> bytes | None:
    """The pack's own background texture, verbatim, or None if it has none."""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())
            for candidate in CANDIDATES:
                if candidate not in names:
                    continue
                raw = zf.read(candidate)
                try:
                    with Image.open(io.BytesIO(raw)) as im:
                        # An animated block ships as a vertical strip; tiling
                        # the whole strip would smear it down the page.
                        if im.height > im.width and im.height % im.width == 0:
                            frame = im.convert("RGBA").crop(
                                (0, 0, im.width, im.width))
                            buf = io.BytesIO()
                            frame.save(buf, "PNG", optimize=True)
                            return buf.getvalue()
                        im.verify()
                except Exception:
                    continue          # unreadable: try the next candidate
                return raw            # verbatim, the pack's own bytes
    except (OSError, zipfile.BadZipFile):
        return None
    return None


def cache_path() -> Path:
    """Where the last pack's background is kept between runs.

    Per-user, not beside the exe: the exe may sit somewhere unwritable, and a
    tool should not scribble next to itself.
    """
    import os
    base = (os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME")
            or os.path.expanduser("~/.cache"))
    return Path(base) / "MCPackConverter" / "wall.png"


def remember_wall(png: bytes) -> None:
    """Keep it so the drop screen opens wearing the last pack converted."""
    try:
        p = cache_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(png)
    except OSError:
        pass          # a background is never worth failing a conversion over


def remembered_wall() -> str:
    """The cached background as a data URI, or "" on the very first run."""
    try:
        return ("data:image/png;base64,"
                + base64.b64encode(cache_path().read_bytes()).decode("ascii"))
    except OSError:
        return ""
