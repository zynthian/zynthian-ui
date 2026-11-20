"""zynthian_cc_feedback: the chain manager's broker that sends bound controllers' values back to devices.

Also the FCB1010 riban driver, which relies on it for all its feedback.
"""

import pytest

from zyngine.zynthian_controller import zynthian_controller

pytestmark = pytest.mark.integration

DEV, OTHER = 3, 4       # zmips
CHAN = 5


@pytest.fixture
def cm(state_manager):
    cm = state_manager.chain_manager
    for chain_id in [c for c in list(cm.chains) if c != 0]:
        cm.remove_chain(chain_id)
    cm.set_active_chain_by_id(0)
    cm.midi_cc_binding.clear()
    yield cm
    for zmip in (DEV, OTHER):
        cm.cc_feedback.unregister(zmip)
    cm.midi_cc_binding.clear()
    cm.midi_bindings_changed()


class Device:
    """Records the broker's callbacks"""

    def __init__(self, cm, zmip=DEV):
        self.sent = []
        cm.cc_feedback.register(zmip, self.cb)

    def cb(self, chan, cc, val, zctrl):
        self.sent.append((chan, cc, val))

    def take(self):
        sent, self.sent = self.sent, []
        return sent


def ctrl(symbol="ctl", value=0, toggle=False):
    options = {"value_min": 0, "value_max": 127, "value": value}
    if toggle:
        options["is_toggle"] = True
    zctrl = zynthian_controller(None, symbol, options)
    zctrl.midi_cc_mode_set(0)   # absolute, no detection
    return zctrl


def test_new_binding_sends_the_current_value_once(cm):
    dev = Device(cm)
    z = ctrl(value=40)
    cm.add_midi_binding(z, 21, CHAN, DEV)
    assert dev.take() == [(CHAN, 21, 40)]
    cm.add_midi_binding(z, 21, CHAN, DEV)   # no change
    cm.midi_bindings_changed()
    assert dev.take() == []


def test_value_changes_are_sent_to_the_bound_device_only(cm):
    dev, other = Device(cm), Device(cm, OTHER)
    z = ctrl()
    cm.add_midi_binding(z, 21, CHAN, DEV)
    dev.take()
    z.set_value(127)
    z.set_value(127)     # unchanged: set_value does not call back
    z.send_value()       # same value: the device has it
    assert dev.take() == [(CHAN, 21, 127)]
    assert other.take() == []


def test_unregistered_device_and_channel_mode_ccs_get_nothing(cm):
    dev = Device(cm)
    z = ctrl()
    cm.add_midi_binding(z, 21, CHAN, OTHER)     # OTHER is not registered
    cm.add_midi_binding(z, 123, CHAN, DEV)      # all notes off: never fed back
    z.set_value(100)
    assert dev.take() == []


def test_removed_binding_stops_feedback(cm):
    dev = Device(cm)
    z = ctrl()
    cm.add_midi_binding(z, 21, CHAN, DEV)
    assert z.send_value_cb
    cm.toggle_midi_binding(z, 21, CHAN, DEV, 0xff)
    assert not z.send_value_cb
    z.set_value(90)
    assert dev.take() == [(CHAN, 21, 0), (CHAN, 21, None)]    # the value when bound, then released


def test_unregister_releases_the_controllers(cm):
    Device(cm)
    z = ctrl()
    cm.add_midi_binding(z, 21, CHAN, DEV)
    cm.cc_feedback.unregister(DEV)
    assert not z.send_value_cb


def test_device_cc_is_not_echoed_back(cm):
    dev = Device(cm)
    z = ctrl()
    cm.add_midi_binding(z, 21, CHAN, DEV)
    dev.take()
    for val in (1, 37, 64, 99, 127):
        cm.midi_control_change(DEV, CHAN, 21, val)
    assert dev.take() == []
    assert z.value != 0
    # A change from elsewhere is sent
    z.set_value(10)
    assert dev.take() == [(CHAN, 21, 10)]


