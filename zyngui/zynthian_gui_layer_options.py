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

from collections import OrderedDict
import sys
import logging

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

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
		self.midifx_layers = None


	def setup(self, layer_index=None):
		if layer_index is not None:
			self.layer_index = layer_index

		if self.layer_index is None:
			self.layer_index = self.zyngui.screens['layer'].get_root_layer_index()

		if self.layer_index is not None:
			try:
				self.layer = self.zyngui.screens['layer'].get_root_layers()[self.layer_index]
				return True
			except Exception as e:
				self.layer = None
				logging.error("Bad layer index '{}'! => {}".format(self.layer_index, e))
		else:
			self.layer = None
			logging.error("No layer index!")

		return False


	def fill_list(self):
		self.list_data = []

		self.audiofx_layers = self.zyngui.screens['layer'].get_fxchain_layers(self.layer)

		self.midifx_layers = self.zyngui.screens['layer'].get_midichain_layers(self.layer)

		# Add root layer options
		if self.layer.midi_chan == 256:
			eng_options = {
				'audio_capture': True,
				'indelible': True,
				'audio_rec': True
			}
			if zynthian_gui_config.enable_onscreen_buttons:
				eng_options['midi_learn'] = True
		else:
			eng_options = self.layer.engine.get_options()

		eng_options['midi_learn'] = True

		if self.layer.midi_chan is not None:
			if 'note_range' in eng_options and eng_options['note_range']:
				self.list_data.append((self.layer_note_range, None, "Note Range & Transpose"))

			if 'clone' in eng_options and eng_options['clone'] and self.layer.midi_chan is not None:
				self.list_data.append((self.layer_clone, None, "Clone MIDI to..."))

			self.list_data.append((self.audio_options, None, "Audio Options..."))

		if 'audio_capture' in eng_options and eng_options['audio_capture']:
			self.list_data.append((self.layer_audio_capture, None, "Audio Capture"))

		if 'audio_route' in eng_options and eng_options['audio_route']:
			self.list_data.append((self.layer_audio_routing, None, "Audio Output"))

		if 'audio_rec' in eng_options:
			if self.zyngui.audio_recorder.get_status():
				self.list_data.append((self.toggle_recording, None, "■ Stop Audio Recording"))
			else:
				self.list_data.append((self.toggle_recording, None, "⬤ Start Audio Recording"))

		if 'midi_learn' in eng_options:
			self.list_data.append((self.midi_learn, None, "MIDI Learn"))

		if 'midi_route' in eng_options and eng_options['midi_route']:
			self.list_data.append((self.layer_midi_routing, None, "MIDI Routing"))

		if 'midi_chan' in eng_options and eng_options['midi_chan']:
			self.list_data.append((self.layer_midi_chan, None, "MIDI Channel"))

		if 'indelible' not in eng_options or not eng_options['indelible']:
			self.list_data.append((self.chain_remove, None, "Remove Chain"))

		indent = 0
		in_str = ""

		if self.layer.engine.type in ('MIDI Synth', 'MIDI Tool', 'Special') and self.layer.midi_chan is not None:
			# Add separator
			self.list_data.append((None,None,"  MIDI Effects"))

			# Add MIDI-FX options
			self.list_data.append((self.midifx_add, None, "Add MIDI-FX"))

			if len(self.midifx_layers) > 0 and self.layer.engine.type == "MIDI Synth":
				self.list_data.append((self.midifx_reset, None, "Remove All MIDI-FX"))

			# Add MIDI-FX chain list
			if len(self.midifx_layers) > 0:
				sl0 = None
				for i, sl in enumerate(self.midifx_layers):
					if i and not sl.is_parallel_midi_routed(sl0):
						indent += 1
					if indent:
						in_str = "  " * indent + "⤷"
					self.list_data.append((self.sublayer_options, sl, in_str + sl.engine.get_name(sl)))
					sl0 = sl
				indent += 1

		# Root
		# Add separator
		self.list_data.append((None,None,"  Root"))
		if indent:
			in_str = "  " * indent +  "⤷"
		self.list_data.append((self.sublayer_options, self.layer, in_str + self.layer.engine.get_name(self.layer)))
		if self.layer.engine.type in ('MIDI Synth'):
			indent += 1

		if self.layer.engine.type != 'MIDI Tool' and self.layer.midi_chan is not None:
			# Add separator
			self.list_data.append((None,None,"  Audio Effects"))

			# Add Audio-FX chain list
			if len(self.audiofx_layers) > 0:
				# Add Audio-FX layers
				sl0 = None
				for i,sl in enumerate(self.audiofx_layers):
					if i and not sl.is_parallel_audio_routed(sl0):
						indent += 1
					if indent:
						in_str = "  " * indent + "⤷"
					self.list_data.append((self.sublayer_options, sl, in_str + sl.engine.get_name(sl)))
					sl0 = sl

			# Add Audio-FX options
			self.list_data.append((self.audiofx_add, None, "Add Audio-FX"))

			if len(self.audiofx_layers)>0 and (self.layer.engine.type=="MIDI Synth" or self.layer.midi_chan>=16):
				self.list_data.append((self.audiofx_reset, None, "Remove All Audio-FX"))

		super().fill_list()


	def refresh_signal(self, sname):
		if sname=="AUDIO_RECORD":
			self.fill_list()


	def search_fx_index(self, sl):
		for i,row in enumerate(self.list_data):
			if row[1]==sl:
				return i
		return 0


	def fill_listbox(self):
		super().fill_listbox()
		for i, val in enumerate(self.list_data):
			if val[0]==None:
				self.listbox.itemconfig(i, {'bg':zynthian_gui_config.color_panel_hl,'fg':zynthian_gui_config.color_tx_off})


	def build_view(self):
		if self.layer is None:
			self.setup()

		if self.layer is not None and self.layer in self.zyngui.screens['layer'].root_layers:
			super().build_view()
			if self.index>=len(self.list_data):
				self.index = len(self.list_data)-1
		else:
			self.zyngui.close_screen()


	def topbar_bold_touch_action(self):
		self.zyngui.zynswitch_defered('B', 1)


	def select_action(self, i, t='S'):
		self.index = i
		if self.list_data[i][0] is None:
			pass
		elif self.list_data[i][1] is None:
			self.list_data[i][0]()
		else:
			self.list_data[i][0](self.list_data[i][1], t)


	def sublayer_options(self, sublayer, t='S'):
		self.zyngui.screens['sublayer_options'].setup(self.layer, sublayer)
		self.zyngui.show_screen("sublayer_options")


	def layer_midi_chan(self):
		chan_list = self.zyngui.screens['layer'].get_free_midi_chans() + [self.layer.midi_chan]
		chan_list.sort()
		self.zyngui.screens['midi_chan'].set_mode("SET", self.layer.midi_chan, chan_list)
		self.zyngui.show_screen('midi_chan')


	def layer_clone(self):
		self.zyngui.screens['midi_chan'].set_mode("CLONE", self.layer.midi_chan)
		self.zyngui.show_screen('midi_chan')


	def layer_note_range(self):
		self.zyngui.screens['midi_key_range'].config(self.layer.midi_chan)
		self.zyngui.show_screen('midi_key_range')


	def layer_transpose(self):
		self.zyngui.show_screen('transpose')


	def midi_learn(self):
		options = OrderedDict()
		options['Enter MIDI-learn'] = "enter"
		options['Clean MIDI-learn'] = "clean"
		self.zyngui.screens['option'].config("MIDI-learn", options, self.midi_learn_menu_cb)
		self.zyngui.show_screen('option')


	def midi_learn_menu_cb(self, options, params):
		if params == 'enter':
			self.zyngui.close_screen()
			self.zyngui.enter_midi_learn()
		elif params == 'clean':
			self.zyngui.show_confirm("Do you want to clean MIDI-learn for ALL controls in all engines in the whole chain?", self.zyngui.screens['layer'].midi_unlearn, self.layer)


	def layer_midi_routing(self):
		self.zyngui.screens['midi_out'].set_layer(self.layer)
		self.zyngui.show_screen('midi_out')


	def layer_audio_routing(self):
		self.zyngui.screens['audio_out'].set_layer(self.layer)
		self.zyngui.show_screen('audio_out')


	def audio_options(self):
		options = OrderedDict()
		if self.zyngui.zynmixer.get_mono(self.layer.midi_chan):
			options['[x] Mono'] = 'mono'
		else:
			options['[  ] Mono'] = 'mono'
		if self.zyngui.zynmixer.get_phase(self.layer.midi_chan):
			options['[x] Phase reverse'] = 'phase'
		else:
			options['[  ] Phase reverse'] = 'phase'
		if zynthian_gui_config.multichannel_recorder:
			if self.layer.midi_chan is not None:
				if self.zyngui.audio_recorder.get_status():
					# Recording so don't allow change of primed state
					if self.zyngui.audio_recorder.is_primed(self.layer.midi_chan):
						options['[x] Recording Primed'] = None
					else:
						options['[  ] Recording Primed'] = None
				else:
					if self.zyngui.audio_recorder.is_primed(self.layer.midi_chan):
						options['[x] Recording Primed'] = 'prime'
					else:
						options['[  ] Recording Primed'] = 'prime'

		self.zyngui.screens['option'].config("Audio options", options, self.audio_menu_cb)
		self.zyngui.show_screen('option')


	def audio_menu_cb(self, options, params):
		if params == 'mono':
			self.zyngui.zynmixer.toggle_mono(self.layer.midi_chan)
		elif params == 'phase':
			self.zyngui.zynmixer.toggle_phase(self.layer.midi_chan)
		elif params == 'prime':
			self.zyngui.audio_recorder.toggle_prime(self.layer.midi_chan)
		self.audio_options()


	def layer_audio_capture(self):
		self.zyngui.screens['audio_in'].set_layer(self.layer)
		self.zyngui.show_screen('audio_in')


	def toggle_recording(self):
		self.zyngui.audio_recorder.toggle_recording()
		self.fill_list()


	def chain_remove(self):
		self.zyngui.show_confirm("Do you really want to remove this chain?", self.chain_remove_confirmed)


	def chain_remove_confirmed(self, params=None):
		self.zyngui.screens['layer'].remove_root_layer(self.layer_index)
		self.zyngui.show_screen_reset('audio_mixer')


	# FX-Chain management

	def audiofx_add(self):
		self.zyngui.screens['layer'].add_fxchain_layer(self.layer.midi_chan)


	def audiofx_reset(self):
		self.zyngui.show_confirm("Do you really want to remove all audio-FXs for this chain?", self.audiofx_reset_confirmed)


	def audiofx_reset_confirmed(self, params=None):
		# Remove all layers
		for sl in self.audiofx_layers:
			i = self.zyngui.screens['layer'].layers.index(sl)
			self.zyngui.screens['layer'].remove_layer(i)

		if self.layer in self.zyngui.screens['layer'].root_layers:
			self.build_view()
			self.show()
		else:
			self.zyngui.close_screen()


	# MIDI-Chain management

	def midifx_add(self):
		self.zyngui.screens['layer'].add_midichain_layer(self.layer.midi_chan)


	def midifx_reset(self):
		self.zyngui.show_confirm("Do you really want to remove all MIDI-FXs for this chain?", self.midifx_reset_confirmed)


	def midifx_reset_confirmed(self, params=None):
		# Remove all layers
		for sl in self.midifx_layers:
			i = self.zyngui.screens['layer'].layers.index(sl)
			self.zyngui.screens['layer'].remove_layer(i)

		if self.layer in self.zyngui.screens['layer'].root_layers:
			self.build_view()
			self.show()
		else:
			self.zyngui.close_screen()


	# Select Path

	def set_select_path(self):
		if self.layer:
			if self.layer.midi_chan is None or self.layer.midi_chan<16:
				self.select_path.set("{} > Chain Options".format(self.layer.get_basepath()))
			else:
				self.select_path.set("Main > Chain Options")
		else:
			self.select_path.set("Chain Options")


#------------------------------------------------------------------------------
