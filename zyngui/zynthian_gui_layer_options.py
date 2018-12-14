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
		self.reset()
		super().__init__('Option', True)


	def reset(self):
		self.layer_index = None
		self.layer = None
		self.sublayers = None


	def fill_list(self):
		self.list_data = []
		
		if not self.layer:
			root_layer_options = True
			self.layer = zynthian_gui_config.zyngui.screens['layer'].root_layers[self.layer_index]
			# Add fxchain layers
			self.sublayers = zynthian_gui_config.zyngui.screens['layer'].get_fxchain_layers(self.layer)
			if self.sublayers:
				self.sublayers.remove(self.layer)
				for sl in self.sublayers:
					self.list_data.append((self.sublayer_options, len(self.list_data), sl.get_basepath()))

				# Add separator
				if len(self.sublayers)>0:
					self.list_data.append((None,len(self.list_data),"--------------------------"))

		else:
			root_layer_options = False

		# Add layer options

		if root_layer_options:
			eng_options = self.layer.engine.get_options()

			if eng_options['clone'] and self.layer.midi_chan is not None:
				self.list_data.append((self.clone, len(self.list_data), "Clone"))

			if eng_options['transpose']:
				self.list_data.append((self.transpose, len(self.list_data), "Transpose"))

			if eng_options['audio_route']:
				self.list_data.append((self.audio_routing, len(self.list_data), "Audio Routing"))

			if eng_options['midi_chan']:
				self.list_data.append((self.midi_chan, len(self.list_data), "MIDI Chan"))

		self.list_data.append((self.remove_layer, len(self.list_data), "Remove Layer"))
		super().fill_list()


	def show(self):
		self.index = 0
		self.layer_index = zynthian_gui_config.zyngui.screens['layer'].get_layer_selected()

		if self.layer_index is not None:
			super().show()
		else:
			zynthian_gui_config.zyngui.show_active_screen()


	def select_action(self, i):
		self.index = i

		if self.list_data[i][0] is None:
			pass

		else:
			self.list_data[i][0]()


	def sublayer_options(self):
		self.layer = self.sublayers[self.index]
		self.layer_index = zynthian_gui_config.zyngui.screens['layer'].layers.index(self.layer)
		self.show()


	def midi_chan(self):
		zynthian_gui_config.zyngui.screens['midi_chan'].set_mode("SET", self.layer.midi_chan)
		zynthian_gui_config.zyngui.show_modal('midi_chan')


	def clone(self):
		zynthian_gui_config.zyngui.screens['midi_chan'].set_mode("CLONE", self.layer.midi_chan)
		zynthian_gui_config.zyngui.show_modal('midi_chan')


	def transpose(self):
		zynthian_gui_config.zyngui.show_modal('transpose')


	def audio_routing(self):
		zynthian_gui_config.zyngui.screens['audio_out'].set_layer(self.layer)
		zynthian_gui_config.zyngui.show_modal('audio_out')


	def remove_layer(self):
		if self.layer in zynthian_gui_config.zyngui.screens['layer'].root_layers:
			zynthian_gui_config.zyngui.screens['layer'].remove_root_layer(self.layer_index)
			zynthian_gui_config.zyngui.show_screen('layer')
		else:
			zynthian_gui_config.zyngui.screens['layer'].remove_layer(self.layer_index)
			self.reset()
			self.show()


	def set_select_path(self):
		if self.layer:
			self.select_path.set("{} > Layer Options".format(self.layer.get_basepath()))
		else:
			self.select_path.set("Layer Options")

#------------------------------------------------------------------------------
