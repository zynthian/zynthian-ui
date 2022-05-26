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
	def __init__(self):
		try:
			self.handle = None
			self.libaudioplayer = ctypes.cdll.LoadLibrary(dirname(realpath(__file__))+"/build/libzynaudioplayer.so")
			handle = self.libaudioplayer.init()
			if handle == -1:
				return
			self.handle = handle

			self.libaudioplayer.get_duration.restype = ctypes.c_float
			self.libaudioplayer.get_position.restype = ctypes.c_float
			self.libaudioplayer.get_loop_start_time.restype = ctypes.c_float
			self.libaudioplayer.get_loop_end_time.restype = ctypes.c_float
			self.libaudioplayer.get_file_duration.restype = ctypes.c_float
			self.libaudioplayer.get_file_info.restype = ctypes.c_char_p
			self.libaudioplayer.get_filename.restype = ctypes.c_char_p
			self.libaudioplayer.get_jack_client_name.restype = ctypes.c_char_p
			self.libaudioplayer.get_gain.restype = ctypes.c_float
			self.libaudioplayer.set_gain.argtypes = [ctypes.c_int, ctypes.c_float]
			self.libaudioplayer.set_position.argtypes = [ctypes.c_int, ctypes.c_float]
			self.libaudioplayer.set_loop_start_time.argtypes = [ctypes.c_int, ctypes.c_float]
			self.libaudioplayer.set_loop_end_time.argtypes = [ctypes.c_int, ctypes.c_float]
			self.libaudioplayer.set_pos_notify_delta.argtypes = [ctypes.c_int, ctypes.c_float]
			self.control_cb = None
		except Exception as e:
			self.libaudioplayer=None
			print("Can't initialise zynaudioplayer library: %s" % str(e))


	#	Destoy instance of shared library
	def destroy(self):
		if self.libaudioplayer:
			self.libaudioplayer.end()
			dlclose(self.libaudioplayer._handle)
		self.libaudioplayer = None


	#	Remove player from library
	def remove_player(self):
		if self.handle is None:
			return
		self.set_control_cb(None)
		self.libaudioplayer.remove_player(self.handle)
		self.libaudioplayer = None
		self.handle = None
		

	#	Get jack client name
	def get_jack_client_name(self):
		if self.handle is None:
			return ""
		return self.libaudioplayer.get_jack_client_name(self.handle).decode("utf-8")


	#	Load an audio file
	#	filename: Full path and filename
	#	Returns: True on success
	def load(self, filename):
		if self.handle is None:
			return False
		return self.libaudioplayer.load(self.handle, bytes(filename, "utf-8"), ctypes.py_object(self), self.value_cb)


	#	Unload the currently loaded audio file
	def unload(self):
		if self.handle is None:
			return
		self.libaudioplayer.unload(self.handle)


	def set_control_cb(self, cb):
		self.control_cb = cb


	@ctypes.CFUNCTYPE(None, ctypes.py_object, ctypes.c_int, ctypes.c_float)
	def value_cb(self, type, value):
		if self.control_cb:
			self.control_cb(type, value)


	#	Get the full path and name of the currently loaded file
	#	Returns: Filename
	def get_filename(self):
		if self.handle is None:
			return ""
		return self.libaudioplayer.get_filename(self.handle).decode("utf-8")


	#	Get duration of loaded file
	#	Returns: Duration in seconds or zero if file cannot be opened or invalid format
	def get_duration(self):
		if self.handle is None:
			return 0.0
		return self.libaudioplayer.get_duration(self.handle)


	#	Save an audio file
	#	filename: Full path and filename
	#	Returns: True on success
	def save(self, filename):
		if self.handle is None:
			return False
		return self.libaudioplayer.save(self.handle, bytes(filename, "utf-8"))


	#	Set playback position
	#	time: Position in seconds from start of file
	def set_position(self, time):
		if self.handle is None:
			return
		self.libaudioplayer.set_position(self.handle, time)
    	
	#	Get playback position
	#	Returns: Position in seconds from start of file
	def get_position(self):
		if self.handle is None:
			return 0.0
		return self.libaudioplayer.get_position(self.handle)
    	
	#	Enable looping of playback
	#	enable: True to enable looping
	def enable_loop(self, enable):
		if self.handle is None:
			return
		self.libaudioplayer.enable_loop(self.handle, enable)
    	
	#	Get playback looping state
	#	Returns: True looping enabled
	def is_loop(self):
		if self.handle is None:
			return False
		return (self.libaudioplayer.is_loop(self.handle) == 1)

	#	Get start of loop in seconds from start of file
	#	Returns: Loop start
	def get_loop_start(self):
		if self.handle is None:
			return 0.0
		return self.libaudioplayer.get_loop_start_time(self.handle)

	#	Set start of loop in seconds from start of file
	#	time: Loop start
	def set_loop_start(self, time):
		if self.handle is None:
			return 
		self.libaudioplayer.set_loop_start_time(self.handle, time)

	#	Get end of loop in seconds from end of file
	#	Returns: Loop end
	def get_loop_end(self):
		if self.handle is None:
			return 0.0
		return self.libaudioplayer.get_loop_end_time(self.handle)

	#	Set end of loop in seconds from end of file
	#	time: Loop end
	def set_loop_end(self, time):
		if self.handle is None:
			return 
		self.libaudioplayer.set_loop_end_time(self.handle, time)

	#	Start playback
	def start_playback(self):
		if self.handle is None:
			return
		self.libaudioplayer.start_playback(self.handle)
 
 	#	Stop playback
	def stop_playback(self):
		if self.handle is None:
			return
		self.libaudioplayer.stop_playback(self.handle)

 	#	Get playback state
	def get_playback_state(self):
		if self.handle is None:
			return 0
		return self.libaudioplayer.get_playback_state(self.handle)

 	#	Get samplerate of loaded file
	#	Returns:Samplerate of loaded file
	def get_samplerate(self):
		if self.handle is None:
			return 0
		return self.libaudioplayer.get_samplerate(self.handle)


 	#	Get quantity of channels in loaded file
	#	Returns: Quantity of channels in loaded file
	def get_channels(self):
		if self.handle is None:
			return 0
		return self.libaudioplayer.get_channels(self.handle)


 	#	Get quantity of frames in loaded file
	#	Returns: Quantity of frames in loaded file
	def get_frames(self):
		if self.handle is None:
			return 0
		return self.libaudioplayer.get_frames(self.handle)


 	#	Get format of channels in loaded file
	#	Returns: Bitwise OR of major and minor format type and optional endianness value
	#   See sndfile.h for supported formats
	def get_format(self):
		if self.handle is None:
			return 0
		return self.libaudioplayer.get_format(self.handle)


 	#	Set quality of samplerate converion
	#	quality: Samplerate conversion quality [SRC_SINC_BEST_QUALITY | SRC_SINC_MEDIUM_QUALITY | SRC_SINC_FASTEST | SRC_ZERO_ORDER_HOLD | SRC_LINEAR]
	#	Returns: True on success, i.e. the quality parameter is valid
	def set_src_quality(self, quality):
		if self.handle is None:
			return False
		return (self.libaudioplayer.set_src_quality(self.handle, quality) == 1)


 	#	Get quality of samplerate converion
	#	Returns: Samplerate conversion quality [SRC_SINC_BEST_QUALITY | SRC_SINC_MEDIUM_QUALITY | SRC_SINC_FASTEST | SRC_ZERO_ORDER_HOLD | SRC_LINEAR]
	def get_src_quality(self):
		if self.handle is None:
			return 2
		return self.libaudioplayer.get_src_quality(self.handle)


 	#	Set playback gain
	#	gain: Playback gain factor [0..2]
	def set_gain(self, gain):
		if self.handle is None:
			return
		self.libaudioplayer.set_gain(self.handle, gain)


 	#	Get playback gain
	#	Returns: Playback gain factor [0..2]
	#	TODO: error in float means get differs to set, e.g. set(0.2), get()=0.20000000298023224
	def get_gain(self):
		if self.handle is None:
			return 0.0
		return self.libaudioplayer.get_gain(self.handle)


	#	Set playback track for left output
	#	track: Index of track to playback to left channel, -1 to mix odd tracks
	#	Mono files are played to both outputs
	def set_track_a(self, track):
		if self.handle is None:
			return
		self.libaudioplayer.set_track_a(self.handle, track)


	#	Set playback track for right output
	#	track: Index of track to playback to right channel, -1 to mix even tracks
	#	Mono files are played to both outputs
	def set_track_b(self, track):
		if self.handle is None:
			return
		self.libaudioplayer.set_track_b(self.handle, track)


	#	Get playback track for left output
	#	Returns: Index of track to playback to left channel, -1 to mix odd to left
	def get_track_a(self):
		if self.handle is None:
			return 0
		return self.libaudioplayer.get_track_a(self.handle)


	#	Get playback track for right output
	#	Returns: Index of track to playback to right channel, -1 to mix even to left
	def get_track_b(self):
		if self.handle is None:
			return 0
		return self.libaudioplayer.get_track_b(self.handle)


	#	Set file read buffer size
	#	count: Buffer size in frames
	#	Cannot change size whilst file is open
	def set_buffer_size(self, size):
		if self.handle is None:
			return
		self.libaudioplayer.set_buffer_size(self.handle, size)


	#	Get file read buffer size
	#	Returns: Buffers size in frames
	def get_buffer_size(self):
		if self.handle is None:
			return 0
		return self.libaudioplayer.get_buffer_size(self.handle)


	#	Set quantity of file read buffers
	#	count: Quantity of buffers
	def set_buffer_count(self, count):
		if self.handle is None:
			return
		self.libaudioplayer.set_buffer_count(self.handle, count)


	#	Get quantity of file read buffers
	#	Returns: Quantity of buffers
	def get_buffer_count(self):
		if self.handle is None:
			return 0
		return self.libaudioplayer.get_buffer_count(self.handle)


	#	Set difference in postion that will trigger notificaton 
	#	time: Time difference in seconds
	def set_pos_notify_delta(self, time):
		if self.handle is None:
			return
		self.libaudioplayer.set_pos_notify_delta(self.handle, time)


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
		if self.handle is None:
			return ""
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
