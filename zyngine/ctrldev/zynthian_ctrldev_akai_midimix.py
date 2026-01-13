#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Akai MIDI-mix"
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
from zyncoder.zyncore import lib_zyncore
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynmixer

# --------------------------------------------------------------------------
# Akai MIDI-Mix Integration
# --------------------------------------------------------------------------


class zynthian_ctrldev_akai_midimix(zynthian_ctrldev_zynmixer):

    dev_ids = ["MIDI Mix IN 1"]
    driver_description = "Full mixer integration"

    bank_left_note = 25
    bank_right_note = 26
    solo_note = 27
    mute_notes = [1, 4, 7, 10, 13, 16, 19, 22]
    solo_notes = [2, 5, 8, 11, 14, 17, 20, 23]
    rec_notes = [3, 6, 9, 12, 15, 18, 21, 24]

    # knobs1_ccnum = [16, 20, 24, 28, 46, 50, 54, 58]
    # knobs2_ccnum = [17, 21, 25, 29, 47, 51, 55, 59]
    knobs3_ccnum = [18, 22, 26, 30, 48, 52, 56, 60]
    faders_ccnum = [19, 23, 27, 31, 49, 53, 57, 61]
    master_ccnum = 62

    # Function to initialise class
    def __init__(self, state_manager, idev_in, idev_out=None):
        self.rec_mode = 0
        self.midimix_bank = 0
        super().__init__(state_manager, idev_in, idev_out)

    # Update LED status for a single strip
    def update_mixer_strip(self, chan, symbol, value, mixbus=False):
        if self.idev_out is None or mixbus:  # Nothing to update on master strip
            return
        chain_id = self.chain_manager.get_chain_id_by_mixer_chan(chan)
        if chain_id:
            col = self.get_filtered_index_by_chain_id(chain_id) - self.scroll_h
            if 0 <= col < 8:
                if symbol == "mute":
                    lib_zyncore.dev_send_note_on(self.idev_out, 0, self.mute_notes[col], value)
                elif symbol == "solo":
                    lib_zyncore.dev_send_note_on(self.idev_out, 0, self.solo_notes[col], value)
                elif symbol == "rec" and self.rec_mode:
                    lib_zyncore.dev_send_note_on(self.idev_out, 0, self.rec_notes[col], value)

    # Update LED status for active chain
    def on_active_chain(self, active_chain_id):
        # Scroll modes are DISABLED for MIDI MIX, so no need to call the base class method
        #super().on_active_chain(active_chain_id)

        if self.rec_mode or self.idev_out is None:
            return
        for i in range(0, 8):
            chain_id = self.get_filtered_chain_id_by_index(self.scroll_h + i)
            if chain_id and chain_id == active_chain_id:
                rec = 1
            else:
                rec = 0
            lib_zyncore.dev_send_note_on(self.idev_out, 0, self.rec_notes[i], rec)

    # Update full LED status
    def refresh(self):
        super().refresh()
        if self.idev_out is None:
            return

        # Bank selection LED
        if self.midimix_bank:
            lib_zyncore.dev_send_note_on(self.idev_out, 0, self.bank_left_note, 0)
            lib_zyncore.dev_send_note_on(self.idev_out, 0, self.bank_right_note, 1)
        else:
            lib_zyncore.dev_send_note_on(self.idev_out, 0, self.bank_left_note, 1)
            lib_zyncore.dev_send_note_on(self.idev_out, 0, self.bank_right_note, 0)

        # Strips Leds
        for i in range(0, 8):
            pos = self.scroll_h + i
            chain_id = self.get_filtered_chain_id_by_index(pos)
            mute = self.get_mixer_param("mute", pos)
            solo = self.get_mixer_param("solo", pos)

            if not self.rec_mode:
                if chain_id and chain_id == self.chain_manager.get_active_chain().chain_id:
                    rec = 1
                else:
                    rec = 0
            else:
                rec = self.get_mixer_param("record", pos)

            lib_zyncore.dev_send_note_on(self.idev_out, 0, self.mute_notes[i], mute)
            lib_zyncore.dev_send_note_on(self.idev_out, 0, self.solo_notes[i], solo)
            lib_zyncore.dev_send_note_on(self.idev_out, 0, self.rec_notes[i], rec)

    def midi_event(self, ev):
        evtype = (ev[0] >> 4) & 0x0F
        if evtype == 0x9:
            note = ev[1] & 0x7F
            if note == self.solo_note:
                return True
            elif note == self.bank_left_note:
                self.midimix_bank = 0
                self.scroll_h = 0
                self.refresh()
                return True
            elif note == self.bank_right_note:
                self.midimix_bank = 1
                self.scroll_h = 8
                self.refresh()
                return True
            elif note in self.mute_notes:
                pos = self.scroll_h + self.mute_notes.index(note)
                val = self.toggle_mixer_param("mute", pos)
                # Send LED feedback
                if self.idev_out is not None:
                    lib_zyncore.dev_send_note_on(self.idev_out, 0, note, val)
                return True
            elif note in self.solo_notes:
                pos = self.scroll_h + self.solo_notes.index(note)
                val = self.toggle_mixer_param("solo", pos)
                # Send LED feedback
                if self.idev_out is not None:
                    lib_zyncore.dev_send_note_on(self.idev_out, 0, note, val)
                return True
            elif note in self.rec_notes:
                pos = self.scroll_h + self.rec_notes.index(note)
                if not self.rec_mode:
                    self.chain_manager.set_active_chain_by_index(pos)
                    self.refresh()
                else:
                    val = self.toggle_mixer_param("rec", pos)
                    # Send LED feedback
                    if self.idev_out is not None:
                        lib_zyncore.dev_send_note_on(self.idev_out, 0, note, val)
                return True
        elif evtype == 0xB:
            ccnum = ev[1] & 0x7F
            ccval = ev[2] & 0x7F
            if ccnum == self.master_ccnum:
                self.set_mixer_param("level", -1, ccval / 127.0)
                return True
            elif ccnum in self.faders_ccnum:
                pos = self.scroll_h + self.faders_ccnum.index(ccnum)
                self.set_mixer_param("level", pos, ccval / 127.0)
                return True
            elif ccnum in self.knobs3_ccnum:
                pos = self.scroll_h + self.knobs3_ccnum.index(ccnum)
                self.set_mixer_param("balance", pos, ccval/64.0 - 1.0)
                return True

    # Light-Off all LEDs
    def light_off(self):
        if self.idev_out is None:
            return
        for note in range(1, 28):
            lib_zyncore.dev_send_note_on(self.idev_out, 0, note, 0)

# ------------------------------------------------------------------------------
