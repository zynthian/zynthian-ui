#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Novation Launchpad Mini MK1"
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

# Zynthian specific modules
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynpad
from zyngine.zynthian_signal_manager import zynsigman
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq

# ------------------------------------------------------------------------------------------------------------------
# Novation Launchpad Mini MK1
# ------------------------------------------------------------------------------------------------------------------


class zynthian_ctrldev_launchpad_mini(zynthian_ctrldev_zynpad):

    dev_ids = ["Launchpad Mini IN 1"]

    OFF_COLOUR = 0xC		 # Light Off
    PLAYING_COLOUR = 0x3C    # Solid Green
    # STOPPED_COLOUR = 0x3F   # Solid Amber
    STOPPED_COLOUR = 0x0F    # Solid Red
    # STARTING_COLOUR = 0x3A  # Blinking Yellow
    STARTING_COLOUR = 0x38   # Blinking Green
    STOPPING_COLOUR = 0x0B   # Blinking Red
    ACTIVE_COLOUR = 0x3C     # Solid Green

    def get_note_xy(self, note):
        row = note // 16
        col = note % 16
        return col, row

    def init(self):
        super().init()
        zynsigman.register_queued(
            zynsigman.S_CHAIN_MAN, self.chain_manager.SS_SET_ACTIVE_CHAIN, self.update_active_chain)
        # Configure blinking LEDs
        lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, 0, 0x28)

    def end(self):
        zynsigman.unregister(
            zynsigman.S_CHAIN_MAN, self.chain_manager.SS_SET_ACTIVE_CHAIN, self.update_active_chain)
        super().end()

    def refresh(self):
        super().refresh()
        self.update_active_chain()

    def update_active_chain(self, active_chain=None):
        if self.idev_out is None:
            return
        if active_chain is None:
            active_chain = self.chain_manager.active_chain_id
        for col in range(self.cols):
            chain_id = self.chain_manager.get_chain_id_by_index(col)
            if chain_id and chain_id == active_chain:
                light = self.ACTIVE_COLOUR
            else:
                light = self.OFF_COLOUR
            lib_zyncore.dev_send_ccontrol_change(
                self.idev_out, 0, 104 + col, light)

    def update_seq_bank(self):
        if self.idev_out is None:
            return
        # logging.debug("Updating Launchpad MINI bank leds")
        col = 8
        for row in range(self.rows):
            note = 16 * row + col
            if row == self.zynseq.bank - 1:
                lib_zyncore.dev_send_note_on(
                    self.idev_out, 0, note, self.ACTIVE_COLOUR)
            else:
                lib_zyncore.dev_send_note_on(
                    self.idev_out, 0, note, self.OFF_COLOUR)

    def update_seq_state(self, bank, seq, state, mode, group):
        if self.idev_out is None or bank != self.zynseq.bank:
            return
        # logging.debug("Updating Launchpad MINI pad {}".format(seq))
        col, row = self.zynseq.get_xy_from_pad(seq)
        note = 16 * row + col
        chan = 0
        if mode == 0:
            vel = self.OFF_COLOUR
        elif state == zynseq.SEQ_STOPPED:
            vel = self.STOPPED_COLOUR
        elif state == zynseq.SEQ_PLAYING:
            vel = self.PLAYING_COLOUR
        elif state == zynseq.SEQ_STOPPING:
            vel = self.STOPPING_COLOUR
        elif state == zynseq.SEQ_STARTING:
            vel = self.STARTING_COLOUR
        else:
            vel = self.OFF_COLOUR
        lib_zyncore.dev_send_note_on(self.idev_out, chan, note, vel)

    # Light-Off the pad specified with column & row
    def pad_off(self, col, row):
        note = 16 * row + col
        lib_zyncore.dev_send_note_on(self.idev_out, 0, note, 0xC)

    def midi_event(self, ev):
        # logging.debug("Launchpad MINI MIDI handler => {}".format(ev))
        evtype = (ev[0] >> 4) & 0x0F
        if evtype == 0x9:
            note = ev[1] & 0x7F
            col, row = self.get_note_xy(note)
            # scene change
            if col == 8:
                self.zynseq.select_bank(row + 1)
                return True
            # launch/stop pad
            pad = self.zynseq.get_pad_from_xy(col, row)
            if pad >= 0:
                self.zynseq.libseq.togglePlayState(self.zynseq.bank, pad)
                return True
        elif evtype == 0xB:
            ccnum = ev[1] & 0x7F
            ccval = ev[2] & 0x7F
            if 104 <= ccnum <= 111:
                if ccval > 0:
                    self.chain_manager.set_active_chain_by_index(ccnum-104)
                return True

    # Light-Off all LEDs
    def light_off(self):
        for row in range(self.rows):
            for col in range(self.cols + 1):
                note = 16 * row + col
                lib_zyncore.dev_send_note_on(
                    self.idev_out, 0, note, self.OFF_COLOUR)
        for col in range(self.cols):
            lib_zyncore.dev_send_ccontrol_change(
                self.idev_out, 0, 104 + col, self.OFF_COLOUR)

    def sleep_on(self):
        self.light_off()

    def sleep_off(self):
        self.refresh()

# ------------------------------------------------------------------------------
