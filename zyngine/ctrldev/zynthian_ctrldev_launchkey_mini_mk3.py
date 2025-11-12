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
        self.shift = False
        super().__init__(state_manager, idev_in, idev_out)

    def init(self):
        # Enable session mode on launchkey
        lib_zyncore.dev_send_note_on(self.idev_out, 15, 12, 127)
        self.cols = 8
        self.rows = 2
        self.pot_mode = 0 # Potentiometer mode
        self.mixer_toggle = False # Used to toggle mixer / launcher view
        super().init()

    def end(self):
        super().end()
        # Disable session mode on launchkey
        lib_zyncore.dev_send_note_on(self.idev_out, 15, 12, 0)

    def light_off(self):
        for row in range(self.rows):
            for col in range(8):
                self.pad_off(col, row)

    def update_seq_state(self, phrase, chan, state=None, mode=None):
        if self.idev_out is None :
            return
        try:
            row, col = self.zynseq.get_pad_coords(phrase, chan)
            if col is None:
                return
            row -= self.zynseq.phrase
        except:
            return
        if row < 0 or row >= self.rows or col < 0 or col >= self.cols:
            return
        if state is None or mode is None:
            state = self.zynseq.libseq.getSequenceState(self.zynseq.scene, phrase, chan)
            mode = (state >> 8) & 0xff
            state &= 0xff
        note = 96 + row * 16 + col
        # chan: 0=static, 1=flashing, 2=pulsing
        try:
            if mode == 0 or chan >= MAX_NUM_MIDI_CHANS: #TODO: Handle phrase launcher
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
            else:
                vel = 0
                chan = 0
        except Exception as e:
            chan = 0
            vel = 0
            logging.warning(e)

        lib_zyncore.dev_send_note_on(self.idev_out, chan, note, vel)

    def pad_off(self, col, row):
        note = 96 + row * 16 + col
        lib_zyncore.dev_send_note_on(self.idev_out, 0, note, 0)

    def refresh(self):
        if self.idev_out is None:
            return
        for row in range(self.rows):
            for col in range(zynseq.PHRASE_CHANNEL + 1):
                self.update_seq_state(row + self.zynseq.phrase, col)

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
                row = (note - 96) // 16 + self.zynseq.phrase
                midi_chan = self.zynseq.get_chan_from_col(col)
                if midi_chan is not None:
                    self.zynseq.libseq.togglePlayState(self.zynseq.scene, row, midi_chan)
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
                    chain = self.chain_manager.get_chain_by_position(pot, midi=False)
                    if chain is None or chain.mixer_chan > 16:
                        return True
                    match self.pot_mode:
                        case self.POT_MODE_VOLUME:
                            self.zynmixer.set_level(chain.mixer_chan, ccval / 127.0)
                        case self.POT_MODE_PAN:
                            self.zynmixer.set_balance(chain.mixer_chan, 2 * ccval / 127.0 - 1)
                        case self.POT_MODE_DEVICE:
                            # Ignore CC on MIDI channel 16 as it may trigger master channel or other unexpected action.
                            return True
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
                return True # Ignore Modulation CC and button release
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
                        self.state_manager.send_cuia("show_screen", ["audio_mixer"])
                    self.mixer_toggle = not self.mixer_toggle
        elif evtype == 0xC:
            val1 = ev[1] & 0x7F
            self.zynseq.select_bank(val1 + 1)

        return True

# ------------------------------------------------------------------------------
