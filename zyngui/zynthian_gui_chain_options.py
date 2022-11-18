#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Chain Options Class
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
import logging

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian Chain Options GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_chain_options(zynthian_gui_selector):

	def __init__(self):
		super().__init__('Option', True)
		self.setup(None)


	def setup(self, chain_id=None):
		self.index = 0
		if chain_id is not None:
			self.chain_id = chain_id
		self.chain = self.zyngui.chain_manager.get_chain(chain_id)


	def fill_list(self):
		self.list_data = []

		# Add root chain options
		if self.chain_id == "main":
			eng_options = {
				'audio_capture': False,
				'indelible': True,
				'audio_rec': True,
				'audio_route': True,
				'midi_learn': True
			}
		if self.chain.synth_processor:
			eng_options = self.chain.synth_processor.engine.get_options()
		else:
			eng_options = {}

		#TODO Disable midi learn for some chains???
	
		if self.chain.midi_chan is not None:
			if 'note_range' in eng_options and eng_options['note_range']:
				self.list_data.append((self.chain_note_range, None, "Note Range & Transpose"))

			if 'clone' in eng_options and eng_options['clone']:
				self.list_data.append((self.chain_clone, None, "Clone MIDI to..."))

		if self.chain.mixer_chan is not None:
			self.list_data.append((self.audio_options, None, "Audio Options..."))

		if 'audio_capture' in eng_options and eng_options['audio_capture'] or self.chain.audio_thru:
			self.list_data.append((self.chain_audio_capture, None, "Audio Capture..."))

		if 'audio_route' in eng_options and eng_options['audio_route'] or self.chain.is_audio:
			self.list_data.append((self.chain_audio_routing, None, "Audio Output..."))

		if 'audio_rec' in eng_options:
			if self.zyngui.audio_recorder.get_status():
				self.list_data.append((self.toggle_recording, None, "■ Stop Audio Recording"))
			else:
				self.list_data.append((self.toggle_recording, None, "⬤ Start Audio Recording"))

		if 'midi_learn' in eng_options:
			self.list_data.append((self.midi_learn, None, "MIDI Learn"))

		if 'midi_route' in eng_options and eng_options['midi_route']:
			self.list_data.append((self.chain_midi_routing, None, "MIDI Routing"))

		if 'midi_chan' in eng_options and eng_options['midi_chan']:
			self.list_data.append((self.chain_midi_chan, None, "MIDI Channel"))


		self.list_data.append((None, None, "> Chain"))

		if self.chain.synth_processor or self.chain.midi_thru:
			# Add MIDI-FX options
			self.list_data.append((self.midifx_add, None, "Add MIDI-FX"))

		self.list_data += self.generate_chaintree_menu()

		if self.chain.is_audio():
			# Add Audio-FX options
			self.list_data.append((self.audiofx_add, None, "Add Audio-FX"))

		if self.chain.get_processor_count("MIDI Tool") + self.chain.get_processor_count("Audio Effect") == 0:
			self.list_data.append((self.remove_chain, None, "Remove Chain"))
		else:
			self.list_data.append((self.remove_cb, None, "Remove..."))

		super().fill_list()


	# Generate chain tree menu
	def generate_chaintree_menu(self):
		res = []
		indent = 0
		# Build MIDI chain
		for slot in range(self.chain.get_slot_count("MIDI Tool")):
			procs = self.chain.get_processors("MIDI Tool")
			num_procs = len(procs)
			for index, processor in enumerate(procs):
				name = processor.engine.get_name(self.chain)
				if index == num_procs - 1:
					res.append((self.processor_options, processor, "  " * indent + "╰─ " + name))
				else:
					res.append((self.processor_options, processor, "  " * indent + "├─ " + name))
			indent += 1
		# Add synth processor
		if self.chain.synth_processor:
			res.append((self.processor_options, self.chain.synth_processor, "  " * indent + "╰━ " + self.chain.synth_processor.engine.get_name(self.chain)))
			indent += 1
		# Build audio effects chain
		for slot in range(self.chain.get_slot_count("Audio Effect")):
			procs = self.chain.get_processors("Audio Effect", slot)
			num_procs = len(procs)
			for index, processor in enumerate(procs):
				name = processor.engine.get_name(self.chain)
				if index == num_procs - 1:
					res.append((self.processor_options, processor, "  " * indent + "┗━ " + name))
				else:
					res.append((self.processor_options, processor, "  " * indent + "┣━ " + name))
			indent += 1
		return res


	def refresh_signal(self, sname):
		if sname=="AUDIO_RECORD":
			self.fill_list()

	def fill_listbox(self):
		super().fill_listbox()
		for i, val in enumerate(self.list_data):
			if val[0]==None:
				self.listbox.itemconfig(i, {'bg':zynthian_gui_config.color_panel_hl,'fg':zynthian_gui_config.color_tx_off})


	def build_view(self):
		if self.chain is None:
			self.setup()

		if self.chain is not None:
			super().build_view()
			if self.index >= len(self.list_data):
				self.index = len(self.list_data) - 1
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


	def back_action(self):
		#TODO: What behaviour?
		if self.chain.engine.type in ("Audio Effect", "MIDI Tool") and len(self.midifx_chains) + len(self.audiofx_chains) == 0:
			self.zyngui.show_screen_reset('audio_mixer')
			return True
		return False


	def processor_options(self, subchain, t='S'):
		self.zyngui.screens['processor_options'].setup(self.chain_id, subchain)
		self.zyngui.show_screen("processor_options")


	def chain_midi_chan(self):
		chan_list = self.zyngui.chain_manager.get_free_midi_chans() + [self.chain.midi_chan]
		chan_list.sort()
		self.zyngui.screens['midi_chan'].set_mode("SET", self.chain.midi_chan, chan_list)
		self.zyngui.show_screen('midi_chan')


	def chain_clone(self):
		self.zyngui.screens['midi_chan'].set_mode("CLONE", self.chain.midi_chan)
		self.zyngui.show_screen('midi_chan')


	def chain_note_range(self):
		self.zyngui.screens['midi_key_range'].config(self.chain.midi_chan)
		self.zyngui.show_screen('midi_key_range')


	def chain_transpose(self):
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
			self.zyngui.show_confirm("Do you want to clean MIDI-learn for ALL controls in all engines in the whole chain?", self.zyngui.screens['chain'].midi_unlearn, self.chain)


	def chain_midi_routing(self):
		self.zyngui.screens['midi_out'].set_chain(self.chain)
		self.zyngui.show_screen('midi_out')


	def chain_audio_routing(self):
		self.zyngui.screens['audio_out'].set_chain(self.chain_id)
		self.zyngui.show_screen('audio_out')


	def audio_options(self):
		options = OrderedDict()
		if self.zyngui.state_manager.zynmixer.get_mono(self.chain.mixer_chan):
			options['[x] Mono'] = 'mono'
		else:
			options['[  ] Mono'] = 'mono'
		if self.zyngui.state_manager.zynmixer.get_phase(self.chain.mixer_chan):
			options['[x] Phase reverse'] = 'phase'
		else:
			options['[  ] Phase reverse'] = 'phase'

		self.zyngui.screens['option'].config("Audio options", options, self.audio_menu_cb)
		self.zyngui.show_screen('option')


	def audio_menu_cb(self, options, params):
		if params == 'mono':
			self.zyngui.state_manager.zynmixer.toggle_mono(self.chain.midi_chan)
		elif params == 'phase':
			self.zyngui.state_manager.zynmixer.toggle_phase(self.chain.midi_chan)
		self.audio_options()


	def chain_audio_capture(self):
		self.zyngui.screens['audio_in'].set_chain(self.chain)
		self.zyngui.show_screen('audio_in')


	def toggle_recording(self):
		self.zyngui.audio_recorder.toggle_recording()
		self.fill_list()


	# Remove submenu

	def remove_cb(self):
		options = OrderedDict()
		if self.chain.get_processor_count("MIDI Tool"):
			options['Remove All MIDI-FXs'] = "midifx"
		if self.chain.get_processor_count("Audio Effect"):
			options['Remove All Audio-FXs'] = "audiofx"
		if self.chain_id != "main":
			options['Remove Chain'] = "chain"
		self.zyngui.screens['option'].config("Remove...", options, self.remove_all_cb)
		self.zyngui.show_screen('option')


	def remove_all_cb(self, options, params):
		if params == 'midifx':
			self.remove_all_midifx()
		elif params == 'audiofx':
			self.remove_all_audiofx()
		elif params == 'chain':
			self.remove_chain()


	def remove_chain(self, params=None):
		self.zyngui.show_confirm("Do you really want to remove this chain?", self.chain_remove_confirmed)


	def chain_remove_confirmed(self, params=None):
		self.zyngui.chain_manager.remove_chain(self.chain_id)
		self.zyngui.show_screen_reset('audio_mixer')


	# FX-Chain management

	def audiofx_add(self):
		self.zyngui.add_chain({"type":"Audio Effect", "chain_id":self.chain_id})


	def remove_all_audiofx(self):
		self.zyngui.show_confirm("Do you really want to remove all audio effects from this chain?", self.remove_all_procs_cb, "Audio Effect")


	def remove_all_procs_cb(self, type=None):
		for processor in self.chain.get_processors(type):
			self.zyngui.chain_manager.remove_processor(self.chain_id, processor)
		self.build_view()
		self.show()


	# MIDI-Chain management

	def midifx_add(self):
		self.zyngui.screens['chain'].add_midichain_chain(self.chain.midi_chan)


	def remove_all_midifx(self):
		self.zyngui.show_confirm("Do you really want to remove all MIDI effects from this chain?", self.remove_all_procs_cb, "MIDI Tool")


	# Select Path

	def set_select_path(self):
		try:
			self.select_path.set("{} > Chain Options".format(self.chain_id))
		except:
			self.select_path.set("Chain Options")


#------------------------------------------------------------------------------
