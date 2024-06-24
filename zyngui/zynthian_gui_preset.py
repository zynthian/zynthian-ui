#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Preset Selector Class
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
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
import copy
import logging

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

# -------------------------------------------------------------------------------
# Zynthian Preset/Instrument Selection GUI Class
# -------------------------------------------------------------------------------


class zynthian_gui_preset(zynthian_gui_selector):

	def __init__(self):
		super().__init__('Preset', True)

	def fill_list(self):
		proc = self.zyngui.get_current_processor()
		if not proc:
			logging.error("Can't fill preset list for None processor!")
			return
		proc.load_preset_list()
		self.list_data = proc.preset_list
		super().fill_list()

	def build_view(self):
		if self.zyngui.get_current_processor():
			return super().build_view()
		else:
			return False

	def show(self):
		if len(self.list_data) > 0:
			super().show()

	def select_action(self, i, t='S'):
		if t == 'S':
			self.zyngui.state_manager.start_busy("set preset")
			self.zyngui.get_current_processor().set_preset(i)
			self.zyngui.state_manager.end_busy("set preset")
			self.zyngui.purge_screen_history("bank")
			self.zyngui.replace_screen("control")

	def arrow_right(self):
		active = self.zyngui.chain_manager.active_chain_id
		if active != self.zyngui.chain_manager.next_chain():
			self.zyngui.chain_control()

	def arrow_left(self):
		active = self.zyngui.chain_manager.active_chain_id
		if active != self.zyngui.chain_manager.previous_chain():
			self.zyngui.chain_control()

	def show_preset_options(self):
		preset = copy.deepcopy(self.list_data[self.index])
		if preset[2][0] == "❤":
			preset[2] = preset[2][1:]
		preset_name = preset[2]
		options = {}
		proc = self.zyngui.get_current_processor()
		if proc.engine.is_preset_fav(preset):
			options["\u2612 Favourite"] = preset
		else:
			options["\u2610 Favourite"] = preset
		if proc.engine.is_preset_user(preset):
			if hasattr(proc.engine, "rename_preset"):
				options["Rename"] = preset
			if hasattr(proc.engine, "delete_preset"):
				options["Delete"] = preset
		self.zyngui.screens['option'].config("Preset: {}".format(preset_name), options, self.preset_options_cb)
		self.zyngui.show_screen('option')

	def show_menu(self):
		self.show_preset_options()

	def toggle_menu(self):
		if self.shown:
			self.show_menu()
		elif self.zyngui.current_screen == "option":
			self.close_screen()

	def preset_options_cb(self, option, preset):
		if option.endswith("Favourite"):
			proc = self.zyngui.get_current_processor()
			proc.toggle_preset_fav(preset)
			proc.load_preset_list()
			self.show_preset_options()
		elif option == "Rename":
			self.zyngui.show_keyboard(self.rename_preset, preset[2])
		elif option == "Delete":
			self.delete_preset(preset)

	def rename_preset(self, new_name):
		preset = self.list_data[self.index]
		new_name = new_name.strip()
		if new_name != preset[2]:
			proc = self.zyngui.get_current_processor()
			try:
				# TODO: Confirm rename if overwriting existing preset or duplicate name
				proc.engine.rename_preset(proc.bank_info, preset, new_name)
				if preset[0] == proc.preset_info[0]:
					self.zyngui.state_manager.start_busy("set preset")
					proc.set_preset_by_id(preset[0])
					self.fill_list()
					self.zyngui.state_manager.end_busy("set preset")
			except Exception as e:
				logging.error("Failed to rename preset => {}".format(e))

	def delete_preset(self, preset):
		self.zyngui.show_confirm("Do you really want to delete '{}'?".format(preset[2]), self.delete_preset_confirmed, preset)

	def delete_preset_confirmed(self, preset):
		try:
			proc = self.zyngui.get_current_processor()
			count = proc.engine.delete_preset(proc.bank_info, preset)
			proc.remove_preset_fav(preset)
			self.fill_list()
			if count == 0:
				self.zyngui.close_screen()
		except Exception as e:
			logging.error("Failed to delete preset => {}".format(e))

	# Function to handle *all* switch presses.
	#	swi: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	t: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def switch(self, swi, t='S'):
		if swi == 0:
			if t == 'S':
				self.arrow_right()
				return True
		elif swi == 1:
			if t == 'S':
				if len(self.zyngui.get_current_processor().get_bank_list()) > 1:
					self.zyngui.replace_screen('bank')
					return True
		elif swi == 2:
			if t == 'S':
				self.zyngui.toggle_favorites()
				return True
		elif swi == 3:
			if t == 'B':
				self.show_preset_options()
				return True
		return False

	def cuia_toggle_play(self):
		try:
			if self.zyngui.get_current_processor().engine.nickname == "AP":
				self.click_listbox()
		except:
			pass

	def set_selector(self, zs_hidden=False):
		super().set_selector(zs_hidden)

	def preselect_action(self):
		self.zyngui.state_manager.start_busy("preselect preset")
		res = self.zyngui.get_current_processor().preload_preset(self.index)
		self.zyngui.state_manager.end_busy("preselect preset")
		return res

	def restore_preset(self):
		return self.zyngui.get_current_processor().restore_preset()

	def set_select_path(self):
		proc = self.zyngui.get_current_processor()
		if proc:
			if proc.show_fav_presets:
				self.select_path.set(proc.get_basepath() + " > Favorites")
			else:
				self.select_path.set(proc.get_bankpath())

# ------------------------------------------------------------------------------
