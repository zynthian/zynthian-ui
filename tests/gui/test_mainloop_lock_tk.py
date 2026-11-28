"""zyngine.zynthian_mainloop_lock with a real Tk main loop.

Reproduces the "clean all" freeze: a thread holds the screen lock and makes Tk calls (which wait for
the main thread) while the main thread, in a Tk callback, waits for that lock.
"""

import threading
import time

import pytest

from zyngine import zynthian_mainloop_lock as mll

pytestmark = pytest.mark.gui

TIMEOUT = 3.0


@pytest.fixture
def tk_root():
    import tkinter
    root = tkinter.Tk()
    root.geometry("320x240")
    root.update()
    mll.set_tk(root.tk)
    yield root
    mll.unset_tk()
    root.destroy()


def run_in_mainloop(root, fn):
    """Run fn() from a Tk callback inside mainloop (Tk calls from threads need a running main loop)"""
    result = {}

    def cb():
        try:
            result["value"] = fn()
        except BaseException as e:
            result["error"] = e
        finally:
            root.quit()

    root.after(1, cb)
    root.after(int(TIMEOUT * 4000), root.quit)  # never hang the test run
    root.mainloop()
    if "error" in result:
        raise result["error"]
    return result.get("value")


def holder_scenario(root, lock, acquire):
    import tkinter
    label = tkinter.Label(root, text="-")
    label.pack()
    log = []
    holding = threading.Event()

    def holder():
        with lock:
            holding.set()
            time.sleep(0.1)  # the main thread waits for the lock now
            for i in range(50):
                label.config(text=str(i))  # Tk calls: run by the main thread
            log.append("holder done")

    def main():
        t = threading.Thread(target=holder, daemon=True)
        t.start()
        assert holding.wait(TIMEOUT)
        # These must not run while the main thread waits for the lock: only after it got it
        root.after(0, lambda: log.append("timer"))
        root.after_idle(lambda: log.append("idle"))
        root.bind("<<Probe>>", lambda e: log.append("window event"))  # root: mapped (an unmapped widget drops it)
        root.event_generate("<<Probe>>", when="tail")
        got = acquire(lock)
        if got:
            log.append("main got lock")
            lock.release()
        mll.join(t, TIMEOUT)
        return got

    got = run_in_mainloop(root, main)
    root.update()  # run what was deferred
    return got, log, label.cget("text")


def test_main_thread_waiting_for_lock_runs_holder_tk_calls(tk_root):
    got, log, text = holder_scenario(tk_root, mll.MainLoopLock(), lambda lk: lk.acquire(timeout=TIMEOUT))
    assert got
    assert text == "49"
    # Only the holder's Tk calls ran while waiting: UI events and callbacks waited for the main loop
    assert log[:2] == ["holder done", "main got lock"]
    assert sorted(log[2:]) == ["idle", "timer", "window event"]


def test_plain_lock_deadlocks(tk_root):
    """Control: the same scenario with threading.RLock only ends because acquire() times out."""
    got, log, _ = holder_scenario(tk_root, threading.RLock(), lambda lk: lk.acquire(timeout=0.5))
    assert not got
