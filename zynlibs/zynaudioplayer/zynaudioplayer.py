#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ********************************************************************
# ZYNTHIAN PROJECT: Zynaudioplayer Python Wrapper
#
# A Python wrapper for zynaudioplayer library
#
# Copyright (C) 2021-2024 Brian Walton <brian@riban.co.uk>
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
from _ctypes import dlclose
from os.path import dirname, realpath

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

control_cb = None

try:
    # Load or increment ref to lib
    libaudioplayer = ctypes.cdll.LoadLibrary(
        dirname(realpath(__file__))+"/build/libzynaudioplayer.so")
    libaudioplayer.get_codec.restype = ctypes.c_char_p
    libaudioplayer.get_base_note.restype = ctypes.c_uint8
    libaudioplayer.get_duration.restype = ctypes.c_float
    libaudioplayer.get_position.restype = ctypes.c_float
    libaudioplayer.get_loop_start_time.restype = ctypes.c_float
    libaudioplayer.get_loop_end_time.restype = ctypes.c_float
    libaudioplayer.get_crop_start_time.restype = ctypes.c_float
    libaudioplayer.get_crop_end_time.restype = ctypes.c_float
    libaudioplayer.get_file_duration.restype = ctypes.c_float
    libaudioplayer.get_env_attack.restype = ctypes.c_float
    libaudioplayer.get_env_hold.restype = ctypes.c_float
    libaudioplayer.get_env_decay.restype = ctypes.c_float
    libaudioplayer.get_env_sustain.restype = ctypes.c_float
    libaudioplayer.get_env_release.restype = ctypes.c_float
    libaudioplayer.get_file_info.restype = ctypes.c_char_p
    libaudioplayer.get_filename.restype = ctypes.c_char_p
    libaudioplayer.get_supported_codecs.restype = ctypes.c_char_p
    libaudioplayer.get_jack_client_name.restype = ctypes.c_char_p
    libaudioplayer.get_gain.restype = ctypes.c_float
    libaudioplayer.add_player.restype = ctypes.c_void_p
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
    libaudioplayer.get_pitch.restype = ctypes.c_float
    libaudioplayer.get_varispeed.restype = ctypes.c_float
    libaudioplayer.is_loop.restype = ctypes.c_uint8

except Exception as e:
    libaudioplayer = None
    logging.error(f"Can't initialise zynaudioplayer library: {e}")


def stop():
    libaudioplayer.lib_stop()
    set_control_cb(None)
    # dlclose(libaudioplayer._handle)


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
def remove_player(handle):
    return libaudioplayer.remove_player(ctypes.c_void_p(handle))


# Set a player's MIDI base note;
# handle: Index of player
# base_note: MIDI note to playback at normal speed
def set_base_note(handle, base_note):
    libaudioplayer.set_base_note(
        ctypes.c_void_p(handle), ctypes.c_uint8(base_note))


# Get a player's MIDI base note;
# handle: Index of player
# Returns: MIDI note to playback at normal speed
def get_base_note(handle):
    return libaudioplayer.get_base_note(ctypes.c_void_p(handle))


# Set a player's MIDI channel;
# handle: Index of player
# midi_chan: MIDI channel (0..15 or other value to disable MIDI)
def set_midi_chan(handle, midi_chan):
    if isinstance(midi_chan, int) and 0 <= midi_chan < 16:
        libaudioplayer.set_midi_chan(
            ctypes.c_void_p(handle), ctypes.c_uint8(midi_chan))
    else:
        libaudioplayer.set_midi_chan(
            ctypes.c_void_p(handle), ctypes.c_uint8(-1))


# Get a player's index;
# handle: Index of player
# Returns: Index
def get_index(handle):
    return libaudioplayer.get_index(ctypes.c_void_p(handle))


# Load an audio file
# filename: Full path and filename
# handle: Index of player
# Returns: True on success
def load(handle, filename):
    return libaudioplayer.load(ctypes.c_void_p(handle), bytes(filename, "utf-8"), value_cb)


