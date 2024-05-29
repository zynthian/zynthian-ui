#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Akai APC Key 25 mk2"
#
# Copyright (C) 2023,2024 Oscar Aceña <oscaracena@gmail.com>
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
import signal
import jack
import logging
from bisect import bisect
from copy import deepcopy
from functools import partial
import multiprocessing as mp
from threading import Thread, RLock, Event

from zynlibs.zynseq import zynseq
from zyncoder.zyncore import lib_zyncore
from zyngine.zynthian_signal_manager import zynsigman
from zyngine.zynthian_engine_audioplayer import zynthian_engine_audioplayer

from .zynthian_ctrldev_base import (
    zynthian_ctrldev_zynmixer, zynthian_ctrldev_zynpad
)
from .zynthian_ctrldev_base_extended import (
    RunTimer, KnobSpeedControl, ButtonTimer, CONST
)
from .zynthian_ctrldev_base_ui import ModeHandlerBase


# FIXME: these defines should be taken from where they are defined (zynseq.h)
MAX_STUTTER_COUNT                    = 32
MAX_STUTTER_DURATION                 = 96

# MIDI channel events (first 4 bits), next 4 bits is the channel!
EV_NOTE_ON                           = 0x09
EV_NOTE_OFF                          = 0x08
EV_CC                                = 0x0B

# MIDI system events (first 8 bits)
EV_SYSEX                             = 0xF0
EV_CLOCK                             = 0xF8
EV_CONTINUE                          = 0xFB

# APC Key25 buttons
BTN_SHIFT                            = 0x62
BTN_STOP_ALL_CLIPS                   = 0x51
BTN_PLAY                             = 0x5B
BTN_RECORD                           = 0x5D

BTN_TRACK_1 = BTN_UP                 = 0x40
BTN_TRACK_2 = BTN_DOWN               = 0x41
BTN_TRACK_3 = BTN_LEFT               = 0x42
BTN_TRACK_4 = BTN_RIGHT              = 0x43
BTN_TRACK_5 = BTN_KNOB_CTRL_VOLUME   = 0x44
BTN_TRACK_6 = BTN_KNOB_CTRL_PAN      = 0x45
BTN_TRACK_7 = BTN_KNOB_CTRL_SEND     = 0x46
BTN_TRACK_8 = BTN_KNOB_CTRL_DEVICE   = 0x47

BTN_SOFT_KEY_START                   = 0x52
BTN_SOFT_KEY_END                     = 0x56
BTN_SOFT_KEY_CLIP_STOP = BTN_KNOB_1  = 0x52
BTN_SOFT_KEY_SOLO = BTN_KNOB_2       = 0x53
BTN_SOFT_KEY_MUTE = BTN_KNOB_3       = 0x54
BTN_SOFT_KEY_REC_ARM = BTN_KNOB_4    = 0x55
BTN_SOFT_KEY_SELECT                  = 0x56

BTN_PAD_START                        = 0x00
BTN_PAD_END                          = 0x27
BTN_PAD_29 = BTN_ALT                 = 0x1C
BTN_PAD_30 = BTN_METRONOME           = 0x1D
BTN_PAD_31 = BTN_PAD_STEP            = 0x1E
BTN_PAD_37 = BTN_OPT_ADMIN           = 0x24
BTN_PAD_38 = BTN_MIX_LEVEL           = 0x25
BTN_PAD_39 = BTN_CTRL_PRESET         = 0x26
BTN_PAD_40 = BTN_ZS3_SHOT            = 0x27
BTN_PAD_5 = BTN_PAD_LEFT             = 0x04
BTN_PAD_6 = BTN_PAD_DOWN             = 0x05
BTN_PAD_7 = BTN_PAD_RIGHT            = 0x06
BTN_PAD_8 = BTN_F4                   = 0x07
BTN_PAD_13 = BTN_BACK_NO             = 0x0C
BTN_PAD_14 = BTN_PAD_UP              = 0x0D
BTN_PAD_15 = BTN_SEL_YES             = 0x0E
BTN_PAD_16 = BTN_F3                  = 0x0F
BTN_PAD_21 = BTN_PAD_RECORD          = 0x14
BTN_PAD_23 = BTN_PAD_PLAY            = 0x16
BTN_PAD_24 = BTN_F2                  = 0x17
BTN_PAD_32 = BTN_F1                  = 0x1F

# APC Key25 knobs
KNOB_1 = KNOB_LAYER                  = 0x30
KNOB_2 = KNOB_SNAPSHOT               = 0x31
KNOB_3                               = 0x32
KNOB_4                               = 0x33
KNOB_5 = KNOB_BACK                   = 0x34
KNOB_6 = KNOB_SELECT                 = 0x35
KNOB_7                               = 0x36
KNOB_8                               = 0x37

# APC Key25 LED colors and modes
COLOR_RED                            = 0x05
COLOR_GREEN                          = 0x15
COLOR_BLUE                           = 0x25
COLOR_AQUA                           = 0x21
COLOR_BLUE_DARK                      = 0x2D
COLOR_WHITE                          = 0x08
COLOR_EGYPT                          = 0x6C
COLOR_ORANGE                         = 0x09
COLOR_AMBER                          = 0x54
COLOR_RUSSET                         = 0x3D
COLOR_PURPLE                         = 0x51
COLOR_PINK                           = 0x39
COLOR_PINK_LIGHT                     = 0x52
COLOR_PINK_WARM                      = 0x38
COLOR_YELLOW                         = 0x0D
COLOR_LIME                           = 0x4B
COLOR_LIME_DARK                      = 0x11
COLOR_GREEN_YELLOW                   = 0x4A

LED_BRIGHT_10                        = 0x00
LED_BRIGHT_25                        = 0x01
LED_BRIGHT_50                        = 0x02
LED_BRIGHT_65                        = 0x03
LED_BRIGHT_75                        = 0x04
LED_BRIGHT_90                        = 0x05
LED_BRIGHT_100                       = 0x06
LED_PULSING_16                       = 0x07
LED_PULSING_8                        = 0x08
LED_PULSING_4                        = 0x09
LED_PULSING_2                        = 0x0A
LED_BLINKING_24                      = 0x0B
LED_BLINKING_16                      = 0x0C
LED_BLINKING_8                       = 0x0D
LED_BLINKING_4                       = 0x0E
LED_BLINKING_2                       = 0x0F

# Function/State constants
FN_VOLUME                            = 0x01
FN_PAN                               = 0x02
FN_SOLO                              = 0x03
FN_MUTE                              = 0x04
FN_REC_ARM                           = 0x05
FN_SELECT                            = 0x06
FN_SCENE                             = 0x07
FN_SEQUENCE_MANAGER                  = 0x08
FN_COPY_SEQUENCE                     = 0x09
FN_MOVE_SEQUENCE                     = 0x0A
FN_CLEAR_SEQUENCE                    = 0x0B
FN_PLAY_NOTE                         = 0x0C
FN_REMOVE_NOTE                       = 0x0D
FN_REMOVE_PATTERN                    = 0x0F
FN_SELECT_PATTERN                    = 0x10
FN_CLEAR_PATTERN                     = 0x11


# --------------------------------------------------------------------------
# 'Akai APC Key 25 mk2' device controller class
# --------------------------------------------------------------------------
class zynthian_ctrldev_akai_apc_key25_mk2(zynthian_ctrldev_zynmixer, zynthian_ctrldev_zynpad):

    dev_ids = ["APC Key 25 mk2 MIDI 2", "APC Key 25 mk2 IN 2"]

    def __init__(self, state_manager, idev_in, idev_out=None):
        self._leds = FeedbackLEDs(idev_out)
        self._device_handler = DeviceHandler(state_manager, self._leds)
        self._mixer_handler = MixerHandler(state_manager, self._leds)
        self._padmatrix_handler = PadMatrixHandler(state_manager, self._leds)
        self._stepseq_handler = StepSeqHandler(state_manager, self._leds, idev_in)
        self._current_handler = self._mixer_handler
        self._is_shifted = False

        self._signals = [
            (zynsigman.S_GUI,
                zynsigman.SS_GUI_SHOW_SCREEN,
                self._on_gui_show_screen),

            (zynsigman.S_AUDIO_PLAYER,
                zynthian_engine_audioplayer.SS_AUDIO_PLAYER_STATE,
                lambda handle, state:
                    self._on_media_change_state(state, f"audio-{handle}", "player")),

            (zynsigman.S_AUDIO_RECORDER,
                state_manager.audio_recorder.SS_AUDIO_RECORDER_STATE,
                partial(self._on_media_change_state, media="audio", kind="recorder")),

            (zynsigman.S_STATE_MAN,
                state_manager.SS_MIDI_PLAYER_STATE,
                partial(self._on_media_change_state, media="midi", kind="player")),

            (zynsigman.S_STATE_MAN,
                state_manager.SS_MIDI_RECORDER_STATE,
                partial(self._on_media_change_state, media="midi", kind="recorder")),
        ]

        # NOTE: init will call refresh(), so _current_hanlder must be ready!
        super().__init__(state_manager, idev_in, idev_out)

    def init(self):
        super().init()
        for signal, subsignal, callback in self._signals:
            zynsigman.register(signal, subsignal, callback)

    def end(self):
        for signal, subsignal, callback in self._signals:
            zynsigman.unregister(signal, subsignal, callback)
        super().end()

    def refresh(self):
        # PadMatrix is handled in volume/pan modes (when mixer handler is active)
        self._current_handler.refresh()
        if self._current_handler == self._mixer_handler:
            self._padmatrix_handler.refresh()

    def midi_event(self, ev):
        if self._on_midi_event(ev):
            while True:
                action = self._current_handler.pop_action_request()
                if not action:
                    return True

                # NOTE: Add other receivers as needed
                receiver, action, args, kwargs = action
                if receiver == "stepseq":
                    self._stepseq_handler.run_action(action, args, kwargs)
        return False

    def _on_midi_event(self, ev):
        evtype = (ev[0] >> 4) & 0x0F

        if evtype == EV_NOTE_ON:
            note = ev[1] & 0x7F
            vel = ev[2] & 0x7F

            if note == BTN_SHIFT:
                return self._on_shift_changed(True)

            if self._is_shifted:
                old_handler = self._current_handler
                # Change global mode here
                if note == BTN_KNOB_CTRL_DEVICE:
                    self._current_handler = self._device_handler
                elif note in [BTN_KNOB_CTRL_PAN, BTN_KNOB_CTRL_VOLUME]:
                    self._current_handler = self._mixer_handler
                    self._padmatrix_handler.refresh()
                elif note == BTN_KNOB_CTRL_SEND:
                    self._current_handler = self._stepseq_handler

                if old_handler != self._current_handler:
                    old_handler.set_active(False)
                    self._current_handler.set_active(True)

                # Change sub-modes here
                if self._current_handler == self._mixer_handler:
                    if note == BTN_SOFT_KEY_CLIP_STOP:
                        self._padmatrix_handler.enable_seqman(True)
                    elif BTN_SOFT_KEY_SOLO <= note <= BTN_SOFT_KEY_END:
                        self._padmatrix_handler.enable_seqman(False)

            # Padmatrix related events
            if self._current_handler == self._mixer_handler:
                if BTN_PAD_START <= note <= BTN_PAD_END:

                    # Launch StepSeq directly from SHIFT + PAD
                    if self._is_shifted:
                        seq = self._padmatrix_handler.get_sequence_from_pad(note)
                        if seq is None:
                            return False
                        if self._current_handler != self._stepseq_handler:
                            self._current_handler.set_active(False)
                        self._current_handler = self._stepseq_handler
                        self._current_handler.set_sequence(seq)
                        self._current_handler.set_active(True)
                        self._current_handler.refresh(shifted_override=self._is_shifted)
                        return True

                    return self._padmatrix_handler.pad_press(note)

                # FIXME: move these events to padmatrix handler itself
                elif note == BTN_RECORD and not self._is_shifted:
                    return self._padmatrix_handler.on_record_changed(True)
                elif note == BTN_PLAY:
                    if not self._is_shifted:
                        return self._padmatrix_handler.on_toggle_play()
                    self._padmatrix_handler.note_on(note, vel, self._is_shifted)
                elif (BTN_SOFT_KEY_START <= note <= BTN_SOFT_KEY_END
                      and not self._is_shifted):
                    row = note - BTN_SOFT_KEY_START
                    return self._padmatrix_handler.on_toggle_play_row(row)
                elif BTN_TRACK_1 <= note <= BTN_TRACK_8:
                    track = note - BTN_TRACK_1
                    self._padmatrix_handler.on_track_changed(track, True)
                    self._current_handler.note_on(note, vel, self._is_shifted)
                    self._padmatrix_handler.refresh()
                    return True
                elif note == BTN_STOP_ALL_CLIPS:
                    self._padmatrix_handler.note_on(note, vel, self._is_shifted)

            return self._current_handler.note_on(note, vel, self._is_shifted)

        elif evtype == EV_NOTE_OFF:
            note = ev[1] & 0x7F

            if note == BTN_SHIFT:
                return self._on_shift_changed(False)

            # Padmatrix related events
            if self._current_handler == self._mixer_handler:
                if note == BTN_RECORD:
                    return self._padmatrix_handler.on_record_changed(False)
                elif BTN_TRACK_1 <= note <= BTN_TRACK_8:
                    track = note - BTN_TRACK_1
                    self._padmatrix_handler.on_track_changed(track, False)
                elif note == BTN_STOP_ALL_CLIPS:
                    self._padmatrix_handler.note_off(note, self._is_shifted)

            return self._current_handler.note_off(note, self._is_shifted)

        elif evtype == EV_CC:
            ccnum = ev[1] & 0x7F
            ccval = ev[2] & 0x7F
            return self._current_handler.cc_change(ccnum, ccval)

        elif ev[0] == EV_SYSEX:
            logging.info(f" received SysEx => {ev}")
            return True

    def light_off(self):
        self._leds.all_off()

    def update_mixer_strip(self, chan, symbol, value):
        if self._current_handler == self._mixer_handler:
            self._current_handler.update_strip(chan, symbol, value)

    def update_mixer_active_chain(self, active_chain):
        refresh = self._current_handler == self._mixer_handler
        self._mixer_handler.set_active_chain(active_chain, refresh)

    def update_seq_state(self, *args, **kwargs):
        if self._current_handler == self._mixer_handler:
            self._padmatrix_handler.update_seq_state(*args, **kwargs)
        elif self._current_handler == self._stepseq_handler:
            self._current_handler.update_seq_state(*args, **kwargs)

    def get_state(self):
        state = {}
        state.update(self._stepseq_handler.get_state())
        return state

    def set_state(self, state):
        self._stepseq_handler.set_state(state)

    def _on_shift_changed(self, state):
        self._is_shifted = state
        self._current_handler.on_shift_changed(state)
        if self._current_handler == self._mixer_handler:
            self._padmatrix_handler.on_shift_changed(state)
        return True

    def _on_gui_show_screen(self, screen):
        self._device_handler.on_screen_change(screen)
        self._padmatrix_handler.on_screen_change(screen)
        self._stepseq_handler.on_screen_change(screen)
        if self._current_handler == self._device_handler:
            self._current_handler.refresh()

    def _on_media_change_state(self, state, media, kind):
        self._current_handler.on_media_change(media, kind, state)
        if self._current_handler == self._device_handler:
            self._current_handler.refresh()


