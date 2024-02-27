#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Akai APC Key 25 mk2"
#
# Copyright (C) 2023,2024 Oscar Aceña <oscaracena@gmail.com>
#
#******************************************************************************
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
#******************************************************************************

import time
from bisect import bisect
from functools import partial
from threading import Thread, RLock, Event
from zyngine.ctrldev.zynthian_ctrldev_base import (
    zynthian_ctrldev_zynmixer, zynthian_ctrldev_zynpad
)
from zyngine.zynthian_engine_audioplayer import zynthian_engine_audioplayer
from zyngine.zynthian_signal_manager import zynsigman
from zyngui import zynthian_gui_config
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq


# Some MIDI event constants
EV_NOTE_ON                           = 0x09
EV_NOTE_OFF                          = 0x08
EV_CC                                = 0x0B

# APC Key25 buttons
BTN_SHIFT                            = 0x62
BTN_STOP_ALL_CLIPS                   = 0x51
BTN_PLAY                             = 0x5b
BTN_RECORD                           = 0x5d

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
COLOR_BLUE_DARK                      = 0x2D
COLOR_WHITE                          = 0x08
COLOR_ORANGE                         = 0x09
COLOR_PURPLE                         = 0x51
COLOR_PINK                           = 0x39
COLOR_YELLOW                         = 0x0D
COLOR_LIME                           = 0x4B

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

FN_PATTERN_MANAGER                   = 0x08
FN_PATTERN_COPY                      = 0x09
FN_PATTERN_MOVE                      = 0x0a
FN_PATTERN_CLEAR                     = 0x0b

PT_SHORT                             = "short"
PT_BOLD                              = "bold"
PT_LONG                              = "long"
PT_BOLD_TIME                         = 0.3
PT_LONG_TIME                         = 2.0


# --------------------------------------------------------------------------
# 'Akai APC Key 25 mk2' device controller class
# --------------------------------------------------------------------------
class zynthian_ctrldev_akai_apc_key25_mk2(zynthian_ctrldev_zynmixer, zynthian_ctrldev_zynpad):

    dev_ids = ["APC Key 25 mk2 IN 2"]

    def __init__(self, state_manager, idev_in, idev_out=None):
        self._leds = FeedbackLEDs(idev_out)
        self._device_handler = DeviceHandler(state_manager, self._leds)
        self._mixer_handler = MixerHandler(state_manager, self._leds)
        self._padmatrix_handler = PadMatrixHandler(state_manager, self._leds)
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
        evtype = (ev & 0xF00000) >> 20
        if evtype == EV_NOTE_ON:
            note = (ev >> 8) & 0x7F
            if note == BTN_SHIFT:
                return self._on_shift_changed(True)

            if self._is_shifted:
                # Change global mode here
                if note == BTN_KNOB_CTRL_DEVICE:
                    self._current_handler = self._device_handler
                elif note in [BTN_KNOB_CTRL_PAN, BTN_KNOB_CTRL_VOLUME]:
                    self._current_handler = self._mixer_handler
                    self._padmatrix_handler.refresh()

                # Change sub-modes here
                elif note == BTN_SOFT_KEY_CLIP_STOP:
                    if self._current_handler == self._mixer_handler:
                        self._padmatrix_handler.enable_pattman(True)
                elif BTN_SOFT_KEY_CLIP_STOP < note <= BTN_SOFT_KEY_END:
                    self._padmatrix_handler.enable_pattman(False)

            # Padmatrix related events
            if self._current_handler == self._mixer_handler:
                if BTN_PAD_START <= note <= BTN_PAD_END:
                    return self._padmatrix_handler.pad_press(note)
                elif note == BTN_RECORD and not self._is_shifted:
                    return self._padmatrix_handler.on_record_changed(True)
                elif note == BTN_PLAY:
                    return self._padmatrix_handler.on_toggle_play()
                elif (BTN_SOFT_KEY_START <= note <= BTN_SOFT_KEY_END
                      and not self._is_shifted):
                    row = note - BTN_SOFT_KEY_START
                    return self._padmatrix_handler.on_toggle_play_row(row)
                elif BTN_TRACK_1 <= note <= BTN_TRACK_8:
                    track = note - BTN_TRACK_1
                    self._padmatrix_handler.on_track_changed(track, True)
                elif note == BTN_STOP_ALL_CLIPS:
                    self._padmatrix_handler.note_on(note, self._is_shifted)

            return self._current_handler.note_on(note, self._is_shifted)

        elif evtype == EV_NOTE_OFF:
            note = (ev >> 8) & 0x7F
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
            ccnum = (ev & 0x7F00) >> 8
            ccval = (ev & 0x007F)
            return self._current_handler.cc_change(ccnum, ccval)

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

    def _on_shift_changed(self, state):
        self._is_shifted = state
        self._current_handler.on_shift_changed(state)
        if self._current_handler == self._mixer_handler:
            self._padmatrix_handler.on_shift_changed(state)
        return True

    def _on_gui_show_screen(self, screen):
        self._device_handler.on_screen_change(screen)
        self._padmatrix_handler.on_screen_change(screen)
        if self._current_handler == self._device_handler:
            self._current_handler.refresh()

    def _on_media_change_state(self, state, media, kind):
        self._device_handler.on_media_change(media, kind, state)
        if self._current_handler == self._device_handler:
            self._current_handler.refresh()


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
            if elapsed > PT_LONG_TIME:
                retval = btn
                break
        if retval:
            self._pressed.pop(btn, None)
        return retval, elapsed if retval else 0

    def _run_callback(self, note, elapsed):
        ptype = [PT_SHORT, PT_BOLD, PT_LONG][bisect([PT_BOLD_TIME, PT_LONG_TIME], elapsed)]
        try:
            self._callback(note, ptype)
        except Exception as ex:
            print(f" error in handler: {ex}")


