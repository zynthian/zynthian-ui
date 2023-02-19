#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Step-Sequencer Track Editor Class
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <brian@riban.co.uk>
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

import tkinter
import logging

# Zynthian specific modules
from . import zynthian_gui_base
from zyngui import zynthian_gui_config
from zynlibs.zynseq import zynseq


# Class implements track editor
class zynthian_gui_track_editor(zynthian_gui_base.zynthian_gui_base):

	# Function to initialise class
	def __init__(self):
		logging.getLogger('PIL').setLevel(logging.WARNING)

		super().__init__()

		# ListBoxs
		self.track_patterns_listbox = tkinter.Listbox(self.main_frame,
			font=zynthian_gui_config.font_listbox,
			bd=7,
			highlightthickness=0,
			relief='flat',
			#bg=zynthian_gui_config.color_panel_bg,
			bg='yellow',
			fg=zynthian_gui_config.color_panel_tx,
			selectbackground=zynthian_gui_config.color_ctrl_bg_on,
			selectforeground=zynthian_gui_config.color_ctrl_tx,
			selectmode=tkinter.SINGLE)

		self.avail_patterns_listbox = tkinter.Listbox(self.main_frame,
			font=zynthian_gui_config.font_listbox,
			bd=7,
			highlightthickness=0,
			relief='flat',
			bg='blue',
			fg=zynthian_gui_config.color_panel_tx,
			selectbackground=zynthian_gui_config.color_ctrl_bg_on,
			selectforeground=zynthian_gui_config.color_ctrl_tx,
			selectmode=tkinter.SINGLE)

		self.pattern_groups_listbox = tkinter.Listbox(self.main_frame,
			font=zynthian_gui_config.font_listbox,
			bd=7,
			highlightthickness=0,
			relief='flat',
			bg='green',
			fg=zynthian_gui_config.color_panel_tx,
			selectbackground=zynthian_gui_config.color_ctrl_bg_on,
			selectforeground=zynthian_gui_config.color_ctrl_tx,
			selectmode=tkinter.SINGLE)

		# Layout
		self.track_patterns_listbox.grid(row=0, column=0, rowspan=4, sticky="news")
		self.avail_patterns_listbox.grid(row=0, column=1, sticky="news")
		self.pattern_groups_listbox.grid(row=1, column=1, sticky="news")


		self.set_title("Track Editor")


	def build_view(self):
		self.fill_list()
		self.set_selector()
		self.set_select_path()


	def fill_patterns_list(self):
		self.avail_patterns_listbox.delete(0, tkinter.END)
		
		if not self.list_data:
			self.list_data=[]
		for i, item in enumerate(self.list_data):
			self.listbox.insert(tkinter.END, item[2])
			if item[0] is None:
				self.listbox.itemconfig(i, {'bg':zynthian_gui_config.color_panel_hl,'fg':zynthian_gui_config.color_tx_off})
			last_param = item[len(item) - 1]
			if isinstance(last_param, dict) and 'format' in last_param:
				self.listbox.itemconfig(i, last_param['format'])

		self.select()
		self.last_index_change_ts = datetime.min

	def show_pattern_editor(self):
		pass #TODO: Implement show_pattern_editor