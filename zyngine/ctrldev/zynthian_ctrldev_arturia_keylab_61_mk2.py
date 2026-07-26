#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Arturia Keylab 61 Mk2"
#
# Copyright (C) 2026 Fernando Moyano <jofemodo@zynthian.org>
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

import logging

from zyngine import zynthian_state_manager
from zynlibs.zynseq import zynseq
from zyncoder.zyncore import lib_zyncore
from zyngine.zynthian_signal_manager import zynsigman

from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynmixer, zynthian_ctrldev_zynpad

from collections import namedtuple

Button = namedtuple("Button", ["sysex", "note", "chan"], defaults=[0, 0, 0])

# https://github.com/bitwig/bitwig-extensions/blob/953f4be03da06dcbfa7efdd42a5e2236c9a3b77e/src/main/java/com/bitwig/extensions/controllers/arturia/keylab/mk2/ButtonId.java

# Pads
PAD1 = Button(0x70, 36, 9)
# PAD2-PAD15 = Button(0x71-0x7E, 37-50, 9)
PAD16 = Button(0x7F, 51, 9)

# Pads come in on the DAW channel nine notes 36 and up
# Pad colors go out on sysex index 0x70 and up
PAD_MIDI_OFFSET = 36
PAD_SYSEX_OFFSET = 0x70

# Track controls
SOLO = Button(0x60, 0x08)
MUTE = Button(0x61, 0x10)
RECORD_ARM = Button(0x62, 0x00)
READ = Button(0x63, 0x38)
WRITE = Button(0x64, 0x39)

TRACK_SOLO = 8
TRACK_MUTE = 16
TRACK_RECORD = 0
TRACK_READ = 56
TRACK_WRITE = 57

# Global controls
SAVE = Button(0x65, 0x4A)
PUNCH_IN = Button(0x66, 0x57)
PUNCH_OUT = Button(0x67, 0x58)
METRO = Button(0x68, 0x59)
UNDO = Button(0x69, 0x51)

GLOBAL_SAVE = 74
GLOBAL_IN = Button(0x66, 0x57)
GLOBAL_OUT = Button(0x67, 0x58)
GLOBAL_METRO = Button(0x68, 0x59)
GLOBAL_UNDO = 81

# Transport controls
REWIND = Button(0x6A, 0x5B)
FORWARD = Button(0x6B, 0x5C)
STOP = Button(0x6C, 0x5D)
PLAY_OR_PAUSE = Button(0x6D, 0x5E)
RECORD = Button(0x6E, 0x5F)
LOOP = Button(0x6F, 0x56)

TRANSPORT_BACK = 91
TRANSPORT_FORWARD = 92
TRANSPORT_STOP = 93
TRANSPORT_PLAY_PAUSE = 94
TRANSPORT_RECORD = Button(0x6E, 0x5F)
TRANSPORT_LOOP = 86

# Preset controls
PRESET_PREVIOUS = Button(0x1A, 0x62)
PRESET_NEXT = Button(0x1B, 0x63)
WHEEL_CLICK = Button(0, 0x54)

# Navigation controls
NEXT = Button(0x1F, 0x31)
PREVIOUS = Button(0x20, 0x30)
BANK = Button(0x21, 0x21)

# Select controls
SELECT_1 = Button(0x22, 0x18)
SELECT_2 = Button(0x23, 0x19)
SELECT_3 = Button(0x24, 0x1A)
SELECT_4 = Button(0x25, 0x1B)
SELECT_5 = Button(0x26, 0x1C)
SELECT_6 = Button(0x27, 0x1D)
SELECT_7 = Button(0x28, 0x1E)
SELECT_8 = Button(0x29, 0x1F)
SELECT_MULTI = Button(0x2A, 0x33)
 


def pad_seq_index_inversion(pad_or_seq_index):
    """
    The pads on the arturia are row major and on the zynthian
    they are column major. This function converts between the two
    
    :param pad_or_seq_index: Description
    """
    return pad_or_seq_index % 4 * 4 + pad_or_seq_index // 4 


