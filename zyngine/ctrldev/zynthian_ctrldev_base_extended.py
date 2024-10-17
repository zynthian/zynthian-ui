#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Control Device Manager Extended Base Classes
#
# Copyright (C) 2024 Oscar Acena <oscaracena@gmail.com>
#
# ******************************************************************************
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the LICENSE.txt file.
#
# ******************************************************************************

import time
import logging
from bisect import bisect
from threading import Thread, RLock, Event


class CONST:
    # Some MIDI event constants
    MIDI_NOTE_ON = 0x09
    MIDI_NOTE_OFF = 0x08
    MIDI_CC = 0x0B
    MIDI_PC = 0x0C
    MIDI_SYSEX = 0xF0
    MIDI_CLOCK = 0xF8
    MIDI_CONTINUE = 0xFB

    PT_SHORT = "short"
    PT_BOLD = "bold"
    PT_LONG = "long"
    PT_BOLD_TIME = 0.3
    PT_LONG_TIME = 2.0


# --------------------------------------------------------------------------
# A timer for running delayed actions
# --------------------------------------------------------------------------
class RunTimer(Thread):
    RESOLUTION = 0.1

    def __init__(self):
        super().__init__()
        self._lock = RLock()
        self._awake = Event()
        self._actions = {}

        self.daemon = True
        self.start()

    def __contains__(self, b):
        return b in self._actions

    def add(self, name, timeout, callback, *args, **kwargs):
        with self._lock:
            self._actions[name] = [timeout, callback, name, args, kwargs]
        self._awake.set()

    def update(self, name, timeout):
        with self._lock:
            action = self._actions.get(name)
            if action is None:
                return
            action[0] = timeout

    def remove(self, name):
        with self._lock:
            self._actions.pop(name, None)

    def run(self):
        while True:
            if not self._actions:
                self._awake.wait()
            self._awake.clear()
            for action in self._get_expired():
                self._run_action(*action[1:])
            time.sleep(self.RESOLUTION)
            self._update_timeouts(-self.RESOLUTION)

    def _update_timeouts(self, delta):
        delta *= 1000
        with self._lock:
            for action in self._actions.values():
                action[0] += delta

    def _get_expired(self):
        retval = []
        with self._lock:
            to_remove = []
            for name, spec in self._actions.items():
                if spec[0] > 0:
                    continue
                to_remove.append(name)
                retval.append(spec)
            for name in to_remove:
                self._actions.pop(name, None)
        return retval

    def _run_action(self, callback, name, args, kwargs):
        try:
            callback(name, *args, **kwargs)
        except Exception as ex:
            logging.error(f" error in handler: {ex}")


# --------------------------------------------------------------------------
#  A timer for running repeated actions
# --------------------------------------------------------------------------
class IntervalTimer(RunTimer):
    RESOLUTION = 0.05

    def add(self, name, timeout, callback, *args, **kwargs):
        with self._lock:
            self._actions[name] = [timeout, timeout,
                                   callback, name, args, kwargs]
        self._awake.set()

    def update(self, name, timeout):
        with self._lock:
            action = self._actions.get(name)
            if action is None:
                return
            action[1] = timeout

    def run(self):
        while True:
            if not self._actions:
                self._awake.wait()
            self._awake.clear()
            for action in self._get_expired():
                self._run_action(*action[2:])
            time.sleep(self.RESOLUTION)
            self._update_timeouts(self.RESOLUTION)

    def _get_expired(self):
        retval = []
        with self._lock:
            for spec in self._actions.values():
                if spec[0] < spec[1]:
                    continue
                retval.append(spec)
                spec[0] = 0

        return retval


