"""zynconf.zynthian_config: the envars files shared by the UI and webconf (save / plain parsing / MIDI profile).

load_config() sources the file with bash, so it is not covered here (the default run starts no process);
save_config() and load_plain_envars() are pure file manipulation.
"""

import os

import pytest

pytestmark = pytest.mark.unit

ENVARS = """#!/bin/bash
# Zynthian config
export ZYNTHIAN_UI_COLOR_BG="#000000"
export ZYNTHIAN_AUDIO_CHANNELS="2"

# Directory Paths
export ZYNTHIAN_DIR="/zynthian"
"""


@pytest.fixture
def zc(monkeypatch):
    from zynconf import zynthian_config
    return zynthian_config


@pytest.fixture
def envars(tmp_path, monkeypatch):
    path = tmp_path / "zynthian_envars.sh"
    path.write_text(ENVARS)
    for name in ("ZYNTHIAN_UI_COLOR_BG", "ZYNTHIAN_AUDIO_CHANNELS", "ZYNTHIAN_NEW_VAR", "ZYNTHIAN_DIR"):
        monkeypatch.setenv(name, os.environ.get(name, ""))       # restored after the test
    return path


def test_load_plain_envars(zc, envars):
    cfg = zc.load_plain_envars(str(envars), set_env=False)
    assert cfg == {"ZYNTHIAN_UI_COLOR_BG": "#000000", "ZYNTHIAN_AUDIO_CHANNELS": "2", "ZYNTHIAN_DIR": "/zynthian"}


def test_load_plain_envars_accepts_lines_without_export_and_single_quotes(zc, tmp_path):
    path = tmp_path / "plain.sh"
    path.write_text("A=1\nexport B='two'\nlocal C=3\n# D=4\n")
    assert zc.load_plain_envars(str(path), set_env=False) == {"A": "1", "B": "two"}


def test_load_plain_envars_sets_the_environment(zc, envars):
    zc.load_plain_envars(str(envars))
    assert os.environ["ZYNTHIAN_AUDIO_CHANNELS"] == "2"


def test_save_config_updates_existing_variables_in_place(zc, envars):
    zc.save_config({"ZYNTHIAN_AUDIO_CHANNELS": "4"}, fpath=str(envars))
    text = envars.read_text()
    assert 'export ZYNTHIAN_AUDIO_CHANNELS="4"\n' in text
    assert text.count("ZYNTHIAN_AUDIO_CHANNELS") == 1
    assert text.index("ZYNTHIAN_UI_COLOR_BG") < text.index("ZYNTHIAN_AUDIO_CHANNELS")   # order kept
    assert os.environ["ZYNTHIAN_AUDIO_CHANNELS"] == "4"


def test_save_config_adds_new_variables_before_the_directory_paths(zc, envars):
    zc.save_config({"ZYNTHIAN_NEW_VAR": "x"}, fpath=str(envars))
    lines = envars.read_text().splitlines()
    new = lines.index('export ZYNTHIAN_NEW_VAR="x"')
    assert new < lines.index("# Directory Paths")


def test_save_config_escapes_newlines_and_drops_carriage_returns(zc, envars):
    zc.save_config({"ZYNTHIAN_NEW_VAR": "line1\nline2\r"}, fpath=str(envars))
    assert 'export ZYNTHIAN_NEW_VAR="line1\\nline2"\n' in envars.read_text()


def test_save_then_load_round_trip(zc, envars):
    zc.save_config({"ZYNTHIAN_AUDIO_CHANNELS": "8", "ZYNTHIAN_NEW_VAR": "hello world"}, fpath=str(envars))
    cfg = zc.load_plain_envars(str(envars), set_env=False)
    assert cfg["ZYNTHIAN_AUDIO_CHANNELS"] == "8" and cfg["ZYNTHIAN_NEW_VAR"] == "hello world"


def test_update_midi_profile_moves_only_midi_variables(zc, tmp_path, monkeypatch):
    profile = tmp_path / "default.sh"
    profile.write_text('export ZYNTHIAN_MIDI_FILTER_RULES=""\n')
    monkeypatch.setenv("ZYNTHIAN_MIDI_FILTER_RULES", "")
    monkeypatch.setenv("ZYNTHIAN_MIDI_PRESET_PRELOAD_NOTEON", "")
    params = {"ZYNTHIAN_MIDI_FILTER_RULES": ["IGNORE CH#1 CC#7"], "ZYNTHIAN_MIDI_PRESET_PRELOAD_NOTEON": "1",
              "ZYNTHIAN_UI_COLOR_BG": "#ffffff"}
    zc.update_midi_profile(params, fpath=str(profile))
    assert params == {"ZYNTHIAN_UI_COLOR_BG": "#ffffff"}             # MIDI ones consumed
    saved = zc.load_plain_envars(str(profile), set_env=False)
    assert saved == {"ZYNTHIAN_MIDI_FILTER_RULES": "IGNORE CH#1 CC#7", "ZYNTHIAN_MIDI_PRESET_PRELOAD_NOTEON": "1"}


def test_get_midi_config_fpath_uses_the_profile_envar(zc, tmp_path, monkeypatch):
    profile = tmp_path / "custom.sh"
    profile.write_text("")
    monkeypatch.setenv("ZYNTHIAN_SCRIPT_MIDI_PROFILE", str(profile))
    assert zc.get_midi_config_fpath() == str(profile)


def test_external_storage_lists_only_writable_mount_points(zc, tmp_path):
    (tmp_path / "not_a_mount").mkdir()
    assert zc.get_external_storage_dirs(str(tmp_path)) == []
    assert zc.get_external_storage_dirs(str(tmp_path / "missing")) == []
