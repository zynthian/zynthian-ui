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

# Class implements zynthian step sequencer parent, hosting child screens:editors, players, etc.
class zynthian_gui_stepsequencer(zynthian_gui_base.zynthian_gui_base):

	buttonbar_config = [
		(1, 'BACK'),
		(0, 'MENU'),
		(2, 'TRANSPORT'),
		(3, 'TOGGLE')
	]

	# Function to initialise class
	def __init__(self):
		super().__init__()
		self.shown = False # True when GUI in view
		self.zyncoderOwner = [None, None, None, None] # Object that currently "owns" encoder, indexed by encoder
		self.switchOwner = [None] * 12 # Object that currently "owns" switch, indexed by (switch *3 + type)
		self.zyngui = zynthian_gui_config.zyngui # Zynthian GUI configuration
		self.child = None # Pointer to instance of child panel
		self.lastchild = 2 # Index of last child shown - used to return to same screen
		self.song = 1 # The song that will play / edit (may be different to libseq.getSong, e.g. when editing patter)
		self.song_editor_mode = 1 # 1 for song editor, 3 for pad editor

		# Initalise libseq and load pattern from file
		# TODO: Should this be done at higher level rather than within a screen?
		self.libseq = ctypes.CDLL(dirname(realpath(__file__))+"/../zynlibs/zynseq/build/libzynseq.so")
		self.libseq.init()
		self.libseq.enableDebug(True)
		self.filename = "default"
		time.sleep(2)
		self.load(self.filename)
		print("Loaded file")
		time.sleep(2)
		print("Continuing")

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
			bg = zynthian_gui_config.color_bg)
		self.title_canvas.grid_propagate(False)
		self.title_canvas.create_text(0, zynthian_gui_config.topbar_height / 2,
			font=font,
			anchor="w",
			fill=zynthian_gui_config.color_panel_tx,
			tags="lblTitle",
			text="Step Sequencer")
		self.title_canvas.grid(row=0, column=0, sticky='ew')
		self.title_canvas.bind('<Button-1>', self.toggleMenu)

		iconsize = (zynthian_gui_config.topbar_height - 2, zynthian_gui_config.topbar_height - 2)
		img = (Image.open("/zynthian/zynthian-ui/icons/play.png").resize(iconsize))
		self.imgPlay = ImageTk.PhotoImage(img)
		pixdata = img.load()
		for y in range(img.size[1]):
			for x in range(img.size[0]):
				if pixdata[x, y][0] == (255):
					pixdata[x, y] = (0, 255, 0, pixdata[x, y][3])
		self.imgPlaying = ImageTk.PhotoImage(img)
		self.imgBack = ImageTk.PhotoImage(Image.open("/zynthian/zynthian-ui/icons/back.png").resize(iconsize))
		self.imgForward = ImageTk.PhotoImage(Image.open("/zynthian/zynthian-ui/icons/tick.png").resize(iconsize))
		img = (Image.open("/zynthian/zynthian-ui/icons/arrow.png").resize(iconsize))
		self.imgUp = ImageTk.PhotoImage(img)
		self.imgDown = ImageTk.PhotoImage(img.rotate(180))

		# Parameter value editor
		self.paramEditorItem = None
		self.MENU_ITEMS = {} # Dictionary of menu items
		self.param_editor_canvas = tkinter.Canvas(self.tb_frame,
			height=zynthian_gui_config.topbar_height,
			bd=0, highlightthickness=0)
		self.param_editor_canvas.grid_propagate(False)

		if zynthian_gui_config.enable_touch_widgets:
			# Parameter editor cancel button
			self.btnParamCancel = tkinter.Button(self.param_editor_canvas, command=self.hideParamEditor,
				image=self.imgBack,
				bd=0, highlightthickness=0,
				relief=tkinter.FLAT, activebackground=zynthian_gui_config.color_bg, bg=zynthian_gui_config.color_bg)
			self.btnParamCancel.grid(column=0, row=0)
			# Parameter editor decrement button
			self.btnParamDown = tkinter.Button(self.param_editor_canvas, command=self.decrementParam,
				image=self.imgDown,
				bd=0, highlightthickness=0, repeatdelay=500, repeatinterval=100,
				relief=tkinter.FLAT, activebackground=zynthian_gui_config.color_bg, bg=zynthian_gui_config.color_bg)
			self.btnParamDown.grid(column=1, row=0)
			# Parameter editor increment button
			self.btnParamUp = tkinter.Button(self.param_editor_canvas, command=self.incrementParam,
				image=self.imgUp,
				bd=0, highlightthickness=0, repeatdelay=500, repeatinterval=100,
				relief=tkinter.FLAT, activebackground=zynthian_gui_config.color_bg, bg=zynthian_gui_config.color_bg)
			self.btnParamUp.grid(column=2, row=0)
			# Parameter editor assert button
			self.btnParamAssert = tkinter.Button(self.param_editor_canvas, command=self.menuValueAssert,
				image=self.imgForward,
				bd=0, highlightthickness=0,
				relief=tkinter.FLAT, activebackground=zynthian_gui_config.color_bg, bg=zynthian_gui_config.color_bg)
			self.btnParamAssert.grid(column=3, row=0)
		# Parameter editor value text
		self.param_title_canvas = tkinter.Canvas(self.param_editor_canvas, height=zynthian_gui_config.topbar_height, bd=0, highlightthickness=0, bg=zynthian_gui_config.color_bg)
		self.param_title_canvas.create_text(3, zynthian_gui_config.topbar_height / 2,
			anchor='w',
			font=zynthian_gui_config.font_topbar,
#			font=tkFont.Font(family=zynthian_gui_config.font_topbar[0],
#				size=int(self.height * 0.05)),
			fill=zynthian_gui_config.color_panel_tx,
			tags="lblparamEditorValue",
			text="VALUE...")
		self.param_title_canvas.grid(column=4, row=0, sticky='ew')
		self.param_editor_canvas.grid_columnconfigure(4, weight=1)

		#TODO: Consolidate menu to base class
		self.status_canvas.bind('<Button-1>', self.toggleStatusMenu)

		# Menu #TODO: Replace listbox with painted canvas providing swipe gestures
		self.listboxTextHeight = tkFont.Font(font=zynthian_gui_config.font_listbox).metrics('linespace')
		self.lstMenu = tkinter.Listbox(self.main_frame,
			font=zynthian_gui_config.font_listbox,
			bd=7,
			highlightthickness=0,
			relief='flat',
			bg=zynthian_gui_config.color_panel_bg,
			fg=zynthian_gui_config.color_panel_tx,
			selectbackground=zynthian_gui_config.color_ctrl_bg_on,
			selectforeground=zynthian_gui_config.color_ctrl_tx,
			selectmode=tkinter.BROWSE)
		self.lstMenu.bind('<Button-1>', self.onMenuPress)
		self.lstMenu.bind('<B1-Motion>', self.onMenuDrag)
		self.lstMenu.bind('<ButtonRelease-1>', self.onMenuRelease)
		self.scrollTime = 0.0
		if zynthian_gui_config.enable_touch_widgets:
			self.menu_button_canvas = tkinter.Canvas(self.tb_frame,
				height=zynthian_gui_config.topbar_height,
				bg=zynthian_gui_config.color_bg, bd=0, highlightthickness=0)
			self.menu_button_canvas.grid_propagate(False)
			self.menu_button_canvas.bind('<Button-1>', self.hideMenu)
			self.btnMenuBack = tkinter.Button(self.menu_button_canvas, command=self.closePanelManager,
				image=self.imgBack,
				bd=0, highlightthickness=0,
				relief=tkinter.FLAT, activebackground=zynthian_gui_config.color_bg, bg=zynthian_gui_config.color_bg)
			self.btnMenuBack.grid(column=0, row=0)
			self.menu_button_canvas.grid_columnconfigure(4, weight=1)

		self.status_menu_frame = tkinter.Frame(self.main_frame)

		img = (Image.open("/zynthian/zynthian-ui/icons/stop.png").resize(iconsize))
		self.imgStop = ImageTk.PhotoImage(img)
		self.btnStop = tkinter.Button(self.status_menu_frame, command=self.stop,
			image=self.imgStop,
			bd=0, highlightthickness=0,
			relief=tkinter.FLAT, activebackground=zynthian_gui_config.color_bg, bg=zynthian_gui_config.color_bg)
		self.btnStop.grid()

		self.btnTransport = tkinter.Button(self.status_menu_frame, command=self.toggleTransport,
			image=self.imgPlay,
			bd=0, highlightthickness=0,
			relief=tkinter.FLAT, activebackground=zynthian_gui_config.color_bg, bg=zynthian_gui_config.color_bg)
		self.btnTransport.grid()

		self.patternEditor = zynthian_gui_patterneditor(self)
		self.songEditor = zynthian_gui_songeditor(self)
		self.zynpad = zynthian_gui_zynpad(self)

		# Init touchbar
		self.init_buttonbar()

		self.selectSong(self.song)

	# Function to print traceback - for debug only
	#	TODO: Remove debug function (or move to other zynthian class)
	def debugTraceback(self):
		for trace in inspect.stack():
			print(trace.function)

	# Function to close the panel manager
	def closePanelManager(self):
		self.hideMenu()
		self.zyngui.zynswitch_defered('S', 1)

	# Function to populate menu with global entries
	def populateMenu(self):
		self.lstMenu.delete(0, tkinter.END)
		self.MENU_ITEMS = {} # Dictionary of menu items
		self.addMenu({'ZynPad':{'method':self.showChild, 'params':2}})
		self.addMenu({'Pad Editor':{'method':self.showChild, 'params':3}})
