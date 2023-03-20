#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian Keyboard Binding Class
# 
# Copyright (C) 2019-2023 Brian Walton <brian@riban.co.uk>
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

import json
import logging
from subprocess import run, PIPE
from os import environ

# Zynthian specific modules
#from zyngui import zynthian_gui_config

#------------------------------------------------------------------------------
# Zynthian Keyboard Binding Class
#------------------------------------------------------------------------------

class zynthian_gui_keybinding:
	"""Provides interface to key binding"""

	modifiers = {
		'shift': 1,
		'caps': 2,
		'ctrl': 4,
		'alt': 8,
		'num': 16,
		'shift_r': 32,
		'super': 64,
		'altgr': 128
	}

	default_map = {
		"65 0": "ALL_NOTES_OFF",
		"65 1": "ALL_SOUNDS_OFF",

		"110 1": "RESTART_UI",
		"110 4": "REBOOT",
		"115 4": "POWER_OFF",
		"118 4": "RELOAD_MIDI_CONFIG",

		"31": "ZYNSWITCH 0",
		"45": "ZYNSWITCH 1",
		"22": "ZYNSWITCH 1",
		"9": "ZYNSWITCH 1",
		"32": "ZYNSWITCH 2",
		"46": "ZYNSWITCH 3",
		"36": "ZYNSWITCH 3",

		"60 4": "ZYNPOT 1,1",
		"59 4": "ZYNPOT 1,-1",
		"60 0": "ZYNPOT 3,1",
		"59 0": "ZYNPOT 3,-1",
		"60 5": "ZYNPOT 0,1",
		"59 5": "ZYNPOT 0,-1",
		"60 1": "ZYNPOT 2,1",
		"59 1": "ZYNPOT 2,-1",

		"38 0": "START_AUDIO_RECORD",
		"38 1": "STOP_AUDIO_RECORD",
		"38 8": "TOGGLE_AUDIO_RECORD",
		"38 4": "START_AUDIO_PLAY",
		"38 5": "STOP_AUDIO_PLAY",
		"38 12": "TOGGLE_AUDIO_PLAY",

		"58 0": "START_MIDI_RECORD",
		"58 1": "STOP_MIDI_RECORD",
		"58 8": "TOGGLE_MIDI_RECORD",
		"58 4": "START_MIDI_PLAY",
		"58 5": "STOP_MIDI_PLAY",
		"58 12": "TOGGLE_MIDI_PLAY",

		"116": "ARROW_DOWN",
		"111": "ARROW_UP",
		"114": "ARROW_RIGHT",
		"113": "ARROW_LEFT",

		"88": "ARROW_DOWN",
		"80": "ARROW_UP",
		"85": "ARROW_RIGHT",
		"83": "ARROW_LEFT",
		"104": "ZYNSWITCH 3",
		"79": "ZYNSWITCH 0",
		"87": "ZYNSWITCH 1",
		"81": "ZYNSWITCH 2",
		"89": "ZYNSWITCH 3",

		"10": "PROGRAM_CHANGE 1",
		"11": "PROGRAM_CHANGE 2",
		"12": "PROGRAM_CHANGE 3",
		"13": "PROGRAM_CHANGE 4",
		"14": "PROGRAM_CHANGE 5",
		"15": "PROGRAM_CHANGE 6",
		"16": "PROGRAM_CHANGE 7",
		"17": "PROGRAM_CHANGE 8",
		"18": "PROGRAM_CHANGE 9",
		"19": "PROGRAM_CHANGE 0"
	}

	map = default_map.copy()

	@classmethod
	def get_key_action(cls, keycode, modifier):
		"""Get the name of the function bound to a key combination

		keycode : Keyboard code
		modifier : Bitwise flags of keyboard modifiers [0: none, 1: shift, 2: capslock, 4: ctrl, 8: alt, 16: numlock, 64: super, 128: altgr]
			None to match any modifer (other configurations with modifiers will be captured first)

		Returns : Space separated list of cuia and parameters mapped to the keybinding or None if no match found		
		"""
	
		logging.debug(f"Get keybinding function name for keycode: {keycode}, modifier: {modifier}")
		try:
			# Check for defined modifier
			if keycode not in [63,77,79,80,81,82,83,84,85,86,87,88,89,90,91,104,106]:
				modifier &= 239
			return zynthian_gui_keybinding.map[f"{keycode} {modifier}"]
		except:
			try:
				# Check for "any" modifier
				return zynthian_gui_keybinding.map[f"{keycode}"]
			except:
				logging.debug("Key not configured")

	@classmethod
	def load(cls, config="keybinding"):
		"""Load key binding map from file
		config : Name of configuration to load - the file <config>.json will be loaded from the zynthian config directory
			Default: 'keybinding'
		Returns : True on success
		"""

		config_fpath = f"{environ.get('ZYNTHIAN_CONFIG_DIR', '/zynthian/config')}/{config}.json"
		try:
			with open(config_fpath, "r") as fh:
				j = fh.read()
				zynthian_gui_keybinding.map =  json.loads(j)
				return True
		except Exception as e:
			zynthian_gui_keybinding.map = zynthian_gui_keybinding.default_map.copy()
			return False


	@classmethod
	def save(cls, config="keybinding"):
		"""
		Save key binding map to file
		
		config : Name of configuration to save - the file <config>.json will be saved to the Zynthian config directory
			Default: 'keybinding'
		Returns : True on success
		"""
		
		config_fpath = f"{environ.get('ZYNTHIAN_CONFIG_DIR', '/zynthian/config')}/{config}.json"
		try:
			with open(config_fpath, "w") as fh:
				fh.write(json.dumps(zynthian_gui_keybinding.map))
				logging.info("Saving keyboard binding config file {}".format(config_fpath))
				return True

		except Exception as e:
			logging.error("Can't save keyboard binding config file '{}': {}".format(config_fpath,e))
			return False


	@classmethod
	def reset_config(cls):
		"""Reset keyboard binding to default values"""

		zynthian_gui_keybinding.map = zynthian_gui_keybinding.default_map.copy()


	@classmethod
	def add_binding(cls, keycode, modifier, cuia):
		"""Bind key/action pair
		
		keycode : Keyboard code
		modifier: Bitwise modifier flags or None to ignore modifiers
		cuia: Callable UI action, including parameters or None to clear binding
		"""

		zynthian_gui_keybinding.remove_binding(keycode, modifier)
		try:
			if modifier is None:
				zynthian_gui_keybinding.map[f"{keycode}"] = cuia
			else:
				zynthian_gui_keybinding.map[f"{keycode} {modifier}"] = cuia
		except:
			pass

	@classmethod
	def remove_binding(cls, key):
		"""Removes a keybinding

		key : Keyboard code and modifier separated by space
		"""

		try:
			del zynthian_gui_keybinding.map[key]
		except:
			pass

	@classmethod
	def get_keymap(cls):
		"""Get the currently loaded keyboard translation table
		
		Returns : Dictionary of key names mapped by keycode
		"""

		keymap = {}
		result = run(["xmodmap", "-pke", "-display", ":0"], stdout=PIPE)
		raw_map = result.stdout.decode("utf-8").split("\n")
		for line in raw_map:
			if line.startswith("keycode"):
				parts = line.split()
				try:
					keymap[int(parts[1])] = parts[3]
				except:
					pass
		return keymap

	@classmethod
	def get_reverse_keymap(cls):
		"""Get the currently loaded keyboard translation table
		
		Returns : Dictionary of keycodes mapped by key name
		"""

		keymap = {}
		result = run(["xmodmap", "-pke", "-display", ":0"], stdout=PIPE)
		raw_map = result.stdout.decode("utf-8").split("\n")
		for line in raw_map:
			if line.startswith("keycode"):
				parts = line.split()
				try:
					keymap[int(parts[3])] = parts[1]
				except:
					pass
		return keymap

#------------------------------------------------------------------------------