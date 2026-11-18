"""zyngine.zynthian_engine_setbfree start(): the busy state ends also when the start fails."""

import sys

import pytest

import zyngine.zynthian_engine_setbfree  # noqa: F401 (the module: zyngine/__init__ star-imports the classes)


class FakeStateManager:
    def __init__(self):
        self.busy = set()

    def start_busy(self, clid, message=None, details=None, tts=True):
        self.busy.add(clid)

    def end_busy(self, clid):
        self.busy.discard(clid)


def test_a_failing_setbfree_start_does_not_leave_zynthian_busy():
    mod = sys.modules["zyngine.zynthian_engine_setbfree"]
    eng = mod.zynthian_engine_setbfree.__new__(mod.zynthian_engine_setbfree)
    eng.state_manager = FakeStateManager()

    def failing_start():
        assert eng.state_manager.busy == {"setBfree"}
        raise RuntimeError("setBfree exited")  # as a process that ends before its prompt

    eng._start = failing_start
    with pytest.raises(RuntimeError):
        eng.start()
    assert eng.state_manager.busy == set()
