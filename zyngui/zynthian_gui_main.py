#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Main Menu Class
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

import logging

# Zynthian specific modules
from . import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian App Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_main(zynthian_gui_selector):

	def __init__(self):
		super().__init__('Main', True)


	def fill_list(self):
		self.list_data=[]

		# Layer & Snapshots
		self.list_data.append((self.layers,0,"Layers"))
		self.list_data.append((self.load_snapshot,0,"Load Snapshot"))
		if len(self.zyngui.screens['layer'].layers)>0:
			self.list_data.append((self.save_snapshot,0,"Save Snapshot"))

		self.list_data.append((None,0,"-----------------------------"))

		# Add list of Apps
		self.list_data.append((self.audio_recorder,0,"Audio Recorder"))
		self.list_data.append((self.midi_recorder,0,"MIDI Recorder"))
		self.list_data.append((self.alsa_mixer,0,"ALSA Mixer"))
		self.list_data.append((self.auto_eq,0,"Auto EQ"))

		self.list_data.append((None,0,"-----------------------------"))

		self.list_data.append((self.admin,0,"Admin"))

		super().fill_list()


	def select_action(self, i, t='S'):
		if self.list_data[i][0]:
			self.last_action=self.list_data[i][0]
			self.last_action()


	def layers(self):
		logging.info("Layers")
		self.zyngui.show_screen("layer")


	def load_snapshot(self):
		logging.info("Load Snapshot")
		self.zyngui.load_snapshot()


	def save_snapshot(self):
		logging.info("Save Snapshot")
		self.zyngui.save_snapshot()


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


	def admin(self):
		logging.info("Admin")
		self.zyngui.show_modal("admin")


	def set_select_path(self):
		self.select_path.set("Main")


#------------------------------------------------------------------------------