#		self.addMenu({'Song Editor':{'method':self.showChild, 'params':1}})
		self.addMenu({'Song':{'method':self.showParamEditor, 'params':{'min':1, 'max':999, 'getValue':self.libseq.getSong, 'onChange':self.onMenuChange}}})
		self.addMenu({'Load':{'method':self.select_filename, 'params':self.filename}})
		self.addMenu({'Save':{'method':self.save_as, 'params':self.filename}})
		self.addMenu({'---':{}})

	# Function to update title
	#	title: Title to display in topbar
	def setTitle(self, title):
		self.title_canvas.itemconfig("lblTitle", text=title)

	# Function to show GUI
	def show(self):
		if not self.shown:
			self.shown=True
			self.main_frame.grid_propagate(False)
			self.main_frame.grid(column=0, row=0)
			self.showChild()
		self.main_frame.focus()

	# Function to hide GUI
	def hide(self):
		if self.shown:
			self.shown=False
			self.main_frame.grid_forget()
			if self.child:
				self.child.hide()

	# Function to refresh the status widgets
	#	status: Dictionary containing update data
	def refresh_status(self, status={}):
		if self.shown:
			super().refresh_status(status)
			# Refresh child panel
			if self.child:
				self.child.refresh_status()

	# Function to open menu
	def showMenu(self):
		self.populateMenu()
		if self.child:
			self.child.populateMenu()
		button_height = 0
		if zynthian_gui_config.enable_touch_widgets:
			button_height = zynthian_gui_config.buttonbar_height
		rows = min((self.height - zynthian_gui_config.topbar_height - button_height) / self.listboxTextHeight - 1, self.lstMenu.size())
		self.lstMenu.configure(height = int(rows))
		self.lstMenu.grid(column=0, row=1, sticky="nw")
		self.lstMenu.tkraise()
		self.lstMenu.selection_clear(0,tkinter.END)
		self.lstMenu.activate(0)
		self.lstMenu.selection_set(0)
		self.lstMenu.see(0)
		for encoder in range(4):
			self.unregisterZyncoder(encoder)
		self.registerSwitch(ENC_SELECT, self)
		self.registerSwitch(ENC_BACK, self)
		if zynthian_gui_config.enable_touch_widgets:
			self.menu_button_canvas.grid()
			self.menu_button_canvas.grid_propagate(False)
			self.menu_button_canvas.grid(column=0, row=0, sticky='nsew')

	# Function to close menu
	#	event: Mouse event (not used)
	def hideMenu(self, event=None):
		self.hideParamEditor()
		self.unregisterZyncoder(ENC_SELECT)
		self.lstMenu.grid_forget()
		if zynthian_gui_config.enable_touch_widgets:
			self.menu_button_canvas.grid_forget()
		for encoder in range(4):
			self.unregisterZyncoder(encoder)
		if self.child:
			self.child.setupEncoders()

	# Function to handle title bar click
	#	event: Mouse event (not used)
	def toggleMenu(self, event=None):
		if self.lstMenu.winfo_viewable():
			self.hideMenu()
		else:
			self.showMenu()

	# Function to open status menu
	def showStatusMenu(self):
		self.status_menu_frame.grid(column=0, row=1, sticky="ne")
		self.status_menu_frame.tkraise()

	# Function to close status menu
	def hideStatusMenu(self):
		self.status_menu_frame.grid_forget()

	# Function to handle status bar click
	#	event: Mouse event (not used)
	def toggleStatusMenu(self, event=None):
		if self.status_menu_frame.winfo_viewable():
			self.hideStatusMenu()
		else:
			self.showStatusMenu()

	# Function to handle press menu
	def onMenuPress(self, event):
		pass

	# Function to handle motion menu
	def onMenuDrag(self, event):
		now = time.monotonic()
		if self.scrollTime < now:
			self.scrollTime = now + 0.1
			try:
				item = self.lstMenu.curselection()[0]
				self.lstMenu.see(item + 1)
				self.lstMenu.see(item - 1)
			except:
				pass
		#self.lstMenu.winfo(height)
		pass

	# Function to handle release menu
	def onMenuRelease(self, event):
		self.onMenuSelect()

	# Function to handle menu item selection (SELECT button or click on listbox entry)
	def onMenuSelect(self):
		if self.lstMenu.winfo_viewable():
			menuItem = None
			action = None
			params = {}
			try:
				menuItem = self.lstMenu.get(self.lstMenu.curselection()[0])
				action = self.MENU_ITEMS[menuItem]['method']
				params = self.MENU_ITEMS[menuItem]['params']
			except:
				logging.error("**Error selecting menu**")
			self.hideMenu()
			if not menuItem:
				return
			if action == self.showParamEditor:
				self.showParamEditor(menuItem)
			elif action:
				action(params) # Call menu handler defined during addMenu

	# Function to add items to menu
	#	item: Dictionary containing menu item data, indexed by menu item title
	#		Dictionary should contain {'method':<function to call when menu selected>} and {'params':<parameters to pass to method>}
	def addMenu(self, item):
		self.MENU_ITEMS.update(item)
		self.lstMenu.insert(tkinter.END, list(item)[0])

	# Function to set menu data parameters
	#	item: Menu item name
	#	param: Parameter name
	#	value: Parameter value
	def setParam(self, item, param, value):
		if item in self.MENU_ITEMS:
			self.MENU_ITEMS[item]['params'].update({param: value})

	# Function to refresh parameter editor display
	def refreshParamEditor(self):
		self.param_title_canvas.itemconfig("lblparamEditorValue", 
			text=self.MENU_ITEMS[self.paramEditorItem]['params']['onChange'](self.MENU_ITEMS[self.paramEditorItem]['params']))

	# Function to get menu data parameters
	#	item: Menu item name
	#	param: Parameter name
	#	returns: Parameter value
	def getParam(self, item, param):
		if item in self.MENU_ITEMS and param in self.MENU_ITEMS[item]['params']:
			return self.MENU_ITEMS[item]['params'][param]
		return None

	# Function to show menu editor
	#	menuitem: Name of the menu item who's parameters to edit
	def showParamEditor(self, menuItem):
		if not menuItem in self.MENU_ITEMS:
			return
		self.paramEditorItem = menuItem
		if self.getParam(menuItem, 'getValue'):
			self.setParam(menuItem, 'value', self.getParam(menuItem, 'getValue')())
		self.param_editor_canvas.grid_propagate(False)
		self.param_editor_canvas.grid(column=0, row=0, sticky='nsew')
		# Get the value to display in the param editor
		self.param_title_canvas.itemconfig("lblparamEditorValue", 
			text=self.MENU_ITEMS[menuItem]['params']['onChange'](self.MENU_ITEMS[menuItem]['params'])
			)
		if 'onAssert' in self.MENU_ITEMS[menuItem]['params']:
			self.param_editor_canvas.itemconfig("btnparamEditorAssert", state='normal')
		else:
			self.param_editor_canvas.itemconfig("btnparamEditorAssert", state='hidden')
		for encoder in range(4):
			self.unregisterZyncoder(encoder)
		self.registerSwitch(ENC_SELECT, self)
		self.registerSwitch(ENC_BACK, self)

	# Function to hide menu editor
	def hideParamEditor(self):
		self.paramEditorItem = None
		self.param_editor_canvas.grid_forget()
		for encoder in range(4):
			self.unregisterZyncoder(encoder)
		if self.child:
			self.child.setupEncoders()

	# Function to handle menu editor value change and get display label text
	#	params: Menu item's parameters
	#	returns: String to populate menu editor label
	#	note: This is default but other method may be used for each menu item
	#	note: params is a dictionary with required fields: min, max, value
	def onMenuChange(self, params):
		value = params['value']
		if value < params['min']:
			value = params['min']
		if value > params['max']:
			value = params['max']
		if self.paramEditorItem == 'Song':
			self.selectSong(value)
		self.setParam(self.paramEditorItem, 'value', value)
		return "%s: %d" % (self.paramEditorItem, value)

	# Function to change parameter value
	#	value: Offset by which to change parameter value
	def changeParam(self, value):
		value = self.getParam(self.paramEditorItem, 'value') + value
		if value < self.getParam(self.paramEditorItem, 'min'):
			if self.getParam(self.paramEditorItem, 'value' == value):
				return
			value = self.getParam(self.paramEditorItem, 'min')
		if value > self.getParam(self.paramEditorItem, 'max'):
			if self.getParam(self.paramEditorItem, 'value' == value):
				return
			value = self.getParam(self.paramEditorItem, 'max')
		self.setParam(self.paramEditorItem, 'value', value)
		result = self.getParam(self.paramEditorItem, 'onChange')(self.MENU_ITEMS[self.paramEditorItem]['params'])
		if result == -1:
			hideParamEditor()
		else:
			self.param_title_canvas.itemconfig("lblparamEditorValue", text=result)

	# Function to decrement parameter value
	def decrementParam(self):
		self.changeParam(-1)

	# Function to increment selected menu value
	def incrementParam(self):
		self.changeParam(1)

	# Function to assert selected menu value
	def menuValueAssert(self):
		if self.paramEditorItem and 'onAssert' in self.MENU_ITEMS[self.paramEditorItem]['params'] and self.MENU_ITEMS[self.paramEditorItem]['params']['onAssert']:
			self.MENU_ITEMS[self.paramEditorItem]['params']['onAssert']()
		self.hideParamEditor()

	# Function to show child GUI
	#	childIndex: Index of child to show [0:PatternEditor 1:SongEditor 2:ZynPad 3:PadEditor]
	#	params: Parameters to pass to child class show() method
	def showChild(self, childIndex=None, params=None):
		if not self.shown:
			return
		self.hideChild()
		if childIndex == None:
			childIndex = self.lastchild
		self.lastchild = childIndex # A bit contrived but it allows us to return to same panel
		if childIndex == 1:
			self.libseq.selectSong(self.song)
			self.child = self.songEditor
			params = 0
			self.song_editor_mode = 1
		elif childIndex == 3:
			self.libseq.selectSong(self.song)
			self.child = self.songEditor
			params = 1
			self.song_editor_mode = 3
		elif childIndex == 0:
			self.libseq.stop() #TODO This is a sledgehammer approach - stopping everything when editing pattern because otherwise we need to consider relative positions for everything
			#self.libseq.selectSong(0)
			self.child = self.patternEditor
		elif childIndex == 2:
