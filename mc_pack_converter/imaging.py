from __future__ import annotations
from pathlib import Path
from PIL import Image

def png_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as im:
        return im.size

def is_valid_png(path: Path) -> bool:
    try:
        if path.stat().st_size == 0:
            return False
        with Image.open(path) as im:
            im.verify()
        return True
    except Exception:
        return False

def crop_paste(src: Path, dst: Path, regions: list[dict],
               out_size: tuple[int, int]) -> None:
    with Image.open(src) as im:
        im = im.convert("RGBA")
        canvas = Image.new("RGBA", out_size, (0, 0, 0, 0))
        for r in regions:
            sx, sy, sw, sh = r["src"]
            dx, dy, dw, dh = r["dst"]
            piece = im.crop((sx, sy, sx + sw, sy + sh))
            if (sw, sh) != (dw, dh):
                piece = piece.resize((dw, dh), Image.NEAREST)
            canvas.paste(piece, (dx, dy))
        dst.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(dst)

def slice_sheet(sheet: Path, out_dir: Path, specs: list[dict]) -> list[Path]:
    written: list[Path] = []
    with Image.open(sheet) as im:
        im = im.convert("RGBA")
        for s in specs:
            x, y, w, h = s["x"], s["y"], s["w"], s["h"]
            crop = im.crop((x, y, x + w, y + h))
            out = out_dir / f"{s['name']}.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            crop.save(out)
            written.append(out)
    return written
