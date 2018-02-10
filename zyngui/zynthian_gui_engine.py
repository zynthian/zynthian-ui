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

import sys
import logging
from time import sleep
from collections import OrderedDict

# Zynthian specific modules
import zynautoconnect
import os
from zyngine import *
from . import zynthian_gui_config
from . import zynthian_gui_selector

#------------------------------------------------------------------------------
# Configure logging
#------------------------------------------------------------------------------

# Set root logging level
logging.basicConfig(stream=sys.stderr, level=zynthian_gui_config.log_level)

#------------------------------------------------------------------------------
# Zynthian Engine Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_engine(zynthian_gui_selector):
	engine_info=OrderedDict([
		["ZY", ("ZynAddSubFX","ZynAddSubFX - Synthesizer")],
		["FS", ("FluidSynth","FluidSynth - Sampler")],
		["LS", ("LinuxSampler","LinuxSampler - Sampler")],
		["BF", ("setBfree","setBfree - Hammond Emulator")],
		["MD", ("MOD-UI","MOD-UI - Plugin Host")]
	])
	if(os.path.isfile("/zynthian/zynthian-sw/pianoteq/Pianoteq 6 STAGE") and os.access("/zynthian/zynthian-sw/pianoteq/Pianoteq 6 STAGE", os.X_OK)):
		engine_info['PT']=("Pianoteq6","Pianoteq6-Stage-Demo")

	def __init__(self):
		self.zyngines={}
		super().__init__('Engine', True)
    
	def fill_list(self):
		self.index=0
		self.list_data=[]
		i=0
		for en in self.engine_info:
			if en not in ["BF", "MD", "PT"] or en not in self.zyngines:
				ei=self.engine_info[en]
				self.list_data.append((en,i,ei[1],ei[0]))
				i=i+1
		super().fill_list()

	def select_action(self, i):
		try:
			zynthian_gui_config.zyngui.screens['layer'].add_layer_engine(self.start_engine(self.list_data[i][0]))
		except Exception as e:
			logging.error("Can't add layer %s => %s" % (self.list_data[i][2],e))

	def start_engine(self, eng, wait=0):
		if eng not in self.zyngines:
			if eng=="ZY":
				self.zyngines[eng]=zynthian_engine_zynaddsubfx(zynthian_gui_config.zyngui)
			elif eng=="LS":
				self.zyngines[eng]=zynthian_engine_linuxsampler(zynthian_gui_config.zyngui)
			elif eng=="FS":
				self.zyngines[eng]=zynthian_engine_fluidsynth(zynthian_gui_config.zyngui)
			elif eng=="BF":
				self.zyngines[eng]=zynthian_engine_setbfree(zynthian_gui_config.zyngui)
			elif eng=="MD":
				self.zyngines[eng]=zynthian_engine_modui(zynthian_gui_config.zyngui)
			elif eng=="PT":
				self.zyngines[eng]=zynthian_engine_pianoteq(zynthian_gui_config.zyngui)
			else:
				return None
			if wait>0:
				sleep(wait)
			zynautoconnect.autoconnect()
		else:
			pass
			#TODO => Check Engine Name and Status
		return self.zyngines[eng]

	def stop_engine(self, eng, wait=0):
		if eng in self.zyngines:
			self.zyngines[eng].stop()
			del self.zyngines[eng]
			if wait>0:
				sleep(wait)

	def clean_unused_engines(self):
		for eng in list(self.zyngines.keys()):
			if len(self.zyngines[eng].layers)==0:
				zynautoconnect.unset_monitored_engine(self.zyngines[eng].name)
				self.zyngines[eng].stop()
				self.zyngines.pop(eng, None)

	def get_engine_info(self, eng):
		return self.engine_info[eng]

	def set_select_path(self):
		self.select_path.set("Engine")

#------------------------------------------------------------------------------
