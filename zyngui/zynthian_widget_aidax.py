#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian Widget Class for "x42 Instrument Tuner" (tuna#one)
# 
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
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
from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base

#------------------------------------------------------------------------------
# Zynthian Widget Class for "x42 Instrument Tuner"
#------------------------------------------------------------------------------

class zynthian_widget_aidax(zynthian_widget_base.zynthian_widget_base):


	def __init__(self, parent):
		super().__init__(parent)

		# Geometry vars set accurately during resize
		self.bar_width = 1
		self.bar_height = 1
		self.x0 = 0
		self.y0 = 0

		self.widget_canvas = tkinter.Canvas(self,
			highlightthickness=0,
			relief='flat',
			bg=zynthian_gui_config.color_bg)
		self.widget_canvas.grid(sticky='news')

		# Create custom GUI elements (position and size set when canvas is grid and size applied)

		self.input_level_bg = self.widget_canvas.create_rectangle(
			0, 0, 0, 0,
			fill="grey")
		self.input_level = self.widget_canvas.create_rectangle(
			0, 0, 0, 0,
			fill="green")
		self.output_level_bg = self.widget_canvas.create_rectangle(
			0, 0, 0, 0,
			fill="grey")
		self.output_level = self.widget_canvas.create_rectangle(
			0, 0, 0, 0,
			fill="green")
		self.input_label = self.widget_canvas.create_text(
			0, 0,
			fill="white",
			text='Input',
			anchor="w"
			)
		self.output_label = self.widget_canvas.create_text(
			0, 0,
			fill="white",
			text='Output',
			anchor="w"
			)


	def on_size(self, event):
		if event.width == self.width and event.height == self.height:
			return
		super().on_size(event)

		self.bar_width = round(0.8 * self.width)
		self.bar_height = round(0.1 * self.height)
		self.x0 = round(0.1 * self.width)
		self.y0 = round(0.2 * self.height)
		self.widget_canvas.coords(self.input_level_bg, self.x0, self.y0, self.x0 + self.bar_width, self.y0 + self.bar_height)
		self.widget_canvas.coords(self.output_level_bg, self.x0, self.y0 + self.bar_height + 2, self.x0 + self.bar_width, self.y0 + self.bar_height * 2 + 2)
		self.widget_canvas.coords(self.input_label, self.x0 + 2, self.y0 + self.bar_height // 2)
		self.widget_canvas.coords(self.output_label, self.x0 + 2, self.y0 + round(1.5 * self.bar_height))
		self.widget_canvas.itemconfig(self.input_label, font=(zynthian_gui_config.font_family, self.bar_height // 2))
		self.widget_canvas.itemconfig(self.output_label, font=(zynthian_gui_config.font_family, self.bar_height // 2))
		self.widget_canvas.grid(row=0, column=0, sticky='news')

	def refresh_gui(self):
		if 'MeterIn' in self.monitors:
			x = int(self.x0 + self.bar_width * min(1, self.monitors['MeterIn']))
			self.widget_canvas.coords(self.input_level, self.x0, self.y0, x, self.y0 + self.bar_height)
			if self.monitors['MeterIn'] > 1:
				self.widget_canvas.itemconfig(self.input_level, fill="red")
			elif self.monitors['MeterIn'] > 0.85:
				self.widget_canvas.itemconfig(self.input_level, fill="orange")
			else:
				self.widget_canvas.itemconfig(self.input_level, fill="green")
		if 'MeterOut' in self.monitors:
			x = int(self.x0 + self.bar_width * min(1, self.monitors['MeterOut']))
			self.widget_canvas.coords(self.output_level, self.x0, self.y0 + self.bar_height + 2, x, self.y0 + self.bar_height * 2 + 2)
			if self.monitors['MeterOut'] > 1:
				self.widget_canvas.itemconfig(self.output_level, fill="red")
			elif self.monitors['MeterOut'] > 0.85:
				self.widget_canvas.itemconfig(self.output_level, fill="orange")
			else:
				self.widget_canvas.itemconfig(self.output_level, fill="green")
		if 'ModelInSize' in self.monitors:
			pass


#------------------------------------------------------------------------------
