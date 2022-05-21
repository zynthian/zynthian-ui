#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian Widget Base Class
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
from time import sleep
from threading  import Thread

# Zynthian specific modules
from zyngui import zynthian_gui_config

#------------------------------------------------------------------------------
# Base Class for Control Widgets
#------------------------------------------------------------------------------

class zynthian_widget_base():

	def __init__(self):
		self.zyngui = zynthian_gui_config.zyngui
		self.zyngui_control = self.zyngui.screens['control']
		self.width = self.zyngui_control.lb_width
		self.height = self.zyngui_control.lb_height
		self.wide = self.zyngui_control.wide
		self.shown = False

		self.layer = None
		self.mon_canvas = None
		self.monitors = None


	def create_gui(self):
		self.mon_canvas = tkinter.Canvas(self.zyngui_control.lb_frame,
			width=self.width,
			height=self.height,
			#bd=0,
			highlightthickness=0,
			relief='flat',
			bg=zynthian_gui_config.color_bg)


	def show(self):
		if not self.shown:
			if not self.mon_canvas:
				self.create_gui()
			self.zyngui_control.listbox.grid_forget()
			self.mon_canvas.grid(sticky="wens")
			self.shown = True


	def hide(self):
		if self.shown:
			self.mon_canvas.grid_forget()
			self.zyngui_control.listbox.grid(sticky="wens")
			self.shown = False


	def update(self):
		if self.shown and self.zyngui_control.shown:
			self.get_monitors()
			self.refresh_gui()


	def set_layer(self, layer):
		self.layer = layer


	def get_monitors(self):
		self.monitors = self.layer.engine.get_monitors_dict()


	def refresh_gui(self):
		pass
		#for k,v in self.monitors.items():
		#	logging.debug("MONITOR {} = {}".format(k,v))

#------------------------------------------------------------------------------
