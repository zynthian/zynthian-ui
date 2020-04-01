#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI App Selector Class
# 
# Copyright (C) 2015-2020 Fernando Moyano <jofemodo@zynthian.org>
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


import os
import sys
import logging
from collections import OrderedDict

# Zynthian specific modules
from . import zynthian_gui_config
from . import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian App Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_apps(zynthian_gui_selector):

	def __init__(self):
		super().__init__('Apps', True)


	def fill_list(self):
		self.list_data=[]

		# Add list of Apps
		self.list_data.append((self.audio_recorder,0,"Audio Recorder"))
		self.list_data.append((self.midi_recorder,0,"MIDI Recorder"))
		self.list_data.append((self.alsa_mixer,0,"ALSA Mixer"))
		self.list_data.append((self.auto_eq,0,"Auto EQ"))

		super().fill_list()


	def select_action(self, i, t='S'):
		if self.list_data[i][0]:
			self.last_action=self.list_data[i][0]
			self.last_action()


	def audio_recorder(self):
		logging.info("Audio Recorder")
		self.zyngui.show_modal("audio_recorder")


	def midi_recorder(self):
		logging.info("MIDI Recorder")
		self.zyngui.show_modal("midi_recorder")


	def alsa_mixer(self):
		logging.info("ALSA Mixer")
		self.zyngui.screens['layer'].layer_control_amixer()


	def auto_eq(self):
		logging.info("Auto EQ")
		self.zyngui.show_modal('autoeq')


	def set_select_path(self):
		self.select_path.set("Apps")


#------------------------------------------------------------------------------
