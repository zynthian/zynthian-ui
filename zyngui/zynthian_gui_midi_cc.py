#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Midi-CC Selector Class
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

import sys
import tkinter
import logging
from ctypes import c_ubyte

# Zynthian specific modules
from zyncoder import *
from . import zynthian_gui_config
from . import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian MIDI Channel Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_midi_cc(zynthian_gui_selector):

	def __init__(self):
		self.midi_chan_from = None
		self.midi_chan_to = None
		self.cc = [0] * 16
		super().__init__('CC', True)


	def set_clone_channels(self, chan_from, chan_to):
		self.midi_chan_from = chan_from
		self.midi_chan_to = chan_to
		self.cc = zyncoder.lib_zyncoder.get_midi_filter_clone_cc(chan_from, chan_to).tolist()


	@staticmethod
	def set_clone_cc(chan_from, chan_to, cc):
		cc_array = (c_ubyte*128)()

		if len(cc)==128:
			for i in range(0, 128):
				cc_array[i] = cc[i]
		else:
			for i in range(0, 128):
				if i in cc:
					cc_array[i] = 1
				else:
					cc_array[i] = 0

		zyncoder.lib_zyncoder.set_midi_filter_clone_cc(chan_from, chan_to, cc_array)


	def fill_list(self):
		self.list_data=[]
		for i, ccnum in enumerate(self.cc):
			if ccnum:
				self.list_data.append((str(i),i,"[x] CC {}".format(str(i).zfill(2))))
			else:
				self.list_data.append((str(i),i,"[  ] CC {}".format(str(i).zfill(2))))
		super().fill_list()


	def select_action(self, i, t='S'):
		cc_num=self.list_data[i][1]

		if self.cc[cc_num]:
			self.cc[cc_num] = 0
		else:
			self.cc[cc_num] = 1
			
		self.set_clone_cc(self.midi_chan_from, self.midi_chan_to, self.cc)
		
		self.set_clone_channels(self.midi_chan_from, self.midi_chan_to)
		self.update_list()

		logging.info("MIDI CC {} CLONE CH#{}=>CH#{}: {}".format(cc_num, self.midi_chan_from, self.midi_chan_to, self.cc[cc_num]))


	def back_action(self):
		self.zyngui.show_modal('midi_chan')
		return ''


	def set_select_path(self):
		try:
			self.select_path.set("Clone {} => {}, MIDI CC...".format(self.midi_chan_from, self.midi_chan_to))
		except:
			self.select_path.set("Clone MIDI CC...")


#------------------------------------------------------------------------------