# --------------------------------------------------------------------------
# Feedback LEDs controller
# --------------------------------------------------------------------------
class FeedbackLEDs:
    def __init__(self, idev):
        self._idev = idev
        self._state = {}
        self._timer = RunTimer()

    def all_off(self):
        self.control_leds_off()
        self.pad_leds_off()

    def control_leds_off(self):
        buttons = [
            BTN_UP, BTN_DOWN, BTN_LEFT, BTN_RIGHT, BTN_KNOB_CTRL_VOLUME,
            BTN_KNOB_CTRL_PAN, BTN_KNOB_CTRL_SEND, BTN_KNOB_CTRL_DEVICE,
            BTN_SOFT_KEY_CLIP_STOP, BTN_SOFT_KEY_MUTE, BTN_SOFT_KEY_SOLO,
            BTN_SOFT_KEY_REC_ARM, BTN_SOFT_KEY_SELECT,
        ]
        for btn in buttons:
            self.led_off(btn)

    def pad_leds_off(self):
        buttons = [btn for btn in range(BTN_PAD_START, BTN_PAD_END + 1)]
        for btn in buttons:
            self.led_off(btn)

    def led_state(self, led, state):
        (self.led_on if state else self.led_off)(led)

    def led_off(self, led, overlay=False):
        self._timer.remove(led)
        lib_zyncore.dev_send_note_on(self._idev, 0, led, 0)
        if not overlay:
            self._state[led] = (0, 0)

    def led_on(self, led, color=1, brightness=0, overlay=False):
        self._timer.remove(led)
        lib_zyncore.dev_send_note_on(self._idev, brightness, led, color)
        if not overlay:
            self._state[led] = (color, brightness)

    def led_blink(self, led):
        self._timer.remove(led)
        lib_zyncore.dev_send_note_on(self._idev, 0, led, 2)

    def remove_overlay(self, led):
        old_state = self._state.get(led)
        if old_state:
            self.led_on(led, *old_state)
        else:
            self._timer.remove(led)
            lib_zyncore.dev_send_note_on(self._idev, 0, led, 0)

    def delayed(self, action, timeout, led, *args, **kwargs):
        action = getattr(self, action)
        self._timer.add(led, timeout, action, *args, **kwargs)

    def clear_delayed(self, led):
        self._timer.remove(led)


# --------------------------------------------------------------------------
# Handle GUI (device mode)
# --------------------------------------------------------------------------
class DeviceHandler(ModeHandlerBase):
    def __init__(self, state_manager, leds: FeedbackLEDs):
        super().__init__(state_manager)
        self._leds = leds
        self._knobs_ease = KnobSpeedControl()
        self._is_alt_active = False
        self._is_playing = set()
        self._is_recording = set()
        self._btn_timer = ButtonTimer(self._handle_timed_button)

        self._btn_actions = {
            BTN_OPT_ADMIN:      ("MENU", "SCREEN_ADMIN"),
            BTN_MIX_LEVEL:      ("SCREEN_AUDIO_MIXER", "SCREEN_ALSA_MIXER"),
            BTN_CTRL_PRESET:    ("SCREEN_CONTROL", "PRESET", "SCREEN_BANK"),
            BTN_ZS3_SHOT:       ("SCREEN_ZS3", "SCREEN_SNAPSHOT"),
            BTN_PAD_STEP:       ("SCREEN_ZYNPAD", "SCREEN_PATTERN_EDITOR"),
            BTN_METRONOME:      ("TEMPO",),
            BTN_RECORD:         ("TOGGLE_RECORD",),
            BTN_PLAY: (
                lambda is_bold: [
                    "AUDIO_FILE_LIST" if is_bold else "TOGGLE_PLAY"
                ]
            ),
            BTN_STOP_ALL_CLIPS: (
                lambda is_bold: [
                    "ALL_SOUNDS_OFF" if is_bold else "STOP"
                ]
            ),
            BTN_KNOB_1: (lambda is_bold: [f"V5_ZYNPOT_SWITCH:0,{'B' if is_bold else 'S'}"]),
            BTN_KNOB_2: (lambda is_bold: [f"V5_ZYNPOT_SWITCH:1,{'B' if is_bold else 'S'}"]),
            BTN_KNOB_3: (lambda is_bold: [f"V5_ZYNPOT_SWITCH:2,{'B' if is_bold else 'S'}"]),
            BTN_KNOB_4: (lambda is_bold: [f"V5_ZYNPOT_SWITCH:3,{'B' if is_bold else 'S'}"]),
        }

        self._btn_states = {k:-1 for k in self._btn_actions}

    def refresh(self):
        self._leds.all_off()

        # On this mode, DEVICE led is always lit
        self._leds.led_blink(BTN_KNOB_CTRL_DEVICE)

        # Lit up fixed buttons
        for btn in [BTN_PAD_UP, BTN_PAD_DOWN, BTN_PAD_LEFT, BTN_PAD_RIGHT]:
            self._leds.led_on(btn, COLOR_YELLOW, LED_BRIGHT_100)
        self._leds.led_on(BTN_SEL_YES, COLOR_GREEN, LED_BRIGHT_100)
        self._leds.led_on(BTN_BACK_NO, COLOR_RED, LED_BRIGHT_100)

        # Lit up alt-related buttons
        alt_color = COLOR_BLUE_DARK if not self._is_alt_active else COLOR_PURPLE
        fn_color = COLOR_WHITE if not self._is_alt_active else COLOR_PURPLE
        for btn in [BTN_F1, BTN_F2, BTN_F3, BTN_F4]:
            self._leds.led_on(btn, fn_color, LED_BRIGHT_100)
        self._leds.led_on(BTN_ALT, alt_color, LED_BRIGHT_100)

        # Lit up state-full control buttons
        for btn, state in self._btn_states.items():
            color = [COLOR_GREEN, COLOR_ORANGE, COLOR_BLUE][state]
            self._leds.led_on(btn, color, LED_BRIGHT_100)

        # Lit up play/record buttons
        if self._is_playing:
            self._leds.led_on(BTN_PAD_PLAY, COLOR_LIME, LED_BLINKING_8)
        if self._is_recording:
            self._leds.led_on(BTN_PAD_RECORD, COLOR_RED, LED_BLINKING_8)

    def note_on(self, note, velocity, shifted_override=None):
        self._on_shifted_override(shifted_override)
        if self._is_shifted:
            if note == BTN_KNOB_CTRL_DEVICE:
                self.refresh()
                return True
        else:
            if note in (BTN_UP, BTN_PAD_UP):
                self._state_manager.send_cuia("ARROW_UP")
            elif note in (BTN_DOWN, BTN_PAD_DOWN):
                self._state_manager.send_cuia("ARROW_DOWN")
            elif note in (BTN_LEFT, BTN_PAD_LEFT):
                self._state_manager.send_cuia("ARROW_LEFT")
            elif note in (BTN_RIGHT, BTN_PAD_RIGHT):
                self._state_manager.send_cuia("ARROW_RIGHT")
            elif note == BTN_SEL_YES:
                self._state_manager.send_cuia("V5_ZYNPOT_SWITCH", [3, 'S'])
            elif note == BTN_BACK_NO:
                self._state_manager.send_cuia("BACK")
            elif note == BTN_ALT:
                self._is_alt_active = not self._is_alt_active
                self._state_manager.send_cuia("TOGGLE_ALT_MODE")
                self.refresh()
            else:
                # Function buttons (F1-F4)
                fn_btns = {BTN_F1: 1, BTN_F2: 2, BTN_F3: 3, BTN_F4: 4}
                pgm = fn_btns.get(note)
                if pgm is not None:
                    pgm += 4 if self._is_alt_active else 0
                    self._state_manager.send_cuia("PROGRAM_CHANGE", [pgm])
                    return True

                # Buttons that may have bold/long press
                self._btn_timer.is_pressed(note, time.time())
            return True

    def note_off(self, note, shifted_override=None):
        self._on_shifted_override(shifted_override)
        self._btn_timer.is_released(note)

    def cc_change(self, ccnum, ccval):
        delta = self._knobs_ease.feed(ccnum, ccval, self._is_shifted)
        if delta is None:
            return

        zynpot = {
            KNOB_LAYER: 0,
            KNOB_BACK: 1,
            KNOB_SNAPSHOT: 2,
            KNOB_SELECT: 3
        }.get(ccnum, None)
        if zynpot is None:
            return

        self._state_manager.send_cuia("ZYNPOT", [zynpot, delta])

    def on_screen_change(self, screen):
        screen_map = {
            "option":         (BTN_OPT_ADMIN, 0),
            "main_menu":      (BTN_OPT_ADMIN, 0),
            "admin":          (BTN_OPT_ADMIN, 1),
            "audio_mixer":    (BTN_MIX_LEVEL, 0),
            "alsa_mixer":     (BTN_MIX_LEVEL, 1),
            "control":        (BTN_CTRL_PRESET, 0),
            "engine":         (BTN_CTRL_PRESET, 0),
            "preset":         (BTN_CTRL_PRESET, 1),
            "bank":           (BTN_CTRL_PRESET, 1),
            "zs3":            (BTN_ZS3_SHOT, 0),
            "snapshot":       (BTN_ZS3_SHOT, 1),
            "zynpad":         (BTN_PAD_STEP, 0),
            "pattern_editor": (BTN_PAD_STEP, 1),
            "arranger":       (BTN_PAD_STEP, 1),
            "tempo":          (BTN_METRONOME, 0),
        }

        self._btn_states = {k:-1 for k in self._btn_states}
        try:
            btn, idx = screen_map[screen]
            self._btn_states[btn] = idx
        except KeyError:
            pass

    def on_media_change(self, media, kind, state):
        flags = self._is_playing if kind == "player" else self._is_recording
        flags.add(media) if state else flags.discard(media)

    def _handle_timed_button(self, btn, press_type):
        if press_type == CONST.PT_LONG:
            cuia = {
                BTN_OPT_ADMIN:   "POWER_OFF",
                BTN_CTRL_PRESET: "PRESET_FAV",
                BTN_PAD_STEP:    "SCREEN_ARRANGER",
            }.get(btn)
            if cuia:
                self._state_manager.send_cuia(cuia)
            return True

        actions = self._btn_actions.get(btn)
        if actions is None:
            return
        if callable(actions):
            actions = actions(press_type == CONST.PT_BOLD)

        idx = -1
        if press_type == CONST.PT_SHORT:
            idx = self._btn_states[btn]
            idx = (idx + 1) % len(actions)
            cuia = actions[idx]
        elif press_type == CONST.PT_BOLD:
            # In buttons with 2 functions, the default on bold press is the second
            idx = 1 if len(actions) > 1 else 0
            cuia = actions[idx]

        # Split params, if given
        params = []
        if ":" in cuia:
            cuia, params = cuia.split(":")
            params = params.split(",")
            params[0] = int(params[0])

        self._state_manager.send_cuia(cuia, params)
        return True


