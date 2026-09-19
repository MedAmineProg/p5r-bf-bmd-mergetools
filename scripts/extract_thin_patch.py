"""
Converts a full-copy compat mod (every file from N constituent mods, reconciled) into a thin
patch (only the files that genuinely needed reconciling). For each file the compat mod ships,
keeps it only if it does NOT byte-match any single constituent mod's own file at that path --
a file matching one constituent exactly needs no patch, that constituent already provides it.
Case-insensitive path comparison (P5R mods are inconsistent about file-extension casing).
"""
import os, shutil

def walk_files(root):
    """Keys are lowercased -- P5R's own file/directory casing is inconsistent between mods
    (e.g. E740_001.BMD vs e740_001.bmd are the same file on a case-insensitive filesystem),
    so comparisons must be case-insensitive or genuinely-identical files get miscounted as
    distinct."""
    out = {}
    for r, dirs, files in os.walk(root):
        for fn in files:
            rel = os.path.relpath(os.path.join(r, fn), root).replace("\\", "/").lower()
            out[rel] = os.path.join(r, fn)
    return out

def read(path):
    try:
        return open(path, "rb").read()
    except Exception:
        return None

def build_thin_patch(compat_fem_bf, source_fem_bfs, out_fem_bf):
    """compat_fem_bf: the full-copy compat mod's FEmulator/BF dir.
    source_fem_bfs: list of each constituent source mod's own FEmulator/BF dir.
    out_fem_bf: destination dir for the thin patch's FEmulator/BF.

    A file is kept in the thin patch only if it does NOT byte-match any single source mod's
    own file at that same relative path -- i.e. it's a genuine combination, not something one
    source mod already fully provides on its own."""
    compat_files = walk_files(compat_fem_bf)
    source_indexes = [walk_files(s) for s in source_fem_bfs]

    kept = []
    skipped_matches_source = []
    for rel, compat_path in compat_files.items():
        compat_bytes = read(compat_path)
        matched_any = False
        for idx in source_indexes:
            if rel in idx:
                src_bytes = read(idx[rel])
                if src_bytes is not None and src_bytes == compat_bytes:
                    matched_any = True
                    break
        if matched_any:
            skipped_matches_source.append(rel)
        else:
            kept.append(rel)

    os.makedirs(out_fem_bf, exist_ok=True)
    for rel in kept:
        dst = os.path.join(out_fem_bf, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(compat_files[rel], dst)

    return kept, skipped_matches_source

if __name__ == "__main__":
    import sys
    compat_fem_bf = sys.argv[1]
    out_fem_bf = sys.argv[2]
    source_fem_bfs = sys.argv[3:]
    kept, skipped = build_thin_patch(compat_fem_bf, source_fem_bfs, out_fem_bf)
    print(f"Kept (genuine merges): {len(kept)}")
    print(f"Skipped (identical to one source, base mod already provides it): {len(skipped)}")
