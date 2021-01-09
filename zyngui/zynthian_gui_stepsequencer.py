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
import sys
import os
import tkinter
import logging
import tkinter.font as tkFont
import time
from threading import Timer
import ctypes
from os.path import dirname, realpath
from PIL import Image, ImageTk

# Zynthian specific modules
from . import zynthian_gui_base
from . import zynthian_gui_config
from zyncoder import *
from zyngui.zynthian_gui_patterneditor import zynthian_gui_patterneditor
from zyngui.zynthian_gui_songeditor import zynthian_gui_songeditor
from zyngui.zynthian_gui_zynpad import zynthian_gui_zynpad
from zyngui.zynthian_gui_fileselector import zynthian_gui_fileselector
from zyngui.zynthian_gui_rename import zynthian_gui_rename

#------------------------------------------------------------------------------
# Zynthian Step-Sequencer GUI Class
#------------------------------------------------------------------------------

# Local constants
CANVAS_BACKGROUND	= zynthian_gui_config.color_panel_bg
HEADER_BACKGROUND	= zynthian_gui_config.color_header_bg
# Define encoder use: 0=Layer, 1=Back, 2=Snapshot, 3=Select
ENC_LAYER			= 0
ENC_BACK			= 1
ENC_SNAPSHOT		= 2
ENC_SELECT			= 3

#------------------------------------------------------------------------------
# Sequence states
#------------------------------------------------------------------------------
SEQ_DISABLED		= 0
SEQ_ONESHOT			= 1
SEQ_LOOP			= 2
SEQ_ONESHOTALL		= 3
SEQ_LOOPALL			= 4
SEQ_LASTPLAYMODE	= 4

SEQ_STOPPED			= 0
SEQ_PLAYING			= 1
SEQ_STOPPING		= 2
SEQ_STARTING		= 3
SEQ_LASTPLAYSTATUS	= 3

USER_PATH			= "/zynthian/zynthian-my-data/zynseq"

PLAY_MODES = ['Disabled', 'Oneshot', 'Loop', 'Oneshot all', 'Loop all', 'Oneshot sync', 'Loop sync']
PAD_COLOUR_DISABLED = 'grey'
PAD_COLOUR_STARTING = 'orange'
PAD_COLOUR_PLAYING = 'green'
PAD_COLOUR_STOPPING = 'red'
PAD_COLOUR_STOPPED_ODD = 'purple'
PAD_COLOUR_STOPPED_EVEN = 'blue'

# Class implements zynthian step sequencer parent, hosting child screens:editors, players, etc.
class zynthian_gui_stepsequencer(zynthian_gui_base.zynthian_gui_base):

	buttonbar_config = [
		(1, 'BACK'),
		(0, 'MENU'),
		(2, ''),
		(3, 'TOGGLE')
	]


	# Function to initialise class
	def __init__(self):
		super().__init__()
		self.shown = False # True when GUI in view
		self.zyncoder_owner = [None, None, None, None] # Object that currently "owns" encoder, indexed by encoder
		self.switch_owner = [None] * 12 # Object that currently "owns" switch, indexed by (switch *3 + type)
		self.zyngui = zynthian_gui_config.zyngui # Zynthian GUI configuration
		self.child = None # Pointer to instance of child panel
		self.last_child = None # Pointer to instance of last child shown - used to return to same screen
		self.song = 1 # The song that will play / edit (may be different to libseq.getSong, e.g. when editing pattern)

		# Load default sequence file
		self.filename = "default"
		self.load(self.filename)

		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.display_height

		# Title