def test_device_cc_reaches_other_ccs_bound_to_the_same_controller(cm):
    dev = Device(cm)
    z = ctrl()
    cm.add_midi_binding(z, 21, CHAN, DEV)
    cm.add_midi_binding(z, 22, CHAN, DEV)
    dev.take()
    cm.midi_control_change(DEV, CHAN, 21, 127)
    assert dev.take() == [(CHAN, 22, 127)]


def test_momentary_toggle_result_is_sent_back(cm):
    dev = Device(cm)
    z = ctrl(toggle=True)
    z.midi_cc_momentary_switch = True
    cm.add_midi_binding(z, 21, CHAN, DEV)
    dev.take()
    cm.midi_control_change(DEV, CHAN, 21, 127)     # toggles on: the device has 127 already
    assert dev.take() == []
    cm.midi_control_change(DEV, CHAN, 21, 0)       # release: nothing changes, but the device has 0
    assert dev.take() == [(CHAN, 21, 127)]
    cm.midi_control_change(DEV, CHAN, 21, 127)     # toggles off
    assert dev.take() == [(CHAN, 21, 0)]


def test_chain_bindings_follow_the_active_chain(cm):
    dev = Device(cm)
    cm.add_chain(1)
    cm.set_active_chain_by_id(0)
    z = ctrl(value=30)
    cm.add_midi_binding(z, 21, CHAN, DEV, 1)
    assert dev.take() == []       # chain 1 is not active
    z.set_value(50)
    assert dev.take() == []
    cm.set_active_chain_by_id(1)
    assert dev.take() == [(CHAN, 21, 50)]
    z.set_value(60)
    assert dev.take() == [(CHAN, 21, 60)]


def test_chain_change_releases_the_old_chain_and_rebinding_sends_again(cm):
    dev = Device(cm)
    cm.add_chain(1)
    cm.add_chain(2)
    cm.set_active_chain_by_id(1)
    a, b = ctrl("a", 10), ctrl("b", 10)
    cm.add_midi_binding(a, 21, CHAN, DEV, 1)
    cm.add_midi_binding(b, 21, CHAN, DEV, 2)
    assert dev.take() == [(CHAN, 21, 10)]
    cm.set_active_chain_by_id(0)
    assert dev.take() == [(CHAN, 21, None)]
    cm.set_active_chain_by_id(2)            # another controller with the same value: sent anyway
    assert dev.take() == [(CHAN, 21, 10)]


def test_driver_bindings(cm):
    dev = Device(cm)
    a, b = ctrl("a", 1), ctrl("b", 2)
    cm.cc_feedback.set_bindings(DEV, {(1, 30): a, (1, 31): b})
    assert sorted(dev.take()) == [(1, 30, 1), (1, 31, 2)]
    cm.cc_feedback.set_bindings(DEV, {(1, 30): a, (1, 31): b})
    assert dev.take() == []                 # unchanged
    cm.add_chain(1)
    cm.set_active_chain_by_id(1)            # always active
    a.set_value(3)
    assert dev.take() == [(1, 30, 3)]
    cm.cc_feedback.set_bindings(DEV, {(1, 31): a})
    assert sorted(dev.take(), key=str) == [(1, 30, None), (1, 31, 3)]
    b.set_value(9)
    assert dev.take() == []
    cm.cc_feedback.unregister(DEV)
    assert not a.send_value_cb and not b.send_value_cb


def test_driver_cc_received_suppresses_the_echo(cm):
    dev = Device(cm)
    z = ctrl()
    cm.cc_feedback.set_bindings(DEV, {(1, 30): z})
    dev.take()
    cm.cc_feedback.cc_received(DEV, 1, 30, 77)
    z.set_value(77)
    cm.cc_feedback.cc_handled()
    assert dev.take() == []