# --------------------------------------------------------------------------
# Feedback LEDs controller
# --------------------------------------------------------------------------
class FeedbackLEDs:
    def __init__(self, idev):
        self._idev = idev

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

    def led_off(self, led):
        lib_zyncore.dev_send_note_on(self._idev, 0, led, 0)

    def led_on(self, led, color=1, brightness=0):
        lib_zyncore.dev_send_note_on(self._idev, brightness, led, color)

    def led_blink(self, led):
        lib_zyncore.dev_send_note_on(self._idev, 0, led, 2)


# --------------------------------------------------------------------------
#  Base class for handlers
# --------------------------------------------------------------------------
class BaseHandler:
    def __init__(self, state_manager, leds):
        self._leds = leds
        self._state_manager = state_manager
        self._chain_manager = state_manager.chain_manager
        self._zynmixer = state_manager.zynmixer
        self._zynseq = state_manager.zynseq

        self._is_shifted = False

    def refresh(self):
        pass

    def note_on(self, note, shifted_override=None):
        pass

    def note_off(self, note, shifted_override=None):
        pass

    def cc_change(self, ccnum, ccval):
        pass

    def on_shift_changed(self, state):
        self._is_shifted = state
        return True

    def _on_shifted_override(self, override=None):
        if override is not None:
            self._is_shifted = override


