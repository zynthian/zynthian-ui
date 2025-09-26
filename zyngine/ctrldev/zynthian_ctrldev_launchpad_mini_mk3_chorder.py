#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Novation Launchpad Mini MK3"
# A simple chorder for user mode.
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
from zyncoder.zyncore import lib_zyncore
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_base


# ------------------------------------------------------------------------------------------------------------------
# Basic Chorder for Novation Launchpad Mini MK3
# ------------------------------------------------------------------------------------------------------------------

PLAYING_COLOUR = 21


class zynthian_ctrldev_launchpad_mini_mk3_chorder(zynthian_ctrldev_base):

    dev_ids = ["Launchpad Mini MK3 IN 2"]
    driver_description = "Basic chorder example using mididings for RT midi processing"
    unroute_from_chains = False
    autoload_flag = False

    # The midiproc task itself. It runs in a spawned process.
    def midiproc_task(self):
        self.midiproc_task_reset_signal_handlers()

        import mididings

        mididings.config(
            backend='jack-rt',
            client_name=self.midiproc_jackname,
            in_ports=1,
            out_ports=1
        )
        mididings.run(
            #mididings.Pass() // (mididings.Channel(2) >> (mididings.Pass() // mididings.Transpose(4) // mididings.Transpose(7)))
            mididings.Pass() // mididings.Transpose(4) // mididings.Transpose(7)
        )

    def midi_event(self, ev):
        #logging.debug(f"Launchpad MINI MK3 MIDI handler => {ev}")
        evtype = (ev[0] >> 4) & 0x0F
        #evchan = ev[0] & 0x0F
        # Note ON
        if evtype == 0x9:
            note = ev[1] & 0x7F
            vel = ev[2] & 0x7F
            #logging.debug(f"Chan {evchan}, Note ON {note}")
            if vel > 0:
                lib_zyncore.dev_send_note_on(self.idev_out, 0, note, PLAYING_COLOUR)
            else:
                lib_zyncore.dev_send_note_on(self.idev_out, 0, note, 0)
            return True
        # Note OFF
        elif evtype == 0x8:
            note = ev[1] & 0x7F
            #logging.debug(f"Chan {evchan}, Note OFF {note}")
            lib_zyncore.dev_send_note_on(self.idev_out, 0, note, 0)
            return True

# ------------------------------------------------------------------------------
