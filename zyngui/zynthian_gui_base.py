#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Base Class: Status Bar + Basic layout & events
#
# Copyright (C) 2015-2020 Fernando Moyano <jofemodo@zynthian.org>
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
import time
import logging
import tkinter
from threading import Timer
from tkinter import font as tkFont
from PIL import Image, ImageTk

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_keybinding import zynthian_gui_keybinding

#------------------------------------------------------------------------------
# Zynthian Base GUI Class: Status Bar + Basic layout & events
#------------------------------------------------------------------------------

class zynthian_gui_base:

	#Default buttonbar config (touchwidget)
	buttonbar_config = [
		(1, 'BACK'),
		(0, 'LAYER'),
		(2, 'LEARN'),
		(3, 'SELECT')
	]

	def __init__(self):
		self.shown = False
		self.zyngui = zynthian_gui_config.zyngui

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
		self.status_midi_clock = None

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

		#Title Area parameters
		self.title_canvas_width=zynthian_gui_config.display_width-self.status_l-self.status_lpad-2
		self.select_path_font=tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=zynthian_gui_config.font_topbar[1])
		self.select_path_width=0
		self.select_path_offset=0
		self.select_path_dir=2

		#Menu parameters
		iconsize = (zynthian_gui_config.topbar_height - 4, zynthian_gui_config.topbar_height - 4)
		self.image_play = ImageTk.PhotoImage(Image.open("/zynthian/zynthian-ui/icons/playing.png").resize(iconsize))
		self.image_playing = ImageTk.PhotoImage(Image.open("/zynthian/zynthian-ui/icons/playing.png").resize(iconsize))
		self.image_back = ImageTk.PhotoImage(Image.open("/zynthian/zynthian-ui/icons/back.png").resize(iconsize))
		self.image_forward = ImageTk.PhotoImage(Image.open("/zynthian/zynthian-ui/icons/tick.png").resize(iconsize))
		img = (Image.open("/zynthian/zynthian-ui/icons/arrow.png").resize(iconsize))
		self.image_up = ImageTk.PhotoImage(img)
		self.image_down = ImageTk.PhotoImage(img.rotate(180))

		# Main Frame
		self.main_frame = tkinter.Frame(zynthian_gui_config.top,
			width=zynthian_gui_config.display_width,
			height=zynthian_gui_config.display_height,
			bg=zynthian_gui_config.color_bg)

		# Topbar's frame
		self.tb_frame = tkinter.Frame(self.main_frame,
			width=zynthian_gui_config.display_width,
			height=zynthian_gui_config.topbar_height,
			bg=zynthian_gui_config.color_bg)
		self.tb_frame.grid(row=0, column=0, columnspan=3)
		self.tb_frame.grid_propagate(False)
		self.tb_frame.grid_columnconfigure(0, weight=1)
		# Setup Topbar's Callback
		self.tb_frame.bind("<Button-1>", self.toggle_menu)

		# Title
