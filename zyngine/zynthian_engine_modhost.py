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
	max_chan=1

	command=("/usr/local/bin/mod-host", "-i")
	command_pb2mh="/home/pi/zynthian/zynthian-ui/zyngine/pedalboard2modhost"
	lv2_path="/home/pi/.lv2:/home/pi/zynthian/zynthian-plugins/mod-lv2"

	plugin_info={}

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
		#self.start(True)
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
		self.plugin_info={}
		midi_cc=1
		cmds=""
		for r in res:
			print(r.strip())
			#Catch plugin names and IDs
			m=re.search(r'add\s+([^\s]+)\s+([\d]+)',r)
			if m and m.group(1) and m.group(2):
				plugin_id=m.group(2)
				plugin_uri=m.group(1)
				plugin_name=plugin_uri.split('/')[-1]
				self.plugin_info[plugin_id]={}
				self.plugin_info[plugin_id]['name']=plugin_name.replace('_', ' ')
				self.plugin_info[plugin_id]['parameter_list']=[]
				continue
			#Try to detect MIDI Input plugins and connect it to capture_1 => must be improved!
			m=re.search(r'connect\s+([^\s]+)\s+ttymidi\:MIDI_in',r)
			if m and m.group(1):
				cmds=cmds+"connect "+m.group(1)+" system:midi_capture_1\n"
				continue
			#Set controller mapping => overwrite midi learning from UI (to fix!!)
			m=re.search(r'param_set\s+([\d]+)\s+([^\s]+)\s+(\-?[\.\d]+)',r)
			if m and m.group(1) and m.group(2) and m.group(3):
				plugin_id=m.group(1)
				param_name=m.group(2).replace('_', ' ')
				param_value=m.group(3)
				plugin_name=self.plugin_info[plugin_id]['name']
				print("SETTING MIDI CC "+str(midi_cc)+" => "+plugin_name+"->"+param_name)
				#Add parameter to plugin_info
				param={
					'name': param_name,
					'value': param_value,
					'min': 0,
					'max': 0,
					'midi_cc': midi_cc
				}
				self.plugin_info[plugin_id]['parameter_list'].append(param)
				#Build midi_map command for mod-host
				cmds=cmds+"midi_map "+plugin_id+" "+param_name+" "+str(self.midi_chan)+" "+str(midi_cc)+"\n"
				#Next MIDI CC
				midi_cc=midi_cc+1
				continue
		#Send mod-host post-commands
		res=self.proc_cmd(cmds,1)
		for r in res:
			print(r.strip())
		#Generate controller config lists
		if not self.snapshot_fpath:
			self.generate_ctrl_list()
		#Reload Parameter Values
		#self.load_snapshot_post()

	def generate_ctrl_list(self):
		self.ctrl_list=[]
		for i in self.plugin_info:
			c=1
			param_set=[]
			for param in self.plugin_info[i]['parameter_list']:
				try:
					#print("CTRL LIST PLUGIN %s PARAM %s" % (i,param))
					if param['midi_cc']>0:
						r=param['max']-param['min']
						if r!=0: midi_val=int(127*(param['value']-param['min'])/r)
						else: midi_val=0;
						param_set.append([param['name'], param['midi_cc'], midi_val, 127])
						if len(param_set)>=4:
							self.ctrl_list.append([param_set,0,self.plugin_info[i]['name']+'#'+str(c)])
							param_set=[]
							c=c+1
				except Exception as err:
					#print("EXCEPTION REGENERATING CONTROLLER LIST: "+str(param)+" => "+str(err))
					pass
			if len(param_set)>=1:
				self.ctrl_list.append([param_set,0,self.plugin_info[i]['name']+'#'+str(c)])
		if len(self.ctrl_list)==0:
			print("LOADING CONTROLLER DEFAULTS")
			self.ctrl_list=self.default_ctrl_list
		self.load_ctrl_config()


#******************************************************************************
