# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_sysex)
#
# zynthian_engine implementation for SysEx manager
#
# Copyright (C) 2015-2024 Fernando Moyano <jofemodo@zynthian.org>
# *******************************************************************************
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
import shutil
import logging
from time import sleep

import zynautoconnect
from . import zynthian_engine
from zyncoder.zyncore import lib_zyncore

# ------------------------------------------------------------------------------
# SysEx Manager Engine Class
# ------------------------------------------------------------------------------


class zynthian_engine_sysex(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Controllers & Screens
	# ---------------------------------------------------------------------------

	_ctrls = []
	_ctrl_screens = []

	# ----------------------------------------------------------------------------
	# Config variables
	# ----------------------------------------------------------------------------

	preset_fexts = ["syx"]
	root_bank_dirs = [
		('User', zynthian_engine.my_data_dir + "/presets/sysex"),
	]

	# ----------------------------------------------------------------------------
	# Initialization
	# ----------------------------------------------------------------------------

	def __init__(self, state_manager=None):
		super().__init__(state_manager)

		self.name = "SysEx"
		self.nickname = "SX"
		self.jackname = "sysex"

		self.sysex_fpath = ""
		self.sysex_data = None

		self.base_command = None
		self.reset()

	# ---------------------------------------------------------------------------
	# Processor Management
	# ---------------------------------------------------------------------------

	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	# ----------------------------------------------------------------------------
	# Bank Managament
	# ----------------------------------------------------------------------------

	def set_bank(self, processor, bank):
		return True

	# ----------------------------------------------------------------------------
	# Preset Managament
	# ----------------------------------------------------------------------------

	def get_preset_list(self, bank):
		return self.get_filelist(bank[0], self.preset_fexts[0])

	def set_preset(self, processor, preset, preload=False):
		self.sysex_fpath = preset[0]
		if self.load_sysex_file(self.sysex_fpath):
			for jn in processor.chain.get_midi_out():
				self.send_sysex_data(jn)
			sleep(0.2)
			return True
		else:
			return False

	def cmp_presets(self, preset1, preset2):
		try:
			if preset1[0] == preset2[0] and preset1[2] == preset2[2]:
				return True
			else:
				return False
		except:
			return False

	# ----------------------------------------------------------------------------
	# Controllers Managament
	# ----------------------------------------------------------------------------

	# --------------------------------------------------------------------------
	# Specific functions
	# --------------------------------------------------------------------------

	def load_sysex_file(self, fpath):
		try:
			logging.info("Loading SysEx file %s ..." % fpath)
			with open(fpath, "rb") as fh:
				self.sysex_data = fh.read()
		except Exception as e:
			logging.error("Can't load SysEx file '%s': %s" % (fpath, e))
			return False
		if self.check_sysex_data():
			return True
		else:
			self.sysex_data = None
			logging.error("Wrong SysEx data format")
			return False

	def check_sysex_data(self):
		if self.sysex_data[0] == 0xf0 and self.sysex_data[-1] == 0xf7:
			return True
		else:
			return False

	def send_sysex_data(self, device_name):
		try:
			idev = zynautoconnect.devices_out_name.index(device_name)
		except:
			logging.warning(f"Can't send MIDI SysEx data to {device_name}")
			return False
		lib_zyncore.dev_send_midi_event(idev, self.sysex_data, len(self.sysex_data))
		logging.info(f"Sending MIDI SysEx data to {device_name} ({idev}) => {self.sysex_data}")
		return True

	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

	@classmethod
	def zynapi_get_banks(cls):
		banks = []
		for b in cls.get_bank_dirlist(exclude_empty=False):
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
		for p in cls.get_filelist(bank['fullpath'], cls.preset_fexts[0]):
			presets.append({
				'text': p[4],
				'name': p[4],
				'fullpath': p[0],
				'raw': p,
				'readonly': False
			})
		return presets

	@classmethod
	def zynapi_new_bank(cls, bank_name):
		os.mkdir(zynthian_engine.my_data_dir + "/presets/sysex/" + bank_name)

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
		new_preset_path = head + "/" + new_preset_name
		os.rename(preset_path, new_preset_path)

	@classmethod
	def zynapi_remove_preset(cls, preset_path):
		os.remove(preset_path)

	@classmethod
	def zynapi_download(cls, fullpath):
		return fullpath

	@classmethod
	def zynapi_install(cls, fpath, bank_path):
		if not bank_path:
			raise Exception("You must select a destiny bank folder!")
		if os.path.isfile(fpath):
			fname, ext = os.path.splitext(fpath)
			if ext[1:] in cls.preset_fexts:
				shutil.move(fpath, bank_path)
			else:
				raise Exception("File doesn't look like a SysEx data file!")

	@classmethod
	def zynapi_get_formats(cls):
		return ",".join(cls.preset_fexts)

# -----------------------------------------------------------------------------
