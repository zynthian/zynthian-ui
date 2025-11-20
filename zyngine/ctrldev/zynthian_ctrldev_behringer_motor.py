#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for Behringer Motör
# Stage control for setBfree and pianoteq
# Mode enforcer implemented as a python jack client.
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
from zyncoder.zyncore import lib_zyncore
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
        # Bank C (5-note scales => black keys)
        "Chromatic",
        "Minor Pentatonic",
        "Major Pentatonic",
        "Hirojoshi",
        "In-Sen",
        "Iwato",
        "Kumoi",
        None,
        # Bank D (other => custom keys)
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


class zynthian_ctrldev_behringer_motor(zynthian_ctrldev_base, zynthian_ctrldev_base_moder):

    dev_ids = ["MOTÖR61 Keyboard IN 1", "MOTÖR49 Keyboard IN 1"]
    driver_description = "Mode enforcer. Use pads to change mode:\n" \
                         "+ Bank A (White Keys): Chromatic, Major, Minor, Harmonic Minor, Melodic Minor, Dorian, Mixolydian, Lydian\n" \
                         "+ Bank B (White Keys): Chromatic, Phrygian, Locrian, Super Locrian, Bhairav, Hungarian Minor, Minor Gypsy, Spanish\n" \
                         "+ Bank C (Black Keys): Chromatic, Minor Pentatonic, Major Pentatonic, Hirojoshi, In-Sen, Iwato, Kumoi\n" \
                         "+ Bank D (Custom Keys): Chromatic, Diminished, Whole-Half, Spanish, Whole Tone, Minor Blues, Pelog"

    unroute_from_chains = 0b0000000000000010  # Unroute channel 2 (pad's channel)
    autoload_flag = False

    # Map zctrl symbols => MOTÖR ccnums => Faders (21-53), Encoders (71-102)
    zctrls2ccnum = {
        # Master Fader (CC53) => Volume
        # Bank A Faders 1-8 & Encoder 1 => Upper Drawbars
        #        Encoder 2 => Percussion on/off
        #        Encoder 3 => Vibrato routing
        #        Encoder 4 => Reverb
        'Upper': {
            'volume': 53,
            'DB 16': 21,
            'DB 5 1/3': 22,
            'DB 8': 23,
            'DB 4': 24,
            'DB 2 2/3': 25,
            'DB 2': 26,
            'DB 1 3/5': 27,
            'DB 1 1/3': 28,
            'DB 1': 71,
            'percussion': 72,
            'vibrato routing': 73,
            'reverb': 74,
        },
        # Bank B Faders 1-8 & Encoder 1 => Lower Drawbars
        'Lower': {
            'DB 16': 29,
            'DB 5 1/3': 30,
            'DB 8': 31,
            'DB 4': 32,
            'DB 2 2/3': 33,
            'DB 2': 34,
            'DB 1 3/5': 35,
            'DB 1 1/3': 36,
            'DB 1': 79
        },
        # Bank C Faders 1-8 & Encoder 1 => Pedal Drawbars
        'Pedals': {
            'DB 16': 37,
            'DB 5 1/3': 38,
            'DB 8': 39,
            'DB 4': 40,
            'DB 2 2/3': 41,
            'DB 2': 42,
            'DB 1 3/5': 43,
            'DB 1 1/3': 44,
            'DB 1': 87
        },
        # Bank A Encoders 5-8
        'Pianoteq': {
            'volume': 75,
            #'reverb_switch': 76,
            'dynamics': 76,
            'reverb_mix': 77,
            'reverb_duration': 78
        }
    }
    fader_touch_flags = [False] * 33  # 4 banks x 8 faders + 1 master fader
    setbfree_procs = None
    pianoteq_proc = None
    ccnum2zctrls = {}

    def init(self):
        super().init()
        # Register for processor tree changes
        zynsigman.register_queued(zynsigman.S_STATE_MAN, self.state_manager.SS_LOAD_SNAPSHOT, self.refresh)
        zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_REMOVE_CHAIN, self.refresh)
        zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_REMOVE_ALL_CHAINS, self.refresh)
        zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_REMOVE_PROCESSOR, self.refresh)

    def end(self):
        self.reset_feedback()
        # Unregister from processor tree changes
        zynsigman.unregister(zynsigman.S_STATE_MAN, self.state_manager.SS_LOAD_SNAPSHOT, self.refresh)
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_REMOVE_CHAIN, self.refresh)
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_REMOVE_ALL_CHAINS, self.refresh)
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_REMOVE_PROCESSOR, self.refresh)
        super().end()

    def refresh(self):
        changed = False
        # Look for setBfree engine
        if "BF" in self.chain_manager.zyngines:
            if self.setbfree_procs != self.chain_manager.zyngines["BF"].processors:
                self.setbfree_procs = self.chain_manager.zyngines["BF"].processors
                changed = True
        elif self.setbfree_procs:
            self.setbfree_procs = None
            changed = True

        # Look for pianoteq engine
        if "PT" in self.chain_manager.zyngines:
            if self.pianoteq_proc != self.chain_manager.zyngines["PT"].processors[0]:
                self.pianoteq_proc = self.chain_manager.zyngines["PT"].processors[0]
                changed = True
        elif self.pianoteq_proc:
            self.pianoteq_proc = None
            changed = True

        if changed:
            self.setup_feedback()

    def midi_event(self, ev):
        evtype = (ev[0] >> 4) & 0x0F
        evchan = ev[0] & 0x0F

        # By default, pads, faders and encoders use MIDI channel 2
        if evchan == 1:
            # Note-Off:
            if evtype == 0x8:
                note = ev[1] & 0x7F
                # Fader touch
                if 0 <= note <= 32:
                    self.fader_touch_flags[note] = False
                    return True
            # Note-On:
            elif evtype == 0x9:
                note = ev[1] & 0x7F
                # Fader touch
                if 0 <= note <= 32:
                    self.fader_touch_flags[note] = True
                    return True
                # Pads (bank A, B, C & D) => Mode selection
                if 66 <= note <= 97:
                    mode_key = _MODE_BANKS["notes"][note - 66]
                    try:
                        self.mode_index.value = self.mode_keys.index(mode_key)
                    except:
                        pass
                    logging.debug(f"MODE => {mode_key} ({self.mode_index.value})")
                    zynsigman.send_queued(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_MESSAGE, message=f"{self.get_driver_name()}: {mode_key}")
                    return True
                return False
            # CCs: faders and encoders
            elif evtype == 0xB:
                ccnum = ev[1] & 0x7F
                ccval = ev[2] & 0x7F
                try:
                    zctrl = self.ccnum2zctrls[ccnum]
                    if zctrl.processor == self.pianoteq_proc:
                        self.ccnum2zctrls[ccnum].midi_control_change(ccval)
                    else:
                        self.ccnum2zctrls[ccnum].set_value(ccval)
                    return True
                except:
                    pass
        return False

    def setup_feedback(self):
        logging.debug("SETTING UP FADER FEEDBACK")
        self.ccnum2zctrls = {}
        if self.setbfree_procs:
            for proc in self.setbfree_procs:
                for symbol, ccnum in self.zctrls2ccnum[proc.bank_name].items():
                    logging.debug(f"Setting Up feedback for {symbol}, CC{ccnum}")
                    zctrl = proc.controllers_dict[symbol]
                    zctrl.set_send_value_cb(self.send_feedback)
                    self.ccnum2zctrls[ccnum] = zctrl
        if self.pianoteq_proc:
            for symbol, ccnum in self.zctrls2ccnum['Pianoteq'].items():
                logging.debug(f"Setting Up feedback for {symbol}, CC{ccnum}")
                zctrl = self.pianoteq_proc.controllers_dict[symbol]
                zctrl.set_send_value_cb(self.send_feedback)
                self.ccnum2zctrls[ccnum] = zctrl

    def reset_feedback(self):
        logging.debug("RESETTING FADER FEEDBACK")
        self.ccnum2zctrls = {}
        if self.setbfree_procs:
            for proc in self.setbfree_procs:
                for symbol in self.zctrls2ccnum[proc.bank_name]:
                    zctrl = proc.controllers_dict[symbol]
                    logging.debug(f"Resetting feedback for {zctrl.symbol}")
                    zctrl.reset_send_value_cb()
        if self.pianoteq_proc:
            for symbol in self.zctrls2ccnum['Pianoteq']:
                zctrl = self.pianoteq_proc.controllers_dict[symbol]
                logging.debug(f"Resetting feedback for {zctrl.symbol}")
                zctrl.reset_send_value_cb()

    def send_feedback(self, zctrl):
        try:
            if zctrl.processor == self.pianoteq_proc:
                ccnum = self.zctrls2ccnum['Pianoteq'][zctrl.symbol]
                ccval = zctrl.get_ctrl_midi_val()
            #elif zctrl.processor in self.setbfree_procs:
            else:
                ccnum = self.zctrls2ccnum[zctrl.processor.bank_name][zctrl.symbol]
                # Don't send feedback if fader is touched
                if 21 <= ccnum <= 53 and self.fader_touch_flags[ccnum - 21]:
                    return
                ccval = zctrl.value
            #logging.debug(f"Sending feedback to CC{ccnum} => {ccval}")
            lib_zyncore.dev_send_ccontrol_change(self.idev_out, 1, ccnum, ccval)
        except Exception as e:
            logging.error(f"Can't find feedback config for zctrl {zctrl.symbol}")

# ------------------------------------------------------------------------------
