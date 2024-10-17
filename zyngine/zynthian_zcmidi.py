# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_midi)
#
# zynthian_midi implements the MIDI functionality needed by Zynthian Synth Engine
#
# Copyright (C) 2015-2016 Fernando Moyano <jofemodo@zynthian.org>
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
from zyncoder.zyncore import lib_zyncore

# ------------------------------------------------------------------------------
# MIDI Class
# ------------------------------------------------------------------------------


class zynthian_zcmidi:

    bank_msb_selected = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    bank_lsb_selected = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    prg_selected = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

    def __init__(self):
        pass

    @staticmethod
    def note_on(chan, note, vel):
        lib_zyncore.ui_send_note_on(chan, note, vel)

    @staticmethod
    def note_off(chan, note):
        lib_zyncore.ui_send_note_on(chan, note, 0)

    @staticmethod
    def set_midi_control(chan, ctrl, val):
        lib_zyncore.ui_send_ccontrol_change(chan, ctrl, val)

    def set_midi_bank_msb(self, chan, msb):
        if not isinstance(chan, int) or chan > len(self.bank_msb_selected):
            return
        logging.debug("Set MIDI CH " + str(chan) + ", Bank MSB: " + str(msb))
        self.bank_msb_selected[chan] = msb
        self.set_midi_control(chan, 0, msb)

    def get_midi_bank_msb(self, chan):
        if not isinstance(chan, int) or chan > len(self.bank_msb_selected):
            return 0
        return self.bank_msb_selected[chan]

    def set_midi_bank_lsb(self, chan, lsb):
        if not isinstance(chan, int) or chan > len(self.bank_msb_selected):
            return
        logging.debug("Set MIDI CH " + str(chan) + ", Bank LSB: " + str(lsb))
        self.bank_lsb_selected[chan] = lsb
        self.set_midi_control(chan, 32, lsb)

    def get_midi_bank_lsb(self, chan):
        if not isinstance(chan, int) or chan > len(self.bank_msb_selected):
            return 0
        return self.bank_lsb_selected[chan]

    def set_midi_prg(self, chan, prg):
        if not isinstance(chan, int) or chan > len(self.bank_msb_selected):
            return
        logging.debug("Set MIDI CH " + str(chan) + ", Program: " + str(prg))
        self.prg_selected[chan] = prg
        lib_zyncore.ui_send_program_change(chan, prg)

    def get_midi_prg(self, chan):
        if not isinstance(chan, int) or chan > len(self.bank_msb_selected):
            return 0
        return self.prg_selected[chan]

    def set_midi_preset(self, chan, msb, lsb, prg):
        if not isinstance(chan, int) or chan > len(self.bank_msb_selected):
            return
        logging.debug("Set MIDI CH " + str(chan) + ", Bank MSB: " +
                      str(msb) + ", Bank LSB: " + str(lsb) + ", Program: " + str(prg))
        self.bank_msb_selected[chan] = msb
        self.bank_lsb_selected[chan] = lsb
        self.prg_selected[chan] = prg
        self.set_midi_control(chan, 0, msb)
        self.set_midi_control(chan, 32, lsb)
        lib_zyncore.ui_send_program_change(chan, prg)

    def get_midi_preset(self, chan):
        if not isinstance(chan, int) or chan > len(self.bank_msb_selected):
            return []
        return [self.bank_msb_selected[chan], self.bank_lsb_selected[chan], self.prg_selected[chan]]
