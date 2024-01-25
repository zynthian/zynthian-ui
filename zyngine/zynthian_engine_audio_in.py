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
	# ---------------------------------------------------------------------------
	# Config variables
	# ---------------------------------------------------------------------------

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------

	def __init__(self, zyngui=None, jackname=None):
		self._ctrl_screens = []
		super().__init__(zyngui)
		self.name = "Audio Input"
		self.nickname = "AI"
		self.type = "Audio Effect"

		if jackname:
			self.jackname = jackname
		else:
			self.jackname = self.get_next_jackname("audioin") # Should never be here

		self.options['audio_capture'] = True
		self.options['note_range'] = False
		self.options['clone'] = True

		self.reset()
		self.start()


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

	def get_bank_list(self, layer=None):
		return []

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
