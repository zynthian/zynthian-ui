#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Akai MPK mini mk3"
#
# Copyright (C) 2024 Oscar Aceña <oscaracena@gmail.com>
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
import logging
from bisect import bisect

from zyncoder.zyncore import lib_zyncore
from zyngine.zynthian_signal_manager import zynsigman

from .zynthian_ctrldev_base import (
    zynthian_ctrldev_zynmixer
)
from .zynthian_ctrldev_base_extended import (
    CONST, KnobSpeedControl, IntervalTimer, ButtonTimer
)
from .zynthian_ctrldev_base_ui import ModeHandlerBase


# NOTE: some of these constants are taken from:
# https://github.com/tsmetana/mpk3-settings/blob/master/src/message.h

# Offsets from the beginning of the SYSEX message
OFF_PGM_NAME                = 7
OFF_KEYBED_OCTAVE           = 26
OFF_ARP_ON                  = 27
OFF_ARP_MODE                = 28
OFF_ARP_DIVISION            = 29
OFF_ARP_CLK_EXT             = 30
OFF_ARP_LATCH               = 31
OFF_ARP_SWING               = 32
OFF_ARP_OCTAVE              = 36

# Message constants
MANUFACTURER_ID             = 0x47
PRODUCT_ID                  = 0x49
DATA_MSG_LEN                = 252
MSG_PAYLOAD_LEN             = 246
MSG_DIRECTION_OUT           = 0x7f
MSG_DIRECTION_IN            = 0x00

# Command values
CMD_WRITE_DATA              = 0x64
CMD_QUERY_DATA              = 0x66
CMD_INCOMING_DATA           = 0x67

# Name (program, knob) string length
NAME_STR_LEN                = 16

# Aftertouch settings
AFTERTOUCH_OFF              = 0x00
AFTERTOUCH_CHANNEL          = 0x01
AFTERTOUCH_POLYPHONIC       = 0x02

# Keybed octave
KEY_OCTAVE_MIN              = 0x00
KEY_OCTAVE_MAX              = 0x08

# Arpeggiator settings
ARP_ON                      = 0x7f
ARP_OFF                     = 0x00
ARP_OCTAVE_MIN              = 0x00
ARP_OCTAVE_MAX              = 0x03
ARP_MODE_UP                 = 0x00
ARP_MODE_DOWN               = 0x01
ARP_MODE_EXCL               = 0x02
ARP_MODE_INCL               = 0x03
ARP_MODE_ORDER              = 0x04
ARP_MODE_RAND               = 0x05
ARP_DIV_1_4                 = 0x00
ARP_DIV_1_4T                = 0x01
ARP_DIV_1_8                 = 0x02
ARP_DIV_1_8T                = 0x03
ARP_DIV_1_16                = 0x04
ARP_DIV_1_16T               = 0x05
ARP_DIV_1_32                = 0x06
ARP_DIV_1_32T               = 0x07
ARP_LATCH_OFF               = 0x00
ARP_LATCH_ON                = 0x01
ARP_SWING_MIN               = 0x00
ARP_SWING_MAX               = 0x19

# Clock settings
CLK_INTERNAL                = 0x00
CLK_EXTERNAL                = 0x01
TEMPO_TAPS_MIN              = 0x02
TEMPO_TAPS_MAX              = 0x04
BPM_MIN                     = 60
BPM_MAX                     = 240

# Joystick
JOY_MODE_PITCHBEND          = 0x00
JOY_MODE_SINGLE             = 0x01
JOY_MODE_DUAL               = 0x02

# Knobs
KNOB_MODE_ABS               = 0x00
KNOB_MODE_REL               = 0x01

# Device Layout constants
DEFAULT_KEYBED_CH           = 0x00
DEFAULT_PADS_CH             = 0x09
DEFAULT_TEMPO_TAPS          = 0x03
DEFAULT_KEYBED_OCTAVE       = 0x04

# PC numbers for related actions
PROG_MIXER_MODE             = 0x04
PROG_DEVICE_MODE            = 0x05
PROG_PATTERN_MODE           = 0x06
PROG_NOTEPAD_MODE           = 0x07
PROG_USER_MODE              = 0x0c
PROG_CONFIG_MODE            = 0x0d

PROG_OPEN_MIXER             = 0x00
PROG_OPEN_ZYNPAD            = 0x01
PROG_OPEN_TEMPO             = 0x02
PROG_OPEN_SNAPSHOT          = 0x03

# Function/State constants
FN_VOLUME                   = 0x01
FN_PAN                      = 0x02
FN_SOLO                     = 0x03
FN_MUTE                     = 0x04
FN_SELECT                   = 0x06


# --------------------------------------------------------------------------
#  SysEx command for querying a device program/settings
# --------------------------------------------------------------------------
class SysExQueryProgram:
    def __init__(self, program=0):
        assert 0 <= program <= 8, "Invalid program number, only 0 (RAM) to 8 available."

        self.data = [
            MANUFACTURER_ID, MSG_DIRECTION_OUT, PRODUCT_ID, CMD_QUERY_DATA,
            0, 1, program,
        ]

    def __repr__(self):
        return " ".join(f"{b:02X}" for b in self.data)


