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
# For a full copy of the GNU General Public License see the doc/GPL.txt file.
# 
#******************************************************************************

import os
from time import sleep
from zyngine.zynthian_engine import *

#------------------------------------------------------------------------------
# carla-patchbay Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_carla(zynthian_engine):
	name="Carla"
	nickname="CP"
	patch_dir="./data/carla/"
	patch_name="dexed_simple_pb.carxp"
	command=None

	map_list=(
		([
			('volume',7,96,127),
			#('expression',11,127,127),
			('modulation',1,0,127),
			('filter Q',71,64,127),
			('filter cutoff',74,64,127)
		],0,'main'),
		([
			('expression',11,127,127),
			('modulation',1,0,127),
			('reverb',91,64,127),
			('chorus',93,2,127)
		],0,'effects')
	)
	default_ctrl_config=map_list[0][0]

	def __init__(self,parent=None):
		self.parent=parent
		self.clean()
		self.load_bank_list()

	def osc_init(self):
		self.osc_server.add_method("/set_peaks", None, self.cb_set_peaks)
		self.osc_server.add_method("/set_parameter_value", None, self.cb_set_parameter_value)
		super().osc_init()
		try:
			url="osc.udp://[::ffff:127.0.0.1]:"+str(self.osc_server_port)
			liblo.send(self.osc_target, "/register",url)
			print("***** SENDING OSC /register "+url) 
		except Exception as e:
			print("ERROR engine_carla::osc_register: %s" % str(e))

	def cb_set_peaks(self):
		pass

	def cb_set_parameter_value(self):
		pass

	def cb_osc_all(self, path, args, types, src):
		parts=path.split("/")
		if parts[1]=="set_peaks" or parts[1]=="set_parameter_value" or parts[1]=="set_default_value":
			return
		print("OSC MESSAGE '%s' from '%s'" % (path, src.url))
		for a, t in zip(args, types):
			print("argument of type '%s': %s" % (t, a))

	def load_bank_list(self):
		self.load_bank_filelist(self.patch_dir,"carxp")

	def load_instr_list(self):
		os.environ['CARLA_OSC_UDP_PORT']=str(self.osc_target_port)
		self.patch_name=self.bank_list[self.get_bank_index()][0]
		if os.environ.get('ZYNTHIANX'):
			self.command=("/usr/local/bin/carla-patchbay", self.patch_dir+"/"+self.patch_name)
		else:
			self.command=("/usr/local/bin/carla-patchbay", "-n", self.patch_dir+"/"+self.patch_name)
		print("Running Command: "+ str(self.command))
		self.stop()
		sleep(1)
		self.start()
		sleep(2)
		self._osc_init()

		try:
			liblo.send(self.osc_target, "/")
			self.osc_server.recv()
		except:
			zyngui.show_screen('control')
		#zyngui.screens['control'].fill_list()
		
		self.instr_list=[]
		for i in range(32):
			f="MIDI PRG"+str(i)
			bank_msb=0
			bank_lsb=0
			prg=i
			title=f
			self.instr_list.append((f,[bank_msb,bank_lsb,prg],title))


#******************************************************************************
