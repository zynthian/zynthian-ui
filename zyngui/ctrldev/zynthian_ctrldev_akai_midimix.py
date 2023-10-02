#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Akai MIDI-mix"
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
from zyngui import zynthian_gui_config
from zyngui.zynthian_ctrldev_manager import zynthian_ctrldev_base
from zyncoder.zyncore import lib_zyncore

# --------------------------------------------------------------------------
# Akai MIDI-Mix Integration
# --------------------------------------------------------------------------

class zynthian_ctrldev_akai_midimix(zynthian_ctrldev_base):

	dev_id = "MIDI_Mix_MIDI_1"
	dev_zynmixer = True  # Can act as an audio mixer controller device

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
	def __init__(self):
		super().__init__()
		self.midimix_bank = 0
		self.zynmixer = self.zyngui.zynmixer
		self.zyngui_mixer = self.zyngui.screens["audio_mixer"]


	def init(self):
		self.midimix_bank = 0
		self.light_off()


	def end(self):
		self.light_off()


	# Update LED status
	def refresh(self, force = False):
		# Bank selection LED
		if self.midimix_bank:
			index0 = 8
			lib_zyncore.dev_send_note_on(self.idev, 0, self.bank_left_note, 0)
			lib_zyncore.dev_send_note_on(self.idev, 0, self.bank_right_note, 1)
		else:
			index0 = 0
			lib_zyncore.dev_send_note_on(self.idev, 0, self.bank_left_note, 1)
			lib_zyncore.dev_send_note_on(self.idev, 0, self.bank_right_note, 0)

		# Strips Leds
		layers = self.zyngui.screens['layer'].get_root_layers()
		for i in range(0, 8):
			index = index0 + i
			if index < len(self.zyngui.zynmixer.zctrls):
				mute = self.zyngui.zynmixer.get_mute(index)
				solo = self.zyngui.zynmixer.get_solo(index)
			else:
				mute = 0
				solo = 0

			if zynthian_gui_config.midi_single_active_channel:
				if self.zyngui.curlayer and index < len(layers) and layers[index] == self.zyngui.curlayer:
					rec = 1
				else:
					rec = 0
			else:
				if index < len(layers):
					rec = self.zyngui.audio_recorder.is_armed(layers[index].midi_chan)
				else:
					rec = 0

			lib_zyncore.dev_send_note_on(self.idev, 0, self.mute_notes[i], mute)
			lib_zyncore.dev_send_note_on(self.idev, 0, self.solo_notes[i], solo)
			lib_zyncore.dev_send_note_on(self.idev, 0, self.rec_notes[i], rec)


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
				lib_zyncore.dev_send_note_on(self.idev, 0, note, val)
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
				# Update Main "solo" control
				self.zyngui_mixer.pending_refresh_queue.add((self.zyngui_mixer.main_mixbus_strip, 'solo'))
				# Send LED feedback
				lib_zyncore.dev_send_note_on(self.idev, 0, note, val)
				return True
			elif note in self.rec_notes:
				index = self.rec_notes.index(note)
				if self.midimix_bank:
					index += 8
				if index < len(self.zynmixer.zctrls):
					if zynthian_gui_config.midi_single_active_channel:
						self.zyngui_mixer.select_chain_by_index(index)
					else:
						layers = self.zyngui.screens['layer'].get_root_layers()
						if index < len(layers):
							layer = layers[index]
							self.zyngui.audio_recorder.toggle_arm(layer.midi_chan)
							# Send LED feedback
							val = self.zyngui.audio_recorder.is_armed(layer.midi_chan)
							lib_zyncore.dev_send_note_on(self.idev, 0, note, val)
				return True
		elif evtype == 0xB:
			ccnum = (ev & 0x7F00) >> 8
			ccval = (ev & 0x007F)
			if ccnum == self.master_ccnum:
				self.zyngui_mixer.main_mixbus_strip.zctrls['level'].set_value(ccval/127.0)
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
			lib_zyncore.dev_send_note_on(self.idev, 0, note, 0)


#------------------------------------------------------------------------------
