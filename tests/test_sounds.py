from mc_pack_converter.pipeline import ConversionContext
from mc_pack_converter.stages.sounds import sounds
import mc_pack_converter.stages.sounds as mod

def test_sound_moved(mini_pack, monkeypatch):
    root = mini_pack({"assets/minecraft/sounds/random/click.ogg": b"OggS"})
    monkeypatch.setattr(mod, "load_table",
                        lambda n: {"random/click.ogg": "ui/button/click.ogg"})
    ctx = ConversionContext(root=root)
    sounds(ctx)
    s = root/"assets/minecraft/sounds"
    assert (s/"ui/button/click.ogg").exists()
    assert not (s/"random/click.ogg").exists()
