#!/usr/bin/python3
# -*- coding: utf-8 -*-
#********************************************************************
# ZYNTHIAN PROJECT: Zynseq Python Wrapper
#
# A Python wrapper for zynseq library
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

libseq = None


#-------------------------------------------------------------------------------
# 	Zynthian Step Sequencer Library Wrapper
#
#	Most library functions are accessible directly by calling libseq.functionName(parameters)
#	Following function wrappers provide simple access for complex data types. Access with zynseq.function_name(parameters)
#
#	Include the following imports to access these two library objects:
# 		from zynlibs.zynseq import zynseq
#		from zynlibs.zynseq.zynseq import libseq
#
#-------------------------------------------------------------------------------

#	Initiate library - performed by zynseq module
def init():
	global libseq
	try:
		libseq=ctypes.cdll.LoadLibrary(dirname(realpath(__file__))+"/build/libzynseq.so")
		libseq.getSequenceName.restype = ctypes.c_char_p
		libseq.getTempo.restype = ctypes.c_double
	except Exception as e:
		libseq=None
		print("Can't initialise zynseq library: %s" % str(e))


#	Destoy instance of shared library
def destroy():
	global libseq
	if libseq:
		dlclose(libseq._handle)
	libseq = None


#	Load a zynseq file
#	filename: Full path and filename
#	Returns: True on success
def load(filename):
	if libseq:
		return libseq.load(bytes(filename, "utf-8"))
	return None


#	Save a zynseq file
#	filename: Full path and filename
#	Returns: True on success
def save(filename):
	if libseq:
		return libseq.save(bytes(filename, "utf-8"))
	return None


#	Set sequence name
#	name: Sequence name (truncates at 16 characters)
def set_sequence_name(bank, sequence, name):
	if libseq:
		libseq.setSequenceName(bank, sequence, bytes(name, "utf-8"))


#	Get sequence name
#	Returns: Sequence name (maximum 16 characters)
def get_sequence_name(bank, sequence):
	if libseq:
		return libseq.getSequenceName(bank, sequence).decode("utf-8")
	else:
		return "%d" % (sequence)


#	Request JACK transport start
#	client: Name to register with transport to avoid other clients stopping whilst in use
def transport_start(client):
	if libseq:
		libseq.transportStart(bytes(client, "utf-8"))


#	Request JACK transport stop
#	client: Name registered with transport when started
#	Note: Transport stops when all registered clients have requested stop
def transport_stop(client):
	if libseq:
		libseq.transportStop(bytes(client, "utf-8"))


#	Toggle JACK transport
#	client: Nameto register or was previously registered with transport when started
def transport_togle(client):
	if libseq:
		libseq.transportToggle(bytes(client, "utf-8"))


#-------------------------------------------------------------------------------
