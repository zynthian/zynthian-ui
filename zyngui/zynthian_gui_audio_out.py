#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Audio-Out Selector Class
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
import zynautoconnect
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector
from zyngine.zynthian_engine_modui import zynthian_engine_modui

#------------------------------------------------------------------------------
# Zynthian Audio-Out Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_audio_out(zynthian_gui_selector):

	def __init__(self):
		self.chain = None
		self.chain_id = None
		super().__init__('Audio Out', True)


	def set_chain(self, chain_id):
		self.chain_id = chain_id
		self.chain = self.zyngui.chain_manager.get_chain(chain_id)


	def fill_list(self):
		self.list_data = []

		mod_running = False
		for chain_id, chain in self.zyngui.chain_manager.chains.items():
			if isinstance(chain, zynthian_engine_modui):
				mod_running = True
				break

		port_names = list(zynautoconnect.get_audio_input_ports(True).keys())
		if self.chain_id == "main":
			port_names = ["system"] + port_names
		else:
			port_names = ["mixer"] + port_names
		if mod_running:
			port_names += ["mod-ui"]

		for k in port_names:
			try:
				title = self.chain.get_processor_by_jackname(k).get_basepath()
			except:
				title = k

			logging.debug("AUDIO OUTPUT PORT {} => {}".format(k,title))
			"""
			try:
				chan = title.split('#')[0]
				if chan == "Main":
					continue
				else:
					ch = int(chan)-1
					if ch==self.end_chain.midi_chan or ch>15:
						continue
			except Exception as e:
				#logging.debug("Can't get chain's midi chan => {}".format(e))
				pass
			"""

			if k in self.chain.get_audio_out():
				self.list_data.append((k, k, "[x] " + title))
			else:
				self.list_data.append((k, k, "[  ] " + title))

		if zynthian_gui_config.multichannel_recorder:
			if self.zyngui.state_manager.audio_recorder.get_status():
				# Recording so don't allow change of armed state
				if self.zyngui.state_manager.audio_recorder.is_armed(self.chain.midi_chan):
					self.list_data.append((None, 'record_disable', '[x] multitrack recorder'))
				else:
					self.list_data.append((None, 'record_enable', '[  ] multitrack recorder'))
			else:
				if self.zyngui.state_manager.audio_recorder.is_armed(self.chain.midi_chan):
					self.list_data.append(('record', None, '[x] multitrack recorder'))
				else:
					self.list_data.append(('record', None, '[  ] multitrack recorder'))

		super().fill_list()


	def fill_listbox(self):
		super().fill_listbox()


	def select_action(self, i, t='S'):
		if self.list_data[i][0] == 'record':
			self.zyngui.state_manager.audio_recorder.toggle_arm(self.chain.midi_chan)
		else:
			self.chain.toggle_audio_out(self.list_data[i][1])
		self.fill_list()


	def set_select_path(self):
		self.select_path.set("Send Audio to ...")

#------------------------------------------------------------------------------