# --------------------------------------------------------------------------
# Handle Mixer (Mixpad mode)
# --------------------------------------------------------------------------
class MixerHandler(ModeHandlerBase):

    # To control main level, use SHIFT + K1
    main_chain_knob = KNOB_1

    def __init__(self, state_manager, leds: FeedbackLEDs):
        super().__init__(state_manager)
        self._leds = leds
        self._is_shifted = False
        self._knobs_function = FN_VOLUME
        self._track_buttons_function = FN_SELECT
        self._chains_bank = 0

        active_chain = self._chain_manager.get_active_chain()
        self._active_chain = active_chain.chain_id if active_chain else 0

    def refresh(self):
        self._leds.control_leds_off()

        # If SHIFT is pressed, show active knob's function
        if self._is_shifted:
            # Knob Ctrl buttons
            btn = {
                FN_VOLUME: BTN_KNOB_CTRL_VOLUME,
                FN_PAN: BTN_KNOB_CTRL_PAN,
            }[self._knobs_function]
            self._leds.led_on(btn)

            # Soft Keys buttons
            btn = {
                FN_SEQUENCE_MANAGER: BTN_SOFT_KEY_CLIP_STOP,
                FN_MUTE: BTN_SOFT_KEY_MUTE,
                FN_SOLO: BTN_SOFT_KEY_SOLO,
                FN_SELECT: BTN_SOFT_KEY_SELECT,
                FN_SCENE: BTN_SOFT_KEY_REC_ARM,
            }[self._track_buttons_function]
            self._leds.led_on(btn)

            # Clips bank selection
            btn = BTN_LEFT if self._chains_bank == 0 else BTN_RIGHT
            self._leds.led_on(btn)

        # Otherwise, show current function status
        else:
            if self._track_buttons_function == FN_SCENE:
                for i in range(8):
                    scene = i + (8 if self._chains_bank == 1 else 0)
                    state = scene == (self._zynseq.bank - 1)
                    self._leds.led_state(BTN_TRACK_1 + i, state)
                return

            if self._track_buttons_function == FN_SEQUENCE_MANAGER:
                self._leds.led_blink(BTN_SOFT_KEY_CLIP_STOP)
                return

            query = {
                FN_MUTE: self._zynmixer.get_mute,
                FN_SOLO: self._zynmixer.get_solo,
                FN_SELECT: self._is_active_chain,
            }[self._track_buttons_function]
            for i in range(8):
                index = i + (8 if self._chains_bank == 1 else 0)
                chain = self._chain_manager.get_chain_by_index(index)
                if not chain:
                    break
                # Main channel ignored
                if chain.chain_id == 0:
                    continue
                self._leds.led_state(BTN_TRACK_1 + i, query(index))

    def on_shift_changed(self, state):
        retval = super().on_shift_changed(state)
        self.refresh()
        return retval

    def note_on(self, note, velocity, shifted_override=None):
        self._on_shifted_override(shifted_override)

        # If SHIFT is pressed, handle alternative functions
        if self._is_shifted:
            if note == BTN_KNOB_CTRL_VOLUME:
                self._knobs_function = FN_VOLUME
            elif note == BTN_KNOB_CTRL_PAN:
                self._knobs_function = FN_PAN
            elif note == BTN_SOFT_KEY_MUTE:
                self._track_buttons_function = FN_MUTE
            elif note == BTN_SOFT_KEY_SOLO:
                self._track_buttons_function = FN_SOLO
            elif note == BTN_SOFT_KEY_REC_ARM:
                self._track_buttons_function = FN_SCENE
            elif note == BTN_SOFT_KEY_CLIP_STOP:
                self._track_buttons_function = FN_SEQUENCE_MANAGER
            elif note == BTN_LEFT:
                self._chains_bank = 0
            elif note == BTN_RIGHT:
                self._chains_bank = 1
            elif note == BTN_STOP_ALL_CLIPS:
                self._stop_all_sounds()
            elif note == BTN_PLAY:
                self._run_track_button_function_on_channel(255, FN_MUTE)
            elif note == BTN_SOFT_KEY_SELECT:
                self._track_buttons_function = FN_SELECT
            elif note == BTN_RECORD:
                self._state_manager.send_cuia("TOGGLE_RECORD")
                return True  # skip refresh
            elif note == BTN_UP:
                self._state_manager.send_cuia("BACK")
                return True  # skip refresh
            elif note == BTN_DOWN:
                self._state_manager.send_cuia("SCREEN_ZYNPAD")
                return True  # skip refresh
            else:
                return False
            self.refresh()
            return True

        # Otherwise, handle primary functions
        else:
            if BTN_TRACK_1 <= note <= BTN_TRACK_8:
                return self._run_track_button_function(note)

    def cc_change(self, ccnum, ccval):
        if self._knobs_function == FN_VOLUME:
            return self._update_volume(ccnum, ccval)
        if self._knobs_function == FN_PAN:
            return self._update_pan(ccnum, ccval)

    def update_strip(self, chan, symbol, value):
        if {"mute": FN_MUTE, "solo": FN_SOLO}.get(symbol) != self._track_buttons_function:
            return
        chan -= self._chains_bank * 8
        if 0 > chan > 8:
            return
        self._leds.led_state(BTN_TRACK_1 + chan, value)
        return True

    def set_active_chain(self, chain, refresh):
        # Do not change chain if 'main' is selected
        if chain == 0:
            return
        self._chains_bank = 0 if chain <= 8 else 1
        self._active_chain = chain
        if refresh:
            self.refresh()

    def _is_active_chain(self, position):
        chain = self._chain_manager.get_chain_by_position(position)
        if chain is None:
            return False
        return chain.chain_id == self._active_chain

    def _update_volume(self, ccnum, ccval):
        return self._update_control("level", ccnum, ccval, 0, 100)

    def _update_pan(self, ccnum, ccval):
        return self._update_control("balance", ccnum, ccval, -100, 100)

    def _update_control(self, type, ccnum, ccval, minv, maxv):
        if self._is_shifted:
            # Only main chain is handled with SHIFT, ignore the rest
            if ccnum != self.main_chain_knob:
                return False
            mixer_chan = 255
        else:
            index = (ccnum - KNOB_1) + self._chains_bank * 8
            chain = self._chain_manager.get_chain_by_index(index)
            if chain is None or chain.chain_id == 0:
                return False
            mixer_chan = chain.mixer_chan

        if type == "level":
            value = self._zynmixer.get_level(mixer_chan)
            set_value = self._zynmixer.set_level
        elif type == "balance":
            value = self._zynmixer.get_balance(mixer_chan)
            set_value = self._zynmixer.set_balance
        else:
            return False

        # NOTE: knobs are encoders, not pots (so ccval is relative)
        value *= 100
        value += ccval if ccval < 64 else ccval - 128
        value = max(minv, min(value, maxv))
        set_value(mixer_chan, value / 100)
        return True

    def _run_track_button_function(self, note):
        index = (note - BTN_TRACK_1) + self._chains_bank * 8

        # FIXME: move this to padmatrix handler!
        if self._track_buttons_function == FN_SCENE:
            self._zynseq.select_bank(index + 1)
            self._state_manager.send_cuia("SCREEN_ZYNPAD")
            return True

        chain = self._chain_manager.get_chain_by_index(index)
        if chain is None or chain.chain_id == 0:
            return False

        return self._run_track_button_function_on_channel(chain)

    def _run_track_button_function_on_channel(self, chain, function=None):
        if isinstance(chain, int):
            channel = chain
            chain = None
        else:
            channel = chain.mixer_chan

        if function is None:
            function = self._track_buttons_function

        if function == FN_MUTE:
            val = self._zynmixer.get_mute(channel) ^ 1
            self._zynmixer.set_mute(channel, val, True)
            return True

        if function == FN_SOLO:
            val = self._zynmixer.get_solo(channel) ^ 1
            self._zynmixer.set_solo(channel, val, True)
            return True

        if function == FN_SELECT and chain is not None:
            self._chain_manager.set_active_chain_by_id(chain.chain_id)
            return True


