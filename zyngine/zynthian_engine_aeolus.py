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

import logging
import copy
import struct
from collections import OrderedDict

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
		"name": "Manual III",
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
		"name": "Manual II",
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
		"name": "Manual I",
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
		"name": "Pedals",
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

	common_ctrls=[
		['Swell',7,64],
		['TFreq',12,42],
		['TMod',13,64],
		['Sustain',64,"off","off|on"]
	]

	_ctrls=[]
	_ctrl_screens=[]

	#----------------------------------------------------------------------------
	# Config variables
	#----------------------------------------------------------------------------

	n_banks = 32
	n_presets = 32
	stop_cc_num = 98
	ctrl_cc_num_start = 14
	presets_fpath = "/root/.aeolus-presets"

	#----------------------------------------------------------------------------
	# Initialization
	#----------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__(zyngui)
		self.name = "Aeolus"
		self.nickname = "AE"
		self.jackname = "aeolus"

		self.options['midi_chan']=False

		if self.config_remote_display():
			self.proc_start_sleep = 3
			self.command_prompt = None
			self.command = "/usr/bin/aeolus"
		else:
			self.command_prompt = "\nAeolus>"
			self.command = "/usr/bin/aeolus -t"

		self.presets_data = self.read_presets_file()
		self.generate_ctrl_list()

		self.start()
		self.reset()

	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------

	def add_layer(self, layer):
		super().add_layer(layer)


	def del_layer(self, layer):
		super().del_layer(layer)

	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	@classmethod
	def get_needed_channels(cls):
		chans = []
		for manual in cls.instrument:
			chans.append(manual['chan'])
		return chans

	#----------------------------------------------------------------------------
	# Bank Managament
	#----------------------------------------------------------------------------

	def get_bank_list(self, layer=None):
		res=[]
		i=-1
		#for i in range(self.n_banks):
		for gc in self.presets_data['group_config']:
			if gc['bank']>i:
				i=gc['bank']
				title="Bank {0:02d}".format(i+1)
				res.append((title,i,title))
		return res


	def set_bank(self, layer, bank):
		self.zyngui.zynmidi.set_midi_bank_lsb(layer.get_midi_chan(), bank[1])
		#Change Bank for all Layers
		for l in self.layers:
			if l!=layer:
				l.bank_index=layer.bank_index
				l.bank_name=layer.bank_name
				l.bank_info=copy.deepcopy(layer.bank_info)
		return True

	#----------------------------------------------------------------------------
	# Preset Managament
	#----------------------------------------------------------------------------

	def get_preset_list(self, bank):
		res=[]
		i=-1
		#for i in range(self.n_presets):
		for gc in self.presets_data['group_config']:
			if gc['preset']>i and gc['bank']==bank[1]:
				i=gc['preset']
				title="Preset {0:02d}".format(i+1)
				res.append([str(bank[1]) + '/' + title,[0,bank[1],i],title,gc['gconf']])
		return res


	def set_preset(self, layer, preset, preload=False):
		#Send Program Change
		self.zyngui.zynmidi.set_midi_preset(layer.get_midi_chan(), preset[1][0], preset[1][1], preset[1][2])

		if not preload:
			#Update Controller Values
			for ig, gc in enumerate(preset[3]):
				for ic, ctrl in enumerate(self.instrument[ig]['ctrls']):
					if (gc >> ic) & 1:
						ctrl[2]='on'
					else:
						ctrl[2]='off'
			self.refresh_all()

			#Change Preset for all Layers
			for l in self.layers:
				if l!=layer:
					l.preset_index=layer.preset_index
					l.preset_name=layer.preset_name
					l.preset_info=copy.deepcopy(layer.preset_info)
					l.preset_bank_index=l.bank_index
					l.preload_index=l.preset_index
					l.preload_name=l.preset_name
					l.preload_info=l.preset_info

		return True

	#----------------------------------------------------------------------------
	# Controllers Managament
	#----------------------------------------------------------------------------

	@classmethod
	def generate_ctrl_list(cls):
		#Generate ctrl list for each group in instrument
		n=0
		for ig, group in enumerate(cls.instrument):
			#Generate _ctrls list
			i=0
			cls.instrument[ig]['ctrls']=[]
			#self.instrument[ig]['ctrls']=copy.deepcopy(self.common_ctrls)
			for ctrl_name in group['buttons']:
				cc_num=cls.ctrl_cc_num_start+n
				cls.instrument[ig]['ctrls'].append([ctrl_name,cc_num,'off','off|on',[ig,i]])
				i+=1
				n+=1
		
			#Generate _ctrl_screens list
			cls.instrument[ig]['ctrl_screens']=[]
			ctrl_set=[]
			i=0
			for ctrl in cls.instrument[ig]['ctrls']:
				ctrl_set.append(ctrl[0])
				if len(ctrl_set)==4:
					cls.instrument[ig]['ctrl_screens'].append(["{} ({})".format(group['name'],i),ctrl_set])
					ctrl_set=[]
					i+=1
			if len(ctrl_set)>0:
				cls.instrument[ig]['ctrl_screens'].append(["{} ({})".format(group['name'],i),ctrl_set])


	def get_controllers_dict(self, layer):
		#Find ctrl list for layer's group
		for group in self.instrument:
			if group['chan']==layer.midi_chan:
				self._ctrls=group['ctrls']
				self._ctrl_screens=group['ctrl_screens']
				return super().get_controllers_dict(layer)

		return OrderedDict()



	def send_controller_value(self, zctrl):
		self.midi_zctrl_change(zctrl, int(zctrl.get_value()))

	#----------------------------------------------------------------------------
	# MIDI CC processing
	#----------------------------------------------------------------------------

	def midi_zctrl_change(self, zctrl, val):
		try:
			if isinstance(zctrl.graph_path,list):
				if isinstance(val,int):
					if val>=64:
						val="on"
					else:
						val="off"

					if val!=zctrl.get_value2label():
						zctrl.set_value(val)
	
				if val=="on":
					mm="10"
				else:
					mm="01"

				v1="01{0}0{1:03b}".format(mm,zctrl.graph_path[0])
				v2="000{0:05b}".format(zctrl.graph_path[1])
				self.zyngui.zynmidi.set_midi_control(zctrl.midi_chan,self.stop_cc_num,int(v1,2))
				self.zyngui.zynmidi.set_midi_control(zctrl.midi_chan,self.stop_cc_num,int(v2,2))

				#logging.debug("Aeolus Stop ({}) => mm={}, group={}, button={})".format(val,mm,zctrl.graph_path[0],zctrl.graph_path[1]))

		except Exception as e:
			logging.debug(e)

	#--------------------------------------------------------------------------
	# Special
	#--------------------------------------------------------------------------

	def get_chan_name(self, chan):
		for group in self.instrument:
			if group['chan']==chan:
				return group['name']


	@classmethod
	def read_presets_file(cls):

		with open(cls.presets_fpath, mode='rb') as file:
			data = file.read()

			pos=0
			header=struct.unpack("6sbHHHH", data[pos:16])
			#logging.debug(header)
			pos+=16
			if header[0].decode('ASCII')!="PRESET":
				logging.error("FORMAT => Bad Header")

			n_groups=header[5]
			if n_groups!=len(cls.instrument):
				logging.error("Number of groups ({}) doesn't fit with engine's configuration ({}) !".format(n_groups,len(cls.instrument)))

			chan_config=[]
			for num in range(8):
				chan_config.append([])
				for group in range(16):
					res=struct.unpack("H", data[pos:pos+2])
					pos+=2
					chan_config[num].append(res[0])
					logging.debug("CHAN CONFIG (NUM {0}, GROUP {1} => {2:b}".format(num,group,res[0]))

			for i,group in enumerate(cls.instrument):
				group['chan'] = chan_config[0][i] & 0xF;

			group_config=[]
			try:
				while True:
					res=struct.unpack("BBBB", data[pos:pos+4])
					pos+=4
					if res[0]>=cls.n_banks:
						logging.error("FORMAT => Bank index ({}>={})".format(res[0],cls.n_banks))
						return
					if res[1]>=cls.n_presets:
						logging.error("FORMAT => Preset index ({}>={})".format(res[1],cls.n_presets))
						return
					logging.debug("BANK {}, PRESET {} =>".format(res[0],res[1]))
					gconf=[]
					for group in range(n_groups):
						gc=struct.unpack("I", data[pos:pos+4])
						pos+=4
						gconf.append(gc[0])
						logging.debug("GROUP CONFIG {0} => {1:b}".format(group,gc[0]))

					group_config.append({
						'bank': res[0],
						'preset': res[1],
						'gconf':gconf
					})
					
			except:
				pass

			return {
				'n_groups' : n_groups,
				'chan_config' : chan_config,
				'group_config': group_config
			}

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
