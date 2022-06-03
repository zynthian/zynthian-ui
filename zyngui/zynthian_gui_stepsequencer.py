#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Step-Sequencer Class
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

import inspect
import sys
import os
import tkinter
import logging
import tkinter.font as tkFont
import time
import ctypes
from os.path import dirname, realpath
from PIL import Image, ImageTk

#Avoid unwanted debug messages from PIL module
pil_logger = logging.getLogger('PIL')
pil_logger.setLevel(logging.INFO)

# Zynthian specific modules
from zyngui import zynthian_gui_base
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_patterneditor import zynthian_gui_patterneditor
from zyngui.zynthian_gui_arranger import zynthian_gui_arranger
from zyngui.zynthian_gui_zynpad import zynthian_gui_zynpad
from zyngui.zynthian_gui_fileselector import zynthian_gui_fileselector
from zyngui.zynthian_gui_keyboard import zynthian_gui_keyboard

from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq
from zynlibs.zynseq.zynseq import libseq
libseq.init(bytes("zynthstep", "utf-8"))

#------------------------------------------------------------------------------
# Zynthian Step-Sequencer GUI Class
#------------------------------------------------------------------------------

# Local constants
CANVAS_BACKGROUND	= zynthian_gui_config.color_panel_bg
HEADER_BACKGROUND	= zynthian_gui_config.color_header_bg
# Define encoder use: 0=Layer, 1=Back, 2=Snapshot, 3=Select


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
SEQ_RESTARTING		= 4
SEQ_STOPPINGSYNC	= 5
SEQ_LASTPLAYSTATUS	= 5

USER_PATH			= "/zynthian/zynthian-my-data/zynseq"

