#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Auto-EQ Class
# 
# Copyright (C) 2015-2020 Fernando Moyano <jofemodo@zynthian.org>
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
from . import zynthian_gui_config

#------------------------------------------------------------------------------
# Zynthian Auto-EQ GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_autoeq():

	def __init__(self):
		self.canvas = None
		self.shown = False
		self.zyngui = zynthian_gui_config.zyngui

		# Auto-EQ vars
		self.n_bands = 30
		self.mon_layer = None
		self.eq_layer = None
		self.mon_bars = []
		self.eq_bars = []
		self.autoeq_thread = None

		# Geometry vars
		self.bar_width = int(zynthian_gui_config.display_width/self.n_bands)
		self.padx = int((zynthian_gui_config.display_width%self.n_bands)/2)
		self.pady=0
		self.width=zynthian_gui_config.display_width-2*self.padx
		self.height=zynthian_gui_config.display_height-2*self.pady

		self.select_zctrl=None

		# Main Frame
		self.main_frame = tkinter.Frame(zynthian_gui_config.top,
			width=zynthian_gui_config.display_width,
			height=zynthian_gui_config.display_height,
			bg=zynthian_gui_config.color_panel_bg)

		# Create Canvas
		self.canvas= tkinter.Canvas(self.main_frame,
			width=self.width,
			height=self.height,
			#bd=0,
			highlightthickness=0,
			relief='flat',
			bg=zynthian_gui_config.color_bg)
		self.canvas.grid(padx=(self.padx,self.padx),pady=(self.pady,self.pady))

		# Setup Canvas Callback
		self.canvas.bind("<B1-Motion>", self.cb_canvas)

		# Create Bars
		x0 = 0
		for i in range(self.n_bands):
			self.mon_bars.append(self.canvas.create_rectangle(x0, self.height, x0 + self.bar_width, self.height, fill=zynthian_gui_config.color_on))
			self.eq_bars.append(self.canvas.create_line(x0, self.height, x0 + self.bar_width, self.height, fill=zynthian_gui_config.color_hl))
			x0 += self.bar_width 

		# Start Thread
		self.start_autoeq_thread()


	def show(self):
		if not self.shown:
			self.shown=True
			self.main_frame.grid()


	def hide(self):
		if self.shown:
			self.shown=False
			self.main_frame.grid_forget()


	def start_autoeq_thread(self):
		self.autoeq_thread=Thread(target=self.autoeq_thread_task, args=())
		self.autoeq_thread.daemon = True # thread dies with the program
		self.autoeq_thread.start()


	def autoeq_thread_task(self):
		while not self.zyngui.exit_flag:
			if self.shown:
				self.refresh_bars()
			sleep(0.04)


	def refresh_bars(self):
		self.mon_layer = self.zyngui.screens['layer'].get_layer_by_jackname('1/3')
		x0 = 0
		if self.mon_layer:
			i = 0
			for k, v in self.mon_layer.engine.get_lv2_monitors_dict().items():
				mon_y = int((100 + v) * self.height / 100)
				#logging.error("MON {}: {} => {}".format(i,k,mon_y))
				self.canvas.coords(self.mon_bars[i], x0, self.height, x0 + self.bar_width, self.height - mon_y)
				x0 += self.bar_width
				i += 1
				if i>=self.n_bands:
					break
		else:
			for i in range(self.n_bands):
				self.canvas.coords(self.mon_bars[i], x0, self.height, x0 + self.bar_width, self.height)
				x0 += self.bar_width

		self.eq_layer = self.zyngui.screens['layer'].get_layer_by_jackname('ZamGEQ31-01')
		x0 = 0
		if self.eq_layer:
			#TODO: To implement!!
			pass
		else:
			for i in range(self.n_bands):
				self.canvas.coords(self.eq_bars[i], x0, 60, x0 + self.bar_width, 60)
				x0 += self.bar_width


	def refresh_loading(self):
		pass


	def zyncoder_read(self):
		pass


	def cb_canvas(self, event):
		pass


	def switch_select(self, t='S'):
		pass


#------------------------------------------------------------------------------
