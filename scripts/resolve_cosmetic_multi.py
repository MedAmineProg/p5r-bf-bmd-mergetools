"""
Batch-resolves ModConverter's "needs review" backlog for the common case: many of those flags are
rescan_generic-detected 100%-cosmetic decompiler noise, not real logic changes. For each staged
review pair, normalizes and compares; cosmetic files get their message-only override auto-emitted
(or are confirmed no-actual-change) exactly like ModConverter's own auto-convert path, instead of
sitting on raw fallback pending a human. Handles mods whose raw-fallback files are split across
multiple CPK containers.
"""
import sys, os, glob
sys.path.insert(0, os.path.dirname(__file__))
from rescan_generic import build_bit_patterns, load_procs, normalize
from merge_morgana_compat import load_blocks

def classify(review_dir):
    pairs = []
    for vpath in glob.glob(os.path.join(review_dir, "**", "*.vanilla.flow"), recursive=True):
        base = vpath[:-len(".vanilla.flow")]
        mpath = base + ".mod.flow"
        if os.path.exists(mpath):
            pairs.append((base, vpath, mpath))

    real_files = []
    cosmetic_files = []
    for base, vpath, mpath in pairs:
        rel = os.path.relpath(base, review_dir)
        bit_patterns = build_bit_patterns(vpath, mpath)
        vprocs = load_procs(vpath)
        mprocs = load_procs(mpath)
        common = sorted(set(vprocs) & set(mprocs))
        only_v = sorted(set(vprocs) - set(mprocs))
        only_m = sorted(set(mprocs) - set(vprocs))
        real_procs = [n for n in common if normalize(vprocs[n], bit_patterns) != normalize(mprocs[n], bit_patterns)]
        if real_procs or only_v or only_m:
            real_files.append((rel, base, real_procs, only_v, only_m))
        else:
            cosmetic_files.append((rel, base))
    return real_files, cosmetic_files

def find_container(mod_root, containers, rel):
    rel_os = rel.replace("/", os.sep)
    for c in containers:
        candidate = os.path.join(mod_root, "P5REssentials", "CPK", c, rel_os)
        if os.path.exists(candidate):
            return c, candidate
    return None, None

def resolve(mod_root, review_dir, containers, dry_run=True):
    real_files, cosmetic_files = classify(review_dir)
    resolved_msg_override = 0
    resolved_no_change = 0
    unresolved_no_container = []
    log_lines = []

    for rel, base in cosmetic_files:
        vmsg = base + ".vanilla.msg"
        mmsg = base + ".mod.msg"
        rel_fwd = rel.replace("\\", "/")
        container, cpk_dest = find_container(mod_root, containers, rel_fwd)
        # loose .bmd overrides go under FEmulator/BMD (separate emulator); .bf under FEmulator/BF
        fem_emu = "BMD" if rel_fwd.lower().endswith(".bmd") else "BF"
        fem_dest = os.path.join(mod_root, "FEmulator", fem_emu, os.path.splitext(rel.replace("/", os.sep))[0] + ".msg")

        if container is None:
            unresolved_no_container.append(rel_fwd)
            continue

        overrides = []
        if os.path.exists(vmsg) and os.path.exists(mmsg):
            vblocks, _ = load_blocks(vmsg)
            mblocks, morder = load_blocks(mmsg)
            for name in morder:
                if vblocks.get(name) != mblocks[name]:
                    overrides.append((name, mblocks[name]))

        if overrides:
            resolved_msg_override += 1
            log_lines.append(f"{rel_fwd} :: RESOLVED message-only ({len(overrides)} blocks, container={container}) -- flow diff confirmed 100% cosmetic (decompiler noise) via batch_rescan normalizer")
            if not dry_run:
                os.makedirs(os.path.dirname(fem_dest), exist_ok=True)
                with open(fem_dest, "w", encoding="utf-8") as f:
                    for name, block in overrides:
                        f.write(block.rstrip() + "\n\n")
                open(cpk_dest, "wb").close()
        else:
            resolved_no_change += 1
            log_lines.append(f"{rel_fwd} :: RESOLVED no-actual-change (container={container}) -- flow diff confirmed 100% cosmetic (decompiler noise) via batch_rescan normalizer, and message content identical too")
            if not dry_run:
                open(cpk_dest, "wb").close()

    print(f"Real (needs hand hook): {len(real_files)}")
    print(f"Resolved as message-only override: {resolved_msg_override}")
    print(f"Resolved as no-actual-change: {resolved_no_change}")
    print(f"Unresolved (no matching raw-fallback file found in any container): {len(unresolved_no_container)}")
    for r in unresolved_no_container:
        print(f"  MISSING CONTAINER MATCH: {r}")
    print(f"dry_run={dry_run}")

    return real_files, log_lines

if __name__ == "__main__":
    mod_root = sys.argv[1]
    review_dir = sys.argv[2]
    containers = sys.argv[3].split(",")
    dry_run = len(sys.argv) > 4 and sys.argv[4] == "--dry-run"
    real_files, log_lines = resolve(mod_root, review_dir, containers, dry_run=dry_run)
    if not dry_run:
        with open(os.path.join(mod_root, "_cosmetic_resolution_log.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(log_lines) + "\n")
    print("\n--- Files still needing hand-written hooks ---")
    for rel, base, real_procs, only_v, only_m in real_files:
        print(rel.replace("\\", "/"), real_procs, only_v, only_m)
