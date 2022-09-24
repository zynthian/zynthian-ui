#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian LV2-plugin management
# 
# zynthian LV2
# 
# Copyright (C) 2015-2020 Fernando Moyano <jofemodo@zynthian.org>
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
import sys
import json
import lilv
import time
import string
import logging
import contextlib
import re
import urllib.parse

from enum import Enum
from collections import OrderedDict

#------------------------------------------------------------------------------

def init_lilv():
	global world

	world.load_all()

	world.ns.ev = lilv.Namespace(world, "http://lv2plug.in/ns/ext/event#")
	world.ns.presets = lilv.Namespace(world, "http://lv2plug.in/ns/ext/presets#")
	world.ns.portprops = lilv.Namespace(world, "http://lv2plug.in/ns/ext/port-props#")
	world.ns.portgroups = lilv.Namespace(world, "http://lv2plug.in/ns/ext/port-groups#")


#------------------------------------------------------------------------------
# LV2 Plugin management
#------------------------------------------------------------------------------

class PluginType(Enum):
	MIDI_SYNTH = "MIDI Synth"
	MIDI_TOOL = "MIDI Tool"
	AUDIO_EFFECT = "Audio Effect"
	AUDIO_GENERATOR = "Audio Generator"
	#UNKNOWN = "Unknown"

JALV_LV2_CONFIG_FILE = "{}/jalv/plugins.json".format(os.environ.get('ZYNTHIAN_CONFIG_DIR'))
JALV_LV2_CONFIG_FILE_ALL = "{}/jalv/all_plugins.json".format(os.environ.get('ZYNTHIAN_CONFIG_DIR'))

plugins = None
plugin_by_type = None
plugins_mtime = None


def get_plugins():
	global plugins, plugins_mtime
	mtime = os.stat(JALV_LV2_CONFIG_FILE).st_mtime
	if mtime != plugins_mtime:
		plugins_mtime = mtime
		return load_plugins()
	else:
		return plugins


def load_plugins():
	global plugins, plugins_mtime
	plugins = OrderedDict()

	try:
		with open(JALV_LV2_CONFIG_FILE) as f:
			plugins = json.load(f, object_pairs_hook=OrderedDict)

		plugins_mtime = os.stat(JALV_LV2_CONFIG_FILE).st_mtime
		convert_from_all_plugins()

	except Exception as e:
		logging.debug('Loading list of LV2-Plugins failed: {}'.format(e))
		generate_plugins_config_file()

	get_plugins_by_type()
	return plugins


def save_plugins():
	global plugins, plugins_mtime

	try:
		with open(JALV_LV2_CONFIG_FILE, 'w') as f:
			json.dump(plugins, f)

		plugins_mtime = os.stat(JALV_LV2_CONFIG_FILE).st_mtime
	
	except Exception as e:
		logging.error('Saving list of LV2-Plugins failed: {}'.format(e))


def is_plugin_enabled(plugin_name):
	global plugins
	try:
		return plugins[plugin_name]['ENABLED']
	except:
		return False


def	is_plugin_ui(plugin):
	for uri in plugin.get_data_uris():
		try:
			with open(urllib.parse.unquote(str(uri)[7:])) as f:
				ttl = f.read()
				if ttl.find("a ui:Qt5UI")>0 or ttl.find("a lv2ui:Qt5UI")>0:
					return "Qt5UI"
				if ttl.find("a ui:Qt4UI")>0 or ttl.find("a lv2ui:Qt4UI")>0:
					return "Qt4UI"
				if ttl.find("a ui:X11UI")>0 or ttl.find("a lv2ui:X11UI")>0:
					return "X11UI"
		except:
			logging.debug("Can't find UI for plugin %s", str(plugin.get_name()))

	return None


def generate_plugins_config_file(refresh=True):
	global world, plugins, plugins_mtime
	genplugins = OrderedDict()

	start = int(round(time.time()))
	try:
		if refresh:
			init_lilv()

		for plugin in world.get_all_plugins():
			name = str(plugin.get_name())
			genplugins[name] = {
				'URL': str(plugin.get_uri()),
				'TYPE': get_plugin_type(plugin).value,
				'CLASS': re.sub(' Plugin', '', str(plugin.get_class().get_label())),
				'ENABLED': is_plugin_enabled(name),
				'UI': is_plugin_ui(plugin)
				#'UI': plugin.get_uis()
				# get_binary_uri()
			}
			logging.debug("Plugin '{}' => {}".format(name, genplugins[name]))

		plugins = OrderedDict(sorted(genplugins.items()))

		with open(JALV_LV2_CONFIG_FILE, 'w') as f:
			json.dump(plugins, f)

		plugins_mtime = os.stat(JALV_LV2_CONFIG_FILE).st_mtime

	except Exception as e:
		logging.error('Generating list of LV2-Plugins failed: {}'.format(e))

	dt = int(round(time.time())) - start
	logging.debug('LV2 plugin list generation took {}s'.format(dt))