#		font=tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=int(self.height * 0.05)),
		font=zynthian_gui_config.font_topbar
		self.title_canvas = tkinter.Canvas(self.tb_frame,
			height=zynthian_gui_config.topbar_height,
			bd=0,
			highlightthickness=0,
			bg = zynthian_gui_config.color_header_bg)
		self.title_canvas.grid_propagate(False)
		self.title_canvas.create_text(0, zynthian_gui_config.topbar_height / 2,
			font=font,
			anchor="w",
			fill=zynthian_gui_config.color_panel_tx,
			tags="lblTitle",
			text="Step Sequencer")
		self.title_canvas.grid(row=0, column=0, sticky='ew')
		self.title_canvas.bind('<Button-1>', self.toggle_menu)

		iconsize = (zynthian_gui_config.topbar_height - 2, zynthian_gui_config.topbar_height - 2)
		img = (Image.open("/zynthian/zynthian-ui/icons/play.png").resize(iconsize))
		self.image_play = ImageTk.PhotoImage(img)
		pixdata = img.load()
		for y in range(img.size[1]):
			for x in range(img.size[0]):
				if pixdata[x, y][0] == (255):
					pixdata[x, y] = (0, 255, 0, pixdata[x, y][3])
		self.image_playing = ImageTk.PhotoImage(img)
		self.image_back = ImageTk.PhotoImage(Image.open("/zynthian/zynthian-ui/icons/back.png").resize(iconsize))
		self.image_forward = ImageTk.PhotoImage(Image.open("/zynthian/zynthian-ui/icons/tick.png").resize(iconsize))
		img = (Image.open("/zynthian/zynthian-ui/icons/arrow.png").resize(iconsize))
		self.image_up = ImageTk.PhotoImage(img)
		self.image_down = ImageTk.PhotoImage(img.rotate(180))

		# Parameter value editor
		self.param_editor_item = None
		self.menu_items = {} # Dictionary of menu items
		self.param_editor_canvas = tkinter.Canvas(self.tb_frame,
			height=zynthian_gui_config.topbar_height,
			bd=0, highlightthickness=0)
		self.param_editor_canvas.grid_propagate(False)
		self.param_editor_canvas.bind('<Button-1>', self.hide_param_editor)

		if zynthian_gui_config.enable_touch_widgets:
			# Parameter editor cancel button
			self.button_param_cancel = tkinter.Button(self.param_editor_canvas, command=self.hide_param_editor,
				image=self.image_back,
				bd=0, highlightthickness=0,
				relief=tkinter.FLAT, activebackground=zynthian_gui_config.color_header_bg, bg=zynthian_gui_config.color_header_bg)
			self.button_param_cancel.grid(column=0, row=0)
			# Parameter editor decrement button
			self.button_param_down = tkinter.Button(self.param_editor_canvas, command=self.decrement_param,
				image=self.image_down,
				bd=0, highlightthickness=0, repeatdelay=500, repeatinterval=100,
				relief=tkinter.FLAT, activebackground=zynthian_gui_config.color_header_bg, bg=zynthian_gui_config.color_header_bg)
			self.button_param_down.grid(column=1, row=0)
			# Parameter editor increment button
			self.button_param_up = tkinter.Button(self.param_editor_canvas, command=self.increment_param,
				image=self.image_up,
				bd=0, highlightthickness=0, repeatdelay=500, repeatinterval=100,
				relief=tkinter.FLAT, activebackground=zynthian_gui_config.color_header_bg, bg=zynthian_gui_config.color_header_bg)
			self.button_param_up.grid(column=2, row=0)
			# Parameter editor assert button
			self.button_param_assert = tkinter.Button(self.param_editor_canvas, command=self.menu_value_assert,
				image=self.image_forward,
				bd=0, highlightthickness=0,
				relief=tkinter.FLAT, activebackground=zynthian_gui_config.color_header_bg, bg=zynthian_gui_config.color_header_bg)
			self.button_param_assert.grid(column=3, row=0)
		# Parameter editor value text
		self.param_title_canvas = tkinter.Canvas(self.param_editor_canvas, height=zynthian_gui_config.topbar_height, bd=0, highlightthickness=0, bg=zynthian_gui_config.color_header_bg)
		self.param_title_canvas.create_text(3, zynthian_gui_config.topbar_height / 2,
			anchor='w',
			font=zynthian_gui_config.font_topbar,
#			font=tkFont.Font(family=zynthian_gui_config.font_topbar[0],
#				size=int(self.height * 0.05)),
			fill=zynthian_gui_config.color_panel_tx,
			tags="lbl_param_editor_value",
			text="VALUE...")
		self.param_title_canvas.grid(column=4, row=0, sticky='ew')
		self.param_editor_canvas.grid_columnconfigure(4, weight=1)
		self.param_title_canvas.bind('<Button-1>', self.hide_param_editor)


		#TODO: Consolidate menu to base class
		self.status_canvas.bind('<Button-1>', self.toggle_status_menu)

		# Menu #TODO: Replace listbox with painted canvas providing swipe gestures
		self.listbox_text_height = tkFont.Font(font=zynthian_gui_config.font_listbox).metrics('linespace')
		self.lst_menu = tkinter.Listbox(self.main_frame,
			font=zynthian_gui_config.font_listbox,
			bd=7,
			highlightthickness=0,
			relief='flat',
			bg=zynthian_gui_config.color_panel_bg,
			fg=zynthian_gui_config.color_panel_tx,
			selectbackground=zynthian_gui_config.color_ctrl_bg_on,
			selectforeground=zynthian_gui_config.color_ctrl_tx,
			selectmode=tkinter.BROWSE)
		self.lst_menu.bind('<Button-1>', self.on_menu_press)
		self.lst_menu.bind('<B1-Motion>', self.on_menu_drag)
		self.lst_menu.bind('<ButtonRelease-1>', self.on_menu_release)
		self.scrollTime = 0.0
		if zynthian_gui_config.enable_touch_widgets:
			self.menu_button_canvas = tkinter.Canvas(self.tb_frame,
				height=zynthian_gui_config.topbar_height,
				bg=zynthian_gui_config.color_bg, bd=0, highlightthickness=0)
			self.menu_button_canvas.grid_propagate(False)
			self.menu_button_canvas.bind('<Button-1>', self.hide_menu)
			self.btn_menu_back = tkinter.Button(self.menu_button_canvas, command=self.close_panel_manager,
				image=self.image_back,
				bd=0, highlightthickness=0,
				relief=tkinter.FLAT, activebackground=zynthian_gui_config.color_header_bg, bg=zynthian_gui_config.color_header_bg)
			self.btn_menu_back.grid(column=0, row=0)
			self.menu_button_canvas.grid_columnconfigure(4, weight=1)

		self.status_menu_frame = tkinter.Frame(self.main_frame)

		img = (Image.open("/zynthian/zynthian-ui/icons/stop.png").resize(iconsize))
		self.image_stop = ImageTk.PhotoImage(img)
		self.button_stop = tkinter.Button(self.status_menu_frame, command=self.stop,
			image=self.image_stop,
			bd=0, highlightthickness=0,
			relief=tkinter.FLAT, activebackground=zynthian_gui_config.color_header_bg, bg=zynthian_gui_config.color_header_bg)
		self.button_stop.grid()

		self.button_transport = tkinter.Button(self.status_menu_frame, command=self.toggle_transport,
			image=self.image_play,
			bd=0, highlightthickness=0,
			relief=tkinter.FLAT, activebackground=zynthian_gui_config.color_header_bg, bg=zynthian_gui_config.color_header_bg)
		self.button_transport.grid()

		self.pattern_editor = zynthian_gui_patterneditor(self)
		self.song_editor = zynthian_gui_songeditor(self)
		self.zynpad = zynthian_gui_zynpad(self)

		# Init touchbar
		self.init_buttonbar()

		self.select_song(self.song)
		self.populate_menu()
		self.param_editor_timer = None


	# Function to print traceback - for debug only
	#	TODO: Remove debug function (or move to other zynthian class)
	def debug_traceback(self):
		for trace in inspect.stack():
			print(trace.function)


	# Function to close the panel manager
	def close_panel_manager(self):
		self.hide_menu()
		self.zyngui.zynswitch_defered('S', 1)


	# Function to populate menu with global entries
	def populate_menu(self):
		self.lst_menu.delete(0, tkinter.END)
		self.menu_items = {} # Dictionary of menu items
		self.add_menu({'ZynPad':{'method':self.show_child, 'params':"zynpad"}})
		self.add_menu({'Pad Editor':{'method':self.show_child, 'params':"pad editor"}})
