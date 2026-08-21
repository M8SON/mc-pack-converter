"""The enchant glint, on the pack's own art, moving.

A glint is a scrolling overlay: flat, it is diagonal streaks on a square and
tells you nothing about whether the enchantment will read in game. The
question a pack author actually has is "does my sword look enchanted", so the
preview answers that one -- the pack's sprite, the pack's glint, in motion.

How Minecraft draws it, and what this reproduces: the glint is masked to the
sprite's opaque pixels, added to what is underneath, and scrolled diagonally
on a loop. What this does NOT reproduce is the game's exact colour modulator
and alpha curve, which live in the glint shader; the preview is for judging
the art's density and motion, not for matching brightness pixel for pixel.
"""
from __future__ import annotations

from PIL import Image, ImageChops

# One full loop of the scroll. Matches the frame count the sheet's other
# animated previews use, so the page plays them all at one speed.
FRAMES = 24

# How far the glint tiles across the sprite. The glint is a small texture
# scrolled over a 16px sprite; showing the whole thing at once would be one
# streak. Two repeats reads as a shimmer at sprite scale.
REPEATS = 2


def glint_frames(item: Image.Image, glint: Image.Image,
                 count: int = FRAMES) -> list[Image.Image]:
    """One scroll cycle of `glint` over `item`, masked to the item's pixels."""
    item = item.convert("RGBA")
    w, h = item.size
    mask = item.getchannel("A")

    # Sized so one scroll step is a whole pixel: a fractional step would
    # resample the glint every frame and blur the art being judged.
    tile = glint.convert("RGB").resize((w * REPEATS, h * REPEATS), Image.NEAREST)
    tw, th = tile.size

    frames = []
    for i in range(count):
        shift = round(i * tw / count)
        # Scrolled diagonally, the direction the game moves it.
        rolled = Image.new("RGB", (tw, th))
        rolled.paste(tile, (-shift, -shift))
        rolled.paste(tile, (tw - shift, -shift))
        rolled.paste(tile, (-shift, th - shift))
        rolled.paste(tile, (tw - shift, th - shift))

        over = rolled.crop((0, 0, w, h))
        # Added, not pasted: an enchantment brightens the art underneath it.
        lit = ImageChops.add(item.convert("RGB"), over).convert("RGBA")
        lit.putalpha(mask)
        frames.append(lit)
    return frames
