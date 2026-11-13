# -*- coding: utf-8 -*-
"""Fixtures for tests that wire real core objects together (native layer faked).

``state_manager`` builds the real ``zynthian_state_manager`` (and with it the chain manager, mixer
wrapper, sequencer wrapper, ...). Two things outside the native libraries had to be stubbed because
the core has no abstraction for them yet - both are refactoring targets (see tests/README.md):

* ``zynautoconnect`` (JACK client + port scanning): every public function is replaced by a mock;
* ``subprocess``: the state manager shells out (``powersave_control.sh``, systemctl, ...). All
  process creation is blocked and recorded in ``fake_subprocess.commands`` so a test run can never
  touch the host system.
"""

import subprocess
import sys
import types
from unittest import mock

import pytest

CORE_PREFIXES = ("zyngine", "zynconf", "zynautoconnect", "zynlibs", "zyngui")
SUBPROCESS_NAMES = ("Popen", "check_output", "check_call", "call", "run", "getoutput", "getstatusoutput")


class FakeSubprocess:
    """Records every attempted command; returns empty output / success."""

    def __init__(self):
        self.commands = []
        self.outputs = {}  # substring of command -> bytes returned by check_output

    def _record(self, args):
        cmd = args[0] if args else ""
        self.commands.append(cmd)
        return cmd

    def check_output(self, *args, **kwargs):
        cmd = self._record(args)
        text = " ".join(cmd) if isinstance(cmd, (list, tuple)) else str(cmd)
        for key, out in self.outputs.items():
            if key in text:
                return out
        return "" if kwargs.get("text") or kwargs.get("universal_newlines") else b""

    def check_call(self, *args, **kwargs):
        self._record(args)
        return 0

    call = check_call

    def run(self, *args, **kwargs):
        self._record(args)
        return subprocess.CompletedProcess(args, 0, b"", b"")

    def getoutput(self, cmd):
        self._record((cmd,))
        return ""

    def getstatusoutput(self, cmd):
        self._record((cmd,))
        return 0, ""

    def Popen(self, *args, **kwargs):  # noqa: N802 (mirrors subprocess API)
        self._record(args)
        proc = mock.MagicMock(name="Popen")
        proc.returncode = 0
        proc.pid = 0
        proc.poll.return_value = 0
        proc.wait.return_value = 0
        proc.communicate.return_value = (b"", b"")
        proc.stdout.readline.return_value = b""
        proc.stdout.read.return_value = b""
        return proc


@pytest.fixture
def fake_subprocess(monkeypatch):
    """Block process creation everywhere in the core. Inspect ``fake_subprocess.commands``."""
    fake = FakeSubprocess()
    for name in SUBPROCESS_NAMES:
        monkeypatch.setattr(subprocess, name, getattr(fake, name))
    # Modules that did `from subprocess import check_output, Popen` hold their own references.
    for modname, mod in list(sys.modules.items()):
        if mod is None or not modname.startswith(CORE_PREFIXES):
            continue
        for name in SUBPROCESS_NAMES:
            if getattr(mod, name, None) is getattr(subprocess, name, None) or \
                    getattr(getattr(mod, name, None), "__module__", None) == "subprocess":
                monkeypatch.setattr(mod, name, getattr(fake, name))
    return fake


@pytest.fixture
def fake_autoconnect(monkeypatch):
    """Replace every public ``zynautoconnect`` function with a MagicMock (no JACK client needed)."""
    import zynautoconnect
    mocks = {}
    for name, value in list(vars(zynautoconnect).items()):
        if (isinstance(value, types.FunctionType) and value.__module__.startswith("zynautoconnect")
                and not name.startswith("_")):
            m = mock.MagicMock(name=f"zynautoconnect.{name}", return_value=0)
            monkeypatch.setattr(zynautoconnect, name, m)
            mocks[name] = m
    # Getters whose callers iterate / test membership need containers, not 0.
    for name, m in mocks.items():
        if name == "get_port_friendly_names":
            m.return_value = {}
        elif any(k in name for k in ("ports", "portnames", "devices")):
            m.return_value = []
    # Module-level device tables normally sized by zynautoconnect.init() (mocked above).
    cm = sys.modules["zyngine.zynthian_chain_manager"]
    monkeypatch.setattr(zynautoconnect, "devices_in", [None] * cm.NUM_MIDI_DEVS_IN)
    monkeypatch.setattr(zynautoconnect, "devices_in_mode", [None] * cm.NUM_MIDI_DEVS_IN)
    monkeypatch.setattr(zynautoconnect, "devices_out", [None] * cm.NUM_MIDI_DEVS_OUT)
    monkeypatch.setattr(zynautoconnect, "devices_out_name", [None] * cm.NUM_MIDI_DEVS_OUT)
    mocks["get_jackd_blocksize"].return_value = 1024
    mocks["get_jackd_samplerate"].return_value = 48000
    return types.SimpleNamespace(**mocks)


@pytest.fixture
def state_manager(zyncore, native_libs, fake_autoconnect, fake_subprocess, zynthian_dirs):
    """A real ``zynthian_state_manager`` running on the fakes. Stopped on teardown."""
    module = sys.modules["zyngine.zynthian_state_manager"]
    sm = module.zynthian_state_manager()
    yield sm
    try:
        sm.exit_flag = True
        for name in ("fast_thread", "slow_thread"):
            t = getattr(sm, name, None)
            if t is not None and t.is_alive():
                t.join(timeout=5)
    finally:
        sm.exit_flag = True
