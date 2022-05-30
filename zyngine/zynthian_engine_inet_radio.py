# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_inetradio)
#
# zynthian_engine implementation for internet radio streamer
#
# Copyright (C) 2022 Brian Walton <riban@zynthian.org>
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
from collections import OrderedDict
import logging
import subprocess
import json
from time import sleep
from . import zynthian_engine
from . import zynthian_controller

#------------------------------------------------------------------------------
# Internet Radio Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_inet_radio(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Config variables
	# ---------------------------------------------------------------------------

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__(zyngui)
		self.name = "InternetRadio"
		self.nickname = "IR"
		self.jackname = "inetradio"
		self.type = "MIDI Synth" # TODO: Should we override this? With what value?

		self.options['clone'] = False
		self.options['note_range'] = False
		self.options['audio_route'] = True
		self.options['midi_chan'] = True
		self.options['replace'] = True
		self.options['drop_pc'] = True
		self.options['layer_audio_out'] = True

		self.cmd = "mplayer -nogui -nolirc -nojoystick -quiet -ao jack:noconnect:name={}".format(self.jackname)
		self.command_prompt = "Starting playback..."
		self.proc_timeout = 5
		
		# MIDI Controllers
		self._ctrls=[
			['volume',None,'up/down',[['down','up/down','up'],[-1,0,1]]],
			['stream',None,'streaming',['stopped','streaming']]
		]

		# Controller Screens
		self._ctrl_screens=[
			['main',['volume','stream']]
		]

		self.reset()


	# ---------------------------------------------------------------------------
	# Subproccess Management & IPC
	# ---------------------------------------------------------------------------

	def start(self):
		res = super().start()
		if res == None:
			self.stop()
		else:
			self.zyngui.zynautoconnect(True)


	def stop(self):
		if self.proc:
			self.proc.send('q')
			sleep(1)
		super().stop()

	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------


	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------


	# ---------------------------------------------------------------------------
	# Bank Management
	# ---------------------------------------------------------------------------

	def get_bank_list(self, layer=None):
		with open(self.my_data_dir + "/presets/inet_radio/presets.json", "r") as f:
			self.presets = json.load(f)
		self.banks = []
		for bank in self.presets:
			self.banks.append([bank, None, bank, None])
		return self.banks

	# ---------------------------------------------------------------------------
	# Preset Management
	# ---------------------------------------------------------------------------

	def get_preset_list(self, bank):
		presets = []
		for preset in self.presets[bank[0]]:
			presets.append(preset)
		return presets


	def set_preset(self, layer, preset, preload=False):		
		uri = preset[0]
		demux = preset[3]
		command = self.cmd
		if uri.endswith("m3u") or uri.endswith("pls"):
			command += " -playlist"
		if demux and demux != 'auto':
			command += " -demuxer {}".format(demux)
		command += " {}".format(uri)
		if self.proc and command == self.command:
			return
		self.stop()
		self.command = command
		self.start()


	#----------------------------------------------------------------------------
	# Controllers Management
	#----------------------------------------------------------------------------

	def get_controllers_dict(self, layer):
		dict = super().get_controllers_dict(layer)
		return dict


	def send_controller_value(self, zctrl):
		if zctrl.symbol == "volume":
			if self.proc:
				try:
					if zctrl.value == -1:
						self.proc.send('9')
					elif zctrl.value == 1:
						self.proc.send('0')
				except Exception as e:
					logging.warning(e)
			zctrl.set_value(0)
		elif zctrl.symbol == "stream":
			if zctrl.value == 0:
				self.stop()
			else:
				self.start()

	# ---------------------------------------------------------------------------
	# Specific functions
	# ---------------------------------------------------------------------------


	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

#******************************************************************************
