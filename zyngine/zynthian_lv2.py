#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian LV2-plugin management
# 
# zynthian LV2
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
import sys
import json
import lilv
import copy
import time
import string
import hashlib
import logging
import urllib.parse
from enum import Enum
from random import randrange

# ------------------------------------------------------------------------------
# Some variables & definitions
# ------------------------------------------------------------------------------


class EngineType(Enum):
	MIDI_SYNTH = "MIDI Synth"
	MIDI_TOOL = "MIDI Tool"
	AUDIO_EFFECT = "Audio Effect"
	AUDIO_GENERATOR = "Audio Generator"
	SPECIAL = "Special"
	#UNKNOWN = "Unknown"

engine_type_title = {
	"MIDI Synth": "MIDI Instrument",
	"Audio Effect": "Audio Effect",
	"MIDI Tool": "MIDI tool",
	"Audio Generator": "Audio Generator",
	"Special": "Special"
}

lv2_plugin_classes = {
	"MIDI_SYNTH": ("Instrument"),
	"AUDIO_EFFECT": ("Analyser", "Spectral", "Delay", "Compressor", "Distortion", "Filter", "Equaliser",
		"Modulator", "Expander", "Spatial", "Limiter", "Pitch Shifter", "Reverb", "Simulator", "Envelope",
		"Gate", "Amplifier", "Chorus", "Flanger", "Phaser", "Highpass", "Lowpass", "Dynamics"),
	"AUDIO_GENERATOR": ("Oscillator", "Generator"),
	"UNKNOWN": ("Utility", "Plugin")
}

engine_categories = {
	"MIDI Synth": (
		"Synth",
		"Sampler",
		"Piano",
		"Organ",
		"Acoustic",
		"Percussion",
		"Other"
	),
	"Audio Effect": (
		"Delay",
		"Distortion",
		"Dynamics",
		"Filter & EQ",
		"Modulation",
		"Panning & Spatial",
		"Pitch",
		"Reverb",
		"Amplifier",
		"Analyzer",
		"Other"
	),
	"MIDI Tool": (
		"Arpeggiator",
		"Automation",
		"Filter",
		"Mapper",
		"Sequencer",
		"Other"
	),
	"Audio Generator": (
		"Generator",
		"Oscillator",
		"Other"
	),
	"Special": (
		"Language",
		"Patchbay",
		"Sampler",
		"Other"
	)
}

lv2class2engcat = {
	"Analogue": "Synth",
	"Sampler & Wavetable": "Synth",
	"Hybrid": "Synth",
	"Emulator": "Synth",
	"Soundfont": "Sampler",
	"Instrument": "Synth",
	"Analyser": "Analyzer",
	"Spectral": "Filter",
	"Delay": "Delay",
	"Looper": "Delay",
	"Compressor": "Dynamics",
	"Distortion": "Distortion",
	"Filter": "Filter & EQ",
	"EQ": "Filter & EQ",
	"Equaliser": "Filter & EQ",
	"Modulator": "Modulation",
	"Expander": "Dynamics",
	"Spatial": "Panning & Spatial",
	"Panning": "Panning & Spatial",
	"Limiter": "Dynamics",
	"Pitch Shifter": "Pitch",
	"Reverb": "Reverb",
	"Simulator": "Amplifier",
	"Envelope": "Modulation",
	"Gate": "Dynamics",
	"Amplifier": "Amplifier",
	"Chorus": "Modulation",
	"Flanger": "Modulation",
	"Phaser": "Modulation",
	"Highpass": "Filter & EQ",
	"Lowpass": "Filter & EQ",
	"Dynamics": "Dynamics",
	"Oscillator": "Oscillator",
	"Generator": "Generator",
	"Utility": "Other",
	"Plugin": "Other"
}


