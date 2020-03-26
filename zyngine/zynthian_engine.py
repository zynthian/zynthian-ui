# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine)
# 
# zynthian_engine is the base class for the Zynthian Synth Engine
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

#import sys
import os
import copy
import json
import liblo
import logging
import pexpect
from time import sleep
from os.path import isfile, isdir, join
from string import Template
from collections import OrderedDict

from . import zynthian_controller

#--------------------------------------------------------------------------------
# Basic Engine Class: Spawn a proccess & manage IPC communication using pexpect
#--------------------------------------------------------------------------------

class zynthian_basic_engine:

	# ---------------------------------------------------------------------------
	# Data dirs 
	# ---------------------------------------------------------------------------

	config_dir = os.environ.get('ZYNTHIAN_CONFIG_DIR',"/zynthian/config")
	data_dir = os.environ.get('ZYNTHIAN_DATA_DIR',"/zynthian/zynthian-data")
	my_data_dir = os.environ.get('ZYNTHIAN_MY_DATA_DIR',"/zynthian/zynthian-my-data")
	ex_data_dir = os.environ.get('ZYNTHIAN_EX_DATA_DIR',"/media/usb0")

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------

	def __init__(self, name=None, command=None, prompt=None):
		self.name = name

		self.proc = None
		self.proc_timeout = 20
		self.proc_start_sleep = None
		self.command = command
		self.command_env = None
		self.command_prompt = prompt


	def __del__(self):
		self.stop()


	# ---------------------------------------------------------------------------
	# Subproccess Management & IPC
	# ---------------------------------------------------------------------------

	def start(self):
		if not self.proc:
			logging.info("Starting Engine {}".format(self.name))
			try:

				logging.debug("Command: {}".format(self.command))
				if self.command_env:
					self.proc=pexpect.spawn(self.command, timeout=self.proc_timeout, env=self.command_env)
				else:
					self.proc=pexpect.spawn(self.command, timeout=self.proc_timeout)

				self.proc.delaybeforesend = 0

				output = self.proc_get_output()

				if self.proc_start_sleep:
					sleep(self.proc_start_sleep)

				return output

			except Exception as err:
				logging.error("Can't start engine {} => {}".format(self.name, err))


	def stop(self):
		if self.proc:
			try:
				logging.info("Stoping Engine " + self.name)
				self.proc.terminate()
				sleep(0.2)
				self.proc.terminate(True)
				self.proc=None
			except Exception as err:
				logging.error("Can't stop engine {} => {}".format(self.name, err))


	def proc_get_output(self):
		if self.command_prompt:
			self.proc.expect(self.command_prompt)
			return self.proc.before.decode()
		else:
			logging.warning("Command Prompt is not defined!")
			return None


	def proc_cmd(self, cmd):
		if self.proc:
			try:
				#logging.debug("proc command: "+cmd)
				self.proc.sendline(cmd)
				out=self.proc_get_output()
				#logging.debug("proc output:\n{}".format(out))
			except Exception as err:
				out=""
				logging.error("Can't exec engine command: {} => {}".format(cmd, err))
			return out


#------------------------------------------------------------------------------
# Synth Engine Base Class
#------------------------------------------------------------------------------

