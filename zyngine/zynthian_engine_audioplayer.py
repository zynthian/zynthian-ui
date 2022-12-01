# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_audioplayer)
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
from glob import glob
from . import zynthian_engine
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

	def __init__(self, zyngui=None, jackname=None):
		super().__init__(zyngui)
		self.name = "AudioPlayer"
		self.nickname = "AP"
		self.type = "MIDI Synth"
		self.options['replace'] = False
		
		if jackname:
			self.jackname = jackname
		else:
			self.jackname = self.get_next_jackname("audioplayer")

		self.file_exts = []
		self.custom_gui_fpath = "/zynthian/zynthian-ui/zyngui/zynthian_widget_audioplayer.py"

		self.start()

		# MIDI Controllers
		self._ctrls=[
			['gain', None, 1.0, 2.0],
			['record', None, 'stopped', ['stopped', 'recording']],
			['loop', None, 'one-shot', ['one-shot', 'looping']],
			['transport', None, 'stopped', ['stopped', 'playing']],
			['position', None, 0.0, 0.0],
			['left track', None, 0, [['mixdown'], [0]]],
			['right track', None, 0, [['mixdown'], [0]]],
			['loop start', None, 0.0, 0.0],
			['loop end', None, 0.0, 0.0]
		]		

		# Controller Screens
		self._ctrl_screens = [
				['main', ['record'], None, None],
				['config', [None, 'gain']]
		]

		self.monitors_dict = []
		for chan in range(17):
			self.monitors_dict.append(OrderedDict())
			self.monitors_dict[chan]["state"] = 0
			self.monitors_dict[chan]["pos"] = 0
			self.monitors_dict[chan]["duration"] = 0
			self.monitors_dict[chan]["samplerate"] = 0
			self.monitors_dict[chan]["filename"] = ""
			self.monitors_dict[chan]["loop start"] = 0
			self.monitors_dict[chan]["loop end"] = 0

		self.reset()


	# ---------------------------------------------------------------------------
	# Subproccess Management & IPC
	# ---------------------------------------------------------------------------

	def start(self):
		self.player = zynaudioplayer.zynaudioplayer(self.jackname)
		self.jackname = self.player.get_jack_client_name()
		self.player.set_control_cb(self.control_cb)
		self.file_exts = self.get_file_exts()


	def stop(self):
		try:
			self.player.stop()
			self.player = None
		except Exception as e:
			logging.error("Failed to close audio player: %s", e)

	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------

	def add_layer(self, layer):
		handle = layer.midi_chan if layer.midi_chan < 16 else 16
		if self.player.add_player(handle):
			self.layers.append(layer)
			layer.jackname = self.jackname
			layer.jackname = "{}:out_{:02d}(a|b)".format(self.jackname, handle + 1)
		


	def del_layer(self, layer):
		self.player.remove_player(layer.midi_chan if layer.midi_chan < 16 else 16)
		super().del_layer(layer)


	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------


	# ---------------------------------------------------------------------------
	# Bank Management
	# ---------------------------------------------------------------------------

	def get_bank_list(self, layer=None):
		banks = [[self.my_data_dir + "/capture", None, "Internal", None]]
		try:
			walk = next(os.walk(self.my_data_dir + "/capture"))
			walk[1].sort()
			for dir in walk[1]:
				for ext in self.file_exts:
					if glob(walk[0] + "/" + dir + "/*." + ext):
						banks.append([walk[0] + "/" + dir, None, "  " + dir, None])
						break
			if os.path.ismount(self.ex_data_dir):
				for ext in self.file_exts:
					if glob(self.ex_data_dir + "/*." + ext) or glob(self.ex_data_dir + "/*/*." + ext):
						banks.append([self.ex_data_dir, None, "USB", None])
						walk = next(os.walk(self.ex_data_dir))
						walk[1].sort()
						for dir in walk[1]:
							for ext in self.file_exts:
								if glob(walk[0] + "/" + dir + "/*." + ext):
									banks.append([walk[0] + "/" + dir, None, "  " + dir, None])
									break
						break
		except:
			pass
		return banks


	# ---------------------------------------------------------------------------
	# Preset Management
	# ---------------------------------------------------------------------------

	def get_file_exts(self):
		file_exts = self.player.get_supported_codecs()
		logging.info("Supported Codecs: {}".format(file_exts))
		exts_upper = []
		for ext in file_exts:
			exts_upper.append(ext.upper())
		file_exts += exts_upper
		return file_exts


	def get_preset_list(self, bank):
		presets = []
		for ext in self.file_exts:
			presets += self.get_filelist(bank[0], ext)
		for preset in presets:
			name = preset[4]
			duration = self.player.get_file_duration(preset[0])
			preset[2] = "{} ({:02d}:{:02d})".format(name, int(duration/60), round(duration)%60)
		return presets


	def set_preset(self, layer, preset, preload=False):
		handle = layer.midi_chan if layer.midi_chan < 16 else 16
		if self.player.get_filename(handle) == preset[0] and self.player.get_file_duration(preset[0]) == self.player.get_duration(handle):
			return

		good_file = self.player.load(handle, preset[0])
		dur = self.player.get_duration(handle, )
		self.player.set_position(handle, 0)
		if self.player.is_loop(handle):
			loop = 'looping'
		else:
			loop = 'one-shot'
		if self.player.get_playback_state(handle):
			transport = 'playing'
		else:
			transport = 'stopped'
		if self.zyngui.audio_recorder.get_status():
			record = 'recording'
		else:
			record = 'stopped'
		gain = self.player.get_gain(handle)
		default_a = 0
		default_b = 0
		track_labels = ['mixdown']
		track_values = [-1]
		if dur:
			channels = self.player.get_channels(handle)
			if channels > 2:
				default_a = -1
				default_b = -1
			elif channels > 1:
				default_b = 1
			for track in range(channels):
				track_labels.append('{}'.format(track + 1))
				track_values.append(track)
			self._ctrl_screens = [
				['main',['record','loop','transport','position']],
				['config',['left track','gain','right track']]
			]
		else:
			self._ctrl_screens = [
				['main', ['record'], None, None],
				['config', [None, 'gain']]
		]
		self._ctrls=[
			['gain',None,gain,2.0],
			['record',None,record,['stopped','recording']],
			['loop',None,loop,['one-shot','looping']],
			['transport',None,transport,['stopped','playing']],
			['position',None,0.0,dur],
			['left track',None,default_a,[track_labels,track_values]],
			['right track',None,default_b,[track_labels,track_values]],
			['loop start',None,0.0,dur],
			['loop end',None,dur,dur]
		]
		layer.refresh_controllers()
		self.player.set_track_a(handle, default_a)
		self.player.set_track_b(handle, default_b)
		self.monitors_dict[handle]['filename'] = self.player.get_filename(handle)
		self.monitors_dict[handle]['duration'] = self.player.get_duration(handle)
		self.monitors_dict[handle]['samplerate'] = self.player.get_samplerate(handle)


	def delete_preset(self, bank, preset):
		try:
			os.remove(preset[0])
			os.remove("{}.png".format(preset[0]))
		except Exception as e:
			logging.debug(e)


	def rename_preset(self, bank, preset, new_preset_name):
		src_ext = None
		dest_ext = None
		for ext in self.file_exts:
			if preset[0].endswith(ext):
				src_ext = ext
			if new_preset_name.endswith(ext):
				dest_ext = ext
			if src_ext and dest_ext:
				break
		if src_ext != dest_ext:
			new_preset_name += "." + src_ext
		try:
			os.rename(preset[0], "{}/{}".format(bank[0], new_preset_name))
		except Exception as e:
			logging.debug(e)

		
	def is_preset_user(self, preset):
		return True

	#----------------------------------------------------------------------------
	# Controllers Management
	#----------------------------------------------------------------------------

	def control_cb(self, handle, id, value):
		if handle == 16:
			if id == 1 and value == 0:
				self.zyngui.stop_audio_player()
			return
		try:
			for layer in self.layers:
				if layer.midi_chan == handle:
					ctrl_dict = layer.controllers_dict
					if id == 1:
						ctrl_dict['transport'].set_value(int(value) * 64, False)
						if value:
							layer.status = "\uf04b"
						else:
							layer.status = ""
					elif id == 2:
						ctrl_dict['position'].set_value(value, False)
						self.monitors_dict[handle]['pos'] = value
					elif id == 3:
						ctrl_dict['gain'].set_value(value, False)
					elif id == 4:
						ctrl_dict['loop'].set_value(int(value) * 64, False)
					elif id == 5:
						ctrl_dict['left track'].set_value(int(value), False)
					elif id == 6:
						ctrl_dict['right track'].set_value(int(value), False)
					elif id == 11:
						ctrl_dict['loop start'].set_value(value, False)
						self.monitors_dict[handle]['loop start'] = value
					elif id == 12:
						ctrl_dict['loop end'].set_value(value, False)
						self.monitors_dict[handle]['loop end'] = value
					return
		except Exception as e:
			return


	def send_controller_value(self, zctrl):
		handle = zctrl.midi_chan if zctrl.midi_chan < 16 else 16
		if zctrl.symbol == "position":
			self.player.set_position(handle, zctrl.value)
		elif zctrl.symbol == "gain":
			self.player.set_gain(handle, zctrl.value)
		elif zctrl.symbol == "loop":
			self.player.enable_loop(handle, zctrl.value)
		elif zctrl.symbol == "transport":
			if zctrl.value > 63:
				self.player.start_playback(handle)
			else:
				self.player.stop_playback(handle)
		elif zctrl.symbol == "left track":
			self.player.set_track_a(handle, zctrl.value)
		elif zctrl.symbol == "right track":
			self.player.set_track_b(handle, zctrl.value)
		elif zctrl.symbol == "record":
			if zctrl.value:
				self.zyngui.audio_recorder.start_recording()
			else:
				self.zyngui.audio_recorder.stop_recording()
		elif zctrl.symbol == "loop start":
			self.player.set_loop_start(handle, zctrl.value)
		elif zctrl.symbol == "loop end":
			self.player.set_loop_end(handle, zctrl.value)


	def get_monitors_dict(self, handle):
		return self.monitors_dict[handle]


	# ---------------------------------------------------------------------------
	# Specific functions
	# ---------------------------------------------------------------------------


	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

#******************************************************************************
