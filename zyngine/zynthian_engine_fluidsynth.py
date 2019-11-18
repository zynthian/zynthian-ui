# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_fluidsynth)
# 
# zynthian_engine implementation for FluidSynth Sampler
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
import copy
import shutil
import logging
from subprocess import check_output
from . import zynthian_engine
from . import zynthian_controller

#------------------------------------------------------------------------------
# FluidSynth Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_fluidsynth(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Controllers & Screens
	# ---------------------------------------------------------------------------

	# Controller Screens
	_ctrl_screens=[
		['main',['volume','expression','pan','sustain']],
		['effects',['volume','modulation','reverb','chorus']]
	]

	# ---------------------------------------------------------------------------
	# Config variables
	# ---------------------------------------------------------------------------

	fs_options = "-o synth.midi-bank-select=mma -o synth.cpu-cores=3 -o synth.polyphony=64"

	soundfont_dirs=[
		('EX', zynthian_engine.ex_data_dir + "/soundfonts/sf2"),
		('MY', zynthian_engine.my_data_dir + "/soundfonts/sf2"),
		('_', zynthian_engine.data_dir + "/soundfonts/sf2")
	]

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__(zyngui)
		self.name = "FluidSynth"
		self.nickname = "FS"
		self.jackname = "fluidsynth"

		self.command = "/usr/local/bin/fluidsynth -p fluidsynth -a jack -m jack -g 1 -j {}".format(self.fs_options)
		self.command_prompt = "\n> "

		self.start()
		self.reset()


	def reset(self):
		super().reset()
		self.soundfont_index={}
		self.clear_midi_routes()
		self.unload_unused_soundfonts()

	# ---------------------------------------------------------------------------
	# Subproccess Management & IPC
	# ---------------------------------------------------------------------------

	def stop(self):
		try:
			self.proc.sendline("quit")
			self.proc.expect("\ncheers!")
		except:
			super().stop()

	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------

	def add_layer(self, layer):
		super().add_layer(layer)
		layer.part_i=None
		self.setup_router(layer)


	def del_layer(self, layer):
		super().del_layer(layer)
		if layer.part_i is not None:
			self.set_all_midi_routes()
		self.unload_unused_soundfonts()

	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	def set_midi_chan(self, layer):
		self.setup_router(layer)

	# ---------------------------------------------------------------------------
	# Bank Management
	# ---------------------------------------------------------------------------

	def get_bank_list(self, layer=None):
		return self.get_filelist(self.soundfont_dirs,"sf2") + self.get_filelist(self.soundfont_dirs,"sf3")


	def set_bank(self, layer, bank):
		if self.load_soundfont(bank[0]):
			self.unload_unused_soundfonts()
			return True
		else:
			return False

	# ---------------------------------------------------------------------------
	# Bank Management
	# ---------------------------------------------------------------------------

	def get_preset_list(self, bank):
		logging.info("Getting Preset List for {}".format(bank[2]))
		preset_list=[]
		if bank[0] in self.soundfont_index:
			sfi=self.soundfont_index[bank[0]]
			output=self.proc_cmd("inst {}".format(sfi))
			for f in output.split("\n"):
				try:
					prg=int(f[4:7])
					bank_msb=int(f[0:3])
					bank_lsb=int(bank_msb/128)
					bank_msb=bank_msb%128
					title=str.replace(f[8:-1], '_', ' ')
					preset_list.append((f.strip(),[bank_msb,bank_lsb,prg],title,sfi))
				except:
					pass
		else:
			logging.warning("Bank {} is not loaded".format(bank[2]))
		return preset_list


	def set_preset(self, layer, preset, preload=False):
		sfi=preset[3]
		if sfi in self.soundfont_index.values():
			midi_bank=preset[1][0]+preset[1][1]*128
			midi_prg=preset[1][2]
			logging.debug("Set Preset => Layer: {}, SoundFont: {}, Bank: {}, Program: {}".format(layer.part_i, sfi, midi_bank, midi_prg))
			self.proc_cmd("select {} {} {} {}".format(layer.part_i, sfi, midi_bank, midi_prg))
			layer.send_ctrl_midi_cc()
			return True
		else:
			logging.warning("SoundFont {} is not loaded".format(sfi))
			return False


	def cmp_presets(self, preset1, preset2):
		try:
			if preset1[3]==preset2[3] and preset1[1][0]==preset2[1][0] and preset1[1][1]==preset2[1][1] and preset1[1][2]==preset2[1][2]:
				return True
			else:
				return False
		except:
			return False

	# ---------------------------------------------------------------------------
	# Specific functions
	# ---------------------------------------------------------------------------

	def get_free_parts(self):
		free_parts = list(range(0,16))
		for layer in self.layers:
			try:
				free_parts.remove(layer.part_i)
			except:
				pass
		return free_parts


	def load_soundfont(self, sf):
		if sf not in self.soundfont_index:
			logging.info("Loading SoundFont '{}' ...".format(sf))
			# Send command to FluidSynth
			output=self.proc_cmd("load \"{}\"".format(sf))
			# Parse ouput ...
			sfi=None
			cre=re.compile(r"loaded SoundFont has ID (\d+)")
			for line in output.split("\n"):
				res=cre.match(line)
				if res:
					sfi=int(res.group(1))
			# If soundfont was loaded succesfully ...
			if sfi is not None:
				logging.info("Loaded SoundFont '{}' => {}".format(sf,sfi))
				# Re-select presets for all layers to prevent instrument change
				for layer in self.layers:
					if layer.preset_info:
						self.set_preset(layer, layer.preset_info)
				# Insert ID in soundfont_index dictionary
				self.soundfont_index[sf]=sfi
				# Return soundfont ID
				return sfi
			else:
				logging.warning("SoundFont '{}' can't be loaded".format(sf))
				return False


	def setup_router(self, layer):
		if layer.part_i is not None:
			# Clear and recreate all routes if the routes for this layer were set already
			self.set_all_midi_routes()
		else:
			# No need to clear routes if there is the only layer to add
			try:
				layer.part_i=self.get_free_parts()[0]
				logging.debug("ADD LAYER => PART {}".format(layer.part_i))
			except:
				logging.error("ADD LAYER => NO FREE PARTS!")
			self.set_layer_midi_routes(layer)


	def unload_unused_soundfonts(self):
		#Make a copy of soundfont index and remove used soundfonts
		sf_unload=copy.copy(self.soundfont_index)
		for layer in self.layers:
			bi=layer.bank_info
			if bi is not None:
				if bi[2] and bi[0] in sf_unload:
					#print("Skip "+bi[0]+"("+str(sf_unload[bi[0]])+")")
					del sf_unload[bi[0]]
		#Then, remove the remaining ;-)
		for sf,sfi in sf_unload.items():
			logging.info("Unload SoundFont => {}".format(sfi))
			self.proc_cmd("unload {}".format(sfi))
			del self.soundfont_index[sf]


	def set_layer_midi_routes(self, layer):
		if layer.part_i is not None:
			midich = layer.get_midi_chan()
			router_chan_cmd = "router_chan {0} {0} 0 {1}".format(midich, layer.part_i)
			self.proc_cmd("router_begin note")
			self.proc_cmd(router_chan_cmd)
			self.proc_cmd("router_end")
			self.proc_cmd("router_begin cc")
			self.proc_cmd(router_chan_cmd)
			self.proc_cmd("router_end")
			self.proc_cmd("router_begin pbend")
			self.proc_cmd(router_chan_cmd)
			self.proc_cmd("router_end")
			self.proc_cmd("router_begin prog")
			self.proc_cmd(router_chan_cmd)
			self.proc_cmd("router_end")


	def set_all_midi_routes(self):
		self.clear_midi_routes()
		for layer in self.layers:
			self.set_layer_midi_routes(layer)


	def clear_midi_routes(self):
		self.proc_cmd("router_clear")

	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

	@classmethod
	def zynapi_get_banks(cls):
		banks=[]
		for b in cls.get_filelist(cls.soundfont_dirs,"sf2") + cls.get_filelist(cls.soundfont_dirs,"sf3"):
			head, tail = os.path.split(b[0])
			fname, fext = os.path.splitext(tail)
			banks.append({
				'text': tail,
				'name': fname,
				'fullpath': b[0],
				'raw': b,
				'readonly': False
			})
		return banks


	@classmethod
	def zynapi_get_presets(cls, bank):
		return []


	@classmethod
	def zynapi_rename_bank(cls, bank_path, new_bank_name):
		head, tail = os.path.split(bank_path)
		fname, ext = os.path.splitext(tail)
		new_bank_path = head + "/" + new_bank_name + ext
		os.rename(bank_path, new_bank_path)


	@classmethod
	def zynapi_remove_bank(cls, bank_path):
		os.remove(bank_path)


	@classmethod
	def zynapi_download(cls, fullpath):
		return fullpath


	@classmethod
	def zynapi_install(cls, dpath, bank_path):

		if os.path.isdir(dpath):
			# Get list of sf2/sf3 files ...
			sfx_files = check_output("find \"{}\" -type f -iname *.sf2 -o -iname *.sf3".format(dpath), shell=True).decode("utf-8").split("\n")

			# Copy sf2/sf3 files to destiny ...
			count = 0
			for f in sfx_files:
				head, fname = os.path.split(f)
				if fname:
					shutil.move(f, zynthian_engine.my_data_dir + "/soundfonts/sf2/" + fname)
					count += 1

			if count==0:
				raise Exception("No SF2/SF3 soundfont files found!")

		else:
			fname, ext = os.path.splitext(dpath)
			if ext.lower() in ['.sf2', '.sf3']:
				shutil.move(dpath, zynthian_engine.my_data_dir + "/soundfonts/sf2")
			else:
				raise Exception("File doesn't look like a SF2/SF3 soundfont")


	@classmethod
	def zynapi_get_formats(cls):
		return "sf2,sf3,zip,tgz,tar.gz,tar.bz2"


	@classmethod
	def zynapi_martifact_formats(cls):
		return "sf2,sf3"


#******************************************************************************
