#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Control Device Manager Class
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

#------------------------------------------------------------------------------------------------------------------
# Control device base class
#------------------------------------------------------------------------------------------------------------------

class zynthian_ctrldev_base():

	dev_ids = []			# String list that could identify the device
	dev_id = None  			# String that identifies the device
	dev_zynpad = False		# Can act as a zynpad trigger device
	dev_zynmixer = False	# Can act as an audio mixer controller device
	dev_pated = False		# Can act as a pattern editor device
	enabled = False			# True if device driver is enabled


	# Function to initialise class
	def __init__(self):
		self.idev = 0		# Slot index where the input device is connected, starting from 1 (0 = None)
		self.idev_out = 0	# Slot index where the output device (feedback), if any, is connected, starting from 1 (0 = None)

	# Refresh device status (LED feedback, etc)
	# It *SHOULD* be implemented by child class
	def refresh(self, force=False):
		logging.debug("Refresh LEDs for {}: NOT IMPLEMENTED!".format(type(self).__name__))


	# Device MIDI event handler
	# It *SHOULD* be implemented by child class
	def midi_event(self, ev):
		logging.debug("MIDI EVENT FROM '{}'".format(type(self).__name__))


	# Light-Off LEDs
	# It *SHOULD* be implemented by child class
	def light_off(self):
		logging.debug("Lighting Off LEDs for {}: NOT IMPLEMENTED!".format(type(self).__name__))


	# Sleep On
	# It *COULD* be improved by child class
	def sleep_on(self):
		self.light_off()


	# Sleep On
	# It *COULD* be improved by child class
	def sleep_off(self):
		self.refresh(True)


# ------------------------------------------------------------------------------------------------------------------
# Zynpad control device base class
# ------------------------------------------------------------------------------------------------------------------

class zynthian_ctrldev_zynpad(zynthian_ctrldev_base):

	dev_zynpad = True		# Can act as a zynpad trigger device

	def __init__(self):
		super().__init__()


	def refresh(self, force=False):
		return #TODO: Implement refresh
		# When zynpad is shown, this is done by refresh_status, so no need to refresh twice
		if force or not self.zynpad.shown:
			self.refresh_pads(force)
		if force:
			self.refresh_zynpad_bank()


	# It *SHOULD* be implemented by child class
	def refresh_zynpad_bank(self):
		#logging.debug("Refressh zynpad banks for {}: NOT IMPLEMENTED!".format(type(self).__name__))
		pass


	def refresh_pads(self, force=False):
		if force:
			self.light_off()
		for pad in range(self.zynseq.col_in_bank ** 2):
			# It MUST be called for cleaning the dirty bit
			changed_state = self.zynseq.libseq.hasSequenceChanged(self.zynpad.bank, pad)
			if changed_state or force:
				mode = self.zynseq.libseq.getPlayMode(self.zynpad.bank, pad)
				state = self.zynpad.get_pad_state(pad)
				self.update_pad(pad, state, mode)


	def refresh_pad(self, pad, force=False):
		# It MUST be called for cleaning the dirty bit!!
		changed_state = self.zynseq.libseq.hasSequenceChanged(self.zynpad.bank, pad)
		if changed_state or force:
			mode = self.zynseq.libseq.getPlayMode(self.zynpad.bank, pad)
			state = self.zynpad.get_pad_state(pad)
			self.update_pad(pad, state, mode)


	# It *SHOULD* be implemented by child class
	def update_pad(self, pad, state, mode):
		logging.debug("Update pads for {}: NOT IMPLEMENTED!".format(type(self).__name__))

#-----------------------------------------------------------------------------------------
