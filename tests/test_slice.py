from PIL import Image
from mc_pack_converter.pipeline import ConversionContext, Severity
from mc_pack_converter.stages import slice as slice_mod
from mc_pack_converter.stages.slice import slice_atlases


def _put(root, rel, size, color=(10, 20, 30, 255)):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, color).save(p)
    return p


def test_crop_proportional_standard_res(mini_pack, monkeypatch):
    root = mini_pack()
    _put(root, "assets/minecraft/textures/gui/widgets.png", (256, 256))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [
        {"input": "assets/minecraft/textures/gui/widgets.png",
         "output": "assets/minecraft/textures/gui/sprites/hud/hotbar.png",
         "box": [0, 0, 182, 22, 256, 256], "op": "crop"}])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    out = root / "assets/minecraft/textures/gui/sprites/hud/hotbar.png"
    assert out.exists()
    assert Image.open(out).size == (182, 22)


def test_crop_scales_with_resolution(mini_pack, monkeypatch):
    # A 2x-resolution atlas: a 256-ref box must scale up proportionally.
    root = mini_pack()
    _put(root, "assets/minecraft/textures/gui/widgets.png", (512, 512))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [
        {"input": "assets/minecraft/textures/gui/widgets.png",
         "output": "assets/minecraft/textures/gui/sprites/hud/hotbar.png",
         "box": [0, 0, 182, 22, 256, 256], "op": "crop"}])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    assert Image.open(root / "assets/minecraft/textures/gui/sprites/hud/hotbar.png").size == (364, 44)


def test_copy_op_relocates_whole_file(mini_pack, monkeypatch):
    root = mini_pack()
    _put(root, "assets/minecraft/textures/gui/title/mojangstudios.png", (128, 128))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [
        {"input": "assets/minecraft/textures/gui/title/mojangstudios.png",
         "output": "assets/minecraft/textures/gui/sprites/title/mojangstudios.png",
         "box": [0, 0, 1, 1, 1, 1], "op": "copy"}])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    assert (root / "assets/minecraft/textures/gui/sprites/title/mojangstudios.png").exists()


def test_missing_atlas_is_skipped(mini_pack, monkeypatch):
    root = mini_pack()
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [
        {"input": "assets/minecraft/textures/gui/nonexistent.png",
         "output": "assets/minecraft/textures/gui/sprites/x.png",
         "box": [0, 0, 8, 8, 16, 16], "op": "crop"}])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)  # must not raise
    assert any(f.stage == "slice" and f.severity is Severity.INFO for f in ctx.findings)


def test_transparent_region_is_left_to_vanilla(mini_pack, monkeypatch):
    # A 1.8.9 atlas has no pixels where a modern sprite lives. Writing a
    # transparent PNG would OVERRIDE vanilla and render it invisible in-game,
    # so no file may be written at all.
    root = mini_pack()
    _put(root, "assets/minecraft/textures/gui/widgets.png", (256, 256), (0, 0, 0, 0))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [
        {"input": "assets/minecraft/textures/gui/widgets.png",
         "output": "assets/minecraft/textures/gui/sprites/hud/hotbar.png",
         "box": [0, 0, 182, 22, 256, 256], "op": "crop"}])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    assert not (root / "assets/minecraft/textures/gui/sprites/hud/hotbar.png").exists()
    assert any("left to vanilla" in f.message for f in ctx.findings)


def test_zero_size_crop_is_left_to_vanilla(mini_pack, monkeypatch):
    # A box that scales down to zero pixels must not produce a file.
    root = mini_pack()
    _put(root, "assets/minecraft/textures/gui/widgets.png", (16, 16))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [
        {"input": "assets/minecraft/textures/gui/widgets.png",
         "output": "assets/minecraft/textures/gui/sprites/hud/tiny.png",
         "box": [0, 0, 1, 1, 512, 512], "op": "crop"}])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    assert not (root / "assets/minecraft/textures/gui/sprites/hud/tiny.png").exists()
    # Must be the deliberate skip, not the fail-soft handler swallowing
    # PIL's "cannot write empty image" on a 0x0 crop.
    assert any("left to vanilla" in f.message for f in ctx.findings)


def test_clip_with_empty_region_is_left_to_vanilla(mini_pack, monkeypatch):
    root = mini_pack()
    _put(root, "assets/minecraft/textures/gui/widgets.png", (256, 256), (0, 0, 0, 0))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [
        {"input": "assets/minecraft/textures/gui/widgets.png",
         "output": "assets/minecraft/textures/gui/sprites/hud/clipped.png",
         "box": [0, 0, 32, 32, 256, 256], "op": "clip"}])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    assert not (root / "assets/minecraft/textures/gui/sprites/hud/clipped.png").exists()


def test_opaque_region_still_written(mini_pack, monkeypatch):
    # Guard: the skip rule must not suppress real art.
    root = mini_pack()
    _put(root, "assets/minecraft/textures/gui/widgets.png", (256, 256), (10, 20, 30, 255))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [
        {"input": "assets/minecraft/textures/gui/widgets.png",
         "output": "assets/minecraft/textures/gui/sprites/hud/hotbar.png",
         "box": [0, 0, 182, 22, 256, 256], "op": "crop"}])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    assert (root / "assets/minecraft/textures/gui/sprites/hud/hotbar.png").exists()


def test_written_sprites_are_recorded_on_the_context(mini_pack, monkeypatch):
    root = mini_pack()
    _put(root, "assets/minecraft/textures/particle/particles.png", (128, 128))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [
        {"input": "assets/minecraft/textures/particle/particles.png",
         "output": "assets/minecraft/textures/particle/flame.png",
         "box": [0, 24, 8, 8, 128, 128], "op": "crop"}])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    assert ctx.sliced == [("assets/minecraft/textures/particle/particles.png",
                           "assets/minecraft/textures/particle/flame.png")]


def test_skipped_sprites_are_not_recorded(mini_pack, monkeypatch):
    root = mini_pack()
    _put(root, "assets/minecraft/textures/particle/particles.png", (128, 128),
         (0, 0, 0, 0))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [
        {"input": "assets/minecraft/textures/particle/particles.png",
         "output": "assets/minecraft/textures/particle/flame.png",
         "box": [0, 24, 8, 8, 128, 128], "op": "crop"}])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    assert ctx.sliced == []
