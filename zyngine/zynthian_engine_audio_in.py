# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_audiopass)
#
# zynthian_engine implementation for dummy audio input (pass-through)
#
# Copyright (C) 2022 Brian Walton <riban@zynthian.org>
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
from itertools import count

from . import zynthian_engine

#------------------------------------------------------------------------------
# Audio Input Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_audio_in(zynthian_engine):
	_ai_count = count(1)

	# ---------------------------------------------------------------------------
	# Config variables
	# ---------------------------------------------------------------------------

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__(zyngui)
		self.name = "Audio Input"
		self.nickname = "AI"
		self.jackname = "audioin_{:03d}".format(next(self._ai_count))
		self.type = "Audio Effect"

		self.options['audio_capture'] = True
		self.options['note_range'] = False
		self.options['clone'] = False
		
		self.start()

		# MIDI Controllers
		self._ctrls = []

		# Controller Screens
		self._ctrl_screens = []

		self.reset()


	# ---------------------------------------------------------------------------
	# Subproccess Management & IPC
	# ---------------------------------------------------------------------------

	def start(self):
		pass


	def stop(self):
		pass


	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------


	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------


	# ---------------------------------------------------------------------------
	# Bank Management
	# ---------------------------------------------------------------------------

	# ---------------------------------------------------------------------------
	# Preset Management
	# ---------------------------------------------------------------------------

	#----------------------------------------------------------------------------
	# Controllers Management
	#----------------------------------------------------------------------------

	# ---------------------------------------------------------------------------
	# Specific functions
	# ---------------------------------------------------------------------------


	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

#******************************************************************************
