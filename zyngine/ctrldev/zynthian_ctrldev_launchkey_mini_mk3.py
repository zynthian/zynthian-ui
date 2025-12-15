#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Novation Launchkey Mini MK3"
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
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq
from zyngui import zynthian_gui_config
from zyngine.zynthian_chain_manager import MAX_NUM_MIDI_CHANS
from zyngine.zynthian_signal_manager import zynsigman

# ------------------------------------------------------------------------------------------------------------------
# Novation Launchkey Mini MK3
# ------------------------------------------------------------------------------------------------------------------


class zynthian_ctrldev_launchkey_mini_mk3(zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer):

    dev_ids = ["Launchkey Mini MK3 IN 2"]
    driver_name = "Launchkey Mini Mk3"
    driver_description = "Interface Novation Launchkey Mini Mk3 with zynpad and zynmixer"

    POT_MODE_CUSTOM_0   = 0
    POT_MODE_VOLUME     = 1
    POT_MODE_DEVICE     = 2
    POT_MODE_PAN        = 3
    POT_MODE_SEND_A     = 4
    POT_MODE_SEND_B     = 5
    POT_MODE_CUSTOM_0   = 6
    POT_MODE_CUSTOM_1   = 7
    POT_MODE_CUSTOM_2   = 8
    POT_MODE_CUSTOM_3   = 9

    # Function to initialise class
    def __init__(self, state_manager, idev_in, idev_out=None):
        super().__init__(state_manager, idev_in, idev_out)
        self.cols = 8
        self.rows = 2
        self.scroll_v = self.zynseq.phrase
        self.shift = False
        self.pot_mode = self.POT_MODE_VOLUME    # Potentiometer mode
        self.mixer_toggle = False               # Used to toggle mixer / launcher view

    def init(self):
        # Enable session mode on launchkey
        lib_zyncore.dev_send_note_on(self.idev_out, 15, 12, 127)
        # Set pots to volume control
        self.pot_mode = self.POT_MODE_VOLUME
        lib_zyncore.dev_send_ccontrol_change(self.idev_out, 15, 9, self.pot_mode)
        self.mixer_toggle = False
        super().init()
        # Register for zynseq updates
        zynsigman.register_queued(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_SELECT_PHRASE, self.set_phrase_cb)

    def end(self):
        # Unregister for zynseq updates
        zynsigman.unregister(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_SELECT_PHRASE, self.set_phrase_cb)
        super().end()
        # Disable session mode on launchkey
        lib_zyncore.dev_send_note_on(self.idev_out, 15, 12, 0)

    def light_off(self):
        for row in range(self.rows):
            for col in range(8):
                self.pad_off(col, row)

    def set_phrase_cb(self, phrase):
        self.scroll_v = phrase
        self.refresh()

    def update_pad(self, row, col, pad_info):
        if col == self.cols:  # Phrase launcher not implemented!
            return
        note = 96 + row * 16 + col
        chan = 0  # chan: 0=static, 1=flashing, 2=pulsing
        vel = 0
        try:
            state = pad_info["state"]
            repeat = pad_info["repeat"]
            if repeat == 0 or chan >= MAX_NUM_MIDI_CHANS:
                vel = 0
                chan = 0
            elif state == zynseq.SEQ_STOPPED:
                vel = zynthian_gui_config.LAUNCHER_COLOUR[chan]["launchpad"]
                chan = 0
            elif state == zynseq.SEQ_PLAYING:
                vel = zynthian_gui_config.LAUNCHER_COLOUR[chan]["launchpad"]
                chan = 2
            elif state in [zynseq.SEQ_STOPPING, zynseq.SEQ_STOPPING_SYNC]:
                vel = zynthian_gui_config.LAUNCHER_STOPPING_COLOUR["launchpad"]
                chan = 1
            elif state == zynseq.SEQ_STARTING:
                vel = zynthian_gui_config.LAUNCHER_STARTING_COLOUR["launchpad"]
                lib_zyncore.dev_send_note_on(self.idev_out, 0, note, vel)
                vel = zynthian_gui_config.LAUNCHER_COLOUR[chan]["launchpad"]
                chan = 1
        except:
            pass
        lib_zyncore.dev_send_note_on(self.idev_out, chan, note, vel)

    def pad_off(self, col, row):
        note = 96 + row * 16 + col
        lib_zyncore.dev_send_note_on(self.idev_out, 0, note, 0)

    def midi_event(self, ev):
        if self.state_manager.power_save_mode:
            return True
        evtype = (ev[0] >> 4) & 0x0F
        chan = ev[0] & 0x0f
        if evtype == 0x9:
            note = ev[1] & 0x7F
            if ev == b'\x9f\x0C\x7F':
                # Ignore tally of the request to put the device into DAW mode
                return True

            # Toggle pad
            try:
                col = (note - 96) % 16
                midi_chan = self.get_filtered_midi_chan_by_index(col)
                if midi_chan is not None:
                    row = (note - 96) // 16
                    phrase = row + self.scroll_v
                    self.zynseq.libseq.togglePlayState(self.zynseq.scene, phrase, midi_chan)
            except:
                pass
        elif evtype == 0xB:
            ccnum = ev[1] & 0x7F
            ccval = ev[2] & 0x7F
            if chan == 0xf:
                if ccval == 0:
                    return True # Ignore button release
                if ccnum == 9:
                    self.pot_mode = ccval
                elif 20 < ccnum < 29:
                    # Pots
                    if self.shift:
                        # Add 8 extra pots with shift
                        pot = ccnum - 13
                    else:
                        pot = ccnum - 21
                    match self.pot_mode:
                        case self.POT_MODE_VOLUME:
                            self.set_mixer_param("level", pot, ccval / 127.0)
                        case self.POT_MODE_PAN:
                            self.set_mixer_param("balance", pot, 2 * ccval / 127.0 - 1)
                        case self.POT_MODE_DEVICE:
                            return False
                elif ccnum == 0x66:
                    # TRACK RIGHT
                    self.state_manager.send_cuia("ARROW_RIGHT")
                elif ccnum == 0x67:
                    # TRACK LEFT
                    self.state_manager.send_cuia("ARROW_LEFT")
                elif ccnum == 0x73:
                    # PLAY
                    if self.shift:
                        self.state_manager.send_cuia("TOGGLE_MIDI_PLAY")
                    else:
                        self.state_manager.send_cuia("TOGGLE_PLAY")
                elif ccnum == 0x75:
                    # RECORD
                    if self.shift:
                        self.state_manager.send_cuia("TOGGLE_MIDI_RECORD")
                    else:
                        self.state_manager.send_cuia("TOGGLE_RECORD")
                return True

            if ccnum == 0x6C:
                # SHIFT
                self.shift = ccval != 0
            elif ccnum == 0 or ccval == 0:
                return True  # Ignore Modulation CC and button release
            elif ccnum == 0x68:
                if self.shift:
                    # UP
                    self.zynseq.select_phrase(self.zynseq.phrase - 1)
                    self.refresh()
                else:
                    # Scene (Phrase) launcher
                    self.zynseq.libseq.togglePlayState(self.zynseq.scene, self.zynseq.phrase, zynseq.PHRASE_CHANNEL)
            elif ccnum == 0x69:
                if self.shift:
                    # DOWN
                    self.zynseq.select_phrase(self.zynseq.phrase + 1)
                    self.refresh()
                else:
                    # Stop Solo Mute button
                    if self.mixer_toggle:
                        self.state_manager.send_cuia("show_screen", ["launcher"])
                    else:
                        self.state_manager.send_cuia("show_screen", ["mixer"])
                    self.mixer_toggle = not self.mixer_toggle
        elif evtype == 0xC:
            val1 = ev[1] & 0x7F
            self.zynseq.select_bank(val1 + 1)

        return True

# ------------------------------------------------------------------------------
