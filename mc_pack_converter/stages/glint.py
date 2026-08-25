"""Tile the enchant glint so it keeps the density it had in 1.8.9.

Measured from vanilla's own glint, which is the only ground truth available
without reading the game: 1.8.9 and 1.12.2 ship a 64x64 glint carrying 2
streaks across the texture, and 1.16.5 through 26.2 ship 128x128 carrying 4.
Mojang did not upscale the art -- the texel period stayed 32px both times and
the streak count doubled. Their in-game glint did not visibly double in
density, so the game must now tile the glint half as far to compensate.

A converted 1.8.9 pack therefore renders its glint at half the on-screen
density the pack author drew it for: the same art, streaks twice as wide.
Reported from the game as the glint looking "wierd".

Tiling the art 2x2 doubles its streaks across the texture and cancels the
game's halved tiling exactly, which is the same transform Mojang applied to
their own glint. It costs one quadrupled texture -- 256x256 becomes 512x512,
against a 128x128 vanilla -- and needs no core shader override, so OptiFine,
which replaces core shaders wholesale, cannot interfere with it.

Runs after `flatten_rename`, which is what creates the two modern names.
"""
from __future__ import annotations

from PIL import Image

from ..imaging import is_valid_png
from ..pipeline import ConversionContext, Severity

# The two names modern Minecraft reads. Both come from the pack's single
# 1.8.9 glint, so both need the same correction.
_GLINTS = ("enchanted_glint_item.png", "enchanted_glint_armor.png")


def glint(ctx: ConversionContext) -> None:
    misc = ctx.root / "assets" / "minecraft" / "textures" / "misc"
    for name in _GLINTS:
        path = misc / name
        if not path.exists() or not is_valid_png(path):
            continue
        with Image.open(path) as im:
            src = im.convert("RGBA")
        w, h = src.size
        tiled = Image.new("RGBA", (w * 2, h * 2))
        for x in (0, w):
            for y in (0, h):
                tiled.paste(src, (x, y))
        tiled.save(path)
        ctx.add("glint", Severity.INFO,
                f"{name} tiled 2x2 -> {w * 2}x{h * 2} "
                "(modern tiles the glint half as far as 1.8.9)",
                path=str(path))
