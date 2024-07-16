#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Control Test Class
# 
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
#
# ******************************************************************************
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
# ******************************************************************************

import logging
import tkinter
from time import sleep

# Zynthian specific modules
from zyngine import zynthian_controller
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_base import zynthian_gui_base
from zyngui.zynthian_gui_controller import zynthian_gui_controller

# ------------------------------------------------------------------------------
# Zynthian Controller Test GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_control_test(zynthian_gui_base):

	REQUIRED_NUM_PUSHES = 3

	def __init__(self):
		super().__init__()

		if zynthian_gui_config.layout['columns'] == 3:
			padx = (2, 2)
		else:
			padx = (0, 2)
		pady = (0, 0)

		# Test Canvas
		self.canvas_width = 0
		self.test_canvas = tkinter.Canvas(self.main_frame,
			highlightthickness=0,
			relief='flat',
			bg=zynthian_gui_config.color_bg)
		self.test_canvas.grid(sticky='news')

		# Create GUI elements (position and size set when canvas is grid and size applied)
		self.text_info = self.test_canvas.create_text(
			0,
			0,
			#anchor=tkinter.NW,
			justify=tkinter.CENTER,
			width=0,
			text="",
			font=(zynthian_gui_config.font_family, 8),
			fill=zynthian_gui_config.color_panel_tx)
		self.text_error = self.test_canvas.create_text(
			0,
			0,
			#anchor=tkinter.NW,
			justify=tkinter.CENTER,
			width=0,
			text="",
			font=(zynthian_gui_config.font_family, 8),
			fill=zynthian_gui_config.color_error)

		# Configure layout
		for ctrl_pos in zynthian_gui_config.layout['ctrl_pos']:
			self.main_frame.columnconfigure(ctrl_pos[1], weight=1, uniform='ctrl_col')
			self.main_frame.rowconfigure(ctrl_pos[0], weight=1, uniform='ctrl_row')
		self.main_frame.columnconfigure(zynthian_gui_config.layout['list_pos'][1], weight=3)
		self.main_frame.columnconfigure(zynthian_gui_config.layout['list_pos'][1] + 1, weight=1)
		self.test_canvas.grid(row=zynthian_gui_config.layout['list_pos'][0], column=zynthian_gui_config.layout['list_pos'][1], rowspan=4, padx=padx, pady=pady, sticky="news")

		# Setup Controllers & Buttons
		self.setup_gui_controllers()
		self.setup_button_test()

	def on_size(self, event):
		if event.width == self.width and event.height == self.height:
			return
		super().on_size(event)
		text_fs = round(self.canvas_width / 22)
		self.test_canvas.coords(self.text_info, self.canvas_width // 2, self.height // 2 - text_fs * 1)
		self.test_canvas.itemconfigure(self.text_info, width=self.canvas_width, font=(zynthian_gui_config.font_family, text_fs))
		self.test_canvas.coords(self.text_error, self.canvas_width // 2, self.height // 2 + text_fs * 2)
		self.test_canvas.itemconfigure(self.text_error, width=self.canvas_width, font=(zynthian_gui_config.font_family, text_fs))

	def update_layout(self):
		super().update_layout()
		if zynthian_gui_config.layout['columns'] == 2:
			self.canvas_width = int(self.width * 0.75)
			w = 3
		else:
			self.canvas_width = int(self.width * 0.50)
			w = 2
		self.test_canvas.configure(width=self.canvas_width, height=self.height)
		self.main_frame.columnconfigure(zynthian_gui_config.layout['list_pos'][1], minsize=self.canvas_width, weight=w)
		self.main_frame.columnconfigure(zynthian_gui_config.layout['list_pos'][1] + 1, minsize=int(self.width * 0.25 * self.sidebar_shown), weight=self.sidebar_shown)
		for pos in zynthian_gui_config.layout['ctrl_pos']:
			self.main_frame.columnconfigure(pos[1], minsize=int((self.width * 0.25 - 1) * self.sidebar_shown), weight=self.sidebar_shown)

	def show_sidebar(self, show):
		self.sidebar_shown = show
		for zctrl in self.zgui_controllers:
			if self.sidebar_shown:
				zctrl.grid()
			else:
				zctrl.grid_remove()
		self.update_layout()

	def show(self):
		self.reset_button_test()
		super().show()

	def setup_gui_controllers(self):
		self.zcontrollers = []
		self.zgui_controllers = []
		for i in range(4):
			ctrl_name = "CTRL#{}".format(i)
			self.zcontrollers.append(zynthian_controller(None, ctrl_name, {'value_min':-100, 'value_max':100, 'value':0 }))
			self.zgui_controllers.append(zynthian_gui_controller(i, self.main_frame, self.zcontrollers[i]))
			pos = zynthian_gui_config.layout['ctrl_pos'][i]
			self.zgui_controllers[i].grid(row=pos[0], column=pos[1], pady=(0, 1), sticky='news')
		self.update_layout()

	def setup_button_test(self):
		if zynthian_gui_config.wiring_layout.startswith("Z2"):
			self.zynswitch_info = [
				["MENU", 4, 0],
				["-1-", 5, 1],
				["-2-", 6, 2],
				["-3-", 7, 3],
				["-4-", 8, 4],
				["-5-", 9, 5],
				["-*-", 10, 6],
				["MODE", 11, 7],
				["F1", 12, 8],
				["F2", 13, 9],
				["F3", 14, 10],
				["F4", 15, 11],
				["F5", 16, 12],
				["ALT", 17, 13],
				["REC", 18, 14],
				["PLAY", 19, 15],
				["METRONOME", 20, 16],
				["STOP", 21, 17],
				["BACK", 22, 18],
				["UP", 23, 19],
				["SELECT", 24, 20],
				["LEFT", 25, 21],
				["DOWN", 26, 22],
				["RIGHT", 27, 23],
				["MASTER", 28, 24],
				["KNOB#1 TOUCH", 31, None],
				["KNOB#2 TOUCH", 30, None],
				["KNOB#3 TOUCH", 32, None],
				["SELECTOR TOUCH", 33, None],
				["SELECTOR PUSH", 29, None]
			]
		elif zynthian_gui_config.wiring_layout.startswith("V5"):
			self.zynswitch_info = [
				["OPT", 4, 0],
				["MIX", 5, 1],
				["CTRL", 6, 2],
				["ZS3", 7, 3],
				["ALT", 8, 7],
				["METRONOME", 9, 6],
				["PAD", 10, 5],
				["F1", 11, 4],
				["REC", 12, 8],
				["STOP", 13, 9],
				["PLAY", 14, 10],
				["F2", 15, 11],
				["BACK", 16, 15],
				["UP", 17, 14],
				["SELECT", 18, 13],
				["F3", 19, 12],
				["LEFT", 20, 16],
				["DOWN", 21, 17],
				["RIGHT", 22, 18],
				["F4", 23, 19],
				#["KNOB#1 PUSH", 24, None],
				#["KNOB#2 PUSH", 25, None],
				#["KNOB#3 PUSH", 26, None],
				#["KNOB#4 PUSH", 27, None]
			]
		else:
			self.zynswitch_info = [
				["KNOB#1", 0],
				["KNOB#2", 1],
				["KNOB#3", 2],
				["KNOB#4", 3],
				["S1", 4],
				["S2", 5],
				["S3", 6],
				["S4", 7]
			]

	def update_button_test(self):
		if self.test_button_index >= len(self.zynswitch_info):
			self.test_button_name = f"BUTTON TEST OK!"
			if self.test_color_name:
				self.test_button_name += f"\n\nPush to test LED color {self.test_color_name}..."
			else:
				self.test_button_name += "\n\nPush to exit test tool..."
		else:
			self.test_button_name = f"{self.zynswitch_info[self.test_button_index][0]}\n{self.test_button_counter} / {self.REQUIRED_NUM_PUSHES}"
		self.test_canvas.itemconfigure(self.text_info, text=self.test_button_name)
		self.test_canvas.itemconfigure(self.text_error, text="")

	def reset_button_test(self):
		self.test_button_index = 0
		self.test_button_counter = 0
		self.wsleds_color_base = self.zyngui.wsleds.wscolor_off
		self.test_color_name = "RED"
		self.update_button_test()

	# Function to handle *all* switch presses.
	#  swi: Switch index
	#  t: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#  returns True if action fully handled or False if parent action should be triggered
	def switch(self, swi, t='S'):
		if t == 'P':
			# Test push buttons & switches
			if self.test_button_index < len(self.zynswitch_info):
				if swi == self.zynswitch_info[self.test_button_index][1]:
					self.test_button_counter += 1
					if self.test_button_counter >= self.REQUIRED_NUM_PUSHES:
						self.test_button_index += 1
						self.test_button_counter = 0
					self.update_button_test()
				else:
					self.test_canvas.itemconfigure(self.text_error, text="WRONG BUTTON: {}".format(swi))
			# Test LED's colors
			else:
				if self.wsleds_color_base == self.zyngui.wsleds.wscolor_off:
					self.wsleds_color_base = self.zyngui.wsleds.wscolor_red
					self.test_color_name = "GREEN"
					self.update_button_test()
				elif self.wsleds_color_base == self.zyngui.wsleds.wscolor_red:
					self.wsleds_color_base = self.zyngui.wsleds.wscolor_green
					self.test_color_name = "BLUE"
					self.update_button_test()
				elif self.wsleds_color_base == self.zyngui.wsleds.wscolor_green:
					self.wsleds_color_base = self.zyngui.wsleds.wscolor_blue
					self.test_color_name = None
					self.update_button_test()
				else:
					#self.zyngui.close_screen()
					self.zyngui.exit(101)
					#self.zyngui.exit(0)
		return True

	def zynpot_cb(self, i, dval):
		self.zgui_controllers[i].zynpot_cb(dval)

	def plot_zctrls(self, force=False):
		for zgui_ctrl in self.zgui_controllers:
			if zgui_ctrl.zctrl and zgui_ctrl.zctrl.is_dirty or force:
				zgui_ctrl.calculate_plot_values()
			zgui_ctrl.plot_value()

	def update_wsleds(self, leds=None):
		# Switch off all LEDS
		for i in range(0, self.zyngui.wsleds.get_num()):
			self.zyngui.wsleds.set_led(i, self.wsleds_color_base)
		# Light test button LED
		if 0 <= self.test_button_index < len(self.zynswitch_info):
			led_num = self.zynswitch_info[self.test_button_index][2]
			if led_num is not None and led_num < self.zyngui.wsleds.get_num():
				self.zyngui.wsleds.set_led(led_num, self.zyngui.wsleds.wscolor_white)

	def test_wsleds_colors(self):
		tdelay = 2
		# Light all LEDS to RED
		self.wsleds_color_base = self.zyngui.wsleds.wscolor_red
		sleep(tdelay)
		# Light all LEDS to GREEN
		self.wsleds_color_base = self.zyngui.wsleds.wscolor_green
		sleep(tdelay)
		# Light all LEDS to BLUE
		self.wsleds_color_base = self.zyngui.wsleds.wscolor_blue
		sleep(tdelay)

	def set_select_path(self):
		self.select_path.set("Control Test")

# ------------------------------------------------------------------------------
