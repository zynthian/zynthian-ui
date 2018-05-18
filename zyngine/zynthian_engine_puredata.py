# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_puredata)
#
# zynthian_engine implementation for PureData
#
# Copyright (C) 2015-2018 Fernando Moyano <jofemodo@zynthian.org>
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
import re
import logging
import time
import subprocess
import yaml
from collections import OrderedDict
from os.path import isfile,isdir,join
from json import JSONEncoder, JSONDecoder

from . import zynthian_engine
from . import zynthian_controller

#------------------------------------------------------------------------------
# Puredata Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_puredata(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Controllers & Screens
	# ---------------------------------------------------------------------------

	_ctrls=[
		['volume',7,96],
		['ctrl 1',1,0],
		['ctrl 2',2,0],
		['ctrl 3',3,0],
		['ctrl 4',4,0],
		['ctrl 5',5,0],
		['ctrl 6',6,0]
	]

	_ctrl_screens=[
		['main',['volume','ctrl 1','ctrl 2','ctrl 3']],
		['controllers',['volume','ctrl 4','ctrl 5','ctrl 6']]
	]

	#----------------------------------------------------------------------------
	# Initialization
	#----------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__(zyngui)
		self.name="PureData"
		self.nickname="PD"
		self.preset=""
		self.preset_config=None

		self.bank_dirs=[
			('_', os.getcwd()+"/my-data/presets/puredata")
		]

		if self.config_remote_display():
			self.base_command=("/usr/bin/pd", "-jack", "-rt", "-alsamidi", "-mididev", "1")
		else:
			self.base_command=("/usr/bin/pd", "-nogui", "-jack", "-rt", "-alsamidi", "-mididev", "1")

		self.reset()

	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------

	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	#----------------------------------------------------------------------------
	# Bank Managament
	#----------------------------------------------------------------------------

	def get_bank_list(self, layer=None):
		return self.get_dirlist(self.bank_dirs)

	def set_bank(self, layer, bank):
		pass


	#----------------------------------------------------------------------------
	# Preset Managament
	#----------------------------------------------------------------------------

	def get_preset_list(self, bank):
		return self.get_dirlist(bank[0])

	def set_preset(self, layer, preset, preload=False):
		if preset[0] != self.preset:
			self.start_loading()
			self.load_preset_config(preset)
			self.command=self.base_command+(self.get_preset_filepath(preset),)
			self.preset=preset[0]
			self.stop()
			self.start(True,False)
			self.refresh_all()
			self.stop_loading()

	def load_preset_config(self, preset):
		config_fpath = preset[0] + "/zynconfig.yml"
		try:
			with open(config_fpath,"r") as fh:
				yml = fh.read()
				logging.info("Loading preset config file %s => \n%s" % (config_fpath,yml))
				self.preset_config = yaml.load(yml)
				return True
		except Exception as e:
			logging.error("Can't load preset config file '%s': %s" % (config_fpath,e))
			return False

	def get_preset_filepath(self, preset):
		if self.preset_config:
			preset_fpath=self.preset_config['main_file']
			if isfile(preset_fpath):
				return preset_fpath

		preset_fpath = preset[0]+"/main.pd"
		if isfile(preset_fpath):
			return preset_fpath
		
		preset_fpath = preset[0] + "/" + os.path.basename(preset[0]) + ".pd"
		if isfile(preset_fpath):
			return preset_fpath
		
		preset_fpath = join(preset[0],os.listdir(preset[0])[0])
		return preset_fpath


	#----------------------------------------------------------------------------
	# Controllers Managament
	#----------------------------------------------------------------------------

	def get_controllers_dict(self, layer):
		zctrls=OrderedDict()
		self._ctrl_screens=[]
		logging.debug("Generating Controller Config ...")
		try:
			c=1
			ctrl_set=[]
			for name, num in self.preset_config['midi_controllers'].items():
				try:
					title=str.replace(name, '_', ' ')
					logging.debug("CTRL %s: %s" % (num, name))
					zctrls[name]=zynthian_controller(self,name,title,{
						'midi_chan': 1,
						'midi_cc': int(num),
						'value': 0,
						'value_default': 0,
						'value_min': 0,
						'value_max': 127
					})
					ctrl_set.append(name)
					if len(ctrl_set)>=4:
						logging.debug("ADDING CONTROLLER SCREEN #"+str(c))
						self._ctrl_screens.append(['Controllers#'+str(c),ctrl_set])
						ctrl_set=[]
						c=c+1
				except Exception as err:
					logging.error("Generating Controller Screens: %s" % err)
			if len(ctrl_set)>=1:
				logging.debug("ADDING CONTROLLER SCREEN #"+str(c))
				self._ctrl_screens.append(['Controllers#'+str(c),ctrl_set])
		except Exception as err:
			logging.error("Generating Controller List: %s" % err)
		return zctrls

	#--------------------------------------------------------------------------
	# Special
	#--------------------------------------------------------------------------


#******************************************************************************
