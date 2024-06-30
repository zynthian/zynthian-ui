#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI ZS3 options selector Class
# 
# Copyright (C) 2015-2020 Fernando Moyano <jofemodo@zynthian.org>
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

import logging

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

# ------------------------------------------------------------------------------
# Zynthian ZS3 options GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_zs3_options(zynthian_gui_selector):

	def __init__(self):
		self.last_action = None
		self.zs3_id = None
		super().__init__('Option', True)

	def config(self, id):
		self.last_action = None
		self.zs3_id = id

	def fill_list(self):
		self.list_data=[]
		if self.zs3_id == "zs3-0":
			self.list_data.append((self.zs3_update, 2, "Overwrite"))
		else:
			self.list_data.append((self.zs3_restoring_submenu, 1, "Restore options..."))
			self.list_data.append((self.zs3_update, 2, "Overwrite"))
			self.list_data.append((self.zs3_rename, 3, "Rename"))
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
			state = self.zyngui.state_manager.zs3[self.zs3_id]
		except:
			logging.error("Bad ZS3 id ({}).".format(self.zs3_id))
			return

		title = self.zyngui.state_manager.get_zs3_title(self.zs3_id)
		self.zyngui.screens['option'].config(f"ZS3 Restore: {title}", self.zs3_restoring_options_cb,
			self.zs3_restoring_options_select_cb, close_on_select=False, click_type=True)
		self.zyngui.show_screen('option')

	def zs3_restoring_options_cb(self):
		try:
			state = self.zyngui.state_manager.zs3[self.zs3_id]
		except:
			logging.error(f"Bad ZS3 id ({self.zs3_id}).")
			return

		options = {}

		# Restoring Audio Mixer
		mixer_state = state["mixer"]
		try:
			restore_flag = mixer_state["restore"]
		except:
			restore_flag = True
		if restore_flag:
			options["\u2612 Mixer"] = "mixer"
		else:
			options["\u2610 Mixer"] = "mixer"

		# Restoring chains
		options["Chains"] = None
		if "chains" in state:
			for chain_id, chain_state in state["chains"].items():
				chain = self.zyngui.chain_manager.get_chain(chain_id)
				label = chain.get_name()
				try:
					restore_flag = chain_state["restore"]
				except:
					restore_flag = True
				if restore_flag:
					options[f"\u2612 {label}"] = chain_id
				else:
					options[f"\u2610 {label}"] = chain_id

		return options

	def zs3_restoring_options_select_cb(self, label, id, ct):
		if ct == "S":
			self.zyngui.state_manager.toggle_zs3_chain_restore_flag(self.zs3_id, id)
		elif ct == "B":
			try:
				state = self.zyngui.state_manager.zs3[self.zs3_id]
			except:
				logging.error("Bad ZS3 ID ({}).".format(self.zs3_id))
				return
			# Invert selection (toggle all elements in list)
			for chain_id in list(state["chains"]) + ["mixer"]:
				self.zyngui.state_manager.toggle_zs3_chain_restore_flag(self.zs3_id, chain_id)

	def zs3_rename(self):
		title = self.zyngui.state_manager.get_zs3_title(self.zs3_id)
		self.zyngui.show_keyboard(self.zs3_rename_cb, title)

	def zs3_rename_cb(self, title):
		logging.info("Renaming ZS3 '{}'".format(self.zs3_id))
		self.zyngui.state_manager.set_zs3_title(self.zs3_id, title)
		self.zyngui.close_screen()

	def zs3_update(self):
		logging.info("Updating ZS3 '{}'".format(self.zs3_id))
		self.zyngui.state_manager.save_zs3(self.zs3_id)
		self.zyngui.close_screen()

	def zs3_delete(self):
		self.zyngui.show_confirm(f"Do you really want to delete ZS3: {self.zs3_id}?", self.do_delete)

	def do_delete(self, params):
		if self.zs3_id == "zs3-0":
			logging.info("Can't delete ZS3 '{}'!".format(self.zs3_id))
		else:
			logging.info("Deleting ZS3 '{}'".format(self.zs3_id))
			self.zyngui.state_manager.delete_zs3(self.zs3_id)
		self.zyngui.close_screen()

	def set_select_path(self):
		title = self.zyngui.state_manager.get_zs3_title(self.zs3_id)
		self.select_path.set(f"ZS3 Options: {title}")

# ------------------------------------------------------------------------------
