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
		#TODO: Allow multiple instances of audioplayer
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
			['play',68,'stopped',['stopped','playing']],
			['position',1,0]
		]

		# Controller Screens
		self._ctrl_screens=[
			['main',['volume','loop','play','position']]
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


	def delete_preset(self, bank, preset):
		try:
			os.remove(preset[0])
		except Exception as e:
			logging.error(e)


	def rename_preset(self, bank, preset, new_preset_name):
		src_ext = None
		dest_ext = None
		for ext in ('.wav','.ogg','.flac'):
			if preset[0].endswith(ext):
				src_ext = ext
			if new_preset_name.endswith(ext):
				dest_ext = ext
			if src_ext and dest_ext:
				break
		if src_ext != dest_ext:
			new_preset_name += src_ext
		try:
			os.rename(preset[0], "{}/{}".format(bank[0], new_preset_name))
		except Exception as e:
			logging.error(e)

		

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
