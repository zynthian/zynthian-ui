# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_linuxsampler)
# 
# zynthian_engine implementation for Linux Sampler
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
import logging
from time import sleep
from os.path import isfile, isdir
from subprocess import check_output
from collections import OrderedDict
from . import zynthian_engine
from . import zynthian_controller

#------------------------------------------------------------------------------
# Linuxsampler Exception Classes
#------------------------------------------------------------------------------

class zyngine_lscp_error(Exception): pass
class zyngine_lscp_warning(Exception): pass

#------------------------------------------------------------------------------
# Linuxsampler Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_linuxsampler(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Controllers & Screens
	# ---------------------------------------------------------------------------

	# Controller Screens
	_ctrl_screens=[
		['main',['volume','FX send','pan','sustain']]
	]

	# ---------------------------------------------------------------------------
	# LADSPA plugins
	# ---------------------------------------------------------------------------

	_ladspa_plugins=[
		('tap_chorusflanger', { 'lib': '/usr/lib/ladspa/tap_chorusflanger.so', 'id': None }),
		#('mod_delay', { 'lib': '/usr/lib/ladspa/mod_delay_1419.so', 'id': None }) => BAD
		#('revdelay', { 'lib': '/usr/lib/ladspa/revdelay_1605.so', 'id': None }), => BAD
		#('vocoder', { 'lib': '/usr/lib/ladspa/vocoder.so', 'id': None }),
		#('g2reverb', { 'lib': '/usr/lib/ladspa/g2reverb.so', 'id': None }),
		#('tap_vibrato', { 'lib': '/usr/lib/ladspa/tap_vibrato.so', 'id': None }), => BAD 
		#('tap_tremolo', { 'lib': '/usr/lib/ladspa/tap_tremolo.so', 'id': None }), => BAD
		#('caps', { 'lib': '/usr/lib/ladspa/caps.so', 'id': None }), => BAD
		#('rubberband', { 'lib': '/usr/lib/ladspa/ladspa-rubberband.so', 'id': None }), => BAD
		('tap_reverb', { 'lib': '/usr/lib/ladspa/tap_reverb.so', 'id': None }),
		#('tap_echo', { 'lib': '/usr/lib/ladspa/tap_echo.so', 'id': None })
	]

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__(zyngui)
		self.name="LinuxSampler"
		self.nickname="LS"

		self.sock=None
		self.port=6688
		self.command=("linuxsampler", "--lscp-port", str(self.port))
		#os.environ["LADSPA_PATH"]="/usr/lib/ladspa"

		self.ls_chans={}
		self.ls_effects=OrderedDict(self._ladspa_plugins)

		self.lscp_dir="./data/lscp"
		self.bank_dirs=[
			('SFZ', os.getcwd()+"/data/soundfonts/sfz"),
			('GIG', os.getcwd()+"/data/soundfonts/gig"),
			('MySFZ', os.getcwd()+"/my-data/soundfonts/sfz"),
			('MyGIG', os.getcwd()+"/my-data/soundfonts/gig")
		]
		self.lscp_v1_6_supported=False
		self.start()
		self.lscp_connect()
		self.lscp_get_version()
		self.reset()

	def reset(self):
		super().reset()
		self.ls_chans={}
		self.ls_init()

	# ---------------------------------------------------------------------------
	# Subproccess Management & IPC
	# ---------------------------------------------------------------------------

	def lscp_connect(self):
		logging.info("Connecting with LinuxSampler Server...")
		self.sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
		self.sock.setblocking(0)
		self.sock.settimeout(1)
		i=0
		while i<20:
			try:
				self.sock.connect(("127.0.0.1",self.port))
				break
			except:
				sleep(0.25)
				i+=1
		return self.sock

	def lscp_get_version(self):
		sv_info=self.lscp_send_multi("GET SERVER INFO")
		if 'PROTOCOL_VERSION' in sv_info:
			match=re.match(r"(?P<major>\d+)\.(?P<minor>\d+).*",sv_info['PROTOCOL_VERSION'])
			if match:
				version_major=int(match['major'])
				version_minor=int(match['minor'])
				if version_major>1 or (version_major==1 and version_minor>=6):
					self.lscp_v1_6_supported=True

	def lscp_send(self,data):
		command=command+"\r\n"
		try:
			self.sock.send(data.encode())
		except Exception as err:
			logging.error("FAILED lscp_send: %s" % err)

	def lscp_get_result_index(self, result):
		parts=result.split('[')
		if len(parts)>1:
			parts=parts[1].split(']')
			return int(parts[0])

	def lscp_send_single(self, command):
		self.start_loading()
		#logging.debug("LSCP SEND => %s" % command)
		command=command+"\r\n"
		try:
			self.sock.send(command.encode())
			line=self.sock.recv(4096)
		except Exception as err:
			logging.error("FAILED lscp_send_single(%s): %s" % (command,err))
			self.stop_loading()
			return None
		line=line.decode()
		#logging.debug("LSCP RECEIVE => %s" % line)
		if line[0:2]=="OK":
			result=self.lscp_get_result_index(line)
		elif line[0:3]=="ERR":
			parts=line.split(':')
			self.stop_loading()
			raise zyngine_lscp_error("%s (%s)" % (parts[1],parts[0]))
		elif line[0:3]=="WRN":
			parts=line.split(':')
			self.stop_loading()
			raise zyngine_lscp_warning("%s (%s)" % (parts[1],parts[0]))
		self.stop_loading()
		return result

	def lscp_send_multi(self, command):
		self.start_loading()
		#logging.debug("LSCP SEND => %s" % command)
		command=command+"\r\n"
		try:
			self.sock.send(command.encode())
			result=self.sock.recv(4096)
		except Exception as err:
			logging.error("FAILED lscp_send_multi(%s): %s" % (command,err))
			self.stop_loading()
			return None
		lines=result.decode().split("\r\n")
		result=OrderedDict()
		for line in lines:
			#logging.debug("LSCP RECEIVE => %s" % line)
			if line[0:2]=="OK":
				result=self.lscp_get_result_index(line)
			elif line[0:3]=="ERR":
				parts=line.split(':')
				self.stop_loading()
				raise zyngine_lscp_error("%s (%s)" % (parts[1],parts[0]))
			elif line[0:3]=="WRN":
				parts=line.split(':')
				self.stop_loading()
				raise zyngine_lscp_warning("%s (%s)" % (parts[1],parts[0]))
			elif len(line)>3:
				parts=line.split(':')
				result[parts[0]]=parts[1]
		self.stop_loading()
		return result

	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------

	def add_layer(self, layer):
		super().add_layer(layer)
		self.ls_set_channel(layer)
		self.set_midi_chan(layer)
		layer.refresh_flag=True

	def del_layer(self, layer):
		super().del_layer(layer)
		self.ls_unset_channel(layer)

	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	def set_midi_chan(self, layer):
		if layer.ls_chan_info:
			ls_chan_id=layer.ls_chan_info['chan_id']
			self.lscp_send_single("SET CHANNEL MIDI_INPUT_CHANNEL %d %d" % (ls_chan_id,layer.get_midi_chan()))

	# ---------------------------------------------------------------------------
	# Bank Management
	# ---------------------------------------------------------------------------

	def get_bank_list(self, layer=None):
		return self.get_dirlist(self.bank_dirs)

	def set_bank(self, layer, bank):
		pass

	# ---------------------------------------------------------------------------
	# Preset Management
	# ---------------------------------------------------------------------------

	_exclude_sfz = re.compile(r"[MOPRSTV][1-9]?l?\.sfz")

	def get_preset_list(self, bank):
		self.start_loading()
		logging.info("Getting Preset List for %s" % bank[2])
		i=0
		preset_list=[]
		preset_dpath=bank[0]
		if os.path.isdir(preset_dpath):
			cmd="find '"+preset_dpath+"' -maxdepth 2 -type f -name '*.sfz'"
			output=check_output(cmd, shell=True).decode('utf8')
			cmd="find '"+preset_dpath+"' -maxdepth 2 -type f -name '*.gig'"
			output=output+"\n"+check_output(cmd, shell=True).decode('utf8')
			lines=output.split('\n')
			for f in lines:
				if f:
					filehead,filetail=os.path.split(f)
					if not self._exclude_sfz.fullmatch(filetail):
						filename,filext=os.path.splitext(f)
						title=filename[len(preset_dpath)+1:].replace('_', ' ')
						engine=filext[1:].lower()
						preset_list.append((i,[0,0,0],title,f,engine))
						i=i+1
		self.stop_loading()
		return preset_list

	def set_preset(self, layer, preset):
		self.ls_set_preset(layer, preset[4], preset[3])

	# ---------------------------------------------------------------------------
	# Controllers Management
	# ---------------------------------------------------------------------------

	# Get zynthian controllers dictionary:
	def get_controllers_dict(self, layer):
		#Get default static controllers
		zctrls=super().get_controllers_dict(layer)
		#Add specific controllers
		if layer.ls_chan_info:
			for fx_name,fx_info in list(layer.ls_chan_info['fx_instances'].items()):
				scrctrls=[]
				j=1
				for i,ctrl_info in enumerate(fx_info['controls']):
					desc=ctrl_info['DESCRIPTION'].strip()
					parts=desc.split(' [')
					ctrl_symbol=fx_name+'/'+parts[0]
					ctrl_name=parts[0]
					if len(parts)>1:
						sparts=parts[1].split(']')
						unit=sparts[0]
					else:
						unit=None
					logging.debug("CTRL %s => %s" % (desc,unit))
					if 'VALUE' in ctrl_info:
						value=float(ctrl_info['VALUE'])
					else:
						value=0
					if 'RANGE_MIN' in ctrl_info:
						range_min=float(ctrl_info['RANGE_MIN'])
					else:
						if unit=='dB':
							range_min=-30
						elif unit=='ms':
							range_min=0
						elif unit=='Hz':
							range_min=0
						elif unit=='Hz':
							range_min=0
						elif unit=='%':
							range_min=0
						else:
							range_min=0
					if 'RANGE_MAX' in ctrl_info:
						range_max=float(ctrl_info['RANGE_MAX'])
					else:
						if unit=='dB':
							range_max=-range_min
						elif unit=='ms':
							range_max=19999
						elif unit=='Hz':
							range_max=19999
						elif unit=='deg':
							range_max=180
						elif unit=='%':
							range_max=100
						else:
							range_max=127
					ctrl_options={
						'value': int(value),
						'value_default': int(value),
						'value_min': int(range_min),
						'value_max': int(range_max),
						'graph_path': str(fx_info['id'])+'/'+str(i)
					}
					zctrls[ctrl_symbol]=zynthian_controller(self,ctrl_symbol,ctrl_name,ctrl_options)
					if len(scrctrls)==4:
						self._ctrl_screens.append([fx_name+':'+str(j),scrctrls])
						scrctrls=[]
						j=j+1
					scrctrls.append(ctrl_symbol)
				self._ctrl_screens.append([fx_name+':'+str(j),scrctrls])
		return zctrls

	def send_controller_value(self, zctrl):
		if zctrl.graph_path:
			parts=zctrl.graph_path.split('/')
			fx_id=parts[0]
			fx_ctrl_i=parts[1]
			logging.debug("LSCP: Sending controller %s => %s" % (zctrl.name,zctrl.value))
			self.lscp_send_single("SET EFFECT_INSTANCE_INPUT_CONTROL VALUE %s %s %s" % (fx_id,fx_ctrl_i,zctrl.value))
		else:
			super.send_controller_value(zctrl)

	# ---------------------------------------------------------------------------
	# Specific functions
	# ---------------------------------------------------------------------------

	def ls_init(self):
		# Reset
		self.lscp_send_single("RESET")

		# Config Audio JACK Device 0
		self.ls_audio_device_id=self.lscp_send_single("CREATE AUDIO_OUTPUT_DEVICE JACK ACTIVE='true' CHANNELS='2' NAME='LinuxSampler' SAMPLERATE='44100'")
		self.lscp_send_single("SET AUDIO_OUTPUT_CHANNEL_PARAMETER %s 0 NAME='Channel 1'" % self.ls_audio_device_id)
		self.lscp_send_single("SET AUDIO_OUTPUT_CHANNEL_PARAMETER %s 1 NAME='Channel 2'" % self.ls_audio_device_id)
		self.lscp_send_single("SET AUDIO_OUTPUT_CHANNEL_PARAMETER %s 0 JACK_BINDINGS='system:playback_1'" % self.ls_audio_device_id)
		self.lscp_send_single("SET AUDIO_OUTPUT_CHANNEL_PARAMETER %s 1 JACK_BINDINGS='system:playback_2'" % self.ls_audio_device_id)
		#self.lscp_send_single("SET AUDIO_OUTPUT_CHANNEL_PARAMETER %s 0 IS_MIX_CHANNEL='false'" % self.ls_audio_device_id)
		#self.lscp_send_single("SET AUDIO_OUTPUT_CHANNEL_PARAMETER %s 1 IS_MIX_CHANNEL='false'" % self.ls_audio_device_id)

		# Config MIDI JACK Device 1
		self.ls_midi_device_id=self.lscp_send_single("CREATE MIDI_INPUT_DEVICE JACK ACTIVE='true' NAME='LinuxSampler' PORTS='1'")
		#self.lscp_send_single("SET MIDI_INPUT_PORT_PARAMETER %s 0 JACK_BINDINGS=''" % self.ls_midi_device_id)
		#self.lscp_send_single("SET MIDI_INPUT_PORT_PARAMETER %s 0 NAME='midi_in_0'" % self.ls_midi_device_id)

		# Global volume level
		self.lscp_send_single("SET VOLUME 0.45")

	def ls_set_channel(self, layer):
		# Adding new channel
		ls_chan_id=self.lscp_send_single("ADD CHANNEL")
		if ls_chan_id>=0:
			self.lscp_send_single("SET CHANNEL AUDIO_OUTPUT_DEVICE %d %d" % (ls_chan_id,self.ls_audio_device_id))
			# Use "ADD CHANNEL MIDI_INPUT"
			if self.lscp_v1_6_supported:
				self.lscp_send_single("ADD CHANNEL MIDI_INPUT %d %d 0" % (ls_chan_id,self.ls_midi_device_id))
			else:
				self.lscp_send_single("SET CHANNEL MIDI_INPUT_DEVICE %d %d" % (ls_chan_id,self.ls_midi_device_id))
				self.lscp_send_single("SET CHANNEL MIDI_INPUT_PORT %d %d" % (ls_chan_id,0))

			#self.lscp_send_single("SET CHANNEL MIDI_INPUT_CHANNEL %d %d" % (ls_chan_id,layer.get_midi_chan()))

			#TODO: need?
			#self.lscp_send_single("SET CHANNEL AUDIO_OUTPUT_CHANNEL %d 0 0" % ls_chan_id)
			#self.lscp_send_single("SET CHANNEL AUDIO_OUTPUT_CHANNEL %d 1 1" % ls_chan_id)
			#self.lscp_send_single("SET CHANNEL VOLUME %d 1" % ls_chan_id)
			#self.lscp_send_single("SET CHANNEL MIDI_INSTRUMENT_MAP %d 0" % ls_chan_id)
			
			#Setup Effect Chain
			fx_chain_id=self.lscp_send_single("ADD SEND_EFFECT_CHAIN %d" % self.ls_audio_device_id)
			fx_instances={}
			for name,info in list(self.ls_effects.items()):
				try:
					fx_instance_id=self.lscp_send_single("CREATE EFFECT_INSTANCE LADSPA '%s' '%s'" % (info['lib'],name))
					self.lscp_send_single("APPEND SEND_EFFECT_CHAIN EFFECT %d %d %d" % (self.ls_audio_device_id,fx_chain_id,fx_instance_id))
					fx_info=self.lscp_send_multi("GET EFFECT_INSTANCE INFO %d" % fx_instance_id)
					fx_controls=[]
					try:
						n_controls=int(fx_info['INPUT_CONTROLS'])
						for i in range(n_controls):
							fx_controls.append(self.lscp_send_multi("GET EFFECT_INSTANCE_INPUT_CONTROL INFO %d %d" % (fx_instance_id,i)))
					except Exception as err:
						logging.error("Can't get effect info: %s" % err)
					fx_instances[name]={
						'id': fx_instance_id,
						'controls': fx_controls
					}
				except zyngine_lscp_error as err:
					logging.error(err)
				except zyngine_lscp_warning as warn:
					logging.warning(warn)

			#Save chan info in layer
			layer.ls_chan_info={
				'chan_id': ls_chan_id,
				'fx_chain_id': fx_chain_id,
				'fx_instances': fx_instances,
				'fx_send_id': None,
				'ls_engine': None
			}

	def ls_set_preset(self, layer, ls_engine, fpath):
		if layer.ls_chan_info:
			ls_chan_id=layer.ls_chan_info['chan_id']

			# Load engine and create FX Send if needed
			if ls_engine!=layer.ls_chan_info['ls_engine']:
				try:
					self.lscp_send_single("LOAD ENGINE %s %d" % (ls_engine,ls_chan_id))
					# Save engine to layer
					layer.ls_chan_info['ls_engine']=ls_engine
					# Recreate FX send after engine change
					if len(layer.ls_chan_info['fx_instances'])>0:
						fx_send_id=self.lscp_send_single("CREATE FX_SEND %d %d" % (ls_chan_id,12))
						self.lscp_send_single("SET FX_SEND EFFECT %d %d %d %d" % (ls_chan_id,fx_send_id,layer.ls_chan_info['fx_chain_id'],0))
						# Save FX send to layer
						layer.ls_chan_info['fx_send_id']=fx_send_id
				except zyngine_lscp_error as err:
					logging.error(err)
				except zyngine_lscp_warning as warn:
					logging.warning(warn)
			
			# Load instument
			try:
				self.sock.settimeout(5)
				self.lscp_send_single("LOAD INSTRUMENT '%s' 0 %d" % (fpath,ls_chan_id))
			except zyngine_lscp_error as err:
				logging.error(err)
			except zyngine_lscp_warning as warn:
				logging.warning(warn)
			self.sock.settimeout(1)

	def ls_unset_channel(self, layer):
		if layer.ls_chan_info:
			chan_id=layer.ls_chan_info['chan_id']
			fx_send_id=layer.ls_chan_info['fx_send_id']
			fx_chain_id=layer.ls_chan_info['fx_chain_id']
			self.lscp_send_single("RESET CHANNEL %d" % chan_id)
			# Remove sampler channel
			if self.lscp_v1_6_supported:
				self.lscp_send_single("REMOVE CHANNEL MIDI_INPUT %d" % chan_id)
			if fx_send_id:
				self.lscp_send_single("REMOVE FX_SEND EFFECT %d %d" % (chan_id,fx_send_id))
			self.lscp_send_single("REMOVE CHANNEL %d" % chan_id)

			# Remove FX instances from FX chain
			fx_len=len(layer.ls_chan_info['fx_instances'])
			for i in range(fx_len):
				try:
					self.lscp_send_single("REMOVE SEND_EFFECT_CHAIN EFFECT %d %d %d" % (self.ls_audio_device_id,fx_chain_id,fx_len-i-1))
				except:
					pass

			# Remove FX chain
			try:
				self.lscp_send_single("REMOVE SEND_EFFECT_CHAIN %d %d" % (self.ls_audio_device_id,fx_chain_id))
			except:
				pass

			# Destroy FX instances
			for name,fx_instance in list(layer.ls_chan_info['fx_instances'].items()):
				try:
					self.lscp_send_single("DESTROY EFFECT_INSTANCE %d" % fx_instance['id'])
				except:
					pass
			layer.ls_chan_info=None

#******************************************************************************
