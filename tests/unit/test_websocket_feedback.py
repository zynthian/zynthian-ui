"""Websocket feedback of zyngui.zynthian_gui: subscriptions, "chain_state", DPM streams and helpers.

zynthian_gui can't be built in tests (its __init__ starts the whole UI), so the websocket methods run on a
bare instance (``__new__``) holding only the attributes they use, with a fake websocket server and a fake
Tk root that records ``after()`` calls instead of running them.
"""

import json
import logging
import socket
import sys
import threading
import time
from queue import SimpleQueue
from types import SimpleNamespace

import pytest

from tests.bootstrap import STUBBED_MODULES
from zyngui import zynthian_gui as gui_module
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui import zynthian_gui, zynthian_websocket_server
from zyngine.zynthian_signal_manager import zynsigman


class FakeServer:
    """Records what is sent to each client"""

    def __init__(self):
        self.sent = []

    def send_message(self, client, payload):
        self.sent.append((client["id"], json.loads(payload)))

    def to(self, client_id):
        return [msg for cid, msg in self.sent if cid == client_id]


class FakeTop:
    """Stands for the Tk root: after()/after_idle() are recorded, not run"""

    def __init__(self):
        self.calls = []

    def after(self, ms, func, *args):
        self.calls.append((ms, func, args))

    def after_idle(self, func, *args):
        self.calls.append((0, func, args))


class FakeChain(SimpleNamespace):

    def get_name(self):
        return self.name

    def get_type(self):
        return self.type


@pytest.fixture
def top(monkeypatch):
    fake = FakeTop()
    monkeypatch.setattr(zynthian_gui_config, "top", fake, raising=False)
    return fake


@pytest.fixture
def gui(top, monkeypatch):
    monkeypatch.setattr(gui_module, "sleep", lambda s: None)  # send_chain_state's coalescing delay
    g = zynthian_gui.__new__(zynthian_gui)
    g.exit_flag = False
    g.websocket_server = FakeServer()
    g.websocket_clients = {}
    g.websocket_subscriptions = {}
    g.websocket_queue = SimpleQueue()
    g.websocket_send_lock = threading.Lock()
    g.wsleds = SimpleNamespace(last_wsled_state="R,G,B")
    g.chain_state_active = False
    g.chain_state_pending = False
    g.chain_state_json = ""
    g.dpm_feedback_active = False
    g.dpm_global_sent = None
    g.dpm_state_sent = {}
    g.zynmixer_bus = SimpleNamespace(name="bus")
    g.state_manager = SimpleNamespace(zynmixer_bus=g.zynmixer_bus, zynmixer_chan=SimpleNamespace(name="chan"))
    g.chain_manager = SimpleNamespace(chains={}, active_chain=None)
    g.websocket_feedback_streams = {
        "wsled_state": lambda: g.wsleds.last_wsled_state,
        "screen_state": lambda: None,
        "dpm_global": lambda: None,
        "dpm_state": lambda: None,
        "chain_state": lambda: g.get_chain_state(),
    }
    yield g
    # Never leave callbacks registered in the global signal manager
    g.websocket_subscriptions.clear()
    g.chain_state_sync()


def connect(g, client_id):
    client = {"id": client_id}
    g.websocket_clients[client_id] = client
    g.websocket_subscriptions[client_id] = set()
    return client


def registered(callback):
    return [(s, ss) for s, ss in zynthian_gui.chain_state_signals
            if any(rdata[0] == callback for rdata in zynsigman.signal_register[s][ss])]


def drain(queue):
    items = []
    while not queue.empty():
        items.append(queue.get())
    return items


# --- subscription commands ----------------------------------------------------------------------------------

def test_subscribe_sends_current_value_then_subscriptions(gui):
    c = connect(gui, 1)
    gui.websocket_command(c, "/subscribe wsled_state")
    assert gui.websocket_server.to(1) == [{"wsled_state": "R,G,B"}, {"subscriptions": ["wsled_state"]}]


def test_subscribing_twice_doesnt_resend_the_value(gui):
    c = connect(gui, 1)
    gui.websocket_command(c, "/subscribe wsled_state")
    gui.websocket_server.sent.clear()
    gui.websocket_command(c, "/subscribe wsled_state")
    assert gui.websocket_server.to(1) == [{"subscriptions": ["wsled_state"]}]