class zynthian_engine(zynthian_basic_engine):

	# ---------------------------------------------------------------------------
	# Default Controllers & Screens
	# ---------------------------------------------------------------------------

	# Standard MIDI Controllers
	_ctrls=[
		['volume',7,96],
		['modulation',1,0],
		['pan',10,64],
		['sustain',64,'off',['off','on']]
	]

	# Controller Screens
	_ctrl_screens=[
		['main',['volume','modulation','pan','sustain']]
	]

	# ---------------------------------------------------------------------------
	# Config variables
	# ---------------------------------------------------------------------------

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__()

		self.zyngui=zyngui

		self.type = "MIDI Synth"
		self.nickname = ""
		self.jackname = ""

		self.loading = 0
		self.layers = []

		self.options = {
			'clone': True,
			'transpose': True,
			'audio_route': True,
			'midi_chan': True
		}

		self.osc_target = None
		self.osc_target_port = None
		self.osc_server = None
		self.osc_server_port = None
		self.osc_server_url = None

		self.preset_favs = None
		self.preset_favs_fpath = None


	def __del__(self):
		self.stop()

	def reset(self):
		#Reset Vars
		self.loading=0
		self.loading_snapshot=False
		#TODO: OSC, IPC, ...

	def config_remote_display(self):
		fvars={}
		if os.environ.get('ZYNTHIANX'):
			fvars['DISPLAY']=os.environ.get('ZYNTHIANX')
		else:
			try:
				with open("/root/.remote_display_env","r") as fh:
					lines = fh.readlines()
					for line in lines:
						parts=line.strip().split('=')
						if len(parts)>=2 and parts[1]: fvars[parts[0]]=parts[1]
			except:
				fvars['DISPLAY']=""
		if 'DISPLAY' not in fvars or not fvars['DISPLAY']:
			logging.info("NO REMOTE DISPLAY")
			return False
		else:
			logging.info("REMOTE DISPLAY: %s" % fvars['DISPLAY'])
			self.command_env=os.environ.copy()
			for f,v in fvars.items():
				self.command_env[f]=v
			return True

	# ---------------------------------------------------------------------------
	# Loading GUI signalization
	# ---------------------------------------------------------------------------

	def start_loading(self):
		self.loading=self.loading+1
		if self.loading<1: self.loading=1
		if self.zyngui:
			self.zyngui.start_loading()

	def stop_loading(self):
		self.loading=self.loading-1
		if self.loading<0: self.loading=0
		if self.zyngui:
			self.zyngui.stop_loading()

	def reset_loading(self):
		self.loading=0
		if self.zyngui:
			self.zyngui.stop_loading()

	# ---------------------------------------------------------------------------
	# Refresh Management
	# ---------------------------------------------------------------------------

	def refresh_all(self, refresh=True):
		for layer in self.layers:
			layer.refresh_flag=refresh

	# ---------------------------------------------------------------------------
	# OSC Management
	# ---------------------------------------------------------------------------

	def osc_init(self, target_port=None, proto=liblo.UDP):
		if target_port:
			self.osc_target_port=target_port
		try:
			self.osc_target=liblo.Address('localhost',self.osc_target_port,proto)
			logging.info("OSC target in port %s" % str(self.osc_target_port))
			self.osc_server=liblo.ServerThread(None,proto)
			self.osc_server_port=self.osc_server.get_port()
			self.osc_server_url=liblo.Address('localhost',self.osc_server_port,proto).get_url()
			logging.info("OSC server running in port %s" % str(self.osc_server_port))
			self.osc_add_methods()
			self.osc_server.start()
		except liblo.AddressError as err:
			logging.error("OSC Server can't be initialized (%s). Running without OSC feedback." % err)


	def osc_end(self):
		if self.osc_server:
			try:
				#self.osc_server.stop()
				logging.info("OSC server stopped")
			except Exception as err:
				logging.error("Can't stop OSC server => %s" % err)


	def osc_add_methods(self):
		self.osc_server.add_method(None, None, self.cb_osc_all)


	def cb_osc_all(self, path, args, types, src):
		logging.info("OSC MESSAGE '%s' from '%s'" % (path, src.url))
		for a, t in zip(args, types):
			logging.debug("argument of type '%s': %s" % (t, a))


	# ---------------------------------------------------------------------------
	# Generating list from different sources
	# ---------------------------------------------------------------------------

	@staticmethod
	def get_filelist(dpath, fext):
		res=[]
		if isinstance(dpath, str): dpath=[('_', dpath)]
		fext='.'+fext
		xlen=len(fext)
		i=0
		for dpd in dpath:
			dp=dpd[1]
			dn=dpd[0]
			try:
				for f in sorted(os.listdir(dp)):
					if not f.startswith('.') and isfile(join(dp,f)) and f[-xlen:].lower()==fext:
						title=str.replace(f[:-xlen], '_', ' ')
						if dn!='_': title=dn+'/'+title
						#print("filelist => "+title)
						res.append([join(dp,f),i,title,dn,f])
						i=i+1
			except:
				pass

		return res


	@staticmethod
	def get_dirlist(dpath, exclude_empty=True):
		res=[]
		if isinstance(dpath, str): dpath=[('_', dpath)]
		i=0
		for dpd in dpath:
			dp=dpd[1]
			dn=dpd[0]
			try:
				for f in sorted(os.listdir(dp)):
					if exclude_empty and next(os.scandir(join(dp,f)), None) is None:
						continue
					if not f.startswith('.') and isdir(join(dp,f)):
						title,ext=os.path.splitext(f)
						title=str.replace(title, '_', ' ')
						if dn!='_': title=dn+'/'+title
						#print("dirlist => "+title)
						res.append([join(dp,f),i,title,dn,f])
						i=i+1
			except:
				pass

		return res


	@staticmethod
	def get_cmdlist(cmd):
		res=[]
		i=0
		output=check_output(cmd, shell=True)
		lines=output.decode('utf8').split('\n')
		for f in lines:
			title=str.replace(f, '_', ' ')
			res.append([f,i,title])
			i=i+1
		return res


	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------

	def add_layer(self, layer):
		self.layers.append(layer)
		layer.jackname = self.jackname


	def del_layer(self, layer):
		self.layers.remove(layer)
		layer.jackname = None


	def del_all_layers(self):
		for layer in self.layers:
			self.del_layer(layer)


	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	def set_midi_chan(self, layer):
		pass


	def get_active_midi_channels(self):
		chans=[]
		for layer in self.layers:
			if layer.midi_chan is None:
				return None
			elif layer.midi_chan>=0 and layer.midi_chan<=15:
				chans.append(layer.midi_chan)
		return chans


	# ---------------------------------------------------------------------------
	# Bank Management
	# ---------------------------------------------------------------------------


	def get_bank_list(self, layer=None):
		logging.info('Getting Bank List for %s: NOT IMPLEMENTED!' % self.name)


	def set_bank(self, layer, bank):
		self.zyngui.zynmidi.set_midi_bank_msb(layer.get_midi_chan(), bank[1])
		return True


	# ---------------------------------------------------------------------------
	# Preset Management
	# ---------------------------------------------------------------------------

	def get_preset_list(self, bank):
		logging.info('Getting Preset List for %s: NOT IMPLEMENTED!' % self.name),'PD'


	def set_preset(self, layer, preset, preload=False):
		if isinstance(preset[1],int):
			self.zyngui.zynmidi.set_midi_prg(layer.get_midi_chan(), preset[1])
		else:
			self.zyngui.zynmidi.set_midi_preset(layer.get_midi_chan(), preset[1][0], preset[1][1], preset[1][2])
		return True


	def cmp_presets(self, preset1, preset2):
		try:
			if preset1[1][0]==preset2[1][0] and preset1[1][1]==preset2[1][1] and preset1[1][2]==preset2[1][2]:
				return True
			else:
				return False
		except:
			return False


	# ---------------------------------------------------------------------------
	# Preset Favorites Management
	# ---------------------------------------------------------------------------

	def toggle_preset_fav(self, layer, preset):
		if self.preset_favs is None:
			self.load_preset_favs()

		try:
			del self.preset_favs[preset[0]]
			fav_status = False
		except:
			self.preset_favs[preset[0]]=[layer.bank_info, preset]
			fav_status = True

		try:
			with open(self.preset_favs_fpath, 'w') as f:
				json.dump(self.preset_favs, f)
		except Exception as e:
			logging.error("Can't save preset favorites! => {}".format(e))

		return fav_status


	def get_preset_favs(self, layer):
		if self.preset_favs is None:
			self.load_preset_favs()

		return self.preset_favs


	def is_preset_fav(self, preset):
		if self.preset_favs is None:
			self.load_preset_favs()

		if preset[0] in [item[1][0] for item in self.preset_favs.values()]:
			return True
		else:
			return False


	def load_preset_favs(self):
		if self.nickname:
			fname = self.nickname.replace("/","_")
			self.preset_favs_fpath = self.my_data_dir + "/preset-favorites/" + fname + ".json"

			try:
				with open(self.preset_favs_fpath) as f:
					self.preset_favs = json.load(f, object_pairs_hook=OrderedDict)
			except:
				self.preset_favs = OrderedDict()

		else:
			logging.warning("Can't load preset favorites until the engine have a nickname!")


	# ---------------------------------------------------------------------------
	# Controllers Management
	# ---------------------------------------------------------------------------

	# Get zynthian controllers dictionary:
	# + Default implementation uses a static controller definition array
	def get_controllers_dict(self, layer):
		midich=layer.get_midi_chan()
		zctrls=OrderedDict()

		if self._ctrls is not None:
			for ctrl in self._ctrls:
				options={}

				#OSC control =>
				if isinstance(ctrl[1],str):
					#replace variables ...
					tpl=Template(ctrl[1])
					cc=tpl.safe_substitute(ch=midich)
					try:
						cc=tpl.safe_substitute(i=layer.part_i)
					except:
						pass
					#set osc_port option ...
					if self.osc_target_port>0:
						options['osc_port']=self.osc_target_port
					#debug message
					logging.debug('CONTROLLER %s OSC PATH => %s' % (ctrl[0],cc))
				#MIDI Control =>
				else:
					cc=ctrl[1]

				#Build controller depending on array length ...
				if len(ctrl)>4:
					if isinstance(ctrl[4],str):
						zctrl=zynthian_controller(self,ctrl[4],ctrl[0])
					else:
						zctrl=zynthian_controller(self,ctrl[0])
						zctrl.graph_path=ctrl[4]
					zctrl.setup_controller(midich,cc,ctrl[2],ctrl[3])
				elif len(ctrl)>3:
					zctrl=zynthian_controller(self,ctrl[0])
					zctrl.setup_controller(midich,cc,ctrl[2],ctrl[3])
				else:
					zctrl=zynthian_controller(self,ctrl[0])
					zctrl.setup_controller(midich,cc,ctrl[2])

				#Set controller extra options
				if len(options)>0:
					zctrl.set_options(options)

				zctrls[zctrl.symbol]=zctrl
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
					#logging.debug("ADDING CONTROLLER SCREEN {}#{}".format(self.nickname,c))
					self._ctrl_screens.append(["{}#{}".format(self.nickname,c),ctrl_set])
					ctrl_set=[]
					c=c+1
			except Exception as err:
				logging.error("Generating Controller Screens => {}".format(err))

		if len(ctrl_set)>=1:
			#logging.debug("ADDING CONTROLLER SCREEN #"+str(c))
			self._ctrl_screens.append(["{}#{}".format(self.nickname,c),ctrl_set])


	def send_controller_value(self, zctrl):
		raise Exception("NOT IMPLEMENTED!")


	# ---------------------------------------------------------------------------
	# MIDI Learn
	# ---------------------------------------------------------------------------

	def midi_learn(self, zctrl):
		raise Exception("NOT IMPLEMENTED!")


	def midi_unlearn(self, zctrl):
		raise Exception("NOT IMPLEMENTED!")


	def set_midi_learn(self, zctrl):
		raise Exception("NOT IMPLEMENTED!")


	def reset_midi_learn(self):
		raise Exception("NOT IMPLEMENTED!")


	#----------------------------------------------------------------------------
	# MIDI CC processing
	#----------------------------------------------------------------------------

	def midi_control_change(self, chan, ccnum, val):
		raise Exception("NOT IMPLEMENTED!")


	def midi_zctrl_change(self, zctrl, val):
		try:
			if val!=zctrl.get_value():
				zctrl.set_value(val)
				#logging.debug("MIDI CC {} -> '{}' = {}".format(zctrl.midi_cc, zctrl.name, val))

				#Refresh GUI controller in screen when needed ...
				if self.zyngui.active_screen=='control' and self.zyngui.screens['control'].mode=='control':
					self.zyngui.screens['control'].set_controller_value(zctrl)

		except Exception as e:
			logging.debug(e)


	# ---------------------------------------------------------------------------
	# Layer "Path" String
	# ---------------------------------------------------------------------------

	def get_path(self, layer):
		return self.nickname


	# ---------------------------------------------------------------------------
	# Options and Extended Config
	# ---------------------------------------------------------------------------

	def get_options(self):
		return self.options


	def get_extended_config(self):
		return None


	def set_extended_config(self, xconfig):
		pass

	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

	@classmethod
	def get_zynapi_methods(cls):
		return [f for f in dir(cls) if f.startswith('zynapi_')]
		#callable(f) and


#******************************************************************************
