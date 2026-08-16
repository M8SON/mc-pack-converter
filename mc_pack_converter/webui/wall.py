"""Build the page's background out of the converted pack's own blocks.

A terrain cross-section: grass on top, dirt beneath it, then stone shot
through with ore. The art is the pack's, so the window is dressed in the
textures you just converted rather than in something generic.

Seamless left-to-right, so it tiles across any window width, and deliberately
NOT seamless top-to-bottom -- it is a cross-section, and the sky is up.
"""
from __future__ import annotations
import base64, io, random, zipfile
from pathlib import Path

from PIL import Image

B = "assets/minecraft/textures/block/"

# Column layout, top row first. Ore rows carry a weighted mix so the wall
# reads like a cave face rather than a chessboard.
GRASS, DIRT, STONE = "grass_block_side", "dirt", "stone"
ORES = ["coal_ore", "iron_ore", "gold_ore", "diamond_ore",
        "redstone_ore", "lapis_ore", "emerald_ore"]
# Mostly stone. Ore is a find, not a floor.
ORE_CHANCE = 0.22

COLS, ROWS = 8, 8
GRASS_ROWS, DIRT_ROWS = 1, 2


def _read(zf: zipfile.ZipFile, name: str) -> Image.Image | None:
    try:
        with Image.open(io.BytesIO(zf.read(B + name + ".png"))) as im:
            im = im.convert("RGBA")
            # An animated block ships as a vertical strip; take frame one.
            if im.height > im.width and im.height % im.width == 0:
                im = im.crop((0, 0, im.width, im.width))
            return im.copy()
    except (KeyError, OSError, ValueError):
        return None


def build_wall(zip_path: Path, seed: int = 5) -> bytes | None:
    """PNG bytes of a wall built from this pack, or None if it lacks the art."""
    rng = random.Random(seed)
    try:
        with zipfile.ZipFile(zip_path) as zf:
            stone = _read(zf, STONE)
            if stone is None:
                return None            # no stone, no wall worth building
            grass = _read(zf, GRASS) or stone
            dirt = _read(zf, DIRT) or stone
            ores = [im for im in (_read(zf, o) for o in ORES) if im is not None]
    except (OSError, zipfile.BadZipFile):
        return None

    size = stone.width
    wall = Image.new("RGBA", (size * COLS, size * ROWS))
    for row in range(ROWS):
        for col in range(COLS):
            if row < GRASS_ROWS:
                block = grass
            elif row < GRASS_ROWS + DIRT_ROWS:
                block = dirt
            elif ores and rng.random() < ORE_CHANCE:
                block = ores[rng.randrange(len(ores))]
            else:
                block = stone
            if block.size != (size, size):
                block = block.resize((size, size), Image.NEAREST)
            wall.paste(block, (col * size, row * size))

    buf = io.BytesIO()
    wall.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def wall_data_uri(zip_path: Path) -> str:
    png = build_wall(zip_path)
    if not png:
        return ""
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def cache_path() -> Path:
    """Where the last pack's wall is kept between runs.

    Per-user, not beside the exe: the exe may sit somewhere unwritable, and a
    tool should not scribble next to itself.
    """
    import os, tempfile
    base = (os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME")
            or os.path.expanduser("~/.cache"))
    return Path(base) / "MCPackConverter" / "wall.png"


def remember_wall(png: bytes) -> None:
    """Keep this wall so the drop screen opens wearing the last pack."""
    try:
        p = cache_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(png)
    except OSError:
        pass          # a background is never worth failing a conversion over


def remembered_wall() -> str:
    """The cached wall as a data URI, or "" on the very first run."""
    try:
        return ("data:image/png;base64,"
                + base64.b64encode(cache_path().read_bytes()).decode("ascii"))
    except OSError:
        return ""