standalone_engine_info = {
	"SL": ["SooperLooper", "SooperLooper", "Audio Effect", "Delay", True],
	"ZY": ["ZynAddSubFX", "ZynAddSubFX", "MIDI Synth", "Synth", True],
	"FS": ["FluidSynth", "FluidSynth: SF2, SF3", "MIDI Synth", "Sampler", True],
	"SF": ["Sfizz", "Sfizz: SFZ", "MIDI Synth", "Sampler", True],
	"LS": ["LinuxSampler", "LinuxSampler: SFZ, GIG", "MIDI Synth", "Sampler", True],
	"BF": ["setBfree", "setBfree - Hammond Emulator", "MIDI Synth", "Organ", True],
	"AE": ["Aeolus", "Aeolus - Pipe Organ Emulator", "MIDI Synth", "Organ", True],
	"PT": ['Pianoteq', "Pianoteq", "MIDI Synth", "Piano", True],
	"AP": ["ZynSampler", "ZynSampler", "MIDI Synth", "Sampler", True],
	'PD': ["PureData", "PureData - Visual Programming", "Special", "Language", True],
	'MD': ["MOD-UI", "MOD-UI - Plugin Host", "Special", "Language", True],
	'IR': ["InternetRadio", "Internet Radio", "Audio Generator", "Other", True]
}

ENGINE_DEFAULT_CONFIG_FILE = "{}/config/engine_config.json".format(os.environ.get('ZYNTHIAN_SYS_DIR'))
ENGINE_CONFIG_FILE = "{}/engine_config.json".format(os.environ.get('ZYNTHIAN_CONFIG_DIR'))
JALV_LV2_CONFIG_FILE = "{}/jalv/plugins.json".format(os.environ.get('ZYNTHIAN_CONFIG_DIR'))

engines = None
engines_by_type = None
engines_mtime = None

# ------------------------------------------------------------------------------
# Lilv LV2 library initialization
# ------------------------------------------------------------------------------


def init_lilv():
	global world
	world = lilv.World()
	# Disable language filtering
	# world.set_option(lilv.OPTION_FILTER_LANG, world.new_bool(False))
	world.load_all()
	world.ns.ev = lilv.Namespace(world, "http://lv2plug.in/ns/ext/event#")
	world.ns.presets = lilv.Namespace(world, "http://lv2plug.in/ns/ext/presets#")
	world.ns.portprops = lilv.Namespace(world, "http://lv2plug.in/ns/ext/port-props#")
	world.ns.portgroups = lilv.Namespace(world, "http://lv2plug.in/ns/ext/port-groups#")


# ------------------------------------------------------------------------------
# Engines management
# ------------------------------------------------------------------------------


def get_engines():
	try:
		mtime = os.stat(ENGINE_CONFIG_FILE).st_mtime
	except:
		mtime = None
	if not mtime or not engines_mtime or engines_mtime != mtime:
		return load_engines()
	else:
		return engines


def load_engines():
	global engines, engines_mtime
	engines = {}

	if os.path.exists(ENGINE_CONFIG_FILE):
		fpath = ENGINE_CONFIG_FILE
	else:
		fpath = JALV_LV2_CONFIG_FILE

	try:
		with open(fpath) as f:
			engines = json.load(f)
		engines_mtime = os.stat(fpath).st_mtime
		logging.debug(f'Loaded engine config with timestamp: {engines_mtime}')
	except Exception as e:
		logging.error('Loading engine config failed: {}'.format(e))

	# Regenerate config file if it doesn't exist or is an older version
	if not os.path.exists(ENGINE_CONFIG_FILE) or 'AE' in engines and "ID" not in engines['AE']:
		generate_engines_config_file(reset_rankings=1)

	get_engines_by_type()
	return engines


def sanitize_engines():
	for key, info in engines.items():
		info['ENABLED'] = bool(info['ENABLED'])
		info['QUALITY'] = int(info['QUALITY'])
		info['COMPLEX'] = int(info['COMPLEX'])


def save_engines():
	global engines_mtime

	# Make a deep copy and remove not serializable objects (ENGINE)
	sengines = copy.deepcopy(engines)
	for key, info in sengines.items():
		try:
			del info['ENGINE']
		except:
			pass
	# Save to file
	try:
		with open(ENGINE_CONFIG_FILE, 'w') as f:
			json.dump(sengines, f)
		engines_mtime = os.stat(ENGINE_CONFIG_FILE).st_mtime
		logging.info(f"Saved engine config file with timestamp {engines_mtime}")
	except Exception as e:
		logging.error(f"Saving engine config file failed: {e}")