#			self.libseq.selectSong(self.song)
			self.child = self.zynpad
		else:
			return
		self.child.show(params)
		self.status_menu_frame.tkraise()

	# Function to hide child GUI
	def hideChild(self):
		if self.child:
			self.child.hide()
		self.child = None
		self.hideParamEditor()
#		self.setTitle("Step Sequencer")
		for switch in range(4):
			for type in ['S', 'B', 'L']:
				self.unregisterSwitch(switch, type)

	# Function to start transport
	def start(self):
		self.libseq.transportStart();

	# Function to pause transport
	def pause(self):
		self.libseq.transportStop();

	# Function to stop and recue transport
	def stop(self):
		if self.child == self.patternEditor:
			self.libseq.setPlayState(0, SEQ_STOPPED)
			self.libseq.setTransportToStartOfBar()
		#TODO: Handle other views

	# Function to recue transport
	def recue(self):
		playState = self.libseq.getPlayState()
		# Workaround issue with jack_transport needing to stop and pause before locate
		self.libseq.transportStop();
		time.sleep(0.1)
		self.libseq.locate(0);
		if playState:
			self.libseq.transportStart();

	# Function to select song
	#	song: Index of song to select
	def selectSong(self, song):
		if song > 0:
#			self.libseq.transportStop() #TODO: Stopping transport due to jack_transport restarting if locate called
			self.libseq.selectSong(song)
			self.song = song
