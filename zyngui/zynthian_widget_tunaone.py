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

class zynthian_widget_tunaone(zynthian_widget_base.zynthian_widget_base):

	note_names = [ 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B' ]


	def __init__(self, parent):
		super().__init__(parent)

		self.note_label = []

		# Geometry vars set accurately during resize
		self.note_fs = 1
		self.bar_width = 1
		self.bar_height = 1

		self.widget_canvas = tkinter.Canvas(self,
			highlightthickness=0,
			relief='flat',
			bg=zynthian_gui_config.color_bg)
		self.widget_canvas.grid(sticky='news')

		# Create custom GUI elements (position and size set when canvas is grid and size applied)

		self.note_label = self.widget_canvas.create_text(
			0,
			0,
			#anchor=tkinter.NW,
			justify=tkinter.CENTER,
			width=4 * self.note_fs,
			text="??",
			font=(zynthian_gui_config.font_family, self.note_fs),
			fill=zynthian_gui_config.color_panel_tx)
		self.flat_bar = self.widget_canvas.create_rectangle(
			0, 0, 0, 0,
			fill=zynthian_gui_config.color_on)
		self.sharp_bar = self.widget_canvas.create_rectangle(
			0, 0, 0, 0,
			fill=zynthian_gui_config.color_hl)
		# Scale axis for cents
		self.axis_y = self.widget_canvas.create_line(
			0, 0, 0, 0,
			width=3,
			fill=zynthian_gui_config.color_tx_off)
		self.axis_x = self.widget_canvas.create_line(
			0, 0, 0, 0,
			fill=zynthian_gui_config.color_tx_off)


	def on_size(self, event):
		if event.width == self.width and event.height == self.height:
			return
		super().on_size(event)
		self.widget_canvas.configure(width=self.width, height=self.height)

		self.note_fs = round(self.width / 8)
		self.bar_width = round(self.width / 160)
		self.bar_height = round(self.height / 10)
		self.x0 = self.width // 2
		self.y0 = self.height // 4
		self.widget_canvas.coords(self.note_label, self.x0, int(0.7 * self.height))
		self.widget_canvas.itemconfigure(self.note_label, width=4 * self.note_fs, font=(zynthian_gui_config.font_family, self.note_fs))
		self.widget_canvas.coords(self.axis_x, 0, self.y0, self.width, self.y0)
		self.widget_canvas.coords(self.axis_y, self.x0, self.y0 + self.bar_height, self.x0, self.y0 - self.bar_height)
		self.widget_canvas.coords(self.flat_bar, 0, self.y0 + self.bar_height, self.x0, self.y0 - self.bar_height)
		self.widget_canvas.coords(self.sharp_bar, self.x0, self.y0 + self.bar_height, self.width, self.y0 - self.bar_height)
		self.cent_dx = self.width / 100
		dx = self.width // 20
		dy = int(0.6 * self.bar_height)
		self.widget_canvas.delete('axis')
		for i in range(1, 10):
			x = self.x0 + i * dx
			self.widget_canvas.create_line(x, self.y0 + dy, x, self.y0 - dy, fill=zynthian_gui_config.color_tx_off, tags='axis')
			x = self.x0 - i * dx
			self.widget_canvas.create_line(x, self.y0 + dy, x, self.y0 - dy, fill=zynthian_gui_config.color_tx_off, tags='axis')
		self.widget_canvas.grid(row=0, column=0, sticky='news')


	def refresh_gui(self):
		# It should receive: rms, freq_out, octave, note, cent, accuracy
		if 'freq_out' not in self.monitors:
			return

		#for k,v in self.monitors.items():
		#	logging.debug("MONITOR {} = {}".format(k,v))

		#if monitors['rms']>-50.0 and monitors['accuracy']>0.0:
		if self.monitors['rms'] > -50.0:
			try:
				note_name = "{}{}".format(self.note_names[int(self.monitors["note"])], int(self.monitors["octave"]))
			except:
				note_name = "??"
			try:
				x = int(self.x0 + self.cent_dx * self.monitors['cent'])
			except:
				x = self.x0

			if int(self.monitors['cent']) == 0:
				self.widget_canvas.itemconfigure(self.note_label, text=note_name, state=tkinter.NORMAL, fill=zynthian_gui_config.color_hl)
			else:
				self.widget_canvas.itemconfigure(self.note_label, text=note_name, state=tkinter.NORMAL, fill=zynthian_gui_config.color_panel_tx)
			self.widget_canvas.itemconfigure(self.flat_bar, state=tkinter.NORMAL)
			self.widget_canvas.itemconfigure(self.sharp_bar, state=tkinter.NORMAL)
			self.widget_canvas.coords(self.flat_bar, 0, self.y0 + self.bar_height, x, self.y0 - self.bar_height)
			self.widget_canvas.coords(self.sharp_bar, x, self.y0 + self.bar_height, self.width, self.y0 - self.bar_height)
		else:
			self.widget_canvas.itemconfigure(self.flat_bar, state=tkinter.HIDDEN)
			self.widget_canvas.itemconfigure(self.sharp_bar, state=tkinter.HIDDEN)
			self.widget_canvas.itemconfigure(self.note_label, state=tkinter.HIDDEN)


#------------------------------------------------------------------------------
