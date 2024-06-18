# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_linuxsampler)
# 
# zynthian_engine implementation for Linux Sampler
# 
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
#
# ******************************************************************************
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
# ******************************************************************************

import os
import re
import glob
import logging
import socket
import shutil
from time import sleep
from os.path import isfile
from Levenshtein import distance
from subprocess import check_output
from collections import OrderedDict

from . import zynthian_engine
from zynconf import ServerPort
from zyncoder.zyncore import lib_zyncore

# ------------------------------------------------------------------------------
# Linuxsampler Exception Classes
# ------------------------------------------------------------------------------


class zyngine_lscp_error(Exception):
	pass


class zyngine_lscp_warning(Exception):
	pass


# ------------------------------------------------------------------------------
# Linuxsampler Engine Class
# ------------------------------------------------------------------------------


class zynthian_engine_linuxsampler(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Controllers & Screens
	# ---------------------------------------------------------------------------

	# LS Hardcoded MIDI Controllers
	_ctrls = [
		['modulation wheel', 1, 0],
		['volume', 7, 96],
		['pan', 10, 64],
		['expression', 11, 127],

		['sustain', 64, 'off', ['off', 'on']],
		['sostenuto', 66, 'off', ['off', 'on']],
		['legato', 68, 'off', ['off', 'on']],
		['breath', 2, 127],

		['portamento on/off', 65, 'off', ['off', 'on']],
		['portamento time-coarse', 5, 0],
		['portamento time-fine', 37, 0],

		# ['expr. pedal', 4, 127],
		['filter cutoff', 74, 64],
		['filter resonance', 71, 64],
		['env. attack', 73, 64],
		['env. release', 72, 64]
	]

	# Controller Screens
	_ctrl_screens = [
		['main', ['volume', 'pan', 'modulation wheel', 'expression']],
		['pedals', ['legato', 'breath', 'sostenuto', 'sustain']],
		['portamento', ['portamento on/off', 'portamento time-coarse', 'portamento time-fine']],
		['envelope/filter', ['env. attack', 'env. release', 'filter cutoff', 'filter resonance']]
	]

	# ---------------------------------------------------------------------------
	# Config variables
	# ---------------------------------------------------------------------------

	lscp_port = ServerPort["linuxsampler_osc"]

	preset_fexts = ["sfz", "gig"]
	root_bank_dirs = [
		('User GIG', zynthian_engine.my_data_dir + "/soundfonts/gig"),
		('User SFZ', zynthian_engine.my_data_dir + "/soundfonts/sfz"),
		('System GIG', zynthian_engine.data_dir + "/soundfonts/gig"),
		('System SFZ', zynthian_engine.data_dir + "/soundfonts/sfz")
	]

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------

	def __init__(self, state_manager=None):
		super().__init__(state_manager)
		self.name = "LinuxSampler"
		self.nickname = "LS"
		self.jackname = "LinuxSampler"

		self.sock = None
		self.command = "linuxsampler --lscp-port {}".format(self.lscp_port)
		self.command_prompt = "\nLinuxSampler initialization completed."

		self.ls_chans = {}

		self.start()
		self.lscp_connect()
		self.reset()

	def reset(self):
		super().reset()
		self.ls_chans = {}
		self.ls_init()

	# ---------------------------------------------------------------------------
	# Subproccess Management & IPC
	# ---------------------------------------------------------------------------

	def lscp_connect(self):
		logging.info("Connecting with LinuxSampler Server...")
		self.state_manager.start_busy("linux_sampler")
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.setblocking(False)
		self.sock.settimeout(1)
		i = 0
		while i < 20:
			try:
				self.sock.connect(("127.0.0.1", self.lscp_port))
				break
			except:
				sleep(0.25)
				i += 1
		return self.sock

	def lscp_send(self, command):
		command = command + "\r\n"
		try:
			self.sock.send(command.encode())
		except Exception as err:
			logging.error("FAILED lscp_send: %s" % err)

	def lscp_get_result_index(self, result):
		parts = result.split('[')
		if len(parts) > 1:
			parts = parts[1].split(']')
			return int(parts[0])

	def lscp_send_single(self, command):
		#logging.debug("LSCP SEND => %s" % command)
		command = command + "\r\n"
		try:
			self.sock.send(command.encode())
			line = self.sock.recv(4096)
		except Exception as err:
			logging.error("FAILED lscp_send_single(%s): %s" % (command,err))
			self.state_manager.end_busy("linux_sampler")
			return None
		line = line.decode()
		#logging.debug("LSCP RECEIVE => %s" % line)
		if line[0:2] == "OK":
			result = self.lscp_get_result_index(line)
			self.state_manager.end_busy("linux_sampler")
			return result
		elif line[0:3] == "ERR":
			parts = line.split(':')
			self.state_manager.end_busy("linux_sampler")
			raise zyngine_lscp_error("{} ({} {})".format(parts[2], parts[0], parts[1]))
		elif line[0:3] == "WRN":
			parts = line.split(':')
			self.state_manager.end_busy("linux_sampler")
			raise zyngine_lscp_warning("{} ({} {})".format(parts[2], parts[0], parts[1]))

	def lscp_send_multi(self, command):
		#logging.debug("LSCP SEND => %s" % command)
		command = command + "\r\n"
		try:
			self.sock.send(command.encode())
			result = self.sock.recv(4096)
		except Exception as err:
			logging.error("FAILED lscp_send_multi(%s): %s" % (command,err))
			self.state_manager.end_busy("linux_sampler")
			return None
		lines = result.decode().split("\r\n")
		result = OrderedDict()
		for line in lines:
			#logging.debug("LSCP RECEIVE => %s" % line)
			if line[0:2] == "OK":
				result = self.lscp_get_result_index(line)
			elif line[0:3] == "ERR":
				parts = line.split(':')
				raise zyngine_lscp_error("{} ({} {})".format(parts[2], parts[0], parts[1]))
			elif line[0:3] == "WRN":
				parts = line.split(':')
				raise zyngine_lscp_warning("{} ({} {})".format(parts[2], parts[0], parts[1]))
			elif len(line) > 3:
				parts = line.split(':')
				result[parts[0]] = parts[1]
		self.state_manager.end_busy("linux_sampler")
		return result

	# ---------------------------------------------------------------------------
	# Processor Management
	# ---------------------------------------------------------------------------

	def add_processor(self, processor):
		self.processors.append(processor)
		processor.jackname = None
		processor.ls_chan_info = None
		self.ls_set_channel(processor)
		self.set_midi_chan(processor)
		processor.refresh_controllers()

	def remove_processor(self, processor):
		#self.ls_unset_channel(processor)
		super().remove_processor(processor)

	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	def set_midi_chan(self, processor):
		if processor.ls_chan_info:
			lib_zyncore.zmop_set_midi_chan_trans(processor.chain.zmop_index, processor.get_midi_chan(), processor.ls_chan_info['midi_chan'])

	# ---------------------------------------------------------------------------
	# Bank Management
	# ---------------------------------------------------------------------------

	def get_bank_list(self, processor=None):
		return self.get_bank_dirlist(recursion=2)

	def set_bank(self, processor, bank):
		return True

	# ---------------------------------------------------------------------------
	# Preset Management
	# ---------------------------------------------------------------------------

	@staticmethod
	def _get_preset_list(bank):
		logging.info("Getting Preset List for %s" % bank[2])
		i = 0
		preset_list = []
		preset_dpath = bank[0]
		if os.path.isdir(preset_dpath):
			exclude_sfz = re.compile(r"[MOPRSTV][1-9]?l?\.sfz")
			for sd in glob.glob(preset_dpath + "/*"):
				if os.path.isdir(sd):
					cmd = f"find '{sd}' -maxdepth 2 -type f -name '*.sfz'"
					output = check_output(cmd, shell=True).decode('utf8')
					flist = list(filter(None, output.split('\n')))
					for f in flist:
						filehead, filetail = os.path.split(f)
						if not exclude_sfz.fullmatch(filetail):
							filename, filext = os.path.splitext(f)
							filename = filename[len(preset_dpath)+1:]
							if len(flist) == 1:
								dirname = filehead.split("/")[-1]
								if dirname[-4:].lower() == ".sfz":
									dirname = dirname[:-4]
								title = dirname.replace('_', ' ')
							else:
								title = filename.replace('_', ' ')
							engine = filext[1:].lower()
							preset_list.append([f, i, title, engine, "{}{}".format(filename, filext)])
							i += 1
				else:
					f = sd
					filehead, filetail = os.path.split(f)
					filename, filext = os.path.splitext(f)
					if filext.lower() == ".sfz" and not exclude_sfz.fullmatch(filetail):
						filename = filename[len(preset_dpath) + 1:]
						title = filename.replace('_', ' ')
						engine = filext[1:].lower()
						preset_list.append([f, i, title, engine, "{}{}".format(filename, filext)])
						i += 1
					elif filext.lower() == ".gig":
						filename = filename[len(preset_dpath) + 1:]
						title = filename.replace('_', ' ')
						engine = filext[1:].lower()
						# Get instrument list inside each GIG file
						inslist = ""
						# Try getting from cache file
						icache_fpath = f + ".ins"
						if isfile(icache_fpath):
							try:
								with open(icache_fpath, "r") as fh:
									inslist = fh.read()
							except Exception as e:
								logging.error(f"Can't load instrument cache '{icache_fpath}'")
						# If not cache, parse soundfont and cache info
						if not inslist:
							cmd = f"gigdump --instrument-names \"{f}\""
							inslist = check_output(cmd, shell=True).decode('utf8')
							try:
								with open(icache_fpath, "w") as fh:
									fh.write(inslist)
							except Exception as e:
								logging.error(f"Can't save instrument cache '{icache_fpath}'")
						#logging.debug(f"INSTRUMENTS IN {f} =>\n{inslist}")
						ilines = inslist.split('\n')
						ii = 0
						for iline in ilines:
							try:
								parts = iline.split(")")
								ititle = parts[1].replace('"', '').strip()
								l = len(title)
								if distance(title.lower(), ititle.lower()[0:l]) > int(l/3):
									ititle = title + "/" + ititle
							except:
								continue
							preset_list.append([f"{f}#{ii}", i, ititle, engine, f"{filename}{filext}#{ii}"])
							ii += 1
							i += 1
		return preset_list

	def get_preset_list(self, bank):
		return self._get_preset_list(bank)

	def set_preset(self, processor, preset, preload=False):
		# Search for an instrument index, if any
		parts = preset[0].split("#")
		sfpath = parts[0]
		try:
			ii = int(parts[1])
		except:
			ii = 0
		# Load instrument from soundfont
		if self.ls_set_preset(processor, preset[3], sfpath, ii):
			processor.send_ctrl_midi_cc()
			return True
		else:
			return False

	def cmp_presets(self, preset1, preset2):
		try:
			if preset1[0] == preset2[0] and preset1[3] == preset2[3]:
				return True
			else:
				return False
		except:
			return False

	# ---------------------------------------------------------------------------
	# Controllers Management
	# ---------------------------------------------------------------------------

	def send_controller_value(self, zctrl):
		try:
			izmop = zctrl.processor.chain.zmop_index
			if izmop is not None and izmop >= 0:
				mchan = zctrl.processor.ls_chan_info['midi_chan']
				mval = zctrl.get_ctrl_midi_val()
				lib_zyncore.zmop_send_ccontrol_change(izmop, mchan, zctrl.midi_cc, mval)
		except Exception as err:
			logging.error(err)

	# ---------------------------------------------------------------------------
	# Specific functions
	# ---------------------------------------------------------------------------

	def ls_init(self):
		try:
			# Reset
			self.lscp_send_single("RESET")

			# Config Audio JACK Device 0
			self.ls_audio_device_id = self.lscp_send_single(f"CREATE AUDIO_OUTPUT_DEVICE JACK ACTIVE='true' CHANNELS='32' NAME='{self.jackname}'")
			for i in range(16):
				self.lscp_send_single(f"SET AUDIO_OUTPUT_CHANNEL_PARAMETER {self.ls_audio_device_id} {i * 2} NAME='out{i}_l'")
				self.lscp_send_single(f"SET AUDIO_OUTPUT_CHANNEL_PARAMETER {self.ls_audio_device_id} {i * 2 + 1} NAME='out{i}_r'")

			#self.lscp_send_single("SET AUDIO_OUTPUT_CHANNEL_PARAMETER %s 0 JACK_BINDINGS='system:playback_1'" % self.ls_audio_device_id)
			#self.lscp_send_single("SET AUDIO_OUTPUT_CHANNEL_PARAMETER %s 1 JACK_BINDINGS='system:playback_2'" % self.ls_audio_device_id)
			#self.lscp_send_single("SET AUDIO_OUTPUT_CHANNEL_PARAMETER %s 0 IS_MIX_CHANNEL='false'" % self.ls_audio_device_id)
			#self.lscp_send_single("SET AUDIO_OUTPUT_CHANNEL_PARAMETER %s 1 IS_MIX_CHANNEL='false'" % self.ls_audio_device_id)

			# Config MIDI JACK Device 1
			self.ls_midi_device_id = self.lscp_send_single(f"CREATE MIDI_INPUT_DEVICE JACK ACTIVE='true' NAME='{self.jackname}' PORTS='1'")
			#self.lscp_send_single("SET MIDI_INPUT_PORT_PARAMETER %s 0 JACK_BINDINGS=''" % self.ls_midi_device_id)
			#self.lscp_send_single("SET MIDI_INPUT_PORT_PARAMETER %s 0 NAME='midi_in_0'" % self.ls_midi_device_id)

			# Global volume level
			self.lscp_send_single("SET VOLUME 0.45")

		except zyngine_lscp_error as err:
			logging.error(err)
		except zyngine_lscp_warning as warn:
			logging.warning(warn)

	def ls_set_channel(self, processor):
		# Adding new channel
		ls_chan_id = self.lscp_send_single("ADD CHANNEL")
		if ls_chan_id >= 0:
			try:
				self.lscp_send_single(f"SET CHANNEL AUDIO_OUTPUT_DEVICE {ls_chan_id} {self.ls_audio_device_id}")
				#self.lscp_send_single("SET CHANNEL VOLUME %d 1" % ls_chan_id)
				# Configure MIDI input
				self.lscp_send_single(f"ADD CHANNEL MIDI_INPUT {ls_chan_id} {self.ls_midi_device_id} 0")
			except zyngine_lscp_error as err:
				logging.error(err)
			except zyngine_lscp_warning as warn:
				logging.warning(warn)

			audio_out = self.ls_get_free_audio_output()

			midi_chan = self.ls_get_free_midi_chan()
			try:
				self.lscp_send_single(f"SET CHANNEL MIDI_INPUT_CHANNEL {ls_chan_id} {midi_chan}")
			except zyngine_lscp_error as err:
				logging.error(err)
			except zyngine_lscp_warning as warn:
				logging.warning(warn)

			# Save chan info in processor
			processor.ls_chan_info = {
				'chan_id': ls_chan_id,
				'ls_engine': None,
				'audio_output': audio_out,
				'midi_chan': midi_chan
			}
			processor.jackname = f"LinuxSampler:out{audio_out}_"

	def ls_set_preset(self, processor, ls_engine, fpath, ii=0):
		res = False
		if processor.ls_chan_info:
			ls_chan_id = processor.ls_chan_info['chan_id']

			# Load engine and set output channels if needed
			if ls_engine != processor.ls_chan_info['ls_engine']:
				try:
					self.lscp_send_single(f"LOAD ENGINE {ls_engine} {ls_chan_id}")
					processor.ls_chan_info['ls_engine'] = ls_engine

				except zyngine_lscp_error as err:
					logging.error(err)
				except zyngine_lscp_warning as warn:
					logging.warning(warn)
			
			# Load instument
			try:
				self.sock.settimeout(10)
				self.lscp_send_single(f"LOAD INSTRUMENT '{fpath}' {ii} {ls_chan_id}")
				res = True
			except zyngine_lscp_error as err:
				logging.error(err)
			except zyngine_lscp_warning as warn:
				res = True
				logging.warning(warn)

			self.sock.settimeout(1)

			audio_output = processor.ls_chan_info['audio_output']
			self.lscp_send_single(f"SET CHANNEL AUDIO_OUTPUT_CHANNEL {ls_chan_id} 0 {audio_output * 2}")
			self.lscp_send_single(f"SET CHANNEL AUDIO_OUTPUT_CHANNEL {ls_chan_id} 1 {audio_output * 2 + 1}")

		return res

	def ls_unset_channel(self, processor):
		if processor.ls_chan_info:
			chan_id = processor.ls_chan_info['chan_id']
			try:
				self.lscp_send_single(f"RESET CHANNEL {chan_id}")
				# Remove sampler channel
				self.lscp_send_single(f"REMOVE CHANNEL MIDI_INPUT {chan_id}")
				self.lscp_send_single(f"REMOVE CHANNEL {chan_id}")
			except zyngine_lscp_error as err:
				logging.error(err)
			except zyngine_lscp_warning as warn:
				logging.warning(warn)

			processor.ls_chan_info = None
			processor.jackname = None

	def ls_get_free_audio_output(self):
		for i in range(16):
			busy = False
			for processor in self.processors:
				if processor.ls_chan_info and i == processor.ls_chan_info['audio_output']:
					busy = True
			if not busy:
				return i

	def ls_get_free_midi_chan(self):
		for i in range(16):
			busy = False
			for processor in self.processors:
				if processor.ls_chan_info and i == processor.ls_chan_info['midi_chan']:
					busy = True
			if not busy:
				return i

	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

	@classmethod
	def zynapi_get_banks(cls):
		banks = []
		for b in cls.get_bank_dirlist(recursion=2, exclude_empty=False):
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
		presets = []
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
		parts = preset_path.split("#")
		if len(parts) > 1:
			fname, ext = os.path.splitext(parts[0])
			if ext == ".gig":
				preset_path = parts[0]
		os.remove(preset_path)
		# TODO => If last preset in SFZ dir, delete it too!

	@classmethod
	def zynapi_download(cls, fullpath):
		fname, ext = os.path.splitext(fullpath)
		if ext and ext[0] == '.':
			head, tail = os.path.split(fullpath)
			return head
		else:
			return fullpath

	@classmethod
	def zynapi_install(cls, dpath, bank_path):
		# TODO: Test that bank_path fits preset type (sfz/gig)
		if not os.path.isdir(bank_path):
			raise Exception("Destiny is not a directory!")

		fname, ext = os.path.splitext(dpath)
		if os.path.isdir(dpath):
			# Locate sfz files and move all them to first level directory
			try:
				cmd = "find \"{}\" -type f -iname *.sfz".format(dpath)
				sfz_files = check_output(cmd, shell=True).decode("utf-8").split("\n")
				# Find the "shallower" SFZ file 
				shallower_sfz_file = sfz_files[0]
				for f in sfz_files:
					if f and (f.count('/') < shallower_sfz_file.count('/')):
						shallower_sfz_file = f
				head, tail = os.path.split(shallower_sfz_file)
				# Move SFZ stuff to the top level
				if head and head != dpath:
					for f in glob.glob(head + "/*"):
						shutil.move(f, dpath)
					shutil.rmtree(head)
			except:
				raise Exception("Directory doesn't contain any SFZ file")

			# Move directory to destiny bank
			if "/sfz/" in bank_path:
				shutil.move(dpath, bank_path)
			else:
				raise Exception("Destiny is not a SFZ bank!")

		elif ext.lower() == '.gig':
			# Move directory to destiny bank
			if "/gig/" in bank_path:
				shutil.move(dpath, bank_path)
			else:
				raise Exception("Destiny is not a GIG bank!")

		else:
			raise Exception("File doesn't look like a SFZ or GIG soundfont")

	@classmethod
	def zynapi_get_formats(cls):
		return "gig,zip,tgz,tar.gz,tar.bz2,tar.xz"

	@classmethod
	def zynapi_martifact_formats(cls):
		return "sfz,gig"

# ******************************************************************************
