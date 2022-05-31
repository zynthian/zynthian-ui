#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Bank Selector Class
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
import copy

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian Bank Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_bank(zynthian_gui_selector):

	def __init__(self):
		self.buttonbar_config = [
			(1, 'CONTROL\n[mixer]'),
			(0, '\n[menu]'),
			(2, 'FAVORITES\n[snapshot]'),
			(3, 'PRESETS\n[options]')
		]
		super().__init__('Bank', True)

    
	def fill_list(self):
		if not self.zyngui.curlayer:
			logging.error("Can't fill bank list for None layer!")
			return
		self.zyngui.curlayer.load_bank_list()
		self.list_data = self.zyngui.curlayer.bank_list
		super().fill_list()


	def show(self):
		if self.zyngui.curlayer:
			self.index = self.zyngui.curlayer.get_bank_index()
			if self.zyngui.curlayer.get_show_fav_presets():
				if len(self.zyngui.curlayer.get_preset_favs())>0:
					self.index = 0
				else:
					self.curlayer.set_show_fav_presets(False)
			super().show()
		else:
			self.zyngui.close_screen()


	def select_action(self, i, t='S'):
		if self.list_data[i][0] == '*FAVS*':
			self.zyngui.curlayer.set_show_fav_presets(True)
		else:
			if not self.zyngui.curlayer.set_bank(i):
				self.show()
				return
			else:
				self.zyngui.curlayer.set_show_fav_presets(False)

		self.zyngui.show_screen('preset')

		# If bank is empty (no presets), jump to instrument control
		if len(self.zyngui.curlayer.preset_list) == 0 or self.zyngui.curlayer.preset_list[0][0] == "":
			self.zyngui.screens['preset'].select_action(0)


	def show_bank_options(self):
		bank = copy.deepcopy(self.list_data[self.index])
		bank_name = bank[2]
		options = {}
		if self.zyngui.curlayer.engine.is_preset_user(bank):
			if hasattr(self.zyngui.curlayer.engine, "rename_user_bank"):
				options["Rename"] = bank
			if hasattr(self.zyngui.curlayer.engine, "delete_user_bank"):
				options["Delete"] = bank
		self.zyngui.screens['option'].config("Bank: {}".format(bank_name), options, self.bank_options_cb)
		if len(options):
			self.zyngui.show_screen('option')


	def bank_options_cb(self, option, bank):
		self.options_bank_index = self.index
		if option == "Rename":
			self.zyngui.show_keyboard(self.rename_bank, bank[2])
		elif option == "Delete":
			self.zyngui.show_confirm("Do you really want to remove bank '{}' and delete all of its presets?".format(bank[2]), self.delete_bank, bank)


	def rename_bank(self, bank_name):
		self.zyngui.curlayer.engine.rename_user_bank(self.list_data[self.options_bank_index], bank_name)
		self.zyngui.close_screen()


	def delete_bank(self, bank):
		self.zyngui.curlayer.engine.delete_user_bank(bank)
		self.zyngui.close_screen()


	# Function to handle *all* switch presses.
	#	swi: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	t: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def switch(self, swi, t='S'):
		if swi == 2:
			if t == 'S':
				self.zyngui.show_favorites()
				return True
		elif swi == 3:
			if t == 'B':
				self.show_bank_options()
				return True
		return False


	def set_selector(self, zs_hiden=False):
		super().set_selector(zs_hiden)


	def set_select_path(self):
		if self.zyngui.curlayer:
			self.select_path.set(self.zyngui.curlayer.get_basepath())


#-------------------------------------------------------------------------------