def test_unsubscribe_one_and_all(gui):
    c = connect(gui, 1)
    gui.websocket_command(c, "/subscribe wsled_state screen_state")
    gui.websocket_command(c, "/unsubscribe wsled_state")
    assert gui.websocket_subscriptions[1] == {"screen_state"}
    gui.websocket_command(c, "/unsubscribe *")
    assert gui.websocket_subscriptions[1] == set()
    assert gui.websocket_server.to(1)[-1] == {"subscriptions": []}


def test_unknown_stream_is_reported_and_ignored(gui):
    c = connect(gui, 1)
    gui.websocket_command(c, "/subscribe nope wsled_state")
    msgs = gui.websocket_server.to(1)
    assert any("error" in m and "nope" in m["error"] for m in msgs)
    assert msgs[-1] == {"subscriptions": ["wsled_state"]}


@pytest.mark.parametrize("command", ["/subscribe", "/bogus x", "/unsubscribe"])
def test_bad_commands_get_an_error(gui, command):
    c = connect(gui, 1)
    gui.websocket_command(c, command)
    assert "error" in gui.websocket_server.to(1)[-1]
    assert gui.websocket_subscriptions[1] == set()


def test_broadcast_reaches_only_subscribers(gui):
    a, b = connect(gui, 1), connect(gui, 2)
    gui.websocket_command(a, "/subscribe wsled_state")
    gui.websocket_server.sent.clear()
    gui.websocket_broadcast("wsled_state", "G,G")
    assert gui.websocket_server.to(1) == [{"wsled_state": "G,G"}]
    assert gui.websocket_server.to(2) == []


def test_subscribing_feedback_streams_schedules_their_sync(gui, top):
    c = connect(gui, 1)
    gui.websocket_command(c, "/subscribe screen_state dpm_global dpm_state")
    funcs = [(f.__name__, args) for _, f, args in top.calls]
    assert ("screen_state_sync", (True,)) in funcs
    # Both DPM streams in one command => a single DPM sync with both names
    assert funcs.count(("dpm_feedback_sync", (["dpm_global", "dpm_state"],))) == 1


# --- "chain_state" ------------------------------------------------------------------------------------------

def test_chain_state_signals_are_registered_only_while_subscribed(gui):
    assert registered(gui.cb_chain_state) == []
    a, b = connect(gui, 1), connect(gui, 2)
    gui.websocket_command(a, "/subscribe chain_state")
    gui.websocket_command(b, "/subscribe chain_state")
    assert len(registered(gui.cb_chain_state)) == len(zynthian_gui.chain_state_signals)
    gui.websocket_command(a, "/unsubscribe *")
    assert len(registered(gui.cb_chain_state)) == len(zynthian_gui.chain_state_signals)  # b still subscribed
    gui.websocket_command(b, "/unsubscribe chain_state")
    assert registered(gui.cb_chain_state) == []


def test_chain_state_signals_cover_midi_chan_and_state_loading():
    signals = set(zynthian_gui.chain_state_signals)
    assert (zynsigman.S_CHAIN_MAN, zynsigman.SS_SET_MIDI_CHAN) in signals
    assert (zynsigman.S_STATE_MAN, zynsigman.SS_LOAD_SNAPSHOT) in signals
    assert (zynsigman.S_STATE_MAN, zynsigman.SS_LOAD_ZS3) in signals


def test_chain_state_callbacks_queue_one_update(gui):
    for _ in range(5):
        gui.cb_chain_state(active_chain_id=1)
    assert drain(gui.websocket_queue) == [("chain_state", None)]


def test_chain_state_is_sent_only_when_it_changes(gui):
    c = connect(gui, 1)
    gui.websocket_subscriptions[1].add("chain_state")
    gui.chain_manager.chains = {0: FakeChain(name="Main", title="Main", type="Audio Effect", midi_chan=None,
                                             zmop_index=None, zynmixer_proc=None, audio_thru=True, midi_thru=False)}
    gui.send_chain_state()
    gui.send_chain_state()
    assert len(gui.websocket_server.to(1)) == 1
    gui.chain_manager.chains[0].title = "Master"
    gui.send_chain_state()
    assert len(gui.websocket_server.to(1)) == 2


