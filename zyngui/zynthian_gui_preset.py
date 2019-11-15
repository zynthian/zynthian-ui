#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Preset Selector Class
# 
# Copyright (C) 2015-2016 Fernando Moyano <jofemodo@zynthian.org>
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
import logging

# Zynthian specific modules
from . import zynthian_gui_config
from . import zynthian_gui_selector

#-------------------------------------------------------------------------------
# Zynthian Preset/Instrument Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_preset(zynthian_gui_selector):

	def __init__(self):
		super().__init__('Preset', True)
      
      
	def fill_list(self):
		self.zyngui.curlayer.load_preset_list()
		self.list_data=self.zyngui.curlayer.preset_list
		super().fill_list()


	def show(self):
		self.index=self.zyngui.curlayer.get_preset_index()
		super().show()


	def select_action(self, i, t='S'):
		self.zyngui.curlayer.set_preset(i)
		self.zyngui.show_screen('control')


	def preselect_action(self):
		return self.zyngui.curlayer.preload_preset(self.index)


	def restore_preset(self):
		return self.zyngui.curlayer.restore_preset()


	def set_select_path(self):
		if self.zyngui.curlayer:
			self.select_path.set(self.zyngui.curlayer.get_bankpath())

#------------------------------------------------------------------------------
