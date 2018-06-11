#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Info Class
# 
# Copyright (C) 2015-2016 Fernando Moyano <jofemodo@zynthian.org>
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
from . import zynthian_gui_config

#------------------------------------------------------------------------------
# Configure logging
#------------------------------------------------------------------------------

# Set root logging level
logging.basicConfig(stream=sys.stderr, level=zynthian_gui_config.log_level)

#------------------------------------------------------------------------------
# Zynthian Info GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_info:

	def __init__(self):
		self.shown=False

		# Main Frame
		self.main_frame = tkinter.Frame(zynthian_gui_config.top,
			width = zynthian_gui_config.display_width,
			height = zynthian_gui_config.display_height,
			bg = zynthian_gui_config.color_bg)

		#Textarea
		self.textarea = tkinter.Text(self.main_frame,
			font=(zynthian_gui_config.font_family,zynthian_gui_config.font_size,"normal"),
			#wraplength=80,
			#justify=tkinter.LEFT,
			bd=0,
			highlightthickness=0,
			relief=tkinter.FLAT,
			bg=zynthian_gui_config.color_bg,
			fg=zynthian_gui_config.color_tx)
		self.textarea.bind("<Button-1>", self.cb_push)
		self.textarea.pack(fill="both", expand=True)

	def clean(self):
		self.textarea.delete(1.0,tkinter.END)

	def add(self, text):
		self.textarea.insert(tkinter.END,text)
		self.textarea.see(tkinter.END)

	def set(self, text):
		self.add(text+"\n")

	def hide(self):
		if self.shown:
			self.shown=False
			self.main_frame.grid_forget()

	def show(self, text):
		self.clean()
		self.set(text)
		if not self.shown:
			self.shown=True
			self.main_frame.grid()

	def zyncoder_read(self):
		pass

	def refresh_loading(self):
		pass

	def switch_select(self):
		pass

	def cb_push(self,event):
		zynthian_gui_config.zyngui.zynswitch_defered('S',1)

#-------------------------------------------------------------------------------
