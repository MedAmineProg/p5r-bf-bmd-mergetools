using CriFsV2Lib;
using CriFsV2Lib.Definitions;
using CriFsV2Lib.Definitions.Structs;

if (args.Length == 3 && args[0] == "--search")
{
    return SearchMode(args[1], args[2]);
}

if (args.Length == 4 && args[0] == "--batch")
{
    return BatchMode(args[1], args[2], args[3]);
}

if (args.Length < 3)
{
    Console.Error.WriteLine("Usage: CpkFileExtract <cpk-path> <internal-target-path> <output-path>");
    Console.Error.WriteLine("  <cpk-path>            Path to the .cpk file, e.g. D:\\...\\P5R\\CPK\\BASE.CPK");
    Console.Error.WriteLine("  <internal-target-path> Path of the file inside the CPK, e.g. field/pack/fd007_003.arc");
    Console.Error.WriteLine("  <output-path>         Where to write the extracted file");
    Console.Error.WriteLine("Or: CpkFileExtract --search <cpk-path> <substring>   (lists matching internal paths)");
    Console.Error.WriteLine("Or: CpkFileExtract --batch <cpk-path> <list-file> <out-dir>   (extracts every rel path listed, one per line, preserving structure under out-dir; lines not found are reported and skipped)");
    return 1;
}

var cpkPath = args[0];
var targetPath = NormalizePath(args[1]);
var outPath = args[2];

if (!File.Exists(cpkPath))
{
    Console.Error.WriteLine($"CPK not found: {cpkPath}");
    return 1;
}

// P5R's CPKs are encrypted; CriFsV2Lib ships a known decryption function for it.
var decrypt = CriFsLib.Instance.GetKnownDecryptionFunction(KnownDecryptionFunction.P5R);

using var fileStream = new FileStream(cpkPath, FileMode.Open, FileAccess.Read);
using var reader = CriFsLib.Instance.CreateCpkReader(fileStream, true, decrypt);

var files = reader.GetFiles();

CpkFile? match = null;
foreach (var f in files)
{
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
    Console.Error.WriteLine($"({files.Length} files scanned in {Path.GetFileName(cpkPath)})");
    return 2;
}

using var extracted = reader.ExtractFile(match.Value);

var outDir = Path.GetDirectoryName(outPath);
if (!string.IsNullOrEmpty(outDir))
    Directory.CreateDirectory(outDir);

File.WriteAllBytes(outPath, extracted.Span.ToArray());
Console.WriteLine($"Extracted '{targetPath}' ({extracted.Span.Length} bytes) -> {outPath}");
return 0;

static string NormalizePath(string path) => path.Replace('\\', '/').TrimStart('/');

static int BatchMode(string cpkPath, string listFile, string outDir)
{
    if (!File.Exists(cpkPath))
    {
        Console.Error.WriteLine($"CPK not found: {cpkPath}");
        return 1;
    }
    if (!File.Exists(listFile))
    {
        Console.Error.WriteLine($"List file not found: {listFile}");
        return 1;
    }

    var wanted = File.ReadAllLines(listFile)
        .Select(l => l.Trim())
        .Where(l => l.Length > 0)
        .Select(NormalizePath)
        .ToList();

    var decrypt = CriFsLib.Instance.GetKnownDecryptionFunction(KnownDecryptionFunction.P5R);
    using var fileStream = new FileStream(cpkPath, FileMode.Open, FileAccess.Read);
    using var reader = CriFsLib.Instance.CreateCpkReader(fileStream, true, decrypt);
    var files = reader.GetFiles();

    var index = new Dictionary<string, CpkFile>(StringComparer.OrdinalIgnoreCase);
    foreach (var f in files)
    {
        var fullPath = NormalizePath(string.IsNullOrEmpty(f.Directory) ? f.FileName : $"{f.Directory}/{f.FileName}");
        index[fullPath] = f;
    }

    int ok = 0, missing = 0;
    foreach (var rel in wanted)
    {
        if (!index.TryGetValue(rel, out var match))
        {
            Console.Error.WriteLine($"NOT FOUND: {rel}");
            missing++;
            continue;
        }
        using var extracted = reader.ExtractFile(match);
        var outPath = Path.Combine(outDir, rel.Replace('/', Path.DirectorySeparatorChar));
        var dir = Path.GetDirectoryName(outPath);
        if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
        File.WriteAllBytes(outPath, extracted.Span.ToArray());
        ok++;
    }

    Console.WriteLine($"Batch extract: {ok} ok, {missing} not found (of {wanted.Count} requested)");
    return 0;
}

static int SearchMode(string cpkPath, string substring)
{
    if (!File.Exists(cpkPath))
    {
        Console.Error.WriteLine($"CPK not found: {cpkPath}");
        return 1;
    }

    var decrypt = CriFsLib.Instance.GetKnownDecryptionFunction(KnownDecryptionFunction.P5R);
    using var fileStream = new FileStream(cpkPath, FileMode.Open, FileAccess.Read);
    using var reader = CriFsLib.Instance.CreateCpkReader(fileStream, true, decrypt);
    var files = reader.GetFiles();

    var count = 0;
    foreach (var f in files)
    {
        var fullPath = NormalizePath(string.IsNullOrEmpty(f.Directory) ? f.FileName : $"{f.Directory}/{f.FileName}");
        if (fullPath.Contains(substring, StringComparison.OrdinalIgnoreCase))
        {
            Console.WriteLine(fullPath);
            count++;
        }
    }

    Console.Error.WriteLine($"({count} matches / {files.Length} total files in {Path.GetFileName(cpkPath)})");
    return count > 0 ? 0 : 2;
}
