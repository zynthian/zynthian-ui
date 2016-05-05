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
from zyngine.zynthian_engine import *

#------------------------------------------------------------------------------
# setBfree Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_setbfree(zynthian_engine):
	name="setBfree"
	nickname="BF"

	#drawbar_values=[['8','7','6','5','4','3','2','1','0'], [8,24,40,56,72,88,104,120,128]]
	drawbar_values=[['0','1','2','3','4','5','6','7','8'], [128,120,104,88,72,56,40,24,8]]
	base_dir="./data/setbfree/"

	chan_names=("upper","lower","pedals")
	
	map_list=(
		([
			('volume',1,96,127),
#			('swellpedal 2',11,96,127),
			('percussion on/off',80,'off','off|on'),
			('rotary speed',91,'off','off|chr|trm|chr'),
#			('rotary speed toggle',64,0,3)
			('vibrato on/off',92,'off','off|on')
		],0,'main'),
		([
			('16',70,'8',drawbar_values),
			('5 1/3',71,'8',drawbar_values),
			('8',72,'8',drawbar_values),
			('4',73,'8',drawbar_values)
		],0,'drawbars low'),
		([
			('2 2/3',74,'8',drawbar_values),
			('2',75,'8',drawbar_values),
			('1 3/5',76,'8',drawbar_values),
			('1 1/3',77,'8',drawbar_values)
			#('1',78,'8',drawbar_values)
		],0,'drawbars hi'),
		([
			('drawbar 1',78,'8',drawbar_values),
			('vibrato selector',83,'c3','v1|v2|v3|c1|c2|c3'),
			#('percussion.volume',xx,90,127),
			('percussion decay',81,'slow','slow|fast'),
			('percussion harmonic',82,'3rd','2nd|3rd')
		],0,'percussion & vibrato'),
		([
			('overdrive on/off',23,'off','off|on'),
			('overdrive character',93,64,127),
			('overdrive inputgain',21,64,127),
			('overdrive outputgain',22,64,127)
		],0,'overdrive')
	)
	default_ctrl_config=map_list[0][0]

	def __init__(self,parent=None):
		self.max_chan=3
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
		pgm_fpath=self.get_bank_dir()+'/'+self.bank_list[self.get_bank_index()][0]
		self.instr_list=self.load_pgm_list(pgm_fpath)

	def load_pgm_list(self,fpath):
		pgm_list=[]
		with open(fpath) as f:
			lines = f.readlines()
			ptrn=re.compile("^([\d]+)[\s]*\{[\s]*name\=\"([^\"]+)\"")
			i=0
			for line in lines:
				m=ptrn.match(line)
				if m:
					try:
						prg=int(m.group(1))-1
						title=m.group(2)
						if prg>=0:
							pgm_list.append((i,[0,0,prg],title))
							i=i+1
					except:
						pass
			return pgm_list

	def get_path(self,chan=None):
		path=super().get_path(chan)
		chan_name=self.get_chan_name(chan)
		if chan_name:
			return chan_name+'/'+path
		else:
			return path

#******************************************************************************
