# scripts

Python tooling that came out of actually converting and reconciling ~40 mods at scale. These
assume `ModConverter`'s output layout (a `.mergeable` mod with `FEmulator/BF/`, `FEmulator/BMD/`,
and `P5REssentials/CPK/<container>/` following its conventions) and were extracted from a larger
private working set -- expect to read and adapt them rather than treat this as a polished,
pip-installable package. Every script has a module docstring explaining what it does and why;
that's the real documentation, this file is just an index.

No hardcoded paths -- configuration is environment variables throughout. `_common.py` centralizes
the ones most scripts share (`P5R_MODS_ROOT`, `P5R_APPCONFIG`); each script's own docstring lists
whatever else it additionally needs.

| script | what it's for |
|---|---|
| `_common.py` | Shared config helpers (`get_enabled_mods()` reads a live Reloaded-II `AppConfig.json`). Not standalone, imported by the two collision checkers. |
| `flow_extract.py` | Brace-balanced procedure extraction/removal for an already-shipped `.flow` file. |
| `rescan_generic.py` | The decompiler-noise normalizer (see `docs/FINDINGS.md` section 5). Exposes `normalize`/`build_bit_patterns`/`load_procs` for reuse. |
| `vanilla_cache.py` | On-demand vanilla extraction + decompilation with a persistent disk cache, keyed by target path. |
| `vanilla_svar_map.py` | Recovers the true vanilla<->mod script-variable mapping for a hooked file, using unhooked sibling procedures as a Rosetta stone. |
| `merge_morgana_compat.py` | Generic message-block union/merge with an optional value-shift on one side -- the pattern for reconciling a mechanical-rule mod against a text-rewrite mod. |
| `generic_pipeline.py` | Compile + `-Hook` verify + `__JUMP` check + ship, given a "plan" dict. |
| `generate_generic_hooks_v2.py` | Builds a "plan" from a target file + changed procedure(s), with safe variable remapping via `vanilla_svar_map`. |
| `resolve_cosmetic_multi.py` | Batch-resolves `ModConverter`'s "needs review" backlog for files that turn out to be 100% decompiler noise. |
| `final_collision_check.py` | Cross-mod procedure-name collision check across your live enabled mod set. Expected result: 0. |
| `final_var_collision_check.py` | Same, for script-variable declarations. Expected result: 0. |
| `audit_all_pairs.py` | All-pairs name-overlap audit between `.mergeable` mods sharing a target file (raw signal). |
| `classify_conflicts.py` | Byte-level classifier on top of `audit_all_pairs.py`'s output -- separates real conflicts from the cosmetic bit-id false positive. |
| `extract_thin_patch.py` | Turns a full-copy compat mod into a thin patch (only the files that genuinely needed reconciling). |

## Running the collision checks

The two scripts you'll actually want to run regularly:

```
export P5R_MODS_ROOT="/path/to/Reloaded-II/Mods"
python final_collision_check.py
python final_var_collision_check.py
```

Both should report 0 on a healthy mod set. A nonzero result names the exact mods and target file
-- see `docs/FINDINGS.md` section 1 for what to do about it (make every provider agree; don't rely
on load order).
