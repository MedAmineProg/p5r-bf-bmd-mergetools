import re

PROC_START_RE = re.compile(r'^void\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*\)\s*$', re.MULTILINE)

def list_procedures(text):
    """Returns list of (name, start_idx, end_idx) where text[start_idx:end_idx] is the full
    'void NAME() { ... }' block including trailing blank lines up to (not including) the next
    procedure or EOF. Brace-balanced from the '{' after the signature."""
    procs = []
    for m in PROC_START_RE.finditer(text):
        name = m.group(1)
        sig_end = m.end()
        brace_start = text.find("{", sig_end)
        if brace_start == -1:
            continue
        depth = 0
        i = brace_start
        while i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        body_end = i + 1
        procs.append((name, m.start(), body_end))
    return procs

def get_procedure_body(text, name):
    for n, s, e in list_procedures(text):
        if n == name:
            return text[s:e]
    return None

def remove_procedures(text, names_to_remove):
    """Removes the named procedures (whole block incl. any immediately-following blank lines
    up to the next 'void' or EOF) from text. Returns (new_text, removed_count)."""
    procs = list_procedures(text)
    name_set = set(names_to_remove)
    removed = 0
    cursor = 0
    out = []
    for n, s, e in procs:
        # always emit whatever lies between the previous cursor and this procedure's start
        # (comments, blank lines, other non-procedure content) -- untouched either way
        out.append(text[cursor:s])
        if n in name_set:
            j = e
            while j < len(text) and text[j] in ("\n", "\r"):
                j += 1
            cursor = j
            removed += 1
        else:
            out.append(text[s:e])
            cursor = e
    out.append(text[cursor:])
    return "".join(out), removed
