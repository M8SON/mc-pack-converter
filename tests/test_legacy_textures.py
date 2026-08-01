from PIL import Image
from mc_pack_converter.pipeline import ConversionContext
from mc_pack_converter.stages.legacy_textures import legacy_textures


def test_water_is_grayscaled(mini_pack):
    root = mini_pack()
    p = root / "assets/minecraft/textures/block/water_still.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (16, 512), (30, 90, 220, 255)).save(p)  # blue
    legacy_textures(ConversionContext(root=root))
    px = Image.open(p).convert("RGBA").getpixel((8, 8))
    assert px[0] == px[1] == px[2]      # now gray (R==G==B)
    assert px[3] == 255                  # alpha preserved


def test_compass_strip_split_into_frames(mini_pack):
    root = mini_pack()
    it = root / "assets/minecraft/textures/item"
    it.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (16, 512), (200, 0, 0, 255)).save(it / "compass.png")  # 32 frames
    (it / "compass.png.mcmeta").write_text("{}")
    legacy_textures(ConversionContext(root=root))
    assert (it / "compass_00.png").exists()
    assert (it / "compass_31.png").exists()
    assert Image.open(it / "compass_00.png").size == (16, 16)
    # The strip is KEPT as of 2026-08-01: modern vanilla ships no
    # item/compass.png, but a pack with its own compass model references
    # 'items/compass', and removing it left that dangling as a missing texture.
    assert (it / "compass.png").exists()
    assert not (it / "compass.png.mcmeta").exists()       # mcmeta removed


def test_clock_64_frames(mini_pack):
    root = mini_pack()
    it = root / "assets/minecraft/textures/item"
    it.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (16, 1024), (0, 0, 0, 255)).save(it / "clock.png")  # 64 frames
    legacy_textures(ConversionContext(root=root))
    assert (it / "clock_63.png").exists()
    assert not (it / "clock_64.png").exists()


def test_non_strip_item_untouched(mini_pack):
    root = mini_pack()
    it = root / "assets/minecraft/textures/item"
    it.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (16, 16), (1, 2, 3, 255)).save(it / "compass.png")  # square, not a strip
    legacy_textures(ConversionContext(root=root))
    assert (it / "compass.png").exists()          # left alone
    assert not (it / "compass_00.png").exists()


def test_compass_strip_is_kept_for_custom_models(mini_pack):
    """A pack shipping its own compass model references 'items/compass'.

    Deleting the strip after splitting left that reference dangling as a
    missing-texture placeholder. Modern vanilla ships no item/compass.png, so
    keeping it costs nothing and cannot shadow anything.
    """
    root = mini_pack()
    p = root / "assets/minecraft/textures/item/compass.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (16, 64), (10, 20, 30, 255)).save(p)
    p.with_name("compass.png.mcmeta").write_text('{"animation":{}}')
    legacy_textures(ConversionContext(root=root))
    assert p.exists(), "the strip must survive for custom models"
    assert (p.parent / "compass_00.png").exists()
    assert (p.parent / "compass_03.png").exists()
    assert not p.with_name("compass.png.mcmeta").exists(), "stale animation meta must go"
