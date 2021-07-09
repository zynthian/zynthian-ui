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
		self.only_favs = False;
		self.show()
      
      
	def fill_list(self):
		if not self.zyngui.curlayer:
			logging.error("Can't fill preset list for None layer!")
			return

		self.zyngui.curlayer.load_preset_list(self.only_favs)
		if not self.zyngui.curlayer.preset_list and self.only_favs:
			self.only_favs = False
			self.set_select_path()
			self.zyngui.curlayer.load_preset_list()

		self.list_data=self.zyngui.curlayer.preset_list
		super().fill_list()


	def show(self, only_favs=None):
		if not self.zyngui.curlayer:
			logging.error("Can't show preset list for None layer!")
			return
		if only_favs is not None:
			self.only_favs = only_favs
		self.select(self.zyngui.curlayer.get_preset_index())
		if not self.zyngui.curlayer.get_preset_name():
			self.zyngui.curlayer.set_preset(self.zyngui.curlayer.get_preset_index())

		super().show()


	def select_action(self, i, t='S'):
		if t=='S':
			self.zyngui.curlayer.set_preset(i)
			if self.only_favs:
				self.zyngui.screens['bank'].fill_list()
				self.zyngui.show_screen('control')
			else:
				self.zyngui.screens['control'].show()
		else:
			self.zyngui.curlayer.toggle_preset_fav(self.list_data[i])
			self.update_list()

	def index_supports_immediate_activation(self, index=None):
		return True

	def back_action(self):
		if self.only_favs:
			self.disable_only_favs()
			return ''
		else:
			return None


	def preselect_action(self):
		return self.zyngui.curlayer.preload_preset(self.index)


	def restore_preset(self):
		return self.zyngui.curlayer.restore_preset()

	def set_show_only_favorites(self, show):
		if show:
			self.enable_only_favs()
		else:
			self.disable_only_favs()

	def get_show_only_favorites(self):
		return self.only_favs

	def enable_only_favs(self):
		if not self.only_favs:
			self.only_favs = True
			self.set_select_path()
			self.update_list()
			self.show_only_favorites_changed.emit()
			if self.zyngui.curlayer.get_preset_name():
				self.zyngui.curlayer.set_preset_by_name(self.zyngui.curlayer.get_preset_name())


	def disable_only_favs(self):
		if self.only_favs:
			self.only_favs = False
			self.set_select_path()
			self.update_list()
			self.show_only_favorites_changed.emit()
			if self.zyngui.curlayer.get_preset_name():
				self.zyngui.curlayer.set_preset_by_name(self.zyngui.curlayer.get_preset_name())


	def toggle_only_favs(self):
		if self.only_favs:
			self.only_favs = False
		else:
			self.only_favs = True

		self.set_select_path()
		self.update_list()
		self.show_only_favorites_changed.emit()
		if self.zyngui.curlayer.get_preset_name():
			self.zyngui.curlayer.set_preset_by_name(self.zyngui.curlayer.get_preset_name())


	def set_select_path(self):
		if self.zyngui.curlayer:
			if self.only_favs:
				self.select_path = (self.zyngui.curlayer.get_basepath() + " > Favorites")
				self.select_path_element = "Favorites"
			else:
				self.select_path = self.zyngui.curlayer.get_bankpath()
				self.select_path_element = self.zyngui.curlayer.bank_name
		super().set_select_path()


	show_only_favorites_changed = Signal()

	show_only_favorites = Property(bool, get_show_only_favorites, set_show_only_favorites, notify = show_only_favorites_changed)


#------------------------------------------------------------------------------
