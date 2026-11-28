"""libzynmixer channel strips on the REAL library: what reaches the outputs for a known input.

Input is DC: 0.5 on leg A, 0.25 on leg B unless stated. ``mix.out()`` returns the settled (A, B) output.
"""

import math

import jack
import pytest

from tests.native.zynmixer.conftest import CLIENT, FADER_UNITY

pytestmark = [pytest.mark.native, pytest.mark.jack]
TOL = 1e-4


def db(x):
    return 10 ** (x / 20)


# --- strips and ports ---------------------------------------------------------------------------------------
def test_add_strip_creates_ports_and_remove_deletes_them(mix):
    client = jack.Client("zyntest_mix_ports", servername=mix.server.name, no_start_server=True)
    try:
        chan = mix.lib.addStrip()
        names = {p.shortname for p in client.get_ports(f"{CLIENT}:")}
        assert {f"input_{chan:02d}a", f"input_{chan:02d}b", f"output_{chan:02d}a", f"output_{chan:02d}b"} <= names
        assert mix.lib.getLastChannel() >= chan + 1
        assert mix.lib.removeStrip(chan) == chan
        names = {p.shortname for p in client.get_ports(f"{CLIENT}:")}
        assert f"input_{chan:02d}a" not in names
        assert mix.lib.removeStrip(chan) == -1                     # already gone
    finally:
        client.close()


def test_mixer_has_solo_and_pfl_trunk_ports(mix):
    client = jack.Client("zyntest_mix_ports", servername=mix.server.name, no_start_server=True)
    try:
        names = {p.shortname for p in client.get_ports(f"{CLIENT}:")}
        assert {"solo_a", "solo_b", "pfl_out_a", "pfl_out_b"} <= names
    finally:
        client.close()


def test_max_channels(zynmixer):
    assert zynmixer.getMaxChannels() == 99


# --- fader law ----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("level,expected_db", [(0.75, 0.0), (1.0, 10.0), (0.375, None), (0.0, -200.0)])
def test_level_to_db(zynmixer, level, expected_db):
    got = zynmixer.levelToDb(level)
    if expected_db is None:
        assert -40 < got < 0
    else:
        assert got == pytest.approx(expected_db, abs=1e-3)


@pytest.mark.parametrize("decibels", [-60.0, -18.0, -6.0, -1.0, 0.0, 3.0, 10.0])
def test_db_level_round_trip(zynmixer, decibels):
    assert zynmixer.levelToDb(zynmixer.dbToLevel(decibels)) == pytest.approx(decibels, abs=1e-3)


def test_unity_is_at_three_quarters_of_the_throw(zynmixer):
    assert zynmixer.dbToLevel(0.0) == pytest.approx(FADER_UNITY)


def test_fader_law_is_monotonic(zynmixer):
    dbs = [zynmixer.levelToDb(x / 100) for x in range(1, 101)]
    assert dbs == sorted(dbs)


# --- the signal path ----------------------------------------------------------------------------------------
def test_reset_strip_passes_audio_at_unity(mix):
    chan = mix.strip()
    mix.lib.reset(chan)
    assert mix.out() == pytest.approx((0.5, 0.25), abs=TOL)


@pytest.mark.xfail(strict=True, reason="mixer.c addStrip(): `strip->reqlevel = dbToLevel(0.0f)` stores a fader "
                                       "position (0.75) where a gain is expected (setLevel stores levelToGain()), so "
                                       "a new strip plays at 0.75 (-2.5 dB) until reset()/setLevel() is called")
def test_new_strip_starts_at_unity(mix):
    mix.strip()
    assert mix.out() == pytest.approx((0.5, 0.25), abs=TOL)


@pytest.mark.parametrize("decibels", [-12.0, -6.0, 0.0, 6.0])
def test_fader_level(mix, decibels):
    chan = mix.strip()
    mix.lib.reset(chan)
    mix.lib.setLevel(chan, mix.lib.dbToLevel(decibels))
    assert mix.lib.getLevel(chan) == pytest.approx(mix.lib.dbToLevel(decibels), abs=1e-4)
    assert mix.out() == pytest.approx((0.5 * db(decibels), 0.25 * db(decibels)), rel=1e-3)


def test_fader_at_zero_is_silent(mix):
    chan = mix.strip()
    mix.lib.setLevel(chan, 0.0)
    assert mix.out() == (0.0, 0.0)


