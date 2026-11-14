"""libzynaudioplayer on the REAL library: loading files, playback state, levels, seeking, loop and crop.

Rewritten from the legacy ``zynlibs/zynaudioplayer/unit_tests.py``, which targeted the API from before multiple
players existed (``getDuration()`` without a player id, a missing ``test.wav``). Test files are generated here.
The JACK client is ``audioplayer``; player N has ports ``out_NNa`` / ``out_NNb``.
"""

import time

import jack
import pytest

from tests.native.zynaudioplayer.conftest import PLAYING, STARTING, STOPPED, STOPPING, wait_for

pytestmark = [pytest.mark.native, pytest.mark.jack]

LEVEL_TOL = 0.03


# --- players and ports --------------------------------------------------------------------------------------
def test_add_player_creates_stereo_output_ports_and_remove_deletes_them(libplayer, capture):
    before = libplayer.get_player_count()
    client = jack.Client("zyntest_ap_ports", servername=capture.server.name, no_start_server=True)
    try:
        pid = libplayer.add_player()
        names = {p.name for p in client.get_ports(libplayer.get_jack_client_name().decode() + ":")}
        assert {f"audioplayer:out_{pid:02d}a", f"audioplayer:out_{pid:02d}b"} <= names
        assert libplayer.get_player_count() == before + 1
        libplayer.remove_player(pid)
        names = {p.name for p in client.get_ports("audioplayer:")}
        assert f"audioplayer:out_{pid:02d}a" not in names
        assert libplayer.get_player_count() == before
    finally:
        client.close()


def test_codecs(libplayer):
    codecs = libplayer.get_supported_codecs().decode().lower().split(",")
    assert {"wav", "flac", "ogg", "mp3"} <= set(codecs)
    assert libplayer.is_codec_supported(b"wav") == 1
    assert libplayer.is_codec_supported(b"not-a-codec") == 0


# --- files --------------------------------------------------------------------------------------------------
def test_load_reports_the_file_properties(player, wavs):
    assert player.load(wavs["dc"].encode())
    assert player.get_duration() == pytest.approx(1.5, abs=0.01)
    assert (player.get_channels(), player.get_samplerate(), player.get_frames()) == (2, 48000, 72000)
    assert b"WAV" in player.get_codec()
    assert player.get_filename() == wavs["dc"].encode()


def test_load_mono_file(player, wavs):
    assert player.load(wavs["mono"].encode())
    assert player.get_channels() == 1
    assert player.get_duration() == pytest.approx(1.0, abs=0.01)


def test_mono_file_plays_on_both_outputs_at_half_level(player, wavs):
    """Characterization: a mono file (0.5) is sent to left and right at 0.25 each."""
    player.load(wavs["mono"].encode())
    player.play()
    left, right = player.heard(0.2)
    assert left == pytest.approx(0.25, abs=LEVEL_TOL)
    assert right == pytest.approx(0.25, abs=LEVEL_TOL)


def test_unload_forgets_the_file(player, wavs):
    player.load(wavs["dc"].encode())
    player.unload()
    assert player.get_duration() == 0.0
    assert player.get_filename() == b""


@pytest.mark.parametrize("what", ["missing", "not-audio"])
def test_load_rejects_unusable_files(player, wavs, what):
    path = wavs["dir"] / "text.wav"
    path.write_text("this is not a wave file")
    target = "/nonexistent/dir/missing.wav" if what == "missing" else str(path)
    assert not player.load(target.encode())
    assert player.get_duration() == 0.0


def test_file_info_without_a_player(libplayer, wavs):
    assert libplayer.get_file_duration(wavs["ramp"].encode()) == pytest.approx(2.0, abs=0.01)
    assert libplayer.get_file_channels(wavs["ramp"].encode()) == 2
    assert libplayer.get_file_duration(b"/nonexistent.wav") == 0.0


