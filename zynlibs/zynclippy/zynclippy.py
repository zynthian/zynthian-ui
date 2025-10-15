#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ********************************************************************
# ZYNTHIAN PROJECT: Zynaudioplayer Python Wrapper
#
# A Python wrapper for zynclippy library
#
# Copyright (C) 2025 Brian Walton <brian@riban.co.uk>
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
from os.path import dirname, realpath

# -------------------------------------------------------------------------------
# Zynthian audio clip player Library Wrapper
#
# Most library functions are accessible directly by calling libzynclippy.functionName(parameters)
# Module function wrappers provide simple access for complex data types: zynclippy.function_name(parameters)
#
# Include the following import to initialise the lib:
#   from zynlibs.zynclippy import zynclippy
#
# To access module functions:
#   zynclippy.fn(params)
#
# To access low-level library functions:
#   zynclippy.libclippy.fn(params)
# -------------------------------------------------------------------------------

try:
    # Load or increment ref to lib
    libclippy = ctypes.cdll.LoadLibrary(
        dirname(realpath(__file__))+"/build/libzynclippy.so")
    libclippy.init()

    libclippy.getGain.restype = ctypes.c_float
    #libclippy.copyFile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint8, ctypes.c_float]


except Exception as e:
    libclippy = None
    logging.error(f"Can't initialise zynclippy library: {e}")

""" Add a clip player

    channel - MIDI channel
    returns - True on success
"""
def add_player(channel):
    return libclippy.addPlayer(channel) == 0

""" Remove a clip player

    channel - MIDI channel
    returns - True on success
"""
def remove_player(channel):
    return libclippy.removePlayer(channel) == 0

""" Load an audio file

    channel - MIDI channel [0..15]
    clip - Clip id [0..MAX_CLIPS]
    filename - Full path and filename
    returns - True on success
"""
def load_clip(channel, clip, path):
    ret = libclippy.loadClip(channel, clip, bytes(path, "utf-8"))
    if ret:
        logging.warning(f"Failed to load file {path} to clip {clip} on channel {channel}: {ret}")
    return ret == 0

""" Unload an audio file

    channel - MIDI channel [0..15]
    clip - Clip id [0..MAX_CLIPS]
    returns - True on success
"""
def unload_clip(channel, clip):
    return libclippy.unloadClip(channel, clip) == 0

""" Set the gain fo a player

    channel - MIDI channel [0..15]
    clip - Clip id [0..MAX_CLIPS]
    gain - Gain [float]
"""
def set_gain(channel, clip, gain):
    libclippy.setGain(channel, clip, ctypes.c_float(gain))

""" Get the gain fo a player

    channel - MIDI channel [0..15]
    clip - Clip id [0..MAX_CLIPS]
    returns - Gain [float]
"""
def get_gain(channel, clip):
    return libclippy.getGain(channel, clip)

""" Get the samplerate of a file

    path - Full path and filename
    returns - samplerate in frames per second or 0 on error
"""
def get_file_samplerate(path):
    return libclippy.getFileSamplerate(bytes(path, "utf-8"))

""" Get the quantity of frames in a file

    path - Full path and filename
    returns - Duration in frames or 0 on error
"""
def get_file_frames(path):
    return libclippy.getFileFrames(bytes(path, "utf-8"))

""" Copy a file, converting to 16-bit WAV at system samplerate with optional time stretch
    src_path -  Full path and filename of file to read
    dst_path - Full path and filename of file to write
    quality - Conversion quality [SINC_BEST_QUALITY=0,SINC_MEDIUM_QUALITY=1,SINC_FASTEST=2,ZERO_ORDER_HOLD=3,LINEAR=4]
    ratio - Stretch ratio (1.0 for no stretch (default))
    returns - Error code
"""
def copy_file(src_path, dst_path, quality=2, ratio=1.0):
    return libclippy.copyFile(bytes(src_path, "utf-8"), bytes(dst_path, "utf-8"), quality, ctypes.c_float(ratio))

# -------------------------------------------------------------------------------
