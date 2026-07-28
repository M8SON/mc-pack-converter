from __future__ import annotations
from collections import defaultdict
from .pipeline import Finding, Severity

def render_conversion_report(findings: list[Finding]) -> str:
    by_stage: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_stage[f.stage].append(f)
    lines = ["# Conversion Report", ""]
    for stage, items in by_stage.items():
        lines.append(f"## {stage}")
        for f in items:
            loc = f" (`{f.path}`)" if f.path else ""
            lines.append(f"- **{f.severity.value}**: {f.message}{loc}")
        lines.append("")
    return "\n".join(lines)

def render_null_texture_report(findings: list[Finding]) -> str:
    risks = [f for f in findings
             if f.stage == "validate" and f.severity in (Severity.WARNING, Severity.ERROR)]
    lines = ["# Null-Texture Safety Report", ""]
    if not risks:
        lines.append("0 null-texture risks")
        return "\n".join(lines)
    for f in risks:
        loc = f" (`{f.path}`)" if f.path else ""
        lines.append(f"- **{f.severity.value}**: {f.message}{loc}")
    return "\n".join(lines)
