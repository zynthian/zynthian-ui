"""Proves the GUI test plumbing works (Tk + a display). Real screen tests build on this.

Skipped automatically without a display; run with ``./run_tests.sh gui`` (xvfb) or in CI.
"""

import pytest

pytestmark = pytest.mark.gui


@pytest.fixture
def tk_root():
    import tkinter
    root = tkinter.Tk()
    root.geometry("320x240")
    yield root
    root.destroy()


def test_tk_root_opens_and_processes_events(tk_root):
    fired = []
    tk_root.after(1, lambda: fired.append(True))
    tk_root.update()
    tk_root.after(5, lambda: None)
    tk_root.update()
    assert fired == [True]
    assert tk_root.winfo_exists()


def test_synthetic_event_reaches_widget(tk_root):
    import tkinter
    got = []
    canvas = tkinter.Canvas(tk_root, width=100, height=100)
    canvas.pack()
    canvas.bind("<ButtonPress-1>", lambda e: got.append((e.x, e.y)))
    tk_root.update()
    canvas.event_generate("<ButtonPress-1>", x=10, y=20)
    tk_root.update()
    assert got == [(10, 20)]
