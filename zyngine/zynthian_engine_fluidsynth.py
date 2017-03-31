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
from . import zynthian_controller

#------------------------------------------------------------------------------
# FluidSynth Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_fluidsynth(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Controllers & Screens
	# ---------------------------------------------------------------------------

	# Controller Screens
	_ctrl_screens=[
		['main',['volume','expression','pan','sustain']],
		['effects',['volume','modulation','reverb','chorus']]
	]

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__(zyngui)
		self.name="FluidSynth"
		self.nickname="FS"
		self.command=("/usr/bin/fluidsynth", "-p", "fluidsynth", "-a", "jack", "-m", "jack" ,"-g", "1", "-j", "-o", "synth.midi-bank-select", "mma", "synth.cpu-cores", "3")

		self.soundfont_dirs=[
			('_', os.getcwd()+"/data/soundfonts/sf2"),
			('MY', os.getcwd()+"/my-data/soundfonts/sf2")
		]

		self.start(True)
		self.reset()

	def reset(self):
		super().reset()
		self.soundfont_count=0
		self.soundfont_index={}
		self.clear_midi_routes()
		self.unload_unused_soundfonts()

	def stop(self):
		self.proc_cmd("quit",2)
		super().stop()

	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------

	def add_layer(self, layer):
		super().add_layer(layer)
		layer.part_i=self.get_free_parts()[0]
		logging.debug("ADD LAYER => PART %s" % layer.part_i)

	def del_layer(self, layer):
		super().del_layer(layer)
		self.set_all_midi_routes()
		self.unload_unused_soundfonts()

	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	def set_midi_chan(self, layer):
		self.set_all_midi_routes()

	# ---------------------------------------------------------------------------
	# Bank Management
	# ---------------------------------------------------------------------------

	def get_bank_list(self, layer=None):
		return self.get_filelist(self.soundfont_dirs,"sf2")

	def set_bank(self, layer, bank):
		if self.load_soundfont(bank[0]):
			self.unload_unused_soundfonts()

	# ---------------------------------------------------------------------------
	# Bank Management
	# ---------------------------------------------------------------------------

	def get_preset_list(self, bank):
		logging.info("Getting Preset List for %s" % bank[2])
		preset_list=[]
		sfi=self.soundfont_index[bank[0]]
		lines=self.proc_cmd("inst %d" % sfi)
		for f in lines:
			try:
				prg=int(f[4:7])
				bank_msb=int(f[0:3])
				bank_lsb=int(bank_msb/128)
				bank_msb=bank_msb%128
				title=str.replace(f[8:-1], '_', ' ')
				preset_list.append((f,[bank_msb,bank_lsb,prg],title))
			except:
				pass
		return preset_list

	def set_preset(self, layer, preset):
		bi=layer.bank_info
		if bi:
			sf=bi[0]
			if sf and sf in self.soundfont_index:
				sfi=self.soundfont_index[sf]
				midi_bank=preset[1][0]+preset[1][1]*128
				midi_prg=preset[1][2]
				logging.debug("Set Preset => Layer: %d, SoundFont: %d, Bank: %d, Program: %d" % (layer.part_i,sfi,midi_bank,midi_prg))
				self.proc_cmd("select %d %d %d %d" % (layer.part_i,sfi,midi_bank,midi_prg))
				self.set_all_midi_routes()
			else:
				logging.warning("Can't set Instrument before loading SoundFont")

	# ---------------------------------------------------------------------------
	# Specific functions
	# ---------------------------------------------------------------------------

	def get_free_parts(self):
		free_parts=list(range(0,16))
		for layer in self.layers:
			try:
				free_parts.remove(layer.part_i)
			except:
				pass
		return free_parts

	def load_soundfont(self, sf):
		if sf not in self.soundfont_index:
			self.soundfont_count=self.soundfont_count+1
			logging.info("Load SoundFont => %s (%d)" % (sf,self.soundfont_count))
			self.proc_cmd("load \"%s\"" % sf, 20)
			self.soundfont_index[sf]=self.soundfont_count
			return self.soundfont_count	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	def set_midi_channel(self, layer):
		if layer.part_i is not None:
			liblo.send(self.osc_target, "/part%d/Prcvchn" % layer.part_i, layer.get_midi_chan())


	def unload_unused_soundfonts(self):
		#Make a copy of soundfont index and remove used soundfonts
		sf_unload=copy.copy(self.soundfont_index)
		for layer in self.layers:
			bi=layer.bank_info
			if bi[2] and bi[0] in sf_unload:
				#print("Skip "+bi[0]+"("+str(sf_unload[bi[0]])+")")
				del sf_unload[bi[0]]
		#Then, remove the remaining ;-)
		for sf,sfi in sf_unload.items():
			logging.info("Unload SoundFont => %d" % sfi)
			self.proc_cmd("unload %d" % sfi,2)
			del self.soundfont_index[sf]

	def set_layer_midi_routes(self, layer):
		if layer.part_i is not None:
			midich=layer.get_midi_chan()
			self.proc_cmd("router_begin note\nrouter_chan %d %d 0 %d\nrouter_end" % (midich,midich,layer.part_i))
			self.proc_cmd("router_begin cc\nrouter_chan %d %d 0 %d\nrouter_end" % (midich,midich,layer.part_i))

	def set_all_midi_routes(self):
		self.clear_midi_routes()
		for layer in self.layers:
			self.set_layer_midi_routes(layer)

	def clear_midi_routes(self):
		self.proc_cmd("router_clear")

#******************************************************************************
