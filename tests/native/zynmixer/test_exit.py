"""What happens when a process using libzynmixer exits (the library closes itself from an atexit handler)."""

import subprocess
import sys
import textwrap

import pytest

from tests.native.support import lib_path

pytestmark = [pytest.mark.native, pytest.mark.jack]

SCRIPT = textwrap.dedent("""
    import ctypes, sys, time
    lib = ctypes.CDLL(sys.argv[1])            # connects to $JACK_DEFAULT_SERVER from its constructor
    chan = lib.addStrip()
    if {solo}:
        lib.setSolo(chan, 1)
    time.sleep(0.2)                           # let the JACK process callback run a few periods
""")


def run(server, solo):
    return subprocess.run([sys.executable, "-c", SCRIPT.format(solo=solo), str(lib_path("zynmixer"))],
                          env={"JACK_DEFAULT_SERVER": server.name, "PATH": "/usr/bin:/bin"},
                          capture_output=True, timeout=30)


def test_exit_is_clean(zynmixer, jack_server):
    assert run(jack_server, solo=False).returncode == 0


@pytest.mark.xfail(strict=True, reason="mixer.c: once a strip is soloed onJackProcess sets g_soloBufferA/B to the "
                                       "JACK solo port buffers ('populate the trunk directly'); end(), run by "
                                       "atexit, then free()s those JACK-owned pointers -> SIGSEGV/abort at exit "
                                       "(and the buffers malloc'ed in init() leak)")
def test_exit_after_solo_is_clean(zynmixer, jack_server):
    assert run(jack_server, solo=True).returncode == 0
