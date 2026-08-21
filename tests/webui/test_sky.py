from PIL import Image

from mc_pack_converter.webui.sky import faces, render_sky

RED, GREEN, BLUE, GREY = (200, 40, 40), (40, 200, 40), (40, 40, 200), (128, 128, 128)


def _skybox(cell: int = 64) -> Image.Image:
    """A 3x2 skybox: ring faces red, zenith blue, nadir green.

    Laid out the way OptiFine packs are, derived by edge-matching a real
    6144x4096 sky: (0,0) is the nadir, (0,1) the zenith, and (0,2) (1,0)
    (1,1) (1,2) are the horizon ring in that cyclic order.
    """
    im = Image.new("RGB", (cell * 3, cell * 2), GREY)
    for (r, c), colour in {(0, 0): GREEN, (0, 1): BLUE, (0, 2): RED,
                           (1, 0): RED, (1, 1): RED, (1, 2): RED}.items():
        im.paste(Image.new("RGB", (cell, cell), colour), (c * cell, r * cell))
    return im


def test_the_texture_splits_into_six_square_faces():
    got = faces(_skybox())

    assert set(got) == {"up", "down", "ring"}
    assert len(got["ring"]) == 4
    assert got["up"].size == got["down"].size == (64, 64)
    assert got["up"].getpixel((32, 32)) == BLUE
    assert got["down"].getpixel((32, 32)) == GREEN
    for face in got["ring"]:
        assert face.getpixel((32, 32)) == RED


def test_the_view_puts_the_sky_overhead_and_the_ring_at_eye_level():
    """The whole point of the preview: the sky where the sky is.

    A view that samples the wrong face reads as a plausible image, so the
    check has to be which face lands where, not merely that pixels differ.
    """
    view = render_sky(_skybox(), size=(80, 60))

    w, h = view.size
    overhead = view.getpixel((w // 2, 1))
    eye_level = view.getpixel((w // 2, h // 2))
    assert overhead[2] > overhead[0], "the zenith is not overhead"
    assert eye_level[0] > eye_level[2], "the horizon ring is not at eye level"


def test_turning_changes_the_view():
    box = _skybox()
    # One ring face marked, so a turn has something to reveal.
    box.paste(Image.new("RGB", (64, 64), (255, 255, 0)), (0, 64))

    ahead = render_sky(box, yaw=0.0, size=(80, 60))
    behind = render_sky(box, yaw=180.0, size=(80, 60))

    assert list(ahead.getdata()) != list(behind.getdata())