# Unload the currently loaded audio file
# handle: Index of player
def unload(handle):
    libaudioplayer.unload(ctypes.c_void_p(handle))


def set_control_cb(cb):
    global control_cb
    control_cb = cb


@ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int, ctypes.c_float)
def value_cb(handle, vtype, value):
    if callable(control_cb):
        control_cb(handle, vtype, value)


# Get the full path and name of the currently loaded file
# handle: Index of player
# Returns: Filename
def get_filename(handle):
    return libaudioplayer.get_filename(ctypes.c_void_p(handle)).decode("utf-8")


# Get duration of loaded file
# handle: Index of player
# Returns: Duration in seconds or zero if file cannot be opened or invalid format
def get_duration(handle):
    return libaudioplayer.get_duration(ctypes.c_void_p(handle))


# Save an audio file
# handle: Index of player
# filename: Full path and filename
# Returns: True on success
def save(handle, filename):
    return libaudioplayer.save(ctypes.c_void_p(handle), ctypes.c_char_p(bytes(filename, "utf-8")))


# Set playback position
# handle: Index of player
# time: Position in seconds from start of file
def set_position(handle, time):
    libaudioplayer.set_position(ctypes.c_void_p(handle), ctypes.c_float(time))


# Get playback position
# handle: Index of player
# Returns: Position in seconds from start of file
def get_position(handle):
    return libaudioplayer.get_position(ctypes.c_void_p(handle))


# Enable looping of playback
# handle: Index of player
# enable: True to enable looping
def enable_loop(handle, enable):
    libaudioplayer.enable_loop(ctypes.c_void_p(handle), ctypes.c_uint8(enable))


# Get playback looping state
# handle: Index of player
# Returns: True looping enabled
def is_loop(handle):
    return libaudioplayer.is_loop(ctypes.c_void_p(handle)) > 0


# Get start of loop in seconds from start of file
# handle: Index of player
# Returns: Loop start
def get_loop_start(handle):
    return libaudioplayer.get_loop_start_time(ctypes.c_void_p(handle))


# Set start of loop in seconds from start of file
# handle: Index of player
# time: Loop start
def set_loop_start(handle, time):
    libaudioplayer.set_loop_start_time(
        ctypes.c_void_p(handle), ctypes.c_float(time))


# Get end of loop in seconds from end of file
# handle: Index of player
# Returns: Loop end
def get_loop_end(handle):
    return libaudioplayer.get_loop_end_time(ctypes.c_void_p(handle))


# Set end of loop in seconds from end of file
# handle: Index of player
# time: Loop end
def set_loop_end(handle, time):
    libaudioplayer.set_loop_end_time(
        ctypes.c_void_p(handle), ctypes.c_float(time))


# Get start of audio (crop) in seconds from start of file
# handle: Index of player
# Returns: Crop start
def get_crop_start(handle):
    return libaudioplayer.get_crop_start_time(ctypes.c_void_p(handle))


# Set start of audio (crop) in seconds from start of file
# handle: Index of player
# time: Crop start
def set_crop_start(handle, time):
    libaudioplayer.set_crop_start_time(
        ctypes.c_void_p(handle), ctypes.c_float(time))


# Get end of audio (crop) in seconds from end of file
# handle: Index of player
# Returns: Crop end
def get_crop_end(handle):
    return libaudioplayer.get_crop_end_time(ctypes.c_void_p(handle))


# Set end of audio (crop) in seconds from end of file
# handle: Index of player
# time: Crop end
def set_crop_end(handle, time):
    libaudioplayer.set_crop_end_time(
        ctypes.c_void_p(handle), ctypes.c_floattime)


