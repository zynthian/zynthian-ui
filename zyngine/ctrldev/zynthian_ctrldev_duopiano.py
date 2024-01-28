#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "riband wearable controller"
#
# Copyright (C) 2015-2024 Fernando Moyano <jofemodo@zynthian.org>
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
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_base

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore

# ------------------------------------------------------------------------------------------------------------------
# Duo Piano MIDI controller
# ------------------------------------------------------------------------------------------------------------------

class zynthian_ctrldev_duopiano(zynthian_ctrldev_base):
	counter = 0

	dev_ids = ["GENERAL MIDI 1"]

	def init(self):
		self.counter = 0
		self.keep_alive()

	""" Call regularly to keep piano alive
		TODO: Set period. Set caller. Enable only when driver enabled (default?).
	"""
	def keep_alive(self):
		if self.counter == 0:
			lib_zyncore.dev_send_note_on(self.idev_out, 0, 0, 0)
			self.counter = 10000
		self.counter -= 1

# ------------------------------------------------------------------------------
