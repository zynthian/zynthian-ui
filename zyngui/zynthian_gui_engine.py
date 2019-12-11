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

def initializator(cls):
	cls.init_engine_info()
	return cls

@initializator
class zynthian_gui_engine(zynthian_gui_selector):

	single_layer_engines = ["BF", "MD", "PT", "PD", "AE", "CS"]
	check_channels_engines = ["AE"]

	@classmethod
	def init_engine_info(cls):

		cls.engine_info=OrderedDict([
			["MX", ("Mixer", "ALSA Mixer", "MIXER", zynthian_engine_mixer)],
			["ZY", ("ZynAddSubFX", "ZynAddSubFX - Synthesizer", "MIDI Synth", zynthian_engine_zynaddsubfx)],
			["FS", ("FluidSynth", "FluidSynth - SF2 Player", "MIDI Synth", zynthian_engine_fluidsynth)],
			["LS", ("LinuxSampler", "LinuxSampler - SFZ/GIG Player", "MIDI Synth", zynthian_engine_linuxsampler)],
			["BF", ("setBfree", "setBfree - Hammond Emulator", "MIDI Synth", zynthian_engine_setbfree)],
			["AE", ("Aeolus", "Aeolus - Pipe Organ Emulator", "MIDI Synth", zynthian_engine_aeolus)]
		])

		if check_pianoteq_binary():
			pianoteq_title="Pianoteq {}.{} {}{}".format(
				PIANOTEQ_VERSION[0],
				PIANOTEQ_VERSION[1],
				PIANOTEQ_PRODUCT,
				" (Demo)" if PIANOTEQ_TRIAL else "")
			cls.engine_info['PT'] = (PIANOTEQ_NAME, pianoteq_title, "MIDI Synth", zynthian_engine_pianoteq)

		for plugin_name, plugin_info in get_jalv_plugins().items():
			cls.engine_info['JV/{}'.format(plugin_name)] = (plugin_name, "{} - Plugin LV2".format(plugin_name), plugin_info['TYPE'], zynthian_engine_jalv)

		cls.engine_info['PD'] = ("PureData", "PureData - Visual Programming", "Special", zynthian_engine_puredata)
		#cls.engine_info['CS'] = ("CSound", "CSound Audio Language", "Special", zynthian_engine_csound)
		cls.engine_info['MD'] = ("MOD-UI", "MOD-UI - Plugin Host", "Special", zynthian_engine_modui)


	def __init__(self):
		self.zyngine_counter = 0
		self.zyngines = OrderedDict()
		self.set_engine_type("MIDI Synth")
		super().__init__('Engine', True)


	def set_engine_type(self, etype):
		self.engine_type = etype
		self.midi_chan = None


	def set_fxchain_mode(self, midi_chan):
		self.engine_type = "Audio Effect"
		self.midi_chan = midi_chan


	def fill_list(self):
		self.init_engine_info()
		self.index=0
		self.list_data=[]
		i=0
		for en, info in self.engine_info.items():
			if ((info[2]==self.engine_type or self.engine_type is None) and
				(en not in self.single_layer_engines or en not in self.zyngines)):

				# For some engines, check if needed channels are free ...
				if (en in self.check_channels_engines and
					not all(chan in self.zyngui.screens['layer'].get_free_midi_chans() for chan in info[3].get_needed_channels())):
						continue

				ei=self.engine_info[en]
				self.list_data.append((en,i,ei[1],ei[0]))
				i=i+1

		super().fill_list()


	def select_action(self, i, t='S'):
		try:
			self.zyngui.screens['layer'].add_layer_engine(self.start_engine(self.list_data[i][0]), self.midi_chan)
		except Exception as e:
			logging.error("Can't add layer %s => %s" % (self.list_data[i][2],e))


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
