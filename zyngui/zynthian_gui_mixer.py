#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Audio Mixer
# 
# Copyright (C) 2015-2020 Fernando Moyano <jofemodo@zynthian.org>
# Copyright (C) 2015-2020 Brian Walton <brian@riban.co.uk>
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
import logging
import tkinter
from datetime import datetime
from tkinter import font as tkFont
from PIL import Image, ImageTk

# Zynthian specific modules
from zyngine import zynthian_controller
from . import zynthian_gui_base
from . import zynthian_gui_config
from . import zynthian_gui_controller
from zynmixer import *

#------------------------------------------------------------------------------
# Zynthian Listbox Selector GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_mixer(zynthian_gui_base.zynthian_gui_base):

	def __init__(self):
		super().__init__()

		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.display_height - zynthian_gui_config.topbar_height
		self.fader_width = (self.width - 6 ) / 17
		self.fader_height = self.height - 20

		# Faders
		self.channel_faders = [None] * 17 # 16 channels + Master
		self.selected_fader = None

		# Fader Canvas
		self.main_canvas = tkinter.Canvas(self.main_frame,
			height=self.height,
			width=self.width,
			bd=0, highlightthickness=0,
			bg = zynthian_gui_config.color_bg)
		self.main_canvas.grid()


		# Draw faders
		offset = 1
		fill = 'green'
		for fader in range(17):
			label = "Layer %d" % fader
			if fader > 15:
				offset = 4
				fill = 'red'
				label = 'Master'
			fader_bg = self.main_canvas.create_rectangle(offset + fader * self.fader_width, 1, offset + self.fader_width * (fader + 1) - 1, self.fader_height, fill='grey', width=0)
			self.channel_faders[fader] = self.main_canvas.create_rectangle(offset + fader * self.fader_width, 1, offset + self.fader_width * (fader + 1) - 1, self.fader_height, fill=fill, width=0)
			self.main_canvas.tag_bind(self.channel_faders[fader], "<ButtonPress-1>", self.on_fader_press)
			self.main_canvas.tag_bind(fader_bg, "<ButtonPress-1>", self.on_fader_press)
			self.main_canvas.tag_bind(self.channel_faders[fader], "<ButtonRelease-1>", self.on_fader_release)
			self.main_canvas.tag_bind(fader_bg, "<ButtonRelease-1>", self.on_fader_release)
			self.main_canvas.tag_bind(self.channel_faders[fader], "<B1-Motion>", self.on_fader_motion)
			self.main_canvas.tag_bind(fader_bg, "<B1-Motion>", self.on_fader_motion)
			self.main_canvas.create_text(offset + int(self.fader_width * (fader + 0.5)), self.fader_height + 10, text=label)
			self.draw_fader(fader)
		self.main_canvas.create_line(0, self.fader_height * 0.2, self.width, self.fader_height * 0.2, fill="white")


	# Function to set fader values
	#	fader: Index of fader
	#	value: Fader value (0..1)
	def set_fader(self, fader, value):
		if fader > len(self.channel_faders) or value < 0 or value > 1:
			return
		zynmixer.set_level(fader, value)
		self.draw_fader(fader)


	# Function to draw fader
	#	fader: index of fader
	def draw_fader(self, fader):
		offset = 1
		if fader > 15: offset = 4
		self.main_canvas.coords(self.channel_faders[fader], offset + fader * self.fader_width, self.fader_height * (1 - zynmixer.get_level(fader)), offset + (fader + 1) * self.fader_width - 1, self.fader_height)


	# Function to handle fader press
	#	event: Mouse event
	def on_fader_press(self, event):
		self.drag_start = event
		try:
			sel = int(self.main_canvas.find_withtag(tkinter.CURRENT)[0])
		except:
			return
		for fader in range(len(self.channel_faders)):
			if sel == self.channel_faders[fader]:
				self.selected_fader = fader
				return


	# Function to handle fader release
	#	event: Mouse event
	def on_fader_release(self, event):
		pass


	# Function to handle fader drag
	#	event: Mouse event
	def on_fader_motion(self, event):
		if self.selected_fader == None:
			return
		level = zynmixer.get_level(self.selected_fader) + (self.drag_start.y - event.y) / self.fader_height
		if level > 1: level = 1
		if level < 0: level = 0
		self.drag_start = event
		self.set_fader(self.selected_fader, level)


	# Function to refresh loading animation
	def refresh_loading(self):
		pass


	# Function to handle zyncoder polling
	def zyncoder_read(self):
		pass