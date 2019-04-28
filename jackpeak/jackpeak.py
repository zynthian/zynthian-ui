#!/usr/bin/python3
# -*- coding: utf-8 -*-
#********************************************************************
# ZYNTHIAN PROJECT: Jackpeak Python Wrapper
#
# A Python wrapper for jackpeak library
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

lib_jackpeak=None

def lib_jackpeak_init():
	global lib_jackpeak
	try:
		lib_jackpeak=cdll.LoadLibrary(dirname(realpath(__file__))+"/build/libjackpeak.so")
		lib_jackpeak.initJackpeak()
		lib_jackpeak.getPeak.restype = c_float
		lib_jackpeak.getPeakRaw.restype = c_float
		lib_jackpeak.getHold.restype = c_float
	except Exception as e:
		lib_jackpeak=None
		print("Can't init jackpeak library: %s" % str(e))
	return lib_jackpeak

def get_lib_jackpeak():
	return lib_jackpeak

#-------------------------------------------------------------------------------
