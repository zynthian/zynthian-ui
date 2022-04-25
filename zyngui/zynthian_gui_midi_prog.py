#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Midi Program Change Selector Class
# 
# Copyright (C) 2015-2021 Fernando Moyano <jofemodo@zynthian.org>
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
from zyngui.zynthian_gui_selector import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian MIDI Channel Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_midi_prog(zynthian_gui_selector):

	def __init__(self):
		self.cb_action = None
		super().__init__('Prog', True)


	def config(self, prg_num, cb_action):
		try:
			self.index = int(prg_num) + 1
		except:
			self.index = 0
		self.cb_action = cb_action


	def fill_list(self):
		self.list_data=[(-1,0,"None")]
		for i in range(0,128):
				self.list_data.append((i,i+1,str(i).zfill(2)))
		super().fill_list()


	def select_action(self, i, t='S'):
		if self.cb_action:
			self.cb_action(self.list_data[i][0])


	def set_select_path(self):
		self.select_path.set("Program Change...")


#------------------------------------------------------------------------------
