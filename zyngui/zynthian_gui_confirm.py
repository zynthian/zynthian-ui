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

class zynthian_gui_confirm():

	def __init__(self):
		self.shown=False

		self.canvas = tkinter.Canvas(zynthian_gui_config.top,
			width = zynthian_gui_config.display_width,
			height = zynthian_gui_config.display_height,
			bd=1,
			highlightthickness=0,
			relief='flat',
			bg = zynthian_gui_config.color_bg)
		self.canvas.bind("<Button-1>",self.cb_canvas_push)

		self.text = tkinter.StringVar()
		self.label_text = tkinter.Label(self.canvas,
			font=(zynthian_gui_config.font_family,zynthian_gui_config.font_size,"normal"),
			textvariable=self.text,
			#wraplength=80,
			justify=tkinter.LEFT,
			bg=zynthian_gui_config.color_bg,
			fg=zynthian_gui_config.color_tx)
		self.label_text.place(x=1, y=0, anchor=tkinter.NW)
		self.yes_text = tkinter.StringVar()
		self.yes_text.set('Yes')
		self.yes_text_label=tkinter.Label(self.canvas,
                        font=(zynthian_gui_config.font_family,zynthian_gui_config.font_size*3,"normal"),
                        textvariable=self.yes_text,
                        #wraplength=80,
                        justify=tkinter.RIGHT,
                        bg=zynthian_gui_config.color_ctrl_bg_off,
                        fg=zynthian_gui_config.color_tx)

		self.yes_text_label.place(x=zynthian_gui_config.display_width, y=zynthian_gui_config.display_height, anchor=tkinter.SE)

		self.no_text = tkinter.StringVar()
		self.no_text.set('No')
		self.no_text_label=tkinter.Label(self.canvas,
                        font=(zynthian_gui_config.font_family,zynthian_gui_config.font_size*3,"normal"),
                        textvariable=self.no_text,
                        #wraplength=80,
                        justify=tkinter.LEFT,
                        bg=zynthian_gui_config.color_ctrl_bg_off,
                        fg=zynthian_gui_config.color_tx)

		self.no_text_label.place(x=0, y=zynthian_gui_config.display_height, anchor=tkinter.SW)


	def clean(self):
		self.text.set("")

	def set(self, text):
		self.text.set(text)

	def add(self, text):
		self.text.set(self.text.get()+text)

	def hide(self):
		if self.shown:
			self.shown=False
			self.canvas.grid_forget()

	def show(self, text, switch_select_callback):
		self.text.set(text)
		self.switch_select_callback = switch_select_callback
		if not self.shown:
			self.shown=True
			self.canvas.grid()

	def zyncoder_read(self):
		pass

	def refresh_loading(self):
		pass

	def switch_select(self):
		logging.info("confirm.switch_select_callback")
		self.switch_select_callback()

	def cb_canvas_push(self,event):
		zynthian_gui_config.zyngui.zynswitch_defered('S',1)

#-------------------------------------------------------------------------------
