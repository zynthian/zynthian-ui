# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_alsa_mixer)
#
# zynthian_engine implementation for Alsa Mixer
#
# Copyright (C) 2015-2019 Fernando Moyano <jofemodo@zynthian.org>
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
import shlex
import logging
import threading
from time import sleep
from collections import OrderedDict
from subprocess import check_output, Popen, PIPE, DEVNULL, STDOUT

from zyncoder.zyncore import lib_zyncore
from . import zynthian_engine
from . import zynthian_controller
from zyngui import zynthian_gui_config

#------------------------------------------------------------------------------
# ALSA Mixer Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_alsa_mixer(zynthian_engine):

	sys_dir = os.environ.get('ZYNTHIAN_SYS_DIR',"/zynthian/zynthian-sys")

	#----------------------------------------------------------------------------
	# Config variables
	#----------------------------------------------------------------------------

	chan_names = ["Left", "Right"]

	# ---------------------------------------------------------------------------
	# Translations by device
	# ---------------------------------------------------------------------------

	if zynthian_gui_config.gui_layout == "Z2":
		chan_trans = ["1", "2"]
	else:
		chan_trans = chan_names

	translations_by_device = {
		"sndrpihifiberry": {
			"Digital Left": "Output {} Level".format(chan_trans[0]),
			"Digital Right": "Output {} Level".format(chan_trans[1]),
			"ADC Left": "Input {} Level".format(chan_trans[0]),
			"ADC Right": "Input {} Level".format(chan_trans[1]),
			"PGA Gain Left": "Input {} Gain".format(chan_trans[0]),
			"PGA Gain Right": "Input {} Gain".format(chan_trans[1]),
			"ADC Left Input": "Input {} Mode".format(chan_trans[0]),
			"ADC Right Input": "Input {} Mode".format(chan_trans[1]),
			"No Select": "Disabled",
			"VINL1[SE]": "Unbalanced Mono TS",
			"VINL2[SE]": "Unbalanced Mono TR",
			"VINL2[SE] + VINL1[SE]": "Stereo TRS to Mono",
			"{VIN1P, VIN1M}[DIFF]": "Balanced Mono TRS",
			"VINR1[SE]": "Unbalanced Mono TS",
			"VINR2[SE]": "Unbalanced Mono TR",
			"VINR2[SE] + VINR1[SE]": "Stereo TRS to Mono",
			"{VIN2P, VIN2M}[DIFF]": "Balanced Mono TRS"
		}
	}

	# ---------------------------------------------------------------------------
	# Controllers & Screens
	# ---------------------------------------------------------------------------

	_ctrl_screens = []

	#----------------------------------------------------------------------------
	# ZynAPI variables
	#----------------------------------------------------------------------------

	zynapi_instance = None

	#----------------------------------------------------------------------------
	# Initialization
	#----------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__(zyngui)

		self.type = "Mixer"
		self.name = "Audio Levels"
		self.nickname = "MX"

		self.audio_out = []
		self.options = {
			'clone': False,
			'note_range': False,
			'audio_route': False,
			'midi_chan': False,
			'replace': False,
			'drop_pc': False,
			'drop_cc': True
		}

		self.zctrls = None
		self.sender_poll_state = 0
		self.amixer_sender_proc = None

		self.get_soundcard_config()


		def stop(self):
			self.stop_sender_poll()
			super().stop()


	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------

	def add_layer(self, layer):
		super().add_layer(layer)


	def get_path(self, layer):
		return self.name

	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	#----------------------------------------------------------------------------
	# Bank Managament
	#----------------------------------------------------------------------------

	def get_bank_list(self, layer=None):
		return [("", None, "", None)]


	def set_bank(self, layer, bank):
		return True

	#----------------------------------------------------------------------------
	# Preset Managament
	#----------------------------------------------------------------------------

	def get_preset_list(self, bank):
		return [("", None, "", None)]


	def set_preset(self, layer, preset, preload=False):
		return True


	def cmp_presets(self, preset1, preset2):
		return True


	#----------------------------------------------------------------------------
	# Controllers Managament
	#----------------------------------------------------------------------------

	def allow_rbpi_headphones(self):
		try:
			if not callable(lib_zyncore.set_hpvol) and self.rbpi_device_name and self.device_name != self.rbpi_device_name:
				return True
			else:
				return False
		except:
			return False


	def get_controllers_dict(self, layer, ctrl_list=None):
		if ctrl_list == "*":
			ctrl_list = None
		elif ctrl_list is None:
			ctrl_list = copy.copy(self.ctrl_list)

		logging.debug("MIXER CTRL LIST: {}".format(ctrl_list))

		self.stop_sender_poll()

		zctrls = self.get_mixer_zctrls(self.device_name, ctrl_list)

		# Add HP amplifier interface if available
		try:
			if callable(lib_zyncore.set_hpvol):
				hp_zctrl = zynthian_controller(self, "Headphones", "Headphones", {
					'graph_path': lib_zyncore.set_hpvol,
					'value': lib_zyncore.get_hpvol(),
					'value_min': 0,
					'value_max': lib_zyncore.get_hpvol_max(),
					'is_integer': True
				})
				hp_zctrl.last_value_sent = None
				zctrls["Headphones"] = hp_zctrl
				#ctrl_list.insert(0, "Headphones")
				ctrl_list.append("Headphones")
				logging.debug("Added Headphones Amplifier volume control")
		except:
			pass

		# Add RBPi headphones if enabled and available... 
		if self.allow_rbpi_headphones() and self.zyngui and self.zyngui.get_zynthian_config("rbpi_headphones"):
			try:
				zctrls_headphones = self.get_mixer_zctrls(self.rbpi_device_name, ["Headphone", "PCM"])
				if "Headphone" in zctrls_headphones:
					hp_zctrl = zctrls_headphones["Headphone"]
				elif "PCM" in zctrls_headphones:
					hp_zctrl = zctrls_headphones["PCM"]
					hp_zctrl.symbol = hp_zctrl.name = hp_zctrl.short_name = "Headphone"
				else:
					raise Exception("RBPi Headphone volume control not found!")

				zctrls["Headphone"] = hp_zctrl
				#ctrl_list.insert(0, "Headphone")
				ctrl_list.append("Headphone")
				logging.debug("Added RBPi Headphone volume control")

			except Exception as e:
				logging.error("Can't configure headphones volume control: {}".format(e))

		# Sort zctrls to match the configured mixer control list
		if ctrl_list and len(ctrl_list) > 0:
			sorted_zctrls = OrderedDict()
			for ctrl_name in ctrl_list:
				trans_name = self.translate(ctrl_name)
				try:
					for k, zctrl in zctrls.items():
						if zctrl.name == trans_name:
							sorted_zctrls[k] = zctrl
							self.keep_midi_learn(zctrl)
				except:
					pass
		else:
			sorted_zctrls = zctrls

		# Generate control screens
		self._ctrl_screens = None
		self.generate_ctrl_screens(sorted_zctrls)

		self.zctrls = sorted_zctrls
		self.start_sender_poll()

		return sorted_zctrls


	def get_mixer_zctrls(self, device_name, ctrl_list):
		zctrls = OrderedDict()
		try:
			ctrls = check_output("amixer -M -c {}".format(device_name), shell=True).decode("utf-8").split("Simple mixer control ")
			for ctrl in ctrls:
				lines = ctrl.splitlines()
				if len(lines)==0:
					continue

				m = re.match("'(.*?)'.*", lines[0], re.M | re.I)
				if m:
					ctrl_name = m.group(1).strip()
					ctrl_symbol = ctrl_name.replace(' ', '_')
				else:
					ctrl_name = None
					ctrl_symbol = None
	
				ctrl_type = None
				ctrl_caps = None
				ctrl_chans = []
				ctrl_items = None
				ctrl_item0 = None
				ctrl_ticks = None
				ctrl_limits = None
				ctrl_maxval = 100
				ctrl_minval = 0
				ctrl_value = 50
				ctrl_values = []

				#logging.debug("MIXER CONTROL => {}\n{}".format(ctrl_name, ctrl))
				for line in lines[1:]:
					try:
						key, value = line.strip().split(": ",1)
						#logging.debug("  {} => {}".format(key,value))
					except:
						continue

					if key == 'Capabilities':
						ctrl_caps = value.split(' ')
						if 'enum' in ctrl_caps:
							ctrl_type = "Selector"
						elif 'volume' in ctrl_caps or 'pvolume' in ctrl_caps:
							ctrl_type = "Playback"
						elif 'cvolume' in ctrl_caps:
							ctrl_type = "Capture"
						elif 'pswitch' in ctrl_caps or 'cswitch' in ctrl_caps:
							ctrl_type = "Toggle"
							ctrl_items = ["off", "on"]
							ctrl_ticks = [0, 1]

					elif key == 'Playback channels':
						ctrl_chans = value.strip().split(' - ')

					elif key == 'Capture channels':
						ctrl_chans = value.strip().split(' - ')

					elif key == 'Limits':
						m = re.match(".*(\d+) - (\d+).*", value, re.M | re.I)
						if m:
							ctrl_limits = [int(m.group(1)), int(m.group(2))]
							if ctrl_limits[0] == 0 and ctrl_limits[1] == 1:
								ctrl_type = "VToggle"
								ctrl_items = ["off", "on"]
								ctrl_ticks = [0, 100]

					elif key == 'Items':
						ctrl_items = value[1:-1].split("' '")
						ctrl_ticks = list(range(len(ctrl_items)))

					elif key == 'Item0':
						ctrl_item0 = value[1:-1]

					elif key in ctrl_chans:
						if ctrl_type == "Toggle":
							m = re.match(".*\[(off|on)\].*", value, re.M | re.I)
							if m:
								ctrl_item0 = m.group(1)
							else:
								ctrl_item0 = "off"
						else:
							m = re.match(".*\[(\d*)%\].*", value, re.M | re.I)
							if m:
								ctrl_value = int(m.group(1))
								ctrl_values.append(ctrl_value)
								if ctrl_type == "VToggle":
									ctrl_item0 = 'on' if (ctrl_value>0) else 'off'

				if ctrl_symbol and ctrl_type:
					if ctrl_type in ("Selector", "Toggle", "VToggle") and len(ctrl_items) > 1 and (not ctrl_list or ctrl_name in ctrl_list):
						# Translate control name & labels
						ctrl_name_trans = self.translate(ctrl_name)
						ctrl_labels = [self.translate(item) for item in ctrl_items]
						#ctrl_labels = ctrl_items
						ctrl_value = self.translate(ctrl_item0)
						logging.debug("ADDING ZCTRL SELECTOR: {} ({}) => {}".format(ctrl_name_trans, ctrl_symbol, ctrl_item0))
						zctrl = zynthian_controller(self, ctrl_symbol, ctrl_name_trans, {
							'graph_path': [ctrl_name, ctrl_type, ctrl_items],
							'labels': ctrl_labels,
							'ticks': ctrl_ticks,
							'value': ctrl_value,
							'value_min': ctrl_ticks[0],
							'value_max': ctrl_ticks[-1],
							'is_toggle': (ctrl_type == 'Toggle'),
							'is_integer': True
						})
						zctrl.last_value_sent = None
						zctrls[ctrl_symbol] = zctrl

					elif ctrl_type in ("Playback", "Capture"):
						for i, chan in enumerate(ctrl_chans):
							if len(ctrl_chans) > 2:
								graph_path = [ctrl_name, ctrl_type, i, len(ctrl_chans)]
								zctrl_symbol = ctrl_symbol + "_" + str(i)
								zctrl_name = ctrl_name + " " + str(i+1)
							elif len(ctrl_chans) == 2:
								graph_path = [ctrl_name, ctrl_type, i, 2]
								zctrl_symbol = ctrl_symbol + "_" + str(i)
								zctrl_name = ctrl_name + " " + self.chan_names[i]
							else:
								graph_path = [ctrl_name, ctrl_type]
								zctrl_symbol = ctrl_symbol
								zctrl_name = ctrl_name
							if not ctrl_list or zctrl_name in ctrl_list:
								zctrl_name_trans = self.translate(zctrl_name)
								logging.debug("ADDING ZCTRL LEVEL: {} ({}) => {}".format(zctrl_name_trans, zctrl_symbol, ctrl_values[i]))
								zctrl = zynthian_controller(self, zctrl_symbol, zctrl_name_trans, {
									'graph_path': graph_path,
									'value': ctrl_values[i],
									'value_min': ctrl_minval,
									'value_max': ctrl_maxval,
									'is_toggle': False,
									'is_integer': True
								})
								zctrl.last_value_sent = None
								zctrls[zctrl_symbol] = zctrl

		except Exception as err:
			logging.error(err)

		return zctrls


	def translate(self, text):
		try:
			return self.translations[text]
			#return text
		except:
			return text


	def send_controller_value(self, zctrl):
		pass


	def _send_controller_value(self, zctrl):
		try:
			if callable(zctrl.graph_path):
				zctrl.graph_path(zctrl.value)
			else:
				if zctrl.labels:
					if zctrl.graph_path[1] == "VToggle":
						amixer_command = "set '{}' '{}%'".format(zctrl.graph_path[0], zctrl.value)
					else:
						i = zctrl.get_value2index()
						try:
							itemval = zctrl.graph_path[2][i]
						except:
							itemval = zctrl.get_value()
						amixer_command = "set '{}' '{}'".format(zctrl.graph_path[0], itemval)
					logging.debug(amixer_command)
					print(amixer_command, file=self.amixer_sender_proc.stdin, flush=True)
				else:
					if zctrl.symbol == "Headphone" and self.allow_rbpi_headphones() and self.zyngui and self.zyngui.get_zynthian_config("rbpi_headphones"):
						amixer_command = "amixer -M -c {} set '{}' '{}' {}% unmute".format(self.rbpi_device_name, zctrl.graph_path[0], zctrl.graph_path[1], zctrl.value)
						logging.debug(amixer_command)
						check_output(shlex.split(amixer_command))
					else:
						values = []
						if len(zctrl.graph_path) > 2:
							nchans = zctrl.graph_path[3]
							symbol_prefix = zctrl.symbol[:-1]
							for i in range(0, nchans):
								symbol_i = symbol_prefix + str(i)
								if symbol_i in self.zctrls:
									values.append("{}%".format(self.zctrls[symbol_i].value))
								else:
									values.append("0%")
						else:
							values.append("{}%".format(zctrl.value))

						amixer_command = "set '{}' '{}' {} unmute".format(zctrl.graph_path[0], zctrl.graph_path[1], ','.join(values))
						logging.debug(amixer_command)
						print(amixer_command, file=self.amixer_sender_proc.stdin, flush=True)
			sleep(0.05)

		except Exception as err:
			logging.error(err)


	def start_sender_poll(self):

		def runInThread():
			sleep(0.1)
			self.amixer_sender_proc = Popen(["amixer", "-s", "-M", "-c", self.device_name], stdin=PIPE, stdout=DEVNULL, stderr=STDOUT, bufsize=1, universal_newlines=True)
			while self.sender_poll_state == 1:
				counter = 0
				if self.zctrls:
					for sym, zctrl in self.zctrls.items():
						if zctrl.last_value_sent != zctrl.value:
							zctrl.last_value_sent = zctrl.value
							self._send_controller_value(zctrl)
							counter += 1

				if counter == 0:
					sleep(0.05)
			self.amixer_sender_proc.terminate()
			self.amixer_sender_proc = None
			self.sender_poll_state = 0

		self.sender_poll_state = 1
		thread = threading.Thread(target=runInThread, daemon=True)
		thread.name = "ALSA mixer engine"
		thread.start()


	def stop_sender_poll(self):
		if self.sender_poll_state == 1:
			self.sender_poll_state = 2
		while self.sender_poll_state:
			sleep(0.1)

	#----------------------------------------------------------------------------
	# MIDI CC processing
	#----------------------------------------------------------------------------

	def midi_control_change(self, chan, ccnum, val):
		for ch in range(0, 16):
			try:
				self.learned_cc[ch][ccnum].midi_control_change(val)
			except:
				pass

	#--------------------------------------------------------------------------
	# Special
	#--------------------------------------------------------------------------

	def get_soundcard_config(self):
		try:
			jack_opts = os.environ.get('JACKD_OPTIONS')
			res = re.compile(r" hw:([^\s]+) ").search(jack_opts)
			self.device_name = res.group(1)
		except:
			self.device_name = "0"

		try:
			self.translations = self.translations_by_device[self.device_name]
		except:
			self.translations = {}

		try:
			cmd = self.sys_dir + "/sbin/get_rbpi_audio_device.sh"
			self.rbpi_device_name = check_output(cmd, shell=True).decode("utf-8")
		except:
			self.rbpi_device_name = None

		try:
			scmix = os.environ.get('SOUNDCARD_MIXER', "").replace("\\n","")
			self.ctrl_list = [item.strip() for item in scmix.split(',')]

		except:
			self.ctrl_list = None


	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

	@classmethod
	def init_zynapi_instance(cls):
		if not cls.zynapi_instance:
			cls.zynapi_instance = cls(None)
		else:
			logging.debug("\n\n********** REUSING INSTANCE ***********")


	@classmethod
	def refresh_zynapi_instance(cls):
		if cls.zynapi_instance:
			cls.zynapi_instance.stop()
			cls.zynapi_instance = cls(None)


	@classmethod
	def zynapi_get_controllers(cls, ctrl_list="*"):
		return cls.zynapi_instance.get_controllers_dict(None, ctrl_list)


	@classmethod
	def zynapi_get_device_name(cls):
		return cls.zynapi_instance.device_name


	@classmethod
	def zynapi_get_rbpi_device_name(cls):
		return cls.zynapi_instance.rbpi_device_name


#******************************************************************************