def update_engine_defaults(refresh=True):
	global engines

	default_engines = {}
	fpath = ENGINE_DEFAULT_CONFIG_FILE
	try:
		with open(fpath) as f:
			default_engines = json.load(f)
		mtime = os.stat(fpath).st_mtime
		logging.debug(f'Loaded default engine config with timestamp: {mtime}')
	except Exception as e:
		logging.error('Loading default engine config failed: {}'.format(e))

	current_engines = {}
	fpath = ENGINE_CONFIG_FILE
	try:
		with open(fpath) as f:
			current_engines = json.load(f)
		mtime = os.stat(fpath).st_mtime
		logging.debug(f'Loaded current engine config with timestamp: {mtime}')
	except Exception as e:
		logging.error('Loading current engine config failed: {}'.format(e))

	# Merge default and current engine DBs
	if default_engines:
		for key, info in default_engines.items():
			info['EDIT'] = 0
			try:
				if current_engines[key]['EDIT'] == 1:
					info['ENABLED'] = current_engines[key]['ENABLED']
					info['EDIT'] = 1
				elif current_engines[key]['EDIT'] >= 2:
					continue
			except:
				pass
			current_engines[key] = info

		engines = current_engines
		generate_engines_config_file(refresh=refresh)


def is_engine_enabled(key, default=False):
	try:
		return engines[key]['ENABLED']
	except:
		key = key[3:]
		try:
			return engines[key]['ENABLED']
		except:
			return default


def get_engine_description(key):
	description = [
		"Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
		"Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.",
		"Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.",
		"Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."]
	return description[randrange(4)]


def generate_engines_config_file(refresh=True, reset_rankings=None):
	global engines, engines_mtime
	genengines = {}

	hash = hashlib.new('sha1')
	start = int(round(time.time()))
	try:
		if refresh:
			init_lilv()

		# Add standalone engines
		i = 0
		for key, engine_info in standalone_engine_info.items():
			engine_name = engine_info[0]
			engine_type = engine_info[2]
			try:
				engine_id = engines[key]['ID']
				engine_title = engines[key]['TITLE']
				engine_cat = engines[key]['CAT']
				if engine_cat not in engine_categories[engine_type]:
					engine_cat = engine_info[3]
				engine_index = engines[key]['INDEX']
				engine_descr = engines[key]['DESCR']
				engine_quality = engines[key]['QUALITY']
				engine_complex = engines[key]['COMPLEX']
				try:
					engine_edit = engines[key]['EDIT']
				except:
					engine_edit = 0
			except:
				hash.update(key.encode())
				engine_id = hash.hexdigest()[:10]
				engine_title = engine_info[1]
				engine_cat = engine_info[3]
				engine_index = i
				engine_descr = get_engine_description(key)
				engine_quality = 0
				engine_complex = 0
				engine_edit = 0

			if reset_rankings == 1:
				engine_quality = engine_complex = 0
			elif reset_rankings == 2:
				engine_quality = randrange(5)
				engine_complex = randrange(5)

			genengines[key] = {
				'ID': engine_id,
				'NAME': engine_name,
				'TITLE': engine_title,
				'TYPE': engine_type,
				'CAT': engine_cat,
				'ENABLED': is_engine_enabled(key, True),
				'INDEX': engine_index,
				'URL': "",
				'UI': "",
				'DESCR': engine_descr,
				"QUALITY": engine_quality,
				"COMPLEX": engine_complex,
				"EDIT": engine_edit
			}
			logging.debug("Standalone Engine '{}' => {}".format(key, genengines[key]))
			i += 1

		# Add LV2 plugins
		for plugin in world.get_all_plugins():
			engine_name = str(plugin.get_name())
			key = f"JV/{engine_name}"
			try:
				engine_id = engines[key]['ID']
				engine_title = engines[key]['TITLE']
				engine_type = engines[key]['TYPE']
				engine_cat = engines[key]['CAT']
				if engine_cat not in engine_categories[engine_type]:
					try:
						engine_cat = lv2class2engcat[engine_cat]
					except:
						engine_cat = get_plugin_cat(plugin)
				engine_index = engines[key]['INDEX']
				engine_descr = engines[key]['DESCR']
				engine_quality = engines[key]['QUALITY']
				engine_complex = engines[key]['COMPLEX']
				try:
					engine_edit = engines[key]['EDIT']
				except:
					engine_edit = 0
			except:
				hash.update(key.encode())
				engine_id = hash.hexdigest()[:10]
				engine_title = engine_name
				engine_type = get_plugin_type(plugin).value
				engine_cat = get_plugin_cat(plugin)
				engine_index = 9999
				engine_descr = get_engine_description(key)
				engine_quality = 0
				engine_complex = 0
				engine_edit = 0

			if reset_rankings == 1:
				engine_quality = engine_complex = 0
			elif reset_rankings == 2:
				engine_quality = randrange(5)
				engine_complex = randrange(5)

			genengines[key] = {
				'ID': engine_id,
				'NAME': engine_name,
				'TITLE': engine_title,
				'TYPE': engine_type,
				'CAT': engine_cat,
				'ENABLED': is_engine_enabled(key, False),
				'INDEX': engine_index,
				'URL': str(plugin.get_uri()),
				'UI': is_plugin_ui(plugin),
				'DESCR': engine_descr,
				"QUALITY": engine_quality,
				"COMPLEX": engine_complex,
				"EDIT": engine_edit
			}
			logging.debug("LV2 Plugin '{}' => {}".format(engine_name, genengines[key]))

		# Sort using title, so user can customize order by changing title from webconf
		engines = dict(sorted(genengines.items(), key=lambda r: r[1]['TITLE'].casefold()))

		with open(ENGINE_CONFIG_FILE, 'w') as f:
			json.dump(engines, f)
		engines_mtime = os.stat(ENGINE_CONFIG_FILE).st_mtime

	except Exception as e:
		logging.error(e)

	dt = int(round(time.time())) - start
	logging.debug('Generating engine config file took {}s'.format(dt))


