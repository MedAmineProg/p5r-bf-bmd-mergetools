# How FileEmulationFramework BF/BMD merging actually works

Findings from converting ~40 raw-replacement Persona 5 Royal mods to FileEmulationFramework
hooks and running the results together, that either aren't documented anywhere else, contradict
the existing docs, or extend them significantly. Six sections, roughly in the order you'd hit
them.

## 1. The merge model

The common description of FileEmulationFramework's BF/BMD merging is "two mods touching the same
file, last loaded wins." That's true for exactly one case and misleading for every other.

**What actually happens:** when N mods each ship a `.flow` hook for the same target file, the
emulator doesn't pick a winner by load order for everything. It **textually combines every
contributing mod's procedures/declarations with vanilla's own compiled declarations into one
compilation unit, and compiles that.** Two different rules apply depending on what's colliding:

- **Redefining a name vanilla itself already declares as a procedure** (the standard hook
  mechanism -- renaming a vanilla procedure and providing a `<name>_hook`) is safe and IS
  overwrite-by-name: whichever mod loaded last wins that procedure outright, silently discarding
  any other mod's hook for it. This is the one case the "last wins" description is right about.
- **Any other top-level symbol** -- a `_hook`-suffixed procedure name (which doesn't exist in
  vanilla), or *any* `int sVarN;` / `float sfVarN;` script-level variable declaration, even one
  that merely duplicates a number vanilla itself also declares -- gets **zero** override handling,
  ever. A duplicate is a hard compile failure (`Cannot Create File From ...!` in the runtime log),
  regardless of whether the two declarations are content-identical, regardless of load order, and
  regardless of whether the "duplicate" is two mods or just one mod vs. vanilla's own baseline.

Two mods shipping a byte-identical `dungeon_start_format_hook` for the same file is still a
failure -- content identity is never a reason to skip deduping a shared hook name across mods,
only a reason it's *safe* to delete one copy without picking a side.