# --------------------------------------------------------------------------
# Handle GUI (device mode)
# --------------------------------------------------------------------------
class DeviceHandler(BaseHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._knobs_ease = {}
        self._is_alt_active = False
        self._is_playing = set()
        self._is_recording = set()
        self._btn_timer = ButtonTimer(self._handle_timed_button)

        self._btn_actions = {
            BTN_OPT_ADMIN:      ("MENU", "SCREEN_ADMIN"),
            BTN_MIX_LEVEL:      ("SCREEN_AUDIO_MIXER", "SCREEN_ALSA_MIXER"),
            BTN_CTRL_PRESET:    ("SCREEN_CONTROL", "PRESET"),
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
            BTN_KNOB_1: (lambda is_bold: [f"ZYNSWITCH:0,{'B' if is_bold else 'S'}"]),
            BTN_KNOB_2: (lambda is_bold: [f"ZYNSWITCH:1,{'B' if is_bold else 'S'}"]),
            BTN_KNOB_3: (lambda is_bold: [f"ZYNSWITCH:2,{'B' if is_bold else 'S'}"]),
            BTN_KNOB_4: (lambda is_bold: [f"ZYNSWITCH:3,{'B' if is_bold else 'S'}"]),
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

    def note_on(self, note, shifted_override=None):
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
                self._state_manager.send_cuia("ZYNSWITCH", [3, 'S'])
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
        zynpot = {
            KNOB_LAYER: 0,
            KNOB_BACK: 1,
            KNOB_SNAPSHOT: 2,
            KNOB_SELECT: 3
        }.get(ccnum, None)
        if zynpot is None:
            return

        # Knobs ease is used to control knob speed
        count = self._knobs_ease.get(ccnum, 0)
        delta = ccval if ccval < 64 else (ccval - 128)
        steps = 2 if self._is_shifted else 8

        if (delta < 0 and count > 0) or (delta > 0 and count < 0):
            count = 0
        count += delta
        if abs(count) < steps:
            self._knobs_ease[ccnum] = count
            return

        self._knobs_ease[ccnum] = 0
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
        if press_type == PT_LONG:
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
            actions = actions(press_type == PT_BOLD)

        idx = -1
        if press_type == PT_SHORT:
            idx = self._btn_states[btn]
            idx = (idx + 1) % len(actions)
            cuia = actions[idx]
        elif press_type == PT_BOLD:
            # In buttons with 2 functions, the default on bold press is the second
            idx = 1 if len(actions) > 1 else 0
            cuia = actions[idx]

        # Split params, if given
        params = []
        if ":" in cuia:
            cuia, params = cuia.split(":")
            params = params.split(",")

        self._state_manager.send_cuia(cuia, params)
        return True


# --------------------------------------------------------------------------
# Handle Mixer (Mixpad mode)
# --------------------------------------------------------------------------
class MixerHandler(BaseHandler):

    # To control main level, use SHIFT + K1
    main_chain_knob = KNOB_1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
                FN_PATTERN_MANAGER: BTN_SOFT_KEY_CLIP_STOP,
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

            if self._track_buttons_function == FN_PATTERN_MANAGER:
                # FIXME: update pattman function buttons too!
                self._leds.led_blink(BTN_SOFT_KEY_CLIP_STOP)
                return

            query = {
                FN_MUTE: self._zynmixer.get_mute,
                FN_SOLO: self._zynmixer.get_solo,
                FN_SELECT: lambda c: c == (self._active_chain - 1),
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

    def note_on(self, note, shifted_override=None):
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
                self._track_buttons_function = FN_PATTERN_MANAGER
            elif note == BTN_LEFT:
                self._chains_bank = 0
            elif note == BTN_RIGHT:
                self._chains_bank = 1
            elif note == BTN_STOP_ALL_CLIPS:
                self._run_track_button_function_on_channel(255)
            elif note == BTN_SOFT_KEY_SELECT:
                self._track_buttons_function = FN_SELECT
            elif note == BTN_RECORD:
                self._state_manager.send_cuia("TOGGLE_RECORD")
                return True  # skip refresh
            elif note == BTN_UP:
                self._state_manager.send_cuia("BACK")
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

    def _run_track_button_function_on_channel(self, chain):
        if isinstance(chain, int):
            channel = chain
            chain = None
        else:
            channel = chain.mixer_chan

        if self._track_buttons_function == FN_MUTE:
            val = self._zynmixer.get_mute(channel) ^ 1
            self._zynmixer.set_mute(channel, val, True)
            return True

        if self._track_buttons_function == FN_SOLO:
            val = self._zynmixer.get_solo(channel) ^ 1
            self._zynmixer.set_solo(channel, val, True)
            return True

        if self._track_buttons_function == FN_SELECT and chain is not None:
            self._chain_manager.set_active_chain_by_id(chain.chain_id)
            return True


# --------------------------------------------------------------------------
#  Handle pad matrix for Zynseq (in Mixpad mode)
# --------------------------------------------------------------------------
class PadMatrixHandler(BaseHandler):

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._libseq = self._zynseq.libseq
        self._cols = 8
        self._rows = 5
        self._is_record_pressed = False
        self._track_btn_pressed = None
        self._current_screen = None
        self._playing_seqs = set()
        self._btn_timer = ButtonTimer(self._handle_timed_button)

        # Pattman sub-mode
        self._pattman_func = None
        self._pattman_src_seq = None

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
        # If pattman is enabled, ignore row functions
        if self._pattman_func is not None:
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

        # Switch pattman function (if pattman enabled and SHIFT is not pressed)
        if state and self._pattman_func is not None and not self._is_shifted:
            btn = BTN_TRACK_1 + track

            if btn == BTN_LEFT:
                return self._change_scene(-1)
            if btn == BTN_RIGHT:
                return self._change_scene(1)

            func = {
                BTN_KNOB_CTRL_VOLUME: FN_PATTERN_COPY,
                BTN_KNOB_CTRL_PAN: FN_PATTERN_MOVE,
                BTN_KNOB_CTRL_SEND: FN_PATTERN_CLEAR,
            }.get(btn)
            if func is not None:
                self._pattman_func = func
                self._refresh_tool_buttons()

                # Function CLEAR does not have source sequence, remove it
                if func == FN_PATTERN_CLEAR and self._pattman_src_seq is not None:
                    scene, seq = self._pattman_src_seq
                    self._pattman_src_seq = None
                    if scene == self._zynseq.bank:
                        self._update_pad(seq)

    def on_screen_change(self, screen):
        self._current_screen = screen

    def on_shift_changed(self, state):
        retval = super().on_shift_changed(state)
        # Update tool buttons only when SHIFT is not pressed
        if not state:
            self._refresh_tool_buttons()
        return retval

    def enable_pattman(self, state):
        if state:
            if self._pattman_func is None:
                self._pattman_func = FN_PATTERN_COPY
        else:
            self._pattman_func = None
            self._pattman_src_seq = None
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

    def note_on(self, note, shifted_override=None):
        self._on_shifted_override(shifted_override)
        if not self._is_shifted:
            if note == BTN_STOP_ALL_CLIPS:
                self._btn_timer.is_pressed(note, time.time())

    def note_off(self, note, shifted_override=None):
        if note == BTN_STOP_ALL_CLIPS:
            self._btn_timer.is_released(note)

    def pad_press(self, pad):
        index = self._pads.index(pad)
        col = index // self._rows
        row = index % self._rows

        # Pad outside grid, discarded
        if col >= self._zynseq.col_in_bank or row >= self._zynseq.col_in_bank:
            return True

        seq = col * self._zynseq.col_in_bank + row
        if self._pattman_func is not None:
            self._pattman_handle_pad_press(seq)
        elif self._track_btn_pressed is not None:
            self._clear_pattern((self._zynseq.bank, seq))
        elif self._is_shifted:
            self._show_pattern_editor(seq)
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
        btn = self._pads[col * self._rows + row]
        pattern = self._libseq.getPattern(bank, seq, 0, 0)
        is_empty = self._zynseq.is_pattern_empty(pattern)
        color = self.GROUP_COLORS[group]

        # If pattman is enabled, update according to it's function
        if self._pattman_func is not None:
            led_mode = LED_BRIGHT_25 if is_empty else LED_BRIGHT_100
            if (self._pattman_func in (FN_PATTERN_COPY, FN_PATTERN_MOVE)
                    and self._pattman_src_seq is not None):
                src_scene, src_seq = self._pattman_src_seq
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

    def _handle_timed_button(self, btn, ptype):
        if btn == BTN_STOP_ALL_CLIPS:
            if ptype == PT_LONG:
                self._state_manager.send_cuia("ALL_SOUNDS_OFF")
                self._state_manager.stop_midi_playback()
                self._state_manager.stop_audio_player()
                # FIXME: this is fishy...
                self._state_manager.audio_player.engine.player.set_position(
                    self._state_manager.audio_player.handle, 0.0)
            else:
                in_all_banks = ptype == PT_BOLD
                self._stop_all_seqs(in_all_banks)

    def _pattman_handle_pad_press(self, seq):
        if self._pattman_func is None:
            return

        # FIXME: if pattern editor is open, and showing affected seq, update it!
        # FIXME: if Zynpad is open, also update it!

        seq_is_empty = self._libseq.isEmpty(self._zynseq.bank, seq)
        if self._pattman_func == FN_PATTERN_CLEAR:
            if not seq_is_empty:
                self._clear_pattern((self._zynseq.bank, seq))
            return

        # Set selected sequence as source
        if self._pattman_src_seq is None:
            if not seq_is_empty:
                self._pattman_src_seq = (self._zynseq.bank, seq)
        else:
            # Clear source sequence
            if self._pattman_src_seq == (self._zynseq.bank, seq):
                self._pattman_src_seq = None
            # Copy/Move source to selected sequence (will be overwritten)
            else:
                if self._pattman_func == FN_PATTERN_COPY:
                    self._copy_pattern(self._pattman_src_seq, seq)
                elif self._pattman_func == FN_PATTERN_MOVE:
                    self._copy_pattern(self._pattman_src_seq, seq)
                    self._clear_pattern(self._pattman_src_seq)
                    self._pattman_src_seq = None

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
        # Switch on pattman active function
        if self._pattman_func is not None:
            active = {
                FN_PATTERN_COPY: BTN_KNOB_CTRL_VOLUME,
                FN_PATTERN_MOVE: BTN_KNOB_CTRL_PAN,
                FN_PATTERN_CLEAR: BTN_KNOB_CTRL_SEND,
            }[self._pattman_func]
            for idx in range(8):
                btn = BTN_TRACK_1 + idx
                self._leds.led_state(btn, btn == active)
            return

        # If pattman is disabled, show playing status in row launchers
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

    def _clear_pattern(self, seq):
        scene, seq = seq
        pattern = self._libseq.getPattern(scene, seq, 0, 0)
        self._libseq.selectPattern(pattern)
        self._libseq.clear()
        self._libseq.updateSequenceInfo()
        self._update_pad(seq)

    def _copy_pattern(self, src, dst):
        scene_src, seq_src = src
        patt_src = self._libseq.getPattern(scene_src, seq_src, 0, 0)
        patt_dst = self._libseq.getPattern(self._zynseq.bank, dst, 0, 0)
        self._libseq.copyPattern(patt_src, patt_dst)
        self._libseq.updateSequenceInfo()

    def _show_pattern_editor(self, seq):
        # This way shows Zynpad everytime you change the sequuence (but is decoupled from UI)
        # self._state_manager.send_cuia("SCREEN_ZYNPAD")
        # self._select_pad(seq)
        # self._state_manager.send_cuia("SCREEN_PATTERN_EDITOR")

        # FIXME: this way avoids to show Zynpad every time, BUT is coupled to UI!
        if self._current_screen != 'pattern_editor':
            self._state_manager.send_cuia("SCREEN_ZYNPAD")
        self._select_pad(seq)
        zynthian_gui_config.zyngui.screens["zynpad"].show_pattern_editor()

    def _select_pad(self, pad):
        # FIXME: this SHOULD be a CUIA, not this hack! (is coupled with UI)
        zynthian_gui_config.zyngui.screens["zynpad"].select_pad(pad)
