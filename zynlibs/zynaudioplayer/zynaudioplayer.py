#!/usr/bin/python3
# -*- coding: utf-8 -*-
#********************************************************************
# ZYNTHIAN PROJECT: Zynaudioplayer Python Wrapper
#
# A Python wrapper for zynaudioplayer library
#
# Copyright (C) 2021 Brian Walton <brian@riban.co.uk>
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

zynaudioplayer = None

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
def init():
	global libaudioplayer
	try:
		libaudioplayer=ctypes.cdll.LoadLibrary(dirname(realpath(__file__))+"/build/libzynaudioplayer.so")
		libaudioplayer.getDuration.restype = ctypes.c_double
		libaudioplayer.getFileDuration.restype = ctypes.c_double
		libaudioplayer.init()
	except Exception as e:
		libaudioplayer=None
		print("Can't initialise zynaudioplayer library: %s" % str(e))


#	Destoy instance of shared library
def destroy():
	global libaudioplayer
	if libaudioplayer:
		dlclose(libaudioplayer._handle)
	libaudioplayer = None


#	Open an audio file
#	filename: Full path and filename
#	Returns: True on success
def open(filename):
	if libaudioplayer:
		return libaudioplayer.open(bytes(filename, "utf-8"))
	return False

#	Get duration of an audio file
#	filename: Full path and filename
#	Returns: Duration in seconds or zero if file cannot be opened or invalid format
def get_duration(filename):
	if libaudioplayer:
		return libaudioplayer.getFileDuration(bytes(filename, "utf-8"))
	return 0.0


#	Save an audio file
#	filename: Full path and filename
#	Returns: True on success
def save(filename):
	if libaudioplayer:
		return libaudioplayer.save(bytes(filename, "utf-8"))
	return False


#-------------------------------------------------------------------------------
