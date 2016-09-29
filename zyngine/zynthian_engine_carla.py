# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_carlapatch)
# 
# zynthian_engine implementation for Carla Plugin Host
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
import socket
from time import sleep, time
from zyngine.zynthian_engine import *

#------------------------------------------------------------------------------
# carla-patchbay Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_carla(zynthian_engine):
	name="Carla"
	nickname="CP"

	patch_name=""
	patch_dirs=[
		('_', os.getcwd()+"/data/carla"),
		('MY', os.getcwd()+"/my-data/carla")
	]

	plugin_info={}
	touched=False
	refreshed_ts=None

	def __init__(self,parent=None):
		self.plugin_info={}
		self.touched=False
		self.refreshed_ts=None
		self.parent=parent
		self.clean()
		self.load_bank_list()

	def osc_init(self, proto):
		super().osc_init(proto)
		#Register OSC connection
		self.osc_register(proto)

	def osc_add_methods(self):
		#Plugin list
		self.osc_server.add_method("//add_plugin_start", 'is', self.cb_add_plugin_start)
		self.osc_server.add_method("//add_plugin_end", 'i', self.cb_add_plugin_end)
		#Program list
		self.osc_server.add_method("//set_program_count", 'ii', self.cb_set_program_count)
		self.osc_server.add_method("//set_program_name", 'iis', self.cb_set_program_name)
		#Parameter list
		self.osc_server.add_method("//set_parameter_count", 'iii', self.cb_set_parameter_count)
		self.osc_server.add_method("//set_parameter_data", 'iiiiss', self.cb_set_parameter_data)
		self.osc_server.add_method("//set_parameter_ranges1", 'iifff', self.cb_set_parameter_ranges1)
		self.osc_server.add_method("//set_parameter_midi_cc", 'iii', self.cb_set_parameter_midi_cc)
		#self.osc_server.add_method("//set_parameter_midi_channel", 'iii', self.cb_set_parameter_midi_channel)
		#self.osc_server.add_method("//set_parameter_value", 'iif', self.cb_set_parameter_value)
		#Capture some extra messages to avoid trash
		#self.osc_server.add_method("//set_peaks", None, self.cb_set_peaks)
		#super().osc_add_methods()

	def xosc_add_methods(self):
		self.osc_server.add_method("//set_peaks", None, self.cb_set_peaks)
		super().osc_add_methods()

	def osc_register(self, proto):
		self.osc_registered=False
		#self.osc_register_n=0
		if proto==liblo.TCP: self.osc_register_tcp()
		else: self.osc_register_udp()

	def osc_register_tcp(self):
		#self.osc_register_n=self.osc_register_n+1
		#print("OSC Register TCP, try "+str(self.osc_register_n))
		try:
			liblo.send(self.osc_target, "/register",self.osc_server_url)
			self.osc_registered=True
			print("OSC registered")
		except Exception as e:
			print("ERROR engine_carla::osc_register: %s" % str(e))
			self.parent.after(200,self.osc_register_tcp)

	def osc_register_udp(self):
		#self.osc_register_n=self.osc_register_n+1
		#print("OSC Register UDP, try "+str(self.osc_register_n))
		try:
			liblo.send(self.osc_target, "/register",self.osc_server_url)
		except Exception as e:
			print("ERROR engine_carla::osc_register: %s" % str(e))
		if not self.osc_registered:
			self.parent.after(200,self.osc_register_udp)

	def cb_osc_all(self, path, args, types, src):
		self.osc_registered=True
		print("OSC %s => %s : %s" % (path, len(args), types))
		#super().cb_osc_all(path, args, types, src)

	def cb_set_peaks(self):
		self.osc_registered=True

	def cb_add_plugin_start(self, path, args):
		#print("PLUGIN START %s" % (args[1]))
		self.osc_connected=True
		try:
			self.plugin_info[args[0]]={
				'name': args[1],
				'program_count': 0,
				'program_list': {},
				'parameter_count': 0,
				'parameter_list': []
			}
		except:
			pass

	def cb_add_plugin_end(self, path, args):
		#print("PLUGIN END %s" % (args[0]))
		try:
			self.refresh()
		except:
			pass

	def cb_set_program_count(self, path, args):
		#print("PROGRAM COUNT FOR PLUGIN %s => %s" % (args[0],args[1]))
		try:
			self.plugin_info[args[0]]['program_count']=args[1]
			self.touched=True
		except:
			pass

	def cb_set_program_name(self, path, args):
		#print("PROGRAM NAME FOR PLUGIN %s => %s (%s)" % (args[0],args[2],args[1]))
		try:
			if not args[2]: args[2]="Program "+args[1]
			self.plugin_info[args[0]]['program_list'][args[1]]=args[2]
			self.touched=True
		except:
			pass

	def cb_set_parameter_count(self, path, args):
		#print("PARAMETER COUNT FOR PLUGIN %s => %s" % (args[0],args[1]))
		try:
			self.plugin_info[args[0]]['parameter_count']=args[1]
			for i in range(args[1]):
				self.plugin_info[args[0]]['parameter_list'].append({})
			self.touched=True
		except:
			pass

	def cb_set_parameter_data(self, path, args):
		#print("PARAMETER DATA FOR PLUGIN %s => %s (%s)" % (args[0],args[1],args[4]))
		try:
			self.plugin_info[args[0]]['parameter_list'][args[1]]['name']=args[4]
		except:
			pass

	def cb_set_parameter_ranges1(self, path, args):
		#print("PARAMETER RANGES FOR PLUGIN %s => %s [%s, %s, %s]" % (args[0],args[1],args[2],args[3],args[4]))
		try:
			param=self.plugin_info[args[0]]['parameter_list'][args[1]]
			param['value']=args[2]
			param['min']=args[3]
			param['max']=args[4]
			self.touched=True
		except:
			pass

	def cb_set_parameter_midi_cc(self, path, args):
		#print("PARAMETER MIDI-CC FOR PLUGIN %s => %s (%s)" % (args[0],args[1],args[2]))
		try:
			self.plugin_info[args[0]]['parameter_list'][args[1]]['midi_cc']=args[2]
			self.touched=True
		except:
			pass

	def cb_set_parameter_midi_channel(self, path, args):
		pass

	def cb_set_parameter_value(self, path, args, types, src):
		#print("PARAMETER VALUE FOR PLUGIN %s => %s (%s)" % (args[0],args[1],args[2]))
		try:
			self.plugin_info[args[0]]['parameter_list'][args[1]]['value']=args[2]
			self.touched=True
		except:
			pass

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

	def generate_instr_list(self):
		self.instr_list=[]
		for i in self.plugin_info:
			for prg,name in self.plugin_info[i]['program_list'].items():
				bank_lsb=int(prg/128)
				prg=prg%128
				self.instr_list.append((name,[0,bank_lsb,prg],name))
		if len(self.instr_list)==0:
			self.instr_list.append((None,[0,0,0],""))

	def refresh(self):
		if self.touched:
			self.touched=False
			self.refreshed_ts=time()
			#generate program list
			self.generate_instr_list()
			print("PROGRAM LIST ...\n"+str(self.instr_list))
			#generate controller list
			if not self.snapshot_fpath:
				self.generate_ctrl_list()
			else:
				self.ctrl_list=self.ctrl_config[self.midi_chan]
			print("CONTROLLER LIST ...\n"+str(self.ctrl_list))
			#refresh screen
			self.parent.refresh_screen()
		elif self.refreshed_ts and (time()-self.refreshed_ts)>0.5:
			self.refreshed_ts=None
			if self.loading:
				print("AFTER REFRESH POST LOADING  ...")
				self.stop_loading()
				self.load_snapshot_post()

	def load_bank_list(self):
		self.load_bank_filelist(self.patch_dirs,"carxp")

	def load_instr_list(self):
		new_patch=self.bank_list[self.get_bank_index()][0]
		if new_patch!=self.patch_name:
			self.load_patch(new_patch)

	#TODO: Revise this!!!
	def load_ctrl_config(self):
		self.ctrl_config[self.midi_chan]=self.ctrl_list

	def set_all_instr(self):
		self.load_instr_list()
		super().set_all_instr()

	def load_patch(self, patch):
		#Set OSC PORT connection variables
		#os.environ['CARLA_OSC_UDP_PORT']=str(self.osc_target_port)
		os.environ['CARLA_OSC_TCP_PORT']=str(self.osc_target_port)
		#Load patch
		self.patch_name=patch
		if self.config_remote_display():
			self.command=("/usr/local/bin/carla-patchbay", self.patch_name)
		else:
			self.command=("/usr/local/bin/carla-patchbay", "-n", self.patch_name)
		#Stop Previous Carla Instance
		self.osc_end()
		self.stop(1)
		#Reset plugin info
		self.plugin_info={}
		self.touched=False
		self.instr_list=[]
		self.ctrl_list=self.default_ctrl_list
		#Run Carla Instance
		print("Running Command: "+ str(self.command))
		self.start(True)
		self.osc_init(liblo.TCP)
		self.start_loading()

#******************************************************************************
