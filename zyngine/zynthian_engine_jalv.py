# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_jalv)
#
# zynthian_engine implementation for Jalv Plugin Host
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
import pexpect
from time import sleep
from collections import OrderedDict
from json import JSONDecoder

from . import zynthian_engine
from . import zynthian_controller


#------------------------------------------------------------------------------
# Jalv Plugin List: Hardcoded by now #TODO Get from LV2_PATH
#------------------------------------------------------------------------------

def get_jalv_plugins():
	return [
		("Dexed", "https://github.com/dcoredump/dexed.lv2"),
		("Helm", "http://tytel.org/helm"),
		("MDA EPiano", "http://moddevices.com/plugins/mda/EPiano"),
		("MDA Piano", "http://moddevices.com/plugins/mda/Piano"),
		("MDA JX10", "http://moddevices.com/plugins/mda/JX10"),
		("MDA DX10", "http://moddevices.com/plugins/mda/DX10"),
		("OBXD", " https://obxd.wordpress.com"),
		("SynthV1", "http://synthv1.sourceforge.net/lv2"),
		("TAL NoizeMak3r", "http://kunz.corrupt.ch/products/tal-noisemaker")
	]

#------------------------------------------------------------------------------
# Jalv Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_jalv(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Controllers & Screens
	# ---------------------------------------------------------------------------

	_ctrls=None
	_ctrl_screens=None

	#----------------------------------------------------------------------------
	# Initialization
	#----------------------------------------------------------------------------

	def __init__(self, plugin_url, zyngui=None):
		super().__init__(zyngui)
		self.name = "Jalv"
		self.nickname = "JV"

		self.plugin_url = plugin_url

		if self.config_remote_display():
			self.command = ("/usr/local/bin/jalv {}".format(self.plugin_url))		#TODO => It's possible to run plugins UI?
		else:
			self.command = ("/usr/local/bin/jalv {}".format(self.plugin_url))

		output = self.start()

		#Get Plugin & Jack names from Jalv starting text ...
		self.jackname = None
		self.plugin_name = None
		if output:
			for line in output.split("\n"):
				if line[0:15]=="JACK Real Name:":
					self.jackname = line[16:].strip()
					logging.debug("Jack Name => {}".format(self.jackname))
					break
				elif line[0:10]=="JACK Name:":
					self.plugin_name = line[11:].strip()
					logging.debug("Plugin Name => {}".format(self.plugin_name))

		self.zctrl_dict = self.get_zctrl_dict()
		self.generate_ctrl_screens(self.zctrl_dict)

		self.preset_list = self._get_preset_list()

		self.reset()


	# ---------------------------------------------------------------------------
	# Subproccess Management & IPC
	# ---------------------------------------------------------------------------

	def proc_get_output(self):
		self.proc.expect('\n> ')
		return self.proc.before.decode()

	def start(self):
		if not self.proc:
			logging.info("Starting Engine " + self.name)
			try:
				self.start_loading()
				self.proc=pexpect.spawn(self.command)
				output=self.proc_get_output()
				self.stop_loading()
				return output
			except Exception as err:
				logging.error("Can't start engine %s => %s" % (self.name,err))

	def stop(self, wait=0.2):
		if self.proc:
			self.start_loading()
			try:
				logging.info("Stoping Engine " + self.name)
				self.proc.terminate()
				if wait>0: sleep(wait)
				self.proc.terminate(True)
			except Exception as err:
				logging.error("Can't stop engine %s => %s" % (self.name,err))
			self.proc=None
			self.stop_loading()

	def proc_cmd(self, cmd):
		if self.proc:
			try:
				logging.debug("proc command: "+cmd)
				self.proc.sendline(cmd)
				out=self.proc_get_output()
				logging.debug("proc output:\n%s" % (out))
			except Exception as err:
				out=""
				logging.error("Can't exec engine command: %s => %s" % (cmd,err))
			return out


	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------

	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	#----------------------------------------------------------------------------
	# Bank Managament
	#----------------------------------------------------------------------------

	def get_bank_list(self, layer=None):
		return [("", None, "", None)]

	def set_bank(self, layer, bank):
		pass


	#----------------------------------------------------------------------------
	# Preset Managament
	#----------------------------------------------------------------------------

	def _get_preset_list(self):
		self.start_loading()
		logging.info("Getting Preset List from LV2 Plugin ...")
		preset_list=[]
		output=self.proc_cmd("\get_presets")
		for line in sorted(output.split("\n")):
			try:
				parts=line.split(" => ")
				if len(parts)==2:
					title=parts[0].strip()
					url=parts[1].strip()
					preset_list.append((url,None,title,None))
			except Exception as e:
				logging.error(e)
		self.stop_loading()
		return preset_list

	def get_preset_list(self, bank):
		return self.preset_list

	def set_preset(self, layer, preset, preload=False):
		self.start_loading()
		
		output=self.proc_cmd("\set_preset {}".format(preset[0]))

		#Parse new controller values
		for line in output.split("\n"):
			try:
				parts=line.split(" = ")
				if len(parts)==2:
					self.zctrl_dict[parts[0]].value=float(parts[1])
			except Exception as e:
				logging.error(e)

		self.stop_loading()

	def cmp_presets(self, preset1, preset2):
		if preset1[0]==preset2[0]:
			return True
		else:
			return False

	#----------------------------------------------------------------------------
	# Controllers Managament
	#----------------------------------------------------------------------------

	def get_zctrl_dict(self):
		self.start_loading()
		logging.info("Getting Controller List from LV2 Plugin ...")
		output=self.proc_cmd("\info_controls")
		zctrls=OrderedDict()
		for line in output.split("\n"):
			parts=line.split(" => ")
			if len(parts)==2:
				symbol=parts[0]
				info=JSONDecoder().decode(parts[1])

				try:
					#If there is points info ...
					if len(info['points'])>1:
						labels=[]
						values=[]
						for p in info['points']:
							labels.append(p['label'])
							values.append(p['value'])
						try:
							val=info['value']
						except:
							val=labels[0]
						zctrls[symbol]=zynthian_controller(self,symbol,info['label'],{
							'graph_path': info['index'],
							'value': val,
							'labels': labels,
							'ticks': values,
							'value_min': values[0],
							'value_max': values[-1]
						})

					#If it's a normal controller ...
					else:
						r=info['max']-info['min']
						if info['is_integer']:
							if r==1 and info['is_toggle']:
								if info['value']==0: val='off'
								else: val='on'
								zctrls[symbol]=zynthian_controller(self,symbol,info['label'],{
									'graph_path': info['index'],
									'value': val,
									'labels': ['off','on'],
									'ticks': [0,1],
									'value_min': 0,
									'value_max': 1
								})
							else:
								zctrls[symbol]=zynthian_controller(self,symbol,info['label'],{
									'graph_path': info['index'],
									'value': int(info['value']),
									'value_default': int(info['default']),
									'value_min': int(info['min']),
									'value_max': int(info['max'])
								})
						else:
								zctrls[symbol]=zynthian_controller(self,symbol,info['label'],{
									'graph_path': info['index'],
									'value': info['value'],
									'value_default': info['default'],
									'value_min': info['min'],
									'value_max': info['max']
								})

				#If there is no range info (should be!!) => Default MIDI CC controller with 0-127 range
				except:
					zctrls[symbol]=zynthian_controller(self,symbol,info['label'],{
						'graph_path': info['index'],
						'value': 0,
						'value_default': 0,
						'value_min': 0,
						'value_max': 127
					})

		self.stop_loading()
		return zctrls


	def generate_ctrl_screens(self, zctrl_dict=None):
		self._ctrl_screens=[]
		if zctrl_dict is None:
			zctrl_dict=self.zctrl_dict

		c=1
		ctrl_set=[]
		for symbol, zctrl in zctrl_dict.items():
			try:
				#logging.debug("CTRL {}".format(symbol))
				ctrl_set.append(symbol)
				if len(ctrl_set)>=4:
					#logging.debug("ADDING CONTROLLER SCREEN #"+str(c))
					self._ctrl_screens.append(['Controllers#'+str(c),ctrl_set])
					ctrl_set=[]
					c=c+1
			except Exception as err:
				logging.error("Generating Controller Screens => {}".format(err))

		if len(ctrl_set)>=1:
			#logging.debug("ADDING CONTROLLER SCREEN #"+str(c))
			self._ctrl_screens.append(['Controllers#'+str(c),ctrl_set])


	def get_controllers_dict(self, layer):
		return self.zctrl_dict


	def send_controller_value(self, zctrl):
		self.proc_cmd("\set_control %d, %.6f" % (zctrl.graph_path, zctrl.value))


	#--------------------------------------------------------------------------
	# Special
	#--------------------------------------------------------------------------

	# ---------------------------------------------------------------------------
	# Layer "Path" String
	# ---------------------------------------------------------------------------

	def get_path(self, layer):
		path=self.nickname
		if self.plugin_name:
			path=path+'/'+self.plugin_name
		return path


#******************************************************************************