# --------------------------------------------------------------------------
#  SysEx command for updating a device program/settings
# --------------------------------------------------------------------------
class SysExSetProgram:
    def __init__(self, program=0, name="Zynthian", channels={}, aftertouch=AFTERTOUCH_OFF,
                 keybed_octave=4, arp={}, tempo_taps=3, tempo=90, joy={},
                 pads={}, knobs={}, transpose=0x0c):

        arp_swing = int(arp.get("swing", ARP_SWING_MIN))
        assert 0 <= program <= 8, "Invalid program number: {program} (valid: 0(RAM)-8)."
        assert aftertouch in [AFTERTOUCH_OFF, AFTERTOUCH_CHANNEL, AFTERTOUCH_POLYPHONIC], \
            f"Invalid aftertouch mode: {aftertouch} (valid: 0-2)."
        assert KEY_OCTAVE_MIN <= keybed_octave <= KEY_OCTAVE_MAX, \
            f"Invalid keybed octave: {keybed_octave} (valid: 0-8)."
        assert ARP_SWING_MIN <= arp_swing <= ARP_SWING_MAX, \
            f"Invalid swing value: {arp_swing} (valid: 0-25)."
        assert TEMPO_TAPS_MIN <= tempo_taps <= TEMPO_TAPS_MAX, \
            f"Invalid tempo taps: {tempo_taps} (valid: {TEMPO_TAPS_MIN}-{TEMPO_TAPS_MAX})."
        assert BPM_MIN <= tempo <= BPM_MAX, f"Invalid tempo: {tempo} (valid: 60-240)."
        for c in channels.values():
            assert 0 <= c <= 15, f"Invalid channel number: {c} (valid: 0-15)."
        for field in ["note", "pc", "cc"]:
            assert field in pads, f"Invalid pads definition, missing '{field}' list."
            assert len(pads[field]) == 16, f"Invalid pads definition, len('{field}') != 16."
            for v in pads[field]:
                assert 0 <= v <= 127, f"Invalid pads definition, invalid value: {v}."
        for field in ["mode", "cc", "min", "max", "name"]:
            assert field in knobs, f"Invalid knobs definition, missing '{field}' list."
            assert len(knobs[field]) == 8, f"Invalid knobs definition, len('{field}') != 8."

        self.data = [
            MANUFACTURER_ID, MSG_DIRECTION_OUT, PRODUCT_ID, CMD_WRITE_DATA,
            (MSG_PAYLOAD_LEN >> 7) & 127, MSG_PAYLOAD_LEN & 127, program,
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            channels.get("pads", DEFAULT_PADS_CH),
            aftertouch,
            channels.get("keybed", DEFAULT_KEYBED_CH),
            keybed_octave,
            ARP_ON if arp.get("on") else ARP_OFF,
            arp.get("mode", ARP_MODE_UP),
            arp.get("division", ARP_DIV_1_4),
            CLK_EXTERNAL if arp.get("ext_clock", False) else CLK_INTERNAL,
            ARP_LATCH_ON if arp.get("latch", False) else ARP_LATCH_OFF,
            arp_swing,
            tempo_taps, (tempo >> 7) & 127, tempo & 127,
            arp.get("octave", ARP_OCTAVE_MIN),
            joy.get("x-mode", JOY_MODE_PITCHBEND), joy.get("x-neg-ch", 1), joy.get("x-pos-ch", 2),
            joy.get("y-mode", JOY_MODE_DUAL), joy.get("y-neg-ch", 1), joy.get("y-pos-ch", 2),
        ]

        for pidx in range(16):
            self.data.append(pads["note"][pidx])
            self.data.append(pads["pc"][pidx])
            self.data.append(pads["cc"][pidx])

        for kidx in range(8):
            self.data.append(knobs["mode"][kidx])
            self.data.append(knobs["cc"][kidx])
            self.data.append(knobs["min"][kidx])
            self.data.append(knobs["max"][kidx])
            padname = list(bytes(16))
            padname[:len(knobs["name"][kidx])] = [ord(c) for c in knobs["name"][kidx]]
            self.data += padname

        self.data.append(transpose)

        padname = list(bytes(16))
        padname[:len(name)] = [ord(c) for c in name]
        self.data[OFF_PGM_NAME:OFF_PGM_NAME + NAME_STR_LEN] = padname[:NAME_STR_LEN]

        assert len(self.data) == DATA_MSG_LEN, \
            f"ERROR, invalid message size!! ({len(self.data)} != {DATA_MSG_LEN})"

    @classmethod
    def get_user_fields_from_sysex(self, msg):
        if msg is None or len(msg) != DATA_MSG_LEN:
            logging.error(" invalid SysEx message, discarded!")
            return {}

        return dict(
            keybed_octave = msg[OFF_KEYBED_OCTAVE],
            arp = dict(
                on = msg[OFF_ARP_ON],
                division = msg[OFF_ARP_DIVISION],
                mode = msg[OFF_ARP_MODE],
                latch = msg[OFF_ARP_LATCH] == 1,
                swing = msg[OFF_ARP_SWING],
                octave = msg[OFF_ARP_OCTAVE],
                ext_clock = msg[OFF_ARP_CLK_EXT] == 1,
            )
        )

    def __repr__(self):
        return " ".join(f"{b:02X}" for b in self.data)


# --------------------------------------------------------------------------
#  Class to marshall/un-marshall saved state of those handlers that need it
# --------------------------------------------------------------------------
class SavedState:
    def __init__(self, zynseq):
        self._zynseq = zynseq

        self.is_empty = True
        self.pads_channel = None
        self.keybed_channel = None
        self.keybed_octave = DEFAULT_KEYBED_OCTAVE
        self.pad_notes = []
        self.aftertouch = AFTERTOUCH_OFF
        self.tempo_taps = DEFAULT_TEMPO_TAPS
        self.arpeggiator = dict(
            on = False,
            division = ARP_DIV_1_4,
            mode = ARP_MODE_UP,
            latch = ARP_LATCH_OFF,
            swing = ARP_SWING_MIN,
            octave =  ARP_OCTAVE_MIN,
            ext_clock = False,
        )

    @property
    def tempo(self):
        return int(round(self._zynseq.get_tempo()))

    def load(self, state: dict):
        self.pads_channel = state.get("pads_channel", DEFAULT_PADS_CH)
        self.keybed_channel = state.get("keybed_channel", DEFAULT_KEYBED_CH)
        self.keybed_octave = state.get("keybed_octave", DEFAULT_KEYBED_OCTAVE)
        self.pad_notes = state.get("pad_notes", list(range(16)))
        self.aftertouch = state.get("aftertouch", AFTERTOUCH_OFF)
        self.tempo_taps = state.get("tempo_taps", DEFAULT_TEMPO_TAPS)
        self.arpeggiator = dict(
            on = state.get("on", False),
            division = state.get("division", ARP_DIV_1_4),
            mode = state.get("mode", ARP_MODE_UP),
            latch = state.get("latch", ARP_LATCH_OFF),
            swing = state.get("swing", ARP_SWING_MIN),
            octave =  state.get("octave", ARP_OCTAVE_MIN),
            ext_clock = state.get("ext_clock", False),
        )
        self.is_empty = False

    def save(self):
        return {
            "pads_channel": self.pads_channel,
            "keybed_channel": self.keybed_channel,
            "keybed_octave": self.keybed_octave,
            "pad_notes": self.pad_notes,
            "aftertouch": self.aftertouch,
            "tempo_taps": self.tempo_taps,
            "arpeggiator": self.arpeggiator,
        }


