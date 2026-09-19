"""
On-demand extraction + decompilation of TRUE vanilla content for any target .bf, with a
persistent on-disk cache keyed by target path. Used throughout the hook-writing workflow to
diff a mod's changes against real vanilla rather than against another mod's raw-fallback copy
(see docs/FINDINGS.md and the main README for why that distinction matters).

Config (environment variables):
  P5R_CPKFILEEXTRACT_EXE   Path to CpkFileExtract.exe (built from the CpkFileExtract/ folder
                           in this repo).
  P5R_COMPILER_EXE         Path to AtlusScriptCompiler.exe.
  P5R_CPK_ROOT             Folder containing your P5R CPK files (BASE.CPK, EN.CPK, ...).
  P5R_CPK_LIST             Optional, comma-separated CPK filenames to search, in order.
                           Default: "BASE.CPK,EN.CPK,SOUND_E.CPK,SOUND_J.CPK"
  P5R_VANILLA_CACHE_DIR    Optional. Where to persist decompiled vanilla + lookup metadata.
                           Default: a "vanilla_cache_store" folder next to this script.
"""
import os, subprocess, json, hashlib, re


def _require(env_var):
    v = os.environ.get(env_var)
    if not v:
        raise SystemExit(f"Set {env_var} before using vanilla_cache.py (see its module docstring).")
    return v


EXTRACT_EXE = _require("P5R_CPKFILEEXTRACT_EXE")
COMPILER = _require("P5R_COMPILER_EXE")
CPK_ROOT = _require("P5R_CPK_ROOT")
CPKS = [c.strip() for c in os.environ.get("P5R_CPK_LIST", "BASE.CPK,EN.CPK,SOUND_E.CPK,SOUND_J.CPK").split(",") if c.strip()]

CACHE_DIR = os.environ.get("P5R_VANILLA_CACHE_DIR") or os.path.join(os.path.dirname(__file__), "vanilla_cache_store")
os.makedirs(CACHE_DIR, exist_ok=True)

DECL_RE = re.compile(r"^\s*(?:int|float)\s+(s(?:f)?Var\d+)\s*;\s*$", re.MULTILINE)


def find_container_and_extract(rel_path_bf):
    """rel_path_bf like 'FIELD/HIT/FHIT_151_001_00.bf' (no leading slash). Tries each CPK via
    --search on the basename, then extracts using the exact internal path returned.

    Some CPKs contain multiple files sharing the same basename in DIFFERENT folders (confirmed
    the hard way: BASE.CPK can hold both an unrelated same-named file in one folder and the real
    target in another -- see docs/FINDINGS.md, "Never key a lookup on basename alone"). A
    basename-only match can silently grab the wrong one, so this prefers, in order: (1) a match
    whose full directory ALSO matches rel_path_bf's directory, case-insensitively; (2) otherwise
    the first basename+.bf match found, across every configured CPK."""
    base = os.path.basename(rel_path_bf)
    base_noext = os.path.splitext(base)[0]
    want_dir = os.path.dirname(rel_path_bf).replace("\\", "/").lower()

    candidates = []  # (cpk, line)
    for cpk in CPKS:
        proc = subprocess.run([EXTRACT_EXE, "--search", os.path.join(CPK_ROOT, cpk), base_noext],
                               capture_output=True, text=True, timeout=120)
        lines = [l.strip() for l in proc.stdout.splitlines() if l.strip() and "matches" not in l]
        for line in lines:
            b, ext = os.path.splitext(os.path.basename(line))
            if b.lower() == base_noext.lower() and ext.lower() == ".bf":
                candidates.append((cpk, line))

    for cpk, line in candidates:
        if os.path.dirname(line).replace("\\", "/").lower() == want_dir:
            return cpk, line
    if candidates:
        return candidates[0]
    return None, None


def get_vanilla_flow(rel_path_bf):
    """Returns (decompiled_flow_text, declared_names_set) for the true vanilla version of
    rel_path_bf, using a persistent on-disk cache keyed by rel_path_bf."""
    key = rel_path_bf.replace("\\", "/").lower()
    cache_key = hashlib.md5(key.encode()).hexdigest()
    cached_flow = os.path.join(CACHE_DIR, cache_key + ".flow")
    cached_meta = os.path.join(CACHE_DIR, cache_key + ".json")

    if os.path.exists(cached_flow) and os.path.exists(cached_meta):
        meta = json.load(open(cached_meta, encoding="utf-8"))
        if meta.get("status") == "ok":
            text = open(cached_flow, encoding="utf-8", errors="replace").read()
            return text, set(meta["decls"])
        else:
            return None, None

    cpk, internal_path = find_container_and_extract(rel_path_bf)
    if not internal_path:
        json.dump({"status": "not_found"}, open(cached_meta, "w"))
        return None, None

    raw_bf = os.path.join(CACHE_DIR, cache_key + ".bf")
    proc = subprocess.run([EXTRACT_EXE, os.path.join(CPK_ROOT, cpk), internal_path, raw_bf],
                           capture_output=True, text=True, timeout=120)
    if not os.path.exists(raw_bf) or os.path.getsize(raw_bf) == 0:
        json.dump({"status": "extract_failed", "log": proc.stdout + proc.stderr}, open(cached_meta, "w"))
        return None, None

    # -Encoding P5R_EFIGS is mandatory -- omitting it garbles special characters into fake diffs.
    proc2 = subprocess.run([COMPILER, raw_bf, "-Decompile", "-Library", "P5R", "-Encoding", "P5R_EFIGS", "-Out", cached_flow],
                            capture_output=True, text=True, timeout=90)
    if not os.path.exists(cached_flow):
        json.dump({"status": "decompile_failed", "log": proc2.stdout + proc2.stderr}, open(cached_meta, "w"))
        return None, None

    text = open(cached_flow, encoding="utf-8", errors="replace").read()
    decls = parse_declared_names(text)
    json.dump({"status": "ok", "decls": sorted(decls), "cpk": cpk, "internal_path": internal_path},
               open(cached_meta, "w"))
    return text, decls


def parse_declared_names(text):
    """Returns the set of top-level sVarN / sfVarN names declared anywhere in the file."""
    return set(DECL_RE.findall(text))
