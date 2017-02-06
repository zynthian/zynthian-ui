# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_fluidsynth)
# 
# zynthian_engine implementation for FluidSynth Sampler
# 
# Copyright (C) 2015-2016 Fernando Moyano <jofemodo@zynthian.org>
#
#******************************************************************************
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
#******************************************************************************

import os
import copy
import logging
from . import zynthian_engine

#------------------------------------------------------------------------------
# FluidSynth Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_fluidsynth(zynthian_engine):
	name="FluidSynth"
	nickname="FS"

	soundfont_count=0
	soundfont_index={}
	soundfont_dirs=[
		('_', os.getcwd()+"/data/soundfonts/sf2"),
		('MY', os.getcwd()+"/my-data/soundfonts/sf2")
	]

	ctrl_list=[
		[[
			['volume',7,96,127],
			['modulation',1,0,127],
			['pan',10,64,127],
			['expression',11,64,127]
		],0,'main'],
		[[
			['volume',7,96,127],
			['sustain on/off',64,'off','off|on'],
			['reverb',91,64,127],
			['chorus',93,0,127]
		],0,'effects']
	]

	def __init__(self,parent=None):
		if self.midi_driver=='alsa':
			mdriver="alsa_seq";
		else:
			mdriver=self.midi_driver
		self.command=("/usr/bin/fluidsynth", "-p", "fluidsynth", "-a", self.audio_driver, "-m", mdriver ,"-g", "1", "-j", "-o", "synth.midi-bank-select=mma")
		self.parent=parent
		self.clean()
		self.start(True)

	def clean(self):
		super().clean()
		self.soundfont_count=0
		self.soundfont_index={}

	def stop(self):
		self.proc_cmd("quit",2)
		super().stop()

	def load_bank_list(self):
		self.load_bank_filelist(self.soundfont_dirs,"sf2")

	def load_instr_list(self):
		logging.info('Getting Instrument List for ' + self.bank_name[self.midi_chan])
		self.instr_list=[]
		bi=self.bank_index[self.midi_chan]
		sfi=self.soundfont_index[self.bank_list[bi][0]]
		lines=self.proc_cmd("inst " + str(sfi))
		for f in lines:
			try:
				prg=int(f[4:7])
				bank_msb=int(f[0:3])
				bank_lsb=int(bank_msb/128)
				bank_msb=bank_msb%128
				title=str.replace(f[8:-1], '_', ' ')
				self.instr_list.append((f,[bank_msb,bank_lsb,prg],title))
			except:
				pass

	def _set_bank(self, bank, chan=None):
		if self.load_soundfont(bank[0]):
			self.unload_unused_soundfonts()
			self.set_all_instr()

	def _set_instr(self, instr, chan=None):
		if chan is None: chan=self.midi_chan
		bi=self.bank_index[chan]
		sf=self.bank_list[bi][0]
		if sf in self.soundfont_index:
			sfi=self.soundfont_index[sf]
			midi_bank=instr[1][0]+instr[1][1]*128
			midi_prg=instr[1][2]
			logging.debug("Set INSTR CH " + str(chan) + ", SoundFont: " + str(sfi) + ", Bank: " + str(midi_bank) + ", Program: " + str(midi_prg))
			self.proc_cmd("select "+str(chan)+' '+str(sfi)+' '+str(midi_bank)+' '+str(midi_prg))
		else:
			logging.warning("Can't set Instrument before loading SoundFont")

	def load_soundfont(self, sf):
		if sf not in self.soundfont_index:
			self.soundfont_count=self.soundfont_count+1
			logging.info("Load SoundFont " + sf + " => " + str(self.soundfont_count))
			self.proc_cmd("load \"" + sf + "\"", 20)
			self.soundfont_index[sf]=self.soundfont_count
			return True

	def unload_unused_soundfonts(self):
		#Make a copy of soundfont index and remove used soundfonts
		sf_unload=copy.copy(self.soundfont_index)
		for c,i in enumerate(self.bank_index):
			if self.bank_name[c] and self.bank_list[i][0] in sf_unload:
				#print("Skip "+self.bank_list[i][0]+"("+str(sf_unload[self.bank_list[i][0]])+")")
				del sf_unload[self.bank_list[i][0]]
		#Then, remove the remaining ;-)
		for sf,sfi in sf_unload.items():
			logging.info("Unload SoundFont "+ str(sfi))
			self.proc_cmd("unload " + str(sfi),2)
			del self.soundfont_index[sf]

	def load_instr_config(self):
		super().load_instr_config()

#******************************************************************************
