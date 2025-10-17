#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Novation Launchkey MK4"
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <brian@riban.co.uk>
#                         Jorge Razon <jrazon@gmail.com>
#
#
#******************************************************************************
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
#******************************************************************************

import logging
from time import sleep, time

# Zynthian specific modules
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq

# ------------------------------------------------------------------------------------------------------------------
# Novation Launchkey MK4 37
# ------------------------------------------------------------------------------------------------------------------

class zynthian_ctrldev_launchkey_mk4_37(zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer):

    dev_ids = ["Launchkey MK4 37 DAW In", "Launchkey MK4 37 IN 2"]
    driver_name = "Launchkey MK4 37"
    driver_description = "Interface Novation Launchkey Mk4 with zynpad"

    PAD_COLOURS = [71, 104, 76, 51, 104, 41, 64, 12, 11, 71, 4, 67, 42, 9, 105, 15]
    STARTING_COLOUR = 123
    STOPPING_COLOUR = 120
    
    # Function to initialise class
    def __init__(self, state_manager, idev_in, idev_out=None):
        self.shift = False
        self.mode_cc51 = False
        self.mode_cc52 = False
        self.press_times = {}
        super().__init__(state_manager, idev_in, idev_out)
        self.sys_ex_header = (0xF0, 0x00, 0x20, 0x29, 0x02, 0x14)

    def send_sysex(self, data):
        if self.idev_out is not None:
            msg = self.sys_ex_header + bytes.fromhex(data) + (0xF7,)
            lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))
            sleep(0.05)

    def init(self):
        # Enable DAW mode on launchkey
        lib_zyncore.dev_send_note_on(self.idev_out, 15, 12, 127)
        self.cols = 8
        self.rows = 2
        super().init()

    def end(self):
        super().end()
        # Disable DAW mode on launchkey
        lib_zyncore.dev_send_note_on(self.idev_out, 15, 12, 0)
    
    def update_seq_state(self, bank, seq, state, mode, group):
        if self.idev_out is None or bank != self.zynseq.bank:
            return
        col, row = self.zynseq.get_xy_from_pad(seq)
        if row > 1:
            return
        note = 96 + row * 16 + col
        try:
            if mode == 0 or group > 16:
                chan = 0
                vel = 0
            elif state == zynseq.SEQ_STOPPED:
                chan = 0
                vel = self.PAD_COLOURS[group]
            elif state == zynseq.SEQ_PLAYING:
                chan = 2
                vel = self.PAD_COLOURS[group]
            elif state in [zynseq.SEQ_STOPPING, zynseq.SEQ_STOPPINGSYNC]:
                chan = 1
                vel = self.STOPPING_COLOUR
            elif state == zynseq.SEQ_STARTING:
                chan = 1
                vel = self.STARTING_COLOUR
            else:
                chan = 0
                vel = 0
        except Exception as e:
            chan = 0
            vel = 0
            # logging.warning(e)

        lib_zyncore.dev_send_note_on(self.idev_out, chan, note, vel)

    def midi_event(self, ev):
        evtype = (ev[0] >> 4) & 0x0F
        ev_chan = ev[0] & 0x0F
        
        # New block: Handle pad events for the sequencer
        if evtype == 0x9:
            note = ev[1] & 0x7F
            try:
                col = (note - 96) // 16
                row = (note - 96) % 16
                pad = row * self.zynseq.col_in_bank + col
                if pad < self.zynseq.seq_in_bank:
                    self.zynseq.libseq.togglePlayState(self.zynseq.bank, pad)
            except:
                pass
        elif evtype == 0xB:
            ccnum = ev[1] & 0x7F
            ccval = ev[2] & 0x7F
            
            # Button mappings for cleaner code
            button_commands = {
                0x66: "ARROW_RIGHT",
                0x67: "ARROW_LEFT",
                106: "ARROW_UP",
                107: "ARROW_DOWN",
                118: "BACK"
            }
            
            # The Launchkey's physical shift button uses CC 0x3F.
            if ccnum == 0x3F:
                self.shift = ccval != 0
                return True

            # Logic for CC 51 and CC 52, which toggle mixer bank for knobs 1-4
            elif ccnum == 51 and ev_chan == 0:
                self.mode_cc51 = (ccval != 0)
                return True
            elif ccnum == 52 and ev_chan == 0:
                self.mode_cc52 = (ccval != 0)
                return True
                
            # Consolidated Knob Logic
            elif 20 < ccnum < 25:
                # Knobs 1-4 for mixer channels
                mixer_channel = ccnum - 20
                if self.mode_cc51:
                    mixer_channel += 4
                elif self.mode_cc52:
                    mixer_channel += 8
                    
                chain = self.chain_manager.get_chain_by_position(mixer_channel - 1, midi=False)
                if chain and chain.mixer_chan is not None and chain.mixer_chan < 17:
                    self.zynmixer.set_level(chain.mixer_chan, ccval / 127.0)
                return True
            elif 24 < ccnum < 29:
                # Knobs 5-8 for ZYNPOT_ABS
                self.state_manager.send_cuia("ZYNPOT_ABS", [ccnum - 25, ccval / 127])
                return True

            # Combined ZynSwitch and Metronome logic
            elif ccnum in [74, 75, 76, 77]:
                # If SHIFT is held and it's the Metronome button (CC 76)
                if self.shift and ccnum == 76:
                    if ccval > 0:
                        self.state_manager.send_cuia("TEMPO")
                    return True
                
                # ZynSwitch logic for button presses and releases
                zynswitch_index = {74: 0, 75: 1, 76: 3, 77: 2}.get(ccnum)
                if ccval > 0:
                    # Button press: Record the current time
                    self.press_times[ccnum] = time()
                else:
                    # Button release: Calculate the duration and send the command
                    if ccnum in self.press_times:
                        duration = time() - self.press_times[ccnum]
                        if duration < 0.5:
                            # Short press
                            self.state_manager.send_cuia("ZYNSWITCH", [zynswitch_index, 'S'])
                        elif duration < 1.5:
                            # Bold press
                            self.state_manager.send_cuia("ZYNSWITCH", [zynswitch_index, 'B'])
                        else:
                            # Long press
                            self.state_manager.send_cuia("ZYNSWITCH", [zynswitch_index, 'L'])
                        del self.press_times[ccnum]
                return True

            # Handle the PLAY and RECORD buttons
            elif ccnum == 0x73 and ccval > 0:
                if self.shift:
                    self.state_manager.send_cuia("TOGGLE_MIDI_PLAY")
                else:
                    self.state_manager.send_cuia("TOGGLE_PLAY")
                return True
            elif ccnum == 0x75 and ccval > 0:
                if self.shift:
                    self.state_manager.send_cuia("TOGGLE_MIDI_RECORD")
                else:
                    self.state_manager.send_cuia("TOGGLE_RECORD")
                return True
            
            # Use the dictionary for the remaining buttons and check for press
            elif ccnum in button_commands and ccval > 0:
                self.state_manager.send_cuia(button_commands[ccnum])
                return True
            elif ccnum == 0 or ccval == 0:
                return True

        elif evtype == 0xC:
            val1 = ev[1] & 0x7F
            self.zynseq.select_bank(val1 + 1)

        return True
# ------------------------------------------------------------------------------------------------------------------
