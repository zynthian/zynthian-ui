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
			bg='orange',
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


		self.selected_group = ""
		self.selected_pattern = 1
		self.sequence = 0
		self.track = 0
		self.set_title("Track Editor")


	def build_view(self):
		self.fill_avail_patterns_list()
		self.fill_groups_list()
		self.fill_track_patterns_list()


	def get_pattern_name(self, pattern):
		pattern_name = self.zyngui.zynseq.get_pattern_name(pattern)
		if pattern_name:
			return f"{pattern} {pattern_name}"
		else:
			return f"Pattern {pattern}"


	def fill_avail_patterns_list(self):
		self.avail_patterns_listbox.delete(0, tkinter.END)
		self.pattern_list = []
		patterns_in_group = self.zyngui.zynseq.get_patterns_in_group(self.selected_group)
		if patterns_in_group:
			for i in patterns_in_group.split(","):
				index = int(i)
				value = (index, self.get_pattern_name(index))
				self.pattern_list.append(value)
				self.avail_patterns_listbox.insert(tkinter.END, f'{value[1]}')


	def fill_track_patterns_list(self):
		self.track_patterns_listbox.delete(0, tkinter.END)
		self.track_pattern_list = []
		patterns_in_track = self.zyngui.zynseq.get_patterns_in_track(self.zyngui.zynseq.bank, self.sequence, self.track)
		if patterns_in_track:
			dur = 0
			for pair in patterns_in_track.split(","):
				pos, pattern = pair.split(":")
				pos = int(pos)
				pattern = int(pattern)
				if dur < pos:
					self.track_pattern_list.append((pos, -1))
					self.track_patterns_listbox.insert(tkinter.END, f"SPACER ({pos - dur})")
				self.track_pattern_list.append((pos, pattern))
				self.track_patterns_listbox.insert(tkinter.END, f"{self.get_pattern_name(pattern)}")
				dur = pos + self.zyngui.zynseq.libseq.getPatternDuration(pattern)


	def fill_groups_list(self):
		self.pattern_groups_listbox.delete(0, tkinter.END)
		self.pattern_groups_listbox.insert(tkinter.END, "ALL PATTERNS")
		for group in self.zyngui.zynseq.get_pattern_groups().split(','):
			self.pattern_groups_listbox.insert(tkinter.END, f'{group}')


	def show_pattern_editor(self):
		pass #TODO: Implement show_pattern_editor