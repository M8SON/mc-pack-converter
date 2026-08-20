"""The report: one self-contained HTML file, opened in whatever browser the
user already has.

This replaces the pywebview window. The window needed a system WebKit that pip
cannot install, which made the program Windows-only in practice; the page it
displayed was already self-contained, so writing it to a file costs nothing and
works everywhere.
"""
from __future__ import annotations
import json
from pathlib import Path

from ..pipeline import Severity

_SEVERITY_RANK = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}


def build_model(result, sheet: dict, update: str | None = None) -> dict:
    """Everything the page renders, as plain JSON-serialisable data.

    Sorted by severity because 408 of the reference pack's 413 findings are
    INFO: unsorted, the five that matter are five lines lost in four hundred.
    """
    counts = result.counts
    return {
        "headline": result.out_path.name,
        "findings": [
            {"severity": f.severity.value, "stage": f.stage,
             "message": f.message, "path": f.path}
            for f in sorted(result.ctx.findings,
                            key=lambda f: _SEVERITY_RANK[f.severity])
        ],
        "counts": {s.value: counts[s] for s in Severity},
        "out_path": str(result.out_path),
        "out_name": result.out_path.name,
        "update": update,
        "sheet": sheet,
    }
