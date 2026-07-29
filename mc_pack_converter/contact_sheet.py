"""Render sliced sprites into one labelled PNG for eyeball review.

Written next to the output archive, never inside it: `write_output` zips
everything under the working root, so a sheet placed there would ship
inside the pack.
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw

# The 1.14 slicer's source atlases. Outputs cut from these are what the sheet
# shows; the GUI sprites from the 1.20.2 slicer are excluded to keep it small.
ATLAS_1_14 = {
    "assets/minecraft/textures/particle/particles.png",
    "assets/minecraft/textures/entity/explosion.png",
    "assets/minecraft/textures/painting/paintings_kristoffer_zetterstrand.png",
}

TILE = 64          # sprites are scaled to fit this box, nearest-neighbour
PAD = 6
LABEL_H = 12
COLS = 8
CELL_W = 104       # wider than TILE so sprite names fit under each tile
CELL_H = TILE + PAD * 2 + LABEL_H
CHECK = 8          # checkerboard square size, so alpha reads
NAME_CHARS = 16

BG = (32, 32, 32, 255)
LIGHT = (90, 90, 90, 255)
DARK = (70, 70, 70, 255)
TEXT = (230, 230, 230, 255)


def _checkerboard() -> Image.Image:
    board = Image.new("RGBA", (TILE, TILE), DARK)
    d = ImageDraw.Draw(board)
    for y in range(0, TILE, CHECK):
        for x in range(0, TILE, CHECK):
            if (x // CHECK + y // CHECK) % 2 == 0:
                d.rectangle([x, y, x + CHECK - 1, y + CHECK - 1], fill=LIGHT)
    return board


def build_contact_sheet(root: Path, rel_paths: list[str], out_path: Path) -> bool:
    """Render each rel_path (relative to root) as a labelled tile.

    Returns False, writing nothing, if there is nothing to draw.
    """
    entries = [(r, root / r) for r in sorted(rel_paths)]
    entries = [(r, p) for r, p in entries if p.exists()]
    if not entries:
        return False
    rows = (len(entries) + COLS - 1) // COLS
    sheet = Image.new("RGBA", (COLS * CELL_W, rows * CELL_H), BG)
    board = _checkerboard()
    draw = ImageDraw.Draw(sheet)
    for i, (rel, path) in enumerate(entries):
        ox = (i % COLS) * CELL_W + (CELL_W - TILE) // 2
        oy = (i // COLS) * CELL_H + PAD
        sheet.paste(board, (ox, oy))
        with Image.open(path) as im:
            im = im.convert("RGBA")
            scale = TILE / max(im.width, im.height)
            w, h = max(1, round(im.width * scale)), max(1, round(im.height * scale))
            im = im.resize((w, h), Image.NEAREST)
            sheet.paste(im, (ox + (TILE - w) // 2, oy + (TILE - h) // 2), im)
        draw.text((ox, oy + TILE + 2), Path(rel).stem[:NAME_CHARS], fill=TEXT)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    return True
