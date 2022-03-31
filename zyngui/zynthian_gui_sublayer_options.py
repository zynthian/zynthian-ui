#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Sublayer Options Class
#
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
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

#------------------------------------------------------------------------------
# Zynthian Sublayer Options GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_sublayer_options(zynthian_gui_selector):

	def __init__(self):
		self.reset()
		super().__init__('Option', True)


	def reset(self):
		self.index = 0
		self.root_layer = None
		self.root_layer_index = None
		self.sublayer = None
		self.sublayer_index = None
		self.sublayer_type = None


	def fill_list(self):
		self.list_data = []

		if len(self.sublayer.preset_list)>1:
			self.list_data.append((self.sublayer_presets, None, "Presets"))

		# Effect Layer Options
		if self.sublayer_type=="Audio Effect":
			self.list_data.append((self.audiofx_replace, None, "Replace"))
			if self.audiofx_can_move_upchain():
				self.list_data.append((self.audiofx_move_upchain, None, "Move Upchain"))
			if self.audiofx_can_move_downchain():
				self.list_data.append((self.audiofx_move_downchain, None, "Move Downchain"))

		elif self.sublayer_type=="MIDI Tool":
			self.list_data.append((self.midifx_replace, None, "Replace"))
			if self.midifx_can_move_upchain():
				self.list_data.append((self.midifx_move_upchain, None, "Move Upchain"))
			if self.midifx_can_move_downchain():
				self.list_data.append((self.midifx_move_downchain, None, "Move Downchain"))

		self.list_data.append((self.sublayer_remove, None, "Remove"))

		super().fill_list()


	def show(self):
		if self.sublayer_index is not None:
			super().show()
			if self.index>=len(self.list_data):
				self.index = len(self.list_data)-1
		else:
			self.zyngui.close_screen()


	def select_action(self, i, t='S'):
		self.index = i

		if self.list_data[i][0] is None:
			pass
		elif self.list_data[i][1] is None:
			self.list_data[i][0]()


	def setup(self, root_layer, sublayer):
		try:
			self.root_layer = root_layer
			self.root_layer_index = self.zyngui.screens['layer'].layers.index(root_layer)
			self.sublayer = sublayer
			self.sublayer_index = self.zyngui.screens['layer'].layers.index(sublayer)
			self.sublayer_type = sublayer.engine.type
		except Exception as e:
			logging.error(e)


	def sublayer_presets(self):
		self.zyngui.set_curlayer(self.sublayer, True)
		self.zyngui.show_screen('bank')
		# If there is only one bank, jump to preset selection
		if len(self.layer.bank_list)<=1:
			self.zyngui.screens['bank'].select_action(0)


	def sublayer_remove(self):
		self.zyngui.screens['layer'].remove_layer(self.sublayer_index)
		self.zyngui.close_screen()


	# FX-Chain management

	def audiofx_can_move_upchain(self):
		ups = self.zyngui.screens['layer'].get_fxchain_upstream(self.sublayer)
		if len(ups)>0 and (self.root_layer.engine.type!="MIDI Synth" or self.root_layer not in ups):
			return True


	def audiofx_move_upchain(self):
		ups = self.zyngui.screens['layer'].get_fxchain_upstream(self.sublayer)
		self.zyngui.screens['layer'].swap_fxchain(ups[0], self.sublayer)
		self.zyngui.close_screen()


	def audiofx_can_move_downchain(self):
		downs = self.zyngui.screens['layer'].get_fxchain_downstream(self.sublayer)
		if len(downs)>0 and (self.root_layer.engine.type!="MIDI Synth" or self.root_layer not in downs):
			return True


	def audiofx_move_downchain(self):
		downs = self.zyngui.screens['layer'].get_fxchain_downstream(self.sublayer)
		self.zyngui.screens['layer'].swap_fxchain(self.sublayer, downs[0])
		self.zyngui.close_screen()


	def audiofx_replace(self):
		self.zyngui.screens['layer'].replace_fxchain_layer(self.sublayer_index)


	# MIDI-Chain management

	def midifx_can_move_upchain(self):
		ups = self.zyngui.screens['layer'].get_midichain_upstream(self.sublayer)
		if len(ups)>0 and (self.root_layer.engine.type!="MIDI Synth" or self.root_layer not in ups):
			return True


	def midifx_move_upchain(self):
		ups = self.zyngui.screens['layer'].get_midichain_upstream(self.sublayer)
		self.zyngui.screens['layer'].swap_midichain(ups[0], self.sublayer)
		self.zyngui.close_screen()


	def midifx_can_move_downchain(self):
		downs = self.zyngui.screens['layer'].get_midichain_downstream(self.sublayer)
		if len(downs)>0 and (self.root_layer.engine.type!="MIDI Synth" or self.root_layer not in downs):
			return True


	def midifx_move_downchain(self):
		downs = self.zyngui.screens['layer'].get_midichain_downstream(self.sublayer)
		self.zyngui.screens['layer'].swap_midichain(self.sublayer, downs[0])
		self.zyngui.close_screen()


	def midifx_replace(self):
		self.zyngui.screens['layer'].replace_midichain_layer(self.sublayer_index)


	# Select Path

	def set_select_path(self):
		if self.sublayer_type=="Audio Effect":
			self.select_path.set("{} > Audio-FX Options".format(self.sublayer.get_basepath()))
		elif self.sublayer_type=="MIDI Tool":
			self.select_path.set("{} > MIDI-FX Options".format(self.sublayer.get_basepath()))
		else:
			return "FX Options"

#------------------------------------------------------------------------------