# --------------------------------------------------------------------------
# 'Akai MPK mini mk3' device controller class
# --------------------------------------------------------------------------
class zynthian_ctrldev_akai_mpk_mini_mk3(zynthian_ctrldev_zynmixer):

    dev_ids = ["MPK mini 3 IN 1"]
    unroute_from_chains = False

    @classmethod
    def get_autoload_flag(cls):
        return False

    def __init__(self, state_manager, idev_in, idev_out):
        self._saved_state = SavedState(state_manager.zynseq)
        self._mixer_handler = MixerHandler(state_manager, idev_out, self._saved_state)
        self._device_handler = DeviceHandler(state_manager, idev_out, self._saved_state)
        self._pattern_handler = PatternHandler(state_manager, idev_out, self._saved_state)
        self._notepad_handler = NotePadHandler(state_manager, idev_out, self._saved_state)
        self._user_handler = UserHandler(state_manager, idev_out, self._saved_state)
        self._config_handler = ConfigHandler(state_manager, idev_out, self._saved_state)
        self._current_handler = self._mixer_handler
        self._current_screen = None
        self._saved_mpk_program = None

        self._signals = [
            (zynsigman.S_GUI,
                zynsigman.SS_GUI_SHOW_SCREEN,
                self._on_gui_show_screen),

            # FIXME: add a signal for tempo change, and then update device!
        ]
        super().__init__(state_manager, idev_in, idev_out)

    def init(self):
        super().init()
        for signal, subsignal, callback in self._signals:
            zynsigman.register(signal, subsignal, callback)
        self._save_mpk_program()

    def end(self):
        for signal, subsignal, callback in self._signals:
            zynsigman.unregister(signal, subsignal, callback)
        self._restore_mpk_program()
        super().end()

    def get_state(self):
        return self._saved_state.save()

    def set_state(self, state):
        self._saved_state.load(state)

        # Change to active handler only if MPK program is saved
        if self._saved_mpk_program is not None:
            self._current_handler.set_active(True)

    def midi_event(self, ev: bytes):
        evtype = (ev[0] >> 4) & 0x0F

        if evtype == CONST.MIDI_PC:
            program = ev[1] & 0x7F
            if program == PROG_MIXER_MODE:
                self._change_handler(self._mixer_handler)
            elif program == PROG_DEVICE_MODE:
                self._change_handler(self._device_handler)
            elif program == PROG_PATTERN_MODE:
                self._change_handler(self._pattern_handler)
            elif program == PROG_NOTEPAD_MODE:
                self._change_handler(self._notepad_handler)
            elif program == PROG_USER_MODE:
                self._change_handler(self._user_handler)
            elif program == PROG_CONFIG_MODE:
                self._change_handler(self._config_handler)
            elif program == PROG_OPEN_MIXER:
                self.state_manager.send_cuia(
                    "SCREEN_ALSA_MIXER" if self._current_screen == "audio_mixer" else
                    "SCREEN_AUDIO_MIXER"
                )
            elif program == PROG_OPEN_ZYNPAD:
                self.state_manager.send_cuia({
                    "zynpad": "SCREEN_ARRANGER",
                    "arranger": "SCREEN_PATTERN_EDITOR"
                }.get(self._current_screen, "SCREEN_ZYNPAD"))
            elif program == PROG_OPEN_TEMPO:
                self.state_manager.send_cuia("TEMPO")
            elif program == PROG_OPEN_SNAPSHOT:
                self.state_manager.send_cuia(
                    "SCREEN_SNAPSHOT" if self._current_screen == "zs3" else
                    "SCREEN_ZS3"
                )
            else:
                self._current_handler.pg_change(program)

        elif evtype == CONST.MIDI_NOTE_ON:
            note = ev[1] & 0x7F
            velocity = ev[2] & 0x7F
            channel = ev[0] & 0x0F
            self._current_handler.note_on(note, channel, velocity)

        elif evtype == CONST.MIDI_NOTE_OFF:
            note = ev[1] & 0x7F
            channel = ev[0] & 0x0F
            self._current_handler.note_off(note, channel)

        elif evtype == CONST.MIDI_CC:
            ccnum = ev[1] & 0x7F
            ccval = ev[2] & 0x7F
            self._current_handler.cc_change(ccnum, ccval)

        elif ev[0] == CONST.MIDI_SYSEX:
            if len(ev) == 254 and self._saved_mpk_program is None:
                self._saved_mpk_program = ev[1:-1]

                # Now, we can change the device program
                self._current_handler.set_active(True)
                return

            self._current_handler.sysex_message(ev[1:-1])

    def refresh(self):
        pass

    def update_mixer_strip(self, chan, symbol, value):
        pass

    def update_mixer_active_chain(self, active_chain):
        pass

    def _change_handler(self, new_handler):
        if new_handler == self._current_handler:
            return
        self._current_handler.set_active(False)
        self._current_handler = new_handler
        self._current_handler.set_active(True)

    def _on_gui_show_screen(self, screen):
        self._current_screen = screen
        for handler in [self._device_handler, self._mixer_handler, self._pattern_handler]:
            handler.on_screen_change(screen)

    def _save_mpk_program(self):
        cmd = SysExQueryProgram(program=0)
        query = bytes.fromhex("F0 {} F7".format(cmd))
        lib_zyncore.dev_send_midi_event(self.idev_out, query, len(query))

    def _restore_mpk_program(self):
        if self._saved_mpk_program is None:
            return

        query = [0xF0]
        query.extend(list(self._saved_mpk_program))
        query[2] = MSG_DIRECTION_OUT
        query[4] = CMD_WRITE_DATA
        query.append(0xF7)
        lib_zyncore.dev_send_midi_event(self.idev_out, bytes(query), len(query))


# --------------------------------------------------------------------------
# Audio mixer and (a sort of) Zynpad handler (Mixer mode)
# --------------------------------------------------------------------------
class MixerHandler(ModeHandlerBase):

    CC_PAD_START_A           = 8
    CC_PAD_VOLUME_A          = 8
    CC_PAD_PAN_A             = 9
    CC_PAD_MUTE_A            = 10
    CC_PAD_SOLO_A            = 11
    CC_PAD_PANIC_STOP_A      = 12
    CC_PAD_AUDIO_RECORD      = 13
    CC_PAD_AUDIO_STOP        = 14
    CC_PAD_AUDIO_PLAY        = 15
    CC_PAD_END_A             = 15

    CC_PAD_START_B           = 16
    CC_PAD_VOLUME_B          = 16
    CC_PAD_PAN_B             = 17
    CC_PAD_MUTE_B            = 18
    CC_PAD_SOLO_B            = 19
    CC_PAD_PANIC_STOP_B      = 20
    CC_PAD_MIDI_RECORD       = 21
    CC_PAD_MIDI_STOP         = 22
    CC_PAD_MIDI_PLAY         = 23
    CC_PAD_END_B             = 23

    CC_KNOBS_START           = 24
    CC_KNOBS_END             = 31

    CC_JOY_X_NEG             = 32
    CC_JOY_X_POS             = 33

    def __init__(self, state_manager, idev_out, saved_state: SavedState):
        super().__init__(state_manager)
        self._idev_out = idev_out
        self._saved_state = saved_state
        self._knobs_function = FN_VOLUME
        self._pads_action = None
        self._pressed_pads = {}
        self._chains_bank = 0

    def set_active(self, active):
        super().set_active(active)
        if active:
            self._upload_mode_layout_to_device()

    def cc_change(self, ccnum, ccval):
        # Is a PAD press
        if self.CC_PAD_START_A <= ccnum <= self.CC_PAD_END_B:

            # This will happend when FULL LEVEL is on (or with a very strong press)
            if ccval == 127:
                if self._current_screen in ["audio_mixer", "zynpad"]:
                    self._pads_action = FN_SELECT
                    return self._change_chain(ccnum, ccval)

            # Single step actions
            cuia = {
                self.CC_PAD_PANIC_STOP_A: "ALL_SOUNDS_OFF",
                self.CC_PAD_PANIC_STOP_B: "ALL_SOUNDS_OFF",
                self.CC_PAD_AUDIO_RECORD: "TOGGLE_AUDIO_RECORD",
                self.CC_PAD_AUDIO_STOP: "STOP_AUDIO_PLAY",
                self.CC_PAD_AUDIO_PLAY: "TOGGLE_AUDIO_PLAY",
                self.CC_PAD_MIDI_RECORD: "TOGGLE_MIDI_RECORD",
                self.CC_PAD_MIDI_STOP: "STOP_MIDI_PLAY",
                self.CC_PAD_MIDI_PLAY: "TOGGLE_MIDI_PLAY",
            }.get(ccnum)
            if cuia is not None:
                if ccval > 0:
                    if cuia == "ALL_SOUNDS_OFF":
                        self._stop_all_sounds()
                    else:
                        self._state_manager.send_cuia(cuia)
                return

            if ccval == 0:
                if self._pads_action != None:
                    self._pads_action = None
                    return
                self._chains_bank = 0
            elif self.CC_PAD_START_B <= ccnum <= self.CC_PAD_END_B:
                self._chains_bank = 1

            if self._current_screen in ["audio_mixer", "zynpad"]:
                if ccnum in (self.CC_PAD_VOLUME_A, self.CC_PAD_VOLUME_B):
                    self._knobs_function = FN_VOLUME
                elif ccnum in (self.CC_PAD_PAN_A, self.CC_PAD_PAN_B):
                    self._knobs_function = FN_PAN
                elif ccnum in (self.CC_PAD_MUTE_A, self.CC_PAD_MUTE_B):
                    self._knobs_function = FN_MUTE
                elif ccnum in (self.CC_PAD_SOLO_A, self.CC_PAD_SOLO_B):
                    self._knobs_function = FN_SOLO

        # Is a Knob rotation
        elif self.CC_KNOBS_START <= ccnum <= self.CC_KNOBS_END:
            if self._current_screen in ["audio_mixer", "zynpad"]:
                if self._knobs_function == FN_VOLUME:
                    self._update_volume(ccnum, ccval)
                elif self._knobs_function == FN_PAN:
                    self._update_pan(ccnum, ccval)
                elif self._knobs_function == FN_MUTE:
                    self._update_mute(ccnum, ccval)
                elif self._knobs_function == FN_SOLO:
                    self._update_solo(ccnum, ccval)

    def _upload_mode_layout_to_device(self):
        cmd = SysExSetProgram(
            name="Zynthian MIXER",
            tempo=self._saved_state.tempo,
            arp=self._saved_state.arpeggiator,
            tempo_taps=self._saved_state.tempo_taps,
            aftertouch=self._saved_state.aftertouch,
            keybed_octave=self._saved_state.keybed_octave,
            channels={
                "pads": self._saved_state.pads_channel,
                "keybed": self._saved_state.keybed_channel
            },
            pads={
                "note": self._saved_state.pad_notes,
                "pc": range(16),
                "cc": range(self.CC_PAD_START_A, self.CC_PAD_END_B + 1)
            },
            knobs={
                "mode": [KNOB_MODE_REL] * 8,
                "cc": range(self.CC_KNOBS_START, self.CC_KNOBS_END + 1),
                "min": [0] * 8,
                "max": [127] * 8,
                "name": [f"Chain {i}/{i+8}" for i in range(1, 9)]
            },
            joy={
                "x-mode": JOY_MODE_DUAL,
                "x-neg-ch": self.CC_JOY_X_NEG,
                "x-pos-ch": self.CC_JOY_X_POS,
                "y-mode": JOY_MODE_PITCHBEND
            }
        )
        msg = bytes.fromhex("F0 {} F7".format(cmd))
        lib_zyncore.dev_send_midi_event(self._idev_out, msg, len(msg))

    def _change_chain(self, ccnum, ccval):
        # CCNUM is a PAD, but we expect a KNOB; offset it
        ccnum = ccnum + self.CC_KNOBS_START - self.CC_PAD_START_A
        return self._update_chain("select", ccnum, ccval)

    def _update_volume(self, ccnum, ccval):
        return self._update_chain("level", ccnum, ccval, 0, 100)

    def _update_pan(self, ccnum, ccval):
        return self._update_chain("balance", ccnum, ccval, -100, 100)

    def _update_mute(self, ccnum, ccval):
        return self._update_chain("mute", ccnum, ccval)

    def _update_solo(self, ccnum, ccval):
        return self._update_chain("solo", ccnum, ccval)

    def _update_chain(self, type, ccnum, ccval, minv=None, maxv=None):
        index = ccnum - self.CC_KNOBS_START + self._chains_bank * 8
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
        elif type == "mute":
            value = ccval < 64
            set_value = lambda c, v: self._zynmixer.set_mute(c, v, True)
        elif type == "solo":
            value = ccval < 64
            set_value = lambda c, v: self._zynmixer.set_solo(c, v, True)
        elif type == "select":
            return self._chain_manager.set_active_chain_by_id(chain.chain_id)
        else:
            return False

        # NOTE: knobs are encoders, not pots (so ccval is relative)
        if minv is not None and maxv is not None:
            value *= 100
            value += ccval if ccval < 64 else ccval - 128
            value = max(minv, min(value, maxv))
            value /= 100

        set_value(mixer_chan, value)
        return True


