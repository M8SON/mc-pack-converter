from PIL import Image
from mc_pack_converter.pipeline import ConversionContext
from mc_pack_converter.stages.chest import chest_remap, _apply
from mc_pack_converter.data import load_table


def test_single_chest_remapped_in_place(mini_pack):
    root = mini_pack()
    p = root / "assets/minecraft/textures/entity/chest/normal.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (64, 64), (200, 100, 50, 255)).save(p)
    ctx = ConversionContext(root=root)
    chest_remap(ctx)
    assert p.exists() and Image.open(p).size == (64, 64)


def test_double_chest_split_into_left_right(mini_pack):
    root = mini_pack()
    base = root / "assets/minecraft/textures/entity/chest"
    base.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (128, 64), (200, 100, 50, 255)).save(base / "normal_double.png")
    ctx = ConversionContext(root=root)
    chest_remap(ctx)
    assert (base / "normal_left.png").exists()
    assert (base / "normal_right.png").exists()
    assert not (base / "normal_double.png").exists()  # old double removed
    assert Image.open(base / "normal_left.png").size == (64, 64)


def test_non_power_of_two_skipped(mini_pack):
    root = mini_pack()
    p = root / "assets/minecraft/textures/entity/chest/normal.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (50, 50), (0, 0, 0, 255)).save(p)  # 50 is not a power of two
    before = p.read_bytes()
    ctx = ConversionContext(root=root)
    chest_remap(ctx)
    assert p.read_bytes() == before  # untouched


def test_remap_ops_are_well_formed():
    cfg = load_table("chest_remap")
    for key, ops in [("single", cfg["single"]["ops"]),
                     ("double.left", cfg["double"]["left"]),
                     ("double.right", cfg["double"]["right"])]:
        for op in ops:
            assert len(op) == 7, f"{key} op wrong arity: {op}"
            assert op[6] in ("", "v", "180"), f"{key} bad flip: {op}"