def test_input_gain(mix):
    chan = mix.strip()
    mix.lib.reset(chan)
    mix.lib.setGain(chan, 2.0)
    assert mix.lib.getGain(chan) == 2.0
    assert mix.out() == pytest.approx((1.0, 0.5), abs=TOL)
    mix.lib.setGain(chan, -1.0)                                     # negative gain is ignored
    assert mix.lib.getGain(chan) == 2.0


def test_mute(mix):
    chan = mix.strip()
    mix.lib.reset(chan)
    mix.lib.setMute(chan, 1)
    assert mix.lib.getMute(chan) == 1
    assert mix.out() == (0.0, 0.0)
    mix.lib.toggleMute(chan)
    assert mix.out() == pytest.approx((0.5, 0.25), abs=TOL)


@pytest.mark.parametrize("balance,expected", [(0.0, (0.5, 0.25)), (1.0, (0.0, 0.25)), (-1.0, (0.5, 0.0)),
                                              (0.5, (0.25, 0.25)), (-0.5, (0.5, 0.125))])
def test_balance_attenuates_the_opposite_leg(mix, balance, expected):
    chan = mix.strip()
    mix.lib.reset(chan)
    mix.lib.setBalance(chan, balance)
    assert mix.lib.getBalance(chan) == balance
    assert mix.out() == pytest.approx(expected, abs=TOL)


def test_balance_out_of_range_is_ignored(mix):
    chan = mix.strip()
    mix.lib.setBalance(chan, 0.3)
    mix.lib.setBalance(chan, 1.5)
    assert mix.lib.getBalance(chan) == pytest.approx(0.3)


def test_phase_inverts_leg_b(mix):
    chan = mix.strip()
    mix.lib.reset(chan)
    mix.lib.setPhase(chan, 1)
    assert mix.out() == pytest.approx((0.5, -0.25), abs=TOL)


def test_mono_sums_both_legs(mix):
    chan = mix.strip()
    mix.lib.reset(chan)
    mix.lib.setMono(chan, 1)
    assert mix.lib.getMono(chan) == 1
    assert mix.out() == pytest.approx((0.375, 0.375), abs=TOL)


def test_mid_side_decoding(mix):
    """A carries Mid, B carries Side: L = M + S, R = M - S."""
    chan = mix.strip()
    mix.lib.reset(chan)
    mix.lib.setMS(chan, 1)
    assert mix.out() == pytest.approx((0.75, 0.25), abs=TOL)


def test_reset_clears_the_strip_settings(mix):
    chan = mix.strip()
    for setter, value in (("setGain", 3.0), ("setBalance", 0.5), ("setMute", 1), ("setMono", 1), ("setPhase", 1)):
        getattr(mix.lib, setter)(chan, value)
    mix.lib.reset(chan)
    assert (mix.lib.getGain(chan), mix.lib.getBalance(chan), mix.lib.getMute(chan), mix.lib.getMono(chan),
            mix.lib.getPhase(chan)) == (1.0, 0.0, 0, 0, 0)
    assert mix.out() == pytest.approx((0.5, 0.25), abs=TOL)


def test_strips_sum_on_a_shared_output(mix):
    one = mix.strip(0.1, 0.2)
    two = mix.strip(0.3, 0.05, inputs=("a2", "b2"))
    for chan in (one, two):
        mix.lib.reset(chan)
    assert mix.out() == pytest.approx((0.4, 0.25), abs=TOL)


def test_level_changes_are_ramped_over_one_period(mix):
    """No zipper noise: a level jump is faded across the next period instead of applied at once."""
    chan = mix.strip()
    mix.lib.reset(chan)
    mix.settle()
    mix.probe.history = []
    mix.lib.setLevel(chan, 0.0)
    mix.settle()
    periods, mix.probe.history = mix.probe.history, None
    # Periods are numpy arrays: locate the ramp by index (list.index() would compare arrays with ==, which raises)
    ramps = [i for i, p in enumerate(periods) if p[0] > 0.4 and p[-1] < 0.01]
    assert len(ramps) == 1, "exactly one period fades from the old level to the new one"
    ramp = ramps[0]
    assert all(abs(x) < 1e-6 for p in periods[ramp + 1:] for x in p[:1])
    assert len(set(periods[ramp].round(6))) > 200                   # a smooth ramp, not a step


