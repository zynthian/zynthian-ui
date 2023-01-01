# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_aeolus)
#
# zynthian_engine implementation for Aeolus
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
import copy
import shutil
import struct
import logging
import json
from  subprocess import Popen, DEVNULL
from time import sleep
import liblo

from . import zynthian_engine
from zyngine.zynthian_processor import zynthian_processor

#------------------------------------------------------------------------------
# Aeolus Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_aeolus(zynthian_engine):
	"""
	We use the default aeolus configuration that presents 4 divisions:
		III Upper swell division
		II Lower swell division
		I Great division
		P Pedal division
	Each division is controlled by a keyboard (manual or pedal)
	Only the swell divisions (II & III) have swell control (swell, trem freq, trem amp)
	There are several tuning temeraments which is configured when engine starts
	"""

	# ---------------------------------------------------------------------------
	# Manual and pedal configuration
	# ---------------------------------------------------------------------------

	keyboard_config_names = {
		15: "Manual I+II+III+Pedals",
		11: "Manual I+II+Pedals",
		9: "Manual I+Pedals",
		7: "Manual I+II+III",
		3: "Manual I+II",
		1: "Manual I"
	}

	# ---------------------------------------------------------------------------
	# Tuning temperaments
	# ---------------------------------------------------------------------------

	temperament_names = [
		"Pythagorean",
		"Meantone 1/4",
		"Werckmeister III",
		"Kimberger III",
		"Well Tempered",
		"Equally Tempered",
		"Vogel/Ahrend",
		"Vallotti",
		"Kellner",
		"Lehman",
		"Pure C/F/G"
	]

	# ---------------------------------------------------------------------------
	# Controllers & Screens
	# ---------------------------------------------------------------------------

	swell_ctrls = [
		['Swell', 7, 64],
		['Trem Freq', 12, 42],
		['Trem Amp', 13, 64],
	]

	instrument = [
		{
			"name": "Manual I",
			"ctrls":  [
				['Principal 8', 14, 'off', 'off|on', [2, 0]],
				['Principal 4', 15, 'off', 'off|on', [2, 1]],
				['Octave 2', 16, 'off', 'off|on', [2, 2]],
				['Octave 1', 17, 'off', 'off|on', [2, 3]],
				['Quint 5 1/3', 18, 'off', 'off|on', [2, 4]],
				['Quint 2 2/3', 19, 'off', 'off|on', [2, 5]],
				['Tibia 8', 20, 'off', 'off|on', [2, 6]],
				['Celesta 8', 21, 'off', 'off|on', [2, 7]],
				['Flöte 8', 22, 'off', 'off|on', [2, 8]],
				['Flöte 4', 23, 'off', 'off|on', [2, 9]],
				['Flöte 2', 24, 'off', 'off|on', [2, 10]],
				['Cymbel VI', 25, 'off', 'off|on', [2, 11]],
				['Mixtur', 26, 'off', 'off|on', [2, 12]],
				['Trumpet', 27, 'off', 'off|on', [2, 13]],
				['I+II', 28, 'off', 'off|on', [2, 14]],
				['I+III', 29, 'off', 'off|on', [2, 15]],
				['Sustain', 64, "off", "off|on"]
			],
			"ctrl_screens" : [
				['Manual I (1)', ['Principal 8', 'Principal 4', 'Octave 2', 'Octave 1']],
				['Manual I (2)', ['Quint 5 1/3', 'Quint 2 2/3', 'Tibia 8', 'Celesta 8']],
				['Manual I (3)', ['Flöte 8', 'Flöte 4', 'Flöte 2', 'Cymbel VI']],
				['Manual I (4)', ['Mixtur', 'Trumpet', 'I+II', 'I+III']],
				['Manual I (5)', ['Sustain']]
			]
		},
		{
			"name": "Manual II",
			"ctrls":  [
				['Rohrflöte 8', 30, 'off', 'off|on', [1, 0]],
				['Harmonic Flute 4', 31, 'off', 'off|on', [1, 1]],
				['Flauto Dolce 4', 32, 'off', 'off|on', [1, 2]],
				['Nasard 2 2/3', 33, 'off', 'off|on', [1, 3]],
				['Ottavina 2', 34, 'off', 'off|on', [1, 4]],
				['Tertia 1 3/5', 35, 'off', 'off|on', [1, 5]],
				['Sesqui-altera', 36, 'off', 'off|on', [1, 6]],
				['Septime', 37, 'off', 'off|on', [1, 7]],
				['None', 38, 'off', 'off|on', [1, 8]],
				['Krumhorn', 39, 'off', 'off|on', [1, 9]],
				['Melodia', 40, 'off', 'off|on', [1, 10]],
				['Tremulant', 41, 'off', 'off|on', [1, 11]],
				['II+III', 42, 'off', 'off|on', [1, 12]],
				['Sustain', 64, "off", "off|on"]
			] + swell_ctrls,
			"ctrl_screens" : [
				['Manual II (1)', ['Rohrflöte 8', 'Harmonic Flute 4', 'Flauto Dolce 4', 'Nasard 2 2/3']],
				['Manual II (2)', ['Ottavina 2', 'Tertia 1 3/5', 'Sesqui-altera', 'Septime']],
				['Manual II (3)', ['Krumhorn', 'Melodia', 'Tremulant', 'II+III']],
				['Manual II (4)', ['Swell', 'Trem Freq', 'Trem Amp', 'Sustain']]
			]
		},
		{
			"name": "Manual III",
			"ctrls":  [
				['Principal 8', 43, 'off', 'off|on', [0, 0]],
				['Gemshorn 8', 44, 'off', 'off|on', [0, 1]],
				['Quinta-dena 8', 45, 'off', 'off|on', [0, 2]],
				['Suabile 8', 46, 'off', 'off|on', [0, 3]],
				['Rohrflöte 4', 47, 'off', 'off|on', [0, 4]],
				['Dulzflöte 4', 48, 'off', 'off|on', [0, 5]],
				['Quintflöte 2 2/3', 49, 'off', 'off|on', [0, 6]],
				['Super-octave 2', 50, 'off', 'off|on', [0, 7]],
				['Sifflet 1', 51, 'off', 'off|on', [0, 8]],
				['Cymbel VI', 52, 'off', 'off|on', [0, 9]],
				['Oboe', 53, 'off', 'off|on', [0, 10]],
				['Tremulant', 54, 'off', 'off|on', [0, 11]],
				['Sustain', 64, "off", "off|on"]
			] + swell_ctrls,
			"ctrl_screens" : [
				['Manual III (1)', ['Principal 8', 'Gemshorn 8', 'Quinta-dena 8', 'Suabile 8']],
				['Manual III (2)', ['Rohrflöte 4', 'Dulzflöte 4', 'Quintflöte 2 2/3', 'Super-octave 2']],
				['Manual III (3)', ['Sifflet 1', 'Cymbel VI', 'Oboe', 'Tremulant']],
				['Manual III (4)', ['Swell', 'Trem Freq', 'Trem Amp', 'Sustain']]
			]
		},
		{
			"name": "Pedals",
			"ctrls":  [
				['Subbass 16', 55, 'off', 'off|on', [3, 0]],
				['Principal 16', 56, 'off', 'off|on', [3, 1]],
				['Principal 8', 57, 'off', 'off|on', [3, 2]],
				['Principal 4', 58, 'off', 'off|on', [3, 3]],
				['Octave 2', 59, 'off', 'off|on', [3, 4]],
				['Octave 1', 60, 'off', 'off|on', [3, 5]],
				['Quint 5 1/3', 61, 'off', 'off|on', [3, 6]],
				['Quint 2 2/3', 62, 'off', 'off|on', [3, 7]],
				['Mixtur', 63, 'off', 'off|on', [3, 8]],
				['Fagott 16', 64, 'off', 'off|on', [3, 9]],
				['Trombone 16', 65, 'off', 'off|on', [3, 10]],
				['Bombarde 32', 66, 'off', 'off|on', [3, 11]],
				['Trumpet', 67, 'off', 'off|on', [3, 12]],
				['P+I', 68, 'off', 'off|on', [3, 13]],
				['P+II', 69, 'off', 'off|on', [3, 14]],
				['P+III', 70, 'off', 'off|on', [3, 15]],
				['Sustain', 64, "off", "off|on"]
			],
			"ctrl_screens" : [
				['Pedals (1)', ['Subbass 16', 'Principal 16', 'Principal 8', 'Principal 4']],
				['Pedals (2)', ['Octave 2', 'Octave 1', 'Quint 5 1/3', 'Quint 2 2/3']],
				['Pedals (3)', ['Trumpet', 'P+I', 'P+II', 'P+III']],
				['Pedals (4)', ['Sustain']]
			]
		}
	]

	_ctrls=[]
	_ctrl_screens=[]

	#----------------------------------------------------------------------------
	# Config variables
	#----------------------------------------------------------------------------

	#TODO: Do not use system default files
	waves_dpath = "/usr/share/aeolus/stops/waves"
	config_fpath = "/usr/share/aeolus/stops/Aeolus/definition"
	presets_fpath = "/root/.aeolus-presets"
	presets_fpath_stub = "/zynthian/zynthian-data/aeolus/aeolus-presets-"
	#presets_fpath = "/usr/share/aeolus/stops/Aeolus/presets"

	n_banks = 32
	n_presets = 32
	stop_cc_num = 98
	ctrl_cc_num_start = 14

	#----------------------------------------------------------------------------
	# Initialization
	#----------------------------------------------------------------------------

	def __init__(self, state_manager=None):
		super().__init__(state_manager)
		self.name = "Aeolus"
		self.nickname = "AE"
		self.jackname = "aeolus"

		self.options['midi_chan'] = False
		self.options['replace'] = False
		self.options['drop_pc'] = True #TODO: This does not seem to be working
		self.options['layer_audio_out'] = False #TODO: What???
		self.last_preset = None # Last selected preset info
		self.proc_start_sleep = 1

		if self.config_remote_display():
			self.command = ["aeolus"]
		else:
			self.command = ["aeolus", "-t"]

		self.get_current_config()
		self.read_presets_file()

		self.keyboard_config = None
		self.temperament = None
		self.reset()


	def start(self):
		self.config_remote_display()
		self.proc = Popen(self.command, stdout=DEVNULL, stderr=DEVNULL, env=self.command_env)
		sleep(self.proc_start_sleep)


	def get_current_config(self):
		# Get current config ...
		with open(self.config_fpath, 'r') as cfg_file:
			self.config_lines = cfg_file.readlines()
			for line in self.config_lines:
				if line.startswith("/tuning"):
					parts = line[8:].split(' ')
					try:
						self.current_tuning_freq = float(parts[0])
						logging.info("Current tuning frequency = {:.1f}".format(self.current_tuning_freq))
					except Exception as e:
						logging.error("Can't get current tuning frequency! Using default (440.0 Hz) => {}".format(e))
						self.current_tuning_freq = 440.0
					try:
						self.current_temperament = int(parts[1])
						logging.info("Current tuning temperament = {:d}".format(self.current_temperament))
					except Exception as e:
						logging.error("Can't get current tuning temperament! Using default (Equally Tempered) => {}".format(e))
						self.current_temperament = 5


	def set_tuning(self, freq=None):
		"""Write fine tuning to config
		
		freq : Fine tuning frequency (Default : 440.0)
		Returns : True if changed
		"""
		
		# Generate tuning line
		if freq is None:
			freq = 440.0
		tuning_line = "/tuning {:.1f} {:d}\n".format(freq, self.temperament)
		# Get current config ...
		for i, line in enumerate(self.config_lines):
			if line.startswith("/tuning"):
				if line != tuning_line:
					self.config_lines[i] = tuning_line
					with open(self.config_fpath, 'w+') as cfg_file:
						cfg_file.writelines(self.config_lines)
					self.del_waves()
					return True
				break
		return False
	

	def del_waves(self):
		# We delete any existing waveforms because we don't have a way to save and hence recreate the waveforms
		try:
			shutil.rmtree(self.waves_dpath, ignore_errors=True)
			os.mkdir(self.waves_dpath)
			logging.info("Waves deleted! Retuning ...")
		except Exception as e:
			logging.error("Can't delete waves! => {}".format(e))


	def is_empty_waves(self):
		if not os.listdir(self.waves_dpath):
			return True
		else:
			return False


	def get_path(self, layer):
		path = self.name
		if not self.keyboard_config:
			path += "/Keyboards"
		elif not self.temperament:
			path += "/Temperament"
		else:
			chan_name = self.instrument[layer.aeolus_chan]['name']
			if chan_name:
				path = path + '/' + chan_name
		return path


	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------

	def add_layer(self, layer):
		layer.aeolus_chan = 0
		super().add_layer(layer)


	#----------------------------------------------------------------------------
	# Bank Managament
	#----------------------------------------------------------------------------

	def get_bank_list(self, layer=None):
		"""Get list of bank_info structures
		
		bank_info is list: [bank uri, bank index, bank title]
		Before engine is fully configured, returns setup lists: keyboard layouts, temperaments
		"""
		res = []
		if not self.keyboard_config:
			for i, title in self.keyboard_config_names.items():
				res.append((title, i, title))
		elif not self.temperament:
			for i, title in enumerate(self.temperament_names):
				res.append((title, i, title))
			#TODO: Select current setting in GUI: self.state_manager.screens['bank'].index = self.current_temperament-1
		else:
			for index, bank in enumerate(self.presets):
				res.append((bank, index, bank))
			for l in self.layers:
				l.bank_list = res
		return res


	def set_bank(self, layer, bank_info):
		"""Select a bank
		
		layer : Instance of engine (processor)
		bank_info : Bank info structure
		Before engine configured accepts keyboard layout or temperament
		"""
		if not self.keyboard_config:
			self.keyboard_config = bank_info[1]
			return None
		elif not self.temperament:
			self.temperament = bank_info[1]
			self.name = f"Aeolus {bank_info[0]}"
			res = False

			# Add extra layers
			chain_manager = self.state_manager.chain_manager
			for i in range(1, 4):
				if self.keyboard_config & 1 << i:
					midi_chan = chain_manager.get_next_free_midi_chan(self.layers[0].midi_chan)
					if midi_chan is None:
						break
					chain_id = chain_manager.add_chain(None, midi_chan)
					chain = chain_manager.get_chain(chain_id)
					proc_id = chain_manager.get_available_processor_id()
					processor = zynthian_processor("AE", chain_manager.engine_info["AE"], proc_id)
					chain.insert_processor(processor)
					chain_manager.processors[proc_id] = processor
					self.layers.append(processor)
					processor.engine = self
					chain.audio_out = []
					chain.mixer_chan = None
					processor.aeolus_chan = i

			# Update preset config with used MIDI channels
			"""
			From offset 16 within file, there are 8 MIDI preset configurations
			Each configuration consists of 16 x 16-bit words, one for each MIDI channel
			Each word consists of:
				Bit 14: Enable Continuous Control (binary flag)
				Bit 13: Enable Division specific CC, i.e. swell, Trem Freq, Trem Amp (binary flag)
				    Bits 8..11 indicate which division (BCD)
				Bit 12: Enable Keyboard (binary flag)
			    	Bits 0..3 indicate which keyboard the MIDI channel controls (BCD)

			We want to enable CC for all chains, swell CC for III & II and relevant keyboard for each chain
			"""
			keyboard_order = [2,1,0,3] # Order of manuals/pedals in aeolus native config
			with open(self.presets_fpath, mode='rb+') as file:
				file.seek(16)
				for chan in range(16):
					val = 0
					for i, layer in enumerate(self.layers):
						if layer.midi_chan == chan:
							keyboard = keyboard_order[i]
							val = 0x5000 | keyboard
							if keyboard < 2:
								# First two keyboards (III,II) are swell manuals
								val |= 0x2000 + (keyboard << 8)
							break
					file.write(struct.pack("H", val))

			# Load preset file and generate controllers
			for layer in self.layers:
				layer.refresh_controllers()

			# Select first chain so that preset selection is on "Upper" manual
			chain_manager.set_active_chain_by_id(chain_manager.get_chain_id_by_processor(self.layers[0]))

		else:
			res = True

		if self.set_tuning(self.state_manager.fine_tuning_freq) or not self.proc:
			self.stop()
			self.start()
			self.state_manager.autoconnect_midi(True)
			self.state_manager.autoconnect_audio()
			self.layers[0].load_bank_list()
			self.layers[0].reset_bank()
			
			if not res:
				return None

		self.state_manager.zynmidi.set_midi_bank_lsb(layer.get_midi_chan(), bank_info[1])
		#Change Bank for all Layers
		for l in self.layers:
			if l != layer:
				l.bank_index = layer.bank_index
				l.bank_name = layer.bank_name
				l.bank_info = copy.deepcopy(bank_info)
		return True

	#----------------------------------------------------------------------------
	# Preset Managament
	#----------------------------------------------------------------------------

	def get_preset_list(self, bank):
		res = []
		for preset in self.presets[bank[0]]:
			res.append([f"{bank[1]}/{preset}", bank[0], preset, None])
		return res


	def set_preset(self, layer, preset_info, preload=False):
		preset = self.presets[preset_info[1]][preset_info[2]]

		#Send Program Change to engine
		self.state_manager.zynmidi.set_midi_preset(layer.get_midi_chan(), 0, 0, 0)
		#self.state_manager.zynmidi.set_midi_preset(layer.get_midi_chan(), preset[1][0], preset[1][1], preset[1][2])

		if not preload:
			#Update Controller Values
			for l in self.layers:
				for zctrl in l.controllers_dict.values():
					try:
						value = preset[str(l.aeolus_chan)][zctrl.symbol]
						zctrl.set_value(value, True)
					except:
						pass

			layer.preset_name = preset_info[2]
			layer.preset_info = copy.deepcopy(preset_info)

			#Change Preset for all Layers
			for l in self.layers:
				if l != layer:
					l.preset_index = layer.preset_index
					l.preset_name = layer.preset_name
					l.preset_info = copy.deepcopy(layer.preset_info)
					l.preset_bank_index = l.bank_index
					l.preload_index = l.preset_index
					l.preload_name = l.preset_name
					l.preload_info = l.preset_info

		return True

	def save_all_presets(self):
		try:
			#TODO: Use config dir
			os.mkdir("/zynthian/zynthian-my-data/presets/aeolus")
		except:
			pass
		with open("/zynthian/zynthian-my-data/presets/aeolus/presets", "w") as file:
			json.dump(self.presets, file)


	def save_preset(self, bank_info, preset_name):
		#TODO: Update aeolus native preset file
		state = {}
		for layer in self.layers:
			state[layer.aeolus_chan] = {}
			for symbol in layer.controllers_dict:
				state[layer.aeolus_chan][symbol] = layer.controllers_dict[symbol].value
		self.presets[bank_info[1]][preset_name] = state
		self.save_all_presets()
		return f"{bank_info[1]}/{preset_name}"


	def delete_preset(self, bank_info, preset_info):
		if bank_info[1] in self.presets and preset_info[2] in self.presets[bank_info[1]]:
			del self.presets[bank_info[1]][preset_info[2]]
		self.save_all_presets()

	def preset_exists(self, bank_info, preset_name):
		return bank_info[1] in self.presets and preset_name in self.presets[bank_info[1]]

	def is_preset_user(self, preset_info):
		return not preset_info[1] == "Factory Presets"


	#----------------------------------------------------------------------------
	# Controllers Managament
	#----------------------------------------------------------------------------


	def get_controllers_dict(self, layer):
		self._ctrls = self.instrument[layer.aeolus_chan]['ctrls']
		self._ctrl_screens = self.instrument[layer.aeolus_chan]['ctrl_screens']
		return super().get_controllers_dict(layer)


	def send_controller_value(self, zctrl):
		for c in self.swell_ctrls + ["Sustain"]:
			if zctrl.symbol == c[0]:
				self.state_manager.zynmidi.set_midi_control(zctrl.midi_chan, zctrl.midi_cc, zctrl.value)
				return
		if zctrl.value:
			mm = "10"
		else:
			mm = "01"
		v1 = "01{0}0{1:03b}".format(mm, zctrl.graph_path[0])
		v2 = "000{0:05b}".format(zctrl.graph_path[1])
		self.state_manager.zynmidi.set_midi_control(zctrl.midi_chan, self.stop_cc_num, int(v1, 2))
		self.state_manager.zynmidi.set_midi_control(zctrl.midi_chan, self.stop_cc_num, int(v2, 2))
		#logging.debug("Aeolus Stop ({}) => mm={}, group={}, button={})".format(val,mm,zctrl.graph_path[0],zctrl.graph_path[1]))

	#--------------------------------------------------------------------------
	# Special
	#--------------------------------------------------------------------------

	def read_presets_file(self):
		# Get user presets
		try:
			with open("/zynthian/zynthian-my-data/presets/aeolus/presets", "r") as file:
				self.presets = json.load(file)
		except:
			pass
		# Get factory presets
		with open(self.presets_fpath, mode='rb') as file:
			data = file.read()
		pos = 0
		header = struct.unpack("6sbHHHH", data[pos:16])
		if header[0].decode('ASCII') != "PRESET":
			logging.error("FORMAT => Bad Header")
			return
		pos += 16
		n_divs = header[5]
		if n_divs != len(self.instrument):
			logging.error("Number of groups ({}) doesn't fit with engine's configuration ({}) !".format(n_divs, len(self.instrument)))
			return
		chan_config = []

		for num in range(8):
			chan_config.append([])
			for group in range(16):
				res = struct.unpack("H", data[pos:pos + 2])
				pos += 2
				chan_config[num].append(res[0])
				logging.debug("CHAN CONFIG (NUM {0}, GROUP {1} => {2:b}".format(num,group,res[0]))

		for i, group in enumerate(self.instrument):
			group['chan'] = chan_config[0][i] & 0xF

		self.presets["Factory Presets"] = {}
		preset_index = 1
		try:
			while True:
				res = struct.unpack("BBBB", data[pos:pos+4])
				pos += 4
				preset = {"0": {}, "1": {}, "2": {}, "3": {}}
				for i in range(n_divs):
					division = [2, 1, 0, 3][i]
					raw_ctrls = struct.unpack("I", data[pos:pos + 4])[0]
					pos += 4
					for ctrl in self.instrument[division]["ctrls"]:
						preset[str(division)][ctrl[0]] = (raw_ctrls & 1) * 127
						raw_ctrls = raw_ctrls >> 1
				self.presets["Factory Presets"][f"Preset {preset_index:02d}"] = preset
				preset_index += 1
		except:
			# Exception when reach end of file's data
			pass


	# ---------------------------------------------------------------------------
	# Extended Config
	# ---------------------------------------------------------------------------

	def get_extended_config(self):
		xconfig = { 
			'keyboard': self.keyboard_config,
			'temperament': self.temperament
		}
		return xconfig


	def set_extended_config(self, xconfig):
		if "temperament" in xconfig:
			self.temperament = xconfig['temperament']
		elif "tuning_temp" in xconfig:
			# Legacy config
			self.temperament = xconfig['tuning_temp']
		self.name = f"Aeolus {self.temperament_names[self.temperament]}"
		if "keyboard" in xconfig:
			self.keyboard_config = xconfig['keyboard']


#******************************************************************************
