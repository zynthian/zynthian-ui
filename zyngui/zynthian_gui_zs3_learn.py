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
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian Sub-SnapShot (ZS3) MIDI-learn GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_zs3_learn(zynthian_gui_selector):

	def __init__(self):
		super().__init__('Program', True)
		self.index = 0

		self.zs3_waiting_label = tkinter.Label(self.main_frame,
			text = 'Waiting for MIDI Program Change...',
			font=(zynthian_gui_config.font_family, zynthian_gui_config.font_size-2),
			fg = zynthian_gui_config.color_ml,
			bg = zynthian_gui_config.color_panel_bg
		)
		if self.wide:
			padx = (0,2)
		else:
			padx = (2,2)
		self.zs3_waiting_label.grid(row=zynthian_gui_config.layout['list_pos'][0] + 4, column=zynthian_gui_config.layout['list_pos'][1], padx=padx, sticky='ew')


	def show(self):
		self.zyngui.enter_midi_learn()
		super().show()


	def hide(self):
		if self.shown:
			self.zyngui.exit_midi_learn()
			super().hide()


	def fill_list(self):
		self.list_data=[]
		self.list_data.append(('SAVE_ZS3', None, "Save as new ZS3"))

		#Add list of programs
		if len(self.zyngui.screens['layer'].learned_zs3)>0:
			self.list_data.append((None, None, "> SAVED ZS3s"))
		for i, state in enumerate(self.zyngui.screens['layer'].learned_zs3):
			if state['midi_learn_prognum'] is not None:
				if zynthian_gui_config.midi_single_active_channel:
					title = "{} -> PR#{}".format(state['zs3_title'], state['midi_learn_prognum'])
				else:
					title = "{} -> CH#{}:PR#{}".format(state['zs3_title'], state['midi_learn_chan'], state['midi_learn_prognum'])
			else:
				title = state['zs3_title']
			self.list_data.append((i, state, title))
			if self.index == 0 and i == self.zyngui.screens['layer'].get_last_zs3_index():
				self.index = i + 2 # Skip "Save" and separator 

		super().fill_list()


	def select_action(self, i, t='S'):
		self.index = i
		zs3_index = self.list_data[self.index][0]
		if isinstance(zs3_index, int):
			if t  == 'S':
				self.zyngui.exit_midi_learn()
				self.zyngui.screens['layer'].restore_zs3(zs3_index)
				self.zyngui.close_screen()
			elif t == 'B':
				self.zyngui.exit_midi_learn()
				self.zyngui.screens['zs3_options'].config(zs3_index)
				self.zyngui.show_screen('zs3_options')
				return True
		elif isinstance(zs3_index, str):
			if zs3_index == "SAVE_ZS3":
				self.zyngui.exit_midi_learn()
				self.zyngui.screens['layer'].save_zs3()
				self.zyngui.close_screen()
				return True


	def set_select_path(self):
		if self.zyngui.current_processor:
			self.select_path.set(self.zyngui.current_processor.get_basepath() + "/PROG MIDI-Learn")
		else:
			self.select_path.set("PROG MIDI-Learn")


	def back_action(self):
		self.zyngui.exit_midi_learn()
		return False


#-------------------------------------------------------------------------------
