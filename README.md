# p5r-bf-bmd-mergetools

Tools and notes for converting Persona 5 Royal mods that do **raw whole-file `.bf`/`.bmd`
replacement** into [FileEmulationFramework](https://github.com/Sewer56/FileEmulationFramework)
hooks and message overrides that **merge cleanly** with other mods touching the same file.

## The problem this solves

A lot of P5R script/dialogue mods work by replacing a whole compiled `.bf` (FlowScript) or `.bmd`
(message data) file wholesale. That's simple to make, but it means **any two mods that happen to
touch the same file are mutually exclusive** -- whichever loads last silently wins the entire
file, and the other mod's changes are gone with no warning. On a large modlist this adds up fast:
a survey of one real install found ~90 mods doing raw replacement, with over 2,000 files fought
over by two or more of them.

FileEmulationFramework already provides the mechanism to avoid this -- hook a specific procedure,
or override a specific message, instead of replacing the whole file -- but converting an existing
raw-replacement mod to that shape by hand is slow, and the runtime merge behavior has several
sharp edges that aren't documented anywhere (see `docs/FINDINGS.md`).

`ModConverter` automates the mechanical part of that conversion, `CpkFileExtract` supports the
manual part (writing a real hook for a file with genuine logic changes), and `scripts/` has the
decompiler-noise normalizer, cross-mod conflict auditor, and a few other tools that came out of
actually doing this at scale (~40 mods, several thousand files).

## What's here

| | |
|---|---|
| `ModConverter/` | The main tool. Point it at a mod, it converts every file it safely can and flags the rest for manual review instead of guessing. |
| `CpkFileExtract/` | Pulls one file out of a P5R CPK without unpacking the whole (~60GB) archive. Used to get a clean vanilla copy for manual hook-writing. |
| `scripts/` | Python: the decompiler-noise normalizer, cross-mod collision/conflict auditors, scripted hook generation, and a few other pieces. See `scripts/README.md`. |
| `docs/FINDINGS.md` | The distilled "read this first" writeup -- how the merge actually resolves conflicts, the merged-file cache, the decompiler-noise catalog, Reloaded-II gotchas. |
| `docs/REFERENCE.md` | The full sourced research doc underneath `FINDINGS.md` -- FileEmulationFramework + AtlusScriptCompiler mechanics from the ground up, plus corrections found by actually running the toolchain. |

## Prerequisites

- **[.NET 8 SDK](https://dotnet.microsoft.com/download)** -- to build `ModConverter` / `CpkFileExtract`.
- **[AtlusScriptCompiler](https://github.com/thealexbarney/AtlusScriptLib)** -- decompiles/compiles `.bf`/`.bmd`.
  A prebuilt copy with the P5R function library ships in most P5R modding toolchains; ShrineFox's
  [Atlus-Script-Tools](https://github.com/ShrineFox/Atlus-Script-Tools) release is a common source.
- **[PAKPack](https://github.com/tge-was-taken)** -- only needed if you're converting a mod that edits a
  message file living inside a PAK archive (e.g. `INIT/DATMSG.PAK`).
- **Python 3.10+** -- for everything in `scripts/`.
- A Reloaded-II install with
  [P5R Essentials / FileEmulationFramework](https://github.com/Sewer56/FileEmulationFramework)
  already set up, and a legitimate copy of the game to pull vanilla files from.

None of this bundles or redistributes the game's data or any third-party mod's content -- you
point these tools at your own install.

## Quick start

1. Build both tools:
   ```
   dotnet build ModConverter/ModConverter.csproj
   dotnet build CpkFileExtract/CpkFileExtract.csproj
   ```
2. Copy `ModConverter/p5rconverter.config.example.json` to `p5rconverter.config.json` next to the
   built `ModConverter.exe` (or anywhere, and pass `--config <path>`) and fill in your paths.
3. Convert a mod:
   ```
   ModConverter.exe <modId> [outputModId] [maxFilesForTesting]
   ```
   `modId` is the mod's folder name under your Reloaded-II `Mods/` directory. Output goes to
   `OutRoot/<outputModId>` (default `<modId>.mergeable`).
4. Read the summary and `_conversion_review_log.txt` in the output folder. Files that converted
   cleanly are done. Files flagged "needs review" have a real logic change ModConverter can't
   safely auto-convert -- see `docs/FINDINGS.md` and the hook-writing methodology below for how
   to write and verify a real hook for those.
5. Before enabling a large converted mod set together, run `scripts/final_collision_check.py` and
   `scripts/final_var_collision_check.py` against your Reloaded-II `Mods/` folder -- these catch
   the hard-failure class of conflict described in `docs/FINDINGS.md` section 1, which nothing
   else will warn you about until the game won't launch.

## Writing a hook by hand (for files `ModConverter` flags "needs review")

Short version -- see `docs/FINDINGS.md` and the scripts' own docstrings for the full detail on
*why* each step matters:

1. Get vanilla and the mod's decompiled `.flow` (ModConverter stages these under the output mod's
   `_review/` folder for every flagged file).
2. Diff them through `scripts/rescan_generic.py`'s normalizer first -- a large raw diff is very
   often decompiler noise (see `docs/FINDINGS.md` section 5), not a real change.
3. Extract the **entire** changed procedure body, not just the lines a diff shows changed -- a
   diff's context window silently truncates unchanged trailing calls.
4. Any new or changed message the procedure references goes in a companion `.msg`, named
   something other than the target's own base name (that exact name is reserved for the separate
   sibling-message convention).
5. Any script-level variable the procedure uses needs checking against `scripts/vanilla_svar_map.py`
   -- reusing vanilla's own number is required whenever an *unhooked* procedure in the same file
   also touches that variable, or the hook will silently read/write the wrong slot when reached
   through that other call path.
6. Test-compile with `-Hook` against a **freshly extracted true vanilla** copy (via
   `CpkFileExtract`, not a mod's own raw-fallback copy -- those can differ if the mod renamed a
   procedure internally, and a mismatch here fails silently, with no compile error). Confirm every
   intended procedure produced a `Registering X_hook as hook for Y` line, not just that the
   compile succeeded.
7. Decompile the compiled result back and confirm the original procedure is now just
   `__JUMP(<name>_hook);` with your logic intact under the new name.
8. Ship the `.flow` + `.msg` (without the vanilla import you added for testing), replace the raw
   fallback with a 0-byte dummy, and note what actually changed in the review log.

`scripts/generic_pipeline.py` automates steps 6-8 once you have a "plan" (procedure bodies +
message overrides + variable remapping) -- worth it if a mod's real changes are the same repeated
shape across many files; for one-off changes, doing it by hand per the steps above is usually
clearer.

## Credits

Built on top of [Sewer56](https://github.com/Sewer56)'s FileEmulationFramework and Reloaded-II,
[ShrineFox](https://github.com/ShrineFox)'s Atlus-Script-Tools packaging of AtlusScriptCompiler,
and TGE's PAKPack. None of that is included here -- go get it from those projects.

## License

MIT -- see `LICENSE`. This covers the tools and documentation in this repo only. It does not
grant any rights to, and isn't affiliated with, Persona 5 Royal, Atlus/Sega, or any third-party
mod referenced in the examples above.
