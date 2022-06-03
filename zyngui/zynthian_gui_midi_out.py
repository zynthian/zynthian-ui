#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI MIDI-Out Selector Class
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

import sys
import tkinter
import logging
from collections import OrderedDict

# Zynthian specific modules
import zynautoconnect
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian MIDI-Out Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_midi_out(zynthian_gui_selector):

	def __init__(self):
		self.end_layer = None
		super().__init__('MIDI Out', True)


	def set_layer(self, layer):
		try:
			self.end_layer = self.zyngui.screens['layer'].get_midichain_ends(layer)[0]
		except:
			self.end_layer = None


	def fill_list(self):
		self.list_data = []

		if self.end_layer:
			midi_outs = OrderedDict([
				["MIDI-OUT", "Hardware MIDI Out"],
				["NET-OUT", "Network MIDI Out" ]
			])
			for layer in zynthian_gui_config.zyngui.screens["layer"].get_midichain_roots():
				if layer.midi_chan!=self.end_layer.midi_chan:
					midi_outs[layer.get_midi_jackname()] = layer.get_presetpath()
				
			for jn, title in midi_outs.items():
				if jn in self.end_layer.get_midi_out():
					self.list_data.append((jn, jn, "[x] " + title))
				else:
					self.list_data.append((jn, jn, "[  ] " + title))

		super().fill_list()


	def fill_listbox(self):
		super().fill_listbox()
		#self.highlight()


	# Highlight current engine assigned outputs ...
	def highlight(self):
		for i in range(len(self.list_data)):
			if self.list_data[i][2][:2]=='[x':
				self.listbox.itemconfig(i, {'fg':zynthian_gui_config.color_hl})
			else:
				self.listbox.itemconfig(i, {'fg':zynthian_gui_config.color_panel_tx})


	def select_action(self, i, t='S'):
		self.end_layer.toggle_midi_out(self.list_data[i][1])
		self.fill_list()


	def set_select_path(self):
		self.select_path.set("Send MIDI to ...")

#------------------------------------------------------------------------------
