#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI MIDI-Out Selector Class
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
from collections import OrderedDict

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian MIDI-Out Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_midi_out(zynthian_gui_selector):

	def __init__(self):
		self.end_processor = None
		super().__init__('MIDI Out', True)


	def fill_list(self):
		self.list_data = []
		chain_manager = zynthian_gui_config.zyngui.chain_manager
		active_chain = chain_manager.get_active_chain()

		if active_chain:
			midi_outs = OrderedDict([
				["MIDI-OUT", "Hardware MIDI Out"],
				["NET-OUT", "Network MIDI Out" ]
			])
			for chain_id, chain in chain_manager.chains.items():
				if chain.is_midi() and chain != active_chain:
					if chain_manager.will_route_howl(chain_manager.active_chain_id, chain_id):
						midi_outs[chain_id] = f"∞Chain {chain_id}"
					else:
						midi_outs[chain_id] = f"Chain {chain_id}"

			for dst_node, title in midi_outs.items():
				if dst_node in active_chain.midi_out:
					self.list_data.append((dst_node, dst_node, f"[x] {title}"))
				else:
					self.list_data.append((dst_node, dst_node, f"[  ] {title}"))

		super().fill_list()


	def fill_listbox(self):
		super().fill_listbox()
		#self.highlight()


	# Highlight current engine assigned outputs ...
	def highlight(self):
		for i in range(len(self.list_data)):
			if self.list_data[i][2][:2]=='[x':
				self.listbox.itemconfig(i, {'fg':zynthian_gui_config.color_hl})
			else:
				self.listbox.itemconfig(i, {'fg':zynthian_gui_config.color_panel_tx})


	def select_action(self, i, t='S'):
		try:
			zynthian_gui_config.zyngui.chain_manager.get_active_chain().toggle_midi_out(self.list_data[i][1])
			self.fill_list()
		except Exception as e:
			logging.error(e)


	def set_select_path(self):
		self.select_path.set("Send MIDI to ...")

#------------------------------------------------------------------------------
