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
from threading import Timer

# Zynthian specific modules
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynmixer
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq
from zyngine.zynthian_signal_manager import zynsigman

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
        self.strip2chan = [] # List of mixer channels, indexed by display position
        self.aux = [False] * 24 # Aux selector state for each chain
        self.feedback_timer = None

    def init(self):
        # Send the current mixer state to the mixtab allowing "enable" mode to be used
        super().init()
        # Register for processor tree changes
        zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_ADD_CHAIN, self.refresh)
        zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_REMOVE_CHAIN, self.refresh)
        zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_REMOVE_ALL_CHAINS, self.refresh)
        zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_MOVE_CHAIN, self.refresh)

    def end(self):
        # Unregister from processor tree changes
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_ADD_CHAIN, self.refresh)
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_REMOVE_CHAIN, self.refresh)
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_REMOVE_ALL_CHAINS, self.refresh)
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_MOVE_CHAIN, self.refresh)
        super().end()

    def set_param(self, cc, val, midi_chan):
        if cc == 7:
            # Main fader
            self.set_mixer_param("level", -1, val / 127)
        if cc < 16 or cc > 31:
            return False
        strip = midi_chan * 8 + cc % 8
        match int(cc / 8):
            case 2:
                # Fader
                self.set_mixer_param("level", strip, val / 127.0)
            case 3:
                # Pan
                self.set_mixer_param("balance", strip, (val / 64) - 1)
        return True

    def get_param(self, cc, midi_chan):
        if cc == 7:
            # Main fader
            return int(self.zynmixer_bus.get_level(0) * 127)
        if cc < 16 or cc > 31:
            return None
        strip = midi_chan * 8 + cc % 8
        match int(cc / 8):
            case 2:
                # Fader
                return int(self.get_mixer_param("level", strip) * 127)
            case 3:
                # Pan
                return int(self.get_mixer_param("balance", strip) * 64) + 64
        return None

    def midi_event(self, ev):
        evtype = (ev[0] >> 4) & 0x0F
        midi_chan = ev[0] & 0xF
        if midi_chan > 2:
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
                        self.refresh()
                    else:
                        lib_zyncore.dev_send_ccontrol_change(self.idev_out, self.midi_chan, val, self.get_param(val))
                    return True
                case 50:
                    # Scene store 0..99
                    self.state_manager.save_zs3(f"{self.midi_chan}/{val}", "Saved by MIXTAB")
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
            if 66 <= cc <= 73:
                # Aux
                if val < 64:
                    # Aux 1
                    val *=  2
                    self.aux[(cc - 66) + (midi_chan * 8)] = False
                else:
                    val = (val - 64) * 2
                    self.aux[(cc - 66) + (midi_chan * 8)] = True
                self.chain_manager.midi_control_change(ev[0], midi_chan, cc, val)
                self.zynmixer.midi_control_change(midi_chan, cc, val)
                self.state_manager.alsa_mixer_processor.midi_control_change(midi_chan, cc, val)
                self.state_manager.audio_player.midi_control_change(midi_chan, cc, val)
                return True
            return self.set_param(cc, val, midi_chan)
        elif evtype == 0xc:
            pass
            # Let zynthian handle PC
        return False

    def update_mixer_strip(self, chan, symbol, value, mixbus):
        #TODO: Blunt refresh of all controls after 2s of inactivity
        if self.feedback_timer:
            self.feedback_timer.cancel()
        self.feedback_timer = Timer(2.0, self.refresh)
        self.feedback_timer.start()

    def refresh(self):
        if self.feedback_timer:
            self.feedback_timer.cancel()
            self.feedback_timer = None
        self.strip2chan = []
        for chain_id in self.chain_manager.ordered_chain_ids:
            chain = self.chain_manager.chains[chain_id]
            if chain.zynmixer_proc is not None and chain.zynmixer_proc.eng_code == "MI" and chain.zynmixer_proc.mixer_chan < 16:
                self.strip2chan.append(chain.zynmixer_proc.mixer_chan)
        main_level = int(self.zynmixer_bus.get_level(0) * 127)
        lib_zyncore.dev_send_ccontrol_change(self.idev_out, self.midi_chan, 7, main_level)
        for strip, chan in enumerate(self.strip2chan):
            value = int(self.zynmixer.get_level(chan) * 127)
            lib_zyncore.dev_send_ccontrol_change(self.idev_out, self.midi_chan + int(strip / 8), 16 + strip % 8 , value)
            value = int(self.zynmixer.get_balance(chan) * 64 + 64)
            lib_zyncore.dev_send_ccontrol_change(self.idev_out, self.midi_chan + int(strip / 8), 24 + strip % 8 , value)

# ------------------------------------------------------------------------------
