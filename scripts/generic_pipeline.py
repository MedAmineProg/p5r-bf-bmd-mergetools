"""
Compile-and-verify + ship machinery for scripted hook generation: builds a .flow + companion
.msg from a "plan" dict (see generate_generic_hooks_v2.py / generate_ngp_hooks.py for how plans
are built), test-compiles it with -Hook against a real vanilla import, checks every intended
procedure actually produced a "Registering X_hook as hook for Y" line (NOT just that the compile
succeeded -- a renamed procedure in the mod's own binary can silently emit an unlinked standalone
procedure instead of a hook, with no error), decompile-verifies every __JUMP is present, then
ships the final .flow/.msg and zeroes the raw-fallback dummy. See the main README's hook-writing
methodology section for the full reasoning behind each check here.

Config: set P5R_COMPILER_EXE (path to AtlusScriptCompiler.exe).
"""
import sys, os, json, subprocess, re

COMPILER = os.environ.get("P5R_COMPILER_EXE")
if not COMPILER:
    raise SystemExit("Set P5R_COMPILER_EXE to your AtlusScriptCompiler.exe path.")
REGISTER_RE = re.compile(r'Registering (\S+) as hook for (\S+)')

def decode(b):
    if b[:2] in (b"\xff\xfe", b"\xfe\xff") or (len(b) > 4 and b[1] == 0 and b[3] == 0):
        return b.decode("utf-16-le", errors="replace")
    return b.decode("utf-8", errors="replace")

def build_flow_text(plan, vanilla_bf_path_for_test, msg_basename):
    lines = []
    if vanilla_bf_path_for_test:
        vpath_escaped = vanilla_bf_path_for_test.replace("\\", "\\\\")
        lines.append(f'import("{vpath_escaped}");')
    msg_name = None
    if plan["msg_overrides"]:
        msg_name = msg_basename + "_msg.msg"
        lines.append(f'import("{msg_name}");')
    lines.append("")
    # When importing the real vanilla .bf (test-compile only), vanilla's own top-level sVar
    # declarations are already exposed through that import -- redeclaring a preserved
    # (vanilla-numbered) sVar would collide with it as a duplicate declaration. Use the
    # fresh-only decl set for that case; the shipped file (no import) needs everything.
    decls = plan.get("test_decl_lines", plan["decl_lines"]) if vanilla_bf_path_for_test else plan["decl_lines"]
    for d in decls:
        lines.append(d)
    lines.append("")
    for body in plan["bodies"]:
        lines.append(body.rstrip())
        lines.append("")
    return "\n".join(lines), msg_name

def build_msg_text(plan):
    parts = []
    for name, block in plan["msg_overrides"]:
        parts.append(block.rstrip())
        parts.append("")
    return "\n".join(parts)

def compile_and_verify(plan, vanilla_bf_path, work_dir, msg_basename):
    work_dir = os.path.abspath(work_dir)
    os.makedirs(work_dir, exist_ok=True)
    if vanilla_bf_path:
        vanilla_bf_path = os.path.abspath(vanilla_bf_path)
    flow_text, msg_name = build_flow_text(plan, vanilla_bf_path, msg_basename)
    flow_path = os.path.join(work_dir, "hook_test.flow")
    with open(flow_path, "w", encoding="utf-8") as f:
        f.write(flow_text)
    if msg_name:
        with open(os.path.join(work_dir, msg_name), "w", encoding="utf-8") as f:
            f.write(build_msg_text(plan))

    out_bf = os.path.join(work_dir, "result.bf")
    proc = subprocess.run(
        [COMPILER, flow_path, "-Compile", "-Library", "P5R", "-Encoding", "P5R_EFIGS",
         "-OutFormat", "V3BE", "-Hook", "-Out", out_bf],
        cwd=work_dir, capture_output=True, timeout=60
    )
    log = decode(proc.stdout) + "\n" + decode(proc.stderr)
    registered = dict(REGISTER_RE.findall(log))
    expected_hooks = set(plan["hook_names"])
    got_hooks = set(registered.keys())
    ok = (proc.returncode == 0) and os.path.exists(out_bf) and (expected_hooks == got_hooks)

    jump_ok = True
    missing_jumps = []
    if ok:
        verify_flow = os.path.join(work_dir, "verify.flow")
        proc2 = subprocess.run(
            [COMPILER, out_bf, "-Decompile", "-Library", "P5R", "-Encoding", "P5R_EFIGS", "-Out", verify_flow],
            capture_output=True, timeout=60
        )
        if os.path.exists(verify_flow):
            text = open(verify_flow, encoding="utf-8").read()
            for target in plan["hook_names"]:
                if f"__JUMP({target})" not in text:
                    missing_jumps.append(target)
                    jump_ok = False
        else:
            jump_ok = False
            missing_jumps = ["<decompile failed>"]

    return {
        "rel": plan["rel"],
        "compile_ok": ok,
        "returncode": proc.returncode,
        "expected_hooks": sorted(expected_hooks),
        "got_hooks": sorted(got_hooks),
        "jump_ok": jump_ok,
        "missing_jumps": missing_jumps,
        "overall_ok": ok and jump_ok,
        "log_tail": log[-1200:],
    }

def ship(plan, mod_root, msg_basename, containers=("EN.CPK",)):
    flow_text, msg_name = build_flow_text(plan, None, msg_basename)
    flow_dest = os.path.join(mod_root, "FEmulator", "BF",
                              os.path.splitext(plan["rel"].replace("/", os.sep))[0] + ".flow")
    os.makedirs(os.path.dirname(flow_dest), exist_ok=True)
    with open(flow_dest, "w", encoding="utf-8") as f:
        f.write(flow_text)
    if msg_name:
        msg_dest = os.path.join(os.path.dirname(flow_dest), msg_name)
        with open(msg_dest, "w", encoding="utf-8") as f:
            f.write(build_msg_text(plan))

    dummy_path = None
    for c in containers:
        candidate = os.path.join(mod_root, "P5REssentials", "CPK", c, plan["rel"].replace("/", os.sep))
        if os.path.exists(candidate):
            dummy_path = candidate
            break
    if dummy_path:
        open(dummy_path, "wb").close()
    else:
        print(f"  WARNING: no raw-fallback dummy found in any container for {plan['rel']}")
    return flow_dest, msg_name
