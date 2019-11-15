#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI XY-Controller Class
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
# Zynthian X-Y Controller GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_control_xy():

	def __init__(self):
		self.canvas = None
		self.hline = None
		self.vline = None
		self.shown = False
		self.zyngui = zynthian_gui_config.zyngui

		# Init X vars
		self.padx=24
		self.width=zynthian_gui_config.display_width-2*self.padx
		self.x=self.width/2
		self.x_zctrl=None
		self.xvalue_max=127
		self.xvalue=64

		# Init X vars
		self.pady=18
		self.height=zynthian_gui_config.display_height-2*self.pady
		self.y=self.height/2
		self.y_zctrl=None
		self.yvalue_max=127
		self.yvalue=64

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

		# Create Cursor
		self.hline=self.canvas.create_line(0,self.y,zynthian_gui_config.display_width,self.y,fill=zynthian_gui_config.color_on)
		self.vline=self.canvas.create_line(self.x,0,self.x,zynthian_gui_config.display_width,fill=zynthian_gui_config.color_on)

		# Show
		self.show()


	def show(self):
		if not self.shown:
			self.shown=True
			self.main_frame.grid()
			self.refresh()


	def hide(self):
		if self.shown:
			self.shown=False
			self.main_frame.grid_forget()


	def set_controllers(self, x_zctrl, y_zctrl):
		self.x_zctrl=x_zctrl
		self.y_zctrl=y_zctrl
		self.xvalue_max=self.x_zctrl.value_max
		self.yvalue_max=self.y_zctrl.value_max
		self.get_controller_values()


	def set_x_controller(self, x_zctrl):
		self.x_zctrl=x_zctrl
		self.xvalue_max=self.x_zctrl.value_max
		self.get_controller_values()


	def set_y_controller(self, y_zctrl):
		self.y_zctrl=y_zctrl
		self.yvalue_max=self.y_zctrl.value_max
		self.get_controller_values()


	def get_controller_values(self):
		xv=self.x_zctrl.value
		if xv!=self.xvalue:
			self.xvalue=xv
			self.x=int(self.xvalue*zynthian_gui_config.display_width/self.xvalue_max)
			self.canvas.coords(self.vline,self.x,0,self.x,self.height)
		yv=self.y_zctrl.value
		if yv!=self.yvalue:
			self.yvalue=yv
			self.y=int(self.yvalue*zynthian_gui_config.display_height/self.yvalue_max)
			self.canvas.coords(self.hline,0,self.y,self.width,self.y)


	def refresh(self):
		self.xvalue=self.x*self.xvalue_max/self.width
		self.yvalue=self.y*self.yvalue_max/self.height
		self.canvas.coords(self.hline,0,self.y,self.width,self.y)
		self.canvas.coords(self.vline,self.x,0,self.x,self.height)
		if self.x_zctrl is not None:
			self.x_zctrl.set_value(self.xvalue,True)
		if self.y_zctrl is not None:
			self.y_zctrl.set_value(self.yvalue,True)


	def cb_canvas(self, event):
		#logging.debug("XY controller => %s, %s" % (event.x, event.y))
		self.x=event.x
		self.y=event.y
		self.refresh()


	def zyncoder_read(self):
		self.zyngui.screens['control'].zyncoder_read()
		self.get_controller_values()


	def refresh_loading(self):
		pass


	def switch_select(self, t='S'):
		pass


#------------------------------------------------------------------------------
