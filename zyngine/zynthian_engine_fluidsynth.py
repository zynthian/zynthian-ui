# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_fluidsynth)
# 
# zynthian_engine implementation for FluidSynth Sampler
# 
# Copyright (C) 2015-2024 Fernando Moyano <jofemodo@zynthian.org>
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
import copy
import shutil
import logging
import oyaml as yaml
from subprocess import check_output

import zynautoconnect
from . import zynthian_engine
from . import zynthian_controller
from zyngui import zynthian_gui_config
from zyncoder.zyncore import lib_zyncore

# ------------------------------------------------------------------------------
# FluidSynth Engine Class
# ------------------------------------------------------------------------------


class zynthian_engine_fluidsynth(zynthian_engine):

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
		['portamento control', 84, 0],

		# ['expr. pedal', 4, 127],
		['filter cutoff', 74, 64],
		['filter resonance', 71, 64],
		['env. attack', 73, 64],
		['env. release', 72, 64]
	]

	# Controller Screens
	default_ctrl_screens = [
		['main', ['volume', 'pan', 'modulation wheel', 'expression']],
		['pedals', ['legato', 'breath', 'sostenuto', 'sustain']],
		['portamento', ['portamento on/off', 'portamento control', 'portamento time-coarse', 'portamento time-fine']],
		['envelope/filter', ['env. attack', 'env. release', 'filter cutoff', 'filter resonance']]
	]

	# ---------------------------------------------------------------------------
	# Config variables
	# ---------------------------------------------------------------------------

	preset_fexts = ["sf2", "sf3"]
	root_bank_dirs = [
		('User', zynthian_engine.my_data_dir + "/soundfonts/sf2"),
		('System', zynthian_engine.data_dir + "/soundfonts/sf2")
	]

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------

	def __init__(self, state_manager=None):
		super().__init__(state_manager)
		self.name = "FluidSynth"
		self.nickname = "FS"
		self.jackname = "fluidsynth"

		self.bank_config = {}

		self.fs_options = "-o synth.midi-bank-select=mma -o synth.cpu-cores=3 -o synth.polyphony=64 -o midi.jack.id='{}' -o audio.jack.id='{}' -o audio.jack.autoconnect=0 -o audio.jack.multi='yes' -o synth.audio-groups=16 -o synth.audio-channels=16 -o synth.effects-groups=1 -o synth.chorus.active=0 -o synth.reverb.active=0".format(self.jackname,self.jackname)

		self.command = "fluidsynth -a jack -m jack -g 1 {}".format(self.fs_options)
		self.command_prompt = "\n> "

		self.start()
		self.reset()

	def reset(self):
		super().reset()
		self.soundfont_index={}
		self.unload_unused_soundfonts()

	# ---------------------------------------------------------------------------
	# Subproccess Management & IPC
	# ---------------------------------------------------------------------------

	def stop(self):
		try:
			self.proc.sendline("quit")
			self.proc.expect("\ncheers!")
			# We have asked nicely but sometimes fluidsynth needs more encouragement...
			self.proc.terminate(True)
			self.proc = None
		except:
			super().stop()

	# ---------------------------------------------------------------------------
	# Processor Management
	# ---------------------------------------------------------------------------

	def add_processor(self, processor):
		self.processors.append(processor)
		processor.jackname = None
		processor.part_i = None
		# Add the processor part
		try:
			i = self.get_free_parts()[0]
			processor.part_i = i
			#processor.jackname = "{}:((l|r)_{:02d}|fx_(l|r)_({:02d}|{:02d}))".format(self.jackname,i,i*2,i*2+1)
			processor.jackname = "{}:(l|r)_{:02d}".format(self.jackname,i)
			self.set_midi_chan(processor)
			zynautoconnect.request_audio_connect()
			logging.debug("Add part {} => {}".format(i, processor.jackname))
		except Exception as e:
			logging.error(f"Unable to add processor to engine - {e}")

	def remove_processor(self, processor):
		super().remove_processor(processor)
		self.unload_unused_soundfonts()

	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	def set_midi_chan(self, processor):
		if processor.part_i is not None:
			lib_zyncore.zmop_set_midi_chan_trans(processor.chain.zmop_index, processor.get_midi_chan(), processor.part_i)

	# ---------------------------------------------------------------------------
	# Bank Management
	# ---------------------------------------------------------------------------

	@classmethod
	def get_bank_filelist(cls, recursion=1, exclude_empty=True):
		banks = []
		logging.debug(f"LOADING BANK FILES ...")

		# External storage banks
		for exd in zynthian_gui_config.get_external_storage_dirs(cls.ex_data_dir):
			flist = cls.find_all_preset_files(exd, recursion=2)
			if not exclude_empty or len(flist) > 0:
				banks.append([None, None, f"USB> {os.path.basename(exd)}", None, None])
			for fpath in flist:
				fname = os.path.basename(fpath)
				title, filext = os.path.splitext(fname)
				title = title.replace('_', ' ')
				banks.append([fpath, None, title, None, fname])

		# Internal storage banks
		for root_bank_dir in cls.root_bank_dirs:
			flist = cls.find_all_preset_files(root_bank_dir[1], recursion=2)
			if not exclude_empty or len(flist) > 0:
				banks.append([None, None, "SD> " + root_bank_dir[0], None, None])
			for fpath in flist:
				fname = os.path.basename(fpath)
				title, filext = os.path.splitext(fname)
				title = title.replace('_', ' ')
				banks.append([fpath, None, title, None, fname])

		return banks

	def get_bank_list(self, processor=None):
		return self.get_bank_filelist(recursion=2)

	def set_bank(self, processor, bank):
		if self.load_bank(bank[0]):
			processor.refresh_controllers()
			return True
		else:
			return False

	def load_bank(self, bank_fpath, unload_unused_sf=True):
		if bank_fpath in self.soundfont_index:
			return True
		elif self.load_soundfont(bank_fpath):
			self.load_bank_config(bank_fpath)
			if unload_unused_sf:
				self.unload_unused_soundfonts()
			self.set_all_presets()
			return True
		else:
			return False

	def load_bank_config(self, bank_fpath):
		config_fpath = bank_fpath[0:-3] + "yml"
		try:
			fh = open(config_fpath, "r")
		except:
			logging.info(f"No yaml config file for soundfont '{bank_fpath}'")
			return False
		try:
			yml = fh.read()
			logging.info(f"Loading yaml config file for soundfont '{bank_fpath}' =>\n{yml}")
			self.bank_config[bank_fpath] = yaml.load(yml, Loader=yaml.SafeLoader)
			return True
		except Exception as e:
			logging.error(f"Bad yaml config file for soundfont '{bank_fpath}' => {e}")
			return False

	# ---------------------------------------------------------------------------
	# Preset Management
	# ---------------------------------------------------------------------------

	def get_preset_list(self, bank):
		logging.info("Getting Preset List for {}".format(bank[2]))
		preset_list = []
		try:
			sfi = self.soundfont_index[bank[0]]
		except:
			sfi = self.load_bank(bank[0], False)

		if sfi:
			output = self.proc_cmd("inst {}".format(sfi))
			for f in output.split("\n"):
				try:
					prg = int(f[4:7])
					bank_msb = int(f[0:3])
					bank_lsb = int(bank_msb/128)
					bank_msb = bank_msb%128
					title = str.replace(f[8:-1], '_', ' ')
					preset_list.append([bank[0] + '/' + f.strip(), [bank_msb, bank_lsb, prg], title, bank[0]])
				except:
					pass

		return preset_list

	def set_preset(self, processor, preset, preload=False):
		try:
			sfi = self.soundfont_index[preset[3]]
		except:
			if processor.set_bank_by_id(preset[3]):
				sfi = self.soundfont_index[preset[3]]
			else:
				return False

		midi_bank = preset[1][0]+preset[1][1]*128
		midi_prg = preset[1][2]
		logging.debug("Set Preset => Processor: {}, SoundFont: {}, Bank: {}, Program: {}".format(processor.part_i, sfi, midi_bank, midi_prg))
		self.proc_cmd("select {} {} {} {}".format(processor.part_i, sfi, midi_bank, midi_prg))
		processor.send_ctrl_midi_cc()
		return True

	def cmp_presets(self, preset1, preset2):
		try:
			if preset1[3]==preset2[3] and preset1[1][0]==preset2[1][0] and preset1[1][1]==preset2[1][1] and preset1[1][2]==preset2[1][2]:
				return True
			else:
				return False
		except:
			return False

	# ----------------------------------------------------------------------------
	# Controllers Management
	# ----------------------------------------------------------------------------

	def get_controllers_dict(self, processor):
		zctrls = super().get_controllers_dict(processor)
		self._ctrl_screens = copy.copy(self.default_ctrl_screens)

		try:
			sf = processor.bank_info[0]
			ctrl_items = self.bank_config[sf]['midi_controllers'].items()
		except:
			ctrl_items = None

		if ctrl_items:
			logging.debug("Generating extra controllers config ...")
			try:
				c = 1
				ctrl_set = []
				zctrls_extra = {}
				for name, options in ctrl_items:
					try:
						if isinstance(options, int):
							options = { 'midi_cc': options }
						if 'midi_chan' not in options:
							options['midi_chan'] = processor.midi_chan
						midi_cc = options['midi_cc']
						logging.debug("CTRL %s: %s" % (midi_cc, name))
						options['name'] = str.replace(name, '_', ' ')
						zctrls_extra[name] = zynthian_controller(self, name, options)
						ctrl_set.append(name)
						if len(ctrl_set) >= 4:
							logging.debug("ADDING CONTROLLER SCREEN #"+str(c))
							self._ctrl_screens.append(['Extended#'+str(c),ctrl_set])
							ctrl_set = []
							c = c + 1
					except Exception as err:
						logging.error("Generating extra controller screens: %s" % err)

				if len(ctrl_set) >= 1:
					logging.debug("ADDING EXTRA CONTROLLER SCREEN #"+str(c))
					self._ctrl_screens.append(['Extended#' + str(c), ctrl_set])

				zctrls.update(zctrls_extra)

			except Exception as err:
				logging.error("Generating extra controllers config: %s" % err)

		return zctrls

	def send_controller_value(self, zctrl):
		try:
			izmop = zctrl.processor.chain.zmop_index
			if izmop is not None and izmop >= 0:
				mchan = zctrl.processor.part_i
				mval = zctrl.get_ctrl_midi_val()
				lib_zyncore.zmop_send_ccontrol_change(izmop, mchan, zctrl.midi_cc, mval)
		except Exception as err:
			logging.error(err)

	# ---------------------------------------------------------------------------
	# Specific functions
	# ---------------------------------------------------------------------------

	def load_soundfont(self, sf):
		if sf not in self.soundfont_index:
			logging.info(f"Loading SoundFont '{sf}' ...")
			# Send command to FluidSynth
			output = self.proc_cmd(f"load \"{sf}\"")
			# Parse ouput ...
			sfi = None
			cre = re.compile(r"loaded SoundFont has ID (\d+)")
			for line in output.split("\n"):
				#logging.debug(f" => {line}")
				res = cre.match(line)
				if res:
					sfi = int(res.group(1))
			# If soundfont was loaded succesfully ...
			if sfi is not None:
				logging.info(f"Loaded SoundFont '{sf}' => {sfi}")
				# Insert ID in soundfont_index dictionary
				self.soundfont_index[sf] = sfi
				# Return soundfont ID
				return sfi
			else:
				logging.warning("SoundFont '{}' can't be loaded".format(sf))
				return False
		else:
			return self.soundfont_index[sf]

	def unload_unused_soundfonts(self):
		# Make a copy of soundfont index and remove used soundfonts
		sf_unload = copy.copy(self.soundfont_index)
		for processor in self.processors:
			bi = processor.bank_info
			if bi is not None:
				if bi[2] and bi[0] in sf_unload:
					#print("Skip "+bi[0]+"("+str(sf_unload[bi[0]])+")")
					del sf_unload[bi[0]]
			pi = processor.preset_info
			if pi is not None:
				if pi[2] and pi[3] in sf_unload:
					#print("Skip "+pi[0]+"("+str(sf_unload[pi[3]])+")")
					del sf_unload[pi[3]]
		# Then, remove the remaining ;-)
		for sf, sfi in sf_unload.items():
			logging.info("Unload SoundFont => {}".format(sfi))
			self.proc_cmd("unload {}".format(sfi))
			del self.soundfont_index[sf]

	# Set presets for all processors to restore soundfont assign (select) after load/unload soundfonts 
	def set_all_presets(self):
		for processor in self.processors:
			if processor.preset_info:
				self.set_preset(processor, processor.preset_info)


	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

	@classmethod
	def zynapi_get_banks(cls):
		banks = []
		for b in cls.get_bank_filelist(recursion=2):
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
		return "sf2,sf3,zip,tgz,tar.gz,tar.bz2,tar.xz"

	@classmethod
	def zynapi_martifact_formats(cls):
		return "sf2,sf3"


# ******************************************************************************
