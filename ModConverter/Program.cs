using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using CriFsV2Lib;
using CriFsV2Lib.Definitions;
using CriFsV2Lib.Definitions.Structs;

// ---- Config ----
// All machine-specific paths live outside the source now -- see ToolConfig.Load() below.
// Point it at a config file with --config <path>, or via a p5rconverter.config.json next to the
// exe / in the current directory, or via environment variables. See README.md / the shipped
// p5rconverter.config.example.json for the exact keys.
var explicitConfigPath = ExtractFlag(ref args, "--config");
var cfg = ToolConfig.Load(explicitConfigPath);

var ModsRoot = cfg.ModsRoot;
var OutRoot = cfg.OutRoot;
var BaseCpkPath = cfg.BaseCpkPath;
var EnCpkPath = cfg.EnCpkPath;
var CompilerExe = cfg.CompilerExe;
var PakPackExe = cfg.PakPackExe;
var TempDir = Path.Combine(cfg.TempRoot, Environment.ProcessId.ToString());

if (args.Length < 1)
{
    Console.Error.WriteLine("Usage: ModConverter <modId> [outputModId] [maxFilesForTesting] [--config <path>]");
    Console.Error.WriteLine();
    Console.Error.WriteLine("Config is read from (in order): --config <path>, ./p5rconverter.config.json,");
    Console.Error.WriteLine("<exe-dir>/p5rconverter.config.json, or the P5R_MODS_ROOT / P5R_OUT_ROOT /");
    Console.Error.WriteLine("P5R_BASE_CPK / P5R_EN_CPK / P5R_COMPILER_EXE / P5R_PAKPACK_EXE / P5R_TEMP_ROOT");
    Console.Error.WriteLine("environment variables. See p5rconverter.config.example.json.");
    return 1;
}

var modId = args[0];
var outModId = args.Length > 1 ? args[1] : modId + ".mergeable";

var modRoot = Path.Combine(ModsRoot, modId);
var outModRoot = Path.Combine(OutRoot, outModId);
var cpkContainerRoot = Path.Combine(modRoot, "P5REssentials", "CPK");

if (!Directory.Exists(modRoot))
{
    Console.Error.WriteLine($"Mod not found: {modRoot}");
    return 1;
}
if (!Directory.Exists(cpkContainerRoot))
{
    Console.Error.WriteLine($"No P5REssentials/CPK folder in this mod -- nothing to convert: {cpkContainerRoot}");
    return 1;
}

Directory.CreateDirectory(TempDir);
Directory.CreateDirectory(outModRoot);

ICpkReader enReader = null!;
ICpkReader baseReader = null!;

Console.WriteLine("Loading CPK indexes (BASE.CPK, EN.CPK)...");
var baseFiles = LoadCpkIndex(BaseCpkPath, "BASE.CPK");
var enFiles = LoadCpkIndex(EnCpkPath, "EN.CPK");
Console.WriteLine($"BASE.CPK: {baseFiles.Count} files, EN.CPK: {enFiles.Count} files");

// Auto-discover container folders (arbitrary names per Source 1 -- "call it anything you want")
var containers = Directory.GetDirectories(cpkContainerRoot);
Console.WriteLine($"Found {containers.Length} CPK container folder(s): {string.Join(", ", containers.Select(Path.GetFileName))}");

var targets = new List<(string ModFile, string ContainerRoot, string Rel)>();
var otherFiles = new List<(string ModFile, string ContainerName, string Rel)>();

foreach (var container in containers)
{
    var containerName = Path.GetFileName(container)!;
    foreach (var f in Directory.EnumerateFiles(container, "*.*", SearchOption.AllDirectories))
    {
        var rel = Path.GetRelativePath(container, f).Replace('\\', '/');
        if (f.EndsWith(".bf", StringComparison.OrdinalIgnoreCase) || f.EndsWith(".bmd", StringComparison.OrdinalIgnoreCase))
            targets.Add((f, container, rel));
        else
            otherFiles.Add((f, containerName, rel));
    }
}
targets = targets.OrderBy(t => t.Rel).ToList();

if (args.Length > 2 && int.TryParse(args[2], out var maxFiles))
    targets = targets.Take(maxFiles).ToList();

Console.WriteLine($"Found {targets.Count} target .bf/.bmd files, {otherFiles.Count} other files to carry over verbatim.");

int converted = 0, noChange = 0, notFound = 0, needsReview = 0, decompileFailed = 0;
int pakBmdConverted = 0, pakLeftRaw = 0;
// FEmulator-relative and CPK-container-relative paths already handled by the PAK pass, so the
// later verbatim-copy passes skip them (or write a 0-byte dummy in their place).
var pakHandledFEmulator = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
var pakHandledContainer = new HashSet<string>(StringComparer.OrdinalIgnoreCase); // "<container>/<rel>"
var reviewLog = new List<string>();
var notFoundLog = new List<string>();

