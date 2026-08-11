"""Minecraft rejects resource paths containing uppercase letters.

A ResourceLocation must match [a-z0-9_.-/]. Any file whose path has a capital
is refused by the loader, so the art silently never appears. 130 of 170 corpus
packs ship at least one; one pack ships 172, including 49 block textures.
"""
import os

import pytest

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


@pytest.mark.skipif(
    os.name == "nt",
    reason="fixture needs tripwire.png and tripWire.png to coexist; on NTFS they "
           "are the same file, so the second write overwrites the first",
)
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


def test_optifine_keeps_its_case_but_loses_invalid_characters(mini_pack):
    """OptiFine loads these itself and its .properties reference tiles by name,
    so case is preserved. Spaces are NOT preserved: the game log shows OptiFine
    rejecting 'optifine/ctm/glass gray/glass.properties' by path, so a space is
    fatal there too.
    """
    root = mini_pack()
    _put(root, "optifine/ctm/Glass/Grey Glass/0.png", b"ctm")
    _put(root, "mcpatcher/ctm/Glass/1.png", b"ctm")
    lowercase_paths(ConversionContext(root=root))
    mc = root / "assets/minecraft"
    assert (mc / "optifine/ctm/Glass/Grey_Glass/0.png").exists()
    assert (mc / "mcpatcher/ctm/Glass/1.png").exists()


def test_already_lowercase_pack_is_untouched(mini_pack):
    root = mini_pack()
    _put(root, "textures/blocks/stone.png", b"art")
    ctx = ConversionContext(root=root)
    lowercase_paths(ctx)
    assert (root / "assets/minecraft/textures/blocks/stone.png").read_bytes() == b"art"
    assert any("0 paths" in f.message for f in ctx.findings)


def test_spaces_in_a_texture_name_are_replaced(mini_pack):
    """Minecraft's log: "Invalid path in datapack: .../iron ore.png, ignoring".

    Spaces are as invalid as capitals — the file is refused and the art never
    appears.
    """
    root = mini_pack()
    _put(root, "textures/blocks/iron ore.png", b"art")
    lowercase_paths(ConversionContext(root=root))
    assert (root / "assets/minecraft/textures/blocks/iron_ore.png").read_bytes() == b"art"


def test_space_variant_dropped_when_the_valid_name_exists(mini_pack):
    root = mini_pack()
    _put(root, "textures/blocks/iron_ore.png", b"LOADED")
    _put(root, "textures/blocks/iron ore.png", b"never-loadable")
    lowercase_paths(ConversionContext(root=root))
    mc = root / "assets/minecraft"
    assert (mc / "textures/blocks/iron_ore.png").read_bytes() == b"LOADED"
    assert not (mc / "textures/blocks/iron ore.png").exists()


def test_optifine_folder_spaces_are_fixed_but_case_is_kept(mini_pack):
    """OptiFine rejects 'optifine/ctm/glass gray/glass.properties' by path.

    Renaming to glass_gray makes it loadable, and the CTM table normalises
    underscores to spaces so the mapping still resolves. Case is preserved
    there because .properties reference tiles by name.
    """
    root = mini_pack()
    _put(root, "optifine/ctm/glass gray/glass.properties", b"method=ctm")
    _put(root, "optifine/ctm/Glass/1.png", b"tile")
    lowercase_paths(ConversionContext(root=root))
    mc = root / "assets/minecraft"
    assert (mc / "optifine/ctm/glass_gray/glass.properties").exists()
    assert (mc / "optifine/ctm/Glass/1.png").exists(), "case must survive in optifine"


def test_case_only_rename_preserves_content(tmp_path):
    """A case-only rename must go through a temp name.

    On a case-insensitive filesystem `src.rename(dst)` where the two differ only
    by case is either a no-op or an error, and the naive `if dst.exists()` guard
    reads it as a collision and deletes the file. Two steps make it work
    identically on both kinds of filesystem.
    """
    from mc_pack_converter.stages.lowercase_paths import _case_only_rename
    src = tmp_path / "tripWire.png"
    src.write_bytes(b"art")
    dst = tmp_path / "tripwire.png"
    _case_only_rename(src, dst)
    assert dst.read_bytes() == b"art"
    assert not any(p.name == "tripWire.png" for p in tmp_path.iterdir())
    assert not any(p.name.endswith(".casetmp") for p in tmp_path.iterdir())
