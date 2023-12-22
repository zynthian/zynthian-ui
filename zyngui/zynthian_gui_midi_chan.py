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
		super().__init__('Channel', True)
		self.chan_list = list(range(16))
		self.set_mode('ADD')

	def set_mode(self, mode, chan=None, chan_all=False):
		self.mode = mode
		self.chan_all = chan_all
		self.midi_chan_sel = None
		self.midi_chan_act = None
		self.midi_chan = chan

		if self.mode == 'ADD':
			try:
				self.midi_chan = self.zyngui.chain_manager.get_next_free_midi_chan(self.midi_chan)
			except:
				pass
		self.index = self.get_midi_chan_index(self.midi_chan)

	def fill_list(self):
		self.list_data = []
		free_chans = self.zyngui.chain_manager.get_free_midi_chans()

		if self.chan_all:
			if self.midi_chan > 15:
				self.list_data.append(("ALL", 0xffff, ">ALL MIDI CHANNELS"))
			else:
				self.list_data.append(("ALL", 0xffff, "ALL MIDI CHANNELS"))
		#for i in self.zyngui.chain_manager.get_free_midi_chans():
		for i in range(16):
			if i == zynthian_gui_config.master_midi_channel:
				continue
			if i == self.midi_chan:
				self.list_data.append((str(i + 1), i, f">MIDI CH#{i + 1}"))
			elif i in free_chans:
				self.list_data.append((str(i + 1), i, f"MIDI CH#{i + 1}"))
			else:
				self.list_data.append((str(i + 1), i, f"*MIDI CH#{i + 1}"))

		super().fill_list()

	def get_midi_chan_index(self, chan):
		if chan > 15:
			return 0
		if self.chan_all:
			return chan + 1
		else:
			return chan

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
