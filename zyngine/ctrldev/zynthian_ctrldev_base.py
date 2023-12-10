#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Control Device Manager Class
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
# ******************************************************************************

import logging
from zyngui import zynthian_gui_config

# ------------------------------------------------------------------------------------------------------------------
# Control device base class
# ------------------------------------------------------------------------------------------------------------------


class zynthian_ctrldev_base:

	dev_ids = []			# String list that could identify the device
	dev_id = None  			# String that identifies the device
	fb_dev_id = None		# Index of zmop connected to controller input
	dev_zynpad = False		# Can act as a zynpad trigger device
	dev_zynmixer = False    # Can act as an audio mixer controller device
	dev_pated = False		# Can act as a pattern editor device
	enabled = False			# True if device driver is enabled

	# Function to initialise class
	def __init__(self, state_manager, idev_in, idev_out=None):
		self.state_manager = state_manager
		self.idev = idev_in		       # Slot index where the input device is connected, starting from 1 (0 = None)
		self.idev_out = idev_out       # Slot index where the output device (feedback), if any, is connected, starting from 1 (0 = None)
		self.init()

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

	def __init__(self, state_manager, idev_in, idev_out=None):
		self.zynseq = state_manager.zynseq
		super().__init__(state_manager, idev_in, idev_out)

	# It *SHOULD* be implemented by child class
	def refresh_zynpad_bank(self):
		#logging.debug("Refressh zynpad banks for {}: NOT IMPLEMENTED!".format(type(self).__name__))
		pass

	# It *SHOULD* be implemented by child class
	def update_pad(self, pad, state, mode):
		logging.debug("Update pads for {}: NOT IMPLEMENTED!".format(type(self).__name__))

# -----------------------------------------------------------------------------------------


# ------------------------------------------------------------------------------------------------------------------
# Zynmixer control device base class
# ------------------------------------------------------------------------------------------------------------------

class zynthian_ctrldev_zynmixer(zynthian_ctrldev_base):

	dev_zynmixer = True		# Can act as a zynmixer trigger device

	def __init__(self, state_manager, idev_in, idev_out=None):
		self.zynmixer = state_manager.zynmixer
		self.chain_manager = state_manager.chain_manager
		super().__init__(state_manager, idev_in, idev_out)

	def update_mixer(self, channel, symbol, value):
		"""Update hardware indications
		*SHOULD* be implemented by child class

		chan - Mixer strip index
		ctrl - Control name
		value - Control value
		"""
		
		logging.debug(f"Update mixer for {type(self).__name__}: NOT IMPLEMENTED!")
# -----------------------------------------------------------------------------------------
