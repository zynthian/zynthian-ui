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
import logging
import json
from  subprocess import Popen, DEVNULL
import pexpect
from collections import OrderedDict
from time import sleep

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

	temperament_names = OrderedDict()
	temperament_names[5] = "Equally Tempered"
	temperament_names[4] = "Well Tempered"
	temperament_names[1] = "Meantone 1/4"
	temperament_names[2] = "Werckmeister III"
	temperament_names[3] = "Kimberger III"
	temperament_names[6] = "Vogel/Ahrend"
	temperament_names[7] = "Vallotti"
	temperament_names[8] = "Kellner"
	temperament_names[9] = "Lehman"
	temperament_names[10] = "Pure C/F/G"
	temperament_names[0] = "Pythagorean"

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

	#TODO: Do not use system default files in /usr/share
	waves_dpath = "/usr/share/aeolus/stops/waves"
	config_fpath = "/usr/share/aeolus/stops/Aeolus/definition"
	presets_fpath = "/root/.aeolus-presets"
	presets_fpath_stub = "/zynthian/zynthian-data/aeolus/aeolus-presets-"
	#presets_fpath = "/usr/share/aeolus/stops/Aeolus/presets"

	stop_cc_num = 98

	#----------------------------------------------------------------------------
	# Initialization
	#----------------------------------------------------------------------------

	def __init__(self, state_manager=None):
		super().__init__(state_manager)
		self.config_remote_display()
		self.name = "Aeolus"
		self.nickname = "AE"
		self.jackname = "aeolus"
		self.osc_target_port = 9000

		self.options['midi_chan'] = False
		self.options['replace'] = False
		self.options['drop_pc'] = True #TODO: This does not seem to be working
		self.options['layer_audio_out'] = False #TODO: What???
		self.ready = True

		self.keyboard_config = None
		self.temperament = None
		self.reset() #TODO: Is this required?
		self.load_presets()


	def wait_for_ready(self, timeout=10):
		"""Wait for aeolus to be ready
		
		timeout : Max seconds to wait (Default: 10) or None to wait indefinitely
		Blocks until ready or timeout
		Set self.ready to False before calling action that will trigger ready signal
		"""

		if timeout is None:
			while not self.ready:
				sleep(0.25)
		while timeout > 0:
			if self.ready:
				return
			timeout -= 0.25
			sleep (0.25)


	def start(self):
		self.osc_init()
		self.get_current_config()
		self.ready = False
		self.command = f"aeolus -o {self.osc_target_port} -O localhost:{self.osc_server_port}"

		#self.command = ["aeolus", f"-o {self.osc_target_port}", f"-O localhost:{self.osc_server_port}"]
		if not self.config_remote_display():
			#self.command.append("-t")
			self.command += " -t"
		#self.proc = Popen(self.command, stdout=DEVNULL, stderr=DEVNULL, env=self.command_env)
		self.proc = pexpect.spawn(self.command, timeout=self.proc_timeout, env=self.command_env, cwd=self.command_cwd)
		self.wait_for_ready() #TODO: Avoid waiting twice (startup and tuning)
		self.set_tuning()
		self.set_midi_chans()


	def stop(self):
		if self.proc:
			try:
				logging.info("Stoping Engine " + self.name)
				self.osc_server.send(self.osc_target, '/exit')
				sleep(0.2)
				if self.proc.isalive():
					self.proc.terminate(True)
				self.proc = None
			except Exception as err:
				logging.error("Can't stop engine {} => {}".format(self.name, err))
		self.osc_end()


	def get_current_config(self):
		# Get current config ...
		with open(self.config_fpath, 'r') as cfg_file:
			config_lines = cfg_file.readlines()
		for line in config_lines:
			if line.startswith("/tuning"):
				parts = line[8:].split(' ')
				try:
					self.current_tuning_freq = float(parts[0])
				except Exception as e:
					self.current_tuning_freq = None
				try:
					self.current_temperament = int(parts[1])
				except Exception as e:
					self.current_temperament = None


	def set_tuning(self):
		"""Write fine tuning to config
		
		Returns : True if changed
		"""

		if self.current_tuning_freq == self.state_manager.fine_tuning_freq and self.current_temperament == self.temperament:
			return False

		self.current_tuning_freq = self.state_manager.fine_tuning_freq
		self.current_temperament = self.temperament
		self.ready = False
		self.osc_server.send(self.osc_target, "/retune", ("f", self.current_tuning_freq), ("i", self.current_temperament))
		self.wait_for_ready()
		self.osc_server.send(self.osc_target, "/save")
		return True


	def set_midi_chans(self):
		"""Update the MIDI channels that aeolus listens to"""

		keyboard_order = [2,1,0,3] # Order of manuals/pedals in aeolus native config
		midi_config = []
		for chan in range(16):
			val = 0
			for i, layer in enumerate(self.layers):
				if layer.midi_chan == chan:
					keyboard = keyboard_order[i]
					val = 0x5000 | keyboard
					if keyboard < 2:
						# First two keyboards (III,II) are swell manuals
						val |= 0x2000 + (keyboard << 4)
					break
			midi_config.append(("i", val))

		# We only care about first MIDI config preset
		self.osc_server.send(self.osc_target, "/store_midi_config", ("i", 0), *midi_config)
		# Don't save - we configure MIDI for this session only


	def get_path(self, layer):
		path = self.name
		if self.keyboard_config is None:
			path += "/Keyboards" #TODO: Should this be "/Divisions"?
		elif self.temperament is None:
			path += "/Temperament"
		else:
			path = f"{self.get_name(layer)}/{self.temperament_names[self.temperament]}"
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

		res = [] #TODO: Called twice twice during init
		if self.keyboard_config is None:
			for i, title in self.keyboard_config_names.items():
				res.append((title, i, title))
		elif self.temperament is None:
			for value, title in self.temperament_names.items():
				res.append((title, value, title))
			#TODO: Select current setting in GUI: self.state_manager.screens['bank'].index = self.current_temperament-1
		else:
			keyboard = self.instrument[layer.aeolus_chan]["name"]
			res = [("General", 0, "General"), (keyboard, 1, keyboard)]
			layer.bank_list = res
		return res


	def set_bank(self, layer, bank_info):
		"""Select a bank
		
		layer : Instance of engine (processor)
		bank_info : Bank info structure
		Before engine configured accepts keyboard layout or temperament
		"""
		if self.keyboard_config is None:
			self.keyboard_config = bank_info[1]
			return None
		elif self.temperament is None:
			self.temperament = bank_info[1]
			self.layers[0].load_bank_list()
			return None

		if not self.proc:
			chain_manager = self.state_manager.chain_manager
			if len(self.layers) <= 1:
				# Add extra layers
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
						processor.load_bank_list()

			for layer in self.layers:
				layer.refresh_controllers()

			# Select first chain so that preset selection is on "Upper" manual
			chain_manager.set_active_chain_by_id(chain_manager.get_chain_id_by_processor(self.layers[0]))

			self.start()
			self.state_manager.autoconnect_midi(True)
			self.state_manager.autoconnect_audio(True) #TODO: What's so urgent???
			self.layers[0].load_bank_list()
			self.layers[0].reset_bank()


		self.state_manager.zynmidi.set_midi_bank_lsb(layer.get_midi_chan(), bank_info[1])
		self.layers[0].load_bank_list()

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

	def get_preset_list(self, bank_info):
		#TODO: Support "General Pistions" (presets for all divisions) and and "Local Pistions" (presets for one division)
		res = []
		for index, preset in enumerate(self.presets[bank_info[0]]):
			res.append([f"{bank_info[0]}/{preset['name']}", bank_info[0], preset['name'], index])
		return res


	def set_preset(self, layer, preset_info, preload=False):
		preset = self.presets[preset_info[1]][preset_info[3]]

		#Update Controller Values
		for l in self.layers:
			if preset_info[1] == "General" or l == layer:
				for zctrl in l.controllers_dict.values():
					try:
						value = preset[str(l.aeolus_chan)][zctrl.symbol]
						zctrl.set_value(value, True)
					except:
						pass

			if not preload:
				l.preset_name = preset_info[2]
				l.preset_info = copy.deepcopy(preset_info)
				l.preset_index = preset_info[3]
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
		bank = bank_info[0]
		state = {"name": preset_name}
		for layer in self.layers:
			if bank == "General" or bank == self.instrument[layer.aeolus_chan]["name"]:
				state[layer.aeolus_chan] = {}
				for symbol in layer.controllers_dict:
					state[layer.aeolus_chan][symbol] = layer.controllers_dict[symbol].value
		index = self.get_preset_index(bank_info[1], preset_name)
		if index is None:
			index = len(self.presets[bank])
			self.presets[bank].append(state)
		else:
			self.presets[bank][index] = state
		self.save_all_presets()
		#self.osc_server.send(self.osc_target, "/store_preset", ("i", bank), ("i", index))
		#self.osc_server.send(self.osc_target, "/save")
		return f"{bank}/{preset_name}"


	def delete_preset(self, bank_info, preset_info):
		try:
			del self.presets[bank_info[1]][preset_info[3]]
		except:
			return
		self.save_all_presets()
		return len(self.presets[bank_info][1])

	def preset_exists(self, bank_info, preset_name):
		if self.get_preset_index(bank_info[1], preset_name) is None:
			return False
		return True

	def is_preset_user(self, preset_info):
		return True

	def get_preset_index(self, bank, preset_name):
		try:
			for index, preset in enumerate(self.presets[bank]):
				if preset['name'] == preset_name:
					return index
		except:
			pass
		return None
			

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

	def load_presets(self):
		# Get user presets
		try:
			with open("/zynthian/zynthian-my-data/presets/aeolus/presets", "r") as file:
				self.presets = json.load(file)
		except:
			self.presets = {}

	# ---------------------------------------------------------------------------
	# Extended Config
	# ---------------------------------------------------------------------------

	def get_extended_config(self):
		"""Get engine specific configuration
		
		Returns : Configuration as dictionary
		"""

		xconfig = { 
			"keyboard": self.keyboard_config,
			"temperament": self.temperament,
			"processors": []
		}
		for layer in self.layers:
			xconfig["processors"].append(layer.aeolus_chan)
		return xconfig


	def set_extended_config(self, xconfig):
		"""Set engine specific configuration
		
		xconfig : Configuration as dictionary
		"""
		
		if "temperament" in xconfig:
			self.temperament = xconfig['temperament']
		elif "tuning_temp" in xconfig:
			# Legacy config
			self.temperament = xconfig['tuning_temp']
		if "keyboard" in xconfig:
			self.keyboard_config = xconfig['keyboard']
		else:
			# Legacy default is 4 keyboards
			self.keyboard_config = 15

		chain_manager = self.state_manager.chain_manager
		for i, layer in enumerate(self.layers):
			chain = chain_manager.get_chain(chain_manager.get_chain_id_by_processor(layer))
			try:
				chain.aeolus_chan = xconfig["processors"][i]
			except:
				chain.aeolus_chan = i
			if i:
				chain.mixer_chan = None
		

	def get_name(self, layer):
		return f"{self.name} {self.instrument[layer.aeolus_chan]['name']}"


	#----------------------------------------------------------------------------
	# OSC Managament
	#----------------------------------------------------------------------------

	def cb_osc_all(self, path, args, types, src):
		if self.osc_server is None:
			return

		#logging.debug("Rx OSC => {} {}".format(path, args))
		if path == '/ready':
			self.ready = True

#******************************************************************************
