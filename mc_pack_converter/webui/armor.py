"""Draw an armor UV sheet onto a humanoid body.

Minecraft entity models are axis-aligned boxes, each face taking a fixed
rectangle of the texture. Twelve flat UV sheets mean nothing to a human eye;
on a body they read instantly as right or wrong.

The camera is fixed and the boxes are axis-aligned, so each visible face maps
to a parallelogram under a constant affine transform -- no perspective divide,
and no depth sort: for a fixed camera and a fixed skeleton the painter's order
is constant, so parts nearer the camera simply paint last.

This is an oblique (cabinet) 3/4 projection rather than a true isometric one:
the front face stays an undistorted rectangle, so the art being judged is not
resampled. Three constants define the whole view.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from PIL import Image

# The whole projection. Adjust the view by changing these three numbers.
X_STEP = 5.0   # screen px per model unit along +x (right)
Y_STEP = 5.0   # screen px per model unit along +y (up)
Z_STEP = 2.5   # screen px per model unit along +z (toward the viewer);
               # depth also lifts by half this, which is what turns a flat
               # elevation into a 3/4 view.

CANVAS = (150, 210)
ORIGIN = (75, 190)   # where model (0, 0, 0) lands on the canvas


@dataclass(frozen=True)
class Box:
    """One axis-aligned box. UV rects are in the 64x32 base texture."""
    name: str
    size: tuple[int, int, int]              # w, h, d in model units
    origin: tuple[float, float, float]      # left-bottom-front corner
    front: tuple[int, int, int, int]        # u, v, w, h
    top: tuple[int, int, int, int]
    right: tuple[int, int, int, int]
    # The three faces a fixed 3/4 camera never shows. Optional so the model
    # still renders from the front-only definitions, but a box that turns
    # needs all six or it goes hollow as it comes about.
    back: tuple[int, int, int, int] | None = None
    left: tuple[int, int, int, int] | None = None
    bottom: tuple[int, int, int, int] | None = None


# Vanilla's 64x32 humanoid layout. In this layout the left limbs have no UVs
# of their own and mirror the right ones, which is why the pairs share rects.
HUMANOID: tuple[Box, ...] = (
    Box("left_leg",  (4, 12, 4), (0, 0, -2),
        front=(4, 20, 4, 12),  top=(4, 16, 4, 4),  right=(0, 20, 4, 12),
        back=(12, 20, 4, 12),  left=(8, 20, 4, 12), bottom=(8, 16, 4, 4)),
    Box("right_leg", (4, 12, 4), (-4, 0, -2),
        front=(4, 20, 4, 12),  top=(4, 16, 4, 4),  right=(0, 20, 4, 12),
        back=(12, 20, 4, 12),  left=(8, 20, 4, 12), bottom=(8, 16, 4, 4)),
    Box("body",      (8, 12, 4), (-4, 12, -2),
        front=(20, 20, 8, 12), top=(20, 16, 8, 4), right=(16, 20, 4, 12),
        back=(32, 20, 8, 12),  left=(28, 20, 4, 12), bottom=(28, 16, 8, 4)),
    Box("left_arm",  (4, 12, 4), (4, 12, -2),
        front=(44, 20, 4, 12), top=(44, 16, 4, 4), right=(40, 20, 4, 12),
        back=(52, 20, 4, 12),  left=(48, 20, 4, 12), bottom=(48, 16, 4, 4)),
    Box("right_arm", (4, 12, 4), (-8, 12, -2),
        front=(44, 20, 4, 12), top=(44, 16, 4, 4), right=(40, 20, 4, 12),
        back=(52, 20, 4, 12),  left=(48, 20, 4, 12), bottom=(48, 16, 4, 4)),
    Box("head",      (8, 8, 8),  (-4, 24, -4),
        front=(8, 8, 8, 8),    top=(8, 0, 8, 8),   right=(0, 8, 8, 8),
        back=(24, 8, 8, 8),    left=(16, 8, 8, 8),  bottom=(16, 0, 8, 8)),
)

FACES = ("front", "back", "right", "left", "top", "bottom")


def _yaw(x: float, z: float, yaw: float) -> tuple[float, float]:
    """Turn a point about the vertical axis. yaw is radians, 0 = face-on."""
    c, s = math.cos(yaw), math.sin(yaw)
    return (x * c + z * s, -x * s + z * c)


def project(x: float, y: float, z: float, yaw: float = 0.0,
            origin: tuple[float, float] = ORIGIN) -> tuple[float, float]:
    """Model space to canvas pixels. +y is up, +z is toward the viewer.

    yaw defaults to 0, which is the fixed 3/4 view the still render uses.
    """
    if yaw:
        x, z = _yaw(x, z, yaw)
    return (origin[0] + x * X_STEP + z * Z_STEP,
            origin[1] - y * Y_STEP - z * Z_STEP * 0.5)


def depth_of(x: float, y: float, z: float, yaw: float = 0.0) -> float:
    """Painter's-order key: bigger is nearer.

    This projection is parallel, so screen position is unchanged by sliding a
    point along one fixed direction. z varies along that direction, which makes
    the turned z a valid depth -- no perspective divide, and no special case
    when a face swings edge-on.
    """
    if yaw:
        _, z = _yaw(x, z, yaw)
    return z


def face_corners(box: Box, face: str):
    """Model-space (top_left, top_right, bottom_left) of one face.

    Ordered so the texture lands right-side-up when the face is seen from
    outside the box, which is what keeps a turning model from showing mirrored
    art as each face comes round.
    """
    ox, oy, oz = box.origin
    w, h, d = box.size
    xr, yt, zf = ox + w, oy + h, oz + d
    if face == "front":       # +z
        return ((ox, yt, zf), (xr, yt, zf), (ox, oy, zf))
    if face == "back":        # -z, so left and right swap
        return ((xr, yt, oz), (ox, yt, oz), (xr, oy, oz))
    if face == "right":       # +x
        return ((xr, yt, zf), (xr, yt, oz), (xr, oy, zf))
    if face == "left":        # -x
        return ((ox, yt, oz), (ox, yt, zf), (ox, oy, oz))
    if face == "top":         # +y
        return ((ox, yt, oz), (xr, yt, oz), (ox, yt, zf))
    if face == "bottom":      # -y
        return ((ox, oy, zf), (xr, oy, zf), (ox, oy, oz))
    raise ValueError(f"not a face: {face}")


def face_quad(box: Box, face: str, yaw: float = 0.0,
              origin: tuple[float, float] = ORIGIN):
    """Destination (top_left, top_right, bottom_left) in canvas pixels."""
    return tuple(project(*p, yaw=yaw, origin=origin)
                 for p in face_corners(box, face))


def _affine_coeffs(p0, p1, p2, w: float, h: float):
    """PIL wants the DEST->SRC map, so invert the SRC->DEST parallelogram.

    Raises on a degenerate face rather than silently drawing nothing: a
    collapsed parallelogram is the exact failure a golden image would bake in
    as 'expected' if the golden were generated from broken output.
    """
    ux, uy = (p1[0] - p0[0]) / w, (p1[1] - p0[1]) / w
    vx, vy = (p2[0] - p0[0]) / h, (p2[1] - p0[1]) / h
    det = ux * vy - uy * vx
    if abs(det) < 1e-9:
        raise ValueError("degenerate face transform")
    a, b = vy / det, -vx / det
    d, e = -uy / det, ux / det
    return (a, b, -(a * p0[0] + b * p0[1]),
            d, e, -(d * p0[0] + e * p0[1]))


def render_boxes(texture: Image.Image, boxes, yaw: float = 0.0,
                 base: int = 64, canvas_size: tuple[int, int] = CANVAS,
                 origin: tuple[float, float] = ORIGIN) -> Image.Image:
    """Draw the given boxes onto a fresh canvas, far faces first.

    At yaw 0 with only the three front-facing UVs defined this reproduces the
    original fixed view exactly. Once the model turns, every face that has a
    UV is drawn and ordered by depth: painting back-to-front means a face
    swinging out of sight is simply overpainted, so there is no cull to get
    wrong and no flicker as a face passes edge-on.
    """
    tex = texture.convert("RGBA")
    scale = max(1, tex.width // base)  # chainmail is 128x64; the rest are 64x32
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))

    ordered = []
    for box in boxes:
        for face in FACES:
            uv = getattr(box, face, None)
            if uv is None:
                continue
            corners = face_corners(box, face)
            # depth at the face centre; the 4th corner is TR + BL - TL
            cx = (corners[1][0] + corners[2][0]) / 2
            cy = (corners[1][1] + corners[2][1]) / 2
            cz = (corners[1][2] + corners[2][2]) / 2
            ordered.append((depth_of(cx, cy, cz, yaw), box, face, uv))
    ordered.sort(key=lambda t: t[0])

    for _, box, face, (u, v, w, h) in ordered:
        patch = tex.crop((u * scale, v * scale,
                          (u + w) * scale, (v + h) * scale))
        try:
            coeffs = _affine_coeffs(*face_quad(box, face, yaw, origin),
                                    patch.width, patch.height)
        except ValueError:
            continue  # edge-on at this angle: zero width, nothing to show
        drawn = patch.transform(canvas_size, Image.AFFINE, coeffs, Image.NEAREST)
        canvas.alpha_composite(drawn)
    return canvas


def render_armor(texture: Image.Image, yaw: float = 0.0) -> Image.Image:
    """One armor UV sheet, drawn on the humanoid model."""
    return render_boxes(texture, HUMANOID, yaw)


def spin_frames(texture: Image.Image, count: int = 24) -> list[Image.Image]:
    """One full turn of the model, as `count` evenly spaced frames."""
    return [render_armor(texture, 2 * math.pi * i / count) for i in range(count)]


# --- a single block texture on a turning cube --------------------------------
#
# A block texture is 16x16 (or a multiple), and the same image goes on all six
# faces. Seeing it on a cube shows two things a flat tile cannot: how the art
# tiles against itself at an edge, and how the top reads against the side.

CUBE_CANVAS = (140, 130)
# The cube is centred on the model origin, so it reaches +-50 px vertically
# (8 units of height at Y_STEP, plus 8 of depth at half Z_STEP) and +-60
# horizontally. Centre it or it clips.
CUBE_ORIGIN = (70, 65)


# The cube is always 16 MODEL units, whatever the texture's resolution. A
# 32x pack does not get a cube twice the size -- it gets the same cube at
# twice the detail, which is what render_boxes' `scale` already handles.
CUBE_UNITS = 16


def cube_box() -> Box:
    """A cube centred on the origin, textured identically on all six faces."""
    uv = (0, 0, CUBE_UNITS, CUBE_UNITS)
    half = CUBE_UNITS / 2
    return Box("cube", (CUBE_UNITS, CUBE_UNITS, CUBE_UNITS), (-half, -half, -half),
               front=uv, top=uv, right=uv, back=uv, left=uv, bottom=uv)


def render_cube(texture: Image.Image, yaw: float = 0.0) -> Image.Image:
    """One block texture drawn on a cube, turned by `yaw` radians."""
    return render_boxes(texture, [cube_box()], yaw, base=CUBE_UNITS,
                        canvas_size=CUBE_CANVAS, origin=CUBE_ORIGIN)


def cube_spin_frames(frames: list[Image.Image], count: int = 24
                     ) -> list[Image.Image]:
    """Turn a cube through a full circle while its texture animates.

    The angle and the animation frame advance together in ONE loop, so an
    N-frame result costs N renders rather than angles x animation-frames. When
    the texture is a still, `frames` is a single image and only the cube turns.
    """
    return [render_cube(frames[i % len(frames)], 2 * math.pi * i / count)
            for i in range(count)]


# --- textures that are not blocks --------------------------------------------
#
# Fire is not a cube, and it is not a cross either. Minecraft clings it to the
# VERTICAL FACES of the block it burns on, so what you see is the block's side
# profile in flame with nothing across its middle and nothing on top. Drawing
# it as two planes crossed through the centre -- which this module did until
# Mason said "it looks like a cross in the middle whereas in the game its
# rended on all sides of a block" -- puts flame inside the block volume and
# makes it narrower than the block it is burning on.


def fire_boxes() -> list[Box]:
    """The four upright quads on a block's vertical faces.

    Each is flat in one axis and pinned to that axis's surface. A quad carries
    the UVs of the two faces that share its plane, so it reads the same from
    either side -- fire has no back.
    """
    uv = (0, 0, CUBE_UNITS, CUBE_UNITS)
    half = CUBE_UNITS / 2
    flat_z = (CUBE_UNITS, CUBE_UNITS, 0)
    flat_x = (0, CUBE_UNITS, CUBE_UNITS)
    return [
        Box("north", flat_z, (-half, -half, -half), front=uv, back=uv,
            top=None, right=None, left=None, bottom=None),
        Box("south", flat_z, (-half, -half, half), front=uv, back=uv,
            top=None, right=None, left=None, bottom=None),
        Box("west", flat_x, (-half, -half, -half), right=uv, left=uv,
            front=None, top=None, back=None, bottom=None),
        Box("east", flat_x, (half, -half, -half), right=uv, left=uv,
            front=None, top=None, back=None, bottom=None),
    ]


def render_fire(texture: Image.Image, yaw: float = 0.0) -> Image.Image:
    """Fire on the four faces of the block it burns on, turned by `yaw`.

    ONE render_boxes call, not four composited in sequence: it orders every
    face of every box by depth together, so a far quad can never paint over a
    near one. That is precisely what the old two-call render_crossed got
    wrong, and it only got away with it because planes crossed at the centre
    intersect rather than occlude.
    """
    return render_boxes(texture, fire_boxes(), yaw, base=CUBE_UNITS,
                        canvas_size=CUBE_CANVAS, origin=CUBE_ORIGIN)


def fire_spin_frames(frames: list[Image.Image], count: int = 24
                     ) -> list[Image.Image]:
    """A full turn of the fire quads while the texture animates."""
    return [render_fire(frames[i % len(frames)], 2 * math.pi * i / count)
            for i in range(count)]


# --- the nether portal is a plane, not a block and not fire -------------------
#
# The portal is one flat quad through the middle of its block, along whichever
# axis the portal was built on. Crossed planes show it from both orientations
# at once, which is why fire moving onto the block's faces must NOT take the
# portal with it -- they were only ever sharing a code path, not a shape.


def plane_box() -> Box:
    """A flat upright quad. Only front and back exist; a plane has no sides."""
    uv = (0, 0, CUBE_UNITS, CUBE_UNITS)
    half = CUBE_UNITS / 2
    return Box("plane", (CUBE_UNITS, CUBE_UNITS, 0), (-half, -half, 0),
               front=uv, top=None, right=uv, back=uv, left=None, bottom=None)


def render_crossed(texture: Image.Image, yaw: float = 0.0) -> Image.Image:
    """One texture drawn as two planes crossed at right angles."""
    canvas = Image.new("RGBA", CUBE_CANVAS, (0, 0, 0, 0))
    for turn in (yaw, yaw + math.pi / 2):
        canvas.alpha_composite(
            render_boxes(texture, [plane_box()], turn, base=CUBE_UNITS,
                         canvas_size=CUBE_CANVAS, origin=CUBE_ORIGIN))
    return canvas


def crossed_spin_frames(frames: list[Image.Image], count: int = 24
                        ) -> list[Image.Image]:
    """A full turn of the crossed planes while the texture animates."""
    return [render_crossed(frames[i % len(frames)], 2 * math.pi * i / count)
            for i in range(count)]
