#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI MIDI-In Selector Class
# 
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
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
import zynautoconnect
from zyncoder.zyncore import lib_zyncore
from zyngui.zynthian_gui_selector import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian MIDI-In Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_midi_in(zynthian_gui_selector):

	def __init__(self):
		self.root_layer = None
		super().__init__('MIDI In', True)


	def set_layer(self, layer):
		try:
			self.root_layer = self.zyngui.screens['layer'].get_midichain_root(layer)
		except:
			self.root_layer = None


	def fill_list(self):
		self.list_data = []

		if self.root_layer:
			midi_ins = []
			# USB connected device ports
			for i in range(0, 15):
				dev_id = zynautoconnect.devices_in[i]
				if dev_id:
					midi_ins.append(dev_id.replace("_", " "))
			# Hardcoded ports
			midi_ins.append("Network MIDI-IN")

			for i, devname in enumerate(midi_ins):
				# Check mode (Omni/Multi)
				if lib_zyncore.zmip_get_flag_active_chan(i):
					mode = "OMNI"
				else:
					mode = "MULTI"
				if lib_zyncore.zmop_get_route_from(self.root_layer.midi_chan, i):
					self.list_data.append((i, 0, "[x] " + mode + " - " + devname))
				else:
					self.list_data.append((i, 1, "[  ] " + mode + " - " + devname))

		super().fill_list()


	def fill_listbox(self):
		super().fill_listbox()


	def select_action(self, i, t='S'):
		if t == 'S':
			route = self.list_data[i][1]
			lib_zyncore.zmop_set_route_from(self.root_layer.midi_chan, i, route)
		elif t == 'B':
			lib_zyncore.zmip_toggle_flag_active_chan(i)
		self.fill_list()


	def set_select_path(self):
		self.select_path.set("Capture MIDI from ...")

#------------------------------------------------------------------------------
