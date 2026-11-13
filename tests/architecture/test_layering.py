"""Layering rules between the core (zyngine, zynconf, zynautoconnect, zynlibs) and the UI (zyngui).

Target architecture: the core never imports the UI. Today ``zyngine`` still reaches into
``zyngui.zynthian_gui_config`` for settings, so this is a *ratchet*:

* A core file that is NOT in the allow-list below must not import ``zyngui`` (new violations fail).
* A file that is in the allow-list but no longer imports ``zyngui`` must be removed from it
  (so progress can't silently regress).

Static analysis only (``ast``): nothing is imported, so it needs no fakes and runs anywhere.
"""

import ast
import warnings
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# Phase 2 of the refactoring plan removes entries from this set. NEVER add to it.
KNOWN_CORE_TO_UI_IMPORTS = {
    "zyngine/ctrldev/zynthian_ctrldev_akai_apc_40_mk2.py",
    "zyngine/ctrldev/zynthian_ctrldev_akai_apc_key25_mk2.py",
    "zyngine/ctrldev/zynthian_ctrldev_base_ui.py",
    "zyngine/ctrldev/zynthian_ctrldev_launchkey_mini_mk3.py",
    "zyngine/ctrldev/zynthian_ctrldev_launchkey_mk3_88.py",
    "zyngine/ctrldev/zynthian_ctrldev_launchpad_mini_mk3.py",
    "zyngine/ctrldev/zynthian_ctrldev_launchpad_pro_mk2.py",
    "zyngine/ctrldev/zynthian_ctrldev_launchpad_pro_mk3.py",
    "zyngine/ctrldev/zynthian_ctrldev_launchpad_x.py",
    "zyngine/zynthian_audio_recorder.py",
    "zyngine/zynthian_chain_manager.py",
    "zyngine/zynthian_ctrldev_manager.py",
    "zyngine/zynthian_legacy_snapshot.py",
    "zyngine/zynthian_state_manager.py",
    "zyngine/zynthian_tts.py",
    "zynautoconnect/zynthian_autoconnect.py",
}

CORE_PACKAGES = ("zyngine", "zynconf", "zynautoconnect", "zynlibs")
UI_ROOTS = {"zyngui"}
GUI_TOOLKIT_ROOTS = {"tkinter", "PIL", "tkinterweb"}


def imported_roots(path):
    """Top-level package names imported anywhere in the file (including lazy, in-function imports)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # legacy invalid-escape SyntaxWarnings
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def core_files():
    for pkg in CORE_PACKAGES:
        for f in sorted((REPO / pkg).rglob("*.py")):
            if "__pycache__" in f.parts or "build" in f.parts:
                continue
            yield f


def violations(banned):
    found = set()
    for f in core_files():
        if imported_roots(f) & banned:
            found.add(f.relative_to(REPO).as_posix())
    return found


def test_core_does_not_import_ui_beyond_known_violations():
    new = violations(UI_ROOTS) - KNOWN_CORE_TO_UI_IMPORTS
    assert not new, (
        "Core modules must not import zyngui. Pass settings in (dependency injection) or use "
        f"zynsigman signals instead. New violations: {sorted(new)}")


def test_known_violation_list_is_not_stale():
    fixed = KNOWN_CORE_TO_UI_IMPORTS - violations(UI_ROOTS)
    assert not fixed, (
        f"These files no longer import zyngui - remove them from KNOWN_CORE_TO_UI_IMPORTS: {sorted(fixed)}")


@pytest.mark.parametrize("pkg", CORE_PACKAGES)
def test_core_does_not_import_gui_toolkits(pkg):
    bad = {f.relative_to(REPO).as_posix() for f in core_files()
           if f.relative_to(REPO).parts[0] == pkg and imported_roots(f) & GUI_TOOLKIT_ROOTS}
    assert not bad, f"{pkg} must stay toolkit-free: {sorted(bad)}"


def test_zynconf_is_a_leaf_package():
    """zynconf (config file handling) must not depend on the engine or the UI."""
    bad = {f.relative_to(REPO).as_posix() for f in (REPO / "zynconf").rglob("*.py")
           if imported_roots(f) & (UI_ROOTS | {"zyngine", "zynautoconnect"})}
    assert not bad, sorted(bad)
