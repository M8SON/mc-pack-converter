# tests/conftest.py
from pathlib import Path
import pytest

@pytest.fixture
def mini_pack(tmp_path: Path):
    """Build a minimal 1.8.9-style pack tree; return its root Path."""
    def _build(files: dict[str, bytes] | None = None) -> Path:
        root = tmp_path / "pack"
        (root / "assets/minecraft/textures/blocks").mkdir(parents=True)
        (root / "pack.mcmeta").write_text(
            '{"pack":{"pack_format":1,"description":"test"}}'
        )
        for rel, data in (files or {}).items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        return root
    return _build
