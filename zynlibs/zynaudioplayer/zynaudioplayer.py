#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ********************************************************************
# ZYNTHIAN PROJECT: Zynaudioplayer Python Wrapper
#
# A Python wrapper for zynaudioplayer library
#
# Copyright (C) 2021-2026 Brian Walton <brian@riban.co.uk>
# License: LGPL V3
#
# ********************************************************************
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
# ********************************************************************

import ctypes
import logging
#from _ctypes import dlclose
from os.path import dirname, realpath

from zyngine.zynthian_signal_manager import zynsigman

# -------------------------------------------------------------------------------
# Zynthian audio file player Library Wrapper
#
# Most library functions are accessible directly by calling libzynaudioplayer.functionName(parameters)
# Module function wrappers provide simple access for complex data types: zynaudioplayer.function_name(parameters)
#
# Include the following imports to access these two library objects:
# 	import zynlibs.zynaudioplayer
# 	from zynlibs.zynaudioplayer import libaudioplayer
#
# -------------------------------------------------------------------------------

@ctypes.CFUNCTYPE(None, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_float)
def cb_handler(id, play_state, loop, pos):
    zynsigman.send(zynsigman.S_AUDIO_PLAYER, zynsigman.SS_AUDIO_PLAYER_STATE, id=id, play_state=play_state, loop=loop, pos=pos)

try:
    # Load or increment ref to lib
    libaudioplayer = ctypes.cdll.LoadLibrary(dirname(realpath(__file__))+"/build/libzynaudioplayer.so")
    libaudioplayer.get_codec.restype = ctypes.c_char_p
    libaudioplayer.get_duration.restype = ctypes.c_float
    libaudioplayer.get_position.restype = ctypes.c_float
    libaudioplayer.get_crop_start_time.restype = ctypes.c_float
    libaudioplayer.get_crop_end_time.restype = ctypes.c_float
    libaudioplayer.get_filename.restype = ctypes.c_char_p
    libaudioplayer.get_supported_codecs.restype = ctypes.c_char_p
    libaudioplayer.get_jack_client_name.restype = ctypes.c_char_p
    libaudioplayer.get_gain.restype = ctypes.c_float
    libaudioplayer.add_player.restype = ctypes.c_uint8
    libaudioplayer.get_cue_point_position.restype = ctypes.c_float
    libaudioplayer.set_cue_point_position.restype = ctypes.c_bool
    libaudioplayer.add_cue_point.restype = ctypes.c_int32
    libaudioplayer.remove_cue_point.restype = ctypes.c_int32
    libaudioplayer.get_cue_point_count.restype = ctypes.c_uint32
    libaudioplayer.get_cue_point_name.restype = ctypes.c_char_p
    libaudioplayer.set_cue_point_name.restype = ctypes.c_bool
    libaudioplayer.get_playback_state.restype = ctypes.c_uint8
    libaudioplayer.set_src_quality.restype = ctypes.c_uint8
    libaudioplayer.get_speed.restype = ctypes.c_float
    libaudioplayer.get_pitch_semitone.restype = ctypes.c_int8
    libaudioplayer.get_pitch_cent.restype = ctypes.c_int8
    libaudioplayer.get_varispeed.restype = ctypes.c_float
    libaudioplayer.is_loop.restype = ctypes.c_uint8
    libaudioplayer.get_file_duration.restype = ctypes.c_float
    libaudioplayer.get_file_channels.restype = ctypes.c_int32
    libaudioplayer.get_file_info.restype = ctypes.c_char_p
    if not libaudioplayer.init(cb_handler):
        logging.error("libzynaudioplayer failed to initialise jack client\n");

except Exception as e:
    libaudioplayer = None
    logging.error(f"Can't initialise zynaudioplayer library: {e}")

def stop():
    libaudioplayer.lib_stop()
    # dlclose(libaudioplayer._id)

def is_codec_supported(codec):
    return libaudioplayer.is_codec_supported(bytes(codec, "utf-8")) == 1

def get_supported_codecs():
    return libaudioplayer.get_supported_codecs().decode("utf-8").lower().split(',')

# Get jack client name
def get_jack_client_name():
    return libaudioplayer.get_jack_client_name().decode("utf-8")