# --------------------------------------------------------------------------
# A handy timer for triggering short/bold/long push actions
# --------------------------------------------------------------------------
class ButtonTimer(Thread):
    def __init__(self, callback):
        super().__init__()
        self._callback = callback
        self._lock = RLock()
        self._awake = Event()
        self._pressed = {}

        self.daemon = True
        self.start()

    def is_pressed(self, btn, ts):
        with self._lock:
            self._pressed[btn] = ts
        self._awake.set()

    def is_released(self, btn):
        with self._lock:
            ts = self._pressed.pop(btn, None)
        if ts is not None:
            elapsed = time.time() - ts
            self._run_callback(btn, elapsed)

    def run(self):
        while True:
            with self._lock:
                expired, elapsed = self._get_expired()
            if expired is not None:
                self._run_callback(expired, elapsed)

            time.sleep(0.1)
            if not self._pressed:
                self._awake.wait()
            self._awake.clear()

    def _get_expired(self):
        now = time.time()
        retval = None
        for btn, ts in self._pressed.items():
            elapsed = now - ts
            if elapsed > CONST.PT_LONG_TIME:
                retval = btn
                break
        if retval:
            self._pressed.pop(btn, None)
        return retval, elapsed if retval else 0

    def _run_callback(self, note, elapsed):
        ptype = [CONST.PT_SHORT, CONST.PT_BOLD, CONST.PT_LONG][
            bisect([CONST.PT_BOLD_TIME, CONST.PT_LONG_TIME], elapsed)]
        try:
            self._callback(note, ptype)
        except Exception as ex:
            logging.error(f" error in handler: {ex}")


# --------------------------------------------------------------------------
#  Helper class to handle knobs' speed
# --------------------------------------------------------------------------
class KnobSpeedControl:
    def __init__(self, steps_normal=3, steps_shifted=8):
        self._steps_normal = steps_normal
        self._steps_shifted = steps_shifted
        self._knobs_ease = {}

    def feed(self, ccnum, ccval, is_shifted=False):
        delta = ccval if ccval < 64 else (ccval - 128)
        count = self._knobs_ease.get(ccnum, 0)
        steps = self._steps_shifted if is_shifted else self._steps_normal

        if (delta < 0 and count > 0) or (delta > 0 and count < 0):
            count = 0
        count += delta

        if abs(count) < steps:
            self._knobs_ease[ccnum] = count
            return

        self._knobs_ease[ccnum] = 0
        return delta


