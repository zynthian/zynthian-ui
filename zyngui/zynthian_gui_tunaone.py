#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Class for Instrument Tuner "tuna#one"
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
import threading
from time import sleep
from threading  import Thread, Lock

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui import zynthian_gui_control

#------------------------------------------------------------------------------
# Zynthian Instrument Tuner GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_tunaone(zynthian_gui_control.zynthian_gui_control):

	note_names = [ 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B' ]


	def __init__(self):
		super().__init__('Tuna One')

		self.note_label = []
		self.cents_bar = []
		self.mon_thread = None

		# Geometry vars
		self.note_fs = int(self.lb_width/8)
		self.bar_width = int(self.lb_width/80)
		self.bar_height = int(self.height/10)

		# Create Canvas
		self.mon_canvas= tkinter.Canvas(self.lb_frame,
			width=self.lb_width,
			height=self.lb_height,
			#bd=0,
			highlightthickness=0,
			relief='flat',
			bg=zynthian_gui_config.color_bg)
		self.listbox.grid_forget()
		self.mon_canvas.grid(sticky="wens")

		# Create custom GUI elements
		x0 = self.lb_width//2
		y0 = self.lb_height//4
		self.note_label = self.mon_canvas.create_text(
				x0,
				self.lb_height//2,
				#anchor=tkinter.NW,
				justify=tkinter.CENTER,
				width=4*self.note_fs,
				text="??",
				font=(zynthian_gui_config.font_family,self.note_fs),
				fill=zynthian_gui_config.color_panel_tx)
		self.cents_bar = self.mon_canvas.create_rectangle(x0-self.bar_width, y0, x0 + self.bar_width, y0 - self.bar_height, fill=zynthian_gui_config.color_on)
		# Scale axis for cents
		y0 -= self.bar_height//2
		self.mon_canvas.create_line(0, y0, self.lb_width, y0, fill=zynthian_gui_config.color_tx_off)
		self.mon_canvas.create_line(x0, y0 + self.bar_height, x0, y0 - self.bar_height, fill=zynthian_gui_config.color_tx_off)
		dx = self.lb_width//20
		dy = self.bar_height//2
		for i in range(1,10):
			x = x0 + i * dx
			self.mon_canvas.create_line(x, y0 + dy, x, y0 - dy, fill=zynthian_gui_config.color_tx_off)
			x = x0 - i * dx
			self.mon_canvas.create_line(x, y0 + dy, x, y0 - dy, fill=zynthian_gui_config.color_tx_off)
			

		# Start Thread
		self.start_mon_thread()


	def start_mon_thread(self):
		self.mon_thread=Thread(target=self.mon_thread_task, args=())
		self.mon_thread.daemon = True # thread dies with the program
		self.mon_thread.start()


	def mon_thread_task(self):
		while not self.zyngui.exit_flag:
			if self.shown:
				self.refresh_monitors()
			sleep(0.04)


	def refresh_monitors(self):
		monitors = self.zyngui.curlayer.engine.get_lv2_monitors_dict()

		# It should receive: rms, freq_out, octave, note, cent, accuracy
		if 'freq_out' not in monitors:
			return

		#for k,v in monitors.items():
		#	logging.debug("MONITOR {} = {}".format(k,v))

		#if monitors['rms']>-50.0 and monitors['accuracy']>0.0:
		if monitors['rms']>-70.0:
			try:
				note_name = "{}{}".format(self.note_names[int(monitors["note"])], int(monitors["octave"]))
			except:
				note_name = "??"
			try:
				x = int(self.lb_width//2 + monitors['cent'])
			except:
				x = self.lb_width//2

			y0 = self.lb_height//4
			self.mon_canvas.itemconfigure(self.note_label, text=note_name)
			self.mon_canvas.coords(self.cents_bar, x - self.bar_width, y0, x + self.bar_width, y0 - self.bar_height)


#------------------------------------------------------------------------------
