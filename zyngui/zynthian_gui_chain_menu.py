#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Chain Menu Class
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

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

# ------------------------------------------------------------------------------
# Zynthian App Selection GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_chain_menu(zynthian_gui_selector):

	def __init__(self):
		super().__init__('Chain', True)

	def fill_list(self):
		self.list_data = []

		# Add Chain options
		self.list_data.append((None, 0, "> ADD CHAIN"))
		self.list_data.append((self.add_synth_layer, 0, "Add Synth Chain"))
		self.list_data.append((self.add_audiofx_layer, 0, "Add Audio Chain"))
		self.list_data.append((self.add_midifx_layer, 0, "Add MIDI Chain"))
		self.list_data.append((self.add_generator_layer, 0, "Add Generator Chain"))
		self.list_data.append((self.add_special_layer, 0, "Add Special Chain"))

		# Remove options
		self.list_data.append((None, 0, "> REMOVE"))
		self.list_data.append((self.remove_sequences, 0, "Remove Sequences"))
		self.list_data.append((self.remove_chains, 0, "Remove Chains"))
		self.list_data.append((self.remove_all, 0, "Remove All"))

		# System / configuration screens
		if zynthian_gui_config.control_test_enabled:
			self.list_data.append((None, 0, "> SYSTEM"))
			self.list_data.append((self.control_test, 0, "Control Test"))

		super().fill_list()

	def select_action(self, i, t='S'):
		if self.list_data[i][0]:
			self.last_action = self.list_data[i][0]
			self.last_action(t)

	def add_synth_layer(self, t='S'):
		self.zyngui.screens['layer'].add_layer("MIDI Synth")

	def add_audiofx_layer(self, t='S'):
		self.zyngui.screens['layer'].add_layer_engine("AI")

	def add_midifx_layer(self, t='S'):
		self.zyngui.screens['layer'].add_layer("MIDI Tool")

	def add_generator_layer(self, t='S'):
		self.zyngui.screens['layer'].add_layer("Audio Generator")

	def add_special_layer(self, t='S'):
		self.zyngui.screens['layer'].add_layer("Special")

	def remove_sequences(self, t='S'):
		self.zyngui.show_confirm("Do you really want to remove ALL sequences?", self.remove_sequences_confirmed)

	def remove_sequences_confirmed(self, params=None):
		self.index = 0
		self.zyngui.clean_sequences()

	def remove_chains(self, t='S'):
		self.zyngui.show_confirm("Do you really want to remove ALL chains?", self.remove_chains_confirmed)

	def remove_chains_confirmed(self, params=None):
		self.index = 0
		self.zyngui.clean_chains()

	def remove_all(self, t='S'):
		self.zyngui.show_confirm("Do you really want to remove ALL chains & sequences?", self.remove_all_confirmed)

	def remove_all_confirmed(self, params=None):
		self.index = 0
		self.zyngui.clean_all()

	def set_select_path(self):
		self.select_path.set("Chain")

# ------------------------------------------------------------------------------