# --------------------------------------------------------------------------
#  Handle pad matrix for Zynseq (in Mixpad mode)
# --------------------------------------------------------------------------
class PadMatrixHandler(ModeHandlerBase):

    # NOTE: use this tool to help you getting the right colors:
    # https://github.com/oscaracena/mdevtk/blob/main/examples/apc_key25_mk2/09-pad-tool.py
    GROUP_COLORS = [
        0x05,   # #FF0000, Red Granate
        0x66,   # #0D5038, Blue Aguamarine
        0x12,   # #1D5900, Green Pistacho
        0x31,   # #5400FF, Lila
        0x25,   # #00A9FF, Mid Blue
        0x03,   # #FFFFFF, Sky Blue
        0x57,   # #00FF00, Dark Green
        0x0D,   # #FFFF00, Ocre
        0x0A,   # #591D00, Maroon
        0x69,   # #693C1C, Dark Grey
        0x04,   # #FF4C4C, Pink
        0x43,   # #0000FF, Blue sat.
        0x4D,   # #00FF87, Turquesa
        0x3C,   # #FF1500, Orange
        0x6C,   # #D86A1C, Light Maroon
        0x56,   # #72FF15, Light Green
    ]

    def __init__(self, state_manager, leds: FeedbackLEDs):
        super().__init__(state_manager)
        self._leds = leds
        self._libseq = self._zynseq.libseq
        self._cols = 8
        self._rows = 5
        self._is_record_pressed = False
        self._track_btn_pressed = None
        self._playing_seqs = set()
        self._btn_timer = ButtonTimer(self._handle_timed_button)

        # Seqman sub-mode
        self._seqman_func = None
        self._seqman_src_seq = None

        # FIXME: this value should be updated by a signal, to be in sync with UI state
        self._recording_seq = None

        # Sort pads in the same order that libseq uses
        self._pads = []
        for c in reversed(range(self._cols)):
            for r in range(self._rows):
                self._pads.append(BTN_PAD_END - (r * self._cols + c))

    def on_record_changed(self, state):
        self._is_record_pressed = state
        if state and self._recording_seq:
            self._stop_pattern_record()

    def on_toggle_play(self):
        self._state_manager.send_cuia("TOGGLE_PLAY")

    def on_toggle_play_row(self, row):
        # If seqman is enabled, ignore row functions
        if self._seqman_func is not None:
            return False
        if row >= self._zynseq.col_in_bank:
            return True

        # Get overall status: playing if at least one sequence is playing
        is_playing = False
        for col in range(self._zynseq.col_in_bank):
            seq = col * self._zynseq.col_in_bank + row
            if seq in self._playing_seqs:
                is_playing = True
                break

        stop_states = (zynseq.SEQ_STOPPED, zynseq.SEQ_STOPPING, zynseq.SEQ_STOPPINGSYNC)
        play_states = (zynseq.SEQ_RESTARTING, zynseq.SEQ_STARTING, zynseq.SEQ_PLAYING)
        for col in range(self._zynseq.col_in_bank):
            seq = col * self._zynseq.col_in_bank + row
            # We only play sequences that are not empty
            if not is_playing and self._libseq.isEmpty(self._zynseq.bank, seq):
                continue
            state = self._libseq.getPlayState(self._zynseq.bank, seq)
            if is_playing and state in stop_states:
                continue
            if not is_playing and state in play_states:
                continue
            self._libseq.togglePlayState(self._zynseq.bank, seq)

    def on_track_changed(self, track, state):
        self._track_btn_pressed = track if state else None

        # Switch seqman function (if seqman enabled and SHIFT is not pressed)
        if state and self._seqman_func is not None and not self._is_shifted:
            btn = BTN_TRACK_1 + track

            if btn == BTN_LEFT:
                return self._change_scene(-1)
            if btn == BTN_RIGHT:
                return self._change_scene(1)

            func = {
                BTN_KNOB_CTRL_VOLUME: FN_COPY_SEQUENCE,
                BTN_KNOB_CTRL_PAN: FN_MOVE_SEQUENCE,
                BTN_KNOB_CTRL_SEND: FN_CLEAR_SEQUENCE,
            }.get(btn)
            if func is not None:
                self._seqman_func = func
                self._refresh_tool_buttons()

                # Function CLEAR does not have source sequence, remove it
                if func == FN_CLEAR_SEQUENCE and self._seqman_src_seq is not None:
                    scene, seq = self._seqman_src_seq
                    self._seqman_src_seq = None
                    if scene == self._zynseq.bank:
                        self._update_pad(seq)

    def on_shift_changed(self, state):
        retval = super().on_shift_changed(state)
        # Update tool buttons only when SHIFT is not pressed
        if not state:
            self._refresh_tool_buttons()
        return retval

    def enable_seqman(self, state):
        if state:
            if self._seqman_func is None:
                self._seqman_func = FN_COPY_SEQUENCE
        else:
            self._seqman_func = None
            self._seqman_src_seq = None
        self.refresh()

    def refresh(self):
        if not self._libseq.isMidiRecord():
            self._recording_seq = None

        for c in range(self._cols):
            for r in range(self._rows):
                # Pad outside grid, switch off
                if c >= self._zynseq.col_in_bank or r >= self._zynseq.col_in_bank:
                    self.pad_off(c, r)
                    continue

                seq = c * self._zynseq.col_in_bank + r
                self._update_pad(seq, False)

        self._refresh_tool_buttons()

    def note_on(self, note, velocity, shifted_override=None):
        self._on_shifted_override(shifted_override)
        if not self._is_shifted:
            if note == BTN_STOP_ALL_CLIPS:
                self._btn_timer.is_pressed(note, time.time())

    def note_off(self, note, shifted_override=None):
        if note == BTN_STOP_ALL_CLIPS:
            self._btn_timer.is_released(note)

    def pad_press(self, pad):
        # Pad outside grid, discarded
        seq = self.get_sequence_from_pad(pad)
        if seq is None:
            return True

        if self._seqman_func is not None:
            self._seqman_handle_pad_press(seq)
        elif self._track_btn_pressed is not None:
            self._clear_sequence(self._zynseq.bank, seq)
        elif self._is_record_pressed:
            self._start_pattern_record(seq)
        elif self._recording_seq == seq:
            self._stop_pattern_record()
        else:
            self._libseq.togglePlayState(self._zynseq.bank, seq)

        return True

    def pad_off(self, col, row):
        index = col * self._rows + row
        self._leds.led_off(self._pads[index])

    def update_seq_state(self, bank, seq, state=None, mode=None, group=None, refresh=True):
        col, row = self._zynseq.get_xy_from_pad(seq)
        idx = col * self._rows + row
        if idx >= len(self._pads):
            return
        btn = self._pads[idx]

        is_empty = all(
            self._zynseq.is_pattern_empty(pattern)
            for pattern in self._get_sequence_patterns(bank, seq))
        color = self.GROUP_COLORS[group]

        # If seqman is enabled, update according to it's function
        if self._seqman_func is not None:
            led_mode = LED_BRIGHT_25 if is_empty else LED_BRIGHT_100
            if (self._seqman_func in (FN_COPY_SEQUENCE, FN_MOVE_SEQUENCE)
                    and self._seqman_src_seq is not None):
                src_scene, src_seq = self._seqman_src_seq
                if src_scene == self._zynseq.bank and src_seq == seq:
                    led_mode = LED_BLINKING_24

        # Otherwise, update according to sequence state
        else:
            if self._recording_seq == seq:
                led_mode = LED_BLINKING_16
            elif state == zynseq.SEQ_PLAYING:
                led_mode = LED_BLINKING_8
                self._playing_seqs.add(seq)
            elif state in (zynseq.SEQ_STOPPING, zynseq.SEQ_STARTING):
                led_mode = LED_PULSING_2
            else:
                led_mode = LED_BRIGHT_25 if is_empty else LED_BRIGHT_100
                self._playing_seqs.discard(seq)

        self._leds.led_on(btn, color, led_mode)

        if refresh:
            self._refresh_tool_buttons()

    def get_sequence_from_pad(self, pad):
        index = self._pads.index(pad)
        col = index // self._rows
        row = index % self._rows

        # Pad outside grid, discarded
        if col >= self._zynseq.col_in_bank or row >= self._zynseq.col_in_bank:
            return None
        return col * self._zynseq.col_in_bank + row

    def _handle_timed_button(self, btn, ptype):
        if btn == BTN_STOP_ALL_CLIPS:
            if ptype == CONST.PT_LONG:
                self._stop_all_sounds()
            else:
                in_all_banks = ptype == CONST.PT_BOLD
                self._stop_all_seqs(in_all_banks)

    def _seqman_handle_pad_press(self, seq):
        if self._seqman_func is None:
            return

        # FIXME: if pattern editor is open, and showing affected seq, update it!
        # FIXME: if Zynpad is open, also update it!
        # You can use self._current_screen...
        self._libseq.updateSequenceInfo()
        seq_is_empty = self._libseq.isEmpty(self._zynseq.bank, seq)
        if self._seqman_func == FN_CLEAR_SEQUENCE:
            if not seq_is_empty:
                self._clear_sequence(self._zynseq.bank, seq)
            return

        # Set selected sequence as source
        if self._seqman_src_seq is None:
            if not seq_is_empty:
                self._seqman_src_seq = (self._zynseq.bank, seq)
        else:
            # Clear source sequence
            if self._seqman_src_seq == (self._zynseq.bank, seq):
                self._seqman_src_seq = None
            # Copy/Move source to selected sequence (will be overwritten)
            else:
                if self._seqman_func == FN_COPY_SEQUENCE:
                    self._copy_sequence(*self._seqman_src_seq, self._zynseq.bank, seq)
                elif self._seqman_func == FN_MOVE_SEQUENCE:
                    self._copy_sequence(*self._seqman_src_seq, self._zynseq.bank, seq)
                    self._clear_sequence(*self._seqman_src_seq)
                    self._seqman_src_seq = None

        self._update_pad(seq)

    def _change_scene(self, offset):
        scene = min(64, max(1, self._zynseq.bank + offset))
        if scene != self._zynseq.bank:
            self._zynseq.select_bank(scene)
            self._state_manager.send_cuia("SCREEN_ZYNPAD")

    def _update_pad(self, seq, refresh=True):
        state = self._libseq.getSequenceState(self._zynseq.bank, seq)
        mode = (state >> 8) & 0xFF
        group = (state >> 16) & 0xFF
        state &= 0xFF
        self.update_seq_state(
            bank=self._zynseq.bank, seq=seq, state=state, mode=mode, group=group,
            refresh=refresh)

    def _refresh_tool_buttons(self):
        # Switch on seqman active function
        if self._seqman_func is not None:
            active = {
                FN_COPY_SEQUENCE: BTN_KNOB_CTRL_VOLUME,
                FN_MOVE_SEQUENCE: BTN_KNOB_CTRL_PAN,
                FN_CLEAR_SEQUENCE: BTN_KNOB_CTRL_SEND,
            }[self._seqman_func]
            for idx in range(8):
                btn = BTN_TRACK_1 + idx
                self._leds.led_state(btn, btn == active)
            return

        # If seqman is disabled, show playing status in row launchers
        playing_rows = {seq % self._zynseq.col_in_bank for seq in self._playing_seqs}
        for row in range(5):
            state = row in playing_rows
            self._leds.led_state(BTN_SOFT_KEY_START + row, state)

    def _start_pattern_record(self, seq):
        channel = self._libseq.getChannel(self._zynseq.bank, seq, 0)
        chain_id = self._chain_manager.get_chain_id_by_mixer_chan(channel)
        if chain_id is None:
            return

        if self._libseq.isMidiRecord():
            self._state_manager.send_cuia("TOGGLE_RECORD")
        self._chain_manager.set_active_chain_by_id(chain_id)

        self._show_pattern_editor(seq)
        if self._libseq.getPlayState(self._zynseq.bank, seq) == zynseq.SEQ_STOPPED:
            self._libseq.togglePlayState(self._zynseq.bank, seq)
        if not self._libseq.isMidiRecord():
            self._state_manager.send_cuia("TOGGLE_RECORD")

        self._recording_seq = seq
        self._update_pad(seq)

    def _stop_all_seqs(self, in_all_banks=False):
        bank = 0 if in_all_banks else self._zynseq.bank
        while True:
            seq_num = self._libseq.getSequencesInBank(bank)
            for seq in range(seq_num):
                state = self._libseq.getPlayState(bank, seq)
                if state not in [zynseq.SEQ_STOPPED, zynseq.SEQ_STOPPING, zynseq.SEQ_STOPPINGSYNC]:
                    self._libseq.togglePlayState(bank, seq)
            if not in_all_banks:
                break
            bank += 1
            if bank >= 64 or self._libseq.getPlayingSequences() == 0:
                break

    def _stop_pattern_record(self):
        if self._libseq.isMidiRecord():
            self._state_manager.send_cuia("TOGGLE_RECORD")
        self._recording_seq = None
        self.refresh()

    def _clear_sequence(self, scene, seq, create_empty=True):
        # Remove all patterns in all tracks
        seq_len = self._libseq.getSequenceLength(scene, seq)
        if seq_len != 0:
            n_tracks = self._libseq.getTracksInSequence(scene, seq)
            for track in range(n_tracks):
                n_patts = self._libseq.getPatternsInTrack(scene, seq, track)
                if n_patts == 0:
                    continue
                pos = 0
                while pos < seq_len:
                    pattern = self._libseq.getPatternAt(scene, seq, track, pos)
                    if pattern != -1:
                        self._libseq.removePattern(scene, seq, track, pos)
                        pos += self._libseq.getPatternLength(pattern)
                    else:
                        # Arranger's offset step is a quarter note (24 clocks)
                        pos += 24

            if n_tracks > 0:
                for track in range(n_tracks-1):
                    self._libseq.removeTrackFromSequence(scene, seq, track)

        # Add a new empty pattern at the beginning of first track
        if create_empty:
            pattern = self._libseq.createPattern()
            self._libseq.addPattern(scene, seq, 0, 0, pattern)

    def _copy_sequence(self, src_scene, src_seq, dst_scene, dst_seq):
        self._clear_sequence(dst_scene, dst_seq, create_empty=False)

        # Copy all patterns in all tracks
        seq_len = self._libseq.getSequenceLength(src_scene, src_seq)
        if seq_len != 0:
            n_tracks = self._libseq.getTracksInSequence(src_scene, src_seq)
            for track in range(n_tracks):
                if track >= self._libseq.getTracksInSequence(dst_scene, dst_seq):
                    self._libseq.addTrackToSequence(dst_scene, dst_seq)
                n_patts = self._libseq.getPatternsInTrack(src_scene, src_seq, track)
                if n_patts == 0:
                    continue
                pos = 0
                while pos < seq_len:
                    pattern = self._libseq.getPatternAt(src_scene, src_seq, track, pos)
                    if pattern != -1:
                        new_pattern = self._libseq.createPattern()
                        self._libseq.copyPattern(pattern, new_pattern)
                        self._libseq.addPattern(dst_scene, dst_seq, track, pos, new_pattern)
                        pos += self._libseq.getPatternLength(pattern)
                    else:
                        # Arranger's offset step is a quarter note (24 clocks)
                        pos += 24

        # Also copy StepSeq instrument pages
        self._request_action("stepseq", "sync-sequences",
            src_scene, src_seq, dst_scene, dst_seq)