# Add a cue point marker
# handle: Index of player
# pos: Marker position in seconds
# name: Marker name (max 255 chars)
# Returns: Index of cue point or -1 on failure
def add_cue_point(handle, pos, name=None):
    if name is None:
        name = ""
    return libaudioplayer.add_cue_point(ctypes.c_void_p(handle), ctypes.c_float(pos), ctypes.c_char_p(bytes(name, "utf-8")))


# Remove a cue point marker
# handle: Index of player
# frames: Marker position in frames
# Returns: True on success
def remove_cue_point(handle, frames):
    return libaudioplayer.remove_cue_point(ctypes.c_void_p(handle), ctypes.c_float(frames))


# Get quantity of cue point markers
# handle: Index of player
# Returns: Quantity of cue point markers
def get_cue_point_count(handle):
    return libaudioplayer.get_cue_point_count(ctypes.c_void_p(handle))


# Get a cue point's position
# handle: Index of player
# index Index of cue point
# Returns: Position (in seconds) of cue point or -1.0 if not found
def get_cue_point_position(handle, index):
    return libaudioplayer.get_cue_point_position(ctypes.c_void_p(handle), ctypes.c_uint32(index))


# Set a cue point's position
# handle: Index of player
# index Index of cue point
# position: Position (in seconds) of cue point or -1.0 if not found
# Returns: True on success
def set_cue_point_position(handle, index, position):
    return libaudioplayer.set_cue_point_position(ctypes.c_void_p(handle), ctypes.c_uint32(index), ctypes.c_float(position))


# Get a cue point's name
# handle: Index of player
# index Index of cue point
# Returns: Cue point name  or "" if not found
def get_cue_point_name(handle, index):
    return libaudioplayer.get_cue_point_name(ctypes.c_void_p(handle), ctypes.c_uint32(index)).decode("utf-8")


# Set a cue point's name
# handle: Index of player
# index Index of cue point
# name: New name for cue point (max 255 chars)
# Returns: True on success
def set_cue_point_name(handle, index, name):
    return libaudioplayer.set_cue_point_name(ctypes.c_void_p(handle), ctypes.c_uint32(index), ctypes.c_char_p(bytes(name[:255], "utf-8")))


# Remove all cue points
# handle: Index of player
def clear_cue_points(handle):
    libaudioplayer.clear_cue_points(ctypes.c_void_p(handle))


# Start playback
# handle: Index of player
def start_playback(handle):
    libaudioplayer.start_playback(ctypes.c_void_p(handle))


# Stop playback
# handle: Index of player
def stop_playback(handle):
    libaudioplayer.stop_playback(ctypes.c_void_p(handle))


# Get playback state
# handle: Index of player
def get_playback_state(handle):
    return libaudioplayer.get_playback_state(ctypes.c_void_p(handle))


# Get samplerate of loaded file
# handle: Index of player
# Returns: Samplerate of loaded file
def get_samplerate(handle):
    return libaudioplayer.get_samplerate(ctypes.c_void_p(handle))


# Get CODEC of loaded file
# handle: Index of player
# Returns: Name of CODEC (WAV|FLAC|OGG|MP3)
def get_codec(handle):
    return libaudioplayer.get_codec(ctypes.c_void_p(handle)).decode("utf-8")


# Get quantity of channels in loaded file
# handle: Index of player
# Returns: Quantity of channels in loaded file
def get_channels(handle):
    return libaudioplayer.get_channels(ctypes.c_void_p(handle))


# Get quantity of frames in loaded file
# handle: Index of player
# Returns: Quantity of frames in loaded file
def get_frames(handle):
    return libaudioplayer.get_frames(ctypes.c_void_p(handle))


# Get format of channels in loaded file
# handle: Index of player
# Returns: Bitwise OR of major and minor format type and optional endianness value
# See sndfile.h for supported formats
def get_format(handle):
    return libaudioplayer.get_format(ctypes.c_void_p(handle))


