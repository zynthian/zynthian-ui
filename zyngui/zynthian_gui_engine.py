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
import sys
import logging
import re
import subprocess
from time import sleep
from collections import OrderedDict

# Zynthian specific modules
import zynautoconnect
from zyngine import *
from zyngine.zynthian_engine_pianoteq import *
from zyngine.zynthian_engine_jalv import *
from . import zynthian_gui_config
from . import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian Engine Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_engine(zynthian_gui_selector):

	single_layer_engines = ["BF", "MD", "PT", "PD", "AE", "CS"]
	check_channels_engines = ["AE"]

	def init_engine_info(self):

		self.engine_info=OrderedDict([
			["MX", ("Mixer", "ALSA Mixer", "MIXER", zynthian_engine_mixer, True)],
			["ZY", ("ZynAddSubFX", "ZynAddSubFX - Synthesizer", "MIDI Synth", zynthian_engine_zynaddsubfx, True)],
			["FS", ("FluidSynth", "FluidSynth - SF2 Player", "MIDI Synth", zynthian_engine_fluidsynth, True)],
			["LS", ("LinuxSampler", "LinuxSampler - SFZ/GIG Player", "MIDI Synth", zynthian_engine_linuxsampler, True)],
			["BF", ("setBfree", "setBfree - Hammond Emulator", "MIDI Synth", zynthian_engine_setbfree, True)],
			["AE", ("Aeolus", "Aeolus - Pipe Organ Emulator", "MIDI Synth", zynthian_engine_aeolus, True)],
			['PD', ("PureData", "PureData - Visual Programming", "Special", zynthian_engine_puredata, True)],
			['CS', ("CSound", "CSound Audio Language", "Special", zynthian_engine_csound, False)],
			['MD', ("MOD-UI", "MOD-UI - Plugin Host", "Special", zynthian_engine_modui, True)]
		])

		if check_pianoteq_binary():
			pianoteq_title="Pianoteq {}.{} {}{}".format(
				PIANOTEQ_VERSION[0],
				PIANOTEQ_VERSION[1],
				PIANOTEQ_PRODUCT,
				" (Demo)" if PIANOTEQ_TRIAL else "")
			self.engine_info['PT'] = (PIANOTEQ_NAME, pianoteq_title, "MIDI Synth", zynthian_engine_pianoteq, True)

		builtin = {}
		for en, info in self.engine_info.items():
			if (info[4] and (info[2]==self.engine_type or self.engine_type is None) and
			    (en not in self.single_layer_engines or en not in self.zyngines)):
				builtin[en] = info
				
		self.engine_info_categorized = {}
		if len(builtin) > 0:
			self.engine_info_categorized["Zynthian Built-in"] = builtin
		
		for plugin_name, plugin_info in get_jalv_plugins().items():
			en = 'JV/{}'.format(plugin_name)
			info = (plugin_name, plugin_name, plugin_info['TYPE'], zynthian_engine_jalv, plugin_info['ENABLED'])
			if (info[4] and (info[2]==self.engine_type or self.engine_type is None) and
			    (en not in self.single_layer_engines or en not in self.zyngines)):
				pluginClass = plugin_info.get('CLASS','')
				self.engine_info[en] = info
				category = self.engine_info_categorized.setdefault("LV2 {}".format(pluginClass), {})
				category[en] = info

	def __init__(self):
		self.zyngine_counter = 0
		self.zyngines = OrderedDict()
		self.set_engine_type("MIDI Synth")
		super().__init__('Engine', True)


	def set_engine_type(self, etype):
		self.engine_type = etype
		self.midi_chan = None
		self.init_engine_info()

	def set_fxchain_mode(self, midi_chan):
		self.engine_type = "Audio Effect"
		self.midi_chan = midi_chan
		self.init_engine_info()

	def set_midichain_mode(self, midi_chan):
		self.engine_type = "MIDI Tool"
		self.midi_chan = midi_chan
		self.init_engine_info()

	def fill_list_item(self, en, info):
		# For some engines, check if needed channels are free ...
		if (en in self.check_channels_engines and
			not all(chan in self.zyngui.screens['layer'].get_free_midi_chans() for chan in info[3].get_needed_channels())):
			return

		ei=self.engine_info[en]
		self.list_data.append((en,len(self.list_data),ei[1],ei[0]))

	def fill_list(self):
		self.init_engine_info()
		self.list_data=[]

		# Sort category headings, but headings starting with "Zynthian" are shown first
		for cat, infos in sorted(self.engine_info_categorized.items(), key = lambda kv:
			                 "! {}".format(kv[0]) if kv[0].startswith("Zynthian") else kv[0]):
			self.list_data.append((None,len(self.list_data),"  {}".format(cat)))
			# Sort the list of plugins, unless it's the built-in list (which has a fixed order)
			if cat.startswith("Zynthian"):
				items = infos.items()
			else:
				items = sorted(infos.items(), key = lambda kv: kv[0])
			for en, info in items:
				self.fill_list_item(en, info)

		if (len(self.list_data) == 0):
			self.list_data.append((None,len(self.list_data),"Please use webconf to enable plugins."))

		# Select the first element that is not a category heading
		self.index=0
		for idx, val in enumerate(self.list_data):
			if val[0] != None:
				self.index = idx
				break
		
		super().fill_list()

	def fill_listbox(self):
		super().fill_listbox()
		# TODO Give the category headers a nice color
		for idx, val in enumerate(self.list_data):
			if (val[0] == None):
				self.listbox.itemconfig(idx, {'fg':zynthian_gui_config.color_tx_off,'bg':zynthian_gui_config.color_bg})

	def select_action(self, i, t='S'):
		self.zyngui.screens['layer'].add_layer_engine(self.start_engine(self.list_data[i][0]), self.midi_chan)


	def start_engine(self, eng):
		if eng not in self.zyngines:
			info=self.engine_info[eng]
			zynthian_engine_class=info[3]
			if eng[0:3]=="JV/":
				eng="JV/{}".format(self.zyngine_counter)
				self.zyngines[eng]=zynthian_engine_class(info[0], info[2], self.zyngui)
			else:
				self.zyngines[eng]=zynthian_engine_class(self.zyngui)

		self.zyngine_counter+=1
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
			if len(self.zyngines[eng].layers)==0 and eng[0:3]=="JV/":
				self.zyngines[eng].stop()
				del self.zyngines[eng]


	def get_engine_info(self, eng):
		return self.engine_info[eng]


	def set_select_path(self):
		self.select_path.set("Engine")

#------------------------------------------------------------------------------
