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

# Zynthian specific modules
from . import zynthian_gui_config
from zyncoder import *
from zyngui.zynthian_gui_keybinding import zynthian_gui_keybinding
from zyngui.zynthian_gui_patterneditor import zynthian_gui_patterneditor
from zyngui.zynthian_gui_songeditor import zynthian_gui_songeditor
from zyngui.zynthian_gui_seqtrigger import zynthian_gui_seqtrigger
import ctypes
from os.path import dirname, realpath

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

# Class implements host screen which shows topstrap with widgets, title and menu and hosts a panel below
class zynthian_gui_stepsequencer():

	# Function to initialise class
	def __init__(self):
		self.shown = False # True when GUI in view
		self.zyncoderOwner = [None, None, None, None] # Object that is currently "owns" encoder, indexed by encoder
		self.zyngui = zynthian_gui_config.zyngui # Zynthian GUI configuration
		self.child = None # Index of child (from self.children)
		self.children = [
			{'title':'Pattern Editor', 'class':zynthian_gui_patterneditor, 'instance':None},
			{'title':'Song Editor', 'class':zynthian_gui_songeditor, 'instance':None},
			{'title':'ZynPad', 'class':zynthian_gui_seqtrigger, 'instance':None},
			]

		# Initalise libseq and load pattern from file
		# TODO: Should this be done at higher level rather than within a screen?
		self.libseq = ctypes.CDLL(dirname(realpath(__file__))+"/../zynseq/build/libzynseq.so")
		self.libseq.init()
		self.filename = os.environ.get("ZYNTHIAN_MY_DATA_DIR", "/zynthian/zynthian-my-data") + "/sequences/patterns.zynseq"
		self.load(self.filename)

		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.display_height

		#Status Area Canvas Objects
		self.status_cpubar = None
		self.status_peak_lA = None
		self.status_peak_mA = None
		self.status_peak_hA = None
		self.status_hold_A = None
		self.status_peak_lB = None
		self.status_peak_mB = None
		self.status_peak_hB = None
		self.status_hold_B = None
		self.status_error = None
		self.status_recplay = None
		self.status_midi = None

		#Status Area Parameters
		self.status_h = zynthian_gui_config.topbar_height
		self.status_l = int(1.8*zynthian_gui_config.topbar_height)
		self.status_rh = max(2,int(self.status_h/4))
		self.status_fs = int(self.status_h/3)
		self.status_lpad = self.status_fs

		#Digital Peak Meter (DPM) parameters
		self.dpm_rangedB = 30 # Lowest meter reading in -dBFS
		self.dpm_highdB = 10 # Start of yellow zone in -dBFS
		self.dpm_overdB = 3  # Start of red zone in -dBFS
		self.dpm_high = 1 - self.dpm_highdB / self.dpm_rangedB
		self.dpm_over = 1 - self.dpm_overdB / self.dpm_rangedB
		self.dpm_scale_lm = int(self.dpm_high * self.status_l)
		self.dpm_scale_lh = int(self.dpm_over * self.status_l)

		# Main Frame
		self.main_frame = tkinter.Frame(zynthian_gui_config.top,
			width=self.width,
			height=self.height,
			bg=CANVAS_BACKGROUND)
		self.main_frame.bind("<Key>", self.cb_keybinding)
		self.main_frame.grid_propagate(False) # Don't auto size main frame

		# Topbar frame
		self.tb_frame = tkinter.Frame(self.main_frame,
			width=zynthian_gui_config.display_width,
			height=zynthian_gui_config.topbar_height,
			bg=zynthian_gui_config.color_bg)
		self.tb_frame.grid_propagate(False)
		self.tb_frame.grid(row=0, column=0)
		self.tb_frame.grid_columnconfigure(0, weight=1)

		# Title
		font=tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=int(self.height * 0.05)),
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

		iconsize = 60
		iconsizes = [12,24,32,48,60]
		for size in iconsizes:
			if zynthian_gui_config.topbar_height <= size:
				iconsize = size
				break
		self.imgLoopOff = tkinter.PhotoImage(file="/zynthian/zynthian-ui/icons/%d/loop.png" % (iconsize))
		self.imgLoopOn = tkinter.PhotoImage(file="/zynthian/zynthian-ui/icons/%d/loopon.png" % (iconsize))
		self.imgBack = tkinter.PhotoImage(file="/zynthian/zynthian-ui/icons/%d/left.png" % (iconsize))
		self.imgForward = tkinter.PhotoImage(file="/zynthian/zynthian-ui/icons/%d/right.png" % (iconsize))
		self.imgUp = tkinter.PhotoImage(file="/zynthian/zynthian-ui/icons/%d/up.png" % (iconsize))
		self.imgDown = tkinter.PhotoImage(file="/zynthian/zynthian-ui/icons/%d/down.png" % (iconsize))

		self.btnTransport = tkinter.Button(self.tb_frame, command=self.toggleTransport,
			image=self.imgLoopOff,
			bd=0, highlightthickness=0)
		self.btnTransport.grid(column=1, row=0)

		# Parameter value editor
		self.paramEditorItem = None
		self.MENU_ITEMS = {'Back':None} # Dictionary of menu items
		self.param_editor_canvas = tkinter.Canvas(self.tb_frame,
			height=zynthian_gui_config.topbar_height,
			bd=0, highlightthickness=0,
			bg = zynthian_gui_config.color_bg)
		self.param_editor_canvas.grid_propagate(False)
		# Parameter editor cancel button
		self.btnParamCancel = tkinter.Button(self.param_editor_canvas, command=self.hideParamEditor,
			image=self.imgBack,
			bd=0, highlightthickness=0)
		self.btnParamCancel.grid(column=0, row=0)
		# Parameter editor decrement button
		self.btnParamDown = tkinter.Button(self.param_editor_canvas, command=self.decrementParam,
			image=self.imgDown,
			bd=0, highlightthickness=0, repeatdelay=500, repeatinterval=100)
		self.btnParamDown.grid(column=1, row=0)
		# Parameter editor increment button
		self.btnParamUp = tkinter.Button(self.param_editor_canvas, command=self.incrementParam,
			image=self.imgUp,
			bd=0, highlightthickness=0, repeatdelay=500, repeatinterval=100)
		self.btnParamUp.grid(column=2, row=0)
		# Parameter editor assert button
		self.btnParamAssert = tkinter.Button(self.param_editor_canvas, command=self.menuValueAssert,
			image=self.imgForward,
			bd=0, highlightthickness=0)
		self.btnParamAssert.grid(column=3, row=0)
		# Parameter editor value text
		self.param_title_canvas = tkinter.Canvas(self.param_editor_canvas, height=zynthian_gui_config.topbar_height, bd=0, highlightthickness=0, bg=zynthian_gui_config.color_bg)
		self.param_title_canvas.create_text(3, zynthian_gui_config.topbar_height / 2,
			anchor='w',
			font=tkFont.Font(family=zynthian_gui_config.font_topbar[0],
				size=int(self.height * 0.05)),
			fill=zynthian_gui_config.color_panel_tx,
			tags="lblparamEditorValue",
			text="VALUE...")
		self.param_title_canvas.grid(column=4, row=0, sticky='ew')
		self.param_editor_canvas.grid_columnconfigure(4, weight=1)

		# Canvas for displaying status: CPU, ...
		self.status_canvas = tkinter.Canvas(self.tb_frame,
			width=self.status_l+2,
			height=self.status_h,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg = zynthian_gui_config.color_bg)
		self.status_canvas.grid(column=2, row=0, sticky="ens", padx=(2,0))

		# Menu #TODO: Replace listbox with painted canvas providing swipe gestures
		self.listboxTextHeight = tkFont.Font(font=zynthian_gui_config.font_listbox).metrics('linespace')
		self.lstMenu = tkinter.Listbox(self.main_frame,
			font=zynthian_gui_config.font_listbox,
			height = int(self.height / self.listboxTextHeight / 2),
			bd=7,
			highlightthickness=0,
			relief='flat',
			bg=zynthian_gui_config.color_panel_bg,
			fg=zynthian_gui_config.color_panel_tx,
			selectbackground=zynthian_gui_config.color_ctrl_bg_on,
			selectforeground=zynthian_gui_config.color_ctrl_tx,
			selectmode=tkinter.BROWSE)
		self.lstMenu.bind("<Key>", self.cb_keybinding)
		self.lstMenu.bind('<Button-1>', self.onMenuPress)
		self.lstMenu.bind('<B1-Motion>', self.onMenuDrag)
		self.lstMenu.bind('<ButtonRelease-1>', self.onMenuRelease)
		self.populateMenu()
		self.scrollTime = 0.0

	# Function to print traceback - for debug only
	#	TODO: Remove debug function (or move to other zynthian class)
	def debugTraceback(self):
		for trace in inspect.stack():
			print(trace.function)

	# Function to populate menu with global entries
	def populateMenu(self):
		self.MENU_ITEMS = {'Back':None}
		self.lstMenu.delete(0, tkinter.END)
		for item in self.MENU_ITEMS:
			self.lstMenu.insert(tkinter.END, item)
		for index in range(len(self.children)):
			self.addMenu({self.children[index]['title']:{'method':self.showChild, 'params':index}})
		self.addMenu({'Tempo':{'method':self.showParamEditor, 'params':{'min':0, 'max':999, 'value':self.zyngui.zyntransport.get_tempo(), 'getValue':self.zyngui.zyntransport.get_tempo, 'onChange':self.onMenuChange}}})
		self.addMenu({'Save':{'method':self.save}})
		self.addMenu({'Load':{'method':self.load}})

	# Function to update title
	#	title: Title to display in topbar
	def setTitle(self, title):
		self.title_canvas.itemconfig("lblTitle", text=title)

	# Function to get current child object from index within self.children[]
	def getChild(self):
		if self.child == None:
			return None
		return self.children[self.child]['instance']

	# Function to show GUI
	def show(self):
		if not self.shown:
			self.shown=True
			self.populateMenu()
			self.main_frame.grid_propagate(False)
			self.main_frame.grid(column=0, row=0)
			self.showChild(self.child)
		self.main_frame.focus()

	# Function to hide GUI
	def hide(self):
		if self.shown:
			self.shown=False
			self.main_frame.grid_forget()
			if self.getChild():
				self.getChild().hide()

	# Function to refresh the status widgets
	#	status: Dictionary containing update data
	def refresh_status(self, status={}):
		if self.shown:
			if zynthian_gui_config.show_cpu_status:
				# Display CPU-load bar
				l = int(status['cpu_load']*self.status_l/100)
				cr = int(status['cpu_load']*255/100)
				cg = 255-cr
				color = "#%02x%02x%02x" % (cr,cg,0)
				try:
					if self.status_cpubar:
						self.status_canvas.coords(self.status_cpubar,(0, 0, l, self.status_rh))
						self.status_canvas.itemconfig(self.status_cpubar, fill=color)
					else:
						self.status_cpubar=self.status_canvas.create_rectangle((0, 0, l, self.status_rh), fill=color, width=0)
				except Exception as e:
					logging.error(e)
			else:
				# Display audio peak
				signal = max(0, 1 + status['peakA'] / self.dpm_rangedB)
				llA = int(min(signal, self.dpm_high) * self.status_l)
				lmA = int(min(signal, self.dpm_over) * self.status_l)
				lhA = int(min(signal, 1) * self.status_l)
				signal = max(0, 1 + status['peakB'] / self.dpm_rangedB)
				llB = int(min(signal, self.dpm_high) * self.status_l)
				lmB = int(min(signal, self.dpm_over) * self.status_l)
				lhB = int(min(signal, 1) * self.status_l)
				signal = max(0, 1 + status['holdA'] / self.dpm_rangedB)
				lholdA = int(min(signal, 1) * self.status_l)
				signal = max(0, 1 + status['holdB'] / self.dpm_rangedB)
				lholdB = int(min(signal, 1) * self.status_l)
				try:
					# Channel A (left)
					if self.status_peak_lA:
						self.status_canvas.coords(self.status_peak_lA,(0, 0, llA, self.status_rh/2))
						self.status_canvas.itemconfig(self.status_peak_lA, state='normal')
					else:
						self.status_peak_lA=self.status_canvas.create_rectangle((0, 0, 0, 0), fill="#00C000", width=0, state='hidden')

					if self.status_peak_mA:
						if lmA >= self.dpm_scale_lm:
							self.status_canvas.coords(self.status_peak_mA,(self.dpm_scale_lm, 0, lmA, self.status_rh/2))
							self.status_canvas.itemconfig(self.status_peak_mA, state="normal")
						else:
							self.status_canvas.itemconfig(self.status_peak_mA, state="hidden")
					else:
						self.status_peak_mA=self.status_canvas.create_rectangle((0, 0, 0, 0), fill="#C0C000", width=0, state='hidden')

					if self.status_peak_hA:
						if lhA >= self.dpm_scale_lh:
							self.status_canvas.coords(self.status_peak_hA,(self.dpm_scale_lh, 0, lhA, self.status_rh/2))
							self.status_canvas.itemconfig(self.status_peak_hA, state="normal")
						else:
							self.status_canvas.itemconfig(self.status_peak_hA, state="hidden")
					else:
						self.status_peak_hA=self.status_canvas.create_rectangle((0, 0, 0, 0), fill="#C00000", width=0, state='hidden')

					if self.status_hold_A:
						self.status_canvas.coords(self.status_hold_A,(lholdA, 0, lholdA, self.status_rh/2))
						if lholdA >= self.dpm_scale_lh:
							self.status_canvas.itemconfig(self.status_hold_A, state="normal", fill="#FF0000")
						elif lholdA >= self.dpm_scale_lm:
							self.status_canvas.itemconfig(self.status_hold_A, state="normal", fill="#FFFF00")
						elif lholdA > 0:
							self.status_canvas.itemconfig(self.status_hold_A, state="normal", fill="#00FF00")
						else:
							self.status_canvas.itemconfig(self.status_hold_A, state="hidden")
					else:
						self.status_hold_A=self.status_canvas.create_rectangle((0, 0, 0, 0), width=0, state='hidden')

					# Channel B (right)
					if self.status_peak_lB:
						self.status_canvas.coords(self.status_peak_lB,(0, self.status_rh/2 + 1, llB, self.status_rh + 1))
						self.status_canvas.itemconfig(self.status_peak_lB, state='normal')
					else:
						self.status_peak_lB=self.status_canvas.create_rectangle((0, 0, 0, 0), fill="#00C000", width=0, state='hidden')

					if self.status_peak_mB:
						if lmB >= self.dpm_scale_lm:
							self.status_canvas.coords(self.status_peak_mB,(self.dpm_scale_lm, self.status_rh/2 + 1, lmB, self.status_rh + 1))
							self.status_canvas.itemconfig(self.status_peak_mB, state="normal")
						else:
							self.status_canvas.itemconfig(self.status_peak_mB, state="hidden")
					else:
						self.status_peak_mB=self.status_canvas.create_rectangle((0, 0, 0, 0), fill="#C0C000", width=0, state='hidden')

					if self.status_peak_hB:
						if lhB >= self.dpm_scale_lh:
							self.status_canvas.coords(self.status_peak_hB,(self.dpm_scale_lh, self.status_rh/2 + 1, lhB, self.status_rh + 1))
							self.status_canvas.itemconfig(self.status_peak_hB, state="normal")
						else:
							self.status_canvas.itemconfig(self.status_peak_hB, state="hidden")
					else:
						self.status_peak_hB=self.status_canvas.create_rectangle((0, 0, 0, 0), fill="#C00000", width=0, state='hidden')

					if self.status_hold_B:
						self.status_canvas.coords(self.status_hold_B,(lholdB, self.status_rh/2 + 1, lholdB, self.status_rh + 1))
						if lholdB >= self.dpm_scale_lh:
							self.status_canvas.itemconfig(self.status_hold_B, state="normal", fill="#FF0000")
						elif lholdB >= self.dpm_scale_lm:
							self.status_canvas.itemconfig(self.status_hold_B, state="normal", fill="#FFFF00")
						elif lholdB > 0:
							self.status_canvas.itemconfig(self.status_hold_B, state="normal", fill="#00FF00")
						else:
							self.status_canvas.itemconfig(self.status_hold_B, state="hidden")
					else:
						self.status_hold_B=self.status_canvas.create_rectangle((0, 0, 0, 0), width=0, state='hidden')

				except Exception as e:
					logging.error("%s" % e)

			#status['xrun']=True
			#status['audio_recorder']='PLAY'

			# Display error flags
			flags = ""
			color = zynthian_gui_config.color_status_error
			if 'xrun' in status and status['xrun']:
				#flags = "\uf00d"
				flags = "\uf071"
			elif 'undervoltage' in status and status['undervoltage']:
				flags = "\uf0e7"
			elif 'overtemp' in status and status['overtemp']:
				#flags = "\uf2c7"
				flags = "\uf769"

			if not self.status_error:
				self.status_error = self.status_canvas.create_text(
					int(self.status_fs*0.7),
					int(self.status_h*0.6),
					width=int(self.status_fs*1.2),
					justify=tkinter.RIGHT,
					fill=color,
					font=("FontAwesome",self.status_fs),
					text=flags)
			else:
				self.status_canvas.itemconfig(self.status_error, text=flags, fill=color)

			# Display Rec/Play flags
			flags = ""
			color = zynthian_gui_config.color_bg
			if 'audio_recorder' in status:
				if status['audio_recorder']=='REC':
					flags = "\uf111"
					color = zynthian_gui_config.color_status_record
				elif status['audio_recorder']=='PLAY':
					flags = "\uf04b"
					color = zynthian_gui_config.color_status_play
				elif status['audio_recorder']=='PLAY+REC':
					flags = "\uf144"
					color = zynthian_gui_config.color_status_record
			if not flags and 'midi_recorder' in status:
				if status['midi_recorder']=='REC':
					flags = "\uf111"
					color = zynthian_gui_config.color_status_record
				elif status['midi_recorder']=='PLAY':
					flags = "\uf04b"
					color = zynthian_gui_config.color_status_play
				elif status['midi_recorder']=='PLAY+REC':
					flags = "\uf144"
					color = zynthian_gui_config.color_status_record

			if not self.status_recplay:
				self.status_recplay = self.status_canvas.create_text(
					int(self.status_fs*2.6),
					int(self.status_h*0.6),
					width=int(self.status_fs*1.2),
					justify=tkinter.RIGHT,
					fill=color,
					font=("FontAwesome",self.status_fs),
					text=flags)
			else:
				self.status_canvas.itemconfig(self.status_recplay, text=flags, fill=color)

			# Display MIDI flag
			flags=""
			if 'midi' in status and status['midi']:
				flags="m";
				#flags="\uf001";
				#flags="\uf548";
			else:
				flags=""
			if not self.status_midi:
				mfs=int(self.status_fs*1.3)
				self.status_midi = self.status_canvas.create_text(
					int(self.status_l-mfs+1),
					int(self.status_h*0.55),
					width=int(mfs*1.2),
					justify=tkinter.RIGHT,
					fill=zynthian_gui_config.color_status_midi,
					font=(zynthian_gui_config.font_family, mfs),
					#font=("FontAwesome",self.status_fs),
					text=flags)
			else:
				self.status_canvas.itemconfig(self.status_midi, text=flags)

		if self.zyngui.zyntransport.get_state():
			self.btnTransport.configure(image=self.imgLoopOn)
		else:
			self.btnTransport.configure(image=self.imgLoopOff)

		# Refresh child panel
		if self.getChild() and self.getChild().refresh_status:
			self.getChild().refresh_status()

	# Function to open menu
	def showMenu(self):
		rows = min((self.height - zynthian_gui_config.topbar_height) / self.listboxTextHeight, self.lstMenu.size())
		self.lstMenu.configure(height = int(rows))
		self.lstMenu.grid(row=1, column=0, sticky="wn")
		self.lstMenu.tkraise()
		self.lstMenu.selection_clear(0,tkinter.END)
		self.lstMenu.activate(0)
		self.lstMenu.selection_set(0)
		self.lstMenu.see(0)
		for encoder in range(4):
			self.unregisterZyncoder(encoder)
		self.registerZyncoder(ENC_SELECT, self)
		self.registerZyncoder(ENC_LAYER, self)

	# Function to close menu
	def hideMenu(self):
		self.unregisterZyncoder(ENC_SELECT)
		self.lstMenu.grid_forget()
		for encoder in range(4):
			self.unregisterZyncoder(encoder)
		if self.getChild():
			self.getChild().setupEncoders()

	# Function to handle title bar click
	#	event: Mouse event (not used)
	def toggleMenu(self, event=None):
		if self.lstMenu.winfo_viewable():
			self.hideMenu()
		else:
			self.showMenu()

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
			if menuItem == 'Back':
				self.zyngui.zynswitch_defered('S',1)
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
		self.registerZyncoder(ENC_SELECT, self)
		self.registerZyncoder(ENC_LAYER, self)

	# Function to hide menu editor
	def hideParamEditor(self):
		self.paramEditorItem = None
		self.param_editor_canvas.grid_forget()
		for encoder in range(4):
			self.unregisterZyncoder(encoder)
		if self.getChild():
			self.getChild().setupEncoders()

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
		if self.paramEditorItem == 'Tempo': #TODO: Tempo should be handled by paramEditor 'getValue'
			self.zyngui.zyntransport.set_tempo(value)
		self.setParam(self.paramEditorItem, 'value', value)
		return "%s: %d" % (self.paramEditorItem, value)

	# Function to change parameter value
	#	value: Offset by which to change parameter value
	def changeParam(self, value):
		value = self.getParam(self.paramEditorItem, 'value') + value
		if value < self.getParam(self.paramEditorItem, 'min'):
			value = self.getParam(self.paramEditorItem, 'min')
		if value > self.getParam(self.paramEditorItem, 'max'):
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
	def showChild(self, childIndex):
		if not self.shown:
			return
		self.hideChild()
		if childIndex == None:
			childIndex = 0
		if not self.children[childIndex]['instance']:
			self.children[childIndex]['instance'] = self.children[childIndex]['class'](self)
		self.child = childIndex
		self.getChild().show()

	# Function to hide child GUI
	def hideChild(self):
		if self.getChild():
			self.getChild().hide()
		self.child = None
		self.hideParamEditor()
		self.populateMenu()
		self.setTitle("Step Sequencer")

	# Function to toggle transport
	def toggleTransport(self):
		self.zyngui.zyntransport.transport_toggle()
		if self.getChild():
			if self.zyngui.zyntransport.get_state():
				self.getChild().onTransportStart()
			else:
				self.getChild().onTransportStop()

	# Function to save to RIFF file
	#	filename: Full path and filename to save
	def save(self, filename = None):
		if not filename:
			filename = self.filename
		os.makedirs(os.path.dirname(filename), exist_ok=True)
		self.libseq.save(bytes(filename, "utf-8"))

	# Function to load from RIFF file
	#	filename: Full path and filename to load
	def load(self, filename = None):
		if not filename:
			filename = self.filename
		self.libseq.load(bytes(filename, "utf-8"))
		if self.getChild():
			self.getChild().onLoad()
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

	# Function to handle switch press
	#	switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def switch(self, switch, type):
		if type == "L":
			return False # Don't handle any long presses
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
			return False
		elif switch == ENC_SELECT or switch == ENC_LAYER:
			if self.lstMenu.winfo_viewable():
				self.onMenuSelect()
				return True
			elif self.paramEditorItem:
				self.menuValueAssert()
				return True
		elif switch == ENC_SNAPSHOT:
			self.toggleTransport()
		if self.getChild():
			return self.getChild().switch(switch, type)
		return True # Tell parent that we handled all short and bold key presses

	#Function to handle computer keyboard key press
	def cb_keybinding(self, event):
		logging.debug("Key press {} {}".format(event.keycode, event.keysym))
		self.main_frame.focus_set() # Must remove focus from listbox to avoid interference with physical keyboard

		if not zynthian_gui_keybinding.getInstance().isEnabled():
			logging.debug("Key binding is disabled - ignoring key press")
			return

		# Ignore TAB key (for now) to avoid confusing widget focus change
		if event.keysym == "Tab":
			return

		# Space is not recognised as keysym so need to convert keycode
		if event.keycode == 65:
			keysym = "Space"
		else:
			keysym = event.keysym

		action = zynthian_gui_keybinding.getInstance().get_key_action(keysym, event.state)
		if action != None:
			self.zyngui.callable_ui_action(action)

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
		self.zyncoderOwner[encoder] = None

#------------------------------------------------------------------------------

