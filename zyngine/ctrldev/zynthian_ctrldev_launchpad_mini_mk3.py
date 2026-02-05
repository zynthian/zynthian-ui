#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Novation Launchpad Mini MK3"
#
# Copyright (C) 2015-2025 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <brian@riban.co.uk>
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
from time import sleep

# Zynthian specific modules
from zynlibs.zynseq import zynseq
from zyncoder.zyncore import lib_zyncore
from zyngine.zynthian_chain_manager import MAX_NUM_MIDI_CHANS
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynpad
from zyngui import zynthian_gui_config

# ------------------------------------------------------------------------------------------------------------------
# Novation Launchpad Mini MK3
# ------------------------------------------------------------------------------------------------------------------


class zynthian_ctrldev_launchpad_mini_mk3(zynthian_ctrldev_zynpad):

    dev_ids = ["Launchpad Mini MK3 IN 1"]
    driver_description = "Launcher + arrow keys integration"

    def send_sysex(self, data):
        if self.idev_out is not None:
            msg = bytes.fromhex(f"F0 00 20 29 02 0D {data} F7")
            lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))
            sleep(0.05)

    def get_note_xy(self, note):
        row = 8 - (note // 10)
        col = (note % 10) - 1
        return col, row

    def init(self):
        # Awake
        self.sleep_off()
        # self.send_sysex_universal_inquiry()
        # Enter DAW session mode
        self.send_sysex("10 01")
        # Select session layout (session = 0x00, faders = 0x0D)
        self.send_sysex("00 00")
        super().init()

    def end(self):
        super().end()
        # Exit DAW session mode
        self.send_sysex("10 00")
        # Select Keys layout (drums = 0x04, keys = 0x05, user = 0x06, prog = 0x7F)
        self.send_sysex("00 05")

    def update_pad(self, row, col, pad_info):
        midi_chan = 0
        color = 0
        try:
            state = pad_info["state"]
            if col == self.cols:
                group = 32
            else:
                group = pad_info["group"]
            if pad_info["repeat"] == 0 or group > MAX_NUM_MIDI_CHANS:
                pass
            elif state == zynseq.SEQ_STOPPED:
                if not pad_info["empty"]:
                    color = zynthian_gui_config.LAUNCHER_COLOUR[group]["launchpad"]
            elif state in (zynseq.SEQ_PLAYING, zynseq.SEQ_CHILD_PLAYING):
                midi_chan = 2
                if col == self.cols:
                    color = zynthian_gui_config.LAUNCHER_STARTING_COLOUR["launchpad"]
                else:
                    color = zynthian_gui_config.LAUNCHER_COLOUR[group]["launchpad"]
            elif state in (zynseq.SEQ_STOPPING, zynseq.SEQ_STOPPING_SYNC, zynseq.SEQ_FORCED_STOP, zynseq.SEQ_CHILD_STOPPING):
                midi_chan = 1
                color = zynthian_gui_config.LAUNCHER_STOPPING_COLOUR["launchpad"]
            elif state == zynseq.SEQ_STARTING:
                midi_chan = 1
                color = zynthian_gui_config.LAUNCHER_STARTING_COLOUR["launchpad"]
        except:
            pass
        # Send MIDI event to controller
        if col < self.cols:
            note = 10 * (8 - row) + col + 1
            lib_zyncore.dev_send_note_on(self.idev_out, midi_chan, note, color)
        elif col == self.cols:
            ccnum = 89 - 10 * row
            lib_zyncore.dev_send_ccontrol_change(self.idev_out, midi_chan, ccnum, color)

    # Light-Off the pad specified with chan & phrase (column & row)
    def pad_off(self, col, row):
        if col < zynseq.PHRASE_CHANNEL:
            note = 10 * (8 - row) + col + 1
            lib_zyncore.dev_send_note_on(self.idev_out, 0, note, 0)
        elif col == zynseq.PHRASE_CHANNEL:
            ccnum = 89 - 10 * row
            lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, ccnum, 0)

    def midi_event(self, ev):
        # logging.debug(f"Launchpad MINI MK3 MIDI handler => {ev}")
        evtype = (ev[0] >> 4) & 0x0F
        # Note ON => launch/stop sequence
        if evtype == 0x9:
            note = ev[1] & 0x7F
            vel = ev[2] & 0x7F
            if vel > 0:
                col, row = self.get_note_xy(note)
                midi_chan = self.get_filtered_midi_chan_by_index(col)
                if midi_chan is not None:
                    phrase = row + self.scroll_v
                    try:
                        self.zynseq.libseq.togglePlayState(self.zynseq.scene, phrase, midi_chan)
                    except:
                        pass
            return True
        # CC => arrows & phrases
        elif evtype == 0xB:
            ccnum = ev[1] & 0x7F
            ccval = ev[2] & 0x7F
            if ccval > 0:
                if ccnum == 0x5B:
                    self.state_manager.send_cuia("ARROW_UP")
                elif ccnum == 0x5C:
                    self.state_manager.send_cuia("ARROW_DOWN")
                elif ccnum == 0x5D:
                    self.state_manager.send_cuia("ARROW_LEFT")
                elif ccnum == 0x5E:
                    self.state_manager.send_cuia("ARROW_RIGHT")
                else:
                    col, row = self.get_note_xy(ccnum)
                    if col == 8:
                        try:
                            phrase = row + self.scroll_v
                            self.zynseq.libseq.togglePlayState(self.zynseq.scene, phrase, zynseq.PHRASE_CHANNEL)
                        except:
                            pass
            return True
        # SysEx
        elif ev[0] == 0xF0:
            logging.info(f"Received SysEx => {ev.hex(' ')}")
            return True

    # Light-Off LEDs
    def light_off(self):
        # logging.debug("Lighting Off LEDs Launchpad MINI MK3")
        # Clean state of notes & CCs
        self.send_sysex("12 01 00 01")

    # Sleep On
    def sleep_on(self):
        # Sleep Mode (0 = sleep, 1 = awake)
        self.send_sysex("09 00")

    # Sleep On
    def sleep_off(self):
        # Sleep Mode (0 = sleep, 1 = awake)
        self.send_sysex("09 01")

# ------------------------------------------------------------------------------
