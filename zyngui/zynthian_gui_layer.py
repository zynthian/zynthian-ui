#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Layer Selector Class
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
import sys
import logging
from json import JSONEncoder, JSONDecoder

# Zynthian specific modules
import zynautoconnect
from zyncoder import *
from . import zynthian_gui_config
from . import zynthian_gui_selector
from zyngine import zynthian_layer

#------------------------------------------------------------------------------
# Configure logging
#------------------------------------------------------------------------------

# Set root logging level
logging.basicConfig(stream=sys.stderr, level=zynthian_gui_config.log_level)

#------------------------------------------------------------------------------
# Zynthian Layer Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_layer(zynthian_gui_selector):

	def __init__(self):
		self.layers=[]
		self.curlayer=None
		self.add_layer_eng=None
		self.last_snapshot_fpath=None
		super().__init__('Layer', True)

	def reset(self):
		self.remove_all_layers()
		self.layers=[]
		self.curlayer=None
		self.index=0
		self.fill_list()

	def fill_list(self):
		self.list_data=[]
		#Add list of layers
		for i,layer in enumerate(self.layers):
			self.list_data.append((str(i+1),i,layer.get_presetpath()))
		#Add fixed entries
		self.list_data.append(('NEW',len(self.list_data),"New Layer"))
		self.list_data.append(('RESET',len(self.list_data),"Remove All"))
		self.list_data.append(('ALL_NOTES_OFF',len(self.list_data),"All Notes Off: PANIC!"))
		self.list_data.append(('ALL_SOUNDS_OFF',len(self.list_data),"All Sounds Off: PANIC!!!"))
		super().fill_list()

	def select_action(self, i):
		self.index=i
		if self.list_data[self.index][0]=='NEW':
			self.add_layer()
		elif self.list_data[self.index][0]=='RESET':
			self.reset()
		elif self.list_data[self.index][0]=='ALL_NOTES_OFF':
			zynthian_gui_config.zyngui.all_notes_off()
		elif self.list_data[self.index][0]=='ALL_SOUNDS_OFF':
			zynthian_gui_config.zyngui.all_sounds_off()
		else:
			self.curlayer=self.layers[self.index]
			zynthian_gui_config.zyngui.set_curlayer(self.curlayer)
			# If there is an preset selection for the active layer ...
			if self.curlayer.get_preset_name():
				zynthian_gui_config.zyngui.show_screen('control')
			else:
				zynthian_gui_config.zyngui.show_screen('bank')
				# If there is only one bank, jump to preset selection
				if len(self.curlayer.bank_list)==1:
					zynthian_gui_config.zyngui.screens['bank'].select_action(0)

	def next(self):
		self.index=self.index+1;
		if self.index>=len(self.layers):
			self.index=0
		self.select_listbox(self.index)
		self.select_action(self.index)

	def get_num_layers(self):
		return len(self.layers)

	def add_layer(self):
		self.add_layer_eng=None
		zynthian_gui_config.zyngui.show_modal('engine')

	def add_layer_engine(self, eng):
		self.add_layer_eng=eng
		if eng.nickname=='MD':
			self.add_layer_midich(None)
		elif eng.nickname=='BF':
			self.add_layer_midich(0,False)
			self.add_layer_midich(1,False)
			self.add_layer_midich(2,False)
			self.index=len(self.layers)-3
			self.select_action(self.index)
		else:
			zynthian_gui_config.zyngui.screens['midich'].set_mode("ADD")
			zynthian_gui_config.zyngui.show_modal('midich')

	def add_layer_midich(self, midich, select=True):
		if self.add_layer_eng:
			self.layers.append(zynthian_layer(self.add_layer_eng,midich,zynthian_gui_config.zyngui))
			self.fill_list()
			if select:
				self.index=len(self.layers)-1
				self.select_action(self.index)

	def remove_layer(self, i, cleanup_unused_engines=True):
		if i>=0 and i<len(self.layers):
			self.layers[i].reset()
			del self.layers[i]
			if len(self.layers)==0:
				self.index=0
				self.curlayer=None
			elif self.index>(len(self.layers)-1):
				self.index=len(self.layers)-1
				self.curlayer=self.layers[self.index]
			else:
				self.curlayer=self.layers[self.index-1]
			self.fill_list()
			self.set_selector()
			if cleanup_unused_engines:
				zynthian_gui_config.zyngui.screens['engine'].clean_unused_engines()

	def remove_all_layers(self, cleanup_unused_engines=True):
		while len(self.layers)>0:
			self.remove_layer(0, False)
		if cleanup_unused_engines:
			zynthian_gui_config.zyngui.screens['engine'].clean_unused_engines()

	#def refresh(self):
	#	self.curlayer.refresh()

	def set_midi_chan_preset(self, midich, preset_index):
		for layer in self.layers:
			mch=layer.get_midi_chan()
			if mch is None or mch==midich:
				#TODO => Pass PROGRAM CHANGE to Linuxsampler, MOD-UI, etc.
				layer.set_preset(preset_index,True)

	def set_select_path(self):
		self.select_path.set("Layer List")

	#----------------------------------------------------------------------------
	# Snapshot Save & Load
	#----------------------------------------------------------------------------

	def save_snapshot(self, fpath):
		try:
			snapshot={
				'index':self.index,
				'layers':[],
				'transpose':[],
				'monitored_engines':zynautoconnect.monitored_engines
			}
			#Layers info
			for layer in self.layers:
				snapshot['layers'].append(layer.get_snapshot())
			#Transpose info
			for i in range(0,16):
				snapshot['transpose'].append(zyncoder.lib_zyncoder.get_midi_filter_transpose(i))
			#JSON Encode
			json=JSONEncoder().encode(snapshot)
			logging.info("Saving snapshot %s => \n%s" % (fpath,json))
		except Exception as e:
			logging.error("Can't generate snapshot: %s" %e)
			return False
		try:
			with open(fpath,"w") as fh:
				fh.write(json)
				fh.flush()
				os.fsync(fh.fileno())
			self.last_snapshot_fpath=fpath
		except Exception as e:
			logging.error("Can't save snapshot '%s': %s" % (fpath,e))
			return False
		return True

	def load_snapshot(self, fpath):
		try:
			with open(fpath,"r") as fh:
				json=fh.read()
				logging.info("Loading snapshot %s => \n%s" % (fpath,json))
			self.last_snapshot_fpath=fpath
		except Exception as e:
			logging.error("Can't load snapshot '%s': %s" % (fpath,e))
			return False
		try:
			snapshot=JSONDecoder().decode(json)
			#Clean all layers
			self.remove_all_layers(False)
			#Create layers
			for lss in snapshot['layers']:
				engine=zynthian_gui_config.zyngui.screens['engine'].start_engine(lss['engine_nick'],1)
				self.layers.append(zynthian_layer(engine,lss['midi_chan'],zynthian_gui_config.zyngui))
			#Set active layer
			self.index=snapshot['index']
			self.curlayer=self.layers[self.index]
			zynthian_gui_config.zyngui.set_curlayer(self.curlayer)
			#Load layers
			i=0
			for lss in snapshot['layers']:
				self.layers[i].restore_snapshot(lss)
				i+=1
			#Fill layer list
			self.fill_list()
			#Remove unused engines
			zynthian_gui_config.zyngui.screens['engine'].clean_unused_engines()
			#Set Transpose
			if 'transpose' in snapshot:
				for i in range(0,16):
					zyncoder.lib_zyncoder.set_midi_filter_transpose(i,snapshot['transpose'][i])
			#Set CC-Map
			#TODO
			#Set Monitored Engines
			if 'monitored_engines' in snapshot:
				zynautoconnect.set_monitored_engines(snapshot['monitored_engines'])
			else:
				zynautoconnect.reset_monitored_engines()
			#Post action
			if self.list_data[self.index][0] in ('NEW','RESET'):
				self.index=0
				zynthian_gui_config.zyngui.show_screen('layer')
			else:
				self.select_action(self.index)
		except Exception as e:
			logging.error("Invalid snapshot format: %s" % e)
			return False
		return True

#------------------------------------------------------------------------------
