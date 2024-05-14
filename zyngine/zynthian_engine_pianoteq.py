# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_pianoteq)
#
# zynthian_engine implementation for Pianoteq (>=v7.5)
#
# Copyright (C) 2023-2024 Fernando Moyano <jofemodo@zynthian.org>
# 			  Holger Wirtz <holger@zynthian.org>
#             Brian Walton <riban@zynthian.org>
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
import shutil
import struct
import logging
import requests
from time import sleep
from xml.etree import ElementTree
from collections import OrderedDict
from subprocess import Popen, DEVNULL, PIPE, check_output, run

from . import zynthian_engine
from . import zynthian_controller
from zynconf import ServerPort

pt_ctrl_map = OrderedDict((
	("Condition", "Cond"),
	("Dynamics", "Dyn"),
	("Volume", "Volum"),
	("Post Effect Gain", "EffGain"),
	("Equalizer Switch", "EquOn"),
	("Aftertouch", "AfTouch"),
	("Diapason", "Diap"),
	("Sustain Pedal", "SustP"),
	("Soft Pedal", "SoftP"),
	("Sostenuto Pedal", "SostP"),
	("Harmonic Pedal", "HarmP"),
	("Rattle Pedal", "Rattle"),
	("Lute Stop Pedal", "LutStp"),
	("Celeste Pedal", "Celes"),
	("Mozart Rail", "Mozart"),
	("Super Sostenuto", "SSosP"),
	("Pinch Harmonic Pedal", "PinchH"),
	("Glissando Pedal", "Gliss"),
	("Harpsichord Register[1]", "Regis[1]"),
	("Harpsichord Register[2]", "Regis[2]"),
	("Harpsichord Register[3]", "Regis[3]"),
	("Reversed Sustain", "RevSus"),
	("Pitch Bend", "PBend"),
	("Clavinet Low Mic", "ClvMicL"),
	("Clavinet High Mic", "ClvMicH"),
	("Output Mode", "Output"),
	("Mute", "Mute"),
	("Damper Noise", "DampNois"),
	("Pedal Noise", "PSnd"),
	("Key Release Noise", "KSnd"),
	("Keyboard Range Switch", "KbRng"),
	("Bounce Switch", "MBOn"),
	("Bounce Delay", "MBDel"),
	("Bounce Sync", "MBSync"),
	("Bounce Sync Speed", "MBSyncS"),
	("Bounce Velocity Sensitivity", "MBVelS"),
	("Bounce Delay Loss", "MBAccel"),
	("Bounce Velocity Loss", "MBVelL"),
	("Bounce Humanization", "MBHuma"),
	("NFX Lfo Shape", "nfxLfoSh"),
	("NFX Lfo Skew", "nfxLfoSk"),
	("NFX Lfo Rate", "nfxLfoRt"),
	("NFX Lfo Phase", "nfxLfoP"),
	("NFX Lfo Phase Locked", "nfxLfoPL"),
	("NFX Onset Duration", "nfxOnset"),
	("NFX Vibrato", "nfxVibC"),
	("NFX Vibrato Offset", "nfxVibB"),
	("NFX Tremolo Depth", "nfxTrmD"),
	("NFX Tremolo Phase", "nfxTrmP"),
	("Attack Envelope", "AttkE"),
	("Virtuosity", "Virt"),
	("Fret", "Fret"),
	("Guitar Legato", "Legato"),
	("Guitar easy fingering", "GFing"),
	("Guitar Body", "GBody"),
	("Effect[1].Switch", "Eff[1].Switch"),
	("Effect[1].Param[1]", "Eff[1].Param[1]"),
	("Effect[1].Param[2]", "Eff[1].Param[2]"),
	("Effect[1].Param[3]", "Eff[1].Param[3]"),
	("Effect[1].Param[4]", "Eff[1].Param[4]"),
	("Effect[1].Param[5]", "Eff[1].Param[5]"),
	("Effect[1].Param[6]", "Eff[1].Param[6]"),
	("Effect[1].Param[7]", "Eff[1].Param[7]"),
	("Effect[1].Param[8]", "Eff[1].Param[8]"),
	("Effect[2].Switch", "Eff[2].Switch"),
	("Effect[2].Param[1]", "Eff[2].Param[1]"),
	("Effect[2].Param[2]", "Eff[2].Param[2]"),
	("Effect[2].Param[3]", "Eff[2].Param[3]"),
	("Effect[2].Param[4]", "Eff[2].Param[4]"),
	("Effect[2].Param[5]", "Eff[2].Param[5]"),
	("Effect[2].Param[6]", "Eff[2].Param[6]"),
	("Effect[2].Param[7]", "Eff[2].Param[7]"),
	("Effect[2].Param[8]", "Eff[2].Param[8]"),
	("Effect[3].Switch", "Eff[3].Switch"),
	("Effect[3].Param[1]", "Eff[3].Param[1]"),
	("Effect[3].Param[2]", "Eff[3].Param[2]"),
	("Effect[3].Param[3]", "Eff[3].Param[3]"),
	("Effect[3].Param[4]", "Eff[3].Param[4]"),
	("Effect[3].Param[5]", "Eff[3].Param[5]"),
	("Effect[3].Param[6]", "Eff[3].Param[6]"),
	("Effect[3].Param[7]", "Eff[3].Param[7]"),
	("Effect[3].Param[8]", "Eff[3].Param[8]"),
	("Reverb Switch", "RevrbOn"),
	("Reverb Duration", "RevDur"),
	("Reverb Mix", "RevM"),
	("Room Dimensions", "RevDim"),
	("Reverb Pre-delay", "RevDel"),
	("Reverb Early Reflections", "RevEarl"),
	("Reverb Tone", "RevTon"),
	("Limiter Switch", "LimOn"),
	("Limiter Sharpness", "LimSharp"),
	("Limiter Threshold", "LimThr"),
	("Limiter Gain", "LimGain")
))