# --- solo and PFL -------------------------------------------------------------------------------------------
def test_solo_sends_the_strip_to_the_solo_trunk(mix):
    chan = mix.strip()
    mix.lib.reset(chan)
    mix.lib.setSolo(chan, 1)
    assert mix.lib.getSolo(chan) == 1 and mix.lib.getGlobalSolo() == 1
    assert (mix.tap("solo_a"), mix.tap("solo_b")) == pytest.approx((0.5, 0.25), abs=TOL)
    mix.lib.clearSolo()
    assert mix.lib.getGlobalSolo() == 0 and mix.lib.getSolo(chan) == 0


def test_solo_counts_soloed_strips(mix):
    one, two = mix.strip(), mix.strip(inputs=("a2", "b2"))
    mix.lib.setSolo(one, 1)
    mix.lib.setSolo(two, 1)
    mix.lib.setSolo(two, 1)                                          # idempotent
    assert mix.lib.getGlobalSolo() == 2
    mix.lib.setSolo(one, 0)
    assert mix.lib.getGlobalSolo() == 1


TOGGLE_BUG = "mixer.c toggleSolo()/togglePFL() read the strip's `mute` flag instead of `solo`/`pfl`, so on an " \
             "unmuted strip they always switch it ON (and on a muted one always OFF)"


def test_toggle_solo_switches_it_on(mix):
    chan = mix.strip()
    mix.lib.toggleSolo(chan)
    assert mix.lib.getSolo(chan) == 1


@pytest.mark.xfail(strict=True, reason=TOGGLE_BUG)
def test_toggle_solo_switches_it_off_again(mix):
    chan = mix.strip()
    mix.lib.setSolo(chan, 1)
    mix.lib.toggleSolo(chan)
    assert mix.lib.getSolo(chan) == 0


@pytest.mark.xfail(strict=True, reason=TOGGLE_BUG)
def test_toggle_pfl_switches_it_off_again(mix):
    chan = mix.strip()
    mix.lib.setPfl(chan, 1)
    mix.lib.togglePFL(chan)
    assert mix.lib.getPfl(chan) == 0


@pytest.mark.parametrize("toggle,getter", [("toggleMute", "getMute"), ("toggleMono", "getMono"),
                                           ("toggleMS", "getMS"), ("togglePhase", "getPhase")])
def test_other_toggles_flip_their_flag(mix, toggle, getter):
    chan = mix.strip()
    mix.lib.reset(chan)
    getattr(mix.lib, toggle)(chan)
    assert getattr(mix.lib, getter)(chan) == 1
    getattr(mix.lib, toggle)(chan)
    assert getattr(mix.lib, getter)(chan) == 0


def test_pfl_taps_the_signal_before_the_fader(mix):
    chan = mix.strip()
    mix.lib.reset(chan)
    mix.lib.setLevel(chan, 0.0)
    mix.lib.setPfl(chan, 1)
    assert mix.lib.getGlobalPfl() == 1
    assert mix.out() == (0.0, 0.0)
    assert (mix.tap("pfl_a"), mix.tap("pfl_b")) == pytest.approx((0.5, 0.25), abs=TOL)


# --- AB crossfader ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("xfader,gain_a,gain_b", [(0.0, 1.0, 0.0), (1.0, 0.0, 1.0),
                                                  (0.5, math.cos(math.pi / 4), math.sin(math.pi / 4))])
def test_crossfader_is_constant_power(mix, xfader, gain_a, gain_b):
    group_a = mix.strip(0.5, 0.5)
    mix.lib.reset(group_a)
    mix.lib.setABMixGroup(group_a, 1)
    mix.lib.setGlobalXFader(xfader)
    assert mix.lib.getGlobalXFader() == pytest.approx(xfader)
    assert mix.out()[0] == pytest.approx(0.5 * gain_a, abs=TOL)
    mix.lib.setABMixGroup(group_a, 2)
    assert mix.out()[0] == pytest.approx(0.5 * gain_b, abs=TOL)
    mix.lib.setABMixGroup(group_a, 0)                                # not in a group: crossfader ignored
    assert mix.out()[0] == pytest.approx(0.5, abs=TOL)


def test_crossfader_is_clamped(zynmixer):
    zynmixer.setGlobalXFader(3.0)
    assert zynmixer.getGlobalXFader() == 1.0
    zynmixer.setGlobalXFader(-1.0)
    assert zynmixer.getGlobalXFader() == 0.0


