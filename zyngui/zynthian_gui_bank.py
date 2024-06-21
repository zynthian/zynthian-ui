#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Bank Selector Class
# 
# Copyright (C) 2015-2016 Fernando Moyano <jofemodo@zynthian.org>
#
# ******************************************************************************
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
# ******************************************************************************

import sys
import logging
import copy

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

# ------------------------------------------------------------------------------
# Zynthian Bank Selection GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_bank(zynthian_gui_selector):

	def __init__(self):
		super().__init__('Bank', True)

	def fill_list(self):
		proc = self.zyngui.get_current_processor()
		if not proc:
			logging.error("Can't fill bank list for None processor!")
			return
		#self.list_data = proc.bank_list
		# TODO: Can't optimize because of setBfree / Aeolus "bank anomaly"
		self.list_data = proc.get_bank_list()
		super().fill_list()

	def build_view(self):
		proc = self.zyngui.get_current_processor()
		if proc:
			self.index = proc.get_bank_index()
			if proc.get_show_fav_presets():
				if len(proc.get_preset_favs()) > 0:
					self.index = 0
				else:
					proc.set_show_fav_presets(False)
			return super().build_view()
		else:
			return False

	def show(self):
		if len(self.list_data) > 0:
			super().show()

	def select_action(self, i, t='S'):
		proc = self.zyngui.get_current_processor()
		if self.list_data and self.list_data[i][0] == '*FAVS*':
			proc.set_show_fav_presets(True)
		else:
			if proc.set_bank(i) is None:
				# More setup stages to progess
				self.build_view()
				return
			proc.set_show_fav_presets(False)

		# If only one bank, show to preset list
		if len(self.list_data) <= 1:
			self.zyngui.replace_screen('preset')
		else:
			self.zyngui.show_screen('preset')

		# If bank is empty (no presets), show instrument control
		if len(proc.preset_list) == 0 or proc.preset_list[0][0] == "":
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
		proc = self.zyngui.get_current_processor()
		bank = copy.deepcopy(self.list_data[self.index])
		bank_name = bank[2]
		title_user = False
		options = {}
		if hasattr(proc.engine, "create_user_bank"):
			options["New"] = "new bank"
		if proc.engine.is_preset_user(bank):
			if hasattr(proc.engine, "rename_user_bank"):
				options["Rename"] = bank
				title_user = True
			if hasattr(proc.engine, "delete_user_bank"):
				options["Delete"] = bank
				title_user = True
		if not options:
			options["No bank options!"] = None
		if title_user:
			title = f"Bank options: {bank_name}"
		else:
			title = "Bank options"
		self.zyngui.screens['option'].config(title, options, self.bank_options_cb)
		self.zyngui.show_screen('option')

	def show_menu(self):
		self.show_bank_options()

	def toggle_menu(self):
		if self.shown:
			self.show_menu()
		elif self.zyngui.current_screen == "option":
			self.close_screen()

	def bank_options_cb(self, option, bank):
		self.options_bank_index = self.index
		if option == "New":
			self.zyngui.show_keyboard(self.create_bank, bank)
		elif option == "Rename":
			self.zyngui.show_keyboard(self.rename_bank, bank[2])
		elif option == "Delete":
			self.zyngui.show_confirm("Do you really want to remove bank '{}' and delete all of its presets?".format(bank[2]), self.delete_bank, bank)

	def create_bank(self, bank_name):
		self.zyngui.get_current_processor().engine.create_user_bank(bank_name)
		self.zyngui.close_screen()

	def rename_bank(self, bank_name):
		self.zyngui.get_current_processor().engine.rename_user_bank(self.list_data[self.options_bank_index], bank_name)
		self.zyngui.close_screen()

	def delete_bank(self, bank):
		self.zyngui.get_current_processor().engine.delete_user_bank(bank)
		self.zyngui.close_screen()

	# Function to handle *all* switch presses.
	# swi: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	# t: Press type ["S"=Short, "B"=Bold, "L"=Long]
	# returns True if action fully handled or False if parent action should be triggered
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

	def set_selector(self, zs_hidden=False):
		super().set_selector(zs_hidden)

	def set_select_path(self):
		proc = self.zyngui.get_current_processor()
		if proc:
			self.select_path.set(proc.get_basepath())

# -------------------------------------------------------------------------------
