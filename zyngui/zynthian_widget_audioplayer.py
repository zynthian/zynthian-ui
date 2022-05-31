#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian Widget Class for "Zynthian Audio Player" (zynaudioplayer#one)
# 
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
# Copyright (C) 2015-2022 Brian Walton <riban@zynthian.org>
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
from PIL import Image, ImageTk
import os
import logging

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base

#------------------------------------------------------------------------------
# Zynthian Widget Class for "zynaudioplayer"
#------------------------------------------------------------------------------

class zynthian_widget_audioplayer(zynthian_widget_base.zynthian_widget_base):


	def __init__(self):
		super().__init__()
		self.refreshing = False
		self.play_pos = 0.0
		self.loop_start = 0.0
		self.loop_end = 1.0
		self.filename = ""
		self.duration = 0.0
		self.samplerate = 44100
		self.bg_color = "000000"
		self.waveform_color = "6070B0"


	def create_gui(self):
		super().create_gui()

		self.loading_text = self.mon_canvas.create_text(
			int(self.width / 2),
			int(self.height / 2),
			anchor=tkinter.CENTER,
			font=(
				zynthian_gui_config.font_family,
				int(1.5 * zynthian_gui_config.font_size)
			),
			justify=tkinter.CENTER,
			fill=zynthian_gui_config.color_tx_off,
			text="Creating\nwaveform..."
		)
		
		self.waveform = self.mon_canvas.create_image(
			0,
			0,
			anchor=tkinter.NW,
			state=tkinter.HIDDEN
		)

		self.play_line = self.mon_canvas.create_line(
			0,
			0,
			0,
			self.height,
			fill=zynthian_gui_config.color_on
		)

		self.loop_start_line = self.mon_canvas.create_line(
			0,
			0,
			0,
			self.height,
			fill=zynthian_gui_config.color_ml,
			state=tkinter.HIDDEN # loop markers currently disabled
		)

		self.loop_end_line = self.mon_canvas.create_line(
			self.width,
			0,
			self.width,
			self.height,
			fill=zynthian_gui_config.color_ml,
			state=tkinter.HIDDEN # loop markers currently disabled
		)

		self.info_text = self.mon_canvas.create_text(
			self.width-int(0.5 * zynthian_gui_config.font_size),
			self.height,
			anchor = tkinter.SE,
			justify=tkinter.RIGHT,
			width=self.width,
			font=(zynthian_gui_config.font_family, int(1.5 * zynthian_gui_config.font_size)),
			fill=zynthian_gui_config.color_panel_tx,
			text="00:00"
		)
		self.mon_canvas.bind("<Button-4>",self.cb_canvas_wheel)
		self.mon_canvas.bind("<Button-5>",self.cb_canvas_wheel)


	def refresh_gui(self):
		if self.refreshing:
			return
		self.refreshing = True
		try:
			pos = self.monitors["pos"]
			dur = self.monitors["duration"]
			if self.play_pos != pos:
				self.play_pos = pos
				if dur:
					x =  int(pos / dur * self.width)
				else:
					x = 0
				self.mon_canvas.coords(self.play_line, x, 0, x, self.height)

			loop_start = self.monitors["loop start"]
			if self.loop_start != loop_start:
				self.loop_start = loop_start
				if dur:
					x =  int(loop_start / dur * self.width)
				else:
					x = 0
				self.mon_canvas.coords(self.loop_start_line, x, 0, x, self.height)

			loop_end = self.monitors["loop end"]
			if self.loop_end != loop_end:
				self.loop_end = loop_end
				if dur:
					x =  int(loop_end / dur * self.width)
				else:
					x = 0
				self.mon_canvas.coords(self.loop_end_line, x, 0, x, self.height)

			if self.duration != dur:
				self.duration = dur
				self.mon_canvas.itemconfigure(self.info_text, text="{:02d}:{:02d}".format(int(dur / 60), int(dur % 60)), state=tkinter.NORMAL)
			if self.filename != self.monitors["filename"]:
				self.mon_canvas.itemconfigure(self.waveform, state=tkinter.HIDDEN)
				if(dur):
					self.mon_canvas.itemconfigure(self.loading_text, text="Creating\nwaveform...")
					waveform_png = "{}.png".format(self.monitors["filename"])
					self.filename = self.monitors["filename"]
					if not os.path.exists(waveform_png) or os.path.getmtime(self.filename) > os.path.getmtime(waveform_png):
						cmd = 'audiowaveform -i "{}" -o "{}" --split-channels -w {} -h {} --zoom auto --background-color {} --waveform-color {} --no-axis-labels > /dev/null 2>&1'.format(
							self.filename,
							waveform_png,
							self.width,
							self.height,
							self.bg_color,
							self.waveform_color
						)
						os.system(cmd)
					if os.path.exists(waveform_png):
						image = Image.open(waveform_png)
						self.img = ImageTk.PhotoImage(image.resize((self.width, self.height)))
						self.mon_canvas.itemconfigure(self.waveform, image=self.img, state=tkinter.NORMAL)
					else:
						self.mon_canvas.itemconfigure(self.loading_text, text="Cannot\ndisplay\nwaveform")
				else:
						self.mon_canvas.itemconfigure(self.loading_text, text="No\nfile\nloaded")

		except Exception as e:
			logging.error(e)
		
		self.refreshing = False


	def cb_canvas_wheel(self, event):
		try:
			if event.num == 5 or event.delta == -120:
				self.zyngui_control.layers[0].controllers_dict['position'].nudge(-1)
			if event.num == 4 or event.delta == 120:
				self.zyngui_control.layers[0].controllers_dict['position'].nudge(1)
		except Exception as e:
			logging.debug("Failed to change value")

#------------------------------------------------------------------------------
