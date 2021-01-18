#!/usr/bin/python3
# -*- coding: utf-8 -*-
#********************************************************************
# ZYNTHIAN PROJECT: Zynsfm Python Wrapper
#
# A Python wrapper for zynsmf library
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

#-------------------------------------------------------------------------------
# Jackpeak Library Wrapper
#-------------------------------------------------------------------------------

lib_zynsmf = None

def lib_zynsmf_init():
	global lib_zynsmf
	try:
		lib_zynsmf=ctypes.cdll.LoadLibrary(dirname(realpath(__file__))+"/build/libzynsmf.so")
		lib_zynsmf.getDuration.restype = ctypes.c_double
	except Exception as e:
		lib_zynsmf=None
		print("Can't init zynsmf library: %s" % str(e))

def destroy():
	global lib_zynsmf
	if lib_zynsmf:
		dlclose(lib_zynsmf._handle)
	lib_zynsmf = None

def get_lib_zynsmf():
	if not lib_zynsmf:
		init()
	return lib_zynsmf

def load(filename):
	lib_zynsmf.load(bytes(filename, "utf-8"))
#-------------------------------------------------------------------------------
