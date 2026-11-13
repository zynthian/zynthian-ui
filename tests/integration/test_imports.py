"""Import smoke tests: the core can be imported with no hardware, JACK or display.

Two flavours:

* in-process - every module of the core packages imports (catches syntax errors, bad imports,
  accidental import-time hardware access);
* fresh interpreter - key modules imported FIRST, to expose import-order dependencies
  (circular imports) that in-process tests hide.
"""

import ctypes
import importlib
import os
import pkgutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SKIP_NAMES = {"unit_tests", "test", "jacktest", "format_docs"}  # scripts with import-time side effects


def discover(package):
    pkg = importlib.import_module(package)
    for m in pkgutil.walk_packages(pkg.__path__, prefix=package + "."):
        if m.name.rsplit(".", 1)[-1] in SKIP_NAMES:
            continue
        yield m.name


ALL_MODULES = [m for p in ("zyngine", "zynconf", "zynautoconnect", "zyngui", "zynlibs")
               for m in discover(p)]


@pytest.mark.parametrize("name", ALL_MODULES)
def test_module_imports(name):
    try:
        importlib.import_module(name)
    except ModuleNotFoundError as e:
        top = (e.name or "").split(".")[0]
        if top in {"zyngine", "zyngui", "zynlibs", "zynconf", "zynautoconnect", "zyncoder", "tests"}:
            raise  # our own module is missing: a real failure
        pytest.skip(f"optional third-party dependency not installed: {e.name}")


# ---------------------------------------------------------------------------
# Hermeticity of the harness itself
# ---------------------------------------------------------------------------

def test_harness_blocks_jack_autostart():
    assert os.environ.get("JACK_NO_START_SERVER") == "1"


def test_native_libraries_are_faked(native_libs):
    lib = ctypes.cdll.LoadLibrary("/zynthian/zynthian-ui/zynlibs/zynseq/build/libzynseq.so")
    assert lib is native_libs["libzynseq.so"]
    assert not Path("/proc/self/maps").read_text().count("libzynseq.so")


def test_state_manager_module_uses_fake_zyncore(zyncore):
    from zyngine import zynthian_state_manager as _  # noqa: F401  (class shadows module; just ensure import works)
    mod = sys.modules["zyngine.zynthian_state_manager"]
    assert mod.lib_zyncore is zyncore


# ---------------------------------------------------------------------------
# Import-order independence (fresh interpreter)
# ---------------------------------------------------------------------------

CYCLE = "circular import (state manager <-> chain manager / legacy snapshot); fix in refactoring phase 2"

FIRST_IMPORTS = [
    "zyngine",
    "zyngine.zynthian_controller",
    "zyngine.zynthian_processor",
    "zyngine.zynthian_chain",
    "zyngine.zynthian_midi_filter",
    "zyngine.zynthian_signal_manager",
    "zyngine.zynthian_state_manager",
    "zyngine.ctrldev.zynthian_ctrldev_base",
    "zynconf",
    "zynautoconnect",
    "zyngui.zynthian_gui_config",
    "zyngui.zynthian_gui_base",
    pytest.param("zyngine.zynthian_chain_manager", marks=pytest.mark.xfail(strict=True, reason=CYCLE)),
    pytest.param("zyngine.zynthian_legacy_snapshot", marks=pytest.mark.xfail(strict=True, reason=CYCLE)),
]


@pytest.mark.parametrize("name", FIRST_IMPORTS)
def test_module_imports_first_in_fresh_interpreter(name):
    code = (f"import sys; sys.path.insert(0, {str(REPO)!r})\n"
            f"import tests.bootstrap\nimport importlib\nimportlib.import_module({name!r})\n")
    env = dict(os.environ, PYTHONWARNINGS="ignore")
    proc = subprocess.run([sys.executable, "-c", code], cwd=REPO, env=env,
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-1500:]