# --------------------------------------------------------------------------
#  Jack client for playback sync
# --------------------------------------------------------------------------
#
# NOTE: This is not a thread to avoid overloading the whole system
# FIXME: make this a C service and use a FIFO for IPC
#        or a library with a thread accessed using ctypes
#        https://docs.python.org/3.7/library/ctypes.html
class StepSyncProvider(mp.Process):
    def __init__(self, steps_per_beat, step_callback):
        """NOTE: This constructor will be called in the old process."""
        super().__init__()
        self._commands = mp.Queue()
        self._steps = mp.Queue()
        self._spb = steps_per_beat
        self._tick_counter = 0

        # Create a new thread to read steps and call sync callback
        StepSyncConsumer(self._steps, step_callback)

        # IPC methods
        self.enable = partial(self._enqueue_cmd, "enable", True)
        self.disable = partial(self._enqueue_cmd, "enable", False)
        self.stop = partial(self._enqueue_cmd, "stop")
        self.set_steps_per_beat = partial(self._enqueue_cmd, "spb")

        self.daemon = True
        self.start()

    def _init(self):
        """NOTE: This _init() is called inside the new process."""
        signal.signal(signal.SIGINT, self._on_interrupt)
        signal.signal(signal.SIGTERM, self._on_interrupt)
        signal.signal(signal.SIGHUP, self._on_interrupt)

    # Process worker
    def run(self):
        self._init()

        self._jack_client = jack.Client("StepSeq-Monitor")
        self._inport = self._jack_client.midi_inports.register("input")
        self._jack_client.set_process_callback(self._process)

        # Process incoming messages
        while True:
            cmd = self._commands.get()
            if cmd[0] == "stop":
                break
            if cmd[0] == "spb":
                self._spb = cmd[1]
            elif cmd[0] == "enable":
                self._cmd_enable(cmd[1])

    # Internal commands
    def _cmd_enable(self, enable):
        if self._jack_client is None:
            return

        if enable:
            self._tick_counter = 0
            self._jack_client.activate()
            self._jack_client.connect("zynseq:output", self._inport)
        else:
            self._jack_client.deactivate()

    # For simple IPC methods
    def _enqueue_cmd(self, cmd, *args):
        self._commands.put([cmd] + list(args))

    def _on_interrupt(self, signum, frame):
        if self._jack_client:
            self._jack_client.deactivate()
            self._jack_client.close()
            self._jack_client = None
        self.stop()

    # Jack events processor
    def _process(self, nframes):
        for offset, data in self._inport.incoming_midi_events():
            data = bytes(data)
            ev = data[0]

            # 'Continue' is sent on every bar end
            if ev == EV_CONTINUE:
                self._steps.put("B")

            # 24 'Clock' events for each beat (quarter note)
            elif ev == EV_CLOCK:
                self._tick_counter += 1
                if self._tick_counter >= 24 / self._spb:
                    self._steps.put("S")
                    self._tick_counter = 0


# --------------------------------------------------------------------------
#  Step Sequencer clock sync
# --------------------------------------------------------------------------
class StepSyncConsumer(Thread):
    def __init__(self, event_queue, callback):
        super().__init__()
        self._events = event_queue
        self._callback = callback

        self.daemon = True
        self.start()

    def run(self):
        while True:
            ev = self._events.get()
            self._callback(ev)


# --------------------------------------------------------------------------
#  Class to hold instrument pads for StepSeq (a.k.a. note-pads)
#  Note: it inherits from dict to be json-serializable and easily comparable
# --------------------------------------------------------------------------
class NotePad(dict):
    def __init__(self, note, velocity, duration=1, stutter_count=0, stutter_duration=1):
        super().__init__(
            note = note,
            velocity = velocity,
            duration = duration,
            stutter_count = stutter_count,
            stutter_duration = stutter_duration,
        )

    # To support dot-access
    def __getattr__(self, name):
        try:
            return self[name]
        except (IndexError, KeyError):
            return super().__getattr__(name)

    def __setattr__(self, name, value):
        self[name] = value


# --------------------------------------------------------------------------
#  Class to marshall/un-marshall saved state of StepSeq
#  FIXME: add support for scenes too!
# --------------------------------------------------------------------------
class StepSeqState:
    def __init__(self):
        self._seqs = {}
        self._chains = {}

    def load(self, state):
        state = deepcopy(state)

        # Convert JSON stringfied key ints as real ints, and note-pad's dicts to NotePad
        self._chains = state.get("chains", {})
        for c in self._chains.values():
            src_pages = c.get("pages", [])
            dst_pages = []
            for p in src_pages:
                dst_pages.append({int(k):NotePad(**v) for k,v in p.items()})
            c["pages"] = dst_pages

        for seq, value in state.get("seqs", {}).items():
            self._seqs[int(seq)] = value

    def save(self):
        return {"seqs": self._seqs, "chains": self._chains}

    def get_chain_by_id(self, chain_id):
        chain_id = str(chain_id) if chain_id is not None else "default"
        chain = self._chains.get(chain_id)
        if chain is None:
            chain = {"pages": [{}, {}, {}, {}]}
            self._chains[chain_id] = chain
        return chain

    def get_page_by_sequence(self, seq):
        return self._seqs.get(seq, [0, 0])

    def set_sequence_selection(self, seq, page, pad):
        self._seqs[seq] = [page, pad]


# --------------------------------------------------------------------------
#  Note objects used in NotePlayer's event queue
# --------------------------------------------------------------------------
class Note:
    def __init__(self, note, velocity, duration_cycles, channel, stutt_count, stutt_duration):
        self._duration = duration_cycles
        self._stutter_count = stutt_count
        self._stutter_duration = stutt_duration
        self._velocity = velocity
        self._elapsed = 0
        self._is_stopped = False
        self._is_finished = False
        self._iter = iter(self)

        # Public attributes
        self.note = note
        self.channel = channel

    def stop(self):
        self._is_stopped = True

    def __next__(self):
        if self._is_stopped:
            if not self._is_finished:
                self._is_finished = True
                return ("off", self.note, self.channel, 0)
            raise StopIteration()
        return next(self._iter)

    def __iter__(self):
        if self._stutter_count > 0 and self._duration > 0:
            while self._stutter_count:
                total_stutt_duration = self._stutter_count * self._stutter_duration * 2
                if total_stutt_duration < self._duration:
                    break
                self._stutter_count -= 1

        for _ in range(self._stutter_count):
            yield self._event("on", self.note, self.channel, self._velocity)
            duration = self._stutter_duration - 1
            while duration > 0:
                duration -= 1
                yield self._event()
            yield self._event("off", self.note, self.channel, 0)
            duration = self._stutter_duration - 1
            while duration > 0:
                duration -= 1
                yield self._event()

        if self._duration > 0 and self._elapsed > self._duration:
            return

        mode = "on" if self._velocity != 0 else "off"
        yield self._event(mode, self.note, self.channel, self._velocity)
        if mode == "on" and self._duration > 0:
            while self._elapsed < self._duration:
                yield self._event()
            yield self._event("off", self.note, self.channel, 0)

    def _event(self, *args):
        self._elapsed += 1
        return args


# --------------------------------------------------------------------------
#  Note player (adds support for stutter, is also quantized)
#  FIXME: if jack is playing, synchronize with it
# --------------------------------------------------------------------------
class NotePlayer(Thread):
    def __init__(self, libseq):
        super().__init__()
        self._libseq = libseq
        self._ready = Event()
        self._notes_pending = []
        self._pending_lock = RLock()

        self.daemon = True
        self.start()

    def run(self):
        while self._ready.wait():
            try:
                self._tick()
            except Exception as ex:
                logging.error(f" error on note player: {ex}")
            time.sleep(self._clock_cycles_to_ms(1) / 1000)

    def stop(self, note, channel):
        with self._pending_lock:
            for n in self._notes_pending:
                if n.note == note and n.channel == channel:
                    n.stop()
                    return
            n = Note(note, 0, 0, channel, 0, 1)
            self._notes_pending.append(n)
            self._ready.set()

    def play(self, note, velocity, duration, channel=0, stutt_count=0, stutt_duration=1):
        duration_ms = int(self._get_step_duration() * duration)
        duration_cycles = duration_ms / self._clock_cycles_to_ms(1)
        with self._pending_lock:
            for n in self._notes_pending:
                if n.note == note and n.channel == channel:
                    n.stop()
            n = Note(note, velocity, duration_cycles, channel, stutt_count, stutt_duration)
            self._notes_pending.append(n)
            self._ready.set()

    def _clock_cycles_to_ms(self, cycles):
        # 24 'Clock' events for each beat (quarter note)
        bpm = self._libseq.getTempo()
        return round(60 / bpm / 24 * 1000 * cycles)

    def _tick(self):
        with self._pending_lock:
            if not self._notes_pending:
                self._ready.clear()
                return
            for note in self._notes_pending[:]:
                try:
                    note_spec = next(note)
                    if note_spec:
                        self._send_note(*note_spec)
                except StopIteration:
                    self._notes_pending.remove(note)

    # FIXME: Could this be in zynseq?
    def _get_step_duration(self):
        spb = self._libseq.getStepsPerBeat()
        bpm = self._libseq.getTempo()
        return int(60 / (spb * bpm) * 1000)  # ms

    def _send_note(self, mode, note, channel, velocity=0):
        status = 0x90 if mode == "on" else 0x80
        status |= (channel & 0xF)
        b1 = note & 0x7F
        b2 = (velocity & 0x7F) if mode == "on" else 0
        self._libseq.sendMidiCommand(status, b1, b2)


