"""Dress the window in the converted pack's own blocks.

A cross-section of the world the pack is for: a layer of its grass block
across the top, and below it a field of its stone with its iron, gold and
diamond ore scattered through it.

Nothing here is drawn. Every tile is a texture decoded out of the pack and
pasted whole -- two earlier walls with generated ore art were rejected, and
rightly: the pack's art is the only art this tool is allowed to show. A pack
with no stone falls back to tiling one texture verbatim, as before.
"""
from __future__ import annotations
import io, random, zipfile
from pathlib import Path

from PIL import Image

T = "assets/minecraft/textures/"
B = T + "block/"

GRASS = B + "grass_block_side.png"
STONE = B + "stone.png"

# How many tiles of each ore land in the field, ranked the way the game ranks
# them: iron common, diamond rare. 23 of 256 tiles is about 9% ore, sparse
# enough to read as stone with ore in it rather than as an ore wall.
ORES = ((B + "iron_ore.png", 12),
        (B + "gold_ore.png", 7),
        (B + "diamond_ore.png", 4))

FIELD = 16      # tiles a side; at 4x that is a 1024px wall, taller than most windows
SEED = 1989     # fixed, so a pack's wall is the same wall on every launch

# Tiled verbatim when a pack ships no stone to build a field out of. The first
# is the texture vanilla itself puts behind the options screen, so a pack that
# customised it has already decided what its own menus should look like.
CANDIDATES = (T + "gui/options_background.png", B + "dirt.png", STONE)


def _first_frame(im: Image.Image) -> Image.Image:
    """An animated block ships as a vertical strip; only the top frame is a
    block, and tiling the whole strip would smear it down the page."""
    if im.height > im.width and im.height % im.width == 0:
        return im.crop((0, 0, im.width, im.width))
    return im


def _tile(zf: zipfile.ZipFile, name: str) -> Image.Image | None:
    try:
        with Image.open(io.BytesIO(zf.read(name))) as im:
            return _first_frame(im.convert("RGBA")).copy()
    except (KeyError, OSError, ValueError):
        return None


def _terrain(zf: zipfile.ZipFile) -> bytes | None:
    """A square field of the pack's stone with its own ore pasted into it."""
    stone = _tile(zf, STONE)
    if stone is None or stone.width != stone.height:
        return None
    px = stone.width

    field = Image.new("RGBA", (px * FIELD, px * FIELD))
    for i in range(FIELD * FIELD):
        field.paste(stone, ((i % FIELD) * px, (i // FIELD) * px))

    # Resizing an ore to fit would invent pixels the pack never drew, so an
    # ore at another resolution is simply left out.
    veins = [(ore, n) for path, n in ORES
             if (ore := _tile(zf, path)) is not None and ore.size == stone.size]

    rng = random.Random(SEED)
    slots = rng.sample(range(FIELD * FIELD), sum(n for _, n in veins))
    for ore, n in veins:
        for _ in range(n):
            i = slots.pop()
            field.paste(ore, ((i % FIELD) * px, (i // FIELD) * px))

    buf = io.BytesIO()
    field.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _verbatim(zf: zipfile.ZipFile, names: set[str]) -> bytes | None:
    """One texture, the pack's own bytes, tiled the way Minecraft tiles it."""
    for candidate in CANDIDATES:
        if candidate not in names:
            continue
        raw = zf.read(candidate)
        try:
            with Image.open(io.BytesIO(raw)) as im:
                whole = im.size
                frame = _first_frame(im.convert("RGBA"))
        except Exception:
            continue                           # unreadable: try the next candidate
        if frame.size != whole:                # it was a strip: re-encode one frame
            buf = io.BytesIO()
            frame.save(buf, "PNG", optimize=True)
            return buf.getvalue()
        return raw                             # verbatim, the pack's own bytes
    return None


def build_wall(zip_path: Path) -> bytes | None:
    """The ground the window stands on, or None if the pack has no art for it."""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            return _terrain(zf) or _verbatim(zf, set(zf.namelist()))
    except (OSError, zipfile.BadZipFile):
        return None


def build_grass(zip_path: Path) -> bytes | None:
    """The pack's grass block side, verbatim, to lay across the top."""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            raw = zf.read(GRASS)
            with Image.open(io.BytesIO(raw)) as im:
                im.verify()
            return raw
    except (KeyError, OSError, ValueError, zipfile.BadZipFile):
        return None


def cache_dir() -> Path:
    """Per-user, not beside the exe: the exe may sit somewhere unwritable, and
    a tool should not scribble next to itself."""
    import os
    base = (os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME")
            or os.path.expanduser("~/.cache"))
    return Path(base) / "MCPackConverter"


def main(argv: list[str] | None = None) -> int:
    """Rebuild the wall the app ships, from a converted pack.

    The background is a fixed asset, so it changes only when it is rebuilt on
    purpose:  python -m mc_pack_converter.webui.wall <converted-pack.zip>
    """
    import sys
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(__doc__ and main.__doc__, file=sys.stderr)
        return 2
    assets = Path(__file__).parent / "assets"
    ground, grass = build_wall(Path(args[0])), build_grass(Path(args[0]))
    if not ground or not grass:
        print(f"pack has no stone/ore/grass to build a wall from: {args[0]}",
              file=sys.stderr)
        return 1
    (assets / "wall.png").write_bytes(ground)
    (assets / "grass.png").write_bytes(grass)
    print(f"wrote {assets / 'wall.png'} and {assets / 'grass.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
