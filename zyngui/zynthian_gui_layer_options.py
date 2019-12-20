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
# Zynthian Layer Options GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_layer_options(zynthian_gui_selector):


	def __init__(self):
		self.reset()
		super().__init__('Option', True)


	def reset(self):
		self.index = 0
		self.layer_index = None
		self.layer = None
		self.sublayers = None
		self.sublayer_index = None
		self.sublayer = None
		self.detailed_list = False


	def fill_list(self):
		self.list_data = []

		# Effect Layer Options
		if self.sublayer:
			if len(self.sublayer.preset_list)>1:
				self.list_data.append((self.fx_presets, None, "Effect Presets"))

			if self.can_move_upchain():
				self.list_data.append((self.fx_move_upchain, None, "Move Upchain"))

			if self.can_move_downchain():
				self.list_data.append((self.fx_move_downchain, None, "Move Downchain"))

			self.list_data.append((self.fx_remove, None, "Remove Effect"))

		# Root Layer Options
		else:
			self.layer = self.zyngui.screens['layer'].root_layers[self.layer_index]

			#Change to sublayer mode if not root layer selected => Detailed List!
			root_layer = self.zyngui.screens['layer'].get_fxchain_root(self.layer)
			if root_layer!=self.layer:
				self.detailed_list = True
				self.sublayer = self.layer
				self.sublayer_index = self.zyngui.screens['layer'].layers.index(self.sublayer)
				self.layer = root_layer
				self.fill_list()
				return
			
			self.sublayers = self.zyngui.screens['layer'].get_fxchain_layers(self.layer)
			self.sublayers.remove(self.layer)

			# Add root layer options
			eng_options = self.layer.engine.get_options()

			#self.list_data.append((self.layer_presets, None, "Presets"))

			if 'clone' in eng_options and eng_options['clone'] and self.layer.midi_chan is not None:
				self.list_data.append((self.layer_clone, None, "Clone MIDI to ..."))

			if 'transpose' in eng_options and eng_options['transpose']:
				self.list_data.append((self.layer_transpose, None, "Transpose"))

			if 'audio_route' in eng_options and eng_options['audio_route']:
				self.list_data.append((self.layer_audio_routing, None, "Audio Routing"))

			if 'midi_chan' in eng_options and eng_options['midi_chan']:
				self.list_data.append((self.layer_midi_chan, None, "MIDI Channel"))

			if 'indelible' not in eng_options or not eng_options['indelible']:
				self.list_data.append((self.layer_remove, None, "Remove Layer"))

			# Add separator
			self.list_data.append((None,None,"-----------------------------"))

			# Add FX-chain options
			if self.layer.midi_chan is not None:
				self.list_data.append((self.fxchain_add, None, "Add Effect"))

			if len(self.sublayers)>0:
				self.list_data.append((self.fxchain_reset, None, "Remove All Effects"))

				# Add separator
				self.list_data.append((None,None,"-----------------------------"))

				# Add effect layers
				for sl in self.sublayers:
					self.list_data.append((self.sublayer_action, sl, sl.engine.get_path(sl)))

		super().fill_list()


	def show(self):
		if self.layer_index is None:
			self.layer_index = self.zyngui.screens['layer'].index

		if self.layer_index is not None:
			super().show()
			if self.index>=len(self.list_data):
				self.index = len(self.list_data)-1

		else:
			self.zyngui.show_active_screen()


	def select_action(self, i, t='S'):
		self.index = i

		if self.list_data[i][0] is None:
			pass

		elif self.list_data[i][1] is None:
			self.list_data[i][0]()

		else:
			self.list_data[i][0](self.list_data[i][1], t)


	def sublayer_action(self, sublayer, t='S'):
		self.index = 0
		self.sublayer = sublayer
		self.sublayer_index = self.zyngui.screens['layer'].layers.index(sublayer)

		if t=='S':
			if len(self.sublayer.preset_list):
				self.fx_presets()
			else:
				self.show()

		elif t=='B':
			self.show()


	def back_action(self):
		if self.sublayer and not self.detailed_list:
			sl = self.sublayer
			self.reset()
			self.show()

			# Recover cursor position
			if len(self.sublayers)>0:
				self.index = len(self.list_data) - len(self.sublayers)
				try:
					self.index += self.sublayers.index(sl)
				except:
					pass

			else:
				self.index = len(self.list_data) - 1

			self.select()
			return ''

		else:
			return None


	def layer_presets(self):
		self.zyngui.set_curlayer(self.layer)
		self.zyngui.show_screen('bank')
		# If there is only one bank, jump to preset selection
		if len(self.layer.bank_list)<=1:
			self.zyngui.screens['bank'].select_action(0)


	def layer_midi_chan(self):
		self.zyngui.screens['midi_chan'].set_mode("SET", self.layer.midi_chan, self.zyngui.screens['layer'].get_free_midi_chans())
		self.zyngui.show_modal('midi_chan')


	def layer_clone(self):
		self.zyngui.screens['midi_chan'].set_mode("CLONE", self.layer.midi_chan)
		self.zyngui.show_modal('midi_chan')


	def layer_transpose(self):
		self.zyngui.show_modal('transpose')


	def layer_audio_routing(self):
		self.zyngui.screens['audio_out'].set_layer(self.layer)
		self.zyngui.show_modal('audio_out')


	def layer_remove(self):
		self.zyngui.screens['layer'].remove_root_layer(self.layer_index)
		self.zyngui.show_screen('layer')


	def fxchain_add(self):
		midi_chan=self.layer.midi_chan
		self.zyngui.screens['layer'].add_fxchain_layer(midi_chan)


	def fxchain_reset(self):
		# Remove all sublayers
		for sl in self.sublayers:
			i = self.zyngui.screens['layer'].layers.index(sl)
			self.zyngui.screens['layer'].remove_layer(i)

		self.reset()
		self.show()


	def fx_presets(self):
		self.zyngui.set_curlayer(self.sublayer)
		self.zyngui.show_screen('bank')
		# If there is only one bank, jump to preset selection
		if len(self.layer.bank_list)<=1:
			self.zyngui.screens['bank'].select_action(0)


	def can_move_upchain(self):
		ups = self.zyngui.screens['layer'].get_fxchain_upstream(self.sublayer)
		if len(ups)>0 and self.layer not in ups:
			return True


	def fx_move_upchain(self):
		ups = self.zyngui.screens['layer'].get_fxchain_upstream(self.sublayer)
		self.zyngui.screens['layer'].swap_fxchain(ups[0], self.sublayer)
		
		if self.detailed_list:
			self.zyngui.show_screen('layer')
		else:
			self.back_action()


	def can_move_downchain(self):
		downs = self.zyngui.screens['layer'].get_fxchain_downstream(self.sublayer)
		if len(downs)>0 and self.layer not in downs:
			return True


	def fx_move_downchain(self):
		downs = self.zyngui.screens['layer'].get_fxchain_downstream(self.sublayer)
		self.zyngui.screens['layer'].swap_fxchain(self.sublayer, downs[0])

		if self.detailed_list:
			self.zyngui.show_screen('layer')
		else:
			self.back_action()


	def fx_remove(self):
		self.zyngui.screens['layer'].remove_layer(self.sublayer_index)

		if self.detailed_list:
			self.zyngui.show_screen('layer')
		else:
			self.back_action()


	def set_select_path(self):
		if self.sublayer:
			self.select_path.set("{} > Options".format(self.sublayer.get_basepath()))
		elif self.layer:
			self.select_path.set("{} > Options".format(self.layer.get_basepath()))
		else:
			self.select_path.set("Layer Options")


#------------------------------------------------------------------------------
