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
from zyngine import zynthian_engine_transport as zyntransport
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
		self.zyncoderMutex = [None, None, None, None] # Object that is currently "owns" encoder, indexed by encoder
		self.zyngui = zynthian_gui_config.zyngui # Zynthian GUI configuration
		self.child = None # Child GUI class

		# Initalise libseq and load pattern from file
		self.libseq = ctypes.CDLL(dirname(realpath(__file__))+"/../zynseq/build/libzynseq.so")
		self.libseq.init()
		self.libseq.load(bytes(os.environ.get("ZYNTHIAN_MY_DATA_DIR", "/zynthian/zynthian-my-data") + "/sequences/patterns.zynseq", "utf-8"))

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

		# Topbar's frame
		buttonSize = zynthian_gui_config.topbar_height - 4
		self.tb_frame = tkinter.Frame(self.main_frame, 
			width=zynthian_gui_config.display_width,
			height=zynthian_gui_config.topbar_height,
			bg=zynthian_gui_config.color_bg)
		self.tb_frame.grid(row=0, column=0)
		self.tb_frame.grid_propagate(False)
		self.tb_frame.bind('<Button-1>', self.toggleMenu)

		# Title
		title_width=zynthian_gui_config.display_width-self.status_l - self.status_lpad - 2 - buttonSize
		self.title_canvas = tkinter.Canvas(self.tb_frame,
			width=title_width,
			height=zynthian_gui_config.topbar_height,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg = zynthian_gui_config.color_bg)
		self.title_canvas.create_text(0, zynthian_gui_config.topbar_height / 2,
			anchor="w",
			font=tkFont.Font(family=zynthian_gui_config.font_topbar[0],
				size=int(self.height * 0.05)),
			fill=zynthian_gui_config.color_panel_tx,
			tags="lblTitle",
			text="Step Sequencer")
		self.title_canvas.grid(row=0, column=0)
		self.title_canvas.bind('<Button-1>', self.toggleMenu)

		# Transport play button
		self.transport_canvas = tkinter.Canvas(self.tb_frame,
			width=buttonSize + 4,
			height=buttonSize + 4,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg = zynthian_gui_config.color_bg)
		self.transport_canvas.create_rectangle(3, 3, buttonSize, buttonSize, outline="white", tags="btnTransport", fill=zynthian_gui_config.color_bg)
		self.transport_canvas.create_text(2 + buttonSize / 2, 2 + buttonSize / 2,
			font=tkFont.Font(family=zynthian_gui_config.font_topbar[0],
				size=int(self.height * 0.05)),
			fill=zynthian_gui_config.color_panel_tx,
			tags="btnTransport",
			text=">")
		self.transport_canvas.tag_bind("btnTransport", '<Button-1>', self.transportToggle)
		self.transport_canvas.grid(row=0, column=1)

		# Parameter value editor
		self.paramEditorState = False
		self.MENU_ITEMS = {'Back':None} # Dictionary of menu items
		self.paramEditor = {'menuitem':None,'min':0, 'max':1, 'value':0, 'onChange':self.onMenuChange} # Values for currently editing menu item
		self.param_editor_canvas = tkinter.Canvas(self.tb_frame,
			width=title_width,
			height=zynthian_gui_config.topbar_height,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg = zynthian_gui_config.color_bg)
		# Parameter editor cancel button
		self.param_editor_canvas.create_rectangle(2, 2, buttonSize + 2, buttonSize + 2, outline="white", tags="btnparamEditorCancel", fill=zynthian_gui_config.color_bg)
		self.param_editor_canvas.create_text(2 + buttonSize / 2, zynthian_gui_config.topbar_height / 2,
			font=tkFont.Font(family=zynthian_gui_config.font_topbar[0],
				size=int(self.height * 0.05)),
			fill=zynthian_gui_config.color_panel_tx,
			tags="btnparamEditorCancel",
			text="<")

		self.param_editor_canvas.tag_bind("btnparamEditorCancel", '<Button-1>', self.hideparamEditor)
		# Parameter editor decrement button
		self.param_editor_canvas.create_rectangle(2 + buttonSize, 2, 2 * buttonSize + 2, buttonSize + 2, outline="white", tags="btnparamEditorDown", fill=zynthian_gui_config.color_bg)
		self.param_editor_canvas.create_text(2 + 3 * buttonSize / 2, zynthian_gui_config.topbar_height / 2,
			font=tkFont.Font(family=zynthian_gui_config.font_topbar[0],
				size=int(self.height * 0.05)),
			fill=zynthian_gui_config.color_panel_tx,
			tags="btnparamEditorDown",
			text="-")
		self.param_editor_canvas.tag_bind("btnparamEditorDown", '<Button-1>', self.decrementParam)
		# Parameter editor increment button
		self.param_editor_canvas.create_rectangle(2 + 2 * buttonSize, 2, 3 * buttonSize + 2, buttonSize + 2, outline="white", tags="btnparamEditorUp", fill=zynthian_gui_config.color_bg)
		self.param_editor_canvas.create_text(2 + 5 * buttonSize / 2, zynthian_gui_config.topbar_height / 2,
			font=tkFont.Font(family=zynthian_gui_config.font_topbar[0],
				size=int(self.height * 0.05)),
			fill=zynthian_gui_config.color_panel_tx,
			tags="btnparamEditorUp",
			text="+")
		self.param_editor_canvas.tag_bind("btnparamEditorUp", '<Button-1>', self.incrementParam)
		# Parameter editor assert button
		self.param_editor_canvas.create_rectangle(2 + 3 * buttonSize, 2, 4 * buttonSize + 2, buttonSize + 2, outline="white", tags="btnparamEditorAssert", fill=zynthian_gui_config.color_bg)
		self.param_editor_canvas.create_text(2 + 7 * buttonSize / 2, zynthian_gui_config.topbar_height / 2,
			font=tkFont.Font(family=zynthian_gui_config.font_topbar[0],
				size=int(self.height * 0.05)),
			fill=zynthian_gui_config.color_panel_tx,
			tags="btnparamEditorAssert",
			text=">")
		self.param_editor_canvas.tag_bind("btnparamEditorAssert", '<Button-1>', self.menuValueAssert)
		# Parameter editor value text
		self.param_editor_canvas.create_text(6 + 4 * buttonSize, zynthian_gui_config.topbar_height / 2,
			font=tkFont.Font(family=zynthian_gui_config.font_topbar[0],
				size=int(self.height * 0.05)),
			anchor="w",
			fill=zynthian_gui_config.color_panel_tx,
			tags="btnparamEditorValue",
			text="VALUE...")

		# Canvas for displaying status: CPU, ...
		self.status_canvas = tkinter.Canvas(self.tb_frame,
			width=self.status_l+2,
			height=self.status_h,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg = zynthian_gui_config.color_bg)
		self.status_canvas.grid(row=0, column=2, sticky="ens", padx=(self.status_lpad,0))

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

		self.showChild(zynthian_gui_patterneditor)
