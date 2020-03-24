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
import glob
import logging
import socket
import shutil
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

	# LS Hardcoded MIDI Controllers
	_ctrls=[
		['volume',7,96],
		['pan',10,64],
		['sustain',64,'off',['off','on']],
		['sostenuto',66,'off',['off','on']],
		['legato on/off',68,'off',['off','on']],
		['portamento on/off',65,'off',['off','on']],
		['portamento time-coarse',5,0],
		['portamento time-fine',37,0]
	]

	# Controller Screens
	_ctrl_screens=[
		['main',['volume','sostenuto','pan','sustain']],
		['portamento',['legato on/off','portamento on/off','portamento time-coarse','portamento time-fine']]
	]

	# ---------------------------------------------------------------------------
	# Config variables
	# ---------------------------------------------------------------------------

	lscp_port = 6688
	lscp_v1_6_supported=False

	bank_dirs = [
		('ExSFZ', zynthian_engine.ex_data_dir + "/soundfonts/sfz"),
		('ExGIG', zynthian_engine.ex_data_dir + "/soundfonts/gig"),
		('MySFZ', zynthian_engine.my_data_dir + "/soundfonts/sfz"),
		('MyGIG', zynthian_engine.my_data_dir + "/soundfonts/gig"),
		('SFZ', zynthian_engine.data_dir + "/soundfonts/sfz"),
		('GIG', zynthian_engine.data_dir + "/soundfonts/gig")
	]

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__(zyngui)
		self.name = "LinuxSampler"
		self.nickname = "LS"
		self.jackname = "LinuxSampler"

		self.sock = None
		self.command = "linuxsampler --lscp-port {}".format(self.lscp_port)
		self.command_prompt = "\nLinuxSampler initialization completed."

		self.ls_chans = {}

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
				self.sock.connect(("127.0.0.1",self.lscp_port))
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


	def lscp_send(self, data):
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
			raise zyngine_lscp_error("{} ({} {})".format(parts[2],parts[0],parts[1]))
		elif line[0:3]=="WRN":
			parts=line.split(':')
			self.stop_loading()
			raise zyngine_lscp_warning("{} ({} {})".format(parts[2],parts[0],parts[1]))
		return result


	def lscp_send_multi(self, command):
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
				raise zyngine_lscp_error("{} ({} {})".format(parts[2],parts[0],parts[1]))
			elif line[0:3]=="WRN":
				parts=line.split(':')
				self.stop_loading()
				raise zyngine_lscp_warning("{} ({} {})" % (parts[2],parts[0],parts[1]))
			elif len(line)>3:
				parts=line.split(':')
				result[parts[0]]=parts[1]
		return result

	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------

	def add_layer(self, layer):
		self.layers.append(layer)
		layer.jackname = None
		layer.ls_chan_info=None
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
			try:
				self.lscp_send_single("SET CHANNEL MIDI_INPUT_CHANNEL {} {}".format(ls_chan_id, layer.get_midi_chan()))
			except zyngine_lscp_error as err:
				logging.error(err)
			except zyngine_lscp_warning as warn:
				logging.warning(warn)

	# ---------------------------------------------------------------------------
	# Bank Management
	# ---------------------------------------------------------------------------

	def get_bank_list(self, layer=None):
		return self.get_dirlist(self.bank_dirs)


	def set_bank(self, layer, bank):
		return True

	# ---------------------------------------------------------------------------
	# Preset Management
	# ---------------------------------------------------------------------------

	@staticmethod
	def _get_preset_list(bank):
		logging.info("Getting Preset List for %s" % bank[2])
		i=0
		preset_list=[]
		preset_dpath=bank[0]
		if os.path.isdir(preset_dpath):
			exclude_sfz = re.compile(r"[MOPRSTV][1-9]?l?\.sfz")
			cmd="find '"+preset_dpath+"' -maxdepth 3 -type f -name '*.sfz'"
			output=check_output(cmd, shell=True).decode('utf8')
			cmd="find '"+preset_dpath+"' -maxdepth 2 -type f -name '*.gig'"
			output=output+"\n"+check_output(cmd, shell=True).decode('utf8')
			lines=output.split('\n')
			for f in lines:
				if f:
					filehead,filetail=os.path.split(f)
					if not exclude_sfz.fullmatch(filetail):
						filename,filext=os.path.splitext(f)
						filename = filename[len(preset_dpath)+1:]
						title=filename.replace('_', ' ')
						engine=filext[1:].lower()
						preset_list.append([f,i,title,engine,"{}.{}".format(filename,filext)])
						i=i+1
		return preset_list


	def get_preset_list(self, bank):
		return self._get_preset_list(bank)


	def set_preset(self, layer, preset, preload=False):
		if self.ls_set_preset(layer, preset[3], preset[0]):
			layer.send_ctrl_midi_cc()
			return True
		else:
			return False


	def cmp_presets(self, preset1, preset2):
		try:
			if preset1[0]==preset2[0] and preset1[3]==preset2[3]:
				return True
			else:
				return False
		except:
			return False

	# ---------------------------------------------------------------------------
	# Controllers Management
	# ---------------------------------------------------------------------------


	# ---------------------------------------------------------------------------
	# Specific functions
	# ---------------------------------------------------------------------------

	def ls_init(self):
		try:
			# Reset
			self.lscp_send_single("RESET")

			# Config Audio JACK Device 0
			self.ls_audio_device_id=self.lscp_send_single("CREATE AUDIO_OUTPUT_DEVICE JACK ACTIVE='true' CHANNELS='16' NAME='{}'".format(self.jackname))
			for i in range(8):
				self.lscp_send_single("SET AUDIO_OUTPUT_CHANNEL_PARAMETER {} {} NAME='CH{}_1'".format(self.ls_audio_device_id, i*2, i))
				self.lscp_send_single("SET AUDIO_OUTPUT_CHANNEL_PARAMETER {} {} NAME='CH{}_2'".format(self.ls_audio_device_id, i*2+1, i))

			#self.lscp_send_single("SET AUDIO_OUTPUT_CHANNEL_PARAMETER %s 0 JACK_BINDINGS='system:playback_1'" % self.ls_audio_device_id)
			#self.lscp_send_single("SET AUDIO_OUTPUT_CHANNEL_PARAMETER %s 1 JACK_BINDINGS='system:playback_2'" % self.ls_audio_device_id)
			#self.lscp_send_single("SET AUDIO_OUTPUT_CHANNEL_PARAMETER %s 0 IS_MIX_CHANNEL='false'" % self.ls_audio_device_id)
			#self.lscp_send_single("SET AUDIO_OUTPUT_CHANNEL_PARAMETER %s 1 IS_MIX_CHANNEL='false'" % self.ls_audio_device_id)

			# Config MIDI JACK Device 1
			self.ls_midi_device_id=self.lscp_send_single("CREATE MIDI_INPUT_DEVICE JACK ACTIVE='true' NAME='LinuxSampler' PORTS='1'")
			#self.lscp_send_single("SET MIDI_INPUT_PORT_PARAMETER %s 0 JACK_BINDINGS=''" % self.ls_midi_device_id)
			#self.lscp_send_single("SET MIDI_INPUT_PORT_PARAMETER %s 0 NAME='midi_in_0'" % self.ls_midi_device_id)

			# Global volume level
			self.lscp_send_single("SET VOLUME 0.45")

		except zyngine_lscp_error as err:
			logging.error(err)
		except zyngine_lscp_warning as warn:
			logging.warning(warn)


	def ls_set_channel(self, layer):
		# Adding new channel
		ls_chan_id=self.lscp_send_single("ADD CHANNEL")
		if ls_chan_id>=0:
			try:
				self.lscp_send_single("SET CHANNEL AUDIO_OUTPUT_DEVICE {} {}".format(ls_chan_id, self.ls_audio_device_id))
				#self.lscp_send_single("SET CHANNEL VOLUME %d 1" % ls_chan_id)

				# Configure MIDI input
				if self.lscp_v1_6_supported:
					self.lscp_send_single("ADD CHANNEL MIDI_INPUT {} {} 0".format(ls_chan_id, self.ls_midi_device_id))
				else:
					self.lscp_send_single("SET CHANNEL MIDI_INPUT_DEVICE {} {}".format(ls_chan_id, self.ls_midi_device_id))
					self.lscp_send_single("SET CHANNEL MIDI_INPUT_PORT {} {}".format(ls_chan_id, 0))

			except zyngine_lscp_error as err:
				logging.error(err)
			except zyngine_lscp_warning as warn:
				logging.warning(warn)

			#Save chan info in layer
			layer.ls_chan_info={
				'chan_id': ls_chan_id,
				'ls_engine': None,
				'audio_output': None
			}


	def ls_set_preset(self, layer, ls_engine, fpath):
		res=False
		if layer.ls_chan_info:
			ls_chan_id=layer.ls_chan_info['chan_id']

			# Load engine and set output channels if needed
			if ls_engine!=layer.ls_chan_info['ls_engine']:
				try:
					self.lscp_send_single("LOAD ENGINE {} {}".format(ls_engine, ls_chan_id))
					layer.ls_chan_info['ls_engine']=ls_engine

					i = self.ls_get_free_output_channel()
					self.lscp_send_single("SET CHANNEL AUDIO_OUTPUT_CHANNEL {} 0 {}".format(ls_chan_id, i*2))
					self.lscp_send_single("SET CHANNEL AUDIO_OUTPUT_CHANNEL {} 1 {}".format(ls_chan_id, i*2+1))
					layer.ls_chan_info['audio_output']=i

					layer.jackname = "{}:CH{}".format(self.jackname, i)
					self.zyngui.zynautoconnect_audio()

				except zyngine_lscp_error as err:
					logging.error(err)
				except zyngine_lscp_warning as warn:
					logging.warning(warn)
			
			# Load instument
			try:
				self.sock.settimeout(10)
				self.lscp_send_single("LOAD INSTRUMENT '{}' 0 {}".format(fpath, ls_chan_id))
				res=True
			except zyngine_lscp_error as err:
				logging.error(err)
			except zyngine_lscp_warning as warn:
				res=True
				logging.warning(warn)

			self.sock.settimeout(1)

		return res


	def ls_unset_channel(self, layer):
		if layer.ls_chan_info:
			chan_id=layer.ls_chan_info['chan_id']
			try:
				self.lscp_send_single("RESET CHANNEL {}".format(chan_id))
				# Remove sampler channel
				if self.lscp_v1_6_supported:
					self.lscp_send_single("REMOVE CHANNEL MIDI_INPUT {}".format(chan_id))
					self.lscp_send_single("REMOVE CHANNEL {}".format(chan_id))
			except zyngine_lscp_error as err:
				logging.error(err)
			except zyngine_lscp_warning as warn:
				logging.warning(warn)

			layer.ls_chan_info = None
			layer.jackname = None


	def ls_get_free_output_channel(self):
		for i in range(16):
			busy=False
			for layer in self.layers:
				if layer.ls_chan_info and i==layer.ls_chan_info['audio_output']:
					busy=True

			if not busy:
				return i

	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

	@classmethod
	def zynapi_get_banks(cls):
		bank_dirs = [
			('SFZ', zynthian_engine.my_data_dir + "/soundfonts/sfz"),
			('GIG', zynthian_engine.my_data_dir + "/soundfonts/gig")
		]
		banks=[]
		for b in cls.get_dirlist(cls.bank_dirs, False):
			banks.append({
				'text': b[2],
				'name': b[4],
				'fullpath': b[0],
				'raw': b,
				'readonly': False
			})
		return banks


	@classmethod
	def zynapi_get_presets(cls, bank):
		presets=[]
		for p in cls._get_preset_list(bank['raw']):
			head, tail = os.path.split(p[2])
			presets.append({
				'text': p[4],
				'name': tail,
				'fullpath': p[0],
				'raw': p,
				'readonly': False
			})
		return presets


	@classmethod
	def zynapi_new_bank(cls, bank_name):
		if bank_name.lower().startswith("gig/"):
			bank_type = "gig"
			bank_name = bank_name[4:]
		elif bank_name.lower().startswith("sfz/"):
			bank_type = "sfz"
			bank_name = bank_name[4:]
		else:
			bank_type = "sfz"
		os.mkdir(zynthian_engine.my_data_dir + "/soundfonts/{}/{}".format(bank_type, bank_name))


	@classmethod
	def zynapi_rename_bank(cls, bank_path, new_bank_name):
		head, tail = os.path.split(bank_path)
		new_bank_path = head + "/" + new_bank_name
		os.rename(bank_path, new_bank_path)


	@classmethod
	def zynapi_remove_bank(cls, bank_path):
		shutil.rmtree(bank_path)


	@classmethod
	def zynapi_rename_preset(cls, preset_path, new_preset_name):
		head, tail = os.path.split(preset_path)
		fname, ext = os.path.splitext(tail)
		new_preset_path = head + "/" + new_preset_name + ext
		os.rename(preset_path, new_preset_path)


	@classmethod
	def zynapi_remove_preset(cls, preset_path):
		os.remove(preset_path)
		#TODO => If last preset in SFZ dir, delete it too!


	@classmethod
	def zynapi_download(cls, fullpath):
		fname, ext = os.path.splitext(fullpath)
		if ext[0]=='.':
			head, tail = os.path.split(fullpath)
			return head
		else:
			return fullpath


	@classmethod
	def zynapi_install(cls, dpath, bank_path):
		#TODO: Test that bank_path fits preset type (sfz/gig)
		 
		fname, ext = os.path.splitext(dpath)
		if os.path.isdir(dpath):
			# Locate sfz files and move all them to first level directory
			try:
				sfz_files = check_output("find \"{}\" -type f -iname *.sfz".format(dpath), shell=True).decode("utf-8").split("\n")
				# Find the "shallower" SFZ file 
				shallower_sfz_file = sfz_files[0]
				for f in sfz_files:
					if len(f)<len(shallower_sfz_file):
						shallower_sfz_file = f
				head, tail = os.path.split(shallower_sfz_file)
				# Move SFZ stuff to the top level
				if head!=dpath:
					for f in glob.glob(head + "/*"):
						shutil.move(f, dpath)
					#shutil.rmtree(head)
			except:
				raise Exception("Directory doesn't contain any SFZ file")

			# Move directory to destiny bank
			if "/sfz/" in bank_path:
				shutil.move(dpath, bank_path)
			else:
				raise Exception("Destiny is not a SFZ bank!")

		elif ext.lower()=='.gig':

			# Move directory to destiny bank
			if "/gig/" in bank_path:
				shutil.move(dpath, bank_path)
			else:
				raise Exception("Destiny is not a GIG bank!")

		else:
			raise Exception("File doesn't look like a SFZ or GIG soundfont")


	@classmethod
	def zynapi_get_formats(cls):
		return "gig,zip,tgz,tar.gz,tar.bz2"


	@classmethod
	def zynapi_martifact_formats(cls):
		return "sfz,gig"

#******************************************************************************
