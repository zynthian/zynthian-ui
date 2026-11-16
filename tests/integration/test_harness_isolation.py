"""The suite must be safe to run ON a Zynthian (or with zynthian_envars.sh sourced).

Regression: a run on a device whose shell exported ZYNTHIAN_CONFIG_DIR=/zynthian/config
overwrote the real zynthian_envars.sh, wiring profile and jalv/plugins.json with the
bootstrap stubs. tests/bootstrap.py now drops every inherited ZYNTHIAN_* variable and
tests/write_guard.py refuses writes to real locations.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests import bootstrap, write_guard

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[2]


# --- in-process: the live environment ----------------------------------------
def test_zynthian_dirs_point_to_the_sandbox():
    for var in ("ZYNTHIAN_DIR", "ZYNTHIAN_CONFIG_DIR", "ZYNTHIAN_MY_DATA_DIR", "ZYNTHIAN_EX_DATA_DIR",
                "ZYNTHIAN_DATA_DIR", "ZYNTHIAN_SYS_DIR", "ZYNTHIAN_SW_DIR", "ZYNTHIAN_HELP_DIR"):
        assert Path(os.environ[var]).is_relative_to(bootstrap.SANDBOX), var


def test_production_modules_read_the_sandbox_config():
    from zynconf import zynthian_config
    assert Path(zynthian_config.config_fpath).is_relative_to(bootstrap.SANDBOX)


@pytest.mark.parametrize("path", ["/zynthian/config/zynthian_envars.sh", "/zynthian/zynthian-my-data/snapshots/x.zss",
                                  "/boot/firmware/config.txt", "/etc/hostname"])
def test_real_zynthian_locations_are_protected(path):
    assert write_guard.is_protected(path)


def test_sandbox_tmp_and_repo_are_writable(tmp_path):
    for path in (bootstrap.SANDBOX / "config" / "x", tmp_path / "x", REPO / "tests" / "native" / "build" / "x"):
        assert not write_guard.is_protected(path), path


@pytest.fixture
def guarded_dir(tmp_path, monkeypatch):
    """A protected directory inside tmp_path (more specific than the allowed /tmp)."""
    real = tmp_path / "real"
    real.mkdir()
    (real / "keep.txt").write_text("original")
    monkeypatch.setattr(write_guard, "_protected", write_guard._protected + (str(real),))
    n = len(write_guard.VIOLATIONS)
    yield real
    del write_guard.VIOLATIONS[n:]  # expected violations: don't let the autouse check fail the test


@pytest.mark.parametrize("op", [
    lambda d: open(d / "keep.txt", "w"),
    lambda d: open(d / "keep.txt", "a"),
    lambda d: open(d / "keep.txt", "r+"),
    lambda d: (d / "new.txt").write_text("x"),
    lambda d: os.open(d / "keep.txt", os.O_WRONLY | os.O_TRUNC),
    lambda d: os.remove(d / "keep.txt"),
    lambda d: os.replace(d / "keep.txt", d / "moved.txt"),
    lambda d: os.mkdir(d / "sub"),
    lambda d: __import__("shutil").rmtree(d),
    lambda d: __import__("shutil").copyfile(d / "keep.txt", d / "copy.txt"),
], ids=["w", "a", "r+", "write_text", "os.open", "remove", "replace", "mkdir", "rmtree", "copyfile"])
def test_writes_to_protected_dirs_are_refused(guarded_dir, op):
    with pytest.raises(write_guard.WriteGuardError):
        op(guarded_dir)
    assert write_guard.VIOLATIONS
    assert sorted(p.name for p in guarded_dir.iterdir()) == ["keep.txt"]
    assert (guarded_dir / "keep.txt").read_text() == "original"


def test_dir_fd_relative_writes_in_protected_dirs_are_refused(guarded_dir, tmp_path, monkeypatch):
    """os.remove(name, dir_fd=...) (as used by shutil.rmtree) is checked in the dir_fd's folder, not the cwd."""
    monkeypatch.chdir(tmp_path)
    fd = os.open(guarded_dir, os.O_RDONLY)
    try:
        with pytest.raises(write_guard.WriteGuardError):
            os.remove("keep.txt", dir_fd=fd)
    finally:
        os.close(fd)
    assert (guarded_dir / "keep.txt").read_text() == "original"


