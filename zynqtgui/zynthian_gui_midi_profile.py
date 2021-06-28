#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Midi-Profile Selector Class
# 
# Copyright (C) 2015-2017 Fernando Moyano <jofemodo@zynthian.org>
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
from os.path import isfile, isdir, join, basename

# Zynthian specific modules
import zynconf
from . import zynthian_gui_config
from . import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian MIDI Channel Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_midi_profile(zynthian_gui_selector):

	def __init__(self):
		self.midi_profiles_dir=os.environ.get('ZYNTHIAN_CONFIG_DIR',"/zynthian/config") + "/midi-profiles"
		super().__init__('Profile', True)


	def get_profile_fpath(self,f):
		return join(self.midi_profiles_dir,f);


	def fill_list(self):
		self.current_profile=os.environ.get("ZYNTHIAN_SCRIPT_MIDI_PROFILE",self.midi_profiles_dir + "/default.sh")
		self.list_data=[]
		i=0
		for f in sorted(os.listdir(self.midi_profiles_dir)):
			fpath=self.get_profile_fpath(f)
			if isfile(fpath) and f[-3:].lower()=='.sh':
				if fpath==self.current_profile:
					self.index=i
				#title=str.replace(f[:-3], '_', ' ')
				title=f[:-3]
				self.list_data.append((fpath,i,title))
				i+=1
		super().fill_list()

	def show(self):
		super().show()


	def select_action(self, i, t='S'):
		profile_fpath=self.list_data[i][0]
		if profile_fpath==self.current_profile:
			logging.info("MIDI PROFILE '%s' IS THE CURRENT PROFILE", profile_fpath)
		else:
			logging.info("LOADING MIDI PROFILE => %s", profile_fpath)
			zynconf.save_config({ 
				"ZYNTHIAN_SCRIPT_MIDI_PROFILE": self.list_data[i][0]
			})
			self.zyngui.reload_midi_config()
		self.zyngui.show_active_screen()


	def set_select_path(self):
		self.select_path.set("MIDI Profile")

#------------------------------------------------------------------------------
