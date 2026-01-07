#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Novation Launchpad Pro MK2"
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
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynpad
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq
from zyngui import zynthian_gui_config

# ------------------------------------------------------------------------------------------------------------------
# Novation Launchpad Pro MK2
# ------------------------------------------------------------------------------------------------------------------


class zynthian_ctrldev_launchpad_pro_mk2(zynthian_ctrldev_zynpad):

    dev_ids = ["Launchpad Pro IN 1"]
    driver_description = "Launcher + arrow keys integration"

    def send_sysex(self, data):
        if self.idev_out is not None:
            msg = bytes.fromhex("F0 00 20 29 02 10 {} F7".format(data))
            lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))
            sleep(0.05)

    def get_note_xy(self, note):
        row = 8 - (note // 10)
        col = (note % 10) - 1
        return col, row

    def init(self):
        # Enter Ableton mode session mode
        self.send_sysex("21 00")
        # Select session layout (layout session = 0x00, page = 0x0D)
        self.send_sysex("22 00")

    def end(self):
        # Light off
        # self.light_off()
        # Exit DAW session mode
        self.send_sysex("21 01")
        # Select Notes/Drum layout, page 0 (Chord = 0x2, Note/Drum = 0x4, Scale Settings = 0x5, ...)
        self.send_sysex("22 02")

    def update_pad(self, row, col, pad_info):
        chan = 0
        vel = 0
        note = 10 * (8 - row) + col + 1
        try:
            state = pad_info["state"]
            mode = pad_info["mode"]
            repeat = pad_info["repeat"]
            if col == self.cols:
                group = 0
            else:
                group = pad_info["group"]
            if repeat == 0 or mode == 0 or group >= MAX_NUM_MIDI_CHANS:
                pass
            elif state == zynseq.SEQ_STOPPED:
                chan = 0
                vel = zynthian_gui_config.LAUNCHER_COLOUR[group]["launchpad"]
            elif state == zynseq.SEQ_PLAYING:
                chan = 2
                vel = zynthian_gui_config.LAUNCHER_COLOUR[group]["launchpad"]
            elif state == zynseq.SEQ_STOPPING:
                chan = 1
                vel = zynthian_gui_config.LAUNCHER_STOPPING_COLOUR["launchpad"]
            elif state == zynseq.SEQ_STARTING:
                chan = 1
                vel = zynthian_gui_config.LAUNCHER_STARTING_COLOUR["launchpad"]
        except:
            pass
        lib_zyncore.dev_send_note_on(self.idev_out, chan, note, vel)

    def midi_event(self, ev):
        # logging.debug("Launchpad Pro MK2  MIDI handler => {}".format(ev))
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
                if ccnum == 91:
                    self.state_manager.send_cuia("ARROW_UP")
                elif ccnum == 92:
                    self.state_manager.send_cuia("ARROW_DOWN")
                elif ccnum == 93:
                    self.state_manager.send_cuia("ARROW_LEFT")
                elif ccnum == 94:
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

# ------------------------------------------------------------------------------
