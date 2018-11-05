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
import json
import logging
import pexpect
from time import sleep
from os.path import isfile
from collections import OrderedDict

from . import zynthian_engine
from . import zynthian_controller



def get_jalv_plugins():
	if isfile(zynthian_engine_jalv.JALV_LV2_CONFIG_FILE):
		with open(zynthian_engine_jalv.JALV_LV2_CONFIG_FILE,'r') as f:
			zynthian_engine_jalv.plugins_dict=json.load(f, object_pairs_hook=OrderedDict)
	return zynthian_engine_jalv.plugins_dict

#------------------------------------------------------------------------------
# Jalv Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_jalv(zynthian_engine):

	#------------------------------------------------------------------------------
	# Plugin List
	#------------------------------------------------------------------------------

	JALV_LV2_CONFIG_FILE = "{}/jalv_plugins.json".format(os.environ.get('ZYNTHIAN_CONFIG_DIR','/zynthian/config'))

	plugins_dict = OrderedDict([
		("Dexed", {'TYPE': "MIDI Synth",'URL': "https://github.com/dcoredump/dexed.lv2"}),
		("Helm", {'TYPE': "MIDI Synth",'URL': "http://tytel.org/helm"}),
		("MDA ePiano", {'TYPE': "MIDI Synth",'URL': "http://moddevices.com/plugins/mda/EPiano"}),
		("MDA Piano", {'TYPE': "MIDI Synth",'URL': "http://moddevices.com/plugins/mda/Piano"}),
		("MDA JX10", {'TYPE': "MIDI Synth",'URL': "http://moddevices.com/plugins/mda/JX10"}),
		("MDA DX10", {'TYPE': "MIDI Synth",'URL': "http://moddevices.com/plugins/mda/DX10"}),
		("OBXD", {'TYPE': "MIDI Synth",'URL': "https://obxd.wordpress.com"}),
		("SynthV1", {'TYPE': "MIDI Synth",'URL': "http://synthv1.sourceforge.net/lv2"}),
		("Noize Mak3r", {'TYPE': "MIDI Synth",'URL': "http://kunz.corrupt.ch/products/tal-noisemaker"})
	])

	# ---------------------------------------------------------------------------
	# Controllers & Screens
	# ---------------------------------------------------------------------------

	plugin_ctrl_info = {
		"Dexed": {
		},
		"Helm": {
		},
		"MDA DX10": {
			"ctrls": [
				['volume',7,96],
				['mod-wheel',1,0],
				['sustain on/off',64,'off','off|on']
			],
			"ctrl_screens": [['MIDI Controllers',['volume','mod-wheel','sustain on/off']]]
		},
		"MDA JX10": {
			"ctrls": [
				['volume',7,96],
				['mod-wheel',1,0],
			],
			"ctrl_screens": [['MIDI Controllers',['volume','mod-wheel']]]
		},
		"MDA ePiano": {
			"ctrls": [
				['volume',7,96],
				['mod-wheel',1,0],
				['sustain on/off',64,'off','off|on']
			],
			"ctrl_screens": [['MIDI Controllers',['volume','mod-wheel','sustain on/off']]]
		},
		"MDA Piano": {
			"ctrls": [
				['volume',7,96],
				['mod-wheel',1,0],
				['sustain on/off',64,'off','off|on']
			],
			"ctrl_screens": [['MIDI Controllers',['volume','mod-wheel','sustain on/off']]]
		},
		"Noize Mak3r": {
		},
		"Obxd": {
		},
		"synthv1": {
		}
	}

	_ctrls=None
	_ctrl_screens=None

	#----------------------------------------------------------------------------
	# Initialization
	#----------------------------------------------------------------------------

	def __init__(self, plugin_name, zyngui=None):
		super().__init__(zyngui)

		self.type = self.plugins_dict[plugin_name]['TYPE']
		self.name = "Jalv/" + plugin_name
		self.nickname = "JV/" + plugin_name

		self.plugin_name = plugin_name
		self.plugin_url = self.plugins_dict[plugin_name]['URL']

		if self.config_remote_display():
			self.command = ("/usr/local/bin/jalv {}".format(self.plugin_url))		#TODO => Is possible to run plugins UI?
		else:
			self.command = ("/usr/local/bin/jalv {}".format(self.plugin_url))

		self.learned_cc = [[None for c in range(128)] for chan in range(16)]
		self.learned_zctrls = {}
		self.current_learning_zctrl = None

		output = self.start()

		# Get Plugin & Jack names from Jalv starting text ...
		self.jackname = None
		if output:
			for line in output.split("\n"):
				if line[0:15]=="JACK Real Name:":
					self.jackname = line[16:].strip()
					logging.debug("Jack Name => {}".format(self.jackname))
					break
				elif line[0:10]=="JACK Name:":
					self.plugin_name = line[11:].strip()
					logging.debug("Plugin Name => {}".format(self.plugin_name))

		# Set static MIDI Controllers from hardcoded plugin info
		try:
			self._ctrls = self.plugin_ctrl_info[self.plugin_name]['ctrls']
			self._ctrl_screens = self.plugin_ctrl_info[self.plugin_name]['ctrl_screens']
		except:
			logging.info("No defined MIDI controllers for '{}'.")

		# Generate LV2-Plugin Controllers
		self.lv2_zctrl_dict = self.get_lv2_controllers_dict()
		self.generate_ctrl_screens(self.lv2_zctrl_dict)

		# Get preset list from plugin host
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
				self.proc.delaybeforesend = 0
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
				#logging.debug("proc command: "+cmd)
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
					self.lv2_zctrl_dict[parts[0]]._set_value(float(parts[1]))
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

	def get_lv2_controllers_dict(self):
		self.start_loading()
		logging.info("Getting Controller List from LV2 Plugin ...")
		output=self.proc_cmd("\info_controls")
		zctrls=OrderedDict()
		for line in output.split("\n"):
			parts=line.split(" => ")
			if len(parts)==2:
				symbol=parts[0]
				try:
					info=json.JSONDecoder().decode(parts[1])

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
									'value_max': 1,
									'is_toggle': True,
									'is_integer': True
								})
							else:
								zctrls[symbol]=zynthian_controller(self,symbol,info['label'],{
									'graph_path': info['index'],
									'value': int(info['value']),
									'value_default': int(info['default']),
									'value_min': int(info['min']),
									'value_max': int(info['max']),
									'is_integer': True
								})
						else:
								zctrls[symbol]=zynthian_controller(self,symbol,info['label'],{
									'graph_path': info['index'],
									'value': info['value'],
									'value_default': info['default'],
									'value_min': info['min'],
									'value_max': info['max'],
								})

				#If control info is not OK
				except Exception as e:
					logging.error(e)

		self.stop_loading()
		return zctrls


	def generate_ctrl_screens(self, zctrl_dict=None):
		if zctrl_dict is None:
			zctrl_dict=self.zctrl_dict

		if self._ctrl_screens is None:
			self._ctrl_screens=[]

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
		# Get plugin static controllers
		zctrls=super().get_controllers_dict(layer)
		# Add plugin native controllers
		zctrls.update(self.lv2_zctrl_dict)
		return zctrls


	def send_controller_value(self, zctrl):
		self.proc_cmd("\set_control %d, %.6f" % (zctrl.graph_path, zctrl.value))

	#----------------------------------------------------------------------------
	# MIDI learning
	#----------------------------------------------------------------------------

	def midi_learn(self, zctrl):
		if zctrl.graph_path:
			# Set current learning zctrl
			logging.info("Learning '{}' ({}) ...".format(zctrl.symbol,zctrl.graph_path))
			self.current_learning_zctrl = zctrl


	def midi_unlearn(self, zctrl):
		if zctrl.graph_path in self.learned_zctrls:
			logging.info("Unlearning '{}' ...".format(zctrl.symbol))
			try:
				self.learned_cc[zctrl.midi_learn_chan][zctrl.midi_learn_cc] = None
				del self.learned_zctrls[zctrl.graph_path]
				return True
			except Exception as e:
				logging.warning("Can't Unlearn => {}".format(e))


	def set_midi_learn(self, zctrl):
		try:
			if zctrl.graph_path and zctrl.midi_learn_chan is not None and zctrl.midi_learn_cc is not None:
				logging.info("Learned '%s' => %d, %d" % (zctrl.symbol, zctrl.midi_learn_chan, zctrl.midi_learn_cc))
				# Clean current binding if any ...
				try:
					self.learned_cc[zctrl.midi_learn_chan][zctrl.midi_learn_cc].midi_unlearn()
				except:
					pass
				# Add midi learning info
				self.learned_zctrls[zctrl.graph_path] = zctrl
				self.learned_cc[zctrl.midi_learn_chan][zctrl.midi_learn_cc] = zctrl
				# Clean current learning zctrl
				self.current_learning_zctrl = None
		except Exception as e:
			logging.error("Can't learn %s => %s" % (zctrl.graph_path, e))


	def reset_midi_learn(self):
		logging.info("Reset MIDI-learn ...")
		self.current_learning_zctrl = None
		self.learned_zctrls = {}
		self.learned_cc = [[None for chan in range(16)] for cc in range(128)]


	def midi_control_change(self, chan, ccnum, val):
		if self.current_learning_zctrl:
			self.current_learning_zctrl.set_midi_learn(chan, ccnum)
		else:
			try:
				self.learned_cc[chan][ccnum].midi_control_change(val)
			except:
				pass



	#--------------------------------------------------------------------------
	# Special
	#--------------------------------------------------------------------------

	# ---------------------------------------------------------------------------
	# Layer "Path" String
	# ---------------------------------------------------------------------------

	def get_path(self, layer):
		path=self.nickname
		return path


#******************************************************************************
