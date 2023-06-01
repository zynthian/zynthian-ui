#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Chain Menu Class
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
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

# Zynthian specific modules
from zyngui.zynthian_gui_selector import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian App Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_chain_menu(zynthian_gui_selector):

	def __init__(self):
		super().__init__('Chain', True)


	def fill_list(self):
		self.list_data = []
		self.list_data.append((self.new_synth_layer, 0, "New Synth Chain"))
		self.list_data.append((self.new_audiofx_layer, 0, "New Audio Chain"))
		self.list_data.append((self.new_midifx_layer, 0, "New MIDI Chain"))
		self.list_data.append((self.new_generator_layer, 0, "New Generator Chain"))
		self.list_data.append((self.new_special_layer, 0, "New Special Chain"))
		self.list_data.append((self.clean_all, 0, "Clean All"))
		super().fill_list()


	def select_action(self, i, t='S'):
		if self.list_data[i][0]:
			self.last_action = self.list_data[i][0]
			self.last_action(t)


	def new_synth_layer(self, t='S'):
		self.zyngui.screens['layer'].add_layer("MIDI Synth")


	def new_audiofx_layer(self, t='S'):
		self.zyngui.screens['layer'].add_layer_engine("AI")


	def new_midifx_layer(self, t='S'):
		self.zyngui.screens['layer'].add_layer("MIDI Tool")


	def new_generator_layer(self, t='S'):
		self.zyngui.screens['layer'].add_layer("Audio Generator")


	def new_special_layer(self, t='S'):
		self.zyngui.screens['layer'].add_layer("Special")


	def clean_all(self, t='S'):
		self.zyngui.show_confirm("Do you really want to remove ALL chains & sequences?", self.clean_all_confirmed)


	def clean_all_confirmed(self, params=None):
		self.index = 0
		self.zyngui.clean_all()


	def set_select_path(self):
		self.select_path.set("Chain")

#------------------------------------------------------------------------------
