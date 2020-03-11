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
import shutil
import logging
import subprocess
import oyaml as yaml
from time import sleep
from collections import OrderedDict
from os.path import isfile,isdir,join

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
		['modulation',1,0],
		['ctrl 2',2,0],
		['ctrl 3',3,0]
	]

	_ctrl_screens=[
		['main',['volume','modulation','ctrl 2','ctrl 3']]
	]

	#----------------------------------------------------------------------------
	# Config variables
	#----------------------------------------------------------------------------

	startup_patch = zynthian_engine.data_dir + "/presets/puredata/zynthian_startup.pd"

	bank_dirs = [
		('EX', zynthian_engine.ex_data_dir + "/presets/puredata"),
		('MY', zynthian_engine.my_data_dir + "/presets/puredata"),
		('_', zynthian_engine.data_dir + "/presets/puredata")
	]

	#----------------------------------------------------------------------------
	# Initialization
	#----------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__(zyngui)

		self.type = "Special"
		self.name = "PureData"
		self.nickname = "PD"
		#self.jackname = "pure_data_0"
		self.jackname = "pure_data"

		#self.options['midi_chan']=False

		self.preset = ""
		self.preset_config = None

		if self.config_remote_display():
			self.base_command="/usr/bin/pd -jack -jackname \"{}\" -rt -alsamidi -mididev 1 -open \"{}\"".format(self.jackname, self.startup_patch)
		else:
			self.base_command="/usr/bin/pd -nogui -jack  -jackname \"{}\" -rt -alsamidi -mididev 1 -open \"{}\"".format(self.jackname, self.startup_patch)

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
		self.load_preset_config(preset)
		self.command=self.base_command+ " " + self.get_preset_filepath(preset)
		self.preset=preset[0]
		self.stop()
		self.start()
		self.refresh_all()
		sleep(0.3)
		self.zyngui.zynautoconnect()
		layer.send_ctrl_midi_cc()
		return True


	def load_preset_config(self, preset):
		config_fpath = preset[0] + "/zynconfig.yml"
		try:
			with open(config_fpath,"r") as fh:
				yml = fh.read()
				logging.info("Loading preset config file %s => \n%s" % (config_fpath,yml))
				self.preset_config = yaml.load(yml, Loader=yaml.SafeLoader)
				return True
		except Exception as e:
			logging.error("Can't load preset config file '%s': %s" % (config_fpath,e))
			return False


	def get_preset_filepath(self, preset):
		if self.preset_config:
			preset_fpath = preset[0] + "/" + self.preset_config['main_file']
			if isfile(preset_fpath):
				return preset_fpath

		preset_fpath = preset[0] + "/main.pd"
		if isfile(preset_fpath):
			return preset_fpath
		
		preset_fpath = preset[0] + "/" + os.path.basename(preset[0]) + ".pd"
		if isfile(preset_fpath):
			return preset_fpath
		
		preset_fpath = join(preset[0],os.listdir(preset[0])[0])
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

	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

	@classmethod
	def zynapi_get_banks(cls):
		banks=[]
		for b in cls.get_dirlist(cls.bank_dirs, False):
			banks.append({
				'text': b[2],
				'name': b[4],
				'fullpath': b[0],
				'raw': b,
				'readonly': False
			})
		return banks


	@classmethod
	def zynapi_get_presets(cls, bank):
		presets=[]
		for p in cls.get_dirlist(bank['fullpath']):
			presets.append({
				'text': p[4],
				'name': p[2],
				'fullpath': p[0],
				'raw': p,
				'readonly': False
			})
		return presets


	@classmethod
	def zynapi_new_bank(cls, bank_name):
		os.mkdir(zynthian_engine.my_data_dir + "/presets/puredata/" + bank_name)


	@classmethod
	def zynapi_rename_bank(cls, bank_path, new_bank_name):
		head, tail = os.path.split(bank_path)
		new_bank_path = head + "/" + new_bank_name
		os.rename(bank_path, new_bank_path)


	@classmethod
	def zynapi_remove_bank(cls, bank_path):
		shutil.rmtree(bank_path)


	@classmethod
	def zynapi_rename_preset(cls, preset_path, new_preset_name):
		head, tail = os.path.split(preset_path)
		new_preset_path = head + "/" + new_preset_name
		os.rename(preset_path, new_preset_path)


	@classmethod
	def zynapi_remove_preset(cls, preset_path):
		shutil.rmtree(preset_path)


	@classmethod
	def zynapi_download(cls, fullpath):
		return fullpath


	@classmethod
	def zynapi_install(cls, dpath, bank_path):
		if os.path.isdir(dpath):
			shutil.move(dpath, bank_path)
			#TODO Test if it's a PD bundle
		else:
			fname, ext = os.path.splitext(dpath)
			if ext=='.pd':
				bank_path += "/" + fname
				os.mkdir(bank_path)
				shutil.move(dpath, bank_path)
			else:
				raise Exception("File doesn't look like a PD patch!")


	@classmethod
	def zynapi_get_formats(cls):
		return "pd,zip,tgz,tar.gz,tar.bz2"


#******************************************************************************