var vFlowOut = Path.Combine(TempDir, "v.flow");
var mFlowOut = Path.Combine(TempDir, "m.flow");
var vMsgOut = Path.Combine(TempDir, "v.msg");
var mMsgOut = Path.Combine(TempDir, "m.msg");

int idx = 0;
foreach (var (modFile, containerRoot, rel) in targets)
{
    idx++;
    if (idx % 100 == 0) Console.WriteLine($"[{idx}/{targets.Count}] converted={converted} noChange={noChange} notFound={notFound} review={needsReview}");

    var ext = Path.GetExtension(modFile);

    string? foundCpkName = null;
    CpkFile foundFile = default;
    if (enFiles.TryGetValue(rel, out var enMatch)) { foundFile = enMatch; foundCpkName = "EN.CPK"; }
    else if (baseFiles.TryGetValue(rel, out var baseMatch)) { foundFile = baseMatch; foundCpkName = "BASE.CPK"; }

    if (foundCpkName is null)
    {
        // Folder-style PAK convention: a mod drops "INIT/DATMSG/datDressHelp.bmd" (a loose dir,
        // not the ".PAK") to replace the entry inside "INIT/DATMSG.PAK". If that archive exists in
        // a CPK and contains this entry, convert it as a PAK-nested BMD instead of raw fallback.
        var isBmdTarget = ext.Equals(".bmd", StringComparison.OrdinalIgnoreCase);
        var dir = Path.GetDirectoryName(rel)?.Replace('\\', '/');
        var entryName2 = Path.GetFileName(rel);
        if (isBmdTarget && !string.IsNullOrEmpty(dir))
        {
            foreach (var pakExt in new[] { ".PAK", ".BIN" })
            {
                var archiveRel = dir + pakExt;
                string? aCpk = null; CpkFile aFile = default;
                if (enFiles.TryGetValue(archiveRel, out var aem)) { aFile = aem; aCpk = "EN.CPK"; }
                else if (baseFiles.TryGetValue(archiveRel, out var abm)) { aFile = abm; aCpk = "BASE.CPK"; }
                if (aCpk is null) continue;
                try
                {
                    var rdr = aCpk == "EN.CPK" ? enReader : baseReader;
                    using var ax = rdr.ExtractFile(aFile);
                    var aPakTmp = Path.Combine(TempDir, "vpak3.pak");
                    File.WriteAllBytes(aPakTmp, ax.Span.ToArray());
                    var aUnpack = Path.Combine(TempDir, "vpak3_out");
                    if (Directory.Exists(aUnpack)) Directory.Delete(aUnpack, true);
                    if (PakUnpackAll(aPakTmp, aUnpack))
                    {
                        var vEntry = Directory.EnumerateFiles(aUnpack, "*", SearchOption.AllDirectories)
                            .FirstOrDefault(p => string.Equals(Path.GetFileName(p), entryName2, StringComparison.OrdinalIgnoreCase));
                        if (vEntry is not null &&
                            ConvertOnePakBmd(vEntry, modFile, archiveRel, entryName2, $"folder-PAK {rel} -> {archiveRel}"))
                        {
                            goto pakHandledContinue;
                        }
                    }
                }
                catch (Exception ex) { reviewLog.Add($"{rel} :: folder-PAK probe failed ({ex.Message})"); }
            }
        }

        notFound++;
        notFoundLog.Add(rel);
        // Not in either CPK's top level -- either a brand-new file the mod adds (no vanilla to
        // diff/hook against) or nested inside an archive this tool doesn't unpack (e.g. a .PAK).
        // Either way, preserve the mod's own original content and routing so nothing silently
        // vanishes from the converted mod, even though this one file isn't made mergeable.
        var origContainerName = Path.GetFileName(containerRoot)!;
        var fallbackDest = Path.Combine(outModRoot, "P5REssentials", "CPK", origContainerName, rel);
        Directory.CreateDirectory(Path.GetDirectoryName(fallbackDest)!);
        File.Copy(modFile, fallbackDest, true);
        continue;

        pakHandledContinue:
        continue;
    }

    byte[] vanillaBytes;
    try
    {
        var reader = foundCpkName == "EN.CPK" ? enReader : baseReader;
        using var extracted = reader.ExtractFile(foundFile);
        vanillaBytes = extracted.Span.ToArray();
    }
    catch (Exception ex)
    {
        reviewLog.Add($"{rel} :: EXTRACT FAILED: {ex.Message}");
        needsReview++;
        continue;
    }

    var vanillaTemp = Path.Combine(TempDir, "vanilla" + ext);
    File.WriteAllBytes(vanillaTemp, vanillaBytes);

    foreach (var f in new[] { vFlowOut, mFlowOut, vMsgOut, mMsgOut })
        if (File.Exists(f)) File.Delete(f);

    var isBmd = ext.Equals(".bmd", StringComparison.OrdinalIgnoreCase);

    var vOk = Decompile(vanillaTemp, vFlowOut);
    var mOk = Decompile(modFile, mFlowOut);

    if (!vOk || !mOk)
    {
        decompileFailed++;
        var srcSize = new FileInfo(modFile).Length;
        reviewLog.Add($"{rel} :: DECOMPILE FAILED (vanilla={vOk}, mod={mOk}, modFileSize={srcSize})");
        if (srcSize == 0)
        {
            // Already a dummy in the source mod -- likely a pre-existing correct FEmulator hook.
            // Preserve the dummy; the corresponding FEmulator/* files get copied verbatim below.
            WriteDummyOrRaw(rel, foundCpkName, raw: null);
        }
        continue;
    }

    var msgOverrides = new List<(string Name, string Block)>();

    if (isBmd)
    {
        var vBlocks = ParseMsgBlocks(File.ReadAllText(vFlowOut));
        var mBlocks = ParseMsgBlocks(File.ReadAllText(mFlowOut));
        foreach (var (name, block) in mBlocks)
        {
            if (!vBlocks.TryGetValue(name, out var vBlock) || vBlock != block)
                msgOverrides.Add((name, block));
        }
    }
    else
    {
        var flowChanged = FlowDiffersBeyondImport(vFlowOut, mFlowOut);

        var vMsgExists = File.Exists(vMsgOut);
        var mMsgExists = File.Exists(mMsgOut);

        if (vMsgExists && mMsgExists)
        {
            var vBlocks = ParseMsgBlocks(File.ReadAllText(vMsgOut));
            var mBlocks = ParseMsgBlocks(File.ReadAllText(mMsgOut));

            foreach (var (name, block) in mBlocks)
            {
                if (!vBlocks.TryGetValue(name, out var vBlock) || vBlock != block)
                    msgOverrides.Add((name, block));
            }
        }
        else if (vMsgExists != mMsgExists)
        {
            reviewLog.Add($"{rel} :: MSG PRESENCE MISMATCH (vanilla={vMsgExists}, mod={mMsgExists})");
            needsReview++;
            continue;
        }

        if (flowChanged)
        {
            reviewLog.Add($"{rel} :: FLOW LOGIC DIFFERS beyond import line -- needs manual hook, not auto-converted");
            needsReview++;
            WriteDummyOrRaw(rel, foundCpkName, raw: modFile);

            // Stage the decompiled vanilla/mod pair for manual hook-writing.
            var reviewBase = Path.Combine(outModRoot, "_review", rel);
            Directory.CreateDirectory(Path.GetDirectoryName(reviewBase)!);
            try
            {
                if (File.Exists(vFlowOut)) File.Copy(vFlowOut, reviewBase + ".vanilla.flow", true);
                else reviewLog.Add($"{rel} :: NOTE: vanilla .flow vanished before staging, re-run to retry");
                if (File.Exists(mFlowOut)) File.Copy(mFlowOut, reviewBase + ".mod.flow", true);
                else reviewLog.Add($"{rel} :: NOTE: mod .flow vanished before staging, re-run to retry");
                if (File.Exists(vMsgOut)) File.Copy(vMsgOut, reviewBase + ".vanilla.msg", true);
                if (File.Exists(mMsgOut)) File.Copy(mMsgOut, reviewBase + ".mod.msg", true);
            }
            catch (Exception ex)
            {
                reviewLog.Add($"{rel} :: NOTE: staging copy failed ({ex.Message}), re-run to retry");
            }
            continue;
        }
    }

    if (msgOverrides.Count == 0)
    {
        noChange++;
        continue;
    }

    // Loose .bmd targets are handled by the SEPARATE BMD emulator, which only scans
    // FEmulator/BMD -- NOT FEmulator/BF. Putting a bmd's .msg override under FEmulator/BF
    // means it is never applied and the 0-byte dummy gets served, causing the game's CRI
    // layer to spin in an infinite retry loop on that file (confirmed in-game 2026-08-30
    // on kasumi.roseandviolet's BATTLE/MESSAGE/DATJYOKYOHELP.BMD). .bf targets (including
    // .bf files with embedded messages, edited via the sibling-.msg convention) stay under
    // FEmulator/BF. Path is mirrored below the CPK container to disambiguate same-named
    // bmds in different dirs (e.g. BATTLE/MESSAGE/0304 vs /030A/DATCHARAORDER.BMD).
    var outEmu = isBmd ? "BMD" : "BF";
    var outMsgPath = Path.Combine(outModRoot, "FEmulator", outEmu, rel);
    outMsgPath = Path.ChangeExtension(outMsgPath, ".msg");
    Directory.CreateDirectory(Path.GetDirectoryName(outMsgPath)!);
    var sb = new StringBuilder();
    foreach (var (name, block) in msgOverrides)
    {
        sb.AppendLine(block.TrimEnd());
        sb.AppendLine();
    }
    File.WriteAllText(outMsgPath, sb.ToString());

    WriteDummyOrRaw(rel, foundCpkName, raw: null);

    converted++;
}

