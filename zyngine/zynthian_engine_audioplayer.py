# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_audio_player)
#
# zynthian_engine implementation for audio player
#
# Copyright (C) 2021-2022 Brian Walton <riban@zynthian.org>
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
from . import zynthian_engine
from . import zynthian_controller
from zynlibs.zynaudioplayer import zynaudioplayer

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
		self.type = "MIDI Synth" # TODO: Should we override this? With what value?

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
			['position',1,0],
			['quality',2,'best',['best','medium','fastest','zero order','linear']],
			['track',3,0]
		]

		# Controller Screens
		self._ctrl_screens=[
			['main',['volume','loop','play','position']],
			['config',['quality','track']]
		]

		self.custom_gui_fpath = "/zynthian/zynthian-ui/zyngui/zynthian_widget_audioplayer.py"
		self.start()
		self.reset()
		self.osc_server_port = 9000


	# ---------------------------------------------------------------------------
	# Subproccess Management & IPC
	# ---------------------------------------------------------------------------

	def start(self):
		self.player = zynaudioplayer.zynaudioplayer()
		self.jackname = self.player.get_jack_client_name()
		#self.jackname = "{}/{:03d}".format(self.player.get_jack_client_name(), self.player.handle)


	def stop(self):
		try:
			self.player.remove_player()
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
			duration = self.player.get_file_duration(preset[0])
			preset[2] = "{} ({:02d}:{:02d})".format(name, int(duration/60), round(duration)%60)
		return presets


	def set_preset(self, layer, preset, preload=False):
		if self.player.get_filename() == preset[0] and self.player.get_file_duration(preset[0]) == self.player.get_duration():
			return
		self.player.load(preset[0])
		self.player.set_position(0)


	def delete_preset(self, bank, preset):
		try:
			os.remove(preset[0])
			os.remove("{}.png".format(preset[0]))
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

	"""
	def get_controllers_dict(self, layer):
		midi_chan=layer.get_midi_chan()
		zctrls=OrderedDict()

		zctrl=zynthian_controller(self, 'gain')
		zctrl.setup_controller(midi_chan, '/player{:03d}/gain'.format(self.player.handle), 1.0, 2.0)
		zctrl=zynthian_controller(self, 'loop')
		zctrl.setup_controller(midi_chan, '/player{:03d}/loop'.format(self.player.handle), 0, 1)
		zctrl=zynthian_controller(self, 'play')
		zctrl.setup_controller(midi_chan, '/player{:03d}/play'.format(self.player.handle), 0, 1)
		zctrl=zynthian_controller(self, 'position')
		zctrl.setup_controller(midi_chan, '/player{:03d}/position'.format(self.player.handle), 0.0, self.player.get_duration())
		zctrl=zynthian_controller(self, 'quality')
		zctrl.setup_controller(midi_chan, '/player{:03d}/quality'.format(self.player.handle), [
			'best',
			'medium',
			'fastest',
			'zero order',
			'linear'], 4)
		zctrl=zynthian_controller(self, 'track')
		zctrl.setup_controller(midi_chan, '/player{:03d}/track'.format(self.player.handle), 0, self.player.get_channels())
		"""


	def get_monitors_dict(self):
		#TODO: Optimise
		self.monitors_dict = OrderedDict()
		try:
			self.monitors_dict["state"] = self.player.get_playback_state()
			self.monitors_dict["pos"] = self.player.get_position()
			self.monitors_dict["duration"] = self.player.get_duration()
			self.monitors_dict["filename"] = self.player.get_filename()
		except Exception as e:
			logging.error(e)

		return self.monitors_dict


	# ---------------------------------------------------------------------------
	# Specific functions
	# ---------------------------------------------------------------------------


	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

#******************************************************************************
