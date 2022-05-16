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

		self.custom_gui_fpath = "/zynthian/zynthian-ui/zyngui/zynthian_widget_audioplayer.py"
		self.start()

		# MIDI Controllers
		self._ctrls=[
			['gain',None,1.0,2.0],
			['loop',None,'one-shot',['one-shot','looping']],
			['play',None,'stopped',['stopped','playing']],
			['position',None,0.0,1.0],
			['quality',None,'fastest',[['best','medium','fastest','zero order','linear'],[0,1,2,3,4]]],
			['left track',None,0,[['mixdown','1','2'],[-1,0,1]]],
			['right track',None,0,[['mixdown','2','2'],[-1,0,1]]]
		]

		# Controller Screens
		self._ctrl_screens=[
			['main',['gain','loop','play','position']],
			['config',['left track','quality','right track']]
		]

		self.reset()


	# ---------------------------------------------------------------------------
	# Subproccess Management & IPC
	# ---------------------------------------------------------------------------

	def start(self):
		self.player = zynaudioplayer.zynaudioplayer()
		self.jackname = self.player.get_jack_client_name()


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
		dur = self.player.get_duration()
		self.player.set_position(0)
		if self.player.is_loop():
			loop = 'looping'
		else:
			loop = 'one-shot'
		if self.player.get_playback_state():
			transport = 'playing'
		else:
			transport = 'stopped'
		gain = self.player.get_gain()
		quals = ['best','medium','fastest','zero order','linear']
		qual = quals[self.player.get_src_quality()]
		#TODO: Set gain control as logarithmic
		#TODO: Player jumps to postition when preset window cancelled
		if dur:
			track_labels = ['mixdown']
			track_values = [-1]
			channels = self.player.get_channels()
			if channels > 1:
				default_b = 1
			else:
				default_b = 0
			for track in range(channels):
				track_labels.append('{}'.format(track + 1))
				track_values.append(track)
			self._ctrls=[
				['gain',None,gain,2.0],
				['loop',None,loop,['one-shot','looping']],
				['play',None,transport,['stopped','playing']],
				['position',None,0.0,dur],
				['quality',None,qual,[quals,[0,1,2,3,4]]],
				['left track',None,0,[track_labels,track_values]],
				['right track',None,default_b,[track_labels,track_values]],
				['buffer size',None,48000,[48000,96000,144000,192000,240000,288000,336000,384000,432000]],
				['buffer count',None,5,10],
				['debug',None,0,1]
			]
			self._ctrl_screens=[
				['main',['gain','loop','play','position']],
				['config',['left track','quality','right track','debug']]
			]
		else:
			self._ctrls=[
				['gain',None,gain,2.0],
				['quality',None,qual,[quals,[0,1,2,3,4]]],
			]
			self._ctrl_screens=[
				['main',['gain']],
				['config',['quality']]
		]
		layer.refresh_controllers()


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

	def send_controller_value(self, zctrl):
		if zctrl.symbol == "position":
			self.player.set_position(zctrl.value)
		elif zctrl.symbol == "gain":
			self.player.set_gain(zctrl.value)
		elif zctrl.symbol == "loop":
			self.player.enable_loop(zctrl.value)
		elif zctrl.symbol == "play":
			if zctrl.value:
				self.player.start_playback()
			else:
				self.player.stop_playback()
		elif zctrl.symbol == "quality":
			self.player.set_quality(zctrl.value)
		elif zctrl.symbol == "left track":
			self.player.set_track_a(zctrl.value)
		elif zctrl.symbol == "right track":
			self.player.set_track_b(zctrl.value)
		elif zctrl.symbol == "buffer size" and zctrl.value > 32000:
			self.player.set_buffer_size(zctrl.value)
		elif zctrl.symbol == "buffer count" and zctrl.value > 0:
			self.player.set_buffer_count(zctrl.value)
		elif zctrl.symbol == 'debug':
			self.player.enable_debug(zctrl.value == 1)


	def get_monitors_dict(self):
		#TODO: Optimise - maybe register for notification events
		self.monitors_dict = OrderedDict()
		try:
			self.monitors_dict["state"] = self.player.get_playback_state()
			self.monitors_dict["pos"] = self.player.get_position()
			self.monitors_dict["duration"] = self.player.get_duration()
			self.monitors_dict["samplerate"] = self.player.get_samplerate()
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
