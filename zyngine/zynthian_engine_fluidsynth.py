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
# For a full copy of the GNU General Public License see the doc/GPL.txt file.
# 
#******************************************************************************

from zyngine.zynthian_engine import *

#------------------------------------------------------------------------------
# FluidSynth Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_fluidsynth(zynthian_engine):
	name="FluidSynth"
	nickname="FS"

	command=None
	#synth.midi-bank-select => mma
	soundfont_dir="./data/soundfonts/sf2"
	bank_id=0

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
		self.command=("/usr/bin/fluidsynth", "-p", "fluidsynth", "-a", self.audio_driver, "-m", mdriver ,"-g", "1", "-j")

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
		print('Getting Instrument List for ' + self.bank_name[self.midi_chan])
		lines=self.proc_cmd("inst " + str(self.bank_id))
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
		if self.bank_id>0:
			self.proc_cmd("unload " + str(self.bank_id),2)
		self.proc_cmd("load " + self.soundfont_dir + '/' + self.bank_list[i][0],20)
		self.bank_id=self.bank_id+1
		print('Bank Selected: ' + self.bank_name[self.midi_chan] + ' (' + str(i)+')')
		self.load_instr_list()

	def load_instr_config(self):
		super().load_instr_config()

#******************************************************************************
