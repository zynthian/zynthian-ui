"""zyngine.zynthian_engine_aeolus start(): the busy state ends also when Aeolus fails.

A fake "aeolus" executable on PATH stands in for the engine; the engine object is made without
__init__ (that reads the stops directory and presets), with only what start() uses."""

import os
import socket
import sys
import time
from types import SimpleNamespace

import pexpect
import pytest

import zyngine.zynthian_engine_aeolus  # noqa: F401 (the module, see aeolus_module())

PY = sys.executable


def aeolus_module():
    """zyngine/__init__ star-imports the engine classes, so go via sys.modules"""
    return sys.modules["zyngine.zynthian_engine_aeolus"]


class FakeStateManager:
    def __init__(self):
        self.busy = set()
        self.fine_tuning_freq = 440.0
        self.chain_manager = SimpleNamespace(set_active_chain_by_id=lambda chain_id: None,
                                             get_chain=lambda chain_id: None)

    def start_busy(self, clid, message=None, details=None, tts=True):
        self.busy.add(clid)

    def end_busy(self, clid):
        self.busy.discard(clid)


def fake_aeolus(tmp_path, body):
    """An executable "aeolus" in tmp_path: writes its arguments to tmp_path/args, then runs body"""
    path = tmp_path / "aeolus"
    path.write_text(f"#!{PY}\nimport sys, time, socket\n"
                    f"open({str(tmp_path / 'args')!r}, 'w').write(' '.join(sys.argv[1:]))\n" + body)
    path.chmod(0o755)
    return path


def make_engine(tmp_path, monkeypatch):
    mod = aeolus_module()
    eng = mod.zynthian_engine_aeolus.__new__(mod.zynthian_engine_aeolus)
    eng.name = "Aeolus"
    eng.state_manager = FakeStateManager()
    eng.processors = [SimpleNamespace(midi_chan=0, chain_id=1)]
    eng.keyboard_config = 0  # no manuals to set up
    eng.temperament = eng.current_temperament = 1
    eng.current_tuning_freq = 440.0  # as the state manager's: no /retune
    eng.stops_fpath = str(tmp_path)
    # A free port nobody listens on: zynthian's messages to Aeolus go nowhere
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        eng.osc_target_port = s.getsockname()[1]
    eng.osc_proto = sys.modules["zyngine.zynthian_engine"].liblo.UDP
    eng.osc_server = None
    eng.osc_server_port = None
    eng.proc = None
    eng.proc_timeout = 5
    eng.command_env = dict(os.environ, PATH=f"{tmp_path}:{os.environ.get('PATH', '')}", TERM="dumb")
    eng.command_cwd = None
    eng.get_current_config = lambda: None
    eng.config_remote_display = lambda: False
    eng.set_midi_chan = lambda processor=None: None
    monkeypatch.setattr(mod.zynautoconnect, "request_midi_connect", lambda *a, **k: None)
    monkeypatch.setattr(mod.zynautoconnect, "request_audio_connect", lambda *a, **k: None)
    return eng


def wait_for(cond, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def test_a_failing_aeolus_does_not_leave_zynthian_busy(tmp_path, monkeypatch):
    # As the Nura aeolus that exits during the start: its output ends before "Ready"
    fake_aeolus(tmp_path, "print('Aeolus starting'); sys.exit(1)\n")
    eng = make_engine(tmp_path, monkeypatch)
    try:
        with pytest.raises(pexpect.EOF):
            eng.start()
        assert eng.state_manager.busy == set()
    finally:
        eng.stop()