#		font=tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=int(self.height * 0.05)),
		font=zynthian_gui_config.font_topbar
		self.title_fg = zynthian_gui_config.color_panel_tx
		self.title_bg = zynthian_gui_config.color_header_bg
		self.title_canvas = tkinter.Canvas(self.tb_frame,
			height=zynthian_gui_config.topbar_height,
			bd=0,
			highlightthickness=0,
			bg = self.title_bg)
		self.title_canvas.grid_propagate(False)
		self.title_canvas.create_text(0, zynthian_gui_config.topbar_height / 2,
			font=font,
			anchor="w",
			fill=self.title_fg,
			tags="lblTitle",
			text="")
		self.title_canvas.grid(row=0, column=0, sticky='ew')
		self.title_canvas.bind('<Button-1>', self.toggle_menu)
		self.path_canvas = self.title_canvas
		self.title_timer = None

		# Topbar's Select Path
		self.select_path = tkinter.StringVar()
		self.select_path.trace("w", self.cb_select_path)
		self.label_select_path = tkinter.Label(self.title_canvas,
			font=zynthian_gui_config.font_topbar,
			textvariable=self.select_path,
			justify=tkinter.LEFT,
			bg=zynthian_gui_config.color_header_bg,
			fg=zynthian_gui_config.color_header_tx)
		self.label_select_path.place(x=0, y=0)
		# Setup Topbar's Callback
		self.label_select_path.bind("<Button-1>", self.toggle_menu)
		self.title_canvas.bind('<Button-1>', self.toggle_menu)


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

		# Canvas for displaying status: CPU, ...
		self.status_canvas = tkinter.Canvas(self.tb_frame,
			width=self.status_l+2,
			height=self.status_h,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg = zynthian_gui_config.color_bg)
		self.status_canvas.grid(row=0, column=1, sticky="ens", padx=(self.status_lpad,0))

		# Configure Topbar's Frame column widths
		self.tb_frame.grid_columnconfigure(0, minsize=self.title_canvas_width)

		# Init touchbar
		#self.init_buttonbar()

		self.button_push_ts = 0

		# Update Title
		self.set_select_path()
		self.cb_scroll_select_path()

	# Function to update title
	#	title: Title to display in topbar
	#	fg: Title foreground colour [Default: Do not change]
	#	bg: Title background colour [Default: Do not change]
	#	timeout: If set, title is shown for this period (seconds) then reverts to previous title
	def set_title(self, title, fg=None, bg=None, timeout = None):
		if self.title_timer:
			self.title_timer.cancel()
			self.title_timer = None
		if timeout:
			self.title_timer = Timer(timeout, self.on_title_timeout)
			self.title_timer.start()
		else:
			self.title = title
			if fg:
				self.title_fg = fg
			if bg:
				self.title_bg = bg
		self.select_path.set(title)
