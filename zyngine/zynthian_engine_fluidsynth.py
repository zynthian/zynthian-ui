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

from zyngine.zynthian_engine import *

#------------------------------------------------------------------------------
# FluidSynth Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_fluidsynth(zynthian_engine):
	name="FluidSynth"
	nickname="FS"

	soundfont_dir="./data/soundfonts/sf2"
	soundfont_count=0
	soundfont_index={}

	map_list=(
		([
			('volume',7,96,127),
			#('expression',11,127,127),
			('modulation',1,0,127),
			('reverb',91,64,127),
			('chorus',93,2,127)
		],0,'main'),
		([
			('expression',11,127,127),
			('modulation',1,0,127),
			('reverb',91,64,127),
			('chorus',93,2,127)
		],0,'extra')
	)
	default_ctrl_config=map_list[0][0]

	def __init__(self,parent=None):
		if self.midi_driver=='alsa':
			mdriver="alsa_seq";
		else:
			mdriver=self.midi_driver
		#self.command=("/usr/local/bin/fluidsynth", "-p", "fluidsynth", "-a", self.audio_driver, "-m", mdriver ,"-g", "1")
		self.command=("/usr/bin/fluidsynth", "-p", "fluidsynth", "-a", self.audio_driver, "-m", mdriver ,"-g", "1", "-j", "synth.midi-bank-select", "mma")

		self.parent=parent
		self.clean()
		self.start(True)
		self.load_bank_list()

	def stop(self):
		self.proc_cmd("quit",2)
		super().stop()

	def load_bank_list(self):
		self.load_bank_filelist(self.soundfont_dir,"sf2")

	def load_instr_list(self):
		self.instr_list=[]
		bi=self.bank_index[self.midi_chan]
		sfi=self.soundfont_index[self.bank_list[bi][0]]
		print('Getting Instrument List for ' + self.bank_name[self.midi_chan])
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

	def set_bank(self, i):
		self.bank_index[self.midi_chan]=i
		self.bank_name[self.midi_chan]=self.bank_list[i][2]
		self.load_soundfont(self.bank_list[i][0])
		print('Bank Selected: ' + self.bank_name[self.midi_chan] + ' (' + str(i)+')')
		self.load_instr_list()
		self.unload_unused_soundfonts()

	def set_instr(self, i):
		last_instr_index=self.instr_index[self.midi_chan]
		last_instr_name=self.instr_name[self.midi_chan]
		self.instr_index[self.midi_chan]=i
		self.instr_name[self.midi_chan]=self.instr_list[i][2]
		print('Instrument Selected: ' + self.instr_name[self.midi_chan] + ' (' + str(i)+')')
		if last_instr_index!=i or not last_instr_name:
			#self.parent.zynmidi.set_midi_instr(self.midi_chan, self.instr_list[i][1][0], self.instr_list[i][1][1], self.instr_list[i][1][2])
			self.set_soundfont_instr(self.instr_list[i])
			self.load_instr_config()

	def set_soundfont_instr(self, instr):
		bi=self.bank_index[self.midi_chan]
		sfi=self.soundfont_index[self.bank_list[bi][0]]
		midi_bank=instr[1][0]+instr[1][1]*128
		midi_prg=instr[1][2]
		print("Set INSTR CH " + str(self.midi_chan) + ", SoundFont: " + str(sfi) + ", Bank: " + str(midi_bank) + ", Program: " + str(midi_prg))
		self.proc_cmd("select "+str(self.midi_chan)+' '+str(sfi)+' '+str(midi_bank)+' '+str(midi_prg))

	def load_soundfont(self, sf):
		if sf not in self.soundfont_index:
			self.soundfont_count=self.soundfont_count+1
			print("Load SoundFont " + sf + " => " + str(self.soundfont_count))
			self.proc_cmd("load " + self.soundfont_dir + '/' + sf, 20)
			self.soundfont_index[sf]=self.soundfont_count

	def unload_unused_soundfonts(self):
		#Make a copy of soundfont index and remove used soundfonts
		sf_unload=copy.copy(self.soundfont_index)
		for c,i in enumerate(self.bank_index):
			if self.bank_name[c] and self.bank_list[i][0] in sf_unload:
				#print("Skip "+self.bank_list[i][0]+"("+str(sf_unload[self.bank_list[i][0]])+")")
				del sf_unload[self.bank_list[i][0]]
		#Then, remove the remaining ;-)
		for sf,sfi in sf_unload.items():
			print("Unload SoundFont "+ str(sfi))
			self.proc_cmd("unload " + str(sfi),2)
			del self.soundfont_index[sf]

	def load_instr_config(self):
		super().load_instr_config()

#******************************************************************************