# ------------------------------------------------------------------------------
# Pianoteq module helper functions
# ------------------------------------------------------------------------------


# True if pianoteq binary is installed. Fixes symlink if broken
def check_pianoteq_binary():
	if os.path.islink(PIANOTEQ_BINARY) and not os.access(PIANOTEQ_BINARY, os.X_OK):
		os.remove(PIANOTEQ_BINARY)

	if not os.path.isfile(PIANOTEQ_BINARY):
		try:
			os.symlink(PIANOTEQ_SW_DIR + "/Pianoteq 6 STAGE", PIANOTEQ_BINARY)
		except:
			return False

	if os.path.isfile(PIANOTEQ_BINARY) and os.access(PIANOTEQ_BINARY, os.X_OK):
		return True
	else:
		return False


# Get {'version_str', 'version', 'api', 'multicore', 'trial', 'product', 'name', 'jackname'} from pianoteq binary
def get_pianoteq_binary_info():
	info = {
		'version_str': '',
		'version': [0,0,0],
		'api': False,
		'multicore': '1',
		'trial': True,
		'product': '',
		'name': 'Pianoteq',
		'jackname': 'Pianoteq'
	}
	if check_pianoteq_binary():
		version_pattern = re.compile(" version ([0-9]+\.[0-9]+\.[0-9]+)", re.IGNORECASE)
		stage_pattern = re.compile(" stage ", re.IGNORECASE)
		pro_pattern = re.compile(" pro ", re.IGNORECASE)
		trial_pattern = re.compile(" trial ", re.IGNORECASE)
		proc = Popen([PIANOTEQ_BINARY, "--version"], stdout=PIPE)
		for line in proc.stdout:
			l = line.rstrip().decode("utf-8")
			m = version_pattern.search(l)
			if m:
				# Get version info
				info['version_str'] = m.group(1)
				info['version'] = list(map(int, str(info['version_str']).split(".")))
				if info['version'][0] > 7 or info['version'][0] == 7 and info['version'][1] >= 5:
					info['api'] = True
				else:
					info['api'] = False
				if info['version'][0] == 6 and info['version'][1] == 0:
					# Pianoteq 6.0 only offers multicore rendering on/off
					info['multicore'] = '1'
				else:
					info['multicore'] = '2'
				if  info['version'][0] == 6 and info['version'][1] < 5:
					info['jackname'] = "Pianoteq{}{}".format(info['version'][0], info['version'][1])
				# Get trial info
				m = trial_pattern.search(l)
				if m:
					info['trial'] = True
				else:
					info['trial'] = False
				# Get product info
				m = stage_pattern.search(l)
				if m:
					info['product'] = "STAGE"
				else:
					m = pro_pattern.search(l)
					if m:
						info['product'] = "PRO"
					else:
						info['product'] = "STANDARD"
		if info['product']:
			info['name'] += ' {}'.format(info['product'])
		if info['trial']:
			info['name'] += " (Demo)"
		if info['version_str']:
			info['name'] += " {}".format(info['version_str'])
		if info['product'] == "STANDARD":
			lkey = get_pianoteq_config_value('LKey')
			if len(lkey) > 0:
				lkey_product_pattern = re.compile(" Pianoteq \d* (\w*)")
				m = lkey_product_pattern.search(lkey[0])
				if m:
					info['product'] = m.group(1).upper()
	return info


