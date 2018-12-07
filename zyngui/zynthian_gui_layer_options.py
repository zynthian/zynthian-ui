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
		self.layer=None

	def fill_list(self):
		self.list_data=[]
		self.layer=zynthian_gui_config.zyngui.screens['layer'].layers[self.layer_index]
		eng_options=self.layer.engine.get_options()
		if eng_options['clone'] and self.layer.midi_chan is not None:
			self.list_data.append((self.clone,0,"Clone"))
		if eng_options['transpose']:
			self.list_data.append((self.transpose,0,"Transpose"))
		if eng_options['audio_route']:
			self.list_data.append((self.audio_routing,0,"Audio Routing"))
		if eng_options['midi_chan']:
			self.list_data.append((self.midi_chan,0,"MIDI Chan"))
		self.list_data.append((self.remove_layer,0,"Remove Layer"))
		super().fill_list()

	def show(self):
		self.index=0
		self.layer_index=zynthian_gui_config.zyngui.screens['layer'].get_layer_selected()
		if self.layer_index is not None:
			super().show()
		else:
			zynthian_gui_config.zyngui.show_active_screen()

	def select_action(self, i):
		self.list_data[i][0]()

	def set_select_path(self):
		self.select_path.set("Layer Options")

	def midi_chan(self):
		zynthian_gui_config.zyngui.screens['midi_chan'].set_mode("SET", self.layer.midi_chan)
		zynthian_gui_config.zyngui.show_modal('midi_chan')

	def clone(self):
		zynthian_gui_config.zyngui.screens['midi_chan'].set_mode("CLONE", self.layer.midi_chan)
		zynthian_gui_config.zyngui.show_modal('midi_chan')

	def transpose(self):
		zynthian_gui_config.zyngui.show_modal('transpose')

	def audio_routing(self):
		layer=zynthian_gui_config.zyngui.screens['layer'].layers[self.layer_index]
		zynthian_gui_config.zyngui.screens['audio_out'].set_layer(layer)
		zynthian_gui_config.zyngui.show_modal('audio_out')

	def remove_layer(self):
		zynthian_gui_config.zyngui.screens['layer'].remove_layer(self.layer_index)
		zynthian_gui_config.zyngui.show_screen('layer')


#------------------------------------------------------------------------------
