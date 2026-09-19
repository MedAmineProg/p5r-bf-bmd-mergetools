# BF / BMD Editing & Merging -- Reference

This is the research doc behind the tools in this repo. It's a combined, unabridged reference compiled from the community docs for FileEmulationFramework and AtlusScriptCompiler, plus a substantial "Source 21" section recording corrections found by actually running the toolchain against a real Steam P5R install -- several things the underlying doc sites say are outdated or wrong for the compiler build in current use.

For the higher-level findings (how the runtime merge actually resolves conflicts, the merged-file cache, decompiler-noise catalog, Reloaded-II operational gotchas), see FINDINGS.md in this same folder -- that's the distilled "read this first" version. This file is the full sourced reference underneath it.

---


Combined, unabridged reference compiled from twenty source pages/files, plus a 21st section recording a real hands-on verification pass against the actual toolchain and a live Steam P5R install, for use as context when working on BF/BMD script merging (e.g. feeding to Claude Code for a modding project).

**Sources:**
1. [P5R PC Essentials — Usage](https://sewer56.dev/p5rpc.modloader/usage/)
2. [BF [Atlus] — File Emulation Framework](https://sewer56.dev/FileEmulationFramework/emulators/bf.html)
3. [Intro to Scripting — ShrineFox Modding Docs](https://docs.shrinefox.com/flowscript/intro-to-scripting)
4. [BMD [Atlus] — File Emulation Framework](https://sewer56.dev/FileEmulationFramework/emulators/bmd.html)
5. [Routing — File Emulation Framework](https://sewer56.dev/FileEmulationFramework/routing.html)
6. [Reloaded-II — Creating Mods](https://reloaded-project.github.io/Reloaded-II/CreatingMods/)
7. [Reloaded-II — Adding Functionality (Example)](https://reloaded-project.github.io/Reloaded-II/AddingModFunctionality/)
8. [AtlusScriptCompiler — Overview & Run via Commandline](https://docs.shrinefox.com/flowscript/atlusscriptcompiler/run-via-commandline)
9. [AtlusScriptCompiler — Decompile](https://docs.shrinefox.com/flowscript/atlusscriptcompiler/run-via-commandline/decompile)
10. [AtlusScriptCompiler — Compile](https://docs.shrinefox.com/flowscript/atlusscriptcompiler/run-via-commandline/compile)
11. [AtlusScriptCompiler — Run via GUI](https://docs.shrinefox.com/flowscript/atlusscriptcompiler/run-via-gui)
12. [Messagescript — Markup](https://docs.shrinefox.com/flowscript/messagescript/markup)
13. [Persona 5 — Library Functions](https://docs.shrinefox.com/flowscript/library-functions/persona-5) (applies to P5R — confirmed P5R reuses the P5 function library)
14. [p5.flow](https://github.com/tge-was-taken/Atlus-Script-Tools/blob/539e25eec0eed909ca1e04b931157360cf8acd1b/Source/AtlusScriptCompiler/Resources/Include/p5.flow) — the complete raw function library from inside AtlusScriptCompiler itself (delivered as a separate companion file, `p5-library-functions.flow`)
15. [Flowscript — Procedures](https://docs.shrinefox.com/flowscript/flowscript/procedures) — core `.flow` syntax: procedures, statements, return types, parameters
16. [Flowscript — Variables](https://docs.shrinefox.com/flowscript/flowscript/variables-and-procedures) — declaring/initializing variables, data types
17. [Flowscript — Scope](https://docs.shrinefox.com/flowscript/flowscript/scope) — local/global/static/const/out variable scopes
18. [Flowscript — Importing Files](https://docs.shrinefox.com/flowscript/flowscript/importing) — the `import()` mechanism for chaining `.flow`/`.msg`/`.bf`/`.bmd` files, directly relevant to how hook scripts reference their base file
19. Remaining Flowscript/Messagescript pages (Arrays, Enums, Loops, Conditionals, Functions, Menus, Message Variables) — checked and confirmed to exist, but genuinely incomplete stubs on the doc site itself (see the dedicated section below for what each one does have)
20. [Persona 5 Royal (PC) Mod Support](https://docs.shrinefox.com/getting-started/persona-5-royal-pc-mod-support), [Extracting Files — Persona Modding](https://personamodding.com/p5r/getting-started/making-mods/extracting-files/), [CriFsV2Lib](https://github.com/Sewer56/CriFsV2Lib), and [CpkExtract](https://github.com/1330-Studios/CPK-Extract) — CPK unpacking and PAK/archive extraction tooling (CLI-first: CpkExtract + PackTools), the prerequisite step for getting a target file out of the game before decompiling it
21. Not an external page — a real, hands-on verification pass (2026-08-23) against the actually-downloaded toolchain and a live Steam P5R install, done specifically to catch places where Sources 1–20 were wrong, outdated, or an untested guess. See the dedicated section near the end of this document for the full corrections list.

Sources 4–5 were pulled in on a first follow-up pass (BMD's emulator-mechanics counterpart to BF, and the routing/file-resolution system underneath both). Sources 6–12 were pulled in on a second pass, specifically chasing the gaps identified after that: how to actually create the Reloaded mod and set a dependency (6–7), how to run AtlusScriptCompiler to decompile/compile `.bf`/`.bmd` files including the exact `-Library`/`-Encoding`/`-OutFormat` flags for Persona 5 Royal and the `-Hook` flag that the `_hook` naming convention (Source 2) actually relies on (8–11), and the `.msg` markup/color-tag syntax needed to actually write message edits (12).

> **Verification pass (2026-08-23):** every tool named below was actually downloaded, run, and exercised end-to-end against the real Steam P5R install (real `BASE.CPK`, a real decompiled Confidant gift-event script, a real PAKPack unpack) rather than trusted from prose alone. Several details the sources above stated as fact turned out to be wrong or outdated against the tool builds and CPK layout actually in use today, and a few explicitly-flagged "illustrative/unverified" items got confirmed or fixed. All corrections are marked inline where they apply, with a full summary in **Source 21** at the end of this document — read that section first if you're about to run a command copied from this doc.

---

## Worked Example: End-to-End BF Merge Walkthrough

Everything below is assembled from Sources 1–19 above — this section adds no new facts, it just stitches the pieces into one continuous walkthrough so the shape of the whole workflow is visible in one place. Each step names which Source it's drawn from so you can jump to the full detail.

**Scenario:** you want to edit an NPC's dialogue by hooking a procedure inside `f007.bf`, which lives inside the archive `field\pack\fd007_003.arc`. This mirrors the worked example already used in Source 2 and Source 1, carried all the way through instead of stopping at "and then follow the guide."

### 1. Create the Reloaded mod (Source 6)

In the Reloaded-II launcher, open Manage Mods → New, and give the mod a unique Mod Id (format `game.type.name`, e.g. `p5r.dialogue.f007tweak`). Fill in Name/Author/Version/Description in the Edit Mod menu, set the preview image, and check the box to support Persona 5 Royal in "Add Game Support to Mod."

### 2. Add P5R Essentials as a dependency (Source 1, Source 7)

Still in the Edit Mod menu, go to the dependencies section and add **Persona 5 Royal Essentials**. This is the same generic "add a dependency so the other mod always loads with yours" pattern Source 7 walks through with the File Redirector example — P5R Essentials bundles the BF/BMD/CPK/PAK emulators so you don't need to add those individually.

### 3. Get the original script's contents (Source 9, Source 20)

You need to know what's actually in `f007.bf` before you can write a correct hook — none of the merge mechanics work without this step, and it's easy to skip past by accident.

First, extract `f007.bf` from the game's files (Source 20): unpack `BASE.CPK`/`EN.CPK` with CpkExtract (CLI), locate `field\pack\fd007_003.arc` in the unpacked output, and extract it with PackTools' `PAKPack.exe unpack` (also CLI) to get the loose `f007.bf`. See the fully-scriptable command sequence under Source 20's "Updating the walkthrough's Step 3" for the exact commands.

> **Correction (Source 21):** `field\pack\fd007_003.arc` / `f007.bf` was never confirmed against a real CPK — it's Source 2's own doc example, carried through here unverified. A real scan of the current Steam build's `BASE.CPK` (44,934 files) found no such path. Real field/event `.bf` files in the current build are loose directly in the CPK (e.g. `EVENT_DATA/SCRIPT/E800/E800_002.BF`), not nested inside an `.arc` — treat this walkthrough's archive-nested framing as illustrative of the *mechanism* (Sources 1/2/5's archive-emulation rules are still accurate), not as a literal file that exists today.

Then decompile it:

```
"C:\Path\To\AtlusScriptCompiler.exe" "C:\Path\To\f007.bf" -Decompile -Library P5R -Encoding P5R_EFIGS -Out "C:\Path\To\f007.flow"
```

(Using `-Library P5R` here — Source 9's table lists it explicitly; Source 13 confirms P5R draws on the same function set as P5 regardless of which flag you use. **Correction (Source 21): use `-Encoding P5R_EFIGS`, not `-Encoding P5`** — the installed compiler ships a P5R-specific charset distinct from P5's, confirmed from a real shipped mod's `CompilerArgs.json`. Also note the actual compiler build tested takes `-Library` and `-Encoding` as separate tokens from their value, e.g. `-Library P5R`, not concatenated as `-LibraryP5R` — see Source 21.) Open the resulting `f007.flow` and find the procedure you want to change — say it's called `TalkNPC003()`.

### 4. Write the hook (Source 2, Source 10 "Hooking" section, Sources 15–18 for syntax)

Create a **new** `.flow` file — don't edit the decompiled one directly, and don't paste the whole decompiled script into it (Source 2's warning). Copy just the one procedure you're changing out of the decompiled file, paste it into your new file, and rename it with the `_hook` suffix:

```
// f007.flow  (your mod's hook file — NOT the decompiled original)
import( "messages.msg" );

void TalkNPC003_hook()
{
    // your edited logic goes here, using normal .flow syntax
    // (Source 15: procedures/statements, Source 16: variables, Source 17: scope)
    MSG_WND_DSP();
    MSG( newDialogueLine, 0 ); // newDialogueLine defined in messages.msg
    MSG_WND_CLS();
}
```

Per Source 10: compiling with `-Hook` redirects existing call sites for `TalkNPC003` to your `TalkNPC003_hook` replacement, while leaving the original procedure intact and still callable by name if you need to fall back to it. Per Source 2: this `_hook` suffix convention is exactly what FileEmulationFramework's BF emulator looks for at runtime — you don't actually run the compiler yourself for the mod; the emulator does the decompile/hook/recompile dance live when the game loads the file. The manual CLI walkthrough in step 3 and this step is how you *read* the original and *validate* your hook syntax before trusting it to the emulator, not how you ship it.

If your NPC also needs a brand-new procedure at a specific call-site index (e.g. a new interactable), name it `whatever_index_21` per Source 2's Forced Procedure Indices section, so other mods hooking the same file can't accidentally shift it.

### 5. Place the hook file where the emulator will find it (Source 2, Source 5)

In your mod folder:

```
FEmulator/BF/f007.flow
```

The filename must match the target `.bf`'s name (`f007.flow` for `f007.bf`) — per Source 5 (Routing), the folder name under `FEmulator/<Type>/` is what the emulator matches against the base file's route.

### 6. Add the dummy file so P5R Essentials' redirection recognizes the target (Source 1)

Since `f007.bf` lives inside an archive (not loose), create an empty text file, rename its extension to `.bf`, and place it at:

```
P5REssentials/CPK/<the CPK containing fd007_003.arc>/field/pack/fd007_003.arc/f007.bf
```

(Adjust the path to match exactly where `fd007_003.arc` actually sits inside the game's CPK structure — Source 1's own BF example follows this same "mirror the archive path" pattern for `f007.bf` in `field\pack\fd007_003.arc` via `FEmulator\PAK\field\pack\fd007_003.arc`, per Source 5's file-resolution rules on archive-relative matching.)

### 7. (Optional) Add just a message edit instead of a full procedure hook (Source 2 "Message Hooking", Source 12)

If all you actually want is to change dialogue text without touching logic, skip steps 3–4's procedure copy and instead make `FEmulator/BF/f007.msg` containing only the edited message, with the **exact same name** as the original message entry (or it'll be added as a new message instead of overwriting):

```
[dlg TalkNPC003Line1]
[clr 18]Persona[clr 0] users are pretty rare, you know.[e]
```

(`[clr 18]`/`[clr 0]` is the Pink/reset-to-White color tag pair from Source 12's markup table.)

### 8. Same pattern for BMD-only targets (Source 4)

If your target is a standalone `.bmd` (not embedded in a `.bf`), the whole shape repeats with the BMD emulator instead: dependency string `reloaded.universal.fileemulationframework.bmd`, files go in `FEmulator/BMD/<name>.msg` instead of `FEmulator/BF/`, same exact-name-to-overwrite rule, same dummy-file-mirrors-original-path placement rule (Source 1's BMD examples, Source 5's routing). BMD has no equivalent to forced indices or Functions.json/Enums.json overrides — those are BF-only, per Source 4's own notes.

### 9. Set the mod version and finish up (Source 6, Source 1's "Releasing/Uploading")

Bump the Version field using semantic versioning (Source 6), and when ready to share, follow Source 1's pointer to Reloaded's Enabling Update Support / Creating a Release guidance.

### What this walkthrough deliberately leaves out

- Any actual game logic beyond `MSG`/`MSG_WND_DSP`/`MSG_WND_CLS` calls — per Source 19, `.flow`'s array/loop/conditional syntax isn't documented on the source site, so anything needing branching logic will need real decompiled examples as a syntax reference rather than more doc pages.
- Testing/debugging the mod in-game — none of the 20 sources cover this; you'd be relying on the game's own crash/log behavior and trial and error.

(Archive extraction — the third gap from the earlier version of this list — is now covered by Source 20 and folded into Step 3 above.)

---

## Source 1: P5R PC Essentials — Usage

### Prerequisites

**Create a Reloaded Mod**

Follow the guidance in the Reloaded wiki to create a new Reloaded mod.

**Download Mod**

> Note: This image needs updated.

If you don't have it already, download the Persona 5 Royal Essentials Mod.

**Set Dependency on P5R Essentials**

In the Edit Mod menu (right click your mod in mods list) we're going to add Persona 5 Royal Essentials as a dependency.

Adding a 'dependency' to your mod will make it such that P5R Essentials will always be loaded when your mod is loaded. This is a necessary step.

### Replacing files in CPKs

> Info: Files inside CPKs can be replaced by creating a folder called `P5REssentials/CPK` in your mod, and adding folders corresponding to the names of the CPKs inside those folders.

**Opening the Mod Folder**

Go to the folder where your mod is stored, this can be done by simply clicking the Open Folder button.

**Add Some Files**

Make a folder called `P5REssentials`, and inside that a folder called `CPK`.
Inside that folder, make a folder [or multiple!] where you will store your mod files (you can call it anything you want!).

I used `EN.CPK` for clarity to match the game's structure.

We will replace these two files to enable different button prompts 😇.

The contents of our mod folder would now look as follows.

```
// Mod Contents
ModConfig.json
Preview.png
P5REssentials
└─CPK
  └─EN.CPK
    └─BUTTON
      ├─BUTTON_XBOX.PAK
      └─BUTTONXBOXTEXINFO.DAT
```

The connectors `└─` represent folders.

### Replacing Music

> Info: Essentials can be used to replace audio inside AWB & ACB pairs.

Uses FileRedirectionFramework under the hood, follow instructions here for more information.
Don't add dependency on AWB emulator (it's not necessary), but do follow rest of guide.

**Example**

As per usage guide above.
This works the same as it does in Persona 4 Golden 64-bit/2023 version.

Replaces 53rd audio track (Signs of Love).

> Warning: Encryption keys/scheme on the ADX/hca audio must match original file.
> [Can someone please link Amicitia or other relevant wiki here??]

### Replacing Files In Archives

> Info: Essentials can be used to replace individual files in archives such as PAK, BIN, PAC, and ARC

Uses FileRedirectionFramework under the hood, follow instructions here for more information.
Don't add dependency on PAK emulator (it's not necessary), but do follow rest of guide.

**Example**

As per usage guide above.
Replaces `battle/MSG.TBL` in `init_free.bin`.

### Editing BF Files

> Info: Essentials can be used to edit the procedures and messages in BF files such that multiple mods can edit the same file.

Uses FileRedirectionFramework under the hood, follow instructions here for more information.
Don't add dependency on BF emulator (it's not necessary), but do follow rest of guide.

In addition to the `.flow` and/or `.msg` files you include in `FEmulator\BF` per the above guide you will also need to add dummy bf files where they would normally go in `FEmulator\PAK` or `P5REssentials\CPK`.

**Example - Loose BF**

> Info: To create a dummy bf file you can create a new empty text file and just rename it, changing the file extension.

To edit the loose `e860_034a.bf` file in `event_data\script` you would first add a dummy bf file in `P5REssentials\CPK\data_e.cpk\event_data\script`

Then you would put your `.flow` or `.msg` file with the same name in `FEmulator\BF`

**Example - BF In Archive**

To edit `f007.bf` in the archive `field\pack\fd007_003.arc` you would first add a dummy bf file in `FEmulator\PAK\field\pack\fd007_003.arc` (as per the information above)

Then you would put your `.flow` or `.msg` file with the same name in `FEmulator\BF`

### Editing BMD Files

> Info: Essentials can be used to edit messages in BMD files such that multiple mods can edit the same file.

Uses FileRedirectionFramework under the hood, follow instructions here for more information.
Don't add dependency on BMD emulator (it's not necessary), but do follow rest of guide.

In addition to the `.msg` files you include in `FEmulator\BMD` per the above guide you will also need to add dummy bmd files where they would normally go in `FEmulator\PAK` or `P5REssentials\CPK`.

**Example - Loose BMD**

> Info: To create a dummy bmd file you can create a new empty text file and just rename it, changing the file extension.

To edit the loose `e722_103.bmd` file in `event_data\message` you would first add a dummy bmd file in `P5REssentials\CPK\en.cpk\event_data\message`

Then you would put your `.msg` file with the same name in `FEmulator\BMD`

**Example - BMD In Archives**

To edit `datSkillHelp.bmd` in the archive `init\datmsg.pak` you would first add a dummy bmd file in `FEmulator\PAK\init\datmsg.pak` (as per the information above)

Then you would put your `.msg` file with the same name in `FEmulator\BMD`

### Editing TBL Files

Any TBL files in P3P, P4G and P5R (such as `SKILL.TBL` and `UNIT.TBL`) will automatically be merged if multiple mods edit them. This includes `itemtbl.bin` in P4G and P3P.

> Info: Note that some TBLS that vary drastically between languages (such as `NAME.TBL` in P5R) will be ignored if the player's game language is not set to English, unless a localized version for their game language is available (see supporting multiple languages).

**Embedded BF in AICALC.TBL**

In P3P and P4G `AICALC.TBL` contains two embedded bf files, `friend.bf` and `enemy.bf`. To edit these place a dummy bf with the same name in `FEmulator\PAK\init_free.bin\battle` and then hook anything you want to the same way you would any other bf file.

**Embedded BMD in MSG.TBL**

In P3P and P4G `MSG.TBL` contains an embedded bmd file, `msgtbl.bmd`. To edit it, place a dummy bmd with the same name in `FEmulator\PAK\init_free.bin\battle` and then hook anything you want the same way you would any other bmd file.

### Editing SPD Files

> Info: Essentials can be used to edit textures and sprites in SPD files such that multiple mods can edit sprites in the same texture.

Uses FileRedirectionFramework under the hood, follow instructions here for more information.
Don't add dependency on SPD emulator (it's not necessary), but do follow rest of guide.

In addition to the sprite entry files (`.spdspr`/`.sprt`) and/or textures (`.dds`/`.tmx`) files you include in `FEmulator\SPD` per the above guide you may need to add dummy spd files where they would normally go in `FEmulator\PAK` (only if the spd you're editing is located in an archive).

**Example - Loose SPD**

To edit the loose `CHAT.SPD` file in `FONT\CHAT` you would first create a directory mimicking the path of the spd in `FEmulator\SPD`, including the spds filename.

Then you would put your sprite entry and/or texture files in `FEmulator\SPD\FONT\CHAT\CHAT.SPD\`

**Example - SPD in archive**

> Info: To create a dummy spd file you can create a new empty text file and just rename it, changing the file extension.

To edit `higawari_common.spd` in the archive `CALENDAR\HIGAWARI.PAK` you would first add a dummy spd file in `FEmulator\PAK\CALENDAR\HIGAWARI.PAK` (as per the information above)

Then follow the steps for loose spds.

### Supporting Multiple Languages

Persona Essentials has integration with Localisation Framework to help you make your mods support multiple languages. By adding files as described in its documentation you can have different versions of any type of file for each language. The framework will automatically determine what language the user is playing in and use the correct ones.

**Example - BMD**

Say you have edited the BMD file `E722_103.bmd` in `EVENT_DATA\MESSAGE` as described in Example - Loose BMD and want it to work in Japanese. As per that section, you will have a msg file at `FEmulator\BMD\E722_013.msg` with your English messages.

To support Japanese you would place a corresponding msg file with Japanese text at `FEmulator\L10N\ja\E722_013.msg`.

To support more languages you would add more copies of that file in the folder `FEmulator\L10N\{langCode}` where `{langCode}` is the id of the language listed in the Localisation Framework documentation.

**Example - TBL**

Some TBLS that differ heavily between languages must be localized for changes to appear when playing in a language other than English. To do this you would first place an English-language TBL in the appropriate essentials subfolder (eg. `P5REssentials/CPK/folderName/BATTLE/TABLE/NAME.TBL` for name.tbl in P5R).

Then, to support eg. Spanish you would place a Spanish-language TBL at `FEmulator/L10N/es/NAME.TBL`.

### Releasing/Uploading your Mods

Please refer to the Reloaded wiki, and follow the guidance.

You should both Enable Update Support AND Publish according to the guidelines.

It is recommended to enable update support even if you don't plan to ship updates as doing so will allow your mod to be used in Mod Packs.

---

## Source 2: BF [Atlus] — File Emulation Framework

> Info: BF is a script file used by Atlus, for more information on the format check out ShrineFox's intro to scripting.
>
> Code for this emulator lives inside main project's GitHub repository.

### Supported Applications

A number of Atlus games such as Persona, SMT, and Catherine use BF files. Any that Atlus Script Compiler has libraries for should work, however, this has only been tested with:

- Persona 3 Portable (PC)
- Persona 4 Golden (PC)
- Persona 5 Royal (PC)

For games other than these, script compiler arguments need to be supplied as detailed in Custom Script Compiler Args.

### Example Usage

As this mod is primarily intended for use with the PC Persona games, it is recommended that you use Persona Essentials which has this as a dependency. However, the steps for using it on its own are very similar to with Persona Essentials:

**A.** Add a dependency on this mod in your mod configuration. (via Edit Mod menu dependencies section, or in ModConfig.json directly)

```
"ModDependencies": ["reloaded.universal.fileemulationframework.bf"]
```

**B.** Add a folder called `FEmulator/BF` in your mod folder.

**C.** Make a `.flow` file with the same name as the bf you want to edit, e.g. `f007.flow` to edit `f007.bf` (this can be in subfolders as per Routing).

**D.** In the `.flow` file include any new procedures and hooks of existing procedures from the base `.bf` file

> **Warning:** Only include new procedures and hooked procedures, do not copy and paste the entire decompiled bf into your flow.
>
> To hook a procedure add `_hook` to the end of the name of the original (e.g. to hook `init` make a procedure called `init_hook`)

### Message Hooking

If you just want to change existing messages inside of a bf you can do so using message hooking which works very similarly to regular flowscript merging.

To do so:

**A.** Follow steps A and B from above.

**B.** Make a `.msg` file with the same name as the bf you want to edit, e.g. `f007.msg` to edit messages in `f007.bf`

**C.** In the `.msg` file include any messages that you want to edit from the base `.bf` file.

> **Warning:** Only include edited messages, do not copy and paste the entire decompiled msg file into your new msg.
>
> The edited messages must have exactly the same names as the originals otherwise they will not be overwritten and instead will be added.

Note that you can also hook messages in flow files by having messages with the same name as original ones in any imported `.msg` files. Normally script compiler would ignore duplicate named messages, however, the version in BF Emulator has been modified to instead overwrite them.

### Forced Procedure Indices

In some cases you will need to add new procedures to a bf which are at a specific index, such as when adding new interactable NPCs. In this case you can force a specific index by adding `_index_x` to the end of the procedure's name.

For example, if you have a new NPC that calls procedure 21, in your `.flow` file should have a procedure with a name like `npc_thing_index_21` to ensure your new procedure is always at index 21 (the stuff before `_index_21` is completely arbitrary).

> Info: This is necessary as other mods hooking functions in the same bf could potentially change the index of your procedures if they are not forced.

### Script Compiler Library Overrides

In some cases you will want to utilise custom flowscript functions provided either by your mod or a dependency. In these cases you can use library overrides to replace the information about existing (generally unused) functions with your custom ones.

To do so:

**A.** Create a file named `Functions.json` in your `FEmulator/BF` folder.

**B.** Inside of `Functions.json` copy the information of the changed functions into the file inside of a json array.

For example, to use the P3P Movie Player mod's `CUSTOM_MOVIE_PLAY` function you would have the following in `Functions.json`:

```json
[
  {
    "Index": "0x0004",
    "ReturnType": "void",
    "Name": "CUSTOM_MOVIE_PLAY",
    "Description": "Custom function that plays a usm based on its id. This REQUIRES the Movie Player mod to work!",
    "Parameters": [
      {
        "Type": "int",
        "Name": "CutsceneId",
        "Description": "The id of the usm to play, the usm should be in \\data\\sound\\usm and be called CutsceneId.usm (e.g. 21.usm for id 21)"
      }
    ]
  }
]
```

Where that information was copied directly from the mod's readme.

> **Warning:** Do not change the information of functions that are not unused (such as changing the name of undocumented functions). If any other mod hooks the same bf and uses those functions they will be unable to compile.
>
> If you have documented previously unknown functions you should make a pull request with these changes to the main Atlus-Script-Tools repository, this can then be merged into BF Emulator at a later time.

This can also be done with custom enums by adding an `Enums.json` file into `FEmulator/BF` and adding the information in a similar manner. For example:

```json
[
  {
    "Name": "Cutscene",
    "Description": "This enum represents different movies added by cutscenes restored",
    "Members": [
      {
        "Name": "First",
        "Value": 1,
        "Description": ""
      }
    ]
  }
]
```

This enum can then be used in your code like: `CUSTOM_MOVIE_PLAY( Cutscene.First );`

### Custom Script Compiler Args

> Info: If you are doing this to use BF Emulator with an unsupported game you could instead make a pull request, adding automatic support for it by adding to the constructor in `BfEmulator.cs`.

If you want to use BF Emulator on a game that is not automatically supported you will need to supply Atlus Script Compiler with the correct arguments to compile the bf for it.

To do so:

**A.** Create a file named `CompilerArgs.json` in your `FEmulator/BF` folder.

**B.** Inside of `CompilerArgs.json` use the following template with the appropriate arguments (which can usually be found in the Script Compiler GUI repo):

```json
{
  "Library": "P3P",
  "Encoding": "P3",
  "OutFormat": "V1"
}
```

---

## Source 3: Intro to Scripting — ShrineFox Modding Docs

> For the complete documentation index, see llms.txt. This page is also available as Markdown.

### What the hey is all this?

Persona games feature their own built-in scripting engine. With a basic understanding of coding, you can build completely custom experiences into your mod. This is a chance for your creativity to shine as you work with the limited (yet robust) tools that the game provides us.

You do NOT have to have any prior knowledge of programming to follow this tutorial. However, it's recommended to watch at least the first 3 videos from Harvard's CS50 playlist. A lot of the same concepts apply here, and these videos lay them all out for you in an easy-to-digest fashion.

### So, what is Scripting?

Scripting is the act of writing a script.

Scripts are text files containing human-readable code. These instructions are meant to be interpreted by another program, rather than your computer's processor.

A program for interpreting scripts is called a **compiler**.

Compiling is the act of converting human-readable code to machine language.

A **Binary** is what we call the output, usually a single game file.

Atlus games use scripts to perform various logical procedures:

- Giving the player items, skills, or money
- Showing message windows or choosing options in a menu
- Playing sound effects or loading fields/events/battles
- etc. etc. etc. ...

The compiled binary is unreadable to humans, but the game can understand it perfectly.

Scripts found in the game have already been compiled. Normally, we wouldn't be able to do much with these files, since they only exist as binaries.

But thanks to clever reverse engineering, we have TGE's **AtlusScriptCompiler**. This program can:

- Decompile `.BF` to `.FLOW` and `.BMD` to `.MSG`
- Compile `.FLOW` to `.BF` and `.MSG` to `.BMD`

### What is Flowscript?

To answer that, let's go over these proprietary Atlus binary formats.

**BF (binary flow)** — The compiled form of Atlus's scripts.

**BMD (binary message data)** — Another binary format often found embedded within `.BF` files. These contain text and markup.

**.FLOW and .MSG**

AtlusScriptCompiler supports two unique script formats.

- **Flowscript (`.FLOW`)** — A human-readable scripting language designed by TGE. It mimics the original script format `.BF` files were created from.
- **Messagescript (`.MSG`)** — TGE's answer to `.BMD` as a script format. It contains text with markup that can be linked to a `.FLOW` script.

Altogether, this makes it possible to edit and create `.BF` and `.BMD` files.

### What does .FLOW look like?

Flowscript (`.FLOW`) looks similar to C, so anyone familiar with object-oriented programming should feel right at home.

The following is an example of a simple menu in Persona 5:

```
// Import the MessageScript into the script
import( "TestScript2.msg" );

// Main Script Procedure
void Main()
{
    // Display dialog window (by message name)
    MSG_WND_DSP();

    // Display dialog (by message name)
    MSG( HelloDialog, 0 );

    // Display selection menu (by message index)
    int selection = SEL( 1 );

    // Close dialog window
    MSG_WND_CLS();

    // Do whatever you selected
    switch ( selection )
    {
        case 0:
            // Get Player Resource Handle
            int playerResHandle = FLD_PC_GET_RESHND( 0 );
            // Change Player Model Size
            FLD_MODEL_SET_SCALE( playerResHandle, 2f );
            break;
        case 1:
            // Go to Field 000_002
            CALL_FIELD( 0, 2, 0, 0 );
            break;
        default:
            break;
    }
}
```

### What does .MSG look like?

Messagescript is even more straightforward. See below for an idea of how dialog and selections are labelled and formatted.

```
// Index 0
[dlg BossRushModeDialog [TGE]]
[f 2 1]Select a boss fight.[f 1 1][e]

// Index 1
[sel SelectBoss0]
[f 2 1]D00_SCENARIO_BATTLE_01[e]
[f 2 1]D01_01_SCENARIO_BATTLE_01[e]
[f 2 1]D01_01_MORUGANA_BATTLE[e]
[f 2 1]D01_02_SCENARIO_BATTLE_01[e]
[f 2 1]Previous[e]
[f 2 1]Next[e]
```

### Getting Started

To make full use of this guide, you will need:

- A PC running Windows
- Extracted files from the game you're modding
- An open mind :)

Read on for how to get started with the program.

---

## Source 4: BMD [Atlus] — File Emulation Framework

> Info: BMD is a script file used by Atlus, for more information on the format check out ShrineFox's intro to scripting.
>
> Code for this emulator lives inside main project's GitHub repository.

### Supported Applications

A number of Atlus games such as Persona, SMT, and Catherine use BMD files. Any that Atlus Script Compiler has libraries for should work, however, this has only been tested with:

- Persona 3 Portable (PC)
- Persona 4 Golden (PC)
- Persona 5 Royal (PC)

For games other than these, script compiler arguments need to be supplied as detailed in Custom Script Compiler Args.

### Example Usage

As this mod is primarily intended for use with the PC Persona games, it is recommended that you use Persona Essentials which has this as a dependency. However, the steps for using it on its own are very similar to with Persona Essentials:

**A.** Add a dependency on this mod in your mod configuration. (via Edit Mod menu dependencies section, or in ModConfig.json directly)

```
"ModDependencies": ["reloaded.universal.fileemulationframework.bmd"]
```

**B.** Add a folder called `FEmulator/BMD` in your mod folder.

**C.** Make a `.msg` file with the same name as the bmd you want to edit, e.g. `e722_103.msg` to edit messages in `e722_103.bmd`

**D.** In the `.msg` file include any messages that you want to edit from the base `.bmd` file.

> **Warning:** Only include edited messages, do not copy and paste the entire decompiled msg file into your new msg.
>
> The edited messages must have exactly the same names as the originals otherwise they will not be overwritten and instead will be added.

Normally script compiler would ignore duplicate named messages, however, the version in BMD Emulator has been modified to instead overwrite them.

### Custom Script Compiler Args

> **Todo (from source page):** The link in the below is copy-pasted from bf.md and is not correct.
>
> Info: If you are doing this to use BMD Emulator with an unsupported game you could instead make a pull request, adding automatic support for it by adding to the constructor in `BfEmulator.cs`.

If you want to use BMD Emulator on a game that is not automatically supported you will need to supply Atlus Script Compiler with the correct arguments to compile the bmd for it.

To do so:

**A.** Create a file named `CompilerArgs.json` in your `FEmulator/BMD` folder.

**B.** Inside of `CompilerArgs.json` use the following template with the appropriate arguments (which can usually be found in the Script Compiler GUI repo):

```json
{
  "Library": "P3P",
  "Encoding": "P3",
  "OutFormat": "V1"
}
```

**Note:** unlike the BF emulator page, the BMD emulator page does *not* document Forced Procedure Indices or Script Compiler Library Overrides (`Functions.json`/`Enums.json`) — those appear to be BF-specific concepts (procedures/indices are a flowscript concern, not a plain message-data concern), and the source page has no equivalent sections for BMD.

---

## Source 5: Routing — File Emulation Framework

> Info: This page describes the basics of how files on disk are used to modify existing files through the use of 'emulators'.

When virtual/emulated files are being built, the library keeps track of a **Route**.

This 'route' is a combination of the base file, and the name of each recursive internal file(s):
- Base file uses full path, e.g. `<GameFolder>/English/Sound.afs`.
- Internal files are delimited by the `/` character.

e.g. File `00000.adx` in `<GameFolder>/English/Sound.afs` would make the full path `<GameFolder>/English/Sound.afs/00000.adx`.

This route is passed onto the individual emulators to work with.

### File Resolution

> Info: Describes how files in user mods are matched to the file to be modified.

Each emulator will have its own folder under the `FEmulator` folder inside user made mods, so the emulator for CRIWARE `.AFS` would use `FEmulator/AFS`.

Folder names are used for resolving what files should be modified by each 'emulator'; with the folder name corresponding to the file to modify and the contents of the folder being the input to the 'emulator'.

In the case of 'archive emulators' like the AFS ones, placing files inside can be used to override existing files inside the source `.afs` file.

Folder `Sound.afs/00000.adx` in `FEmulator/AFS` will override files named `00000.adx` in all `Sound.afs` loaded.

Additional folders can be used to specify the file to be overwritten more precisely. This can be useful when multiple files of the same name exist.

For example, `English/Sound.afs/00000.adx` in `FEmulator/AFS`:
- Will match `<GameFolder>/English/Sound.afs`
- Will not match `<GameFolder>/Japanese/Sound.afs`

Comparisons performed are case insensitive. Partial matches e.g. `nglish/Sound.afs` are allowed, but are discouraged from use.

### Recursive Resolution

> Info: Emulators work recursively. Meaning you can emulate a file inside an emulated file.

In the case of archives, suppose you have `textures.one` and inside that `textures.txd`.

You can inject into `textures.txd` by doing the following:
- Add `FEmulator/ONE/textures.one/textures.txd` — inject unmodified `textures.txd` into `textures.one`.
- Add `FEmulator/TXD/textures.txd/texture_001.dds` — inject `texture_001` into `textures.txd`.

### File Usage

The File Resolution section used the 'AFS Redirector' as an example of inserting/replacing files into an archive by using existing files.

The contents of the folder corresponding to the emulated file are open to the emulator's interpretation.

For example, for an ADX (sound file) emulator, `Musictrack.adx/settings.json` could be a valid file; and the emulator use `settings.json` to perform post processing the file such as sound normalization or concatenating music tracks.

Equally well, for archives which use compression for internal files, having pre-compressed files is also valid.

---

## Source 6: Reloaded-II — Creating Mods

URL: https://reloaded-project.github.io/Reloaded-II/CreatingMods/

> Note: This section is for non-programmers wishing to create mods which take advantage of existing mods/plugins (such as file redirection). If you intend on programming with Reloaded, please see Programmers' Getting Started instead.

### Create A Configuration File

The first step towards creating a mod is to make a configuration file. This can be simply done by entering the Manage Mods (3 gears) menu and clicking the New button.

For the Mod Id you should enter a name that is unique to your mod.

The format `game.type.name` is suggested, for example `sonicheroes.asset.seasidehillmidnight`.

This name should be human readable.

> **Gap filled (Source 21):** this page (and Source 7) only ever describes the GUI flow — neither shows the actual `ModConfig.json` schema, which matters for a CLI-only/no-GUI workflow where you're hand-writing the file instead of clicking through "New". Verified against a real, currently-installed, working P5R BF-editing mod (`p5r.scripts.restoredoutfitsdialogue`) rather than guessed:
>
> ```json
> {
>   "ModId": "p5r.dialogue.mytweak",
>   "ModName": "My Tweak",
>   "ModAuthor": "",
>   "ModVersion": "1.0.0",
>   "ModDescription": "Short description of what this mod does.",
>   "ModDll": "",
>   "ModIcon": "",
>   "ModR2RManagedDll32": "",
>   "ModR2RManagedDll64": "",
>   "ModNativeDll32": "",
>   "ModNativeDll64": "",
>   "Tags": [],
>   "CanUnload": null,
>   "HasExports": null,
>   "IsLibrary": false,
>   "IsUniversalMod": false,
>   "ModDependencies": [
>     "p5rpc.modloader"
>   ],
>   "OptionalDependencies": [],
>   "SupportedAppId": [
>     "p5r.exe"
>   ]
> }
> ```
>
> Notes from the real example:
> - `"p5rpc.modloader"` is P5R Essentials' actual Mod Id — this is what Source 1's "add Persona 5 Royal Essentials as a dependency" instruction resolves to in `ModDependencies`. Per Source 1's own advice, you generally don't need to *also* list `reloaded.universal.fileemulationframework.bf`/`.bmd` separately — Essentials already depends on them — though the real example mod does list the BF emulator explicitly as well (redundant but harmless).
> - `"SupportedAppId": ["p5r.exe"]` is what "check the box to support Persona 5 Royal in 'Add Game Support to Mod'" (Source 6's own later section) resolves to as raw JSON.
> - The real example mod also carries a large auto-generated `PluginData.GitHubDependencies` block and a `ReleaseMetadataFileName` field — these are populated by Reloaded-II's package manager when you add dependencies through the GUI's update-checking flow. They are **not required** for the mod to load; a hand-written `ModConfig.json` without them loads fine, since the loader resolves dependencies by `ModId` against the `Mods` folder, not through that metadata.
> - The mod folder must live inside (or be symlinked into) Reloaded-II's configured `ModConfigDirectory` (check `ReloadedII.json` in the Reloaded-II Mod Loader's AppData folder for the exact path on a given machine) for the launcher to actually discover and load it — a `ModConfig.json` sitting in an arbitrary folder elsewhere won't show up on its own.

### Edit the Mod Configuration

> Note: You can access this menu in the future by selecting the mod and clicking Edit in the Manage Mods menu, or by right clicking the mod in any game's mod list.

**Main Mod Details**

Set the following mod properties:
- **Name:** The name of the mod as seen in the launcher.
- **Author:** The name of the author(s) of the mod.
- **Version:** The version of the mod.
- **Description:** Short summary of the mod.

For the Version field, Reloaded uses Semantic Versioning.

In simple terms, use the `X.Y.Z` format for your versions and increment:
- `X` when you make big/breaking changes that fundamentally change your mod (example: major game rebalance).
- `Y` when you add new features without breaking existing functionality (example: add stage to stage pack).
- `Z` when you add new bug fixes (example: fixed bad texture).

**Update the Preview Image**

To set the preview image, click on the image above the Name field.

Although any resolution is accepted, it is recommended that your preview image is 256x256 in size (or a multiple like 512x512). This is the size it will be displayed at to most users.

**Add Game Support to Mod**

Select the game(s) you wish to support from the dropdown menu. This will make it so that your mod will be visible in that specific game's mod list.

### Summary

By the end of this guide, you should have a newly created mod, which will be visible in your game's mods list.

Next: Adding Mod Functionality (see Source 7 below).

---

## Source 7: Reloaded-II — Adding Functionality (Example)

URL: https://reloaded-project.github.io/Reloaded-II/AddingModFunctionality/

> Info: The following guide will walk you through adding functionality to your (non-code) mod through the use of other mods.

In this guide the Reloaded File Redirector Mod is used as the example — this is the same dependency-plus-folder pattern that P5R Essentials, the BF Emulator, and the BMD Emulator all follow.

### Download the Mod

First, download the mod which will extend the functionality of your mod. In this case, the Reloaded File Redirector.

### Add Dependency to Other Mod

In the Edit Mod menu, add Reloaded File Redirector as a dependency.

Adding a 'dependency' to your mod will make it such that the other mod will always be loaded when your mod is loaded. This is a necessary step.

### Following the Guide

Mods such as File Redirector will typically include guides on using them, which can typically be found on their download page.

Steps A (adding the dependency) is done; the rest of the guide follows:

**Opening the Mod Folder** — go to the folder where your mod is stored (Open Folder button).

**Add Some Files** — make a folder called `Redirector`. Inside it, place the files that you want to be replaced.

The contents of the example mod folder:

```
// Mod Contents
ModConfig.json
Preview.png
Redirector
└─dvdroot
  ├─advertise
  │ adv_pl_rouge.one
  └─playmodel
    ro.txd
    ro_dff.one
```

The connectors `└─` represent folders.

### Summary

That's all — this is the generic template that the game-specific/file-type-specific Essentials guides (Sources 1, 2, 4) all specialize.

---

## Source 8: AtlusScriptCompiler — Overview & Run via Commandline

URLs: https://docs.shrinefox.com/flowscript/atlusscriptcompiler and https://docs.shrinefox.com/flowscript/atlusscriptcompiler/run-via-commandline

> About TGE's script (de)compiler program.

### Downloading the Program

Click the download link and download the `.zip`. Extract All, and move the files to a safe location on your PC.

### Using the Program

There are two ways to use the program — Run via Commandline, or Run via GUI (the GUI is far easier, but it's good to be familiar with both).

### Run via Commandline

This method is the traditional way to use the compiler. If using the GUI method instead, you can safely skip this page and the Compile/Decompile sections.

**Usage — Command Prompt**

If you tried to run `AtlusScriptCompiler.exe` like a typical `.EXE`, the program would appear to quickly open and close without doing anything — commandline programs must be run from the Windows Command Prompt ("CMD").

1. Press Windows Key + R and type `cmd`.
2. Press Enter.
3. Drag `AtlusScriptCompiler.exe` onto the CMD window, OR type the full path to the program in the CMD (wrap it in quotes in case any folder names contain spaces).
4. Press Enter.

Your CMD window should look like:

```
Microsoft Windows [Version 10.0.22000.120]
(c) Microsoft Corporation. All rights reserved.

C:\Users\Username>"C:\Path\To\AtlusScriptCompiler.exe"
```

At this point, the program should just spit out a list of arguments to use.

**Arguments**

Arguments are the commands that commandline programs take as user input, typed after the path to the program.

For instance, to Decompile a Persona 5 `.BF` script:

```
C:\Users\Username>"C:\Path\To\AtlusScriptCompiler.exe" "C:\Path\To\input.bf" -Decompile -Library P5 -Encoding P5 -Out "C:\Path\To\output.flow"
```

AtlusScriptCompiler can compile `.FLOW` and `.MSG` files, and decompile `.BF` and `.BMD` files.

---

## Source 9: AtlusScriptCompiler — Decompile (full argument reference)

URL: https://docs.shrinefox.com/flowscript/atlusscriptcompiler/run-via-commandline/decompile

> Convert BF and BMD into flowscripts and messagescripts. This allows you to view scripts in plain text and edit to your liking.

### 1. Specifying the Input File

For decompiling, this must be a `.BF` or `.BMD` file:

```
C:\Users\Username>"C:\Path\To\AtlusScriptCompiler.exe" "C:\Path\To\input.bmd"
```

You can drag `AtlusScriptCompiler.exe` and then `input.bmd` onto the command prompt window — this automatically wraps each path in quotes, keeping arguments separate in case paths contain spaces.

### 2. Specify that you are Decompiling

Add `-Decompile`, separated by a space:

```
C:\Users\Username>"C:\Path\To\AtlusScriptCompiler.exe" "C:\Path\To\input.bmd" -Decompile
```

### 2 (sic — page numbering as published). Specifying the Library

A Flowscript Library instructs the compiler on function names and parameters. Tell the compiler which Library to use with `-Library`:

```
C:\Users\Username>"C:\Path\To\AtlusScriptCompiler.exe" "C:\Path\To\input.bmd" -Decompile -Library P5
```

**Included Libraries**

| Library Name | Usage |
|---|---|
| DigitalDevilSaga | `-LibraryDDS` |
| Nocturne | `-LibrarySMT3` |
| Persona3 | `-LibraryP3` |
| Persona3FES | `-LibraryP3FES` |
| Persona3Portable | `-LibraryP3P` |
| Persona4 | `-LibraryP4` |
| Persona4Golden | `-LibraryP4G` |
| Persona5 | `-LibraryP5` |
| **Persona5Royal** | **`-LibraryP5R`** |
| PersonaQ2 | `-LibraryPQ2` |

Not all games have libraries available. Knowledge of reverse engineering game executables is required to generate a library, since you have to find the offsets of function signatures yourself. A sample script for dumping that data from P3/P4 (PS2) is linked on the source page.

> **Correction (Source 21):** the concatenated `-LibraryP5R`-style flags in this table do not match the actual AtlusScriptCompiler build tested (v1.0-1c557a0, 2026-05-17). That build takes `-Library` and its value as two separate tokens — `-Library P5R` — and accepts either the full name in quotes (`"Persona 5 Royal"`) or a lowercase shorthand (`p5r`). Running the compiler with no arguments prints the full current list of available libraries and their shorthands; `-Library P5R` was confirmed valid this way. Treat this table as historical/possibly-version-specific rather than the literal flag syntax to type.

### 3. Specifying Encoding

An Encoding can be specified using `-Encoding`. It tells the compiler what set of characters to use:

```
C:\Users\Username>"C:\Path\To\AtlusScriptCompiler.exe" "C:\Path\To\input.bmd" -Decompile -Library P5 -Encoding P5
```

**Encodings**

| Game Name | Usage |
|---|---|
| Persona 5 | `-EncodingP5` |
| Persona 4 | `-EncodingP4` |
| Persona 3 (FES) | `-EncodingP3` |
| PersonaQ(2) or any game using Shift-JIS/CP932 | `-EncodingSJ` |

> **Correction (Source 21):** this table has no P5R-specific row and the walkthrough previously assumed reusing `P5`'s encoding was fine — it isn't. The installed compiler lists a distinct `P5R_EFIGS` charset (aliases `p5r`, `p5r_m5`, `p5r_efigs`), and a real shipped P5R mod's `CompilerArgs.json` uses `"Encoding": "P5R_EFIGS"`, not `"P5"`. Use `-Library P5R -Encoding P5R_EFIGS` for P5R, not `-Encoding P5`. (Also note the flag syntax correction from Source 9's Library section above applies here too — `-Encoding` and its value are separate tokens on the compiler build tested, not concatenated.)

### 5 (sic). Specifying the Output File

Name the Output File using `-Out`:

```
C:\Users\Username>"C:\Path\To\AtlusScriptCompiler.exe" "C:\Path\To\input.bmd" -Decompile -Library P5 -Encoding P5 -Out "C:\Path\To\output.msg"
```

If `-Out` is not specified, it defaults to the input filename and folder, but with the output filetype appended (e.g. `C:\Path\To\input.bmd.msg`).

Press Enter to begin decompiling.

---

## Source 10: AtlusScriptCompiler — Compile (full argument reference + Hooking)

URL: https://docs.shrinefox.com/flowscript/atlusscriptcompiler/run-via-commandline/compile

> Convert flowscripts and messagescripts back into BF and BMD.

### 1. Specifying the Input File

For compiling, this must be a `.FLOW` or `.MSG` file:

```
C:\Users\Username>"C:\Path\To\AtlusScriptCompiler.exe" "C:\Path\To\field.bf.flow"
```

### 2. Specify that you are Compiling

Add `-Compile`:

```
C:\Users\Username>"C:\Path\To\AtlusScriptCompiler.exe" "C:\Path\To\field.bf.flow" -Compile
```

### 2 (sic). Specifying the Library

Same `-Library` flag and table as Decompile above (e.g. `-LibraryP5R` for Persona 5 Royal — **but see the correction under Source 9/Source 21: the compiler build actually tested takes this as `-Library P5R`, two separate tokens**):

```
C:\Users\Username>"C:\Path\To\AtlusScriptCompiler.exe" "C:\Path\To\field.bf.flow" -Compile -Library P5
```

### 3. Specifying Output Format

Choose an Output Type with `-OutFormat` — this determines the version and endianness of the generated BF or BMD:

```
C:\Users\Username>"C:\Path\To\AtlusScriptCompiler.exe" "C:\Path\To\field.bf.flow" -Compile -Library P5 -OutFormat V3BE
```

**Output Types**

| Output Type | Usage |
|---|---|
| Persona 5 BF | `-OutFormatV3BE` |
| Persona 5 (PS3) BMD | `-OutFormatV1BE` |
| Persona 5 (PS4) & Persona 3/4 (PS2) BF/BMD | `-OutFormatV1` |

### 4. Specifying Encoding

Same `-Encoding` flag and table as Decompile above (**for P5R use `-Encoding P5R_EFIGS`, not `P5` — see the correction under Source 9/Source 21**):

```
C:\Users\Username>"C:\Path\To\AtlusScriptCompiler.exe" "C:\Path\To\field.bf.flow" -Compile -Library P5 -OutFormat V3BE -Encoding P5
```

### 5. Specifying the Output File

```
C:\Users\Username>"C:\Path\To\AtlusScriptCompiler.exe" "C:\Path\To\field.bf.flow" -Compile -Library P5 -OutFormat V3BE -Encoding P5 -Out "C:\Path\To\field.bf"
```

If `-Out` is not specified, it defaults to the input filename and folder with the output filetype appended (e.g. `field.bf.flow.bf`).

### 6. Hooking — the mechanism behind the `_hook` naming convention

> This section is the actual compiler-level explanation of the `_hook` suffix convention referenced in Source 2 (BF Emulator) — that page tells you *to* name a procedure `x_hook` but not *why* it works; this page does.

Hooking is handy when you're compiling a `.FLOW` and only want to replace specific procedures in an imported `.BF`. AtlusScriptCompiler is not perfect, so it doesn't hurt to be proactive — with hooks, you can avoid potential compiler issues when recompiling an entire `.BF` script.

Enable Hooking by adding the `-Hook` argument.

When compiling your `.FLOW` into `.BF`, this redirects existing procedures in an imported `.BF` file to replacement procedures with matching names that end in `_hook_()`.

The original procedure still exists and can be called by name in your `.FLOW` script, since the original data is not overwritten when hooking a function. References to the original procedure in the original `.BF` are simply redirected to your replacement.

```
C:\Users\Username>"C:\Path\To\AtlusScriptCompiler.exe" "C:\Path\To\field.bf.flow" -Compile -Library P5 -OutFormat V3BE -Encoding P5 -Out "C:\Path\To\field.bf" -Hook
```

**Setup steps for hooking:**

1. Decompile the `.BF` that you're referencing in the `.FLOW` you're compiling.
2. Open the `.FLOW` and copy the procedure you want to edit.
3. Paste it into your `.FLOW` that references the `.BF`, and add `_hook` to the procedure name.
4. Edit the procedure however you'd like.
5. Import the original `.BF` file.
6. Compile your new `.FLOW` with the `-Hook` argument.

---

## Source 11: AtlusScriptCompiler — Run via GUI

URL: https://docs.shrinefox.com/flowscript/atlusscriptcompiler/run-via-gui

> Using the Compiler with AtlusScriptCompilerGUI — a Graphical User Interface made by ShrineFox for ease of use when (de)compiling.

1. Download the GUI (under "Assets" on its release page).
2. Extract All from the downloaded `.zip`.
3. Move the files to the location of your `AtlusScriptCompiler.exe`.
4. Double-click `AtlusScriptCompilerGUI.exe` to run it. If `AtlusScriptCompiler.exe` is found, the form will open.
5. Choose the game you'll be working with from the dropdown.

### Usage

To (de)compile, drag and drop files onto the corresponding buttons of the form. Checkboxes toggle:

- **Hooking** — safe to leave on by default.
- **Displaying the log** — useful for diagnosing errors.
- **Disassembling** — off by default, useful for reverse engineers when a script fails to (de)compile.
- **Overwriting** — when on, output looks like `script.bf` rather than `script.bf.flow.bf` (i.e. it overwrites any existing file of that name).

SumBits is enabled by default when decompiling — it simplifies mathematical expressions automatically.

---

## Source 12: Messagescript — Markup

URL: https://docs.shrinefox.com/flowscript/messagescript/markup

> How to style the text in messages. Change the appearance of text in a `.MSG` by inserting the following commands in brackets into your message.

### Commands

- **`[clr x]`** — Text color. Affects all text after the tag until the end of the line (`[e]`). `x` is a number between 0 and 30 (see color table below).
- **`[n]`** — Linebreak. Put this between text to make it show up on a new line in-game.
- **`[w]`** — Wait. Makes the game await user input before moving on to the next line.
- **`[vp w x y z 0 0]`** — Voice Pack. Makes the game play a voice clip. `w` = eventIdMajor, `x` = eventIdMinor, `y` = eventIdSub, `z` = cueId.
- **`[bup 0 x y z 0]`** — Bustup. Shows a character's talking sprite during dialog. `x` = characterId, `y` = expressionId, `z` = customeId. Lip flap will animate if this command is followed by `[f 4 10 -1 0 0]`.

(Recall from Source 3's examples that `[dlg Name [TGE]]` and `[sel Name]` mark dialog/selection blocks, `[f 2 1]`/`[f 1 1]` are additional formatting tags, and `[e]` ends a line/entry — those tags weren't otherwise defined on the pages fetched.)

### Colors (for `[clr x]`)

| Index | Color | Hex Value |
|---|---|---|
| 0 | White | #FFFFFF |
| 1 | Light Blue | #72C5FF |
| 2 | Light Red | #FF423F |
| 3 | Light Yellow | #FFFF76 |
| 4 | Light Green | #69FF65 |
| 5 | Dark Brown | #50321E |
| 6 | Dark Orange | #DC6E00 |
| 7 | White | #FFFFFF |
| 8 | Dark Brown | #50321E |
| 9 | Red | #FF1800 |
| 10 | Dark Red | #BA0000 |
| 11 | Blue | #1200FFF *(as published — likely a typo for #1200FF or similar)* |
| 12 | Dark Blue | #1F00BA |
| 13 | Green | #0AC000 |
| 14 | Dark Green | #078600 |
| 15 | Purple | #9D00EF |
| 16 | Dark Purple | #78008E |
| 17 | Dark Yellow | #BF9D02 |
| 18 | Pink | #FF0391 |
| 19 | Dark Pink | #FF00FC |
| 20 | Darker Pink | #DB0054 |
| 21 | Light Teal | #00AEFF |
| 22 | Dark Brown | #90401A |
| 23 | Light Black | #161616 |
| 24 | Dark Gray | #404040 |
| 25 | Gray | #656565 |
| 26 | Dark Yellow | #E6B625 |
| 27 | White | #FFFFFFF *(as published — 7 hex digits, likely a typo for #FFFFFF)* |
| 28 | Dark Teal | #99BBD3 |
| 29 | Really Light Brown | #E4D4C7 |

---

## Source 13: Persona 5 — Library Functions (applies to P5R too)

URL: https://docs.shrinefox.com/flowscript/library-functions/persona-5

> Functions found in all versions of Persona 5. **These functions are automatically included when using the P5 library of AtlusScriptCompiler. They are also found in P5R & P5EX libraries.**

This resolves the gap noted below about the empty P5R page: P5R doesn't have its own separate function set documented because it reuses P5's — pass `-Library P5` or `-Library P5R` to AtlusScriptCompiler (both draw on the same underlying function set per this page) and this content applies directly.

The page itself covers "some of the most common commands, in order of usefulness" (not exhaustive — see Source 14 for the exhaustive raw list) with working code examples. Condensed below; see the companion raw file (Source 14) for the complete signature list.

### Message Boxes

- `void MSG_WND_DSP();` — opens the message window; call before a message function.
- `void MSG_WND_CLS();` — closes the message window; call after message functions are done.
- `void MSG(int msgID, int unused);` — basic dialog box, usually for character conversation. First arg is the message's index (or name — AtlusScriptCompiler resolves names to indices) in the imported `.msg` file; second arg is always 0/unused.
- `void MSG_MIND(int msgID, int unused);` — thought-bubble text, usually the protagonist's inner thoughts. Same signature/usage as `MSG()`.
- `void MSG_SYSTEM(int msgID);` — grey system box, usually tutorials/settings confirmations. Same as the above but lacks the unused second argument.

```
// Imports messages from a nearby .msg file
import("messages.msg");

MSG_WND_DSP();
MSG(firstMessage, 0);  // same as MSG(0,0)
MSG(secondMessage, 0); // same as MSG(1,0)
MSG(thirdMessage, 0);  // same as MSG(2,0)
MSG_WND_CLS();
```

### Menus

- `int SEL(int msgID);` — takes a message index of a `[sel]`-type message (not `[msg]`/`[dlg]`); returns the index of the option the user picked. If called between a message-box open and `MSG_WND_CLS()`, the prior message stays onscreen as context behind the menu. The message-box function used (`MSG`, `MSG_MIND`, `MSG_SYSTEM`) determines the menu's visual style (portrait sidebar, thought bubbles, grey boxes respectively).

```
import("messages.msg");
import("menus.msg");

MSG_WND_DSP();
MSG(firstMessage, 0);
int selection = SEL(firstMenu);
MSG_WND_CLS();

if (selection == 0) { /* ... */ }
else if (selection == 1) { /* ... */ }
```

- `int SEL_GENERIC(int msgTitleID, int msgOptionsID);` — a large scrollbar menu covering most of the screen, for when you have many options. First arg is a `[dlg]`/`[msg]`-type title message; second is the `[sel]`-type options message. Returns `-1` if the player cancels (unless using a `_NOT_CANCEL` variant).

Variants: `SEL_GENERIC_NOT_HELP` (no per-option description text), `SEL_GENERIC_NOT_CANCEL` (removes the cancel-to-exit option), `SEL_GENERIC_EX` (undocumented — "takes an extra two integer arguments?" per the source page).

**Menu option descriptions** (used with `SEL_GENERIC` unless `_NOT_HELP` is used): each option can show extra description text when highlighted. This requires a specific, finicky convention per the source page:
- The description `.msg` entries (type `[dlg]`/`[msg]`) must immediately follow the `[sel]` block they describe, in the same order as the options.
- Each option line in the `[sel]` block must end with a `[ref optionIndex descriptionMsgIndex]` tag.
- Description entry names must start with `GENERIC_HELP_` (anything after that is free-form; naming them after the message index is recommended to avoid confusion).

Example from the source page:

```
[sel Options_ModMenu]
Phone/Auto-Recover[ref 0 1][e]
Player[ref 1 2][e]
...

[dlg GENERIC_HELP_1]
View your IM messages[n]or auto heal the party,
[n]just like the [clr 18]IM button[clr 0]
[n]normally does.[e]

[dlg GENERIC_HELP_2]
Change social stats, items,
[n]Personas, Skills, model,
[n]animations, money or name.[e]
```

If any of these conventions aren't followed exactly, the description shows as a blank white box in-game instead of text.

### Calling Functions

Use the Amicitia wiki to find ID numbers for what you're trying to call (per the source page).

- `void CALL_BATTLE(int battleIndex);` — starts a battle by its index (found in the game's `ENCOUNT.TBL`, in `battle/table.pac`; the source page recommends `p5_tbl.bt`/`p5r_tbl.bt` templates in 010 Editor to navigate/edit it). Follow with `WAIT_BATTLE();` (no args) to avoid softlocks; execution resumes on the calling field once the battle ends.
  - Variants: `CALL_EVENTBATTLE(int eventID, int subID, int encounterID)` (plays an event first, then the attached battle); `FLD_START_BOSS(int bossID)` (starts a boss/midboss battle by procedure number in `boss.bf`; may alter story progression).
- `void CALL_FIELD(int majorID, int minorID, int entrance, int unknown);` — warps to another area (town, dungeon, safe room, Velvet Room, title screen, etc.). `entrance` is the spawn point, usually defined in the field's `.FBN` file (use 0 if unsure); `unknown` is usually 0. **Warning from source page:** Mementos and non-existent fields crash the game — use caution.
  - Variants: `CALL_AT_DUNGEON(int area, int floor, int entrance)` (warps to a specific Mementos floor); `FLD_MY_PALACE_ENTER()` (Royal-only, enters the Thieves Den, only works on saves where it's unlocked).
- `void CALL_EVENT(int eventMajor, int eventMinor);` — starts a story event scene (skippable, logged in the conversation log); returns to the calling field afterward. Variant `CALL_KF_EVENT()` takes two extra args (usually 0) and is for field events with a following party-member NPC.

Misc one-liners documented on the source page: `CALL_PUBLIC_SHOP(int shopID)`, `CALL_CHAT_ARRIVAL(int chatID)`, `CALL_CALENDAR()`, `BGM(int waveID)` (changes music from `bgm.awb`), `CALL_BATTING_CENTER()`, `CALL_FISHING_POND()`, `CALL_TITLE()`, `CALL_STAFF_ROLL()`, `CALL_WEAPON_SHOP()`, `CALL_ITEM_SHOP()`, `CALL_COMBINE_SHOP()` (Velvet Room fusion menu), `CALL_NAME_ENTRY()` / `CALL_PHANTOM_NAME_ENTRY()` (naming menus — wrap with `INIT_IME_DRIVER()`/`END_IME_DRIVER()` to prevent crashes).

### Stats

`ADD_PC_ALL_PARAM(knowledge, charm, proficiency, guts, kindness);` — adds social-stat points (integers; it takes hundreds of points to max a stat, so award small amounts; 0 = no award for that stat). Follow with `DISP_PC_PARAM_METER();` to show the points-added/level-up visual.

### Money

```
// Take 540 yen from the player
int yen = -540;
CHANGE_GLOBAL_MONEY(yen, 0);

// Add 154,000 yen and show it being added
yen = 154000;
GET_MONEY_WINDOW(yen, 0);
CALL_GLOBAL_MONEY_PANEL();
CHANGE_GLOBAL_MONEY(yen, 0);
DEL_GLOBAL_MONEY_PANEL();
```

### Personas

> Per the source page: there are no known ways to remove a specific Persona, check which Persona is equipped, change the equipped Persona, or change a party member's Persona using flowscript.

- `ADD_PERSONA_STOCK(int personaID);` — adds a Persona to your current set.
- `CLEAR_PERSONA_STOCK();` — removes all Personas from your current set.
- `PERSONA_EVOLUTION(int partyMember, int personaID);` — evolves a party member's Persona to tier 2.
- `SET_PERSONA_LV(int partyMember, int stockIndex, int level);` — sets a Persona's level (1–99).
- `CHK_PERSONA_EXIST(int lowerRange, int upperRange);` — returns 1/0 for whether a Persona in that ID range is in stock (source page notes uncertainty: "I think it takes a range of Persona IDs?").

### Skills

- `PERSONA_SKILL_ADD(int partyMember, int personaID, int skillID);` — gives a skill to a specific Persona (use `REMOVE_PERSONA_SKILL` for the reverse).
- `SKILL_ADD(int partyMember, int skillID);` — same, without specifying a Persona ID (adds to the protagonist's currently equipped Persona in his case).

```
// Give Joker's equipped Persona the skill Agi
SKILL_ADD(1, 10);

// Show the skill being added
FADEIN(0, 10);
FADE_SYNC();
FLD_REQ_FLASHBACK(152, 51);
FLD_END_FLASHBACK();
```

### Items

Type IDs (OR'd/added to the item ID):

| Type ID | Item Type |
|---|---|
| 0x0 | Melee Weapons |
| 0x1000 | Armor |
| 0x2000 | Accessories |
| 0x3000 | Consumables |
| 0x4000 | Key Items |
| 0x5000 | Materials |
| 0x6000 | Skill Cards |
| 0x7000 | Outfits |
| 0x8000 | Ranged Weapons |

```
// Receive 4 of the key item "Morgana's Scarf"
ItemGet(0x4000, 72, 4);

// Show the item type, name and amount being received
GET_ITEMS_WINDOW(0);

// Borrowable helper procedure to easily add items
void ItemGet(int type, int itemId, int amount)
{
    GET_ITEM_BUF_RESET();
    GET_ITEM_BUF_SET(type + itemId, amount);
    SET_ITEM_NUM(type + itemId, GET_ITEM_NUM(type + itemId) + amount);
}
```

The source page links to the complete raw function list at `Atlus-Script-Tools/Source/AtlusScriptCompiler/Resources/Include/p5.flow` on GitHub — that exact file, in full, is Source 14 below.

---

## Source 14: p5.flow — the complete raw function library (ground truth)

URL: https://github.com/tge-was-taken/Atlus-Script-Tools/blob/539e25eec0eed909ca1e04b931157360cf8acd1b/Source/AtlusScriptCompiler/Resources/Include/p5.flow

This is not a documentation page — it's the actual include file bundled inside the **AtlusScriptCompiler tool itself** (`Source/AtlusScriptCompiler/Resources/Include/p5.flow` in the Atlus-Script-Tools repo the compiler is built from). It's what the compiler literally loads when you pass `-Library P5` (or `-Library P5R`, which per Source 13 draws on the same function set). This is the ground-truth, exhaustive list — **1,878 function signatures**, each as `function(0xHEXCODE) returnType NAME(paramType param0, ...);` — versus Source 13's curated ~40-function subset with prose explanations.

Because this is machine-format source code rather than prose, it's delivered as a **separate companion file** (`p5-library-functions.flow`, sent alongside this document) rather than pasted inline here. A short sample, to show the format:

```
function(0x0000) void SYNC();
function(0x0001) void WAIT(int param0);
function(0x0005) void MSG(int param0, int param1);
function(0x0022) void MSG_WND_DSP();
function(0x0023) void MSG_WND_CLS();
function(0x0024) int SEL(int param0);
function(0x4056) int CHANGE_GLOBAL_MONEY(int param0, int param1);
```

**Recommendation on how to use this alongside Source 13:** feed both to Claude Code, for different purposes. This raw file is the correctness/completeness source — if Claude Code needs to know whether a function exists, its exact name, return type, or parameter count, this file is authoritative and won't have the transcription gaps a hand-written doc page might. Source 13 (the ShrineFox page) is the idiomatic-usage source — it explains conventions this raw list can't: call-before/call-after pairing (`MSG_WND_DSP`/`MSG_WND_CLS`), the finicky `GENERIC_HELP_` menu-description convention, which functions need to be followed by a sync/wait call to avoid softlocks, item-ID bit-flag construction, etc. Note also that once AtlusScriptCompiler itself is downloaded (Source 8), this exact file will already exist on disk in the tool's own `Resources/Include` folder — fetching it now just means Claude Code has it in hand before you've necessarily downloaded the tool.

> **Correction/update (Source 21):** the actual compiler release tested (v1.0-1c557a0, 2026-05-17) does **not** ship a single flat `p5.flow` file — it ships a structured, per-game `Libraries/` folder instead, e.g. `Libraries/Persona5Royal.json` pointing at `Libraries/Persona5Royal/Modules/{AI,Common,Facility,Field,Net,Social}/{Functions.json,Enums.json}`. This is a newer/superseding format of the same information (same function/enum data, split by category, JSON instead of `.flow` syntax) — treat it as more current than this raw `p5.flow` file if the two ever disagree, since it's what the actually-installed compiler build loads. `p5-library-functions.flow` (the standalone companion file this section describes) was never actually present alongside this doc when checked — if you need it, either regenerate it from a fresh compiler download's `Libraries/Persona5Royal/` folder, or pull `p5.flow` fresh from the GitHub URL above.

---

## Source 15: Flowscript — Procedures

URL: https://docs.shrinefox.com/flowscript/flowscript/procedures

> A Procedure is defined as a set of coded instructions that tell a computer how to perform certain calculations. A bulk of scripting takes place within these so-called procedures.

This is the core `.flow` syntax reference — the piece that explains *how to write* a correct procedure, which matters directly for writing `_hook` procedures (Source 2/10) and new procedures with forced indices (Source 2).

### Main()

Every Flowscript has at least one procedure, usually called `Main()`, used as the entry point. When the script is executed by the game, it follows the path starting from the first line of `Main()`.

```
void Main() // Procedure declaration
{
    2 + 2; // Statement, would equal 4 once compiled and run
}
```

Every line of code is a **statement**, ending with a semicolon to tell the compiler the logical expression is complete (the source page's analogy: like saying "OVER" on a walkie-talkie).

The `void` keyword indicates the data type the procedure returns. A `void` doesn't return anything — it just runs its code and continues from wherever it was called. When the end of `Main()` is reached, the entire script has finished executing.

### Return Types

A procedure can return a value once calculations finish, if it isn't `void`. The returned value is then used wherever the procedure was called, as if it were a variable.

```
void Main() // Procedure declaration
{
    2 + GetNumber(); // Statement, would equal 5 once compiled and run
}

int GetNumber() // Procedure declaration
{
    return 3; // Return statement
}
```

Data types a procedure can return:

| Name | Description | Example Value |
|---|---|---|
| `void` | Default procedure type. Does not return anything. | — |
| `int` | Integer. A whole number between -2147483648 and 2147483647. | `24` |
| `float` | Floating-point. A decimal between 1.175494351E-38 and 3.402823466E+38. | `24.01f` |
| `bool` | Boolean. True or false (can also be represented as 1 or 0). | `true` / `1` |

### Parameters

A parameter is an argument a procedure requires to do its calculations (the source page's analogy: like needing to know `x` before solving `x + y = 30`). Parameters use the same data types as above:

```
void Main() // Procedure declaration
{
    GetNumber( 2, 15 ); // Statement, would equal 17 once compiled and run
}

int GetNumber( int inputNumber, int anotherNumber ) // Procedure declaration with parameters
{
    return inputNumber + anotherNumber; // Return statement
}
```

The source page's own conclusion: procedures, return types, and parameters are foundational and get built on further in a "Variables" page (linked next from this one, not fetched here as it was out of scope for this pass — flag it if you need variable-declaration syntax specifically).

---

## Source 16: Flowscript — Variables

URL: https://docs.shrinefox.com/flowscript/flowscript/variables-and-procedures

> Variables are named objects of a specified data type that we can assign a value to.

### Declaring & Initializing

Declaring (naming) a variable: `var variableName;`

Initializing (giving it a value) uses `=`: `var variableName = 25;`

### Data Types

| Name | Description | Example Value |
|---|---|---|
| `var` | Default data type. The compiler assumes the most likely data type. | `5`, `20.3f`, `true` |
| `int` | Integer. A whole number between -2147483648 and 2147483647. | `24` |
| `float` | Floating-point. A decimal between 1.175494351E-38 and 3.402823466E+38. | `24.01f` |
| `bool` | Boolean. True or false (also 1 or 0). | `true` / `1` |

You can initialize with an explicit type:

```
int variableName = 25;
float variableName2 = 25.01;
```

In most cases the compiler assumes a bare number is an `int`. Append `f` to a number to force it to be treated as a `float`, even without a decimal point:

```
// This will be assumed to be an int
var variableName = 25;

// This will be assumed to be a float
var variableName2 = 25f;
```

---

## Source 17: Flowscript — Scope

URL: https://docs.shrinefox.com/flowscript/flowscript/scope

> A Scope is an area of a program where an object is recognized. Procedures have their own scope — to the rest of the script, variables declared inside a procedure do not exist outside it.

```
// variableName only exists within Main() since it's local
void Main() {
    var variableName = 25;
    // no other procedure will be able to recognize 'variableName'
    AnotherProcedure();
}

void AnotherProcedure(int variableTest ) {
    // This would cause an ERROR.
    var test = variableName;
}
```

Unless assigned to a variable of greater scope, a local variable's value is discarded when its procedure ends.

### Variable Scopes

| Name | Description |
|---|---|
| `local` | Default scope for variables. |
| `global` | Persists across all scripts while the game is running. |
| `static` | Value persists per procedure while the script is running. |
| `const` | Must be initialized with a value. Cannot be changed afterward. |

**Local** — can't be accessed outside its procedure, but can be passed by reference to another procedure that accepts it as a parameter:

```
void Main() {
    var variableName = 25;
    // since AnotherProcedure() takes an int...
    AnotherProcedure( variableName );
}

// ... we can make a copy of its value with a different name
void AnotherProcedure(int variableTest ) {
    // This would create a new local variable equal to 25
    var test = variableTest;
}
```

**Global** — persists even after a script finishes executing; stays in memory while the game is running, but is not saved to the save file. Practical use case per the source page: remembering the last entered number after closing/reopening a menu.

```
// globalTest exists for as long as the game is running, even after Main()
global int globalTest = 50;

void Main() {
    globalTest = globalTest + 30;
    AnotherProcedure();
}

void AnotherProcedure() {
    // This would create a new local variable equal to 80
    var test = globalTest;
}
```

**Static** — declared but not initialized outside a procedure; keeps its value between executions while the game is running, but isn't saved to the save file.

```
static int staticNumber;

void Main() {
    // the first static int will be 10 higher every time the script is run
    staticNumber = staticNumber + 10;
}
```

**Const** — value cannot change after initialization; useful for named constants known in advance.

```
const int constantNumber = 99;

void Main() {
    constantNumber = 0;
    // test would still equal 99
    var test = constantNumber;
}
```

**Out Variables** — pass values between procedures (even `void` ones) without reference/global/static/const, using the `out` keyword in the parameter declaration:

```
void Main() {
    OutTest( out x, out y );
    var x + y; // result equaling 35
}

void OutTest( out int x, out int y )
{
    x = 5;
    y = 30;
}
```

The source page notes this is an advanced pattern you won't need often.

---

## Source 18: Flowscript — Importing Files

URL: https://docs.shrinefox.com/flowscript/flowscript/importing

> How to include other scripts in your script.

> At the beginning of a Flowscript, you can import a `.BF`, `.FLOW`, `.BMD`, or `.MSG` file.

**This is directly relevant to merging:** it's the mechanism by which a `.flow` file references the base `.bf`/`.bmd` it's hooking, and how `.msg` files get pulled into a `.flow` script (as seen in the P5 library-functions examples, Source 13).

Chaining multiple `.FLOW` scripts together keeps code clean and organized. You can call procedures by name from pre-compiled `.BF` files and other `.FLOW` files, and reference messages by name (or index) from pre-compiled `.BMD` files.

### Importing Uncompiled Scripts

Example: `Experiment.flow` wants to use a procedure from `Test.flow`.

**Experiment.flow** (the new `.FLOW`):

```
// Import another Flowscript into the script
import( "Test.flow" );

void Main() {
    // Call procedure from the imported FlowScript
    ShowWindow();
}
```

**Test.flow** (the `.FLOW` being imported):

```
import( "Test.msg" );

void ShowWindow() {
    int messageNumber = 2;
    MSG_WND_DSP();
    MSG( messageNumber, 0 );
    MSG_WND_CLS();
}
```

**Test.msg** (the `.MSG` imported by the imported `.FLOW`):

```
[dlg FirstMessage]
[s]Message 1.[e]

[msg SecondMessage]
[s]Nessage 2.[e]

[dlg ThirdMessage]
[s]Message 3.[e]
```

**Result:** if run in-game, "Message 3." would display. `messageNumber` is initialized to `2` and used as `MSG()`'s first argument; message indexes start at 0, so index 2 is the 3rd message.

### Importing Compiled Scripts

With `.BF` and `.BMD`, you can reference procedures, variables, and messages by name, but variable names and comments are lost in compilation. You can still decompile these (Source 9) to see the message names/indexes and procedure names in order to reference them.

> The source page itself flags this subsection ("Importing Compiled Scripts") as still incomplete beyond the paragraph above.

---

## Source 19: Remaining Flowscript/Messagescript pages — confirmed to exist but still incomplete on the doc site

The following pages were checked directly and confirmed to exist (they're real, linked, navigable pages — not 404s), but each one's actual body is just a heading, an example code snippet, and a bullet list of "Pending additional information on the following" topics with no further explanation. Listed here for completeness/honesty rather than silently skipped, and because the pending-topics lists at least tell you *what's not yet documented* if you go looking:

- **[Arrays](https://docs.shrinefox.com/flowscript/flowscript/arrays)** — example shown: `int array2[] = { 1, 2, 3, 4, 5 };`. Pending: Defining Arrays, Initializing Arrays, Getting and Setting Array Values.
- **[Enums](https://docs.shrinefox.com/flowscript/flowscript/enums)** — heading only ("Enumerables"). Pending: What is an Enum, How to Define Enums, Using Enums (user input example). (Note: this is the `.flow`-language concept of enums; not to be confused with the compiler's `Enums.json` library-override feature from Source 2, which is a different, fully-documented mechanism.)
- **[Loops](https://docs.shrinefox.com/flowscript/flowscript/loops-and-conditionals)** — example shown: `for ( int i = 0; i < 22; i = i + 1 ) { ... };`. Pending: For Loops, While Loops.
- **[Conditionals](https://docs.shrinefox.com/flowscript/flowscript/conditionals)** — example shown: `if ( 1 != value ) { ... };`. Pending: If/Else, `!` (not), `||` (or), `&&` (and), Switch cases.
- **[Functions](https://docs.shrinefox.com/flowscript/flowscript/functions)** — one substantive line survives: "Functions are hardcoded procedures in the game's executable (ALL_CAPS)" — i.e. this page's topic is the built-in engine functions (like the ones catalogued in Sources 13/14), as distinct from user-defined procedures (Source 15). Pending: Common, Field, AI, etc. (presumably function categories).
- **[Menus](https://docs.shrinefox.com/flowscript/flowscript/menus)** — heading only. Pending: Selection Masks, Pages, Selection Box Descriptions, Selection Box Help Text (P5) — this last one would have been the primary source for the `GENERIC_HELP_` convention already captured secondhand in Source 13.
- **[Message Variables](https://docs.shrinefox.com/flowscript/messagescript/message-variables)** — heading only ("How to display certain data within a message"). Pending: Defining Message Variables, Using Message Variables.

**Net assessment:** the ShrineFox site's Flowscript sub-tree is genuinely finished through Procedures → Variables → Scope → Importing Files (Sources 15–18, all fully written with working examples) and genuinely unfinished from Arrays onward. If you need Arrays/Enums/Loops/Conditionals/`if`/`switch` syntax, or the P5-specific menu-help-text convention in full, this doc site won't have it — that'd have to come from reading actual decompiled `.flow` files (Source 9's Decompile instructions) as worked examples instead of prose documentation.

---

## Source 20: Archive/CPK Extraction Tooling

URLs: https://docs.shrinefox.com/getting-started/persona-5-royal-pc-mod-support and https://personamodding.com/p5r/getting-started/making-mods/extracting-files/

This fills the one prerequisite step the walkthrough above explicitly flagged as out of scope: how to actually get `f007.bf` (or any other target file) out of the game's CPK/archive files in the first place, before you can decompile it (Step 3 of the walkthrough).

### Step A — Unpacking CPKs (CRIWare archives)

Per the ShrineFox P5R (PC) Mod Support page: the game's assets are stored in `.CPK` files (CRIWare archives) — `data.cpk`/`BASE.CPK` holds most game files, `data_movie.cpk` holds cutscenes, and `data_XX.cpk` (e.g. `data_e.cpk`/`EN.CPK`) holds language-specific files.

**CLI option (recommended for scripting/automation — e.g. Claude Code driving this headlessly): [CpkExtract](https://github.com/1330-Studios/CPK-Extract)**

This matters because the underlying library the GUI tool below is built on, **[CriFsV2Lib](https://github.com/Sewer56/CriFsV2Lib)** (by Sewer56 — same author as P5R PC Essentials and FileEmulationFramework), is explicitly a *library*, not a CLI tool — its own README says "a basic standalone WPF application is also available for testing," meaning the only end-user artifact it ships is a GUI. CpkExtract is a small third-party wrapper program around that same library that exposes a genuine command-line interface instead.

Download the prebuilt `CpkExtract.exe` from its [Releases page](https://github.com/1330-Studios/CPK-Extract/releases/latest) (v1.0.1 at time of writing, ~23 MB, self-contained — no separate .NET runtime install needed). Usage:

```
CpkExtract.exe <file-path> [output-directory]
```

- `<file-path>` — path to a specific `.cpk` file, or a directory to search for `.cpk` files in.
- `[output-directory]` — optional; defaults to the same directory as the `.cpk` file if omitted.

Examples:

```
:: Extract a single CPK to a specific output folder
CpkExtract.exe "C:\Games\Steam\steamapps\common\P5R\BASE.CPK" "C:\P5R_Extracted\BASE"

:: Extract every .cpk found in a directory, each to its own adjacent output folder
CpkExtract.exe "C:\Games\Steam\steamapps\common\P5R"
```

Extraction errors are logged to the console with the filename and failure reason — no GUI needed to see what went wrong. (It's built with .NET 8; if you need to build it yourself rather than use the prebuilt exe, that's `dotnet build -c Release` per its own README.)

**GUI alternative (if you ever want it): [CriFsV2Lib.GUI](https://github.com/Sewer56/CriFsV2Lib/releases/latest)** — download `CriFsLib.GUI.zip`, extract, open/drag in `BASE.CPK`, right-click → Extract All (or Extract Selected with search/filter + Ctrl/Shift-select if short on disk space). Repeat for `EN.CPK`. Not needed if you're standardizing on CLI tooling.

> **Warning (ShrineFox page):** unpacked, the full contents come out to roughly 62 GB total — make sure you have the disk space free, regardless of which tool does the unpacking. **This is the actual size problem** — the CPK layer is where the 62 GB lives. The archive layer (Step B below) is already cheap per-target, since you only unpack the one `.arc`/`.pac`/`.bin` file you actually need, not the whole game's worth of archives.

### Avoiding the full 62 GB unpack — extracting just one file out of a CPK

If you only need a handful of specific files rather than the whole game, **CpkExtract as shown above does not support this** — its CLI only takes a whole `.cpk` (or a directory to find `.cpk`s in) and always extracts everything inside it; there's no per-file selection flag in its documented usage. Checked alternatives and what was found:

- **YACPKTool (YetAnotherCPKTool)** and **[CriPakTools](https://github.com/esperknight/CriPakTools)** (exact YACPKTool repo URL not confirmed in this pass — found by name via a Steam guide, not verified firsthand) — CriPakTools does have genuine single-file CLI extraction (`CriPakTool.exe IN_FILE EXTRACT_ME`), which looks like exactly what's wanted. **However**, real-world reports specific to P5R are mixed-to-bad: a comment on a [Steam Community P5R extraction guide](https://steamcommunity.com/sharedfiles/filedetails/?id=3319919428) (dated April 2025) reports YACPKTool "terminated in the middle of runtime" on P5R's CPKs, and that a GUI tool called "CriPak Browser" "also crashes on a lot of files" though "you can try to pull a specific file with it." That same commenter fell back to CriFsV2Lib specifically because of this, though even then reported "quite a lot of empty textures and models" using it in full-extract mode. **Net read: older/generic CPK tools are not confirmed reliable against P5R's specific CPK encryption**, which is exactly why CriFsV2Lib had to add "Persona 5 Royal Encryption Support" as its own explicit feature (per its commit history) rather than working automatically like a generic CRIWare tool.
- **CriPak Browser (The Citadel)** — GUI-only, and per the report above, unreliable on a number of P5R files. Exact source/repo not chased down since it's GUI-only and unreliable regardless.

**Recommended approach instead: a small custom script against the `CriFsV2Lib` NuGet package directly**, since it's the one library with confirmed-working P5R decryption, and its own High Level API (from Source 20's earlier README excerpt) explicitly supports listing files and extracting just one.

> **Correction (Source 21): the snippet below replaces an earlier illustrative version that had two real bugs**, found by actually compiling it against the real `CriFsV2Lib.Definitions` source (`ICpkReader`, `ICriFsLib`, `CpkFile` struct) rather than guessing from the README alone:
> 1. **`CpkFile` has no `FullPath` property.** The struct only exposes `Directory` and `FileName` separately; `FullPath` only exists on an unrelated GUI view-model class. The original snippet's `f.FullPath` would not compile.
> 2. **P5R's CPKs are encrypted, and the original snippet never supplied a decryption function.** `CreateCpkReader` takes an optional `InPlaceDecryptionFunction? decrypt` parameter; without it, extraction from a real P5R CPK would silently produce garbage/corrupt output rather than failing loudly. The fix is `CriFsLib.Instance.GetKnownDecryptionFunction(KnownDecryptionFunction.P5R)`, passed into `CreateCpkReader`.
>
> The version below was actually built (`dotnet build -c Release`, 0 errors) and run against the real `BASE.CPK`, successfully extracting a real 132 KB `.bf` script with correct decryption.

```csharp
// Verified working (Source 21) — built and run against the real P5R BASE.CPK.
using CriFsV2Lib;
using CriFsV2Lib.Definitions;
using CriFsV2Lib.Definitions.Structs;

if (args.Length < 3)
{
    Console.Error.WriteLine("Usage: CpkFileExtract <cpk-path> <internal-target-path> <output-path>");
    return 1;
}

var cpkPath = args[0];     // e.g. "D:\...\P5R\CPK\BASE.CPK"
var targetPath = NormalizePath(args[1]); // internal path inside the CPK, e.g. "EVENT_DATA/SCRIPT/E800/E800_002.BF"
var outPath = args[2];     // where to write the extracted file

// P5R's CPKs are encrypted; CriFsV2Lib ships a known decryption function for it.
// Omitting this silently produces corrupt output instead of an error.
var decrypt = CriFsLib.Instance.GetKnownDecryptionFunction(KnownDecryptionFunction.P5R);

using var fileStream = new FileStream(cpkPath, FileMode.Open, FileAccess.Read);
using var reader = CriFsLib.Instance.CreateCpkReader(fileStream, true, decrypt);
var files = reader.GetFiles();

CpkFile? match = null;
foreach (var f in files)
{
    // CpkFile has no FullPath property — build it from Directory + FileName,
    // matching how CriFsV2Lib's own GUI does it (MainPageViewModel.cs).
    var fullPath = NormalizePath(string.IsNullOrEmpty(f.Directory) ? f.FileName : $"{f.Directory}/{f.FileName}");
    if (string.Equals(fullPath, targetPath, StringComparison.OrdinalIgnoreCase))
    {
        match = f;
        break;
    }
}

if (match is null)
{
    Console.Error.WriteLine($"File not found in CPK: {targetPath}");
    return 2;
}

using var extracted = reader.ExtractFile(match.Value);
File.WriteAllBytes(outPath, extracted.Span.ToArray());
return 0;

static string NormalizePath(string path) => path.Replace('\\', '/').TrimStart('/');
```

Project file (`AllowUnsafeBlocks` is required — `CriFsV2Lib`'s decryption delegate type uses pointer parameters):

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <AllowUnsafeBlocks>true</AllowUnsafeBlocks>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="CriFsV2Lib" Version="2.1.2" />
  </ItemGroup>
</Project>
```

This is still fully CLI/scriptable (`dotnet build` + run the resulting exe with three arguments — CPK path, internal target path, output path) and, unlike a whole-CPK extraction, only reads and writes the one file you asked for, so disk usage stays proportional to what you're actually editing rather than the full 62 GB.

### Step B — Extracting archives inside the unpacked files (PAK/BIN/PAC/ARC)

Per the personamodding.com Extracting Files page: once CPKs are unpacked, you'll find many `.bin`/`.pac`/`.pak` files — archives-within-the-archive (collectively "PAK files," roughly analogous to a zip/rar) that still need extracting to reach individual files like `f007.bf`.

> Note: `.bin` is sometimes used for raw binary files that are *not* archives — if the normal extraction tools don't work on a `.bin`, it's probably not a PAK archive.

Four tool options — **PackTools is the CLI-native one and the right default if you're standardizing on command-line tooling** (e.g. for Claude Code to drive directly); the other three are GUI-first:

1. **[PackTools / AtlusFileSystemLibrary (CLI)](https://github.com/tge-was-taken/AtlusFileSystemLibrary/releases/latest)** — genuinely command-line: `PAKPack.exe` — double-clicking does nothing, it must be run from a terminal. Running with no arguments shows help; the `unpack` command extracts an archive. It's also the only one of the four built for batch operations (the GUI options below only handle one file at a time). Example — extract every `.bin` in a folder and its subfolders:
   ```
   for /R "Path\To\Folder" %i in (*.bin) do "Path\To\PAKPack.exe" unpack %i
   ```
   For a single known file (e.g. the `fd007_003.arc` from the walkthrough below):
   ```
   "Path\To\PAKPack.exe" unpack "Path\To\field\pack\fd007_003.arc"
   ```
2. **[Amicitia (GUI)](https://github.com/tge-was-taken/Amicitia/releases/latest)** — the easiest *interactive* option per the source page, but GUI-only: download `Release.7z`, extract it, open a file in Amicitia; if it's a valid archive you get a tree of files you can export or replace by right-clicking. (This is the same "Amicitia" the P5 library-functions page (Source 13) already pointed to for looking up battle/field ID numbers — same tool, dual purpose — but still not scriptable.)
3. **[PersonaEditor (GUI)](https://github.com/Meloman19/PersonaEditor/releases/latest)** — an alternative with a similar UI to Amicitia; better for some file types and has limited built-in text editing support, but likewise GUI-only.
4. **[PAKPack-Registry](https://github.com/LTSophia/PAKPack-Registry/releases/latest)** — adds PackTools to the Windows right-click context menu. This is explicitly the *opposite* of what you want for automation: it's a convenience layer for humans who'd rather not open a terminal, wrapping the very tool (PackTools) you'd use directly for CLI/scripted work.

### Updating the walkthrough's Step 3 (CLI-only, minimal-disk version)

Source 20 slots in right before Source 9's decompile step. Fully scriptable, no GUI at any point, and — using the selective single-file approach above instead of a full `CpkExtract.exe` dump — without unpacking the full 62 GB.

> **Correction (Source 21):** the original version of this section used the unverified `field\pack\fd007_003.arc` / `f007.bf` example throughout and left `PAKPack.exe unpack`'s output-folder behavior as an open question. Both are now resolved against real commands run on the real Steam install. `field\pack\fd007_003.arc` still doesn't exist in the current CPK layout (see the correction on the walkthrough's Step 3 above), so the example below uses two real files instead: a loose `.bf` (no archive-unpack step needed — this is actually the more common real-world case) to show the full extract→decompile chain, and a real archive (`BATTLE/ENCOUNT.PAC`) to show `PAKPack.exe unpack`'s confirmed behavior.

**Case 1 — loose `.bf`, no archive involved (most field/event scripts in the current build):**

```
:: Step A — pull the file directly out of BASE.CPK with the verified script above
CpkFileExtract.exe "D:\SteamLibrary\steamapps\common\P5R\CPK\BASE.CPK" "EVENT_DATA/SCRIPT/E800/E800_002.BF" "C:\P5R_Work\test\E800_002.bf"

:: Step B (Source 9) — decompile it directly, no unpack step needed
"C:\P5R_Tools\AtlusScriptTools\AtlusScriptCompiler.exe" "C:\P5R_Work\test\E800_002.bf" -Decompile -Library P5R -Out "C:\P5R_Work\test\E800_002.flow"
```

This was run for real: it produced a clean `E800_002.flow` / `E800_002.msg` pair decompiling an actual Confidant gift-giving event script, with readable procedure names (`SUB_GIFT_MAKOTO`, `SUB_GIFT_HARU`, etc.) and syntax matching Sources 15–18 exactly. (`-Encoding` was omitted here since decompiling doesn't require it — only compiling back to binary does, per Source 9/10; use `-Encoding P5R_EFIGS` when compiling.)

**Case 2 — file nested inside an archive (confirms `PAKPack.exe unpack`'s output behavior):**

```
:: Step A — pull the archive out of BASE.CPK
CpkFileExtract.exe "D:\SteamLibrary\steamapps\common\P5R\CPK\BASE.CPK" "BATTLE/ENCOUNT.PAC" "C:\P5R_Work\test\ENCOUNT.PAC"

:: Step B — unpack it
"C:\P5R_Tools\PackTools\PAKPack.exe" unpack "C:\P5R_Work\test\ENCOUNT.PAC" "C:\P5R_Work\test\ENCOUNT_unpacked"
```

**Confirmed (Source 21): `PAKPack.exe unpack <archive> <output-dir>` creates exactly the output directory you give it and mirrors the archive's internal relative paths underneath — no extra subfolder named after the archive is added.** E.g. this produced `ENCOUNT_unpacked\effect\bes_emydie.EPL`, `ENCOUNT_unpacked\effect\be_syoloop.EPL`, etc. — the internal `effect/` folder straight under the output dir you named. If you omit the output-directory argument, it falls back to extracting next to the input file per PAKPack's own usage text; that fallback path wasn't separately re-verified here.

If disk space genuinely isn't a concern (or the selective-extraction script turns out not to be worth the setup effort for how many files you're actually touching), falling back to whole-CPK `CpkExtract.exe` per the main Step A above is simpler and more battle-tested — it's a real, working, already-built tool, versus the custom script which needed to actually be written and verified first (now done, see above).

### Other notes from the ShrineFox P5R (PC) page (context, not extraction-specific)

- Reloaded-II + P5R Essentials is what lets you skip repacking `BASE.CPK`/`EN.CPK` entirely for testing mods — you only need the manual CPK/archive unpacking above to *find and read* files as a mod author, not to *ship* your mod (shipping is the `FEmulator`/dummy-file mechanism from Sources 1–5).
- The page flags porting differences from the older PS4 version worth knowing if adapting an existing mod: `.PAC` contents are now loosely distributed, file paths are uppercase (but the game still loads lowercase), `.GNF` textures are now `.DDS`, texture `.BIN` files no longer use headerless `.DDS`, `.ACB`/`.AWB`/`.USM` encryption keys changed, and — notably — **"there are additional flowscript functions"** in this PC/Switch port versus the original PS4 version, which is a caveat worth remembering alongside Source 14's raw `p5.flow` (that file may not be exhaustive for PC-exclusive additions; treat it as very likely complete but not guaranteed 100%).
- It links to an ongoing 2025 P5R modding blog tutorial series (shrinefox.com) for creating mods and using the various File Emulation Frameworks, noted as not fully completed at time of writing.

---

## Source 21: Verification Pass — Corrections Summary (2026-08-23)

Unlike Sources 1–20, this section isn't pulled from an external doc page — it's a record of actually downloading, running, and exercising the toolchain end-to-end against a real Steam P5R install, done specifically to catch places where the sourced docs above were wrong, outdated, or (in Source 20's case) an untested guess. Every item below was hit for real; nothing here is inferred from prose. Corrections are cross-referenced inline at each affected Source above — this section is the consolidated version.

**Environment used for verification:** Windows 11, Git Bash (MINGW64) + PowerShell, .NET 8 SDK (freshly installed — none was present before), P5R installed via Steam at a non-default library path (`D:\SteamLibrary\...`). AtlusScriptCompiler build tested: `v1.0-1c557a0` (Atlus-Script-Tools release tag `v1.0-1c557a092dd7610829b7215be0f0f5101acf1d72`, dated 2026-05-17) — version numbers matter here since several corrections are about that specific build's CLI surface, not the format/mechanism itself.

> **Note:** the tools/working-files paths mentioned throughout this section are from the private project this reference was originally compiled in and are illustrative only -- none of them are literal paths in this repo. See this repo's top-level README.md and ModConverter/p5rconverter.config.example.json for how the released tools are actually configured (everything is a CLI arg / config file / environment variable now, nothing hardcoded).

**1. AtlusScriptCompiler flag syntax (affects Source 9, Source 10):** the doc's concatenated flags (`-LibraryP5R`, `-EncodingP5`) don't match the tested build. It takes `-Library` and `-Encoding` as separate tokens from their values (`-Library P5R`, `-Encoding P5R_EFIGS`), and accepts either a quoted full name or a lowercase shorthand for `-Library`. Confirmed by running the compiler with no arguments, which prints the full current library/encoding/charset lists.

**2. P5R needs its own encoding, not P5's (affects Source 9, Source 10, the walkthrough):** `-Encoding P5R_EFIGS`, not `-Encoding P5`. Confirmed two ways: the compiler's own charset list shows `P5R_EFIGS` as a distinct entry from `P5`, and a real, currently-installed, working P5R mod's `CompilerArgs.json` uses `"Encoding": "P5R_EFIGS"`.

**3. The compiler's bundled function library is a different, newer format than Source 14 describes (affects Source 14):** not a flat `p5.flow` file, but a structured `Libraries/Persona5Royal/Modules/{AI,Common,Facility,Field,Net,Social}/{Functions.json,Enums.json}` tree. Same underlying data, JSON instead of `.flow` syntax, split by category. Treat as superseding, not contradicting, Source 14's raw file if the two ever disagree.

**4. `p5-library-functions.flow`, the companion file Source 14 describes, was not actually present** alongside this document when checked (only this markdown file was in the project folder). Resolved by #3 above — the installed compiler's own `Libraries/Persona5Royal/` folder covers the same ground and was used instead for this verification pass.

**5. The CriFsV2Lib selective-extraction script (Source 20) had two real bugs**, found by compiling it against `CriFsV2Lib.Definitions`' actual source rather than the README alone:
   - `CpkFile` has no `FullPath` property — only `Directory` and `FileName` separately. The doc's `f.FullPath` would not compile.
   - P5R's CPKs are encrypted, and the original snippet never supplied a decryption function to `CreateCpkReader`. Without `CriFsLib.Instance.GetKnownDecryptionFunction(KnownDecryptionFunction.P5R)`, extraction would silently produce corrupt output rather than an error — this is the more dangerous of the two bugs since it fails silently.
   
   Fixed version is now in place in Source 20, built (`dotnet build -c Release`, 0 errors) and run for real against `BASE.CPK`.

**6. The walkthrough's worked example path never existed in the current build (affects the walkthrough, Source 20's Step 3 update):** `field\pack\fd007_003.arc` / `f007.bf` — a real scan of `BASE.CPK` (44,934 files) found zero matches. This was Source 2's own doc example, carried through as if verified; it wasn't. Real field/event `.bf` files in the current Steam build are loose directly in the CPK (confirmed real example: `EVENT_DATA/SCRIPT/E800/E800_002.BF`, a genuine Confidant gift-event script), not nested inside archives the way the walkthrough assumed. This doesn't invalidate the archive-emulation mechanics themselves (Sources 1/2/5 are still accurate about how nested-archive editing works) — it just means that specific example file isn't real.

**7. `PAKPack.exe unpack`'s output-folder behavior, flagged as unverified in Source 20, is now confirmed:** given an explicit output directory, it creates exactly that directory and mirrors the archive's internal relative paths underneath — no extra subfolder named after the archive gets added. Confirmed against a real archive (`BATTLE/ENCOUNT.PAC`).

**8. `ModConfig.json`'s actual schema, never shown in Sources 6/7 (GUI-only descriptions), is now documented** in Source 6, verified against a real, currently-installed, working P5R BF-editing mod rather than guessed. Notably: P5R Essentials' real Mod Id is `p5rpc.modloader`, and the large `PluginData.GitHubDependencies` block real mods carry is GUI-updater metadata, not required for the mod to actually load.

**Confirmed accurate, no correction needed:** `-OutFormat V3BE` for P5R (compiler's own help text lists it as "Used by Persona 5 PS3 & PS4"), the `_hook` naming convention and its mechanics (confirmed against a real shipped mod's `PartyChange_hook()` procedure), dummy files being genuinely empty (0 bytes) with the target extension, `.flow` procedure/variable/scope syntax (Sources 15–18, confirmed by decompiling a real 132 KB script and getting output that matches those sources' examples exactly), and the overall FEmulator/BF, FEmulator/BMD, P5REssentials/CPK folder-mirroring mechanism (Sources 1/2/4/5).

---

## Further pages checked and found empty, or found but not pulled in

- **[Persona 5 Royal — Library Functions](https://docs.shrinefox.com/flowscript/library-functions/persona-5-royal)** — checked directly (including a visual screenshot, not just text extraction): this page is **genuinely empty**, just prev/next navigation with no function list. Resolved by Source 13/14 above: P5R doesn't need its own page because it uses P5's function library.
- [Flowscript](https://docs.shrinefox.com/flowscript/flowscript) — short page on `.FLOW`'s origin/naming (the name comes from the `.BF` magic string "FLW0"); links onward to a "Procedures" page (not fetched — likely explains `.FLOW` procedure syntax in more depth than Source 3's single example).
- [ShrineFox intro-to-scripting "Resources" page](https://docs.shrinefox.com/flowscript/intro-to-scripting/resources) — not fetched.
- [FileRedirectionFramework — AWB emulator](https://sewer56.dev/FileEmulationFramework/emulators/awb.html) (music/audio) and the PAK/SPD emulator pages — same family as the BF/BMD emulator pages but for other file types; not fetched since they're outside the BF/BMD scope.
- Reloaded-II's "Creating a Release" page (linked as "Next" from Source 6/Enabling Update Support) — not fetched; covers packaging/publishing, tangential to merging itself.

## Cross-Reference Notes (not from source pages — for orientation only)

- The P5R Essentials usage page (Source 1) is the top-level, game-specific guide: it tells you *where* to place dummy files relative to CPKs/archives so P5R Essentials' redirection recognizes your target.
- The BF Emulator page (Source 2) and BMD Emulator page (Source 4) are the underlying FileEmulationFramework components that actually perform the flowscript/message merging (via `FEmulator/BF` or `FEmulator/BMD`, `.flow`/`.msg` hooking, and — BF only — forced indices and library overrides). These are the deepest documentation on *how merging actually behaves* (overwrite-by-name semantics, hook suffixes, index forcing).
- The Routing page (Source 5) is the general mechanism both emulators sit on top of: it explains *why* dummy files need to mirror the original file's archive path (the "Route" concept), how folder names under `FEmulator/<Type>` resolve to a target file, and how emulation nests recursively (file-inside-file-inside-file).
- The ShrineFox Intro to Scripting page (Source 3) is pure background on the file formats and the Flowscript/Messagescript languages themselves (what `.flow`/`.msg` syntax looks like), produced via AtlusScriptCompiler. It does not cover the mod-merging system.
- Net effect of the BMD gap being filled: BF and BMD merging are now documented symmetrically — same dependency-plus-folder-plus-matching-filename pattern, same "only include what you're changing, names must match exactly to overwrite" rule, same overwrite-not-ignore compiler behavior. BF additionally supports forced procedure indices and script-compiler library/enum overrides, which have no BMD equivalent per the source page.
- Sources 6–7 (Reloaded-II) explain the generic mechanism that Sources 1, 2, and 4 are all specific applications of: create a mod config, add another mod as a dependency so it always loads alongside yours, then drop files into a folder whose name/structure that dependency interprets.
- Sources 8–11 (AtlusScriptCompiler) are the actual tool you decompile/compile with — they're a prerequisite step none of Sources 1–2/4 explain: you need a decompiled `.flow`/`.msg` to know what to hook/overwrite before you can write a merge-safe edit. Source 10 in particular explains *why* the `_hook` suffix convention (from Source 2) works: it's the `-Hook` compiler flag redirecting call sites to your replacement procedure while leaving the original intact.
- Source 12 (Markup) is the piece needed to actually author correct `.msg` content — the color and formatting tags (`[clr x]`, `[n]`, `[w]`, `[vp ...]`, `[bup ...]`) referenced implicitly by Source 3's example but never defined there.
- The Persona 5 Royal Library Functions page — the natural page that would list the actual callable flowscript function names for P5R — was checked and is empty/unfinished on the doc site. This is fully resolved, not just noted as a gap: P5R shares P5's function library (confirmed directly by Source 13's own text), so Source 13 (curated, ~40 functions with usage patterns and worked examples) plus Source 14 (the raw, exhaustive 1,878-function signature list pulled straight from the compiler's own resource file) together cover it completely — one for idiomatic usage, one for ground-truth correctness.
- Sources 15–18 (Procedures, Variables, Scope, Importing Files) are the genuinely finished portion of the ShrineFox Flowscript language reference — together they cover enough `.flow` grammar to read and write simple hook/message procedures correctly. Source 19 catalogues the rest of that same page tree (Arrays, Enums, Loops, Conditionals, Functions, Menus, Message Variables) honestly as unfinished stubs on the source site, each with whatever fragment (a heading, an example line, a pending-topics list) it does have — so nothing was silently skipped, but syntax for arrays/loops/conditionals genuinely isn't available from this doc site and would need to come from reading real decompiled `.flow` examples instead.
