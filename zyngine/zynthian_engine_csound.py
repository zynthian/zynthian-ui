# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_csound)
#
# zynthian_engine implementation for CSound
#
# Copyright (C) 2015-2019 Fernando Moyano <jofemodo@zynthian.org>
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
import subprocess
import oyaml as yaml
from time import sleep
from collections import OrderedDict
from os.path import isfile,isdir,join

from . import zynthian_engine
from . import zynthian_controller

#------------------------------------------------------------------------------
# CSound Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_csound(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Controllers & Screens
	# ---------------------------------------------------------------------------

	_ctrls=[
		['volume',7,96],
		['modulation',1,0],
		['ctrl 2',2,0],
		['ctrl 3',3,0]
	]

	_ctrl_screens=[
		['main',['volume','modulation','ctrl 2','ctrl 3']]
	]

	#----------------------------------------------------------------------------
	# Initialization
	#----------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__(zyngui)

		self.type = "Special"
		self.name = "CSound"
		self.nickname = "CS"
		self.jackname = "csound6"

		#self.options['midi_chan']=False

		self.preset = ""
		self.preset_config = None

		self.bank_dirs = [
			('_', self.my_data_dir + "/presets/csound")
		]


		if self.config_remote_display():
			self.nogui = False
			self.base_command="/usr/bin/csound -+rtaudio=jack -+rtmidi=alsaseq -M14 -o dac"
		else:
			self.nogui = True
			self.base_command="/usr/bin/csound --nodisplays -+rtaudio=jack -+rtmidi=alsaseq -M14 -o dac"

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
		return True

	#----------------------------------------------------------------------------
	# Preset Managament
	#----------------------------------------------------------------------------


	def get_preset_list(self, bank):
		return self.get_dirlist(bank[0])


	def set_preset(self, layer, preset, preload=False):
		self.load_preset_config(preset[0])
		self.command=self.base_command+ " " + self.get_fixed_preset_filepath(preset[0])
		self.preset=preset[0]
		self.stop()
		self.start()
		self.refresh_all()
		sleep(0.3)
		self.zyngui.zynautoconnect(True)
		layer.send_ctrl_midi_cc()
		return True


	def load_preset_config(self, preset_dir):
		config_fpath = preset_dir + "/zynconfig.yml"
		try:
			with open(config_fpath,"r") as fh:
				yml = fh.read()
				logging.info("Loading preset config file %s => \n%s" % (config_fpath,yml))
				self.preset_config = yaml.load(yml, Loader=yaml.SafeLoader)
				return True
		except Exception as e:
			logging.error("Can't load preset config file '%s': %s" % (config_fpath,e))
			return False


	def get_preset_filepath(self, preset_dir):
		if self.preset_config:
			preset_fpath = preset_dir + "/" + self.preset_config['main_file']
			if isfile(preset_fpath):
				return preset_fpath

		preset_fpath = preset_dir + "/main.csd"
		if isfile(preset_fpath):
			return preset_fpath
		
		preset_fpath = preset_dir + "/" + os.path.basename(preset_dir) + ".csd"
		if isfile(preset_fpath):
			return preset_fpath
		
		preset_fpath = join(preset_dir,os.listdir(preset_dir)[0])
		
		return preset_fpath


	def get_fixed_preset_filepath(self, preset_dir):
		
		preset_fpath=self.get_preset_filepath(preset_dir)
		
		if self.nogui:
			# Generate on-the-fly CSD file, disabling GUI
			with open(preset_fpath, 'r') as f:
				data=f.read()
				data = data.replace('FLrun', ";FLrun")
				fixed_preset_fpath = preset_fpath.replace(".csd", ".nogui.csd")

				with open(fixed_preset_fpath, 'w') as ff:
					ff.write(data)

				return fixed_preset_fpath

		return preset_fpath


	def cmp_presets(self, preset1, preset2):
		return True


	#----------------------------------------------------------------------------
	# Controllers Managament
	#----------------------------------------------------------------------------

	def get_controllers_dict(self, layer):
		try:
			ctrl_items=self.preset_config['midi_controllers'].items()
		except:
			return super().get_controllers_dict(layer)
		c=1
		ctrl_set=[]
		zctrls=OrderedDict()
		self._ctrl_screens=[]
		logging.debug("Generating Controller Config ...")
		try:
			for name, options in ctrl_items:
				try:
					if isinstance(options,int):
						options={ 'midi_cc': options }
					if 'midi_chan' not in options:
						options['midi_chan']=layer.midi_chan
					midi_cc=options['midi_cc']
					logging.debug("CTRL %s: %s" % (midi_cc, name))
					title=str.replace(name, '_', ' ')
					zctrls[name]=zynthian_controller(self,name,title,options)
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