def get_pianoteq_config_value(key):
	values = []
	if os.path.isfile(PIANOTEQ_CONFIG_FILE):
		root = ElementTree.parse(PIANOTEQ_CONFIG_FILE)
		for xml_value in root.iter("VALUE"):
			if xml_value.attrib['name'] == key:
				values = xml_value.attrib['val'].split(';')
	return values


def create_pianoteq_config():
	if not os.path.isfile(PIANOTEQ_CONFIG_FILE) or not os.stat(PIANOTEQ_CONFIG_FILE).st_size:
		logging.debug("Pianoteq configuration does not exist. Creating one...")
		if not os.path.exists(PIANOTEQ_CONFIG_DIR):
			os.makedirs(PIANOTEQ_CONFIG_DIR)
		info = get_pianoteq_binary_info()
		try:
			shutil.copy("{}/Pianoteq{}{} {}.prefs".format(PIANOTEQ_CONFIG_DIR, info['version'][0], info['version'][1], info['product']), PIANOTEQ_CONFIG_FILE)
		except:
			try:
				shutil.copy("{}/Pianoteq{}{}.prefs".format(PIANOTEQ_CONFIG_DIR, info['version'][0], info['version'][1]), PIANOTEQ_CONFIG_FILE)
			except:
				shutil.copy(os.environ.get('ZYNTHIAN_DATA_DIR', "/zynthian/zynthian-data") + "/pianoteq6/Pianoteq6.prefs", PIANOTEQ_CONFIG_FILE)


def fix_pianoteq_config(samplerate):
	if os.path.isfile(PIANOTEQ_CONFIG_FILE):
		info = get_pianoteq_binary_info()

		try:
			rate_limit_flag = int(os.environ.get('ZYNTHIAN_PIANOTEQ_LIMIT_RATE', "1"))
		except:
			logging.error("Bad config value for sample rate limit flag")
			rate_limit_flag = 1

		internal_sr = samplerate
		if rate_limit_flag:
			while internal_sr > 24000:
				internal_sr = internal_sr / 2

		try:
			voice_limit = int(os.environ.get('ZYNTHIAN_PIANOTEQ_VOICE_LIMIT', "32"))
		except:
			logging.error("Bad config value for voice limit")
			voice_limit = 32

		try:
			cpu_overload_detection = int(os.environ.get('ZYNTHIAN_PIANOTEQ_CPU_OVERLOAD_DETECTION', "1"))
		except:
			logging.error("Bad config value for CPU overload detection flag")
			cpu_overload_detection = 1

		try:
			tree = ElementTree.parse(PIANOTEQ_CONFIG_FILE)
			root = tree.getroot()
			filter_nodes = []
			audio_setup_node = None
			midi_setup_node = None
			crash_node = None
			for xml_value in root.iter("VALUE"):
				if xml_value.attrib['name'] == 'engine_rate':
					xml_value.set('val', str(internal_sr))
				elif xml_value.attrib['name'] == 'voices':
					xml_value.set('val', str(voice_limit))
				elif xml_value.attrib['name'] == 'multicore':
					xml_value.set('val', info['multicore'])
				elif xml_value.attrib['name'] == 'cpu_overload_detection':
					xml_value.set('val', str(cpu_overload_detection))
				elif xml_value.attrib['name'] == 'midiArchiveEnabled':
					xml_value.set('val', '0')
				elif xml_value.attrib['name'] == 'audio-setup':
					audio_setup_node = xml_value
				elif xml_value.attrib['name'] == 'midi-setup':
					midi_setup_node = xml_value
				elif xml_value.attrib['name'] == 'crash_detect':
					crash_node = xml_value
				elif xml_value.attrib['name'].startswith('filter-state-'):
					filter_nodes.append(xml_value)

			for node in filter_nodes:
				root.remove(node) # Remove last state to avoid crash at startup

			if audio_setup_node:
				logging.debug("Fixing Audio Setup")
				for devicesetup in audio_setup_node.iter('DEVICESETUP'):
					devicesetup.set('deviceType', 'JACK')
					devicesetup.set('audioOutputDeviceName', 'Auto-connect OFF')
					devicesetup.set('audioInputDeviceName', 'Auto-connect OFF')
					devicesetup.set('audioDeviceRate', str(samplerate))
					devicesetup.set('forceStereo', '0')
			else:
				logging.debug("Creating new Audio Setup")
				value = ElementTree.Element('VALUE')
				value.set('name', 'audio-setup')
				devicesetup = ElementTree.SubElement(value, 'DEVICESETUP')
				devicesetup.set('deviceType', 'JACK')
				devicesetup.set('audioOutputDeviceName', 'Auto-connect OFF')
				devicesetup.set('audioInputDeviceName', 'Auto-connect OFF')
				devicesetup.set('audioDeviceRate', str(samplerate))
				devicesetup.set('forceStereo', '0')
				root.append(value)

			if midi_setup_node:
				logging.debug("Fixing MIDI Setup ")
				for midisetup in midi_setup_node.iter('midi-setup'):
					midisetup.set('listen-all', '0')
			else:
				logging.debug("Creating new MIDI Setup")
				value = ElementTree.Element('VALUE')
				value.set('name', 'midi-setup')
				midisetup = ElementTree.SubElement(value, 'midi-setup')
				midisetup.set('listen-all', '0')
				root.append(value)

			if crash_node is not None:
				if crash_node.attrib['val']:
					logging.warning("Pianoteq detected previous crash ({})".format(crash_node.attrib['val']))
					crash_node.attrib['val'] = ''

			tree.write(PIANOTEQ_CONFIG_FILE)

		except Exception as e:
			logging.error("Fixing Pianoteq config failed: {}".format(e))
			return format(e)


