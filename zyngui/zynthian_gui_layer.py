#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Layer Selector Class
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


import os
import copy
import base64
import logging
import collections
from collections import OrderedDict
from json import JSONEncoder, JSONDecoder

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore
from zyngine import zynthian_layer
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian Layer Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_layer(zynthian_gui_selector):

	def __init__(self):
		self.layers = []
		self.root_layers = []
		self.amixer_layer = None
		self.add_layer_eng = None
		self.replace_layer_index = None
		self.layer_chain_parallel = False
		self.last_snapshot_fpath = None
		self.last_snapshot_count = 0 # Increments each time a snapshot is loaded - modules may use to update if required
		self.reset_zs3()
		
		super().__init__('Layer', True)
		self.create_amixer_layer()


	def reset(self):
		self.show_all_layers = False
		self.add_layer_eng = None
		self.last_snapshot_fpath = None
		self.reset_clone()
		self.reset_note_range()
		self.remove_all_layers(True)
		self.reset_midi_profile()
		self.reset_audio_recorder_arm()


	def fill_list(self):
		self.list_data=[]

		# Get list of root layers
		self.root_layers = self.get_fxchain_roots()

		for i, layer in enumerate(self.root_layers):
			self.list_data.append((str(i + 1), i, layer.get_presetpath()))

		#super().fill_list()


	# Recalculate selector and root_layers list
	def refresh(self):
		self.refresh_index()
		self.set_selector()


	def refresh_index(self, layer=None):
		if layer is None:
			layer = self.zyngui.curlayer

		try:
			self.index = self.root_layers.index(self.get_chain_root(layer))
		except:
			self.index = 0
			try:
				self.zyngui.set_curlayer(self.root_layers[0], populate_screens=False)
			except:
				self.zyngui.set_curlayer(None, populate_screens=False)


	def select_action(self, i, t='S'):
		self.index = i
		logging.warning("THIS SHOULDN'T BE CALLED!!")


	def restore_presets(self):
		for layer in self.layers:
			layer.restore_preset()


	def create_amixer_layer(self):
		mixer_eng = self.zyngui.screens['engine'].start_engine('MX')
		self.amixer_layer = zynthian_layer(mixer_eng, None, self.zyngui)


	def remove_amixer_layer(self):
		self.amixer_layer.reset()
		self.amixer_layer = None


	def layer_control(self, layer=None):
		if not layer:
			layer = self.root_layers[self.index]
		self.zyngui.layer_control(layer)


	def layer_options(self):
		i = self.get_layer_selected()
		if i is not None and self.root_layers[i].engine.nickname!='MX':
			self.zyngui.screens['layer_options'].reset()
			self.zyngui.show_screen('layer_options')


	def next(self, control=True):
		self.zyngui.restore_curlayer()
		if len(self.root_layers) > 1:
			if self.zyngui.curlayer in self.root_layers:
				self.index = self.root_layers.index(self.zyngui.curlayer) + 1
				if self.index >= len(self.root_layers):
					self.index = 0

			if control:
				self.layer_control()
			else:
				self.zyngui.set_curlayer(self.root_layers[self.index])


	def prev(self, control=True):
		self.zyngui.restore_curlayer()
		if len(self.root_layers) > 1:
			if self.zyngui.curlayer in self.root_layers:
				self.index = self.root_layers.index(self.zyngui.curlayer) - 1
				if self.index < 0:
					self.index = len(self.root_layers) - 1

			if control:
				self.layer_control()
			else:
				self.zyngui.set_curlayer(self.root_layers[self.index])


	def get_layer_index(self, layer):
		try:
			return self.layers.index(layer)
		except:
			return None


	def get_num_layers(self):
		return len(self.layers)


	def get_root_layers(self):
		self.root_layers = self.get_fxchain_roots()
		return self.root_layers


	def get_root_layer_index(self, layer=None):
		try:
			if layer is None:
				if self.amixer_layer == self.zyngui.curlayer:
					layer = self.get_root_layer_by_midi_chan(self.zyngui._curlayer.midi_chan)
				elif self.zyngui.curlayer:
					layer = self.get_root_layer_by_midi_chan(self.zyngui.curlayer.midi_chan)
			return self.root_layers.index(layer)
		except:
			return None


	def get_root_layer_by_layer(self, layer):
		if layer:
			return self.get_root_layer_by_midi_chan(layer.midi_chan)
		return None


	def get_root_layer_by_midi_chan(self, mch):
		for layer in self.root_layers:
			if layer.midi_chan == mch:
				return layer
		return None


	def get_main_fxchain_root_layer(self):
		for layer in self.root_layers:
			if layer.midi_chan == 256:
				return layer
		return None


	def get_num_root_layers(self):
		return len(self.root_layers)


	def get_layer_selected(self):
		i=self.get_cursel()
		if i<len(self.root_layers):
			return i
		else:
			return None


	def get_free_midi_chans(self):
		free_chans = list(range(16))

		for rl in self.layers:
			try:
				free_chans.remove(rl.midi_chan)
			except:
				pass

		#logging.debug("FREE MIDI CHANNELS: {}".format(free_chans))
		return free_chans


	def get_next_free_midi_chan(self, chan0):
		free_chans = self.get_free_midi_chans()
		for i in range(1,16):
			chan = (chan0 + i) % 16
			if chan in free_chans:
				return chan
		raise Exception("No available free MIDI channels!")


	def show_chain_options_modal(self):
		chain_modes = {
			"Series": False,
			"Parallel": True
		}
		self.zyngui.screens['option'].config("Chain Mode", chain_modes, self.cb_chain_options_modal)
		self.zyngui.show_screen('option')


	def cb_chain_options_modal(self, option, chain_parallel):
		self.layer_chain_parallel = chain_parallel
		self.zyngui.show_screen('engine')


	def add_layer(self, etype):
		self.add_layer_eng = None
		self.replace_layer_index = None
		self.layer_chain_parallel = False
		self.zyngui.screens['engine'].set_engine_type(etype)
		self.zyngui.show_screen('engine')


	def replace_layer(self, i):
		self.add_layer_eng = None
		self.replace_layer_index = i
		self.layer_chain_parallel = False
		seleng = self.zyngui.screens['engine'].get_zyngine_eng(self.layers[i].engine)
		self.zyngui.screens['engine'].set_engine_type(self.layers[i].engine.type, self.layers[i].midi_chan, seleng)
		self.zyngui.show_screen('engine')


	def add_fxchain_layer(self, layer):
		self.add_layer_eng = None
		self.replace_layer_index = None
		self.layer_chain_parallel = False
		self.zyngui.screens['engine'].set_fxchain_mode(layer.midi_chan)
		if self.get_fxchain_count(layer) > 0:
			self.show_chain_options_modal()
		else:
			self.zyngui.show_screen('engine')


	def replace_fxchain_layer(self, i):
		self.replace_layer(i)


	def add_midichain_layer(self, midi_chan):
		self.add_layer_eng = None
		self.replace_layer_index = None
		self.layer_chain_parallel = False
		self.zyngui.screens['engine'].set_midichain_mode(midi_chan)
		if self.get_midichain_count(midi_chan) > 0:
			self.show_chain_options_modal()
		else:
			self.zyngui.show_screen('engine')


	def replace_midichain_layer(self, i):
		self.replace_layer(i)


	def add_layer_engine(self, eng, midi_chan=None):
		self.add_layer_eng=eng

		#if eng=='MD':
		#	self.add_layer_midich(None)

		if eng == 'AE':
			self.add_layer_midich(0, False)
			self.add_layer_midich(1, False)
			self.add_layer_midich(2, False)
			self.add_layer_midich(3, False)
			self.index = len(self.layers) - 3
			self.layer_control()

		elif midi_chan is None:
			self.replace_layer_index = None
			self.zyngui.screens['midi_chan'].set_mode("ADD", 0, self.get_free_midi_chans())
			self.zyngui.show_screen('midi_chan')

		else:
			self.add_layer_midich(midi_chan)


	def add_layer_midich(self, midich, select=True):
		if self.add_layer_eng:
			# Create layer node ...
			if self.add_layer_eng == "AI":
				zyngine = self.zyngui.screens['engine'].start_engine(self.add_layer_eng, "audioin-{:02d}".format(midich))
			else:
				zyngine = self.zyngui.screens['engine'].start_engine(self.add_layer_eng)
			layer = zynthian_layer(zyngine, midich, self.zyngui)

			# if replacing, clean zs3 state from the replaced layer
			if self.replace_layer_index is not None:
				self.clean_layer_state_from_zs3(self.replace_layer_index)

			# add/replace Audio Effects ...
			if len(self.layers) > 0 and layer.engine.type == "Audio Effect":
				if self.replace_layer_index is not None:
					self.replace_on_fxchain(layer)
				else:
					if layer.engine.nickname != "AI":
						self.add_to_fxchain(layer, self.layer_chain_parallel)
					self.layers.append(layer)
			# add/replace MIDI Effects ...
			elif len(self.layers) > 0 and layer.engine.type == "MIDI Tool":
				if self.replace_layer_index is not None:
					self.replace_on_midichain(layer)
				else:
					self.add_to_midichain(layer, self.layer_chain_parallel)
					self.layers.append(layer)
			# replace Synth ...
			elif len(self.layers) > 0 and layer.engine.type == "MIDI Synth" and self.replace_layer_index is not None:
				self.replace_synth(layer)
			# new root layer
			else:
				self.layers.append(layer)

			self.root_layers = self.get_fxchain_roots()
			self.zyngui.zynautoconnect()

			if select:
				self.refresh_index()
				try:
					self.layer_control(layer)
				except Exception as e:
					logging.error(e)
					self.zyngui.show_screen_reset('audio_mixer')


	def remove_layer(self, i, stop_unused_engines=True):
		if i < 0 or i >= len(self.layers):
			return

		layer = self.layers[i]
		logging.debug("Removing layer {} => {} ...".format(i, layer.get_basepath()))

		if layer in self.root_layers:
			refresh = True
		else:
			refresh = False

		if layer.engine.type == "MIDI Tool":
			self.drop_from_midichain(layer)
			layer.mute_midi_out()
			# Handle removal of root layer
			if layer in self.root_layers:
				self.root_layers.remove(layer)
				for l in self.layers:
					if l.midi_chan == layer.midi_chan and l != layer:
						self.root_layers.append(l)
						if self.zyngui.curlayer == layer:
							self.zyngui.curlayer = l
						if self.zyngui._curlayer == layer:
							self.zyngui._curlayer = l
						self.zyngui.screens['layer_options'].reset()
						break
		else:
			self.drop_from_fxchain(layer)
			layer.mute_audio_out()

		self.zyngui.zynautoconnect(True)

		self.zyngui.zynautoconnect_acquire_lock()
		layer.reset()
		self.layers.pop(i)
		self.delete_layer_state_from_zs3(i)
		self.zyngui.zynautoconnect_release_lock()

		# Stop unused engines
		if stop_unused_engines:
			self.zyngui.screens['engine'].stop_unused_engines()

		if refresh:
			self.refresh()


	def remove_root_layer(self, i, stop_unused_engines=True):
		if i >= 0 and i < len(self.root_layers):
			# For some engines (Aeolus, setBfree), delete all layers from the same engine
			if self.root_layers[i].engine.nickname in ['BF', 'AE']:
				root_layers_to_delete = copy.copy(self.root_layers[i].engine.layers)
			else:
				root_layers_to_delete = [self.root_layers[i]]

			# Mute Audio Layers & build list of layers/midi_chans to delete
			layers_to_delete = []
			chans_to_reset = []
			for root_layer in root_layers_to_delete:
				chans_to_reset.append(root_layer.midi_chan)
				self.zyngui.zynmixer.set_mute(root_layer.midi_chan, True)
				# Midichain layers
				midichain_layers = self.get_midichain_layers(root_layer)
				layers_to_delete += midichain_layers
				for layer in reversed(midichain_layers):
					logging.debug("Mute MIDI layer '{}' ...".format(i, layer.get_basepath()))
					self.drop_from_midichain(layer)
					layer.mute_midi_out()
				# Fxchain layers => Mute!
				fxchain_layers = self.get_fxchain_layers(root_layer)
				layers_to_delete += fxchain_layers
				for layer in reversed(fxchain_layers):
					logging.debug("Mute Audio layer '{}' ...".format(i, layer.get_basepath()))
					self.drop_from_fxchain(layer)
					layer.mute_audio_out()
				# Root_layer
				layers_to_delete.append(root_layer)
				root_layer.mute_midi_out()
				root_layer.mute_audio_out()

			self.zyngui.zynautoconnect(True)

			# Remove layers
			self.zyngui.zynautoconnect_acquire_lock()
			for layer in layers_to_delete:
				try:
					i = self.layers.index(layer)
					self.layers[i].reset()
					self.layers.pop(i)
					self.delete_layer_state_from_zs3(i)
				except Exception as e:
					logging.error("Can't delete layer {} => {}".format(i,e))
			self.zyngui.zynautoconnect_release_lock()

			# Stop unused engines
			if stop_unused_engines:
				self.zyngui.screens['engine'].stop_unused_engines()

			for chan in chans_to_reset:
				self.zyngui.zynmixer.reset(chan)

			self.refresh()


	def remove_all_layers(self, stop_engines=True):
		# Mute output
		muted = self.zyngui.zynmixer.get_mute(256)
		self.zyngui.zynmixer.set_mute(256, True)

		'''
		# Remove all layers: Step 1 => Drop from FX chain and mute
		i = len(self.layers)
		while i > 0:
			i -= 1
			logging.debug("Mute layer {} => {} ...".format(i, self.layers[i].get_basepath()))
			self.drop_from_midichain(self.layers[i])
			self.layers[i].mute_midi_out()
			self.drop_from_fxchain(self.layers[i])
			self.layers[i].mute_audio_out()

		self.zyngui.zynautoconnect(True)
		'''

		# Remove all layers: Step 2 => Delete layers
		i = len(self.layers)
		self.zyngui.zynautoconnect_acquire_lock()
		while i > 0:
			i -= 1
			logging.debug("Remove layer {} => {} ...".format(i, self.layers[i].get_basepath()))
			self.layers[i].reset()
			self.layers.pop(i)
		self.zyngui.zynautoconnect_release_lock()

		# Remove all learned ZS3s
		self.reset_zs3()

		# Stop ALL engines
		if stop_engines:
			self.zyngui.screens['engine'].stop_unused_engines()

		self.index = 0
		self.zyngui.set_curlayer(None)

		# Refresh UI
		self.root_layers = []
		self.set_selector()

		# Restore mute state
		self.zyngui.zynmixer.set_mute(256, muted)


	#----------------------------------------------------------------------------
	# Clone, Note Range & Transpose
	#----------------------------------------------------------------------------

	def set_clone(self, clone_status):
		for i in range(0,16):
			for j in range(0,16):
				if isinstance(clone_status[i][j],dict):
					lib_zyncore.set_midi_filter_clone(i,j,clone_status[i][j]['enabled'])
					self.zyngui.screens['midi_cc'].set_clone_cc(i,j,clone_status[i][j]['cc'])
				else:
					lib_zyncore.set_midi_filter_clone(i,j,clone_status[i][j])
					lib_zyncore.reset_midi_filter_clone_cc(i,j)


	def reset_clone(self):
		for i in range(0,16):
			lib_zyncore.reset_midi_filter_clone(i)


	def set_transpose(self, tr_status):
		for i in range(0,16):
			lib_zyncore.set_midi_filter_halftone_trans(i, tr_status[i])


	def set_note_range(self, nr_status):
		for i in range(0,16):
			if nr_status[i]:
				lib_zyncore.set_midi_filter_note_range(i, nr_status[i]['note_low'], nr_status[i]['note_high'], nr_status[i]['octave_trans'], nr_status[i]['halftone_trans'])


	def reset_note_range(self):
		for i in range(0,16):
			lib_zyncore.reset_midi_filter_note_range(i)


	#----------------------------------------------------------------------------
	# MIDI learn management
	#----------------------------------------------------------------------------

	def midi_unlearn(self, root_layer=None):
		if root_layer is None:
			root_layer = self.zyngui.curlayer
		if root_layer:
			for layer in self.get_chain_layers(root_layer):
				layer.midi_unlearn()


	#----------------------------------------------------------------------------
	# MIDI CC & Program Change (when ZS3 is disabled!)
	#----------------------------------------------------------------------------

	def midi_control_change(self, chan, ccnum, ccval):
		if zynthian_gui_config.midi_bank_change and ccnum==0:
			for layer in self.root_layers:
				if layer.midi_chan==chan:
					layer.midi_bank_msb(ccval)
		elif zynthian_gui_config.midi_bank_change and ccnum==32:
			for layer in self.root_layers:
				if layer.midi_chan==chan:
					layer.midi_bank_lsb(ccval)
		else:
			for layer in self.layers:
				layer.midi_control_change(chan, ccnum, ccval)
			self.amixer_layer.midi_control_change(chan, ccnum, ccval)


	def set_midi_prog_preset(self, midich, prognum):
		changed = False
		for i, layer in enumerate(self.root_layers):
			try:
				mch = layer.get_midi_chan()
				if mch is None or mch == midich:
					# TODO This is really DIRTY!!
					# Fluidsynth engine => ignore Program Change on channel 10
					if layer.engine.nickname == "FS" and mch == 9:
						continue
					changed |= layer.set_preset(prognum, True)
			except Exception as e:
				logging.error("Can't set preset for CH#{}:PC#{} => {}".format(midich, prognum, e))
		return changed


	#----------------------------------------------------------------------------
	# ZS3 management
	#----------------------------------------------------------------------------

	def set_midi_prog_zs3(self, midich, prognum):
		if zynthian_gui_config.midi_single_active_channel:
			i = self.get_zs3_index_by_prognum(prognum)
		else:
			i = self.get_zs3_index_by_midich_prognum(midich, prognum)

		if i is not None:
			return self.restore_zs3(i)
		else:
			logging.debug("Can't find a ZS3 for CH#{}, PRG#{}".format(midich, prognum))
			return False


	def save_midi_prog_zs3(self, midich, prognum):
		# Look for a matching zs3 
		if midich is not None and prognum is not None:
			if zynthian_gui_config.midi_single_active_channel:
				i = self.get_zs3_index_by_prognum(prognum)
			else:
				i = self.get_zs3_index_by_midich_prognum(midich, prognum)
		else:
			i = None
		
		# Get state and add MIDI-learn info
		state = self.get_state()
		state['zs3_title'] = "New ZS3"
		state['midi_learn_chan'] = midich
		state['midi_learn_prognum'] = prognum

		# Save in ZS3 list, overwriting if already used
		if i is None or i < 0 or i >= len(self.learned_zs3):
			self.learned_zs3.append(state)
			i = len(self.learned_zs3) - 1
		else:
			self.learned_zs3[i] = state

		self.last_zs3_index = i
		logging.info("Saved ZS3#{} => CH#{}:PRG#{}".format(i, midich, prognum))

		return i


	def get_zs3_index_by_midich_prognum(self, midich, prognum):
		for i, zs3 in enumerate(self.learned_zs3):
			try:
				if zs3['midi_learn_chan'] == midich and zs3['midi_learn_prognum'] == prognum:
					return i
			except:
				pass


	def get_zs3_index_by_prognum(self, prognum):
		for i, zs3 in enumerate(self.learned_zs3):
			try:
				if zs3['midi_learn_prognum'] == prognum:
					return i
			except:
				pass


	def get_last_zs3_index(self):
		return self.last_zs3_index


	def get_zs3_title(self, i):
		if i is not None and i >= 0 and i < len(self.learned_zs3):
			return self.learned_zs3[i]['zs3_title']


	def set_zs3_title(self, i, title):
		if i is not None and i >= 0 and i < len(self.learned_zs3):
			self.learned_zs3[i]['zs3_title'] = title


	def restore_zs3(self, i):
		try:
			if i is not None and i >= 0 and i < len(self.learned_zs3):
				logging.info("Restoring ZS3#{}...".format(i))
				self.restore_state_zs3(self.learned_zs3[i])
				self.last_zs3_index = i
				return True
			else:
				logging.debug("Can't find ZS3#{}".format(i))
		except Exception as e:
			logging.error("Can't restore ZS3 state => %s", e)

		return False


	def save_zs3(self, i=None):
		# Get state and add MIDI-learn info
		state = self.get_state()

		# Save in ZS3 list, overwriting if already used
		if i is None or i < 0 or i >= len(self.learned_zs3):
			state['zs3_title'] = "New ZS3"
			state['midi_learn_chan'] = None
			state['midi_learn_prognum'] = None
			self.learned_zs3.append(state)
			i = len(self.learned_zs3) - 1
		else:
			state['zs3_title'] = self.learned_zs3[i]['zs3_title']
			state['midi_learn_chan'] = self.learned_zs3[i]['midi_learn_chan']
			state['midi_learn_prognum'] = self.learned_zs3[i]['midi_learn_prognum']
			self.learned_zs3[i] = state

		logging.info("Saved ZS3#{}".format(i))
		self.last_zs3_index = i
		return i


	def delete_zs3(self, i):
		del(self.learned_zs3[i])
		if self.last_zs3_index == i:
			self.last_zs3_index = None


	def reset_zs3(self):
		# ZS3 list (subsnapshots)
		self.learned_zs3 = []
		# Last selected ZS3 subsnapshot
		self.last_zs3_index = None


	def delete_layer_state_from_zs3(self, j):
		for state in self.learned_zs3:
			try:
				del state['layers'][j]
			except:
				pass


	def clean_layer_state_from_zs3(self, j):
		for state in self.learned_zs3:
			try:
				state['layers'][j] = None
			except:
				pass


	#----------------------------------------------------------------------------
	# Audio Routing
	#----------------------------------------------------------------------------

	def get_audio_routing(self):
		res = {}
		for i, layer in enumerate(self.layers):
			res[layer.get_jackname()] = layer.get_audio_out()
		return res


	def set_audio_routing(self, audio_routing=None):
		for layer in self.layers:
			try:
				layer.set_audio_out(audio_routing[layer.get_jackname()])
			except:
				if layer.engine.nickname != "AI":
					layer.reset_audio_out()


	# Ensure audio inputs and main mixbus have audio input engines
	def fix_audio_inputs(self):
		ai_layers = {} # Map of ai layers already created from snapshot indexed by midi chan
		fx_layers = {} # Map of list of layers with audio input connected to system inputs indexed by midi_chan

		# Populate maps
		for layer in self.layers:
			if layer.engine.type != "Audio Effect":
				continue
			chan = layer.midi_chan
			if layer.engine.nickname == "AI":
				ai_layers[chan] = layer
			for input in layer.audio_in:
				if input.startswith("system:capture"):
					if chan in fx_layers:
						fx_layers[chan].append(layer)
					else:
						fx_layers[chan] = [layer]
					break

		# Correlate audio chains with existing audio input layers
		for chan in fx_layers:
			if chan not in ai_layers:
				# Insert missing Audio Input layer
				ai_engine = self.zyngui.screens['engine'].start_engine("AI", "audioin-{:02d}".format(chan))
				ai_layer = zynthian_layer(ai_engine, chan, self.zyngui)
				a_out = []
				a_in = []
				for o in fx_layers[chan]:
					a_out.append(o.get_jackname())
					a_in += o.audio_in
				ai_layer.set_audio_out(a_out)
				ai_layer.set_audio_in(list(dict.fromkeys(a_in))) # Remove duplicates

				self.layers.append(ai_layer)

		# Ensure there is a main mixbus chain
		if 256 not in ai_layers:
			ai_engine = self.zyngui.screens['engine'].start_engine("AI", "audioin-256")
			ai_layer = zynthian_layer(ai_engine, 256, self.zyngui)
			self.layers.append(ai_layer)
		
		for layer in self.layers:
			if layer.engine.nickname != "AI":
				layer.set_audio_in([])


	def reset_audio_routing(self):
		self.set_audio_routing()


	#----------------------------------------------------------------------------
	# Audio Capture
	#----------------------------------------------------------------------------

	def get_audio_capture(self):
		res = {}
		for i, layer in enumerate(self.layers):
			res[layer.get_jackname()] = layer.get_audio_in()
		return res


	def set_audio_capture(self, audio_capture=None):
		for i, layer in enumerate(self.layers):
			try:
				layer.set_audio_in(audio_capture[layer.get_jackname()])
			except:
				layer.reset_audio_in()


	def reset_audio_capture(self):
		self.set_audio_capture()


	#----------------------------------------------------------------------------
	# MIDI Routing
	#----------------------------------------------------------------------------

	def get_midi_routing(self):
		res={}
		for i, layer in enumerate(self.layers):
			res[layer.get_jackname()]=layer.get_midi_out()
		return res


	def set_midi_routing(self, midi_routing=None):
		for i, layer in enumerate(self.layers):
			try:
				layer.set_midi_out(midi_routing[layer.get_jackname()])
			except:
				layer.set_midi_out([])


	def reset_midi_routing(self):
		self.set_midi_routing()


	def reset_audio_recorder_arm(self):
		for midi_chan in [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,256]:
			self.zyngui.audio_recorder.unarm(midi_chan)


	#----------------------------------------------------------------------------
	# Jackname managing
	#----------------------------------------------------------------------------

	def get_layer_by_jackname(self, jackname):
		for layer in self.layers:
			if layer.jackname in jackname:
				return layer


	def get_next_jackname(self, jackname):
		names = set()
		for layer in self.layers:
			if layer.jackname is not None and layer.jackname.startswith(jackname):
				names.add(layer.jackname)
		i = 0
		while "{}-{:02d}".format(jackname, i) in names:
			i += 1
		return "{}-{:02d}".format(jackname, i)


	# ---------------------------------------------------------------------------
	# Chain management
	# ---------------------------------------------------------------------------

	def get_chain_root(self, layer):
		if layer.midi_chan is None:
			return layer
		for l in self.layers:
			if l.midi_chan == layer.midi_chan and (l.engine.type != "Audio Effect" or l.engine.nickname == "AI"):
				return l


	def get_chain_layers(self, layer):
		layers = []
		if layer.midi_chan is None:
			layers.append(layer)
		else:
			for l in self.layers:
				if l.midi_chan==layer.midi_chan:
					layers.append(l)
		return layers


	# ---------------------------------------------------------------------------
	# Synth node
	# ---------------------------------------------------------------------------

	def replace_synth(self, layer):
		try:
			rlayer = self.layers[self.replace_layer_index]
			logging.debug("Replacing Synth {} => {}".format(rlayer.get_jackname(), layer.get_jackname()))

			# Re-route audio
			layer.set_audio_out(rlayer.get_audio_out())
			rlayer.mute_audio_out()

			# Re-route MIDI
			for uslayer in self.get_midichain_upstream(rlayer):
				uslayer.del_midi_out(rlayer.get_midi_jackname())
				uslayer.add_midi_out(layer.get_midi_jackname())

			# Replace layer in list
			self.layers[self.replace_layer_index] = layer

			# Remove old layer and stop unused engines
			self.zyngui.zynautoconnect_acquire_lock()
			rlayer.reset()
			self.zyngui.zynautoconnect_release_lock()
			self.zyngui.screens['engine'].stop_unused_engines()

			self.replace_layer_index = None

		except Exception as e:
			logging.error("Error replacing Synth ({})".format(e))


	# ---------------------------------------------------------------------------
	# FX-Chain
	# ---------------------------------------------------------------------------

	def get_fxchain_roots(self):
		roots = []

		for layer in self.layers:
			if layer.midi_chan is None and layer.engine.type in ("Special"):
				roots.append(layer)

		for chan in [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,256]:
			for layer in self.layers:
				if layer.midi_chan == chan:
					if layer.engine.type != "Audio Effect" or layer.engine.nickname == "AI":
						roots.append(layer)
						break

		return roots


	def get_fxchain_layers(self, layer=None):
		if layer is None:
			layer = self.zyngui.curlayer

		fxchain_layers = []
		if layer is not None and layer.midi_chan is not None:
			for l in self.layers:
				if l.engine.type == "Audio Effect" and l not in fxchain_layers and l.midi_chan == layer.midi_chan and l not in self.root_layers:
					fxchain_layers.append(l)

		return fxchain_layers



	def get_fxchain_count(self, layer):
		return len(self.get_fxchain_layers(layer))


	# Returns FX-chain layers routed to extra-chain ports or not routed at all.
	def get_fxchain_ends(self, layer):
		fxlbjn = {}
		for fxlayer in self.get_fxchain_layers(layer):
			fxlbjn[fxlayer.jackname] = fxlayer

		ends = []
		for layer in fxlbjn.values():
			try:
				if layer.get_audio_out()[0] not in fxlbjn:
					ends.append(layer)
			except:
				ends.append(layer)
		if not ends:
			ends = [self.get_root_layer_by_midi_chan(layer.midi_chan)]
		return ends


	def get_fxchain_upstream(self, layer):
		ups=[]
		for uslayer in self.layers:
			if layer.get_jackname() in uslayer.get_audio_out():
				ups.append(uslayer)

		return ups


	def get_fxchain_downstream(self, layer):
		downs=[]
		for uslayer in self.layers:
			if uslayer.get_jackname() in layer.get_audio_out():
				downs.append(uslayer)

		return downs


	def get_fxchain_pars(self, layer):
		pars = [layer]
		#logging.error("FX ROOT LAYER => {}".format(layer.get_basepath()))
		for l in self.layers:
			if l != layer and l.engine.type == "Audio Effect" and l.midi_chan == layer.midi_chan and collections.Counter(l.audio_out) == collections.Counter(layer.audio_out):
				pars.append(l)
				#logging.error("PARALLEL LAYER => {}".format(l.get_audio_jackname()))
		return pars


	def add_to_fxchain(self, layer, chain_parallel=False):
		try:
			for end in self.get_fxchain_ends(layer):
				if end and end != layer:
					logging.debug("Adding to FX-chain {} => {}".format(end.get_audio_jackname(), layer.get_audio_jackname()))
					layer.set_audio_out(end.get_audio_out())
					if chain_parallel:
						for uslayer in self.get_fxchain_upstream(end):
							uslayer.add_audio_out(layer.get_audio_jackname())
					else:
						end.set_audio_out([layer.get_audio_jackname()])

		except Exception as e:
			logging.error("Error chaining Audio Effect ({})".format(e))


	def replace_on_fxchain(self, layer):
		try:
			rlayer = self.layers[self.replace_layer_index]
			logging.debug("Replacing on FX-chain {} => {}".format(rlayer.get_jackname(), layer.get_jackname()))

			# Re-route audio
			layer.set_audio_out(rlayer.get_audio_out())
			rlayer.mute_audio_out()
			for uslayer in self.get_fxchain_upstream(rlayer):
				uslayer.del_audio_out(rlayer.get_jackname())
				uslayer.add_audio_out(layer.get_jackname())

			# Replace layer in list
			self.layers[self.replace_layer_index] = layer

			# Remove old layer and stop unused engines
			self.zyngui.zynautoconnect_acquire_lock()
			rlayer.reset()
			self.zyngui.zynautoconnect_release_lock()
			self.zyngui.screens['engine'].stop_unused_engines()

			self.replace_layer_index = None

		except Exception as e:
			logging.error("Error replacing Audio Effect ({})".format(e))


	def drop_from_fxchain(self, layer):
		try:
			for up in self.get_fxchain_upstream(layer):
				logging.debug("Dropping from FX-chain {} => {}".format(up.get_jackname(), layer.get_jackname()))
				up.del_audio_out(layer.get_jackname())
				if len(up.get_audio_out()) == 0:
					up.set_audio_out(layer.get_audio_out())

		except Exception as e:
			logging.error("Error unchaining Audio Effect ({})".format(e))


	def swap_fxchain(self, layer1, layer2):
		ups1 = self.get_fxchain_upstream(layer1)
		ups2 = self.get_fxchain_upstream(layer2)

		self.zyngui.zynautoconnect_acquire_lock()

		# Move inputs from layer1 to layer2
		for l in ups1:
			l.add_audio_out(layer2.get_jackname())
			l.del_audio_out(layer1.get_jackname())

		# Move inputs from layer2 to layer1
		for l in ups2:
			l.add_audio_out(layer1.get_jackname())
			l.del_audio_out(layer2.get_jackname())

		# Swap outputs from layer1 & layer2
		ao1 = layer1.audio_out
		ao2 = layer2.audio_out
		layer1.set_audio_out(ao2)
		layer2.set_audio_out(ao1)

		self.zyngui.zynautoconnect_release_lock()

		# Swap position in layer list
		for i,layer in enumerate(self.layers):
			if layer==layer1:
				self.layers[i] = layer2

			elif layer==layer2:
				self.layers[i] = layer1

	# ---------------------------------------------------------------------------
	# MIDI-Chain
	# ---------------------------------------------------------------------------

	def get_midichain_roots(self):
		roots = []

		for layer in self.layers:
			if layer.midi_chan == None and layer.engine.type in ("Special"):
				roots.append(layer)

		for chan in range(16):
			rl = self.get_midichain_root_by_chan(chan)
			if rl:
				roots.append(rl)

		return roots


	def get_midichain_layers(self, layer=None):
		if layer is None:
			layer = self.zyngui.curlayer

		if layer is not None:
			midichain_layers = []

			if layer.midi_chan is not None:
				for l in self.layers:
					if l.engine.type in ("MIDI Tool") and l not in midichain_layers and l.midi_chan == layer.midi_chan:
						midichain_layers.append(l)

			return midichain_layers

		else:
			return None


	def get_midichain_count(self, midi_chan):
		count = 0
		if midi_chan is not None:
			for l in self.layers:
				if l.engine.type in ("MIDI Tool") and l.midi_chan == midi_chan:
						count += 1
		return count


	def get_midichain_root(self, layer):
		if layer.midi_chan is None:
			return layer

		for l in self.layers:
			if l.engine.type == "MIDI Tool" and l.midi_chan == layer.midi_chan:
				return l

		for l in self.layers:
			if l.engine.type in ("MIDI Synth", "Special") and l.midi_chan == layer.midi_chan:
				return l

		return None


	def get_midichain_root_by_chan(self, chan):
		if chan is None:
			for l in self.layers:
				if l.midi_chan is None:
					return l

		else:
			for l in self.layers:
				if l.engine.type == "MIDI Tool" and l.midi_chan == chan and l.midi_out:
					return l

			for l in self.layers:
				if l.engine.type in ("MIDI Synth", "Special") and l.midi_chan == chan:
					return l

		return None


	# Returns MIDI-chain layers routed to extra-chain ports or not routed at all.
	def get_midichain_ends(self, layer):
		midilbjn = {}
		for midilayer in self.get_midichain_layers(layer):
			midilbjn[midilayer.get_midi_jackname()] = midilayer

		ends = []
		for layer in midilbjn.values():
			try:
				if layer.get_midi_out()[0] not in midilbjn:
					ends.append(layer)
			except:
				ends.append(layer)
		if not ends:
			end = self.get_root_layer_by_midi_chan(layer.midi_chan)
			if end:
				ends = [end]
		return ends


	def get_midichain_upstream(self, layer):
		ups = []
		for uslayer in self.layers:
			if layer.get_midi_jackname() in uslayer.get_midi_out():
				ups.append(uslayer)

		return ups


	def get_midichain_downstream(self, layer):
		downs = []
		for uslayer in self.layers:
			if uslayer.get_midi_jackname() in layer.get_midi_out():
				downs.append(uslayer)

		return downs


	def get_midichain_pars(self, layer):
		pars = [layer]
		#logging.error("MIDI ROOT LAYER => {}".format(layer.get_basepath()))
		for l in self.layers:
			if l != layer and l.engine.type == "MIDI Tool" and l.midi_chan == layer.midi_chan and collections.Counter(l.midi_out) == collections.Counter(layer.midi_out):
				pars.append(l)
				#logging.error("PARALLEL LAYER => {}".format(l.get_midi_jackname()))
		return pars


	def add_to_midichain(self, layer, chain_parallel=False):
		try:
			for end in self.get_midichain_ends(layer):
				if end != layer:
					logging.debug("Adding to MIDI-chain {} => {}".format(end.get_midi_jackname(), layer.get_midi_jackname()))
					if end.engine.type=="MIDI Tool":
						layer.set_midi_out(end.get_midi_out())
						if chain_parallel:
							for uslayer in self.get_midichain_upstream(end):
								uslayer.add_midi_out(layer.get_midi_jackname())
						else:
							end.set_midi_out([layer.get_midi_jackname()])
					else:
						layer.set_midi_out([end.get_midi_jackname()])
						if chain_parallel:
							for uslayer in self.get_midichain_upstream(end):
								for uuslayer in self.get_midichain_upstream(uslayer):
									uuslayer.add_midi_out(layer.get_midi_jackname())
						else:
							for uslayer in self.get_midichain_upstream(end):
								uslayer.del_midi_out(end.get_midi_jackname())
								uslayer.add_midi_out(layer.get_midi_jackname())

		except Exception as e:
			logging.error("Error chaining MIDI tool ({})".format(e))


	def replace_on_midichain(self, layer):
		try:
			rlayer = self.layers[self.replace_layer_index]
			logging.debug("Replacing on MIDI-chain {} => {}".format(rlayer.get_midi_jackname(), layer.get_midi_jackname()))

			# Re-route MIDI
			layer.set_midi_out(rlayer.get_midi_out())
			rlayer.mute_midi_out()
			for uslayer in self.get_midichain_upstream(rlayer):
				uslayer.del_midi_out(rlayer.get_midi_jackname())
				uslayer.add_midi_out(layer.get_midi_jackname())

			# Replace layer in list
			self.layers[self.replace_layer_index] = layer

			# Remove old layer and stop unused engines
			self.zyngui.zynautoconnect_acquire_lock()
			rlayer.reset()
			self.zyngui.zynautoconnect_release_lock()
			self.zyngui.screens['engine'].stop_unused_engines()

			self.replace_layer_index = None

		except Exception as e:
			logging.error("Error replacing MIDI tool ({})".format(e))


	def drop_from_midichain(self, layer):
		try:
			for up in self.get_midichain_upstream(layer):
				logging.debug("Dropping from MIDI-chain {} => {}".format(up.get_midi_jackname(), layer.get_midi_jackname()))
				up.del_midi_out(layer.get_midi_jackname())
				if len(up.get_midi_out()) == 0:
					up.set_midi_out(layer.get_midi_out())

		except Exception as e:
			logging.error("Error unchaining MIDI tool ({})".format(e))


	def swap_midichain(self, layer1, layer2):
		ups1 = self.get_midichain_upstream(layer1)
		ups2 = self.get_midichain_upstream(layer2)

		self.zyngui.zynautoconnect_acquire_lock()

		# Move inputs from layer1 to layer2
		for l in ups1:
			l.add_midi_out(layer2.get_midi_jackname())
			l.del_midi_out(layer1.get_midi_jackname())

		# Move inputs from layer2 to layer1
		for l in ups2:
			l.add_midi_out(layer1.get_midi_jackname())
			l.del_midi_out(layer2.get_midi_jackname())

		# Swap outputs from layer1 & layer2
		mo1 = layer1.midi_out
		mo2 = layer2.midi_out
		layer1.set_midi_out(mo2)
		layer2.set_midi_out(mo1)

		self.zyngui.zynautoconnect_release_lock()

		# Swap position in layer list
		for i,layer in enumerate(self.layers):
			if layer==layer1:
				self.layers[i] = layer2

			elif layer==layer2:
				self.layers[i] = layer1

	# ---------------------------------------------------------------------------
	# Extended Config
	# ---------------------------------------------------------------------------


	def get_extended_config(self):
		xconfigs={}
		for zyngine in self.zyngui.screens['engine'].zyngines.values():
			xconfigs[zyngine.nickname]=zyngine.get_extended_config()
		return xconfigs


	def set_extended_config(self, xconfigs):
		for zyngine in self.zyngui.screens['engine'].zyngines.values():
			if zyngine.nickname in xconfigs:
				zyngine.set_extended_config(xconfigs[zyngine.nickname])


	#----------------------------------------------------------------------------
	# Snapshot Save & Load
	#----------------------------------------------------------------------------

	def get_state(self):
		state = {
			'index':self.index,
			'mixer':[],
			'layers':[],
			'clone':[],
			'note_range':[],
			'audio_capture': self.get_audio_capture(),
			'last_snapshot_fpath': self.last_snapshot_fpath
		}

		# Layers info
		for layer in self.layers:
			state['layers'].append(layer.get_state())

		# Add ALSA-Mixer setting as a layer
		if zynthian_gui_config.snapshot_mixer_settings and self.amixer_layer:
			state['layers'].append(self.amixer_layer.get_state())

		# Clone info
		for i in range(0,16):
			state['clone'].append([])
			for j in range(0,16):
				clone_info = {
					'enabled': lib_zyncore.get_midi_filter_clone(i,j),
					'cc': list(map(int,lib_zyncore.get_midi_filter_clone_cc(i,j).nonzero()[0]))
				}
				state['clone'][i].append(clone_info)

		# Note-range info
		for i in range(0,16):
			info = {
				'note_low': lib_zyncore.get_midi_filter_note_low(i),
				'note_high': lib_zyncore.get_midi_filter_note_high(i),
				'octave_trans': lib_zyncore.get_midi_filter_octave_trans(i),
				'halftone_trans': lib_zyncore.get_midi_filter_halftone_trans(i)
			}
			state['note_range'].append(info)

		# Mixer
		try:
			state['mixer'] = self.zyngui.zynmixer.get_state()
		except Exception as e:
			pass

		# Audio Recorder Armed
		state['audio_recorder_armed'] = []
		for midi_chan in [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,256]:
			if self.zyngui.audio_recorder.is_armed(midi_chan):
				state['audio_recorder_armed'].append(midi_chan)

		logging.debug("STATE index => {}".format(state['index']))

		return state


	def restore_state_snapshot(self, state):
		# Restore MIDI profile state
		if 'midi_profile_state' in state:
			self.set_midi_profile_state(state['midi_profile_state'])

		# Set MIDI Routing
		if 'midi_routing' in state:
			self.set_midi_routing(state['midi_routing'])
		else:
			self.reset_midi_routing()

		# Calculate root_layers
		self.root_layers = self.get_fxchain_roots()

		# Autoconnect MIDI
		self.zyngui.zynautoconnect_midi(True)

		# Set extended config and load bank list => when loading snapshots, not zs3!
		if 'extended_config' in state:
			# Extended settings (i.e. setBfree tonewheel model, aeolus tuning, etc.)
			self.set_extended_config(state['extended_config'])

		# Restore layer state, step 0 => bank list
		for i, lss in enumerate(state['layers']):
			self.layers[i].restore_state_0(lss)

		# Restore layer state, step 1 => Restore Bank & Preset Status
		for i, lss in enumerate(state['layers']):
			self.layers[i].restore_state_1(lss)

		# Restore layer state, step 2 => Restore Controllers Status
		for i, lss in enumerate(state['layers']):
			self.layers[i].restore_state_2(lss)

		# Set Audio Routing
		if 'audio_routing' in state:
			self.set_audio_routing(state['audio_routing'])
		else:
			self.reset_audio_routing()

		# Set Audio Capture
		if 'audio_capture' in state:
			self.set_audio_capture(state['audio_capture'])
		else:
			self.reset_audio_capture()

		self.fix_audio_inputs()

		# Audio Recorder Primed
		if 'audio_recorder_armed' not in state:
			state['audio_recorder_armed'] = []
		for midi_chan in [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,256]:
			if midi_chan in state['audio_recorder_armed']:
				self.zyngui.audio_recorder.arm(midi_chan)
			else:
				self.zyngui.audio_recorder.unarm(midi_chan)

		# Set Clone
		if 'clone' in state:
			self.set_clone(state['clone'])
		else:
			self.reset_clone()

		# Note-range & Tranpose
		if 'note_range' in state:
			self.set_note_range(state['note_range'])
		# BW compat.
		elif 'transpose' in state:
			self.reset_note_range()
			self.set_transpose(state['transpose'])
		else:
			self.reset_note_range()

		# Mixer
		self.zyngui.zynmixer.reset_state()
		if 'mixer' in state:
			self.zyngui.zynmixer.set_state(state['mixer'])

		# Restore ALSA-Mixer settings
		if self.amixer_layer and 'amixer_layer' in state:
			self.amixer_layer.restore_state_1(state['amixer_layer'])
			self.amixer_layer.restore_state_2(state['amixer_layer'])

		# Set active layer
		if state['index'] < len(self.root_layers) and state['index'] > 0:
			self.index = state['index']
		else:
			self.index = 0
		if self.index < len(self.root_layers):
			logging.info("Setting curlayer to {}".format(self.index))
			self.zyngui.set_curlayer(self.root_layers[self.index])

		# Autoconnect Audio
		self.zyngui.zynautoconnect_audio(True)

		# Restore Learned ZS3s (SubSnapShots)
		if 'learned_zs3' in state:
			self.learned_zs3 = state['learned_zs3']
		else:
			self.reset_zs3()
			self.import_legacy_zs3s(state)


	def import_legacy_zs3s(self, state):
		zs3_index = 0
		for midi_chan in range(0, 16):
			for prognum in range(0, 128):
				lstates = [None] * len(state['layers'])
				note_range = [None] * 16
				root_layer_index = None
				for li, lss in enumerate(state['layers']):
					if 'zs3_list' in lss and midi_chan == lss['midi_chan']:
						lstate = lss['zs3_list'][prognum]
						if not lstate:
							continue
						try:
							root_layer_index = self.root_layers.index(self.layers[li])
						except:
							pass
						lstate['engine_name'] = lss['engine_name']
						lstate['engine_nick'] = lss['engine_nick']
						lstate['engine_jackname'] = self.layers[li].engine.jackname
						lstate['midi_chan'] = midi_chan
						lstate['show_fav_presets'] = lss['show_fav_presets']
						if 'active_screen_index' in lstate:
							lstate['current_screen_index'] = lstate['active_screen_index']
							del lstate['active_screen_index']
						if 'note_range' in lstate:
							if lstate['note_range']:
								note_range[midi_chan] = lstate['note_range']
							del lstate['note_range']
						lstates[li] = lstate

				if root_layer_index is not None:
					zs3_new = {
						'index': root_layer_index,
						'layers': lstates,
						'note_range': note_range,
						'zs3_title': "Legacy ZS3 #{}".format(zs3_index + 1),
						'midi_learn_chan': midi_chan,
						'midi_learn_prognum': prognum
					}
					self.learned_zs3.append(zs3_new)
					#logging.debug("ADDED LEGACY ZS3 #{} => {}".format(zs3_index, zs3_new))
					zs3_index += 1


	def restore_state_zs3(self, state):

		# Get restored active layer index
		if state['index']<len(self.root_layers):
			index = state['index']
			restore_midi_chan = self.root_layers[index].midi_chan
		else:
			index = None
			restore_midi_chan = None

		logging.debug("RESTORING ZS3 STATE (index={}) => {}".format(index, state))

		# Calculate the layers to restore, depending of mode OMNI/MULTI, etc
		layer2restore = []
		for i, lss in enumerate(state['layers']):
			l2r = False
			if lss:
				if zynthian_gui_config.midi_single_active_channel:
					if lss['midi_chan'] == 256 or restore_midi_chan is not None and lss['midi_chan'] == restore_midi_chan:
						l2r = True
				elif lss['engine_nick'] != "MX":
					l2r = True
			layer2restore.append(l2r)

		# Restore layer state, step 1 => Restore Bank & Preset Status
		for i, layer in enumerate(self.layers):
			if layer2restore[i]:
				layer.restore_state_1(state['layers'][i])

		# Restore layer state, step 2 => Restore Controllers Status
		for i, layer in enumerate(self.layers):
			if layer2restore[i]:
				layer.restore_state_2(state['layers'][i])

		# Set Audio Capture
		if 'audio_capture' in state:
			self.set_audio_capture(state['audio_capture'])

		# Audio Recorder Armed
		if 'audio_recorder_armed' in state:
			for midi_chan in [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,256]:
				if midi_chan in state['audio_recorder_armed']:
					self.zyngui.audio_recorder.arm(midi_chan)
				else:
					self.zyngui.audio_recorder.unarm(midi_chan)

		# Set Clone
		if 'clone' in state:
			self.set_clone(state['clone'])

		# Note-range & Tranpose
		if 'note_range' in state:
			self.set_note_range(state['note_range'])
		# BW compat.
		elif 'transpose' in state:
			self.reset_note_range()
			self.set_transpose(state['transpose'])

		# Mixer
		if 'mixer' in state:
			self.zyngui.zynmixer.set_state(state['mixer'])

		# Restore ALSA-Mixer settings
		if self.amixer_layer and 'amixer_layer' in state:
			self.amixer_layer.restore_state_1(state['amixer_layer'])
			self.amixer_layer.restore_state_2(state['amixer_layer'])

		# Set active layer
		if index is not None and index!=self.index:
			logging.info("Setting curlayer to {}".format(index))
			self.index = index
			self.zyngui.set_curlayer(self.root_layers[index])

		# Autoconnect Audio => Not Needed!! It's called after action
		#self.zyngui.zynautoconnect_audio(True)


	def save_snapshot(self, fpath):
		try:
			# Get state
			state = self.get_state()

			# Snapshot file version
			state['version'] = 1

			# Extra engine state
			state['extended_config'] = self.get_extended_config()

			# MIDI profile
			state['midi_profile_state'] = self.get_midi_profile_state()

			# Audio & MIDI routing
			state['audio_routing'] = self.get_audio_routing()
			state['midi_routing'] = self.get_midi_routing()

			# Subsnapshots
			state['learned_zs3'] = self.learned_zs3

			# Zynseq RIFF data
			binary_riff_data = self.zyngui.zynseq.get_riff_data()
			b64_data = base64_encoded_data = base64.b64encode(binary_riff_data)
			state['zynseq_riff_b64'] = b64_data.decode('utf-8')

			# JSON Encode
			json = JSONEncoder().encode(state)
			logging.info("Saving snapshot %s => \n%s", fpath, json)

		except Exception as e:
			logging.error("Can't generate snapshot: %s" %e)
			return False

		try:
			with open(fpath,"w") as fh:
				logging.info("Saving snapshot %s => \n%s" % (fpath, json))
				fh.write(json)
				fh.flush()
				os.fsync(fh.fileno())

		except Exception as e:
			logging.error("Can't save snapshot '%s': %s" % (fpath, e))
			return False

		self.last_snapshot_fpath = fpath
		return True


	#	Fix snapshot, migrating to latest file format
	#	snapshot: Snapshot state in JSON
	#	Returns True on success
	def fix_snapshot(self, snapshot):
		version = 0
		if 'version' in snapshot:
			version = snapshot['version']

		if version < 1:
			# Version 1 2022-11-10
			for lss in snapshot['layers']:
				if 'Pianoteq' in lss['engine_name']:
					lss['engine_name'] = 'Pianoteq' # Pevious version used Pianoteq<ver>


	def load_snapshot(self, fpath, load_sequences=True):
		try:
			with open(fpath,"r") as fh:
				json=fh.read()
				logging.info("Loading snapshot %s => \n%s" % (fpath,json))
		except Exception as e:
			logging.error("Can't load snapshot '%s': %s" % (fpath,e))
			return False

		try:
			snapshot = JSONDecoder().decode(json)
			self.fix_snapshot(snapshot)
			# Layers
			self._load_snapshot_layers(snapshot)
			# Sequences
			if load_sequences:
				self._load_snapshot_sequences(snapshot)

			if fpath == self.zyngui.screens['snapshot'].last_state_snapshot_fpath and "last_snapshot_fpath" in snapshot:
				self.last_snapshot_fpath = snapshot['last_snapshot_fpath']
			else:
				self.last_snapshot_fpath = fpath

		except Exception as e:
			self.zyngui.reset_loading()
			logging.exception("Invalid snapshot: %s" % e)
			return False

		self.last_snapshot_count += 1
		return True


	def load_snapshot_layers(self, fpath):
		return self.load_snapshot(fpath, False)


	def load_snapshot_sequences(self, fpath):
		try:
			with open(fpath,"r") as fh:
				json=fh.read()
				logging.info("Loading snapshot %s => \n%s" % (fpath,json))
		except Exception as e:
			logging.error("Can't load snapshot '%s': %s" % (fpath,e))
			return False

		try:
			snapshot=JSONDecoder().decode(json)
			self._load_snapshot_sequences(snapshot)
		except Exception as e:
			self.zyngui.reset_loading()
			logging.exception("Invalid snapshot: %s" % e)
			return False

		#self.last_snapshot_fpath = fpath
		return True


	def _load_snapshot_layers(self, snapshot):
		# Mute output to avoid unwanted noises
		mute = self.zyngui.zynmixer.get_mute(256)
		self.zyngui.zynmixer.set_mute(256, True)

		# Clean all layers, but don't stop unused engines
		self.remove_all_layers(False)

		# Reusing Jalv engine instances raise problems (audio routing & jack names, etc..),
		# so we stop Jalv engines!
		self.zyngui.screens['engine'].stop_unused_jalv_engines()

		#Create new layers, starting engines when needed
		for i, lss in enumerate(snapshot['layers']):
			if lss['engine_nick'] == "MX":
				if zynthian_gui_config.snapshot_mixer_settings:
					snapshot['amixer_layer'] = lss
				del snapshot['layers'][i]
			else:
				if 'engine_jackname' in lss:
					jackname = lss['engine_jackname']
				elif lss['engine_nick'] == "AI":
					# There must be only one AI per audio mixer input
					jackname = "audioin-{:02d}".format(lss['midi_chan'])
				else:
					jackname = None
				engine = self.zyngui.screens['engine'].start_engine(lss['engine_nick'], jackname)
				self.layers.append(zynthian_layer(engine, lss['midi_chan'], self.zyngui))

		# Finally, stop all unused engines
		self.zyngui.screens['engine'].stop_unused_engines()

		self.restore_state_snapshot(snapshot)

		# Restore mute state
		self.zyngui.zynmixer.set_mute(255, mute)


	def _load_snapshot_sequences(self, snapshot):
		#Zynseq RIFF data
		if 'zynseq_riff_b64' in snapshot:
			b64_bytes = snapshot['zynseq_riff_b64'].encode('utf-8')
			binary_riff_data = base64.decodebytes(b64_bytes)
			self.zyngui.zynseq.restore_riff_data(binary_riff_data)


	def get_midi_profile_state(self):
		# Get MIDI profile state from environment
		midi_profile_state = OrderedDict()
		for key in os.environ.keys():
			if key.startswith("ZYNTHIAN_MIDI_"):
				midi_profile_state[key[14:]] = os.environ[key]
		return midi_profile_state


	def set_midi_profile_state(self, mps):
		# Load MIDI profile from saved state
		if mps is not None:
			for key in mps:
				os.environ["ZYNTHIAN_MIDI_" + key] = mps[key]
			zynthian_gui_config.set_midi_config()
			self.zyngui.init_midi()
			self.zyngui.init_midi_services()
			self.zyngui.zynautoconnect()
			return True


	def reset_midi_profile(self):
		self.zyngui.reload_midi_config()


	def set_select_path(self):
		self.select_path.set("Layers")


#------------------------------------------------------------------------------