def test_get_chain_state_fields(gui):
    synth_mixer = SimpleNamespace(zynmixer=gui.state_manager.zynmixer_chan, mixer_chan=3)
    main_mixer = SimpleNamespace(zynmixer=gui.zynmixer_bus, mixer_chan=0)
    synth = FakeChain(chain_id=5, name="2#Pad", title="", type="MIDI Synth", midi_chan=1, zmop_index=4,
                      zynmixer_proc=synth_mixer, audio_thru=False, midi_thru=False)
    allchan = FakeChain(chain_id=6, name="ALL#Tool", title="My tool", type="MIDI Tool", midi_chan=0xffff,
                        zmop_index=5, zynmixer_proc=None, audio_thru=False, midi_thru=True)
    main = FakeChain(chain_id=0, name="Main", title="Main", type="Audio Effect", midi_chan=None, zmop_index=None,
                     zynmixer_proc=main_mixer, audio_thru=True, midi_thru=False)
    gui.chain_manager.chains = {5: synth, 6: allchan, 0: main}
    gui.chain_manager.active_chain = synth
    state = gui.get_chain_state()
    assert state["active"] == 5
    assert [c["id"] for c in state["chains"]] == [5, 6, 0]
    assert [c["index"] for c in state["chains"]] == [0, 1, 2]     # display order, as the MIXER CUIA uses
    s, t, m = state["chains"]
    assert s["midi_chan"] == 2 and t["midi_chan"] == "all" and m["midi_chan"] is None   # 1-based / "all"
    assert s["mixer"] == {"bus": False, "strip": 3}
    assert m["mixer"] == {"bus": True, "strip": 0}
    assert t["mixer"] is None
    assert t["title"] == "My tool" and t["midi_thru"] is True
    json.dumps(state)


# --- DPM ----------------------------------------------------------------------------------------------------

def dpm(a=1.0, b=1.0, a_hold=1.0, b_hold=1.0):
    """zynmixer DPM values are inverted: 1.0 = silence, 0.0 = 0dBFS"""
    return SimpleNamespace(a=a, b=b, a_hold=a_hold, b_hold=b_hold)


def test_dpm_levels_are_inverted_and_rounded():
    assert zynthian_gui.get_dpm_levels(dpm(1.0, 0.0, 0.5, 0.123)) == [0.0, 1.0, 0.5, 0.88]


@pytest.fixture
def mixers(gui):
    """Fake zynmixers: one channel strip (chain 1) and the main bus (chain 0)"""
    updates = []
    chan = SimpleNamespace(dpm=[dpm()], update_dpm_states=lambda count=0: updates.append(("chan", count)),
                           enable_dpm=lambda enable: None)
    bus = SimpleNamespace(dpm=[dpm()], update_dpm_states=lambda count=0: updates.append(("bus", count)),
                          enable_dpm=lambda enable: None)
    gui.state_manager.zynmixer_chan, gui.state_manager.zynmixer_bus = chan, bus
    gui.chain_manager.chains = {
        1: SimpleNamespace(zynmixer_proc=SimpleNamespace(zynmixer=chan, mixer_chan=0)),
        0: SimpleNamespace(zynmixer_proc=SimpleNamespace(zynmixer=bus, mixer_chan=0)),
    }
    return SimpleNamespace(chan=chan, bus=bus, updates=updates)


def queued(gui):
    return [json.loads(payload) for _, payload in drain(gui.websocket_queue)]


def test_dpm_sampling_runs_only_while_subscribed(gui, top, mixers):
    gui.dpm_feedback_sync()
    assert not gui.dpm_feedback_active and top.calls == [] and mixers.updates == []
    connect(gui, 1)
    gui.websocket_subscriptions[1].add("dpm_global")
    gui.dpm_feedback_sync(["dpm_global"])
    assert gui.dpm_feedback_active
    assert [f.__name__ for _, f, _ in top.calls] == ["dpm_feedback_task"]   # next sample scheduled
    assert mixers.updates == [("bus", 1)]                                     # global only reads the main bus
    gui.websocket_subscriptions[1].clear()
    gui.dpm_feedback_sync()
    assert not gui.dpm_feedback_active
    top.calls.clear()
    gui.dpm_feedback_task()                                                   # a pending tick stops by itself
    assert top.calls == []


def test_dpm_global_sends_only_changes(gui, mixers):
    connect(gui, 1)
    gui.websocket_subscriptions[1].add("dpm_global")
    gui.dpm_feedback_sync(["dpm_global"])
    gui.dpm_feedback_task()                                                    # silence again: nothing
    mixers.bus.dpm[0] = dpm(0.5, 0.5, 0.25, 0.25)
    gui.dpm_feedback_task()
    assert queued(gui) == [{"dpm_global": [0.0, 0.0, 0.0, 0.0]}, {"dpm_global": [0.5, 0.5, 0.75, 0.75]}]


