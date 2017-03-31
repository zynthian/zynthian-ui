# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_midi)
# 
# zynthian_midi implements the MIDI functionality needed by Zynthian Synth Engine
# 
# Copyright (C) 2015-2016 Fernando Moyano <jofemodo@zynthian.org>
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
from zyncoder import *

#------------------------------------------------------------------------------
# MIDI Class
#------------------------------------------------------------------------------

class zynthian_zcmidi:

	bank_msb_selected=[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
	bank_lsb_selected=[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
	prg_selected=[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]

	def __init__(self):
		self.lib_zyncoder=zyncoder.get_lib_zyncoder()

	def set_midi_control(self, chan, ctrl, val):
		self.lib_zyncoder.zynmidi_set_control(chan, ctrl, val)

	def set_midi_bank_msb(self, chan, msb):
		logging.debug("Set MIDI CH " + str(chan) + ", Bank MSB: " + str(msb))
		self.bank_msb_selected[chan]=msb
		self.set_midi_control(chan,0,msb)

	def get_midi_bank_msb(self, chan):
		return self.bank_msb_selected[chan]

	def set_midi_bank_lsb(self, chan, lsb):
		logging.debug("Set MIDI CH " + str(chan) + ", Bank LSB: " + str(lsb))
		self.bank_lsb_selected[chan]=lsb
		self.set_midi_control(chan,32,lsb)

	def get_midi_bank_lsb(self, chan):
		return self.bank_lsb_selected[chan]

	def set_midi_prg(self, chan, prg):
		logging.debug("Set MIDI CH " + str(chan) + ", Program: " + str(prg))
		self.prg_selected[chan]=prg
		self.lib_zyncoder.zynmidi_set_program(chan, prg)

	def get_midi_prg(self, chan):
		return self.prg_selected[chan]

	def set_midi_preset(self, chan, msb, lsb, prg):
		logging.debug("Set MIDI CH " + str(chan) + ", Bank MSB: " + str(msb) + ", Bank LSB: " + str(lsb) + ", Program: " + str(prg))
		self.bank_msb_selected[chan]=msb
		self.bank_lsb_selected[chan]=lsb
		self.prg_selected[chan]=prg
		self.set_midi_control(chan,0,msb)
		self.set_midi_control(chan,32,lsb)
		self.lib_zyncoder.zynmidi_set_program(chan, prg)

	def get_midi_preset(self, chan):
		return [self.bank_msb_selected[chan],self.bank_lsb_selected[chan],self.prg_selected[chan]]
