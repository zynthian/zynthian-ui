# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_sfizz)
# 
# zynthian_engine implementation for Sfizz
# 
# Copyright (C) 2015-2021 Fernando Moyano <jofemodo@zynthian.org>
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
import shutil
from subprocess import check_output

from . import zynthian_engine

#------------------------------------------------------------------------------
# Sfizz Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_sfizz(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Controllers & Screens
	# ---------------------------------------------------------------------------

	# SFZ Default MIDI Controllers (modulators)
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

	bank_dirs = [
		('ExSFZ', zynthian_engine.ex_data_dir + "/soundfonts/sfz"),
		('MySFZ', zynthian_engine.my_data_dir + "/soundfonts/sfz"),
		('SFZ', zynthian_engine.data_dir + "/soundfonts/sfz")
	]

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------

	def __init__(self, zyngui=None, jackname=None):
		super().__init__(zyngui)
		self.name = "Sfizz"
		self.nickname = "SF"
		if jackname:
			self.jackname = jackname
		else:
			self.jackname = self.get_next_jackname("sfizz")

		self.preload_size = 32768 #8192, 16384, 32768, 65536
		self.num_voices = 40
		self.sfzpath = None

		self.command = "sfizz_jack --client_name '{}' --preload_size {} --num_voices {}".format(self.jackname, self.preload_size, self.num_voices, self.sfzpath)
		self.command_prompt = "> "

		self.reset()
		self.start()

	# ---------------------------------------------------------------------------
	# Subproccess Management & IPC
	# ---------------------------------------------------------------------------

	def stop(self):
		try:
			self.proc.sendline("quit")
			self.proc.expect("Closing...")
		except:
			super().stop()

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
		i = 0
		preset_list = []
		preset_dpath = bank[0]
		if os.path.isdir(preset_dpath):
			exclude_sfz = re.compile(r"[MOPRSTV][1-9]?l?\.sfz")
			cmd = "find '"+preset_dpath+"' -maxdepth 3 -type f -name '*.sfz'"
			output = check_output(cmd, shell=True).decode('utf8')
			lines = output.split('\n')
			for f in lines:
				if f:
					filehead,filetail = os.path.split(f)
					if not exclude_sfz.fullmatch(filetail):
						filename,filext = os.path.splitext(f)
						filename = filename[len(preset_dpath)+1:]
						title = filename.replace('_', ' ')
						engine = filext[1:].lower()
						preset_list.append([f,i,title,engine,"{}{}".format(filename,filext)])
						i += 1
		return preset_list


	def get_preset_list(self, bank):
		return self._get_preset_list(bank)


	def set_preset(self, layer, preset, preload=False):
		try:
			self.sfzpath = preset[0]
			return self.proc_cmd("load_instrument \"{}\"".format(self.sfzpath))
			#layer.send_ctrl_midi_cc()
		except:
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
	# API methods
	# ---------------------------------------------------------------------------

	@classmethod
	def zynapi_get_banks(cls):
		bank_dirs = [
			('SFZ', zynthian_engine.my_data_dir + "/soundfonts/sfz")
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
		if bank_name.lower().startswith("sfz/"):
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
		if ext and ext[0]=='.':
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
				cmd = "find \"{}\" -type f -iname *.sfz".format(dpath)
				sfz_files = check_output(cmd, shell=True).decode("utf-8").split("\n")
				# Find the "shallower" SFZ file 
				shallower_sfz_file = sfz_files[0]
				for f in sfz_files:
					if f and (f.count('/') < shallower_sfz_file.count('/')):
						shallower_sfz_file = f
				head, tail = os.path.split(shallower_sfz_file)
				# Move SFZ stuff to the top level
				if head and head!=dpath:
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

		else:
			raise Exception("File doesn't look like a SFZ soundfont")


	@classmethod
	def zynapi_get_formats(cls):
		return "zip,tgz,tar.gz,tar.bz2"


	@classmethod
	def zynapi_martifact_formats(cls):
		return "sfz"

#******************************************************************************
