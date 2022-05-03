#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Option Selector Class
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
from zyngui.zynthian_gui_selector import zynthian_gui_selector
from . import zynthian_gui_config

#------------------------------------------------------------------------------
# Zynthian Option Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_option(zynthian_gui_selector):

	def __init__(self):
		self.title = ""
		self.options = []
		self.cb_select = None
		super().__init__("Option", True)


	def config(self, title, options, cb_select):
		self.title = title
		self.options = options
		self.cb_select = cb_select


	def fill_list(self):
		i=0
		self.list_data=[]
		for k,v in self.options.items():
			self.list_data.append((v,i,k))
			i += 1
		super().fill_list()


	def fill_listbox(self):
		super().fill_listbox()
		for i, val in enumerate(self.list_data):
			if val[0]==None:
				self.listbox.itemconfig(i, {'bg':zynthian_gui_config.color_panel_hl,'fg':zynthian_gui_config.color_tx_off})


	def select_action(self, i, t='S'):
		if self.cb_select:
			self.cb_select(self.list_data[i][2], self.list_data[i][0])
		#self.zyngui.close_screen()


	def set_select_path(self):
		self.select_path.set(self.title)

#------------------------------------------------------------------------------
