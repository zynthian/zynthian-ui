# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_audio_player)
#
# zynthian_engine implementation for audio player
#
# Copyright (C) 2021 Brian Walton <riban@zynthian.org>
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
import shutil
import logging
import oyaml as yaml
from collections import OrderedDict
from subprocess import check_output
from . import zynthian_engine
from . import zynthian_controller
from zynlibs.zynaudioplayer import *

#------------------------------------------------------------------------------
# Audio Player Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_audioplayer(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Config variables
	# ---------------------------------------------------------------------------

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__(zyngui)
		self.name = "AudioPlayer"
		self.nickname = "AP"
		self.jackname = "audioplayer"

		self.options['clone'] = False
		self.options['note_range'] = False
		self.options['audio_route'] = True
		self.options['midi_chan'] = True
		self.options['replace'] = True
		self.options['drop_pc'] = True
		self.options['layer_audio_out'] = True

		# MIDI Controllers
		self._ctrls=[
			['volume',7,100],
			['loop',69,'one-shot',['one-shot','looping']],
			['play',68,'stopped',['stopped','playing']]
		]

		# Controller Screens
		self._ctrl_screens=[
			['main',['volume','loop','play']]
		]

		self.start()
		self.reset()


	# ---------------------------------------------------------------------------
	# Subproccess Management & IPC
	# ---------------------------------------------------------------------------

	def start(self):
		zynaudioplayer.init()


	def stop(self):
		try:
			zynaudioplayer.destroy()
		except Exception as e:
			logging.error("Failed to close audio player: %s", e)

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
		banks = [[self.my_data_dir + "/capture", None, "Internal", None]]
		try:
			if os.listdir(self.ex_data_dir):
				banks.append([self.ex_data_dir, None, "USB", None])
		except:
			pass
		return banks


	# ---------------------------------------------------------------------------
	# Preset Management
	# ---------------------------------------------------------------------------

	def get_preset_list(self, bank):
		presets = self.get_filelist(bank[0],"wav") + self.get_filelist(bank[0],"ogg") + self.get_filelist(bank[0],"flac")
		for preset in presets:
			name = preset[4]
			duration = zynaudioplayer.get_duration(preset[0])
			preset[2] = "{} ({:02d}:{:02d})".format(name, int(duration/60), round(duration)%60)
		return presets


	def set_preset(self, layer, preset, preload=False):
		if zynaudioplayer.get_filename() == preset[0] and zynaudioplayer.get_duration(preset[0]) == zynaudioplayer.libaudioplayer.getDuration():
			return
		zynaudioplayer.load(preset[0])
		zynaudioplayer.libaudioplayer.setPosition(0)


	#----------------------------------------------------------------------------
	# Controllers Management
	#----------------------------------------------------------------------------


	# ---------------------------------------------------------------------------
	# Specific functions
	# ---------------------------------------------------------------------------


	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

#******************************************************************************
