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


def test_particle_rebase_512_atlas_cuts_32px_cell(mini_pack, monkeypatch):
    # Resolution independence: a 512x512 atlas is 4x an 1.8.9 128x128 atlas,
    # so a 128-referenced 8x8 particle box must scale up to a 32x32 crop.
    root = mini_pack()
    _put(root, "assets/minecraft/textures/particle/particles.png", (512, 512))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [
        {"input": "assets/minecraft/textures/particle/particles.png",
         "output": "assets/minecraft/textures/particle/critical_hit.png",
         "box": [8, 32, 8, 8, 128, 128], "op": "crop"}])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    out = root / "assets/minecraft/textures/particle/critical_hit.png"
    assert out.exists()
    assert Image.open(out).size == (32, 32)


def test_out_of_bounds_box_writes_no_file(mini_pack, monkeypatch):
    # A box past the atlas edge: PIL pads the crop with transparent pixels
    # rather than raising, so this must fall out through _is_empty exactly
    # like the real bubble_pop_* records do, writing no file.
    root = mini_pack()
    _put(root, "assets/minecraft/textures/particle/particles.png", (128, 128))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [
        {"input": "assets/minecraft/textures/particle/particles.png",
         "output": "assets/minecraft/textures/particle/bubble_pop_0.png",
         "box": [0, 131, 8, 8, 128, 128], "op": "crop"}])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    assert not (root / "assets/minecraft/textures/particle/bubble_pop_0.png").exists()


def test_pack_format_4_gates_particles_png(mini_pack, monkeypatch):
    # A 1.13+ pack's particles.png is 256x256 with 8px cells at the same
    # layout as 1.8.9 (canvas grew, cells did not scale). Reading it against
    # our 128,128-referenced records would cut 16px cells: non-empty, wrong
    # rectangles. Must be skipped instead, with a WARNING naming why.
    root = mini_pack({"pack.mcmeta":
                       b'{"pack":{"pack_format":4,"description":"test"}}'})
    _put(root, "assets/minecraft/textures/particle/particles.png", (256, 256))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [
        {"input": "assets/minecraft/textures/particle/particles.png",
         "output": "assets/minecraft/textures/particle/critical_hit.png",
         "box": [8, 32, 8, 8, 128, 128], "op": "crop"}])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    assert not (root / "assets/minecraft/textures/particle/critical_hit.png").exists()
    assert ctx.sliced == []
    assert any(f.severity is Severity.WARNING and "particles.png" in f.message
               for f in ctx.findings)


def test_pack_format_1_slices_particles_normally(mini_pack, monkeypatch):
    root = mini_pack()  # mini_pack default: pack_format 1
    _put(root, "assets/minecraft/textures/particle/particles.png", (128, 128))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [
        {"input": "assets/minecraft/textures/particle/particles.png",
         "output": "assets/minecraft/textures/particle/critical_hit.png",
         "box": [8, 32, 8, 8, 128, 128], "op": "crop"}])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    assert (root / "assets/minecraft/textures/particle/critical_hit.png").exists()


def _grid_atlas(root, rel, size, marked_cell, color=(200, 30, 40, 255)):
    """A transparent atlas with one 18px-grid cell filled, at origin (0,198).

    cell_px is derived from size, not passed in, so it can't disagree with it.
    """
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    cx, cy = marked_cell
    scale = size[0] // 256
    cell_px = 18 * scale
    x0 = cx * cell_px
    y0 = 198 * scale + cy * cell_px
    im.paste(Image.new("RGBA", (cell_px, cell_px), color), (x0, y0))
    im.save(p)
    return p


JUMP_BOOST_REC = {
    "input": "assets/minecraft/textures/gui/container/inventory.png",
    "output": "assets/minecraft/textures/mob_effect/jump_boost.png",
    "box": [36, 216, 18, 18, 256, 256], "op": "crop"}


def test_effect_cell_is_cut_at_standard_res(mini_pack, monkeypatch):
    root = mini_pack()
    _grid_atlas(root, "assets/minecraft/textures/gui/container/inventory.png",
                (256, 256), (2, 1))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [JUMP_BOOST_REC])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    out = root / "assets/minecraft/textures/mob_effect/jump_boost.png"
    assert out.exists()
    im = Image.open(out).convert("RGBA")
    assert im.size == (18, 18)
    # the whole crop is the marked cell, nothing bled in from a neighbour
    assert im.getchannel("A").getbbox() == (0, 0, 18, 18)
    assert im.getpixel((0, 0)) == (200, 30, 40, 255)


def test_effect_cell_is_cut_at_2x_res(mini_pack, monkeypatch):
    # M8SON ships a 512x512 inventory.png; the 256-referenced box must scale.
    root = mini_pack()
    _grid_atlas(root, "assets/minecraft/textures/gui/container/inventory.png",
                (512, 512), (2, 1))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [JUMP_BOOST_REC])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    im = Image.open(
        root / "assets/minecraft/textures/mob_effect/jump_boost.png"
    ).convert("RGBA")
    assert im.size == (36, 36)
    assert im.getchannel("A").getbbox() == (0, 0, 36, 36)
    assert im.getpixel((0, 0)) == (200, 30, 40, 255)
