#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Midi-Channel Selector Class
# 
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
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
from datetime import datetime

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector
import zynautoconnect

#------------------------------------------------------------------------------
# Zynthian MIDI Channel Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_midi_chan(zynthian_gui_selector):

	def __init__(self):
		self.set_mode('ADD')
		super().__init__('Channel', True)


	def set_mode(self, mode, chan=None, chan_list=None):
		self.mode = mode

		if chan_list:
			self.chan_list = chan_list
		else:
			self.chan_list = list(range(16))

		self.midi_chan_sel = None
		self.midi_chan_act = None

		if self.mode == 'ADD':
			pass
		elif self.mode == 'SET':
			self.index = self.get_midi_chan_index(chan)
		elif self.mode == 'CLONE':
			self.midi_chan = chan


	def fill_list(self):
		self.list_data=[]
		if self.mode == 'ADD' or self.mode == 'SET':
			for i in self.zyngui.chain_manager.get_free_midi_chans():
				if i == zynthian_gui_config.master_midi_channel:
					continue
				self.list_data.append((str(i + 1), i, "MIDI CH#" + str(i + 1)))
		elif self.mode == 'CLONE':
			for i in self.chan_list:
				if i in (self.midi_chan, zynthian_gui_config.master_midi_channel):
					continue
				elif lib_zyncore.get_midi_filter_clone(self.midi_chan, i):
					cc_to_clone = lib_zyncore.get_midi_filter_clone_cc(self.midi_chan, i).nonzero()[0]
					self.list_data.append((str(i+1), i, "[x] CH#{}, CC {}".format(i+1, ' '.join(map(str, cc_to_clone)))))
					logging.debug("CC TO CLONE: {}".format(cc_to_clone))
				else:
					self.list_data.append((str(i+1), i, "[  ] CH#{}".format(i+1)))
		super().fill_list()


	def fill_listbox(self):
		super().fill_listbox()
		#if self.mode=='CLONE':
		#	self.highlight_cloned()


	# Highlight current channels to which is cloned to ...
	def highlight_cloned(self):
		i=0
		for item in self.list_data:
			if item[2][:2] == '[x':
				self.listbox.itemconfig(i, {'fg':zynthian_gui_config.color_hl})
			else:
				self.listbox.itemconfig(i, {'fg':zynthian_gui_config.color_panel_tx})
			i += 1


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

		elif self.mode == 'CLONE':

			if selchan != self.midi_chan:
				if t == 'S':
					if lib_zyncore.get_midi_filter_clone(self.midi_chan, selchan):
						lib_zyncore.set_midi_filter_clone(self.midi_chan, selchan, 0)
					else:
						lib_zyncore.set_midi_filter_clone(self.midi_chan, selchan, 1)
						
					self.update_list()
					logging.info("CLONE MIDI CHANNEL {} => {}".format(self.midi_chan, selchan))

				elif t == 'B':
					self.clone_config_cc()


	def clone_config_cc(self):
		self.zyngui.screens['midi_cc'].config(self.midi_chan, self.midi_chan_sel)
		self.zyngui.show_screen('midi_cc')


	def midi_chan_activity(self, chan):
		if self.shown and self.mode != 'CLONE' and not self.zyngui.state_manager.zynseq.libseq.transportGetPlayStatus():
			i = self.get_midi_chan_index(chan)
			if i is not None and i != self.index:
				dts = (datetime.now()-self.last_index_change_ts).total_seconds()
				selchan = self.list_data[self.index][1]
				if (selchan == self.midi_chan_act and dts > zynthian_gui_config.zynswitch_bold_seconds) or dts > zynthian_gui_config.zynswitch_long_seconds:
					self.midi_chan_act = chan
					self.select(i)


	def set_select_path(self):
		if self.mode == 'ADD' or self.mode == 'SET':
			self.select_path.set("MIDI Channel")
		elif self.mode == 'CLONE':
			self.select_path.set("Clone MIDI Channel {} to ...".format(self.midi_chan+1))

#------------------------------------------------------------------------------
