#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI keyboard Class
# 
# Copyright (C) 2015-2020 Fernando Moyano <jofemodo@zynthian.org>
# Copyright (C) 2020-2021 Brian Walton <brian@riban.co.uk>
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
from threading import Timer

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore
from zyngui import zynthian_gui_config

#------------------------------------------------------------------------------
# Zynthian Onscreen Keyboard GUI Class
#------------------------------------------------------------------------------

ENC_LAYER			= 0
ENC_BACK			= 1
ENC_SNAPSHOT		= 2
ENC_SELECT			= 3
OSK_NUMPAD			= 0
OSK_QWERTY			= 1

# Class implements renaming dialog
class zynthian_gui_keyboard():

	# Function to initialise class
	#	function: Callback function called when <Enter> pressed
	def __init__(self):

		self.zyngui = zynthian_gui_config.zyngui
		self.columns = 10 # Quantity of columns in keyboard grid
		self.rows = 5 # Quantity of rows in keyboard grid
		self.shift = 0 # 0=Normal, 1=Shift, 2=Shift lock
		self.buttons = [] # Array of [rectangle id, label id] for buttons in keyboard layout
		self.selected_button = 44 # Index of highlighted button
		self.mode = OSK_QWERTY # Keyboard layout mode

		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.display_height - zynthian_gui_config.topbar_height

		# Create main frame
		self.main_frame = tkinter.Frame(zynthian_gui_config.top,
			width=zynthian_gui_config.display_width,
			height=zynthian_gui_config.display_height,
			bg=zynthian_gui_config.color_bg)
		self.main_frame.grid_propagate(False)

		# Display string being edited
		self.text_canvas = tkinter.Canvas(self.main_frame, width=self.width, height=zynthian_gui_config.topbar_height)
		self.text_label = self.text_canvas.create_text(self.width / 2, zynthian_gui_config.topbar_height / 2,
		font=zynthian_gui_config.font_topbar,
		#font=tkFont.Font(family=zynthian_gui_config.font_topbar[0], size= int(zynthian_gui_config.topbar_height * 0.8))
		)
		self.text_canvas.grid(column=0, row=0, sticky="nsew")

		# Display keyboard grid
		self.key_canvas = tkinter.Canvas(self.main_frame, width=self.width, height = self.height, bg="grey")
		self.key_canvas.grid_propagate(False)
		self.key_canvas.grid(column=0, row=1, sticky="nesw")
		self.set_mode(OSK_QWERTY)

		self.highlight(self.selected_button)
		self.hold_timer = Timer(0.8, self.bold_press)
		self.shown = False


	# Function to populate keyboard with keys for requested mode
	#	mode: OSK mode [OSK_NUMPAD | OSK_QWERTY]
	def set_mode(self, mode):
		self.mode = mode
		self.key_canvas.delete('all')
		self.buttons = []
		if mode == OSK_NUMPAD:
			self.columns = 6
			self.rows = 4
			span = 2
		else:
			self.columns = 10
			self.rows = 5
			span = 1
		self.key_width = (self.width - 2) / self.columns
		self.key_height = (self.height - 2) / self.rows
		for row in range(self.rows - 1):
			for col in range(0, self.columns, span):
				self.add_button("", col, row, span)
		row = row + 1
		# Add special keys
		self.btn_cancel = self.add_button('Cancel', 0, row, 2)
		if mode != OSK_NUMPAD:
			self.btn_shift = self.add_button('Shift', 2, row, 1)
		if mode == OSK_NUMPAD:
			self.btn_space = self.add_button('0', 2, row, span)
			self.btn_delete = self.add_button('Delete', 4, row, 1)
			self.btn_enter = self.add_button('Enter', 5, row, 1)
		else:
			self.btn_space = self.add_button(' ', 3, row, 4)
			self.btn_delete = self.add_button('Delete', 7, row, 1)
			self.btn_enter = self.add_button('Enter', 8, row, 2)
		self.highlight_box = self.key_canvas.create_rectangle(0, 0, self.key_width, self.key_height, outline="red", width=2)
		self.refresh_keys()


	# Function to draw keyboard
	def refresh_keys(self):
		if self.mode == OSK_NUMPAD:
			self.keys = ['1','2','3',
						'4','5','6',
						'7','8','9']
		elif self.shift:
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
		self.key_canvas.tag_bind(tag, "<ButtonRelease-1>", self.on_key_release)
		self.buttons.append([r,l])
		return index


	# Function to handle bold touchscreen press and hold
	def bold_press(self):
		self.execute_key_press(self.btn_delete, True)


	# Function to handle key press
	#	event: Mouse event
	def on_key_press(self, event=None):
		tags = self.key_canvas.gettags(self.key_canvas.find_withtag(tkinter.CURRENT))
		if not tags:
			return
		dummy, index = tags[0].split(':')
		key = int(index)
		if key == self.btn_delete:
			self.hold_timer = Timer(0.8, self.bold_press)
			self.hold_timer.start()
		self.execute_key_press(key)


	# Function to handle key release
	#	event: Mouse event
	def on_key_release(self, event=None):
		self.hold_timer.cancel()


	# Function to execute a key press
	#	key: Index of key
	#	bold: True if long / bold press
	def execute_key_press(self, key, bold=False):
		#TODO: Use button ID for special function to allow localisation
		self.selected_button = key
		shift = self.shift
		if key < len(self.keys):
			self.text= self.text+ self.keys[key]
		elif key == self.btn_enter:
			self.zyngui.close_modal()
			self.function(self.text)
			return
		elif key == self.btn_cancel:
			self.zyngui.zynswitch_defered('S', ENC_BACK)
			return
		elif key == self.btn_delete:
			if bold:
				self.text= ""
			else:
				self.text= self.text[:-1]
		elif key == self.btn_space:
			if self.mode == OSK_NUMPAD:
				self.text= self.text+ "0"
			else:
				self.text= self.text+ " "
		if key == self.btn_shift:
			self.shift += 1
			if self.shift > 2:
				self.shift = 0
		elif self.shift == 1:
			self.shift = 0
		if self.max_len:
			self.text= self.text[:self.max_len]
		if shift != self.shift:
			if self.shift == 1:
				self.key_canvas.itemconfig(self.buttons[self.btn_shift][0], fill="grey")
			elif self.shift == 2:
				self.key_canvas.itemconfig(self.buttons[self.btn_shift][0], fill="red")
			else:
				self.key_canvas.itemconfig(self.buttons[self.btn_shift][0], fill="black")
			self.refresh_keys()
		self.text_canvas.itemconfig(self.text_label, text=self.text)
		self.highlight(key)


	# Function to highlight key
	def highlight(self, key):
		if key >= len(self.buttons):
			return
		box = self.key_canvas.bbox(self.buttons[key][0])
		if box:
			self.key_canvas.coords(self.highlight_box, box[0]+1, box[1]+1, box[2], box[3])
			self.selected_button = key


	# Function to hide dialog
	def hide(self):
		if self.shown:
			self.shown=False
			self.main_frame.grid_forget()


	# Function to show keyboard as modal screen
	#	text: Text to display (Default: empty)
	#	max_len: Maximum quantity of characters in text (Default: no limit)
	def show(self,  function, text="", max_len=None):
		self.function = function
		self.text= text
		if max_len:
			self.text= text[:max_len]
		self.max_len = max_len
		self.text_canvas.itemconfig(self.text_label, text=self.text)
		if not self.shown:
			self.selected_button = self.btn_enter
			self.highlight(self.selected_button)
			self.setup_encoders()
			self.main_frame.grid()
			self.shown=True


	# Function to register encoders
	def setup_encoders(self):
		if lib_zyncore:
			lib_zyncore.setup_rangescale_zynpot(ENC_SELECT, 0, 127, 64, 1)
			lib_zyncore.setup_midi_zynpot(ENC_SELECT, 0, 0)
			lib_zyncore.setup_osc_zynpot(ENC_SELECT, None)

			lib_zyncore.setup_rangescale_zynpot(ENC_BACK, 0, 127, 64, 1)
			lib_zyncore.setup_midi_zynpot(ENC_BACK, 0, 0)
			lib_zyncore.setup_osc_zynpot(ENC_BACK, None)



	# Function to handle zyncoder value change
	#	encoder: Zyncoder index [0..4]
	#	value: Current value of zyncoder
	def on_zyncoder(self, encoder, value):
		if encoder == ENC_SELECT:
			# SELECT encoder select key
			self.selected_button = self.selected_button + value
			if self.selected_button < 0:
				self.selected_button = len(self.buttons) - 1
			if self.selected_button >= len(self.buttons):
				self.selected_button = 0
			self.highlight(self.selected_button)
		elif encoder == ENC_BACK:
			selection = self.selected_button + value * int(len(self.keys) / (self.rows - 1))
			if self.mode == OSK_NUMPAD:
				if value < 0 and self.selected_button == self.btn_enter:
					selection = 8
				elif value > 0 and self.selected_button == self.btn_cancel:
					selection = self.btn_cancel
			else:
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


	# Function to handle zyncoder polling
	#	Note: Zyncoder provides positive integers. We need +/- 1 so we keep zyncoder at +64 and calculate offset
	def zyncoder_read(self):
		if not self.shown:
			return
		if lib_zyncore:
			value = lib_zyncore.get_value_zynpot(ENC_BACK)
			if value != 64:
				self.on_zyncoder(ENC_BACK, value - 64)
				lib_zyncore.set_value_zynpot(ENC_BACK, 64)
			value = lib_zyncore.get_value_zynpot(ENC_SELECT)
			if value != 64:
				self.on_zyncoder(ENC_SELECT, value - 64)
				lib_zyncore.set_value_zynpot(ENC_SELECT, 64)
			return

			value = lib_zyncore.get_value_zynpot(ENC_SELECT)
			if self.selected_button == value:
				return
			if value >= len(self.buttons):
				lib_zyncore.set_value_zynpot(ENC_SELECT, 1)
				return
			elif value < 0:
				lib_zyncore.set_value_zynpot(ENC_SELECT, len(self.buttons))
				return
			self.selected_button = value
			self.highlight(value)


	# Function to handle CUIA BACK_UP command
	def back_up(self):
		if lib_zyncore:
			lib_zyncore.set_value_zynpot(ENC_BACK, lib_zyncore.get_value_zynpot(ENC_BACK) + 1)


	# Function to handle CUIA BACK_DOWN command
	def back_down(self):
		if lib_zyncore:
			lib_zyncore.set_value_zynpot(ENC_BACK, lib_zyncore.get_value_zynpot(ENC_BACK) - 1)


	# Function to handle CUIA SELECT_UP command
	def select_up(self):
		if lib_zyncore:
			lib_zyncore.set_value_zynpot(ENC_SELECT, lib_zyncore.get_value_zynpot(ENC_SELECT) + 1)


	# Function to handle CUIA SELECT_DOWN command
	def select_down(self):
		if lib_zyncore:
			lib_zyncore.set_value_zynpot(ENC_SELECT, lib_zyncore.get_value_zynpot(ENC_SELECT) - 1)


	def switch_select(self, type):
		self.execute_key_press(self.selected_button, type=="B")


	# Function to handle switch press
	#	switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def switch(self, switch, type):
		return False
		if switch == ENC_BACK:
			pass
#			self.zyngui.zynswitch_defered('S', ENC_BACK)
#			self.hide()
		elif switch == ENC_SELECT:
			self.execute_key_press(self.selected_button, type=="B")
		return True # Tell parent that we handled all short and bold key presses


	# Function to refresh the loading screen (not used)
	def refresh_loading(self):
		pass


#------------------------------------------------------------------------------
