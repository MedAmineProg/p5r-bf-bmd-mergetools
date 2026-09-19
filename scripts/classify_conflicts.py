"""
Byte-level conflict classifier: takes audit_all_pairs.py's raw name-overlap hits and, using
rescan_generic's normalizer, separates genuine cross-mod conflicts from the cosmetic decompiler-
formatting false positive (one mod's decompile shows unsimplified BIT_CHK((CATEGORY + OFFSET))
with a bit-id comment, another shows the pre-simplified literal -- same value, not a real diff).
Without this step, procedure-conflict counts across a large mod set can be substantially inflated.
"""
import sys, os, glob, re, itertools
sys.path.insert(0, os.path.dirname(__file__))
from merge_morgana_compat import load_blocks
from rescan_generic import normalize as rescan_normalize

import os as _os
MODS_ROOT = _os.environ.get("P5R_PROJECT_MODS_ROOT")
if not MODS_ROOT:
    raise SystemExit("Set P5R_PROJECT_MODS_ROOT to the folder containing your .mergeable mod outputs.")

def norm_key(rel_no_ext):
    return rel_no_ext.replace("\\", "/").lower()

HOOK_PROC_RE = re.compile(r'^\s*void\s+(\w+_hook)\s*\(\s*\)\s*\n\s*\{', re.MULTILINE)

def extract_proc_body(text, name):
    m = re.search(r'^\s*void\s+' + re.escape(name) + r'\s*\(\s*\)\s*\n\s*\{', text, re.MULTILINE)
    if not m:
        return None
    start = m.start()
    brace_start = text.index("{", m.end() - 1)
    depth = 0
    i = brace_start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    return text[start:i+1]

BIT_ID_RE = re.compile(r'//\s*bit id\s*\((\d+)\)\s*\+\s*\((\d+)\)\s*=\s*(\d+)')

def build_global_bit_patterns(*fem_bf_roots):
    mapping = {}
    for root in fem_bf_roots:
        for p in glob.glob(os.path.join(root, "**", "*.flow"), recursive=True):
            try:
                text = open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            for m in BIT_ID_RE.finditer(text):
                cat, off, val = int(m.group(1)), int(m.group(2)), m.group(3)
                mapping[(cat, off)] = val
    return mapping

def norm_body(b, bit_patterns):
    return rescan_normalize(b, bit_patterns)

def index_mod(fem_bf_root):
    """key -> {"msgs": {name: block_text}, "procs": {name: body_text}}"""
    idx = {}
    all_msg_files = {}
    for p in glob.glob(os.path.join(fem_bf_root, "**", "*.msg"), recursive=True):
        rel = os.path.relpath(p, fem_bf_root)
        base_noext = os.path.splitext(rel)[0]
        all_msg_files[base_noext] = p

    flow_files = glob.glob(os.path.join(fem_bf_root, "**", "*.flow"), recursive=True)
    flow_targets = set()
    for p in flow_files:
        rel = os.path.relpath(p, fem_bf_root)
        base_noext = os.path.splitext(rel)[0]
        flow_targets.add(base_noext)
        key = norm_key(base_noext)
        idx.setdefault(key, {"msgs": {}, "procs": {}})
        try:
            text = open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            text = ""
        for name in HOOK_PROC_RE.findall(text):
            body = extract_proc_body(text, name)
            if body:
                idx[key]["procs"][name] = body
        d = os.path.dirname(p)
        base = os.path.splitext(os.path.basename(p))[0]
        msgp = os.path.join(d, base + "_msg.msg")
        if os.path.exists(msgp):
            try:
                blocks, _ = load_blocks(msgp)
                idx[key]["msgs"].update(blocks)
            except Exception:
                pass

    for base_noext, p in all_msg_files.items():
        if base_noext in flow_targets or base_noext.endswith("_msg"):
            continue
        key = norm_key(base_noext)
        idx.setdefault(key, {"msgs": {}, "procs": {}})
        try:
            blocks, _ = load_blocks(p)
            idx[key]["msgs"].update(blocks)
        except Exception:
            pass
    return idx

def main():
    mod_a, mod_b = sys.argv[1], sys.argv[2]
    root_a = os.path.join(MODS_ROOT, mod_a, "FEmulator", "BF")
    root_b = os.path.join(MODS_ROOT, mod_b, "FEmulator", "BF")
    idx_a = index_mod(root_a)
    idx_b = index_mod(root_b)
    bit_patterns = build_global_bit_patterns(root_a, root_b)
    shared = set(idx_a.keys()) & set(idx_b.keys())

    real_msg = []
    identical_msg = []
    real_proc = []
    identical_proc = []

    for key in sorted(shared):
        a, b = idx_a[key], idx_b[key]
        for name in sorted(set(a["msgs"]) & set(b["msgs"])):
            if a["msgs"][name].strip() == b["msgs"][name].strip():
                identical_msg.append((key, name))
            else:
                real_msg.append((key, name))
        for name in sorted(set(a["procs"]) & set(b["procs"])):
            if norm_body(a["procs"][name], bit_patterns) == norm_body(b["procs"][name], bit_patterns):
                identical_proc.append((key, name))
            else:
                real_proc.append((key, name))

    print(f"{mod_a} <-> {mod_b}")
    print(f"  message conflicts: {len(identical_msg)} identical (harmless), {len(real_msg)} REAL")
    print(f"  procedure conflicts: {len(identical_proc)} identical (harmless), {len(real_proc)} REAL")
    if real_proc:
        print("  REAL PROC CONFLICTS:")
        for key, name in real_proc:
            print(f"    {key} :: {name}")
    if real_msg:
        print(f"  REAL MSG CONFLICTS ({len(real_msg)}):")
        for key, name in real_msg[:40]:
            print(f"    {key} :: {name}")
        if len(real_msg) > 40:
            print(f"    ... and {len(real_msg)-40} more")

if __name__ == "__main__":
    main()
