#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Confirm Class
# 
# Copyright (C) 2023 Markus Heidt <markus@heidt-tech.com>
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

import tkinter
import logging

# Zynthian specific modules
from zyngui import zynthian_gui_config

#------------------------------------------------------------------------------
# Zynthian Info GUI Class
#------------------------------------------------------------------------------

#TODO: Derive confirm from gui base class

class zynthian_gui_confirm():

	def __init__(self):
		self.shown = False
		self.callback = None
		self.callback_params = None
		self.zyngui = zynthian_gui_config.zyngui
		self.width = zynthian_gui_config.screen_width
		self.height = zynthian_gui_config.screen_height

		# Main Frame
		self.main_frame = tkinter.Frame(zynthian_gui_config.top,
			width = self.width,
			height = self.height,
			bg = zynthian_gui_config.color_bg)

		self.text = tkinter.StringVar()
		self.label_text = tkinter.Label(self.main_frame,
			font=(zynthian_gui_config.font_family,zynthian_gui_config.font_size,"normal"),
			textvariable=self.text,
			wraplength=self.width-zynthian_gui_config.font_size*2,
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
		self.yes_text_label.bind("<ButtonRelease-1>",self.cb_yes_push)
		self.yes_text_label.place(x=self.width, y=self.height, anchor=tkinter.SE)

		self.no_text_label=tkinter.Label(self.main_frame,
			font=(zynthian_gui_config.font_family,zynthian_gui_config.font_size*2,"normal"),
			text="No",
			width=3,
			justify=tkinter.LEFT,
			padx=zynthian_gui_config.font_size,
			pady=zynthian_gui_config.font_size,
			bg=zynthian_gui_config.color_ctrl_bg_off,
			fg=zynthian_gui_config.color_tx)
		self.no_text_label.bind("<ButtonRelease-1>",self.cb_no_push)
		self.no_text_label.place(x=0, y=self.height, anchor=tkinter.SW)


	def hide(self):
		if self.shown:
			self.shown=False
			self.main_frame.grid_forget()


	def build_view(self):
		return True

	def show(self, text, callback=None, cb_params=None):
		if self.zyngui.test_mode:
			logging.warning("TEST_MODE: {}".format(self.__class__.__module__))
		self.text.set(text)
		self.callback = callback
		self.callback_params = cb_params
		if not self.shown:
			self.shown=True
			self.main_frame.grid(row=0, column=self.zyngui.main_screen_column)


	def zynpot_cb(self, i, dval):
		pass


	def refresh_loading(self):
		pass


	def switch_select(self, t='S'):
		logging.info("callback %s", self.callback_params)
		self.zyngui.close_screen()
		if self.callback:
			self.callback(self.callback_params)


	def switch(self, i, t):
		if i in [0,2]:
			return True


	def cb_yes_push(self, event):
		self.zyngui.zynswitch_defered('S',3)


	def cb_no_push(self, event):
		self.zyngui.zynswitch_defered('S',1)


	def zynpot_cb(self, enc, dval):
		pass # TODO: Derive gui_confirm from gui_base
#-------------------------------------------------------------------------------