**Message-level (loose `.bmd`, or a `.bf`'s sibling `.msg`) same-name clash: the FIRST
(lowest-load-order) provider wins, not the last.** Proven by decompiling the actual merged
artifact (see section 2) rather than reasoning about it -- this is the opposite of what
"overwrite by name" implies, and it means a thin compat patch loaded *after* its constituents
cannot win a same-name clash just by loading later. (One measurement contradicted even this rule
and was never fully explained -- treat it as the dominant behavior, not an absolute guarantee.)

A `.flow`-adjacent companion `<name>_msg.msg` (the file a `.flow` actually `import()`s) beats any
plain sibling `<name>.msg` from another mod, regardless of load order. And a standalone
`<name>_msg.msg` shipped by a mod that does *not* also ship the matching `.flow` is routed as its
own bogus target and never joins the merge at all -- it just silently does nothing.

**The practical rule that actually works:** make every provider agree. Either apply your edit in
the file that owns the hook/companion, or delete the losing block from whichever mod supplies the
unwanted version, so the outcome no longer depends on load order at all. Every fix that held up
was done this way; every fix that relied on reasoning about precedence eventually broke.

## 2. The merged-file cache

Undocumented anywhere in the official sources. `p5rpc.modloader` (P5R Essentials) caches every
merged BF/BMD under `Mods/p5rpc.modloader/Cache/<AppId>/`, indexed by a `MergedFileCache.json`
that maps each target to a file under `Cache/<AppId>/Files/<hash>`.

**Invalidation is by source-file modification time, not content.** Two consequences:

- Editing a mod file with anything that preserves mtime (`cp -p`, Python's `shutil.copy2`,
  `shutil.copytree`, `rsync` without `--checksum`) means the edit is silently ignored and the
  stale merge keeps being served. Use a plain copy, or touch the mtime afterward.
- A pure load-order change (reordering mods in Reloaded-II) invalidates nothing. You can reorder,
  relaunch, and see zero difference in-game -- not because the reorder didn't matter, but because
  the cache never rebuilt.

To force a full rebuild: delete the `Cache/<AppId>/` folder (tens of GB, regenerates on next
boot -- expect a slower first launch after). Do this with the game **closed**; the CriFs hook
holds live handles into the cache directory while the game is running.

**The single most useful diagnostic technique in this whole project:** decompile the actual
merged artifact. `MergedFileCache.json` tells you exactly which file under `Files/` a given
target resolved to -- decompile *that* and read what literally came out, instead of reasoning
about which mod "should" have won.

## 3. File placement, and the hang this project spent its whole early history diagnosing

A loose `.bmd` message override **must** go under `FEmulator/BMD/`, never `FEmulator/BF/` -- the
BMD emulator only scans `FEmulator/BMD/`. Put it in the wrong folder and the override is silently
ignored, the 0-byte raw-fallback dummy gets served in its place, and the game's file-access layer
enters an **infinite retry loop** trying to resolve that file -- thousands of lookups, zero other
activity, until the process is eventually killed. No error, no exception, no crash log -- just a
hang, at whatever point in boot/gameplay that specific `.bmd` first gets requested. Only a
verbose file-access trace log makes this diagnosable at all.

Mirror the path below the CPK container (`FEmulator/BMD/EVENT_DATA/MESSAGE/E700/X.msg`) rather
than flattening -- files with the same basename exist in different directories in the real game
data, and a flat layout can silently collide.

PAK-nested BMD (a message file living inside an archive like `INIT/DATMSG.PAK`) needs a 0-byte
dummy at `FEmulator/PAK/<archive-path>/<name>.bmd` plus the override at
`FEmulator/BMD/<archive-path>/<name>.msg` -- the `ModConverter` tool in this repo automates
detecting and converting this shape.

## 4. CriFs redirects never reach the emulator

A natural (and wrong) assumption: a file injected via a CriFs CPK redirect -- the mechanism many
mods use for an "optional content" folder activated by their own DLL or in-app config toggle --
gets picked up as the base file, with any FileEmulationFramework hooks merging on top of it.

**It doesn't.** The BF/BMD emulator always rebuilds its target from true vanilla plus every
FileEmulationFramework contribution it can see, and then registers *its own* result into the
CriFs bind -- overwriting whatever the redirect had put there. Confirmed by decompiling the merged
artifact for a file a "cheat sheet"-style mod was supposed to be modifying via CriFs redirect: it
came out as plain, unmodified vanilla text.

Practical effect: any mod whose feature works by injecting a modified `.BF`/`.BMD` through a CriFs
redirect is silently doing nothing for that file, the moment *any* FileEmulationFramework mod also
touches it -- with no error and no indication anything is wrong. The fix is to extract whatever
that redirect was supposed to change and ship it as a real FileEmulationFramework override
instead. (Non-rebuilt file types -- PAK archives holding non-BF/BMD content, images, etc. -- are
unaffected; the emulator doesn't touch those, so a CriFs redirect for them works exactly as
expected.)

## 5. Decompiler-noise catalog

AtlusScriptCompiler makes semantically identical code look different across separate decompiles,
badly enough that a raw line-diff is not a reliable signal of how much actually changed. Every one
of the following has been confirmed, by hand, to represent literally zero behavioral difference:

- Every local (`varN`) and script-level (`sVarN`/`sfVarN`) variable is renumbered fresh on each
  decompile -- one added or removed statement anywhere earlier in a procedure cascades and
  reshuffles every later number, making an unnormalized diff nearly unreadable past trivial cases.
- `BIT_CHK((0x10000000 + 658))` and `BIT_CHK(3730)` are the same value, just shown in the
  unsimplified symbolic form (with a `// bit id (...) = ...` comment) vs. the pre-simplified
  literal, depending on how the specific binary being decompiled was originally built. Four
  presentational variants exist (decimal/hex category x decimal/hex offset) -- normalizing only
  the commented decimal form and missing the other three inflates a "real changes" count
  dramatically on any file with many bit-check calls.
- Bare integer literals: `-1` in one decompile can be `65535` in the other (same 16-bit pattern,
  signed vs. unsigned display). Bare hex can print with or without a leading zero (`0x0100` vs
  `0x100`).
- Float literals: `-0.00f` and `0.00f` are the same IEEE value with a sign bit the decompiler is
  inconsistent about printing.
- Goto-label suffix renumbering: a label can decompile as `_1098` in one version and
  `_1098_1401` (or with more chained suffix groups) in the other for the identical jump target --
  the trailing `_NNNN` groups are decompiler-internal bookkeeping, not part of the label identity.
- `[coop A B C]` and `[f 5 13 A B C]` are the same message tag rendered two ways.
- A dead `var = 0;` initialization immediately overwritten a line or two later can appear in only
  one of the two decompiles -- a genuinely no-op statement the decompiler emits inconsistently.
- A redundant `else { <if/else-if chain> }` and the flattened `else if <chain>` are semantically
  identical *whenever nothing else trails inside the wrapped scope* -- but NOT when something does
  trail (a statement only reachable inside the original `else` block becomes unconditionally
  reachable once flattened, which is a real behavioral change, not noise -- check case by case).

Two tooling notes that matter regardless of the noise catalog above:

- **`-Encoding P5R_EFIGS` is mandatory** when decompiling P5R content -- omitting it garbles
  special characters into output that looks like a real content difference but isn't.
- **Never run `AtlusScriptCompiler.exe` invocations in parallel.** A thread pool around plain
  `-Decompile` calls reported the vast majority of a multi-thousand-file batch as decompile
  failures; every one of them succeeded instantly when re-run alone, sequentially. The failures
  are silent and indistinguishable from genuine "can't decompile" results except by re-running
  solo -- always check a batch's failure count before trusting it, especially if it looks
  suspiciously high.
- Grepping message text for a phrase can miss real matches: `.msg` line breaks are stored as the
  literal token `[n]`, so "staring into space" is stored as `staring[n]into space` and a plain
  substring search for the full phrase finds nothing. Search a single word instead.

## 6. Reloaded-II operational gotchas

- Reloaded-II reflects over **every** mod's `ModDll` -- enabled or not -- while building the
  mod-list UI for an app. If that DLL references a sibling assembly that isn't present in the
  mod's own folder, the reflection call throws and **the entire app tab fails to load, showing no
  mods at all**, for every mod in the app, not just the broken one. If you copy a mod's DLL
  somewhere, copy its *entire* sibling DLL set, not just the one you think you need.
- Load order in the UI: a mod sorted **lower** in the visible list has **higher** priority. The
  raw array index in `AppConfig.json`'s `SortedMods` is not self-evidently the same thing as
  where an entry visually sits in the list -- verify which end you're looking at rather than
  assuming.
- `grep`-ing `AppConfig.json` for a mod ID to check whether it's active gives false positives:
  `SortedMods` and any saved `Presets` can contain an ID that isn't currently in `EnabledMods`.
  Check `EnabledMods` specifically.
