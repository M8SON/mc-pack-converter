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
    # RGBA now, not RGB: a sky's transparency may live in a palette tRNS
    # chunk, and dropping it turns clear pixels into whatever the palette
    # holds there -- white, for the reference pack's sunflare.
    assert got["up"].getpixel((32, 32)) == BLUE + (255,)
    assert got["down"].getpixel((32, 32)) == GREEN + (255,)
    for face in got["ring"]:
        assert face.getpixel((32, 32)) == RED + (255,)


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


def test_a_transparent_region_of_a_sky_stays_transparent():
    """M8SON's sky_sunflare.png is a palette PNG with tRNS=0 and 83.6% of it
    fully transparent. Converting to RGB turned all of that into the palette's
    white, so an `add` layer painted the whole sky white instead of a flare on
    nothing.
    """
    from PIL import Image
    from mc_pack_converter.webui.sky import render_sky

    src = Image.new("RGBA", (192, 128), (255, 255, 255, 0))
    out = render_sky(src, yaw=0.0, size=(32, 20))
    assert out.mode == "RGBA"
    assert max(out.getchannel("A").getdata()) == 0, \
        "a wholly transparent sky must render wholly transparent"
