#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Chain Options Class
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
#
# ******************************************************************************
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
# ******************************************************************************

import logging

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

# ------------------------------------------------------------------------------
# Zynthian Chain Options GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_chain_options(zynthian_gui_selector):

	def __init__(self):
		super().__init__('Option', True)
		self.index = 0
		self.chain = None
		self.chain_id = None
		self.processor = None

	def setup(self, chain_id=None, proc=None):
		self.index = 0
		self.chain = self.zyngui.chain_manager.get_chain(chain_id)
		self.chain_id = self.chain.chain_id
		self.processor = proc

	def fill_list(self):
		self.list_data = []

		synth_proc_count = self.chain.get_processor_count("Synth")
		midi_proc_count = self.chain.get_processor_count("MIDI Tool")
		audio_proc_count = self.chain.get_processor_count("Audio Effect")

		if self.chain.is_midi():
			self.list_data.append((self.chain_note_range, None, "Note Range & Transpose"))
			self.list_data.append((self.chain_midi_capture, None, "MIDI In"))

		if self.chain.midi_thru:
			self.list_data.append((self.chain_midi_routing, None, "MIDI Out"))

		if self.chain.is_midi():
			try:
				if synth_proc_count == 0 or self.chain.synth_slots[0][0].engine.options["midi_chan"]:
					self.list_data.append((self.chain_midi_chan, None, "MIDI Channel"))
			except Exception as e:
				logging.error(e)

		if synth_proc_count:
			self.list_data.append((self.chain_midi_cc, None, "MIDI CC"))

		if self.chain.get_processor_count() and not zynthian_gui_config.check_wiring_layout(["Z2", "V5"]):
			# TODO Disable midi learn for some chains???
			self.list_data.append((self.midi_learn, None, "MIDI Learn"))

		if self.chain.audio_thru and self.chain_id != 0:
			self.list_data.append((self.chain_audio_capture, None, "Audio In"))

		if self.chain.is_audio():
			self.list_data.append((self.chain_audio_routing, None, "Audio Out"))

		if self.chain.is_audio():
			self.list_data.append((self.audio_options, None, "Audio Options"))

		if self.chain_id == 0 and not zynthian_gui_config.check_wiring_layout(["Z2", "V5"]):
			if self.zyngui.state_manager.audio_recorder.status:
				self.list_data.append((self.toggle_recording, None, "■ Stop Audio Recording"))
			else:
				self.list_data.append((self.toggle_recording, None, "⬤ Start Audio Recording"))

		self.list_data.append((None, None, "> Processors"))

		if self.chain.is_midi():
			# Add MIDI-FX options
			self.list_data.append((self.midifx_add, None, "Add MIDI-FX"))

		self.list_data += self.generate_chaintree_menu()

		if self.chain.is_audio():
			# Add Audio-FX options
			self.list_data.append((self.audiofx_add, None, "Add Pre-fader Audio-FX"))
			self.list_data.append((self.postfader_add, None, "Add Post-fader Audio-FX"))

		if self.chain_id != 0:
			if synth_proc_count * midi_proc_count + audio_proc_count == 0:
				self.list_data.append((self.remove_chain, None, "Remove Chain"))
			else:
				self.list_data.append((self.remove_cb, None, "Remove..."))
		elif audio_proc_count > 0:
			self.list_data.append((self.remove_all_audiofx, None, "Remove all Audio-FX"))

		self.list_data.append((None, None, "> GUI"))
		self.list_data.append((self.rename_chain, None, "Rename chain"))
		if self.chain_id:
			if len(self.zyngui.chain_manager.ordered_chain_ids) > 2:
				self.list_data.append((self.move_chain, None, "Move chain ⇦ ⇨"))

		super().fill_list()

	# Generate chain tree menu
	def generate_chaintree_menu(self):
		res = []
		indent = 0
		# Build MIDI chain
		for slot in range(self.chain.get_slot_count("MIDI Tool")):
			procs = self.chain.get_processors("MIDI Tool", slot)
			num_procs = len(procs)
			for index, processor in enumerate(procs):
				name = processor.get_name()
				if index == num_procs - 1:
					res.append((self.processor_options, processor, "  " * indent + "╰─ " + name))
				else:
					res.append((self.processor_options, processor, "  " * indent + "├─ " + name))
			indent += 1
		# Add synth processor
		for slot in self.chain.synth_slots:
			for proc in slot:
				res.append((self.processor_options, proc, "  " * indent + "╰━ " + proc.get_name()))
				indent += 1
		# Build pre-fader audio effects chain
		for slot in range(self.chain.fader_pos):
			if self.chain.fader_pos <= slot:
				break 
			procs = self.chain.get_processors("Audio Effect", slot)
			num_procs = len(procs)
			for index, processor in enumerate(procs):
				name = processor.get_name()
				if index == num_procs - 1:
					res.append((self.processor_options, processor, "  " * indent + "┗━ " + name))
				else:
					res.append((self.processor_options, processor, "  " * indent + "┣━ " + name))
			indent += 1
		# Add FADER mark
		res.append((None, None, "  " * indent + "┗━ FADER"))
		indent += 1
		# Build post-fader audio effects chain
		for slot in range(self.chain.fader_pos, len(self.chain.audio_slots)):
			procs = self.chain.get_processors("Audio Effect", slot)
			num_procs = len(procs)
			for index, processor in enumerate(procs):
				name = processor.get_name()
				if index == num_procs - 1:
					res.append((self.processor_options, processor, "  " * indent + "┗━ " + name))
				else:
					res.append((self.processor_options, processor, "  " * indent + "┣━ " + name))
			indent += 1
		return res

	def refresh_signal(self, sname):
		if sname == "AUDIO_RECORD":
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
			return True
		else:
			return False

	def select_action(self, i, t='S'):
		self.index = i
		if self.list_data[i][0] is None:
			pass
		elif self.list_data[i][1] is None:
			self.list_data[i][0]()
		else:
			self.list_data[i][0](self.list_data[i][1], t)

	def arrow_right(self):
		chain_keys = self.zyngui.chain_manager.ordered_chain_ids
		try:
			index = chain_keys.index(self.chain_id) + 1
		except:
			index = len(chain_keys) - 1
		if index < len(chain_keys):
			# We don't call setup() because it reset the list position (index)
			self.chain_id = chain_keys[index]
			self.chain = self.zyngui.chain_manager.get_chain(self.chain_id)
			self.processor = None
			self.set_select_path()
			self.fill_list()

	def arrow_left(self):
		chain_keys = self.zyngui.chain_manager.ordered_chain_ids
		try:
			index = chain_keys.index(self.chain_id) - 1
		except:
			index = 0
		if index >= 0:
			# We don't call setup() because it reset the list position (index)
			self.chain_id = chain_keys[index]
			self.chain = self.zyngui.chain_manager.get_chain(self.chain_id)
			self.processor = None
			self.set_select_path()
			self.fill_list()

	def processor_options(self, subchain, t='S'):
		self.zyngui.screens['processor_options'].setup(self.chain_id, subchain)
		self.zyngui.show_screen("processor_options")

	def chain_midi_chan(self):
		if self.chain.get_type() == "MIDI Tool":
			chan_all = True
		else:
			chan_all = False
		self.zyngui.screens['midi_chan'].set_mode("SET", self.chain.midi_chan, chan_all=chan_all)
		self.zyngui.show_screen('midi_chan')

	def chain_midi_cc(self):
		self.zyngui.screens['midi_cc'].set_chain(self.chain)
		self.zyngui.show_screen('midi_cc')

	def chain_note_range(self):
		self.zyngui.screens['midi_key_range'].config(self.chain)
		self.zyngui.show_screen('midi_key_range')

	def midi_learn(self):
		options = {}
		options['Enter MIDI-learn'] = "enable_midi_learn"
		options['Enter Global MIDI-learn'] = "enable_global_midi_learn"
		if self.processor:
			options[f'Clear {self.processor.name} MIDI-learn'] = "clean_proc"
		options['Clear chain MIDI-learn'] = "clean_chain"
		self.zyngui.screens['option'].config("MIDI-learn", options, self.midi_learn_menu_cb)
		self.zyngui.show_screen('option')

	def midi_learn_menu_cb(self, options, params):
		if params == 'enable_midi_learn':
			self.zyngui.close_screen()
			self.zyngui.cuia_toggle_midi_learn()
		elif params == 'enable_global_midi_learn':
			self.zyngui.close_screen()
			self.zyngui.cuia_toggle_midi_learn()
			self.zyngui.cuia_toggle_midi_learn()
		elif params == 'clean_proc':
			self.zyngui.show_confirm(f"Do you want to clean MIDI-learn for ALL controls in processor {self.processor.name}?", self.zyngui.chain_manager.clean_midi_learn, self.processor)
		elif params == 'clean_chain':
			self.zyngui.show_confirm(f"Do you want to clean MIDI-learn for ALL controls in ALL processors within chain {self.chain_id:02d}?", self.zyngui.chain_manager.clean_midi_learn, self.chain_id)

	def chain_midi_routing(self):
		self.zyngui.screens['midi_config'].set_chain(self.chain)
		self.zyngui.screens['midi_config'].input = False
		self.zyngui.show_screen('midi_config')

	def chain_audio_routing(self):
		self.zyngui.screens['audio_out'].set_chain(self.chain)
		self.zyngui.show_screen('audio_out')

	def audio_options(self):
		options = {}
		if self.zyngui.state_manager.zynmixer.get_mono(self.chain.mixer_chan):
			options['\u2612 Mono'] = 'mono'
		else:
			options['\u2610 Mono'] = 'mono'
		if self.zyngui.state_manager.zynmixer.get_phase(self.chain.mixer_chan):
			options['\u2612 Phase reverse'] = 'phase'
		else:
			options['\u2610 Phase reverse'] = 'phase'
		if self.zyngui.state_manager.zynmixer.get_ms(self.chain.mixer_chan):
			options['\u2612 M+S'] = 'ms'
		else:
			options['\u2610 M+S'] = 'ms'

		self.zyngui.screens['option'].config("Audio options", options, self.audio_menu_cb)
		self.zyngui.show_screen('option')

	def audio_menu_cb(self, options, params):
		if params == 'mono':
			self.zyngui.state_manager.zynmixer.toggle_mono(self.chain.mixer_chan)
		elif params == 'ms':
			self.zyngui.state_manager.zynmixer.toggle_ms(self.chain.mixer_chan)
		elif params == 'phase':
			self.zyngui.state_manager.zynmixer.toggle_phase(self.chain.mixer_chan)
		self.audio_options()

	def chain_audio_capture(self):
		self.zyngui.screens['audio_in'].set_chain(self.chain)
		self.zyngui.show_screen('audio_in')

	def chain_midi_capture(self):
		self.zyngui.screens['midi_config'].set_chain(self.chain)
		self.zyngui.screens['midi_config'].input = True
		self.zyngui.show_screen('midi_config')

	def toggle_recording(self):
		if self.processor and self.processor.engine and self.processor.engine.name == 'AudioPlayer':
			self.zyngui.state_manager.audio_recorder.toggle_recording(self.processor)
		else:
			self.zyngui.state_manager.audio_recorder.toggle_recording(self.zyngui.state_manager.audio_player)
		self.fill_list()

	def move_chain(self):
		self.zyngui.screens["audio_mixer"].moving_chain = True
		self.zyngui.show_screen_reset('audio_mixer')

	def rename_chain(self):
		self.zyngui.show_keyboard(self.do_rename_chain, self.chain.title)

	def do_rename_chain(self, title):
		self.chain.title = title
		self.zyngui.show_screen_reset('audio_mixer')

	# Remove submenu

	def remove_cb(self):
		options = {}
		if self.chain.synth_slots and self.chain.get_processor_count("MIDI Tool"):
			options['Remove All MIDI-FXs'] = "midifx"
		if self.chain.get_processor_count("Audio Effect"):
			options['Remove All Audio-FXs'] = "audiofx"
		if self.chain_id != 0:
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
		self.zyngui.modify_chain({"type": "Audio Effect", "chain_id": self.chain_id, "post_fader": False})

	def postfader_add(self):
		self.zyngui.modify_chain({"type": "Audio Effect", "chain_id": self.chain_id, "post_fader": True})

	def remove_all_audiofx(self):
		self.zyngui.show_confirm("Do you really want to remove all audio effects from this chain?", self.remove_all_procs_cb, "Audio Effect")

	def remove_all_procs_cb(self, type=None):
		for processor in self.chain.get_processors(type):
			self.zyngui.chain_manager.remove_processor(self.chain_id, processor)
		self.build_view()
		self.show()

	# MIDI-Chain management

	def midifx_add(self):
		self.zyngui.modify_chain({"type": "MIDI Tool", "chain_id": self.chain_id})

	def remove_all_midifx(self):
		self.zyngui.show_confirm("Do you really want to remove all MIDI effects from this chain?", self.remove_all_procs_cb, "MIDI Tool")

	# Select Path
	def set_select_path(self):
		try:
			self.select_path.set(f"Chain Options: {self.chain.get_name()}")
		except:
			self.select_path.set("Chain Options")

# ------------------------------------------------------------------------------
