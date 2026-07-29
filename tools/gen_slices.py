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
import ast, json, re, sys
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

# --- 1.14 slicer helpers ---------------------------------------------------
# tools/slicer_src/slicer_1.14.java wraps every output in one of five private
# helpers, all reducing to a single primitive:
#   gridSprite(x,y,w,h,xOff,yOff,xScale,yScale)
#     -> Box(xScale*x + xOff, yScale*y + yOff, w*xScale, h*yScale, 256, 256)
# The helper arguments are literal integer arithmetic ("1 * 2"), so the
# generator evaluates them directly.
BFN = re.compile(r"\bb(256|128)\(([^()]*)\)")
PARTICLE_REF = 128
SKIPPED_HELPERS = {"effect": 0, "sweep": 0}


def as_int(expr: str) -> int:
    """Evaluate a literal integer arithmetic expression from the Java source."""
    def ev(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, int):
            return n.value
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            return -ev(n.operand)
        if isinstance(n, ast.BinOp) and isinstance(
                n.op, (ast.Add, ast.Sub, ast.Mult)):
            l, r = ev(n.left), ev(n.right)
            return (l + r if isinstance(n.op, ast.Add)
                    else l - r if isinstance(n.op, ast.Sub) else l * r)
        raise ValueError(f"not an integer expression: {expr!r}")
    return ev(ast.parse(expr.strip(), mode="eval").body)


def parse_box(expr: str) -> list[int] | None:
    """Resolve `new Box(...)`, `b256(...)` or `b128(...)` to [x,y,w,h,tw,th]."""
    m = BOX.search(expr)
    if m:
        return [int(g) for g in m.groups()]
    m = BFN.search(expr)
    if m:
        ref = int(m.group(1))
        x, y, w, h = (as_int(a) for a in split_top_level(m.group(2)))
        return [x, y, w, h, ref, ref]
    return None


HELPER = re.compile(r"(painting|particle|explosion|effect|sweep)\s*\(")


def parse_helper_output(expr: str, input_path: str) -> dict | None:
    """Resolve a 1.14 helper call to a record, or None if not one / not ported.

    Not ported, deliberately:
      effect() - the 18px effect grid inside inventory.png was rearranged in
                 1.9, so these coordinates would mis-map a 1.8.9 pack.
      sweep()  - needs the slicer's SQUARE post-op; the texture is 1.9+.
    """
    expr = expr.strip()
    m = HELPER.match(expr)
    if not m:
        return None
    fn = m.group(1)
    if fn in SKIPPED_HELPERS:
        SKIPPED_HELPERS[fn] += 1
        return None
    args = split_top_level(balanced(expr, expr.index("(")))
    name = STR.match(args[0]).group(1)
    nums = [as_int(a) for a in args[1:]]
    if fn == "painting":
        x, y, w, h = nums
        return {"input": input_path,
                "output": f"assets/minecraft/textures/painting/{name}.png",
                "box": [16 * x, 16 * y, 16 * w, 16 * h, 256, 256], "op": "crop"}
    if fn == "explosion":
        x, y = nums
        return {"input": input_path,
                "output": f"assets/minecraft/textures/particle/{name}.png",
                "box": [32 * x, 32 * y, 32, 32, 128, 128], "op": "crop"}
    # particle(n,x,y) | particle(n,x,y,w,h) | particle(n,x,y,xOff,yOff,w,h)
    if len(nums) == 2:
        x, y = nums
        w = h = 1
        xoff = yoff = 0
    elif len(nums) == 4:
        x, y, w, h = nums
        xoff = yoff = 0
    else:
        x, y, xoff, yoff, w, h = nums
    return {"input": input_path,
            "output": f"assets/minecraft/textures/particle/{name}.png",
            "box": [8 * x + xoff, 8 * y + yoff, 8 * w, 8 * h, 256, 256],
            "op": "crop"}


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
    b = parse_box(expr)
    if b:
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
            r = parse_helper_output(out_expr, in_path) or parse_output(out_expr, in_path)
            if r:
                recs.append(r)
        if in_path.endswith("textures/particle/particles.png"):
            # 1.13 kept the 8px cell size and GREW the canvas (1.8.9 is
            # 128x128, 1.13.2 is 256x256 at the same coordinates), so restate
            # these boxes against a 128 reference. Proportional scaling then
            # yields cell = width/16, correct for a 1x or a 4x 1.8.9 atlas.
            for r in recs:
                if r["box"][4:] == [256, 256]:
                    r["box"][4:] = [PARTICLE_REF, PARTICLE_REF]
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
    for fn, n in SKIPPED_HELPERS.items():
        if n:
            print(f"skipped {n} {fn}() outputs (not ported - see spec)")
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
