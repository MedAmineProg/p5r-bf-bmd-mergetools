"""
Recovers the TRUE vanilla<->mod script-variable correspondence for a hooked file by using every
OTHER (unhooked, unchanged) procedure in the same file as a Rosetta stone: both are the same
procedure, just independently renumbered by the decompiler, so zipping their sVarN/sfVarN
occurrence sequences positionally recovers the mapping. This exists because "always allocate a
fresh variable slot" is unsafe -- a hooked procedure that shares an EXISTING vanilla variable with
an unhooked sibling procedure will silently read/write the wrong slot if the hook renumbers it.
See docs/FINDINGS.md for the failure mode this prevents.
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(__file__))
from rescan_generic import build_bit_patterns, load_procs, normalize

SVAR_RE = re.compile(r'\bsVar(\d+)\b')
SFVAR_RE = re.compile(r'\bsfVar(\d+)\b')

VAR_PATTERNS = {"sVar": SVAR_RE, "sfVar": SFVAR_RE}

def build_map(vflow_path, mflow_path, hook_target_names, var_prefix="sVar"):
    """Returns (v2m, m2v, ambiguous_v, ambiguous_m):
    v2m/m2v are dicts of confidently-recovered 1:1 vanilla<->mod script-variable number
    correspondences (for the given prefix -- "sVar" for int script vars, "sfVar" for float
    script vars, two independent namespaces), built by cross-referencing every COMMON
    procedure that is NOT one of the hook targets and whose normalized text is identical
    between vanilla and mod (i.e. a genuinely unchanged procedure -- safe Rosetta stone).
    ambiguous_* are sets of numbers where different procedures disagreed."""
    var_re = VAR_PATTERNS[var_prefix]
    bit_patterns = build_bit_patterns(vflow_path, mflow_path)
    vprocs = load_procs(vflow_path)
    mprocs = load_procs(mflow_path)
    common = set(vprocs) & set(mprocs)
    unhooked_common = sorted(common - set(hook_target_names))

    v2m = {}
    m2v = {}
    ambiguous_v = set()
    ambiguous_m = set()

    for name in unhooked_common:
        vb = vprocs[name]
        mb = mprocs[name]
        if normalize(vb, bit_patterns) != normalize(mb, bit_patterns):
            continue  # actually changed (shouldn't happen for unhooked, but be safe)
        vseq = [int(x) for x in var_re.findall(vb)]
        mseq = [int(x) for x in var_re.findall(mb)]
        if len(vseq) != len(mseq):
            continue
        for vn, mn in zip(vseq, mseq):
            if vn in v2m and v2m[vn] != mn:
                ambiguous_v.add(vn)
            else:
                v2m[vn] = mn
            if mn in m2v and m2v[mn] != vn:
                ambiguous_m.add(mn)
            else:
                m2v[mn] = vn

    # An ambiguous vanilla number (maps to >1 distinct mod number across procedures)
    # poisons every mod number that ever pointed at it, and vice versa -- otherwise
    # two genuinely distinct variables can each look "individually consistent" from
    # one side while silently colliding onto the same slot. Propagate to a fixed
    # point since poisoning can chain through shared entries.
    changed = True
    while changed:
        changed = False
        for mn, vn in list(m2v.items()):
            if vn in ambiguous_v and mn not in ambiguous_m:
                ambiguous_m.add(mn)
                changed = True
        for vn, mn in list(v2m.items()):
            if mn in ambiguous_m and vn not in ambiguous_v:
                ambiguous_v.add(vn)
                changed = True
        for vn in list(ambiguous_v):
            v2m.pop(vn, None)
        for mn in list(ambiguous_m):
            m2v.pop(mn, None)

    return v2m, m2v, ambiguous_v, ambiguous_m

if __name__ == "__main__":
    vflow, mflow = sys.argv[1], sys.argv[2]
    hook_targets = sys.argv[3].split(",") if len(sys.argv) > 3 else []
    v2m, m2v, amb_v, amb_m = build_map(vflow, mflow, hook_targets)
    print(f"Recovered {len(m2v)} confident mod->vanilla sVar mappings")
    print("mod->vanilla:", dict(sorted(m2v.items())))
    if amb_m:
        print("AMBIGUOUS mod numbers (inconsistent across procedures):", sorted(amb_m))
