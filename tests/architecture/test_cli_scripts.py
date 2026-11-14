"""Modules that are libraries AND command-line programs must stay runnable as programs.

A script like ``zyngine/zynthian_lv2.py`` is imported by the UI but is also launched directly from shell
scripts / cron / by hand (``./zynthian_lv2.py presets``). That only works while:

* its FIRST line is a Python interpreter shebang,
* the file has the executable bit (on disk, and recorded as 100755 in git: a checkout on a filesystem or
  with ``core.fileMode=false`` can silently drop it), and
* the CLI part sits behind ``if __name__ == "__main__"`` so importing it as a library has no side effects.

Static checks only: the scripts are never executed (their CLI modes rewrite caches / config files).
To protect another dual-use script, add its path to ``CLI_SCRIPTS``.
"""

import ast
import os
import shutil
import subprocess
import sys

import pytest

from tests.bootstrap import REPO_ROOT

CLI_SCRIPTS = [
    "zyngine/zynthian_lv2.py",
]

# Accepted interpreter lines: what the repo's other scripts use.
SHEBANGS = ("#!/usr/bin/env python3", "#!/usr/bin/python3")

pytestmark = pytest.mark.unit


def _path(rel):
    path = REPO_ROOT / rel
    assert path.is_file(), f"{rel} is listed in CLI_SCRIPTS but does not exist"
    return path


@pytest.mark.parametrize("rel", CLI_SCRIPTS)
def test_first_line_is_a_python_interpreter_shebang(rel):
    with open(_path(rel), "rb") as f:
        first = f.readline().decode("utf-8", "replace").rstrip("\r\n")
    assert first in SHEBANGS, (
        f"{rel}: first line must be one of {SHEBANGS} so it can run as ./{os.path.basename(rel)}; got {first!r}")


@pytest.mark.parametrize("rel", CLI_SCRIPTS)
def test_shebang_interpreter_exists(rel):
    with open(_path(rel), "rb") as f:
        first = f.readline().decode().strip()
    interpreter = first[2:].split()
    exe = interpreter[1] if interpreter[0].endswith("/env") else interpreter[0]
    assert shutil.which(exe) or os.path.exists(exe), f"{rel}: interpreter {exe!r} not found"


@pytest.mark.parametrize("rel", CLI_SCRIPTS)
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_file_is_executable(rel):
    path = _path(rel)
    assert os.access(path, os.X_OK), f"{rel} is not executable: chmod +x {rel}"
    assert path.stat().st_mode & 0o100, f"{rel}: owner execute bit missing"


@pytest.mark.parametrize("rel", CLI_SCRIPTS)
def test_git_records_the_executable_bit(rel):
    """The mode committed in git (what a fresh clone / deploy gets) must be 100755."""
    if shutil.which("git") is None or not (REPO_ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    out = subprocess.run(["git", "ls-files", "-s", "--", rel], cwd=REPO_ROOT,
                         capture_output=True, text=True, check=False).stdout.split()
    if not out:
        pytest.skip(f"{rel} is not tracked by git yet")
    assert out[0] == "100755", f"{rel} is committed with mode {out[0]}: git update-index --chmod=+x {rel}"


@pytest.mark.parametrize("rel", CLI_SCRIPTS)
def test_cli_code_is_behind_a_main_guard(rel):
    """Importing the library must not run the CLI part (it would regenerate caches on every import)."""
    tree = ast.parse(_path(rel).read_text(encoding="utf-8"))

    def is_main_guard(node):
        if not (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)):
            return False
        names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
        consts = {n.value for n in ast.walk(node.test) if isinstance(n, ast.Constant)}
        return "__name__" in names and "__main__" in consts

    assert any(is_main_guard(node) for node in tree.body), (
        f"{rel}: no top-level `if __name__ == '__main__':` block; it is meant to run as a program")
