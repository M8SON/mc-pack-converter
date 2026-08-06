# Vendored Mojang slicer sources

`slicer_1.14.java`, `slicer_1.20.2.java` and `slicer262.java` are Mojang's,
from [github.com/Mojang/slicer](https://github.com/Mojang/slicer). They are
kept here because `tools/gen_slices.py` parses them to regenerate
`mc_pack_converter/data/slices.json` — the table of every GUI sprite crop the
1.20.2 atlas migration performs.

They are build-time inputs only. No Mojang code is imported, executed, or
shipped in the converter or in any pack it produces.
