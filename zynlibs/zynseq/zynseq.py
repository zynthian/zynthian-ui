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
SEQ_EVENT_MIDI_LEARN= 9
SEQ_EVENT_LOAD_PAT	= 10

SEQ_MAX_PATTERNS	= 64872

SEQ_DISABLED		= 0
SEQ_ONESHOT			= 1
SEQ_LOOP			= 2
SEQ_ONESHOTALL		= 3
SEQ_LOOPALL			= 4
SEQ_LASTPLAYMODE	= 4

SEQ_STOPPED			= 0
SEQ_PLAYING			= 1
SEQ_STOPPING		= 2
SEQ_STARTING		= 3
SEQ_RESTARTING		= 4
SEQ_STOPPINGSYNC	= 5
SEQ_LASTPLAYSTATUS	= 5

PLAY_MODES = ['Disabled', 'Oneshot', 'Loop', 'Oneshot all', 'Loop all', 'Oneshot sync', 'Loop sync']


class zynseq(zynthian_engine):

	#	Initiate library - performed by zynseq module
	def __init__(self):
		self.changing_bank = False
		try:
			self.libseq = ctypes.cdll.LoadLibrary(dirname(realpath(__file__))+"/build/libzynseq.so")
			self.libseq.getSequenceName.restype = ctypes.c_char_p
			self.libseq.getTempo.restype = ctypes.c_double
			self.libseq.getNoteDuration.restype = ctypes.c_float
			self.libseq.addNote.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_float]
			self.libseq.changeDurationAll.argtypes = [ctypes.c_float]
			self.libseq.setTempo.argtypes = [ctypes.c_double]
			self.libseq.setMetronomeVolume.argtypes = [ctypes.c_float]
			self.libseq.getMetronomeVolume.restype = ctypes.c_float
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
		
		self.bank = None
		self.select_bank(1, True)


	#	Destoy instance of shared library
	def destroy(self):
		if self.libseq:
			ctypes.dlclose(self.libseq._handle)
		self.libseq = None


	#	Function to select a bank for edit / control
	#	bank: Index of bank
	#	force: True to fore bank selection even if same as current bank
	def select_bank(self, bank=None, force=False):
		if self.changing_bank:
			return
		if bank is None:
			bank = self.bank
		else:
			if bank < 1 or bank > 64 or bank == self.bank and not force:
				return
		self.changing_bank = True
		if self.libseq.getSequencesInBank(bank) == 0:
			self.build_default_bank(bank)
		self.bank = bank
		self.changing_bank = False


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


	#	Function to add / remove sequences to change bank size
	#	new_columns: Quantity of columns (and rows) of new grid
	def update_bank_grid(self, new_columns):
		old_columns = int(sqrt(self.libseq.getSequencesInBank(self.bank)))
		# To avoid odd behaviour we stop all sequences from playing before changing grid size (blunt but effective!)
		for seq in range(self.libseq.getSequencesInBank(self.bank)):
			self.libseq.setPlayState(self.bank, seq, SEQ_STOPPED)
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


	#	Load a zynseq file
	#	filename: Full path and filename
	def load(self, filename):
		self.libseq.load(bytes(filename, "utf-8"))
		self.select_bank(1, True) #TODO: Store selected bank in seq file

	#	Load a zynseq pattern file
	#	patnum: Pattern number
	#	filename: Full path and filename
	def load_pattern(self, patnum, filename):
		self.libseq.load_pattern(int(patnum), bytes(filename, "utf-8"))

	#	Save a zynseq file
	#	filename: Full path and filename
	#	Returns: True on success
	def save(self, filename):
		if self.libseq:
			return self.libseq.save(bytes(filename, "utf-8"))
		return None

	#	Save a zynseq pattern file
	#	patnum: Pattern number
	#	filename: Full path and filename
	#	Returns: True on success
	def save_pattern(self, patnum, filename):
		if self.libseq:
			return self.libseq.save_pattern(int(patnum), bytes(filename, "utf-8"))
		return None


	#	Set sequence name
	#	name: Sequence name (truncates at 16 characters)
	def set_sequence_name(self, bank, sequence, name):
		if self.libseq:
			self.libseq.setSequenceName(bank, sequence, bytes(name, "utf-8"))


	#	Check if pattern is empty
	#	Returns: True is pattern is empty
	def is_pattern_empty(self, patnum):
		if self.libseq:
			return self.libseq.isPatternEmpty(patnum)
		return False


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


	def update_tempo(self):
		self.set_tempo(self.libseq.getTempo())


	def nudge_tempo(self, offset):
		self.zctrl_tempo.nudge(offset)


	def send_controller_value(self, zctrl):
		if zctrl == self.zctrl_tempo:
			self.libseq.setTempo(zctrl.value)


	def set_midi_channel(self, bank, sequence, track, channel):
		self.libseq.setChannel(bank, sequence, track, channel)


	def set_group(self, bank, sequence, group):
		self.libseq.setGroup(bank, sequence, group)


	def set_sequences_in_bank(self, bank, count):
		self.libseq.setSequencesInBank(bank, count)


	def insert_sequence(self, bank, sequence):
		self.libseq.insertSequence(bank, sequence)


	def set_beats_per_bar(self, bpb):
		self.libseq.setBeatsPerBar(bpb)


	def set_play_mode(self, bank, sequence, mode):
		self.libseq.setPlayMode(bank, sequence, mode)


	def remove_pattern(self, bank, sequence, track, time):
		self.libseq.removePattern(bank, sequence, track, time)


	def add_pattern(self, bank, sequence, track, time, pattern, force=False):
		if self.libseq.addPattern(bank, sequence, track, time, pattern, force):
			return True


	def enable_midi_learn(self, bank, sequence):
		try:
			self.libseq.enableMidiLearn(bank, sequence, ctypes.py_object(self), self.midi_learn_cb)
		except Exception as e:
			logging.error(e)


	def disable_midi_learn(self):
		try:
			self.libseq.enableMidiLearn(0, 0, ctypes.py_object(self), self.midi_learn_cb)
		except Exception as e:
			logging.error(e)


	def get_riff_data(self):
		fpath = "/tmp/snapshot.zynseq"
		try:
			# Save to tmp
			self.save(fpath)
			# Load binary data
			with open(fpath,"rb") as fh:
				riff_data=fh.read()
				logging.info("Loading RIFF data...\n")
			return riff_data

		except Exception as e:
			logging.error("Can't get RIFF data! => {}".format(e))
			return None


	def restore_riff_data(self, riff_data):
		fpath = "/tmp/snapshot.zynseq"
		try:
			# Save RIFF data to tmp file
			with open(fpath,"wb") as fh:
				fh.write(riff_data)
				logging.info("Restoring RIFF data...\n")
			# Load from tmp file
			if self.load(fpath):
				self.filename = "snapshot"
				return True

		except Exception as e:
			logging.error("Can't restore RIFF data! => {}".format(e))
			return False

#-------------------------------------------------------------------------------
