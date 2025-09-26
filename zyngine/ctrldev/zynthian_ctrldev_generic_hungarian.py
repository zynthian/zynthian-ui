#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for generic MIDI devices
# A simple chorder implemented with mididings.
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
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_base


# ------------------------------------------------------------------------------------------------------------------
# Generic Basic Hungarian Minor scale enforcer with mididings
# ------------------------------------------------------------------------------------------------------------------


class zynthian_ctrldev_generic_hungarian(zynthian_ctrldev_base):

    dev_ids = ["*"]
    driver_description = "Basic chorder example using mididings for RT midi processing"
    unroute_from_chains = False
    autoload_flag = False

    # The midiproc task itself. It runs in a spawned process.
    def midiproc_task(self):
        self.midiproc_task_reset_signal_handlers()

        import mididings
        from functools import partial  # needed for function params in mididings process

        #MODES = _MODES
        # scale_targets = MODES["Minor"]
        # scale_targets = MODES["Hungarian Minor"]
        scale_targets = [0, 2, 3, 6, 7, 8, 11]  # is Hungarian Minor

        mididings.config(
            backend='jack',
            client_name=self.midiproc_jackname,
            in_ports=1,
            out_ports=1,
        )

        # get parameters
        def translate_scale(ev, distance=None):
            note = ev.note
            octave = note // 12
            chroma_note = note % 12
            # Mapping: get white keys, remove black keys from piano notes
            key_map = (0, None, 1, None, 2, 3, None, 4, None, 5, None, 6)

            if chroma_note < 0 or chroma_note >= len(key_map):  # is map right initialized
                return None  # for shorter modes with less then 7 tones

            chroma_note_cleaned = key_map[chroma_note]
            if chroma_note_cleaned == None:  # is black key.
                return None  # discard event

            if not 0 <= chroma_note_cleaned < len(scale_targets):  # wrong scale_map values
                return None

            note_new = scale_targets[chroma_note_cleaned] + (octave * 12)

            ev.note = note_new  # Herueka, a new Mode note event
            return ev

        mididings.run(
            [
                # #mididings.Pass() // (mididings.Channel(2) >> (mididings.Pass() // mididings.Transpose(4) // mididings.Transpose(7)))
                # mididings.Pass() //  mididings.Transpose(4) //  mididings.Transpose(7)

                # with params
                ## mididings.Filter(mididings.PROGRAM) // # all but note events
                # mididings.Channel(5) // # all to channel 5 which will not be routed

                mididings.Filter(mididings.CTRL) >> mididings.Channel(5),  # jst CTRLS to keyboard driver

                mididings.Filter(mididings.NOTEON | mididings.NOTEOFF) >>
                mididings.Process(partial(translate_scale, distance=None)),

                ~mididings.Filter(mididings.NOTEON | mididings.NOTEOFF) >> mididings.Pass()
            ]
        )

# ------------------------------------------------------------------------------
