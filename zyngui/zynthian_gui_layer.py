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
import sys
import copy
import base64
import logging
import collections
from collections import OrderedDict
from json import JSONEncoder, JSONDecoder

# Zynthian specific modules
from zyncoder import *
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
		self.last_zs3_index = [0] * 16; # Last selected ZS3 snapshot, per MIDI channel
		super().__init__('Layer', True)
		self.create_amixer_layer()
		

	def reset(self):
		self.last_zs3_index = [0] * 16; # Last selected ZS3 snapshot, per MIDI channel
		self.show_all_layers = False
		self.add_layer_eng = None
		self.last_snapshot_fpath = None
		self.reset_clone()
		self.reset_note_range()
		self.remove_all_layers(True)
		self.reset_midi_profile()


	def fill_list(self):
		self.list_data=[]

		# Get list of root layers
		self.root_layers=self.get_fxchain_roots()

		for i,layer in enumerate(self.root_layers):
			self.list_data.append((str(i+1),i,layer.get_presetpath()))

		# Add separator
		if len(self.root_layers)>0:
			self.list_data.append((None,len(self.list_data),"-----------------------------"))

		# Add fixed entries
		self.list_data.append(('NEW_SYNTH',len(self.list_data),"NEW Synth Layer"))
		self.list_data.append(('NEW_AUDIO_FX',len(self.list_data),"NEW Audio-FX Layer"))
		self.list_data.append(('NEW_MIDI_FX',len(self.list_data),"NEW MIDI-FX Layer"))
		self.list_data.append(('NEW_GENERATOR',len(self.list_data),"NEW Generator Layer"))
		self.list_data.append(('NEW_SPECIAL',len(self.list_data),"NEW Special Layer"))
		self.list_data.append(('RESET',len(self.list_data),"REMOVE All Layers"))
		self.list_data.append((None,len(self.list_data),"-----------------------------"))
		self.list_data.append(('ALL_OFF',len(self.list_data),"PANIC! All Notes Off"))

		super().fill_list()


	def select_action(self, i, t='S'):
		self.index = i

		if self.list_data[i][0] is None:
			pass

		elif self.list_data[i][0]=='NEW_SYNTH':
			self.add_layer("MIDI Synth")

		elif self.list_data[i][0]=='NEW_AUDIO_FX':
			self.add_layer("Audio Effect")

		elif self.list_data[i][0]=='NEW_MIDI_FX':
			self.add_layer("MIDI Tool")

		elif self.list_data[i][0]=='NEW_GENERATOR':
			self.add_layer("Audio Generator")

		elif self.list_data[i][0]=='NEW_SPECIAL':
			self.add_layer("Special")

		elif self.list_data[i][0]=='RESET':
			self.zyngui.show_confirm("Do you really want to remove all layers?", self.reset_confirmed)

		elif self.list_data[i][0]=='ALL_OFF':
			self.zyngui.callable_ui_action("ALL_OFF")

		else:
			if t=='S':
				self.layer_control()

			elif t=='B':
				self.layer_options()


	def reset_confirmed(self, params=None):
		if len(self.zyngui.screens['layer'].layers)>0:
			self.zyngui.screens['snapshot'].save_last_state_snapshot()
		self.reset()
		self.zyngui.show_screen('layer')


	def create_amixer_layer(self):
		mixer_eng = self.zyngui.screens['engine'].start_engine('MX')
		self.amixer_layer=zynthian_layer(mixer_eng, None, self.zyngui)


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
			self.zyngui.show_modal('layer_options')


	def next(self, control=True):
		self.zyngui.restore_curlayer()
		if len(self.root_layers)>1:
			if self.zyngui.curlayer in self.layers:
				self.index += 1
				if self.index>=len(self.root_layers):
					self.index = 0

			if control:
				self.select_listbox(self.index)
				self.layer_control()
			else:
				self.zyngui.set_curlayer(self.root_layers[self.index])
				self.select(self.index)


	def get_layer_index(self, layer):
		try:
			return self.layers.index(layer)
		except:
			return None


	def get_num_layers(self):
		return len(self.layers)


	def get_root_layers(self):
		self.root_layers=self.get_fxchain_roots()
		return self.root_layers


	def get_root_layer_index(self, layer):
		try:
			return self.root_layers.index(layer)
		except:
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
			"Serial": False,
			"Parallel": True
		}
		self.zyngui.screens['option'].config("Chain Mode", chain_modes, self.cb_chain_options_modal)
		self.zyngui.show_modal('option')


	def cb_chain_options_modal(self, option, chain_parallel):
		self.layer_chain_parallel = chain_parallel
		self.zyngui.show_modal('engine')


	def add_layer(self, etype):
		self.add_layer_eng = None
		self.replace_layer_index = None
		self.layer_chain_parallel = False
		self.zyngui.screens['engine'].set_engine_type(etype)
		self.zyngui.show_modal('engine')


	def replace_layer(self, i):
		self.add_layer_eng = None
		self.replace_layer_index = i
		self.layer_chain_parallel = False
		self.zyngui.screens['engine'].set_engine_type(self.layers[i].engine.type, self.layers[i].midi_chan)
		self.zyngui.show_modal('engine')


	def add_fxchain_layer(self, midi_chan):
		self.add_layer_eng = None
		self.replace_layer_index = None
		self.layer_chain_parallel = False
		self.zyngui.screens['engine'].set_fxchain_mode(midi_chan)
		if self.get_fxchain_count(midi_chan)>0:
			self.show_chain_options_modal()
		else:
			self.zyngui.show_modal('engine')


	def replace_fxchain_layer(self, i):
		self.replace_layer(i)


	def add_midichain_layer(self, midi_chan):
		self.add_layer_eng = None
		self.replace_layer_index = None
		self.layer_chain_parallel = False
		self.zyngui.screens['engine'].set_midichain_mode(midi_chan)
		if self.get_midichain_count(midi_chan)>0:
			self.show_chain_options_modal()
		else:
			self.zyngui.show_modal('engine')


	def replace_midichain_layer(self, i):
		self.replace_layer(i)


	def add_layer_engine(self, eng, midi_chan=None):
		self.add_layer_eng=eng

		if eng=='MD':
			self.add_layer_midich(None)

		elif eng=='AE':
			self.add_layer_midich(0, False)
			self.add_layer_midich(1, False)
			self.add_layer_midich(2, False)
			self.add_layer_midich(3, False)
			self.fill_list()
			self.index=len(self.layers)-4
			self.layer_control()

		elif midi_chan is None:
			self.replace_layer_index=None
			self.zyngui.screens['midi_chan'].set_mode("ADD", 0, self.get_free_midi_chans())
			self.zyngui.show_modal('midi_chan')

		else:
			self.add_layer_midich(midi_chan)


	def add_layer_midich(self, midich, select=True):
		if self.add_layer_eng:
			# Create layer node ...
			zyngine = self.zyngui.screens['engine'].start_engine(self.add_layer_eng)
			layer=zynthian_layer(zyngine, midich, self.zyngui)

			# add/replace Audio Effects ...
			if len(self.layers)>0 and layer.engine.type=="Audio Effect":
				if self.replace_layer_index is not None:
					self.replace_on_fxchain(layer)
				else:
					self.add_to_fxchain(layer, self.layer_chain_parallel)
					self.layers.append(layer)
			# add/replace MIDI Effects ...
			elif len(self.layers)>0 and layer.engine.type=="MIDI Tool":
				if self.replace_layer_index is not None:
					self.replace_on_midichain(layer)
				else:
					self.add_to_midichain(layer, self.layer_chain_parallel)
					self.layers.append(layer)
			# replace Synth ...
			elif len(self.layers)>0 and layer.engine.type=="MIDI Synth":
				if self.replace_layer_index is not None:
					self.replace_synth(layer)
				else:
					self.layers.append(layer)
			# new root layer
			else:
				self.layers.append(layer)

			self.zyngui.zynautoconnect()

			if select:
				self.fill_list()
				root_layer = self.get_fxchain_root(layer)
				try:
					self.index = self.root_layers.index(root_layer)
					self.layer_control(layer)
				except Exception as e:
					logging.error(e)
					self.zyngui.show_screen('layer')


	def remove_layer(self, i, stop_unused_engines=True):
		if i>=0 and i<len(self.layers):
			logging.debug("Removing layer {} => {} ...".format(i, self.layers[i].get_basepath()))

			if self.layers[i].engine.type == "MIDI Tool":
				self.drop_from_midichain(self.layers[i])
				self.layers[i].mute_midi_out()
			else:
				self.drop_from_fxchain(self.layers[i])
				self.layers[i].mute_audio_out()

			self.zyngui.zynautoconnect(True)

			self.zyngui.zynautoconnect_acquire_lock()
			self.layers[i].reset()
			self.layers.pop(i)
			self.zyngui.zynautoconnect_release_lock()

			# Stop unused engines
			if stop_unused_engines:
				self.zyngui.screens['engine'].stop_unused_engines()


	def remove_root_layer(self, i, stop_unused_engines=True):
		if i>=0 and i<len(self.root_layers):
			# For some engines (Aeolus, setBfree), delete all layers from the same engine
			if self.root_layers[i].engine.nickname in ['BF', 'AE']:
				root_layers_to_delete = copy.copy(self.root_layers[i].engine.layers)
			else:
				root_layers_to_delete = [self.root_layers[i]]

			# Mute Audio Layers & build list of layers to delete
			layers_to_delete = []
			for root_layer in root_layers_to_delete:
				# Midichain layers
				midichain_layers = self.get_midichain_layers(root_layer)
				if len(midichain_layers)>0:
					midichain_layers.remove(root_layer)
				layers_to_delete += midichain_layers
				for layer in reversed(midichain_layers):
					logging.debug("Mute MIDI layer '{}' ...".format(i, layer.get_basepath()))
					self.drop_from_midichain(layer)
					layer.mute_midi_out()
				# Fxchain layers => Mute!
				fxchain_layers = self.get_fxchain_layers(root_layer)
				if len(fxchain_layers)>0:
					fxchain_layers.remove(root_layer)
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
				except Exception as e:
					logging.error("Can't delete layer {} => {}".format(i,e))
			self.zyngui.zynautoconnect_release_lock()

			# Stop unused engines
			if stop_unused_engines:
				self.zyngui.screens['engine'].stop_unused_engines()

			# Recalculate selector and root_layers list
			self.fill_list()

			if self.zyngui.curlayer in self.root_layers:
				self.index = self.root_layers.index(self.zyngui.curlayer)
			else:
				self.index=0
				try:
					self.zyngui.set_curlayer(self.root_layers[self.index])
				except:
					self.zyngui.set_curlayer(None)

			self.set_selector()


	def remove_all_layers(self, stop_engines=True):
		# Remove all layers: Step 1 => Drop from FX chain and mute
		i = len(self.layers)
		while i>0:
			i -= 1
			logging.debug("Mute layer {} => {} ...".format(i, self.layers[i].get_basepath()))
			self.drop_from_midichain(self.layers[i])
			self.layers[i].mute_midi_out()
			self.drop_from_fxchain(self.layers[i])
			self.layers[i].mute_audio_out()

		self.zyngui.zynautoconnect(True)

		# Remove all layers: Step 2 => Delete layers
		i = len(self.layers)
		self.zyngui.zynautoconnect_acquire_lock()
		while i>0:
			i -= 1
			logging.debug("Remove layer {} => {} ...".format(i, self.layers[i].get_basepath()))
			self.layers[i].reset()
			self.layers.pop(i)
		self.zyngui.zynautoconnect_release_lock()

		# Stop ALL engines
		if stop_engines:
			self.zyngui.screens['engine'].stop_unused_engines()

		self.index=0
		self.zyngui.set_curlayer(None)

		# Refresh UI
		self.fill_list()
		self.set_selector()


	#----------------------------------------------------------------------------
	# Clone, Note Range & Transpose
	#----------------------------------------------------------------------------

	def set_clone(self, clone_status):
		for i in range(0,16):
			for j in range(0,16):
				if isinstance(clone_status[i][j],dict):
					zyncoder.lib_zyncoder.set_midi_filter_clone(i,j,clone_status[i][j]['enabled'])
					self.zyngui.screens['midi_cc'].set_clone_cc(i,j,clone_status[i][j]['cc'])
				else:
					zyncoder.lib_zyncoder.set_midi_filter_clone(i,j,clone_status[i][j])
					zyncoder.lib_zyncoder.reset_midi_filter_clone_cc(i,j)


	def reset_clone(self):
		for i in range(0,16):
			zyncoder.lib_zyncoder.reset_midi_filter_clone(i)


	def set_transpose(self, tr_status):
		for i in range(0,16):
			zyncoder.lib_zyncoder.set_midi_filter_halftone_trans(i, tr_status[i])


	def set_note_range(self, nr_status):
		for i in range(0,16):
			zyncoder.lib_zyncoder.set_midi_filter_note_range(i, nr_status[i]['note_low'], nr_status[i]['note_high'], nr_status[i]['octave_trans'], nr_status[i]['halftone_trans'])


	def reset_note_range(self):
		for i in range(0,16):
			zyncoder.lib_zyncoder.reset_midi_filter_note_range(i)


	#----------------------------------------------------------------------------
	# MIDI Control (ZS3 & PC)
	#----------------------------------------------------------------------------

	def set_midi_chan_preset(self, midich, preset_index):
		selected = False
		for i,layer in enumerate(self.root_layers):
			mch=layer.get_midi_chan()
			if mch is None or mch==midich:
				# Fluidsynth engine => ignore Program Change on channel 9
				if layer.engine.nickname=="FS" and mch==9:
					continue
				if layer.set_preset(preset_index,True) and not selected:
					selected = True
					try:
						if not self.zyngui.modal_screen:
							if self.shown:
								self.show()
							elif self.zyngui.active_screen in ('bank','preset','control'):
								self.select_action(i)
					except Exception as e:
						logging.error("Can't refresh GUI! => {}".format(e))


	def set_midi_chan_zs3(self, midich, zs3_index):
		selected = False
		for layer in self.layers:
			if zynthian_gui_config.midi_single_active_channel or midich==layer.get_midi_chan():
				if layer.restore_zs3(zs3_index) and not selected:
					self.last_zs3_index[midich] = zs3_index
					try:
						if not self.zyngui.modal_screen and self.zyngui.active_screen not in ('main','layer'):
							self.select_action(self.root_layers.index(layer))
						selected = True
					except Exception as e:
						logging.error("Can't select layer => {}".format(e))


	def get_last_zs3_index(self, midich):
		return self.last_zs3_index[midich]


	def save_midi_chan_zs3(self, midich, zs3_index):
		result = False
		for layer in self.layers:
			mch=layer.get_midi_chan()
			if mch is None or mch==midich:
				layer.save_zs3(zs3_index)
				result = True
			elif zynthian_gui_config.midi_single_active_channel:
				layer.delete_zs3(zs3_index)

		return result


	def delete_midi_chan_zs3(self, midich, zs3_index):
		for layer in self.layers:
			if zynthian_gui_config.midi_single_active_channel or midich==layer.get_midi_chan():
				layer.delete_zs3(zs3_index)


	def get_midi_chan_zs3_status(self, midich, zs3_index):
		for layer in self.layers:
			if zynthian_gui_config.midi_single_active_channel or midich==layer.get_midi_chan():
				if layer.get_zs3(zs3_index):
					return True
		return False


	def get_midi_chan_zs3_used_indexes(self, midich):
		res=[]
		for i in range(128):
			if self.get_midi_chan_zs3_status(midich,i):
				res.append(i)
		return res


	def midi_control_change(self, chan, ccnum, ccval):
		if ccnum==0:
			for layer in self.root_layers:
				if layer.midi_chan==chan:
					layer.midi_bank_msb(ccval)
		elif ccnum==32:
			for layer in self.root_layers:
				if layer.midi_chan==chan:
					layer.midi_bank_lsb(ccval)
		else:
			for layer in self.layers:
				layer.midi_control_change(chan, ccnum, ccval)
			self.amixer_layer.midi_control_change(chan, ccnum, ccval)


	#----------------------------------------------------------------------------
	# Audio Routing
	#----------------------------------------------------------------------------

	def get_audio_routing(self):
		res = {}
		for i, layer in enumerate(self.layers):
			res[layer.get_jackname()] = layer.get_audio_out()
		return res


	def set_audio_routing(self, audio_routing=None):
		for i, layer in enumerate(self.layers):
			try:
				layer.set_audio_out(audio_routing[layer.get_jackname()])
			except:
				layer.reset_audio_out()


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

	#----------------------------------------------------------------------------
	# Jackname managing
	#----------------------------------------------------------------------------

	def get_layer_by_jackname(self, jackname):
		for layer in self.layers:
			if layer.jackname in jackname:
				return layer


	def get_jackname_count(self, jackname):
		count = 0
		for layer in self.layers:
			if layer.jackname is not None and layer.jackname.startswith(jackname):
				count += 1
		return count

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
			if layer.midi_chan==None and layer.engine.type in ("Special"):
				roots.append(layer)

		for chan in range(16):
			for layer in self.layers:
				if layer.midi_chan==chan:
					roots.append(layer)
					break

		return roots


	def get_fxchain_layers(self, layer=None):
		if layer is None:
			layer = self.zyngui.curlayer

		if layer is not None:
			fxchain_layers = []

			if layer.midi_chan is not None:
				for l in self.layers:
					if l.engine.type!="MIDI Tool" and l not in fxchain_layers and l.midi_chan==layer.midi_chan:
						fxchain_layers.append(l)

			elif layer in self.layers:
					fxchain_layers.append(layer)

			return fxchain_layers

		else:
			return None


	def get_fxchain_count(self, midi_chan):
		count = 0
		if midi_chan is not None:
			for l in self.layers:
				if l.engine.type in ("Audio Effect") and l.midi_chan==midi_chan:
						count += 1
		return count


	def get_fxchain_root(self, layer):
		if layer.midi_chan is None:
			return layer
		for l in self.layers:
			if l.midi_chan==layer.midi_chan:
				return l


	# Returns FX-chain layers routed to extra-chain ports or not routed at all.
	def get_fxchain_ends(self, layer):
		fxlbjn = {}
		for fxlayer in self.get_fxchain_layers(layer):
			fxlbjn[fxlayer.jackname] = fxlayer

		ends=[]
		for layer in fxlbjn.values():
			try:
				if layer.get_audio_out()[0] not in fxlbjn:
					ends.append(layer)
			except:
				ends.append(layer)

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
			if l!=layer and l.engine.type=="Audio Effect" and l.midi_chan==layer.midi_chan and collections.Counter(l.audio_out)==collections.Counter(layer.audio_out):
				pars.append(l)
				#logging.error("PARALLEL LAYER => {}".format(l.get_audio_jackname()))
		return pars


	def add_to_fxchain(self, layer, chain_parallel=False):
		try:
			for end in self.get_fxchain_ends(layer):
				if end!=layer:
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
				if len(up.get_audio_out())==0:
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
			if layer.midi_chan==None and layer.engine.type in ("Special"):
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
					if l.engine.type in ("MIDI Synth", "MIDI Tool", "Special") and l not in midichain_layers and l.midi_chan==layer.midi_chan:
						midichain_layers.append(l)

			return midichain_layers

		else:
			return None


	def get_midichain_count(self, midi_chan):
		count = 0
		if midi_chan is not None:
			for l in self.layers:
				if l.engine.type in ("MIDI Tool") and l.midi_chan==midi_chan:
						count += 1
		return count


	def get_midichain_root(self, layer):
		if layer.midi_chan is None:
			return layer

		for l in self.layers:
			if l.engine.type=="MIDI Tool" and l.midi_chan==layer.midi_chan:
				return l

		for l in self.layers:
			if l.engine.type in ("MIDI Synth", "Special") and l.midi_chan==layer.midi_chan:
				return l

		return None


	def get_midichain_root_by_chan(self, chan):
		if chan is None:
			for l in self.layers:
				if l.midi_chan is None:
					return l

		else:
			for l in self.layers:
				if l.engine.type=="MIDI Tool" and l.midi_chan==chan:
					return l

			for l in self.layers:
				if l.engine.type in ("MIDI Synth", "Special") and l.midi_chan==chan:
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
			if l!=layer and l.engine.type=="MIDI Tool" and l.midi_chan==layer.midi_chan and collections.Counter(l.midi_out)==collections.Counter(layer.midi_out):
				pars.append(l)
				#logging.error("PARALLEL LAYER => {}".format(l.get_midi_jackname()))
		return pars


	def add_to_midichain(self, layer, chain_parallel=False):
		try:
			for end in self.get_midichain_ends(layer):
				if end!=layer:
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
				if len(up.get_midi_out())==0:
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

	def save_snapshot(self, fpath):
		try:
			snapshot={
				'index':self.index,
				'layers':[],
				'clone':[],
				'note_range':[],
				'audio_capture': self.get_audio_capture(),
				'audio_routing': self.get_audio_routing(),
				'midi_routing': self.get_midi_routing(),
				'extended_config': self.get_extended_config(),
				'midi_profile_state': self.get_midi_profile_state(),
			}

			#Layers info
			for layer in self.layers:
				snapshot['layers'].append(layer.get_snapshot())

			if zynthian_gui_config.snapshot_mixer_settings and self.amixer_layer:
				snapshot['layers'].append(self.amixer_layer.get_snapshot())

			#Clone info
			for i in range(0,16):
				snapshot['clone'].append([])
				for j in range(0,16):
					clone_info = {
						'enabled': zyncoder.lib_zyncoder.get_midi_filter_clone(i,j),
						'cc': list(map(int,zyncoder.lib_zyncoder.get_midi_filter_clone_cc(i,j).nonzero()[0]))
					}
					snapshot['clone'][i].append(clone_info)

			#Note-range info
			for i in range(0,16):
				info = {
					'note_low': zyncoder.lib_zyncoder.get_midi_filter_note_low(i),
					'note_high': zyncoder.lib_zyncoder.get_midi_filter_note_high(i),
					'octave_trans': zyncoder.lib_zyncoder.get_midi_filter_octave_trans(i),
					'halftone_trans': zyncoder.lib_zyncoder.get_midi_filter_halftone_trans(i)
				}
				snapshot['note_range'].append(info)

			#Zynseq RIFF data
			if 'stepseq' in self.zyngui.screens:
				binary_riff_data = self.zyngui.screens['stepseq'].get_riff_data()
				b64_data = base64_encoded_data = base64.b64encode(binary_riff_data)
				snapshot['zynseq_riff_b64'] = b64_data.decode('utf-8')

			#Audio Recorder out
			snapshot['audio_recorder_out'] = self.zyngui.screens['audio_recorder'].get_audio_out()

			#JSON Encode
			json=JSONEncoder().encode(snapshot)
			logging.info("Saving snapshot %s => \n%s" % (fpath,json))

		except Exception as e:
			logging.error("Can't generate snapshot: %s" %e)
			return False

		try:
			with open(fpath,"w") as fh:
				fh.write(json)
				fh.flush()
				os.fsync(fh.fileno())

		except Exception as e:
			logging.error("Can't save snapshot '%s': %s" % (fpath,e))
			return False

		self.last_snapshot_fpath = fpath
		return True


	def load_snapshot(self, fpath, quiet=False, load_sequences=True):
		try:
			with open(fpath,"r") as fh:
				json=fh.read()
				logging.info("Loading snapshot %s => \n%s" % (fpath,json))
		except Exception as e:
			logging.error("Can't load snapshot '%s': %s" % (fpath,e))
			return False

		try:
			snapshot=JSONDecoder().decode(json)
			self._load_snapshot_layers(snapshot)
			if load_sequences:
				self._load_snapshot_sequences(snapshot)
			#Post action
			if not quiet:
				if self.index<len(self.root_layers):
					self.select_action(self.index)
				else:
					self.index = 0
					self.zyngui.show_screen('layer')
		except Exception as e:
			self.zyngui.reset_loading()
			logging.exception("Invalid snapshot: %s" % e)
			return False

		self.last_snapshot_fpath = fpath
		return True


	def load_snapshot_layers(self, fpath, quiet=False):
		return self.load_snapshot(fpath, quiet, False)


	def load_snapshot_sequences(self, fpath, quiet=False):
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
			#Post action
			if not quiet:
				self.zyngui.show_modal('stepseq')
		except Exception as e:
			self.zyngui.reset_loading()
			logging.exception("Invalid snapshot: %s" % e)
			return False

		#self.last_snapshot_fpath = fpath
		return True


	def _load_snapshot_layers(self, snapshot):
		#Clean all layers, but don't stop unused engines
		self.remove_all_layers(False)

		# Reusing Jalv engine instances raise problems (audio routing & jack names, etc..),
		# so we stop Jalv engines!
		self.zyngui.screens['engine'].stop_unused_jalv_engines()

		#Create new layers, starting engines when needed
		for i, lss in enumerate(snapshot['layers']):
			if lss['engine_nick']=="MX":
				if zynthian_gui_config.snapshot_mixer_settings:
					snapshot['amixer_layer'] = lss
				del snapshot['layers'][i]
			else:
				engine=self.zyngui.screens['engine'].start_engine(lss['engine_nick'])
				self.layers.append(zynthian_layer(engine,lss['midi_chan'], self.zyngui))

		# Finally, stop all unused engines
		self.zyngui.screens['engine'].stop_unused_engines()

		#Restore MIDI profile state
		if 'midi_profile_state' in snapshot:
			self.set_midi_profile_state(snapshot['midi_profile_state'])

		#Set MIDI Routing
		if 'midi_routing' in snapshot:
			self.set_midi_routing(snapshot['midi_routing'])
		else:
			self.reset_midi_routing()

		#Autoconnect MIDI
		self.zyngui.zynautoconnect_midi(True)

		#Set extended config
		if 'extended_config' in snapshot:
			self.set_extended_config(snapshot['extended_config'])

		# Restore layer state, step 1 => Restore Bank & Preset Status
		for i, lss in enumerate(snapshot['layers']):
			self.layers[i].restore_snapshot_1(lss)

		# Restore layer state, step 2 => Restore Controllers Status
		for i, lss in enumerate(snapshot['layers']):
			self.layers[i].restore_snapshot_2(lss)

		#Set Audio Routing
		if 'audio_routing' in snapshot:
			self.set_audio_routing(snapshot['audio_routing'])
		else:
			self.reset_audio_routing()

		#Set Audio Capture
		if 'audio_capture' in snapshot:
			self.set_audio_capture(snapshot['audio_capture'])
		else:
			self.reset_audio_routing()

		#Autoconnect Audio
		self.zyngui.zynautoconnect_audio()

		# Restore ALSA Mixer settings
		if self.amixer_layer and 'amixer_layer' in snapshot:
			self.amixer_layer.restore_snapshot_1(snapshot['amixer_layer'])
			self.amixer_layer.restore_snapshot_2(snapshot['amixer_layer'])

		#Fill layer list
		self.fill_list()

		#Set active layer
		if snapshot['index']<len(self.layers):
			self.index = snapshot['index']
			self.zyngui.set_curlayer(self.layers[self.index])
		elif len(self.layers)>0:
			self.index = 0
			self.zyngui.set_curlayer(self.layers[self.index])

		#Set Clone
		if 'clone' in snapshot:
			self.set_clone(snapshot['clone'])
		else:
			self.reset_clone()

		# Note-range & Tranpose
		self.reset_note_range()
		if 'note_range' in snapshot:
			self.set_note_range(snapshot['note_range'])
		#BW compat.
		elif 'transpose' in snapshot:
			self.set_transpose(snapshot['transpose'])

		#Audio Recorder Out
		if 'audio_recorder_out' in snapshot:
			self.zyngui.screens['audio_recorder'].audio_out = snapshot['audio_recorder_out'] 


	def _load_snapshot_sequences(self, snapshot):
		#Zynseq RIFF data
		if 'zynseq_riff_b64' in snapshot and 'stepseq' in self.zyngui.screens:
			b64_bytes = snapshot['zynseq_riff_b64'].encode('utf-8')
			binary_riff_data = base64.decodebytes(b64_bytes)
			self.zyngui.screens['stepseq'].restore_riff_data(binary_riff_data)


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
