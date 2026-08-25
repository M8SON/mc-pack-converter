"""The pack's sky layers stacked the way the game stacks them.

The per-layer previews in sheet.py answer "what is this layer"; they cannot
answer "what does my sky look like", because the game never shows a layer
alone. It draws every layer whose fade window is open at the current time,
in numeric order, each through its own blend mode.

PORTED FROM THE SHIPPED CODE, NOT FROM THE DOCUMENTATION. The timing here
follows net/optifine/CustomSkyLayer in OptiFine 26.1.2_HD_U_K1_pre2 --
getFadeBrightness, timeBetween and normalizeTime. That distinction earned
itself: the same jar's doc/sky.properties states two things its own classes
do not do, and one of them ("reads until a .properties file is not found")
put a false "never loads" warning on 77 of the 152 corpus packs that ship a
custom sky before it was measured in game.

WHAT THIS DOES NOT REPRODUCE. There is no vanilla sky underneath -- Minecraft
computes its sky colour rather than shipping it as a texture, so inventing a
gradient would put art in the report that no pack drew. Layers composite over
black, which shows exactly what the pack contributes and nothing it does not.
An `add` layer therefore reads darker here than it does in game.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

DAY = 24000

# 6:00 is tick 0, so the clock leads the tick count by six hours. The four
# reference points in OptiFine's doc (6:00=0, 12:00=6000, 18:00=12000,
# 0:00=18000) all fall out of this and are pinned by tests.
_DAWN_MINUTES = 6 * 60
_TICKS_PER_MINUTE = DAY / (24 * 60)

# The times the report shows. Not arbitrary: dawn and dusk are when fade
# windows are actually opening and closing, which is where a mistake in the
# pack's timings shows up, and midnight is the only one that shows a starfield.
TIMES = (("Dawn", "6:00"), ("Noon", "12:00"),
         ("Dusk", "18:00"), ("Midnight", "0:00"))


def parse_time(text: str) -> int:
    """An "hh:mm" clock time as a tick in [0, DAY)."""
    hours, _, minutes = text.strip().partition(":")
    total = int(hours) * 60 + int(minutes or 0)
    return int(round((total - _DAWN_MINUTES) * _TICKS_PER_MINUTE)) % DAY


def normalize(ticks: int) -> int:
    """CustomSkyLayer.normalizeTime: fold a difference back into one day."""
    return ticks % DAY


def time_between(ticks: int, start: int, end: int) -> bool:
    """CustomSkyLayer.timeBetween, wrap included.

    A window that runs past midnight has start > end, and is then the union of
    two ranges rather than the gap between them -- which is why a starfield
    written 18:00-5:25 is on at 2am and not for the nineteen hours between.
    """
    if start <= end:
        return start <= ticks <= end
    return ticks >= start or ticks <= end


def _times(props: dict) -> tuple[int, int, int, int] | None:
    """The four fade ticks, or None if the layer cannot state a window.

    startFadeOut is the one real packs omit -- 1778 of the 2120 sky layers in
    the 173-pack corpus ship exactly three keys -- and isValid derives it from
    the other three rather than rejecting the layer, so this does too.
    """
    try:
        start_in = parse_time(props["startFadeIn"])
        end_in = parse_time(props["endFadeIn"])
        end_out = parse_time(props["endFadeOut"])
    except (KeyError, ValueError):
        return None
    if "startFadeOut" in props:
        try:
            start_out = parse_time(props["startFadeOut"])
        except ValueError:
            return None
    else:
        # isValid: startFadeOut = endFadeOut - (endFadeIn - startFadeIn), the
        # fade out lasting as long as the fade in.
        start_out = normalize(end_out - normalize(end_in - start_in))
    return start_in, end_in, start_out, end_out


def brightness(props: dict, ticks: int) -> float:
    """How strongly this layer draws at this time: 0 through 1.

    CustomSkyLayer.getFadeBrightness. A layer with no usable window is treated
    as dark rather than as always-on: the doc claims the opposite ("If no
    times are specified the layer is always rendered") but no pack in the
    corpus omits them, so nothing real depends on the claim.
    """
    window = _times(props)
    if window is None:
        return 0.0
    start_in, end_in, start_out, end_out = window

    if time_between(ticks, start_in, end_in):
        span = normalize(end_in - start_in)
        return 1.0 if span == 0 else normalize(ticks - start_in) / span
    if time_between(ticks, end_in, start_out):
        return 1.0
    if time_between(ticks, start_out, end_out):
        span = normalize(end_out - start_out)
        return 0.0 if span == 0 else 1.0 - normalize(ticks - start_out) / span
    return 0.0


# --- blending ---------------------------------------------------------------
#
# Counted across every sky layer in the 173-pack corpus: add 1667 (49 of them
# by leaving blend unset, which OptiFine documents as defaulting to add),
# replace 183, screen 123, burn 71, multiply 56, alpha 16, dodge 2, overlay 1,
# and one pack that wrote `blend=blend`. All eight real modes are here; the
# typo falls through to add, exactly as an unset value does.

def _blend(base: np.ndarray, layer: np.ndarray, mode: str) -> np.ndarray:
    if mode in ("replace", "alpha"):
        return layer
    if mode == "multiply":
        return base * layer
    if mode == "screen":
        return 1.0 - (1.0 - base) * (1.0 - layer)
    if mode == "subtract":
        return base - layer
    if mode == "dodge":
        return base / np.clip(1.0 - layer, 1e-6, None)
    if mode == "burn":
        return 1.0 - (1.0 - base) / np.clip(layer, 1e-6, None)
    if mode == "overlay":
        return np.where(base < 0.5, 2.0 * base * layer,
                        1.0 - 2.0 * (1.0 - base) * (1.0 - layer))
    return base + layer                      # add, and OptiFine's default


def composite(layers: list[tuple[Image.Image, str, float]]) -> Image.Image:
    """Stack rendered layers over black, in the order given.

    Each entry is (rendered view, blend mode, brightness). Brightness scales
    the layer before blending, which is what a fade does for every mode except
    replace: there OptiFine takes the full pixel whenever brightness is above
    zero -- "There is no gradual fading with this method" -- and this follows
    it rather than the more obvious thing.
    """
    if not layers:
        raise ValueError("nothing to composite")
    width, height = layers[0][0].size
    out = np.zeros((height, width, 3), dtype=np.float32)
    for view, mode, level in layers:
        rgba = np.asarray(view.convert("RGBA"), dtype=np.float32) / 255.0
        # Premultiply: a clear pixel must contribute nothing whatever the
        # colour sitting under its zero alpha. Skipping this is what turned
        # the reference pack's 83.6%-transparent sunflare into a white sheet.
        arr = rgba[..., :3] * rgba[..., 3:4]
        if mode != "replace":
            arr = arr * level
        out = np.clip(_blend(out, arr, mode), 0.0, 1.0)
    return Image.fromarray((out * 255.0 + 0.5).astype(np.uint8), "RGB")
