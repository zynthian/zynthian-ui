# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_aeolus)
#
# zynthian_engine implementation for Aeolus
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

import copy
import json
import logging
import pexpect
from time import sleep
from subprocess import Popen, DEVNULL
from os.path import exists as file_exists

import zynautoconnect
from . import zynthian_engine
from zyngine.zynthian_processor import zynthian_processor
from zynconf import ServerPort

# ------------------------------------------------------------------------------
# Aeolus Engine Class
# ------------------------------------------------------------------------------


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

	divisions = [
		"III Upper Swell",
		"II Lower Swell",
		"I Great",
		"Pedal"
	]

	# Binary flags: Bit 0: III, 1: II, 2: I, 3: Pedals
	keyboard_config_names = {
		0b1111: "Manual I+II+III+Pedals",
		0b1101: "Manual I+III+Pedals",
		0b1110: "Manual I+II+Pedals",
		0b1100: "Manual I+Pedals",
		0b1000: "Pedals",
		0b0111: "Manual I+II+III",
		0b0101: "Manual I+III",
		0b0110: "Manual I+II",
		0b0100: "Manual I"
	}

	# ---------------------------------------------------------------------------
	# Tuning temperaments
	# ---------------------------------------------------------------------------

	temperament_names = {
		5: "Equally Tempered",
		4: "Well Tempered",
		1: "Meantone 1/4",
		2: "Werckmeister III",
		3: "Kimberger III",
		6: "Vogel/Ahrend",
		7: "Vallotti",
		8: "Kellner",
		9: "Lehman",
		10: "Pure C/F/G",
		0: "Pythagorean"
	}

	# ---------------------------------------------------------------------------
	# Controllers & Screens
	# ---------------------------------------------------------------------------

	swell_ctrls = [
		['Swell', 7, 64],
		['Trem Freq', 12, 42],
		['Trem Amp', 13, 64],
	]

	common_ctrls = [
		['Sustain', 64, 'off', 'off|on'],
		['Azimuth', {'midi_cc': 14, 'value_min':-0.5, 'value_max':0.5}],
		['Width', {'midi_cc': 15, 'value':0.8, 'value_max':1.0}],
		['Direct', {'midi_cc': 16, 'value':-9.5, 'value_min':-22.0, 'value_max':0.0}],
		['Reflect', {'midi_cc': 17, 'value':-16.5, 'value_min':-22.0, 'value_max':0.0}],
		['Reverb', {'midi_cc': 18, 'value':-15, 'value_min':-22.0, 'value_max':0.0}]
	]

	# TODO: The following controls are common to all so should ideally only be in the "main" chain
	audio_ctrls = [
		['Delay', {'midi_cc': 20, 'value':60, 'value_min':0, 'value_max':150}],
		['Rev Time', {'midi_cc': 21, 'value':4.0, 'value_min':2.0, 'value_max':7.0}],
		['Rev Pos', {'midi_cc': 22, 'value':0.5, 'value_min':-1.0, 'value_max':1.0}],
		['Volume', {'midi_cc': 23, 'value':-15, 'value_min':-22, 'value_max':0.0}]
	]

	common_ctrl_screens = [
			["Audio (1)", ['Azimuth', 'Width', 'Direct', 'Reflect']],
			["Audio (2)", ['Reverb', 'Sustain']]
	]

	audio_ctrl_screens = [
		['Audio (3)', ['Delay', 'Rev Time', 'Rev Pos', 'Volume']]
	]

	instrument = [
		{
			# Manual III
			"ctrls": [
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
			] + swell_ctrls + common_ctrls,
			"ctrl_screens": [
				['Stops (1)', ['Principal 8', 'Gemshorn 8', 'Quinta-dena 8', 'Suabile 8']],
				['Stops (2)', ['Rohrflöte 4', 'Dulzflöte 4', 'Quintflöte 2 2/3', 'Super-octave 2']],
				['Stops (3)', ['Sifflet 1', 'Cymbel VI', 'Oboe', 'Tremulant']],
				['Swell', ['Swell', 'Trem Freq', 'Trem Amp']]
			] + common_ctrl_screens
		},
		{
			# Manual II
			"ctrls": [
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
				['Sustain', 64, "off", "off|on"],
				['Reverb', 91, 64]
			] + swell_ctrls + common_ctrls,
			"ctrl_screens": [
				['Stops (1)', ['Rohrflöte 8', 'Harmonic Flute 4', 'Flauto Dolce 4', 'Nasard 2 2/3']],
				['Stops (2)', ['Ottavina 2', 'Tertia 1 3/5', 'Sesqui-altera', 'Septime']],
				['Stops (3)', ['Krumhorn', 'Melodia', 'Tremulant', 'II+III']],
				['Swell', ['Swell', 'Trem Freq', 'Trem Amp']]
			] + common_ctrl_screens
		},
		{
			# Manual I
			"ctrls": [
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
				['Sustain', 64, "off", "off|on"],
				['Reverb', 91, 64]
			] + common_ctrls,
			"ctrl_screens": [
				['Stops (1)', ['Principal 8', 'Principal 4', 'Octave 2', 'Octave 1']],
				['Stops (2)', ['Quint 5 1/3', 'Quint 2 2/3', 'Tibia 8', 'Celesta 8']],
				['Stops (3)', ['Flöte 8', 'Flöte 4', 'Flöte 2', 'Cymbel VI']],
				['Stops (4)', ['Mixtur', 'Trumpet', 'I+II', 'I+III']]
			] + common_ctrl_screens
		},
		{
			# Pedals
			"ctrls": [
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
				['Sustain', 64, "off", "off|on"],
				['Reverb', 91, 64]
			] + common_ctrls,
			"ctrl_screens": [
				['Stops (1)', ['Subbass 16', 'Principal 16', 'Principal 8', 'Principal 4']],
				['Stops (2)', ['Octave 2', 'Octave 1', 'Quint 5 1/3', 'Quint 2 2/3']],
				['Stops (3)', ['Mixtur', 'Fagott 16', 'Trombone 16', 'Bombarde 32']],
				['Stops (4)', ['Trumpet', 'P+I', 'P+II', 'P+III']]
			] + common_ctrl_screens
		}
	]

	_ctrls = []
	_ctrl_screens = []

	# ----------------------------------------------------------------------------
	# Config variables
	# ----------------------------------------------------------------------------

	# TODO: Use paths from global config
	stops_fpath = "/zynthian/zynthian-data/aeolus/stops"
	user_presets_fpath = "/zynthian/zynthian-my-data/presets/aeolus.json"
	default_presets_fpath = "/zynthian/zynthian-data/presets/aeolus.json"

	stop_cc_num = 98

	# ----------------------------------------------------------------------------
	# Initialization
	# ----------------------------------------------------------------------------

	def __init__(self, state_manager=None):
		super().__init__(state_manager)
		self.config_remote_display()
		self.name = "Aeolus"
		self.nickname = "AE"
		self.jackname = "aeolus"
		self.osc_target_port = ServerPort["aeolus_osc"]

		self.options['replace'] = False
		self.ready = True

		self.keyboard_config = None
		self.temperament = None
		self.restart_flag = False
		self.get_current_config()
		self.load_presets()

	def wait_for_ready(self, timeout=10):
		"""Wait for aeolus to be ready
		"""

		self.proc_get_output()
		self.ready = True

	def osc_wait_for_ready(self, timeout=10):
		"""Wait for aeolus to be ready

		timeout : Max seconds to wait (Default: 10) or None to wait indefinitely
		Blocks until ready or timeout
		Set self.ready to False before calling action that will trigger ready signal
		"""

		logging.debug("Waiting aeolus for ready ...")
		if timeout is None:
			while not self.ready:
				sleep(0.25)
			return
		while timeout > 0:
			if self.ready:
				logging.debug("Aeolus is ready!")
				return
			timeout -= 0.25
			sleep(0.25)
		logging.error("Aeolus not ready!!")

	def start(self):
		self.state_manager.start_busy("start_aeolus")
		chain_manager = self.state_manager.chain_manager
		midi_chan = self.processors[0].midi_chan
		proc_i = 0
		for i in range(3, -1, -1):
			if (1 << i) & self.keyboard_config:
				if proc_i >= len(self.processors):
					# First chain is already added
					proc_id = chain_manager.get_available_processor_id()
					processor = zynthian_processor("AE", chain_manager.engine_info["AE"], proc_id)
					chain_id = chain_manager.add_chain(None, midi_chan + proc_i)
					chain = chain_manager.get_chain(chain_id)
					chain.insert_processor(processor)
					chain_manager.processors[proc_id] = processor
					self.add_processor(processor)

				processor = self.processors[proc_i]
				chain_id = processor.chain_id
				try:
					processor.division
				except:
					processor.division = i
				chain = chain_manager.get_chain(chain_id)
				if proc_i:
					chain.audio_out = []
					chain.mixer_chan = None

				processor.refresh_controllers()

				proc_i += 1

		# Disable mixer strip for extra manuals
		for i, processor in enumerate(self.processors):
			if i:
				chain_manager.get_chain(processor.chain_id).mixer_chan = None

		# Select first chain so that preset selection is on "Grand manual"
		chain_manager.set_active_chain_by_id(self.processors[0].chain_id)

		self.get_current_config()
		#self.command = ["aeolus", f"-o {self.osc_target_port}", f"-O localhost:{self.osc_server_port}", f"-S {self.stops_fpath}"]
		self.command = f"aeolus -o {self.osc_target_port} -O localhost:{self.osc_server_port} -S {self.stops_fpath}"
		if not self.config_remote_display():
			#self.command.append("-t")
			self.command += " -t"
		self.command_prompt = "\nReady"
		self.ready = False
		self.osc_init()
		# self.proc = Popen(self.command, stdout=DEVNULL, stderr=DEVNULL, env=self.command_env)
		self.proc = pexpect.spawn(self.command, timeout=self.proc_timeout, env=self.command_env, cwd=self.command_cwd)
		self.proc.delaybeforesend = 0
		self.wait_for_ready()
		self.set_tuning()
		self.set_midi_chan()

		# Need to call autoconnect because engine starts later than chain/processor autorouting
		zynautoconnect.request_midi_connect(True)
		zynautoconnect.request_audio_connect(True)
		self.state_manager.end_busy("start_aeolus")

	def stop(self):
		if self.proc:
			try:
				logging.info("Stoping Engine " + self.name)
				self.osc_server.send(self.osc_target, '/exit')
				sleep(0.2)
				if self.proc.isalive():
					self.proc.terminate(True)
				#try:
				#	self.proc.wait(0.2)
				#except:
				#	self.proc.terminate()
				#	try:
				#		self.proc.wait(0.2)
				#	except:
				#		self.proc.kill()
				self.proc = None
			except Exception as err:
				logging.error("Can't stop engine {} => {}".format(self.name, err))
		self.osc_end()
		self.restart_flag = False

	def get_current_config(self):
		# Get current config ...
		with open(f"{self.stops_fpath}/Aeolus/definition", 'r') as cfg_file:
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

	def get_path(self, processor):
		path = self.name
		if self.keyboard_config is None:
			path += "/Divisions"
		elif self.temperament is None:
			path += "/Temperament"
		else:
			path = f"{self.get_name(processor)}/{self.temperament_names[self.temperament]}"
		return path

	# ---------------------------------------------------------------------------
	# Processor Management
	# ---------------------------------------------------------------------------

	def add_processor(self, processor):
		self.processors.append(processor)
		processor.jackname = self.jackname
		processor.engine = self
		processor.bank_info = ("General", 0, "General")

	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	def set_midi_chan(self, processor=None):
		"""Update the MIDI channels that aeolus listens to

		processor : Processor (not used - always updates all)

		MIDI configuration is set by sending osc command to /store_midi_config with 17 integer values
		First value defines the MIDI preset configuration to store (0..7)
		The next 16 values define each MIDI channel configuration as bitwise flags:
			0x1000: Enable keyboards - bits 0..1 define which keyboard:
				0x1000: Keyboard III
				0x1001: Keyboard II
				0x1002: Keyboard I
				0x1003: Pedals
			0x2000: Enable divisions - bit 2 defines which division:
				0x2000: Division III
				0x2010: Division II
			0x4000: Enable control
		Note: There are other bit combinations that produce other results but this looks like software bug
		"""

		if self.osc_server is None:
			return
		midi_config = []
		for chan in range(16):
			val = 0
			for processor in self.processors:
				if processor.midi_chan == chan:
					val = 0x5000 | processor.division
					if processor.division < 2:
						# Keyboards II & III are swell manuals
						val |= 0x2000 + (processor.division << 4)
					break
			midi_config.append(("i", val))

		# We only care about first MIDI config preset
		self.osc_server.send(self.osc_target, "/store_midi_config", ("i", 0), *midi_config)
		# Don't save - we configure MIDI for this session only

	# ----------------------------------------------------------------------------
	# Bank Managament
	# ----------------------------------------------------------------------------

	def get_bank_list(self, processor=None):
		"""Get list of bank_info structures
		
		bank_info is list: [bank uri, bank index, bank title]
		Before engine is fully configured, returns setup lists: keyboard layouts, temperaments
		"""

		res = []
		current_sel = 0
		if self.keyboard_config is None:
			for i, title in self.keyboard_config_names.items():
				res.append((title, i, title))
		elif self.temperament is None:
			i = 0
			for value, title in self.temperament_names.items():
				res.append((title, value, title))
				if value == self.current_temperament:
					current_sel = i
				i += 1
		elif processor.preset_info is None:
			res = [("General", 0, "General")]
		else:
			res = [("General", 0, "General"), (processor.division, None, f"Local {processor.division}")]
		if res:
			processor.bank_info = res[current_sel]
		return res

	def set_bank(self, processor, bank_info):
		"""Select a bank
		
		processor : Instance of engine (processor)
		bank_info : Bank info structure [uri, index, name]
		Returns - True if bank selected, None if more bank selection steps required or False on failure
		Before engine configured accepts keyboard layout or temperament
		"""

		if self.keyboard_config is None:
			self.keyboard_config = bank_info[1]
			return None
		elif self.temperament is None:
			self.temperament = bank_info[1]

		if self.restart_flag:
			self.stop()
		if not self.proc:
			self.start()
			return None

		self.state_manager.zynmidi.set_midi_bank_lsb(processor.get_midi_chan(), bank_info[1])
		return True

	# ----------------------------------------------------------------------------
	# Preset Managament
	# ----------------------------------------------------------------------------

	def get_preset_list(self, bank_info):
		res = []
		for index, preset_name in enumerate(self.presets):
			res.append([preset_name, bank_info[0], preset_name, index])
		return res

	def all_stops_off(self, processor=None):
		if processor == None:
			processors = self.processors
		else:
			processors = [processor]
		for l in processors:
			for zctrl in l.controllers_dict.values():
				zctrl.set_value(0, True)

	def set_preset(self, processor, preset_info, preload=False):
		preset = self.presets[preset_info[2]]

		# Update Controller Values
		for l in self.processors:
			if preset_info[1] == "General" or l == processor:
				for zctrl in l.controllers_dict.values():
					try:
						value = preset[str(l.division)][zctrl.symbol]
						zctrl.set_value(value, True)
					except:
						zctrl.set_value(zctrl.value, True)

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
		with open(f"{self.user_presets_fpath}", "w") as file:
			json.dump(self.presets, file)

	def save_preset(self, bank_info, preset_name):
		state = {}
		for processor in self.processors:
			division = str(processor.division)
			state[division] = {}
			for symbol in processor.controllers_dict:
				state[division][symbol] = processor.controllers_dict[symbol].value
		self.presets[preset_name] = state
		self.save_all_presets()
		return preset_name

	def delete_preset(self, bank_info, preset_info):
		try:
			self.presets.pop(preset_info[2])
		except:
			return
		self.save_all_presets()
		return len(self.presets)

	def rename_preset(self, bank_info, preset_info, new_name):
		try:
			self.presets[new_name] = self.presets.pop(preset_info[2])
			self.save_all_presets()
		except:
			pass

	def preset_exists(self, bank_info, preset_name):
		return preset_name in self.presets

	def is_preset_user(self, preset_info):
		# TODO: Do we want some factory defaults?
		return True
			
	# ----------------------------------------------------------------------------
	# Controllers Managament
	# ----------------------------------------------------------------------------

	def get_controllers_dict(self, processor):
		self._ctrls = self.instrument[processor.division]['ctrls']
		self._ctrl_screens = self.instrument[processor.division]['ctrl_screens']
		if processor == self.processors[0]:
			self._ctrls += self.audio_ctrls
			self._ctrl_screens += self.audio_ctrl_screens
		return super().get_controllers_dict(processor)

	def send_controller_value(self, zctrl):
		for c in self.swell_ctrls + self.common_ctrls + self.audio_ctrls:
			if zctrl.symbol == c[0]:
				#self.state_manager.zynmidi.set_midi_control(zctrl.midi_chan, zctrl.midi_cc, zctrl.value)
				raise Exception("MIDI handler")
		if zctrl.value:
			mm = "10"
		else:
			mm = "01"
		v1 = "01{0}0{1:03b}".format(mm, zctrl.graph_path[0])
		v2 = "000{0:05b}".format(zctrl.graph_path[1])
		self.state_manager.zynmidi.set_midi_control(zctrl.midi_chan, self.stop_cc_num, int(v1, 2))
		self.state_manager.zynmidi.set_midi_control(zctrl.midi_chan, self.stop_cc_num, int(v2, 2))
		#logging.debug("Aeolus Stop ({}) => mm={}, group={}, button={})".format(val,mm,zctrl.graph_path[0],zctrl.graph_path[1]))

	# --------------------------------------------------------------------------
	# Special
	# --------------------------------------------------------------------------

	def load_presets(self):
		# TODO: Ensure legacy presets are available
		# Get user presets
		if file_exists(self.user_presets_fpath):
			filename = self.user_presets_fpath
		else:
			filename = self.default_presets_fpath
		try:
			with open(filename, "r") as file:
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

		engine_state = { 
			"keyboard": self.keyboard_config,
			"temperament": self.temperament,
			"divisions": []
		}
		for processor in self.processors:
			engine_state["divisions"].append(processor.division)
		return engine_state

	def set_extended_config(self, engine_state):
		"""Set engine specific configuration
		
		engine_state : Configuration as dictionary
		"""

		if "temperament" in engine_state:
			self.temperament = engine_state['temperament']
		elif "tuning_temp" in engine_state:
			# Legacy config
			self.temperament = engine_state['tuning_temp'] #TODO: Retune if necessary

		current_keyboard = self.keyboard_config
		try:
			self.keyboard_config = engine_state['keyboard']
		except:
			# Legacy default is 4 keyboards
			if self.keyboard_config != 15:
				self.restart_flag = True
			self.keyboard_config = 15
		if current_keyboard != self.keyboard_config:
			self.restart_flag = True

		for i, processor in enumerate(self.processors):
			try:
				processor.division = engine_state["divisions"][i]
			except:
				processor.division = list(self.instrument)[i]

	def get_name(self, processor=None):
		try:
			return f"{self.name} {self.divisions[processor.division]}"
		except:
			return self.name

	# ----------------------------------------------------------------------------
	# OSC Managament
	# ----------------------------------------------------------------------------

	def cb_osc_all(self, path, args, types, src):
		if self.osc_server is None:
			return

		#logging.debug("Rx OSC => {} {}".format(path, args))
		if path == '/ready':
			self.ready = True

# ******************************************************************************