def get_engines_by_type():
	global engines_by_type
	engines_by_type = {}

	for t in EngineType:
		engines_by_type[t.value] = {}

	for key, info in engines.items():
		engines_by_type[info['TYPE']][key] = info

	return engines_by_type

# ------------------------------------------------------------------------------
# LV2 plugin info functions
# ------------------------------------------------------------------------------


def is_plugin_ui(plugin):
	for uri in plugin.get_data_uris():
		try:
			with open(urllib.parse.unquote(str(uri)[7:])) as f:
				ttl = f.read()
				if ttl.find("a ui:Qt5UI") > 0 or ttl.find("a lv2ui:Qt5UI") > 0 or ttl.find("a guiext:Qt5UI") > 0:
					return "Qt5UI"
				if ttl.find("a ui:Qt4UI") > 0 or ttl.find("a lv2ui:Qt4UI") > 0 or ttl.find("a guiext:Qt4UI") > 0:
					return "Qt4UI"
				if ttl.find("a ui:X11UI") > 0 or ttl.find("a lv2ui:X11UI") > 0 or ttl.find("a guiext:X11") > 0:
					return "X11UI"
		except:
			logging.debug("Can't find UI for plugin %s", str(plugin.get_name()))

	return None


def get_plugin_type(plugin):
	# Try to determine the plugin type from the LV2 class ...
	plugin_class = re.sub(' Plugin', '', str(plugin.get_class().get_label()))
	
	if plugin_class in lv2_plugin_classes["MIDI_SYNTH"]:
		return EngineType.MIDI_SYNTH

	elif plugin_class in lv2_plugin_classes["AUDIO_EFFECT"]:
		return EngineType.AUDIO_EFFECT

	elif plugin_class in lv2_plugin_classes["AUDIO_GENERATOR"]:
		return EngineType.AUDIO_GENERATOR

	# If failed to determine the plugin type using the LV2 class, 
	# inspect the input/output ports ...

	n_audio_in = plugin.get_num_ports_of_class(world.ns.lv2.InputPort, world.ns.lv2.AudioPort)
	n_audio_out = plugin.get_num_ports_of_class(world.ns.lv2.OutputPort, world.ns.lv2.AudioPort)
	n_midi_in = plugin.get_num_ports_of_class(world.ns.lv2.InputPort, world.ns.ev.EventPort)
	n_midi_out = plugin.get_num_ports_of_class(world.ns.lv2.OutputPort, world.ns.ev.EventPort)
	n_midi_in += plugin.get_num_ports_of_class(world.ns.lv2.InputPort, world.ns.atom.AtomPort)
	n_midi_out += plugin.get_num_ports_of_class(world.ns.lv2.OutputPort, world.ns.atom.AtomPort)

	if n_audio_out > 0 and n_audio_in == 0:
		if n_midi_in > 0:
			return EngineType.MIDI_SYNTH
		else:
			return EngineType.AUDIO_GENERATOR

	if n_audio_out > 0 and n_audio_in > 0 and n_midi_out == 0:
		return EngineType.AUDIO_EFFECT

	if n_midi_in > 0 and n_midi_out > 0 and n_audio_in == n_audio_out == 0:
		return EngineType.MIDI_TOOL

	#return EngineType.UNKNOWN
	return EngineType.AUDIO_EFFECT


