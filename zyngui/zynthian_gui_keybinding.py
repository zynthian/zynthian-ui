#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian Keyboard Binding Class
# 
# Copyright (C) 2019-2022 Brian Walton <brian@riban.co.uk>
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
import liblo

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
		'alt': 8
	}

	default_map = {
		"space 0": "ALL_NOTES_OFF",
		"space 1": "ALL_SOUNDS_OFF",

		"home 1": "RESTART_UI",
		"home 4": "REBOOT",
		"end 4": "POWER_OFF",
		"insert 4": "RELOAD_MIDI_CONFIG",

		"i": "ZYNSWITCH 0",
		"k": "ZYNSWITCH 1",
		"backspace": "ZYNSWITCH 1",
		"escape": "ZYNSWITCH 1",
		"o": "ZYNSWITCH 2",
		"l": "ZYNSWITCH 3",
		"return": "ZYNSWITCH 3",

		"period 4": "ZYNPOT 1,1",
		"comma 4": "ZYNPOT 1,-1",
		"period 0": "ZYNPOT 3,1",
		"comma 0": "ZYNPOT 3,-1",
		"greater 5": "ZYNPOT 0,1",
		"less 5": "ZYNPOT 0,-1",
		"greater 1": "ZYNPOT 2,1",
		"less 1": "ZYNPOT 2,-1",

		"a 0": "START_AUDIO_RECORD",
		"a 1": "STOP_AUDIO_RECORD",
		"a 8": "TOGGLE_AUDIO_RECORD",
		"a 4": "START_AUDIO_PLAY",
		"a 5": "STOP_AUDIO_PLAY",
		"a 12": "TOGGLE_AUDIO_PLAY",

		"m 0": "START_MIDI_RECORD",
		"m 1": "STOP_MIDI_RECORD",
		"m 8": "TOGGLE_MIDI_RECORD",
		"m 4": "START_MIDI_PLAY",
		"m 5": "STOP_MIDI_PLAY",
		"m 12": "TOGGLE_MIDI_PLAY",

		"down 0": "ARROW_DOWN",
		"up 0": "ARROW_UP",
		"right 0": "ARROW_RIGHT",
		"left 0": "ARROW_LEFT",

		"1": "PROGRAM_CHANGE 1",
		"2": "PROGRAM_CHANGE 2",
		"3": "PROGRAM_CHANGE 3",
		"4": "PROGRAM_CHANGE 4",
		"5": "PROGRAM_CHANGE 5",
		"6": "PROGRAM_CHANGE 6",
		"7": "PROGRAM_CHANGE 7",
		"8": "PROGRAM_CHANGE 8",
		"9": "PROGRAM_CHANGE 9",
		"0": "PROGRAM_CHANGE 0"
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


	def get_key_action(self, keysym, modifier):
		"""
		Get the name of the function bound to the key combination passed
		
		Parameters
		----------
		keysym : str
			Keyboard symbol to lookup
		modifier : int
			Keyboard modifier to lookup [0: none, 1: shift, 2: capslock, 4: ctrl, 8: alt]

		Returns
		-------
		str
			Name of the function mapped to the key binding
			<None> if no match found		
		"""
	
		logging.debug("Get keybinding function name for keysym: {}, modifier: {}".format(keysym, modifier))
		try:
			return self.map["{} {}".format(keysym, modifier)]
		except:
			try:
				return self.map[keysym]
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
			map[keysym] = cuia
		else:
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
