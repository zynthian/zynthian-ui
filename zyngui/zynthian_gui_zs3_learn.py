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
			bg = zynthian_gui_config.color_bg)

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

		# Body's frame
		self.body_frame = tkinter.Frame(self.main_frame, 
			width=zynthian_gui_config.display_width,
			height=zynthian_gui_config.display_height-zynthian_gui_config.topbar_height,
			bg=zynthian_gui_config.color_bg)
		self.body_frame.grid(row=1, column=0, sticky="wens")

		# Some blank space
		tkinter.Label(self.body_frame, bg=zynthian_gui_config.color_bg).grid(row=0)

		# Program Matrix
		counter=0
		self.text_status = []
		self.label_text_status = []
		for i in range(8):
			for j in range(16):
				self.text_status.append(tkinter.StringVar())
				self.text_status[counter].set(str(counter))
				self.label_text_status.append(tkinter.Label(self.body_frame,
					font=(zynthian_gui_config.font_family,int(0.7*zynthian_gui_config.font_size),"normal"),
					textvariable=self.text_status[counter],
					height=1,
					bg=zynthian_gui_config.color_bg,
					fg=zynthian_gui_config.color_tx))
				self.label_text_status[counter].grid(row=i+1, column=j, sticky="wens")
				counter+=1

		# Message
		self.text_waiting = tkinter.StringVar()
		self.text_waiting.set("Waiting for Program Change event ...")
		self.label_text_waiting = tkinter.Label(self.body_frame,
			font=(zynthian_gui_config.font_family,zynthian_gui_config.font_size,"normal"),
			textvariable=self.text_waiting,
			height=6,
			bg=zynthian_gui_config.color_bg,
			fg=zynthian_gui_config.color_hl)
		self.label_text_waiting.grid(row=9, columnspan=16, sticky="wens")

		# Adjust weight of rows and columns to fill all the available area
		tkinter.Grid.rowconfigure(self.body_frame, 0, weight=1)
		tkinter.Grid.rowconfigure(self.body_frame, 9, weight=1)
		for i in range(16):
			tkinter.Grid.columnconfigure(self.body_frame, i, weight=1)


	def hide(self):
		if self.shown:
			self.shown=False
			self.main_frame.grid_forget()


	def show(self):
		if not self.shown:
			self.shown=True
			self.set_select_path()
			self.update_status()
			self.main_frame.grid()


	def update_status(self):
		midich=zynthian_gui_config.zyngui.curlayer.get_midi_chan()
		for i in range(128):
			zs3=zynthian_gui_config.zyngui.screens['layer'].get_midi_chan_zs3_status(midich,i)
			#zs3=zynthian_gui_config.zyngui.curlayer.zs3_list[i]
			#logging.debug("ZS3 Status Prog#{} => {}".format(i,zs3))

			if zs3:
				color=zynthian_gui_config.color_on
			else:
				color=zynthian_gui_config.color_tx

			self.label_text_status[i].config(fg=color)


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
