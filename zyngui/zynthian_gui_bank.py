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
		super().__init__('Bank', True)

    
	def fill_list(self):
		if not self.zyngui.get_current_processor():
			logging.error("Can't fill bank list for None layer!")
			return
		self.zyngui.get_current_processor().load_bank_list()
		self.list_data = self.zyngui.get_current_processor().bank_list
		super().fill_list()


	def build_view(self):
		if self.zyngui.get_current_processor():
			self.index = self.zyngui.get_current_processor().get_bank_index()
			if self.zyngui.get_current_processor().get_show_fav_presets():
				if len(self.zyngui.get_current_processor().get_preset_favs()) > 0:
					self.index = 0
				else:
					self.current_processor.set_show_fav_presets(False)
			super().build_view()
		else:
			self.zyngui.close_screen()


	def show(self):
		if len(self.list_data) > 0:
			super().show()


	def select_action(self, i, t='S'):
		if self.list_data and self.list_data[i][0] == '*FAVS*':
			self.zyngui.get_current_processor().set_show_fav_presets(True)
		else:
			if self.zyngui.get_current_processor().set_bank(i) is None:
				self.build_view()
				return
			self.zyngui.get_current_processor().set_show_fav_presets(False)

		if len(self.list_data) <= 1:
			self.zyngui.replace_screen('preset')
		else:
			self.zyngui.show_screen('preset')

		# If bank is empty (no presets), jump to instrument control
		if len(self.zyngui.get_current_processor().preset_list) == 0 or self.zyngui.get_current_processor().preset_list[0][0] == "":
			self.zyngui.screens['preset'].select_action(0)


	def arrow_right(self):
		self.zyngui.chain_manager.next_chain()
		self.build_view()


	def arrow_left(self):
		self.zyngui.chain_manager.previous_chain()
		self.build_view()


	def topbar_bold_touch_action(self):
		self.zyngui.zynswitch_defered('B', 1)


	def show_bank_options(self):
		bank = copy.deepcopy(self.list_data[self.index])
		bank_name = bank[2]
		options = {}
		if self.zyngui.get_current_processor().engine.is_preset_user(bank):
			if hasattr(self.zyngui.get_current_processor().engine, "rename_user_bank"):
				options["Rename"] = bank
			if hasattr(self.zyngui.get_current_processor().engine, "delete_user_bank"):
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
		self.zyngui.get_current_processor().engine.rename_user_bank(self.list_data[self.options_bank_index], bank_name)
		self.zyngui.close_screen()


	def delete_bank(self, bank):
		self.zyngui.get_current_processor().engine.delete_user_bank(bank)
		self.zyngui.close_screen()


	# Function to handle *all* switch presses.
	#	swi: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	t: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def switch(self, swi, t='S'):
		if swi == 0:
			if t == 'S':
				self.arrow_right()
				return True
		elif swi == 2:
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
		if self.zyngui.get_current_processor():
			self.select_path.set(self.zyngui.get_current_processor().get_basepath())


#-------------------------------------------------------------------------------
