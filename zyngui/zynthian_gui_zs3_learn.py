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
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector
from zyngui.zynthian_gui_controller import zynthian_gui_controller

#------------------------------------------------------------------------------
# Zynthian Sub-SnapShot (ZS3) MIDI-learn GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_zs3_learn(zynthian_gui_selector):

	def __init__(self):
		super().__init__('Program', True)
		self.index = 0


	def fill_list(self):
		self.list_data=[]

		#Add "Waiting for Program Change" message
		self.list_data.append(('None',None,"Waiting for Program Change ..."))
		self.list_data.append((None,None,"-----------------------------"))

		#Add list of programs
		try:
			midich = self.zyngui.curlayer.get_midi_chan()
			zs3_indexes = self.zyngui.screens['layer'].get_midi_chan_zs3_used_indexes(midich)
			#select_zs3_idx = self.zyngui.screens['layer'].get_last_zs3_index(midich)
			for i in range(128):
				if i in zs3_indexes:
					zs3_index = i
					label = "used"
				else:
					zs3_index = None
					label = "free"
				zs3_title = "Program {:03d}: {}".format(i, label)
				self.list_data.append((i ,zs3_index, zs3_title))
		except Exception as e:
			logging.error(e)

		super().fill_list()


	def fill_listbox(self):
		super().fill_listbox()
		self.listbox.itemconfig(0, {'fg':zynthian_gui_config.color_hl})


	def set_selector(self):
		if self.zselector:
			self.zselector_ctrl.set_options({ 'symbol':self.selector_caption, 'name':self.selector_caption, 'short_name':self.selector_caption, 'midi_cc':0, 'value_max':130, 'value':self.index })
			self.zselector.config(self.zselector_ctrl)
			self.zselector.show()
		else:
			self.zselector_ctrl=zynthian_controller(None,self.selector_caption,self.selector_caption,{ 'midi_cc':0, 'value_max':130, 'value':self.index })
			self.zselector=zynthian_gui_controller(zynthian_gui_config.select_ctrl,self.main_frame,self.zselector_ctrl)


	def select_action(self, i, t='S'):
		self.index = i
		zs3_index = self.list_data[self.index][1]
		midi_prog = self.list_data[self.index][0]
		if isinstance(zs3_index, int):
			midich = self.zyngui.curlayer.get_midi_chan()
			if t=='S':
				self.zyngui.screens['layer'].set_midi_chan_zs3(midich, zs3_index)
				self.zyngui.close_screen()
				self.zyngui.exit_midi_learn_mode()
			elif t=='B':
				self.zyngui.screens['zs3_options'].config(midich, zs3_index)
				self.zyngui.show_modal('zs3_options')
		elif isinstance(midi_prog, int):
			midich = self.zyngui.curlayer.get_midi_chan()
			self.zyngui.screens['layer'].save_midi_chan_zs3(midich, midi_prog)
			self.zyngui.close_screen()
			self.zyngui.exit_midi_learn_mode()


	def back_action(self):
		self.zyngui.exit_midi_learn_mode()
		return False


	def set_select_path(self):
		if self.zyngui.curlayer:
			self.select_path.set(self.zyngui.curlayer.get_basepath() + " /PROG MIDI-Learn")
		else:
			self.select_path.set("PROG MIDI-Learn")


#-------------------------------------------------------------------------------