def get_plugin_cat(plugin):
	plugin_class = str(plugin.get_class().get_label())
	plugin_class = re.sub(' Plugin', '', plugin_class)
	try:
		return lv2class2engcat[plugin_class]
	except:
		return "Other"

# ------------------------------------------------------------------------------
# LV2 Bank/Preset management
# ------------------------------------------------------------------------------

# workaround to fix segfault:
def generate_presets_cache_workaround():
	start = int(round(time.time()))
	for plugin in world.get_all_plugins():
		plugin.get_name()
	logging.info('Workaround took {}s'.format(int(round(time.time())) - start))


def generate_all_presets_cache(refresh=True):
	if refresh:
		init_lilv()

	for plugin in world.get_all_plugins():
		_generate_plugin_presets_cache(plugin)


def generate_plugin_presets_cache(plugin_url, refresh=True):
	if refresh:
		init_lilv()

	wplugins = world.get_all_plugins()
	return _generate_plugin_presets_cache(wplugins[plugin_url])


def _get_plugin_preset_cache_fpath(plugin_name):
	return "{}/jalv/presets_{}.json".format(os.environ.get('ZYNTHIAN_CONFIG_DIR'), sanitize_fname(plugin_name))


def _generate_plugin_presets_cache(plugin):
	plugin_name = str(plugin.get_name())
	plugin_url = str(plugin.get_uri())
	logging.debug("Generating Bank/Presets cache for '{}' <{}>".format(plugin_name, plugin_url))

	banks_dict = {}
	presets_info = {}

	# Get banks
	banks = plugin.get_related(world.ns.presets.Bank)
	for bank in banks:
		label = world.get(bank, world.ns.rdfs.label, None)
		if label is None:
			logging.debug("Bank <{}> has no label!".format(bank))

		banks_dict[str(bank)] = str(label)
		presets_info[str(label)] = {
			'bank_url': str(bank),
			'presets': []
		}
		logging.debug("Bank {} <{}>".format(label, bank))

	presets_info = dict(sorted(presets_info.items()))
	presets_info['None'] = {
			'bank_url': None,
			'presets': []
	}

	# Get presets
	presets = plugin.get_related(world.ns.presets.Preset)
	for preset in presets:
		world.load_resource(preset)

		label = world.get(preset, world.ns.rdfs.label, None)
		if label is None:
			logging.debug("Preset <{}> has no label!".format(preset))

		bank = world.get(preset, world.ns.presets.bank, None)
		if bank is None:
			logging.debug("Preset <{}> has no bank!".format(preset))
		else:
			try:
				bank = banks_dict[str(bank)]
			except:
				logging.debug("Bank <{}> doesn't exist!".format(bank))
				bank = None

		presets_info[str(bank)]['presets'].append({
			'label': str(label),
			'url': str(preset)
		})

		logging.debug("Preset {} <{}> => <{}>".format(label, bank, preset))
		
	for preset in presets:
		world.unload_resource(preset)

	# Save cache file
	save_plugin_presets_cache(plugin_name, presets_info)

	return presets_info


