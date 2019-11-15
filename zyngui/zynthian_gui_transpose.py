#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Transpose Selector Class
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
from zyncoder import *
from . import zynthian_gui_config
from . import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian Transpose Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_transpose(zynthian_gui_selector):

	def __init__(self):
		super().__init__('Transpose', True)


	def fill_list(self):
		self.list_data=[]
		for i in range(0,121):
			offset=i-60
			self.list_data.append((str(i),offset,str(offset)))
		super().fill_list()


	def show(self):
		offset=zyncoder.lib_zyncoder.get_midi_filter_transpose(self.get_layer_chan())
		self.index=60+offset
		super().show()


	def select_action(self, i, t='S'):
		zyncoder.lib_zyncoder.set_midi_filter_transpose(self.get_layer_chan(),self.list_data[i][1])
		self.zyngui.show_modal('layer_options')


	def back_action(self):
		self.zyngui.show_modal('layer_options')
		return ''


	def set_select_path(self):
		self.select_path.set("Transpose")


	def get_layer_chan(self):
		layer_index=self.zyngui.screens['layer_options'].layer_index
		return self.zyngui.screens['layer'].layers[layer_index].get_midi_chan()


#------------------------------------------------------------------------------