# --- effect sends -------------------------------------------------------------------------------------------
@pytest.fixture
def send(mix):
    """An effect send connected to the probe's send taps: (id returned by addSend, send index, port number)."""
    sid = mix.lib.addSend()
    assert sid >= 1
    index, port = sid - 1, sid + 1
    mix.probe.client.connect(f"{CLIENT}:send_{port:02d}a", mix.probe.ports["send_a"])
    mix.probe.client.connect(f"{CLIENT}:send_{port:02d}b", mix.probe.ports["send_b"])
    yield sid, index, port
    mix.lib.removeSend(port)


def test_post_fader_send(mix, send):
    _, index, _ = send
    chan = mix.strip()
    mix.lib.reset(chan)
    mix.lib.setLevel(chan, mix.lib.dbToLevel(-6.0))
    mix.lib.setSend(chan, index, 0.5)
    assert mix.lib.getSend(chan, index) == 0.5
    assert mix.tap("send_a") == pytest.approx(0.5 * db(-6) * 0.5, rel=1e-3)


def test_pre_fader_send_ignores_the_fader(mix, send):
    _, index, _ = send
    chan = mix.strip()
    mix.lib.reset(chan)
    mix.lib.setLevel(chan, 0.0)
    mix.lib.setSend(chan, index, 0.5)
    mix.lib.setSendMode(chan, index, 1)
    assert mix.lib.getSendMode(chan, index) == 1
    assert (mix.tap("send_a"), mix.tap("send_b")) == pytest.approx((0.25, 0.125), abs=TOL)


def test_send_count_and_removal(mix):
    before = mix.lib.getSendCount()
    sid = mix.lib.addSend()
    assert mix.lib.getSendCount() == before + 1
    assert mix.lib.removeSend(sid + 1) == 0
    assert mix.lib.getSendCount() == before
    assert mix.lib.removeSend(sid + 1) == 1                          # already removed


# --- meters -------------------------------------------------------------------------------------------------
def meter_position(amplitude, range_db=72.0):
    """The library's DPM value: inverted position on a linear-dB scale (0 = full scale, 1 = silence)."""
    pos = 1.0 + 20 * math.log10(amplitude) / range_db
    return 1.0 - min(1.0, max(0.0, pos))


def test_peak_meter_reads_the_output_level(mix):
    chan = mix.strip()
    mix.lib.reset(chan)
    mix.settle(8)
    assert mix.lib.getDpm(chan, 0) == pytest.approx(meter_position(0.5), abs=1e-3)
    assert mix.lib.getDpm(chan, 1) == pytest.approx(meter_position(0.25), abs=1e-3)
    assert mix.lib.getDpmHold(chan, 0) == pytest.approx(meter_position(0.5), abs=1e-3)


def test_peak_meter_of_a_muted_strip_decays_to_silence(mix):
    chan = mix.strip()
    mix.lib.reset(chan)
    mix.settle(8)
    mix.lib.setMute(chan, 1)
    mix.runner.run_seconds(4.0)                                      # 30 dB/s decay over a 72 dB range
    assert mix.lib.getDpm(chan, 0) == pytest.approx(1.0)


def test_meter_config_is_validated(zynmixer):
    assert zynmixer.setMeterConfig(72.0, 30.0, 2.0, 10.0) == 1
    assert zynmixer.setMeterConfig(5.0, 30.0, 2.0, 10.0) == 0       # range too small
    assert zynmixer.setMeterConfig(72.0, 30.0, 2.0, 0.0) == 0       # no fader headroom
    assert zynmixer.setMeterConfig(72.0, 30.0, 2.0, 10.0) == 1


def test_fader_headroom_follows_the_meter_config(zynmixer):
    assert zynmixer.setMeterConfig(72.0, 30.0, 2.0, 6.0) == 1
    try:
        assert zynmixer.levelToDb(1.0) == pytest.approx(6.0, abs=1e-3)
        assert zynmixer.levelToDb(FADER_UNITY) == pytest.approx(0.0, abs=1e-3)
    finally:
        zynmixer.setMeterConfig(72.0, 30.0, 2.0, 10.0)


def test_invalid_channel_is_harmless(zynmixer):
    zynmixer.setLevel(98, 0.5)
    zynmixer.setMute(200, 1)
    assert zynmixer.getLevel(98) == 0.0 and zynmixer.getMute(200) == 0