#		self.addMenu({'Song Editor':{'method':self.show_child, 'params':"song editor"}})
		self.add_menu({'Song':{'method':self.show_param_editor, 'params':{'min':1, 'max':999, 'get_value':self.zyngui.libseq.getSong, 'on_change':self.on_menu_change}}})
		self.add_menu({'Tempo':{'method':self.show_param_editor, 'params':{'min':1, 'max':999, 'get_value':self.zyngui.libseq.getTempo, 'on_change':self.on_menu_change}}})
		self.add_menu({'Load':{'method':self.select_filename, 'params':self.filename}})
		self.add_menu({'Save':{'method':self.save_as, 'params':self.filename}})
		self.add_menu({'---':{}})


	# Function to update title
	#	title: Title to display in topbar
	#	fg: Title foreground colour [Default: Do not change]
	#	bg: Title background colour [Default: Do not change]
	def set_title(self, title, fg=None, bg=None):
		self.title_canvas.itemconfig("lblTitle", text=title)
		if fg:
			self.title_canvas.itemconfig("lblTitle", fill=fg)
		if bg:
			self.title_canvas.configure(bg=bg)


	# Function to show GUI
	def show(self):
		if not self.shown:
			self.shown=True
			self.main_frame.grid_propagate(False)
			self.main_frame.grid(column=0, row=0)
			self.show_child()
		self.main_frame.focus()


	# Function to hide GUI
	def hide(self):
		if self.shown:
			self.shown=False
			self.main_frame.grid_forget()
			if self.child:
				self.child.hide()
			if self.zyngui.libseq.isModified():# and not self.zyngui.libseq.transportGetPlayStatus():
				self.save()


	# Function to refresh the status widgets
	#	status: Dictionary containing update data
	def refresh_status(self, status={}):
		if self.shown:
			super().refresh_status(status)
			# Refresh child panel
			if self.child:
				self.child.refresh_status()


	# Function to open menu
	def show_menu(self):
		self.populate_menu()
		if self.child:
			self.child.populate_menu()
		button_height = 0
		if zynthian_gui_config.enable_touch_widgets:
			button_height = zynthian_gui_config.buttonbar_height
		rows = min((self.height - zynthian_gui_config.topbar_height - button_height) / self.listbox_text_height - 1, self.lst_menu.size())
		self.lst_menu.configure(height = int(rows))
		self.lst_menu.grid(column=0, row=1, sticky="nw")
		self.lst_menu.tkraise()
		self.lst_menu.selection_clear(0,tkinter.END)
		self.lst_menu.activate(0)
		self.lst_menu.selection_set(0)
		self.lst_menu.see(0)
		for encoder in range(4):
			self.unregister_zyncoder(encoder)
		self.register_switch(ENC_SELECT, self)
		self.register_switch(ENC_BACK, self)
		if zynthian_gui_config.enable_touch_widgets:
			self.menu_button_canvas.grid()
			self.menu_button_canvas.grid_propagate(False)
			self.menu_button_canvas.grid(column=0, row=0, sticky='nsew')


	# Function to close menu
	#	event: Mouse event (not used)
	def hide_menu(self, event=None):
		self.hide_param_editor()
		self.unregister_zyncoder(ENC_SELECT)
		self.lst_menu.grid_forget()
		if zynthian_gui_config.enable_touch_widgets:
			self.menu_button_canvas.grid_forget()
		for encoder in range(4):
			self.unregister_zyncoder(encoder)
		if self.child:
			self.child.setup_encoders()

	# Function to handle title bar click
	#	event: Mouse event (not used)
	def toggle_menu(self, event=None):
		if self.lst_menu.winfo_viewable():
			self.hide_menu()
		else:
			self.show_menu()


	# Function to open status menu
	def show_status_menu(self):
		self.status_menu_frame.grid(column=0, row=1, sticky="ne")
		self.status_menu_frame.tkraise()


	# Function to close status menu
	def hide_status_menu(self):
		self.status_menu_frame.grid_forget()


	# Function to handle status bar click
	#	event: Mouse event (not used)
	def toggle_status_menu(self, event=None):
		if self.status_menu_frame.winfo_viewable():
			self.hide_status_menu()
		else:
			self.show_status_menu()


	# Function to handle press menu
	def on_menu_press(self, event):
		pass


	# Function to handle motion menu
	def on_menu_drag(self, event):
		now = time.monotonic()
		if self.scrollTime < now:
			self.scrollTime = now + 0.1
			try:
				item = self.lst_menu.curselection()[0]
				self.lst_menu.see(item + 1)
				self.lst_menu.see(item - 1)
			except:
				pass
		#self.lstMenu.winfo(height)
		pass


	# Function to handle release menu
	def on_menu_release(self, event):
		self.on_menu_select()


	# Function to handle menu item selection (SELECT button or click on listbox entry)
	def on_menu_select(self):
		if self.lst_menu.winfo_viewable():
			menu_item = None
			action = None
			params = {}
			try:
				menu_item = self.lst_menu.get(self.lst_menu.curselection()[0])
				action = self.menu_items[menu_item]['method']
				params = self.menu_items[menu_item]['params']
			except:
				logging.error("**Error selecting menu**")
			self.hide_menu()
			if not menu_item:
				return
			if action == self.show_param_editor:
				self.show_param_editor(menu_item)
			elif action:
				action(params) # Call menu handler defined during addMenu


	# Function to add items to menu
	#	item: Dictionary containing menu item data, indexed by menu item title
	#		Dictionary should contain {'method':<function to call when menu selected>} and {'params':<parameters to pass to method>}
	def add_menu(self, item):
		self.menu_items.update(item)
		self.lst_menu.insert(tkinter.END, list(item)[0])


	# Function to set menu data parameters
	#	item: Menu item name
	#	param: Parameter name
	#	value: Parameter value
	def set_param(self, item, param, value):
		if item in self.menu_items:
			self.menu_items[item]['params'].update({param: value})


	# Function to refresh parameter editor display
	def refreshParamEditor(self):
		self.param_title_canvas.itemconfig("lbl_param_editor_value", 
			text=self.menu_items[self.param_editor_item]['params']['on_change'](self.menu_items[self.param_editor_item]['params']))


	# Function to get menu data parameters
	#	item: Menu item name
	#	param: Parameter name
	#	returns: Parameter value
	def get_param(self, item, param):
		if item in self.menu_items and param in self.menu_items[item]['params']:
			return self.menu_items[item]['params'][param]
		return None


	# Function to show menu editor
	#	menuitem: Name of the menu item who's parameters to edit
	#	timeout: Seconds before hiding (don't show any editor buttons)
	def show_param_editor(self, menu_item, timeout=0):
		if not menu_item in self.menu_items:
			return
		self.param_editor_item = menu_item
		if self.get_param(menu_item, 'get_value'):
			self.set_param(menu_item, 'value', self.get_param(menu_item, 'get_value')())
		self.param_editor_canvas.grid_propagate(False)
		self.param_editor_canvas.grid(column=0, row=0, sticky='nsew')
		# Get the value to display in the param editor
		self.param_title_canvas.itemconfig("lbl_param_editor_value", 
			text=self.menu_items[menu_item]['params']['on_change'](self.menu_items[menu_item]['params'])
			)
		if timeout:
			if self.param_editor_timer:
				self.param_editor_timer.cancel()
			self.param_editor_timer = Timer(timeout, self.hide_param_editor)
			self.param_editor_timer.start()
			return
		if 'on_assert' in self.menu_items[menu_item]['params']:
			self.param_editor_canvas.itemconfig("btnparamEditorAssert", state='normal')
		else:
			self.param_editor_canvas.itemconfig("btnparamEditorAssert", state='hidden')
		for encoder in range(4):
			self.unregister_zyncoder(encoder)
		self.register_switch(ENC_SELECT, self)
		self.register_switch(ENC_BACK, self)


	# Function to hide menu editor
	#	event: Mouse event (not used)
	def hide_param_editor(self, event=None):
		if self.param_editor_timer:
			self.param_editor_timer.cancel()
			self.param_editor_timer = None
		self.param_editor_item = None
		self.param_editor_canvas.grid_forget()
		for encoder in range(4):
			self.unregister_zyncoder(encoder)
		if self.child:
			self.child.setup_encoders()


	# Function to handle menu editor value change and get display label text
	#	params: Menu item's parameters
	#	returns: String to populate menu editor label
	#	note: This is default but other method may be used for each menu item
	#	note: params is a dictionary with required fields: min, max, value
	def on_menu_change(self, params):
		value = params['value']
		if value < params['min']:
			value = params['min']
		if value > params['max']:
			value = params['max']
		if self.param_editor_item == 'Song':
			self.select_song(value)
		elif self.param_editor_item == 'Tempo':
			self.zyngui.libseq.setTempo(value)
		self.set_param(self.param_editor_item, 'value', value)
		return "%s: %d" % (self.param_editor_item, value)


	# Function to change parameter value
	#	value: Offset by which to change parameter value
	def change_param(self, value):
		value = self.get_param(self.param_editor_item, 'value') + value
		if value < self.get_param(self.param_editor_item, 'min'):
			if self.get_param(self.param_editor_item, 'value' == value):
				return
			value = self.get_param(self.param_editor_item, 'min')
		if value > self.get_param(self.param_editor_item, 'max'):
			if self.get_param(self.param_editor_item, 'value' == value):
				return
			value = self.get_param(self.param_editor_item, 'max')
		self.set_param(self.param_editor_item, 'value', value)
		result = self.get_param(self.param_editor_item, 'on_change')(self.menu_items[self.param_editor_item]['params'])
		if result == -1:
			self.parent.hide_param_editor()
		else:
			self.param_title_canvas.itemconfig("lbl_param_editor_value", text=result)


	# Function to decrement parameter value
	def decrement_param(self):
		self.change_param(-1)


	# Function to increment selected menu value
	def increment_param(self):
		self.change_param(1)


	# Function to assert selected menu value
	def menu_value_assert(self):
		if self.param_editor_item and 'on_assert' in self.menu_items[self.param_editor_item]['params'] and self.menu_items[self.param_editor_item]['params']['on_assert']:
			self.menu_items[self.param_editor_item]['params']['on_assert']()
		self.hide_param_editor()


	# Function to show child GUI
	#	name: Name of child to show
	#	params: Dictionary of parameters to pass to child class show() method
	def show_child(self, name=None, params={}):
		if not self.shown:
			return
		if not name:
			name = "zynpad"
		self.hide_child()
		self.buttonbar_config[2] = (2, '')
		if name == "song editor":
			self.zyngui.libseq.selectSong(self.song)
			self.child = self.song_editor
		elif name == "pad editor":
			self.zyngui.libseq.selectSong(self.song)
			self.child = self.song_editor
			try:
				params["track"] = self.zynpad.selected_pad
			except:
				pass
			params["mode"] = "pad"
		elif name == "pattern editor":
			self.zyngui.libseq.stop() #TODO This is a sledgehammer approach - stopping everything when editing pattern because otherwise we need to consider relative positions for everything
			#self.zyngui.libseq.selectSong(0)
			self.child = self.pattern_editor
			params["mode"] = "song"
			self.buttonbar_config[2] = (2, 'PLAY')
		elif name == "zynpad":
