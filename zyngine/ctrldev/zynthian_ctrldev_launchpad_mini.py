#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Novation Launchpad Mini Mk1 & MK2"
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <brian@riban.co.uk>
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

# Zynthian specific modules
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynpad
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq

# ------------------------------------------------------------------------------------------------------------------
# Novation Launchpad Mini MK1 & MK2
# ------------------------------------------------------------------------------------------------------------------

class zynthian_ctrldev_launchpad_mini(zynthian_ctrldev_zynpad):

	dev_ids = ["Launchpad Mini MIDI 1"]

	OFF_COLOUR = 0xC
	PLAYING_COLOUR = 0x3C
	STOPPED_COLOUR = 0x3F
	STARTING_COLOUR = 0x3A
	# STARTING_COLOUR =  = 0x38
	STOPPING_COLOUR = 0x0B


	def get_note_xy(self, note):
		row = note // 16
		col = note % 16
		return col, row


	def init(self):
		pass
		# Light-Off all LEDs
		#self.light_off()


	def end(self):
		self.light_off()


	# Scene LED feedback
	def refresh_zynpad_bank(self):
		if self.idev_out <= 0:
			return
		#logging.debug("Updating Launchpad MINI bank leds")
		col = 8
		for row in range(0, 8):
			note = 16 * row + col
			if row == self.zynpad.bank - 1:
				lib_zyncore.dev_send_note_on(self.idev_out, 0, note, self.PLAYING_COLOUR)
			else:
				lib_zyncore.dev_send_note_on(self.idev_out, 0, note, self.OFF_COLOUR)


	def update_pad(self, pad, state, mode):
		if self.idev_out <= 0:
			return
		#logging.debug("Updating Launchpad MINI pad {}".format(pad))
		col, row = self.zynpad.get_xy_from_pad(pad)
		note = 16 * row + col
		chan = 0
		if mode == 0:
			vel = self.OFF_COLOUR
		elif state == zynseq.SEQ_STOPPED:
			vel = self.STOPPED_COLOUR
		elif state == zynseq.SEQ_PLAYING:
			vel = self.PLAYING_COLOUR
		elif state == zynseq.SEQ_STOPPING:
			vel = self.STOPPING_COLOUR
		elif state == zynseq.SEQ_STARTING:
			vel = self.STARTING_COLOUR
		else:
			vel = self.OFF_COLOUR
		lib_zyncore.dev_send_note_on(self.idev_out, chan, note, vel)


	def midi_event(self, ev):
		#logging.debug("Launchpad MINI MIDI handler => {}".format(ev))
		evtype = (ev & 0xF00000) >> 20
		if evtype == 9:
			note = (ev >> 8) & 0x7F
			col, row = self.get_note_xy(note)
			# scene change
			if col == 8:
				self.zynpad.set_bank(row + 1)
				return True
			# launch/stop pad
			pad = self.zynpad.get_pad_from_xy(col, row)
			if pad >= 0:
				self.zynseq.libseq.togglePlayState(self.zynpad.bank, pad)
				return True


	# Light-Off all LEDs
	def light_off(self):
		for row in range(8):
			for col in range(9):
				note = 16 * row + col
				lib_zyncore.dev_send_note_on(self.idev_out, 0, note, 0xC)


	def sleep_on(self):
		self.light_off()


	def sleep_off(self):
		self.refresh(force=True)


#------------------------------------------------------------------------------
