"""zynthian_ctrldev_manager: finding drivers by SysEx identity, for ports without a device ID (DIN-5).

The identity is asked for only when needed (autoload of a new device without a driver for its ID, the
MIDI input menu), never periodically, and an identity sent unasked (a device powering on) is taken too.
"""

import pytest

pytestmark = pytest.mark.integration

PORT, OUT = 3, 4
REQUEST = bytes.fromhex("F0 7E 7F 06 01 F7")
FCB_IDENTITY = bytes.fromhex("F0 7E 00 06 02 7D 46 43 31 30 00 01 05 00 F7")
OTHER_IDENTITY = bytes.fromhex("F0 7E 00 06 02 41 12 34 56 78 01 02 03 04 F7")
FCB = "zynthian_ctrldev_behringer_fcb1010_riban"


@pytest.fixture
def mgr(state_manager, zyncore, monkeypatch):
    import zynautoconnect
    from zyngine import zynthian_ctrldev_manager as mod
    mgr = state_manager.ctrldev_manager
    clock = [1000.0]
    monkeypatch.setattr(mod, "monotonic", lambda: clock[0])
    monkeypatch.setattr(zynautoconnect, "dev_in_2_dev_out", lambda izmip: OUT if izmip == PORT else None)
    monkeypatch.setattr(zynautoconnect, "get_midi_in_devid", lambda izmip: "DIN MIDI port")
    monkeypatch.setattr(zynautoconnect, "get_midi_in_uid", lambda izmip: f"uid{izmip}")
    mgr.unload_all_drivers()
    mgr.disabled_devices.clear()
    mgr.forget_identity(PORT)
    mgr.clock = clock
    zyncore.reset_fake()
    yield mgr
    mgr.unload_all_drivers()
    mgr.disabled_devices.clear()
    mgr.forget_identity(PORT)


def requests(zyncore):
    n = sum(1 for args in zyncore.calls_to("dev_send_midi_event") if args[0] == OUT and bytes(args[1]) == REQUEST)
    zyncore.log.clear()
    return n


def test_request_is_sent_once_until_answered_or_a_while_later(mgr, zyncore):
    assert mgr.request_identity(PORT) is True
    assert mgr.request_identity(PORT) is False
    assert requests(zyncore) == 1
    mgr.clock[0] += 6
    assert mgr.request_identity(PORT) is True
    assert requests(zyncore) == 1
    mgr.midi_event(PORT, OTHER_IDENTITY)
    mgr.clock[0] += 60
    assert mgr.request_identity(PORT) is False      # known
    assert mgr.request_identity(PORT, force=True) is True
    assert requests(zyncore) == 1


def test_no_request_without_an_output_or_to_internal_ports(mgr, zyncore):
    assert mgr.request_identity(PORT + 1) is False  # no output port
    assert mgr.request_identity(24) is False        # the sequencer
    assert mgr.request_identity(None) is False
    assert requests(zyncore) == 0


def test_identity_is_parsed_and_forgotten(mgr):
    mgr.midi_event(PORT, OTHER_IDENTITY)
    assert mgr.get_identity(PORT) == bytes.fromhex("41 12 34 56 78 01 02 03 04")
    assert mgr.get_identity_str(PORT) == "manufacturer 41, family 12 34, model 56 78, version 01 02 03 04"
    three_byte = bytes.fromhex("F0 7E 00 06 02 00 20 29 01 02 03 04 05 06 07 08 F7")
    mgr.midi_event(PORT, three_byte)
    assert mgr.get_identity_str(PORT).startswith("manufacturer 00 20 29, family 01 02, model 03 04")
    mgr.forget_identity(PORT)
    assert mgr.get_identity(PORT) is None


def test_unsolicited_identity_autoloads_the_matching_driver(mgr):
    assert PORT not in mgr.drivers
    mgr.midi_event(PORT, FCB_IDENTITY)
    assert type(mgr.drivers[PORT]).__name__ == FCB
    # The driver got the identity too (it gives the pedal's channel)
    assert mgr.drivers[PORT].fcb_chan == 0 and mgr.drivers[PORT].fcb_version == (0, 1, 5)


def test_identity_of_an_unknown_device_loads_nothing(mgr):
    mgr.midi_event(PORT, OTHER_IDENTITY)
    assert PORT not in mgr.drivers


def test_disabled_device_is_not_autoloaded(mgr):
    mgr.midi_event(PORT, FCB_IDENTITY)
    mgr.unload_driver(PORT, disable=True)
    mgr.midi_event(PORT, FCB_IDENTITY)
    assert PORT not in mgr.drivers


def test_loaded_driver_is_kept(mgr):
    mgr.load_driver(PORT, "zynthian_ctrldev_behringer_motor")
    mgr.midi_event(PORT, FCB_IDENTITY)
    assert type(mgr.drivers[PORT]).__name__ == "zynthian_ctrldev_behringer_motor"


def test_autoload_without_a_driver_for_the_id_asks_for_the_identity(mgr, zyncore):
    assert mgr.load_driver(PORT) is False
    assert requests(zyncore) == 1
    mgr.midi_event(PORT, FCB_IDENTITY)              # the reply
    assert type(mgr.drivers[PORT]).__name__ == FCB


def test_autoload_with_a_known_identity_loads_at_once(mgr, zyncore):
    mgr.midi_event(PORT, FCB_IDENTITY)
    mgr.unload_driver(PORT)
    zyncore.log.clear()
    assert mgr.load_driver(PORT) is True
    assert requests(zyncore) == 0
    assert type(mgr.drivers[PORT]).__name__ == FCB


def test_device_drivers_list_identity_matches_before_generic_ones(mgr):
    generic = list(mgr.available_drivers["*"])
    before = mgr.get_device_drivers(PORT)
    assert before == generic
    mgr.midi_event(PORT, OTHER_IDENTITY)
    assert mgr.get_device_drivers(PORT) == generic
    mgr.forget_identity(PORT)
    mgr.identities[PORT] = FCB_IDENTITY[5:-1]       # known, without autoloading
    drivers = mgr.get_device_drivers(PORT)
    assert drivers[0].__name__ == FCB
    assert len(drivers) == len(set(drivers))         # the FCB driver is also generic: listed once
    assert set(drivers) == set(generic)
    assert mgr.get_device_drivers(24) == []          # internal port: no generic drivers
