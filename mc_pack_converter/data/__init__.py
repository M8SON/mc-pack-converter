from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path

@lru_cache
def load_table(name: str) -> dict:
    p = Path(__file__).parent / f"{name}.json"
    return json.loads(p.read_text())
