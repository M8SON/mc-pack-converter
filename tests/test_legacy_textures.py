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
    assert not (it / "compass.png").exists()              # strip removed
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
