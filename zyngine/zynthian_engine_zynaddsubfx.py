# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_zynaddsubfx)
# 
# zynthian_engine implementation for ZynAddSubFX Synthesizer
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

import os
from time import sleep
from string import Template
from os.path import isfile, join
from zyngine.zynthian_engine import *

#------------------------------------------------------------------------------
# ZynAddSubFX Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_zynaddsubfx(zynthian_engine):
	name="ZynAddSubFX"
	nickname="ZY"
	command=None
	osc_paths_data=[]

	conf_dir="./data/zynconf"
	bank_dirs=[
		('MY', os.getcwd()+"/my-data/zynbanks"),
		('_', os.getcwd()+"/data/zynbanks")
	]

	ctrl_list=[
		[[
			['volume','/part$ch/Pvolume',96,127],
			#['volume',7,96,127],
			['modulation',1,0,127],
			['filter Q',71,64,127],
			['filter cutoff',74,64,127]
		],0,'main'],
		[[
			['expression',11,127,127],
			['modulation',1,0,127],
			['reverb',91,64,127],
			['chorus',93,2,127]
		],0,'effects'],
		[[
			['bandwidth',75,64,127],
			['modulation amplitude',76,127,127],
			['resonance frequency',77,64,127],
			['resonance bandwidth',78,64,127]
		],0,'resonance']
	]

	def __init__(self,parent=None):
		if self.config_remote_display():
			self.command=("/usr/local/bin/zynaddsubfx", "-O", self.audio_driver, "-I", self.midi_driver, "-P", str(self.osc_target_port), "-l", self.conf_dir+"/zasfx_10ch.xmz", "-a")
		else:
			self.command=("/usr/local/bin/zynaddsubfx", "-O", self.audio_driver, "-I", self.midi_driver, "-U", "-P", str(self.osc_target_port), "-l", self.conf_dir+"/zasfx_10ch.xmz", "-a")
		super().__init__(parent)
		self.osc_init()

	def osc_add_methods(self):
			self.osc_server.add_method("/volume", 'i', self.cb_osc_load_instr)
			self.osc_server.add_method("/paths", None, self.parent.cb_osc_paths)
			self.osc_server.add_method(None, 'i', self.parent.cb_osc_ctrl)
			#super().osc_add_methods()
			#liblo.send(self.osc_target, "/echo")

	def load_bank_list(self):
		self.load_bank_dirlist(self.bank_dirs)

	def load_instr_list(self):
		self.instr_list=[]
		instr_dir=self.bank_list[self.bank_index[self.midi_chan]][0]
		print('Getting Instrument List for ' + self.bank_name[self.midi_chan])
		for f in sorted(os.listdir(instr_dir)):
			#print(f)
			if (isfile(join(instr_dir,f)) and f[-4:].lower()=='.xiz'):
				prg=int(f[0:4])-1
				bank_lsb=int(prg/128)
				bank_msb=self.bank_index[self.midi_chan]
				prg=prg%128
				title=str.replace(f[5:-4], '_', ' ')
				self.instr_list.append((f,[bank_msb,bank_lsb,prg],title))

	def _set_instr(self, instr, chan=None):
		self.start_loading()
		super()._set_instr(instr,chan)
		liblo.send(self.osc_target, "/volume")
		i=0
		while self.loading and i<100: 
			sleep(0.1)
			i=i+1

	def cb_osc_load_instr(self, path, args):
		self.stop_loading()

	def cb_osc_paths(self, path, args, types, src):
		for a, t in zip(args, types):
			if not a or t=='b':
				continue
			print("=> %s (%s)" % (a,t))
			a=str(a)
			postfix=prefix=firstchar=lastchar=''
			if a[-1:]=='/':
				tnode='dir'
				postfix=lastchar='/'
				a=a[:-1]
			elif a[-1:]==':':
				tnode='cmd'
				postfix=':'
				a=a[:-1]
				continue
			elif a[0]=='P':
				tnode='par'
				firstchar='P'
				a=a[1:]
			else:
				continue
			parts=a.split('::')
			if len(parts)>1:
				a=parts[0]
				pargs=parts[1]
				if tnode=='par':
					if pargs=='i':
						tnode='ctrl'
						postfix=':i'
					elif pargs=='T:F':
						tnode='bool'
						postfix=':b'
					else:
						continue
			parts=a.split('#',1)
			if len(parts)>1:
				n=int(parts[1])
				if n>0:
					for i in range(0,n):
						title=prefix+parts[0]+str(i)+postfix
						path=firstchar+parts[0]+str(i)+lastchar
						self.osc_paths.append((path,tnode,title))
			else:
				title=prefix+a+postfix
				path=firstchar+a+lastchar
				self.osc_paths_data.append((path,tnode,title))

#******************************************************************************
