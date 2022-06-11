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
from hashlib import new
from os.path import dirname, realpath
import logging
from math import sqrt

from zyngine import zynthian_engine
from zyngine import zynthian_controller
from zyngui import zynthian_gui_config


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

SEQ_EVENT_BANK		= 1
SEQ_EVENT_TEMPO		= 2
SEQ_EVENT_CHANNEL	= 3
SEQ_EVENT_GROUP		= 4
SEQ_EVENT_BPB		= 5
SEQ_EVENT_PLAYMODE	= 6
SEQ_EVENT_SEQUENCE	= 7
SEQ_EVENT_LOAD		= 8

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
		
		self.event_cb_list = [] # List of callbacks registered for notification of change
		self.bank = None
		self.select_bank(1)


	#	Destoy instance of shared library
	def destroy(self):
		if self.libseq:
			ctypes.dlclose(self.libseq._handle)
		self.libseq = None


	#	Function to add an view to send events to
	#	cb: Callback function
	def add_event_cb(self, cb):
		if cb not in self.event_cb_list:
			self.event_cb_list.append(cb)


	#	Function to remove an view to send events to
	#	cb: Callback function
	def remove_event_cb(self, cb):
		if cb in self.event_cb_list:
			self.event_cb_list.remove(cb)


	#	Function to send notification event to registered callback clients
	#	event: Event number
	def send_event(self, event):
		for cb in self.event_cb_list:
			try:
				cb(event)
			except Exception as e:
				logging.warning(e)


	#	Function to select a bank for edit / control
	#	bank: Index of bank
	def select_bank(self, bank=None):
		if isinstance(bank, int):
			if bank < 1 or bank > 64 or bank == self.bank:
				return
			self.bank = bank
		if self.libseq.getSequencesInBank(self.bank) == 0:
			self.build_default_bank(self.bank)
		self.send_event(SEQ_EVENT_BANK)


	#	Build a default bank 1 with 16 sequences in grid of midi channels 1,2,3,10
	#	bank: Index of bank to rebuild
	def build_default_bank(self, bank):
		if self.libseq:
			self.libseq.setSequencesInBank(bank, 16)
			for column in range(4):
				if column == 3:
					channel = 9
				else:
					channel = column
				for row in range(4):
					seq = row + 4 * column
					self.set_sequence_name(bank, seq, "{}".format(self.libseq.getPatternAt(bank, seq, 0, 0)))
					self.libseq.setGroup(bank, seq, channel)
					self.libseq.setChannel(bank, seq, 0, channel)
			self.send_event(SEQ_EVENT_BANK)


	#	Function to add / remove sequences to change bank size
	#	new_columns: Quanityt of columns (and rows) of new grid
	def update_bank_grid(self, new_columns):
		old_columns = int(sqrt(self.libseq.getSequencesInBank(self.bank)))
		# To avoid odd behaviour we stop all sequences from playing before changing grid size (blunt but effective!)
		for seq in range(self.libseq.getSequencesInBank(self.bank)):
			self.libseq.setPlayState(self.bank, seq, zynthian_gui_config.SEQ_STOPPED)
		channels = []
		groups = []
		for column in range(new_columns):
			if column < old_columns:
				channels.append(self.libseq.getChannel(self.bank, column * old_columns, 0))
				groups.append(self.libseq.getGroup(self.bank, column * old_columns))
			else:
				channels.append(column)
				groups.append(column)
		delta = new_columns - old_columns
		if delta > 0:
			# Growing grid so add extra sequences
			for column in range(old_columns):
				for row in range(old_columns, old_columns + delta):
					pad = row + column * new_columns
					self.libseq.insertSequence(self.bank, pad)
					self.libseq.setChannel(self.bank, pad, 0, channels[column])
					self.libseq.setGroup(self.bank, pad, groups[column])
					self.set_sequence_name(self.bank, pad, "%s"%(pad + 1))
			for column in range(old_columns, new_columns):
				for row in range(new_columns):
					pad = row + column * new_columns
					self.libseq.insertSequence(self.bank, pad)
					self.libseq.setChannel(self.bank, pad, 0, column)
					self.libseq.setGroup(self.bank, pad, column)
					self.set_sequence_name(self.bank, pad, "{}".format(pad + 1))
		elif delta < 0:
			# Shrinking grid so remove excess sequences
			# Lose excess columns
			self.libseq.setSequencesInBank(self.bank, new_columns * old_columns)
			# Lose exess rows
			for col in range(new_columns - 1, -1, -1):
				for row in range(old_columns - 1, new_columns -1, -1):
					offset = old_columns * col + row
					self.libseq.removeSequence(self.bank, offset)
		self.send_event(SEQ_EVENT_BANK)


	#	Load a zynseq file
	#	filename: Full path and filename
	def load(self, filename):
		self.libseq.load(bytes(filename, "utf-8"))
		if not filename:
			self.build_default_bank(1)
		self.send_event(SEQ_EVENT_LOAD)


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
			self.send_event(SEQ_EVENT_SEQUENCE)


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
			self.send_event(SEQ_EVENT_TEMPO)


	def set_midi_channel(self, bank, sequence, track, channel):
		self.libseq.setChannel(bank, sequence, track, channel)
		self.send_event(SEQ_EVENT_CHANNEL)


	def set_group(self, bank, sequence, group):
		self.libseq.setGroup(bank, sequence, group)
		self.send_event(SEQ_EVENT_GROUP)


	def set_sequences_in_bank(self, bank, count):
		self.libseq.setSequencesInBank(bank, count)
		self.send_event(SEQ_EVENT_BANK)


	def insert_sequence(self, bank, sequence):
		self.libseq.insertSequence(bank, sequence)
		self.send_event(SEQ_EVENT_BANK)

	def set_beats_per_bar(self, bpb):
		self.libseq.setBeatsPerBar(bpb)
		self.send_event(SEQ_EVENT_BPB)


	def set_play_mode(self, bank, sequence, mode):
		self.libseq.setPlayMode(bank, sequence, mode)
		self.send_event(SEQ_EVENT_PLAYMODE)


	def remove_pattern(self, bank, sequence, track, time):
		self.libseq.removePattern(bank, sequence, track, time)
		self.send_event(SEQ_EVENT_SEQUENCE)


	def add_pattern(self, bank, sequence, track, time, pattern, force=False):
		if self.libseq.addPattern(bank, sequence, track, time, pattern, force):
			self.send_event(SEQ_EVENT_SEQUENCE)
			return True

#-------------------------------------------------------------------------------
