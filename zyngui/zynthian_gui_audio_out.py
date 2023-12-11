#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Audio-Out Selector Class
# 
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
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
import zynautoconnect
from zyngine.zynthian_signal_manager import zynsigman
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector
from zyngine.zynthian_engine_modui import zynthian_engine_modui
# ------------------------------------------------------------------------------
# Zynthian Audio-Out Selection GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_audio_out(zynthian_gui_selector):

	def __init__(self):
		self.chain = None
		super().__init__('Audio Out', True)

	def set_chain(self, chain):
		self.chain = chain

	def fill_list(self):
		self.list_data = []

		# TODO: Show chain name
		mod_running = False
		if self.chain.chain_id == "main":
			port_names = [["system", "system"]]  # TODO: Get list of available system outputs
		else:
			port_names = [["mixer", "mixer"]]
		jack_input_ports = list(zynautoconnect.get_audio_input_ports(True).keys())
		for chain_id, chain in self.zyngui.chain_manager.chains.items():
			if isinstance(chain, zynthian_engine_modui):
				mod_running = True
			if chain == self.chain:
				continue
			for processor in chain.get_processors():
				jackname = processor.get_jackname()
				if jackname in jack_input_ports:
					# TODO: Check for howl-round
					port_names.append([f"{chain_id}/{processor.id}: {processor.get_basepath()}", processor])

		if mod_running:
			port_names.append([self.chain.chain_id, None, "mod-ui"])  # TODO: Should this now be handled by chain input

		for title,processor in port_names:
			if processor in self.chain.audio_out:
				self.list_data.append((processor, processor, "\u2612 " + title))
			else:
				self.list_data.append((processor, processor, "\u2610 " + title))

		if zynthian_gui_config.multichannel_recorder:
			armed = self.zyngui.state_manager.audio_recorder.is_armed(self.chain.mixer_chan)
			if self.zyngui.state_manager.audio_recorder.get_status():
				# Recording so don't allow change of armed state
				if armed:
					self.list_data.append((None, 'record_disable', '\u2612 multitrack recorder'))
				else:
					self.list_data.append((None, 'record_enable', '\u2610 multitrack recorder'))
			else:
				if armed:
					self.list_data.append(('record', None, '\u2612 multitrack recorder'))
				else:
					self.list_data.append(('record', None, '\u2610 multitrack recorder'))
			zynsigman.send(zynsigman.S_AUDIO_MIXER, self.zyngui.state_manager.zynmixer.SS_ZCTRL_SET_VALUE, chan=self.chain.mixer_chan, symbol="rec", value=armed)

		super().fill_list()

	def fill_listbox(self):
		super().fill_listbox()

	def select_action(self, i, t='S'):
		if self.list_data[i][0] == 'record':
			self.zyngui.state_manager.audio_recorder.toggle_arm(self.chain.mixer_chan)
		else:
			self.chain.toggle_audio_out(self.list_data[i][0])
		self.fill_list()

	def set_select_path(self):
		self.select_path.set("Send Audio to ...")

# ------------------------------------------------------------------------------
