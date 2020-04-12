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
import logging
from collections import OrderedDict
from json import JSONEncoder, JSONDecoder

# Zynthian specific modules
from zyncoder import *
from . import zynthian_gui_config
from . import zynthian_gui_selector
from zyngine import zynthian_layer

#------------------------------------------------------------------------------
# Zynthian Layer Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_layer(zynthian_gui_selector):

	def __init__(self):
		self.layers = []
		self.root_layers = []
		self.curlayer = None
		self._curlayer = None
		self.amixer_layer = None
		self.show_all_layers = False
		self.add_layer_eng = None
		self.replace_layer_index = None
		self.last_snapshot_fpath = None
		super().__init__('Layer', True)


	def reset(self):
		self.show_all_layers = False
		self.add_layer_eng = None
		self.last_snapshot_fpath = None
		self.reset_clone()
		self.reset_transpose()
		self.remove_all_layers(True)


	def toggle_show_all_layers(self):
		if self.show_all_layers:
			self.show_all_layers = False
		else:
			self.show_all_layers = True


	def fill_list(self):
		self.list_data=[]

		# Add list of root layers
		if self.show_all_layers:
			self.root_layers=self.layers
		else:
			self.root_layers=self.get_fxchain_roots()

		for i,layer in enumerate(self.root_layers):
			self.list_data.append((str(i+1),i,layer.get_presetpath()))

		# Add separator
		if len(self.root_layers)>0:
			self.list_data.append((None,len(self.list_data),"-----------------------------"))

		# Add fixed entries
		self.list_data.append(('NEW_SYNTH',len(self.list_data),"NEW Synth Layer"))
		self.list_data.append(('NEW_EFFECT',len(self.list_data),"NEW Effect Layer"))
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

		elif self.list_data[i][0]=='NEW_EFFECT':
			self.add_layer("Audio Effect")

		elif self.list_data[i][0]=='NEW_GENERATOR':
			self.add_layer("Audio Generator")

		elif self.list_data[i][0]=='NEW_SPECIAL':
			self.add_layer("Special")

		elif self.list_data[i][0]=='RESET':
			self.reset()
			self.zyngui.show_screen('layer')

		elif self.list_data[i][0]=='ALL_OFF':
			self.zyngui.callable_ui_action("ALL_OFF")

		else:
			if t=='S':
				self.layer_control()

			elif t=='B':
				self.layer_options()


	def create_amixer_layer(self):
		mixer_eng = self.zyngui.screens['engine'].start_engine('MX')
		self.amixer_layer=zynthian_layer(mixer_eng, None, self.zyngui)


	def remove_amixer_layer(self):
		self.amixer_layer.reset()
		self.amixer_layer = None


	def layer_control_amixer(self):
		if self.amixer_layer:
			self._curlayer = self.curlayer
			self.curlayer = self.amixer_layer
			self.zyngui.set_curlayer(self.curlayer)
			self.zyngui.show_modal('control')


	def restore_curlayer(self):
		if self._curlayer:
			self.curlayer = self._curlayer
			self._curlayer = None
			self.zyngui.set_curlayer(self.curlayer)


	def curlayer_control(self):
		if self.curlayer:
			self.zyngui.set_curlayer(self.curlayer)
			# If there is a preset selection for the active layer ...
			if self.curlayer.get_preset_name():
				self.zyngui.show_screen('control')
			else:
				self.zyngui.show_screen('bank')
				# If there is only one bank, jump to preset selection
				if len(self.curlayer.bank_list)<=1:
					self.zyngui.screens['bank'].select_action(0)


	def layer_control(self):
		self.curlayer = self.root_layers[self.index]
		self.curlayer_control()


	def layer_control_restore(self):
		if self._curlayer:
			self.curlayer = self._curlayer
			self._curlayer = None
		self.curlayer_control()


	def layer_options(self):
		i = self.get_layer_selected()
		if i is not None and self.root_layers[i].engine.nickname!='MX':
			self.zyngui.screens['layer_options'].reset()
			self.zyngui.show_modal('layer_options')


	def next(self):
		self.restore_curlayer()

		if len(self.root_layers)>1:

			if self.curlayer in self.layers:
				self.index += 1
				if self.index>=len(self.root_layers):
					self.index = 0

			self.select_listbox(self.index)
			self.layer_control()


	def get_num_layers(self):
		return len(self.layers)


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


	def add_layer(self, etype):
		self.add_layer_eng = None
		self.replace_layer_index = None
		self.zyngui.screens['engine'].set_engine_type(etype)
		self.zyngui.show_modal('engine')


	def add_fxchain_layer(self, midi_chan):
		self.add_layer_eng = None
		self.replace_layer_index = None
		self.zyngui.screens['engine'].set_fxchain_mode(midi_chan)
		self.zyngui.show_modal('engine')


	def replace_fxchain_layer(self, i):
		self.add_layer_eng = None
		self.replace_layer_index = i
		self.zyngui.screens['engine'].set_fxchain_mode(self.layers[i].midi_chan)
		self.zyngui.show_modal('engine')


	def add_layer_engine(self, eng, midi_chan=None):
		self.add_layer_eng=eng

		if eng.nickname=='MD':
			self.add_layer_midich(None)

		elif eng.nickname=='AE':
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
			layer=zynthian_layer(self.add_layer_eng, midich, self.zyngui)

			# Try to connect effects ...
			if len(self.layers)>0 and layer.engine.type=="Audio Effect":
				if self.replace_layer_index is not None:
					self.replace_on_fxchain(layer)
				else:
					self.add_to_fxchain(layer)
					self.layers.append(layer)
			else:
				self.layers.append(layer)

			self.zyngui.zynautoconnect()

			if select:
				self.fill_list()
				root_layer = self.get_fxchain_root(layer)
				try:
					self.index = self.root_layers.index(root_layer)
					self.layer_control()
				except Exception as e:
					logging.error(e)
					self.zyngui.show_screen('layer')


	def remove_layer(self, i, stop_unused_engines=True):
		if i>=0 and i<len(self.layers):
			logging.debug("Removing layer {} => {} ...".format(i, self.layers[i].get_basepath()))
			
			self.drop_from_fxchain(self.layers[i])
			self.layers[i].mute_audio_out()
			self.zyngui.zynautoconnect()

			self.zyngui.zynautoconnect_acquire_lock()
			self.layers[i].reset()
			del self.layers[i]
			self.zyngui.zynautoconnect_release_lock()

			if self.curlayer not in self.root_layers:
				self.index=0
				try:
					self.curlayer = self.root_layers[self.index]
				except:
					self.curlayer = None
			else:
				self.index = self.root_layers.index(self.curlayer)

			self.fill_list()
			self.set_selector()
			self.zyngui.set_curlayer(self.curlayer)

			# Stop unused engines
			if stop_unused_engines:
				self.zyngui.screens['engine'].stop_unused_engines()


	def remove_root_layer(self, i, stop_unused_engines=True):
		if i>=0 and i<len(self.root_layers):
			# For some engines (Aeolus, setBfree), delete all layers on the same engine
			if self.root_layers[i].engine.nickname in ['BF', 'AE']:
				root_layers_to_delete = copy.copy(self.root_layers[i].engine.layers)
			else:
				root_layers_to_delete = [self.root_layers[i]]

			# Remove root layer and fxchain
			for root_layer in root_layers_to_delete:
				for layer in reversed(self.get_fxchain_layers(root_layer)):
					self.remove_layer(self.layers.index(layer), False)

			# Stop unused engines
			if stop_unused_engines:
				self.zyngui.screens['engine'].stop_unused_engines()


	def remove_all_layers(self, stop_engines=True):
		# Remove all layers: Step 1 => Drop from FX chain and mute
		i = len(self.layers)
		while i>0:
			i -= 1
			logging.debug("Mute layer {} => {} ...".format(i, self.layers[i].get_basepath()))
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
			del self.layers[i]
		self.zyngui.zynautoconnect_release_lock()

		self.index=0
		try:
			self.curlayer = self.root_layers[self.index]
		except:
			self.curlayer = None

		# Stop ALL engines
		if stop_engines:
			self.zyngui.screens['engine'].stop_unused_engines()

		# Reset MIDI config
		self.reset_midi_profile()

		# Refresh UI
		self.fill_list()
		self.set_selector()
		self.zyngui.set_curlayer(self.curlayer)


	#def refresh(self):
	#	self.curlayer.refresh()


	#----------------------------------------------------------------------------
	# Clone & Transpose
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


	def set_transpose(self, transpose_status):
		for i in range(0,16):
			zyncoder.lib_zyncoder.set_midi_filter_transpose(i,transpose_status[i])


	def reset_transpose(self):
		for i in range(0,16):
			zyncoder.lib_zyncoder.set_midi_filter_transpose(i,0)


	#----------------------------------------------------------------------------
	# MIDI Control (ZS3 & CC)
	#----------------------------------------------------------------------------

	def set_midi_chan_preset(self, midich, preset_index):
		selected = False
		for layer in self.layers:
			mch=layer.get_midi_chan()
			if mch is None or mch==midich:
				if layer.set_preset(preset_index,True) and not selected:
					try:
						self.select_action(self.root_layers.index(layer))
						selected = True
					except Exception as e:
						logging.error("Can't select layer => {}".format(e))


	def set_midi_chan_zs3(self, midich, zs3_index):
		selected = False
		for layer in self.layers:
			if zynthian_gui_config.midi_single_active_channel or midich==layer.get_midi_chan():
				if layer.restore_zs3(zs3_index) and not selected:
					try:
						self.select_action(self.root_layers.index(layer))
						selected = True
					except Exception as e:
						logging.error("Can't select layer => {}".format(e))


	def save_midi_chan_zs3(self, midich, zs3_index):
		for layer in self.layers:
			mch=layer.get_midi_chan()
			if mch is None or mch==midich:
				layer.save_zs3(zs3_index)
			elif zynthian_gui_config.midi_single_active_channel:
				layer.delete_zs3(zs3_index)


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
		for layer in self.layers + [self.amixer_layer]:
			layer.midi_control_change(chan, ccnum, ccval)


	#----------------------------------------------------------------------------
	# Audio Routing
	#----------------------------------------------------------------------------


	def get_audio_routing(self):
		res={}
		for i, layer in enumerate(self.layers):
			res[layer.get_jackname()]=layer.get_audio_out()
		return res


	def set_audio_routing(self, audio_routing=None):
		for i, layer in enumerate(self.layers):
			try:
				layer.set_audio_out(audio_routing[layer.get_jackname()])
			except:
				layer.set_audio_out(["system"])


	def reset_audio_routing(self):
		self.set_audio_routing()


	def get_layer_by_jackname(self, jackname):
		for layer in self.layers:
			if layer.jackname==jackname:
				return layer


	def get_jackname_count(self, jackname):
		count = 0
		for layer in self.layers:
			if layer.jackname is not None and layer.jackname.startswith(jackname):
				count += 1
		return count

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
			layer = self.curlayer

		if layer is not None:
			fxchain_layers = []

			if layer.midi_chan is not None:
				for l in self.layers:
					if l not in fxchain_layers and l.midi_chan==layer.midi_chan:
						fxchain_layers.append(l)

			elif layer in self.layers:
					fxchain_layers.append(layer)

			return fxchain_layers

		else:
			return None


	def get_fxchain_root(self, layer):
		if layer.midi_chan is None:
			return layer
		for l in self.layers:
			if l.midi_chan==layer.midi_chan:
				return l


	def get_fxchain_ends(self, layer):
		fxlbjn = {}
		for fxlayer in self.get_fxchain_layers(layer):
			fxlbjn[fxlayer.jackname] = fxlayer

		ends=[]
		layer = self.get_fxchain_root(layer)
		while len(ends)==0:
			try:
				jn = layer.get_audio_out()[0]
				if jn in fxlbjn:
					layer = fxlbjn[jn]
				else:
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


	def add_to_fxchain(self, layer):
		try:
			for end in self.get_fxchain_ends(layer):
				if end!=layer:
					logging.debug("Adding to FX-chain {} => {}".format(end.get_jackname(), layer.get_jackname()))
					layer.set_audio_out(end.get_audio_out())
					end.set_audio_out([layer.get_jackname()])

		except Exception as e:
			logging.error("Error chaining effect ({})".format(e))


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
			logging.error("Error replacing effect ({})".format(e))


	def drop_from_fxchain(self, layer):
		try:
			ups=self.get_fxchain_upstream(layer)
			if len(ups)>0:
				for up in ups:
					logging.debug("Dropping from FX-chain {} => {}".format(up.get_jackname(), layer.get_jackname()))
					up.del_audio_out(layer.get_jackname())
					for ao in layer.get_audio_out():
						up.add_audio_out(ao)

		except Exception as e:
			logging.error("Error unchaining effect ({})".format(e))


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
				'transpose':[],
				'audio_routing': self.get_audio_routing(),
				'extended_config': self.get_extended_config(),
				'midi_profile_state': self.get_midi_profile_state()
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

			#Transpose info
			for i in range(0,16):
				snapshot['transpose'].append(zyncoder.lib_zyncoder.get_midi_filter_transpose(i))

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


	def load_snapshot(self, fpath):
		try:
			with open(fpath,"r") as fh:
				json=fh.read()
				logging.info("Loading snapshot %s => \n%s" % (fpath,json))

		except Exception as e:
			logging.error("Can't load snapshot '%s': %s" % (fpath,e))
			return False

		try:
			snapshot=JSONDecoder().decode(json)

			#Clean all layers, but don't stop unused engines
			self.remove_all_layers(False)

			# Reusing Jalv engine instances raise problems (audio routing & jack names, etc..),
			# so we stop Jalv engines!
			self.zyngui.screens['engine'].stop_unused_jalv_engines()

			#Create new layers, starting engines when needed
			i = 0
			for lss in snapshot['layers']:
				if lss['engine_nick']=="MX":
					if zynthian_gui_config.snapshot_mixer_settings:
						snapshot['amixer_layer'] = lss
					del(snapshot['layers'][i])
				else:
					engine=self.zyngui.screens['engine'].start_engine(lss['engine_nick'])
					self.layers.append(zynthian_layer(engine,lss['midi_chan'], self.zyngui))
				i += 1

			# Finally, stop all unused engines
			self.zyngui.screens['engine'].stop_unused_engines()

			#Autoconnect
			self.zyngui.zynautoconnect_midi(True)
			self.zyngui.zynautoconnect_audio()

			#Restore MIDI profile state
			if 'midi_profile_state' in snapshot:
				self.set_midi_profile_state(snapshot['midi_profile_state'])

			#Set extended config
			if 'extended_config' in snapshot:
				self.set_extended_config(snapshot['extended_config'])

			# Restore layer state, step 1 => Restore Bank & Preset Status
			i = 0
			for lss in snapshot['layers']:
				self.layers[i].restore_snapshot_1(lss)
				i += 1

			# Restore layer state, step 2 => Restore Controllers Status
			i = 0
			for lss in snapshot['layers']:
				self.layers[i].restore_snapshot_2(lss)
				i += 1

			# Restore ALSA Mixer settings
			if self.amixer_layer and 'amixer_layer' in snapshot:
				self.amixer_layer.restore_snapshot_1(snapshot['amixer_layer'])
				self.amixer_layer.restore_snapshot_2(snapshot['amixer_layer'])

			#Fill layer list
			self.fill_list()

			#Set active layer
			self.index = snapshot['index']
			if self.index in self.layers:
				self.curlayer=self.layers[self.index]
				self.zyngui.set_curlayer(self.curlayer)

			#Set Clone
			if 'clone' in snapshot:
				self.set_clone(snapshot['clone'])
			else:
				self.reset_clone()

			#Set Transpose
			if 'transpose' in snapshot:
				self.set_transpose(snapshot['transpose'])
			else:
				self.reset_transpose()

			#Set CC-Map
			#TODO

			#Set Audio Routing
			if 'audio_routing' in snapshot:
				self.set_audio_routing(snapshot['audio_routing'])
			else:
				self.reset_audio_routing()

			#Post action
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
		if self.show_all_layers:
			self.select_path.set("Layers (Detailed)")
		else:
			self.select_path.set("Layers")


#------------------------------------------------------------------------------