def get_plugins_by_type():
	global plugins_by_type
	plugins_by_type = OrderedDict()
	for t in PluginType:
		plugins_by_type[t.value] = OrderedDict()

	for name, properties in plugins.items():
		plugins_by_type[properties['TYPE']][name] = properties

	return plugins_by_type


def convert_from_all_plugins():
	global plugins, plugins_mtime
	try:
		name, prop = next(iter(plugins.items()))
		if 'ENABLED' not in prop:
			enplugins = plugins
			try:
				with open(JALV_LV2_CONFIG_FILE_ALL) as f:
					plugins = json.load(f, object_pairs_hook=OrderedDict)
			except:
				generate_plugins_config_file()

			logging.debug("Converting LV2 config files ...")

			for name, properties in plugins.items():
				if name in enplugins:
					plugins[name]['ENABLED'] = True
				else:
					plugins[name]['ENABLED'] = False

			with open(JALV_LV2_CONFIG_FILE,'w') as f:
				json.dump(plugins, f)

			plugins_mtime = os.stat(JALV_LV2_CONFIG_FILE).st_mtime

			try:
				os.remove(JALV_LV2_CONFIG_FILE_ALL)
			except OSError:
				pass

	except Exception as e:
		logging.error("Converting from old config format failed: {}".format(e))


def get_plugin_type(plugin):
	global world
	lv2_plugin_classes = {
		"MIDI_SYNTH" : ("Instrument"),

		"AUDIO_EFFECT" : ("Analyser", "Spectral", "Delay", "Compressor", "Distortion", "Filter", "Equaliser",
			"Modulator", "Expander", "Spatial", "Limiter", "Pitch Shifter", "Reverb", "Simulator", "Envelope",
			"Gate", "Amplifier", "Chorus", "Flanger", "Phaser", "Highpass", "Lowpass", "Dynamics"),

		"AUDIO_GENERATOR": ("Oscillator", "Generator"),

		"UNKNOWN": ("Utility", "Plugin")
	}

	# Try to determine the plugin type from the LV2 class ...
	plugin_class = re.sub(' Plugin', '', str(plugin.get_class().get_label()))
	
	if plugin_class in lv2_plugin_classes["MIDI_SYNTH"]:
		return PluginType.MIDI_SYNTH

	elif plugin_class in lv2_plugin_classes["AUDIO_EFFECT"]:
		return PluginType.AUDIO_EFFECT

	elif plugin_class in lv2_plugin_classes["AUDIO_GENERATOR"]:
		return PluginType.AUDIO_GENERATOR

	# If failed to determine the plugin type using the LV2 class, 
	# inspect the input/output ports ...

	n_audio_in = plugin.get_num_ports_of_class(world.ns.lv2.InputPort, world.ns.lv2.AudioPort)
	n_audio_out = plugin.get_num_ports_of_class(world.ns.lv2.OutputPort, world.ns.lv2.AudioPort)
	n_midi_in = plugin.get_num_ports_of_class(world.ns.lv2.InputPort, world.ns.ev.EventPort)
	n_midi_out = plugin.get_num_ports_of_class(world.ns.lv2.OutputPort, world.ns.ev.EventPort)
	n_midi_in += plugin.get_num_ports_of_class(world.ns.lv2.InputPort, world.ns.atom.AtomPort)
	n_midi_out += plugin.get_num_ports_of_class(world.ns.lv2.OutputPort, world.ns.atom.AtomPort)

	if n_audio_out>0 and n_audio_in==0:
		if n_midi_in>0:
			return PluginType.MIDI_SYNTH
		else:
			return PluginType.AUDIO_GENERATOR

	if n_audio_out>0 and n_audio_in>0 and n_midi_out==0:
		return PluginType.AUDIO_EFFECT

	if n_midi_in>0 and n_midi_out>0 and n_audio_in==n_audio_out==0:
		return PluginType.MIDI_TOOL

	#return PluginType.UNKNOWN
	return PluginType.AUDIO_EFFECT


