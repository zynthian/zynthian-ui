#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Base Class: Status Bar + Basic layout & events
#
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
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

import time
import logging
import tkinter
from threading import Timer
from tkinter import font as tkFont

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngine import zynthian_controller
from zyngui.zynthian_gui_keybinding import zynthian_gui_keybinding

#------------------------------------------------------------------------------
# Zynthian Base GUI Class: Status Bar + Basic layout & events
#------------------------------------------------------------------------------

class zynthian_gui_base(tkinter.Frame):

	METER_NONE	= 0
	METER_DPM	= 1
	METER_CPU	= 2

	#Default buttonbar config (touchwidget)
	buttonbar_config = []

	def __init__(self):
		tkinter.Frame.__init__(self,
			zynthian_gui_config.top,
			width=zynthian_gui_config.display_width,
			height=zynthian_gui_config.display_height)
		self.grid_propagate(False)
		self.rowconfigure(1, weight=1)
		self.columnconfigure(0, weight=1)
		self.shown = False
		self.zyngui = zynthian_gui_config.zyngui

		self.buttonbar_button = []

		# Geometry vars
		self.buttonbar_height = zynthian_gui_config.display_height // 7
		self.width = zynthian_gui_config.display_width
		#TODO: Views should use current height if they need dynamic changes else grow rows to fill main_frame
		if zynthian_gui_config.enable_onscreen_buttons and self.buttonbar_config:
			self.height = zynthian_gui_config.display_height - zynthian_gui_config.topbar_height - self.buttonbar_height
		else:
			self.height = zynthian_gui_config.display_height - zynthian_gui_config.topbar_height


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
		self.title_canvas_width = zynthian_gui_config.display_width - self.status_l - self.status_lpad - 2
		self.select_path_font=tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=zynthian_gui_config.font_topbar[1])
		self.select_path_width = 0
		self.select_path_offset = 0
		self.select_path_dir = 2

		# Topbar's frame
		self.tb_frame = tkinter.Frame(self,
			width=zynthian_gui_config.display_width,
			height=zynthian_gui_config.topbar_height,
			bg=zynthian_gui_config.color_bg)
		self.tb_frame.grid_propagate(False)
		self.tb_frame.grid(row=0)
		self.tb_frame.grid_columnconfigure(0, weight=1)

		# Setup Topbar's Callback
		self.tb_frame.bind("<Button-1>", self.cb_topbar)
		self.tb_frame.bind("<ButtonRelease-1>", self.cb_topbar_release)
		self.topbar_timer = None

		# Title
		self.title = ""
