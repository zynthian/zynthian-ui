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
		self._ctrls = [
			['gain', None, 1.0, 2.0],
			['record', None, 'stopped', ['stopped', 'recording']],
			['loop', None, 'one-shot', ['one-shot', 'looping']],
			['transport', None, 'stopped', ['stopped', 'playing']],
			['position', None, 0.0, 0.0],
			['left track', None, 0, [['mixdown'], [0]]],
			['right track', None, 0, [['mixdown'], [0]]],
			['loop start', None, 0.0, 0.0],
			['loop end', None, 0.0, 0.0],
			['crop start', None, 0.0, 0.0],
			['crop end', None, 0.0, 0.0],
			['attack', None, 0.1, 20.0],
			['decay', None, 0.1, 20.0],
			['sustain', None, 0.8, 1.0],
			['release', None, 0.1,20.0],
			['zoom', None, 1, ["x1"],[1]],
			['info', None, 0, ["Length", "Play Time", "Remaining", "Samplerate", "None"]],
			['bend range', None, 2, 24],
		]

		# Controller Screens
		self._ctrl_screens = [
				['main', ['record', 'gain']],
		]

		self.monitors_dict = []
		for chan in range(17):
			self.monitors_dict.append(OrderedDict())
			self.monitors_dict[chan]["state"] = 0
			self.monitors_dict[chan]["pos"] = 0
			self.monitors_dict[chan]["frames"] = 0
			self.monitors_dict[chan]["channels"] = 0
			self.monitors_dict[chan]["samplerate"] = 44100
			self.monitors_dict[chan]["filename"] = ""
			self.monitors_dict[chan]["loop start"] = 0
			self.monitors_dict[chan]["loop end"] = 0
			self.monitors_dict[chan]["crop start"] = 0
			self.monitors_dict[chan]["crop end"] = 0
			self.monitors_dict[chan]["zoom"] = 1
			self.monitors_dict[chan]["info"] = 0

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
		handle = self.player.add_player()
		if handle < 0:
			return
		self.layers.append(layer)
		layer.handle = handle
		layer.jackname = self.jackname
		layer.jackname = "{}:out_{:02d}(a|b)".format(self.jackname, handle + 1)
		self.set_midi_chan(layer)


	def del_layer(self, layer):
		self.player.remove_player(layer.handle)
		super().del_layer(layer)


	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	def set_midi_chan(self, layer):
		self.player.set_midi_chan(layer.handle, layer.midi_chan)


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


	def set_bank(self, layer, bank):
		return True

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
			fparts = os.path.splitext(preset[4])
			duration = self.player.get_file_duration(preset[0])
			preset.append("{} ({:02d}:{:02d})".format(fparts[1], int(duration/60), round(duration)%60))
		return presets


	def set_preset(self, layer, preset, preload=False):
		if self.player.get_filename(layer.handle) == preset[0] and self.player.get_file_duration(preset[0]) == self.player.get_duration(layer.handle):
			return False

		good_file = self.player.load(layer.handle, preset[0])
		dur = self.player.get_duration(layer.handle)
		self.player.set_position(layer.handle, 0)
		if self.player.is_loop(layer.handle):
			loop = 'looping'
		else:
			loop = 'one-shot'
		logging.debug("Loading Audio Track '{}' in player {}".format(preset[0], layer.handle))
		if layer.handle == self.zyngui.audio_player.handle:
			self.player.start_playback(layer.handle)
		if self.player.get_playback_state(layer.handle):
			transport = 'playing'
		else:
			transport = 'stopped'
		if self.zyngui.audio_recorder.get_status():
			record = 'recording'
		else:
			record = 'stopped'
		gain = self.player.get_gain(layer.handle)
		bend_range = self.player.get_pitchbend_range(layer.handle)
		attack = self.player.get_attack(layer.handle)
		decay = self.player.get_decay(layer.handle)
		sustain = self.player.get_sustain(layer.handle)
		release = self.player.get_release(layer.handle)
		default_a = 0
		default_b = 0
		track_labels = ['mixdown']
		track_values = [-1]
		zoom_labels = ['x1']
		zoom_values = [1]
		z = 1
		while z < dur * 250:
			z *= 2
			zoom_labels.append(f"x{z}")
			zoom_values.append(z)
		if dur:
			channels = self.player.get_channels(layer.handle)
			if channels > 2:
				default_a = -1
				default_b = -1
			elif channels > 1:
				default_b = 1
			for track in range(channels):
				track_labels.append('{}'.format(track + 1))
				track_values.append(track)
			self._ctrl_screens = [
				['main', ['record', 'transport', 'position', 'gain']],
				['crop', ['crop start', 'crop end', 'position', 'zoom']],
				['loop', ['loop start', 'loop end', 'loop', 'zoom']],
				['config', ['left track', 'right track', 'bend range', 'damper']],
				['info', ['info', None, None, None]]
			]
			if layer.handle == self.zyngui.audio_player.handle:
				self._ctrl_screens[3][1][2] = None
				self._ctrl_screens[3][1][3] = None
			else:
				self._ctrl_screens.insert(-2, ['envelope', ['attack', 'decay', 'sustain', 'release']])

		else:
			self._ctrl_screens = [
				['main', ['record', 'gain']],
			]

		self._ctrls = [
			['gain', None, gain, 2.0],
			['record', None, record, ['stopped', 'recording']],
			['loop', None, loop, ['one-shot', 'looping']],
			['transport', None, transport, ['stopped', 'playing']],
			['position', None, 0.0, dur],
			['left track', None, default_a, [track_labels, track_values]],
			['right track', None, default_b, [track_labels, track_values]],
			['loop start', None, 0.0, dur],
			['loop end', None, dur, dur],
			['crop start', None, 0.0, dur],
			['crop end', None, dur, dur],
			['zoom', None, 1, [zoom_labels, zoom_values]],
			['info', None, 0, ["Length", "Play Time", "Remaining", "Samplerate", "None"]],
		]
		if layer.handle != self.zyngui.audio_player.handle:
			self._ctrls += [['damper', 64, 'off', ['off', 'on']],
						['bend range', None, bend_range, 24],
						['attack', None, attack, 20.0],
						['decay', None, decay, 20.0],
						['sustain', None, sustain, 1.0],
						['release', None, release, 20.0]]

		layer.refresh_controllers()
		self.player.set_track_a(layer.handle, default_a)
		self.player.set_track_b(layer.handle, default_b)
		self.monitors_dict[layer.handle]['filename'] = self.player.get_filename(layer.handle)
		self.monitors_dict[layer.handle]['frames'] = self.player.get_frames(layer.handle)
		self.monitors_dict[layer.handle]['channels'] = self.player.get_frames(layer.handle)
		self.monitors_dict[layer.handle]['samplerate'] = self.player.get_samplerate(layer.handle)
		self.monitors_dict[layer.handle]['zoom'] = 1
		return True


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

	def get_controllers_dict(self, layer):
		ctrls = super().get_controllers_dict(layer)
		for zctrl in ctrls.values():
			zctrl.handle = layer.handle
		return ctrls


	def control_cb(self, handle, id, value):
		try:
			for layer in self.layers:
				if layer.handle == handle:
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
					elif id == 13:
						ctrl_dict['crop start'].set_value(value, False)
						self.monitors_dict[handle]['crop start'] = value
					elif id == 14:
						ctrl_dict['crop end'].set_value(value, False)
						self.monitors_dict[handle]['crop end'] = value
					elif id == 15:
						ctrl_dict['damper'].set_value(value, False)
					elif id == 16:
						ctrl_dict['attack'].set_value(value, False)
					elif id == 17:
						ctrl_dict['decay'].set_value(value, False)
					elif id == 18:
						ctrl_dict['sustain'].set_value(value, False)
					elif id == 19:
						ctrl_dict['release'].set_value(value, False)
					break
		except Exception as e:
			logging.error(e)


	def send_controller_value(self, zctrl):
		handle = zctrl.handle
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
		elif zctrl.symbol == "crop start":
			self.player.set_crop_start(handle, zctrl.value)
		elif zctrl.symbol == "crop end":
			self.player.set_crop_end(handle, zctrl.value)
		elif zctrl.symbol == "bend range":
			self.player.set_pitchbend_range(handle, zctrl.value)
		elif zctrl.symbol == "damper":
			self.player.set_damper(handle, zctrl.value)
		elif zctrl.symbol == "zoom":
			self.monitors_dict[handle]['zoom'] = zctrl.value
			for layer in self.layers:
				if layer.handle == handle:
					pos_zctrl = layer.controllers_dict['position']
					pos_zctrl.nudge_factor = pos_zctrl.value_max / 400 / zctrl.value
					layer.controllers_dict['loop start'].nudge_factor = pos_zctrl.nudge_factor
					layer.controllers_dict['loop end'].nudge_factor = pos_zctrl.nudge_factor
					layer.controllers_dict['crop start'].nudge_factor = pos_zctrl.nudge_factor
					layer.controllers_dict['crop end'].nudge_factor = pos_zctrl.nudge_factor
					return
		elif zctrl.symbol == "info":
			self.monitors_dict[handle]['info'] = zctrl.value
		elif zctrl.symbol == "attack":
			self.player.set_attack(handle, zctrl.value)
		elif zctrl.symbol == "decay":
			self.player.set_decay(handle, zctrl.value)
		elif zctrl.symbol == "sustain":
			self.player.set_sustain(handle, zctrl.value)
		elif zctrl.symbol == "release":
			self.player.set_release(handle, zctrl.value)


	def get_monitors_dict(self, handle):
		return self.monitors_dict[handle]


	# ---------------------------------------------------------------------------
	# Specific functions
	# ---------------------------------------------------------------------------


	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

#******************************************************************************