def get_plugin_presets_cache(plugin_name):
	fpath_cache = _get_plugin_preset_cache_fpath(plugin_name)
	try:
		with open(fpath_cache) as f:
			presets_info = json.load(f)
	except Exception as e:
		logging.error("Can't load presets cache file '{}': {}".format(fpath_cache, e))
		try:
			return generate_plugin_presets_cache(engines["JV/" + plugin_name]['URL'])
		except Exception as e:
			logging.error("Error generating presets cache for '{}': {}".format(plugin_name, e))
			presets_info = {}

	return presets_info


def get_plugin_presets(plugin_name):
	return get_plugin_presets_cache(plugin_name)


def save_plugin_presets_cache(plugin_name, presets_info):
	# Sort and Remove empty banks 
	keys = list(presets_info.keys())
	for k in keys:
		if len(presets_info[k]['presets']) == 0:
			del(presets_info[k])
		else:
			presets_info[k]['presets'] = sorted(presets_info[k]['presets'], key=lambda k: k['label'])

	# Dump json to file
	fpath_cache = _get_plugin_preset_cache_fpath(plugin_name)
	try:
		with open(fpath_cache, 'w') as f:
			json.dump(presets_info, f)
	except Exception as e:
		logging.error("Can't save presets cache file '{}': {}".format(fpath_cache, e))


def sanitize_fname(s):
	"""Take a string and return a valid filename constructed from the string.
	Uses a whitelist approach: any characters not present in valid_chars are
	removed. Also spaces are replaced with underscores.

	Note: this method may produce invalid filenames such as ``, `.` or `..`
	When I use this method I prepend a date string like '2009_01_15_19_46_32_'
	and append a file extension like '.txt', so I avoid the potential of using
	an invalid filename.
	"""

	valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
	filename = ''.join(c for c in s if c in valid_chars)
	filename = filename.replace(' ', '_')  # I don't like spaces in filenames.
	return filename


# ------------------------------------------------------------------------------
# LV2 Port management
# ------------------------------------------------------------------------------


def get_plugin_ports(plugin_url):
	wplugins = world.get_all_plugins()
	plugin = wplugins[plugin_url]

	ports_info = {}
	for i in range(plugin.get_num_ports()):
		port = plugin.get_port_by_index(i)
		if port.is_a(lilv.LILV_URI_INPUT_PORT) and port.is_a(lilv.LILV_URI_CONTROL_PORT):
			port_name = str(port.get_name())
			port_symbol = str(port.get_symbol())

			is_toggled = port.has_property(world.ns.lv2.toggled)
			is_integer = port.has_property(world.ns.lv2.integer)
			is_enumeration = port.has_property(world.ns.lv2.enumeration)
			is_logarithmic = port.has_property(world.ns.portprops.logarithmic)
			not_on_gui = port.has_property(world.ns.portprops.notOnGUI)
			display_priority = port.get(world.ns.lv2.displayPriority)
			if display_priority is None:
				display_priority = 0
			else:
				display_priority = int(display_priority)

			#logging.debug("PORT {} properties =>".format(port.get_symbol()))
			#for node in port.get_properties():
			#	logging.debug("    => {}".format(get_node_value(node)))

			pgroup_index = None
			pgroup_name = None
			pgroup_symbol = None
			pgroup = port.get(world.ns.portgroups.group)
			if pgroup is not None:
				#pgroup_key = str(pgroup).split("#")[-1]
				pgroup_index = world.get(pgroup, world.ns.lv2.index, None)
				if pgroup_index is not None:
					pgroup_index = int(pgroup_index)
					#logging.warning("Port group <{}> has no index.".format(pgroup_key))
				pgroup_name = world.get(pgroup, world.ns.lv2.name, None)
				if pgroup_name is None:
					pgroup_name = world.get(pgroup, world.ns.rdfs.label, None)
				if pgroup_name is not None:
					pgroup_name = str(pgroup_name)
					#logging.warning("Port group <{}> has no name.".format(pgroup_key))
				pgroup_symbol = world.get(pgroup, world.ns.lv2.symbol, None)
				if pgroup_symbol is not None:
					pgroup_symbol = str(pgroup_symbol)
					#logging.warning("Port group <{}> has no symbol.".format(pgroup_key))
			#else:
				#logging.debug("Port <{}> has no group.".format(port_symbol))

			sp = []
			for p in port.get_scale_points():
				sp.append({
					'label': str(p.get_label()),
					'value': get_node_value(p.get_value())
				})
			sp = sorted(sp, key=lambda k: k['value'])

			r = port.get_range()
			try:
				vmin = get_node_value(r[1])
			except:
				vmin = min(sp, key=lambda x: x['value'])
			try:
				vmax = get_node_value(r[2])
			except:
				vmax = max(sp, key=lambda x: x['value'])
			try:
				vdef = get_node_value(r[0])
			except:
				vdef = vmin

			info = {
				'index': i,
				'symbol': port_symbol,
				'name': port_name,
				'group_index': pgroup_index,
				'group_name': pgroup_name,
				'group_symbol': pgroup_symbol,
				'value': vdef,
				'range': {
					'default': vdef,
					'min': vmin,
					'max': vmax
				},
				'is_toggled': is_toggled,
				'is_integer': is_integer,
				'is_enumeration': is_enumeration,
				'is_logarithmic': is_logarithmic,
				'not_on_gui': not_on_gui,
				'display_priority': display_priority,
				'scale_points': sp
			}
			ports_info[i] = info
			#logging.debug("PORT {} => {}".format(i, info))

	return ports_info


