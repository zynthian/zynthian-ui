"""zyngui.zynthian_gui_snapshot: bank handling on the file system."""

from types import SimpleNamespace

from zyngui.zynthian_gui_snapshot import zynthian_gui_snapshot


def make_screen(snapshot_dir, bank=None):
    screen = zynthian_gui_snapshot.__new__(zynthian_gui_snapshot)
    screen.sm = SimpleNamespace(snapshot_dir=str(snapshot_dir), snapshot_bank=bank)
    screen.update_list = lambda: None
    return screen


def test_deleting_the_current_bank_unselects_it(tmp_path):
    (tmp_path / "000").mkdir()
    (tmp_path / "001").mkdir()
    screen = make_screen(tmp_path, "001")
    screen.delete_bank("001")
    assert not (tmp_path / "001").exists()
    assert screen.sm.snapshot_bank is None
    assert screen.sm.snapshot_dir == str(tmp_path)
