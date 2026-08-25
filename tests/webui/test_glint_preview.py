from PIL import Image

from mc_pack_converter.webui.glint_preview import glint_frames


def _item() -> Image.Image:
    """A 16x16 sprite whose left half is opaque grey and right half is empty."""
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y in range(16):
        for x in range(8):
            im.putpixel((x, y), (80, 80, 80, 255))
    return im


def _glint(size: int = 64) -> Image.Image:
    """A glint bright enough that compositing it is unmistakable."""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    for y in range(size):
        for x in range(size):
            if (x + y) % 8 < 4:
                im.putpixel((x, y), (255, 255, 255, 255))
    return im


def test_the_glint_lands_only_on_the_item():
    """Minecraft masks the glint to the sprite. Off the sprite it must not draw.

    Without the mask the preview shows a square of shimmer with an item
    somewhere inside it, which is not what the game does and would read as a
    conversion fault that isn't there.
    """
    frames = glint_frames(_item(), _glint())

    for frame in frames:
        for y in range(16):
            for x in range(8, 16):
                assert frame.getpixel((x, y))[3] == 0, \
                    "the glint drew outside the sprite"


def test_the_glint_brightens_the_item():
    frames = glint_frames(_item(), _glint())
    plain = _item()

    lit = max(sum(f.getpixel((x, y))[:3])
              for f in frames for y in range(16) for x in range(8))
    assert lit > sum(plain.getpixel((0, 0))[:3]), \
        "the glint is not visible on the item at all"


def test_the_glint_scrolls():
    """A still glint is the one thing the preview cannot show, since the whole
    point is judging a moving shimmer."""
    frames = glint_frames(_item(), _glint())

    assert len(frames) > 1
    first = list(frames[0].getdata())
    assert any(list(f.getdata()) != first for f in frames[1:]), \
        "every frame is identical: the glint does not move"
