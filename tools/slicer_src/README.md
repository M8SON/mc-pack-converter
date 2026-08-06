# Vendored Mojang slicer sources

`slicer_1.14.java`, `slicer_1.20.2.java` and `slicer262.java` are Mojang's,
from [github.com/Mojang/slicer](https://github.com/Mojang/slicer). They are
kept here because `tools/gen_slices.py` parses them to regenerate
`mc_pack_converter/data/slices.json` — the table of every GUI sprite crop the
1.20.2 atlas migration performs.

They are build-time inputs only. No Mojang code is imported, executed, or
shipped in the converter or in any pack it produces.

**Licensing.** The three `.java` files are **not** covered by this repository's
`LICENSE`. They are Microsoft/Mojang's, redistributed under the MIT license
they carry — each keeps its original header intact
(`Copyright (c) Microsoft Corporation. All rights reserved. Licensed under the
MIT license.`), and those headers are the authoritative statement of their
terms. The root `LICENSE`'s "Copyright (c) 2026 Mason Misch" covers the rest of
the tree and does not extend to this directory. Do not edit or strip those
headers.
