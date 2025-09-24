#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Fostex MixTab"
#
# Copyright (C) 2025 Fernando Moyano <jofemodo@zynthian.org>
#                    Brian Walton <brian@riban.co.uk>
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
from time import monotonic

# Zynthian specific modules
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynmixer
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq

# ------------------------------------------------------------------------------
# Fostex MixTab MIDI controller
#
# The MixTab is a hardware controller with 8 channels strips, each containing:
#   Fader (CC 16..23)
#   Mute (actually sets fader to zero)
#   Pan (CC 24..31)
#   EQ Low (CC 32..39)
#   EQ High (CC 40..47)
#   Aux 1 (CC 66..73, val 0..63)
#   Aux 2 (CC 66..73, val 64..127)
# There are also global controls:
#   Main fader (CC 7)
#   Aux 1 send (CC 74)
#   Aux 2 send (CC 75)
#   Aux 1 return (CC 76)
#   Aux 2 return (CC 77)
#   Aux 1 EQ Low (CC 78)
#   Aux 2 EQ Low (CC 79)
#   Aux 1 EQ High (CC 80)
#   Aux 2 EQ High (CC 81)
# There is a switch to select different targets which changes the MIDI channel offset used for each parameter.
# MIDI channel is set via DIP switches
# If enabled on DIP switches, request for state are sent on various conditions
#
# This driver interfaces a MixTab with the first 8 chains and main chain. Currently implemented are:
#   Fader (Mute operates fader)
#   Pan
# ------------------------------------------------------------------------------

class zynthian_ctrldev_fostex_mixtab(zynthian_ctrldev_zynmixer):

    dev_ids = ["*"]
    driver_name = "Fostex MixTab"
    driver_description = "Zynthian Mixer integration"
    autoload_flag = False

    # Function to initialise class
    def __init__(self, state_manager, idev_in, idev_out=None):
        super().__init__(state_manager, idev_in, idev_out)
        self.midi_chan = 0  # Base channel for MIDI messages. +1 for +8 offset, +2 for +16 offset.
        self.chan2chain = {}
        self.last_store = monotonic()

    def set_param(self, cc, val, midi_chan):
        if cc == 7:
            # Main fader
            self.zynmixer.set_level(255, val / 127.0, False)
        if cc < 16 or cc > 31:
            return False
        chain = self.chain_manager.get_chain_by_position(
            midi_chan * 8 + cc % 8 , midi=False)
        if chain is None or chain.mixer_chan is None or chain.mixer_chan > 15:
            return False
        match int(cc / 8):
            case 2:
                # Fader
                self.zynmixer.set_level(chain.mixer_chan, val / 127.0, False)
            case 3:
                # Pan
                self.zynmixer.set_balance(chain.mixer_chan, (val - 64) / 64, False)
        return True

    def get_param(self, cc, midi_chan):
        if cc == 7:
            # Main fader
            return int(self.zynmixer.get_level(255) * 127)
        if cc < 16 or cc > 31:
            return None
        chain = self.chain_manager.get_chain_by_position(
            midi_chan * 8 + cc % 8 , midi=False)
        if chain is None or chain.mixer_chan is None or chain.mixer_chan > 15:
            return None
        match int(cc / 8):
            case 2:
                # Fader
                return int(self.zynmixer.get_level(chain.mixer_chan) * 127)
            case 3:
                # Pan
                return int(self.zynmixer.get_balance(chain.mixer_chan) * 64) + 64
        return None

    def midi_event(self, ev):
        evtype = (ev[0] >> 4) & 0x0F
        midi_chan = ev[0] & 0xF
        if midi_chan > 1:
            return False
        if evtype == 0xb:
            cc = ev[1] & 0x7F
            val = ev[2] & 0x7F

            match cc:
                case 48:
                    # Smooth
                    self.state_manager.send_cuia("set_tempo", [40 + val * 2])
                    return True
                case 49:
                    # Dump Request parameter 0..126 or 127 for all parameters
                    if val == 127:
                        for i in range(16, 32):
                            param_val = self.get_param(i, midi_chan)
                            if param_val is not None:
                                lib_zyncore.dev_send_ccontrol_change(self.idev_out, midi_chan, i, param_val)
                    else:
                        lib_zyncore.dev_send_ccontrol_change(self.idev_out, self.midi_chan, val, self.get_param(val))
                    return True
                case 50:
                    # Scene store 0..99
                    now = monotonic()
                    if now < self.last_store + 1.5:
                        # Double press STORE but second press has to be after display stops flashing
                        self.state_manager.save_zs3(f"{self.midi_chan}/{val}", "Saved by MIXTAB")
                    self.last_store = now
                    return True
                case 51:
                    # Scene clear 0..99 or 127 for all scenes
                    #TODO: Clean all?
                    return True
                case 78:
                    # Send 1 EQ LO
                    self.state_manager.send_cuia("ZYNPOT_ABS", [1, val/127])
                    return True
                case 79:
                    # Send 2 EQ LO
                    self.state_manager.send_cuia("ZYNPOT_ABS", [3, val/127])
                    return True
                case 80:
                    # Send 1 EQ HIGH
                    self.state_manager.send_cuia("ZYNPOT_ABS", [0, val/127])
                    return True
                case 81:
                    # Send 2 EQ HIGH
                    self.state_manager.send_cuia("ZYNPOT_ABS", [2, val/127])
                    return True
            return self.set_param(cc, val, midi_chan)
        return False

    def update_mixer_strip(self, chan, symbol, value):
        return
        if chan in self.chan2chain:
            match symbol:
                case "level":
                    lib_zyncore.dev_send_ccontrol_change(self.idev_out, self.midi_chan + int(chan / 8), 16 + chan % 8 , int(value * 127))
                case "balance":
                    lib_zyncore.dev_send_ccontrol_change(self.idev_out, self.midi_chan + int(chan / 8), 24 + chan % 8 , int(value * 64 + 64))

    def refresh(self):
        self.chan2chain = {}
        for chain_id, chain in self.chain_manager.chains.items():
            if chain.mixer_chan is not None and chain.mixer_chan < 16:
                self.chan2chain[chain.mixer_chan] = chain_id

# ------------------------------------------------------------------------------
