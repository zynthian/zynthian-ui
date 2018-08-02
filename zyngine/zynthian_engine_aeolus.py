# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_aeolus)
#
# zynthian_engine implementation for Aeolus
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
from collections import OrderedDict
from os.path import isfile,isdir,join

from . import zynthian_engine
from . import zynthian_controller

#------------------------------------------------------------------------------
# Aeolus Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_aeolus(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Controllers & Screens
	# ---------------------------------------------------------------------------

	instrument=[{
		"name": "Manual I",
		"num": 2,
		"chan": 0,
		"buttons": [
			'Principal 8',
			'Principal 4',
			'Octave 2',
			'Octave 1',
			'Quint 5 1/3',
			'Quint 2 2/3',
			'Tibia 8',
			'Celesta 8',
			'Flöte 8',
			'Flöte 4',
			'Flöte 2',
			'Cymbel VI',
			'Mixtur',
			'Trumpet',
			'I+II',
			'I+III'
		]
	},{
		"name": "Manual II",
		"num": 1,
		"chan": 1,
		"buttons": [
			'Rohrflöte 8',
			'Harmonic Flute 4',
			'Flauto Dolce 4',
			'Nasard 2 2/3',
			'Ottavina 2',
			'Tertia 1 3/5',
			'Sesqui-altera',
			'Septime',
			'None',
			'Krumhorn',
			'Melodia',
			'Tremulant',
			'II+III'
		]
	},{
		"name": "Manual III",
		"num": 0,
		"chan": 2,
		"buttons": [
			'Principal 8',
			'Gemshorn 8',
			'Quinta-dena 8',
			'Suabile 8',
			'Rohrflöte 4',
			'Dulzflöte 4',
			'Quintflöte 2 2/3',
			'Super-octave 2',
			'Sifflet 1',
			'Cymbel VI',
			'Oboe',
			'Tremulant'
		]
	},{
		"name": "Pedals",
		"num": 3,
		"chan": 3,
		"buttons": [
			'Subbass 16',
			'Principal 16',
			'Principal 8',
			'Principal 4',
			'Octave 2',
			'Octave 1',
			'Quint 5 1/3',
			'Quint 2 2/3',
			'Mixtur',
			'Fagott 16',
			'Trombone 16',
			'Bombarde 32',
			'Trumpet',
			'P+I',
			'P+II',
			'P+III'
		]
	}]

	_ctrls=[]
	_ctrl_screens=[]

	#----------------------------------------------------------------------------
	# Initialization
	#----------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__(zyngui)
		self.name="Aeolus"
		self.nickname="AE"

		self.n_banks=32
		self.n_presets=32
		self.stop_cc_num=98
		self.ctrl_cc_num_start=12

		if self.config_remote_display():
			self.command=("/usr/bin/aeolus")
		else:
			self.command=("/usr/bin/aeolus", "-t")

		self.generate_ctrl_list()
		self.start()
		self.reset()

	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------

	def add_layer(self, layer):
		super().add_layer(layer)
		layer.listen_midi_cc=True

	def del_layer(self, layer):
		super().del_layer(layer)
		layer.listen_midi_cc=False

	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	#----------------------------------------------------------------------------
	# Bank Managament
	#----------------------------------------------------------------------------

	def get_bank_list(self, layer=None):
		self.start_loading()
		res=[]
		for i in range(self.n_banks):
			title="Bank {0:02d}".format(i+1)
			res.append((title,i,title))
		self.stop_loading()
		return res

	def set_bank(self, layer, bank):
		self.zyngui.zynmidi.set_midi_bank_lsb(layer.get_midi_chan(), bank[1])

	#----------------------------------------------------------------------------
	# Preset Managament
	#----------------------------------------------------------------------------

	def get_preset_list(self, bank):
		self.start_loading()
		res=[]
		for i in range(self.n_presets):
			title="Preset {0:02d}".format(i+1)
			res.append((title,[0,bank[1],i],title))
		self.stop_loading()
		return res

	def set_preset(self, layer, preset, preload=False):
		self.zyngui.zynmidi.set_midi_preset(layer.get_midi_chan(), preset[1][0], preset[1][1], preset[1][2])


	#----------------------------------------------------------------------------
	# Controllers Managament
	#----------------------------------------------------------------------------

	def send_controller_value(self, zctrl):
		self.midi_control_change(zctrl, zctrl.get_label2value())


	def midi_control_change(self, zctrl, val):
		try:
			if isinstance(val,int):
				if val>=64:
					val="on"
				else:
					val="off"
				if val!=zctrl.get_label2value():
					zctrl.set_value(val)
				else:
					return
			if val=="on":
				mm="10"
			else:
				mm="01"
			v1="01{0}0{1:03b}".format(mm,zctrl.graph_path[0])
			v2="000{0:05b}".format(zctrl.graph_path[1])
			self.zyngui.zynmidi.set_midi_control(zctrl.midi_chan,self.stop_cc_num,int(v1,2))
			self.zyngui.zynmidi.set_midi_control(zctrl.midi_chan,self.stop_cc_num,int(v2,2))
			logging.debug("Aeolus Stop => mm={}, group={}, button={})".format(mm,zctrl.graph_path[0],zctrl.graph_path[1]))
		except Exception as e:
			logging.debug(e)


	def generate_ctrl_list(self):

		#Generate ctrl list for each group in instrument
		n=0
		for ig, group in enumerate(self.instrument):
			#Generate _ctrls list
			i=0
			self.instrument[ig]['ctrls']=[]
			for ctrl_name in group['buttons']:
				cc_num=self.ctrl_cc_num_start+n
				self.instrument[ig]['ctrls'].append([ctrl_name,cc_num,'off','off|on',[group['num'],i]])
				i+=1
				n+=1
		
			#Generate _ctrl_screens list
			self.instrument[ig]['ctrl_screens']=[]
			ctrl_set=[]
			i=0
			for ctrl in self.instrument[ig]['ctrls']:
				ctrl_set.append(ctrl[0])
				if len(ctrl_set)==4:
					self.instrument[ig]['ctrl_screens'].append(["{} ({})".format(group['name'],i),ctrl_set])
					ctrl_set=[]
					i+=1
			if len(ctrl_set)>0:
				self.instrument[ig]['ctrl_screens'].append(["{} ({})".format(group['name'],i),ctrl_set])


	def get_controllers_dict(self, layer):

		#Find ctrl list for layer's group
		for group in self.instrument:
			if group['chan']==layer.midi_chan:
				self._ctrls=group['ctrls']
				self._ctrl_screens=group['ctrl_screens']
				return super().get_controllers_dict(layer)

		return OrderedDict()


	#--------------------------------------------------------------------------
	# Special
	#--------------------------------------------------------------------------

	def get_chan_name(self, chan):
		for group in self.instrument:
			if group['chan']==chan:
				return group['name']

	# ---------------------------------------------------------------------------
	# Layer "Path" String
	# ---------------------------------------------------------------------------

	def get_path(self, layer):
		path=self.nickname
		chan_name=self.get_chan_name(layer.get_midi_chan())
		if chan_name:
			path=path+'/'+chan_name
		return path


#******************************************************************************
