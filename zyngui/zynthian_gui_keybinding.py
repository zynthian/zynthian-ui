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

import sys
import logging

# Zynthian specific modules
from . import zynthian_gui_config

#------------------------------------------------------------------------------
# Configure logging
#------------------------------------------------------------------------------

# Set root logging level
logging.basicConfig(stream=sys.stderr, level=zynthian_gui_config.log_level)

#------------------------------------------------------------------------------
# Zynthian Keyboard Binding Class
#------------------------------------------------------------------------------

class zynthian_gui_keybinding:

	__instance = None
	
	@staticmethod
	def getInstance():
		if zynthian_gui_keybinding.__instance == None:
			zynthian_gui_keybinding()
		return zynthian_gui_keybinding.__instance


	def __init__(self):
		if zynthian_gui_keybinding.__instance == None:
			zynthian_gui_keybinding.__instance = self
		else:
			raise Exception("Use getInstance() to get the singleton object.")
		self.map = {
				"ALL_SOUNDS_OFF":{"modifier":1, "keysym":"space"},
				"REBOOT":{"modifier":1, "keysym":"Insert"},
				"ALL_OFF":{"modifier":4, "keysym":"space"},
				"POWER_OFF":{"modifier":4, "keysym":"Insert"},
				"RELOAD_MIDI_CONFIG":{"modifier":4, "keysym":"m"},
				"SWITCH_SELECT_SHORT":{"modifier":0, "keysym":"Return,Right"},
				"SWITCH_SELECT_BOLD":{"modifier":1, "keysym":"Return,Right"},
				"SWITCH_SELECT_LONG":{"modifier":4, "keysym":"Return,Right"},
				"SWITCH_BACK_SHORT":{"modifier":0, "keysym":"BackSpace,Escape,Left"},
				"SWITCH_BACK_BOLD":{"modifier":1, "keysym":"BackSpace,Escape,Left"},
				"SWITCH_BACK_LONG":{"modifier":4, "keysym":"BackSpace,Escape,Left"},
				"SWITCH_LAYER_SHORT":{"modifier":0, "keysym":"l,L"},
				"SWITCH_LAYER_BOLD":{"modifier":1, "keysym":"l,L"},
				"SWITCH_LAYER_LONG":{"modifier":4, "keysym":"l,L"},
				"SWITCH_SNAPSHOT_SHORT":{"modifier":0, "keysym":"s,S"},
				"SWITCH_SNAPSHOT_BOLD":{"modifier":1, "keysym":"s,S"},
				"SWITCH_SNAPSHOT_LONG":{"modifier":4, "keysym":"s,S"},
				"SELECT_UP":{"modifier":0, "keysym":"Up"},
				"SELECT_DOWN":{"modifier":0, "keysym":"Down"},
				"START_AUDIO_RECORD":{"modifier":0, "keysym":"r"},
				"STOP_AUDIO_RECORD":{"modifier":1, "keysym":"R"},
				"START_MIDI_RECORD":{"modifier":0, "keysym":"m"},
				"STOP_MIDI_RECORD":{"modifier":1, "keysym":"M"},
				"ALL_NOTES_OFF":{"modifier":0, "keysym":"space"},
				"RESTART_UI":{"modifier":0, "keysym":"Insert"}
			}

	
	def getFunctionName(self, keysym, modifier):
		logging.info("Get keybinding function name for keysym: %s, modifier: %d", keysym, modifier)
		try:
			for action,map in self.map.items():
				if map["keysym"].count(keysym) and modifier == map["modifier"]:
					return action
		except:
			logging.warning("Failed to parse key binding")


	def load(self, config):
		config_dir = os.environ.get('ZYNTHIAN_CONFIG_DIR',"/zynthian/config")
		config_fpath = config_dir + "/keybinding/" + config + ".yml"
		try:
			with open(config_fpath,"r") as fh:
				yml = fh.read()
				logging.info("Loading keyboard binding config file %s => \n%s" % (config_fpath,yml))
				self.map = yaml.load(yml, Loader=yaml.SafeLoader)
				return True
		except Exception as e:
			logging.error("Can't load keyboard binding config file '%s': %s - using default binding" % (config_fpath,e))
			# Default map of key binding defaults. Modifier: 0=none, 1=shift, 4=ctrl.
			return False


	@staticmethod
	def save(self, config):
		config_dir = os.environ.get('ZYNTHIAN_CONFIG_DIR',"/zynthian/config")
		config_fpath = config_dir + "/keybinding/" + config + ".yml"
		try:
			with open(config_fpath,"w") as fh:
				yaml.dump(self.map, fh)
				logging.info("Saving keyboard binding config file %s => \n%s" % (config_fpath,yml))
				return True
		except Exception as e:
			logging.error("Can't save keyboard binding config file '%s': %s" % (config_fpath,e))
			return False
#------------------------------------------------------------------------------