#			self.zyngui.libseq.selectSong(self.song)
			self.child = self.zynpad
		else:
			return
		self.child.show(params)
		self.init_buttonbar()
		self.status_menu_frame.tkraise()


	# Function to hide child GUI
	def hide_child(self):
		if self.child:
			self.last_child = self.child.get_name()
			self.child.hide()
		self.child = None
		self.hide_param_editor()
#		self.set_title("Step Sequencer")
		for switch in range(4):
			for type in ['S', 'B', 'L']:
				self.unregister_switch(switch, type)


	# Function to start transport
	def start(self):
		self.zyngui.libseq.transportStart(bytes("zynseq","utf-8"))


	# Function to pause transport
	def pause(self):
		self.zyngui.libseq.transportStop(bytes("zynseq","utf-8"))


	# Function to stop and recue transport
	def stop(self):
		if self.child == self.pattern_editor:
			self.zyngui.libseq.setPlayState(0, SEQ_STOPPED)
			self.zyngui.libseq.setTransportToStartOfBar()
		#TODO: Handle other views


	# Function to recue transport
	def recue(self):
		self.zyngui.libseq.locate(0)


	# Function to select song
	#	song: Index of song to select
	def select_song(self, song):
		if song > 0:
#			self.zyngui.libseq.transportStop() #TODO: Stopping transport due to jack_transport restarting if locate called
			self.zyngui.libseq.selectSong(song)
			self.song = song
			try:
				self.child.select_song()
			except:
				pass


	# Function to toggle transport
	def toggle_transport(self):
		if self.child == self.pattern_editor:
			self.zyngui.libseq.togglePlayState(self.pattern_editor.sequence)
		#TODO: Handle transport for other views


	# Function to name file before saving
	#	filename: Starting filename
	def	save_as(self, filename):
		rename_ui = zynthian_gui_rename(self, self.save, filename)
		if rename_ui.ok:
			self.filename = filename
		del rename_ui


	# Function to save to RIFF file
	#	filename: Filename without path or extension
	def save(self, filename = None):
		if not filename:
			filename = self.filename
		os.makedirs(USER_PATH, exist_ok=True)
		self.zyngui.libseq.save(bytes(USER_PATH + "/" + filename + ".zynseq", "utf-8"))


	# Function to show file dialog to select file to load
	def select_filename(self, filename):
		zynthian_gui_fileselector(self, self.load, USER_PATH, "zynseq", filename)


	# Function to load from RIFF file
	#	filename: Filename without path or extension
	def load(self, filename=None):
		if filename == None:
			filename = self.filename
		if self.zyngui.libseq.load(bytes(USER_PATH + "/" + filename + ".zynseq", "utf-8")):
			self.filename = filename
			self.zyngui.libseq.setTriggerChannel(zynthian_gui_config.master_midi_channel)
			if self.child:
				self.child.on_load()
				#TODO: This won't update hidden children


	# Function to refresh loading animation
	def refresh_loading(self):
		pass


	# Function to handle zyncoder value change
	#	encoder: Zyncoder index [0..4]
	#	value: Value of zyncoder change since last read
	def on_zyncoder(self, encoder, value):
		if self.lst_menu.winfo_viewable():
			# Menu showing
			if encoder == ENC_SELECT or encoder == ENC_LAYER:
				if self.lst_menu.size() < 1:
					return
				index = 0
				try:
					index = self.lst_menu.curselection()[0]
				except:
					logging.error("Problem detecting menu selection")
				index = index + value
				if index < 0:
					index = 0
				if index >= self.lst_menu.size():
					index = self.lst_menu.size() - 1
				self.lst_menu.selection_clear(0,tkinter.END)
				self.lst_menu.selection_set(index)
				self.lst_menu.activate(index)
				self.lst_menu.see(index)
		elif self.param_editor_item and not self.param_editor_timer:
			# Parameter editor showing
			if encoder == ENC_SELECT or encoder == ENC_LAYER:
				self.change_param(value)
		if encoder == ENC_SNAPSHOT:
			self.zyngui.libseq.setTempo(self.zyngui.libseq.getTempo() + value)
			self.show_param_editor("Tempo", 2)


	# Function to handle zyncoder polling
	#	Note: Zyncoder provides positive integers. We need +/- 1 so we keep zyncoder at +1 and calculate offset
	def zyncoder_read(self):
		if not self.shown:
			return
		if zyncoder.lib_zyncoder:
			for encoder in range(len(self.zyncoder_owner)):
				if self.zyncoder_owner[encoder]:
					# Found a registered zyncoder
					value = zyncoder.lib_zyncoder.get_value_zyncoder(encoder)
					if value != 64:
						zyncoder.lib_zyncoder.set_value_zyncoder(encoder, 64, 0)
						self.zyncoder_owner[encoder].on_zyncoder(encoder, value - 64)



	# Function to handle CUIA encoder changes
	def on_cuia_encoder(self, encoder, value):
		if self.zyncoder_owner[encoder]:
			self.zyncoder_owner[encoder].on_zyncoder(encoder, value)


	# Function to handle CUIA SELECT_UP command
	def select_up(self):
		self.on_cuia_encoder(ENC_SELECT, 1)


	# Function to handle CUIA SELECT_DOWN command
	def select_down(self):
		self.on_cuia_encoder(ENC_SELECT, -1)


	# Function to handle CUIA LAYER_UP command
	def layer_up(self):
		self.on_cuia_encoder(ENC_LAYER, 1)


	# Function to handle CUIA LAYER_DOWN command
	def layer_down(self):
		self.on_cuia_encoder(ENC_LAYER, -1)


	# Function to handle CUIA SNAPSHOT_UP command
	def snapshot_up(self):
		self.on_cuia_encoder(ENC_SNAPSHOT, 1)


	# Function to handle CUIA SNAPSHOT_DOWN command
	def snapshot_down(self):
		self.on_cuia_encoder(ENC_SNAPSHOT, -1)


	# Function to handle CUIA BACK_UP command
	def back_up(self):
		self.on_cuia_encoder(ENC_BACK, 1)


	# Function to handle CUIA BACK_UP command
	def back_down(self):
		self.on_cuia_encoder(ENC_BACK, -1)


	# Function to handle CUIA SELECT command
	def switch_select(self, t):
		self.switch(ENC_SELECT, t)


	# Function to handle switch presses
	#	switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def on_switch(self, switch, type):
		if switch == ENC_LAYER and not self.lst_menu.winfo_viewable():
			self.toggle_menu()
		elif switch == ENC_BACK and type == 'B':
			return False
		elif switch == ENC_BACK and type == 'S':
			if self.lst_menu.winfo_viewable():
				# Close menu
				self.hide_menu()
				return True
			if self.param_editor_item:
				# Close parameter editor
				self.hide_param_editor()
				return True
			if self.child == self.song_editor:
				self.show_child("zynpad")
				return True
			if self.child != self.zynpad:
				self.show_child(self.last_child)
				return True
			return False
		elif switch == ENC_SELECT or switch == ENC_LAYER:
			if self.lst_menu.winfo_viewable():
				self.on_menu_select()
				return True
			elif self.param_editor_item:
				self.menu_value_assert()
				return True
		return True # Tell parent that we handled all short and bold key presses


	# Function to manage switch press
	#	switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def switch(self, switch, type):
		if type == 'S':
			type_index = 0
		elif type == 'B':
			type_index = 1
		elif type == 'L':
			type_index = 2
		else:
			return
		index = switch * 3 + type_index
		if index >= len(self.switch_owner) or self.switch_owner[index] == None:
			return False # No one is handling this switch action so let parent manage it
		return self.switch_owner[index].on_switch(switch, type)


	# Function to register ownsership of switches
	#	switch: Index of switch [0..3]
	#	object: Object to register as owner
	#	type: Press type ['S'=Short, 'B'=Bold, 'L'=Long, Default:'S'] Can pass several, e.g. "SB" for both short and bold
	def register_switch(self, switch, object, type='S'):
		for t in type:
			if t == 'S':
				type_index = 0
			elif t == 'B':
				type_index = 1
			elif t == 'L':
				type_index = 2
			else:
				continue
			index = switch * 3 + type_index
			if index >= len(self.switch_owner):
				return
			self.switch_owner[index] = None
			if self.shown:
				self.switch_owner[index] = object


	# Function to unrestister ownership of a switch from an object (and handle in this class instead)
	#	switch: Index of switch [0..3]
	#	type: Press type ['S'=Short, 'B'=Bold, 'L'=Long, Default:'S'] Can pass several, e.g. "SB" for both short and bold
	def unregister_switch(self, switch, type='S'):
		for t in type:
			if t == 'S':
				type_index = 0
			elif t == 'B':
				type_index = 1
			elif t == 'L':
				type_index = 2
			else:
				continue
			index = switch * 3 + type_index
			if index >= len(self.switch_owner):
				continue
			self.register_switch(switch, self, t)


	# Function to register ownership of an encoder by an object
	#	encoder: Index of rotary encoder [0..3]
	#	object: Object to register as owner
	#	Note: Registers an object to own the encoder which will trigger that object's onZyncoder method when encoder rotated passing it +/- value since last read
	def register_zyncoder(self, encoder, object):
		if encoder >= len(self.zyncoder_owner):
			return
		self.zyncoder_owner[encoder] = None
		if self.shown and zyncoder.lib_zyncoder:
			pin_a=zynthian_gui_config.zyncoder_pin_a[encoder]
			pin_b=zynthian_gui_config.zyncoder_pin_b[encoder]
			zyncoder.lib_zyncoder.setup_zyncoder(encoder, pin_a, pin_b, 0, 0, None, 64, 128, 0)
			self.zyncoder_owner[encoder] = object


	# Function to unregister ownership of an encoder from an object
	#	encoder: Index of encoder to unregister
	def unregister_zyncoder(self, encoder):
		if encoder >= len(self.zyncoder_owner):
			return
		self.register_zyncoder(encoder, self)

#------------------------------------------------------------------------------