# Add a player
def add_player():
    return libaudioplayer.add_player()

# Remove a player
def remove_player(id):
    return libaudioplayer.remove_player(id)

# Load an audio file
# filename: Full path and filename
# id: Index of player
# Returns: True on success
def load(id, filename):
    if libaudioplayer.load(id, bytes(filename, "utf-8")):
        return True
    return False

# Unload the currently loaded audio file
# id: Index of player
def unload(id):
    libaudioplayer.unload(id)

# Get the full path and name of the currently loaded file
# id: Index of player
# Returns: Filename
def get_filename(id):
    return libaudioplayer.get_filename(id).decode("utf-8")

# Get duration of loaded file
# id: Index of player
# Returns: Duration in seconds or zero if file cannot be opened or invalid format
def get_duration(id):
    return libaudioplayer.get_duration(id)

# Save an audio file
# id: Index of player
# filename: Full path and filename
# Returns: True on success
def save(id, filename):
    return libaudioplayer.save(id), ctypes.c_char_p(bytes(filename, "utf-8"))


# Set playback position
# id: Index of player
# time: Position in seconds from start of file
def set_position(id, time):
    libaudioplayer.set_position(id, ctypes.c_float(time))


# Get playback position
# id: Index of player
# Returns: Position in seconds from start of file
def get_position(id):
    return libaudioplayer.get_position(id)


# Enable looping of playback
# id: Index of player
# enable: True to enable looping
def enable_loop(id, enable):
    libaudioplayer.enable_loop(id, ctypes.c_uint8(enable))

# Get playback looping state
# id: Index of player
# Returns: True looping enabled
def is_loop(id):
    return libaudioplayer.is_loop(id) > 0

# Get end of loop in seconds from end of file
# id: Index of player
# Returns: Loop end
def get_loop_end(id):
    return libaudioplayer.get_loop_end_time(id)

# Get start of audio (crop) in seconds from start of file
# id: Index of player
# Returns: Crop start
def get_crop_start(id):
    return libaudioplayer.get_crop_start_time(id)

# Set start of audio (crop) in seconds from start of file
# id: Index of player
# time: Crop start
def set_crop_start(id, time):
    libaudioplayer.set_crop_start_time(id, ctypes.c_float(time))

# Get end of audio (crop) in seconds from end of file
# id: Index of player
# Returns: Crop end
def get_crop_end(id):
    return libaudioplayer.get_crop_end_time(id)

# Set end of audio (crop) in seconds from end of file
# id: Index of player
# time: Crop end
def set_crop_end(id, time):
    libaudioplayer.set_crop_end_time(id, ctypes.c_float(time))

# Add a cue point marker
# id: Index of player
# pos: Marker position in seconds
# name: Marker name (max 255 chars)
# Returns: Index of cue point or -1 on failure
def add_cue_point(id, pos, name=None):
    if name is None:
        name = ""
    return libaudioplayer.add_cue_point(id, ctypes.c_float(pos), ctypes.c_char_p(bytes(name, "utf-8")))

# Remove a cue point marker
# id: Index of player
# frames: Marker position in frames
# Returns: True on success
def remove_cue_point(id, frames):
    return libaudioplayer.remove_cue_point(id, ctypes.c_float(frames))

# Get quantity of cue point markers
# id: Index of player
# Returns: Quantity of cue point markers
def get_cue_point_count(id):
    return libaudioplayer.get_cue_point_count(id)

# Get a cue point's position
# id: Index of player
# index Index of cue point
# Returns: Position (in seconds) of cue point or -1.0 if not found
def get_cue_point_position(id, index):
    return libaudioplayer.get_cue_point_position(id, ctypes.c_uint32(index))

# Set a cue point's position
# id: Index of player
# index Index of cue point
# position: Position (in seconds) of cue point or -1.0 if not found
# Returns: True on success
def set_cue_point_position(id, index, position):
    return libaudioplayer.set_cue_point_position(id, ctypes.c_uint32(index), ctypes.c_float(position))

