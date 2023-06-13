#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI ZS3 options selector Class
# 
# Copyright (C) 2015-2020 Fernando Moyano <jofemodo@zynthian.org>
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

import logging

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian App Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_zs3_options(zynthian_gui_selector):

	def __init__(self):
		self.last_action = None
		self.zs3_index = None
		super().__init__('Option', True)


	def config(self, i):
		self.last_action = None
		self.zs3_index = i


	def fill_list(self):
		self.list_data = []
		if not zynthian_gui_config.midi_single_active_channel:
			self.list_data.append((self.zs3_restoring_submenu, 1, "Restoring..."))
		self.list_data.append((self.zs3_rename, 2, "Rename"))
		self.list_data.append((self.zs3_update, 3, "Update"))
		self.list_data.append((self.zs3_delete, 4, "Delete"))
		self.preselect_last_action()
		super().fill_list()


	def preselect_last_action(self, force_select=False):
		for i, data in enumerate(self.list_data):
			if self.last_action and self.last_action == data[0]:
				if force_select:
					self.select_listbox(i)
				else:
					self.index = i
				return i
		return 0


	def select_action(self, i, t='S'):
		self.index = i
		if self.list_data[i][0]:
			self.last_action = self.list_data[i][0]
			self.last_action()


	def zs3_restoring_submenu(self):
		try:
			state = self.zyngui.screens['layer'].learned_zs3[self.zs3_index]
		except:
			logging.error("Bad ZS3 index ({}).".format(self.zs3_index))

		self.zyngui.screens['option'].config("ZS3 restoring: {}".format(state["zs3_title"]), self.zs3_restoring_options_cb, self.zs3_restoring_options_select_cb, close_on_select=False)
		self.zyngui.show_screen('option')


	def zs3_restoring_options_cb(self):
		try:
			state = self.zyngui.screens["layer"].learned_zs3[self.zs3_index]
		except:
			logging.error("Bad ZS3 index ({}).".format(self.zs3_index))

		options = {}

		# Restoring Chains (layers)
		slayers = state["layers"]
		for i, lss in enumerate(sorted(slayers, key=lambda lss: lss["midi_chan"])):
			if lss["midi_chan"] == 256:
				chan = "Main"
			else:
				chan = lss["midi_chan"] + 1
			label = "{}#{} > {}".format(chan, lss["engine_name"], lss["preset_name"])
			if "restore" in lss and not lss["restore"]:
				options["[  ] {}".format(label)] = slayers.index(lss)
			else:
				options["[x] {}".format(label)] = slayers.index(lss)

		# Restoring Audio Mixer
		smixer = state["mixer"]
		if "restore" in smixer and not smixer["restore"]:
			options["[  ] Mixer"] = -1
		else:
			options["[x] Mixer"] = -1

		return options


	def	zs3_restoring_options_select_cb(self, label, index):
		if index >= 0:
			self.zyngui.screens["layer"].toggle_zs3_layer_restore_flag(self.zs3_index, index)
		elif index == -1:
			self.zyngui.screens["layer"].toggle_zs3_mixer_restore_flag(self.zs3_index)


	def zs3_rename(self):
		title = self.zyngui.screens['layer'].get_zs3_title(self.zs3_index)
		self.zyngui.show_keyboard(self.zs3_rename_cb, title)


	def zs3_rename_cb(self, title):
		logging.info("Renaming ZS3#{}".format(self.zs3_index))
		self.zyngui.screens['layer'].set_zs3_title(self.zs3_index, title)
		self.zyngui.close_screen()


	def zs3_update(self):
		logging.info("Updating ZS3#{}".format(self.zs3_index))
		self.zyngui.screens['layer'].save_zs3(self.zs3_index)
		self.zyngui.close_screen()


	def zs3_delete(self):
		logging.info("Deleting ZS3#{}".format(self.zs3_index))
		self.zyngui.screens['layer'].delete_zs3(self.zs3_index)
		self.zyngui.close_screen()


	def set_select_path(self):
		self.select_path.set("ZS3 Options")


#------------------------------------------------------------------------------