# --------------------------------------------------------------------------
# Base class for mode handlers
# --------------------------------------------------------------------------
class ModeHandlerBase:

    SCREEN_CUIA_MAP = {
        "option":         "MENU",
        "main_menu":      "MENU",
        "admin":          "SCREEN_ADMIN",
        "audio_mixer":    "SCREEN_AUDIO_MIXER",
        "alsa_mixer":     "SCREEN_ALSA_MIXER",
        "control":        "SCREEN_CONTROL",
        "preset":         "PRESET",
        "zs3":            "SCREEN_ZS3",
        "snapshot":       "SCREEN_SNAPSHOT",
        "zynpad":         "SCREEN_ZYNPAD",
        "pattern_editor": "SCREEN_PATTERN_EDITOR",
        "tempo":          "TEMPO",
    }

    # These are actions requested to other handlers (shared between everyone)
    _pending_actions = []

    def __init__(self, state_manager):
        self._state_manager = state_manager
        self._chain_manager = state_manager.chain_manager
        self._zynmixer = state_manager.zynmixer
        self._zynseq = state_manager.zynseq

        self._timer = None
        self._current_screen = None
        self._is_shifted = False
        self._is_active = False

    def refresh(self):
        """Overwrite in derived class if needed."""

    def note_on(self, note, velocity, shifted_override=None):
        """Overwrite in derived class if needed."""

    def note_off(self, note, shifted_override=None):
        """Overwrite in derived class if needed."""

    def cc_change(self, ccnum, ccval):
        """Overwrite in derived class if needed."""

    def pg_change(self, program):
        """Overwrite in derived class if needed."""

    def sysex_message(self, payload):
        """Overwrite in derived class if needed."""

    def get_state(self):
        return {}

    def set_state(self, state):
        """Overwrite in derived class if needed."""

    def on_media_change(self, media, kind, state):
        """Overwrite in derived class if needed."""

    def set_active(self, active):
        """Overwrite in derived class if needed."""
        self._is_active = active

    def on_shift_changed(self, state):
        self._is_shifted = state
        return True

    def on_screen_change(self, screen):
        self._current_screen = screen

    def pop_action_request(self):
        if not self._pending_actions:
            return None
        return self._pending_actions.pop(0)

    def run_action(self, action, args, kwargs):
        action = "_action_" + action.replace("-", "_")
        action = getattr(self, action, None)
        if callable(action):
            try:
                action(*args, **kwargs)
            except Exception as ex:
                logging.error(f" error in handler: {ex}")

    def _request_action(self, receiver, action, *args, **kwargs):
        self._pending_actions.append((receiver, action, args, kwargs))

    def _stop_all_sounds(self):
        self._state_manager.send_cuia("ALL_SOUNDS_OFF")
        self._state_manager.stop_midi_playback()
        self._state_manager.stop_audio_player()

    def _on_shifted_override(self, override=None):
        if override is not None:
            self._is_shifted = override

    # FIXME: Could this be in chain_manager?
    def _get_chain_id_by_sequence(self, bank, seq):
        channel = self._libseq.getChannel(bank, seq, 0)
        return next(
            (id for id, c in self._chain_manager.chains.items()
             if c.midi_chan == channel),
            None
        )

    # FIXME: Could this (or part of this) be in libseq?
    def _get_sequence_patterns(self, bank, seq, create=False):
        seq_len = self._libseq.getSequenceLength(bank, seq)
        pattern = -1
        retval = []

        if seq_len == 0:
            if create:
                pattern = self._libseq.createPattern()
                self._libseq.addPattern(bank, seq, 0, 0, pattern)
                retval.append(pattern)
            return retval

        n_tracks = self._libseq.getTracksInSequence(bank, seq)
        for track in range(n_tracks):
            retval.extend(self._get_patterns_in_track(bank, seq, track))
        return retval

    # FIXME: Could this be in libseq?
    def _get_patterns_in_track(self, bank, seq, track):
        retval = []
        n_patts = self._libseq.getPatternsInTrack(bank, seq, track)
        if n_patts == 0:
            return retval

        seq_len = self._libseq.getSequenceLength(bank, seq)
        pos = 0
        while pos < seq_len:
            pattern = self._libseq.getPatternAt(bank, seq, track, pos)
            if pattern != -1:
                retval.append(pattern)
                pos += self._libseq.getPatternLength(pattern)
            else:
                # Arranger's offset step is a quarter note (24 clocks)
                pos += 24
        return retval

    # FIXME: Could this be in libseq?
    def _add_pattern_to_end_of_track(self, bank, seq, track, pattern):
        pos = 0
        if self._libseq.getTracksInSequence(bank, seq) != 0:
            pos = self._libseq.getSequenceLength(bank, seq)
            while pos > 0:
                # Arranger's offset step is a quarter note (24 clocks)
                if self._libseq.getPatternAt(bank, seq, track, pos - 24) != -1:
                    break
                pos -= 24

        return self._libseq.addPattern(bank, seq, track, pos, pattern)

    # FIXME: Could this be in libseq?
    def _set_note_duration(self, step, note, duration):
        velocity = self._libseq.getNoteVelocity(step, note)
        stutt_count = self._libseq.getStutterCount(step, note)
        stutt_duration = self._libseq.getStutterDur(step, note)
        self._libseq.removeNote(step, note)
        self._libseq.addNote(step, note, velocity, duration, 0)
        self._libseq.setStutterCount(step, note, stutt_count)
        self._libseq.setStutterDur(step, note, stutt_duration)

    def _show_screen_briefly(self, screen, cuia, timeout):
        # Only created when/if needed
        if self._timer is None:
            self._timer = RunTimer()

        timer_name = "change-screen"
        prev_screen = "BACK"

        # If screen is audio mixer, there is no 'back', so try to get the screen
        # name. Not all screens may be mapped, so it will fail there (only corner-cases).
        if screen == "audio_mixer":
            prev_screen = self.SCREEN_CUIA_MAP.get(
                self._current_screen, "BACK")

        if screen != self._current_screen:
            self._state_manager.send_cuia(cuia)
            self._timer.add(timer_name, timeout,
                            lambda _: self._state_manager.send_cuia(prev_screen))
        else:
            self._timer.update(timer_name, timeout)

# ----------------------------------------------------------------------------
