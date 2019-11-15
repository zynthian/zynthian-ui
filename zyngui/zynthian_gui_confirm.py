#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Confirm Class
# 
# Copyright (C) 2018 Markus Heidt <markus@heidt-tech.com>
#                    Fernando Moyano <jofemodo@zynthian.org>
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

class zynthian_gui_confirm():

	def __init__(self):
		self.shown = False
		self.callback = None
		self.callback_params = None
		self.zyngui = zynthian_gui_config.zyngui

		# Main Frame
		self.main_frame = tkinter.Frame(zynthian_gui_config.top,
			width = zynthian_gui_config.display_width,
			height = zynthian_gui_config.display_height,
			bg = zynthian_gui_config.color_bg)

		self.text = tkinter.StringVar()
		self.label_text = tkinter.Label(self.main_frame,
			font=(zynthian_gui_config.font_family,zynthian_gui_config.font_size,"normal"),
			textvariable=self.text,
			wraplength=zynthian_gui_config.display_width-zynthian_gui_config.font_size*2,
			justify=tkinter.LEFT,
			padx=zynthian_gui_config.font_size,
			pady=zynthian_gui_config.font_size,
			bg=zynthian_gui_config.color_bg,
			fg=zynthian_gui_config.color_tx)
		self.label_text.place(x=0, y=0, anchor=tkinter.NW)

		self.yes_text_label=tkinter.Label(self.main_frame,
			font=(zynthian_gui_config.font_family,zynthian_gui_config.font_size*2,"normal"),
			text="Yes",
			width=3,
			justify=tkinter.RIGHT,
			padx=zynthian_gui_config.font_size,
			pady=zynthian_gui_config.font_size,
			bg=zynthian_gui_config.color_ctrl_bg_off,
			fg=zynthian_gui_config.color_tx)
		self.yes_text_label.bind("<Button-1>",self.cb_yes_push)
		self.yes_text_label.place(x=zynthian_gui_config.display_width, y=zynthian_gui_config.display_height, anchor=tkinter.SE)

		self.no_text_label=tkinter.Label(self.main_frame,
			font=(zynthian_gui_config.font_family,zynthian_gui_config.font_size*2,"normal"),
			text="No",
			width=3,
			justify=tkinter.LEFT,
			padx=zynthian_gui_config.font_size,
			pady=zynthian_gui_config.font_size,
			bg=zynthian_gui_config.color_ctrl_bg_off,
			fg=zynthian_gui_config.color_tx)
		self.no_text_label.bind("<Button-1>",self.cb_no_push)
		self.no_text_label.place(x=0, y=zynthian_gui_config.display_height, anchor=tkinter.SW)


	def hide(self):
		if self.shown:
			self.shown=False
			self.main_frame.grid_forget()


	def show(self, text, callback=None, cb_params=None):
		self.text.set(text)
		self.callback = callback
		self.callback_params = cb_params
		if not self.shown:
			self.shown=True
			self.main_frame.grid()


	def zyncoder_read(self):
		pass


	def refresh_loading(self):
		pass


	def switch_select(self, t='S'):
		logging.info("callback %s" % self.callback_params)
		
		try:
			self.callback(self.callback_params)
		except:
			pass

		if self.zyngui.modal_screen=="confirm":
			self.zyngui.show_active_screen()


	def cb_yes_push(self, event):
		self.zyngui.zynswitch_defered('S',3)


	def cb_no_push(self, event):
		self.zyngui.zynswitch_defered('S',1)


#-------------------------------------------------------------------------------
