"""libzynmixer_mixbus (the same mixer.c built with -DMIXBUS) on the REAL library.

The mix-bus mixer owns the main bus (strip 0, always processed, cannot be removed) and an aux bus (strip 1,
normalised to the main bus). Effect returns normalised to main are summed into strip 0 before its fader.
"""

import ctypes
import time

import pytest

from tests.jacktest import FreewheelRunner
from tests.native.support import missing_lib_reason
from tests.native.zynmixer.conftest import AudioProbe, AudioSource, load

pytestmark = [pytest.mark.native, pytest.mark.jack]
BUS = "zynmixer_bus"
TOL = 1e-4


@pytest.fixture(scope="module")
def bus(jack_server):
    """The mix-bus library plus a source and probe wired to main (0) and aux (1)."""
    reason = missing_lib_reason("zynmixer_mixbus")
    if reason:
        pytest.skip(reason)
    lib = load("zynmixer_mixbus")
    u8, flt = ctypes.c_uint8, ctypes.c_float
    for name, (restype, argtypes) in {"setNormalise": (None, [u8, u8]), "getNormalise": (u8, [u8]),
                                      "setPflLevel": (None, [flt]), "getPflLevel": (flt, [])}.items():
        getattr(lib, name).restype, getattr(lib, name).argtypes = restype, argtypes
    src = AudioSource(jack_server, ("a", "b", "aux_a", "aux_b", "pfl_a", "pfl_b"), "zyntest_bus_src")
    probe = AudioProbe(jack_server, ("a", "b", "pfl_a", "pfl_b"), "zyntest_bus_probe")
    runner = FreewheelRunner(jack_server, "zyntest_bus_runner")
    for c in (src, probe, runner):
        c.activate()
    for leg in "ab":
        src.client.connect(src.ports[leg], f"{BUS}:input_00{leg}")
        src.client.connect(src.ports[f"aux_{leg}"], f"{BUS}:input_01{leg}")
        src.client.connect(src.ports[f"pfl_{leg}"], f"{BUS}:pfl_in_{leg}")
        probe.client.connect(f"{BUS}:output_00{leg}", probe.ports[leg])
        probe.client.connect(f"{BUS}:pfl_out_{leg}", probe.ports[f"pfl_{leg}"])
    lib.runner, lib.src, lib.probe = runner, src, probe
    yield lib
    for c in (runner, probe, src):
        c.close()


def settle(bus):
    time.sleep(0.2)                                   # let the mixer see the connections (asynchronous callback)
    bus.runner.run(4 * 256)


def main_out(bus):
    settle(bus)
    return bus.probe.level("a"), bus.probe.level("b")


@pytest.fixture
def clean(bus):
    for name in bus.src.levels:
        bus.src.levels[name] = 0.0
    for chan in (0, 1):
        bus.reset(chan)
    bus.setNormalise(1, 1)
    bus.setPflLevel(1.0)
    return bus


def test_main_and_aux_buses_exist_and_main_cannot_be_removed(clean):
    assert clean.getLastChannel() >= 2
    assert clean.removeStrip(0) == -1


def test_aux_bus_is_normalised_to_main_by_default(clean):
    assert clean.getNormalise(1) == 1
    assert clean.getNormalise(0) == 0
    clean.setNormalise(0, 1)                          # the main bus cannot be normalised to itself
    assert clean.getNormalise(0) == 0


def test_main_bus_passes_its_input(clean):
    clean.src.levels["a"], clean.src.levels["b"] = 0.5, 0.25
    assert main_out(clean) == pytest.approx((0.5, 0.25), abs=TOL)


def test_normalised_aux_bus_is_summed_into_main(clean):
    clean.src.levels["a"], clean.src.levels["b"] = 0.1, 0.1
    clean.src.levels["aux_a"], clean.src.levels["aux_b"] = 0.3, 0.2
    assert main_out(clean) == pytest.approx((0.4, 0.3), abs=TOL)


def test_aux_bus_fader_applies_before_main(clean):
    clean.src.levels["aux_a"], clean.src.levels["aux_b"] = 0.4, 0.4
    clean.setLevel(1, clean.dbToLevel(-6.0))
    assert main_out(clean)[0] == pytest.approx(0.4 * 10 ** (-6 / 20), rel=1e-3)


def test_unnormalised_aux_bus_does_not_reach_main(clean):
    clean.src.levels["aux_a"] = 0.3
    clean.setNormalise(1, 0)
    assert main_out(clean)[0] == pytest.approx(0.0, abs=TOL)


def test_main_fader_scales_everything(clean):
    clean.src.levels["a"], clean.src.levels["aux_a"] = 0.2, 0.2
    clean.setLevel(0, clean.dbToLevel(-6.0))
    assert main_out(clean)[0] == pytest.approx(0.4 * 10 ** (-6 / 20), rel=1e-3)


def test_pfl_trunk_passes_through_at_the_pfl_level(clean):
    clean.src.levels["pfl_a"], clean.src.levels["pfl_b"] = 0.5, 0.25
    settle(clean)
    assert (clean.probe.level("pfl_a"), clean.probe.level("pfl_b")) == pytest.approx((0.5, 0.25), abs=TOL)
    clean.setPflLevel(0.5)
    assert clean.getPflLevel() == 0.5
    settle(clean)
    assert clean.probe.level("pfl_a") == pytest.approx(0.25, abs=TOL)
