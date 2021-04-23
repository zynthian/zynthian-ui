#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Audio-In Selector Class
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

# Zynthian specific modules
import zynautoconnect
from . import zynthian_gui_config
from . import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian Audio-In Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_audio_in(zynthian_gui_selector):

	def __init__(self):
		self.layer=None
		super().__init__('Audio Capture', True)


	def set_layer(self, layer):
		self.layer = layer


	def fill_list(self):
		self.list_data = []

		for scp in zynautoconnect.get_audio_capture_ports():
			if scp.name in self.layer.get_audio_in():
				self.list_data.append((scp.name, scp.name, "[x] " + scp.name))
			else:
				self.list_data.append((scp.name, scp.name, "[  ] " + scp.name))

		super().fill_list()


	def fill_listbox(self):
		super().fill_listbox()


	def select_action(self, i, t='S'):
		self.layer.toggle_audio_in(self.list_data[i][1])
		self.fill_list()


	def set_select_path(self):
		self.select_path.set("Capture Audio from ...")


#------------------------------------------------------------------------------