# Set quality of samplerate converion
# handle: Index of player
# quality: Samplerate conversion quality
# [SRC_SINC_BEST_QUALITY | SRC_SINC_MEDIUM_QUALITY | SRC_SINC_FASTEST | SRC_ZERO_ORDER_HOLD | SRC_LINEAR]
# Returns: True on success, i.e. the quality parameter is valid
def set_src_quality(handle, quality):
    return libaudioplayer.set_src_quality(ctypes.c_void_p(handle), quality) == 1


# Get quality of samplerate converion
# handle: Index of player
# Returns: Samplerate conversion quality
# [SRC_SINC_BEST_QUALITY | SRC_SINC_MEDIUM_QUALITY | SRC_SINC_FASTEST | SRC_ZERO_ORDER_HOLD | SRC_LINEAR]
def get_src_quality(handle):
    return libaudioplayer.get_src_quality(ctypes.c_void_p(handle))


# Set playback gain
# handle: Index of player
# gain: Playback gain factor [0..2]
def set_gain(handle, gain):
    libaudioplayer.set_gain(ctypes.c_void_p(handle), ctypes.c_float(gain))


# Get playback gain
# handle: Index of player
# Returns: Playback gain factor [0..2]
# TODO: error in float means get differs to set, e.g. set(0.2), get()=0.20000000298023224
def get_gain(handle):
    return libaudioplayer.get_gain(ctypes.c_void_p(handle))


# Set playback track for left output
# handle: Index of player
# track: Index of track to playback to left channel, -1 to mix odd tracks
# Mono files are played to both outputs
def set_track_a(handle, track):
    libaudioplayer.set_track_a(ctypes.c_void_p(handle), track)


# Set playback track for right output
# handle: Index of player
# track: Index of track to playback to right channel, -1 to mix even tracks
# Mono files are played to both outputs
def set_track_b(handle, track):
    libaudioplayer.set_track_b(ctypes.c_void_p(handle), track)


# Get playback track for left output
# handle: Index of player
# Returns: Index of track to playback to left channel, -1 to mix odd to left
def get_track_a(handle):
    return libaudioplayer.get_track_a(ctypes.c_void_p(handle))


# Get playback track for right output
# handle: Index of player
# Returns: Index of track to playback to right channel, -1 to mix even to left
def get_track_b(handle):
    return libaudioplayer.get_track_b(ctypes.c_void_p(handle))


# Set pitchbend range
# handle: Index of player
# range: Pitchbend range in semitones
def set_pitchbend_range(handle, pbrange):
    return libaudioplayer.set_pitchbend_range(ctypes.c_void_p(handle), pbrange)


# Get pitchbend range
# handle: Index of player
# Returns: Pitchbend range in semitones
def get_pitchbend_range(handle):
    return libaudioplayer.get_pitchbend_range(ctypes.c_void_p(handle))


# Set base speed factor
# handle: Index of player
# factor: Playback speed factor
def set_speed(handle, factor):
    libaudioplayer.set_speed(ctypes.c_void_p(handle), ctypes.c_float(factor))


# Get base speed factor
# handle: Index of player
# Returns: Playback speed factor
def get_speed(handle):
    return libaudioplayer.get_speed(ctypes.c_void_p(handle))


# Set base pitch factor
# handle: Index of player
# factor: Pitch factor
def set_pitch(handle, factor):
    libaudioplayer.set_pitch(ctypes.c_void_p(handle), ctypes.c_float(factor))


# Get base pitch factor
# handle: Index of player
# Returns: Pitch factor
def get_pitch(handle):
    return libaudioplayer.get_pitch(ctypes.c_void_p(handle))


# Set varispeed ratio
# handle: Index of player
# ratio: Ratio of playback speed : pitch shift
def set_varispeed(handle, ratio):
    libaudioplayer.set_varispeed(
        ctypes.c_void_p(handle), ctypes.c_float(ratio))


# Get varispeed ratio
# handle: Index of player
# Returns: Ratio of playback speed : pitch shift
def get_varispeed(handle):
    return libaudioplayer.get_varispeed(ctypes.c_void_p(handle))


