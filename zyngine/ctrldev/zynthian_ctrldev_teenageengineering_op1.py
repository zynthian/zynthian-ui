#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for Teenage Engineering OP-1 OG (Original)
# Tested with firmware version 246.
# Designed to work with OP-1 in MIDI Mode:
# - On OP-1, press Shift+COM
# - Choose CTRL (Button T2)
# - Press Shift button to verify knobs are sending relative CC, change with blue 
#   encoder if needed.
# - Press Shift button to verify <> buttons are sending MIDI CC, change 
#   with white encoder if desired. Set to Octave +- if this behavior is 
#   preferred.
#
# Copyright (C) 2026 Bernard Vander Beken <bernard@jawn.net>
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
from zynlibs.zynseq import zynseq
from zyncoder.zyncore import lib_zyncore

from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_base
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynmixer

# ------------------------------------------------------------------------------------------------------------------
# MIDI CC messages sent by OP-1
# NOTE: constants based on https://github.com/pcppcp/op1/blob/live-9/op1/consts.py
# ------------------------------------------------------------------------------------------------------------------
OP1_ENCODER_1 = 1
OP1_ENCODER_2 = 2
OP1_ENCODER_3 = 3
OP1_ENCODER_4 = 4

OP1_ENCODER_1_PUSH = 64
OP1_ENCODER_2_PUSH = 65
OP1_ENCODER_3_PUSH = 66
OP1_ENCODER_4_PUSH = 67

OP1_HELP_BUTTON = 5
OP1_METRONOME_BUTTON = 6

OP1_MODE_1_BUTTON = 7
OP1_MODE_2_BUTTON = 8
OP1_MODE_3_BUTTON = 9
OP1_MODE_4_BUTTON = 10

OP1_T1_BUTTON = 11
OP1_T2_BUTTON = 12
OP1_T3_BUTTON = 13
OP1_T4_BUTTON = 14

OP1_ARROW_UP_BUTTON = 15
OP1_ARROW_DOWN_BUTTON = 16
OP1_SCISSOR_BUTTON = 17

OP1_SS1_BUTTON = 50
OP1_SS2_BUTTON = 51
OP1_SS3_BUTTON = 52
OP1_SS4_BUTTON = 21
OP1_SS5_BUTTON = 22
OP1_SS6_BUTTON = 23
OP1_SS7_BUTTON = 24
OP1_SS8_BUTTON = 25

OP1_SEQ_BUTTON = 26

OP1_REC_BUTTON = 38
OP1_PLAY_BUTTON = 39
OP1_STOP_BUTTON = 40

OP1_LEFT_ARROW = 41
OP1_RIGHT_ARROW = 42
OP1_SHIFT_BUTTON = 43

OP1_MICRO = 48
OP1_COM = 49
# ------------------------------------------------------------------------------------------------------------------

class zynthian_ctrldev_teenageengineering_op1(zynthian_ctrldev_zynmixer):

    dev_ids = ["OP-1 IN 1"]
    driver_name = "OP-1"
    driver_description = "Teenage Engineering OP-1 integration"
    unroute_from_chains = False

    def __init__(self, state_manager, idev_in, idev_out):
        super().__init__(state_manager, idev_in, idev_out)

    def midi_event(self, ev):
        evtype = (ev[0] >> 4) & 0x0F
        channel = ev[0] & 0x0F
        ccnum = ev[1] & 0x7F
        ccval = ev[2] & 0x7F

        # Control Change (CC) message
        if evtype == 0xB:
            # Encoder rotate: relative CC -127 is CW, 1 is CCW
            # Corresponds to relative mode 2 (or inverse of it) in zynthian_controller.midi_cc_mode_detect()
            if ccnum >= OP1_ENCODER_1 and ccnum <= OP1_ENCODER_4:

                zynpot = ccnum - 1 # 0 based instead of 1 based
                delta = ccval if ccval < 64 else (ccval - 128)

                # logging.debug(f"ZYNPOT {zynpot}, {delta}")

                self.state_manager.send_cuia("ZYNPOT", (zynpot, delta))

            # Encoder buttons
            # ZynSwitch logic for button presses and releases
            elif ccnum >= OP1_ENCODER_1_PUSH and ccnum <= OP1_ENCODER_4_PUSH:                
                # CC to corresonding zynswitch mappings
                zynswitch_index = {OP1_ENCODER_1_PUSH: 0, OP1_ENCODER_2_PUSH: 1, OP1_ENCODER_3_PUSH: 2, OP1_ENCODER_4_PUSH: 3}.get(ccnum)

                # Push button
                if ccval == 127:
                    self.state_manager.send_cuia("ZYNSWITCH", (zynswitch_index, "P"))
                # Release button
                else:
                    self.state_manager.send_cuia("ZYNSWITCH", (zynswitch_index, "R"))

            # Mix / Level
            elif ccnum == OP1_MODE_4_BUTTON:
                if ccval > 0:
                    # Corresponds to Mix / Level on V5
                    self.state_manager.send_cuia("ZYNSWITCH", (5, "S"))

            # Tempo
            elif ccnum == OP1_METRONOME_BUTTON:
                if ccval > 0:
                    self.state_manager.send_cuia("TEMPO")

            # Arrows
            elif ccnum == OP1_ARROW_UP_BUTTON:
                if ccval > 0:
                    self.state_manager.send_cuia("ARROW_UP")
            elif ccnum == OP1_ARROW_DOWN_BUTTON:
                if ccval > 0:
                    self.state_manager.send_cuia("ARROW_DOWN")
            elif ccnum == OP1_LEFT_ARROW:
                if ccval > 0:
                    self.state_manager.send_cuia("ARROW_LEFT")
            elif ccnum == OP1_RIGHT_ARROW:
                if ccval > 0:
                    self.state_manager.send_cuia("ARROW_RIGHT")

            # Record, playback
            elif ccnum == OP1_REC_BUTTON:
                if ccval > 0:
                    self.state_manager.send_cuia("TOGGLE_AUDIO_RECORD")
            elif ccnum == OP1_PLAY_BUTTON:
                if ccval > 0:
                    self.state_manager.send_cuia("TOGGLE_AUDIO_PLAY")

# ------------------------------------------------------------------------------