PLAY_MODES = ['Disabled', 'Oneshot', 'Loop', 'Oneshot all', 'Loop all', 'Oneshot sync', 'Loop sync']
PAD_COLOUR_DISABLED = '#2a2a2a'
PAD_COLOUR_STARTING = '#ffbb00'
PAD_COLOUR_PLAYING = '#00d000'
PAD_COLOUR_STOPPING = 'red'
PAD_COLOUR_STOPPED = [
		'#000060',			#1 dark
		'#048C8C',			#2 dark
		'#996633',			#3 dark
		'#0010A0',			#4 medium too similar to 12
		'#BF9C7C',			#5 medium
		'#999966',			#6 medium
		'#FC6CB4',			#7 medium
		'#CC8464',			#8 medium
		'#4C94CC',			#9 medium
		'#B454CC',			#10 medium
		'#B08080',			#11 medium
		'#0404FC', 			#12 light
		'#9EBDAC',			#13 light
		'#FF13FC',			#14 light
		'#3080C0',			#15 light
		'#9C7CEC'			#16 light
		]

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
		self.zynpot_owner = [None, None, None, None] # Object that currently "owns" encoder, indexed by encoder
		self.zyncoder_step = [1, 1, 1, 1] # Zyncoder step. 0 for dynamic step (speed variable).
		self.switch_owner = [None] * 12 # Object that currently "owns" switch, indexed by (switch *3 + type)
		self.bank = 1 # Currently displayed bank of sequences
		self.layers = [None for i in range(16)] # Root layer indexed by MIDI channel

		#libseq.enableDebug(True)

		# Load default sequence file
		self.filename = "default"
		#self.load(self.filename)

		#TODO: Consolidate menu to base class
		self.status_menu_frame = tkinter.Frame(self.main_frame)

		#Menu parameters
		iconsize = (zynthian_gui_config.topbar_height - 4, zynthian_gui_config.topbar_height - 4)
		self.image_play = ImageTk.PhotoImage(Image.open("/zynthian/zynthian-ui/icons/playing.png").resize(iconsize))
		self.image_playing = ImageTk.PhotoImage(Image.open("/zynthian/zynthian-ui/icons/playing.png").resize(iconsize))
		self.image_back = ImageTk.PhotoImage(Image.open("/zynthian/zynthian-ui/icons/back.png").resize(iconsize))
		self.image_forward = ImageTk.PhotoImage(Image.open("/zynthian/zynthian-ui/icons/tick.png").resize(iconsize))
		img = (Image.open("/zynthian/zynthian-ui/icons/arrow.png").resize(iconsize))
		self.image_up = ImageTk.PhotoImage(img)
		self.image_down = ImageTk.PhotoImage(img.rotate(180))

		#TODO: Do we need status menu and if so, should be implemented in base class
		iconsize = (zynthian_gui_config.topbar_height - 4, zynthian_gui_config.topbar_height - 4)
		img = (Image.open("/zynthian/zynthian-ui/icons/recue.png").resize(iconsize))
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
		self.arranger = zynthian_gui_arranger(self)
		self.zynpad = zynthian_gui_zynpad(self)
		self.child = None # Pointer to instance of child panel
		self.last_child = self.zynpad # Pointer to instance of last child shown - used to return to same screen

				# Parameter value editor
		self.param_editor_item = None
		self.menu_items = {} # Dictionary of menu items
		self.param_editor_canvas = tkinter.Canvas(self.tb_frame,
			height=zynthian_gui_config.topbar_height,
			bd=0, highlightthickness=0)
		self.param_editor_canvas.grid_propagate(False)
		self.param_editor_canvas.bind('<Button-1>', self.hide_param_editor)

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
		self.lst_menu.bind('<ButtonRelease-1>', self.on_menu_select)
		self.scrollTime = 0.0
		if zynthian_gui_config.enable_touch_widgets:
			self.menu_button_canvas = tkinter.Canvas(self.tb_frame,
				height=zynthian_gui_config.topbar_height,
				bg=zynthian_gui_config.color_bg, bd=0, highlightthickness=0)
			self.menu_button_canvas.grid_propagate(False)
			self.menu_button_canvas.bind('<Button-1>', self.hide_menu)
			self.btn_menu_back = tkinter.Button(self.menu_button_canvas, command=self.back,
				image=self.image_back,
				bd=0, highlightthickness=0,
				relief=tkinter.FLAT, activebackground=zynthian_gui_config.color_header_bg, bg=zynthian_gui_config.color_header_bg)
			self.btn_menu_back.grid(column=0, row=0)
			self.menu_button_canvas.grid_columnconfigure(4, weight=1)

			# Parameter editor cancel button
			self.button_param_cancel = tkinter.Button(self.param_editor_canvas, command=self.hide_param_editor,
				image=self.image_back,
				bd=0, highlightthickness=0,
				relief=tkinter.FLAT, activebackground=zynthian_gui_config.color_header_bg, bg=zynthian_gui_config.color_header_bg)
			self.button_param_cancel.grid(column=0, row=0, padx=1)
			# Parameter editor decrement button
			self.button_param_down = tkinter.Button(self.param_editor_canvas, command=self.decrement_param,
				image=self.image_down,
				bd=0, highlightthickness=0, repeatdelay=500, repeatinterval=100,
				relief=tkinter.FLAT, activebackground=zynthian_gui_config.color_header_bg, bg=zynthian_gui_config.color_header_bg)
			self.button_param_down.grid(column=1, row=0, padx=1)
			# Parameter editor increment button
			self.button_param_up = tkinter.Button(self.param_editor_canvas, command=self.increment_param,
				image=self.image_up,
				bd=0, highlightthickness=0, repeatdelay=500, repeatinterval=100,
				relief=tkinter.FLAT, activebackground=zynthian_gui_config.color_header_bg, bg=zynthian_gui_config.color_header_bg)
			self.button_param_up.grid(column=2, row=0, padx=1)
			# Parameter editor assert button
			self.button_param_assert = tkinter.Button(self.param_editor_canvas, command=self.param_editor_assert,
				image=self.image_forward,
				bd=0, highlightthickness=0,
				relief=tkinter.FLAT, activebackground=zynthian_gui_config.color_header_bg, bg=zynthian_gui_config.color_header_bg)
			self.button_param_assert.grid(column=3, row=0, padx=1)
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


		# Init touchbar
		self.init_buttonbar()

		self.title="zynseq"
		self.select_bank(self.bank)
		self.populate_menu()


	# Function to print traceback - for debug only
	#	TODO: Remove debug function (or move to other zynthian class)
	def debug_traceback(self):
		for trace in inspect.stack():
			print(trace.function)

	# Function called when topbar clickde
	def cb_topbar(self, params=None):
		self.toggle_menu()


	# Function to trigger BACK
	def back(self, params=None):
		self.zyngui.zynswitch_defered('S',1)


	# Function to open menu or trigger BACK action if no menu configured
	def show_menu(self):
		self.populate_menu()
		try:
			if len(self.menu_items) == 1 and self.menu_items['BACK']['method'] == self.back:
				self.back()
				return
		except:
			pass

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
		if zynthian_gui_config.enable_touch_widgets:
			self.menu_button_canvas.grid()
			self.menu_button_canvas.grid_propagate(False)
			self.menu_button_canvas.grid(column=0, row=0, sticky='nsew')
		for encoder in range(4):
			self.unregister_zyncoder(encoder)
		self.register_switch(zynthian_gui_config.ENC_SELECT, self)
		self.register_switch(zynthian_gui_config.ENC_BACK, self)


	# Function to close menu
	#	event: Mouse event (not used)
	def hide_menu(self, event=None):
		self.hide_param_editor()
		self.unregister_zyncoder(zynthian_gui_config.ENC_SELECT)
		self.lst_menu.grid_forget()
		if zynthian_gui_config.enable_touch_widgets:
			self.menu_button_canvas.grid_forget()
		for encoder in range(4):
			self.unregister_zyncoder(encoder)
		if self.child:
			self.child.setup_encoders()


	# Function to know if menu is shown
	# 	returns: boolean
	def is_shown_menu(self):
		return self.lst_menu.winfo_viewable()


	# Function to handle title bar click
	#	event: Mouse event (not used)
	def toggle_menu(self, event=None):
		if self.is_shown_menu():
			self.hide_menu()
		else:
			self.show_menu()


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


	# Function to handle menu item selection (SELECT button or click on listbox entry)
	#	event: Mouse event not used
	def on_menu_select(self, event=None):
		if self.lst_menu.winfo_viewable():
			menu_item = None
			action = None
			params = None
			try:
				menu_item = self.lst_menu.get(self.lst_menu.curselection()[0])
				action = self.menu_items[menu_item]['method']
				params = self.menu_items[menu_item]['params']
			except:
				pass
			self.hide_menu()
			if not menu_item:
				return
			if action == self.show_param_editor:
				self.show_param_editor(menu_item)
			elif action:
				action(params) # Call menu handler defined during add_menu


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
	def show_param_editor(self, menu_item):
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
		if 'on_assert' in self.menu_items[menu_item]['params']:
			self.param_editor_canvas.itemconfig("btnparamEditorAssert", state='normal')
		else:
			self.param_editor_canvas.itemconfig("btnparamEditorAssert", state='hidden')
		for encoder in range(4):
			self.unregister_zyncoder(encoder)
		self.register_switch(zynthian_gui_config.ENC_SELECT, self, "SB")
		self.register_switch(zynthian_gui_config.ENC_BACK, self)


	# Function to hide menu editor
	#	event: Mouse event (not used)
	def hide_param_editor(self, event=None):
		self.param_editor_item = None
		self.param_editor_canvas.grid_forget()
		libseq.enableMidiLearn(0,0)
		for encoder in range(4):
			self.unregister_zyncoder(encoder)
		if self.child:
			self.child.setup_encoders()


	# Function to handle parameter editor value change and get display label text
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
			self.hide_param_editor()
		else:
			self.param_title_canvas.itemconfig("lbl_param_editor_value", text=result)


	# Function to decrement parameter value
	def decrement_param(self):
		self.change_param(-1)


	# Function to increment selected menu value
	def increment_param(self):
		self.change_param(1)


	# Function to assert selected menu value
	def param_editor_assert(self):
		if self.param_editor_item and 'on_assert' in self.menu_items[self.param_editor_item]['params'] and self.menu_items[self.param_editor_item]['params']['on_assert']:
			self.menu_items[self.param_editor_item]['params']['on_assert']()
		self.hide_param_editor()


	# Function callback when cancel selected in parameter editor
	def param_editor_cancel(self):
		if self.param_editor_item and 'on_cancel' in self.menu_items[self.param_editor_item]['params'] and self.menu_items[self.param_editor_item]['params']['on_cancel']:
			self.menu_items[self.param_editor_item]['params']['on_cancel']()
		self.hide_param_editor()


	# Function callback when reset selected in parameter editor
	def param_editor_reset(self):
		if self.param_editor_item and 'on_reset' in self.menu_items[self.param_editor_item]['params'] and self.menu_items[self.param_editor_item]['params']['on_reset']:
			self.menu_items[self.param_editor_item]['params']['on_reset']()


	# Highlight a menu entry
	def highlight_menu(self, index):
		if index < 0:
			index = 0
		if index >= self.lst_menu.size():
			index = self.lst_menu.size() - 1
		self.lst_menu.selection_clear(0,tkinter.END)
		self.lst_menu.selection_set(index)
		self.lst_menu.activate(index)
		self.lst_menu.see(index)


	# Function to close the panel manager
	def close_panel_manager(self):
		self.hide_menu()
		self.zyngui.zynswitch_defered('S', 1)


	# Function to populate menu with global entries
	def populate_menu(self):

		self.lst_menu.delete(0, tkinter.END)
		self.menu_items = {} # Dictionary of menu items
		self.add_menu({'BACK':{'method':self.back}})
		if self.child != self.zynpad:
			self.add_menu({'Pads':{'method':self.show_child, 'params':self.zynpad}})
		if self.child != self.arranger:
			self.add_menu({'Arranger':{'method':self.show_child, 'params':self.arranger}})
		if self.child != self.pattern_editor:
			self.add_menu({'Bank':{'method':self.show_param_editor, 'params':{'min':1, 'max':64, 'value':self.bank, 'on_change':self.on_menu_change}}})
		if zynthian_gui_config.enable_touch_widgets:
			self.add_menu({'Tempo':{'method':self.show_param_editor, 'params':{'min':1.0, 'max':500.0, 'get_value':libseq.getTempo, 'on_change':self.on_menu_change}}})
		self.add_menu({'Beats per bar':{'method':self.show_param_editor, 'params':{'min':1, 'max':64, 'get_value':libseq.getBeatsPerBar, 'on_change':self.on_menu_change}}})
		#self.add_menu({'Load':{'method':self.select_filename, 'params':self.filename}})
		self.add_menu({'-------------------':{}})
		if self.child:
			self.child.populate_menu()


	# Function to show GUI
	def show(self):
		if not self.shown:
			self.main_frame.grid_propagate(False)
			self.main_frame.grid(column=0, row=0)
			self.zyngui.screens["control"].unlock_controllers()
			self.shown=True
			self.show_child(self.child, {})
			# Update list of layers
			for chan in range(16):
				for layer in self.zyngui.screens['layer'].layers:
					if layer.midi_chan == chan:
						self.layers[chan] = layer
						break

		self.main_frame.focus()


	# Function to hide GUI
	def hide(self, args=None):
		if self.shown:
			self.shown=False
			self.main_frame.grid_forget()


	# Function to refresh the status widgets
	#	status: Dictionary containing update data
	def refresh_status(self, status={}):
		if self.shown:
			super().refresh_status(status)
			# Refresh child panel
			if self.child:
				self.child.refresh_status()



	# Function to open status menu
	def show_status_menu(self):
		if zynthian_gui_config.enable_touch_widgets:
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
	def show_param_editor(self, menu_item):
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
		if 'on_assert' in self.menu_items[menu_item]['params']:
			self.param_editor_canvas.itemconfig("btnparamEditorAssert", state='normal')
		else:
			self.param_editor_canvas.itemconfig("btnparamEditorAssert", state='hidden')
		for encoder in range(4):
			self.unregister_zyncoder(encoder)
		self.register_switch(zynthian_gui_config.ENC_SELECT, self, "SB")
		self.register_switch(zynthian_gui_config.ENC_BACK, self)


	# Function to hide menu editor
	#	event: Mouse event (not used)
	def hide_param_editor(self, event=None):
		self.param_editor_item = None
		self.param_editor_canvas.grid_forget()
		libseq.enableMidiLearn(0,0)
		for encoder in range(4):
			self.unregister_zyncoder(encoder)
		if self.child:
			self.child.setup_encoders()


	# Function to handle parameter editor value change and get display label text
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
		if self.param_editor_item == 'Bank':
			self.select_bank(value)
		elif self.param_editor_item == 'Tempo':
			libseq.setTempo(ctypes.c_double(value))
			return "Tempo: %0.1f BPM" % (value)
		elif self.param_editor_item == "Beats per bar":
			libseq.setBeatsPerBar(value)
		self.set_param(self.param_editor_item, 'value', value)
		return "%s: %d" % (self.param_editor_item, value)


	# Function to show child GUI
	#	name: Name of child to show
	#	params: Dictionary of parameters to pass to child class show() method
	def show_child(self, child, params=None):
		if not self.shown:
			return
		#logging.warning("name: %s params: %s", name, params)
		if not child:
			child = self.zynpad
		if not params:
			params = {}
		if self.child == self.zynpad:
			params["sequence"] = self.zynpad.selected_pad
		if self.child == self.arranger:
			params["sequence"] = self.arranger.sequence
		if self.child != self.pattern_editor:
			self.last_child = self.child
		self.hide_child()
		self.buttonbar_config[2] = (2, '')
		self.child = child
		if child == self.pattern_editor:
			self.buttonbar_config[2] = (2, 'PLAY')
		elif child == None:
			return
		self.child.show(params)
		self.init_buttonbar()
		self.status_menu_frame.tkraise()


	# Function to hide child GUI
	def hide_child(self):
		if self.child:
			self.child.hide()
		self.child = None
		self.hide_param_editor()
		for switch in range(4):
			for type in ['S', 'B', 'L']:
				self.unregister_switch(switch, type)


	# Function to start transport
	def start(self):
		zynseq.transport_start("zynseq")


	# Function to pause transport
	def pause(self):
		zynseq.transport_stop("zynseq")


	# Function to stop and recue transport
	def stop(self):
		if self.child == self.pattern_editor:
			libseq.setPlayState(0, 0, SEQ_STOPPED)
			libseq.setTransportToStartOfBar()
		#TODO: Handle other views


	# Function to recue transport
	def recue(self):
		libseq.locate(0)


	# Function to get current bank
	def get_bank(self):
		return self.bank


	# Function to select bank
	#	bank: Index of bank to select
	def select_bank(self, bank):
		if bank > 0:
			if libseq.getSequencesInBank(bank) == 0:
				libseq.setSequencesInBank(bank, 16)
				for column in range(4):
					if column == 3:
						channel = 9
					else:
						channel = column
					for row in range(4):
						pad = row + 4 * column
						zynseq.set_sequence_name(bank, pad, "%d" % (libseq.getPatternAt(bank, pad, 0, 0)))
						libseq.setGroup(bank, pad, channel)
						libseq.setChannel(bank, pad, 0, channel)
			self.bank = bank
			self.set_title("Bank %d" % bank)
			try:
				self.child.select_bank(bank)
			except:
				pass


	# Function to toggle transport
	def toggle_transport(self):
		if self.child == self.pattern_editor:
			libseq.togglePlayState(0, 0)
		#TODO: Handle transport for other banks


	# ---------------------------------------------------------------------------
	# ZynSeq File Management
	# ---------------------------------------------------------------------------

	# Function to save to RIFF file
	#	filename: Filename without path or extension
	def save(self, filename = None):
		libseq.cleanPatterns()
		if not filename:
			filename = self.filename
		os.makedirs(USER_PATH, exist_ok=True)
		return self.save_fpath(USER_PATH + "/" + filename + ".zynseq")


	def save_fpath(self, fpath):
		return zynseq.save(fpath)


	# Function to show file dialog to select file to load
	def select_filename(self, filename):
		zynthian_gui_fileselector(self, self.load, USER_PATH, "zynseq", filename)


	# Function to load from RIFF file
	#	filename: Filename without path or extension
	def load(self, filename=None):
		if filename == None:
			filename = self.filename
		if self.load_fpath(USER_PATH + "/" + filename + ".zynseq"):
			self.filename = filename


	def load_fpath(self, fpath):
		return zynseq.load(fpath)


	def get_riff_data(self):
		fpath = "/tmp/snapshot.zynseq"
		try:
			# Save to tmp
			self.save_fpath(fpath)
			# Load binary data
			with open(fpath,"rb") as fh:
				riff_data=fh.read()
				logging.info("Loading RIFF data...\n")
			return riff_data

		except Exception as e:
			logging.error("Can't get RIFF data! => {}".format(e))
			return None


	def restore_riff_data(self, riff_data):
		fpath = "/tmp/snapshot.zynseq"
		try:
			# Save RIFF data to tmp file
			with open(fpath,"wb") as fh:
				fh.write(riff_data)
				logging.info("Restoring RIFF data...\n")
			# Load from tmp file
			if self.load_fpath(fpath):
				self.filename = "snapshot"
				self.arranger.on_load()
				return True

		except Exception as e:
			logging.error("Can't restore RIFF data! => {}".format(e))
			return False


	# ---------------------------------------------------------------------------
	# Encoder & Switch management
	# ---------------------------------------------------------------------------

	# Function to handle zyncoder value change
	#	i: Zynpot index [0..n]
	#	dval: Value change since last event
	def _zynpot_cb(self, i, dval):
		if not self.shown:
			return

		if self.lst_menu.winfo_viewable():
			# Menu browsing
			if i == zynthian_gui_config.ENC_SELECT or i == zynthian_gui_config.ENC_LAYER:
				if self.lst_menu.size() < 1:
					return
				index = 0
				try:
					index = self.lst_menu.curselection()[0]
				except:
					logging.error("Problem detecting menu selection")
				self.highlight_menu(index + dval)
				return
		elif self.param_editor_item:
			# Parameter change
			if i == zynthian_gui_config.ENC_SELECT or i == zynthian_gui_config.ENC_LAYER:
				self.change_param(dval)
			elif i == zynthian_gui_config.ENC_SNAPSHOT:
				self.change_param(dval / 10)
		elif i == zynthian_gui_config.ENC_SNAPSHOT:
			libseq.setTempo(ctypes.c_double(libseq.getTempo() + 0.1*dval))
			self.set_title("Tempo: %0.1f BPM" % (libseq.getTempo()), None, None, 2)
		elif i == zynthian_gui_config.ENC_LAYER:
			self.select_bank(self.bank + dval)


	# Function to dispatch zynpots events to children (owners) or handle by default
	def zynpot_cb(self, i, dval):
		if self.zynpot_owner[i]==self:
			self._zynpot_cb(i, dval)
			return True
		elif self.zynpot_owner[i]:
			#logging.debug("STEPSEQ ZYNCODER {} VALUE => {}".format(encoder,step))
			self.zynpot_owner[i].zynpot_cb(i, dval)
			return True


	# Function to handle CUIA ARROW_UP
	def arrow_up(self):
		if self.lst_menu.winfo_viewable():
			self.zynpot_cb(zynthian_gui_config.ENC_SELECT, -1)
		elif self.child in (self.zynpad, self.pattern_editor):
			self.zynpot_cb(zynthian_gui_config.ENC_BACK, -1)
		else:
			self.zynpot_cb(zynthian_gui_config.ENC_SELECT, -1)


	# Function to handle CUIA ARROW_DOWN
	def arrow_down(self):
		if self.lst_menu.winfo_viewable():
			self.zynpot_cb(zynthian_gui_config.ENC_SELECT, 1)
		elif self.child in (self.zynpad, self.pattern_editor):
			self.zynpot_cb(zynthian_gui_config.ENC_BACK, 1)
		else:
			self.zynpot_cb(zynthian_gui_config.ENC_SELECT, 1)


	# Function to handle CUIA ARROW_RIGHT
	def arrow_right(self):
		self.zynpot_cb(zynthian_gui_config.ENC_SELECT, 1)


	# Function to handle CUIA ARROW_LEFT
	def arrow_left(self):
		self.zynpot_cb(zynthian_gui_config.ENC_SELECT, -1)


	# Function to handle CUIA SELECT command
	def switch_select(self, t):
		self.switch(zynthian_gui_config.ENC_SELECT, t)


	def back_action(self):
		if self.is_shown_menu():
			# Close menu
			self.hide_menu()
			return True
		if self.param_editor_item:
			# Close parameter editor
			self.param_editor_cancel()
			return True
		if self.child == self.arranger:
			self.show_child(self.zynpad)
			return True
		if self.child != self.zynpad:
			self.show_child(self.last_child, {})
			return True
		return False


	# Function to handle switch presses
	#	switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def on_switch(self, switch, type):
		if type == 'S':
			if switch == zynthian_gui_config.ENC_BACK:
				return self.back_action()
			elif switch == zynthian_gui_config.ENC_SELECT:
				if self.is_shown_menu():
					self.on_menu_select()
					return True
				elif self.param_editor_item:
					self.param_editor_assert()
					return True
			elif switch == zynthian_gui_config.ENC_LAYER:
				if self.is_shown_menu():
					self.on_menu_select()
				else:
					self.show_menu()
				return True
		if type == 'B':
			if switch == zynthian_gui_config.ENC_SELECT:
				if self.param_editor_item:
					# Close parameter editor
					self.param_editor_reset()
					return True

		return False # Tell parent to handle the rest of short and bold key presses


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
	def register_zyncoder(self, encoder, object, step=1):
		if encoder >= len(self.zynpot_owner):
			return
		self.zynpot_owner[encoder] = None
		if self.shown and lib_zyncore:
			lib_zyncore.setup_behaviour_zynpot(encoder, step)
			self.zynpot_owner[encoder] = object
			self.zyncoder_step[encoder] = step


	# Function to unregister ownership of an encoder from an object
	#	encoder: Index of encoder to unregister
	def unregister_zyncoder(self, encoder):
		if encoder >= len(self.zynpot_owner):
			return
		if encoder==zynthian_gui_config.ENC_SNAPSHOT:
			step = 0
		else:
			step = 1
		self.register_zyncoder(encoder, self, step)

#------------------------------------------------------------------------------

