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

#	Function to initialize library
#	returns: Library object or None if library not initialized
def lib_zynmixer_init():
	global lib_zynmixer
	try:
		lib_zynmixer=cdll.LoadLibrary(dirname(realpath(__file__))+"/build/libzynmixer.so")
		lib_zynmixer.init()
		lib_zynmixer.getLevel.restype = c_float
		lib_zynmixer.getBalance.restype = c_float
	except Exception as e:
		lib_zynmixer=None
		print("Can't init zynmixer library: %s" % str(e))
	return lib_zynmixer

#	Function to get instance of library
#	returns: Library object or None if library not initialized
def get_lib_zynmixer():
	return lib_zynmixer

#	Function to set fader level for a channel
#	channel: Index of channel
#	level: Fader value (0..+1)
def set_level(channel, level):
	if lib_zynmixer:
		lib_zynmixer.setLevel(channel, c_float(level))

#	Function to set balance for a channel
#	channel: Index of channel
#	balance: Balance value (-1..+1)
def set_balance(channel, balance):
	if lib_zynmixer:
		lib_zynmixer.setBalance(channel, c_float(balance))

#	Function to get fader level for a channel
#	channel: Index of channel
#	returns: Fader level (0..+1)
def get_level(channel):
	if lib_zynmixer:
		return lib_zynmixer.getLevel(channel)
	return 0

#	Function to get balance for a channel
#	channel: Index of channel
#	returns: Balance value (-1..+1)
def get_balance(channel):
	if lib_zynmixer:
		return lib_zynmixer.getBalance(channel)
	return 0

#-------------------------------------------------------------------------------
