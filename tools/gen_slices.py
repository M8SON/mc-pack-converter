#!/usr/bin/env python3
"""Generate mc_pack_converter/data/slices.json from Mojang's vendored slicer
sources (tools/slicer_src/*.java).

Ports the slicer DSL: input(path, SimpleOutputFile(out, Box(...))...),
copy(name), clip(name[,out], box), move(in, out), moveRealmsToMinecraft(name).
Boxes are proportional: Box(x,y,w,h,totalW,totalH).

Output record shape (list): {"input": path, "output": path,
  "box": [x,y,w,h,totalW,totalH], "op": "crop"|"copy"|"clip"|"special"}
'copy' = relocate/keep whole file; 'crop' = proportional sub-rect;
'clip' = full-size canvas keeping only the box region.
Entries whose input is under assets/realms/ are dropped (never in a texture pack).
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

SRC = Path(__file__).parent / "slicer_src"
OUT = Path(__file__).parent.parent / "mc_pack_converter" / "data" / "slices.json"


def name_to_path(ns: str, name: str) -> str:
    return f"assets/{ns}/textures/gui/{name}.png"


def split_top_level(s: str) -> list[str]:
    """Split on commas at paren/brace depth 0, respecting string literals."""
    out, depth, buf, instr = [], 0, [], False
    i = 0
    while i < len(s):
        c = s[i]
        if instr:
            buf.append(c)
            if c == "\\":
                buf.append(s[i + 1]); i += 2; continue
            if c == '"':
                instr = False
        else:
            if c == '"':
                instr = True; buf.append(c)
            elif c in "([{":
                depth += 1; buf.append(c)
            elif c in ")]}":
                depth -= 1; buf.append(c)
            elif c == "," and depth == 0:
                out.append("".join(buf).strip()); buf = []
            else:
                buf.append(c)
        i += 1
    if "".join(buf).strip():
        out.append("".join(buf).strip())
    return out


def balanced(s: str, open_idx: int) -> str:
    """Return substring inside the parens starting at open_idx (index of '(')."""
    depth, i, instr = 0, open_idx, False
    while i < len(s):
        c = s[i]
        if instr:
            if c == "\\":
                i += 2; continue
            if c == '"':
                instr = False
        else:
            if c == '"':
                instr = True
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return s[open_idx + 1:i]
        i += 1
    raise ValueError("unbalanced")


STR = re.compile(r'"((?:[^"\\]|\\.)*)"')
BOX = re.compile(r"new\s+Box\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")


def parse_name_to_path(expr: str) -> str | None:
    """Resolve a nameToPath("ns","name") call or a bare string literal to a path."""
    expr = expr.strip()
    m = re.match(r'nameToPath\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)', expr)
    if m:
        return name_to_path(m.group(1), m.group(2))
    m = STR.match(expr)
    if m:
        return m.group(1)
    return None


def parse_output(expr: str, input_path: str) -> dict | None:
    """Parse a SimpleOutputFile(...) expression into a record."""
    if "new SimpleOutputFile" not in expr:
        return None
    strs = STR.findall(expr)
    if not strs:
        return None
    out_path = strs[0]
    special = ".apply(" in expr
    box = BOX.search(expr)
    if box:
        b = [int(g) for g in box.groups()]
        op = "special" if special else "crop"
        return {"input": input_path, "output": out_path, "box": b, "op": op}
    return None


def parse_entry(entry: str) -> list[dict]:
    entry = entry.strip()
    recs: list[dict] = []
    call = re.match(r"(\w+)\s*\(", entry)
    if not call:
        return recs
    fn = call.group(1)
    inner = balanced(entry, entry.index("("))
    args = split_top_level(inner)

    if fn == "input":
        in_path = parse_name_to_path(args[0])
        if not in_path:
            return recs
        for out_expr in args[1:]:
            r = parse_output(out_expr, in_path)
            if r:
                recs.append(r)
    elif fn == "copy":
        p = name_to_path("minecraft", STR.match(args[0]).group(1))
        recs.append({"input": p, "output": p, "box": [0, 0, 1, 1, 1, 1], "op": "copy"})
    elif fn == "move":
        a = parse_name_to_path(args[0]); b = parse_name_to_path(args[1])
        if a and b:
            recs.append({"input": a, "output": b, "box": [0, 0, 1, 1, 1, 1], "op": "copy"})
    elif fn == "moveRealmsToMinecraft":
        name = STR.match(args[0]).group(1)
        recs.append({"input": name_to_path("realms", name),
                     "output": name_to_path("minecraft", name),
                     "box": [0, 0, 1, 1, 1, 1], "op": "copy"})
    elif fn == "clip":
        if len(args) == 2:  # clip(name, box)
            nm = STR.match(args[0]).group(1); in_nm = out_nm = nm; box_expr = args[1]
        else:               # clip(in, out, box)
            in_nm = STR.match(args[0]).group(1); out_nm = STR.match(args[1]).group(1); box_expr = args[2]
        box = BOX.search(box_expr)
        if box:
            recs.append({"input": name_to_path("minecraft", in_nm),
                         "output": name_to_path("minecraft", out_nm),
                         "box": [int(g) for g in box.groups()], "op": "clip"})
    return recs


def parse_file(path: Path) -> list[dict]:
    txt = path.read_text()
    m = re.search(r"INPUTS\s*=\s*List\.of\(", txt)
    if not m:
        return []
    inner = balanced(txt, m.end() - 1)
    recs: list[dict] = []
    for entry in split_top_level(inner):
        recs.extend(parse_entry(entry))
    return recs


def main() -> int:
    all_recs: list[dict] = []
    for src in ["slicer_1.14.java", "slicer_1.20.2.java", "slicer262.java"]:
        p = SRC / src
        if not p.exists():
            continue
        recs = parse_file(p)
        all_recs.extend(recs)
        print(f"{src}: {len(recs)} slice records")
    # drop realms inputs (never in a resource pack); dedupe by (input,output)
    seen, cleaned = set(), []
    for r in all_recs:
        if r["input"].startswith("assets/realms/"):
            continue
        key = (r["input"], r["output"])
        if key in seen:
            continue
        seen.add(key); cleaned.append(r)
    OUT.write_text(json.dumps(cleaned, indent=0))
    ops = {}
    for r in cleaned:
        ops[r["op"]] = ops.get(r["op"], 0) + 1
    print(f"\nTOTAL: {len(cleaned)} records -> {OUT}")
    print("by op:", ops)
    print("distinct input atlases:", len({r['input'] for r in cleaned}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
