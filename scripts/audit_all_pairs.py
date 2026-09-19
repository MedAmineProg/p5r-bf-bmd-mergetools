"""
All-pairs cross-mod conflict audit: for every pair of .mergeable mods sharing a target file, lists
message-block-name AND hooked-procedure-name overlaps. This is the RAW signal (name overlap) --
see classify_conflicts.py for the byte-level classifier that separates genuine conflicts from the
cosmetic bit-id-reformatting false positive that inflates this list. Run this first to find every
pair worth checking, then classify_conflicts.py (or a manual read) to see which ones are real.
"""
import sys, os, glob, re, itertools

sys.path.insert(0, os.path.dirname(__file__))
from merge_morgana_compat import load_blocks

import os as _os
MODS_ROOT = _os.environ.get("P5R_PROJECT_MODS_ROOT")
if not MODS_ROOT:
    raise SystemExit("Set P5R_PROJECT_MODS_ROOT to the folder containing your .mergeable mod outputs.")

def norm_key(rel_no_ext):
    return rel_no_ext.replace("\\", "/").lower()

HOOK_DECL_RE = re.compile(r'^\s*void\s+(\w+_hook)\s*\(', re.MULTILINE)

def index_mod(fem_bf_root):
    """key -> (set of message block names, set of hooked-procedure names)"""
    idx = {}

    all_msg = {}
    for p in glob.glob(os.path.join(fem_bf_root, "**", "*.msg"), recursive=True):
        rel = os.path.relpath(p, fem_bf_root)
        base_noext = os.path.splitext(rel)[0]
        all_msg[base_noext] = p

    flow_files = glob.glob(os.path.join(fem_bf_root, "**", "*.flow"), recursive=True)
    flow_targets = set()
    for p in flow_files:
        rel = os.path.relpath(p, fem_bf_root)
        base_noext = os.path.splitext(rel)[0]
        flow_targets.add(base_noext)
        key = norm_key(base_noext)
        idx.setdefault(key, (set(), set()))

        try:
            text = open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            text = ""
        hooks = set(HOOK_DECL_RE.findall(text))
        idx[key][1].update(hooks)

        d = os.path.dirname(p)
        base = os.path.splitext(os.path.basename(p))[0]
        companion = os.path.join(d, base + "_msg.msg")
        if os.path.exists(companion):
            try:
                blocks, order = load_blocks(companion)
                idx[key][0].update(blocks.keys())
            except Exception:
                pass

    for base_noext, p in all_msg.items():
        if base_noext in flow_targets:
            continue
        if base_noext.endswith("_msg"):
            continue
        key = norm_key(base_noext)
        idx.setdefault(key, (set(), set()))
        try:
            blocks, order = load_blocks(p)
            idx[key][0].update(blocks.keys())
        except Exception:
            pass

    return idx

def main():
    mod_dirs = sorted(
        d for d in glob.glob(os.path.join(MODS_ROOT, "*.mergeable"))
        if os.path.isdir(os.path.join(d, "FEmulator", "BF"))
    )
    names = [os.path.basename(d) for d in mod_dirs]
    print(f"Indexing {len(names)} mods...")

    indices = {}
    for d, name in zip(mod_dirs, names):
        indices[name] = index_mod(os.path.join(d, "FEmulator", "BF"))
        print(f"  {name}: {len(indices[name])} target files")

    print("\n=== PAIRWISE CONFLICT SCAN ===\n")
    any_found = False
    for a, b in itertools.combinations(names, 2):
        idx_a, idx_b = indices[a], indices[b]
        shared = set(idx_a.keys()) & set(idx_b.keys())
        if not shared:
            continue
        msg_conflicts = []
        proc_conflicts = []
        for key in shared:
            a_msgs, a_procs = idx_a[key]
            b_msgs, b_procs = idx_b[key]
            common_msgs = a_msgs & b_msgs
            common_procs = a_procs & b_procs
            if common_msgs:
                msg_conflicts.append((key, common_msgs))
            if common_procs:
                proc_conflicts.append((key, common_procs))
        if msg_conflicts or proc_conflicts:
            any_found = True
            print(f"### {a}  <->  {b}")
            print(f"    shared target files: {len(shared)}")
            for key, names_set in msg_conflicts:
                print(f"    MSG CONFLICT  {key} :: {sorted(names_set)}")
            for key, names_set in proc_conflicts:
                print(f"    PROC CONFLICT {key} :: {sorted(names_set)}")
            print()
    if not any_found:
        print("No conflicts found across any pair.")

if __name__ == "__main__":
    main()