# --------------------------------------------------------------------------
# 'Arturia Keylab 61 Mk2' device controller class
# --------------------------------------------------------------------------
class zynthian_ctrldev_arturia_keylab_61_mk2(zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer):
    """
    The Arturia Keylab 61 Mk2 
    - has 4x4 pad area
    - pitch shift
    - 61 piano keys
    - track control, global control and transport control buttons
    - and an 8 x mixing set with 8x(1  encoder, 1 fader and 1 toggle button) + 1 master.
    
    
    Resources:
    - https://downloads.arturia.com/products/keylab-49-mkII/manual/keylab-mk2_Manual_1_0_0_EN.pdf
    - https://github.com/bitwig/bitwig-extensions/tree/953f4be03da06dcbfa7efdd42a5e2236c9a3b77e/src/main/java/com/bitwig/extensions/controllers/arturia/keylab/mk2
    - https://github.com/mhugo/sysex/blob/dc3c43de2e17565b6713414f42adb76efa71b702/README.md
    """

    dev_ids = ["KeyLab mkII 61 IN 2"]
    driver_name = 'Arturia Keylab 61 Mk2'
    driver_description = 'Full UI integration'
    # Unroute 9: pads 
    unroute_from_chains = True # 0b0000001000000000 # allow most channels. 

    # TODO: Are these colors any good?
    PAD_COLORS = [
        (127, 0, 0), (0, 127, 0), (0, 0, 127), (127, 127, 0),
        (127, 0, 127), (0, 127, 127), (127, 64, 0), (127, 0, 64),
        (0, 127, 64), (64, 127, 0), (0, 64, 127), (64, 0, 127),
        (127, 127, 127), (80, 80, 80), (40, 40, 40), (0, 0, 0)
    ]
    COLOR_PLAYING = (0, 127, 0)
    COLOR_STARTING = (127, 127, 0)
    COLOR_STOPPING = (127, 0, 0)
    COLOR_EMPTY = (0, 0, 0)



    def __init__(self, state_manager: zynthian_state_manager, idev_in, idev_out=None):
        logging.info("initializing {} with port in:{} out:{}".format(self.driver_name, idev_in, idev_out))

        # Ideally these settings could be customized by user via GUI.
        # No idea how to do that yet. 
        self.record_pressed = False
        self._chain_manager = state_manager.chain_manager
        
        # NOTE: init will call refresh(), so _current_hanlder must be ready!
        super().__init__(state_manager, idev_in, idev_out)
        self.cols = 4
        self.rows = 4

    def init(self):
        super().init()
        self._enter_daw_mode()
        zynsigman.register_queued(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_METRO, self.update_metronome)
        self._send_display_sysex("Zynthian", "Connected")

    def _enter_daw_mode(self):
        """Enters DAW mode and sets the DAW preset to Live."""
        if self.idev_out is None:
            return

        # Init DAW preset in Live mode (DAWMode.Live.getID() is 0x02)
        msg1 = bytearray.fromhex("F0 00 20 6B 7F 42 02 00 40 52 02 F7")
        lib_zyncore.dev_send_midi_event(self.idev_out, bytes(msg1), len(msg1))

        # Set to DAW mode
        msg2 = bytearray.fromhex("F0 00 20 6B 7F 42 05 02 F7")
        lib_zyncore.dev_send_midi_event(self.idev_out, bytes(msg2), len(msg2))

    def end(self):
        super().end()
        zynsigman.unregister(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_METRO, self.update_metronome)
        #zynthian_ctrldev_zynpad.end(self)

    def refresh(self):
        super().refresh()
    
    def update_metronome(self, mode, volume):
        # zero is off and 5 is silent
        self.setButtonState(GLOBAL_METRO.sysex, mode != 0 and mode != 5)

    def update_pad(self, row, col, pad_info):
        dim_ratio = 32
        if self.idev_out is None:
            return

        # Only handle first 4 rows and 4 columns (4x4 grid)
        if row >= 4 or col >= 4:
            return

        # Compute linear sequence index for pad mapping
        seq = row * 4 + col

        # Map to Arturia pad number then to led_id (0x70-0x7F)
        pad_number = seq # pad_seq_index_inversion(seq)
        led_id = 0x70 + pad_number

        if pad_info is None:
            r, g, b = self.COLOR_EMPTY
        else:
            state = pad_info.get("state")
            group = pad_info.get("group", 0)

            if state == zynseq.SEQ_STOPPED:
                r, g, b = self.PAD_COLORS[group % len(self.PAD_COLORS)]
                # dim it
                r, g, b = r // dim_ratio, g // dim_ratio, b // dim_ratio
            elif state == zynseq.SEQ_PLAYING:
                r, g, b = self.PAD_COLORS[group % len(self.PAD_COLORS)]
            elif state == zynseq.SEQ_STOPPING:
                r, g, b = self.COLOR_STOPPING
            elif state == zynseq.SEQ_STARTING:
                r, g, b = self.COLOR_STARTING
            else:
                r, g, b = self.COLOR_EMPTY

        self._send_led_sysex(led_id, r, g, b)

       
    def midi_event(self, ev):
        """ get a midi event  and do something with it. """
        self._log_midi(ev, self.idev)

        if ev == b'\xf0\x00\x20\x6b\x7f\x42\x02\x00\x00\x15\x00\xf7':
            # if we get the switch back into daw mode
            self.refresh()
            return True
        
        evtype = (ev[0] >> 4) & 0x0F
        evchan = ev[0] & 0x0F # exists even if invalid for system messages
            
        # DAW controller MIDI device
        if evtype == 0x9:
            # note on
            note = ev[1] & 0x7F
            _vel = ev[2] & 0x7F
            if note == TRANSPORT_PLAY_PAUSE:
                # play/pause button
                # todo should there be one transport toggle? Seems weird these are separate. 
                self.state_manager.send_cuia("TOGGLE_PLAY")
            if note == TRANSPORT_STOP:
                # play/pause button
                # todo should there be one transport toggle? Seems weird these are separate. 
                self.state_manager.send_cuia("STOP")
            if note == TRANSPORT_RECORD.note:
                self.record_pressed = not self.record_pressed
                self.setButtonState(TRANSPORT_RECORD.sysex, self.record_pressed)
                self.state_manager.send_cuia("TOGGLE_RECORD")
            if note == GLOBAL_METRO.note:
                self.zynseq.zctrl_metro_mode.toggle()
                self._send_display_sysex("Metronome", "mode: " + self.zynseq.zctrl_metro_mode.get_value2label())
            if note >= SELECT_1.note and note <= SELECT_8.note:
                self._chain_manager.set_active_chain_by_id(note - SELECT_1.note + 1)

        if evchan == 9 and evtype == 0x9:
            # note off
            note = ev[1] & 0x7F
            vel = ev[2] & 0x7F
            if 36 <= note <= 51 and vel > 0:
                # This is a pad press.
                # Map Arturia note to zynpad seq, then to (phrase, midi_chan)
                seq = pad_seq_index_inversion(note - PAD_MIDI_OFFSET)
                phrase = seq % 4
                midi_chan = seq // 4
                logging.info(f"Pad press: note={note}, seq={seq}, phrase={phrase}, midi_chan={midi_chan}, scene={self.zynseq.scene}")
                self.zynseq.libseq.togglePlayState(self.zynseq.scene, phrase, midi_chan)
                return True

        return True

    def update_mixer_strip(self, chan, symbol, value, mixbus=None):
        """Update hardware indicators for a mixer strip: mute, solo, level, balance, etc.
        *SHOULD* be implemented by child class

        chan - Mixer strip index
        symbol - Control name
        value - Control value
        """
        # we could probably update color based on if a chain is present/solo/mute etc
        # keylab doesn't have level/balance indicatiors
        pass


    def on_active_chain(self, active_chain_id):
        super().on_active_chain(active_chain_id)
        self.update_mixer_active_chain(active_chain_id)

    def update_mixer_active_chain(self, active_chain):
        """Update hardware indicators for active_chain
        *SHOULD* be implemented by child class

        active_chain - Active chain
        """
        chain_page = active_chain//8
        chain_index_in_page = active_chain % 8 - 1
        print(chain_index_in_page)

        for i in range(SELECT_1.sysex, SELECT_1.sysex + 8):
            self._send_led_sysex(i, 0, 0, 0)
        
        self._send_led_sysex(SELECT_1.sysex + chain_index_in_page, 127, 0, 0)


    def _log_midi(self, ev, idev):
        if not ev:
            return

        status = ev[0]
        raw_hex = " ".join("{:02X}".format(b) for b in ev)
        msg_desc = ""


        if status >= 0xF0:
            # System Messages
            if status == 0xF0: msg_desc = "SysEx"
            elif status == 0xF1: msg_desc = "MTC Quarter Frame"
            elif status == 0xF2:
                val = (ev[1] & 0x7F if len(ev) > 1 else 0) | ((ev[2] & 0x7F if len(ev) > 2 else 0) << 7)
                msg_desc = "Song Position {}".format(val)
            elif status == 0xF3:
                msg_desc = "Song Select {}".format(ev[1] & 0x7F if len(ev) > 1 else 0)
            elif status == 0xF6: msg_desc = "Tune Request"
            elif status == 0xF7: msg_desc = "EOX"
            elif status == 0xF8: msg_desc = "Clock"
            elif status == 0xFA: msg_desc = "Start"
            elif status == 0xFB: msg_desc = "Continue"
            elif status == 0xFC: msg_desc = "Stop"
            elif status == 0xFE: msg_desc = "Active Sensing"
            elif status == 0xFF: msg_desc = "Reset"
            else: msg_desc = "System Undefined"
        elif status >= 0x80:
            # Channel Messages
            cmd = status & 0xF0
            chan = (status & 0x0F) 
            d1 = ev[1] & 0x7F if len(ev) > 1 else 0
            d2 = ev[2] & 0x7F if len(ev) > 2 else 0
            
            if cmd == 0x80: msg_desc = "Note Off Ch={} Note={} Vel={}".format(chan, d1, d2)
            elif cmd == 0x90: msg_desc = "Note {} Ch={} Note={} Vel={}".format("Off" if d2 == 0 else "On", chan, d1, d2)
            elif cmd == 0xA0: msg_desc = "Poly Pressure Ch={} Note={} Val={}".format(chan, d1, d2)
            elif cmd == 0xB0: msg_desc = "CC Ch={} Ctrl={} Val={}".format(chan, d1, d2)
            elif cmd == 0xC0: msg_desc = "PC Ch={} Prog={}".format(chan, d1)
            elif cmd == 0xD0: msg_desc = "Channel Pressure Ch={} Val={}".format(chan, d1)
            elif cmd == 0xE0: msg_desc = "Pitch Bend Ch={} Val={}".format(chan, d1 | (d2 << 7))
        else:
            msg_desc = "Unknown/Data"

        # self._send_display_sysex(msg_desc, raw_hex)
        logging.info("MIDI: idev={} [{}] {}".format(idev, msg_desc, raw_hex))

    def _send_led_sysex(self, led_id, r, g, b):
        """Sends a SysEx message to the Arturia Keylab 61 Mk2 to control an LED."""
        if self.idev_out is None:
            return

        # Start of the SysEx message
        msg = bytearray.fromhex("F0 00 20 6B 7F 42 02 00 16")

        # Append LED ID and color values
        msg.append(led_id)
        msg.append(r)
        msg.append(g)
        msg.append(b)

        # End of SysEx
        msg.append(0xF7)

        lib_zyncore.dev_send_midi_event(self.idev_out, bytes(msg), len(msg))

    def _send_display_sysex(self, upper, lower):
        """Sends a SysEx message to the Arturia Keylab 61 Mk2 to display text on its screen.

        The Keylab's display has two lines. This method sets the text for both.

        Args:
            upper (str): The text to display on the upper line (max 16 chars).
            lower (str): The text to display on the lower line (max 16 chars).
        """
        if self.idev_out is None:
            return

        # Start of the SysEx message
        msg = bytearray.fromhex("F0 00 20 6B 7F 42 04 00 60 01")

        # Append upper string, padded to 16 bytes with space
        upper_bytes = upper.encode('ascii', 'ignore')
        upper_bytes = upper_bytes[:16].ljust(16, ' '.encode('ascii'))
        msg.extend(upper_bytes)

        # Append static part
        msg.extend(bytearray.fromhex("00 02"))

        # Append lower string, padded to 16 bytes with nulls
        lower_bytes = lower.encode('ascii', 'ignore')
        lower_bytes = lower_bytes[:16].ljust(16, b'\x00')
        msg.extend(lower_bytes)

        msg.extend(bytearray.fromhex("00 F7"))
        lib_zyncore.dev_send_midi_event(self.idev_out, bytes(msg), len(msg))
    
    def setButtonState(self, sysex_id, is_on):
        """Sends a SysEx message to set the state of a button LED."""
        if self.idev_out is None:
            return

        intensity = 0x7f if is_on else 0x04
        msg = bytearray.fromhex("F0 00 20 6B 7F 42 02 00 10")
        msg.append(sysex_id)
        msg.append(intensity)
        msg.append(0xF7)

        lib_zyncore.dev_send_midi_event(self.idev_out, bytes(msg), len(msg))
    
    def pad_off(self, col, row):
        seq = row * self.cols + col
        if seq < 16:
            pad_number = pad_seq_index_inversion(seq)
            led_id = PAD_SYSEX_OFFSET + pad_number
            self._send_led_sysex(led_id, 0, 0, 0)
