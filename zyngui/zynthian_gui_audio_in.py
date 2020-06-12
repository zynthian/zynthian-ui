#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Audio-In Selector Class
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

class zynthian_gui_audio_in(zynthian_gui_selector):

	def __init__(self):
		self.layer=None
		super().__init__('Audio In', True)


	def set_layer(self, layer):
		self.layer = layer


	def fill_list(self):
		self.list_data = []

		for p in zynautoconnect.get_audio_capture_ports():
			# [1], [2] etc. to designate top effect inputs. Select to ++ those, wrapping to [ ].
			routed = self.layer.get_audio_in_targetport(p.name)

			if routed >= 0:
				title = "[{}] {}".format(routed + 1, p.name)
			else:
				title = "[ ] {}".format(p.name)

			self.list_data.append((p.name, p.name, title))

		super().fill_list()


	def fill_listbox(self):
		super().fill_listbox()

	def select_action(self, i, t='S'):
		self.layer.toggle_audio_in(self.list_data[i][1])
		self.fill_list()

	def back_action(self):
		self.zyngui.show_modal('layer_options')
		return ''


	def set_select_path(self):
		if self.layer and self.layer.get_basepath():
			self.select_path.set("Audio capture for {}".format(self.layer.get_basepath()))
		else:
			self.select_path.set("Audio Routing ...")

#------------------------------------------------------------------------------