def read_pianoteq_midi_mapping(file):
	result = {}
	with open(file, "rb") as f:
		data = f.read()
	if len(data) < 40:
		print(f"Short read: {len(data)}")
		return result
	if struct.unpack("<I", data[0:4])[0] != 954245913:
		print(f"Wrong magic header number: {struct.unpack('<I', data[0:4])[0]}")
		return result
	payload_len = struct.unpack("<i", data[4:8])[0]
	if payload_len + 8 != len(data):
		print("Error: Wrong length")
	pos = 8

	if get_pianoteq_binary_info()["version"][0] < 8:
		header = ["Flag 1", "Notes Channel", "Notes Transposition", "Dialect","MIDI Tuning", "Map length"]
	else:
		header = ["Flag 1", "Notes Channel", "Notes Transposition", "Flag 2", "Flag 3", "Dialect", "MIDI Tuning", "Map length"]

	for key in header:
		result[key] = struct.unpack("<i", data[pos:pos+4])[0]
		pos += 4
	result["map"] = {}
	while pos < len(data):
		print(f"Get data at {pos}")
		flag = struct.unpack("<i", data[pos:pos+4])[0]
		pos += 4 # What is this extra flag?
		trigger_len = struct.unpack("<i", data[pos:pos+4])[0]
		pos += 4
		trigger_str = data[pos:pos+trigger_len].decode()
		pos += trigger_len
		action_len = struct.unpack("<i", data[pos:pos+4])[0]
		pos += 4
		action_str = data[pos:pos+action_len].decode()
		pos += action_len
		result["map"][trigger_str] = [action_str, flag]
	return result


def write_pianoteq_midi_mapping(config, file):
	data = bytes([25, 163, 224, 56, 0, 0, 0, 0])

	if get_pianoteq_binary_info()["version"][0] < 8:
		header = {"Flag 1": 4, "Notes Channel": -1, "Notes Transposition": 0, "Dialect": 0, "MIDI Tuning": 0}
	else:
		header = {"Flag 1": 6, "Notes Channel": -1, "Notes Transposition": 0, "Flag 2": -1, "Flag 3": -1, "Dialect": 0, "MIDI Tuning": 0}

	for key, val in header.items():
		if key in config:
			data += struct.pack("<i", config[key])
		else:
			data += struct.pack("<i", val)
	data += struct.pack("i", len(config["map"]))
	for key, val in config["map"].items():
		data += struct.pack("<i", val[1])
		data += struct.pack("<i", len(key))
		data += key.encode()
		data += struct.pack("<i", len(val[0]))
		data += val[0].encode()
	# Don't write the same data to disk
	try:
		with open(file, "rb") as f:
			current_data = f.read()
		if current_data[8:] == data[8:]:
			return
	except:
		pass
	with open(file, "wb") as f:
		l = f.write(data)
		f.seek(4)
		f.write(struct.pack("i", l - 8))


