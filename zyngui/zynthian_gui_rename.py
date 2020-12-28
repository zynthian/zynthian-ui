#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Rename Class
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

import tkinter
import logging
import math
import tkinter.font as tkFont

# Zynthian specific modules
from . import zynthian_gui_config
from zyncoder import *

#------------------------------------------------------------------------------
# Zynthian File-Selector GUI Class
#   Acts as Modal window. Ensure parent has set_filename(filename) function
#------------------------------------------------------------------------------

ENC_LAYER			= 0
ENC_BACK			= 1
ENC_SNAPSHOT		= 2
ENC_SELECT			= 3

# Class implements renaming dialog
class zynthian_gui_rename():

	# Function to initialise class
	#	parent: Parent instance
	#	function: Function to call to update name
	#	name: Current name
	def __init__(self, parent, function, name=""):
		self.parent = parent
		self.function = function
		self.name = name
		self.columns = 10 # Quantity of columns in keyboard grid
		self.rows = 5 # Quantity of rows in keyboard grid
		self.shift = False # True when shift locked
		self.buttons = [] # Array of buttons in keyboard layout
		self.selected_button = 44; # Index of highlighted button

		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.display_height - zynthian_gui_config.topbar_height
		self.key_width = (self.width - 2) / self.columns
		self.key_height = (self.height - 2) / self.rows

		# Create main frame
		self.main_frame = tkinter.Frame(parent.main_frame,
			width=zynthian_gui_config.display_width,
			height=zynthian_gui_config.display_height,
			bg=zynthian_gui_config.color_bg)
		self.main_frame.grid_propagate(False)
		self.main_frame.grid(column=0, row=0)

		# Display string being edited
		self.name_canvas = tkinter.Canvas(self.main_frame, width=self.width, height=zynthian_gui_config.topbar_height)
		self.name_label = self.name_canvas.create_text(self.width / 2, zynthian_gui_config.topbar_height / 2, text=name,
		font=zynthian_gui_config.font_topbar,
		#font=tkFont.Font(family=zynthian_gui_config.font_topbar[0], size= int(zynthian_gui_config.topbar_height * 0.8))
		)
		self.name_canvas.grid(column=0, row=0, sticky="nsew")

		# Display keyboard grid
		self.key_canvas = tkinter.Canvas(self.main_frame, width=self.width, height = self.height, bg="grey")
		self.key_canvas.grid_propagate(False)
		self.key_canvas.grid(column=0, row=1, sticky="nesw")
		for row in range(self.rows - 1):
			for col in range(self.columns):
				self.add_button("", col, row)
		row = row + 1
		# Add special keys
		self.btn_cancel = self.add_button('CANCEL', 0, row, 2)
		self.btn_shift = self.add_button('SHIFT', 2, row, 1)
		self.btn_space = self.add_button(' ', 3, row, 4)
		self.btn_delete = self.add_button('DELETE', 7, row, 1)
		self.btn_enter = self.add_button('ENTER', 8, row, 2)

		self.refresh_keys()
		self.setupEncoders()

		self.highlight_box = self.key_canvas.create_rectangle(0, 0, self.key_width, self.key_height, outline="red", width=2)
		self.highlight(self.selected_button)

	# Function to draw keyboard
	def refresh_keys(self):
		if self.shift:
			self.keys = ['!','£','$','€','%','*','(',')','+','-',
						'Q','W','E','R','T','Y','U','I','O','P',
						'A','S','D','F','G','H','J','K','L','[',
						'Z','X','C','V','B','N','M','<','>',']']
		else:
			self.keys = ['1','2','3','4','5','6','7','8','9','0',
						'q','w','e','r','t','y','u','i','o','p',
						'a','s','d','f','g','h','j','k','l',';',
						'z','x','c','v','b','n','m',',','.','#']
		self.key_canvas.itemconfig("keycaps", text="")
		for index in range(len(self.keys)):
			self.key_canvas.itemconfig(self.buttons[index][1], text=self.keys[index], tags=("key:%d"%(index),"keycaps"))

	# Function to add a button to the keyboard
	#	label: Button label
	#	col: Column to add button
	#	row: Row to add button
	#	colspan: Column span [Default: 1]
	#	returns: Index of key in self.buttons[]
	def add_button(self, label, col, row, colspan=1):
		index = len(self.buttons)
		tag = "key:%d"%(index)
		r = self.key_canvas.create_rectangle(1 + self.key_width * col, 1 + self.key_height * row, self.key_width * (col + colspan) - 1, self.key_height * (row + 1) - 1, tags=(tag), fill="black")
		l = self.key_canvas.create_text(1 + self.key_width * (col + colspan / 2), 1 + self.key_height * (row + 0.5), text=label, fill="white", tags=(tag))
		self.key_canvas.tag_bind(tag, "<Button-1>", self.on_key_press)
		self.buttons.append([r,l])
		return index

	# Function to handle key press
	#	event: Mouse event
	def on_key_press(self, event = None):
		tags = self.key_canvas.gettags(self.key_canvas.find_withtag(tkinter.CURRENT))
		if not tags:
			return
		dummy, index = tags[0].split(':')
		self.execute_key_press(int(index))

	# Function to execute a key press
	#	key: Index of key
	def execute_key_press(self, key):
		#TODO: Use button ID for special function to allow localisation
		self.selected_button = key
		if key == self.btn_delete:
			self.name = self.name[:-1]
		elif key == self.btn_enter:
			self.function(self.name)
			self.hide()
			return
		elif key == self.btn_cancel:
			self.hide()
			return
		elif key == self.btn_shift:
			self.shift = not self.shift
			if self.shift:
				self.key_canvas.itemconfig(self.buttons[key][0], fill="grey")
			else:
				self.key_canvas.itemconfig(self.buttons[key][0], fill="black")
			self.refresh_keys()
			return
		elif key == self.btn_space:
			self.name = self.name + " "
		elif key < len(self.keys):
			self.name = self.name + self.keys[key]
		self.name_canvas.itemconfig(self.name_label, text=self.name)
		self.highlight(key)

	# Function to highlight key
	def highlight(self, key):
		if key >= len(self.buttons):
			return
		box = self.key_canvas.bbox(self.buttons[key][0])
		self.key_canvas.coords(self.highlight_box, box[0]+1, box[1]+1, box[2], box[3])
		self.selected_button = key

	# Function to hide dialog
	def hide(self):
		self.main_frame.destroy()
		self.parent.showChild()

	# Function to assert ENTER
	def execute_enter(self):
		self.function(self.name)
		self.hide()

	# Function to register encoders
	def setupEncoders(self):
		self.parent.registerZyncoder(ENC_SELECT, self)
		self.parent.registerZyncoder(ENC_BACK, self)
		self.parent.registerSwitch(ENC_SELECT, self)
		self.parent.registerSwitch(ENC_BACK, self)

	# Function to handle zyncoder value change
	#	encoder: Zyncoder index [0..4]
	#	value: Current value of zyncoder
	def onZyncoder(self, encoder, value):
		if encoder == ENC_SELECT:
			# SELECT encoder select key
			self.selected_button = self.selected_button + value
			if self.selected_button < 0:
				self.selected_button = len(self.buttons) - 1
			if self.selected_button >= len(self.buttons):
				self.selected_button = 0
			self.highlight(self.selected_button)
		elif encoder == ENC_BACK:
			selection = self.selected_button + value * self.columns
			if value < 0:
				if self.selected_button == self.btn_shift:
					selection = 32
				elif self.selected_button == self.btn_space:
					selection = 33
				elif self.selected_button == self.btn_delete:
					selection = 37
				elif self.selected_button == self.btn_enter:
					selection = 38
			elif value > 0:
				if self.selected_button in [30,31]:
					selection = self.btn_cancel
				elif self.selected_button in [32]:
					selection = self.btn_shift
				elif self.selected_button in [33,34,35,36]:
					selection = self.btn_space
				elif self.selected_button in [37]:
					selection = self.btn_delete
				elif self.selected_button in [38,39]:
					selection = self.btn_enter
			if selection < 0 or selection >= self.columns * (self.rows):
				return
			self.highlight(selection)

	# Function to handle switch press
	#	switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def onSwitch(self, switch, type):
		if switch == ENC_BACK:
			self.hide()
		elif switch == ENC_SELECT:
			self.execute_key_press(self.selected_button)
		return True # Tell parent that we handled all short and bold key presses
#------------------------------------------------------------------------------
