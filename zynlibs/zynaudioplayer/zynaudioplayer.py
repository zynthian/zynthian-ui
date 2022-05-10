#!/usr/bin/python3
# -*- coding: utf-8 -*-
#********************************************************************
# ZYNTHIAN PROJECT: Zynaudioplayer Python Wrapper
#
# A Python wrapper for zynaudioplayer library
#
# Copyright (C) 2021 Brian Walton <brian@riban.co.uk>
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

libaudioplayer = None

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

#	Initiate library - performed by zynaudioplayer module
def init(jack_name = "zynaudioplayer"):
	global libaudioplayer
	try:
		libaudioplayer=ctypes.cdll.LoadLibrary(dirname(realpath(__file__))+"/build/libzynaudioplayer.so")
		libaudioplayer.getDuration.restype = ctypes.c_float
		libaudioplayer.getPosition.restype = ctypes.c_float
		libaudioplayer.getFileDuration.restype = ctypes.c_float
		libaudioplayer.getFileInfo.restype = ctypes.c_char_p
		libaudioplayer.getFilename.restype = ctypes.c_char_p
		libaudioplayer.getVolume.restype = ctypes.c_float
		libaudioplayer.setVolume.argtypes = [ctypes.c_float]
		libaudioplayer.setPosition.argtypes = [ctypes.c_float]
		libaudioplayer.init(bytes(jack_name, "utf-8"))
	except Exception as e:
		libaudioplayer=None
		print("Can't initialise zynaudioplayer library: %s" % str(e))


#	Destoy instance of shared library
def destroy():
	global libaudioplayer
	if libaudioplayer:
		libaudioplayer.end()
		handle = libaudioplayer._handle
#		del libaudioplayer 
		dlclose(handle)
	libaudioplayer = None


#	Load an audio file
#	filename: Full path and filename
#	Returns: True on success
def load(filename):
	if libaudioplayer:
		return libaudioplayer.open(bytes(filename, "utf-8"))
	return False


#	Unload the currently loaded audio file
def unload():
	if libaudioplayer:
		libaudioplayer.closeFile()


#	Get the full path and name of the currently loaded file
#	Returns: Filename
def get_filename():
	if libaudioplayer:
		return libaudioplayer.getFilename().decode("utf-8")


#	Get duration of an audio file
#	filename: Full path and filename
#	Returns: Duration in seconds or zero if file cannot be opened or invalid format
def get_duration(filename):
	if libaudioplayer:
		return libaudioplayer.getFileDuration(bytes(filename, "utf-8"))
	return 0.0

#	Get info from file metadata
#	filename: Full path and filename
#	type: Info type [1:Title, 2:Copyright, 3:Software, 4:Artist, 5:Comment, 6:Date, 7:Album, 8:License, 9:Track number, 10:Genre]
#	Returns: Info
def get_info(filename, type):
	if libaudioplayer:
		try:
			return libaudioplayer.getFileInfo(bytes(filename, "utf-8"), type).decode("utf-8")
		except:
			print("get_info failed for type", type)
			pass
	return ""


#	Get info from file metadata
#	filename: Full path and filename
#	Returns: Dictionary of info
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


#	Save an audio file
#	filename: Full path and filename
#	Returns: True on success
def save(filename):
	if libaudioplayer:
		return libaudioplayer.save(bytes(filename, "utf-8"))
	return False


#-------------------------------------------------------------------------------
