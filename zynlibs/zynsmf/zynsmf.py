#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ********************************************************************
# ZYNTHIAN PROJECT: Zynsfm Python Wrapper
#
# A Python wrapper for zynsmf library
#
# Copyright (C) 2021 Brian Walton <brian@riban.co.uk>
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
from _ctypes import dlclose
from os.path import dirname, realpath

libsmf = None

EVENT_TYPE_NONE = 0x00
EVENT_TYPE_MIDI = 0x01
EVENT_TYPE_SYSEX = 0x02
EVENT_TYPE_META = 0x03
EVENT_TYPE_ESCAPE = 0x04

META_TYPE_SEQ_NUMBER = 0x00,
META_TYPE_TEXT = 0x01,
META_TYPE_COPYRIGHT = 0x02,
META_TYPE_TRACK_NAME = 0x03,
META_TYPE_INSTUMENT_NAME = 0x04,
META_TYPE_LYRIC = 0x05,
META_TYPE_MARKER = 0x06,
META_TYPE_CUE_POINT = 0x07,
META_TYPE_MIDI_CHANNEL = 0x20,
META_TYPE_END_OF_TRACK = 0x2F,
META_TYPE_TEMPO = 0x51,
META_TYPE_SMPTE_OFFSET = 0x54,
META_TYPE_TIME_SIGNATURE = 0x58,
META_TYPE_KEY_SIGNATURE = 0x59,
META_TYPE_SEQ_SPECIFIC = 0x7F

MIDI_NOTE_OFF = 0x80  # 128
MIDI_NOTE_ON = 0x90  # 144
MIDI_POLY_PRESSURE = 0xA0  # 160
MIDI_CONTROLLER = 0xB0  # 176
MIDI_PROGRAM_CHANGE = 0xC0  # 192
MIDI_CHANNEL_PRESSURE = 0xD0  # 208
MIDI_PITCH_BEND = 0xE0  # 224
MIDI_ALL_SOUND_OFF = 0x78  # 120
MIDI_ALL_NOTES_OFF = 0x7B  # 123


PLAY_STATE_STOPPED = 0
PLAY_STATE_STARTING = 1
PLAY_STATE_PLAYING = 2
PLAY_STATE_STOPPING = 3


# -------------------------------------------------------------------------------
# Zynthian Standard MIDI File Library Wrapper
#
# Most library functions are accessible directly by calling libsmf.functionName(parameters)
# Following function wrappers provide simple access for complex data types. Access with zynsmf.function_name(parameters)
#
# Include the following imports to access these two library objects:
#  	from zynlibs.zynsmf import zynsmf
# 	from zynlibs.zynsmf.zynsmf import libsmf
#
# -------------------------------------------------------------------------------

# Initiate library - performed by zynsmf module
def init():
    global libsmf
    try:
        libsmf = ctypes.cdll.LoadLibrary(
            dirname(realpath(__file__)) + "/build/libzynsmf.so")
        libsmf.addSmf.restype = ctypes.c_ulong
        libsmf.unload.argtypes = [ctypes.c_ulong]
        libsmf.removeSmf.argtypes = [ctypes.c_ulong]
        libsmf.getDuration.argtypes = [ctypes.c_ulong]
        libsmf.getDuration.restype = ctypes.c_double
        libsmf.setPosition.argtypes = [ctypes.c_ulong, ctypes.c_uint]
        libsmf.getTracks.argtypes = [ctypes.c_ulong]
        libsmf.getFormat.argtypes = [ctypes.c_ulong]
        libsmf.getEvents.argtypes = [ctypes.c_ulong, ctypes.c_ulong]
        libsmf.addNote.argtypes = [ctypes.c_ulong, ctypes.c_uint, ctypes.c_uint,
                                   ctypes.c_uint, ctypes.c_ubyte, ctypes.c_ubyte, ctypes.c_ubyte]
        libsmf.addTempo.argtypes = [
            ctypes.c_ulong, ctypes.c_uint, ctypes.c_double]
        libsmf.setEndOfTrack.argtypes = [
            ctypes.c_ulong, ctypes.c_uint, ctypes.c_uint]
        libsmf.getTicksPerQuarterNote.argtypes = [ctypes.c_ulong]
        libsmf.getEvent.argtypes = [ctypes.c_ulong, ctypes.c_ubyte]
        libsmf.attachPlayer.argtypes = [ctypes.c_ulong]
        libsmf.attachRecorder.argtypes = [ctypes.c_ulong]
        libsmf.getTempo.argtypes = [ctypes.c_ulong, ctypes.c_uint]
        libsmf.getTempo.restype = ctypes.c_double
        libsmf.printEvents.argtypes = [ctypes.c_ulong, ctypes.c_uint]
        libsmf.muteTrack.argtypes = [
            ctypes.c_ulong, ctypes.c_uint, ctypes.c_ubyte]
        libsmf.isTrackMuted.argtypes = [ctypes.c_ulong, ctypes.c_uint]
    except Exception as e:
        libsmf = None
        print(f"Can't initialise zynsmf library: {e}")


# Destroy instance of shared library
def destroy():
    global libsmf
    if libsmf:
        dlclose(libsmf._handle)
    libsmf = None


# Load a MIDI file
#  smf: Pointer to smf object to populate
#  filename: Full path and filename
#  Returns: True on success
def load(smf, filename):
    if libsmf:
        return libsmf.load(ctypes.c_ulong(smf), bytes(filename, "utf-8"))
    return False


# Save a MIDI file
#  smf: Pointer to smf object to save
#  filename: Full path and filename
#  Returns: True on success
def save(smf, filename):
    if libsmf:
        return libsmf.save(ctypes.c_ulong(smf), bytes(filename, "utf-8"))
    return False

# -------------------------------------------------------------------------------
