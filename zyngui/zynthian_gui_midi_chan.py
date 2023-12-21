#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Midi-Channel Selector Class
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

import logging
from datetime import datetime

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector
import zynautoconnect

# ------------------------------------------------------------------------------
# Zynthian MIDI Channel Selection GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_midi_chan(zynthian_gui_selector):

	def __init__(self):
		self.set_mode('ADD')
		super().__init__('Channel', True)

	def set_mode(self, mode, chan=None, chan_list=None, chan_all=False):
		self.mode = mode

		if chan_list:
			self.chan_list = chan_list
		else:
			self.chan_list = list(range(16))

		self.chan_all = chan_all
		self.midi_chan_sel = None
		self.midi_chan_act = None

		if self.mode == 'ADD':
			pass
		elif self.mode == 'SET':
			self.midi_chan = chan
			self.index = self.get_midi_chan_index(chan)

	def fill_list(self):
		self.list_data = []
		chain = self.zyngui.chain_manager.get_active_chain()

		list_index = 0
		if self.chan_all:
			self.list_data.append(("ALL", 0xffff, "ALL MIDI CHANNELS"))
			if chain.midi_chan == 0xffff:
				self.index = 0
			list_index += 1
		for i in self.zyngui.chain_manager.get_free_midi_chans():
			if i == zynthian_gui_config.master_midi_channel:
				continue
			self.list_data.append((str(i + 1), i, "MIDI CH#" + str(i + 1)))
			if chain.midi_chan == i:
				self.index = list_index
			list_index += 1

		super().fill_list()

	def fill_listbox(self):
		super().fill_listbox()

	""" Leave this as example of highlighting code
	def highlight_cloned(self):
		i=0
		for item in self.list_data:
			if item[2][:2] == '[x':
				self.listbox.itemconfig(i, {'fg': zynthian_gui_config.color_hl})
			else:
				self.listbox.itemconfig(i, {'fg': zynthian_gui_config.color_panel_tx})
			i += 1
	"""

	def get_midi_chan_index(self, chan):
		for i, ch in enumerate(self.chan_list):
			if ch == chan:
				return i

	def select_action(self, i, t='S'):
		selchan = self.list_data[i][1]
		self.midi_chan_sel = selchan

		if self.mode == 'ADD':
			self.zyngui.modify_chain_status["midi_chan"] = selchan
			self.zyngui.modify_chain()
		elif self.mode == 'SET':
			self.zyngui.chain_manager.set_midi_chan(self.zyngui.chain_manager.active_chain_id, selchan)
			zynautoconnect.request_midi_connect()
			self.zyngui.screens['audio_mixer'].refresh_visible_strips()
			self.zyngui.close_screen()

	def midi_chan_activity(self, chan):
		if self.shown and not self.zyngui.state_manager.zynseq.libseq.transportGetPlayStatus():
			i = self.get_midi_chan_index(chan)
			if i is not None and i != self.index:
				dts = (datetime.now()-self.last_index_change_ts).total_seconds()
				selchan = self.list_data[self.index][1]
				if (selchan == self.midi_chan_act and dts > zynthian_gui_config.zynswitch_bold_seconds) or dts > zynthian_gui_config.zynswitch_long_seconds:
					self.midi_chan_act = chan
					self.select(i)

	def set_select_path(self):
		self.select_path.set("MIDI Channel")

# ------------------------------------------------------------------------------
