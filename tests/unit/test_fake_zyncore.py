"""The test double itself: make sure the harness is trustworthy."""

import sys


def test_production_import_gets_the_fake(zyncore):
    from zyncoder.zyncore import lib_zyncore
    assert lib_zyncore is zyncore
    assert "zyncoder.zyncore" in sys.modules


def test_records_calls_in_order(zyncore):
    zyncore.foo(1, 2)
    zyncore.bar()
    zyncore.foo(3)
    assert zyncore.log == [("foo", (1, 2)), ("bar", ()), ("foo", (3,))]
    assert zyncore.calls_to("foo") == [(1, 2), (3,)]
    assert zyncore.call_count() == 3
    assert zyncore.call_count("bar") == 1
    assert zyncore.names_called() == {"foo", "bar"}


def test_default_return_is_zero(zyncore):
    assert zyncore.anything() == 0


def test_configured_return_value_and_callable(zyncore):
    zyncore.set_return("get_num_zynpots", 4)
    assert zyncore.get_num_zynpots() == 4
    zyncore.set_return("add", lambda a, b: a + b)
    assert zyncore.add(2, 3) == 5


def test_ctypes_style_attributes_persist(zyncore):
    zyncore.get_thing.restype = "c_ubyte"
    zyncore.get_thing.argtypes = ["c_int"]
    assert zyncore.get_thing.restype == "c_ubyte"


def test_reset_clears_state(zyncore):
    zyncore.foo()
    zyncore.set_return("foo", 9)
    zyncore.reset_fake()
    assert zyncore.log == []
    assert zyncore.foo() == 0


def test_state_does_not_leak_between_tests_part1(zyncore):
    zyncore.leaky()
    zyncore.set_return("leaky", 7)


def test_state_does_not_leak_between_tests_part2(zyncore):
    assert zyncore.call_count() == 0
    assert zyncore.leaky() == 0


def test_helper_names_do_not_shadow_c_symbols(zyncore):
    """libzynmixer exports ``reset``; production code must reach the fake C function, not a helper."""
    zyncore.reset(3)
    assert zyncore.calls_to("reset") == [(3,)]
    assert zyncore.fn("reset") is zyncore.reset


def test_native_registry_gives_one_fake_per_library(native_libs):
    a = native_libs["libzynmixer.so"]
    assert native_libs["libzynmixer.so"] is a
    assert native_libs["libzynseq.so"] is not a
    assert native_libs["libzynaudioplayer.so"].init(None) == 1   # wrapper init succeeds
    assert native_libs["libzynseq.so"].getPPQN() == 96
    a.reset(1)
    native_libs.reset()
    assert a.call_count() == 0
    assert native_libs["libzynseq.so"].getPPQN() == 96           # defaults survive a reset


def test_default_return_follows_ctypes_restype(zyncore):
    import ctypes
    zyncore.get_name.restype = ctypes.c_char_p
    zyncore.get_gain.restype = ctypes.c_float
    assert zyncore.get_name() == b""
    assert zyncore.get_gain() == 0.0
    assert zyncore.other() == 0


def test_router_constants_match_header(zyncore):
    """The fake's import-time constants must mirror zyncoder/zynmidirouter.h."""
    import re
    from pathlib import Path
    header = (Path(__file__).resolve().parents[2] / "zyncoder" / "zynmidirouter.h").read_text()

    def define(name):
        return int(re.search(rf"#define\s+{name}\s+(\d+)", header).group(1))

    assert zyncore.zmop_get_num_chains() == define("NUM_ZMOP_CHAINS")
    assert zyncore.zmop_get_num_devs() == define("NUM_ZMOP_DEVS")
    assert zyncore.zmip_get_seq_index() == define("ZMIP_SEQ")
    assert zyncore.zmip_get_step_index() == define("ZMIP_STEP")
    assert zyncore.zmip_get_int_index() == define("ZMIP_FAKE_INT")
    assert zyncore.zmip_get_ctrl_index() == define("ZMIP_CTRL")
    assert zyncore.zmop_get_mod_index() == define("ZMOP_MOD")
    assert zyncore.zmop_get_step_index() == define("ZMOP_STEP")
    # DEV0..DEV23 inputs
    assert zyncore.zmip_get_num_devs() == define("ZMIP_SEQ") - define("ZMIP_DEV0")
