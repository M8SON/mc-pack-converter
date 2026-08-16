import io, zipfile
import pytest
from PIL import Image
from mc_pack_converter.webui.armor import (
    CANVAS, HUMANOID, Box, face_quad, render_armor)


def _area(q):
    (x0, y0), (x1, y1), (x2, y2) = q
    return abs((x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0))


def test_the_model_has_six_boxes_in_painter_order():
    """Nearer the camera paints last. For a fixed camera and a fixed skeleton
    the order is constant, so there is no depth sort to get wrong."""
    assert [b.name for b in HUMANOID] == [
        "left_leg", "right_leg", "body", "left_arm", "right_arm", "head"]


@pytest.mark.parametrize("box", HUMANOID, ids=lambda b: b.name)
@pytest.mark.parametrize("face", ["front", "top", "right"])
def test_no_face_collapses_to_zero_area(box, face):
    """A transform that flattens a parallelogram would be encoded as
    'expected' by a golden image generated from already-broken output."""
    assert _area(face_quad(box, face)) > 1.0


@pytest.mark.parametrize("box", HUMANOID, ids=lambda b: b.name)
def test_every_face_uv_lies_inside_the_64x32_base(box):
    for face in ("front", "top", "right"):
        u, v, w, h = getattr(box, face)
        assert 0 <= u and 0 <= v and u + w <= 64 and v + h <= 32


def test_the_head_sits_above_the_body_and_the_legs_below():
    """Ordinal geometry a transposed or mirrored transform would violate,
    independent of any golden image."""
    top = lambda n: min(p[1] for p in face_quad(
        next(b for b in HUMANOID if b.name == n), "front"))
    bottom = lambda n: max(p[1] for p in face_quad(
        next(b for b in HUMANOID if b.name == n), "front"))
    assert top("head") < top("body")
    assert bottom("left_leg") > bottom("body")


def test_the_right_arm_is_left_of_the_body_on_screen():
    """The model's right arm faces the viewer's left. Getting this backwards
    mirrors the whole figure."""
    left = lambda n: min(p[0] for p in face_quad(
        next(b for b in HUMANOID if b.name == n), "front"))
    assert left("right_arm") < left("body") < left("left_arm")


def _armor(size=(64, 32), colour=(200, 30, 30, 255)):
    return Image.new("RGBA", size, colour)


def test_render_produces_a_canvas_with_visible_pixels():
    out = render_armor(_armor())
    assert out.size == CANVAS
    assert out.mode == "RGBA"
    assert out.getbbox() is not None


def test_every_box_contributes_visible_pixels():
    """Renders each box alone. A box silently skipped -- a typo'd name, a UV
    rect that lands on empty texture -- would otherwise be invisible."""
    from mc_pack_converter.webui.armor import render_boxes
    for box in HUMANOID:
        out = render_boxes(_armor(), [box])
        assert out.getbbox() is not None, f"{box.name} rendered nothing"


def test_a_128x64_texture_renders_the_same_shape_as_a_64x32_one():
    """chainmail.png is 128x64 while the other ten armor textures are 64x32.
    UVs are defined against the 64x32 base and scaled."""
    small = render_armor(_armor((64, 32)))
    large = render_armor(_armor((128, 64)))
    assert small.getbbox() == large.getbbox()


def test_a_fully_transparent_texture_renders_nothing():
    assert render_armor(_armor(colour=(0, 0, 0, 0))).getbbox() is None


def test_golden_diamond_chestplate():
    """A renderer that pastes the wrong UV rect, or transposes two faces,
    passes every weaker assertion. This is the one that catches it."""
    from pathlib import Path
    golden = Path(__file__).parent / "golden-diamond-chestplate.png"
    src = Path(__file__).parent / "diamond.png"
    out = render_armor(Image.open(src))
    assert list(out.getdata()) == list(Image.open(golden).convert("RGBA").getdata())


def test_turning_the_model_actually_changes_it():
    """A yaw that quietly did nothing would still pass every other test here."""
    import math
    front = render_armor(_armor(), 0.0)
    side = render_armor(_armor(), math.pi / 2)
    assert list(front.getdata()) != list(side.getdata())


def test_a_full_turn_returns_to_the_start():
    import math
    assert list(render_armor(_armor(), 0.0).getdata()) == \
           list(render_armor(_armor(), 2 * math.pi).getdata())


def test_every_spin_frame_is_distinct_and_non_empty():
    """Catches a spin that renders the same angle N times, and one that turns
    the model out of frame.

    Uses the real armor texture, not a flat colour: the humanoid skeleton is
    geometrically symmetric front-to-back, so with a uniform texture 0 and 180
    degrees are genuinely identical images and only the ART tells them apart.
    """
    from pathlib import Path
    from mc_pack_converter.webui.armor import spin_frames
    tex = Image.open(Path(__file__).parent / "diamond.png")
    frames = spin_frames(tex, 12)
    assert len(frames) == 12
    seen = set()
    for i, f in enumerate(frames):
        assert f.size == CANVAS
        assert f.getbbox() is not None, f"frame {i} is empty"
        seen.add(f.tobytes())
    assert len(seen) == 12, "some spin frames are identical"


@pytest.mark.parametrize("box", HUMANOID, ids=lambda b: b.name)
def test_every_box_defines_all_six_faces(box):
    """A missing face leaves the model hollow as it comes about."""
    for face in ("front", "back", "right", "left", "top", "bottom"):
        uv = getattr(box, face)
        assert uv is not None, f"{box.name} has no {face}"
        u, v, w, h = uv
        assert 0 <= u and 0 <= v and u + w <= 64 and v + h <= 32


def test_a_block_texture_renders_on_a_cube_within_its_canvas():
    from mc_pack_converter.webui.armor import CUBE_CANVAS, render_cube
    for res in (16, 32, 64):     # 1x, 2x and 4x packs
        out = render_cube(Image.new("RGBA", (res, res), (10, 200, 90, 255)))
        assert out.size == CUBE_CANVAS, f"{res}px texture escaped the canvas"
        assert out.getbbox() is not None


def test_the_cube_is_the_same_size_whatever_the_texture_resolution():
    """A 32x pack gets the same cube at more detail, not a bigger cube."""
    from mc_pack_converter.webui.armor import render_cube
    a = render_cube(Image.new("RGBA", (16, 16), (255, 0, 0, 255)))
    b = render_cube(Image.new("RGBA", (64, 64), (255, 0, 0, 255)))
    assert a.getbbox() == b.getbbox()
