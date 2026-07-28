from PIL import Image
from mc_pack_converter.pipeline import ConversionContext
from mc_pack_converter.stages.atlas_remap import atlas_remap
from mc_pack_converter.imaging import png_size
import mc_pack_converter.stages.atlas_remap as mod


def test_atlas_remap_applies_table(mini_pack, monkeypatch):
    root = mini_pack({"assets/minecraft/textures/entity/chest/normal.png": b""})
    Image.new("RGBA", (64, 64), (0, 255, 0, 255)).save(
        root / "assets/minecraft/textures/entity/chest/normal.png"
    )
    fake = {
        "textures/entity/chest/normal.png": {
            "out_size": [64, 64],
            "regions": [{"src": [0, 0, 32, 32], "dst": [0, 0, 32, 32]}],
        }
    }
    monkeypatch.setattr(mod, "load_table", lambda name: fake)
    ctx = ConversionContext(root=root)
    atlas_remap(ctx)
    assert png_size(root / "assets/minecraft/textures/entity/chest/normal.png") == (64, 64)
