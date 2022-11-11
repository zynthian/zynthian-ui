#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Engine Selector Class
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
import logging
from time import sleep
from collections import OrderedDict

# Zynthian specific modules
from zyngine import *
from zyngine.zynthian_engine_pianoteq import *
from zyngine.zynthian_engine_pianoteq6 import *
from zyngine.zynthian_engine_jalv import *
from zyngine.zynthian_engine_sooperlooper import zynthian_engine_sooperlooper
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian Engine Selection GUI Class
#------------------------------------------------------------------------------

def initializator(cls):
	cls.init_engine_info()
	return cls

@initializator
class zynthian_gui_engine(zynthian_gui_selector):

	single_layer_engines = ["BF", "MD", "PT", "PD", "AE", "CS", "SL"]
	check_channels_engines = ["AE"]

	@classmethod
	def init_engine_info(cls):

		cls.engine_info=OrderedDict([
			["SL", ("SooperLooper", "SooperLooper", "Audio Effect", None, zynthian_engine_sooperlooper, True)],
			["AI", ("AudioInput", "Audio Input", "Audio Effect", None, zynthian_engine_audio_in, False)],
			["MX", ("Mixer", "ALSA Mixer", "MIXER", None, zynthian_engine_alsa_mixer, True)],
			["ZY", ("ZynAddSubFX", "ZynAddSubFX - Synthesizer", "MIDI Synth", None, zynthian_engine_zynaddsubfx, True)],
			["FS", ("FluidSynth", "FluidSynth - SF2 Player", "MIDI Synth", None, zynthian_engine_fluidsynth, True)],
			["SF", ("Sfizz", "Sfizz - SFZ Player", "MIDI Synth", None, zynthian_engine_sfizz, True)],
			["LS", ("LinuxSampler", "LinuxSampler - SFZ/GIG Player", "MIDI Synth", None, zynthian_engine_linuxsampler, True)],
			["BF", ("setBfree", "setBfree - Hammond Emulator", "MIDI Synth", None, zynthian_engine_setbfree, True)],
			["AE", ("Aeolus", "Aeolus - Pipe Organ Emulator", "MIDI Synth", None, zynthian_engine_aeolus, True)],
			["AP", ("AudioPlayer", "Audio File Player", "Special", None, zynthian_engine_audioplayer, True)],
			['PD', ("PureData", "PureData - Visual Programming", "Special", None, zynthian_engine_puredata, True)],
			#['CS', ("CSound", "CSound Audio Language", "Special", None, zynthian_engine_csound, False)],
			['MD', ("MOD-UI", "MOD-UI - Plugin Host", "Special", None, zynthian_engine_modui, True)]
		])

		pt_info = get_pianoteq_binary_info()
		if pt_info:
			if pt_info['api']:
				cls.engine_info['PT'] = ('Pianoteq', pt_info['name'], "MIDI Synth", None, zynthian_engine_pianoteq, True)
			else:
				cls.engine_info['PT'] = ('Pianoteq', pt_info['name'], "MIDI Synth", None, zynthian_engine_pianoteq6, True)
		
		for plugin_name, plugin_info in get_jalv_plugins().items():
			eng = 'JV/{}'.format(plugin_name)
			cls.engine_info[eng] = (plugin_name, plugin_name, plugin_info['TYPE'], plugin_info.get('CLASS', None), zynthian_engine_jalv, plugin_info['ENABLED'])


	def __init__(self):
		self.reset_index = True
		self.selected_eng = None
		self.zyngine_counter = 0
		self.zyngines = OrderedDict()
		self.set_engine_type("MIDI Synth")
		super().__init__('Engine', True)


	def set_engine_type(self, etype, midi_chan=None, selected_eng=None):
		self.engine_type = etype
		self.midi_chan = midi_chan
		if not selected_eng:
			self.reset_index = True
			self.selected_eng = None
		else:
			self.reset_index = False
			self.selected_eng = selected_eng


	def set_synth_mode(self, midi_chan, selected_eng=None):
		self.set_engine_type("MIDI Synth", midi_chan, selected_eng)


	def set_fxchain_mode(self, midi_chan, selected_eng=None):
		self.set_engine_type("Audio Effect", midi_chan, selected_eng)


	def set_midichain_mode(self, midi_chan, selected_eng=None):
		self.set_engine_type("MIDI Tool", midi_chan, selected_eng)


	def filtered_engines_by_cat(self):
		result = OrderedDict()
		for eng, info in self.engine_info.items():
			eng_type = info[2]
			cat = info[3]
			enabled = info[5]
			if enabled and (eng_type==self.engine_type or self.engine_type is None) and (eng not in self.single_layer_engines or eng not in self.zyngines):
				if cat not in result:
					result[cat] = OrderedDict()
				result[cat][eng] = info
		return result


	def fill_list(self):
		self.init_engine_info()
		self.list_data=[]

		# Sort category headings, but headings starting with "Zynthian" are shown first

		seleng_index = -1
		for cat, infos in sorted(self.filtered_engines_by_cat().items(), key = lambda kv:"!" if kv[0] is None else kv[0]):
			# Add category header...
			if cat:
				if self.engine_type=="MIDI Synth":
					self.list_data.append((None,len(self.list_data),"> LV2 {}".format(cat)))
				else:
					self.list_data.append((None,len(self.list_data),"> {}".format(cat)))

			# Add engines on this category...
			for eng, info in infos.items():
				# For some engines, check if needed channels are free ...
				if eng not in self.check_channels_engines or all(chan in self.zyngui.screens['layer'].get_free_midi_chans() for chan in info[4].get_needed_channels()):
					i = len(self.list_data)
					self.list_data.append((eng, i, info[1], info[0]))
					if self.selected_eng and eng==self.selected_eng:
						seleng_index = i

		# Display help if no engines are enabled ...
		if len(self.list_data)==0:
			self.list_data.append((None,len(self.list_data),"Enable LV2-plugins on webconf".format(os.uname().nodename)))

		# Select "selected_engine" ...
		if seleng_index>=0:
			self.index = seleng_index
		# or select the first engine if reset_index flag is True
		elif self.reset_index:
			self.index = 0
			self.reset_index = False

		super().fill_list()


	def fill_listbox(self):
		super().fill_listbox()
		for i, val in enumerate(self.list_data):
			if val[0]==None:
				self.listbox.itemconfig(i, {'bg':zynthian_gui_config.color_panel_hl,'fg':zynthian_gui_config.color_tx_off})


	def select_action(self, i, t='S'):
		if i is not None and self.list_data[i][0]:
			self.zyngui.screens['layer'].add_layer_engine(self.list_data[i][0], self.midi_chan)


	def arrow_right(self):
		if self.midi_chan is not None:
			if self.zyngui.screens['layer'].get_num_root_layers() > 1:
				self.zyngui.screens['layer'].next(True)


	def arrow_left(self):
		if self.midi_chan is not None:
			if self.zyngui.screens['layer'].get_num_root_layers() > 1:
				self.zyngui.screens['layer'].prev(True)


	def switch(self, swi, t='S'):
		if swi == 0:
			if t == 'S':
				self.arrow_right()
				return True


	def start_engine(self, eng, jackname = None):
		if eng not in self.zyngines:
			info = self.engine_info[eng]
			zynthian_engine_class = info[4]
			if eng[0:3] == "JV/":
				eng = "JV/{}".format(self.zyngine_counter)
				self.zyngines[eng] = zynthian_engine_class(info[0], info[2], self.zyngui, False, jackname)
			elif eng in ["SF","AI"]:
				eng = "{}/{}".format(eng, self.zyngine_counter)
				self.zyngines[eng] = zynthian_engine_class(self.zyngui, jackname)
			else:
				self.zyngines[eng] = zynthian_engine_class(self.zyngui)

		self.zyngine_counter += 1
		return self.zyngines[eng]


	def stop_engine(self, eng, wait=0):
		if eng in self.zyngines:
			self.zyngines[eng].stop()
			del self.zyngines[eng]
			if wait>0:
				sleep(wait)


	def stop_unused_engines(self):
		for eng in list(self.zyngines.keys()):
			if len(self.zyngines[eng].layers)==0:
				logging.debug("Stopping Unused Engine '{}' ...".format(eng))
				self.zyngines[eng].stop()
				del self.zyngines[eng]


	def stop_unused_jalv_engines(self):
		for eng in list(self.zyngines.keys()):
			if len(self.zyngines[eng].layers) == 0 and eng[0:3] in ("JV/", "AP/"):
				self.zyngines[eng].stop()
				del self.zyngines[eng]


	def get_zyngine_eng(self, zyngine):
		try:
			eng = list(self.zyngines.keys())[list(self.zyngines.values()).index(zyngine)]
			if eng.startswith("JV/"):
				eng = "JV/{}".format(zyngine.plugin_name)
			return eng
		except Exception as e:
			logging.error("Engine '{}' not found!! => {}".format(zyngine, e))
			return None


	def get_engine_info(self, eng):
		return self.engine_info[eng]


	def set_select_path(self):
		path = self.engine_type
		if self.midi_chan is not None:
			if self.midi_chan < 16:
				path = "{}#{}".format(self.midi_chan+1, path)
			elif self.midi_chan == 256:
				path = "Main Mix#{}".format(path)
		self.select_path.set(path)

#------------------------------------------------------------------------------
