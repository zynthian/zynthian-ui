# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Layer (zynthian_layer)
# 
# zynthian layer
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
import copy
from time import sleep
from collections import OrderedDict

class zynthian_layer:

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------

	def __init__(self, engine, midi_chan, zyngui=None):
		self.zyngui=zyngui
		self.engine=engine
		self.midi_chan=midi_chan

		self.bank_list=[]
		self.bank_index=0
		self.bank_name=None
		self.bank_info=None

		self.preset_list=[]
		self.preset_index=0
		self.preset_name=None
		self.preset_info=None
		self.preset_bank_index=None

		self.preload_index=None
		self.preload_name=None
		self.preload_info=None

		self.controllers_dict=None
		self.ctrl_screens_dict=None
		self.ctrl_screen_active=None

		self.refresh_flag=False

		self.engine.add_layer(self)
		self.refresh_controllers()
	
	def refresh(self):
		if self.refresh_flag:
			self.refresh_flag=False
			self.refresh_controllers()
			#TODO: Improve this Dirty Hack!!
			if self.engine.nickname=='MD':
				self.zyngui.screens['preset'].fill_list()
			self.zyngui.refresh_screen()

	def reset(self):
		self.refresh_flag=False
		self.engine.del_layer(self)

	# ---------------------------------------------------------------------------
	# MIDI chan Management
	# ---------------------------------------------------------------------------

	def set_midi_chan(self, midi_chan):
		self.midi_chan=midi_chan
		self.engine.set_midi_chan(self)
		for zctrl in self.controllers_dict.values():
			zctrl.set_midi_chan(midi_chan)

	def get_midi_chan(self):
		return self.midi_chan

	# ---------------------------------------------------------------------------
	# Bank Management
	# ---------------------------------------------------------------------------

	def load_bank_list(self):
		self.bank_list=self.engine.get_bank_list(self)
		logging.debug("BANK LIST => \n%s" % str(self.bank_list))

	def reset_bank(self):
		bank_i=None
		bank_name=None
		bank_info=None

	def set_bank(self, i, set_engine=True):
		if i < len(self.bank_list):
			last_bank_index=self.bank_index
			last_bank_name=self.bank_name
			self.bank_index=i
			self.bank_name=self.bank_list[i][2]
			self.bank_info=copy.deepcopy(self.bank_list[i])
			logging.info("Bank Selected: %s (%d)" % (self.bank_name,i))
			if set_engine:
				self.engine.set_bank(self, self.bank_info)
			#if last_bank_index!=i or not last_bank_name:
			#	self.reset_preset()
			return True
		return False

	#TODO Optimize search!!
	def set_bank_by_name(self, name, set_engine=True):
		for i in range(len(self.bank_list)):
			if name==self.bank_list[i][2]:
				self.set_bank(i,set_engine)
				return True
		return False

	def get_bank_name(self):
		return self.preset_name

	def get_bank_index(self):
		return self.bank_index

	# ---------------------------------------------------------------------------
	# Presest Management
	# ---------------------------------------------------------------------------

	def load_preset_list(self):
		if self.bank_info:
			self.preset_list=self.engine.get_preset_list(self.bank_info)
			logging.debug("PRESET LIST => \n%s" % str(self.preset_list))

	def reset_preset(self):
		self.preset_i=None
		self.preset_name=None
		self.preset_info=None

	def set_preset(self, i, set_engine=True):
		if i < len(self.preset_list):
			last_preset_index=self.preset_index
			last_preset_name=self.preset_name
			self.preset_index=i
			self.preset_name=self.preset_list[i][2]
			self.preset_info=copy.deepcopy(self.preset_list[i])
			self.preset_bank_index=self.bank_index
			self.preload_index=i
			self.preload_name=self.preset_name
			self.preload_info=self.preset_info
			logging.info("Preset Selected: %s (%d)" % (self.preset_name,i))
			#=> '+self.preset_list[i][3]
			if set_engine:
				self.engine.set_preset(self, self.preset_info)
			if last_preset_index!=i or not last_preset_name:
				#TODO => Review this!!
				#self.load_ctrl_config()
				pass
			return True
		return False

	#TODO Optimize search!!
	def set_preset_by_name(self, name, set_engine=True):
		for i in range(len(self.preset_list)):
			if name==self.preset_list[i][2]:
				self.set_preset(i,set_engine)
				return True
		return False

	def preload_preset(self, i):
		if i < len(self.preset_list) and (self.preload_info==None or not self.engine.cmp_presets(self.preload_info,self.preset_list[i])):
			self.preload_index=i
			self.preload_name=self.preset_list[i][2]
			self.preload_info=copy.deepcopy(self.preset_list[i])
			logging.info("Preset Preloaded: %s (%d)" % (self.preload_name,i))
			self.engine.set_preset(self, self.preload_info,True)
			return True
		return False

	def restore_preset(self):
		if self.preset_index is not None and not self.engine.cmp_presets(self.preload_info,self.preset_info):
			if self.bank_index!=self.preset_bank_index:
				self.set_bank(self.preset_bank_index,False)
			self.preload_index=self.preset_index
			self.preload_name=self.preset_name
			self.preload_info=self.preset_info
			logging.info("Restore Preset: %s (%d)" % (self.preset_name,self.preset_index))
			self.engine.set_preset(self, self.preset_info)
			return True
		return False

	def get_preset_name(self):
		return self.preset_name

	def get_preset_index(self):
		return self.preset_index

	# ---------------------------------------------------------------------------
	# Controllers Management
	# ---------------------------------------------------------------------------

	def refresh_controllers(self):
		self.init_controllers()
		self.init_ctrl_screens()

	def init_controllers(self):
		self.controllers_dict=self.engine.get_controllers_dict(self)

	# Create controller screens from zynthian controller keys
	def init_ctrl_screens(self):
		self.ctrl_screens_dict=OrderedDict()
		for cscr in self.engine._ctrl_screens:
			self.ctrl_screens_dict[cscr[0]]=self.build_ctrl_screen(cscr[1])
		#Set active the first screen
		try:
			self.ctrl_screen_active=next(iter(self.ctrl_screens_dict))
		except:
			self.ctrl_screen_active=None

	def get_ctrl_screens(self):
		return self.ctrl_screens_dict

	def get_active_screen(self):
		try:
			return self.ctrl_screens_dict[self.ctrl_screen_active]
		except:
			return None

	def get_active_screen_index(self):
		try:
			return list(self.ctrl_screens_dict.keys()).index(self.ctrl_screen_active)
		except:
			return -1

	def set_active_screen(self, key):
		if key in self.ctrl_screens_dict:
			self.ctrl_screen_active=key
		else:
			logging.warning("Screen Key is not valid")

	def set_active_screen_index(self, i):
		if i>=0 and i < len(self.ctrl_screens_dict):
			self.ctrl_screen_active=list(self.ctrl_screens_dict.items())[i][0]
		else:
			logging.warning("Screen Index is not valid")

	# Build array of zynthian_controllers from list of keys
	def build_ctrl_screen(self, ctrl_keys):
		zctrls=[]
		for k in ctrl_keys:
			try:
				zctrls.append(self.controllers_dict[k])
			except:
				logging.error("Controller %s is not defined" % k)
		return zctrls

	def midi_learn(self, zctrl):
		zctrl.midi_learn()

	def midi_unlearn(self, zctrl):
		zctrl.midi_unlearn()

	# ---------------------------------------------------------------------------
	# Snapshot Management
	# ---------------------------------------------------------------------------

	def get_snapshot(self):
		snapshot={
			'engine_name': self.engine.name,
			'engine_nick': self.engine.nickname,
			'midi_chan': self.midi_chan,
			'bank_index': self.bank_index,
			'bank_name': self.bank_name,
			'bank_info': self.bank_info,
			'preset_index': self.preset_index,
			'preset_name': self.preset_name,
			'preset_info': self.preset_info,
			'controllers_dict': {},
			'ctrl_screen_active': self.ctrl_screen_active
		}
		for k in self.controllers_dict:
			snapshot['controllers_dict'][k]=self.controllers_dict[k].value
		return snapshot

	def restore_snapshot(self, snapshot):
		#Constructor, including engine and midi_chan info is called before
		#self.set_midi_chan(snapshot['midi_chan'])
		self.load_bank_list()
		self.set_bank_by_name(snapshot['bank_name'])
		#Wait for bank loading, zcontrols generation
		self.load_preset_list()
		self.set_preset_by_name(snapshot['preset_name'])
		#Wait for preset loading
		if self.refresh_flag:
			self.refresh_flag=False
			self.refresh_controllers()
		else:
			sleep(0.5)
		self.ctrl_screen_active=snapshot['ctrl_screen_active']
		for k in snapshot['controllers_dict']:
			self.controllers_dict[k].set_value(snapshot['controllers_dict'][k],True)


	# ---------------------------------------------------------------------------
	# Channel "Path" String
	# ---------------------------------------------------------------------------

	def get_path(self):
		path=self.bank_name
		if self.preset_name:
			path=path + "/" + self.preset_name
		return path

	def get_basepath(self):
		path=self.engine.get_path(self)
		if self.midi_chan is not None:
			path=path + "#" + str(self.midi_chan+1)
		return path

	def get_bankpath(self):
		path=self.get_basepath()
		if self.bank_name:
			path=path + " > " + self.bank_name
		return path

	def get_presetpath(self):
		path=self.get_bankpath()
		if self.preset_name:
			path=path + "/" + self.preset_name
		return path


#******************************************************************************
