# CpkFileExtract

Pulls one file out of a P5R CPK archive without unpacking the whole thing (P5R's CPKs run to
tens of gigabytes; a full unpack is rarely what you actually want).

## Usage

```
CpkFileExtract.exe <cpk-path> <internal-target-path> <output-path>
CpkFileExtract.exe --search <cpk-path> <substring>
CpkFileExtract.exe --batch <cpk-path> <list-file> <out-dir>
```

- The first form extracts one file by its exact internal path (forward or back slashes both
  work), e.g.:
  ```
  CpkFileExtract.exe "D:\...\P5R\CPK\BASE.CPK" "FIELD/HIT/FHIT_151_001_00.BF" "C:\out\FHIT_151_001_00.BF"
  ```
- `--search` lists every internal path containing the given substring (case-insensitive) -- useful
  when you know roughly what a file is called but not its exact path or extension.
- `--batch` extracts every path listed in a text file (one per line), preserving directory
  structure under the output directory, and reports which lines weren't found rather than failing
  the whole run.

No configuration file -- every path is a plain argument. P5R's CPKs are encrypted; this tool
already knows the correct decryption function for P5R via `CriFsV2Lib`.
