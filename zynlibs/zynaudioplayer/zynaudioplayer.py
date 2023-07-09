#!/usr/bin/python3
# -*- coding: utf-8 -*-
#********************************************************************
# ZYNTHIAN PROJECT: Zynaudioplayer Python Wrapper
#
# A Python wrapper for zynaudioplayer library
#
# Copyright (C) 2021-2022 Brian Walton <brian@riban.co.uk>
# License: LGPL V3
#
#********************************************************************
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
#********************************************************************

import ctypes
from _ctypes import dlclose
from os.path import dirname, realpath

#-------------------------------------------------------------------------------
# Zynthian audio file player Library Wrapper
#
#	Most library functions are accessible directly by calling libzynaudioplayer.functionName(parameters)
#	Following function wrappers provide simple access for complex data types. Access with zynaudioplayer.function_name(parameters)
#
#	Include the following imports to access these two library objects:
# 		from zynlibs.zynaudioplayer import zynaudioplayer
#		from zynlibs.zynaudioplayer.zynaudioplayer import libaudioplayer
#
#-------------------------------------------------------------------------------


class zynaudioplayer():
    
	#	Initiate library
	def __init__(self, jackname = None):
		try:
			# Load or increment ref to lib
			self.libaudioplayer = ctypes.cdll.LoadLibrary(dirname(realpath(__file__))+"/build/libzynaudioplayer.so")
			self.libaudioplayer.get_duration.restype = ctypes.c_float
			self.libaudioplayer.get_position.restype = ctypes.c_float
			self.libaudioplayer.get_loop_start_time.restype = ctypes.c_float
			self.libaudioplayer.get_loop_end_time.restype = ctypes.c_float
			self.libaudioplayer.get_crop_start_time.restype = ctypes.c_float
			self.libaudioplayer.get_crop_end_time.restype = ctypes.c_float
			self.libaudioplayer.get_file_duration.restype = ctypes.c_float
			self.libaudioplayer.get_env_attack.restype = ctypes.c_float
			self.libaudioplayer.get_env_decay.restype = ctypes.c_float
			self.libaudioplayer.get_env_sustain.restype = ctypes.c_float
			self.libaudioplayer.get_env_release.restype = ctypes.c_float
			self.libaudioplayer.get_file_info.restype = ctypes.c_char_p
			self.libaudioplayer.get_filename.restype = ctypes.c_char_p
			self.libaudioplayer.get_supported_codecs.restype = ctypes.c_char_p
			self.libaudioplayer.get_codec.restype = ctypes.c_char_p
			self.libaudioplayer.get_jack_client_name.restype = ctypes.c_char_p
			self.libaudioplayer.get_gain.restype = ctypes.c_float
			self.libaudioplayer.add_player.restype = ctypes.c_void_p
			self.libaudioplayer.set_gain.argtypes = [ctypes.c_void_p, ctypes.c_float]
			self.libaudioplayer.set_position.argtypes = [ctypes.c_void_p, ctypes.c_float]
			self.libaudioplayer.set_loop_start_time.argtypes = [ctypes.c_void_p, ctypes.c_float]
			self.libaudioplayer.set_loop_end_time.argtypes = [ctypes.c_void_p, ctypes.c_float]
			self.libaudioplayer.set_crop_start_time.argtypes = [ctypes.c_void_p, ctypes.c_float]
			self.libaudioplayer.set_crop_end_time.argtypes = [ctypes.c_void_p, ctypes.c_float]
			self.libaudioplayer.set_pos_notify_delta.argtypes = [ctypes.c_void_p, ctypes.c_float]
			self.libaudioplayer.set_env_attack.argtypes = [ctypes.c_void_p, ctypes.c_float]
			self.libaudioplayer.set_env_decay.argtypes = [ctypes.c_void_p, ctypes.c_float]
			self.libaudioplayer.set_env_sustain.argtypes = [ctypes.c_void_p, ctypes.c_float]
			self.libaudioplayer.set_env_release.argtypes = [ctypes.c_void_p, ctypes.c_float]
			self.libaudioplayer.set_env_release.argtypes = [ctypes.c_void_p, ctypes.c_float]
			self.control_cb = None
		except Exception as e:
			self.libaudioplayer=None
			print("Can't initialise zynaudioplayer library: %s" % str(e))


	#	Destoy instance of shared library
	def __del__(self):
		if self.libaudioplayer:
			#self.stop()
			# Decrement ref to lib - when all ref removed shared lib will be unloaded
			dlclose(self.libaudioplayer._handle)


	def stop(self):
		self.libaudioplayer.lib_stop()
		self.set_control_cb(None)


	def is_codec_supported(self, codec):
		return self.libaudioplayer.is_codec_supported(bytes(codec, "utf-8")) == 1


	def get_supported_codecs(self):
		return self.libaudioplayer.get_supported_codecs().decode("utf-8").lower().split(',')


	#	Get jack client name
	def get_jack_client_name(self):
		return self.libaudioplayer.get_jack_client_name().decode("utf-8")


	#	Add a player
	def add_player(self):
		return self.libaudioplayer.add_player()


	#	Remove a player
	def remove_player(self, handle):
		return self.libaudioplayer.remove_player(handle)


	#	Set a player's MIDI channel;
	#	handle: Index of player
	#	midi_chan: MIDI channel (0..15 or other value to disable MIDI)
	def set_midi_chan(self, handle, midi_chan):
		self.libaudioplayer.set_midi_chan(handle, midi_chan)


	#	Get a player's index;
	#	handle: Index of player
	#	Returns: Index
	def get_index(self, handle):
		return self.libaudioplayer.get_index(handle)


	#	Load an audio file
	#	filename: Full path and filename
	#	handle: Index of player
	#	Returns: True on success
	def load(self, handle, filename):
		return self.libaudioplayer.load(handle, bytes(filename, "utf-8"), ctypes.py_object(self), self.value_cb)


	#	Unload the currently loaded audio file
	#	handle: Index of player
	def unload(self, handle):
		self.libaudioplayer.unload(handle)


	def set_control_cb(self, cb):
		self.control_cb = cb


	@ctypes.CFUNCTYPE(None, ctypes.py_object, ctypes.c_void_p, ctypes.c_int, ctypes.c_float)
	def value_cb(self, handle, type, value):
		if self.control_cb:
			self.control_cb(handle, type, value)


	#	Get the full path and name of the currently loaded file
	#	handle: Index of player
	#	Returns: Filename
	def get_filename(self, handle):
		return self.libaudioplayer.get_filename(handle).decode("utf-8")


	#	Get duration of loaded file
	#	handle: Index of player
	#	Returns: Duration in seconds or zero if file cannot be opened or invalid format
	def get_duration(self, handle):
		return self.libaudioplayer.get_duration(handle)


	#	Save an audio file
	#	handle: Index of player
	#	filename: Full path and filename
	#	Returns: True on success
	def save(self, handle, filename):
		return self.libaudioplayer.save(handle, bytes(filename, "utf-8"))


	#	Set playback position
	#	handle: Index of player
	#	time: Position in seconds from start of file
	def set_position(self, handle, time):
		self.libaudioplayer.set_position(handle, time)


	#	Get playback position
	#	handle: Index of player
	#	Returns: Position in seconds from start of file
	def get_position(self, handle):
		return self.libaudioplayer.get_position(handle)


	#	Enable looping of playback
	#	handle: Index of player
	#	enable: True to enable looping
	def enable_loop(self, handle, enable):
		self.libaudioplayer.enable_loop(handle, enable)


	#	Get playback looping state
	#	handle: Index of player
	#	Returns: True looping enabled
	def is_loop(self, handle):
		return (self.libaudioplayer.is_loop(handle) > 0)


	#	Get start of loop in seconds from start of file
	#	handle: Index of player
	#	Returns: Loop start
	def get_loop_start(self, handle):
		return self.libaudioplayer.get_loop_start_time(handle)


	#	Set start of loop in seconds from start of file
	#	handle: Index of player
	#	time: Loop start
	def set_loop_start(self, handle, time):
		self.libaudioplayer.set_loop_start_time(handle, time)


	#	Get end of loop in seconds from end of file
	#	handle: Index of player
	#	Returns: Loop end
	def get_loop_end(self, handle):
		return self.libaudioplayer.get_loop_end_time(handle)


	#	Set end of loop in seconds from end of file
	#	handle: Index of player
	#	time: Loop end
	def set_loop_end(self, handle, time):
		self.libaudioplayer.set_loop_end_time(handle, time)


	#	Get start of audio (crop) in seconds from start of file
	#	handle: Index of player
	#	Returns: Crop start
	def get_crop_start(self, handle):
		return self.libaudioplayer.get_crop_start_time(handle)


	#	Set start of audio (crop) in seconds from start of file
	#	handle: Index of player
	#	time: Crop start
	def set_crop_start(self, handle, time):
		self.libaudioplayer.set_crop_start_time(handle, time)


	#	Get end of audio (crop) in seconds from end of file
	#	handle: Index of player
	#	Returns: Crop end
	def get_crop_end(self, handle):
		return self.libaudioplayer.get_crop_end_time(handle)


	#	Set end of audio (crop) in seconds from end of file
	#	handle: Index of player
	#	time: Crop end
	def set_crop_end(self, handle, time):
		self.libaudioplayer.set_crop_end_time(handle, time)


	#	Start playback
	#	handle: Index of player
	def start_playback(self, handle):
		self.libaudioplayer.start_playback(handle)


 	#	Stop playback
	#	handle: Index of player
	def stop_playback(self, handle):
		self.libaudioplayer.stop_playback(handle)


 	#	Get playback state
	#	handle: Index of player
	def get_playback_state(self, handle):
		return self.libaudioplayer.get_playback_state(handle)


 	#	Get samplerate of loaded file
	#	handle: Index of player
	#	Returns: Samplerate of loaded file
	def get_samplerate(self, handle):
		return self.libaudioplayer.get_samplerate(handle)


	#	Get CODEC of loaded file
	#	handle: Index of player
	#	Returns: Name of CODEC (WAV|FLAC|OGG|MP3)
	def get_codec(self, handle):
		return self.libaudioplayer.get_codec(handle).decode("utf-8")


 	#	Get quantity of channels in loaded file
	#	handle: Index of player
	#	Returns: Quantity of channels in loaded file
	def get_channels(self, handle):
		return self.libaudioplayer.get_channels(handle)


 	#	Get quantity of frames in loaded file
	#	handle: Index of player
	#	Returns: Quantity of frames in loaded file
	def get_frames(self, handle):
		return self.libaudioplayer.get_frames(handle)


 	#	Get format of channels in loaded file
	#	handle: Index of player
	#	Returns: Bitwise OR of major and minor format type and optional endianness value
	#   See sndfile.h for supported formats
	def get_format(self, handle):
		return self.libaudioplayer.get_format(handle)


 	#	Set quality of samplerate converion
	#	handle: Index of player
	#	quality: Samplerate conversion quality [SRC_SINC_BEST_QUALITY | SRC_SINC_MEDIUM_QUALITY | SRC_SINC_FASTEST | SRC_ZERO_ORDER_HOLD | SRC_LINEAR]
	#	Returns: True on success, i.e. the quality parameter is valid
	def set_src_quality(self, handle, quality):
		return (self.libaudioplayer.set_src_quality(handle, quality) == 1)


 	#	Get quality of samplerate converion
	#	handle: Index of player
	#	Returns: Samplerate conversion quality [SRC_SINC_BEST_QUALITY | SRC_SINC_MEDIUM_QUALITY | SRC_SINC_FASTEST | SRC_ZERO_ORDER_HOLD | SRC_LINEAR]
	def get_src_quality(self, handle):
		return self.libaudioplayer.get_src_quality(handle)


 	#	Set playback gain
	#	handle: Index of player
	#	gain: Playback gain factor [0..2]
	def set_gain(self, handle, gain):
		self.libaudioplayer.set_gain(handle, gain)


 	#	Get playback gain
	#	handle: Index of player
	#	Returns: Playback gain factor [0..2]
	#	TODO: error in float means get differs to set, e.g. set(0.2), get()=0.20000000298023224
	def get_gain(self, handle):
		return self.libaudioplayer.get_gain(handle)


	#	Set playback track for left output
	#	handle: Index of player
	#	track: Index of track to playback to left channel, -1 to mix odd tracks
	#	Mono files are played to both outputs
	def set_track_a(self, handle, track):
		self.libaudioplayer.set_track_a(handle, track)


	#	Set playback track for right output
	#	handle: Index of player
	#	track: Index of track to playback to right channel, -1 to mix even tracks
	#	Mono files are played to both outputs
	def set_track_b(self, handle, track):
		self.libaudioplayer.set_track_b(handle, track)


	#	Get playback track for left output
	#	handle: Index of player
	#	Returns: Index of track to playback to left channel, -1 to mix odd to left
	def get_track_a(self, handle):
		return self.libaudioplayer.get_track_a(handle)


	#	Get playback track for right output
	#	handle: Index of player
	#	Returns: Index of track to playback to right channel, -1 to mix even to left
	def get_track_b(self, handle):
		return self.libaudioplayer.get_track_b(handle)


	#	Set pitchbend range
	#	handle: Index of player
	#	range: Pitchbend range in semitones
	def set_pitchbend_range(self, handle, range):
		return self.libaudioplayer.set_pitchbend_range(handle, range)


	#	Get pitchbend range
	#	handle: Index of player
	#	Returns: Pitchbend range in semitones
	def get_pitchbend_range(self, handle):
		return self.libaudioplayer.get_pitchbend_range(handle)


	#	Set envelope attack
	#	handle: Index of player
	#	attack: Attack time in seconds
	def set_attack(self, handle, attack):
		self.libaudioplayer.set_env_attack(handle, attack)


	#	Get envelope attack
	#	handle: Index of player
	#	Returns: Attack time in seconds
	def get_attack(self, handle):
		return self.libaudioplayer.get_env_attack(handle)


	#	Set envelope decay
	#	handle: Index of player
	#	decay: Decay time in seconds
	def set_decay(self, handle, decay):
		self.libaudioplayer.set_env_decay(handle, decay)


	#	Get envelope decay
	#	handle: Index of player
	#	Returns: Decay time in seconds
	def get_decay(self, handle):
		return self.libaudioplayer.get_env_decay(handle)


	#	Set envelope sustain
	#	handle: Index of player
	#	sustain: Sustain time in seconds
	def set_sustain(self, handle, sustain):
		self.libaudioplayer.set_env_sustain(handle, sustain)


	#	Get envelope sustain
	#	handle: Index of player
	#	Returns: Sustain time in seconds
	def get_sustain(self, handle):
		return self.libaudioplayer.get_env_sustain(handle)


	#	Set envelope release
	#	handle: Index of player
	#	release: Release time in seconds
	def set_release(self, handle, release):
		self.libaudioplayer.set_env_release(handle, release)


	#	Get envelope release
	#	handle: Index of player
	#	Returns: Release time in seconds
	def get_release(self, handle):
		return self.libaudioplayer.get_env_release(handle)


	#	Set file read buffer size
	#	handle: Index of player
	#	count: Buffer size in frames
	#	Cannot change size whilst file is open
	def set_buffer_size(self, handle, size):
		self.libaudioplayer.set_buffer_size(handle, size)


	#	Get file read buffer size
	#	handle: Index of player
	#	Returns: Buffers size in frames
	def get_buffer_size(self, handle):
		return self.libaudioplayer.get_buffer_size(handle)


	#	Set quantity of file read buffers
	#	handle: Index of player
	#	count: Quantity of buffers
	def set_buffer_count(self, handle, count):
		self.libaudioplayer.set_buffer_count(handle, count)


	#	Get quantity of file read buffers
	#	handle: Index of player
	#	Returns: Quantity of buffers
	def get_buffer_count(self, handle):
		return self.libaudioplayer.get_buffer_count(handle)


	#	Set difference in postion that will trigger notificaton 
	#	handle: Index of player
	#	time: Time difference in seconds
	def set_pos_notify_delta(self, handle, time):
		self.libaudioplayer.set_pos_notify_delta(handle, time)


 	#	Enable debug output
	#	enable: True to enable debug
	def enable_debug(self, enable=True):
		self.libaudioplayer.enable_debug(enable)


 	#	Get debug state
	#	Returns: True if debug enabled
	def is_debug(self):
		return(self.libaudioplayer.is_debug() == 1);


	#	Get duration of an audio file
	#	filename: Full path and filename
	#	Returns: Duration in seconds or zero if file cannot be opened or invalid format
	def get_file_duration(self, filename):
		return self.libaudioplayer.get_file_duration(bytes(filename, "utf-8"))


	#	Get info from file metadata
	#	filename: Full path and filename
	#	type: Info type [1:Title, 2:Copyright, 3:Software, 4:Artist, 5:Comment, 6:Date, 7:Album, 8:License, 9:Track number, 10:Genre]
	#	Returns: Info
	def get_info(self, filename, type):
		try:
			return self.libaudioplayer.get_file_info(bytes(filename, "utf-8"), type).decode("utf-8")
		except:
			print("self.get_info failed for type", type)
			return ""


	#	Get info from file metadata
	#	filename: Full path and filename
	#	Returns: Dictionary of info
	def get_file_info(self, filename):
		data = {}
		try:
			data["Title"] = self.get_info(filename, 1)
			data["Copyright"] = self.get_info(filename, 2)
			data["Software"] = self.get_info(filename, 3)
			data["Artist"] = self.get_info(filename, 4)
			data["Comment"] = self.get_info(filename, 5)
			data["Date"] = self.get_info(filename, 6)
			data["Album"] = self.get_info(filename, 7)
			data["License"] = self.get_info(filename, 8)
			data["Track"] = self.get_info(filename, 9)
			data["Genre"] = self.get_info(filename, 10)
		except:
			pass
		return data


#-------------------------------------------------------------------------------
