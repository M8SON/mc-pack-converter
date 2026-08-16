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


# Vanilla's 64x32 humanoid layout. In this layout the left limbs have no UVs
# of their own and mirror the right ones, which is why the pairs share rects.
HUMANOID: tuple[Box, ...] = (
    Box("left_leg",  (4, 12, 4), (0, 0, -2),
        front=(4, 20, 4, 12),  top=(4, 16, 4, 4),  right=(0, 20, 4, 12)),
    Box("right_leg", (4, 12, 4), (-4, 0, -2),
        front=(4, 20, 4, 12),  top=(4, 16, 4, 4),  right=(0, 20, 4, 12)),
    Box("body",      (8, 12, 4), (-4, 12, -2),
        front=(20, 20, 8, 12), top=(20, 16, 8, 4), right=(16, 20, 4, 12)),
    Box("left_arm",  (4, 12, 4), (4, 12, -2),
        front=(44, 20, 4, 12), top=(44, 16, 4, 4), right=(40, 20, 4, 12)),
    Box("right_arm", (4, 12, 4), (-8, 12, -2),
        front=(44, 20, 4, 12), top=(44, 16, 4, 4), right=(40, 20, 4, 12)),
    Box("head",      (8, 8, 8),  (-4, 24, -4),
        front=(8, 8, 8, 8),    top=(8, 0, 8, 8),   right=(0, 8, 8, 8)),
)


def project(x: float, y: float, z: float) -> tuple[float, float]:
    """Model space to canvas pixels. +y is up, +z is toward the viewer."""
    return (ORIGIN[0] + x * X_STEP + z * Z_STEP,
            ORIGIN[1] - y * Y_STEP - z * Z_STEP * 0.5)


def face_quad(box: Box, face: str):
    """Destination (top_left, top_right, bottom_left) for one visible face."""
    ox, oy, oz = box.origin
    w, h, d = box.size
    if face == "front":       # the z = oz + d plane, facing the viewer
        zf = oz + d
        return (project(ox, oy + h, zf), project(ox + w, oy + h, zf),
                project(ox, oy, zf))
    if face == "top":         # the y = oy + h plane, seen from above
        yt = oy + h
        return (project(ox, yt, oz), project(ox + w, yt, oz),
                project(ox, yt, oz + d))
    if face == "right":       # the x = ox + w plane, the viewer's right
        xr = ox + w
        return (project(xr, oy + h, oz + d), project(xr, oy + h, oz),
                project(xr, oy, oz + d))
    raise ValueError(f"not a visible face: {face}")


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


def render_boxes(texture: Image.Image, boxes) -> Image.Image:
    """Draw the given boxes, in the order given, onto a fresh canvas."""
    tex = texture.convert("RGBA")
    scale = max(1, tex.width // 64)   # chainmail is 128x64; the rest are 64x32
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for box in boxes:
        for face in ("top", "right", "front"):
            u, v, w, h = getattr(box, face)
            patch = tex.crop((u * scale, v * scale,
                              (u + w) * scale, (v + h) * scale))
            coeffs = _affine_coeffs(*face_quad(box, face),
                                    patch.width, patch.height)
            drawn = patch.transform(CANVAS, Image.AFFINE, coeffs, Image.NEAREST)
            canvas.alpha_composite(drawn)
    return canvas


def render_armor(texture: Image.Image) -> Image.Image:
    """One armor UV sheet, drawn on the humanoid model."""
    return render_boxes(texture, HUMANOID)
