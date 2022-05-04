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

import sys
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


	def __init__(self):
		super().__init__()

		self.note_label = []
		self.cents_bar = []

		# Geometry vars
		self.note_fs = int(self.width/8)
		self.bar_width = int(self.width/80)
		self.bar_height = int(self.height/10)


	def create_gui(self):
		super().create_gui()

		# Create custom GUI elements
		x0 = self.width//2
		y0 = self.height//4
		self.note_label = self.mon_canvas.create_text(
			x0,
			self.height//2,
			#anchor=tkinter.NW,
			justify=tkinter.CENTER,
			width=4*self.note_fs,
			text="??",
			font=(zynthian_gui_config.font_family, self.note_fs),
			fill=zynthian_gui_config.color_panel_tx)
		self.cents_bar = self.mon_canvas.create_rectangle(
			x0-self.bar_width,
			y0,
			x0 + self.bar_width,
			y0 - self.bar_height,
			fill=zynthian_gui_config.color_on)
		# Scale axis for cents
		y0 -= self.bar_height//2
		self.mon_canvas.create_line(
			0,
			y0,
			self.width,
			y0,
			fill=zynthian_gui_config.color_tx_off)
		self.mon_canvas.create_line(
			x0,
			y0 + self.bar_height,
			x0,
			y0 - self.bar_height,
			fill=zynthian_gui_config.color_tx_off)
		dx = self.width//20
		dy = self.bar_height//2
		for i in range(1,10):
			x = x0 + i * dx
			self.mon_canvas.create_line(x, y0 + dy, x, y0 - dy, fill=zynthian_gui_config.color_tx_off)
			x = x0 - i * dx
			self.mon_canvas.create_line(x, y0 + dy, x, y0 - dy, fill=zynthian_gui_config.color_tx_off)


	def refresh_gui(self):
		# It should receive: rms, freq_out, octave, note, cent, accuracy
		if 'freq_out' not in self.monitors:
			return

		#for k,v in self.monitors.items():
		#	logging.debug("MONITOR {} = {}".format(k,v))

		#if monitors['rms']>-50.0 and monitors['accuracy']>0.0:
		if self.monitors['rms']>-50.0:
			try:
				note_name = "{}{}".format(self.note_names[int(self.monitors["note"])], int(self.monitors["octave"]))
			except:
				note_name = "??"
			try:
				x = int(self.width//2 + self.monitors['cent'])
			except:
				x = self.width//2

			y0 = self.height//4
			self.mon_canvas.itemconfigure(self.note_label, text=note_name)
			self.mon_canvas.coords(self.cents_bar,
				x - self.bar_width,
				y0,
				x + self.bar_width,
				y0 - self.bar_height)


#------------------------------------------------------------------------------