# Get a cue point's name
# id: Index of player
# index Index of cue point
# Returns: Cue point name  or "" if not found
def get_cue_point_name(id, index):
    return libaudioplayer.get_cue_point_name(id, ctypes.c_uint32(index)).decode("utf-8")

# Set a cue point's name
# id: Index of player
# index Index of cue point
# name: New name for cue point (max 255 chars)
# Returns: True on success
def set_cue_point_name(id, index, name):
    return libaudioplayer.set_cue_point_name(id, ctypes.c_uint32(index), ctypes.c_char_p(bytes(name[:255], "utf-8")))

# Remove all cue points
# id: Index of player
def clear_cue_points(id):
    libaudioplayer.clear_cue_points(id)

# Start playback
# id: Index of player
def start_playback(id):
    libaudioplayer.start_playback(id)

# Stop playback
# id: Index of player
def stop_playback(id):
    libaudioplayer.stop_playback(id)

# Get playback state
# id: Index of player
def get_playback_state(id):
    return libaudioplayer.get_playback_state(id)

# Get samplerate of loaded file
# id: Index of player
# Returns: Samplerate of loaded file
def get_samplerate(id):
    return libaudioplayer.get_samplerate(id)

# Get CODEC of loaded file
# id: Index of player
# Returns: Name of CODEC (WAV|FLAC|OGG|MP3)
def get_codec(id):
    return libaudioplayer.get_codec(id).decode("utf-8")

# Get quantity of channels in loaded file
# id: Index of player
# Returns: Quantity of channels in loaded file
def get_channels(id):
    return libaudioplayer.get_channels(id)

# Get quantity of frames in loaded file
# id: Index of player
# Returns: Quantity of frames in loaded file
def get_frames(id):
    return libaudioplayer.get_frames(id)

# Get format of channels in loaded file
# id: Index of player
# Returns: Bitwise OR of major and minor format type and optional endianness value
# See sndfile.h for supported formats
def get_format(id):
    return libaudioplayer.get_format(id)

# Set quality of samplerate converion
# id: Index of player
# quality: Samplerate conversion quality
# [SRC_SINC_BEST_QUALITY | SRC_SINC_MEDIUM_QUALITY | SRC_SINC_FASTEST | SRC_ZERO_ORDER_HOLD | SRC_LINEAR]
# Returns: True on success, i.e. the quality parameter is valid
def set_src_quality(id, quality):
    return libaudioplayer.set_src_quality(id, quality) == 1

# Get quality of samplerate converion
# id: Index of player
# Returns: Samplerate conversion quality
# [SRC_SINC_BEST_QUALITY | SRC_SINC_MEDIUM_QUALITY | SRC_SINC_FASTEST | SRC_ZERO_ORDER_HOLD | SRC_LINEAR]
def get_src_quality(id):
    return libaudioplayer.get_src_quality(id)

# Set playback gain
# id: Index of player
# gain: Playback gain factor [0..2]
from time import monotonic
def set_gain(id, gain):
    libaudioplayer.set_gain(id, ctypes.c_float(gain))
    
# Get playback gain
# id: Index of player
# Returns: Playback gain factor [0..2]
# TODO: error in float means get differs to set, e.g. set(0.2), get()=0.20000000298023224
def get_gain(id):
    return libaudioplayer.get_gain(id)

# Set playback track for left output
# id: Index of player
# track: Index of track to playback to left channel, -1 to mix odd tracks
# Mono files are played to both outputs
def set_track_a(id, track):
    libaudioplayer.set_track_a(id, track)

# Set playback track for right output
# id: Index of player
# track: Index of track to playback to right channel, -1 to mix even tracks
# Mono files are played to both outputs
def set_track_b(id, track):
    libaudioplayer.set_track_b(id, track)

# Get playback track for left output
# id: Index of player
# Returns: Index of track to playback to left channel, -1 to mix odd to left
def get_track_a(id):
    return libaudioplayer.get_track_a(id)

# Get playback track for right output
# id: Index of player
# Returns: Index of track to playback to right channel, -1 to mix even to left
def get_track_b(id):
    return libaudioplayer.get_track_b(id)

# Set base speed factor
# id: Index of player
# factor: Playback speed factor
def set_speed(id, factor):
    libaudioplayer.set_speed(id, ctypes.c_float(factor))