// ---- PAK-nested .bmd conversion ----
// Loose message BMDs live inside PAK archives (INIT/DATMSG.PAK, INIT/CMM.BIN, ...). A mod edits
// one either by shipping the whole modified .PAK under P5REssentials/CPK/, or by shipping a raw
// replacement entry under FEmulator/PAK/<archive>/<name>.bmd. Both are whole-BMD replacements that
// stomp any other mod touching the same archive. Convert them to the mergeable form the
// FileEmulationFramework docs (Source 2) and real mods (p4g64.riseOutfit, p4g64.betterFishing)
// use: a 0-byte dummy at FEmulator/PAK/<archive-path>/<name>.bmd + the .msg override at
// FEmulator/BMD/<archive-path>/<name>.msg. Only fully-BMD archive edits are converted; a .PAK
// that also changed a .ctd/.bf/etc entry is left raw and logged.
{
    // (a) whole .PAK files shipped under P5REssentials/CPK/<container>/...
    var pakOthers = otherFiles.Where(o => o.ModFile.EndsWith(".pak", StringComparison.OrdinalIgnoreCase)).ToList();
    foreach (var (modPak, containerName, pakRel) in pakOthers)
    {
        // vanilla PAK must be a top-level CPK entry
        string? vCpk = null;
        CpkFile vFile = default;
        if (enFiles.TryGetValue(pakRel, out var em)) { vFile = em; vCpk = "EN.CPK"; }
        else if (baseFiles.TryGetValue(pakRel, out var bm)) { vFile = bm; vCpk = "BASE.CPK"; }
        if (vCpk is null)
        {
            reviewLog.Add($"{pakRel} :: PAK not in any CPK (mod-added archive) -- left raw");
            pakLeftRaw++;
            continue;
        }
        byte[] vBytes;
        try
        {
            var rdr = vCpk == "EN.CPK" ? enReader : baseReader;
            using var ex = rdr.ExtractFile(vFile);
            vBytes = ex.Span.ToArray();
        }
        catch (Exception ex) { reviewLog.Add($"{pakRel} :: PAK extract failed: {ex.Message} -- left raw"); pakLeftRaw++; continue; }

        var vPakTmp = Path.Combine(TempDir, "vpak.pak");
        File.WriteAllBytes(vPakTmp, vBytes);
        var ok = ConvertPakBmds(vPakTmp, modPak, pakRel, $"whole-PAK {containerName}/{pakRel}");
        if (ok) pakHandledContainer.Add($"{containerName}/{pakRel}");
        else pakLeftRaw++;
    }

    // (b) raw replacement entries the mod ships under FEmulator/PAK/<archive>/<name>.bmd
    var femPakRoot = Path.Combine(modRoot, "FEmulator", "PAK");
    if (Directory.Exists(femPakRoot))
    {
        foreach (var entry in Directory.EnumerateFiles(femPakRoot, "*.bmd", SearchOption.AllDirectories))
        {
            var relFromPak = Path.GetRelativePath(femPakRoot, entry).Replace('\\', '/'); // INIT/CMM.BIN/cmmHelp.bmd
            if (new FileInfo(entry).Length == 0) continue; // already a dummy -- correct as-is
            var slash = relFromPak.LastIndexOf('/');
            if (slash < 0) { reviewLog.Add($"FEmulator/PAK/{relFromPak} :: no archive prefix -- left raw"); continue; }
            var archiveRel = relFromPak[..slash];      // INIT/CMM.BIN
            var entryName = relFromPak[(slash + 1)..]; // cmmHelp.bmd

            string? vCpk = null; CpkFile vFile = default;
            if (enFiles.TryGetValue(archiveRel, out var em)) { vFile = em; vCpk = "EN.CPK"; }
            else if (baseFiles.TryGetValue(archiveRel, out var bm)) { vFile = bm; vCpk = "BASE.CPK"; }
            if (vCpk is null) { reviewLog.Add($"FEmulator/PAK/{relFromPak} :: archive {archiveRel} not in any CPK -- left raw"); continue; }

            byte[] vBytes;
            try
            {
                var rdr = vCpk == "EN.CPK" ? enReader : baseReader;
                using var ex = rdr.ExtractFile(vFile);
                vBytes = ex.Span.ToArray();
            }
            catch (Exception ex) { reviewLog.Add($"FEmulator/PAK/{relFromPak} :: archive extract failed: {ex.Message} -- left raw"); continue; }

            var vPakTmp = Path.Combine(TempDir, "vpak2.pak");
            File.WriteAllBytes(vPakTmp, vBytes);
            var vUnpack = Path.Combine(TempDir, "vpak2_out");
            if (Directory.Exists(vUnpack)) Directory.Delete(vUnpack, true);
            if (!PakUnpackAll(vPakTmp, vUnpack)) { reviewLog.Add($"FEmulator/PAK/{relFromPak} :: PAKPack unpack failed -- left raw"); continue; }
            var vEntry = Directory.EnumerateFiles(vUnpack, "*", SearchOption.AllDirectories)
                .FirstOrDefault(p => string.Equals(Path.GetFileName(p), entryName, StringComparison.OrdinalIgnoreCase));
            if (vEntry is null) { reviewLog.Add($"FEmulator/PAK/{relFromPak} :: entry {entryName} not in vanilla {archiveRel} (mod-added) -- left raw"); continue; }

            if (ConvertOnePakBmd(vEntry, entry, archiveRel, entryName, $"FEmulator/PAK/{relFromPak}"))
                pakHandledFEmulator.Add(("PAK/" + relFromPak).Replace('/', Path.DirectorySeparatorChar));
        }
    }
}