#		font=tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=int(self.height * 0.05)),
		font=zynthian_gui_config.font_topbar
		self.title_fg = zynthian_gui_config.color_panel_tx
		self.title_bg = zynthian_gui_config.color_header_bg
		self.title_canvas = tkinter.Canvas(self.tb_frame,
			height=zynthian_gui_config.topbar_height,
			bd=0,
			highlightthickness=0,
			bg = self.title_bg)
		self.title_canvas.grid(row=0, column=0, sticky='ew')
		self.title_canvas.grid_propagate(False)
		self.path_canvas = self.title_canvas
		self.title_timer = None

		# Topbar's Select Path
		self.title_y = zynthian_gui_config.title_y
		self.select_path = tkinter.StringVar()
		self.select_path.trace(tkinter.W, self.cb_select_path)
		self.label_select_path = tkinter.Label(self.title_canvas,
			font=zynthian_gui_config.font_topbar,
			textvariable=self.select_path,
			justify=tkinter.LEFT,
			bg=zynthian_gui_config.color_header_bg,
			fg=zynthian_gui_config.color_header_tx)
		self.label_select_path.place(x=0, y=self.title_y)
		# Setup Topbar's Callback
		self.label_select_path.bind('<Button-1>', self.cb_topbar)
		self.label_select_path.bind('<ButtonRelease-1>', self.cb_topbar_release)
		self.title_canvas.bind('<Button-1>', self.cb_topbar)
		self.title_canvas.bind('<ButtonRelease-1>', self.cb_topbar_release)

		# Canvas for displaying status: CPU, ...
		self.status_canvas = tkinter.Canvas(self.tb_frame,
			width=self.status_l+2,
			height=self.status_h,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg = zynthian_gui_config.color_bg)
		self.status_canvas.grid(row=0, column=1, sticky="ens", padx=(self.status_lpad,0))

		# Topbar parameter editor
		self.param_editor_zctrl = None

		# Main Frame
		self.main_frame = tkinter.Frame(self,
			bg=zynthian_gui_config.color_bg)
		self.main_frame.propagate(False)
		self.main_frame.grid(row=1, sticky='news')

		# Init touchbar
		self.buttonbar_frame = None
		self.init_buttonbar()

		self.button_push_ts = 0

		if zynthian_gui_config.show_cpu_status:
			self.meter_mode = self.METER_CPU
		else:
			self.meter_mode = self.METER_DPM

		# Update Title
		self.set_select_path()
		self.cb_scroll_select_path()

		self.disable_param_editor() #TODO: Consolidate set_title and set_select_path, etc.


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


	def init_buttonbar(self, config=None):
		if self.buttonbar_frame:
			self.buttonbar_frame.grid_forget()
		if config is None:
			config = self.buttonbar_config    			
		if not zynthian_gui_config.enable_onscreen_buttons or not config:
			return

		self.buttonbar_frame = tkinter.Frame(self,
			width=zynthian_gui_config.display_width,
			height=self.buttonbar_height,
			bg=zynthian_gui_config.color_bg)
		self.buttonbar_frame.grid(row=2, padx=(0,0), pady=(2,0))
		self.buttonbar_frame.grid_propagate(False)
		self.buttonbar_frame.grid_rowconfigure(0, minsize=self.buttonbar_height, pad=0)
		for i in range(4):
			self.buttonbar_frame.grid_columnconfigure(
				i,
				weight=1,
				uniform='buttonbar',
				pad=0)
			try:
				self.add_button(i, config[i][0], config[i][1])
			except:
				pass


	def set_buttonbar_label(self, column, label):
		if len(self.buttonbar_button) > column and self.buttonbar_button[column]:
			self.buttonbar_button[column]['text'] = label


	def add_button(self, column, cuia, label):
		# Touchbar frame
		for new_column in range(len(self.buttonbar_button), column + 1):
				self.buttonbar_button.append(None)
    		
		self.buttonbar_button[column] = select_button = tkinter.Button(
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
		if column == 0:
			padx = (0,0)
		else:
			padx = (2,0)
		select_button.grid(row=0, column=column, sticky='nswe', padx=padx)
		select_button.bind('<ButtonPress-1>', lambda e: self.button_down(e))
		select_button.bind('<ButtonRelease-1>', lambda e: self.button_up(cuia, e))


	def button_down(self, event):
		self.button_push_ts=time.monotonic()


	def button_up(self, cuia, event):
		if isinstance(cuia, int):
			t = 'S'
			if self.button_push_ts:
				dts=(time.monotonic()-self.button_push_ts)
				if dts<0.3:
					t = 'S'
				elif dts>=0.3 and dts<2:
					t = 'B'
				elif dts>=2:
					t = 'L'
			self.zyngui.zynswitch_defered(t, cuia)
		else:
			self.zyngui.callable_ui_action(cuia)


	# Default topbar touch callback
	def cb_topbar(self, params=None):
		self.topbar_timer = Timer(0.4, self.cb_topbar_bold)
		self.topbar_timer.start()


	# Default topbar release callback
	def cb_topbar_release(self, params=None):
		if self.topbar_timer:
			self.topbar_timer.cancel()
			self.topbar_timer = None
			self.topbar_touch_action()


	# Default topbar short touch action
	def topbar_touch_action(self):
		self.zyngui.zynswitch_defered('S', 1)


	# Default topbar bold touch action
	def topbar_bold_touch_action(self):
		self.zyngui.zynswitch_defered('B', 0)


	# Default topbar bold press callback
	def cb_topbar_bold(self, params=None):
		if self.topbar_timer:
			self.topbar_timer.cancel()
			self.topbar_timer = None
			self.topbar_bold_touch_action()


	def show(self):
		if not self.shown:
			if self.zyngui.test_mode:
				logging.warning("TEST_MODE: {}".format(self.__class__.__module__))
			self.shown = True
			self.grid(row=0, column=0, sticky='nsew')
			self.propagate(False)
		self.main_frame.focus()


	def hide(self):
		if self.shown:
			self.shown=False
			self.grid_remove()


	def refresh_status(self, status={}):
		if self.shown:
			if self.meter_mode == self.METER_CPU:
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
			elif self.meter_mode == self.METER_DPM:
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
						self.status_canvas.coords(self.status_peak_lA,(0, 0, llA, self.status_rh-2))
						self.status_canvas.itemconfig(self.status_peak_lA, state='normal')
					else:
						self.status_peak_lA=self.status_canvas.create_rectangle((0, 0, 0, 0), fill="#00C000", width=0, state='hidden')

					if self.status_peak_mA:
						if lmA >= self.dpm_scale_lm:
							self.status_canvas.coords(self.status_peak_mA,(self.dpm_scale_lm, 0, lmA, self.status_rh-2))
							self.status_canvas.itemconfig(self.status_peak_mA, state="normal")
						else:
							self.status_canvas.itemconfig(self.status_peak_mA, state="hidden")
					else:
						self.status_peak_mA=self.status_canvas.create_rectangle((0, 0, 0, 0), fill="#C0C000", width=0, state='hidden')

					if self.status_peak_hA:
						if lhA >= self.dpm_scale_lh:
							self.status_canvas.coords(self.status_peak_hA,(self.dpm_scale_lh, 0, lhA, self.status_rh-2))
							self.status_canvas.itemconfig(self.status_peak_hA, state="normal")
						else:
							self.status_canvas.itemconfig(self.status_peak_hA, state="hidden")
					else:
						self.status_peak_hA=self.status_canvas.create_rectangle((0, 0, 0, 0), fill="#C00000", width=0, state='hidden')

					if self.status_hold_A:
						self.status_canvas.coords(self.status_hold_A,(lholdA, 0, lholdA, self.status_rh-2))
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
						self.status_canvas.coords(self.status_peak_lB,(0, self.status_rh-1, llB, 2 * self.status_rh-3))
						self.status_canvas.itemconfig(self.status_peak_lB, state='normal')
					else:
						self.status_peak_lB=self.status_canvas.create_rectangle((0, 0, 0, 0), fill="#00C000", width=0, state='hidden')

					if self.status_peak_mB:
						if lmB >= self.dpm_scale_lm:
							self.status_canvas.coords(self.status_peak_mB,(self.dpm_scale_lm, self.status_rh-1, lmB, 2 * self.status_rh - 3))
							self.status_canvas.itemconfig(self.status_peak_mB, state="normal")
						else:
							self.status_canvas.itemconfig(self.status_peak_mB, state="hidden")
					else:
						self.status_peak_mB=self.status_canvas.create_rectangle((0, 0, 0, 0), fill="#C0C000", width=0, state='hidden')

					if self.status_peak_hB:
						if lhB >= self.dpm_scale_lh:
							self.status_canvas.coords(self.status_peak_hB,(self.dpm_scale_lh, self.status_rh-1, lhB, 2 * self.status_rh - 3))
							self.status_canvas.itemconfig(self.status_peak_hB, state="normal")
						else:
							self.status_canvas.itemconfig(self.status_peak_hB, state="hidden")
					else:
						self.status_peak_hB=self.status_canvas.create_rectangle((0, 0, 0, 0), fill="#C00000", width=0, state='hidden')

					if self.status_hold_B:
						self.status_canvas.coords(self.status_hold_B,(lholdB, self.status_rh-1, lholdB, 2 * self.status_rh - 3))
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
					font=("forkawesome", self.status_fs),
					text=flags)
			else:
				self.status_canvas.itemconfig(self.status_error, text=flags, fill=color)

			# Display Rec/Play flags
			flags = ""
			color = zynthian_gui_config.color_bg
			if 'audio_recorder' in status:
					flags = "\uf111"
					color = zynthian_gui_config.color_status_record
			if 'audio_player' in status:
				if flags:
					flags = "\uf144"
					color = zynthian_gui_config.color_status_record
				else:
					flags = "\uf04b"
					color = zynthian_gui_config.color_status_play
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
					int(self.status_h*0.7),
					width=int(self.status_fs*1.2),
					justify=tkinter.RIGHT,
					fill=color,
					font=("forkawesome", self.status_fs),
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
					int(self.status_h*0.7),
					width=int(self.status_fs*1.2),
					justify=tkinter.RIGHT,
					fill=zynthian_gui_config.color_status_midi,
					font=("forkawesome", self.status_fs),
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
					int(self.status_h*0.9),
					int(self.status_l-2),
					int(self.status_h*0.9),
					fill=zynthian_gui_config.color_status_midi,
					state=mcstate)
			else:
				self.status_canvas.itemconfig(self.status_midi_clock, state=mcstate)


	def refresh_loading(self):
		pass

	#--------------------------------------------------------------------------
	# Zynpot Callbacks (rotaries!) & CUIA
	#--------------------------------------------------------------------------

	def zynpot_cb(self, i, dval):
		if self.param_editor_zctrl:
			if i == zynthian_gui_config.ENC_SELECT:
				self.param_editor_zctrl.nudge(dval)
			elif i == zynthian_gui_config.ENC_SNAPSHOT:
				self.param_editor_zctrl.nudge(dval * 10)
			else:
				return True
			if self.param_editor_zctrl.labels:
				self.select_path.set("{}: {}".format(self.param_editor_zctrl.name, self.param_editor_zctrl.get_value2label()))
			else:
				self.select_path.set(self.format_print.format(self.param_editor_zctrl.name, self.param_editor_zctrl.value))
			return True


	# Function to handle switch press
	#   switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#   type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#   returns True if action fully handled or False if parent action should be triggered
	def switch(self, switch, type):
		if self.param_editor_zctrl:
			if switch == zynthian_gui_config.ENC_SELECT:
				if type == 'S':
					if self.param_editor_assert_cb:
						self.param_editor_assert_cb(self.param_editor_zctrl.value)
					self.disable_param_editor()
				elif type == 'B':
					self.param_editor_zctrl.set_value(self.param_editor_zctrl.value_default)
				self.zynpot_cb(zynthian_gui_config.ENC_SELECT, 0)
				return True
			
			elif switch == zynthian_gui_config.ENC_BACK:
				self.disable_param_editor()
				if type == 'S':
					return True


	#--------------------------------------------------------------------------
	# Keyboard & Mouse/Touch Callbacks
	#--------------------------------------------------------------------------

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
		self.label_select_path.place(x=0, y=self.title_y)


	def cb_scroll_select_path(self):
		if self.shown:
			if self.dscroll_select_path():
				zynthian_gui_config.top.after(1000, self.cb_scroll_select_path)
				return

		zynthian_gui_config.top.after(100, self.cb_scroll_select_path)


	def dscroll_select_path(self):
		if self.select_path_width > self.title_canvas_width:
			#Scroll label
			self.select_path_offset += self.select_path_dir
			self.label_select_path.place(x=-self.select_path_offset, y=self.title_y)

			#Change direction ...
			if self.select_path_offset > (self.select_path_width - self.title_canvas_width):
				self.select_path_dir = -2
				return True
			elif self.select_path_offset<=0:
				self.select_path_dir = 2
				return True

		elif self.select_path_offset != 0:
			self.select_path_offset = 0
			self.select_path_dir = 2
			self.label_select_path.place(x=0, y=self.title_y)

		return False


	def set_select_path(self):
		pass


	# Function to update display, e.g. after geometry changes
	# Override if required
	def update_layout(self):
		if zynthian_gui_config.enable_onscreen_buttons and self.buttonbar_config:
			self.height = zynthian_gui_config.display_height - zynthian_gui_config.topbar_height - self.buttonbar_height
		else:
			self.height = zynthian_gui_config.display_height - zynthian_gui_config.topbar_height


	# Function to enable the top-bar parameter editor
	#	engine: Object to recieve send_controller_value callback
	#	symbol: String identifying the parameter
	#	name: Parameter human-friendly name
	#	options: zctrl options dictionary
	#	assert_cb: Optional function to call when editor closed with assert: fn(self,value)
	#	Populates button bar with up/down buttons
	def enable_param_editor(self, engine, symbol, name, options, assert_cb=None):
		self.disable_param_editor()
		self.param_editor_zctrl = zynthian_controller(engine, symbol, name, options)
		self.param_editor_assert_cb = assert_cb
		if not self.param_editor_zctrl.is_integer:
			if self.param_editor_zctrl.nudge_factor < 0.1:
				self.format_print = "{}: {:.2f}"
			else:
				self.format_print = "{}: {:.1f}"
		else:
			self.format_print = "{}: {}"

		self.label_select_path.config(bg=zynthian_gui_config.color_panel_tx, fg=zynthian_gui_config.color_header_bg)
		self.init_buttonbar([("SELECT_DOWN", "-1"),("SELECT_UP", "+1"),("SNAPSHOT_DOWN", "-10"),("SNAPSHOT_UP", "+10"),])
		self.zynpot_cb(zynthian_gui_config.ENC_SELECT, 0)
		self.update_layout()
	

	# Function to disable paramter editor
	def disable_param_editor(self):
		if not self.param_editor_zctrl:
			return
		del self.param_editor_zctrl
		self.param_editor_zctrl = None
		self.param_editor_assert_cb = None
		self.init_buttonbar()
		self.set_title(self.title)
		try:
			self.update_layout()
		except:
			pass

#------------------------------------------------------------------------------
