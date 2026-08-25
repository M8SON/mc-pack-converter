"""An OptiFine sky layer, seen from the ground.

A custom sky ships as one image holding six cube faces. Flat, it is an
unreadable 6144x4096 sheet; the question a pack author has is what the sky
looks like standing in the world, so this renders that.

THE LAYOUT WAS MEASURED, NOT ASSUMED. OptiFine's own sky.properties
documentation specifies the fade times, blend modes and rotation but never
states how the six faces are arranged in the file. Splitting a real 6144x4096
sky (M8SON 1.8 PVP PACK, cloud1.png) into a 3x2 grid of 2048px squares and
matching every face's right edge against every other face's left edge gives
one closed loop -- (0,2) -> (1,0) -> (1,1) -> (1,2) -> back -- each seam
scoring 1.45-1.66 against a 1.06 typical interior step, while every
non-neighbouring pair scores 3.2 to 11.2. The remaining two cells are the
poles: (0,0) is the nadir (it carries the pack's watermark) and (0,1) the
zenith.

What is NOT determined by that measurement is absolute compass orientation --
which ring face is north. Nothing here claims one: the faces are a ring in
cyclic order, and yaw is relative to wherever the ring starts. For judging
art that is enough, and it is the honest limit of what the edges can tell us.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image

# Cell positions in the 3x2 grid, from the derivation above.
_DOWN, _UP = (0, 0), (0, 1)
_RING = [(0, 2), (1, 0), (1, 1), (1, 2)]

# A person looks slightly up at a sky, and the horizon sits low in frame.
PITCH = 18.0
FOV = 100.0


def faces(im: Image.Image) -> dict:
    """The six cube faces: the two poles and the horizon ring, in order.

    RGBA, not RGB. A sky texture may carry its transparency in a palette tRNS
    chunk rather than an alpha band -- M8SON's sky_sunflare.png is mode P with
    tRNS=0 and is 83.6% fully clear -- and converting such a file to RGB turns
    every clear pixel into whatever colour the palette holds there. For that
    sunflare it is white, so an `add` layer painted the entire sky white.
    """
    im = im.convert("RGBA")
    w, h = im.size
    cw, ch = w // 3, h // 2

    def cell(rc):
        r, c = rc
        return im.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch))

    return {"up": cell(_UP), "down": cell(_DOWN),
            "ring": [cell(rc) for rc in _RING]}


def render_sky(im: Image.Image, yaw: float = 0.0, size=(320, 200),
               fov: float = FOV, pitch: float = PITCH) -> Image.Image:
    """The sky as seen from the ground, looking `yaw` degrees around the ring.

    One ray per output pixel into the cube. At preview size that is 64k rays,
    which numpy does in a single vectorised pass -- small next to the seconds
    the pack's own textures already cost to decode.
    """
    f = faces(im)
    ring = [np.asarray(face, float) for face in f["ring"]]
    up = np.asarray(f["up"], float)
    n = ring[0].shape[0]

    w, h = size
    # Ray directions for a pinhole camera: +z forward, +y up, +x right.
    ar = w / h
    t = math.tan(math.radians(fov) / 2)
    px = (np.arange(w) + 0.5) / w * 2 - 1
    py = 1 - (np.arange(h) + 0.5) / h * 2
    dx = px[None, :] * t * ar
    dy = np.broadcast_to(py[:, None] * t, (h, w))
    dz = np.ones((h, w))

    # Pitch the camera up, then yaw it around the ring.
    p = math.radians(pitch)
    dy, dz = dy * math.cos(p) + dz * math.sin(p), -dy * math.sin(p) + dz * math.cos(p)
    a = math.radians(yaw)
    dx, dz = dx * math.cos(a) + dz * math.sin(a), -dx * math.sin(a) + dz * math.cos(a)

    out = np.zeros((h, w, 4))
    horiz = np.maximum(np.abs(dx), np.abs(dz))
    looking_up = dy > horiz

    # The zenith face, seen through its own square.
    if looking_up.any():
        u = np.clip((dx[looking_up] / dy[looking_up] + 1) / 2, 0, 1)
        v = np.clip((dz[looking_up] / dy[looking_up] + 1) / 2, 0, 1)
        out[looking_up] = up[(v * (n - 1)).astype(int), (u * (n - 1)).astype(int)]

    # The ring: which quarter turn the ray falls in, and where across it.
    side = ~looking_up
    if side.any():
        ang = np.arctan2(dx[side], dz[side]) % (2 * math.pi)
        quarter = (ang / (math.pi / 2)).astype(int) % 4
        across = (ang % (math.pi / 2)) / (math.pi / 2)
        # Height on the face, from the ray's rise over its horizontal reach.
        rise = dy[side] / np.maximum(horiz[side], 1e-6)
        down = np.clip((1 - rise) / 2, 0, 1)
        ix = (across * (n - 1)).astype(int)
        iy = (down * (n - 1)).astype(int)
        for q in range(4):
            m = quarter == q
            if m.any():
                sel = np.zeros_like(side)
                sel[side] = m
                out[sel] = ring[q][iy[m], ix[m]]

    return Image.fromarray(out.astype(np.uint8), "RGBA")
