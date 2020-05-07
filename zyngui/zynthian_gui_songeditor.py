#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Step-Sequencer Class
# 
# Copyright (C) 2015-2020 Fernando Moyano <jofemodo@zynthian.org>
# Copyright (C) 2015-2020 Brian Walton <brian@riban.co.uk>
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

import inspect
import tkinter
import logging
import tkinter.font as tkFont

# Zynthian specific modules
from . import zynthian_gui_config
from zyncoder import *

#------------------------------------------------------------------------------
# Zynthian Step-Sequencer Song Editor GUI Class
#------------------------------------------------------------------------------

# Class implements step sequencer
class zynthian_gui_songeditor():

	# Function to initialise class
	def __init__(self, parent):
		self.parent = parent
		parent.setTitle("Song Editor not implemented")

		self.shown = False # True when GUI in view
		self.zyngui = zynthian_gui_config.zyngui # Zynthian GUI configuration

		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.display_height - zynthian_gui_config.topbar_height

		# Main Frame
		self.main_frame = tkinter.Frame(self.parent.main_frame)
		self.main_frame.grid(row=1, column=0, sticky="nsew")

	#Function to set values of encoders
	#	note: Call after other routine uses one or more encoders
	def setupEncoders(self):
		pass

	# Function to show GUI
	def show(self):
		self.main_frame.tkraise()
		self.setupEncoders()
		self.shown=True

	# Function to hide GUI
	def hide(self):
		self.shown=False

	# Function to handle menu editor change
	#	value: Menu item's value
	#	returns: String to populate menu editor label
	def onMenuChange(self, value):
		#TODO: Implement acccess to paramEditor
		menuItem = self.parent.paramEditor['menuitem']
		if value < self.parent.paramEditor['min']:
			value = self.parent.paramEditor['min']
		if value > self.parent.paramEditor['max']:
			value = self.parent.paramEditor['max']
		self.parent.paramEditor['value'] = value
		return "%s: %d" % (menuItem, value)

	def refresh_loading(self):
		pass

	# Function to handle zyncoder value change
	#	encoder: Zyncoder index [0..4]
	#	value: Current value of zyncoder
	def onZyncoder(self, encoder, value):
		pass

	# Function to handle switch press
	#	switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def switch(self, switch, type):
		if type == "L":
			return False # Don't handle any long presses
		return True # Tell parent that we handled all short and bold key presses
#------------------------------------------------------------------------------