def test_dir_fd_relative_name_matching_a_protected_link_in_cwd_is_allowed(guarded_dir, tmp_path, monkeypatch):
    """A temporary folder named like a symlink of the cwd that points to a protected folder
    (e.g. zynthian-ui/help -> ../zynthian-help) must still be removable relative to its parent."""
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    (cwd / "alias").symlink_to(guarded_dir)
    monkeypatch.chdir(cwd)
    parent = tmp_path / "old"
    (parent / "alias").mkdir(parents=True)
    n = len(write_guard.VIOLATIONS)
    fd = os.open(parent, os.O_RDONLY)
    try:
        os.rmdir("alias", dir_fd=fd)
    finally:
        os.close(fd)
    assert not (parent / "alias").exists()
    assert len(write_guard.VIOLATIONS) == n
    assert (guarded_dir / "keep.txt").exists()


def test_reading_protected_dirs_is_allowed(guarded_dir):
    n = len(write_guard.VIOLATIONS)
    assert (guarded_dir / "keep.txt").read_text() == "original"
    assert [p.name for p in guarded_dir.iterdir()] == ["keep.txt"]
    guarded_dir.mkdir(exist_ok=True)  # no-op on an existing dir
    assert len(write_guard.VIOLATIONS) == n


# --- fresh interpreter: a shell with a real Zynthian environment ----------------
CHILD = r"""
import json, os, sys
sys.path.insert(0, sys.argv[1])
import tests.bootstrap as b
from tests import write_guard
from zynconf import zynthian_config as zc
out = {"config_dir": os.environ["ZYNTHIAN_CONFIG_DIR"], "fpath": zc.config_fpath,
       "test_var_kept": os.environ.get("ZYNTHIAN_TEST_SENTINEL"),
       "inherited": sorted(b.INHERITED_ZYNTHIAN_ENV)}
zc.save_config({"ZYNTHIAN_UI_COLOR_BG": "#123456"})   # production write: must land in the sandbox
try:
    open(sys.argv[2] + "/zynthian_envars.sh", "w")   # direct write to the real config
    out["direct"] = "written"
except write_guard.WriteGuardError:
    out["direct"] = "refused"
print(json.dumps(out))
"""


def test_inherited_zynthian_environment_is_ignored(tmp_path):
    real = tmp_path / "zynthian"
    config = real / "config"
    (config / "wiring-profiles").mkdir(parents=True)
    (config / "jalv").mkdir()
    files = {config / "zynthian_envars.sh": 'export ZYNTHIAN_KIT_VERSION="V5"\n',
             config / "wiring-profiles" / "v5": 'ZYNTHIAN_WIRING_LAYOUT="V5"\n',
             config / "jalv" / "plugins.json": '{"real": 1}\n'}
    for f, text in files.items():
        f.write_text(text)
    env = dict(os.environ,
               ZYNTHIAN_DIR=str(real), ZYNTHIAN_CONFIG_DIR=str(config),
               ZYNTHIAN_MY_DATA_DIR=str(real / "zynthian-my-data"), ZYNTHIAN_SYS_DIR=str(real / "zynthian-sys"),
               ZYNTHIAN_KIT_VERSION="V5", ZYNTHIAN_TEST_SENTINEL="kept")
    proc = subprocess.run([sys.executable, "-c", CHILD, str(REPO), str(config)], env=env, cwd=tmp_path,
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout.strip().splitlines()[-1])

    assert not Path(out["config_dir"]).is_relative_to(real)
    assert not Path(out["fpath"]).is_relative_to(real)
    assert out["direct"] == "refused"
    assert out["test_var_kept"] == "kept"
    assert {"ZYNTHIAN_CONFIG_DIR", "ZYNTHIAN_KIT_VERSION"} <= set(out["inherited"])
    for f, text in files.items():
        assert f.read_text() == text, f"{f} was modified"
    assert sorted(p.name for p in config.iterdir()) == ["jalv", "wiring-profiles", "zynthian_envars.sh"]