# Set envelope attack
# handle: Index of player
# attack: Attack time in seconds
def set_attack(handle, attack):
    libaudioplayer.set_env_attack(
        ctypes.c_void_p(handle), ctypes.c_float(attack))


# Get envelope attack
# handle: Index of player
# Returns: Attack time in seconds
def get_attack(handle):
    return libaudioplayer.get_env_attack(ctypes.c_void_p(handle))


# Set envelope hold
# handle: Index of player
# attack: Time in seconds between attack and decay phase
def set_hold(handle, hold):
    libaudioplayer.set_env_hold(ctypes.c_void_p(handle), ctypes.c_float(hold))


# Get envelope hold
# handle: Index of player
# Returns: Time in seconds between attack and decay phase
def get_hold(handle):
    return libaudioplayer.get_env_hold(ctypes.c_void_p(handle))


# Set envelope decay
# handle: Index of player
# decay: Decay time in seconds
def set_decay(handle, decay):
    libaudioplayer.set_env_decay(
        ctypes.c_void_p(handle), ctypes.c_float(decay))


# Get envelope decay
# handle: Index of player
# Returns: Decay time in seconds
def get_decay(handle):
    return libaudioplayer.get_env_decay(ctypes.c_void_p(handle))


# Set envelope sustain
# handle: Index of player
# sustain: Sustain time in seconds
def set_sustain(handle, sustain):
    libaudioplayer.set_env_sustain(
        ctypes.c_void_p(handle), ctypes.c_float(sustain))


# Get envelope sustain
# handle: Index of player
# Returns: Sustain time in seconds
def get_sustain(handle):
    return libaudioplayer.get_env_sustain(ctypes.c_void_p(handle))


# Set envelope release
# handle: Index of player
# release: Release time in seconds
def set_release(handle, release):
    libaudioplayer.set_env_release(
        ctypes.c_void_p(handle), ctypes.c_float(release))


# Get envelope release
# handle: Index of player
# Returns: Release time in seconds
def get_release(handle):
    return libaudioplayer.get_env_release(ctypes.c_void_p(handle))


# Set beats in clip
# handle: Index of player
# beats: Quantity of beats or zero for non-beat based sample
def set_beats(handle, beats):
    libaudioplayer.set_beats(ctypes.c_void_p(handle), beats)


# Set beats in clip
# handle: Index of player
# Returns: Quantity of beats or zero for non-beat based sample
def get_beats(handle):
    return libaudioplayer.get_beats(ctypes.c_void_p(handle))


# Set tempo for playback
# tempo : Tempo in BPM
def set_tempo(tempo):
    libaudioplayer.set_tempo(ctypes.c_float(tempo))


# Set file read buffer size
# handle: Index of player
# count: Buffer size in frames
# Cannot change size whilst file is open
def set_buffer_size(handle, size):
    libaudioplayer.set_buffer_size(ctypes.c_void_p(handle), size)


# Get file read buffer size
# handle: Index of player
# Returns: Buffers size in frames
def get_buffer_size(handle):
    return libaudioplayer.get_buffer_size(ctypes.c_void_p(handle))


# Set quantity of file read buffers
# handle: Index of player
# count: Quantity of buffers
def set_buffer_count(handle, count):
    libaudioplayer.set_buffer_count(ctypes.c_void_p(handle), count)


# Get quantity of file read buffers
# handle: Index of player
# Returns: Quantity of buffers
def get_buffer_count(handle):
    return libaudioplayer.get_buffer_count(ctypes.c_void_p(handle))


# Set difference in postion that will trigger notificaton
# handle: Index of player
# time: Time difference in seconds
def set_pos_notify_delta(handle, time):
    libaudioplayer.set_pos_notify_delta(
        ctypes.c_void_p(handle), ctypes.c_float(time))


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
