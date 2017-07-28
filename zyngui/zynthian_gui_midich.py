#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Midi-Channel Selector Class
# 
# Copyright (C) 2015-2016 Fernando Moyano <jofemodo@zynthian.org>
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
import logging

# Zynthian specific modules
from . import zynthian_gui_config
from . import zynthian_gui_selector

#------------------------------------------------------------------------------
# Configure logging
#------------------------------------------------------------------------------

# Set root logging level
logging.basicConfig(stream=sys.stderr, level=zynthian_gui_config.log_level)

#------------------------------------------------------------------------------
# Zynthian MIDI Channel Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_midich(zynthian_gui_selector):

	def __init__(self, max_chan=16):
		self.mode='ADD'
		self.max_chan=max_chan
		super().__init__('Channel', True)

	def set_mode(self, mode):
		self.mode=mode

	def fill_list(self):
		self.list_data=[]
		for i in range(self.max_chan):
			self.list_data.append((str(i+1),i,"MIDI CH#"+str(i+1)))
		super().fill_list()

	def show(self):
		super().show()

	def select_action(self, i):
		if self.mode=='ADD':
			zynthian_gui_config.zyngui.screens['layer'].add_layer_midich(self.list_data[i][1])
		elif self.mode=='SET':
			layer_index=zynthian_gui_config.zyngui.screens['layer_options'].layer_index
			zynthian_gui_config.zyngui.screens['layer'].layers[layer_index].set_midi_chan(self.list_data[i][1])
			zynthian_gui_config.zyngui.show_screen('layer')

	def set_select_path(self):
		self.select_path.set("MIDI Channel")

#------------------------------------------------------------------------------
