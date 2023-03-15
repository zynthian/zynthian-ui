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

from os import environ
from sys import stderr
import oyaml as yaml
import logging
import copy

# Zynthian specific modules
from zyngui import zynthian_gui_config

#------------------------------------------------------------------------------
# Zynthian Keyboard Binding Class
#------------------------------------------------------------------------------

class zynthian_gui_keybinding:
	"""
	Provides interface to key binding
	
	Note: This class is a singleton and should not be instantiated directly (which will raise an exception).
	Use getInstance() to get the instance of the singleton and access functions and methods from that instance.
	"""

	modifiers = {
		'shift': 1,
		'caps': 2,
		'ctrl': 4,
		'alt': 8,
		'num': 16,
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

		"31 0": "ZYNSWITCH 0",
		"45 0": "ZYNSWITCH 1",
		"22 0": "ZYNSWITCH 1",
		"9 0": "ZYNSWITCH 1",
		"32 0": "ZYNSWITCH 2",
		"46 0": "ZYNSWITCH 3",
		"36 0": "ZYNSWITCH 3",

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


	__instance = None
	
	@staticmethod
	def getInstance():
		"""
		Access the singleton
		
		Returns
		-------
		zynthian_gui_keybinding
			The singleton object which should be used for all access
		"""

		if zynthian_gui_keybinding.__instance == None:
			zynthian_gui_keybinding()

		return zynthian_gui_keybinding.__instance


	def __init__(self):
		"""
		Do not initiate this class directly. Use getInstance() to access the singleton object.
		
		Raises
		------
		Exception
			If object already instantiated.
		"""
		
		if zynthian_gui_keybinding.__instance == None:
			zynthian_gui_keybinding.__instance = self
		else:
			raise Exception("Use getInstance() to get the singleton object.")

		self.reset_config()


	def get_key_action(self, keycode, modifier):
		"""
		Get the name of the function bound to the key combination passed
		
		Parameters
		----------
		keycode : int
			Keyboard code to lookup
		modifier : int or None
			Keyboard modifier to lookup [0: none, 1: shift, 2: capslock, 4: ctrl, 8: alt, 16: numlock, 64: super, 128: altgr]
			None to match any modifer (other configurations with modifiers will be captured first)

		Returns
		-------
		str
			Name of the function mapped to the key binding
			<None> if no match found		
		"""
	
		logging.debug(f"Get keybinding function name for keycode: {keycode}, modifier: {modifier}")
		try:
			# Check for defined modifier
			return self.map[f"{keycode} {modifier}"]
		except:
			try:
				# Check for "any" modifier
				return self.map[keycode]
			except:
				logging.debug("Key not configured")


	def load(self, config="keybinding"):
		"""
		Load key binding map from file
		
		Parameters
		----------
		config : str,optional
			Name of configuration to load - the file <config>.yaml will be loaded from the zynthian config directory
			Default: 'keybinding'
		
		Returns
		-------
		bool
			True on success		
		"""

		logging.info("Loading key binding from {}.yaml".format(config))
		config_dir = environ.get('ZYNTHIAN_CONFIG_DIR', "/zynthian/config")
		config_fpath = config_dir + "/" + config + ".yaml"
		try:
			with open(config_fpath, "r") as fh:
				yml = fh.read()
				logging.debug("Loading keyboard binding config file '{}' =>\n{}".format(config_fpath, yml))
				self.map = yaml.load(yml, Loader=yaml.SafeLoader)
				return True
		except Exception as e:
			logging.debug("Loading default keyboard bindings.")
			self.reset_config()
			return False


	def save(self, config="keybinding"):
		"""
		Save key binding map to file
		
		Parameters
		----------
		config : str,optional
			Name of configuration to save - the file <config>.yaml will be saved to the Zynthian config directory
			Default: 'keybinding'
		
		Returns
		-------
		bool
			True on success
		"""
		
		logging.info("Saving key binding to %s.yaml", config)
		config_dir = environ.get('ZYNTHIAN_CONFIG_DIR', "/zynthian/config")
		config_fpath = config_dir + "/" + config + ".yaml"
		try:
			with open(config_fpath, "w") as fh:
				yaml.dump(self.map, fh)
				logging.info("Saving keyboard binding config file {}".format(config_fpath))
				return True

		except Exception as e:
			logging.error("Can't save keyboard binding config file '{}': {}".format(config_fpath,e))
			return False


	def reset_config(self):
		"""
		Reset keyboard binding to default values
		"""

		self.map = copy.copy(self.default_map)
		self.enable()


	def bind_key(self, keysym, modifier, cuia):
		"""
		Bind key/action pair
		Parameters
		----------
		keysym : str
			Keyboard symbol
		modifier: int
			Numeric key modifier. It can be OR-composed.
		cuia: str
			Callable UI action, including parameters
		"""

		if modifier is None:
			modifier = 0
		map["{} {}".format(keysym, modifier)] = cuia


	def enable(self, enabled=True):
		"""
		Enable or disable keyboard binding

		Parameters
		----------
		enabled : bool,optional
			True to enable, false to disable - default: True
		"""
		
		self.enabled = enabled


	def isEnabled(self):
		"""
		Is keyboard binding enabled?

		Returns
		-------
		bool True if enabled
		"""

		return self.enabled

#------------------------------------------------------------------------------