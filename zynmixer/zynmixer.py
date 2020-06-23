#!/usr/bin/python3
# -*- coding: utf-8 -*-
#********************************************************************
# ZYNTHIAN PROJECT: Jackpeak Python Wrapper
#
# A Python wrapper for zynmixer library
#
# Copyright (C) 2019 Brian Walton <brian@riban.co.uk>
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

from ctypes import *
from os.path import dirname, realpath

#-------------------------------------------------------------------------------
# Jackpeak Library Wrapper
#-------------------------------------------------------------------------------

lib_zynmixer=None

def lib_zynmixer_init():
	global lib_zynmixer
	try:
		lib_zynmixer=cdll.LoadLibrary(dirname(realpath(__file__))+"/build/libzynmixer.so")
		lib_zynmixer.init()
		lib_zynmixer.getLevel.restype = c_float
		lib_zynmixer.getPan.restype = c_float
	except Exception as e:
		lib_zynmixer=None
		print("Can't init zynmixer library: %s" % str(e))
	return lib_zynmixer

def get_lib_zynmixer():
	return lib_zynmixer

def set_level(channel, level):
	if lib_zynmixer:
		lib_zynmixer.setLevel(channel, c_float(level))

def set_pan(channel, pan):
	if lib_zynmixer:
		lib_zynmixer.setPan(channel, c_float(pan))

#-------------------------------------------------------------------------------