def test_value_function_and_unsent_values(cm):
    sent = []
    held = [True]

    def cb(chan, cc, val, zctrl):
        if held[0]:
            return False
        sent.append(val)

    cm.cc_feedback.register(DEV, cb, lambda zctrl: int(zctrl.value) // 2)
    z = ctrl(value=100)
    cm.cc_feedback.set_bindings(DEV, {(0, 30): z})
    z.set_value(50)
    held[0] = False
    z.send_value()          # same value as the last one, which was not sent: sent now
    assert sent == [25]


def test_resend_sends_every_binding_again(cm):
    dev = Device(cm)
    a, b = ctrl("a", 1), ctrl("b", 2)
    cm.add_midi_binding(a, 21, CHAN, DEV)
    cm.add_midi_binding(b, 22, CHAN, DEV)
    assert sorted(dev.take()) == [(CHAN, 21, 1), (CHAN, 22, 2)]
    cm.cc_feedback.resend(DEV)
    assert sorted(dev.take()) == [(CHAN, 21, 1), (CHAN, 22, 2)]


def test_reversed_range_is_inverted(cm):
    dev = Device(cm)
    z = ctrl(value=100)
    z.range_reversed = True
    cm.add_midi_binding(z, 21, CHAN, DEV)
    assert dev.take() == [(CHAN, 21, 27)]


# --- FCB1010 riban driver ---------------------------------------------------------------------------------------

IDEV_OUT = 7


def dump(chan=CHAN, bank=1, ccs=range(21, 31), pedal_ccs=(7, 11)):
    data = [bank, chan + 1, 0, 0, 1, 0, bank, 30, 127, 0]
    for cc in ccs:
        data += [0, cc, 127, 0]
    data += [0, 0, 0, 0, 0, 0] + list(pedal_ccs) + [0, 0, 127, 127]
    return bytes([0xF0, 0x7D, 0x46, 0x43, chan, 0x02] + data + [0xF7])


@pytest.fixture
def fcb(cm, zyncore, monkeypatch):
    from zyngine.ctrldev import zynthian_ctrldev_behringer_fcb1010_riban as mod
    clock = [1000.0]
    monkeypatch.setattr(mod, "monotonic", lambda: clock[0])
    driver = mod.zynthian_ctrldev_behringer_fcb1010_riban(cm.state_manager, DEV, IDEV_OUT)
    driver.clock = clock
    driver.init()
    yield driver
    driver.end()


def ccs_sent(zyncore):
    sent = [args[1:] for args in zyncore.calls_to("dev_send_ccontrol_change")]
    zyncore.log.clear()
    return sent


def dumps_asked(zyncore):
    n = sum(1 for args in zyncore.calls_to("dev_send_midi_event") if bytes(args[1][:6]) == bytes.fromhex("F07D46437F01"))
    return n


def test_fcb_asks_for_a_dump_and_sends_bound_values_once_read(fcb, cm, zyncore):
    assert dumps_asked(zyncore) == 1
    z = ctrl(value=127)
    cm.add_midi_binding(z, 21, CHAN, DEV)
    assert ccs_sent(zyncore) == []           # channel not known yet
    assert fcb.midi_event(dump()) is True
    assert fcb.fcb_chan == CHAN and fcb.bank == 1 and fcb.fcb_version == (0, 0, 1)
    assert ccs_sent(zyncore) == [(CHAN, 21, 127)]
    z.set_value(0)
    assert ccs_sent(zyncore) == [(CHAN, 21, 0)]


def test_fcb_sends_only_its_channel_and_any_channel(fcb, cm, zyncore):
    fcb.midi_event(dump())
    zyncore.log.clear()
    a, b = ctrl("a"), ctrl("b")
    cm.add_midi_binding(a, 21, CHAN + 1, DEV)
    cm.add_midi_binding(b, 22, 0xFF, DEV)
    a.set_value(5)
    b.set_value(6)
    assert ccs_sent(zyncore) == [(CHAN, 22, 0), (CHAN, 22, 6)]


def test_fcb_identity_at_power_on_resends_and_redumps(fcb, cm, zyncore):
    fcb.midi_event(dump())
    z = ctrl(value=64)
    cm.add_midi_binding(z, 21, CHAN, DEV)
    zyncore.log.clear()
    identity = bytes.fromhex(f"F0 7E {CHAN:02X} 06 02 7D 46 43 31 30 00 01 05 00 F7")
    assert fcb.midi_event(identity) is True
    assert fcb.fcb_version == (0, 1, 5)
    assert dumps_asked(zyncore) == 1
    assert ccs_sent(zyncore) == [(CHAN, 21, 64)]


def test_fcb_leaves_ccs_to_the_state_manager_and_redumps_on_unknown_cc(fcb, zyncore):
    fcb.midi_event(dump())
    zyncore.log.clear()
    assert fcb.midi_event(bytes([0xB0 | CHAN, 21, 127])) is False    # in the bank: no dump
    fcb.clock[0] += 5
    assert fcb.midi_event(bytes([0xB0 | CHAN, 40, 127])) is False    # not in the bank: another bank
    assert dumps_asked(zyncore) == 1
    zyncore.log.clear()
    fcb.midi_event(bytes([0xB0 | CHAN, 41, 127]))                    # within REDUMP_SECS
    assert dumps_asked(zyncore) == 0


def test_fcb_asks_again_after_an_unanswered_dump(fcb, zyncore):
    zyncore.log.clear()
    fcb.midi_event(bytes([0xB0 | CHAN, 21, 127]))       # dump pending, not timed out: waits for it
    assert dumps_asked(zyncore) == 0
    fcb.clock[0] += 5
    fcb.midi_event(bytes([0xB0 | CHAN, 21, 127]))       # no reply: asked again
    assert dumps_asked(zyncore) == 1
    assert fcb.fcb_chan is None
    fcb.midi_event(dump())
    assert fcb.fcb_chan == CHAN


def test_fcb_has_no_periodic_task(fcb):
    assert not hasattr(fcb, "slow_update")


# --- Behringer Motör ---------------------------------------------------------------------------------------------

class FakeProc:
    def __init__(self, bank_name, symbols):
        self.bank_name = bank_name
        self.controllers_dict = {}
        for symbol in symbols:
            z = ctrl(symbol, 64)
            z.processor = self
            self.controllers_dict[symbol] = z


@pytest.fixture
def motor(cm, zyncore):
    from zyngine.ctrldev.zynthian_ctrldev_behringer_motor import zynthian_ctrldev_behringer_motor as cls
    driver = cls(cm.state_manager, DEV, IDEV_OUT)
    driver.init()
    proc = FakeProc("Upper", cls.zctrls2ccnum["Upper"])
    driver.setbfree_procs = [proc]
    zyncore.log.clear()
    driver.setup_feedback()
    driver.proc = proc
    yield driver
    driver.end()


def test_motor_sends_mapped_values_and_follows_changes(motor, zyncore):
    sent = ccs_sent(zyncore)
    assert len(sent) == len(motor.zctrls2ccnum["Upper"]) and all(ch == 1 and val == 64 for ch, cc, val in sent)
    motor.proc.controllers_dict["DB 16"].set_value(100)
    assert ccs_sent(zyncore) == [(1, 21, 100)]


def test_motor_touched_fader_gets_no_feedback_until_released(motor, zyncore):
    ccs_sent(zyncore)
    db16 = motor.proc.controllers_dict["DB 16"]
    motor.midi_event(bytes([0x91, 0, 127]))         # touch fader 1
    db16.set_value(10)
    assert ccs_sent(zyncore) == []
    motor.midi_event(bytes([0x81, 0, 0]))           # release
    db16.set_value(10)
    db16.send_value()
    assert ccs_sent(zyncore) == [(1, 21, 10)]


def test_motor_own_cc_is_not_echoed(motor, zyncore):
    ccs_sent(zyncore)
    assert motor.midi_event(bytes([0xB1, 21, 33])) is True
    assert motor.proc.controllers_dict["DB 16"].value == 33
    assert ccs_sent(zyncore) == []


def test_motor_end_releases_the_controllers(motor):
    z = motor.proc.controllers_dict["DB 16"]
    assert z.send_value_cb
    motor.end()
    assert not z.send_value_cb
    motor.init()    # for the fixture's end()


# --- Akai APC40 mk2 ----------------------------------------------------------------------------------------------

@pytest.fixture
def apc(cm, zyncore, monkeypatch):
    from zyngine.ctrldev import zynthian_ctrldev_akai_apc_40_mk2 as mod
    from zyngine.ctrldev import zynthian_ctrldev_base as base
    monkeypatch.setattr(mod, "sleep", lambda s: None, raising=False)
    monkeypatch.setattr(base, "sleep", lambda s: None, raising=False)
    driver = mod.zynthian_ctrldev_akai_apc_40_mk2(cm.state_manager, DEV, IDEV_OUT)
    driver.init()
    driver.mod = mod
    yield driver
    driver.end()


def knob_ccs(zyncore, first, last):
    return [args[1:] for args in zyncore.calls_to("dev_send_ccontrol_change") if first <= args[2] <= last]


def test_apc_device_knobs_follow_learned_bindings(apc, cm, zyncore):
    m = apc.mod
    zyncore.log.clear()
    z = ctrl(value=90)
    cm.add_midi_binding(z, m.CC_DEVICE_1, 0, DEV)
    assert knob_ccs(zyncore, m.CC_DEVICE_1, m.CC_DEVICE_8) == [(0, m.CC_DEVICE_1, 90)]
    zyncore.log.clear()
    z.set_value(20)
    cm.toggle_midi_binding(z, m.CC_DEVICE_1, 0, DEV, 0xff)
    assert knob_ccs(zyncore, m.CC_DEVICE_1, m.CC_DEVICE_8) == [(0, m.CC_DEVICE_1, 20), (0, m.CC_DEVICE_1, 0)]


def test_apc_device_knobs_follow_the_active_chain(apc, cm, zyncore):
    m = apc.mod
    cm.add_chain(1)
    cm.set_active_chain_by_id(0)
    z = ctrl(value=70)
    cm.add_midi_binding(z, m.CC_DEVICE_2, 0, DEV, 1)
    zyncore.log.clear()
    cm.set_active_chain_by_id(1)
    assert (0, m.CC_DEVICE_2, 70) in knob_ccs(zyncore, m.CC_DEVICE_1, m.CC_DEVICE_8)
    zyncore.log.clear()
    cm.set_active_chain_by_id(0)
    assert (0, m.CC_DEVICE_2, 0) in knob_ccs(zyncore, m.CC_DEVICE_1, m.CC_DEVICE_8)


def test_apc_track_knobs_in_user_mode(apc, cm, zyncore, monkeypatch):
    m = apc.mod
    z = ctrl(value=55)
    chain = type("Chain", (), {"zctrls": [z]})()
    zyncore.log.clear()
    apc.enc_mode = m.ENC_MODE_USER
    with monkeypatch.context() as mp:
        mp.setattr(apc, "get_filtered_chain_by_index", lambda pos: chain if pos == 0 else None)
        apc.update_track_encoders()
    sent = knob_ccs(zyncore, m.CC_TRACK_1, m.CC_TRACK_8)
    assert (0, m.CC_TRACK_1, 55) in sent and all(val == 0 for ch, cc, val in sent if cc != m.CC_TRACK_1)
    zyncore.log.clear()
    z.set_value(60)
    assert knob_ccs(zyncore, m.CC_TRACK_1, m.CC_TRACK_8) == [(0, m.CC_TRACK_1, 60)]
    zyncore.log.clear()
    apc.enc_mode = m.ENC_MODE_PAN
    apc.update_track_encoders()
    z.set_value(61)
    sent = knob_ccs(zyncore, m.CC_TRACK_1, m.CC_TRACK_8)
    assert len(sent) == 8 and (0, m.CC_TRACK_1, 61) not in sent      # mixer values, no feedback