// Copy the mod's existing FEmulator/ folder verbatim (any pre-existing correct hooks/overrides
// the author already wrote, plus Functions.json/Enums.json/CompilerArgs.json if present).
var existingFEmulator = Path.Combine(modRoot, "FEmulator");
if (Directory.Exists(existingFEmulator))
{
    foreach (var f in Directory.EnumerateFiles(existingFEmulator, "*.*", SearchOption.AllDirectories))
    {
        var relF = Path.GetRelativePath(existingFEmulator, f);
        // A FEmulator/PAK/<archive>/<name>.bmd we already converted to a message override:
        // replace it with a 0-byte dummy in the output, don't carry the raw replacement.
        if (pakHandledFEmulator.Contains(relF))
        {
            var dummyDest = Path.Combine(outModRoot, "FEmulator", relF);
            Directory.CreateDirectory(Path.GetDirectoryName(dummyDest)!);
            File.WriteAllBytes(dummyDest, Array.Empty<byte>());
            continue;
        }
        var dest = Path.Combine(outModRoot, "FEmulator", relF);
        Directory.CreateDirectory(Path.GetDirectoryName(dest)!);
        // Don't clobber an auto-generated override with an older identical one; last-writer wins,
        // and our generated overrides were written first in this run, so existing-mod files here
        // take priority only where we didn't already generate something at the same path.
        if (!File.Exists(dest))
            File.Copy(f, dest, true);
    }
}

