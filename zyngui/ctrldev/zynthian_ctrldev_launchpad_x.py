#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Novation Launchpad X"
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <brian@riban.co.uk>
#                         Wapata <wapata.31@gmail.com>
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
from time import sleep

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_ctrldev_manager import zynthian_ctrldev_zynpad
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq

# ------------------------------------------------------------------------------------------------------------------
# Novation Launchpad X
# ------------------------------------------------------------------------------------------------------------------

class zynthian_ctrldev_launchpad_x(zynthian_ctrldev_zynpad):

	dev_ids = ["Launchpad_X_MIDI_1", "LPX_DAW"]

	PAD_COLOURS = [6, 29, 17, 49, 66, 41, 23, 13, 96, 2, 81, 82, 83, 84, 85, 86, 87]
	STARTING_COLOUR = 21
	STOPPING_COLOUR = 5

	def send_sysex(self, data):
		msg = bytes.fromhex("F0 00 20 29 02 0C {} F7".format(data))
		lib_zyncore.dev_send_midi_event(self.idev, msg, len(msg))
		sleep(0.05)


	def get_note_xy(self, note):
		row = 8 - (note // 10)
		col = (note % 10) - 1
		return col, row


	def init(self):
		# Awake
		self.sleep_off()
		# Enter DAW session mode
		self.send_sysex("10 01")
		# Select session layout (session = 0x00, faders = 0x0D)
		self.send_sysex("00 00")
		# Light off
		#self.light_off()


	def end(self):
		# Light off
		self.light_off()
		# Exit DAW session mode
		self.send_sysex("10 00")
		# Select Keys layout (drums = 0x04, keys = 0x05, user = 0x06, prog = 0x7F)
		self.send_sysex("00 05")


	# Zynpad Scene LED feedback
	def refresh_zynpad_bank(self):
		#logging.debug("Updating Launchpad X bank leds")
		for row in range(0, 8):
			note = 89 - 10 * row
			if row == self.zynpad.bank - 1:
				lib_zyncore.dev_send_ccontrol_change(self.idev, 0, note, 29)
			else:
				lib_zyncore.dev_send_ccontrol_change(self.idev, 0, note, 0)


	# Zynpad Pad LED feedback
	def update_pad(self, pad, state, mode):
		#logging.debug("Updating Launchpad X pad {}".format(pad))
		col, row = self.zynpad.get_xy_from_pad(pad)
		note = 10 * (8 - row) + col + 1

		group = self.zyngui.zynseq.libseq.getGroup(self.zynpad.bank, pad)
		try:
			if mode == 0:
				chan = 0
				vel = 0
			elif state == zynseq.SEQ_STOPPED:
				chan = 0
				vel = self.PAD_COLOURS[group]
			elif state == zynseq.SEQ_PLAYING:
				chan = 2
				vel = self.PAD_COLOURS[group]
			elif state == zynseq.SEQ_STOPPING:
				chan = 1
				vel = self.STOPPING_COLOUR
			elif state == zynseq.SEQ_STARTING:
				chan = 1
				vel = self.STARTING_COLOUR
			else:
				chan = 0
				vel = 0
		except:
			chan = 0
			vel = 0

		#logging.debug("Lighting PAD {}, group {} => {}, {}, {}".format(pad, group, chan, note, vel))
		lib_zyncore.dev_send_note_on(self.idev, chan, note, vel)


	def midi_event(self, ev):
		#logging.debug("Launchpad X MIDI handler => {}".format(ev))
		evtype = (ev & 0xF00000) >> 20
		# Note ON => launch/stop sequence
		if evtype == 0x9:
			note = (ev >> 8) & 0x7F
			val = ev & 0x7F
			if val > 0:
				col, row = self.get_note_xy(note)
				pad = self.zynpad.get_pad_from_xy(col, row)
				if pad >= 0:
					self.zyngui.zynseq.libseq.togglePlayState(self.zynpad.bank, pad)
			return True
		# CC => scene change
		elif evtype == 0xB:
			ccnum = (ev >> 8) & 0x7F
			val = ev & 0x7F
			if val > 0:
				if ccnum == 0x5B:
					self.zyngui.cuia_arrow_up()
				elif ccnum == 0x5C:
					self.zyngui.cuia_arrow_down()
				elif ccnum == 0x5D:
					self.zyngui.cuia_arrow_left()
				elif ccnum == 0x5E:
					self.zyngui.cuia_arrow_right()
				else:
					col, row = self.get_note_xy(ccnum)
					if col == 8:
						self.zynpad.set_bank(row + 1)
			return True


	# Light-Off LEDs
	def light_off(self):
		#logging.debug("Lighting Off LEDs Launchpad X")
		# Clean state of notes & CCs
		self.send_sysex("12 01 00 01")


	# Sleep On
	def sleep_on(self):
		# Sleep Mode (0 = sleep, 1 = awake)
		self.send_sysex("09 00")


	# Sleep On
	def sleep_off(self):
		# Sleep Mode (0 = sleep, 1 = awake)
		self.send_sysex("09 01")


#------------------------------------------------------------------------------
