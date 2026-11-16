"""The test harness frees JACK registry entries leaked by dead test servers (tests/jacktest.py).

JACK2 has room for 8 servers; entries of servers killed before unregistering are only reclaimed
by jackd when a server with the same name starts, and test servers have unique names, so leaked
entries would pile up until jackd refuses to start ("Too many servers already active").
These tests work on a fake registry file, never on the real one.
"""

import os
import struct
import subprocess

import pytest

jacktest = pytest.importorskip("tests.jacktest")

ENTRY_SIZE = 4 + 257  # pid + name, as in jack_shm_server_t
HEADER = b"KCAJ" + b"\0" * 28


def dead_pid():
    proc = subprocess.Popen(["true"])
    proc.wait()
    return proc.pid


def make_registry(path, entries):
    """entries: list of (pid, name) where name is the full registry name, e.g. 'jack-1000:zyntest_1_a:'"""
    data = bytearray(HEADER)
    for pid, name in entries:
        entry = struct.pack("=i", pid) + name.encode()
        data += entry + b"\0" * (ENTRY_SIZE - len(entry))
    path.write_bytes(bytes(data))


def entry(path, i):
    data = path.read_bytes()
    offset = len(HEADER) + i * ENTRY_SIZE
    pid = struct.unpack_from("=i", data, offset)[0]
    name = data[offset + 4:offset + ENTRY_SIZE].split(b"\0")[0].decode()
    return pid, name


@pytest.fixture
def shm(tmp_path):
    (tmp_path / "shm").mkdir()
    return tmp_path


def reclaim(shm, **kwargs):
    return jacktest.reclaim_dead_test_servers(registry=str(shm / "jack-shm-registry"), shm_dir=str(shm / "shm"), **kwargs)


def test_dead_test_server_entry_is_freed_with_its_semaphores(shm):
    uid = os.getuid()
    pid = dead_pid()
    make_registry(shm / "jack-shm-registry", [(pid, f"jack-{uid}:zyntest_{pid}_abc123:")])
    sem = shm / "shm" / f"jack_sem.{uid}_zyntest_{pid}_abc123_system"
    other_sem = shm / "shm" / f"jack_sem.{uid}_zyntest_99_other_system"
    sem.write_text("")
    other_sem.write_text("")

    assert reclaim(shm) == [f"zyntest_{pid}_abc123"]
    assert entry(shm / "jack-shm-registry", 0) == (0, "")
    assert not sem.exists()
    assert other_sem.exists()


def test_live_and_foreign_entries_are_kept(shm):
    uid = os.getuid()
    dead = dead_pid()
    entries = [
        (os.getpid(), f"jack-{uid}:zyntest_live_1:"),       # alive test server
        (dead, f"jack-{uid}:default:"),                      # dead, but not a test server
        (dead, f"jack-{uid + 1}:zyntest_otheruser_1:"),      # another user's
        (0, ""),                                              # free slot
        (dead, f"jack-{uid}:zyntest_dead_2:"),               # dead test server
    ]
    make_registry(shm / "jack-shm-registry", entries)

    assert reclaim(shm) == ["zyntest_dead_2"]
    for i, expected in enumerate(entries[:4]):
        assert entry(shm / "jack-shm-registry", i) == expected
    assert entry(shm / "jack-shm-registry", 4) == (0, "")


def test_reclaim_is_idempotent(shm):
    uid = os.getuid()
    make_registry(shm / "jack-shm-registry", [(dead_pid(), f"jack-{uid}:zyntest_x_1:")])
    assert reclaim(shm) == ["zyntest_x_1"]
    assert reclaim(shm) == []


def test_missing_registry_is_not_an_error(shm):
    assert reclaim(shm) == []
