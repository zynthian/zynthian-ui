# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_mod)
# 
# zynthian_engine implementation for MOD-HOST (LV2 plugin host)
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
import re
from subprocess import check_output
from zyngine.zynthian_engine import *

#------------------------------------------------------------------------------
# ZynAddSubFX Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_modhost(zynthian_engine):
	name="MODHost"
	nickname="MH"
	command=("/usr/local/bin/mod-host", "-i")
	command_pb2mh="/home/pi/zynthian/zynthian-ui/zyngine/pedalboard2modhost"
	lv2_path="/home/pi/.lv2:/home/pi/zynthian/zynthian-plugins/mod-lv2"

	bank_dirs=[
		#('MY', os.getcwd()+"/my-data/mod-pedalboards"),
		('_', os.getcwd()+"/data/mod-pedalboards")
	]

	ctrl_list=[
		[[
			['volume',7,96,127],
			['pan',10,64,127],
			['sustain on/off',64,'off','off|on'],
			['modulation',1,0,127]
		],0,'main'],
		[[
			['volume',7,96,127],
			['pan',10,64,127],
			['portamento on/off',65,'off','off|on'],
			['portamento',5,64,127]
		],0,'portamento']
	]

	def __init__(self,parent=None):
		os.environ['LV2_PATH']=self.lv2_path
		self.parent=parent
		self.clean()
		self.start(True)
		self.load_bank_list()
		#self.osc_init()

	def stop(self):
		self.proc_cmd("quit",1)
		super().stop()

	def proc_get_lines(self, tout=0.1):
		lines=[]
		while True:
			try:
				lines.append(self.queue.get(timeout=tout))
			except Empty:
				break
		return lines

	def load_bank_list(self):
		self.load_bank_dirlist(self.bank_dirs)

	def load_instr_list(self):
		self.instr_list=[(0,[0,0,0],'','')]

	def _set_instr(self, instr, chan=None):
		self.start_loading()
		self.stop()
		self.start(True)
		instr_dpath=self.bank_list[self.get_bank_index()][0]
		instr_ttl=os.path.basename(instr_dpath)
		instr_ttl,ext=os.path.splitext(instr_ttl)
		self.mh_commands(instr_dpath+"/"+instr_ttl+".ttl")
		self.stop_loading()

	def mh_commands(self, ttl_fpath):
		cmds=check_output((self.command_pb2mh,ttl_fpath), shell=False).decode('utf8')
		res=self.proc_cmd(cmds,2)
		for r in res:
			print(r.strip())
			#Try to detect MIDI Input plugins
			m=re.match(r'connect\s+([^\s])\s+ttymidi\:MIDI_in',r)
			if m and m.group(1):
				cmd="connect "+m.group(1)+" midi_system:capture_1"
				res=self.proc_cmd(cmd,0.1)
				print(str(res))

#******************************************************************************
