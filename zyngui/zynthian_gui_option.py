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

import logging
import os

# Zynthian specific modules
from zyngui.zynthian_gui_selector import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian Option Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_option(zynthian_gui_selector):

	def __init__(self):
		self.title = ""
		self.options = {}
		self.options_cb = None
		self.cb_select = None
		self.close_on_select = True
		super().__init__("Option", True)


	def config(self, title, options, cb_select, close_on_select=True):
		self.title = title
		if callable(options):
			self.options_cb = options
			self.options = None
		else:
			self.options_cb = None
			self.options = options
		self.cb_select = cb_select
		self.close_on_select = close_on_select
		self.index = 0


	def config_file_list(self, title, dpaths, fext, cb_select, close_on_select=True):
		self.title = title
		self.options = {}
		self.options_cb = None
		self.cb_select = cb_select
		self.close_on_select = close_on_select
		self.index = 0

		if isinstance(dpaths, str):
			dpaths = [dpaths]
		if isinstance(dpaths, (list, tuple)):
			for dpath in dpaths:
				try:
					for fname in sorted(os.listdir(dpath)):
						if fext and fext != ".*":
							fparts = os.path.splitext(fname)
							if fparts[1].lower() != fext.lower():
								continue
							fbase = fparts[0]
						else:
							fbase = fname

						fpath = os.path.join(dpath, fname)
						if os.path.isfile(fpath):
							self.options[fbase] = fpath
				except:
					pass


	def fill_list(self):
		i = 0
		self.list_data = []
		if self.options_cb:
			self.options = self.options_cb()
		for k, v in self.options.items():
			self.list_data.append((v, i, k))
			i += 1
		super().fill_list()


	def select_action(self, i, t='S'):
		if self.close_on_select:
			self.zyngui.close_screen()
		if self.cb_select and i < len(self.list_data):
			self.cb_select(self.list_data[i][2], self.list_data[i][0])
			if not self.close_on_select:
				self.fill_list()


	def set_select_path(self):
		self.select_path.set(self.title)

#------------------------------------------------------------------------------
