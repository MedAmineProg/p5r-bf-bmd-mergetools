"""
Shared config helpers for the p5r-bf-bmd-mergetools scripts. No hardcoded machine paths --
everything comes from environment variables.

  P5R_MODS_ROOT   Path to Reloaded-II's Mods/ folder (the same value ModConverter's config
                  calls "ModsRoot"), e.g. C:/Users/you/Reloaded-II/Mods
  P5R_APPCONFIG   Optional. Path to Reloaded-II's Apps/p5r.exe/AppConfig.json. If unset, derived
                  from P5R_MODS_ROOT assuming the standard Reloaded-II layout (Mods/ and Apps/
                  as siblings under the same Reloaded-II install root).
"""
import os
import json


def mods_root() -> str:
    v = os.environ.get("P5R_MODS_ROOT")
    if not v:
        raise SystemExit(
            "Set P5R_MODS_ROOT to your Reloaded-II Mods/ folder before running this script "
            "(see scripts/README.md)."
        )
    return v


def appconfig_path() -> str:
    v = os.environ.get("P5R_APPCONFIG")
    if v:
        return v
    reloaded_root = os.path.dirname(mods_root().rstrip("\/"))
    return os.path.join(reloaded_root, "Apps", "p5r.exe", "AppConfig.json")


def get_enabled_mods() -> dict[str, str]:
    """Returns {mod_id: absolute_mod_dir} for every mod in Reloaded-II's EnabledMods list."""
    cfg_path = appconfig_path()
    if not os.path.isfile(cfg_path):
        raise SystemExit(
            f"AppConfig.json not found at {cfg_path} -- set P5R_APPCONFIG explicitly if your "
            f"Reloaded-II layout doesn't put Apps/ next to Mods/."
        )
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    root = mods_root()
    out = {}
    for mid in cfg.get("EnabledMods", []):
        d = os.path.join(root, mid)
        if os.path.isdir(d):
            out[mid] = d
    return out
