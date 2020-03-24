#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Midi-Channel Selector Class
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

import sys
import tkinter
import logging

# Zynthian specific modules
from zyncoder import *
from . import zynthian_gui_config
from . import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian MIDI Channel Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_midi_chan(zynthian_gui_selector):

	def __init__(self):
		self.set_mode('ADD')
		super().__init__('Channel', True)

	def set_mode(self, mode, chan=None, chan_list=None):
		self.mode = mode

		if chan_list:
			self.chan_list = chan_list
		else:
			self.chan_list = range(16)

		if self.mode=='ADD':
			pass
		elif self.mode=='SET':
			self.index=chan
		elif self.mode=='CLONE':
			self.midi_chan=chan


	def fill_list(self):
		self.list_data=[]
		if self.mode=='ADD' or self.mode=='SET':
			for i in self.chan_list:
				self.list_data.append((str(i+1),i,"MIDI CH#"+str(i+1)))
		elif self.mode=='CLONE':
			for i in self.chan_list:
				if i==self.midi_chan:
					continue
				elif zyncoder.lib_zyncoder.get_midi_filter_clone(self.midi_chan, i):
					cc_to_clone = zyncoder.lib_zyncoder.get_midi_filter_clone_cc(self.midi_chan, i).nonzero()[0]
					self.list_data.append((str(i+1),i,"[x] CH#{}, CC {}".format(i+1, ' '.join(map(str, cc_to_clone)))))
					logging.debug("CC TO CLONE: {}".format(cc_to_clone))
				else:
					self.list_data.append((str(i+1),i,"[  ] CH#{}".format(i+1)))
		super().fill_list()


	def fill_listbox(self):
		super().fill_listbox()
		#if self.mode=='CLONE':
		#	self.highlight_cloned()


	# Highlight current channels to which is cloned to ...
	def highlight_cloned(self):
		i=0
		for item in self.list_data:
			if item[2][:2]=='[x':
				self.listbox.itemconfig(i, {'fg':zynthian_gui_config.color_hl})
			else:
				self.listbox.itemconfig(i, {'fg':zynthian_gui_config.color_panel_tx})

			i += 1


	def select_action(self, i, t='S'):
		selchan=self.list_data[i][1]

		if self.mode=='ADD':
			self.zyngui.screens['layer'].add_layer_midich(selchan)

		elif self.mode=='SET':
			root_layer=self.zyngui.screens['layer_options'].layer
			for layer in self.zyngui.screens['layer'].get_fxchain_layers(root_layer):
				layer.set_midi_chan(selchan)
				logging.info("LAYER {} -> MIDI CHANNEL = {}".format(layer.get_path(), selchan))

			self.zyngui.zynautoconnect_midi()
			self.zyngui.show_modal('layer_options')

		elif self.mode=='CLONE':

			if selchan!=self.midi_chan:
				if t=='S':
					if zyncoder.lib_zyncoder.get_midi_filter_clone(self.midi_chan, selchan):
						zyncoder.lib_zyncoder.set_midi_filter_clone(self.midi_chan, selchan, 0)
						self.update_list()
					else:
						zyncoder.lib_zyncoder.set_midi_filter_clone(self.midi_chan, selchan, 1)
						self.update_list()

					logging.info("CLONE MIDI CHANNEL {} => {}".format(self.midi_chan, selchan))

				elif t=='B':
					self.zyngui.screens['midi_cc'].set_clone_channels(self.midi_chan, selchan)
					self.zyngui.show_modal('midi_cc')


	def back_action(self):
		if self.mode=='SET' or self.mode=='CLONE':
			self.zyngui.show_modal('layer_options')
			return ''
		else:
			return None


	def set_select_path(self):
		if self.mode=='ADD' or self.mode=='SET':
			self.select_path.set("MIDI Channel")
		elif self.mode=='CLONE':
			self.select_path.set("Clone MIDI Channel {} to ...".format(self.midi_chan+1))

#------------------------------------------------------------------------------