# --- playback -----------------------------------------------------------------------------------------------
def test_play_state_machine(player, wavs):
    player.load(wavs["dc"].encode())
    assert player.state == STOPPED
    player.lib.start_playback(player.id)
    assert player.state in (STARTING, PLAYING)
    assert wait_for(lambda: player.state == PLAYING)
    player.lib.stop_playback(player.id)
    assert player.state in (STOPPING, STOPPED)
    assert wait_for(lambda: player.state == STOPPED)


def test_playing_outputs_the_file_on_left_and_right(player, wavs):
    player.load(wavs["dc"].encode())
    player.play()
    left, right = player.heard()
    assert left == pytest.approx(0.5, abs=LEVEL_TOL)
    assert right == pytest.approx(0.25, abs=LEVEL_TOL)


def test_nothing_is_output_when_stopped(player, wavs):
    player.load(wavs["dc"].encode())
    left, right = player.heard(0.2)
    assert (left, right) == (0.0, 0.0)


def test_position_advances_in_real_time(player, wavs):
    player.load(wavs["dc"].encode())
    player.play()
    time.sleep(0.5)
    assert player.get_position() == pytest.approx(0.5, abs=0.2)


def test_playback_stops_at_the_end_of_the_file(player, wavs):
    player.load(wavs["mono"].encode())                    # 1 s
    player.play()
    assert wait_for(lambda: player.state == STOPPED, timeout=3.0)


def test_gain(player, wavs):
    player.load(wavs["dc"].encode())
    player.set_gain(0.5)
    assert player.get_gain() == pytest.approx(0.5)
    player.play()
    left, right = player.heard()
    assert left == pytest.approx(0.25, abs=LEVEL_TOL)
    assert right == pytest.approx(0.125, abs=LEVEL_TOL)


def test_track_selection_swaps_channels(player, wavs):
    """track_a / track_b choose which file channel feeds the left / right output."""
    player.load(wavs["dc"].encode())
    player.set_track_a(1)
    player.set_track_b(0)
    assert (player.get_track_a(), player.get_track_b()) == (1, 0)
    player.play()
    left, right = player.heard()
    assert left == pytest.approx(0.25, abs=LEVEL_TOL)
    assert right == pytest.approx(0.5, abs=LEVEL_TOL)


# --- position, crop, loop, speed ----------------------------------------------------------------------------
def test_set_position_while_playing_jumps_there(player, wavs):
    player.load(wavs["ramp"].encode())                    # left = 0.45 * seconds
    player.play()
    time.sleep(0.2)
    player.set_position(1.2)
    time.sleep(0.1)
    left, _ = player.heard(0.1)
    assert left == pytest.approx(0.45 * 1.3, abs=0.12)    # ~1.3 s into the file by now
    assert player.get_position() == pytest.approx(1.4, abs=0.2)


def test_set_position_clamps_to_the_file(player, wavs):
    player.load(wavs["ramp"].encode())
    player.set_position(99.0)
    assert player.get_position() == pytest.approx(2.0, abs=0.05)
    player.set_position(-5.0)
    assert player.get_position() == 0.0


def test_start_after_seeking_while_stopped_plays_from_the_beginning(player, wavs):
    """Characterization of what the library does today, which looks unintended: get_position() reports the
    seek target (1.0 s) before playing, but starting playback outputs the file from its beginning (the ramp is
    ~0.03 here, not ~0.45). Seeking while playing works (previous test). Decide the intended behaviour and
    flip this test."""
    player.load(wavs["ramp"].encode())
    player.set_position(1.0)
    time.sleep(0.3)
    assert player.get_position() == pytest.approx(1.0, abs=0.05)
    player.play()
    left, _ = player.heard(0.1)
    assert left < 0.12


def test_crop_start_and_end_are_stored(player, wavs):
    player.load(wavs["ramp"].encode())
    player.set_crop_start_time(0.5)
    player.set_crop_end_time(1.0)
    assert player.get_crop_start_time() == pytest.approx(0.5, abs=0.01)
    assert player.get_crop_end_time() == pytest.approx(1.0, abs=0.01)


