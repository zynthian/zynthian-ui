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
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector
from zynlibs.zynmixer import *

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
		self.audiofx_layers = None
		self.audiofx_layer_index = None
		self.audiofx_layer = None
		self.midifx_layers = None
		self.midifx_layer_index = None
		self.midifx_layer = None


	def fill_list(self):
		self.list_data = []

		# Effect Layer Options
		if self.audiofx_layer:
			if len(self.audiofx_layer.preset_list)>1:
				self.list_data.append((self.audiofx_presets, None, "Presets"))

			self.list_data.append((self.audiofx_replace, None, "Replace"))

			if self.audiofx_can_move_upchain():
				self.list_data.append((self.audiofx_move_upchain, None, "Move Upchain"))

			if self.audiofx_can_move_downchain():
				self.list_data.append((self.audiofx_move_downchain, None, "Move Downchain"))

			self.list_data.append((self.audiofx_remove, None, "Remove"))

		elif self.midifx_layer:
			if len(self.midifx_layer.preset_list)>1:
				self.list_data.append((self.midifx_presets, None, "Presets"))

			self.list_data.append((self.midifx_replace, None, "Replace"))

			if self.midifx_can_move_upchain():
				self.list_data.append((self.midifx_move_upchain, None, "Move Upchain"))

			if self.midifx_can_move_downchain():
				self.list_data.append((self.midifx_move_downchain, None, "Move Downchain"))

			self.list_data.append((self.midifx_remove, None, "Remove"))

		# Root Layer Options
		else:
			self.layer = self.zyngui.screens['layer'].get_root_layers()[self.layer_index]

			self.audiofx_layers = self.zyngui.screens['layer'].get_fxchain_layers(self.layer)
			if self.audiofx_layers and len(self.audiofx_layers)>0 and self.layer.engine.type!="Audio Effect":
				self.audiofx_layers.remove(self.layer)

			self.midifx_layers = self.zyngui.screens['layer'].get_midichain_layers(self.layer)
			if self.midifx_layers and len(self.midifx_layers)>0 and self.layer.engine.type!="MIDI Tool":
				self.midifx_layers.remove(self.layer)

			# Add root layer options
			eng_options = self.layer.engine.get_options()

			#self.list_data.append((self.layer_presets, None, "Presets"))

			if self.layer.midi_chan is not None:
				if 'note_range' in eng_options and eng_options['note_range']:
					self.list_data.append((self.layer_note_range, None, "Note Range & Transpose"))

				if 'clone' in eng_options and eng_options['clone'] and self.layer.midi_chan is not None:
					self.list_data.append((self.layer_clone, None, "Clone MIDI to ..."))

				if zynmixer.get_mono(self.layer.midi_chan):
					self.list_data.append((self.layer_toggle_mono, None, "[x] Audio Mono"))
				else:
					self.list_data.append((self.layer_toggle_mono, None, "[  ] Audio Mono"))

			if 'audio_capture' in eng_options and eng_options['audio_capture']:
				self.list_data.append((self.layer_audio_capture, None, "Audio Capture"))

			if 'audio_route' in eng_options and eng_options['audio_route']:
				self.list_data.append((self.layer_audio_routing, None, "Audio Output"))

			if 'midi_route' in eng_options and eng_options['midi_route']:
				self.list_data.append((self.layer_midi_routing, None, "MIDI Routing"))

			if 'midi_chan' in eng_options and eng_options['midi_chan']:
				self.list_data.append((self.layer_midi_chan, None, "MIDI Channel"))

			self.list_data.append((self.layer_midi_unlearn, None, "Clean MIDI-Learn"))

			if self.layer.engine.type=="MIDI Synth" and 'replace' in eng_options and eng_options['midi_chan']:
				self.list_data.append((self.layer_replace, None, "Replace Synth"))

			if 'indelible' not in eng_options or not eng_options['indelible']:
				self.list_data.append((self.layer_remove, None, "Remove Layer"))

			if self.layer.engine.type!='MIDI Tool':
				# Add separator
				self.list_data.append((None,None,"-----------------------------"))

				# Add Audio-FX options
				if self.layer.midi_chan is not None:
					self.list_data.append((self.audiofx_add, None, "Add Audio-FX"))

				if len(self.audiofx_layers)>0:
					if self.layer.engine.type=="MIDI Synth":
						self.list_data.append((self.audiofx_reset, None, "Remove All Audio-FX"))
					# Add Audio-FX layers
					sl0 = None
					for sl in self.audiofx_layers:
						if sl.is_parallel_audio_routed(sl0):
							bullet = " || "
						else:
							bullet = " -> "
						self.list_data.append((self.audiofx_layer_action, sl, bullet + sl.engine.get_path(sl)))
						sl0 = sl

			if self.layer.engine.type in ('MIDI Synth', 'MIDI Tool', 'Special') and self.layer.engine.nickname!='MD':
				# Add separator
				self.list_data.append((None,None,"-----------------------------"))

				# Add MIDI-FX options
				if self.layer.midi_chan is not None:
					self.list_data.append((self.midifx_add, None, "Add MIDI-FX"))

				if len(self.midifx_layers)>0:
					if self.layer.engine.type=="MIDI Synth":
						self.list_data.append((self.midifx_reset, None, "Remove All MIDI-FX"))
					# Add MIDI-FX layers
					sl0 = None
					for sl in self.midifx_layers:
						if sl.is_parallel_midi_routed(sl0):
							bullet = " || "
						else:
							bullet = " -> "
						self.list_data.append((self.midifx_layer_action, sl, bullet + sl.engine.get_path(sl)))
						sl0 = sl

		super().fill_list()


	def search_fx_index(self, sl):
		for i,row in enumerate(self.list_data):
			if row[1]==sl:
				return i
		return 0


	def show(self):
		if self.layer_index is None:
			self.layer_index = self.zyngui.screens['layer'].get_root_layer_index()

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


	def audiofx_layer_action(self, layer, t='S'):
		self.index = 0
		self.audiofx_layer = layer
		self.audiofx_layer_index = self.zyngui.screens['layer'].layers.index(layer)
		self.show()


	def midifx_layer_action(self, layer, t='S'):
		self.index = 0
		self.midifx_layer = layer
		self.midifx_layer_index = self.zyngui.screens['layer'].layers.index(layer)
		self.show()


	def back_action(self):
		if self.audiofx_layer or self.midifx_layer:
			if self.audiofx_layer:
				sl = self.audiofx_layer
			else:
				sl = self.midifx_layer

			# Back to layer options
			self.reset()
			self.show()

			# Recover cursor position
			self.index = self.search_fx_index(sl)
			self.select()

		return False


	def layer_presets(self):
		self.zyngui.set_curlayer(self.layer)
		self.zyngui.show_screen('bank')
		# If there is only one bank, jump to preset selection
		if len(self.layer.bank_list)<=1:
			self.zyngui.screens['bank'].select_action(0)


	def layer_midi_chan(self):
		chan_list = self.zyngui.screens['layer'].get_free_midi_chans() + [self.layer.midi_chan]
		chan_list.sort()
		self.zyngui.screens['midi_chan'].set_mode("SET", self.layer.midi_chan, chan_list)
		self.zyngui.show_modal('midi_chan')


	def layer_clone(self):
		self.zyngui.screens['midi_chan'].set_mode("CLONE", self.layer.midi_chan)
		self.zyngui.show_screen('midi_chan')


	def layer_note_range(self):
		self.zyngui.screens['midi_key_range'].config(self.layer.midi_chan)
		self.zyngui.show_modal('midi_key_range')


	def layer_transpose(self):
		self.zyngui.show_modal('transpose')


	def layer_midi_routing(self):
		self.zyngui.screens['midi_out'].set_layer(self.layer)
		self.zyngui.show_modal('midi_out')


	def layer_audio_routing(self):
		self.zyngui.screens['audio_out'].set_layer(self.layer)
		self.zyngui.show_modal('audio_out')


	def layer_toggle_mono(self):
		zynmixer.toggle_mono(self.layer.midi_chan)
		self.show()


	def layer_audio_capture(self):
		self.zyngui.screens['audio_in'].set_layer(self.layer)
		self.zyngui.show_modal('audio_in')


	def layer_replace(self):
		self.zyngui.screens['layer'].replace_layer(self.zyngui.screens['layer'].get_layer_index(self.layer))


	def layer_remove(self):
		self.zyngui.show_confirm("Do you really want to remove this layer?", self.layer_remove_confirmed)


	def layer_remove_confirmed(self, params=None):
		self.zyngui.screens['layer'].remove_root_layer(self.layer_index)
		self.zyngui.close_screen()


	def layer_midi_unlearn(self):
		self.zyngui.show_confirm("Do you really want to clean MIDI-learn for this layer?", self.layer_midi_unlearn_confirmed)


	def layer_midi_unlearn_confirmed(self, params=None):
		self.layer.midi_unlearn()


	# FX-Chain management

	def audiofx_add(self):
		self.zyngui.screens['layer'].add_fxchain_layer(self.layer.midi_chan)


	def audiofx_reset(self):
		self.zyngui.show_confirm("Do you really want to remove all audio-FXs for this layer?", self.audiofx_reset_confirmed)


	def audiofx_reset_confirmed(self, params=None):
		# Remove all layers
		for sl in self.audiofx_layers:
			i = self.zyngui.screens['layer'].layers.index(sl)
			self.zyngui.screens['layer'].remove_layer(i)

		self.reset()
		self.show()


	def audiofx_presets(self):
		self.zyngui.set_curlayer(self.audiofx_layer, True)
		self.zyngui.show_screen('bank')
		# If there is only one bank, jump to preset selection
		if len(self.audiofx_layer.bank_list)<=1:
			self.zyngui.screens['bank'].select_action(0)


	def audiofx_can_move_upchain(self):
		ups = self.zyngui.screens['layer'].get_fxchain_upstream(self.audiofx_layer)
		if len(ups)>0 and (self.layer.engine.type!="MIDI Synth" or self.layer not in ups):
			return True


	def audiofx_move_upchain(self):
		ups = self.zyngui.screens['layer'].get_fxchain_upstream(self.audiofx_layer)
		self.zyngui.screens['layer'].swap_fxchain(ups[0], self.audiofx_layer)
		self.back_action()


	def audiofx_can_move_downchain(self):
		downs = self.zyngui.screens['layer'].get_fxchain_downstream(self.audiofx_layer)
		if len(downs)>0 and (self.layer.engine.type!="MIDI Synth" or self.layer not in downs):
			return True


	def audiofx_move_downchain(self):
		downs = self.zyngui.screens['layer'].get_fxchain_downstream(self.audiofx_layer)
		self.zyngui.screens['layer'].swap_fxchain(self.audiofx_layer, downs[0])
		self.back_action()


	def audiofx_replace(self):
		self.zyngui.screens['layer'].replace_fxchain_layer(self.audiofx_layer_index)


	def audiofx_remove(self):
		self.zyngui.screens['layer'].remove_layer(self.audiofx_layer_index)
		self.back_action()


	# MIDI-Chain management

	def midifx_add(self):
		self.zyngui.screens['layer'].add_midichain_layer(self.layer.midi_chan)


	def midifx_reset(self):
		self.zyngui.show_confirm("Do you really want to remove all MIDI-FXs for this layer?", self.midifx_reset_confirmed)


	def midifx_reset_confirmed(self, params=None):
		# Remove all layers
		for sl in self.midifx_layers:
			i = self.zyngui.screens['layer'].layers.index(sl)
			self.zyngui.screens['layer'].remove_layer(i)

		self.reset()
		self.show()


	def midifx_presets(self):
		self.zyngui.set_curlayer(self.midifx_layer, True)
		self.zyngui.show_modal('bank')
		# If there is only one bank, jump to preset selection
		if len(self.midifx_layer.bank_list)<=1:
			self.zyngui.screens['bank'].select_action(0)


	def midifx_can_move_upchain(self):
		ups = self.zyngui.screens['layer'].get_midichain_upstream(self.midifx_layer)
		if len(ups)>0 and (self.layer.engine.type!="MIDI Synth" or self.layer not in ups):
			return True


	def midifx_move_upchain(self):
		ups = self.zyngui.screens['layer'].get_midichain_upstream(self.midifx_layer)
		self.zyngui.screens['layer'].swap_midichain(ups[0], self.midifx_layer)
		self.back_action()


	def midifx_can_move_downchain(self):
		downs = self.zyngui.screens['layer'].get_midichain_downstream(self.midifx_layer)
		if len(downs)>0 and (self.layer.engine.type!="MIDI Synth" or self.layer not in downs):
			return True


	def midifx_move_downchain(self):
		downs = self.zyngui.screens['layer'].get_midichain_downstream(self.midifx_layer)
		self.zyngui.screens['layer'].swap_midichain(self.midifx_layer, downs[0])
		self.back_action()


	def midifx_replace(self):
		self.zyngui.screens['layer'].replace_midichain_layer(self.midifx_layer_index)


	def midifx_remove(self):
		self.zyngui.screens['layer'].remove_layer(self.midifx_layer_index)
		self.back_action()


	# Select Path

	def set_select_path(self):
		if self.audiofx_layer:
			self.select_path.set("{} > Audio-FX Options".format(self.audiofx_layer.get_basepath()))
		elif self.midifx_layer:
			self.select_path.set("{} > MIDI-FX Options".format(self.midifx_layer.get_basepath()))
		elif self.layer:
			self.select_path.set("{} > Layer Options".format(self.layer.get_basepath()))
		else:
			self.select_path.set("Layer Options")


#------------------------------------------------------------------------------
