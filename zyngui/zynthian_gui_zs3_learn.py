#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI ZS3 learn screen
# 
# Copyright (C) 2018 Fernando Moyano <jofemodo@zynthian.org>
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
# Zynthian Sub-SnapShot (ZS3) MIDI-learn GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_zs3_learn():

	def __init__(self):
		self.shown = False

		# Main Frame
		self.main_frame = tkinter.Frame(zynthian_gui_config.top,
			width = zynthian_gui_config.display_width,
			height = zynthian_gui_config.display_height,
#			bg = zynthian_gui_config.color_bg)
			bg = "#ff0000")

		# Topbar's frame
		self.tb_frame = tkinter.Frame(self.main_frame, 
			width=zynthian_gui_config.display_width,
			height=zynthian_gui_config.topbar_height,
			bg=zynthian_gui_config.color_bg)
		self.tb_frame.grid(row=0, column=0)
		self.tb_frame.grid_propagate(False)
		# Setup Topbar's Callback
		self.tb_frame.bind("<Button-1>", self.cb_topbar)

		# Topbar's Select Path
		self.select_path = tkinter.StringVar()
		self.label_select_path = tkinter.Label(self.tb_frame,
			font=zynthian_gui_config.font_topbar,
			textvariable=self.select_path,
			#wraplength=80,
			justify=tkinter.LEFT,
			bg=zynthian_gui_config.color_header_bg,
			fg=zynthian_gui_config.color_header_tx)
		self.label_select_path.grid(sticky="wns")
		# Setup Topbar's Callback
		self.label_select_path.bind("<Button-1>", self.cb_topbar)

		self.text = tkinter.StringVar()
		self.text.set("Waiting for Program Change event ...\n\n\n")
		self.label_text = tkinter.Label(self.main_frame,
			font=(zynthian_gui_config.font_family,zynthian_gui_config.font_size,"normal"),
			textvariable=self.text,
			wraplength=zynthian_gui_config.display_width-zynthian_gui_config.font_size*2,
			justify=tkinter.LEFT,
			height=int((zynthian_gui_config.display_height-zynthian_gui_config.topbar_height)/zynthian_gui_config.font_size),
			padx=zynthian_gui_config.font_size,
			pady=zynthian_gui_config.font_size,
			bg=zynthian_gui_config.color_bg,
			fg=zynthian_gui_config.color_hl)
		self.label_text.grid(row=1, column=0, rowspan=2, sticky="wens")


	def hide(self):
		if self.shown:
			self.shown=False
			self.main_frame.grid_forget()


	def show(self):
		if not self.shown:
			self.shown=True
			self.set_select_path()
			self.main_frame.grid()


	def zyncoder_read(self):
		pass


	def refresh_loading(self):
		pass


	def cb_topbar(self,event):
		zynthian_gui_config.zyngui.zynswitch_defered('S',1)


	def set_select_path(self):
		if zynthian_gui_config.zyngui.curlayer:
			self.select_path.set(zynthian_gui_config.zyngui.curlayer.get_basepath() + " / ZS3 MIDI-Learn")
		else:
			self.select_path.set("ZS3 MIDI-Learn")


#-------------------------------------------------------------------------------
