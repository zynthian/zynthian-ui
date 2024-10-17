#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Novation Launchpad Pro MK2"
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
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

# ------------------------------------------------------------------------------------------------------------------
# Novation Launchpad Pro MK2
# ------------------------------------------------------------------------------------------------------------------


class zynthian_ctrldev_launchpad_pro_mk2(zynthian_ctrldev_zynpad):

    dev_ids = ["Launchpad Pro IN 1"]

    PAD_COLOURS = [6, 29, 17, 49, 66, 41, 23,
                   13, 96, 2, 81, 82, 83, 84, 85, 86, 87]
    STARTING_COLOUR = 21
    STOPPING_COLOUR = 5

    def send_sysex(self, data):
        if self.idev_out is not None:
            msg = bytes.fromhex("F0 00 20 29 02 10 {} F7".format(data))
            lib_zyncore.dev_send_midi_event(self.idev, msg, len(msg))
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

    # Zynpad Scene LED feedback
    def refresh_zynpad_bank(self):
        if self.idev_out is None:
            return
        # logging.debug("Updating Launchpad Pro MK2 bank leds")
        for row in range(0, 8):
            note = 89 - 10 * row
            if row == self.zynseq.bank - 1:
                lib_zyncore.dev_send_ccontrol_change(
                    self.idev_out, 0, note, 29)
            else:
                lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, note, 0)

    # Zynpad Pad LED feedback
    def update_pad(self, pad, state, mode):
        if self.idev_out is None:
            return
        # logging.debug("Updating LaunchpadPro MK2 pad {}".format(pad))
        col, row = self.zynseq.get_xy_from_pad(pad)
        note = 10 * (8 - row) + col + 1

        group = self.zynseq.libseq.getGroup(self.zynseq.bank, pad)
        try:
            if mode == 0:
                chan = 0
                vel = 0
            elif state == zynseq.SEQ_STOPPED:
                chan = 0
                vel = self.PAD_COLOURS[group]
            elif state == zynseq.SEQ_PLAYING:
                chan = 2
                vel = self.PAD_COLOURS[group]
            elif state == zynseq.SEQ_STOPPING:
                chan = 1
                vel = self.STOPPING_COLOUR
            elif state == zynseq.SEQ_STARTING:
                chan = 1
                vel = self.STARTING_COLOUR
            else:
                chan = 0
                vel = 0
        except:
            chan = 0
            vel = 0
        # logging.debug("Lighting PAD {}, group {} => {}, {}, {}".format(pad, group, chan, note, vel))
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
                pad = self.zynseq.get_pad_from_xy(col, row)
                if pad >= 0:
                    self.zynseq.libseq.togglePlayState(self.zynseq.bank, pad)
            return True
        # CC => scene change
        elif evtype == 0xB:
            ccnum = ev[1] & 0x7F
            ccval = ev[2] & 0x7F
            if ccval > 0:
                if ccnum == 91:
                    self.zyngui.cuia_arrow_up()
                elif ccnum == 92:
                    self.zyngui.cuia_arrow_down()
                elif ccnum == 93:
                    self.zyngui.cuia_arrow_left()
                elif ccnum == 94:
                    self.zyngui.cuia_arrow_right()
                else:
                    col, row = self.get_note_xy(ccnum)
                    if col == 8:
                        self.zynseq.set_bank(row + 1)
            return True

# ------------------------------------------------------------------------------