def test_crop_end_stops_playback_there(player, wavs):
    player.load(wavs["ramp"].encode())
    player.set_crop_end_time(0.6)
    player.play()
    left, _ = player.heard(0.3)
    assert left <= 0.45 * 0.6 + 0.05                       # never louder than the file at the crop end
    assert wait_for(lambda: player.state == STOPPED, timeout=2.0)


def test_crop_start_does_not_move_where_playback_begins(player, wavs):
    """Characterization, same behaviour as the seek test above: with the crop start at 0.5 s playback still
    begins at the start of the file (ramp ~0.03, not ~0.23)."""
    player.load(wavs["ramp"].encode())
    player.set_crop_start_time(0.5)
    time.sleep(0.3)
    player.play()
    left, _ = player.heard(0.1)
    assert left < 0.12


def test_loop_keeps_playing_past_the_end(player, wavs):
    player.load(wavs["dc"].encode())                      # 1.5 s
    player.enable_loop(1)
    assert player.is_loop() == 1
    player.play()
    time.sleep(2.0)
    assert player.state == PLAYING
    left, right = player.heard(0.2)
    assert left == pytest.approx(0.5, abs=LEVEL_TOL) and right == pytest.approx(0.25, abs=LEVEL_TOL)
    player.enable_loop(0)
    assert player.is_loop() == 0
    assert wait_for(lambda: player.state == STOPPED, timeout=3.0)


def test_loop_within_crop_points(player, wavs):
    player.load(wavs["ramp"].encode())
    player.set_crop_start_time(0.2)
    player.set_crop_end_time(0.6)
    player.enable_loop(1)
    player.play()
    time.sleep(1.3)                                        # > 3 passes over the 0.4 s region
    left, _ = player.heard(0.3)
    assert player.state == PLAYING
    assert 0.0 <= left <= 0.27 + 0.05                      # never beyond the crop end (0.45 * 0.6)


def test_double_speed_plays_in_half_the_time(player, wavs):
    player.load(wavs["dc"].encode())                       # 1.5 s
    player.set_speed(2.0)
    assert player.get_speed() == pytest.approx(2.0)
    started = time.monotonic()
    player.lib.start_playback(player.id)
    assert wait_for(lambda: player.state == PLAYING)
    assert wait_for(lambda: player.state == STOPPED, timeout=3.0)
    assert time.monotonic() - started < 1.3                # 0.75 s of audio time plus start-up latency


def test_pitch_and_varispeed_round_trip(player, wavs):
    player.load(wavs["dc"].encode())
    player.set_pitch_semitone(-3)
    assert player.get_pitch_semitone() == -3
    player.set_varispeed(1.5)
    assert player.get_varispeed() == pytest.approx(1.5)


# --- notifications ------------------------------------------------------------------------------------------
def test_state_changes_are_notified_to_the_callback(libplayer, player, wavs):
    """Notifications come from the library's file thread, asynchronously, and player ids are reused: let those of
    the previous test settle before looking, and only consider what follows this player's first PLAYING."""
    player.load(wavs["mono"].encode())
    time.sleep(0.3)
    libplayer.notifications.clear()
    player.play()
    assert wait_for(lambda: player.state == STOPPED, timeout=3.0)
    time.sleep(0.3)
    mine = [(st, pos) for i, st, lp, pos, vs in libplayer.notifications if i == player.id]
    first = next(n for n, (st, _) in enumerate(mine) if st == PLAYING)
    mine = mine[first:]
    assert mine[-1][0] == STOPPED
    positions = [pos for st, pos in mine if st == PLAYING]
    assert positions == sorted(positions)
    assert positions[-1] > 0.3                              # position progressed while playing


# --- saving -------------------------------------------------------------------------------------------------
def test_save_writes_the_cropped_region(player, wavs, libplayer):
    player.load(wavs["ramp"].encode())
    player.set_crop_start_time(0.5)
    player.set_crop_end_time(1.5)
    out = wavs["dir"] / "saved.wav"
    assert player.save(str(out).encode())
    assert out.is_file()
    assert libplayer.get_file_duration(str(out).encode()) == pytest.approx(1.0, abs=0.05)

