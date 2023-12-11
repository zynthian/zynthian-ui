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

from zyngine.zynthian_signal_manager import zynsigman

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

	# Initialize control device: setup, regisater signals, etc
	# It *SHOULD* be implemented by child class
	def init(self):
		logging.debug("Init() for {}: NOT IMPLEMENTED!".format(type(self).__name__))

	# End control device: restore initial state, unregister signals, etc
	# It *SHOULD* be implemented by child class
	def end(self):
		logging.debug("End() for {}: NOT IMPLEMENTED!".format(type(self).__name__))

	# Refresh full device status (LED feedback, etc)
	# It *SHOULD* be implemented by child class
	def refresh(self):
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
		self.cols = 8
		self.rows = 8
		self.zynseq = state_manager.zynseq
		super().__init__(state_manager, idev_in, idev_out)

	def init(self):
		self.refresh()
		# Register for zynseq updates
		zynsigman.register(zynsigman.S_STEPSEQ, self.zynseq.SS_SEQ_PLAY_STATE, self.update_seq_play_state)
		zynsigman.register(zynsigman.S_STEPSEQ, self.zynseq.SS_SEQ_REFRESH, self.refresh)

	def end(self):
		# Unregister from zynseq updates
		zynsigman.unregister(zynsigman.S_STEPSEQ, self.zynseq.SS_SEQ_PLAY_STATE, self.update_seq_play_state)
		zynsigman.unregister(zynsigman.S_STEPSEQ, self.zynseq.SS_SEQ_REFRESH, self.refresh)
		self.light_off()

	def update_seq_bank(self):
		"""Update hardware indicators for active bank and refresh sequence state as needed.
		*COULD* be implemented by child class
		"""
		pass

	def update_seq_play_state(self, bank, seq, state, mode):
		"""Update hardware indicators for a sequence (pad): playing state etc.
		*SHOULD* be implemented by child class

		bank - bank
		seq - sequence index
		state - sequence's state
		mode - sequence's mode
		"""
		logging.debug("Update sequence playing state for {}: NOT IMPLEMENTED!".format(type(self).__name__))

	def pad_off(self, col, row):
		"""Light-Off the pad specified with column & row
		*SHOULD* be implemented by child class
		"""
		pass

	def refresh(self):
		"""Refresh full device status (LED feedback, etc)
		*SHOULD* be implemented by child class
		"""
		if self.idev_out is None:
			return
		#self.light_off()
		self.update_seq_bank()
		for i in range(self.cols):
			for j in range(self.rows):
				if i >= self.zynseq.col_in_bank or j >= self.zynseq.col_in_bank:
					self.pad_off(i, j)
				else:
					seq = i * self.zynseq.col_in_bank + j
					state = self.zynseq.libseq.getPlayState(self.zynseq.bank, seq)
					mode = self.zynseq.libseq.getPlayMode(self.zynseq.bank, seq)
					self.update_seq_play_state(bank=self.zynseq.bank, seq=seq, state=state, mode=mode)

# ------------------------------------------------------------------------------------------------------------------
# Zynmixer control device base class
# ------------------------------------------------------------------------------------------------------------------


class zynthian_ctrldev_zynmixer(zynthian_ctrldev_base):

	dev_zynmixer = True		# Can act as a zynmixer trigger device

	def __init__(self, state_manager, idev_in, idev_out=None):
		self.zynmixer = state_manager.zynmixer
		self.chain_manager = state_manager.chain_manager
		super().__init__(state_manager, idev_in, idev_out)

	def init(self):
		self.refresh()
		zynsigman.register(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_SET_ACTIVE_CHAIN, self.update_mixer_active_chain)
		zynsigman.register(zynsigman.S_AUDIO_MIXER, self.zynmixer.SS_ZCTRL_SET_VALUE, self.update_mixer_strip)

	def end(self):
		zynsigman.unregister(zynsigman.CHAIN_MAN, self.chain_manager.SS_SET_ACTIVE_CHAIN, self.update_mixer_active_chain)
		zynsigman.unregister(zynsigman.S_AUDIO_MIXER, self.zynmixer.SS_ZCTRL_SET_VALUE, self.update_mixer_strip)
		self.light_off()

	def update_mixer_strip(self, chan, symbol, value):
		"""Update hardware indicators for a mixer strip: mute, solo, level, balance, etc.
		*SHOULD* be implemented by child class

		chan - Mixer strip index
		symbol - Control name
		value - Control value
		"""
		logging.debug(f"Update mixer strip for {type(self).__name__}: NOT IMPLEMENTED!")

	def update_mixer_active_chain(self, active_chain):
		"""Update hardware indicators for active_chain
		*SHOULD* be implemented by child class

		active_chain - Active chain
		"""
		logging.debug(f"Update mixer active chain for {type(self).__name__}: NOT IMPLEMENTED!")

# -----------------------------------------------------------------------------------------
