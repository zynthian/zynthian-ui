#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI ZS3 learn screen
# 
# Copyright (C) 2018 Fernando Moyano <jofemodo@zynthian.org>
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
from zyngine import zynthian_controller
from . import zynthian_gui_config
from . import zynthian_gui_selector
from . import zynthian_gui_controller

#------------------------------------------------------------------------------
# Zynthian Sub-SnapShot (ZS3) MIDI-learn GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_zs3_learn(zynthian_gui_selector):

	def __init__(self):
		super().__init__('Program', True)


	def fill_list(self):
		self.list_data=[]

		#Add list of programs
		midich=self.zyngui.curlayer.get_midi_chan()
		zs3_indexes=self.zyngui.screens['layer'].get_midi_chan_zs3_used_indexes(midich)
		self.num_programs=len(zs3_indexes)
		for i, zs3_index in enumerate(zs3_indexes):
			zs3_title="Program {}".format(zs3_index)
			self.list_data.append((zs3_index,len(self.list_data),zs3_title))

		#Add "Waiting for Program Change" message
		if len(self.list_data)>0:
			self.list_data.append((None,len(self.list_data),"-----------------------------"))
		self.list_data.append(('None',len(self.list_data),"Waiting for Program Change ..."))

		super().fill_list()


	def fill_listbox(self):
		super().fill_listbox()
		if self.num_programs>0:
			i = self.num_programs + 1
		else:
			i=0
		self.listbox.itemconfig(i, {'fg':zynthian_gui_config.color_hl})


	def set_selector(self):
		if self.zselector:
			self.zselector_ctrl.set_options({ 'symbol':self.selector_caption, 'name':self.selector_caption, 'short_name':self.selector_caption, 'midi_cc':0, 'value_max':self.num_programs, 'value':self.index })
			self.zselector.config(self.zselector_ctrl)
			self.zselector.show()
		else:
			self.zselector_ctrl=zynthian_controller(None,self.selector_caption,self.selector_caption,{ 'midi_cc':0, 'value_max':self.num_programs, 'value':self.index })
			self.zselector=zynthian_gui_controller(zynthian_gui_config.select_ctrl,self.main_frame,self.zselector_ctrl)


	def select_action(self, i, t='S'):
		self.index=i
		zs3_index=self.list_data[self.index][0]
		if isinstance(zs3_index, int):
			midich=self.zyngui.curlayer.get_midi_chan()
			if t=='S':
				self.zyngui.screens['layer'].set_midi_chan_zs3(midich, zs3_index)
				self.zyngui.exit_midi_learn_mode()
			elif t=='B':
				self.zyngui.screens['zs3_options'].config(midich, zs3_index)
				self.zyngui.show_modal('zs3_options')


	def back_action(self):
		self.zyngui.exit_midi_learn_mode()
		return ''


	def set_select_path(self):
		if self.zyngui.curlayer:
			self.select_path.set(self.zyngui.curlayer.get_basepath() + " /PROG MIDI-Learn")
		else:
			self.select_path.set("PROG MIDI-Learn")


#-------------------------------------------------------------------------------