#			self.libseq.setTempo(self.libseq.getTempo(song, 0))
			try:
				self.child.selectSong()
			except:
				pass

	# Function to toggle transport
	def toggleTransport(self):
		if self.child == self.patternEditor:
			self.libseq.togglePlayState(0)
		#TODO: Handle transport for other views

	# Function to name file before saving
	#	filename: Starting filename
	def	save_as(self, filename):
		zynthian_gui_rename(self, self.save, filename)

	# Function to save to RIFF file
	#	filename: Filename without path or extension
	def save(self, filename = None):
		if not filename:
			filename = self.filename
		os.makedirs(USER_PATH, exist_ok=True)
		self.libseq.save(bytes(USER_PATH + "/" + filename + ".zynseq", "utf-8"))
		self.filename = filename

	# Function to show file dialog to select file to load
	def select_filename(self, filename):
		zynthian_gui_fileselector(self, self.load, USER_PATH, "zynseq", filename)

	# Function to load from RIFF file
	#	filename: Filename without path or extension
	def load(self, filename=None):
		if filename == None:
			filename = self.filename
		if self.libseq.load(bytes(USER_PATH + "/" + filename + ".zynseq", "utf-8")):
			self.filename = filename
			if self.child:
				self.child.onLoad()
				#TODO: This won't update hidden children

	# Function to refresh loading animation
	def refresh_loading(self):
		pass

	# Function to handle zyncoder value change
	#	encoder: Zyncoder index [0..4]
	#	value: Value of zyncoder change since last read
	def onZyncoder(self, encoder, value):
		if encoder == ENC_SELECT or encoder == ENC_LAYER:
			if self.lstMenu.winfo_viewable():
				# Menu showing
				if self.lstMenu.size() < 1:
					return
				index = 0
				try:
					index = self.lstMenu.curselection()[0]
				except:
					logging.error("Problem detecting menu selection")
				index = index + value
				if index < 0:
					index = 0
				if index >= self.lstMenu.size():
					index = self.lstMenu.size() - 1
				self.lstMenu.selection_clear(0,tkinter.END)
				self.lstMenu.selection_set(index)
				self.lstMenu.activate(index)
				self.lstMenu.see(index)
			elif self.paramEditorItem:
				# Parameter editor showing
				self.changeParam(value)
		elif encoder == ENC_SNAPSHOT:
			self.selectSong(self.libseq.getSong() + value)

	# Function to handle zyncoder polling
	#	Note: Zyncoder provides positive integers. We need +/- 1 so we keep zyncoder at +1 and calculate offset
	def zyncoder_read(self):
		if not self.shown:
			return
		if zyncoder.lib_zyncoder:
			for encoder in range(len(self.zyncoderOwner)):
				if self.zyncoderOwner[encoder]:
					# Found a registered zyncoder
					value = zyncoder.lib_zyncoder.get_value_zyncoder(encoder)
					if value != 64:
						zyncoder.lib_zyncoder.set_value_zyncoder(encoder, 64, 0)
						self.zyncoderOwner[encoder].onZyncoder(encoder, value - 64)

	# Function to handle CUIA encoder changes
	def onCuiaEncoder(self, encoder, value):
		if self.zyncoderOwner[encoder]:
			self.zyncoderOwner[encoder].onZyncoder(encoder, value)

	# Function to handle CUIA SELECT_UP command
	def select_up(self):
		self.onCuiaEncoder(ENC_SELECT, 1);

	# Function to handle CUIA SELECT_DOWN command
	def select_down(self):
		self.onCuiaEncoder(ENC_SELECT, -1);

	# Function to handle CUIA LAYER_UP command
	def layer_up(self):
		self.onCuiaEncoder(ENC_LAYER, 1);

	# Function to handle CUIA LAYER_DOWN command
	def layer_down(self):
		self.onCuiaEncoder(ENC_LAYER, -1);

	# Function to handle CUIA SNAPSHOT_UP command
	def snapshot_up(self):
		self.onCuiaEncoder(ENC_SNAPSHOT, 1);

	# Function to handle CUIA SNAPSHOT_DOWN command
	def snapshot_down(self):
		self.onCuiaEncoder(ENC_SNAPSHOT, -1);

	# Function to handle CUIA BACK_UP command
	def back_up(self):
		self.onCuiaEncoder(ENC_BACK, 1);

	# Function to handle CUIA BACK_UP command
	def back_down(self):
		self.onCuiaEncoder(ENC_BACK, -1);

	# Function to handle CUIA SELECT command
	def switch_select(self, t):
		self.switch(ENC_SELECT, t)

	# Function to handle switch presses
	#	switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def onSwitch(self, switch, type):
		if switch == ENC_LAYER and not self.lstMenu.winfo_viewable():
			self.toggleMenu()
		elif switch == ENC_BACK:
			if self.lstMenu.winfo_viewable():
				# Close menu
				self.hideMenu()
				return True
			if self.paramEditorItem:
				# Close parameter editor
				self.hideParamEditor()
				return True
			if self.child == self.patternEditor:
				self.showChild(self.song_editor_mode)
				return True
			return False
		elif switch == ENC_SELECT or switch == ENC_LAYER:
			if self.lstMenu.winfo_viewable():
				self.onMenuSelect()
				return True
			elif self.paramEditorItem:
				self.menuValueAssert()
				return True
		return True # Tell parent that we handled all short and bold key presses

	# Function to manage switch press
	#	switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def switch(self, switch, type):
		if type == 'S':
			typeIndex = 0
		elif type == 'B':
			typeIndex = 1
		elif type == 'L':
			typeIndex = 2
		else:
			return
		index = switch * 3 + typeIndex
		if index >= len(self.switchOwner) or self.switchOwner[index] == None:
			return False # No one is handling this switch action so let parent manage it
		return self.switchOwner[index].onSwitch(switch, type)

	# Function to register ownsership of switches
	#	switch: Index of switch [0..3]
	#	object: Object to register as owner
	#	type: Press type ['S'=Short, 'B'=Bold, 'L'=Long, Default:'S']
	def registerSwitch(self, switch, object, type='S'):
		if type == 'S':
			typeIndex = 0
		elif type == 'B':
			typeIndex = 1
		elif type == 'L':
			typeIndex = 2
		else:
			return
		index = switch * 3 + typeIndex
		if index >= len(self.switchOwner):
			return
		self.switchOwner[index] = None
		if self.shown:
			self.switchOwner[index] = object

	# Function to unrestister ownership of a switch from an object
	#	switch: Index of switch [0..3]
	#	type: Press type ['S'=Short, 'B'=Bold, 'L'=Long, Default:'S']
	def unregisterSwitch(self, switch, type=0):
		if type == 'S':
			typeIndex = 0
		elif type == 'B':
			typeIndex = 1
		elif type == 'L':
			typeIndex = 2
		else:
			return
		index = switch * 3 + typeIndex
		if index >= len(self.switchOwner):
			return
		self.registerSwitch(switch, self, type)

	# Function to register ownership of an encoder by an object
	#	encoder: Index of rotary encoder [0..3]
	#	object: Object to register as owner
	#	Note: Registers an object to own the encoder which will trigger that object's onZyncoder method when encoder rotated passing it +/- value since last read
	def registerZyncoder(self, encoder, object):
		if encoder >= len(self.zyncoderOwner):
			return
		self.zyncoderOwner[encoder] = None
		if self.shown and zyncoder.lib_zyncoder:
			pin_a=zynthian_gui_config.zyncoder_pin_a[encoder]
			pin_b=zynthian_gui_config.zyncoder_pin_b[encoder]
			zyncoder.lib_zyncoder.setup_zyncoder(encoder, pin_a, pin_b, 0, 0, None, 64, 128, 0)
			self.zyncoderOwner[encoder] = object

	# Function to unregister ownership of an encoder from an object
	#	encoder: Index of encoder to unregister
	def unregisterZyncoder(self, encoder):
		if encoder >= len(self.zyncoderOwner):
			return
		self.registerZyncoder(encoder, self)

#------------------------------------------------------------------------------

