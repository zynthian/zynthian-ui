#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Layer Options Class
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
# Zynthian Layer Options GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_layer_options(zynthian_gui_selector):

	def __init__(self):
		super().__init__('Option', True)
		self.layer_index=None

	def fill_list(self):
		self.list_data=[]
		eng=zynthian_gui_config.zyngui.screens['layer'].layers[self.layer_index].engine.nickname
		if eng in ['ZY','LS','FS']:
			self.list_data.append((self.midi_chan,0,"MIDI Chan"))
		self.list_data.append((self.remove_layer,0,"Remove Layer"))
		super().fill_list()

	def show(self):
		self.layer_index=zynthian_gui_config.zyngui.screens['layer'].get_cursel()
		self.index=0
		super().show()

	def select_action(self, i):
		self.list_data[i][0]()

	def set_select_path(self):
		self.select_path.set("Layer Options")

	def midi_chan(self):
		zynthian_gui_config.zyngui.screens['midich'].set_mode("SET")
		zynthian_gui_config.zyngui.screens['midich'].index=zynthian_gui_config.zyngui.screens['layer'].layers[self.layer_index].midi_chan
		zynthian_gui_config.zyngui.show_modal('midich')

	def remove_layer(self):
		zynthian_gui_config.zyngui.screens['layer'].remove_layer(self.layer_index)
		zynthian_gui_config.zyngui.show_screen('layer')

#------------------------------------------------------------------------------
