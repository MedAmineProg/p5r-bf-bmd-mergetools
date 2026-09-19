# ModConverter

Converts a raw whole-file-replacement P5R mod into FileEmulationFramework hooks and message
overrides.

## Usage

```
ModConverter.exe <modId> [outputModId] [maxFilesForTesting] [--config <path>]
```

- `modId` -- the mod's folder name under your Reloaded-II `Mods/` directory.
- `outputModId` -- optional, defaults to `<modId>.mergeable`.
- `maxFilesForTesting` -- optional, caps how many target files are processed (useful for a quick
  first pass on a huge mod before committing to a full run).
- `--config <path>` -- optional, points at a specific config file instead of the default search.

## Configuration

No paths are hardcoded. Config is resolved in this order:

1. `--config <path>` on the command line
2. `p5rconverter.config.json` in the current working directory
3. `p5rconverter.config.json` next to the built executable
4. Environment variables: `P5R_MODS_ROOT`, `P5R_OUT_ROOT`, `P5R_BASE_CPK`, `P5R_EN_CPK`,
   `P5R_COMPILER_EXE`, `P5R_PAKPACK_EXE`, `P5R_TEMP_ROOT`

Copy `p5rconverter.config.example.json` to `p5rconverter.config.json` and fill in the paths for
your machine -- see that file for what each key means. A key missing from every source above is a
fatal error naming exactly which key is missing, not a silent wrong default.

## What it does

- Auto-discovers the mod's `P5REssentials/CPK/*` container folder(s) (names are arbitrary per
  mod -- confirmed in the wild as `EN.CPK`, `BASE.CPK`, and plenty of made-up names).
- For every `.bf`/`.bmd` target: extracts true vanilla, decompiles both, diffs.
  - **No real difference** -> nothing to do, dummy the raw fallback.
  - **Message-only difference** -> emits a mergeable override (`FEmulator/BF/` for `.bf`,
    `FEmulator/BMD/` for loose `.bmd` -- see `docs/FINDINGS.md` for why this distinction matters)
    and a 0-byte raw-fallback dummy.
  - **Real logic difference** -> flagged "needs review" in `_conversion_review_log.txt`, decompiled
    vanilla/mod pair staged under `_review/` for someone to write a real hook (see the main
    README's methodology section), original content preserved on raw fallback in the meantime.
  - **Not found in either CPK** -> either a brand-new file the mod adds (nothing to diff against)
    or nested inside an archive -- see the PAK handling below. Preserved on raw fallback and logged.
- **PAK-nested `.bmd`** (message files living inside an archive like `INIT/DATMSG.PAK`): handles
  three shapes -- a whole modified `.PAK` shipped under `P5REssentials/CPK/`, a raw replacement
  entry under `FEmulator/PAK/<archive>/<name>.bmd`, and the "loose folder instead of `.PAK`"
  convention some mods use. Converts per-entry if every changed entry in the archive is a `.bmd`;
  leaves the whole archive on raw fallback (and logs why) if it also changed a non-`.bmd` entry.
- Carries the mod's existing `FEmulator/` folder and any non-`.bf`/`.bmd` assets under its CPK
  containers over verbatim, and rebuilds `ModConfig.json` from the original (dependencies, tags,
  etc. preserved; `ModDll`/`ModIcon` are currently left blank on the generated config -- if the
  source mod ships a functional plugin DLL, copy the DLL **and every sibling assembly it
  references** by hand, and verify the Reloaded-II mod-list UI still loads before shipping; see
  `docs/FINDINGS.md` section 6 for why a partial DLL copy can break the whole UI, not just that
  mod).

Nothing is ever silently dropped -- every file that isn't cleanly convertible ends up on raw
fallback (still works exactly as the original mod did, just not merged) and is named in one of the
two log files the tool writes alongside its output.
