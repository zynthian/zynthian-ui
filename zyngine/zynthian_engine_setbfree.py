# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_setbfree)
# 
# zynthian_engine implementation for setBfree Hammond Emulator
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

import re
import logging
from zyngine.zynthian_engine import *

#------------------------------------------------------------------------------
# setBfree Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_setbfree(zynthian_engine):
	name="setBfree"
	nickname="BF"

	drawbar_values=[['0','1','2','3','4','5','6','7','8'], [128,120,104,88,72,56,40,24,8]]
	base_dir="./data/setbfree/"

	max_chan=3
	chan_names=("upper","lower","pedals")

	ctrl_list=[
		[[
			['volume',1,96,127],
#			['swellpedal 2',11,96,127],
			['percussion on/off',80,'off','off|on','perc'],
			['rotary speed',91,'off','off|chr|trm|chr','rotaryspeed'],
#			['rotary speed toggle',64,0,3]
			['vibrato on/off',92,'off','off|on','vibratoupper']
		],0,'main'],
		[[
			['16',70,'8',drawbar_values,'drawbar_1'],
			['5 1/3',71,'8',drawbar_values,'drawbar_2'],
			['8',72,'8',drawbar_values,'drawbar_3'],
			['4',73,'8',drawbar_values,'drawbar_4']
		],0,'drawbars low'],
		[[
			['2 2/3',74,'8',drawbar_values,'drawbar_5'],
			['2',75,'8',drawbar_values,'drawbar_6'],
			['1 3/5',76,'8',drawbar_values,'drawbar_7'],
			['1 1/3',77,'8',drawbar_values,'drawbar_8']
			#['1',78,'8',drawbar_values,'drawbar_9']
		],0,'drawbars hi'],
		[[
			['drawbar 1',78,'8',drawbar_values,'drawbar_9'],
			['vibrato selector',83,'c3','v1|v2|v3|c1|c2|c3','vibrato'],
			#['percussion.volume',xx,90,127,'percvol'],
			['percussion decay',81,'slow','slow|fast','percspeed'],
			['percussion harmonic',82,'3rd','2nd|3rd','percharm']
		],0,'percussion & vibrato'],
		[[
			['overdrive on/off',23,'off','off|on','overdrive'],
			['overdrive character',93,64,127,'overdrive_char'],
			['overdrive inputgain',21,64,127,'overdrive_igain'],
			['overdrive outputgain',22,64,127,'overdrive_ogain']
		],0,'overdrive']
	]

	def __init__(self,parent=None):
		self.command=("/usr/local/bin/setBfree", "midi.driver="+self.midi_driver, "-p", self.base_dir+"/pgm/all.pgm", "-c", self.base_dir+"/cfg/zynthian.cfg")
		super().__init__(parent)

	def get_chan_name(self,chan=None):
		if chan is None:
			chan=self.midi_chan
		try:
			return self.chan_names[chan]
		except:
			return None

	def get_bank_dir(self,chan=None):
		bank_dir=self.base_dir+"/pgm-banks"
		chan_name=self.get_chan_name()
		if chan_name:
			bank_dir=bank_dir+'/'+chan_name
		return bank_dir

	def load_bank_list(self):
		self.load_bank_filelist(self.get_bank_dir(),"pgm")

	def load_instr_list(self):
		pgm_fpath=self.bank_list[self.get_bank_index()][0]
		self.instr_list=self.load_pgm_list(pgm_fpath)

	def load_ctrl_config(self, chan=None):
		super().load_ctrl_config(chan)
		#Set preset params into ctrl_config
		for ctrlcfg in self.ctrl_config[self.midi_chan]:
			for ctrl in ctrlcfg[0]:
				try:
					ctrl[2]=self.instr_set[self.midi_chan][3][ctrl[4]]
					if ctrl[4]=='rotaryspeed':
						if ctrl[2]=='tremolo': ctrl[2]='trm'
						elif ctrl[2]=='chorale': ctrl[2]='chr'
						else: ctrl[2]='off'
				except:
					pass

	def load_pgm_list(self,fpath):
		self.start_loading()
		pgm_list=None
		try:
			with open(fpath) as f:
				pgm_list=[]
				lines = f.readlines()
				ptrn1=re.compile("^([\d]+)[\s]*\{[\s]*name\=\"([^\"]+)\"")
				ptrn2=re.compile("[\s]*[\{\}\,]+[\s]*")
				i=0
				for line in lines:
					#Test with first pattern
					m=ptrn1.match(line)
					if not m: continue
					#Get line parts...
					fragments=ptrn2.split(line)
					params={}
					try:
						#Get program MIDI number
						prg=int(fragments[0])-1
						if prg>=0:
							#Get params from line parts ...
							for frg in fragments[1:]:
								parts=frg.split('=')
								try:
									params[parts[0].lower()]=parts[1].strip("\"\'")
								except:
									pass
							#Extract program name
							title=params['name']
							del params['name']
							#Complete program params ...
							if 'vibrato' in params: params['vibratoupper']='on'
							if 'drawbars' in params:
								j=1
								for v in params['drawbars']:
									if v in ['0','1','2','3','4','5','6','7','8']:
										params['drawbar_'+str(j)]=v
										j=j+1
							#Add program to list
							pgm_list.append((i,[0,0,prg],title,params))
							i=i+1
					except:
						#print("Ignored line: %s" % line)
						pass
		except Exception as err:
			pgm_list=None
			logging.error("Getting program info from %s => %s" % (fpath,err))
		self.stop_loading()
		return pgm_list


	def get_path(self,chan=None):
		path=super().get_path(chan)
		chan_name=self.get_chan_name(chan)
		if chan_name:
			return chan_name+'/'+path
		else:
			return path

#******************************************************************************
