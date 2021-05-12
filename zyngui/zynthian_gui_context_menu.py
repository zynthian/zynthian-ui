#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Generic Context Menu Class
# 
# Copyright (C) 2015-2021 Fernando Moyano <jofemodo@zynthian.org>
# Copyright (C) 2015-2021 Brian Walton <riban@zynthian.org>
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

#------------------------------------------------------------------------------
# Zynthian Generic Context Menu GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_context_menu(zynthian_gui_selector):


	def __init__(self):
		super().__init__('Context menu', True)


	#	Configure context menu (before show)
	#	title: Title to show at top of context menu
	#	data: list of menu entries, each entry consists of a tuple of [function, function params (as list), title]
	def config(self, title, data):
		self.selector_caption = title
		self.list_data = data
		

	def show(self):
		self.fill_list()
		super().show()


	def select_action(self, i, t='S'):
		self.index = i
		try:
			self.list_data[i][0](*self.list_data[i][1])
		except:
			logging.warning("Failed to execute context menu item %d", i)


	def back_action(self):
		return None

#------------------------------------------------------------------------------
