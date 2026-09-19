"""
Scripted hook generation: given a target .bf, a real vanilla decompile, and a mod's changed
procedure(s), extracts the changed procedure bodies, remaps script variables using
vanilla_svar_map (preserving vanilla's own numbers for anything an unhooked sibling still
depends on, only allocating fresh slots for genuinely new state), and emits a ready-to-compile
.flow + companion .msg pair. This is the "template" path -- worth it when a mod's real changes are
the same repeated shape across many files; for one-off changes, writing the hook by hand per the
main README's methodology section is usually clearer.
"""
import sys, os, glob, re, json
sys.path.insert(0, os.path.dirname(__file__))
from rescan_generic import build_bit_patterns, load_procs, normalize
from merge_morgana_compat import load_blocks
from vanilla_svar_map import build_map, VAR_PATTERNS

# (var_prefix, declared type keyword) -- two independent script-level variable namespaces.
NAMESPACES = [("sVar", "int"), ("sfVar", "float")]

def get_vanilla_decl_count(vanilla_text, var_prefix, decl_type):
    decl_re = re.compile(r'^\s*' + decl_type + r'\s+' + var_prefix + r'(\d+)\s*;\s*$', re.MULTILINE)
    first_void = vanilla_text.find("\nvoid ")
    head = vanilla_text[:first_void] if first_void != -1 else vanilla_text
    nums = [int(m.group(1)) for m in decl_re.finditer(head)]
    return (max(nums) + 1) if nums else 0

def plan_file(review_dir, rel, real_proc_names):
    """real_proc_names: list of COMMON procedure names (same name in vanilla+mod) whose
    bodies genuinely differ and need to become <name>_hook.

    Unlike the original generator, this version never blindly remaps every script variable
    to a fresh slot. For each of the two script-level variable namespaces (int sVarN, float
    sfVarN), it first recovers the true vanilla<->mod correspondence using every OTHER
    (unhooked, unchanged) common procedure in the file as a Rosetta stone, and reuses
    vanilla's own number for any mod variable with a confident mapping -- this is what makes
    it safe against the "hooked procedure shares state with an unhooked sibling" bug
    described in docs/FINDINGS.md. Only variables with NO recoverable vanilla correspondence
    (genuinely new mod-introduced state) get a fresh slot beyond vanilla's declared count."""
    base = os.path.join(review_dir, rel.replace("/", os.sep))
    vflow_path = base + ".vanilla.flow"
    mflow_path = base + ".mod.flow"
    vmsg_path = base + ".vanilla.msg"
    mmsg_path = base + ".mod.msg"

    vtext = open(vflow_path, encoding="utf-8").read()
    vprocs = load_procs(vflow_path)
    mprocs = load_procs(mflow_path)

    missing = [n for n in real_proc_names if n not in vprocs or n not in mprocs]
    if missing:
        return {"rel": rel, "missing_targets": missing}

    bodies_raw = []
    for n in real_proc_names:
        b = mprocs[n]
        b = re.sub(r'^(void\s+)' + re.escape(n) + r'(\s*\()',
                    lambda m: m.group(1) + n + "_hook" + m.group(2), b, count=1)
        bodies_raw.append((n, b))

    all_decl_lines = []
    all_test_decl_lines = []
    total_preserved = 0
    total_fresh = 0
    all_unmapped_ambiguous = []
    all_remap = {}

    for var_prefix, decl_type in NAMESPACES:
        var_re = VAR_PATTERNS[var_prefix]
        v2m, m2v, ambiguous_v, ambiguous_m = build_map(vflow_path, mflow_path, real_proc_names, var_prefix=var_prefix)

        combined = "\n".join(b for _, b in bodies_raw)
        referenced = sorted(set(int(x) for x in var_re.findall(combined)))
        vanilla_count = get_vanilla_decl_count(vtext, var_prefix, decl_type)

        remap = {}
        unmapped_ambiguous = []
        next_fresh = vanilla_count
        for old in referenced:
            if old in ambiguous_m:
                unmapped_ambiguous.append(old)
                remap[old] = next_fresh
                next_fresh += 1
            elif old in m2v:
                remap[old] = m2v[old]
            else:
                remap[old] = next_fresh
                next_fresh += 1

        def remap_sub(m, remap=remap, var_prefix=var_prefix):
            return f"{var_prefix}{remap[int(m.group(1))]}"

        bodies_raw = [(n, var_re.sub(remap_sub, b)) for n, b in bodies_raw]

        preserved_values = sorted(set(v for k, v in remap.items() if k in m2v and k not in ambiguous_m))
        all_decl_lines += [f"{decl_type} {var_prefix}{v};" for v in sorted(set(remap.values()))]
        all_test_decl_lines += [f"{decl_type} {var_prefix}{v};" for v in sorted(set(remap.values()) - set(preserved_values))]
        total_preserved += sum(1 for k in referenced if k in m2v and k not in ambiguous_m)
        total_fresh += sum(1 for k in referenced if k not in m2v or k in ambiguous_m)
        all_unmapped_ambiguous += [f"{var_prefix}{v}" for v in unmapped_ambiguous]
        all_remap[var_prefix] = {str(k): v for k, v in remap.items()}

    new_bodies = [b for _, b in bodies_raw]

    msg_overrides = []
    if os.path.exists(vmsg_path) and os.path.exists(mmsg_path):
        vblocks, _ = load_blocks(vmsg_path)
        mblocks, morder = load_blocks(mmsg_path)
        for name in morder:
            if vblocks.get(name) != mblocks[name]:
                msg_overrides.append((name, mblocks[name]))
    elif os.path.exists(mmsg_path) and not os.path.exists(vmsg_path):
        mblocks, morder = load_blocks(mmsg_path)
        for name in morder:
            msg_overrides.append((name, mblocks[name]))

    return {
        "rel": rel,
        "hook_names": [n + "_hook" for n in real_proc_names],
        "hook_targets": real_proc_names,
        "helper_names": [],
        "missing_targets": [],
        "svar_remap": all_remap,
        "preserved_vanilla_count": total_preserved,
        "fresh_count": total_fresh,
        "unmapped_ambiguous": all_unmapped_ambiguous,
        "decl_lines": all_decl_lines,
        "test_decl_lines": all_test_decl_lines,
        "bodies": new_bodies,
        "msg_overrides": msg_overrides,
    }

if __name__ == "__main__":
    # args: review_dir out_plan_dir  rel1:proc1,proc2  rel2:proc1  ...
    review_dir = sys.argv[1]
    out_plan_dir = sys.argv[2]
    os.makedirs(out_plan_dir, exist_ok=True)
    for spec in sys.argv[3:]:
        rel, procs = spec.split(":", 1)
        proc_list = procs.split(",")
        plan = plan_file(review_dir, rel, proc_list)
        if plan.get("missing_targets"):
            print(f"PROBLEM {rel}: missing targets {plan['missing_targets']}")
            continue
        safe_name = rel.replace("/", "__")
        with open(os.path.join(out_plan_dir, safe_name + ".json"), "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=1)
        amb_note = f" AMBIGUOUS={plan['unmapped_ambiguous']}" if plan["unmapped_ambiguous"] else ""
        print(f"OK {rel} :: preserved={plan['preserved_vanilla_count']} fresh={plan['fresh_count']}{amb_note}")
