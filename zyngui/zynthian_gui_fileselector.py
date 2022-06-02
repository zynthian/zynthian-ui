#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI File Selector Class
# 
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
# Copyright (C) 2015-2022 Brian Walton <brian@riban.co.uk>
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
import tkinter.font as tkFont
import glob
import os.path
import time
from PIL import Image, ImageTk

# Zynthian specific modules
from zyngui import zynthian_gui_config

#------------------------------------------------------------------------------
# Zynthian File-Selector GUI Class
#------------------------------------------------------------------------------

# Class implements file selector dialog
class zynthian_gui_fileselector():

	# Function to initialise class
	#	parent: Parent instance
	#	function: Function to call when file selected (passes filename without path or extension as only parameter)
	#	path: Filesystem path to show
	#	ext: File extension to filter
	#	filename: Name of file to select in list (Optional: Defaults to first file)
	#	return_full_path: True to return full path. False to return filename (Optional: Defaults to filename only)
	def __init__(self, parent, function, path, ext, filename=None, return_full_path=False):
		self.parent = parent

		self.function = function
		self.path = path
		self.filename = filename
		self.return_full_path = return_full_path
		self.ext = ext
		self.files = {}

		# Cancel button
		self.tb_panel = tkinter.Frame(parent.tb_frame,
			width=zynthian_gui_config.display_width,
			height=zynthian_gui_config.display_height,
			bg=zynthian_gui_config.color_bg)
		self.tb_panel.grid_propagate(False)
		self.tb_panel.grid(column=0, row=0, columnspan=5)

		iconsize = (zynthian_gui_config.topbar_height - 2, zynthian_gui_config.topbar_height - 2)
		self.imgBack = ImageTk.PhotoImage(Image.open("/zynthian/zynthian-ui/icons/back.png").resize(iconsize))
		self.btnCancel = tkinter.Button(self.tb_panel, command=self.hide,
			image=self.imgBack,
			bd=0, highlightthickness=0,
			relief=tkinter.FLAT, activebackground=zynthian_gui_config.color_bg, bg=zynthian_gui_config.color_bg)
		self.btnCancel.grid(column=0, row=0, columnspan=5)

		# File listbox
		self.listboxTextHeight = tkFont.Font(font=zynthian_gui_config.font_listbox).metrics('linespace')
		self.file_list = tkinter.Listbox(self.parent.main_frame,
			font=zynthian_gui_config.font_listbox,
			bd=2,
			highlightthickness=0,
			relief='flat',
			bg=zynthian_gui_config.color_panel_bg,
			fg=zynthian_gui_config.color_panel_tx,
			selectbackground=zynthian_gui_config.color_ctrl_bg_on,
			selectforeground=zynthian_gui_config.color_ctrl_tx,
			selectmode=tkinter.BROWSE)
		self.file_list.bind('<Button-1>', self.on_listbox_press)
		self.file_list.bind('<B1-Motion>', self.on_listbox_drag)
		self.file_list.bind('<ButtonRelease-1>', self.on_listbox_release)
		self.scrollTime = 0.0

		for full_filename in glob.glob('%s/*.%s' % (path, ext)):
			filename = os.path.basename(full_filename)
			name = os.path.splitext(filename)[0]
			self.file_list.insert(tkinter.END, name)
			self.files[name] = full_filename 
		self.file_list.selection_set(0)

		rows = min((zynthian_gui_config.display_height - zynthian_gui_config.topbar_height) / self.listboxTextHeight - 1, self.file_list.size())
		self.file_list.configure(height = int(rows))

		self.file_list.grid(row=1, column=0, sticky="nsew")
		self.setup_encoders()


	# Function to handle listbox press
	#	event: Mouse event
	def on_listbox_press(self, event):
		pass


	# Function to handle listbox drag
	#	event: Mouse event
	def on_listbox_drag(self, event):
		now = time.monotonic()
		if self.scrollTime < now:
			self.scrollTime = now + 0.1
			try:
				item = self.file_list.curselection()[0]
				self.file_list.see(item + 1)
				self.file_list.see(item - 1)
			except:
				pass


	# Function to handle listbox release
	#	event: Mouse event
	def on_listbox_release(self, event):
		self.assert_selection()


	# Function to trigger file action
	def assert_selection(self):
		if self.return_full_path:
			self.function(self.files[self.file_list.get(self.file_list.curselection()[0])])
		else:
			self.function(self.file_list.get(self.file_list.curselection()))
		self.hide()


	# Function to delete file
	def delete_confirmed(self, filename):
		os.remove(self.path + "/" + filename + "." + self.ext)


	# Function to hide dialog
	def hide(self):
		self.parent.unregister_zyncoder(zynthian_gui_config.ENC_SELECT)
		self.parent.unregister_switch(zynthian_gui_config.ENC_SELECT, "SB")
		self.parent.unregister_switch(zynthian_gui_config.ENC_BACK)
		self.file_list.destroy()
#		self.btnCancel.destroy()
		self.tb_panel.destroy()
		self.parent.show_child(self.parent.child)


	# Function to register encoders
	def setup_encoders(self):
		self.parent.register_zyncoder(zynthian_gui_config.ENC_SELECT, self)
		self.parent.register_switch(zynthian_gui_config.ENC_SELECT, self, "SB")
		self.parent.register_switch(zynthian_gui_config.ENC_BACK, self)


	# Function to handle zyncoder value change
	#	encoder: Zyncoder index [0..4]
	#	value: Current value of zyncoder
	def on_zyncoder(self, encoder, value):
		if encoder == zynthian_gui_config.ENC_SELECT:
			# SELECT encoder select file
			try:
				index = self.file_list.curselection()[0]
			except:
				logging.error("Problem detecting file selection")
				self.file_list.selection_set(0)

			index = index + value
			if index < 0:
				index = 0
			if index >= self.file_list.size():
				index = self.file_list.size() - 1
			self.file_list.selection_clear(0,tkinter.END)
			self.file_list.selection_set(index)
			self.file_list.activate(index)
			self.file_list.see(index)


	# Function to handle switch press
	#	switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def on_switch(self, switch, type):
		if switch == zynthian_gui_config.ENC_SELECT and type == 'B':
			filename = self.file_list.get(self.file_list.curselection()[0])
			self.parent.zyngui.show_confirm("Do you really want to delete %s?"%(filename), self.delete_confirmed, filename)
		elif switch == zynthian_gui_config.ENC_BACK:
			self.hide()
		elif switch == zynthian_gui_config.ENC_SELECT:
			self.assert_selection()
		return True # Tell parent that we handled all short and bold key presses
#------------------------------------------------------------------------------
