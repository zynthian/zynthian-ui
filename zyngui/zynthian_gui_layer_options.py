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
		if self.audiofx_layers and len(self.audiofx_layers)>0 and self.layer.engine.type!="Audio Effect":
			self.audiofx_layers.remove(self.layer)

		self.midifx_layers = self.zyngui.screens['layer'].get_midichain_layers(self.layer)
		if self.midifx_layers and len(self.midifx_layers)>0 and self.layer.engine.type!="MIDI Tool":
			self.midifx_layers.remove(self.layer)

		# Add root layer options
		if self.layer.midi_chan==256:
			eng_options = {
				'audio_capture': True,
				'indelible': True
			}
		else:
			eng_options = self.layer.engine.get_options()

		#self.list_data.append((self.layer_presets, None, "Presets"))

		if self.layer.midi_chan is not None:
			if hasattr(self.layer.engine, "save_preset"):
				self.list_data.append((self.save_preset, None, "Save Preset"))

			if 'note_range' in eng_options and eng_options['note_range']:
				self.list_data.append((self.layer_note_range, None, "Note Range & Transpose"))

			if 'clone' in eng_options and eng_options['clone'] and self.layer.midi_chan is not None:
				self.list_data.append((self.layer_clone, None, "Clone MIDI to ..."))

			if zynmixer.get_mono(self.layer.midi_chan):
				self.list_data.append((self.layer_toggle_mono, None, "[x] Audio Mono"))
			else:
				self.list_data.append((self.layer_toggle_mono, None, "[  ] Audio Mono"))

			if zynmixer.get_phase(self.layer.midi_chan):
				self.list_data.append((self.layer_toggle_phase, None, "[x] Phase reverse B"))
			else:
				self.list_data.append((self.layer_toggle_phase, None, "[  ] Phase reverse B"))

		if zynthian_gui_config.multichannel_recorder:
			if self.layer.midi_chan is not None:
				if self.zyngui.audio_recorder.get_status():
					# Recording so don't allow change of primed state
					if self.zyngui.audio_recorder.is_primed(self.layer.midi_chan):
						self.list_data.append((None, None, "[x] Recording Primed"))
					else:
						self.list_data.append((None, None, "[  ] Recording Primed"))
				else:
					if self.zyngui.audio_recorder.is_primed(self.layer.midi_chan):
						self.list_data.append((self.layer_toggle_primed, None, "[x] Recording Primed"))
					else:
						self.list_data.append((self.layer_toggle_primed, None, "[  ] Recording Primed"))

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
			self.list_data.append((self.layer_remove, None, "Remove Chain"))

		if self.layer.engine.type in ('MIDI Synth', 'MIDI Tool', 'Special') and self.layer.midi_chan is not None:
			# Add separator
			self.list_data.append((None,None,"> MIDI Chain ----------------"))

			# Add MIDI-FX chain list
			if len(self.midifx_layers)>0:
				sl0 = None
				indent = "⤷"
				for i,sl in enumerate(self.midifx_layers):
					if i and not sl.is_parallel_midi_routed(sl0):
						indent = "  " + indent
					self.list_data.append((self.sublayer_options, sl, indent + sl.engine.get_name(sl)))
					sl0 = sl

			# Add MIDI-FX options
			self.list_data.append((self.midifx_add, None, "Add MIDI-FX"))

			if len(self.midifx_layers)>0 and self.layer.engine.type=="MIDI Synth":
				self.list_data.append((self.midifx_reset, None, "Remove All MIDI-FX"))

		if self.layer.engine.type!='MIDI Tool' and self.layer.midi_chan is not None:
			# Add separator
			self.list_data.append((None,None,"> Audio Chain ---------------"))

			# Add Audio-FX chain list
			if len(self.audiofx_layers)>0:
				# Add Audio-FX layers
				sl0 = None
				indent = "⤷"
				for i,sl in enumerate(self.audiofx_layers):
					if i and not sl.is_parallel_audio_routed(sl0):
						indent = "  " + indent
					self.list_data.append((self.sublayer_options, sl, indent + sl.engine.get_name(sl)))
					sl0 = sl

			# Add Audio-FX options
			self.list_data.append((self.audiofx_add, None, "Add Audio-FX"))

			if len(self.audiofx_layers)>0 and (self.layer.engine.type=="MIDI Synth" or self.layer.midi_chan>=16):
				self.list_data.append((self.audiofx_reset, None, "Remove All Audio-FX"))

		super().fill_list()


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


	def show(self):
		if self.layer is None:
			self.setup()

		if self.layer is not None and self.layer in self.zyngui.screens['layer'].root_layers:
			super().show()
			if self.index>=len(self.list_data):
				self.index = len(self.list_data)-1
		else:
			self.zyngui.close_screen()


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


	def save_preset(self):
		if self.layer:
			self.layer.load_bank_list()
			options = {}
			options["***New bank***"] = "NEW_BANK"
			index = self.layer.get_bank_index() + 1
			for bank in self.layer.bank_list:
				if bank[0]=="*FAVS*":
					index -= 1
				else:
					options[bank[2]] = bank
			self.zyngui.screens['option'].config("Select bank...", options, self.save_preset_select_bank_cb)
			self.zyngui.show_screen('option')
			self.zyngui.screens['option'].select(index)


	def save_preset_select_bank_cb(self, bank_name, bank_info):
		self.save_preset_bank_info = bank_info
		if bank_info is "NEW_BANK":
			self.zyngui.show_keyboard(self.save_preset_select_name_cb, "NewBank")
		else:
			self.save_preset_select_name_cb()


	def save_preset_select_name_cb(self, create_bank_name=None):
		if create_bank_name is not None:
			create_bank_name = create_bank_name.strip()
		self.save_preset_create_bank_name = create_bank_name
		if self.layer.preset_name:
			self.zyngui.show_keyboard(self.save_preset_cb, self.layer.preset_name + " COPY")
		else:
			self.zyngui.show_keyboard(self.save_preset_cb, "New Preset")


	def save_preset_cb(self, preset_name):
		preset_name = preset_name.strip()
		#If must create new bank, calculate URID
		if self.save_preset_create_bank_name:
			create_bank_urid = self.layer.engine.get_user_bank_urid(self.save_preset_create_bank_name)
			self.save_preset_bank_info = (create_bank_urid, None, self.save_preset_create_bank_name, None)
		if self.layer.engine.preset_exists(self.save_preset_bank_info, preset_name):
			self.zyngui.show_confirm("Do you want to overwrite preset '{}'?".format(preset_name), self.do_save_preset, preset_name)
		else:
			self.do_save_preset(preset_name)


	def do_save_preset(self, preset_name):
		preset_name = preset_name.strip()

		try:
			# Save preset
			preset_uri = self.layer.engine.save_preset(self.save_preset_bank_info, preset_name)
			logging.info("Saved preset with name '{}' to bank '{}' => {}".format(preset_name, self.save_preset_bank_info[2], preset_uri))

			if preset_uri:
				#If must create new bank, do it!
				if self.save_preset_create_bank_name:
					self.layer.engine.create_user_bank(self.save_preset_create_bank_name)
					logging.info("Created new bank '{}' => {}".format(self.save_preset_create_bank_name, self.save_preset_bank_info[0]))
					self.layer.load_bank_list()

				self.layer.set_bank_by_id(self.save_preset_bank_info[0])
				self.layer.load_preset_list()
				self.layer.set_preset_by_id(preset_uri)
			else:
				logging.error("Can't save preset '{}' to bank '{}'".format(preset_name, self.save_preset_bank_info[2]))

		except Exception as e:
			logging.error(e)

		self.save_preset_create_bank_name = None
		self.zyngui.close_screen()
		self.zyngui.close_screen()


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
		self.zyngui.show_screen('midi_chan')


	def layer_clone(self):
		self.zyngui.screens['midi_chan'].set_mode("CLONE", self.layer.midi_chan)
		self.zyngui.show_screen('midi_chan')


	def layer_note_range(self):
		self.zyngui.screens['midi_key_range'].config(self.layer.midi_chan)
		self.zyngui.show_screen('midi_key_range')


	def layer_transpose(self):
		self.zyngui.show_screen('transpose')


	def layer_midi_routing(self):
		self.zyngui.screens['midi_out'].set_layer(self.layer)
		self.zyngui.show_screen('midi_out')


	def layer_audio_routing(self):
		self.zyngui.screens['audio_out'].set_layer(self.layer)
		self.zyngui.show_screen('audio_out')


	def layer_toggle_mono(self):
		zynmixer.toggle_mono(self.layer.midi_chan)
		self.show()


	def layer_toggle_phase(self):
		zynmixer.toggle_phase(self.layer.midi_chan)
		self.show()


	def layer_toggle_primed(self):
		self.zyngui.audio_recorder.toggle_prime(self.layer.midi_chan)
		self.show()


	def layer_audio_capture(self):
		self.zyngui.screens['audio_in'].set_layer(self.layer)
		self.zyngui.show_screen('audio_in')


	def layer_replace(self):
		self.zyngui.screens['layer'].replace_layer(self.zyngui.screens['layer'].get_layer_index(self.layer))


	def layer_remove(self):
		self.zyngui.show_confirm("Do you really want to remove this chain?", self.layer_remove_confirmed)


	def layer_remove_confirmed(self, params=None):
		self.zyngui.screens['layer'].remove_root_layer(self.layer_index)
		self.zyngui.close_screen()


	def layer_midi_unlearn(self):
		self.zyngui.show_confirm("Do you really want to clean MIDI-learn for this chain?", self.layer_midi_unlearn_confirmed)


	def layer_midi_unlearn_confirmed(self, params=None):
		self.layer.midi_unlearn()


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
			self.show()
		else:
			self.zyngui.close_screen()


	# Select Path

	def set_select_path(self):
		if self.layer:
			if self.layer.midi_chan is None or self.layer.midi_chan<16:
				self.select_path.set("{} > Chain Options".format(self.layer.get_basepath()))
			else:
				self.select_path.set("Master FX > Chain Options")
		else:
			self.select_path.set("Chain Options")


#------------------------------------------------------------------------------
