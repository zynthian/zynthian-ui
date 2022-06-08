#!/usr/bin/python3
# -*- coding: utf-8 -*-
#********************************************************************
# ZYNTHIAN PROJECT: Zynseq Python Wrapper
#
# A Python wrapper for zynseq library
#
# Copyright (C) 2021-2022 Brian Walton <brian@riban.co.uk>
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
from os.path import dirname, realpath

from zyngine import zynthian_engine
from zyngine import zynthian_controller


#-------------------------------------------------------------------------------
# 	Zynthian Step Sequencer Library Wrapper
#
#	Most library functions are accessible directly by calling self.libseq.functionName(parameters)
#	Following function wrappers provide simple access for complex data types. Access with zynseq.function_name(parameters)
#
#	Include the following imports to access these two library objects:
# 		from zynlibs.zynseq import zynseq
#		from zynlibs.zynseq.zynseq import libseq
#
#-------------------------------------------------------------------------------

class zynseq(zynthian_engine):

	#	Initiate library - performed by zynseq module
	def __init__(self):
		try:
			self.libseq = ctypes.cdll.LoadLibrary(dirname(realpath(__file__))+"/build/libzynseq.so")
			self.libseq.getSequenceName.restype = ctypes.c_char_p
			self.libseq.getTempo.restype = ctypes.c_double
			self.libseq.getNoteDuration.restype = ctypes.c_float
			self.libseq.addNote.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_float]
			self.libseq.changeDurationAll.argtypes = [ctypes.c_float]
			self.libseq.setTempo.argtypes = [ctypes.c_double]
			self.libseq.init(bytes("zynseq", "utf-8"))
		except Exception as e:
			self.libseq=None
			print("Can't initialise zynseq library: %s" % str(e))
		
		self.zctrl_tempo = zynthian_controller(self, 'tempo', None, {
			'is_integer':False,
			'value_min':20.0,
			'value_max':420,
			'value':self.libseq.getTempo(),
			'nudge_factor':0.1
			})


	#	Destoy instance of shared library
	def destroy(self):
		if self.libseq:
			ctypes.dlclose(self.libseq._handle)
		self.libseq = None


	#	Load a zynseq file
	#	filename: Full path and filename
	#	Returns: True on success
	def load(self, filename):
		if self.libseq:
			return self.libseq.load(bytes(filename, "utf-8"))
		return None


	#	Save a zynseq file
	#	filename: Full path and filename
	#	Returns: True on success
	def save(self, filename):
		if self.libseq:
			return self.libseq.save(bytes(filename, "utf-8"))
		return None


	#	Set sequence name
	#	name: Sequence name (truncates at 16 characters)
	def set_sequence_name(self, bank, sequence, name):
		if self.libseq:
			self.libseq.setSequenceName(bank, sequence, bytes(name, "utf-8"))


	#	Get sequence name
	#	Returns: Sequence name (maximum 16 characters)
	def get_sequence_name(self, bank, sequence):
		if self.libseq:
			return self.libseq.getSequenceName(bank, sequence).decode("utf-8")
		else:
			return "%d" % (sequence)


	#	Request JACK transport start
	#	client: Name to register with transport to avoid other clients stopping whilst in use
	def transport_start(self, client):
		if self.libseq:
			self.libseq.transportStart(bytes(client, "utf-8"))


	#	Request JACK transport stop
	#	client: Name registered with transport when started
	#	Note: Transport stops when all registered clients have requested stop
	def transport_stop(self, client):
		if self.libseq:
			self.libseq.transportStop(bytes(client, "utf-8"))


	#	Toggle JACK transport
	#	client: Nameto register or was previously registered with transport when started
	def transport_toggle(self, client):
		if self.libseq:
			self.libseq.transportToggle(bytes(client, "utf-8"))


	def set_tempo(self, tempo):
		self.zctrl_tempo.set_value(tempo)
	
	
	def get_tempo(self):
		return self.libseq.getTempo()

	
	def nudge_tempo(self, offset):
		self.zctrl_tempo.nudge(offset)


	def send_controller_value(self, zctrl):
		if zctrl == self.zctrl_tempo:
			self.libseq.setTempo(zctrl.value)
#-------------------------------------------------------------------------------
