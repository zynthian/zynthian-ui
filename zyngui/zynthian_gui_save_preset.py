#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Save Preset helper Class
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

import logging

#------------------------------------------------------------------------------
# Zynthian Save Preset GUI Class
#------------------------------------------------------------------------------
# This helper class must be inheritated by a GUI selector class!!
#------------------------------------------------------------------------------

class zynthian_gui_save_preset():

	def save_preset(self):
		if self.layer:
			self.save_preset_create_bank_name = None
			self.save_preset_bank_info = None
			self.layer.load_bank_list()
			if not self.layer.bank_list or not self.layer.bank_list[0][0] or self.layer.auto_save_bank:
				self.save_preset_select_name_cb()
				return
			options = {}
			options["***New bank***"] = "NEW_BANK"
			index = self.layer.get_bank_index() + 1
			for bank in self.layer.bank_list:
				if bank[0]=="*FAVS*":
					index -= 1
				else:
					options[bank[2]] = bank
			self.zyngui.screens['option'].config("Select bank...", options, self.save_preset_select_bank_cb)
			self.zyngui.show_screen('option')
			self.zyngui.screens['option'].select(index)


	def save_preset_select_bank_cb(self, bank_name, bank_info):
		self.save_preset_bank_info = bank_info
		if bank_info is "NEW_BANK":
			self.zyngui.show_keyboard(self.save_preset_select_name_cb, "NewBank")
		else:
			self.save_preset_select_name_cb()


	def save_preset_select_name_cb(self, create_bank_name=None):
		if create_bank_name is not None:
			create_bank_name = create_bank_name.strip()
		self.save_preset_create_bank_name = create_bank_name
		if self.layer.preset_name:
			self.zyngui.show_keyboard(self.save_preset_cb, self.layer.preset_name + " COPY")
		else:
			self.zyngui.show_keyboard(self.save_preset_cb, "New Preset")


	def save_preset_cb(self, preset_name):
		preset_name = preset_name.strip()
		#If must create new bank, calculate URID
		if self.save_preset_create_bank_name:
			create_bank_urid = self.layer.engine.get_user_bank_urid(self.save_preset_create_bank_name)
			self.save_preset_bank_info = (create_bank_urid, None, self.save_preset_create_bank_name, None)
		if self.layer.engine.preset_exists(self.save_preset_bank_info, preset_name):
			self.zyngui.show_confirm("Do you want to overwrite preset '{}'?".format(preset_name), self.do_save_preset, preset_name)
		else:
			self.do_save_preset(preset_name)


	def do_save_preset(self, preset_name):
		preset_name = preset_name.strip()

		try:
			# Save preset
			preset_uri = self.layer.engine.save_preset(self.save_preset_bank_info, preset_name)

			if preset_uri:
				#If must create new bank, do it!
				if self.save_preset_create_bank_name:
					self.layer.engine.create_user_bank(self.save_preset_create_bank_name)
					logging.info("Created new bank '{}' => {}".format(self.save_preset_create_bank_name, self.save_preset_bank_info[0]))
					self.layer.load_bank_list()
				if self.save_preset_bank_info:
					self.layer.set_bank_by_id(self.save_preset_bank_info[0])
				self.layer.load_preset_list()
				self.layer.set_preset_by_id(preset_uri)
			else:
				logging.error("Can't save preset '{}' to bank '{}'".format(preset_name, self.save_preset_bank_info[2]))

		except Exception as e:
			logging.error(e)

		self.save_preset_create_bank_name = None
		self.zyngui.close_screen()


#------------------------------------------------------------------------------
