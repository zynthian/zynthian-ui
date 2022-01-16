#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Class for 1/3 Octave Spectrum Meter
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
# Zynthian Auto-EQ GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_spectr30(zynthian_gui_control.zynthian_gui_control):

	def __init__(self):
		super().__init__('1/3 Octave Spectrum')

		self.n_bands = 30
		self.mon_layer = None
		self.mon_bars = []
		self.mon_thread = None

		# Geometry vars
		self.bar_width = int(self.lb_width/self.n_bands)
		self.spec_padx = int((self.lb_width%self.n_bands)/2)
		self.spec_pady=0
		self.spec_width=self.lb_width-2*self.spec_padx
		self.spec_height=self.lb_height-2*self.spec_pady
		
		# Create Canvas
		self.spec_canvas= tkinter.Canvas(self.lb_frame,
			width=self.spec_width,
			height=self.spec_height,
			#bd=0,
			highlightthickness=0,
			relief='flat',
			bg=zynthian_gui_config.color_bg)
		self.listbox.grid_forget()
		self.spec_canvas.grid(sticky="wens", padx=(self.spec_padx, self.spec_padx), pady=(self.spec_pady, self.spec_pady))

		# Create Bars
		x0 = 0
		for i in range(self.n_bands):
			self.mon_bars.append(self.spec_canvas.create_rectangle(x0, self.spec_height, x0 + self.bar_width, self.spec_height, fill=zynthian_gui_config.color_on))
			x0 += self.bar_width 

		# Start Thread
		self.start_mon_thread()


	def start_mon_thread(self):
		self.mon_thread=Thread(target=self.mon_thread_task, args=())
		self.mon_thread.daemon = True # thread dies with the program
		self.mon_thread.start()


	def mon_thread_task(self):
		while not self.zyngui.exit_flag:
			if self.shown:
				self.refresh_bars()
			sleep(0.04)


	def refresh_bars(self):
		x0 = 0
		items = self.zyngui.curlayer.engine.get_lv2_monitors_dict().items()
		if len(items)>0:
			i = 0
			scale = (12.0 + self.zyngui.curlayer.controllers_dict['UIgain'].value) / 12.0
			for k, v in items:
				mon_y = int(scale * (100 + v) * self.spec_height / 100)
				#logging.error("MON {}: {} => {}".format(i,k,mon_y))
				self.spec_canvas.coords(self.mon_bars[i], x0, self.spec_height, x0 + self.bar_width, self.spec_height - mon_y)
				x0 += self.bar_width
				i += 1
				if i>=self.n_bands:
					break
		else:
			for i in range(self.n_bands):
				self.spec_canvas.coords(self.mon_bars[i], x0, self.spec_height, x0 + self.bar_width, self.spec_height)
				x0 += self.bar_width


#------------------------------------------------------------------------------
