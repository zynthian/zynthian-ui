# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_mainloop_lock)
#
# Locks and waits for the Tk main thread that don't deadlock with Tk calls from other threads
#
# Copyright (C) 2026 Brian Walton <riban@zynthian.org>
#
# ******************************************************************************
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the LICENSE.txt file.
#
# ******************************************************************************

# Tkinter runs every Tk call in the main thread: a Tk call from another thread is queued to the main
# thread and the calling thread waits until the main thread has run it. So if the main thread waits for
# something (a lock, a thread) that is held by a thread that makes a Tk call, both wait forever.
# E.g. the busy thread held the screen lock while updating the loading screen, and the main thread waited
# for that lock in show_screen after "clean all" from the main menu.
#
# The waits here service the Tk calls of other threads while they wait in the main thread, so those
# threads can go on and release what the main thread waits for. Only the calls queued by other threads
# are run while waiting: window events, timers (after) and idle callbacks wait for the main loop, so no
# other UI code runs in the middle of the waiting code. In other threads they wait as usual.
#
# Use MainLoopLock for any lock that the main thread may wait for while a thread that holds it may make Tk
# calls (directly or through code it calls, e.g. signal handlers), and join() to wait for such a thread.
#
# Tk is not imported here (the core doesn't depend on the UI toolkit): zynthian_gui registers the Tk
# interpreter with set_tk() at startup. Before that (or without a UI, e.g. in tests) the waits are plain ones.

import threading
from time import monotonic

# Tk interpreter of the main thread, and what one dooneevent() call services: only the events queued by
# other threads (their Tk calls). Window events stay queued: those are only run with WINDOW_EVENTS. Timers
# and idle callbacks need TIMER_EVENTS / IDLE_EVENTS. FILE_EVENTS is only there because no event flag
# means "all events": it reads pending X events into the queue (still not run) and would run Tk file
# handlers (createfilehandler), which zynthian doesn't use.
_tkapp = None
_main_thread_id = None
TCL_DONT_WAIT = 2  # = _tkinter.DONT_WAIT
TCL_FILE_EVENTS = 8  # = _tkinter.FILE_EVENTS
PUMP_FLAGS = TCL_DONT_WAIT | TCL_FILE_EVENTS

# Longest time the main thread waits without servicing the Tk calls of other threads (s)
PUMP_INTERVAL = 0.001


def set_tk(tkapp):
    """Register the Tk interpreter (e.g. root.tk). Must be called from the main (Tk) thread."""

    global _tkapp, _main_thread_id
    _main_thread_id = threading.get_ident()
    _tkapp = tkapp


def unset_tk():
    """Unregister the Tk interpreter: all the waits are plain waits afterwards"""

    global _tkapp, _main_thread_id
    _tkapp = None
    _main_thread_id = None


def in_main_thread():
    """True if called from the registered Tk main thread"""

    return _tkapp is not None and threading.get_ident() == _main_thread_id


def pump():
    """Run the Tk calls queued by other threads, if called from the main thread. Doesn't wait."""

    if in_main_thread():
        try:
            while _tkapp.dooneevent(PUMP_FLAGS):
                pass
        except Exception:
            pass  # Tk destroyed (exit)


def wait(done, timeout=None):
    """Wait until done(PUMP_INTERVAL) returns True, servicing the Tk calls of other threads meanwhile.

    done : function(timeout) => True when the wait is over. It may block up to timeout seconds.
    timeout : maximum time to wait in seconds, None to wait forever
    Returns : True if done, False on timeout
    """

    deadline = None if timeout is None else monotonic() + timeout
    while True:
        pump()
        if deadline is None:
            if done(PUMP_INTERVAL):
                return True
        else:
            left = deadline - monotonic()
            if done(max(0, min(PUMP_INTERVAL, left))):
                return True
            if left <= 0:
                return False


def join(thread, timeout=None):
    """Thread.join() that doesn't block the Tk calls of other threads when called from the main thread"""

    if not in_main_thread():
        thread.join(timeout)
        return
    wait(lambda t: thread.join(t) or not thread.is_alive(), timeout)


class MainLoopLock:
    """Lock (or RLock) that keeps servicing the Tk calls of other threads while the main thread waits for it.

    Same interface as threading.Lock / RLock: acquire(blocking, timeout), release(), with-statement.
    """

    def __init__(self, reentrant=True):
        self._lock = threading.RLock() if reentrant else threading.Lock()

    def acquire(self, blocking=True, timeout=-1):
        if not blocking or not in_main_thread():
            return self._lock.acquire(blocking, timeout)
        if self._lock.acquire(False):
            return True
        return wait(lambda t: self._lock.acquire(timeout=t), None if timeout < 0 else timeout)

    def release(self):
        self._lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()

# ------------------------------------------------------------------------------
