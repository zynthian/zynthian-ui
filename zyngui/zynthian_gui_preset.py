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
import copy
import logging

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

#-------------------------------------------------------------------------------
# Zynthian Preset/Instrument Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_preset(zynthian_gui_selector):

	def __init__(self):
		self.buttonbar_config = [
			(1, 'BANKS\n[mixer]'),
			(0, '\n[menu]'),
			(2, 'FAVORITES\n[snapshot]'),
			(3, 'SELECT\n[options]')
		]
		super().__init__('Preset', True)


	def fill_list(self):
		if not self.zyngui.curlayer:
			logging.error("Can't fill preset list for None layer!")
			return

		self.zyngui.curlayer.load_preset_list()
		self.list_data=self.zyngui.curlayer.preset_list
		super().fill_list()


	def show(self):
		if self.zyngui.curlayer:
			if len(self.zyngui.curlayer.bank_list) > 1:
				self.set_buttonbar_label(0, 'BANKS\n[mixer]')
			else:
				self.set_buttonbar_label(0, 'CONTROL\n[mixer]')
			super().show()
		else:
			self.zyngui.close_screen()


	def select_action(self, i, t='S'):
		if t=='S':
			self.zyngui.curlayer.set_preset(i)
			self.zyngui.show_screen_reset('control')


	def show_preset_options(self):
		preset = copy.deepcopy(self.list_data[self.index])
		if preset[2][0] == "❤": preset[2] = preset[2][1:]
		preset_name = preset[2]
		options = {}
		if self.zyngui.curlayer.engine.is_preset_fav(preset):
			options["[x] Favourite"] = preset
		else:
			options["[  ] Favourite"] = preset
		if self.zyngui.curlayer.engine.is_preset_user(preset):
			if hasattr(self.zyngui.curlayer.engine, "rename_preset"):
				options["Rename"] = preset
			if hasattr(self.zyngui.curlayer.engine, "delete_preset"):
				options["Delete"] = preset
		self.zyngui.screens['option'].config("Preset: {}".format(preset_name), options, self.preset_options_cb)
		self.zyngui.show_screen('option')


	def preset_options_cb(self, option, preset):
		if option.endswith("Favourite"):
			self.zyngui.curlayer.toggle_preset_fav(preset)
			self.zyngui.curlayer.load_preset_list()
			# Clumsey way to repopulate options screen by hide then show
			self.zyngui.close_screen()
			self.show_preset_options()
		elif option == "Rename":
			self.zyngui.show_keyboard(self.rename_preset, preset[2])
		elif option == "Delete":
			self.delete_preset(preset)


	def rename_preset(self, new_name):
		preset = self.list_data[self.index]
		new_name = new_name.strip()
		if new_name != preset[2]:
			try:
				self.zyngui.curlayer.engine.rename_preset(self.zyngui.curlayer.bank_info, preset, new_name)
				self.zyngui.close_screen()
				if preset[0]==self.zyngui.curlayer.preset_info[0]:
					self.zyngui.curlayer.set_preset_by_id(preset[0])
			except Exception as e:
				logging.error("Failed to rename preset => {}".format(e))


	def delete_preset(self, preset):
		self.zyngui.show_confirm("Do you really want to delete '{}'?".format(preset[2]), self.delete_preset_confirmed, preset)


	def delete_preset_confirmed(self, preset):
		try:
			count = self.zyngui.curlayer.engine.delete_preset(self.zyngui.curlayer.bank_info, preset)
			self.zyngui.curlayer.remove_preset_fav(preset)
			self.zyngui.close_screen()
			if count == 0:
				self.zyngui.close_screen()
		except Exception as e:
			logging.error("Failed to delete preset => {}".format(e))


	# Function to handle *all* switch presses.
	#	swi: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	t: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def switch(self, swi, t='S'):
		if swi == 1:
			if t == 'S':
				if len(self.zyngui.curlayer.bank_list) > 1:
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

		self.restore_preset()
		return False


	def set_selector(self, zs_hiden=False):
		super().set_selector(zs_hiden)


	def preselect_action(self):
		return self.zyngui.curlayer.preload_preset(self.index)


	def restore_preset(self):
		return self.zyngui.curlayer.restore_preset()


	def set_select_path(self):
		if self.zyngui.curlayer:
			if self.zyngui.curlayer.show_fav_presets:
				self.select_path.set(self.zyngui.curlayer.get_basepath() + " > Favorites")
			else:
				self.select_path.set(self.zyngui.curlayer.get_bankpath())

#------------------------------------------------------------------------------
