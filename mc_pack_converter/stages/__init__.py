from . import ingest as _ingest
from . import clean as _clean
from . import restructure as _restructure
from . import flatten_rename as _flatten_rename
from . import atlas_remap as _atlas_remap
from . import chest as _chest
from . import drop as _drop
from . import optifine as _optifine
from . import slice as _slice
from . import sounds as _sounds
from . import pack_meta as _pack_meta
from . import validate as _validate

STAGES = [
    ("ingest", _ingest.ingest), ("clean", _clean.clean), ("restructure", _restructure.restructure),
    ("flatten_rename", _flatten_rename.flatten_rename), ("atlas_remap", _atlas_remap.atlas_remap),
    ("chest", _chest.chest_remap), ("drop", _drop.drop_textures),
    ("optifine", _optifine.optifine_translate), ("slice", _slice.slice_atlases),
    ("sounds", _sounds.sounds), ("pack_meta", _pack_meta.pack_meta), ("validate", _validate.validate),
]