def save_midi_mapping(file):
	data = {"map":{}}
	for i, param in enumerate(pt_ctrl_map.values()):
		cc = i + 1
		data["map"][f"Controller {cc}"] = [f"{{SetParameter|3|{param}|0:1}}", 1]
	data["map"]["Pitch Bend"] = ["{SetParameter|3|PBend|0.458333:0.541667}", 1]
	write_pianoteq_midi_mapping(data, file)


# ------------------------------------------------------------------------------
# Pianoteq module constants & parameter configuration/initialization
# ------------------------------------------------------------------------------

PIANOTEQ_SW_DIR = os.environ.get('ZYNTHIAN_SW_DIR', '/zynthian/zynthian-sw') + '/pianoteq6'
PIANOTEQ_BINARY = PIANOTEQ_SW_DIR + '/pianoteq'
PIANOTEQ_CONFIG_DIR = os.path.expanduser('~') + '/.config/Modartt'
PIANOTEQ_DATA_DIR = os.path.expanduser('~') + '/.local/share/Modartt/Pianoteq'
PIANOTEQ_ADDON_DIR = PIANOTEQ_DATA_DIR + '/Addons'
PIANOTEQ_MY_PRESETS_DIR = PIANOTEQ_DATA_DIR + '/Presets'
PIANOTEQ_CONFIG_FILE = PIANOTEQ_CONFIG_DIR + '/Pianoteq.prefs'
PIANOTEQ_MIDIMAPPINGS_DIR = PIANOTEQ_DATA_DIR + '/MidiMappings'

# ------------------------------------------------------------------------------
# Pianoteq Engine Class
# ------------------------------------------------------------------------------


