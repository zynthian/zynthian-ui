#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for Akai MPK mini MK3
# A mode enforcer implemented as a python jack client.
#
# Copyright (C) 2015-2025 Fernando Moyano <jofemodo@zynthian.org>
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
from zyngine.zynthian_signal_manager import zynsigman
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_base
from zyngine.ctrldev.zynthian_ctrldev_base_moder import zynthian_ctrldev_base_moder

_MODE_BANKS = {
    "notes": [
        # Bank A (7-note scales => white keys)
        "Chromatic",
        "Major",
        "Minor",
        "Harmonic Minor",
        "Melodic Minor",
        "Dorian",
        "Mixolydian",
        "Lydian",
        # Bank B (7-note scales => white keys)
        "Chromatic",
        "Phrygian",
        "Locrian",
        "Super Locrian",
        "Bhairav",
        "Hungarian Minor",
        "Minor Gypsy",
        "Spanish",
    ],
    "CCs": [
        # Bank A (5-note scales => black keys)
        "Chromatic",
        "Minor Pentatonic",
        "Major Pentatonic",
        "Hirojoshi",
        "In-Sen",
        "Iwato",
        "Kumoi",
        None,
        # Bank B (other => custom keys)
        "Chromatic",
        "Diminished",
        "Whole-Half",
        "Spanish",
        "Whole Tone",
        "Minor Blues",
        "Pelog",
        None
    ]
}

# ------------------------------------------------------------------------------------------------------------------
# Mode enforcer for the Akai MPK mini MK3
# ------------------------------------------------------------------------------------------------------------------


class zynthian_ctrldev_akai_mpk_mini_mk3_moder(zynthian_ctrldev_base, zynthian_ctrldev_base_moder):

    dev_ids = ["MPK mini 3 IN 1"]
    driver_description = "Mode enforcer. Use pads notes & CCs to change mode:\n"\
                         "+ Notes / Bank A (White Keys): Chromatic, Major, Minor, Harmonic Minor, Melodic Minor, Dorian, Mixolydian, Lydian\n"\
                         "+ Notes / Bank B (White Keys): Chromatic, Phrygian, Locrian, Super Locrian, Bhairav, Hungarian Minor, Minor Gypsy, Spanish\n"\
                         "+ CC / Bank A (Black Keys): Chromatic, Minor Pentatonic, Major Pentatonic, Hirojoshi, In-Sen, Iwato, Kumoi\n"\
                         "+ CC / Bank B (Custom Keys): Chromatic, Diminished, Whole-Half, Spanish, Whole Tone, Minor Blues, Pelog"

    unroute_from_chains = 0b0000001000000000  # Unroute channel 10 (akai MPK mini's pads)
    autoload_flag = False

    def midi_event(self, ev):
        evtype = (ev[0] >> 4) & 0x0F
        evchan = ev[0] & 0x0F
        # Use the Akai MPK mini's pads (channel 10) for selecting the mode =>
        if evchan == 9:
            # Pad Notes, Bank A & B:
            if evtype == 0x9:
                note = ev[1] & 0x7F
                if 36 <= note <= 51:
                    mode_key = _MODE_BANKS["notes"][note - 36]
                    try:
                        self.mode_index.value = self.mode_keys.index(mode_key)
                    except:
                        pass
                    logging.debug(f"MODE => {mode_key} ({self.mode_index.value})")
                    zynsigman.send_queued(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_MESSAGE, message=f"{self.get_driver_name()}: {mode_key}")
                    return True
            # Pad CCs, Bank A & B:
            elif evtype == 0xB:
                ccnum = ev[1] & 0x7F
                ccval = ev[2] & 0x7F
                if ccval > 0 and 16 <= ccnum <= 31:
                    mode_key = _MODE_BANKS["CCs"][ccnum - 16]
                    try:
                        self.mode_index.value = self.mode_keys.index(mode_key)
                    except:
                        pass
                    logging.debug(f"MODE => {mode_key} ({self.mode_index.value})")
                    zynsigman.send_queued(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_MESSAGE, message=f"{self.get_driver_name()}: {mode_key}")
                    return True

# ------------------------------------------------------------------------------
