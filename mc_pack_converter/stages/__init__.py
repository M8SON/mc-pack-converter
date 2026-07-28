from . import ingest as _ingest
from . import clean as _clean
from . import restructure as _restructure
from . import flatten_rename as _flatten_rename
from . import atlas_remap as _atlas_remap
from . import optifine as _optifine
from . import gui_sprites as _gui_sprites
from . import sounds as _sounds
from . import pack_meta as _pack_meta
from . import validate as _validate

STAGES = [
    ("ingest", _ingest.ingest), ("clean", _clean.clean), ("restructure", _restructure.restructure),
    ("flatten_rename", _flatten_rename.flatten_rename), ("atlas_remap", _atlas_remap.atlas_remap),
    ("optifine", _optifine.optifine_translate), ("gui_sprites", _gui_sprites.gui_sprites),
    ("sounds", _sounds.sounds), ("pack_meta", _pack_meta.pack_meta), ("validate", _validate.validate),
]
