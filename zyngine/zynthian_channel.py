# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Channel (zynthian_channel)
# 
# zynthian channel
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

import logging
from collections import OrderedDict

class zynthian_channel:
	zyngui=None
	engine=None

	midi_chan=None

	patch_list=[]
	patch_index=None
	patch_name=None
	patch_info=None

	bank_list=[]
	bank_index=None
	bank_name=None
	bank_info=None

	preset_list=[]
	preset_index=None
	preset_name=None
	preset_info=None

	zctrl_list=None
	zctrl_screens=None

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------

	def __init__(self, engine, midi_chan, zyngui=None):
		self.zyngui=zyngui
		self.engine=engine
		self.midi_chan=midi_chan
		self.init_controllers()
		self.init_controller_screens()

	# ---------------------------------------------------------------------------
	# Patch Management
	# ---------------------------------------------------------------------------

	#TODO!

	# ---------------------------------------------------------------------------
	# Bank Management
	# ---------------------------------------------------------------------------

	def reset_bank(self):
		bank_i=None
		bank_name=None
		bank_info=None

	def set_bank(self, i, set_engine=True):
		if i in self.bank_list:
			last_bank_index=self.bank_index
			last_bank_name=self.bank_name
			self.bank_index=i
			self.bank_name=self.bank_list[i][2]
			self.bank_info=copy.deepcopy(self.bank_list[i])
			logging.info("Bank Selected: %s (%d)" % (self.bank_name,i))
			if set_engine:
				self.engine.set_bank(self.midi_chan, self.bank_info)
			if last_bank_index!=i or not last_bank_name:
				self.reset_preset()

	# ---------------------------------------------------------------------------
	# Presest Management
	# ---------------------------------------------------------------------------

	def reset_preset(self):
		preset_i=None
		preset_name=None
		preset_info=None

	def set_preset(self, i, set_engine=True):
		if i in self.preset_list:
			last_preset_index=self.preset_index
			last_preset_name=self.preset_name
			self.preset_index=i
			self.preset_name=self.preset_list[i][2]
			self.preset_info=copy.deepcopy(self.preset_list[i])
			logging.info("Instrument Selected: %s (%d)" % (self.preset_name,i))
			#=> '+self.preset_list[i][3]
			if set_engine:
				self.engine.set_engine(self.midi_chan, self.preset_info)
			if last_preset_index!=i or not last_preset_name:
				self.load_ctrl_config()

	# ---------------------------------------------------------------------------
	# Controllers Management
	# ---------------------------------------------------------------------------

	def init_controllers(self):
		self.init_midi_controllers()

	# Create zynthian controllers list from midi controllers list
	def init_midi_controllers(self):
		self.zctrl_list=OrderedDict()
		for ctrl in self.midi_ctrls:
			zctrl=zynthian_controller(ctrl[0])
			if 3 not in ctrl:
				ctrl3=127
			else
				ctrl3=ctrl[3]
			zctrl.set_midi_controller(self.midi_chan,ctrl[1],ctrl[2],ctrl[3])
			self.zctrl_list[ctrl[0]]=zctrl
		
	# Create controller screens from zynthian controller keys
	def init_controller_screens(self):
		self.zctrl_screens=OrderedDict()
		for cscr in self.ctrl_screens_keys:
			self.add_controller_screen_from_keys(cscr)

	def add_controller_screen(self, name, zctrls):
		self.zctrl_screens[name]=zctrls

	def add_controller_screen_from keys(self, name, zctrl_keys):
		# Build array of zynthian_controllers from keys
		zctrls=[]
		for k in zctrl_keys:
			try:
				zctrls.append(self.zctrl_list[k])
			except:
				logging.error("Controller %s is not defined" % k)
		self.zctrl_screens[name]=zctrls

	# ---------------------------------------------------------------------------
	# SnapShot Management
	# ---------------------------------------------------------------------------

	def set_all_banks(self):
		for ch in range(16):
			if self.bank_set[ch]:
				self.set_bank(self.bank_set[ch],ch)

	def set_all_presets(self):
		#logging.debug("set_all_preset()")
		for ch in range(16):
			if self.preset_set[ch]:
				self.set_preset(self.preset_set[ch],ch)

	def save_snapshot(self, fpath):
		status={
			'engine': self.name,
			'engine_nick': self.nickname,
			'midi_chan': self.midi_chan,
			'max_chan': self.max_chan,
			'bank_index': self.bank_index,
			'bank_name': self.bank_name,
			'bank_set': self.bank_set,
			'preset_index': self.preset_index,
			'preset_name': self.preset_name,
			'preset_set': self.preset_set,
			'ctrl_config': self.ctrl_config
		}
		try:
			json=JSONEncoder().encode(status)
			logging.info("Saving snapshot %s => \n%s" % (fpath,json))
		except:
			logging.error("Can't generate snapshot")
			return False

		try:
			with open(fpath,"w") as fh:
				fh.write(json)
		except:
			logging.error("Can't save snapshot '%s'" % fpath)
			return False
		self.snapshot_fpath=fpath
		return True

	def _load_snapshot(self, fpath):
		self.loading_snapshot=True
		try:
			with open(fpath,"r") as fh:
				json=fh.read()
				logging.info("Loading snapshot %s => \n%s" % (fpath,json))
		except:
			logging.error("Can't load snapshot '%s'" % fpath)
			return False
		try:
			status=JSONDecoder().decode(json)
			if self.name!=status['engine'] or self.nickname!=status['engine_nick']:
				raise UserWarning("Incorrect Engine " + status['engine'])
			self.midi_chan=status['midi_chan']
			self.max_chan=status['max_chan']
			self.bank_index=status['bank_index']
			self.bank_name=status['bank_name']
			self.bank_set=status['bank_set']
			self.preset_index=status['preset_index']
			self.preset_name=status['preset_name']
			self.preset_set=status['preset_set']
			self.ctrl_config=status['ctrl_config']
			self.snapshot_fpath=fpath
		except UserWarning as e:
			logging.error("%s" % e)
			return False
		except Exception as e:
			logging.error("Invalid snapshot format. %s" % e)
			return False

	def load_snapshot(self, fpath):
		self._load_snapshot(fpath)
		return self.load_snapshot_post()

	def load_snapshot_post(self):
		try:
			self.set_all_bank()
			self.load_bank_list()
			self.set_all_preset()
			self.load_preset_list()
			sleep(0.2)
			self.set_all_ctrl()
			self.zyngui.refresh_screen()
			self.loading_snapshot=False
			return True
		except Exception as e:
			logging.error("%s" % e)
			return False

	# ---------------------------------------------------------------------------
	# Channel "Path" String
	# ---------------------------------------------------------------------------

	def get_path(self):
		path=self.bank_name
		if self.preset_name:
			path=path + '/' + self.preset_name
		return path

	def get_fullpath(self):
		return self.engine.nickname + "#" + str(self.midi_chan) + " > " + self.get_path()