def get_node_value(node):
	if node.is_int():
		return int(node)
	elif node.is_float():
		return float(node)
	else:
		return str(node)

# ------------------------------------------------------------------------------
# Main program
# ------------------------------------------------------------------------------

# Init Lilv
init_lilv()
# Load engine info from cache
load_engines()

if __name__ == '__main__':
	# Init logging
	#log_level = logging.DEBUG
	#log_level = logging.WARNING
	log_level = logging.INFO
	logging.basicConfig(format='%(levelname)s:%(module)s: %(message)s', stream=sys.stderr, level=log_level)
	logging.getLogger().setLevel(level=log_level)

	start = int(round(time.time()))
	if len(sys.argv) > 1:
		if sys.argv[1] == "engines":
			prev_engines = engines.keys()
			#generate_engines_config_file(refresh=False)
			update_engine_defaults(refresh=False)
			# Detect new LV2 plugins and generate presets cache for them
			for key, info in engines.items():
				if key not in prev_engines and 'URL' in info and info['URL']:
					generate_plugin_presets_cache(info['URL'], False)

		elif sys.argv[1] == "presets":
			generate_presets_cache_workaround()

			if len(sys.argv) > 2:
				plugin_url = sys.argv[2]
				generate_plugin_presets_cache(plugin_url, False)
			else:
				generate_all_presets_cache(False)

		elif sys.argv[1] == "ports":
			if len(sys.argv) > 2:
				print(get_plugin_ports(sys.argv[2]))
			else:
				pass

		elif sys.argv[1] == "all":
			generate_engines_config_file(refresh=False)
			generate_all_presets_cache(False)

	else:
		generate_engines_config_file(refresh=False)
		generate_all_presets_cache(False)

	#get_plugin_ports("https://github.com/dcoredump/dexed.lv2")
	#get_plugin_ports("http://code.google.com/p/amsynth/amsynth")
	#get_plugin_ports("https://obxd.wordpress.com")
	#get_plugin_ports("http://kunz.corrupt.ch/products/tal-noisemaker")
	#get_plugin_ports("http://synthv1.sourceforge.net/lv2")
	#get_plugin_ports("http://drumkv1.sourceforge.net/lv2")

	#generate_plugin_presets_cache("http://code.google.com/p/amsynth/amsynth")
	#print(get_plugin_presets("Dexed"))

	logging.info('Command took {}s'.format(int(round(time.time())) - start))

# ------------------------------------------------------------------------------
