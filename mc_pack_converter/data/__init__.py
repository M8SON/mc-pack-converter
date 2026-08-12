from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path

# pack_format.json's "1.8.9" entry describes the format a pack is READ as, not
# a valid conversion output. Defined here, beside the table, because both the
# CLI (to build its --target choices) and pack_meta (to find the oldest target
# it can claim compatibility with) need to exclude it.
INPUT_FORMAT = "1.8.9"


@lru_cache
def load_table(name: str) -> dict:
    p = Path(__file__).parent / f"{name}.json"
    return json.loads(p.read_text())
