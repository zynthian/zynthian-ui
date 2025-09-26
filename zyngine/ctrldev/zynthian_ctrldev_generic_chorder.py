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
# Generic Basic Chorder with mididings
# ------------------------------------------------------------------------------------------------------------------

class zynthian_ctrldev_generic_chorder(zynthian_ctrldev_base):

    dev_ids = ["*"]
    driver_description = "Basic chorder example using mididings for RT midi processing"
    unroute_from_chains = False
    autoload_flag = False

    # The midiproc task. It runs in a spawned process.
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
            # mididings.Pass() // (mididings.Channel(2) >> (mididings.Pass() // mididings.Transpose(4) // mididings.Transpose(7)))
            mididings.Pass() // mididings.Transpose(4) // mididings.Transpose(7) // mididings.Transpose(11)
        )

# ------------------------------------------------------------------------------