// Copy every non-.bf/.bmd file under each CPK container verbatim (textures, tables, etc. --
// not a BF/BMD merge concern, but shouldn't be silently dropped from a "complete" converted mod).
foreach (var (modFile, containerName, rel) in otherFiles)
{
    if (pakHandledContainer.Contains($"{containerName}/{rel}"))
        continue; // whole .PAK converted to per-BMD message overrides -- don't ship the raw archive
    var dest = Path.Combine(outModRoot, "P5REssentials", "CPK", containerName, rel);
    Directory.CreateDirectory(Path.GetDirectoryName(dest)!);
    File.Copy(modFile, dest, true);
}

// Build ModConfig.json from the original, changing only what needs to change.
var origConfigPath = Path.Combine(modRoot, "ModConfig.json");
string modName = modId, modAuthor = "", modDescription = "", modVersion = "1.0.0";
List<string> tags = new(), supportedAppId = new() { "p5r.exe" }, deps = new();
if (File.Exists(origConfigPath))
{
    using var doc = JsonDocument.Parse(File.ReadAllText(origConfigPath));
    var root = doc.RootElement;
    modName = GetStr(root, "ModName") ?? modId;
    modAuthor = GetStr(root, "ModAuthor") ?? "";
    modDescription = GetStr(root, "ModDescription") ?? "";
    modVersion = GetStr(root, "ModVersion") ?? "1.0.0";
    tags = GetStrArray(root, "Tags");
    var origAppIds = GetStrArray(root, "SupportedAppId");
    if (origAppIds.Count > 0) supportedAppId = origAppIds;
    deps = GetStrArray(root, "ModDependencies");
}
foreach (var required in new[] { "p5rpc.modloader", "reloaded.universal.fileemulationframework.bf", "reloaded.universal.fileemulationframework.bmd", "reloaded.universal.fileemulationframework.pak" })
    if (!deps.Contains(required, StringComparer.OrdinalIgnoreCase)) deps.Add(required);

var configOut = new
{
    ModId = outModId,
    ModName = modName + " (Mergeable)",
    ModAuthor = modAuthor,
    ModVersion = modVersion,
    ModDescription = $"Mergeable conversion of {modId}: raw .bf/.bmd file replacements converted to FEmulator/BF message hooks so it can coexist with other BF/BMD-editing mods. Original description: {modDescription}",
    ModDll = "",
    ModIcon = "",
    ModR2RManagedDll32 = "",
    ModR2RManagedDll64 = "",
    ModNativeDll32 = "",
    ModNativeDll64 = "",
    Tags = tags,
    CanUnload = (bool?)null,
    HasExports = (bool?)null,
    IsLibrary = false,
    IsUniversalMod = false,
    ModDependencies = deps,
    OptionalDependencies = Array.Empty<string>(),
    SupportedAppId = supportedAppId,
};
File.WriteAllText(Path.Combine(outModRoot, "ModConfig.json"), JsonSerializer.Serialize(configOut, new JsonSerializerOptions { WriteIndented = true }));

