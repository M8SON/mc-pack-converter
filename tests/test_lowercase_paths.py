"""Minecraft rejects resource paths containing uppercase letters.

A ResourceLocation must match [a-z0-9_.-/]. Any file whose path has a capital
is refused by the loader, so the art silently never appears. 130 of 170 corpus
packs ship at least one; one pack ships 172, including 49 block textures.
"""
from mc_pack_converter.pipeline import ConversionContext, Severity
from mc_pack_converter.stages.lowercase_paths import lowercase_paths


def _put(root, rel, data=b"x"):
    p = root / "assets/minecraft" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def test_uppercase_filename_is_lowercased(mini_pack):
    root = mini_pack()
    _put(root, "textures/blocks/tripWire.png", b"art")
    ctx = ConversionContext(root=root)
    lowercase_paths(ctx)
    mc = root / "assets/minecraft"
    assert (mc / "textures/blocks/tripwire.png").read_bytes() == b"art"
    assert not (mc / "textures/blocks/tripWire.png").exists()


def test_uppercase_directory_is_lowercased(mini_pack):
    root = mini_pack()
    _put(root, "textures/Blocks/stone.png", b"art")
    lowercase_paths(ConversionContext(root=root))
    assert (root / "assets/minecraft/textures/blocks/stone.png").read_bytes() == b"art"


def test_font_pages_are_lowercased(mini_pack):
    """1.8.9 shipped unicode_page_0A.png; modern wants lowercase hex."""
    root = mini_pack()
    _put(root, "textures/font/unicode_page_0A.png", b"font")
    lowercase_paths(ConversionContext(root=root))
    assert (root / "assets/minecraft/textures/font/unicode_page_0a.png").exists()


def test_collision_keeps_the_already_lowercase_file(mini_pack):
    """Both spellings shipped: the lowercase one is what Minecraft loads today."""
    root = mini_pack()
    _put(root, "textures/blocks/tripwire.png", b"LOADED")
    _put(root, "textures/blocks/tripWire.png", b"ignored-by-minecraft")
    ctx = ConversionContext(root=root)
    lowercase_paths(ctx)
    mc = root / "assets/minecraft"
    assert (mc / "textures/blocks/tripwire.png").read_bytes() == b"LOADED"
    assert not (mc / "textures/blocks/tripWire.png").exists()
    assert any(f.severity is Severity.WARNING and "already" in f.message
               for f in ctx.findings)


def test_sibling_mcmeta_follows(mini_pack):
    root = mini_pack()
    _put(root, "textures/blocks/Fire.png", b"art")
    _put(root, "textures/blocks/Fire.png.mcmeta", b"{}")
    lowercase_paths(ConversionContext(root=root))
    mc = root / "assets/minecraft"
    assert (mc / "textures/blocks/fire.png").exists()
    assert (mc / "textures/blocks/fire.png.mcmeta").exists()


def test_optifine_tree_is_left_alone(mini_pack):
    """OptiFine loads these itself and its .properties reference them by name."""
    root = mini_pack()
    _put(root, "optifine/ctm/Glass/Grey Glass/0.png", b"ctm")
    _put(root, "mcpatcher/ctm/Glass/1.png", b"ctm")
    lowercase_paths(ConversionContext(root=root))
    mc = root / "assets/minecraft"
    assert (mc / "optifine/ctm/Glass/Grey Glass/0.png").exists()
    assert (mc / "mcpatcher/ctm/Glass/1.png").exists()


def test_already_lowercase_pack_is_untouched(mini_pack):
    root = mini_pack()
    _put(root, "textures/blocks/stone.png", b"art")
    ctx = ConversionContext(root=root)
    lowercase_paths(ctx)
    assert (root / "assets/minecraft/textures/blocks/stone.png").read_bytes() == b"art"
    assert any("0 paths" in f.message for f in ctx.findings)
