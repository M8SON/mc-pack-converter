import os

import pytest

from mc_pack_converter.pipeline import ConversionContext, Severity
from mc_pack_converter.stages.clean import clean

@pytest.mark.skipif(
    os.name == "nt",
    reason="fixture needs a file named 'stone.png:Zone.Identifier'; on NTFS ':' "
           "opens an alternate data stream, so the file cannot be created",
)
def test_clean_removes_junk(mini_pack):
    root = mini_pack({
        "assets/minecraft/textures/blocks/stone.png:Zone.Identifier": b"x",
        "assets/minecraft/textures/blocks/Thumbs.db": b"x",
        "assets/minecraft/textures/gui/widgets.png~": b"x",
        "assets/minecraft/textures/blocks/stone.png": b"realpng",
    })
    ctx = ConversionContext(root=root)
    clean(ctx)
    tex = root/"assets/minecraft/textures"
    assert not (tex/"blocks/stone.png:Zone.Identifier").exists()
    assert not (tex/"blocks/Thumbs.db").exists()
    assert not (tex/"gui/widgets.png~").exists()
    assert (tex/"blocks/stone.png").exists()
    assert any("3" in f.message for f in ctx.findings if f.severity is Severity.INFO)


def test_appledouble_resource_forks_are_removed(mini_pack):
    """`._foo.png` is a macOS metadata blob, not a PNG the game can decode.

    63 of the 64 'corrupt or empty png' errors across the 173-pack corpus were
    these, shipped under the name of a real texture.
    """
    root = mini_pack()
    d = root / "assets/minecraft/textures/block"
    d.mkdir(parents=True, exist_ok=True)
    (d / "._anvil.png").write_bytes(b"\x00\x05\x16\x07not a png")
    (d / "anvil.png").write_bytes(b"real")
    clean(ConversionContext(root=root))
    assert not (d / "._anvil.png").exists()
    assert (d / "anvil.png").exists()