#------------------------------------------------------------------------------
# LV2 Bank/Preset management
#------------------------------------------------------------------------------

def generate_all_presets_cache(refresh=True):
	global world

	if refresh:
		init_lilv()

	for plugin in world.get_all_plugins():
		_generate_plugin_presets_cache(plugin)


def generate_plugin_presets_cache(plugin_url, refresh=True):
	global world

	if refresh:
		init_lilv()

	wplugins = world.get_all_plugins()
	return _generate_plugin_presets_cache(wplugins[plugin_url])


def _get_plugin_preset_cache_fpath(plugin_name):
	return  "{}/jalv/presets_{}.json".format(os.environ.get('ZYNTHIAN_CONFIG_DIR'), sanitize_fname(plugin_name))


def _generate_plugin_presets_cache(plugin):
	global world

	plugin_name = str(plugin.get_name())
	plugin_url = str(plugin.get_uri())
	logging.debug("Generating Bank/Presets cache for '{}' <{}>".format(plugin_name, plugin_url))

	banks_dict = {}
	presets_info = OrderedDict()

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

	presets_info = OrderedDict(sorted(presets_info.items()))
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
			presets_info = json.load(f, object_pairs_hook=OrderedDict)
	except Exception as e:
		logging.error("Can't load presets cache file '{}': {}".format(fpath_cache, e))
		try:
			global plugins
			return generate_plugin_presets_cache(plugins[plugin_name]['URL'])
		except Exception as e:
			logging.error("Error generating presets cache for '{}': {}".format(plugin_name, e))
			presets_info = OrderedDict()

	return presets_info


def get_plugin_presets(plugin_name):
	return get_plugin_presets_cache(plugin_name)


def save_plugin_presets_cache(plugin_name, presets_info):
	# Sort and Remove empty banks 
	keys = list(presets_info.keys())
	for k in keys:
		if len(presets_info[k]['presets'])==0:
			del(presets_info[k])
		else:
			presets_info[k]['presets'] = sorted(presets_info[k]['presets'], key=lambda k: k['label'])

	# Dump json to file
	fpath_cache = _get_plugin_preset_cache_fpath(plugin_name)
	try:
		with open(fpath_cache,'w') as f:
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
	filename = filename.replace(' ','_') # I don't like spaces in filenames.
	return filename


#------------------------------------------------------------------------------
# LV2 Port management
#------------------------------------------------------------------------------


def get_plugin_ports(plugin_url):
	global world

	wplugins = world.get_all_plugins()
	plugin = wplugins[plugin_url]

	ports_info = OrderedDict()
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
				vmin = min(sp, key=lambda x:x['value'])
			try:
				vmax = get_node_value(r[2])
			except:
				vmax = max(sp, key=lambda x:x['value'])
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

#------------------------------------------------------------------------------

# Init Lilv
world = lilv.World()
init_lilv()

# Load presets from cache
load_plugins()

if __name__ == '__main__':

	#log_level=logging.DEBUG
	#log_level=logging.WARNING
	log_level=logging.INFO
	logging.basicConfig(format='%(levelname)s:%(module)s: %(message)s', stream=sys.stderr, level=log_level)
	logging.getLogger().setLevel(level=log_level)

	start = int(round(time.time()))
	if len(sys.argv)>1:
		if sys.argv[1]=="plugins":
			generate_plugins_config_file(False)

		elif sys.argv[1]=="presets":
			#workaround to fix segfault:
			for plugin in world.get_all_plugins():
				plugin.get_name()
			logging.info('Workaround took {}s'.format(int(round(time.time())) - start))

			if len(sys.argv)>2:
				plugin_url = sys.argv[2]
				generate_plugin_presets_cache(plugin_url, False)
			else:
				generate_all_presets_cache(False)

		elif sys.argv[1]=="ports":
			if len(sys.argv)>2:
				print(get_plugin_ports(sys.argv[2]))
			else:
				pass

		elif sys.argv[1]=="all":
			generate_plugins_config_file(False)
			generate_all_presets_cache(False)

	else:
		generate_plugins_config_file(False)
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

#------------------------------------------------------------------------------