Console.WriteLine();
Console.WriteLine($"=== SUMMARY: {modId} -> {outModId} ===");
Console.WriteLine($"Total targets:     {targets.Count}");
Console.WriteLine($"Converted to hook: {converted}");
Console.WriteLine($"No actual change:  {noChange}");
Console.WriteLine($"Not found in CPK:  {notFound}");
Console.WriteLine($"Needs review:      {needsReview}");
Console.WriteLine($"Decompile failed:  {decompileFailed}");
Console.WriteLine($"PAK-nested BMD:    {pakBmdConverted} converted, {pakLeftRaw} archive(s) left raw");

File.WriteAllLines(Path.Combine(outModRoot, "_conversion_review_log.txt"), reviewLog);
File.WriteAllLines(Path.Combine(outModRoot, "_conversion_notfound_log.txt"), notFoundLog);
Console.WriteLine($"Review log: {reviewLog.Count} entries. Not-found log: {notFoundLog.Count} entries.");

enReader.Dispose();
baseReader.Dispose();
return 0;

// ---- Helpers ----

string? GetStr(JsonElement root, string prop) =>
    root.TryGetProperty(prop, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : null;

List<string> GetStrArray(JsonElement root, string prop)
{
    var list = new List<string>();
    if (root.TryGetProperty(prop, out var v) && v.ValueKind == JsonValueKind.Array)
        foreach (var item in v.EnumerateArray())
            if (item.ValueKind == JsonValueKind.String) list.Add(item.GetString()!);
    return list;
}

Dictionary<string, CpkFile> LoadCpkIndex(string cpkPath, string label)
{
    var dict = new Dictionary<string, CpkFile>(StringComparer.OrdinalIgnoreCase);
    var stream = new FileStream(cpkPath, FileMode.Open, FileAccess.Read);
    var decrypt = CriFsLib.Instance.GetKnownDecryptionFunction(KnownDecryptionFunction.P5R);
    var reader = CriFsLib.Instance.CreateCpkReader(stream, true, decrypt);
    if (label == "EN.CPK") enReader = reader; else baseReader = reader;

    foreach (var f in reader.GetFiles())
    {
        var full = string.IsNullOrEmpty(f.Directory) ? f.FileName : $"{f.Directory}/{f.FileName}";
        full = full.Replace('\\', '/').TrimStart('/');
        dict[full] = f;
    }
    return dict;
}

// Unpack every entry of a PAK to a flat directory (PAKPack flattens by entry name).
bool PakUnpackAll(string pakPath, string outDir)
{
    Directory.CreateDirectory(outDir);
    var psi = new ProcessStartInfo
    {
        FileName = PakPackExe,
        RedirectStandardOutput = true,
        RedirectStandardError = true,
        UseShellExecute = false,
    };
    psi.ArgumentList.Add("unpack");
    psi.ArgumentList.Add(pakPath);
    psi.ArgumentList.Add(outDir);
    using var proc = Process.Start(psi)!;
    proc.StandardOutput.ReadToEndAsync();
    proc.StandardError.ReadToEndAsync();
    if (!proc.WaitForExit(60000)) { try { proc.Kill(true); } catch { } return false; }
    return proc.ExitCode == 0 && Directory.EnumerateFiles(outDir, "*", SearchOption.AllDirectories).Any();
}

// Diff every .bmd entry of a modified PAK against vanilla, emitting FEmulator/BMD + FEmulator/PAK
// dummy pairs. Returns true only if the archive was FULLY convertible (all differing entries are
// .bmd). A .PAK that also changed a non-.bmd entry returns false and should be kept raw.
bool ConvertPakBmds(string vanillaPak, string modPak, string archiveRel, string label)
{
    var vOut = Path.Combine(TempDir, "pak_v"); var mOut = Path.Combine(TempDir, "pak_m");
    foreach (var d in new[] { vOut, mOut }) if (Directory.Exists(d)) Directory.Delete(d, true);
    if (!PakUnpackAll(vanillaPak, vOut) || !PakUnpackAll(modPak, mOut))
    {
        reviewLog.Add($"{label} :: PAKPack unpack failed -- left raw");
        return false;
    }
    var vByName = Directory.EnumerateFiles(vOut, "*", SearchOption.AllDirectories)
        .ToDictionary(p => Path.GetFileName(p), StringComparer.OrdinalIgnoreCase);
    var changed = new List<string>();
    foreach (var mf in Directory.EnumerateFiles(mOut, "*", SearchOption.AllDirectories))
    {
        var name = Path.GetFileName(mf);
        if (!vByName.TryGetValue(name, out var vf)) { changed.Add(name); continue; }
        if (!File.ReadAllBytes(mf).AsSpan().SequenceEqual(File.ReadAllBytes(vf))) changed.Add(name);
    }
    if (changed.Count == 0) { reviewLog.Add($"{label} :: PAK identical to vanilla -- dropped"); return true; }
    var nonBmd = changed.Where(c => !c.EndsWith(".bmd", StringComparison.OrdinalIgnoreCase)).ToList();
    if (nonBmd.Count > 0)
    {
        reviewLog.Add($"{label} :: PAK also changes non-BMD entries [{string.Join(", ", nonBmd)}] -- kept raw");
        return false;
    }
    bool anyConverted = false;
    foreach (var name in changed)
    {
        var mf = Directory.EnumerateFiles(mOut, "*", SearchOption.AllDirectories)
            .First(p => string.Equals(Path.GetFileName(p), name, StringComparison.OrdinalIgnoreCase));
        var vf = vByName.TryGetValue(name, out var v) ? v : null;
        if (vf is null) { reviewLog.Add($"{label} :: new entry {name} (no vanilla) -- kept raw"); return false; }
        if (ConvertOnePakBmd(vf, mf, archiveRel, name, $"{label}:{name}")) anyConverted = true;
        else return false;
    }
    return anyConverted;
}

// One .bmd entry: decompile vanilla + mod, diff message blocks, write FEmulator/BMD/<archive>/<name>.msg
// and a 0-byte dummy at FEmulator/PAK/<archive>/<name>.bmd. Returns false only on a hard failure.
bool ConvertOnePakBmd(string vanillaBmd, string modBmd, string archiveRel, string entryName, string label)
{
    var vOut = Path.Combine(TempDir, "pe_v.msg"); var mOut = Path.Combine(TempDir, "pe_m.msg");
    foreach (var f in new[] { vOut, mOut }) if (File.Exists(f)) File.Delete(f);
    if (!Decompile(vanillaBmd, vOut) || !Decompile(modBmd, mOut))
    {
        reviewLog.Add($"{label} :: decompile failed -- kept raw");
        return false;
    }
    var vBlocks = ParseMsgBlocks(File.ReadAllText(vOut));
    var mBlocks = ParseMsgBlocks(File.ReadAllText(mOut));
    var overrides = new List<(string Name, string Block)>();
    foreach (var (name, block) in mBlocks)
        if (!vBlocks.TryGetValue(name, out var vb) || vb != block)
            overrides.Add((name, block));

    var baseName = Path.GetFileNameWithoutExtension(entryName);
    var msgDest = Path.Combine(outModRoot, "FEmulator", "BMD",
        archiveRel.Replace('/', Path.DirectorySeparatorChar), baseName + ".msg");
    var dummyDest = Path.Combine(outModRoot, "FEmulator", "PAK",
        archiveRel.Replace('/', Path.DirectorySeparatorChar), entryName);
    Directory.CreateDirectory(Path.GetDirectoryName(dummyDest)!);
    File.WriteAllBytes(dummyDest, Array.Empty<byte>());

    if (overrides.Count == 0)
    {
        reviewLog.Add($"{label} :: BMD decompiles identical to vanilla -- dummy only, no override");
    }
    else
    {
        Directory.CreateDirectory(Path.GetDirectoryName(msgDest)!);
        var sb = new StringBuilder();
        foreach (var (_, block) in overrides) { sb.AppendLine(block.TrimEnd()); sb.AppendLine(); }
        File.WriteAllText(msgDest, sb.ToString());
    }
    pakBmdConverted++;
    reviewLog.Add($"{label} :: RESOLVED PAK-nested BMD, {overrides.Count} message block(s) -> FEmulator/BMD/{archiveRel}/{baseName}.msg");
    return true;
}

bool Decompile(string inputPath, string outPath)
{
    var psi = new ProcessStartInfo
    {
        FileName = CompilerExe,
        RedirectStandardOutput = true,
        RedirectStandardError = true,
        UseShellExecute = false,
    };
    psi.ArgumentList.Add(inputPath);
    psi.ArgumentList.Add("-Decompile");
    psi.ArgumentList.Add("-Library");
    psi.ArgumentList.Add("P5R");
    psi.ArgumentList.Add("-Encoding");
    psi.ArgumentList.Add("P5R_EFIGS");
    psi.ArgumentList.Add("-Out");
    psi.ArgumentList.Add(outPath);

    using var proc = Process.Start(psi)!;
    proc.StandardOutput.ReadToEndAsync();
    proc.StandardError.ReadToEndAsync();
    if (!proc.WaitForExit(30000))
    {
        try { proc.Kill(true); } catch { }
        return false;
    }
    return proc.ExitCode == 0 && File.Exists(outPath);
}

bool FlowDiffersBeyondImport(string vanillaFlow, string modFlow)
{
    var v = File.ReadAllLines(vanillaFlow);
    var m = File.ReadAllLines(modFlow);
    if (v.Length != m.Length) return true;
    for (int i = 0; i < v.Length; i++)
    {
        if (v[i] == m[i]) continue;
        if (v[i].TrimStart().StartsWith("import(") && m[i].TrimStart().StartsWith("import(")) continue;
        return true;
    }
    return false;
}

Dictionary<string, string> ParseMsgBlocks(string content)
{
    var result = new Dictionary<string, string>(StringComparer.Ordinal);
    var lines = content.Replace("\r\n", "\n").Split('\n');
    var headerRegex = new Regex(@"^\[(msg|sel|dlg)\s+(\S+)");

    int i = 0;
    while (i < lines.Length)
    {
        var m = headerRegex.Match(lines[i]);
        if (!m.Success) { i++; continue; }

        var name = m.Groups[2].Value;
        var blockLines = new List<string> { lines[i] };
        i++;
        while (i < lines.Length && !headerRegex.IsMatch(lines[i]))
        {
            blockLines.Add(lines[i]);
            i++;
        }
        var blockText = string.Join("\n", blockLines).TrimEnd();
        result[name] = blockText;
    }
    return result;
}

void WriteDummyOrRaw(string rel, string cpkName, string? raw)
{
    var dest = Path.Combine(outModRoot, "P5REssentials", "CPK", cpkName, rel);
    Directory.CreateDirectory(Path.GetDirectoryName(dest)!);
    if (raw is null)
        File.WriteAllBytes(dest, Array.Empty<byte>());
    else
        File.Copy(raw, dest, true);
}

// Pulls a "--flag value" pair out of args (if present) and returns the value, leaving the
// remaining positional args untouched so modId/outputModId/maxFiles indexing still works.
static string? ExtractFlag(ref string[] args, string flag)
{
    var list = args.ToList();
    var i = list.IndexOf(flag);
    if (i < 0 || i + 1 >= list.Count) return null;
    var value = list[i + 1];
    list.RemoveRange(i, 2);
    args = list.ToArray();
    return value;
}

// All the machine-specific paths this tool needs, resolved from (highest priority first):
//   1. --config <path> on the command line
//   2. ./p5rconverter.config.json (current working directory)
//   3. <directory containing the exe>/p5rconverter.config.json
//   4. Environment variables: P5R_MODS_ROOT, P5R_OUT_ROOT, P5R_BASE_CPK, P5R_EN_CPK,
//      P5R_COMPILER_EXE, P5R_PAKPACK_EXE, P5R_TEMP_ROOT
// A key missing from every source above is a fatal error (with a message naming the key) rather
// than a silent wrong default -- there is no "sensible default" for someone else's disk layout.
sealed class ToolConfig
{
    public required string ModsRoot { get; init; }
    public required string OutRoot { get; init; }
    public required string BaseCpkPath { get; init; }
    public required string EnCpkPath { get; init; }
    public required string CompilerExe { get; init; }
    public required string PakPackExe { get; init; }
    public required string TempRoot { get; init; }

    public static ToolConfig Load(string? explicitPath)
    {
        Dictionary<string, string>? fromFile = null;
        string? usedPath = null;

        foreach (var candidate in new[]
                 {
                     explicitPath,
                     Path.Combine(Directory.GetCurrentDirectory(), "p5rconverter.config.json"),
                     Path.Combine(AppContext.BaseDirectory, "p5rconverter.config.json"),
                 })
        {
            if (candidate is null || !File.Exists(candidate)) continue;
            fromFile = JsonSerializer.Deserialize<Dictionary<string, string>>(File.ReadAllText(candidate))
                       ?? new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            usedPath = candidate;
            break;
        }
        fromFile ??= new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        string Get(string jsonKey, string envVar)
        {
            if (fromFile.TryGetValue(jsonKey, out var fromJson) && !string.IsNullOrWhiteSpace(fromJson))
                return fromJson;
            var fromEnv = Environment.GetEnvironmentVariable(envVar);
            if (!string.IsNullOrWhiteSpace(fromEnv))
                return fromEnv;
            Console.Error.WriteLine($"Missing config value '{jsonKey}' (env var {envVar}).");
            Console.Error.WriteLine(usedPath is null
                ? "No p5rconverter.config.json was found (checked --config, CWD, and the exe's own directory)."
                : $"Config file in use: {usedPath}");
            Console.Error.WriteLine("See p5rconverter.config.example.json for the expected keys.");
            Environment.Exit(1);
            throw new InvalidOperationException(); // unreachable, keeps the compiler happy
        }

        return new ToolConfig
        {
            ModsRoot = Get("ModsRoot", "P5R_MODS_ROOT"),
            OutRoot = Get("OutRoot", "P5R_OUT_ROOT"),
            BaseCpkPath = Get("BaseCpkPath", "P5R_BASE_CPK"),
            EnCpkPath = Get("EnCpkPath", "P5R_EN_CPK"),
            CompilerExe = Get("CompilerExe", "P5R_COMPILER_EXE"),
            PakPackExe = Get("PakPackExe", "P5R_PAKPACK_EXE"),
            TempRoot = Get("TempRoot", "P5R_TEMP_ROOT"),
        };
    }
}
