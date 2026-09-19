"""
Decompiler-noise normalizer. AtlusScriptCompiler renumbers every local/script variable fresh on
each decompile and has several purely-cosmetic display variants (bit-id decimal vs hex, -1 vs
65535, negative-zero floats, goto-label suffix renumbering, [coop] vs [f 5 13] aliasing, dead
inits). This collapses all of them so you can diff two decompiles of the "same" procedure and see
only REAL behavioral differences. See docs/FINDINGS.md, "Decompiler-noise catalog", for the full
list and why each one is safe to normalize away. Exposes build_bit_patterns / load_procs /
normalize for reuse by the other scripts in this folder.
"""
import re, sys, difflib

NUM_TOKEN = r'(0[xX][0-9a-fA-F]+|\d+)'
BIT_EXPR_RE = re.compile(r'\(\s*' + NUM_TOKEN + r'\s*\+\s*' + NUM_TOKEN + r'\s*\)')

def build_bit_patterns(vpath, mpath):
    text = open(vpath, encoding="utf-8").read() + open(mpath, encoding="utf-8").read()
    return build_bit_patterns_from_text(text)

def build_bit_patterns_from_text(text):
    mapping = {}
    for m in re.finditer(r'//\s*bit id\s*\((\d+)\)\s*\+\s*\((\d+)\)\s*=\s*(\d+)', text):
        cat, off, val = int(m.group(1)), int(m.group(2)), m.group(3)
        mapping[(cat, off)] = val
    return mapping

def load_procs(path):
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    decls = []
    for i, line in enumerate(lines):
        m = re.match(r'\s*void\s+(\w+)\s*\(', line)
        if m:
            decls.append((i, m.group(1)))
    procs = {}
    for idx, (start, name) in enumerate(decls):
        if idx + 1 < len(decls):
            end = decls[idx + 1][0] - 3
        else:
            end = len(lines)
        procs[name] = "".join(lines[start:end])
    return procs

def normalize(text, bit_mapping):
    def sub_bit_expr(m):
        cat = int(m.group(1), 0)
        off = int(m.group(2), 0)
        val = bit_mapping.get((cat, off))
        return val if val is not None else m.group(0)
    text = BIT_EXPR_RE.sub(sub_bit_expr, text)
    text = re.sub(r'\b0[xX][0-9a-fA-F]+\b', lambda m: str(int(m.group(0), 16)), text)
    text = re.sub(r'\bvar\d+\b', 'VAR', text)
    text = re.sub(r'\bsVar\d+\b', 'SVAR', text)
    text = re.sub(r'\bfVar\d+\b', 'FVAR', text)
    text = re.sub(r'\bsfVar\d+\b', 'SFVAR', text)
    text = re.sub(r'(?<![\w.])-1(?=[,;\)])', 'N1', text)
    text = re.sub(r'(?<![\w.])65535(?=[,;\)])', 'N1', text)
    text = re.sub(r'-0\.0*f\b', '0.0f', text)
    text = re.sub(r'\b0\.0*f\b', '0.0f', text)
    text = re.sub(r'\b_(\d+)(?:_\d+)*\b', r'_LBL\1', text)
    text = "\n".join(l for l in text.split("\n") if not re.match(r'\s*//\s*bit id', l))
    text = "\n".join(l for l in text.split("\n") if l.strip() != "return;")
    lines = [re.sub(r'\s+', ' ', l).strip() for l in text.split("\n")]
    return [l for l in lines if l]

def main(vpath, mpath):
    bit_patterns = build_bit_patterns(vpath, mpath)
    print(f"Loaded {len(bit_patterns)} bit-id substitution patterns", file=sys.stderr)
    vprocs = load_procs(vpath)
    mprocs = load_procs(mpath)
    print(f"vanilla procs: {len(vprocs)}, mod procs: {len(mprocs)}", file=sys.stderr)
    common = sorted(set(vprocs) & set(mprocs))
    only_v = sorted(set(vprocs) - set(mprocs))
    only_m = sorted(set(mprocs) - set(vprocs))
    results = []
    for name in common:
        vn = normalize(vprocs[name], bit_patterns)
        mn = normalize(mprocs[name], bit_patterns)
        if vn != mn:
            sm = difflib.SequenceMatcher(None, vn, mn)
            diffcount = sum(1 for op in sm.get_opcodes() if op[0] != 'equal')
            results.append((name, diffcount, len(vn), len(mn)))
    results.sort(key=lambda r: -r[1])
    print(f"\nTotal common procedures: {len(common)}")
    print(f"Only in vanilla: {len(only_v)} -> {only_v}")
    print(f"Only in mod: {len(only_m)} -> {only_m}")
    print(f"Procedures with REAL (post-normalization) differences: {len(results)}\n")
    for name, diffcount, vl, ml in results:
        print(f"{name}\tdiffops={diffcount}\tvlines={vl}\tmlines={ml}")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
