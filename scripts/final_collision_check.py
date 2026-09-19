"""
Cross-mod PROCEDURE-NAME collision check.

Groups every enabled mod's FEmulator/BF/*.flow files by basename (FileEmulationFramework matches
a target by filename, tolerant of subfolder differences between mods -- confirmed: one mod can
ship "FEmulator/BF/scheduler_08.flow" flat while another ships the same target nested under
"FEmulator/BF/SCHEDULER/SCHEDULER_08.flow" and they still collide). Flags any basename where two
or more mods declare the SAME procedure name.

This is a HARD compile failure in the live FileEmulationFramework merge, not a soft "last mod
wins" -- see docs/FINDINGS.md, "The merge model". Two mods redefining a name that ISN'T a vanilla
procedure (e.g. two identical `_hook`-suffixed names, or a duplicate script-variable declaration --
see final_var_collision_check.py for that case) never resolves; it's a runtime "Cannot Create File
From ...!" no matter how the two definitions compare. Expected result on a healthy mod set: 0.

Config: set P5R_MODS_ROOT (see scripts/README.md / _common.py).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import get_enabled_mods
from flow_extract import list_procedures

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

# group by basename-noext (lowered) as the "target identity"
by_basename = {}
for mid, files in per_mod.items():
    for f in files:
        base = os.path.splitext(os.path.basename(f))[0].lower()
        by_basename.setdefault(base, []).append((mid, f))

real_collisions = []
for base, providers in by_basename.items():
    if len(providers) < 2:
        continue
    names_by_provider = []
    for mid, f in providers:
        try:
            text = open(f, encoding="utf-8", errors="replace").read()
        except Exception:
            text = ""
        names = set(n for n, s, e in list_procedures(text))
        names_by_provider.append((mid, f, names))
    for i in range(len(names_by_provider)):
        for j in range(i + 1, len(names_by_provider)):
            mi, fi, ni = names_by_provider[i]
            mj, fj, nj = names_by_provider[j]
            common = ni & nj
            if common:
                real_collisions.append((base, mi, mj, sorted(common)))

print(f"Total real procedure-name collisions remaining: {len(real_collisions)}")
for base, mi, mj, common in real_collisions:
    print(f"  {base}: {mi}  <->  {mj}  -- {common}")
