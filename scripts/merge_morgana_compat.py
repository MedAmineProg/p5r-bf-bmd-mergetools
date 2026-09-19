"""
Generic message-block merge: unions two mods' .msg block sets by name, with an optional
+N "bup" (bustup ID) shift applied to any block the first ("morgana") side also defines --
the exact mechanism used to reconcile a mechanical-rule mod (shifts one bustup parameter
everywhere) against a mod that rewrites message text, without hand-transcribing ~50+ blocks.
See docs/FINDINGS.md, section 1, for why this operates at the message-block level rather than
trusting load order to pick a winner.

Usage: python merge_morgana_compat.py <rule_mod.msg> <other_mod.msg> <out.msg>
"""
import re, sys

def load_blocks(path):
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    blocks = {}
    order = []
    cur_name = None
    cur_lines = []
    header_re = re.compile(r'^\[(msg|sel)\s+(\S+)')
    for line in lines:
        m = header_re.match(line)
        if m:
            if cur_name is not None:
                blocks[cur_name] = "".join(cur_lines)
                order.append(cur_name)
            cur_name = m.group(2)
            cur_lines = [line]
        else:
            if cur_name is not None:
                cur_lines.append(line)
    if cur_name is not None:
        blocks[cur_name] = "".join(cur_lines)
        order.append(cur_name)
    return blocks, order

BUP_RE = re.compile(r'(\[bup 0 3 )(\d+)( )')

def shift_bup(text, offset=600):
    def repl(m):
        return f"{m.group(1)}{int(m.group(2)) + offset}{m.group(3)}"
    return BUP_RE.sub(repl, text)

def merge(morgana_path, other_path, out_path, offset=600):
    morgana_blocks, morgana_order = load_blocks(morgana_path)
    other_blocks, other_order = load_blocks(other_path)

    merged = {}
    order = []
    report = []

    # start with the "other" mod's full set (its own new/changed content)
    for name in other_order:
        if name in morgana_blocks:
            merged[name] = shift_bup(other_blocks[name], offset)
            report.append(f"MERGED (other's text + bup+{offset}): {name}")
        else:
            merged[name] = other_blocks[name]
            report.append(f"other-only (as-is): {name}")
        order.append(name)

    # add morgana-only blocks not present in other
    for name in morgana_order:
        if name not in merged:
            merged[name] = morgana_blocks[name]
            order.append(name)
            report.append(f"morgana-only (as-is): {name}")

    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        for i, name in enumerate(order):
            f.write(merged[name].rstrip("\n") + "\n")
            if i != len(order) - 1:
                f.write("\n")

    print(f"Wrote {len(order)} blocks to {out_path}")
    for r in report:
        print("  " + r)

if __name__ == "__main__":
    merge(sys.argv[1], sys.argv[2], sys.argv[3])
