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
		self.file_exts = ["wav","WAV","ogg","OGG","flac","FLAC"]

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
		self._ctrls=[]

		# Controller Screens
		self._ctrl_screens =[]

		self.monitors_dict = OrderedDict()
		self.monitors_dict["state"] = self.player.get_playback_state()
		self.monitors_dict["pos"] = self.player.get_position()
		self.monitors_dict["duration"] = self.player.get_duration()
		self.monitors_dict["samplerate"] = self.player.get_samplerate()
		self.monitors_dict["filename"] = self.player.get_filename()
		self.monitors_dict["loop start"] = self.player.get_loop_start()
		self.monitors_dict["loop end"] = self.player.get_loop_end()

		self.reset()


	# ---------------------------------------------------------------------------
	# Subproccess Management & IPC
	# ---------------------------------------------------------------------------

	def start(self):
		self.player = zynaudioplayer.zynaudioplayer()
		self.jackname = self.player.get_jack_client_name()
		self.player.set_control_cb(self.control_cb)


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
			walk = next(os.walk(self.my_data_dir + "/capture"))
			walk[1].sort()
			for dir in walk[1]:
				for ext in self.file_exts:
					if glob(walk[0] + "/" + dir + "/*." + ext):
						banks.append([walk[0] + "/" + dir, None, "  " + dir, None])
						break
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
		if self.zyngui.audio_recorder.get_status():
			record = 'recording'
		else:
			record = 'stopped'
		gain = self.player.get_gain()
		default_b = 0
		if dur:
			track_labels = ['mixdown']
			track_values = [-1]
			channels = self.player.get_channels()
			if channels > 1:
				default_b = 1
			for track in range(channels):
				track_labels.append('{}'.format(track + 1))
				track_values.append(track)
			self._ctrls=[
				['gain',None,gain,2.0],
				['record',None,record,['stopped','recording']],
				['loop',None,loop,['one-shot','looping']],
				['transport',None,transport,['stopped','playing']],
				['position',None,0.0,dur],
				['left track',None,0,[track_labels,track_values]],
				['right track',None,default_b,[track_labels,track_values]],
				['loop start',None,0.0,dur],
				['loop end',None,dur,dur]
			]
			self._ctrl_screens = [
				['main',['record','loop','transport','position']],
				['config',['left track','gain','right track']]
			]
		else:
			self._ctrls=[
				['gain',None,gain,2.0],
				['record',None,record,['stopped','recording']]
			]
			self._ctrl_screens = [
				['main',['record'],None,None],
				['config',[None,'gain']]
		]
		layer.refresh_controllers()
		self.player.set_track_a(0)
		self.player.set_track_b(default_b)
		self.monitors_dict['filename'] = self.player.get_filename()
		self.monitors_dict['duration'] = self.player.get_duration()
		self.monitors_dict['samplerate'] = self.player.get_samplerate()


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

	def control_cb(self, id, value):
		try:
			for layer in self.layers:
				ctrl_dict = layer.controllers_dict
				if id == 1:
					ctrl_dict['transport'].set_value(int(value) * 64, False)
					if value:
						self.layers[0].status = "\uf04b"
					else:
						self.layers[0].status = ""
				elif id == 2:
					ctrl_dict['position'].set_value(value, False)
					self.monitors_dict['pos'] = value
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
					self.monitors_dict['loop start'] = value
				elif id == 12:
					ctrl_dict['loop end'].set_value(value, False)
					self.monitors_dict['loop end'] = value
		except Exception as e:
			return


	def send_controller_value(self, zctrl):
		if zctrl.symbol == "position":
			self.player.set_position(zctrl.value)
		elif zctrl.symbol == "gain":
			self.player.set_gain(zctrl.value)
		elif zctrl.symbol == "loop":
			self.player.enable_loop(zctrl.value)
		elif zctrl.symbol == "transport":
			if zctrl.value > 63:
				self.player.start_playback()
			else:
				self.player.stop_playback()
		elif zctrl.symbol == "left track":
			self.player.set_track_a(zctrl.value)
		elif zctrl.symbol == "right track":
			self.player.set_track_b(zctrl.value)
		elif zctrl.symbol == "record":
			if zctrl.value:
				self.zyngui.audio_recorder.start_recording()
			else:
				self.zyngui.audio_recorder.stop_recording()
		elif zctrl.symbol == "loop start":
			self.player.set_loop_start(zctrl.value)
		elif zctrl.symbol == "loop end":
			self.player.set_loop_end(zctrl.value)


	def get_monitors_dict(self):
		return self.monitors_dict


	# ---------------------------------------------------------------------------
	# Specific functions
	# ---------------------------------------------------------------------------


	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

#******************************************************************************