# --------------------------------------------------------------------------
#  Step Sequencer mode (StepSeq)
# --------------------------------------------------------------------------
class StepSeqHandler(ModeHandlerBase):
    PAD_COLS = 8
    PAD_ROWS = 5

    NOTE_PAGE_COLORS = [
        COLOR_BLUE,
        COLOR_GREEN,
        COLOR_ORANGE,
        COLOR_PINK,
    ]

    def __init__(self, state_manager, leds: FeedbackLEDs, dev_idx):
        super().__init__(state_manager)
        self._leds = leds
        self._libseq = self._zynseq.libseq
        self._own_device_id = dev_idx
        self._cursor = 0
        self._knobs_ease = KnobSpeedControl(steps_normal=12, steps_shifted=20)
        self._saved_state = StepSeqState()
        self._note_player = NotePlayer(self._libseq)
        self._note_config = None

        spb = self._libseq.getStepsPerBeat()
        self._clock = StepSyncProvider(spb, self._on_next_step)
        self._sequence_patterns = []
        self._selected_seq = None
        self._selected_pattern = None
        self._selected_pattern_idx = 0
        self._selected_note = None
        self._pattern_clock_offset = 0
        self._used_pads = 32

        self._is_select_pressed = False
        self._is_volume_pressed = False
        self._is_send_pressed = False
        self._is_stage_play = False
        self._is_playing = False
        self._is_arranger_mode = False

        # We need to receive clock though MIDI
        self._libseq.enableMidiClockOutput(True)

        # Pads ordered for cursor sliding + note pads
        self._pads = []
        for r in range(self.PAD_ROWS):
            for c in reversed(range(self.PAD_COLS)):
                self._pads.append(BTN_PAD_END - (r * self.PAD_COLS + c))

        # 'Note-Pad' mapping (4 pages available)
        self._note_pads = None
        self._note_pads_function = FN_PLAY_NOTE
        self._note_pages = None
        self._note_page_number = 0
        self._notes_playing = {}
        self._pressed_pads = {}
        self._pressed_pads_action = None

    def set_state(self, state):
        state = state.get("stepseq")
        if state is None:
            return
        self._saved_state.load(state)

    def get_state(self):
        return {"stepseq": self._saved_state.save()}

    def set_active(self, active):
        super().set_active(active)
        if self._selected_seq is None:
            self.set_sequence(0)
        else:
            self._update_for_selected_pattern()
        if active:
            self._clock.enable()
        else:
            if self._is_arranger_mode:
                self._enable_arranger_mode(False)
            self._clock.disable()
            self._is_stage_play = False
        self._pressed_pads_action = "activation"

    def _refresh_status_leds(self):
        self._leds.control_leds_off()

        if self._is_shifted:
            # If SHIFT is pressed, show this mode as active
            self._leds.led_on(BTN_KNOB_CTRL_SEND)

            if self._note_config is None:
                self._leds.led_on(BTN_UP + self._note_page_number)

        if self._is_arranger_mode:
            self._leds.led_blink(BTN_SOFT_KEY_SELECT)

    def _refresh_note_pads(self):
        # If there is a note config controller, it will handle all pads, nothing to do here
        if self._note_config is not None:
            return

        # On 'stage' playing, show patterns bar instead of note-pads
        if self._is_stage_play or self._is_arranger_mode:
            self._show_patterns_bar(overlay=False)
            return

        # Otherwise, show note-pads that are not empty
        color = self.NOTE_PAGE_COLORS[self._note_page_number]
        pads = {self._pads[idx]:None for idx in range(32, 40)}
        for idx, note_spec in self._note_pads.items():
            pad = BTN_PAD_START + idx
            mode = int((note_spec.velocity * 6) / 127)
            if note_spec == self._selected_note:
                mode = LED_PULSING_8
            pads[pad] = (color, mode)

        for pad, args in pads.items():
            self._leds.led_off(pad) if args is None else self._leds.led_on(pad, *args)

    def refresh(self, shifted_override=None, only_steps=False):
        self._on_shifted_override(shifted_override)
        self._refresh_status_leds()

        if self._note_config is not None:
            self._note_config.refresh(is_shifted=self._is_shifted)
            return

        if not only_steps:
            self._refresh_note_pads()
        pads = {self._pads[idx]:None for idx in range(32)}

        # Dimm white for first step on each beat
        spb = self._libseq.getStepsPerBeat()
        for idx in range(0, self._used_pads, spb):
            pad = self._pads[idx]
            pads[pad] = (COLOR_WHITE, LED_BRIGHT_10)

        # Red + velocity for each non-empty step
        for pad, color, mode in self._get_step_colors():
            pads[pad] = (color, mode)

        for pad, args in pads.items():
            self._leds.led_off(pad) if args is None else self._leds.led_on(pad, *args)

    def set_sequence(self, seq):
        self._libseq.setSequence(seq)
        self._selected_seq = seq
        self._sequence_patterns = self._get_sequence_patterns(self._zynseq.bank, seq, create=True)
        self._selected_pattern_idx = 0
        self._pattern_clock_offset = 0
        self._set_pattern(self._sequence_patterns[0])

        # Update active chain and instruments page
        chain_id = self._get_chain_id_by_sequence(self._zynseq.bank, seq)
        self._chain_manager.set_active_chain_by_id(chain_id)
        self._update_instruments(seq, chain_id)

    def on_shift_changed(self, state):
        retval = super().on_shift_changed(state)
        self._refresh_status_leds()
        if self._note_config is not None:
            if not state:
                self._note_config.refresh(only_status=True)
        else:
            self._refresh_note_pads()
        return retval

    def note_on(self, note, velocity, shifted_override=None):
        self._on_shifted_override(shifted_override)
        if self._is_stage_play:
            self._is_stage_play = False
            self.refresh()

        if self._is_shifted:
            # Events that will run independently of note_config
            if note == BTN_KNOB_CTRL_SEND:
                self.refresh()
            elif note == BTN_STOP_ALL_CLIPS:
                self._stop_all_sounds()

            # Events that depends on note_config
            if self._note_config is not None:
                if BTN_PAD_START <= note <= BTN_PAD_END:
                    return self._note_config.note_on(note, velocity, self._is_shifted)
            elif BTN_PAD_START <= note <= BTN_PAD_START + 7:
                if not self._is_arranger_mode and self._note_config is None:
                    self._change_instrument(note)
            elif note == BTN_LEFT:
                self._change_to_previous_pattern()
            elif note == BTN_RIGHT:
                self._change_to_next_pattern()
            elif note == BTN_SOFT_KEY_SELECT:
                self._is_select_pressed = True
                self._enable_arranger_mode(True)
            elif note == BTN_PLAY:
                self._libseq.togglePlayState(self._zynseq.bank, self._selected_seq)
                state = self._libseq.getPlayState(self._zynseq.bank, self._selected_seq)
                if state in (zynseq.SEQ_STARTING, zynseq.SEQ_PLAYING, zynseq.SEQ_RESTARTING):
                    self._is_stage_play = True
                    self.refresh()
            elif note == BTN_UP:
                self._state_manager.send_cuia("BACK")
            elif note == BTN_DOWN:
                self._show_pattern_editor(self._selected_seq)
            else:
                return False
            return True

        else:
            if BTN_SOFT_KEY_START <= note <= BTN_SOFT_KEY_END:
                control = None
                if self._note_config is not None:
                    control = self._note_config.KIND
                elif self._is_volume_pressed:
                    control = VelocityControl.KIND
                elif self._is_send_pressed:
                    control = StutterCountControl.KIND
                if control is not None:
                    return self._create_note_control(control, note)

                if note == BTN_SOFT_KEY_MUTE:
                    if self._is_arranger_mode:
                        self._note_pads_function = FN_CLEAR_PATTERN
                elif note == BTN_SOFT_KEY_SELECT:
                    self._enable_arranger_mode(False)
                else:
                    return False
                return True

            if note == BTN_PLAY:
                self._libseq.togglePlayState(self._zynseq.bank, self._selected_seq)

            elif BTN_PAD_START <= note <= BTN_PAD_END:
                self._pressed_pads[note] = time.time()
                if BTN_PAD_START + 8 <= note <= BTN_PAD_END:
                    if len(self._pressed_pads) == 2:
                        return self._extend_step(note)
                if not self._is_arranger_mode:
                    control = None
                    if self._is_volume_pressed:
                        control = VelocityControl.KIND
                    elif self._is_send_pressed:
                        control = StutterCountControl.KIND
                    if control is not None:
                        return self._create_note_control(control, note)

                if self._note_config is not None:
                    return self._note_config.note_on(note, velocity, self._is_shifted)
                if BTN_PAD_START <= note <= BTN_PAD_START + 7:
                    self._run_note_pad_action(note, state=True)

            elif note == BTN_STOP_ALL_CLIPS:
                if self._is_arranger_mode:
                    self._note_pads_function = FN_REMOVE_PATTERN
                else:
                    self._note_pads_function = FN_REMOVE_NOTE

            elif note == BTN_KNOB_CTRL_VOLUME:
                self._is_volume_pressed = True
                if self._note_config is not None:
                    if self._note_config.KIND == VelocityControl.KIND:
                        self._note_config = None
                    else:
                        self._note_config = self._note_config.clone_to(
                            VelocityControl.KIND)
                    self.refresh()

            elif note == BTN_KNOB_CTRL_SEND:
                self._is_send_pressed = True
                if self._note_config is not None:
                    if self._note_config.KIND == StutterCountControl.KIND:
                        self._note_config = self._note_config.clone_to(
                            StutterDurationControl.KIND)
                    elif self._note_config.KIND == StutterDurationControl.KIND:
                        self._note_config = None
                    else:
                        self._note_config = self._note_config.clone_to(
                            StutterCountControl.KIND)
                    self.refresh()

            elif note == BTN_LEFT and self._note_config is None:
                if self._is_arranger_mode:
                    self._change_to_previous_pattern()
                else:
                    self._change_instruments_page(-1)
            elif note == BTN_RIGHT and self._note_config is None:
                if self._is_arranger_mode:
                    self._change_to_next_pattern()
                else:
                    self._change_instruments_page(1)
            else:
                return False
            return True

    def note_off(self, note, shifted_override=None):
        self._on_shifted_override(shifted_override)

        if BTN_PAD_START <= note <= BTN_PAD_END:
            self._pressed_pads.pop(note, None)

            if self._note_config is not None:
                self._pressed_pads_action = "note-config"

            if BTN_PAD_START <= note <= BTN_PAD_START + 7:
                if not self._is_shifted and self._note_config is None:
                    self._run_note_pad_action(note, state=False)
            elif note in self._pads[:self._used_pads]:
                if self._pressed_pads_action is None:
                    self._toggle_step(self._pads.index(note))

            if not self._pressed_pads:
                self._pressed_pads_action = None
        elif note in (BTN_STOP_ALL_CLIPS, BTN_SOFT_KEY_MUTE):
            if self._is_arranger_mode:
                self._note_pads_function = FN_SELECT_PATTERN
            else:
                self._note_pads_function = FN_PLAY_NOTE
        elif note == BTN_SOFT_KEY_SELECT:
            self._is_select_pressed = False
        elif note == BTN_KNOB_CTRL_VOLUME:
            self._is_volume_pressed = False
        elif note == BTN_KNOB_CTRL_SEND:
            self._is_send_pressed = False
        else:
            return False
        return True

    def cc_change(self, ccnum, ccval):
        delta = self._knobs_ease.feed(ccnum, ccval, self._is_shifted)
        if delta is None:
            return

        if self._pressed_pads:
            if self._note_config is not None:
                return False

            adjust_pad_func = {
                KNOB_1: self._update_note_pad_duration,
                KNOB_2: self._update_note_pad_velocity,
                KNOB_3: self._update_note_pad_stutter_count,
                KNOB_4: self._update_note_pad_stutter_duration,
            }.get(ccnum)
            adjust_step_func = {
                KNOB_1: self._update_step_duration,
                KNOB_2: self._update_step_velocity,
                KNOB_3: self._update_step_stutter_count,
                KNOB_4: self._update_step_stutter_duration,
            }.get(ccnum)

            step_pads = self._pads[:self._used_pads]
            self._pressed_pads_action = "knobs"
            for pad in self._pressed_pads:
                if adjust_pad_func:
                    note_spec = self._note_pads.get(pad)
                    if note_spec is not None:
                        adjust_pad_func(pad, note_spec, delta)
                        continue
                if adjust_step_func:
                    try:
                        step = step_pads.index(pad)
                        adjust_step_func(step, delta)
                        continue
                    except ValueError:
                        pass
            return True

        # Adjust tempo
        if ccnum == KNOB_1:
            self._show_screen_briefly(screen="tempo", cuia="TEMPO", timeout=1500)
            delta *= 0.1 if self._is_shifted else 1
            self._zynseq.set_tempo(self._zynseq.get_tempo() + delta)

        # Update sequence's chain volume
        elif ccnum == KNOB_2:
            self._show_screen_briefly(
                screen="audio_mixer", cuia="SCREEN_AUDIO_MIXER", timeout=1500)
            chain_id = self._get_chain_id_by_sequence(self._zynseq.bank, self._selected_seq)
            chain = self._chain_manager.chains.get(chain_id)
            if chain is not None:
                mixer_chan = chain.mixer_chan
                level = max(0, min(100, self._zynmixer.get_level(mixer_chan) * 100 + delta))
                self._zynmixer.set_level(mixer_chan, level / 100)

    def update_seq_state(self, bank, seq, state=None, mode=None, group=None):
        self._is_playing = state != zynseq.SEQ_STOPPED
        if state == zynseq.SEQ_STOPPED and self._cursor < self._used_pads:
            self._leds.remove_overlay(self._pads[self._cursor])
        if self._note_config is not None:
            is_playing = state != zynseq.SEQ_STOPPED
            self._note_config.update_status(playing=is_playing)

    def _extend_step(self, pad_end):
        pad_start = next(pad for pad in self._pressed_pads if pad != pad_end)
        ts = self._pressed_pads.get(pad_start, 0)
        if time.time() - ts < 0.5:
            return
        step_pads = self._pads[:self._used_pads]
        try:
            step_start = step_pads.index(pad_start)
            step_end = step_pads.index(pad_end)
        except ValueError:
            return
        if step_start >= step_end:
            return
        note = self._selected_note.note
        current_duration = self._libseq.getNoteDuration(step_start, note)
        if current_duration == 0:
            return

        self._pressed_pads_action = "extend-step"
        new_duration = step_end - step_start + 1
        if new_duration == current_duration:
            new_duration -= 0.5
        self._set_note_duration(step_start, note, new_duration)
        self.refresh(only_steps=True)

    def _update_step_duration(self, step, delta):
        if self._selected_note is None:
            return

        note = self._selected_note.note
        max_duration = self._libseq.getSteps()
        duration = self._libseq.getNoteDuration(step, note) + delta * 0.1
        duration = round(min(max_duration, max(0.1, duration)), 1)
        self._set_note_duration(step, note, duration)
        self._play_step(step)
        self.refresh(only_steps=True)

    def _update_step_velocity(self, step, delta):
        if self._selected_note is None:
            return

        note = self._selected_note.note
        velocity = self._libseq.getNoteVelocity(step, note) + delta
        velocity = min(127, max(10, velocity))
        self._libseq.setNoteVelocity(step, note, velocity)
        self._leds.led_on(self._pads[step], COLOR_RED, int((velocity * 6) / 127))
        self._play_step(step)

    def _update_step_stutter_count(self, step, delta):
        if self._selected_note is None:
            return

        note = self._selected_note.note
        count = self._libseq.getStutterCount(step, note) + delta
        count = min(MAX_STUTTER_COUNT, max(0, count))
        self._libseq.setStutterCount(step, note, count)
        self._play_step(step)

    def _update_step_stutter_duration(self, step, delta):
        if self._selected_note is None:
            return

        note = self._selected_note.note
        duration = self._libseq.getStutterDur(step, note) + delta
        duration = min(MAX_STUTTER_DURATION, max(1, duration))
        self._libseq.setStutterDur(step, note, duration)
        self._play_step(step)

    def _update_note_pad_duration(self, pad, note_spec, delta):
        max_duration = self._libseq.getSteps()
        note_spec.duration = \
            round(min(max_duration, max(0.1, note_spec.duration + delta * 0.1)), 1)
        self._play_note_pad(pad)

    def _update_note_pad_velocity(self, pad, note_spec, delta):
        is_selected = note_spec == self._selected_note
        note_spec.velocity = min(127, max(10, note_spec.velocity + delta))
        self._play_note_pad(pad)

        color = self.NOTE_PAGE_COLORS[self._note_page_number]
        self._leds.led_on(pad, color, int((note_spec.velocity * 6) / 127))

        if is_selected:
            self._leds.delayed("led_on", 1000, pad, color, LED_PULSING_8)

    def _update_note_pad_stutter_count(self, pad, note_spec, delta):
        note_spec.stutter_count = \
            min(MAX_STUTTER_COUNT, max(0, note_spec.stutter_count + delta))
        self._play_note_pad(pad)

    def _update_note_pad_stutter_duration(self, pad, note_spec, delta):
        note_spec.stutter_duration = \
            min(MAX_STUTTER_DURATION, max(0, note_spec.stutter_duration + delta))
        self._play_note_pad(pad)

    # NOTE: Do NOT change argument names here (is called using keyword args)
    def _on_midi_note_on(self, izmip, chan, note, vel):
        # Skip own device events / not assigning mode
        if izmip == self._own_device_id or len(self._pressed_pads) == 0:
            return

        # FIXME: if MIDI is playing, we need to ensure this note_on does come
        # from a device (i.e the user pressed it!). Current FIX allows using only
        # the APC itself
        if izmip > 2:
            return

        for pad in self._pressed_pads:
            self._note_pads[pad] = NotePad(note, vel, 1.0)
        self.refresh()

    def _remove_note_pad(self, pad):
        idx = pad - BTN_PAD_START
        note_spec = self._note_pads.pop(idx, None)
        if note_spec is not None:
            if note_spec == self._selected_note:
                self._selected_note = None
            self.refresh()

    def _run_note_pad_action(self, note, velocity=None, state=True):
        dst_idx = note - BTN_PAD_START

        # Only in note-on event
        if state:
            if self._is_arranger_mode and len(self._pressed_pads) == 2:
                src_idx = next(pad for pad in self._pressed_pads if pad != dst_idx)
                self._copy_pattern(src_idx, dst_idx)
                self._leds.led_on(note, COLOR_LIME, LED_BLINKING_16, overlay=True)
                self._leds.delayed("remove_overlay", 1000, note)
            elif self._note_pads_function == FN_SELECT_PATTERN:
                if dst_idx < len(self._sequence_patterns):
                    self._change_to_pattern_index(self._selected_pattern_idx, dst_idx)
                    self._refresh_note_pads()
            elif self._note_pads_function == FN_REMOVE_PATTERN:
                if dst_idx < len(self._sequence_patterns):
                    self._remove_pattern(dst_idx)
                    self._refresh_note_pads()
            elif self._note_pads_function == FN_CLEAR_PATTERN:
                self._clear_pattern(dst_idx)
                self._leds.led_on(note, COLOR_RED, LED_BLINKING_16, overlay=True)
                self._leds.delayed("remove_overlay", 1000, note)
            elif self._note_pads_function == FN_REMOVE_NOTE:
                self._remove_note_pad(note)

        if self._note_pads_function == FN_PLAY_NOTE:
            self._play_note_pad(note, velocity, on=state, force=True)
            self._enable_midi_listening(state)

    def _change_instruments_page(self, offset):
        new_page_number = max(0, min(3, self._note_page_number + offset))
        if new_page_number == self._note_page_number:
            return

        self._note_pads = self._note_pages[new_page_number]
        self._note_page_number = new_page_number
        self.refresh()

        # Briefly turn on a track led to indicate current page
        indicator = BTN_TRACK_1 + self._note_page_number
        self._leds.led_on(indicator)
        self._leds.delayed("led_off", 1000, indicator)

    def _update_instruments(self, seq, chain_id):
        saved_chain = self._saved_state.get_chain_by_id(chain_id)
        self._note_pages = saved_chain["pages"]

        page_num, index = self._saved_state.get_page_by_sequence(seq)
        self._note_pads = self._note_pages[page_num]
        self._note_page_number = page_num
        self._selected_note = self._note_pads.get(index)

    # This will be called as an action (look for 'sync-sequences' requests)
    def _action_sync_sequences(self, src_bank, src_seq, dst_bank, dst_seq):
        src_chain = self._get_chain_id_by_sequence(src_bank, src_seq)
        dst_chain = self._get_chain_id_by_sequence(dst_bank, dst_seq)
        src = self._saved_state.get_chain_by_id(src_chain)
        dst = self._saved_state.get_chain_by_id(dst_chain)
        dst["pages"] = deepcopy(src["pages"])

        # FIXME: add support for scenes
        src_page = self._saved_state.get_page_by_sequence(src_seq)
        self._saved_state.set_sequence_selection(dst_seq, *src_page)

    def _change_instrument(self, pad):
        index = pad - BTN_PAD_START
        note_spec = self._note_pads.get(index)
        if note_spec is None:
            return
        self._selected_note = note_spec
        self._saved_state.set_sequence_selection(
            self._selected_seq, page=self._note_page_number, pad=index)
        self.refresh()

    def _play_note_pad(self, pad, velocity=None, on=True, force=False):
        if not force:
            state = self._libseq.getPlayState(self._zynseq.bank, self._selected_seq)
            if state != zynseq.SEQ_STOPPED:
                return

        note_spec = self._note_pads.get(pad - BTN_PAD_START)
        if note_spec is None:
            return
        # Perform's velocity takes precedence over stored velocity
        if velocity is None:
            velocity = note_spec.velocity

        channel = self._libseq.getChannel(self._zynseq.bank, self._selected_seq, 0)
        if on:
            self._note_player.play(
                note_spec.note, velocity, 0, channel,
                note_spec.stutter_count, note_spec.stutter_duration)
        else:
            self._note_player.stop(note_spec.note, channel)

    def _play_step(self, step, only_when_stopped=True):
        if only_when_stopped:
            state = self._libseq.getPlayState(self._zynseq.bank, self._selected_seq)
            if state != zynseq.SEQ_STOPPED:
                return

        note = self._selected_note.note
        velocity = self._libseq.getNoteVelocity(step, note)
        duration = self._libseq.getNoteDuration(step, note)
        channel = self._libseq.getChannel(self._zynseq.bank, self._selected_seq, 0)
        stutt_count = self._libseq.getStutterCount(step, note)
        stutt_duration = self._libseq.getStutterDur(step, note)
        self._note_player.play(
            note, velocity, duration, channel, stutt_count, stutt_duration)

    def _toggle_step(self, step):
        if self._selected_note is None:
            return

        spec = self._selected_note
        if self._libseq.getNoteStart(step, spec.note) == -1:
            velocity = spec.velocity
            velocity = velocity if not self._is_shifted else velocity // 2
            self._libseq.addNote(
                step, spec.note, velocity, spec.duration, 0)
            self._libseq.setStutterCount(step, spec.note, spec.stutter_count)
            self._libseq.setStutterDur(step, spec.note, spec.stutter_duration)
        else:
            self._libseq.removeNote(step, spec.note)
            channel = self._libseq.getChannel(self._zynseq.bank, self._selected_seq, 0)
            self._libseq.playNote(spec.note, 0, channel, 0)
        self.refresh(only_steps=True)

    def _on_next_step(self, ev):
        if not self._is_active:
            return
        if self._cursor < self._used_pads:
            self._leds.remove_overlay(self._pads[self._cursor])

        self._cursor = self._get_pattern_playhead()
        if self._is_stage_play and self._cursor >= self._used_pads:
            from_idx = self._selected_pattern_idx
            to_idx = from_idx + 1
            if to_idx >= len(self._sequence_patterns):
                to_idx = 0
            self._change_to_pattern_index(from_idx, to_idx)
            self._show_patterns_bar()

        # Avoid turning on the first LED when is stopping
        state = self._libseq.getPlayState(self._zynseq.bank, self._selected_seq)
        if self._cursor == 0 and state != zynseq.SEQ_PLAYING:
            return
        if self._cursor < self._used_pads:
            pad = self._pads[self._cursor]
            self._leds.led_on(pad, COLOR_WHITE, LED_BRIGHT_50, overlay=True)

    def _enable_midi_listening(self, active=True):
        func = zynsigman.register if active else zynsigman.unregister
        func(zynsigman.S_MIDI, zynsigman.SS_MIDI_NOTE_ON, self._on_midi_note_on)

    def _enable_arranger_mode(self, status):
        if self._is_arranger_mode == status:
            return
        self._is_arranger_mode = status
        if status:
            self._note_pads_function = FN_SELECT_PATTERN
            self._previous_screen = self._current_screen
            self._state_manager.send_cuia("SCREEN_ARRANGER")
            self._update_ui_arranger(
                cell_selected=(self._pattern_clock_offset // 24, self._selected_seq))
        else:
            self._note_pads_function = FN_PLAY_NOTE
            previous_screen = getattr(self, "_previous_screen", None)
            cuia_cmd = self.SCREEN_CUIA_MAP.get(previous_screen)
            if cuia_cmd is not None:
                self._state_manager.send_cuia(cuia_cmd)
        self._refresh_status_leds()
        self._refresh_note_pads()

    def _update_for_selected_pattern(self):
        spb = self._libseq.getStepsPerBeat()
        self._clock.set_steps_per_beat(spb)

        steps = self._libseq.getSteps()
        self._used_pads = min(32, steps)
        self._cursor = self._get_pattern_playhead()

    def _get_pattern_playhead(self):
        # NOTE: libseq.getPatternPlayhead() does not work here!
        cps = self._libseq.getClocksPerStep()
        playpos = self._libseq.getPlayPosition(self._zynseq.bank, self._selected_seq)
        playpos -= self._pattern_clock_offset

        # If playhead is in previous patterns, return a big number (which will be ignored)
        if playpos < 0:
            return 256
        return playpos // cps

    def _set_pattern(self, pattern):
        self._selected_pattern = pattern
        self._libseq.selectPattern(self._selected_pattern)
        self._update_for_selected_pattern()

    def _change_to_pattern_index(self, from_idx, to_idx, copy_pattern=False):
        if copy_pattern:
            self._copy_pattern(from_idx, to_idx)

        self._selected_pattern_idx = to_idx
        self._set_pattern(self._sequence_patterns[to_idx])
        self._pattern_clock_offset = self._get_pattern_position(to_idx)
        self._update_ui_arranger(
            cell_selected=(self._pattern_clock_offset // 24, self._selected_seq))
        self.refresh(only_steps=True)

    def _change_to_previous_pattern(self):
        if self._selected_pattern_idx > 0:
            self._change_to_pattern_index(
                self._selected_pattern_idx,
                self._selected_pattern_idx - 1,
                self._is_select_pressed)
        self._show_patterns_bar()

    def _change_to_next_pattern(self):
        bank = self._zynseq.bank
        seq = self._selected_seq
        # FIXME: Add support for track selection
        track = 0

        if self._selected_pattern_idx < 7:
            if self._selected_pattern_idx >= len(self._sequence_patterns) - 1:
                # Create a new pattern only if SHIFT is pressed
                if not self._is_shifted:
                    return
                pattern = self._libseq.createPattern()
                if not self._add_pattern_to_end_of_track(bank, seq, track, pattern):
                    logging.error(" could not add a new pattern!")
                    return
                self._sequence_patterns.append(pattern)

            self._change_to_pattern_index(
                self._selected_pattern_idx,
                self._selected_pattern_idx + 1,
                self._is_select_pressed)
        self._show_patterns_bar()

    def _copy_pattern(self, from_idx, to_idx):
        self._libseq.copyPattern(
            self._sequence_patterns[from_idx],
            self._sequence_patterns[to_idx])
        self._libseq.updateSequenceInfo()

    def _clear_pattern(self, index):
        current = self._libseq.getPatternIndex()
        pattern = self._sequence_patterns[index]
        self._libseq.selectPattern(pattern)
        self._libseq.clear()
        self._libseq.updateSequenceInfo()
        if current != -1 and current != pattern:
            self._libseq.selectPattern(current)

        if index == self._selected_pattern_idx:
            self.refresh(only_steps=True)

    def _remove_pattern(self, index):
        bank = self._zynseq.bank
        seq = self._selected_seq
        # FIXME: Add support for track selection
        track = 0

        # Last pattern could not be removed
        if len(self._sequence_patterns) == 1:
            return

        # Move right patterns one place to the left
        position = None
        for offset, pattern in enumerate(self._sequence_patterns[index:]):
            prev_position = position
            position = self._get_pattern_position(index + offset)
            self._libseq.removePattern(bank, seq, track, position)
            if offset > 0:
                self._libseq.addPattern(bank, seq, track, prev_position, pattern)

        # If pattern to remove is to the left of selected, then update selected
        if index <= self._selected_pattern_idx:
            self._selected_pattern_idx = max(0, self._selected_pattern_idx - 1)

        self._sequence_patterns = self._get_sequence_patterns(self._zynseq.bank, seq, create=True)
        self._change_to_pattern_index(0, self._selected_pattern_idx)
        new_position = self._get_pattern_position(self._selected_pattern_idx)
        self._update_ui_arranger(cell_selected=(new_position // 24, self._selected_seq))

    def _get_pattern_position(self, index):
        position = 0
        for pattern in self._sequence_patterns[:index]:
            position += self._libseq.getPatternLength(pattern)
        return position

    def _show_patterns_bar(self, overlay=True):
        for i in range(8):
            pad = BTN_PAD_START + i
            color = COLOR_WHITE
            mode = LED_BRIGHT_10
            if i < len(self._sequence_patterns):
                mode = LED_BRIGHT_100
                if i == self._selected_pattern_idx:
                    color = COLOR_RED
            self._leds.led_on(pad, color, mode, overlay=overlay)

    def _get_step_colors(self):
        retval = []
        if self._selected_note is None:
            return retval

        num_steps = min(32, self._libseq.getSteps())
        note = self._selected_note.note
        duration = None
        for step in range(num_steps):
            is_old_note = duration != None
            if duration is None:
                duration = self._libseq.getNoteDuration(step, note)
            if not duration:
                duration = None
                continue

            mode = 1
            if not is_old_note:
                mode = (self._libseq.getNoteVelocity(step, note) * 6) // 127
            pad = self._pads[step]
            retval.append((pad, COLOR_AMBER if is_old_note else COLOR_RED, mode))
            if duration <= 1:
                duration = None
                continue

            duration -= 1
        return retval

    def _create_note_control(self, kind, note):
        available = [VelocityControl, StutterCountControl, StutterDurationControl]
        for Control in available:
            if Control.KIND == kind:
                break
        else:
            logging.error(f" control kind not supported: {kind}")
            return False

        notes = {}
        row_led = None
        if note == BTN_SOFT_KEY_SELECT:
            row_led = note
            notes = self._note_pads

        elif BTN_SOFT_KEY_CLIP_STOP <= note <= BTN_SOFT_KEY_REC_ARM:
            row = note - BTN_SOFT_KEY_CLIP_STOP

            # Skip not used rows
            if (row + 1) * self.PAD_COLS - self._used_pads >= self.PAD_COLS:
                return False

            row_led = note
            for step in range(self.PAD_COLS * row, self.PAD_COLS * (row + 1)):
                step_prx = StepProxy(self._libseq, self._selected_note.note, step)
                if step_prx.duration > 0:
                    notes[step % self.PAD_COLS] = step_prx

        elif BTN_PAD_START <= note <= BTN_PAD_START + 7:
            if note not in self._note_pads:
                return False
            notes[note] = self._note_pads[note]

        else:
            if self._selected_note is None:
                return False
            col = note % self.PAD_COLS
            step = self._pads.index(note)
            step_prx = StepProxy(self._libseq, self._selected_note.note, step)
            if step_prx.duration <= 0:
                return False
            notes[col] = step_prx

        channel = self._libseq.getChannel(self._zynseq.bank, self._selected_seq, 0)
        self._note_config = Control(self, notes, channel, row_led=row_led)
        self.refresh()
        return True


# --------------------------------------------------------------------------
#  Class to access individual steps using the same interface that pads uses,
#  to be used by StepSeq's PropertyControls
# --------------------------------------------------------------------------
class StepProxy:
    def __init__(self, libseq, note, step):
        self._libseq = libseq
        self._step = step

        # These are public properties
        self.note = note

    @property
    def velocity(self):
        return self._libseq.getNoteVelocity(self._step, self.note)

    @velocity.setter
    def velocity(self, value):
        self._libseq.setNoteVelocity(self._step, self.note, value)

    @property
    def duration(self):
        return self._libseq.getNoteDuration(self._step, self.note)

    @property
    def stutter_count(self):
        return self._libseq.getStutterCount(self._step, self.note)

    @stutter_count.setter
    def stutter_count(self, value):
        self._libseq.setStutterCount(self._step, self.note, value)

    @property
    def stutter_duration(self):
        return self._libseq.getStutterDur(self._step, self.note)

    @stutter_duration.setter
    def stutter_duration(self, value):
        self._libseq.setStutterDur(self._step, self.note, value)


# --------------------------------------------------------------------------
#  Base of controller utilities to change some property of a NotePad/Step
# --------------------------------------------------------------------------
class BaseControl:
    KIND            = "undefined"
    PAD_COLS        = 8
    PAD_ROWS        = 5
    INDICATOR_LED   = None
    INDICATOR_BLINK = False
    COLOR           = COLOR_PURPLE

    STEPS           = [20, 40, 60, 80, 100]
    HALF_STEPS      = [10, 30, 50, 70, 90]

    # NOTE: This class is 'friend' (if you allow me the license) with StepSeqHandler
    # so it will access some of its private members

    def __init__(self, handler: StepSeqHandler, notes: dict, channel, row_led):
        self._leds: FeedbackLEDs = handler._leds
        self._note_player = handler._note_player
        self._libseq = handler._libseq
        self._is_playing = handler._is_playing

        self._channel = channel
        self._row_led = row_led
        self._notes = notes

    def clone_to(self, kind):
        available = [VelocityControl, StutterCountControl, StutterDurationControl]
        for Control in available:
            if Control.KIND == kind:
                return Control(self, self._notes, self._channel, self._row_led)
        raise TypeError(f"Unknown kind to clone to: {kind}")

    def refresh(self, only_steps=False, only_status=False, is_shifted=False):
        if not only_steps and not is_shifted:
            if self.INDICATOR_LED is not None:
                if self.INDICATOR_BLINK:
                    self._leds.led_blink(self.INDICATOR_LED)
                else:
                    self._leds.led_on(self.INDICATOR_LED)
            if self._row_led is not None:
                self._leds.led_on(self._row_led)

        if not only_status:
            self._leds.pad_leds_off()
            for pad, note in self._notes.items():
                col = pad % self.PAD_COLS
                value = self._get_note_property(note)
                self._draw_column(col, value)

    def update_status(self, playing=False):
        self._is_playing = playing

    def note_on(self, note, velocity, shifted_override=None):
        col = (note - BTN_PAD_START) % self.PAD_COLS
        note_spec = self._notes.get(col)
        if note_spec is None:
            return

        row = (note - BTN_PAD_START) // self.PAD_COLS
        current_value = self._get_note_property(note_spec)

        if shifted_override:
            value = 0
        else:
            value = self.STEPS[row]
            if value == current_value:
                value = self.HALF_STEPS[row]

        self._set_note_property(note_spec, value)
        self._draw_column(col, value)
        self._play_note(note_spec)

    def _play_note(self, note):
        if not self._is_playing:
            self._note_player.play(note.note, note.velocity, note.duration,
                self._channel, note.stutter_count, note.stutter_duration)

    def _draw_column(self, col, value):
        bright_values = [None, LED_BRIGHT_50, LED_BRIGHT_100]

        for r in range(self.PAD_ROWS):
            pad = r * self.PAD_COLS + col
            brightness = bright_values[bisect((self.HALF_STEPS[r], self.STEPS[r]), value)]
            if brightness is not None:
                self._leds.led_on(pad, self.COLOR, brightness)
            else:
                self._leds.led_on(pad, COLOR_PINK_WARM, LED_BRIGHT_10)

    def _get_note_property(self, note):
        raise NotImplementedError(f"{self.__class__.__name__}._get_note_property()")

    def _set_note_property(self, note, value):
        raise NotImplementedError(f"{self.__class__.__name__}._set_note_property()")


# --------------------------------------------------------------------------
#  A controller utility to change velocity of a NotePad/Step
# --------------------------------------------------------------------------
class VelocityControl(BaseControl):
    KIND            = "velocity"
    INDICATOR_LED   = BTN_KNOB_CTRL_VOLUME
    COLOR           = COLOR_AQUA

    STEPS           = [25, 50, 76, 101, 127]
    HALF_STEPS      = [12, 38, 63, 88, 114]

    def _get_note_property(self, note):
        return note.velocity

    def _set_note_property(self, note, value):
        note.velocity = value


# --------------------------------------------------------------------------
#  A controller utility to change stutter count of a NotePad/Step
# --------------------------------------------------------------------------
class StutterCountControl(BaseControl):
    KIND            = "stutter-count"
    INDICATOR_LED   = BTN_KNOB_CTRL_SEND
    COLOR           = COLOR_LIME_DARK

    STEPS           = [2, 4, 8, 12, 20]
    HALF_STEPS      = [1, 3, 6, 10, 15]

    def _get_note_property(self, note):
        return note.stutter_count

    def _set_note_property(self, note, value):
        note.stutter_count = value


# --------------------------------------------------------------------------
#  A controller utility to change stutter duration of a NotePad/Step
# --------------------------------------------------------------------------
class StutterDurationControl(BaseControl):
    KIND            = "stutter-duration"
    INDICATOR_LED   = BTN_KNOB_CTRL_SEND
    INDICATOR_BLINK = True
    COLOR           = COLOR_RUSSET

    STEPS           = [2, 4, 8, 20, 40]
    HALF_STEPS      = [1, 3, 6, 10, 30]

    def _get_note_property(self, note):
        return note.stutter_duration

    def _set_note_property(self, note, value):
        note.stutter_duration = value
