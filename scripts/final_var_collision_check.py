"""
Cross-mod SCRIPT-VARIABLE-DECLARATION collision check.

Companion to final_collision_check.py, same basename-grouping approach, but checks the other half
of the "hard compile failure" surface: two mods each declaring the same `int sVarN;` / `float
sfVarN;` script-level variable for the same target file. This fails EVEN IF the declarations are
byte-identical and EVEN IF the number merely duplicates one vanilla itself already declares --
FileEmulationFramework's merge doesn't dedupe declarations, only vanilla-procedure redefinitions
get real overwrite-by-name handling. See docs/FINDINGS.md, "The merge model", for why this is not
the same as normal "last mod wins" behavior. Expected result on a healthy mod set: 0.

Config: set P5R_MODS_ROOT (see scripts/README.md / _common.py).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import get_enabled_mods

DECL_RE = re.compile(r'^\s*(?:int|float)\s+(sVar\d+|sfVar\d+)\s*;\s*$', re.MULTILINE)
PROC_RE = re.compile(r'^void\s+\w+\s*\(', re.MULTILINE)


def own_decls(text):
    m = PROC_RE.search(text)
    head = text[:m.start()] if m else text
    return set(DECL_RE.findall(head))


per_mod = {}
for mid, d in get_enabled_mods().items():
    bf_root = os.path.join(d, "FEmulator", "BF")
    files = []
    if os.path.isdir(bf_root):
        for r, dirs, fs in os.walk(bf_root):
            for fn in fs:
                if fn.lower().endswith(".flow"):
                    files.append(os.path.join(r, fn))
    per_mod[mid] = files

by_basename = {}
for mid, files in per_mod.items():
    for f in files:
        base = os.path.splitext(os.path.basename(f))[0].lower()
        by_basename.setdefault(base, []).append((mid, f))

collisions = []
for base, providers in by_basename.items():
    if len(providers) < 2:
        continue
    decls_by_provider = []
    for mid, f in providers:
        try:
            text = open(f, encoding="utf-8", errors="replace").read()
        except Exception:
            text = ""
        decls_by_provider.append((mid, f, own_decls(text)))
    for i in range(len(decls_by_provider)):
        for j in range(i + 1, len(decls_by_provider)):
            mi, fi, di = decls_by_provider[i]
            mj, fj, dj = decls_by_provider[j]
            common = di & dj
            if common:
                collisions.append((base, mi, mj, sorted(common)))

print(f"Total variable-declaration collisions remaining: {len(collisions)}")
for base, mi, mj, common in collisions:
    print(f"  {base}: {mi}  <->  {mj}  -- {common}")