# Get base speed factor
# id: Index of player
# Returns: Playback speed factor
def get_speed(id):
    return libaudioplayer.get_speed(id)

# Set base pitch factor in semitones
# id: Index of player
# semitones: Pitch factor
def set_pitch_semitone(id, semitones):
    libaudioplayer.set_pitch_semitone(id, ctypes.c_int8(semitones))

# Get base pitch factor in semitones
# id: Index of player
# Returns: Pitch factor
def get_pitch_semitones(id):
    return libaudioplayer.get_pitch(id)

# Set base pitch factor in cents
# id: Index of player
# cents: Pitch factor
def set_pitch_cent(id, cents):
    libaudioplayer.set_pitch_cent(id, ctypes.c_int8(cents))

# Get base pitch factor in cent
# id: Index of player
# Returns: Pitch factor
def get_pitch_cent(id):
    return libaudioplayer.get_pitch(id)

# Set varispeed ratio
# id: Index of player
# ratio: Ratio of playback speed : pitch shift
def set_varispeed(id, ratio):
    libaudioplayer.set_varispeed(id, ctypes.c_float(ratio))

# Get varispeed ratio
# id: Index of player
# Returns: Ratio of playback speed : pitch shift
def get_varispeed(id):
    return libaudioplayer.get_varispeed(id)

# Set file read buffer size
# id: Index of player
# count: Buffer size in frames
# Cannot change size whilst file is open
def set_buffer_size(id, size):
    libaudioplayer.set_buffer_size(id, size)

# Get file read buffer size
# id: Index of player
# Returns: Buffers size in frames
def get_buffer_size(id):
    return libaudioplayer.get_buffer_size(id)

# Set quantity of file read buffers
# id: Index of player
# count: Quantity of buffers
def set_buffer_count(id, count):
    libaudioplayer.set_buffer_count(id, count)

# Get quantity of file read buffers
# id: Index of player
# Returns: Quantity of buffers
def get_buffer_count(id):
    return libaudioplayer.get_buffer_count(id)

# Set difference in postion that will trigger notificaton
# id: Index of player
# time: Time difference in seconds
def set_pos_notify_delta(id, time):
    libaudioplayer.set_pos_notify_delta(id, ctypes.c_float(time))

# Enable debug output
# enable: True to enable debug
def enable_debug(enable=True):
    libaudioplayer.enable_debug(enable)

# Get debug state
# Returns: True if debug enabled
def is_debug():
    return libaudioplayer.is_debug() == 1

# Get duration of an audio file
# filename: Full path and filename
# Returns: Duration in seconds or zero if file cannot be opened or invalid format
def get_file_duration(filename):
    return libaudioplayer.get_file_duration(bytes(filename, "utf-8"))

# Get num of channels of an audio file
# filename: Full path and filename
# Returns: Num of channels or zero if file cannot be opened or invalid format
def get_file_channels(filename):
    return libaudioplayer.get_file_channels(bytes(filename, "utf-8"))

# Get info from file metadata
# filename: Full path and filename
# itype: Info type [1:Title, 2:Copyright, 3:Software, 4:Artist, 5:Comment, 6:Date, 7:Album, 8:License, 9:Track number, 10:Genre]
# Returns: Info
def get_info(filename, itype):
    try:
        return libaudioplayer.get_file_info(bytes(filename, "utf-8"), itype).decode("utf-8")
    except:
        logging.error("get_info failed for type", itype)
        return ""

# Get info from file metadata
# filename: Full path and filename
# Returns: Dictionary of info
def get_file_info(filename):
    data = {}
    try:
        data["Title"] = get_info(filename, 1)
        data["Copyright"] = get_info(filename, 2)
        data["Software"] = get_info(filename, 3)
        data["Artist"] = get_info(filename, 4)
        data["Comment"] = get_info(filename, 5)
        data["Date"] = get_info(filename, 6)
        data["Album"] = get_info(filename, 7)
        data["License"] = get_info(filename, 8)
        data["Track"] = get_info(filename, 9)
        data["Genre"] = get_info(filename, 10)
    except:
        pass
    return data

# -------------------------------------------------------------------------------
