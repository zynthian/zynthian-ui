#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Audio-Out Selector Class
# 
# Copyright (C) 2015-2018 Fernando Moyano <jofemodo@zynthian.org>
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

# Zynthian specific modules
import zynautoconnect
from . import zynthian_gui_config
from . import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian Audio-Out Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_audio_out(zynthian_gui_selector):

	def __init__(self):
		self.layer=None
		self.end_layer = None
		super().__init__('Audio Out', True)


	def set_layer(self, layer):
		self.layer = layer
		try:
			self.end_layer = self.zyngui.screens['layer'].get_fxchain_ends(self.layer)[0]
		except:
			self.end_layer = None


	def fill_list(self):
		self.list_data = []

		for k in zynautoconnect.get_audio_input_ports().keys():
			try:
				title = self.zyngui.screens['layer'].get_layer_by_jackname(k).get_basepath()
			except:
				title = k

			try:
				ch = int(title.split('#')[0])-1
				if ch==self.layer.midi_chan:
					continue
			except Exception as e:
				#logging.debug("Can't get layer's midi chan => {}".format(e))
				pass

			if self.end_layer and k in self.end_layer.get_audio_out():
				self.list_data.append((k, k, "[x] " + title))
			else:
				self.list_data.append((k, k, "[  ] " + title))

		super().fill_list()


	def fill_listbox(self):
		super().fill_listbox()


	def select_action(self, i, t='S'):
		self.end_layer.toggle_audio_out(self.list_data[i][1])
		self.fill_list()


	def set_select_path(self):
		self.select_path = ("Send Audio to ...")

#------------------------------------------------------------------------------
