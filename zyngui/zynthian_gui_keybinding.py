#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian Keyboard Binding Class
# 
# Copyright (C) 2019 Brian Walton <brian@riban.co.uk>
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

# Zynthian specific modules
from . import zynthian_gui_config

#------------------------------------------------------------------------------
# Configure logging
#------------------------------------------------------------------------------

# Set root logging level
logging.basicConfig(stream=stderr, level=zynthian_gui_config.log_level)

#------------------------------------------------------------------------------
# Zynthian Keyboard Binding Class
#------------------------------------------------------------------------------

class zynthian_gui_keybinding:
	"""
	Provides interface to key binding
	
	Note: This class is a singleton and should not be instantiated directly (which will raise an exception).
	Use getInstance() to get the instance of the singleton and access functions and methods from that instance.
	"""

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
		self.resetConfig()
	
	def getFunctionName(self, keysym, modifier):
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
	
		logging.info("Get keybinding function name for keysym: %s, modifier: %d", keysym, modifier)
		try:
			keysym = keysym.lower()
			for action,map in self.config['map'].items():
				if map["keysym"].count(keysym) and modifier == map["modifier"]:
					return action
		except:
			logging.warning("Failed to parse key binding")


	def load(self, config="keybinding"):
		"""
		Load key binding map from file
		
		Parameters
		----------
		config : str,optional
			Name of configuration to load - the file <config>.yaml will be loaded from the Zynthian config directory
			Default: 'keybinding'
		
		Returns
		-------
		bool
			True on success		
		"""

		logging.info("Loading key binding from %s.yaml", config)
		config_dir = environ.get('ZYNTHIAN_CONFIG_DIR',"/zynthian/config")
		config_fpath = config_dir + "/" + config + ".yaml"
		try:
			with open(config_fpath,"r") as fh:
				yml = fh.read()
				logging.info("Loading keyboard binding config file %s => \n%s" % (config_fpath,yml))
				self.config = yaml.load(yml, Loader=yaml.SafeLoader)
				for action,map in self.config['map'].items():
					map["keysym"] = map["keysym"][0].lower()
				return True
		except Exception as e:
			logging.warning("Can't load keyboard binding config file '%s': %s - using default binding" % (config_fpath,e))
			# Default map of key binding defaults. Modifier: 0=none, 1=shift, 4=ctrl.
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
		config_dir = environ.get('ZYNTHIAN_CONFIG_DIR',"/zynthian/config")
		config_fpath = config_dir + "/" + config + ".yaml"
		try:
			with open(config_fpath,"w") as fh:
				yaml.dump(self.config, fh)
				logging.info("Saving keyboard binding config file %s" % (config_fpath))
				return True
		except Exception as e:
			logging.warning("Can't save keyboard binding config file '%s': %s" % (config_fpath,e))
			return False
			
		
	def resetModifiers(self):
		"""
		Clears all modifier settings (use before setting modifiers from webconf)
		"""
		
		logging.info("Clearing key binding modifiers")
		for action,map in self.config['map'].items():
			map['modifier'] = 0


	def resetConfig(self):
		"""
		Reset keyboard binding to default values
		"""
		
		self.config = {
			"enabled": True,
			"map": {
				"ALL_SOUNDS_OFF":{"modifier":1, "keysym":"space"},
				"REBOOT":{"modifier":1, "keysym":"insert"},
				"ALL_OFF":{"modifier":4, "keysym":"space"},
				"POWER_OFF":{"modifier":4, "keysym":"insert"},
				"RELOAD_MIDI_CONFIG":{"modifier":4, "keysym":"m"},
				"SWITCH_SELECT_SHORT":{"modifier":0, "keysym":"return,right"},
				"SWITCH_SELECT_BOLD":{"modifier":1, "keysym":"return,right"},
				"SWITCH_SELECT_LONG":{"modifier":4, "keysym":"return,right"},
				"SWITCH_BACK_SHORT":{"modifier":0, "keysym":"backSpace,escape,left"},
				"SWITCH_BACK_BOLD":{"modifier":1, "keysym":"backspace,escape,left"},
				"SWITCH_BACK_LONG":{"modifier":4, "keysym":"backspace,escape,left"},
				"SWITCH_LAYER_SHORT":{"modifier":0, "keysym":"l"},
				"SWITCH_LAYER_BOLD":{"modifier":1, "keysym":"l"},
				"SWITCH_LAYER_LONG":{"modifier":4, "keysym":"l"},
				"SWITCH_SNAPSHOT_SHORT":{"modifier":0, "keysym":"s"},
				"SWITCH_SNAPSHOT_BOLD":{"modifier":1, "keysym":"s"},
				"SWITCH_SNAPSHOT_LONG":{"modifier":4, "keysym":"s"},
				"SELECT_UP":{"modifier":0, "keysym":"up"},
				"SELECT_DOWN":{"modifier":0, "keysym":"down"},
				"START_AUDIO_RECORD":{"modifier":0, "keysym":"r"},
				"STOP_AUDIO_RECORD":{"modifier":1, "keysym":"r"},
				"START_MIDI_RECORD":{"modifier":0, "keysym":"m"},
				"STOP_MIDI_RECORD":{"modifier":1, "keysym":"m"},
				"ALL_NOTES_OFF":{"modifier":0, "keysym":"space"},
				"RESTART_UI":{"modifier":0, "keysym":"insert"}
			}
		}
			
	
	def enable(self, enabled=True):
		"""
		Enable or disable keyboard binding

		Parameters
		----------
		enabled : bool,optional
			True to enable, false to disable - default: True
		"""
		
		self.config["enabled"] = enabled

		
	def isEnabled(self):
		"""
		Is keyboard binding enabled?

		Returns
		-------
		bool True if enabled
		"""

		return self.config["enabled"]
		
#------------------------------------------------------------------------------