# --------------------------------------------------------------------------
# Handle GUI (Device mode)
# --------------------------------------------------------------------------
class DeviceHandler(ModeHandlerBase):

    CC_PAD_START         = 8
    CC_PAD_LEFT          = 8
    CC_PAD_DOWN          = 9
    CC_PAD_RIGHT         = 10
    CC_PAD_CTRL_PRESET   = 11
    CC_PAD_BACK_NO       = 12
    CC_PAD_UP            = 13
    CC_PAD_SEL_YES       = 14
    CC_PAD_OPT_ADMIN     = 15

    CC_PAD_KNOB1_BTN     = 16
    CC_PAD_KNOB2_BTN     = 17
    CC_PAD_KNOB3_BTN     = 18
    CC_PAD_KNOB4_BTN     = 19
    CC_PAD_PANIC_STOP    = 20
    CC_PAD_RECORD        = 21
    CC_PAD_STOP          = 22
    CC_PAD_PLAY          = 23
    CC_PAD_END           = 23

    PC_PAD_KNOB1_BTN     = 8
    PC_PAD_KNOB2_BTN     = 9
    PC_PAD_KNOB3_BTN     = 10
    PC_PAD_KNOB4_BTN     = 11

    CC_KNOB_START        = 24
    CC_KNOB_LAYER        = 24
    CC_KNOB_SNAPSHOT     = 25
    CC_KNOB_TEMPO        = 26
    CC_KNOB_BACK         = 28
    CC_KNOB_SELECT       = 29
    CC_KNOB_END          = 31

    CC_JOY_X_NEG         = 32
    CC_JOY_X_POS         = 33
    CC_JOY_Y_NEG         = 34
    CC_JOY_Y_POS         = 35

    def __init__(self, state_manager, idev_out, saved_state: SavedState):
        super().__init__(state_manager)
        self._idev_out = idev_out
        self._saved_state = saved_state
        self._knobs_ease = KnobSpeedControl()
        self._btn_timer = ButtonTimer(self._handle_timed_button)
        self._joystick_timer = None

    def set_active(self, active):
        super().set_active(active)
        if active:
            self._upload_mode_layout_to_device()

    def pg_change(self, program):
        zynswitch = {
            self.PC_PAD_KNOB1_BTN: 0,  # Layer
            self.PC_PAD_KNOB2_BTN: 1,  # Back
            self.PC_PAD_KNOB3_BTN: 2,  # Snapshot
            self.PC_PAD_KNOB4_BTN: 3,  # Select
        }.get(program)
        if zynswitch is not None:
            self._state_manager.send_cuia("V5_ZYNPOT_SWITCH", [zynswitch, 'S'])

    def cc_change(self, ccnum, ccval):
        if self.CC_PAD_START <= ccnum <= self.CC_PAD_END:

            # PADs that support short/bold/long push
            if ccnum in (self.CC_PAD_CTRL_PRESET, self.CC_PAD_OPT_ADMIN, self.CC_PAD_SEL_YES,
                         self.CC_PAD_KNOB1_BTN, self.CC_PAD_KNOB2_BTN, self.CC_PAD_KNOB3_BTN,
                         self.CC_PAD_KNOB4_BTN):
                self._btn_timer.is_released(ccnum) if ccval == 0 else \
                self._btn_timer.is_pressed(ccnum, time.time())

            if ccval == 0:  # Release
                return
            if ccnum == self.CC_PAD_UP:
                self._state_manager.send_cuia("ARROW_UP")
            elif ccnum == self.CC_PAD_DOWN:
                self._state_manager.send_cuia("ARROW_DOWN")
            elif ccnum == self.CC_PAD_LEFT:
                self._state_manager.send_cuia("ARROW_LEFT")
            elif ccnum == self.CC_PAD_RIGHT:
                self._state_manager.send_cuia("ARROW_RIGHT")
            elif ccnum == self.CC_PAD_BACK_NO:
                self._state_manager.send_cuia("BACK")
            elif ccnum == self.CC_PAD_PANIC_STOP:
                self._stop_all_sounds()
            elif ccnum == self.CC_PAD_RECORD:
                self._state_manager.send_cuia("TOGGLE_RECORD")
            elif ccnum == self.CC_PAD_STOP:
                self._state_manager.send_cuia("STOP")
            elif ccnum == self.CC_PAD_PLAY:
                self._state_manager.send_cuia("TOGGLE_PLAY")

        elif self.CC_JOY_X_NEG <= ccnum <= self.CC_JOY_Y_POS:
            if self._joystick_timer is None:
                self._joystick_timer = IntervalTimer()
            key, cuia = {
                self.CC_JOY_X_POS: ("+x", "ARROW_RIGHT"),
                self.CC_JOY_X_NEG: ("-x", "ARROW_LEFT"),
                self.CC_JOY_Y_POS: ("+y", "ARROW_UP"),
                self.CC_JOY_Y_NEG: ("-y", "ARROW_DOWN"),
            }.get(ccnum)
            ts = [None, 800, 300, 50][bisect([30, 100, 120], ccval)]
            if ts is None:
                self._joystick_timer.remove(key)
            else:
                if key not in self._joystick_timer:
                    self._joystick_timer.add(
                        key, ts, lambda _: self._state_manager.send_cuia(cuia))
                else:
                    self._joystick_timer.update(key, ts)

        elif ccnum == self.CC_KNOB_TEMPO:
            delta = self._knobs_ease.feed(ccnum, ccval)
            if delta is None:
                return
            self._show_screen_briefly(screen="tempo", cuia="TEMPO", timeout=1500)
            tempo = self._zynseq.get_tempo() + delta * 0.1
            self._zynseq.set_tempo(tempo)
            self._timer.add("update-device-tempo", 1500, lambda _:
                self._upload_mode_layout_to_device())

        else:
            delta = self._knobs_ease.feed(ccnum, ccval)
            if delta is None:
                return

            zynpot = {
                self.CC_KNOB_LAYER: 0,
                self.CC_KNOB_BACK: 1,
                self.CC_KNOB_SNAPSHOT: 2,
                self.CC_KNOB_SELECT: 3
            }.get(ccnum, None)
            if zynpot is None:
                return

            self._state_manager.send_cuia("ZYNPOT", [zynpot, delta])

    def _handle_timed_button(self, btn, press_type):
        zynswitch = {
            self.CC_PAD_KNOB1_BTN: 0,  # Layer
            self.CC_PAD_KNOB2_BTN: 1,  # Back
            self.CC_PAD_KNOB3_BTN: 2,  # Snapshot
            self.CC_PAD_KNOB4_BTN: 3,  # Select
        }.get(btn)
        if zynswitch is not None:
            state = 'B' if press_type == CONST.PT_BOLD else 'S'
            self._state_manager.send_cuia("V5_ZYNPOT_SWITCH", [zynswitch, state])
            return

        cuia = None
        if press_type == CONST.PT_SHORT:
            if btn == self.CC_PAD_CTRL_PRESET:
                cuia = ("PRESET" if self._current_screen == "control"
                    else "SCREEN_BANK" if self._current_screen == "preset"
                    else "SCREEN_CONTROL")
            elif btn == self.CC_PAD_OPT_ADMIN:
                cuia = "SCREEN_ADMIN" if self._current_screen == "main_menu" else "MENU"
            elif btn == self.CC_PAD_SEL_YES:
                self._state_manager.send_cuia("V5_ZYNPOT_SWITCH", [3, 'S'])

        elif press_type == CONST.PT_BOLD:
            if btn == self.CC_PAD_CTRL_PRESET:
                cuia = "SCREEN_PATTERN_EDITOR"
            elif btn == self.CC_PAD_SEL_YES:
                self._state_manager.send_cuia("V5_ZYNPOT_SWITCH", [3, 'B'])

        elif press_type == CONST.PT_LONG:
            cuia = {
                self.CC_PAD_OPT_ADMIN:   "POWER_OFF",
                self.CC_PAD_CTRL_PRESET: "PRESET_FAV",
            }.get(btn)

        if cuia:
            self._state_manager.send_cuia(cuia)

    def _upload_mode_layout_to_device(self):
        cmd = SysExSetProgram(
            name="Zynthian DEVICE",
            tempo=self._saved_state.tempo,
            arp=self._saved_state.arpeggiator,
            tempo_taps=self._saved_state.tempo_taps,
            aftertouch=self._saved_state.aftertouch,
            keybed_octave=self._saved_state.keybed_octave,
            channels={
                "pads": self._saved_state.pads_channel,
                "keybed": self._saved_state.keybed_channel
            },
            pads={
                "note": self._saved_state.pad_notes,
                "pc": range(16),
                "cc": range(self.CC_PAD_START, self.CC_PAD_END + 1)
            },
            knobs={
                "mode": [KNOB_MODE_REL] * 3 + [KNOB_MODE_ABS, KNOB_MODE_REL,
                    KNOB_MODE_REL, KNOB_MODE_ABS, KNOB_MODE_ABS],
                "cc": range(self.CC_KNOB_START, self.CC_KNOB_END + 1),
                "min": [0] * 8,
                "max": [127] * 8,
                "name": [
                    "Knob#1", "Knob#3", "Tempo", "K4",
                    "Knob#2", "Knob#4", "K7", "K8"
                ]
            },
            joy={
                "x-mode": JOY_MODE_DUAL,
                "x-neg-ch": self.CC_JOY_X_NEG,
                "x-pos-ch": self.CC_JOY_X_POS,
                "y-mode": JOY_MODE_DUAL,
                "y-neg-ch": self.CC_JOY_Y_NEG,
                "y-pos-ch": self.CC_JOY_Y_POS
            }
        )
        msg = bytes.fromhex("F0 {} F7".format(cmd))
        lib_zyncore.dev_send_midi_event(self._idev_out, msg, len(msg))