#		self.title_canvas.itemconfig("lblTitle", text=title, fill=self.title_fg)
		if fg:
			self.label_select_path.config(fg=fg)
		else:
			self.label_select_path.config(fg=self.title_fg)
		if bg:
			self.title_canvas.configure(bg=bg)
			self.label_select_path.config(bg=bg)
		else:
			self.title_canvas.configure(bg=self.title_bg)
			self.label_select_path.config(bg=self.title_bg)


	# Function to revert title after toast
	def on_title_timeout(self):
		if self.title_timer:
			self.title_timer.cancel()
			self.title_timer = None
		self.set_title(self.title)


	def init_buttonbar(self):
		# Touchbar frame
		if not zynthian_gui_config.enable_onscreen_buttons:
			return

		self.buttonbar_frame = tkinter.Frame(self.main_frame,
			width=zynthian_gui_config.display_width,
			height=zynthian_gui_config.buttonbar_height,
			bg=zynthian_gui_config.color_bg)
		self.buttonbar_frame.grid(row=3, column=0, columnspan=3, padx=(0,0), pady=(2,0))
		self.buttonbar_frame.grid_propagate(False)
		self.buttonbar_frame.grid_rowconfigure(
			0, minsize=zynthian_gui_config.buttonbar_height, pad=0)
		for i in range(4):
			self.buttonbar_frame.grid_columnconfigure(
				i, minsize=zynthian_gui_config.button_width, pad=0)
			self.add_button(i, self.buttonbar_config[i][0], self.buttonbar_config[i][1])


	def add_button(self, column, index, label):
		select_button = tkinter.Button(
			self.buttonbar_frame,
			bg=zynthian_gui_config.color_panel_bg,
			fg=zynthian_gui_config.color_header_tx,
			activebackground=zynthian_gui_config.color_panel_bg,
			activeforeground=zynthian_gui_config.color_header_tx,
			highlightbackground=zynthian_gui_config.color_bg,
			highlightcolor=zynthian_gui_config.color_bg,
			highlightthickness=0,
			bd=0,
			relief='flat',
			font=zynthian_gui_config.font_buttonbar,
			text=label)
		if column==0:
			padx = (0,1)
		elif column==3:
			padx = (1,0)
		else:
			padx = (1,1)
		select_button.grid(row=0, column=column, sticky='nswe', padx=padx)
		select_button.bind('<ButtonPress-1>', lambda e: self.button_down(index, e))
		select_button.bind('<ButtonRelease-1>', lambda e: self.button_up(index, e))


	def button_down(self, index, event):
		self.button_push_ts=time.monotonic()


	def button_up(self, index, event):
		t = 'S'
		if self.button_push_ts:
			dts=(time.monotonic()-self.button_push_ts)
			if dts<0.3:
				t = 'S'
			elif dts>=0.3 and dts<2:
				t = 'B'
			elif dts>=2:
				t = 'L'
		self.zyngui.zynswitch_defered(t,index)


	# Function to trigger BACK button
	def back(self, params=None):
		self.zyngui.zynswitch_defered('S',1)


	# Function to populate menu with global entries
	def populate_menu(self):
		self.lst_menu.delete(0, tkinter.END)
		self.menu_items = {} # Dictionary of menu items
		self.add_menu({'BACK':{'method':self.back}})


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


	# Function to close menu
	#	event: Mouse event (not used)
	def hide_menu(self, event=None):
		self.lst_menu.grid_forget()
		if zynthian_gui_config.enable_touch_widgets:
			self.menu_button_canvas.grid_forget()


	# Function to handle title bar click
	#	event: Mouse event (not used)
	def toggle_menu(self, event=None):
		if self.lst_menu.winfo_viewable():
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
		self.register_switch(ENC_SELECT, self, "SB")
		self.register_switch(ENC_BACK, self)


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


	def show(self):
		if not self.shown:
			self.shown=True
			self.main_frame.grid()

		self.main_frame.focus()


	def hide(self):
		if self.shown:
			self.shown=False
			self.main_frame.grid_forget()


	def is_shown(self):
		try:
			self.main_frame.grid_info()
			return True
		except:
			return False


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
					font=("FontAwesome", self.status_fs, "bold"),
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
					font=("FontAwesome", self.status_fs, "bold"),
					text=flags)
			else:
				self.status_canvas.itemconfig(self.status_recplay, text=flags, fill=color)

			# Display MIDI flag
			if 'midi' in status and status['midi']:
				mstate = "normal"
			else:
				mstate = "hidden"

			if not self.status_midi:
				self.status_midi = self.status_canvas.create_text(
					int(self.status_l-self.status_fs+1),
					int(self.status_h*0.6),
					width=int(self.status_fs*1.2),
					justify=tkinter.RIGHT,
					fill=zynthian_gui_config.color_status_midi,
					font=("FontAwesome", self.status_fs, "bold"),
					text="m",
					state=mstate)
			else:
				self.status_canvas.itemconfig(self.status_midi, state=mstate)

			# Display MIDI clock flag
			if 'midi_clock' in status and status['midi_clock']:
				mcstate = "normal"
			else:
				mcstate = "hidden"

			if not self.status_midi_clock:
				self.status_midi_clock = self.status_canvas.create_line(
					int(self.status_l-self.status_fs*1.7+1),
					int(self.status_h*0.85),
					int(self.status_l-2),
					int(self.status_h*0.85),
					fill=zynthian_gui_config.color_status_midi,
					state=mcstate)
			else:
				self.status_canvas.itemconfig(self.status_midi_clock, state=mcstate)


	def refresh_loading(self):
		pass


	def zyncoder_read(self, zcnums=None):
		pass


	def cb_keybinding(self, event):
		logging.debug("Key press {} {}".format(event.keycode, event.keysym))

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


	def cb_select_path(self, *args):
		self.select_path_width=self.select_path_font.measure(self.select_path.get())
		self.select_path_offset = 0
		self.select_path_dir = 2
		self.label_select_path.place(x=0, y=0)


	def cb_scroll_select_path(self):
		if self.shown:
			if self.dscroll_select_path():
				zynthian_gui_config.top.after(1000, self.cb_scroll_select_path)
				return

		zynthian_gui_config.top.after(100, self.cb_scroll_select_path)


	def dscroll_select_path(self):
		if self.select_path_width>self.title_canvas_width:
			#Scroll label
			self.select_path_offset += self.select_path_dir
			self.label_select_path.place(x=-self.select_path_offset, y=0)

			#Change direction ...
			if self.select_path_offset > (self.select_path_width-self.title_canvas_width):
				self.select_path_dir = -2
				return True
			elif self.select_path_offset<=0:
				self.select_path_dir = 2
				return True

		elif self.select_path_offset!=0:
			self.select_path_offset = 0
			self.select_path_dir = 2
			self.label_select_path.place(x=0, y=0)

		return False


	def set_select_path(self):
		pass


#------------------------------------------------------------------------------