#		self.showChild(zynthian_gui_seqtrigger)

	# Function to print traceback - for debug only
	#	TODO: Remove debug function (or move to other zynthian class)
	def debugTraceback(self):
		for trace in inspect.stack():
			print(trace.function)

	# Function to toggle playback
	#	event: Mouse event (not used)
	def transportToggle(self, event=None):
		if self.libseq.getPlayMode(0):
			self.libseq.setPlayMode(0, 0)
		else:
			self.libseq.setPlayMode(0, 2)

	# Function to populate menu with global entries
	def populateMenu(self):
		self.MENU_ITEMS = {'Back':None}
		self.lstMenu.delete(0, tkinter.END)
		for item in self.MENU_ITEMS:
			self.lstMenu.insert(tkinter.END, item)
		self.addMenu({'Pattern Editor':{'method':self.showChild, 'params':zynthian_gui_patterneditor}})
		self.addMenu({'Song Editor':{'method':self.showChild, 'params':zynthian_gui_songeditor}})
		self.addMenu({'Pad Trigger':{'method':self.showChild, 'params':zynthian_gui_seqtrigger}})

	# Function to update title
	#	title: Title to display in topbar
	def setTitle(self, title):
		self.title_canvas.itemconfig("lblTitle", text=title)

	# Function to add items to menu
	#	item: Dictionary containing menu item data, indexed by menu item title
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

	# Function to get menu data parameters
	#	item: Menu item name
	#	param: Parameter name
	#	returns: Parameter value
	def getParam(self, item, param):
		if item in self.MENU_ITEMS and param in self.MENU_ITEMS[item]:
			return self.MENU_ITEMS[item]['params'][value]
		return None

	# Function to show GUI
	def show(self):
		if not self.shown:
			self.shown=True
			self.main_frame.grid()
			if self.child:
				self.child.show()
		self.main_frame.focus()

	# Function to hide GUI
	def hide(self):
		if self.shown:
			self.shown=False
			self.main_frame.grid_forget()
			if self.child:
				self.child.hide()

	# Function to get GUI display status
	#	returns True if showing
	def is_shown(self):
		try:
			self.main_frame.grid_info()
			return True
		except:
			return False

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

		# Transport play status #TODO: Need to relate to selected sequence
		if self.libseq.getPlayMode(0):
			self.transport_canvas.config(bg="green")
		else:
			self.transport_canvas.config(bg=zynthian_gui_config.color_bg)

		# Refresh child panel
		if self.child and self.child.shown and self.child.refresh_status:
			self.child.refresh_status()

	# Function to open menu
	def showMenu(self):
		self.lstMenu.grid(row=1, column=0, sticky="wn")
		self.lstMenu.tkraise()
		self.lstMenu.selection_clear(0,tkinter.END)
		self.lstMenu.activate(0)
		self.lstMenu.selection_set(0)
		self.registerZyncoder(ENC_SELECT, self)

	# Function to close menu
	def hideMenu(self):
		self.unregisterZyncoder(ENC_SELECT)
		self.lstMenu.grid_forget()
		if self.child:
			self.child.setupEncoders()

	# Function to handle title bar click
	#	event: Mouse event (not used)
	def toggleMenu(self, event=None):
		if self.lstMenu.winfo_viewable():
			self.hideMenu()
		else:
			self.showMenu()

	# Function to handle press menu
	def onMenuPress(self, event):
		print("Listbox press", self.main_frame.bbox(self.lstMenu))

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
				print("oops!")
		#self.lstMenu.winfo(height)
		pass

	# Function to handle release menu
	def onMenuRelease(self, event):
		self.onMenuSelect(event)

	# Function to handle menu item selection (SELECT button or click on listbox entry)
	#	event: Listbox event (not used)
	def onMenuSelect(self, event=None):
		if self.lstMenu.winfo_viewable():
			sel = None
			action = None
			params = {}
			try:
				sel = self.lstMenu.get(self.lstMenu.curselection()[0])
				action = self.MENU_ITEMS[sel]['method']
				params = self.MENU_ITEMS[sel]['params']
				params.update({'menuitem':sel}) # Add menu name to params
			except:
				logging.error("**Error selecting menu**")
			self.hideMenu()
			if not sel:
				return
			if sel == 'Back':
				self.zyngui.zynswitch_defered('S',1)
			elif action:
				action(params) # Call menu handler defined during addMenu

	# Function to set menu editor value and get display label text
	#	value: Menu item's value
	#	returns: String to populate menu editor label
	#	note: This is default but other method may be used for each menu item
	def onMenuChange(self, value):
		if value < self.paramEditor['min']:
			value = self.paramEditor['min']
		if value > self.paramEditor['max']:
			value = self.paramEditor['max']
		self.paramEditor['value'] = value
		return "%s: %d" % (self.paramEditor['menuitem'], value)

	# Function to show menu editor
	#	params: Dictionary of menu editor parameters: {
	#		'menuitem':<menu title>,
	#		'min':<minimum permissible value>, [Default: 0]
	#		'max':<maximum permissible value>, [Default: 1]
	#		'value':<current value>,  [Default: 0]
	#		'onChange':<function to call when value is changed by editor>,  [Default: zynthian_gui_stepsequencer::onMenuChange]
	#		'onAssert':<function to call when value is asserted, e.g. assert button pressed> [Default: None]}
	def showParamEditor(self, params):
		self.paramEditorState = True
		self.title_canvas.grid_forget()
		self.param_editor_canvas.grid(row=0, column=0)
		# Populate parameter editor with params from menuitem
		if 'menuitem' in params:
			self.paramEditor['menuitem'] = params['menuitem']
		if 'min' in params:
			self.paramEditor['min'] = params['min']
		else:
			self.paramEditor['min'] = 0
		if 'max' in params:
			self.paramEditor['max'] = params['max']
		else:
			self.paramEditor['max'] = 1
		if 'value' in params:
			self.paramEditor['value'] = params['value']
		else:
			self.paramEditor['value'] = 0
		if 'onChange' in params:
			self.paramEditor['onChange'] = params['onChange']
		else:
			self.paramEditor['onChange'] = self.onMenuChange
		self.param_editor_canvas.itemconfig("btnparamEditorValue", text=self.paramEditor['onChange'](self.paramEditor['value']))
		if 'onAssert' in params:
			self.paramEditor['onAssert'] = params['onAssert']
			self.param_editor_canvas.itemconfig("btnparamEditorAssert", state='normal')
		else:
			self.paramEditor['onAssert'] = None
			self.param_editor_canvas.itemconfig("btnparamEditorAssert", state='hidden')
		self.registerZyncoder(ENC_SELECT, self)

	# Function to hide menu editor
	def hideparamEditor(self, event):
		self.paramEditorState = False
		self.param_editor_canvas.grid_forget()
		self.title_canvas.grid(row=0, column=0)
		self.unregisterZyncoder(ENC_SELECT)
		if self.child:
			self.child.setupEncoders()

	# Function to decrement parameter value
	#	event: Click event (ignored)
	def decrementParam(self, event=None):
		if self.paramEditor['value'] > self.paramEditor['min']:
			self.paramEditor['value'] = self.paramEditor['value'] - 1
		result=self.paramEditor['onChange'](self.paramEditor['value'])
		if result == -1:
			hideparamEditor(0)
		else:
			self.param_editor_canvas.itemconfig("btnparamEditorValue", text=result)

	# Function to increment selected menu value
	#	event: Click event (ignored)
	def incrementParam(self, event=None):
		if self.paramEditor['value'] < self.paramEditor['max']:
			self.paramEditor['value'] = self.paramEditor['value'] + 1
		result=self.paramEditor['onChange'](self.paramEditor['value'])
		if result == -1:
			self.hideparamEditor(0)
		else:
			self.param_editor_canvas.itemconfig("btnparamEditorValue", text=result)

	# Function to assert selected menu value
	def menuValueAssert(self, event=None):
		if self.paramEditor and 'onAssert' in self.paramEditor and self.paramEditor['onAssert']:
			self.paramEditor['onAssert']()
		self.hideparamEditor(0)

	# Function to show child GUI
	def showChild(self, child):
		self.hideChild()
		self.child = child(self)
		if self.shown:
			self.child.show()

	# Function to hide child GUI
	def hideChild(self):
		if self.child:
			self.child.hide()
		self.child = None
		self.populateMenu()
		self.setTitle("Step Sequencer")

	# Function to refresh loading animation
	def refresh_loading(self):
		pass

	# Function to handle zyncoder value change
	#	encoder: Zyncoder index [0..4]
	#	value: Value of zyncoder change [+/- 1]
	def onZyncoder(self, encoder, value):
		if encoder == ENC_SELECT:
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
			elif self.paramEditorState:
				# Parameter editor showing
				if value > 0:
					self.incrementParam()
				elif value < 0:
					self.decrementParam()

	# Function to handle zyncoder polling
	#	Note: Zyncoder provides positive integers. We need +/- 1 so we keep zyncoder at +1 and calculate offset
	def zyncoder_read(self):
		if not self.shown:
			return
		if zyncoder.lib_zyncoder:
			for encoder in range(len(self.zyncoderMutex)):
				if self.zyncoderMutex[encoder]:
					# Found a registered zyncoder
					value = zyncoder.lib_zyncoder.get_value_zyncoder(encoder)
					if value == 2:
						change = 1
						zyncoder.lib_zyncoder.set_value_zyncoder(encoder, 1)
						self.zyncoderMutex[encoder].onZyncoder(encoder, change)
					elif value == 0:
						change = -1
						zyncoder.lib_zyncoder.set_value_zyncoder(encoder, 1)
						self.zyncoderMutex[encoder].onZyncoder(encoder, change)

	# Function to handle CUIA encoder changes
	def onCuiaEncoder(self, encoder, value):
		if self.zyncoderMutex[encoder]:
			self.zyncoderMutex[encoder].onZyncoder(encoder, value)

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
		if switch == ENC_BACK:
			if self.lstMenu.winfo_viewable():
				# Close menu
				self.hideMenu()
				return True
			if self.paramEditorState:
				# Close parameter editor
				self.hideparamEditor(0)
				return True
			return False
		elif switch == ENC_LAYER:
			self.toggleMenu()
		elif switch == ENC_SELECT:
			if self.lstMenu.winfo_viewable():
				self.onMenuSelect()
				return True
			elif self.paramEditorState:
				self.menuValueAssert()
				return True
		if self.child:
			return self.child.switch(switch, type)
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
	#	Note: Registers an object to own the encoder which will trigger that object's onZyncoder method when encoder rotated passing it +/- 1 to indicate direction
	def registerZyncoder(self, encoder, object):
		if encoder >= len(self.zyncoderMutex):
			return
		self.zyncoderMutex[encoder] = None
		if self.shown and zyncoder.lib_zyncoder:
			pin_a=zynthian_gui_config.zyncoder_pin_a[encoder]
			pin_b=zynthian_gui_config.zyncoder_pin_b[encoder]
			zyncoder.lib_zyncoder.setup_zyncoder(encoder, pin_a, pin_b, 0, 0, None, 1, 2, 1)
			self.zyncoderMutex[encoder] = object

	# Function to unregister ownership of an encoder from an object
	#	encoder: Index of encoder to unregister
	def unregisterZyncoder(self, encoder):
		if encoder >= len(self.zyncoderMutex):
			return
		self.zyncoderMutex[encoder] = None

#------------------------------------------------------------------------------

