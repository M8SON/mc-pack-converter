# mc_pack_converter/pipeline.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

class FatalConversionError(Exception):
    """Hard-fail: invalid pack or unwritable output."""

@dataclass
class Finding:
    stage: str
    severity: Severity
    message: str
    path: str | None = None

@dataclass
class ConversionContext:
    root: Path
    findings: list[Finding] = field(default_factory=list)
    target: str = "26.2"

    def add(self, stage: str, severity: Severity, message: str,
            path: str | None = None) -> None:
        self.findings.append(Finding(stage, severity, message, path))

def run_pipeline(
    ctx: ConversionContext,
    stages: list[tuple[str, Callable[[ConversionContext], None]]],
) -> None:
    for name, fn in stages:
        try:
            fn(ctx)
        except FatalConversionError:
            raise
        except Exception as exc:  # fail-soft
            ctx.add(name, Severity.ERROR, f"stage crashed: {exc!r}")
