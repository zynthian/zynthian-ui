"""zyngine.zynthian_mainloop_lock: waits in the Tk main thread service other threads' Tk calls.

A fake Tk interpreter stands for the real one: its dooneevent() counts the calls and runs the
"Tk calls" queued by other threads. The real Tk case is in tests/gui/test_mainloop_lock_tk.py.
"""

import queue
import threading
import time

import pytest

from zyngine import zynthian_mainloop_lock as mll

TIMEOUT = 2.0


class FakeTkapp:
    """dooneevent() runs one queued call, like Tk running a call queued by another thread"""

    def __init__(self):
        self.calls = queue.SimpleQueue()
        self.pumps = 0
        self.flags = set()

    def dooneevent(self, flags):
        self.pumps += 1
        self.flags.add(flags)
        try:
            fn, done = self.calls.get_nowait()
        except queue.Empty:
            return 0
        fn()
        done.set()
        return 1

    def call_from_thread(self, fn):
        """What a Tk call from another thread does: queue it and wait until the main thread runs it"""
        done = threading.Event()
        self.calls.put((fn, done))
        return done.wait(TIMEOUT)


@pytest.fixture
def tkapp():
    app = FakeTkapp()
    mll.set_tk(app)
    yield app
    mll.unset_tk()


def test_without_tk_it_is_a_plain_lock():
    mll.unset_tk()
    lock = mll.MainLoopLock()
    assert not mll.in_main_thread()
    with lock:
        with lock:  # reentrant by default
            pass
    assert lock.acquire(timeout=0.01)
    lock.release()


def test_in_main_thread_only_for_the_registering_thread(tkapp):
    assert mll.in_main_thread()
    seen = []
    t = threading.Thread(target=lambda: seen.append(mll.in_main_thread()))
    t.start()
    t.join(TIMEOUT)
    assert seen == [False]


def test_pump_only_services_calls_from_other_threads(tkapp):
    import _tkinter
    mll.pump()
    # No window, timer or idle events: only what other threads queued (and FILE_EVENTS, see module)
    assert tkapp.flags == {_tkinter.DONT_WAIT | _tkinter.FILE_EVENTS}


def test_main_thread_runs_holder_tk_calls_while_waiting(tkapp):
    """The clean all freeze: holder makes a Tk call while the main thread waits for the lock."""
    lock = mll.MainLoopLock()
    holding = threading.Event()
    result = {}

    def holder():
        with lock:
            holding.set()
            time.sleep(0.05)  # the main thread is waiting for the lock now
            result["tk_call_done"] = tkapp.call_from_thread(lambda: result.setdefault("ran", True))

    t = threading.Thread(target=holder)
    t.start()
    assert holding.wait(TIMEOUT)
    assert lock.acquire(timeout=TIMEOUT)  # a plain RLock would time out: holder waits for us
    lock.release()
    t.join(TIMEOUT)
    assert result == {"tk_call_done": True, "ran": True}


def test_other_threads_wait_without_pumping(tkapp):
    lock = mll.MainLoopLock()
    got = []
    with lock:
        t = threading.Thread(target=lambda: got.append(lock.acquire(timeout=0.05)))
        t.start()
        t.join(TIMEOUT)
    assert got == [False]
    assert tkapp.pumps == 0


def test_acquire_timeout_in_main_thread(tkapp):
    lock = mll.MainLoopLock()
    holding, release = threading.Event(), threading.Event()

    def holder():
        with lock:
            holding.set()
            release.wait(TIMEOUT)

    t = threading.Thread(target=holder)
    t.start()
    assert holding.wait(TIMEOUT)
    t0 = time.monotonic()
    assert not lock.acquire(timeout=0.05)
    assert 0.04 <= time.monotonic() - t0 < 1
    assert tkapp.pumps > 0
    assert not lock.acquire(blocking=False)
    release.set()
    t.join(TIMEOUT)


def test_reentrant_in_main_thread(tkapp):
    lock = mll.MainLoopLock()
    with lock:
        with lock:
            pass
    assert tkapp.pumps == 0  # free lock: no waiting, no pumping


def test_non_reentrant_lock(tkapp):
    lock = mll.MainLoopLock(reentrant=False)
    with lock:
        assert not lock.acquire(timeout=0.01)


def test_join_runs_thread_tk_calls(tkapp):
    """Joining a thread that makes a Tk call: plain join() would wait forever."""
    done = []
    t = threading.Thread(target=lambda: done.append(tkapp.call_from_thread(lambda: None)))
    t.start()
    mll.join(t, TIMEOUT)
    assert not t.is_alive()
    assert done == [True]


def test_join_timeout(tkapp):
    stop = threading.Event()
    t = threading.Thread(target=lambda: stop.wait(TIMEOUT))
    t.start()
    t0 = time.monotonic()
    mll.join(t, 0.05)
    assert t.is_alive()
    assert time.monotonic() - t0 < 1
    stop.set()
    t.join(TIMEOUT)
