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
import logging

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

#-------------------------------------------------------------------------------
# Zynthian Preset/Instrument Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_preset(zynthian_gui_selector):

	def __init__(self):
		super().__init__('Preset', True)


	def fill_list(self):
		if not self.zyngui.curlayer:
			logging.error("Can't fill preset list for None layer!")
			return

		self.zyngui.curlayer.load_preset_list()
		self.list_data=self.zyngui.curlayer.preset_list
		super().fill_list()


	def show(self):
		if not self.zyngui.curlayer:
			logging.error("Can't show preset list for None layer!")
			return
		self.index=self.zyngui.curlayer.get_preset_index()
		super().show()


	def select_action(self, i, t='S'):
		if t=='S':
			self.zyngui.curlayer.set_preset(i)
			self.zyngui.show_screen('control')


	def show_options(self):
		preset = self.list_data[self.index]
		fname = preset[2]
		fav = "[  ] Favourite"
		if fname[0] == '*': fav = "[x] Favourite"
		options = {
			fav: preset,
			"Save": preset,
			"Rename": preset,
			"Delete": preset
		}
		self.zyngui.screens['option'].config("Preset %s" % fname, options, self.options_cb)
		self.zyngui.show_modal('option')


	def options_cb(self, option, preset):
		fpath=preset[0]
		fname=preset[2]

		if option[-9:] == "Favourite":
			self.zyngui.curlayer.toggle_preset_fav(preset)
		elif option == "Save":
			self.zyngui.show_keyboard(self.save_preset, fname)
		elif option == "Rename":
			self.zyngui.show_keyboard(self.rename_preset, fname)
		elif option == "Delete":
			self.delete_preset()
			pass

		self.update_list()


	def save_preset(self, name):
		#TODO Imnplement save preset (check if name changed and save / save as)
		fpath=self.list_data[self.index][0]
		fname=self.list_data[self.index][2]
		name = name.rstrip()
		if name == fname: #TODO Check bank
			#TODO Imnplement save
			pass
		else:
			#TODO Imnplement save as, show confirmation if overwritting
			pass


	def rename_preset(self, name):
		fpath=self.list_data[self.index][0]
		fname=self.list_data[self.index][2]
		name = name.rstrip()
		if name == fname:
			return
		try:
			self.zyngui.curlayer.engine.zynapi_rename_preset(fpath, fname)
			#TODO Reload presets which might mean updating cache, etc.
		except Exception as e:
			logging.warning("Failed to rename preset: %s", e)


	def delete_preset(self):
		fpath=self.list_data[self.index][0]
		fname=self.list_data[self.index][2]
		self.zyngui.show_confirm("Do you really want to delete %s" % (fname), self.delete_confirmed, fpath)


	def delete_confirmed(self, fpath):
		try:
			self.zyngui.curlayer.engine.zynapi_remove_preset(fpath)
		except Exception as e:
			logging.warning("Failed to delete preset: %s", e)


	# Function to handle *all* switch presses.
	#	swi: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	t: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def switch(self, swi, t='S'):
		if swi == 1:
			if t == 'S':
				if len(self.zyngui.curlayer.bank_list)>1:
					self.zyngui.show_modal('bank')
					return True
		elif swi == 2:
			if t == 'S':
				self.zyngui.toggle_favorites()
				return True
		elif swi == 3:
			if t == 'B':
				self.show_options()
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