def test_dpm_state_sends_full_then_changed_chains_and_removals(gui, mixers):
    connect(gui, 1)
    gui.websocket_subscriptions[1].add("dpm_state")
    gui.dpm_feedback_sync(["dpm_state"])
    first = queued(gui)
    assert first == [{"dpm_state": {"1": [0.0] * 4, "0": [0.0] * 4}}]
    mixers.chan.dpm[0] = dpm(0.5, 0.5, 0.5, 0.5)
    gui.dpm_feedback_task()
    assert queued(gui) == [{"dpm_state": {"1": [0.5] * 4}}]                 # only the chain that changed
    del gui.chain_manager.chains[1]
    gui.dpm_feedback_task()
    assert queued(gui) == [{"dpm_state": {"1": None}}]                      # removed chain
    gui.dpm_feedback_task()
    assert queued(gui) == []


def test_new_subscriber_gets_the_full_dpm_state(gui, mixers):
    connect(gui, 1)
    gui.websocket_subscriptions[1].add("dpm_state")
    gui.dpm_feedback_sync(["dpm_state"])
    queued(gui)
    connect(gui, 2)
    gui.websocket_subscriptions[2].add("dpm_state")
    gui.dpm_feedback_sync(["dpm_state"])
    gui.dpm_feedback_task()
    assert queued(gui) == [{"dpm_state": {"1": [0.0] * 4, "0": [0.0] * 4}}]


# --- "screen_state" diff ------------------------------------------------------------------------------------

def test_state_diff_returns_nested_changes():
    old = {"screen": "cc", "title": "A", "zyngui_chain_control": {"zyngui_selector": {"items": ["x"], "selected": 0}}}
    new = {"screen": "cc", "title": "A", "zyngui_chain_control": {"zyngui_selector": {"items": ["x"], "selected": 1}}}
    assert zynthian_gui.get_state_diff(old, new) == {"zyngui_chain_control": {"zyngui_selector": {"selected": 1}}}
    assert zynthian_gui.get_state_diff(old, old) == {}


def test_state_diff_is_none_when_a_key_is_removed():
    old = {"screen": "cc", "zyngui_chain_control": {"chain_blocks": {"selected": 1}, "zyngui_selector": {}}}
    new = {"screen": "cc", "zyngui_chain_control": {"zyngui_selector": {}}}
    assert zynthian_gui.get_state_diff(old, new) is None


def test_state_diff_includes_added_parts():
    old = {"screen": "cc", "zyngui_chain_control": {"zyngui_selector": {"selected": 1}}}
    new = {"screen": "cc", "zyngui_chain_control": {"chain_blocks": {"items": ["a"], "selected": 0},
                                                    "zyngui_selector": {"selected": 1}}}
    assert zynthian_gui.get_state_diff(old, new) == {
        "zyngui_chain_control": {"chain_blocks": {"items": ["a"], "selected": 0}}}


def test_screen_title_of_views_without_breadcrumb():
    assert zynthian_gui.get_screen_title(SimpleNamespace()) == ""
    assert zynthian_gui.get_screen_title(SimpleNamespace(select_path=SimpleNamespace(get=lambda: "A/B"))) == "A/B"


# --- websocket server ---------------------------------------------------------------------------------------

@pytest.mark.skipif("websocket_server" in STUBBED_MODULES,
                    reason="needs the websocket-server package (stubbed by tests/bootstrap.py when missing)")
def test_connections_failing_the_handshake_dont_print_a_traceback(capsys, caplog):
    """Port probes (connect + close) are logged as debug instead of printing socketserver's traceback"""
    server = zynthian_websocket_server(host="127.0.0.1", port=0)
    threading.Thread(target=server.run_forever, daemon=True).start()
    try:
        with caplog.at_level(logging.DEBUG):
            socket.create_connection(("127.0.0.1", server.server_address[1]), timeout=1).close()
            deadline = time.monotonic() + 2
            while not any("failed" in r.getMessage() for r in caplog.records) and time.monotonic() < deadline:
                time.sleep(0.01)
    finally:
        server.shutdown_gracefully()
    assert any(r.levelno == logging.DEBUG and "AssertionError" in r.getMessage() for r in caplog.records)
    assert "Exception occurred during processing" not in capsys.readouterr().err
