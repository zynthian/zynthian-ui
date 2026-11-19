"""zynlibs.zynseq.zynseq: the local transport client ids passed to libzynseq's transportStart/Stop/Toggle(uint8_t)."""

import pytest

from zynlibs.zynseq import zynseq as zynseq_module
from zynlibs.zynseq.zynseq import zynseq


class FakeLib:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        return lambda *args: self.calls.append((name, *args))


@pytest.fixture
def seq(monkeypatch):
    monkeypatch.setattr(zynseq_module, "TRANSPORT_CLIENT_IDS", dict(zynseq_module.TRANSPORT_CLIENT_IDS))
    s = zynseq.__new__(zynseq)
    s.libseq = FakeLib()
    return s


def test_named_clients_get_small_stable_ids(seq):
    seq.transport_start("zynsmf")
    seq.transport_stop("zynsmf")
    seq.transport_toggle("other")
    seq.transport_start("zynseq")
    ids = [call[1] for call in seq.libseq.calls]
    assert ids[0] == ids[1]
    assert ids[2] != ids[0]
    assert ids[3] == 1
    assert all(isinstance(i, int) and 0 < i <= 31 for i in ids)


def test_stop_all_uses_the_all_clients_id(seq):
    seq.transport_stop("ALL")
    assert seq.libseq.calls == [("transportStop", 255)]


def test_too_many_clients_are_refused(seq):
    for n in range(3, 32):
        seq.transport_start(f"client{n}")
    with pytest.raises(ValueError):
        seq.transport_start("one too many")
