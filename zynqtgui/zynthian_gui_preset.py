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
from . import zynthian_gui_config
from . import zynthian_gui_selector

# Qt modules
from PySide2.QtCore import Qt, QObject, Slot, Signal, Property

#-------------------------------------------------------------------------------
# Zynthian Preset/Instrument Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_preset(zynthian_gui_selector):

	buttonbar_config = [
		(1, 'BACK'),
		(0, 'LAYER'),
		(2, 'FAVS'),
		(3, 'SELECT')
	]

	def __init__(self, parent = None):
		super(zynthian_gui_preset, self).__init__('Preset', parent)
		self.show()
      
      
	def fill_list(self):
		if not self.zyngui.curlayer:
			logging.error("Can't fill preset list for None layer!")
			return

		self.zyngui.curlayer.load_preset_list()
		if not self.zyngui.curlayer.preset_list:
			self.set_select_path()
			self.zyngui.curlayer.load_preset_list()

		self.list_data=self.zyngui.curlayer.preset_list
		super().fill_list()


	def show(self, show_fav_presets=None):
		if not self.zyngui.curlayer:
			logging.error("Can't show preset list for None layer!")
			return

		self.select(self.zyngui.curlayer.get_preset_index())
		if not self.zyngui.curlayer.get_preset_name():
			self.zyngui.curlayer.set_preset(self.zyngui.curlayer.get_preset_index())

		super().show()


	def select_action(self, i, t='S'):
		if t=='S':
			self.zyngui.curlayer.set_preset(i)
			self.zyngui.screens['control'].show()
			self.zyngui.screens['layer'].fill_list()
		else:
			self.zyngui.curlayer.toggle_preset_fav(self.list_data[i])
			self.update_list()

	def index_supports_immediate_activation(self, index=None):
		return True

	#def back_action(self):
		#if self.show_fav_presets:
			#self.disable_show_fav_presets()
			#return ''
		#else:
			#return None


	def preselect_action(self):
		return self.zyngui.curlayer.preload_preset(self.index)


	def restore_preset(self):
		return self.zyngui.curlayer.restore_preset()

	def set_show_only_favorites(self, show):
		if show:
			self.enable_show_fav_presets()
		else:
			self.disable_show_fav_presets()

	def get_show_only_favorites(self):
		return self.zyngui.curlayer.show_fav_presets

	def enable_show_fav_presets(self):
		if not self.zyngui.curlayer.show_fav_presets:
			self.zyngui.curlayer.show_fav_presets = True
			self.set_select_path()
			self.update_list()
			self.show_only_favorites_changed.emit()
			if self.zyngui.curlayer.get_preset_name():
				self.zyngui.curlayer.set_preset_by_name(self.zyngui.curlayer.get_preset_name())


	def disable_show_fav_presets(self):
		if self.zyngui.curlayer.show_fav_presets:
			self.zyngui.curlayer.show_fav_presets = False
			self.set_select_path()
			self.update_list()
			self.show_only_favorites_changed.emit()
			if self.zyngui.curlayer.get_preset_name():
				self.zyngui.curlayer.set_preset_by_name(self.zyngui.curlayer.get_preset_name())


	def toggle_show_fav_presets(self):
		if self.zyngui.curlayer.show_fav_presets:
			self.disable_show_fav_presets()
		else:
			self.enable_show_fav_presets()


	def set_select_path(self):
		if self.zyngui.curlayer:
			if self.zyngui.curlayer.show_fav_presets:
				self.select_path = (self.zyngui.curlayer.get_basepath() + " > Favorites")
				self.select_path_element = "Favorites"
			else:
				self.select_path = self.zyngui.curlayer.get_bankpath()
				self.select_path_element = self.zyngui.curlayer.bank_name
		super().set_select_path()


	show_only_favorites_changed = Signal()

	show_only_favorites = Property(bool, get_show_only_favorites, set_show_only_favorites, notify = show_only_favorites_changed)


#------------------------------------------------------------------------------
