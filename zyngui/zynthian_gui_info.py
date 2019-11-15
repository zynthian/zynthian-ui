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
# Zynthian Info GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_info:

	def __init__(self):
		self.shown=False
		self.zyngui=zynthian_gui_config.zyngui

		# Main Frame
		self.main_frame = tkinter.Frame(zynthian_gui_config.top,
			width = zynthian_gui_config.display_width,
			height = zynthian_gui_config.display_height,
			bg = zynthian_gui_config.color_bg)

		#Textarea
		self.textarea = tkinter.Text(self.main_frame,
			height = int(zynthian_gui_config.display_height/(zynthian_gui_config.font_size+8)),
			font=(zynthian_gui_config.font_family,zynthian_gui_config.font_size,"normal"),
			#wraplength=80,
			#justify=tkinter.LEFT,
			bd=0,
			highlightthickness=0,
			relief=tkinter.FLAT,
			cursor="none",
			bg=zynthian_gui_config.color_bg,
			fg=zynthian_gui_config.color_tx)
		self.textarea.bind("<Button-1>", self.cb_push)
		#self.textarea.pack(fill="both", expand=True)
		self.textarea.place(x=0,y=0)

		self.textarea.tag_config("ERROR", foreground="#C00000")
		self.textarea.tag_config("WARNING", foreground="#FF9000")
		self.textarea.tag_config("SUCCESS", foreground="#009000")
		self.textarea.tag_config("EMPHASIS", foreground="#0000C0")


	def clean(self):
		self.textarea.delete(1.0,tkinter.END)


	def add(self, text, tags=None):
		self.textarea.insert(tkinter.END,text,tags)
		self.textarea.see(tkinter.END)


	def set(self, text, tags=None):
		self.clean()
		self.add(text+"\n",tags)


	def hide(self):
		if self.shown:
			self.shown=False
			self.main_frame.grid_forget()


	def show(self, text):
		self.set(text)
		if not self.shown:
			self.shown=True
			self.main_frame.grid()


	def zyncoder_read(self):
		pass


	def refresh_loading(self):
		pass


	def switch_select(self, t='S'):
		pass


	def back_action(self):
		self.zyngui.screens['admin'].kill_command()
		return self.zyngui.active_screen


	def cb_push(self,event):
		self.zyngui.zynswitch_defered('S',1)


#-------------------------------------------------------------------------------
