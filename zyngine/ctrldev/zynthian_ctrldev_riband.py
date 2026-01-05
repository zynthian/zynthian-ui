#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "riband wearable controller"
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

# Zynthian specific modules
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynpad
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq

# ------------------------------------------------------------------------------
# riban wearable MIDI controller
# ------------------------------------------------------------------------------


class zynthian_ctrldev_riband(zynthian_ctrldev_zynpad):

    dev_ids = ["riband Bluetooth"]

    # Function to initialise class
    def __init__(self, state_manager, idev_in, idev_out=None):
        self.cols = 4
        self.rows = 4
        super().__init__(state_manager, idev_in, idev_out)

    def end(self):
        for note in range(16):
            lib_zyncore.dev_send_note_on(self.idev_out, 0, note, 0)
        super().end()

    def update_seq_state(self, phrase, chan, state, mode):
        if self.idev_out is None:
            return
        try:
            #TODO: FIXME - Can we use default function from parent?
            chain_id = self._chain_manager.get_chain_ids_by_midi_chan(chan)[0]
            col = self._chain_manager.get_chain_index(chain_id)
        except:
            return
        if phrase > 3 or col > 3:
            return
        note = col * 4 + phrase
        if note > 15:
            return
        try:
            if mode == 0 or chan > 15:
                vel = 0
            elif state == zynseq.SEQ_STOPPED:
                vel = 4 + chan
            elif state == zynseq.SEQ_PLAYING:
                vel = 64 + chan
            elif state in [zynseq.SEQ_STOPPING, zynseq.SEQ_STOPPING_SYNC]:
                vel = 33
            elif state == zynseq.SEQ_STARTING:
                vel = 31
            else:
                vel = 0
        except Exception as e:
            vel = 0
            # logging.warning(e)

        lib_zyncore.dev_send_note_on(self.idev_out, 0, note, vel)

    def pad_off(self, col, row):
        note = col * 4 + row
        lib_zyncore.dev_send_note_on(self.idev_out, 0, note, 0)

    def midi_event(self, ev):
        evtype = (ev[0] >> 4) & 0x0F
        if evtype == 0x9:
            note = ev[1] & 0x7F
            vel = ev[2] & 0x7F
            if vel > 0 and note < self.zynseq.seq_in_scene:
                # Toggle pad
                self.zynseq.libseq.togglePlayState(self.zynseq.bank, note)
                return True
        return False

# ------------------------------------------------------------------------------
