#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Akai MIDI-mix"
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
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
#* *****************************************************************************

import logging

# Zynthian specific modules
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynmixer
from zyncoder.zyncore import lib_zyncore

# --------------------------------------------------------------------------
# Akai MIDI-Mix Integration
# --------------------------------------------------------------------------


class zynthian_ctrldev_akai_midimix(zynthian_ctrldev_zynmixer):

	dev_ids = ["MIDI Mix MIDI 1"]

	rec_mode = 0

	bank_left_note = 25
	bank_right_note = 26
	solo_note = 27
	mute_notes = [1, 4, 7, 10, 13, 16, 19, 22]
	solo_notes = [2, 5, 8, 11, 14, 17, 20, 23]
	rec_notes = [3, 6, 9, 12, 15, 18, 21, 24]

	# knobs1_ccnum = [16, 20, 24, 28, 46, 50, 54, 58]
	# knobs2_ccnum = [17, 21, 25, 29, 47, 51, 55, 59]
	knobs3_ccnum = [18, 22, 26, 30, 48, 52, 56, 60]
	faders_ccnum = [19, 23, 27, 31, 49, 53, 57, 61]
	master_ccnum = 62

	# Function to initialise class
	def __init__(self, state_manager, idev_in, idev_out=None):
		super().__init__(state_manager, idev_in, idev_out)
		self.midimix_bank = 0
		self.chain_manager = self.state_manager.chain_manager

	def init(self):
		self.midimix_bank = 0
		self.light_off()

	def end(self):
		self.light_off()

	# Update LED status
	def update(self, chan, ctrl, value):
		if self.idev_out <= 0 or chan > 7:
			return
		if ctrl == "record":
			lib_zyncore.dev_send_note_on(self.idev_out, 0, self.rec_notes[chan], value)
		elif ctrl == "mute":
			lib_zyncore.dev_send_note_on(self.idev_out, 0, self.mute_notes[chan], value)
		elif ctrl == "solo":
			lib_zyncore.dev_send_note_on(self.idev_out, 0, self.solo_notes[chan], value)


	def refresh(self, force = False):
		if self.idev_out <= 0:
			return

		# Bank selection LED
		if self.midimix_bank:
			index0 = 8
			lib_zyncore.dev_send_note_on(self.idev_out, 0, self.bank_left_note, 0)
			lib_zyncore.dev_send_note_on(self.idev_out, 0, self.bank_right_note, 1)
		else:
			index0 = 0
			lib_zyncore.dev_send_note_on(self.idev_out, 0, self.bank_left_note, 1)
			lib_zyncore.dev_send_note_on(self.idev_out, 0, self.bank_right_note, 0)

		# Strips Leds
		for i in range(0, 8):
			index = index0 + i
			if index < len(self.zynmixer.zctrls):
				chain = self.chain_manager.get_chain_by_index(index + 1)
				mute = self.zynmixer.get_mute(index)
				solo = self.zynmixer.get_solo(index)
			else:
				chain = None
				mute = 0
				solo = 0

			if not self.rec_mode:
				if chain and chain == self.chain_manager.get_active_chain():
					rec = 1
				else:
					rec = 0
			else:
				if chain:
					rec = self.state_manager.audio_recorder.is_armed(chain.midi_chan)
				else:
					rec = 0

			lib_zyncore.dev_send_note_on(self.idev_out, 0, self.mute_notes[i], mute)
			lib_zyncore.dev_send_note_on(self.idev_out, 0, self.solo_notes[i], solo)
			lib_zyncore.dev_send_note_on(self.idev_out, 0, self.rec_notes[i], rec)

	def midi_event(self, ev):
		evtype = (ev & 0xF00000) >> 20
		if evtype == 0x9:
			note = (ev >> 8) & 0x7F
			if note == self.solo_note:
				return True
			elif note == self.bank_left_note:
				self.midimix_bank = 0
				self.refresh()
				return True
			elif note == self.bank_right_note:
				self.midimix_bank = 1
				self.refresh()
				return True
			elif note in self.mute_notes:
				index = self.mute_notes.index(note)
				if self.midimix_bank:
					index += 8
				if self.zynmixer.get_mute(index):
					val = 0
				else:
					val = 1
				self.zynmixer.set_mute(index, val, True)
				# Send LED feedback
				lib_zyncore.dev_send_note_on(self.idev_out, 0, note, val)
				return True
			elif note in self.solo_notes:
				index = self.solo_notes.index(note)
				if self.midimix_bank:
					index += 8
				if self.zynmixer.get_solo(index):
					val = 0
				else:
					val = 1
				self.zynmixer.set_solo(index, val, True)
				# Send LED feedback
				lib_zyncore.dev_send_note_on(self.idev_out, 0, note, val)
				return True
			elif note in self.rec_notes:
				index = self.rec_notes.index(note)
				if self.midimix_bank:
					index += 8
				if index < len(self.zynmixer.zctrls):
					if not self.rec_mode:
						self.chain_manager.set_active_chain_by_index(index + 1)
					else:
						chain = self.chain_manager.get_chain_by_index(index + 1)
						self.state_manager.audio_recorder.toggle_arm(chain.midi_chan)
						# Send LED feedback
						val = self.state_manager.audio_recorder.is_armed(chain.midi_chan)
						lib_zyncore.dev_send_note_on(self.idev_out, 0, note, val)
				return True
		elif evtype == 0xB:
			ccnum = (ev & 0x7F00) >> 8
			ccval = (ev & 0x007F)
			if ccnum == self.master_ccnum:
				self.zynmixer.set_level(255, ccval / 127.0)
				return True
			elif ccnum in self.faders_ccnum:
				index = self.faders_ccnum.index(ccnum)
				if self.midimix_bank:
					index += 8
				self.zynmixer.set_level(index, ccval/127.0, True)
				return True
			elif ccnum in self.knobs3_ccnum:
				index = self.knobs3_ccnum.index(ccnum)
				if self.midimix_bank:
					index += 8
				self.zynmixer.set_balance(index, 2.0 * ccval/127.0 - 1.0)
				return True

	# Light-Off all LEDs
	def light_off(self):
		for note in range(1, 28):
			lib_zyncore.dev_send_note_on(self.idev_out, 0, note, 0)

# ------------------------------------------------------------------------------

