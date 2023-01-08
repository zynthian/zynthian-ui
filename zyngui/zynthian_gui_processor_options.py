#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Porcessor Options Class
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

# Zynthian specific modules
from zyngui.zynthian_gui_selector import zynthian_gui_selector
from zyngui.zynthian_gui_save_preset import zynthian_gui_save_preset

#------------------------------------------------------------------------------
# Zynthian processor Options GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_processor_options(zynthian_gui_selector, zynthian_gui_save_preset):

	def __init__(self):
		self.reset()
		super().__init__('Option', True)


	def reset(self):
		self.index = 0
		self.chain_id = None
		self.chain = None
		self.processor = None


	def fill_list(self):
		self.list_data = []

		if len(self.processor.get_bank_list()) > 1 or len(self.processor.preset_list) > 0 and self.processor.preset_list[0][0] != '':
			self.list_data.append((self.preset_list, None, "Preset List"))

		if hasattr(self.processor.engine, "save_preset"):
			self.list_data.append((self.save_preset, None, "Save Preset"))

		if self.can_move_upchain():
			self.list_data.append((self.move_upchain, None, "Move up chain"))
		if self.can_move_downchain():
			self.list_data.append((self.move_downchain, None, "Move down chain"))

		if self.processor.type=="MIDI Synth":
			eng_options = self.processor.engine.get_options()
			if eng_options['replace'] and eng_options['midi_chan']:
				self.list_data.append((self.replace, None, "Replace"))
		else:
			self.list_data.append((self.replace, None, "Replace"))

		self.list_data.append((self.midi_clean, None, "Clean MIDI-learn"))

		if self.processor.type == "MIDI Tool" or self.processor.type == "Audio Effect":
			self.list_data.append((self.processor_remove, None, "Remove"))

		super().fill_list()


	def build_view(self):
		if self.chain is not None:
			super().build_view()
			if self.index >= len(self.list_data):
				self.index = len(self.list_data) - 1
		else:
			self.zyngui.close_screen()


	def select_action(self, i, t='S'):
		self.index = i

		if self.list_data[i][0] is None:
			pass
		elif self.list_data[i][1] is None:
			self.list_data[i][0]()


	def setup(self, chain_id, processor):
		try:
			self.chain = self.zyngui.chain_manager.get_chain(chain_id)
			self.chain_id = chain_id
			self.processor = processor
		except Exception as e:
			logging.error(e)


	def processor_remove(self):
		self.zyngui.show_confirm("Do you want to remove {} from chain?".format(self.processor.engine.name), self.do_remove)


	def do_remove(self, unused=None):
		self.zyngui.chain_manager.remove_processor(self.chain_id, self.processor)
		self.zyngui.close_screen()


	# Preset management

	def preset_list(self):
		self.zyngui.cuia_bank_preset(self.processor)


	def save_preset(self):
		self.layer = self.processor
		super().save_preset()


	def midi_clean(self):
		if self.processor and self.processor.engine:
			self.zyngui.show_confirm("Do you want to clean MIDI-learn for ALL controls in {} on MIDI channel {}?".format(self.processor.engine.name, self.processor.midi_chan + 1), self.processor.midi_unlearn)


	# FX-Chain management

	def can_move_upchain(self):
		slot = self.chain.get_slot(self.processor)
		if slot == 0:
			slots = self.chain.get_slots_by_type(self.processor.type)
			return len(slots[0]) > 1
		return (slot is not None and slot > 0)


	def move_upchain(self):
		self.chain.move_processor(self.processor, self.chain.get_slot(self.processor) - 1)
		self.zyngui.close_screen()


	def can_move_downchain(self):
		slot = self.chain.get_slot(self.processor)
		slots = self.chain.get_slots_by_type(self.processor.type)
		if slot >= len(slots) - 1:
			return len(slots[0]) > 1
		return (slot is not None and slot + 1 < self.chain.get_slot_count(self.processor.type))


	def move_downchain(self):
		self.chain.move_processor(self.processor, self.chain.get_slot(self.processor) + 1)
		self.zyngui.close_screen()


	def replace(self):
		self.zyngui.modify_chain({"chain_id":self.chain_id, "processor":self.processor, "type":self.processor.type })


	# Select Path

	def set_select_path(self):
		if self.processor:
			self.select_path.set("{} > Processor Options".format(self.processor.get_basepath()))
		else:
			self.select_path.set("Processor Options")

#------------------------------------------------------------------------------
