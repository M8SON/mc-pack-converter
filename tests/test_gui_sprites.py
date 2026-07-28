from PIL import Image
from mc_pack_converter.pipeline import ConversionContext
from mc_pack_converter.stages.gui_sprites import gui_sprites

def test_widgets_sliced_to_sprites(mini_pack):
    root = mini_pack()
    sheet = root/"assets/minecraft/textures/gui/widgets.png"
    sheet.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA",(256,256),(0,0,255,255)).save(sheet)
    ctx = ConversionContext(root=root)
    gui_sprites(ctx)
    out = root/"assets/minecraft/textures/gui/sprites/hud/hotbar.png"
    assert out.exists()