# --------------------------------------------------------------------------
# Handle pattern editor (Pattern mode)
# --------------------------------------------------------------------------
class PatternHandler(ModeHandlerBase):

    CC_KNOB_START             = 24
    CC_KNOB_MOVE_V            = 25  # K2
    CC_KNOB_STUTTER_COUNT     = 26  # K3
    CC_KNOB_STUTTER_DURATION  = 27  # K4
    CC_KNOB_MOVE_H            = 29  # K6
    CC_KNOB_DURATION          = 30  # K7
    CC_KNOB_VELOCITY          = 31  # K8
    CC_KNOB_END               = 31

    CC_PAD_START              = 8
    CC_PAD_PREV_PATTERN_A     = 9   # PAD 1 A
    CC_PAD_NEXT_PATTERN_A     = 13  # PAD 2 A
    CC_PAD_SHIFT_A            = 17  # PAD 3 A
    CC_PAD_ACTION_A           = 21  # PAD 4 A
    CC_PAD_PANIC_STOP_A       = 8   # PAD 5 A
    CC_PAD_RECORD_A           = 12  # PAD 6 A
    CC_PAD_STOP_A             = 16  # PAD 7 A
    CC_PAD_PLAY_A             = 20  # PAD 8 A
    CC_PAD_PREV_PATTERN_B     = 11  # PAD 1 B
    CC_PAD_NEXT_PATTERN_B     = 15  # PAD 2 B
    CC_PAD_SHIFT_B            = 19  # PAD 3 B
    CC_PAD_ACTION_B           = 23  # PAD 4 B
    CC_PAD_PANIC_STOP_B       = 10  # PAD 5 B
    CC_PAD_RECORD_B           = 14  # PAD 6 B
    CC_PAD_STOP_B             = 18  # PAD 7 B
    CC_PAD_PLAY_B             = 22  # PAD 8 B
    CC_PAD_END                = 23

    CC_JOY_X_NEG              = 32
    CC_JOY_X_POS              = 33
    CC_JOY_Y_NEG              = 34
    CC_JOY_Y_POS              = 35

    def __init__(self, state_manager, idev_out, saved_state: SavedState):
        super().__init__(state_manager)
        self._libseq = self._zynseq.libseq
        self._idev_out = idev_out
        self._saved_state = saved_state
        self._knobs_ease = KnobSpeedControl(steps_normal=5)
        self._joystick_timer = None

    def set_active(self, active):
        super().set_active(active)
        if active:
            self._upload_mode_layout_to_device()

    def cc_change(self, ccnum, ccval):
        if self._current_screen not in ("zynpad", "arranger", "pattern_editor"):
            return

        # If 'FULL-LEVEL' is active (ccval=127), then use PADs to launch sequences
        if self.CC_PAD_START <= ccnum <= self.CC_PAD_END:
            if ccval == 127 and self._current_screen == "zynpad":
                pad = ccnum - self.CC_PAD_START
                seq = self._zynseq.get_pad_from_xy(pad // 4, pad % 4)
                self._libseq.togglePlayState(self._zynseq.bank, seq)
                return

        if ccnum in (self.CC_PAD_SHIFT_A, self.CC_PAD_SHIFT_B):
            self.on_shift_changed(ccval > 0)
        elif ccnum in (self.CC_PAD_PANIC_STOP_A, self.CC_PAD_PANIC_STOP_B):
            if ccval > 0:
                self._stop_all_sounds()
        elif ccnum == self.CC_KNOB_MOVE_H:
            delta = self._knobs_ease.feed(ccnum, ccval)
            if delta is not None:
                dir = "RIGHT" if delta >= 1 else "LEFT"
                self._state_manager.send_cuia(f"ARROW_{dir}")
        elif ccnum == self.CC_KNOB_MOVE_V:
            delta = self._knobs_ease.feed(ccnum, ccval)
            if delta is not None:
                dir = "DOWN" if delta >= 1 else "UP"
                self._state_manager.send_cuia(f"ARROW_{dir}")
        elif ccnum in (self.CC_PAD_ACTION_A, self.CC_PAD_ACTION_B):
            if ccval > 0:
                self._state_manager.send_cuia("V5_ZYNPOT_SWITCH", [3, 'S'])

        elif self.CC_JOY_X_NEG <= ccnum <= self.CC_JOY_Y_POS:
            if self._joystick_timer is None:
                self._joystick_timer = IntervalTimer()
            key, cuia = {
                self.CC_JOY_X_POS: ("+x", "ARROW_RIGHT"),
                self.CC_JOY_X_NEG: ("-x", "ARROW_LEFT"),
                self.CC_JOY_Y_POS: ("+y", "ARROW_UP"),
                self.CC_JOY_Y_NEG: ("-y", "ARROW_DOWN"),
            }.get(ccnum)
            ts = [None, 800, 300, 50][bisect([30, 100, 120], ccval)]
            if ts is None:
                self._joystick_timer.remove(key)
            else:
                if key not in self._joystick_timer:
                    self._joystick_timer.add(
                        key, ts, lambda _: self._state_manager.send_cuia(cuia))
                else:
                    self._joystick_timer.update(key, ts)

        if self._current_screen != "pattern_editor":
            return
        elif ccnum == self.CC_KNOB_DURATION:
            self._change_step_duration(ccnum, ccval)
        elif ccnum == self.CC_KNOB_VELOCITY:
            note, step = self._get_selected_step()
            self._libseq.setNoteVelocity(step, note, ccval)
        elif ccnum == self.CC_KNOB_STUTTER_COUNT:
            note, step = self._get_selected_step()
            self._libseq.setStutterCount(step, note, ccval)
        elif ccnum == self.CC_KNOB_STUTTER_DURATION:
            note, step = self._get_selected_step()
            self._libseq.setStutterDur(step, note, ccval)

        elif ccval > 0:
            if ccnum in (self.CC_PAD_NEXT_PATTERN_A, self.CC_PAD_NEXT_PATTERN_B):
                self._change_to_next_pattern()
            elif ccnum in (self.CC_PAD_PREV_PATTERN_A, self.CC_PAD_PREV_PATTERN_B):
                self._change_to_previous_pattern()
            elif ccnum in (self.CC_PAD_RECORD_A, self.CC_PAD_RECORD_B):
                self._state_manager.send_cuia("TOGGLE_RECORD")
            elif ccnum in (self.CC_PAD_STOP_A, self.CC_PAD_STOP_B):
                self._state_manager.send_cuia("STOP")
            elif ccnum in (self.CC_PAD_PLAY_A, self.CC_PAD_PLAY_B):
                self._state_manager.send_cuia("TOGGLE_PLAY")

    def _change_to_next_pattern(self):
        # FIXME: what if this track has the same pattern twice? It will go back!
        seq = self._get_selected_sequence()
        patterns: list = self._get_sequence_patterns(self._zynseq.bank, seq)
        current = self._libseq.getPatternIndex()
        try:
            pos = patterns.index(current)
            if pos == len(patterns) - 1:
                if not self._is_shifted:
                    return
                pattern = self._libseq.createPattern()
                self._add_pattern_to_end_of_track(self._zynseq.bank, seq, 0, pattern)
                patterns.append(pattern)
            self._libseq.selectPattern(patterns[pos + 1])
            self._refresh_pattern_editor()
        except ValueError:
            pass

    def _change_to_previous_pattern(self):
        # FIXME: what if this track has the same pattern twice? It will go back!
        seq = self._get_selected_sequence()
        patterns: list = self._get_sequence_patterns(self._zynseq.bank, seq)
        current = self._libseq.getPatternIndex()
        try:
            pos = patterns.index(current)
            if pos > 0:
                self._libseq.selectPattern(patterns[pos - 1])
                self._refresh_pattern_editor()
        except ValueError:
            pass

    def _change_step_duration(self, ccnum, ccval):
        if self._knobs_ease.feed(ccnum, ccval) is None:
            return
        note, step = self._get_selected_step()
        duration = self._libseq.getNoteDuration(step, note)
        if not duration:
            return

        # When shifted, move to the nearest half point
        if self._is_shifted:
            duration -= duration % 0.5
        inc = 0.5 if self._is_shifted else 0.1
        delta = inc if ccval == 1 else -inc
        duration = max(0.1, round(duration + delta, 1))
        self._set_note_duration(step, note, duration)

    def _upload_mode_layout_to_device(self):
        cmd = SysExSetProgram(
            name="Zynthian PATTERN",
            tempo=self._saved_state.tempo,
            arp=self._saved_state.arpeggiator,
            tempo_taps=self._saved_state.tempo_taps,
            aftertouch=self._saved_state.aftertouch,
            keybed_octave=self._saved_state.keybed_octave,
            channels={
                "pads":  self._saved_state.pads_channel,
                "keybed": self._saved_state.keybed_channel
            },
            pads={
                "note": self._saved_state.pad_notes,
                "pc": range(16),
                # "cc": range(self.CC_PAD_START, self.CC_PAD_END + 1),
                # "cc": [1, 5, 9, 13, 0, 4, 8, 12, 3, 7, 11, 15, 2, 6, 10, 14],
                # This order is the same as pads in Zynpad
                "cc": [9, 13, 17, 21, 8, 12, 16, 20, 11, 15, 19, 23, 10, 14, 18, 22]
            },
            knobs={
                "mode": [
                    KNOB_MODE_ABS, KNOB_MODE_REL, KNOB_MODE_ABS, KNOB_MODE_ABS,
                    KNOB_MODE_ABS, KNOB_MODE_REL, KNOB_MODE_REL, KNOB_MODE_ABS
                ],
                "cc": range(self.CC_KNOB_START, self.CC_KNOB_END + 1),
                "min": [0, 0, 0, 1, 0, 0, 0, 0],
                "max": [1, 1, 32, 96, 1, 1, 1, 127],
                "name": [
                    "K1", "Cursor V", "Stutter Count", "Stutter Duration",
                    "k5", "Cursor H", "Duration", "Velocity"
                ],
            },
            joy={
                "x-mode": JOY_MODE_DUAL,
                "x-neg-ch": self.CC_JOY_X_NEG,
                "x-pos-ch": self.CC_JOY_X_POS,
                "y-mode": JOY_MODE_DUAL,
                "y-neg-ch": self.CC_JOY_Y_NEG,
                "y-pos-ch": self.CC_JOY_Y_POS
            }
        )
        msg = bytes.fromhex("F0 {} F7".format(cmd))
        lib_zyncore.dev_send_midi_event(self._idev_out, msg, len(msg))


# --------------------------------------------------------------------------
# Handle an editor of note pads (NotePad mode)
# --------------------------------------------------------------------------
class NotePadHandler(ModeHandlerBase):

    CC_PAD_START             = 8
    CC_PAD_END               = 23

    CC_KNOB_START            = 24
    CC_KNOB_ADJUST_NOTE      = 30
    CC_KNOB_REMOVE_NOTE      = 31
    CC_KNOB_END              = 31

    CC_JOY_X_NEG             = 32
    CC_JOY_X_POS             = 33
    CC_JOY_Y_NEG             = 34
    CC_JOY_Y_POS             = 35

    def __init__(self, state_manager, idev_out, saved_state: SavedState):
        super().__init__(state_manager)
        self._libseq = self._zynseq.libseq
        self._saved_state = saved_state
        if saved_state.is_empty:
            saved_state.pads_channel = DEFAULT_PADS_CH
            saved_state.keybed_channel = DEFAULT_KEYBED_CH
            # Note: do not create a zero list, as this index is used to know what pad is pressed
            saved_state.pad_notes = list(range(16))
            saved_state.is_empty = False

        self._idev_out = idev_out
        self._knobs_ease = KnobSpeedControl()
        self._channel_to_commit = None
        self._notes_to_add = {}
        self._notes_to_remove = set()
        self._notes_to_change = {}
        self._pressed_pads = {}

    def set_active(self, active):
        super().set_active(active)
        if active:
            self._channel_to_commit = None
            self._notes_to_add.clear()
            self._notes_to_remove.clear()
            self._upload_mode_layout_to_device()

    def note_on(self, note, channel, velocity):
        if channel == self._saved_state.pads_channel:
            try:
                pad = self._saved_state.pad_notes.index(note)
                self._pressed_pads[pad] = time.time()
            except ValueError:
                pass

        # NOTE: Keybed channel and pad channel may be the same
        if channel == self._saved_state.keybed_channel:
            if len(self._pressed_pads) == 1:
                pad = next(iter(self._pressed_pads))
                if note not in self._saved_state.pad_notes:
                    self._notes_to_add[pad] = note

    def note_off(self, note, channel):
        should_upload = False
        if channel == self._saved_state.pads_channel:
            try:
                pad = self._saved_state.pad_notes.index(note)
                self._pressed_pads.pop(pad, None)
            except ValueError:
                pass

            playing = self._notes_to_change.pop(pad, None)
            if playing:
                note_off = 0x80 | self._saved_state.pads_channel
                self._libseq.sendMidiCommand(note_off, playing, 0)
                self._saved_state.pad_notes[pad] = playing
                should_upload = True

        if len(self._pressed_pads) == 0:
            should_upload |= len(self._notes_to_add) > 0 or len(self._notes_to_remove) > 0
            while self._notes_to_add:
                pad, note = self._notes_to_add.popitem()
                self._saved_state.pad_notes[pad] = note
            while self._notes_to_remove:
                # NOTE: we can't actually remove the note, just reset to its original value
                pad = self._notes_to_remove.pop()
                self._saved_state.pad_notes[pad] = pad

        if should_upload:
            self._upload_mode_layout_to_device()

    def cc_change(self, ccnum, ccval):
        if ccnum == self.CC_KNOB_ADJUST_NOTE and len(self._pressed_pads) == 1:
            self._adjust_note_pad(ccnum, ccval, list(self._pressed_pads.keys())[0])
        elif ccnum == self.CC_KNOB_REMOVE_NOTE:
            self._toggle_mark_to_remove(ccval)

    def _adjust_note_pad(self, ccnum, ccval, pad):
        delta = self._knobs_ease.feed(ccnum, ccval)
        if delta is None:
            return

        # Get note to update
        note = self._notes_to_change.get(pad)
        if note is None:
            note = self._saved_state.pad_notes[pad]

        # Mute current note
        note_off = 0x80 | self._saved_state.pads_channel
        self._libseq.sendMidiCommand(note_off, note, 0)

        # Increase/decrease note
        note = min(127, max(16, note + (1 if ccval == 1 else -1)))
        self._notes_to_change[pad] = note
        # FIXME: check if note is repeated, and do not update it (or remove the older
        # when commited)

        # Play new note
        note_on = 0x90 | self._saved_state.pads_channel
        self._libseq.sendMidiCommand(note_on, note, 64)

    def _toggle_mark_to_remove(self, ccval):
        note_off = 0x80 | self._saved_state.pads_channel
        note_on = 0x90 | self._saved_state.pads_channel

        # CCW rotation: set notes to be removed
        if ccval == 127:
            for pad in self._pressed_pads:
                if pad in self._notes_to_remove:
                    continue
                self._notes_to_remove.add(pad)
                self._libseq.sendMidiCommand(note_off, self._saved_state.pad_notes[pad], 0)

        # CW rotation, undo not-commited changes
        elif ccval == 1:
            for pad in self._pressed_pads:
                if pad in self._notes_to_remove:
                    self._notes_to_remove.discard(pad)
                    self._libseq.sendMidiCommand(note_on, self._saved_state.pad_notes[pad], 64)

    def _upload_mode_layout_to_device(self):
        cmd = SysExSetProgram(
            name="Zynthian NOTEPAD",
            tempo=self._saved_state.tempo,
            arp=self._saved_state.arpeggiator,
            tempo_taps=self._saved_state.tempo_taps,
            aftertouch=self._saved_state.aftertouch,
            keybed_octave=self._saved_state.keybed_octave,
            channels={
                "pads": self._saved_state.pads_channel,
                "keybed": self._saved_state.keybed_channel
            },
            pads={
                "note": self._saved_state.pad_notes,
                "pc": range(16),
                "cc": range(self.CC_PAD_START, self.CC_PAD_END + 1)
            },
            knobs={
                "mode": [KNOB_MODE_ABS] + [KNOB_MODE_REL] * 7,
                "cc": range(self.CC_KNOB_START, self.CC_KNOB_END + 1),
                "min": [1] + [0] * 7,
                "max": [16] + [127] * 7,
                "name": [f"K{i}" for i in range(1, 7)] + ["Adjust Note", "Remove Note"]
            },
            joy={
                "x-mode": JOY_MODE_DUAL,
                "x-neg-ch": self.CC_JOY_X_NEG,
                "x-pos-ch": self.CC_JOY_X_POS,
                "y-mode": JOY_MODE_DUAL,
                "y-neg-ch": self.CC_JOY_Y_NEG,
                "y-pos-ch": self.CC_JOY_Y_POS,
            }
        )
        msg = bytes.fromhex("F0 {} F7".format(cmd))
        lib_zyncore.dev_send_midi_event(self._idev_out, msg, len(msg))


# --------------------------------------------------------------------------
# Empty handler to allow the use of PADs/KNOBs for MIDI learn (User mode)
# --------------------------------------------------------------------------
class UserHandler(ModeHandlerBase):

    CC_JOY_X_NEG = 64
    CC_JOY_X_POS = 65

    def __init__(self, state_manager, idev_out, saved_state: SavedState):
        super().__init__(state_manager)
        self._idev_out = idev_out
        self._saved_state = saved_state

    def set_active(self, active):
        super().set_active(active)
        if active:
            self._upload_mode_layout_to_device()

    def _upload_mode_layout_to_device(self):
        cmd = SysExSetProgram(
            name="Zynthian USER",
            tempo=self._saved_state.tempo,
            arp=self._saved_state.arpeggiator,
            tempo_taps=self._saved_state.tempo_taps,
            aftertouch=self._saved_state.aftertouch,
            keybed_octave=self._saved_state.keybed_octave,
            channels={
                "pads": self._saved_state.pads_channel,
                "keybed": self._saved_state.keybed_channel
            },
            pads={
                "note": self._saved_state.pad_notes,
                "pc": range(16),
                "cc": range(40, 56)
            },
            knobs={
                "mode": [KNOB_MODE_ABS] * 8,
                "cc": range(56, 64),
                "min": [0] * 8,
                "max": [127] * 8,
                "name": [f"K{i}" for i in range(1, 9)]
            },
            joy={
                "x-mode": JOY_MODE_DUAL,
                "x-neg-ch": self.CC_JOY_X_NEG,
                "x-pos-ch": self.CC_JOY_X_POS,
                "y-mode": JOY_MODE_PITCHBEND
            }
        )
        msg = bytes.fromhex("F0 {} F7".format(cmd))
        lib_zyncore.dev_send_midi_event(self._idev_out, msg, len(msg))


# --------------------------------------------------------------------------
# Config handler to allow the user change MPK settings and store them in the snapshot, and
# not loose them in evert mode change. (Config mode)
# --------------------------------------------------------------------------
class ConfigHandler(ModeHandlerBase):

    CC_PAD_START             = 8
    CC_PAD_SHIFT             = 10
    CC_PAD_ARP_TOGGLE        = 11
    CC_PAD_END               = 23

    CC_KNOB_START            = 24
    CC_KNOB_TEMPO_TAPS       = 24
    CC_KNOB_SWING            = 25
    CC_KNOB_AFTERTOUCH       = 26
    CC_KNOB_KEYBED_OCTAVE    = 27
    CC_KNOB_EXT_CLOCK        = 29
    CC_KNOB_PAD_CHANNEL      = 30
    CC_KNOB_KEYBED_CHANNEL   = 31
    CC_KNOB_END              = 31

    NOTE_ARP_DIV_START       = 48
    NOTE_ARP_DIV_END         = 55
    NOTE_ARP_MODE_START      = 56
    NOTE_ARP_MODE_END        = 61
    NOTE_ARP_LATCH_TOGGLE    = 62
    NOTE_ARP_OCTAVE_START    = 63
    NOTE_ARP_OCTAVE_END      = 66
    NOTE_ARP_SWING_START     = 67
    NOTE_ARP_SWING_END       = 72

    def __init__(self, state_manager, idev_out, saved_state: SavedState):
        super().__init__(state_manager)
        self._idev_out = idev_out
        self._libseq = self._zynseq.libseq
        self._saved_state = saved_state
        self._changes_to_commit = {}
        self._pressed_pads = {}

    def set_active(self, active):
        super().set_active(active)
        if active:
            self._upload_mode_layout_to_device()

    def note_on(self, note, channel, velocity):
        if self.NOTE_ARP_DIV_START <= note <= self.NOTE_ARP_DIV_END:
            step = note - self.NOTE_ARP_DIV_START
            self._saved_state.arpeggiator["division"] = ARP_DIV_1_4 + step
        elif self.NOTE_ARP_MODE_START <= note <= self.NOTE_ARP_MODE_END:
            step = note - self.NOTE_ARP_MODE_START
            self._saved_state.arpeggiator["mode"] = ARP_MODE_UP + step
        elif note == self.NOTE_ARP_LATCH_TOGGLE:
            self._saved_state.arpeggiator["latch"] ^= True
        elif self.NOTE_ARP_OCTAVE_START <= note <= self.NOTE_ARP_OCTAVE_END:
            step = note - self.NOTE_ARP_OCTAVE_START
            self._saved_state.arpeggiator["octave"] = ARP_OCTAVE_MIN + step
        elif self.NOTE_ARP_SWING_START <= note <= self.NOTE_ARP_SWING_END:
            step = {
                self.NOTE_ARP_SWING_START: 0,
                self.NOTE_ARP_SWING_START + 1: 5,
                self.NOTE_ARP_SWING_START + 2: 7,
                self.NOTE_ARP_SWING_START + 3: 9,
                self.NOTE_ARP_SWING_START + 4: 11,
                self.NOTE_ARP_SWING_START + 5: 14,
            }[note]
            self._saved_state.arpeggiator["swing"] = ARP_SWING_MIN + step
        else:
            return False
        note_off = 0x80 | self._saved_state.keybed_channel
        self._libseq.sendMidiCommand(note_off, note, 0)
        self._upload_mode_layout_to_device()

    def cc_change(self, ccnum, ccval):
        # SHIFT NoteOn & NoteOff events
        if ccnum == self.CC_PAD_SHIFT:
            if ccval > 0:
                self._pressed_pads[ccnum] = time.time()
            else:
                for target, value in self._changes_to_commit.items():
                    if target.startswith("arp."):
                        target = target.split(".")[1]
                        self._saved_state.arpeggiator[target] = value
                    else:
                        setattr(self._saved_state, target, value)
                if self._changes_to_commit:
                    self._changes_to_commit.clear()
                    self._upload_mode_layout_to_device()
                self._pressed_pads.pop(ccnum, None)

        # ARP toggle
        elif ccnum == self.CC_PAD_ARP_TOGGLE:
            if ccval > 0:
                self._saved_state.arpeggiator["on"] ^= True
                self._upload_mode_layout_to_device()

        # SHIFTed functions
        if self.CC_PAD_SHIFT in self._pressed_pads:
            target, convert_value = {
                self.CC_KNOB_TEMPO_TAPS:     ("tempo_taps",     lambda v: v),
                self.CC_KNOB_SWING:          ("arp.swing",      lambda v: 50 - v),
                self.CC_KNOB_AFTERTOUCH:     ("aftertouch",     lambda v: v),
                self.CC_KNOB_KEYBED_OCTAVE:  ("keybed_octave",  lambda v: v),
                self.CC_KNOB_EXT_CLOCK:      ("arp.ext_clock",  lambda v: v),
                self.CC_KNOB_PAD_CHANNEL:    ("pads_channel",   lambda v: v - 1),
                self.CC_KNOB_KEYBED_CHANNEL: ("keybed_channel", lambda v: v - 1),
            }.get(ccnum, (None, None))
            if target is not None:
                self._changes_to_commit[target] = convert_value(ccval)

    def _upload_mode_layout_to_device(self):
        cmd = SysExSetProgram(
            name="Zynthian CONFIG",
            tempo=self._saved_state.tempo,
            arp=self._saved_state.arpeggiator,
            tempo_taps=self._saved_state.tempo_taps,
            aftertouch=self._saved_state.aftertouch,
            keybed_octave=self._saved_state.keybed_octave,
            channels={
                "pads": self._saved_state.pads_channel,
                "keybed": self._saved_state.keybed_channel
            },
            pads={
                "note": self._saved_state.pad_notes,
                "pc": range(16),
                "cc": range(self.CC_PAD_START, self.CC_PAD_END + 1)
            },
            knobs={
                "cc": range(self.CC_KNOB_START, self.CC_KNOB_END + 1),
                "mode": [
                    KNOB_MODE_ABS, KNOB_MODE_ABS, KNOB_MODE_ABS, KNOB_MODE_ABS,
                    KNOB_MODE_REL, KNOB_MODE_ABS, KNOB_MODE_ABS, KNOB_MODE_ABS
                ],
                "min": [
                    TEMPO_TAPS_MIN, 50 + ARP_SWING_MIN, AFTERTOUCH_OFF, KEY_OCTAVE_MIN,
                    0, 0, 1, 1
                ],
                "max": [
                    TEMPO_TAPS_MAX, 50 + ARP_SWING_MAX, AFTERTOUCH_POLYPHONIC, KEY_OCTAVE_MAX,
                    1, 1, 16, 16
                ],
                "name": [
                    "Tempo Taps", "Swing", "Aftertouch", "KeyBed Octave",
                    "K5", "Ext Clock", "PADs Channel", "KeyBed Channel"
                ]
            }
        )
        msg = bytes.fromhex("F0 {} F7".format(cmd))
        lib_zyncore.dev_send_midi_event(self._idev_out, msg, len(msg))