class zynthian_engine_pianoteq(zynthian_engine):


	# ---------------------------------------------------------------------------
	# Config variables
	# ---------------------------------------------------------------------------

	# Must assign here to avoid common (zynthian_engine class) instances being used
	# Standard MIDI Controllers
	_ctrls = []

	# Controller Screens
	_ctrl_screens = []

	# ----------------------------------------------------------------------------
	# Initialization
	# ----------------------------------------------------------------------------

	def __init__(self, zyngui=None, update_presets_cache=False):
		super().__init__(zyngui)
		self.info = get_pianoteq_binary_info()
		self.name = 'Pianoteq'
		self.nickname = "PT"
		self.jackname = self.info['jackname']

		self.show_demo = True
		self.command_prompt = None
		self.preset = ['', '', '', '']
		self.params = {}
		self.overfreq = 1800000

		create_pianoteq_config()
		save_midi_mapping(f"{PIANOTEQ_MIDIMAPPINGS_DIR}/zynthian.ptm")

		self.command = f"{PIANOTEQ_BINARY} --prefs {PIANOTEQ_CONFIG_FILE} --midimapping zynthian"
		if self.info['api']:
			self.command += f" --serve {ServerPort['pianoteq_rpc']}"
		if not self.config_remote_display():
			self.command += " --headless"

		self.start()

	def start(self):
		if self.proc:
			return
		logging.info("Starting Engine {}".format(self.name))
		try:
			sr = self.state_manager.get_jackd_samplerate()
		except:
			sr = 44100
		fix_pianoteq_config(sr)
		super().start() #TODO: Use lightweight Popen - last attempt stopped RPC working
		# Wait for RPC interface to be available or 10s for <7.5 with GUI
		for i in range(10):
			info = self.get_info()
			if info:
				return
			sleep(1)
		self.stop()
		raise Exception("No response from Pianoteq RPC server")

	def stop(self):
		if not self.proc:
			return
		self.rpc('quit')
		if self.proc.isalive():
			self.proc.close(True)
		self.proc = None

	# ---------------------------------------------------------------------------
	# RPC-JSON API
	# ---------------------------------------------------------------------------

	#   Send a RPC request and return the result
	#   method: API method call
	#   params: List of parameters required by API method
	def rpc(self, method, params=None, id=0):
		url = f"http://127.0.0.1:{ServerPort['pianoteq_rpc']}/jsonrpc"
		if params is None:
			params = []
		payload = {
			"method": method,
			"params": params,
			"jsonrpc": "2.0",
			"id": id}
		try:
			result=requests.post(url, json=payload).json()
		except:
			return None
		return result

	#	Get info
	def get_info(self):
		try:
			return self.rpc('getInfo')['result'][0]
		except:
			return None

	#   Load a preset by name
	#   preset_name: Name of preset to load
	#   bank: Name of bank preset resides (builtin presets have no bank)
	#   returns: True on success
	def load_preset(self, preset_name, bank):
		result = self.rpc('loadPreset', {'name':preset_name, 'bank':bank})
		return result and 'error' not in result

	#   Save a preset by name to "zynthian" bank
	#   preset_name: Name of preset to save
	#   Note: Overwrites existing preset if exists
	#   returns: True on success
	def save_preset(self, bank_info, preset_name):
		result = self.rpc('savePreset', {'name':preset_name, 'bank':'My Presets'})
		return result and 'error' not in result

	#   Get a list of preset names for an instrument
	#   instrument: Name of instrument for which to load presets (default: all instruments)
	#   returns: list of [preset names, pt bank] or None on failure
	def get_presets(self, instrument=None):
		presets = []
		result = self.rpc('getListOfPresets')
		if result is None or 'result' not in result:
			return None
		for preset in result['result']:
			if (instrument is None or preset['instr'] == instrument):
				presets.append([preset['name'], preset['bank']])
		return presets

	#   Get a list of groups (classes of instrument)
	#   returns: List of group names or None on failure
	def get_groups(self):
		groups = []
		result = self.rpc('getListOfPresets')
		if result is None or 'result' not in result:
			return None
		for preset in result['result']:
			if preset['class'] not in groups:
				groups.append(preset['class'])
		return groups

	#   Get a list of instruments
	#   group: Name of group to filter instruments (default: all groups)
	#   returns: List of lists [instrument name, licenced (bool)] or None on failure
	def get_instruments(self, group=None):
		instruments = []
		overclock = int(run(["cat", "/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"], capture_output=True).stdout.decode()[:-1]) > self.overfreq
		result = self.rpc('getListOfPresets')
		if result and 'result' in result:
			for preset in result['result']:
				if (group is None or preset['class'] == group) and [preset['instr'], preset['license_status']=='ok'] not in instruments:
					if overclock and preset['instr'] == "Classical Guitar":
						continue
					instruments.append([preset['instr'], preset['license_status']=='ok'])
		return instruments

	#   Get a list of parameters for the loaded preset
	#   returns: dictionary of all parameters indexed by parameter id: {name, value}
	def get_params(self):
		params = {}
		result = self.rpc('getParameters')
		if result is None or 'result' not in result:
			return {}
		param_list = list(pt_ctrl_map.keys())
		for param in result['result']:
			if param['id'] in param_list:
				params[param['id']] = {'name': param['name'], 'value': param['normalized_value'], 'cc': param_list.index(param['id']) + 1}
			else:
				logging.warning(f"Unknown parameter {param['id']}")
		return params

	#   Get a value of a parameter for the loaded preset
	#   param: Parameter id
	#   returns: Normalized value (0.0..1.0)
	def get_param(self, param):
		params = self.get_params()
		if params and param in params:
			return params[param]['value']
		return 0

	#   Set a value of a parameter for the loaded preset
	#   param: Parameter id
	#   value: Normalized value (0.0..1.0)
	#   returns: True on success
	def set_param(self, param, value):
		result = self.rpc('setParameters', {'list': [{'id': param, 'normalized_value': value}]})
		return result and 'error' not in result

	# ---------------------------------------------------------------------------
	# Processor Management
	# ---------------------------------------------------------------------------

	def add_processor(self, processor):
		super().add_processor(processor)
		processor.auto_save_bank = True


	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	# ----------------------------------------------------------------------------
	# Bank Managament
	# ----------------------------------------------------------------------------

	def get_bank_list(self, processor=None):
		banks = [] # List of bank info: [uri/uid,?,name,?]
		instruments = self.get_instruments()
		for instrument in instruments:
			if instrument[1]:
				banks.append([instrument[0], None, instrument[0], instrument[1]])
		if self.show_demo:
			banks.append([None, 0, '---- DEMO Instruments ----', None])
			for instrument in instruments:
				if not instrument[1]:
					banks.append([instrument[0], None, instrument[0], instrument[1]])
		return banks

	def set_bank(self, processor, bank):
		self.name = (f"Pianoteq {bank[0]}")
		return True

	# ----------------------------------------------------------------------------
	# Preset Managament
	# ----------------------------------------------------------------------------

	def get_display_name(self, preset_name, bank_name):
		"""Remove bank name from front of preset display name

		Attributes
		----------
		preset_name : str
			Name of preset
		bank_name : str
			String to remove from front of display name
		"""

		if preset_name.startswith(bank_name):
			display_name = preset_name[len(bank_name):]
		elif preset_name.startswith("NY Steinway D ") or preset_name.startswith("HB Steinway D "):
			display_name = preset_name[14:]
		elif preset_name.startswith("D. Schoffstoss "):
			display_name = preset_name[15:]
		elif preset_name.startswith("Electra "):
			display_name = preset_name[7:]
		else:
			display_name = preset_name
		if display_name.startswith(" - "):
			display_name = display_name[3:]
		if display_name:
			return display_name.strip()
		else:
			return preset_name

	def get_preset_list(self, bank):
		# [uri/uid, pt bank, display name,zyn bank (pt instr)]
		presets = []
		result = self.get_presets(bank[2])
		user_presets = False
		stub = bank[0].split(" (")[0]
		if stub.startswith("Grand "):
			stub = stub[6:]
		for preset in result:
			if preset[1]:
				presets.append([preset[0], preset[1], self.get_display_name(preset[0], stub), bank[0]])
				user_presets = True
		if user_presets:
			presets.insert(0, [None, None, 'User Presets', ''])
			presets.append([None, None, 'Factory Presets', ''])
		for preset in result:
			if not preset[1]:
				presets.append([preset[0], preset[1] , self.get_display_name(preset[0], stub), bank[0]])
		return presets

	def set_preset(self, processor, preset, preload=False):
		if preset[3] == "Classical Guitar" and int(run(["cat", "/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"], capture_output=True).stdout.decode()[:-1]) > self.overfreq:
			return False
		if self.load_preset(preset[0], preset[1]):
			self.preset = preset
			# Rebuild controls because each preset may use different controls
			self.generate_ctrl_screens(self.get_controllers_dict(processor))
			processor.init_ctrl_screens()
			if preset[3] in ['CP-80', 'Vintage Tines MKI', 'Vintage Tines MKII', 'Vintage Reeds W1', 'Clavinet D6', 'Pianet N', 'Pianet T', 'Electra-Piano']:
				processor.controllers_dict['Output Mode'].set_options({'labels': ['Line out (stereo)',  'Line out (mono)', 'Room mic', 'Binaural']})
			else:
				processor.controllers_dict['Output Mode'].set_options({'labels': ['Stereophonic',  'Monophonic', 'Sound Recording', 'Binaural']})
			self.params = self.get_params()
			for param in self.params:
				processor.controllers_dict[param].set_value(self.params[param]['value'], False)
			# Update control labels
			for effect in range(1, 4):
				for effect_param in range(1, 9):
					symbol = f'Effect[{effect}].Param[{effect_param}]'
					try:
						processor.controllers_dict[symbol].name = self.params[symbol]['name']
						processor.controllers_dict[symbol].short_name = self.params[symbol]['name']
					except:
						pass
			return True
		return False

	def is_preset_user(self, preset):
		return preset[1] != ''

	def preset_exists(self, bank_info, preset_name):
		# Instruments are presented as banks in Zynthian UI but user presets are saved in pianoteq banks 
		presets = self.zynapi_get_presets({'name': 'My Presets', 'fullpath': f'{PIANOTEQ_MY_PRESETS_DIR}/My Presets'})
		for preset in presets:
			if preset['name'] == preset_name:
				return True
		return False

	def cmp_presets(self, preset1, preset2):
		try:
			if preset1[0] == preset2[0] and preset1[3] == preset2[3]:
				return True
			else:
				return False
		except:
			return False

	def is_modified(self):
		params = self.get_params()
		for param in params:
			try:
				if self.params[param]['value'] != params[param]['value']:
					return True
			except:
				return True
		return False

	def delete_preset(self, bank_info, preset):
		return self.zynapi_remove_preset(f'{PIANOTEQ_MY_PRESETS_DIR}/{preset[1]}/{preset[0]}.fxp')

	def rename_preset(self, bank_info, preset, new_name):
		return self.zynapi_rename_preset(f'{PIANOTEQ_MY_PRESETS_DIR}/{preset[1]}/{preset[0]}.fxp', new_name)

	# ---------------------------------------------------------------------------
	# Controller management
	# ---------------------------------------------------------------------------

	# Get zynthian controllers dictionary:
	def get_controllers_dict(self, processor):
		if processor.controllers_dict is None:
			processor.controllers_dict = {}

		params = self.get_params()
		default_cc = {'Sustain Pedal': 64, 'Sostenuto Pedal': 66, 'Soft Pedal': 67, 'Harmonic Pedal': 69}
		for param in params:
			options = {
				'processor': processor,
				'value': 0,
				'value_min': 0.0,
				'value_max': 1.0,
				'is_integer': False,
				'not_on_gui': False,
				'midi_chan': processor.midi_chan,
				'midi_cc': params[param]["cc"]
			}
			# Discrete parameter values
			if param in ['Sustain Pedal', 'Soft Pedal', 'Sostenuto Pedal', 'Harmonic Pedal', 'Rattle Pedal', 'Lute Stop Pedal', 'Celeste Pedal', 'Mozart Rail', 'Super Sostenuto', 'Pitch Harmonic Pedal']:
				options['labels'] = ['Off', '1/4', '1/2', '3/4', 'On']
				options['group_symbol'] = 'Pedals'
			elif param in ['Equalizer Switch', 'Bounce Switch', 'Bounce Sync', 'Effect[1].Switch', 'Effect[2].Switch', 'Effect[3].Switch', 'Reverb Switch', 'Limiter Switch', 'Keyboard Range Switch']:
				options['labels'] = ['Off', 'On']
			elif param == 'Output Mode':
				options['labels'] = ['Stereophonic',  'Monophonic', 'Sound Recording', 'Binaural',]
			if param.startswith('Effect'):
				options['group_symbol'] = 'Effects'
			elif param.startswith('Reverb') or param == "Room Dimensions":
				options['group_symbol'] = 'Reverb'
			elif param.startswith('Limiter'):
				options['group_symbol'] = 'Limiter'
			#TODO Scale Diapason: 220..880Hz, Volume: 0..100 (maybe many parameters to be %)

			if param in processor.controllers_dict:
				processor.controllers_dict[param].set_options(options)
			else:
				zctrl = zynthian_controller(self, param, options)
				processor.controllers_dict[param] = zctrl
				# Default MIDI CC mapping
				if param in default_cc:
					self.state_manager.chain_manager.add_midi_learn(processor.midi_chan, default_cc[param], zctrl)

		return processor.controllers_dict

	#def send_controller_value(self, zctrl):
	#	self.set_param(zctrl.symbol, zctrl.value)

	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

	@classmethod
	def zynapi_get_banks(cls):
		banks = []
		for d in os.listdir(PIANOTEQ_MY_PRESETS_DIR):
			if os.listdir(f'{PIANOTEQ_MY_PRESETS_DIR}/{d}'):
				banks.append({
					'text': d,
					'name': d,
					'fullpath': f'{PIANOTEQ_MY_PRESETS_DIR}/{d}',
					'readonly': False
				})
		banks.append({
			'text': 'Factory Presets',
			'name': '',
			'fullpath': '',
			'readonly': True
		})
		return banks


	@classmethod
	def zynapi_get_presets(cls, bank):
		presets = []
		if bank['name'] == '':
			all_presets = check_output([PIANOTEQ_BINARY, '--list-presets']).decode('utf-8').split('\n')
			for preset in all_presets:
				if preset == '' or '/' in preset: continue
				presets.append({
					'text': preset,
					'name': preset,
					'fullpath': '',
					'readonly': True
				})
		else:
			for f in os.listdir(f"{bank['fullpath']}"):
				if f.endswith('.fxp'):
					presets.append({
						'text': f,
						'name': f[:-4],
						'fullpath': f"{bank['fullpath']}/{f}",
						'raw': f"{bank['fullpath']}/{f}",
						'readonly': False
					})
		return presets

	@classmethod
	def zynapi_download(cls, fullpath):
		return fullpath

	@classmethod
	def zynapi_get_formats(cls):
		return "fxp"

	@classmethod
	def zynapi_martifact_formats(cls):
		return "fxp"

	@classmethod
	def zynapi_install(cls, dpath, bank_path):
		fname, ext = os.path.splitext(dpath)
		if ext.lower() in ['.fxp']:
			shutil.move(dpath, bank_path)
		else:
			raise Exception("File doesn't look like a Pianoteq FXP preset")

	@classmethod
	def zynapi_rename_preset(cls, preset_path, new_preset_name):
		if preset_path[-4:].lower() != ".fxp":
			return False
		try:
			head, tail = os.path.split(preset_path)
			fname, ext = os.path.splitext(tail)
			new_preset_path = head + "/" + new_preset_name + ext
			os.rename(preset_path, new_preset_path)
			return True
		except:
			pass
		return False
		
	@classmethod
	def zynapi_remove_preset(cls, preset_path):
		if preset_path[-4:].lower() != ".fxp":
			return False
		os.system(f"rm '{preset_path}'")
		return True

# ******************************************************************************
