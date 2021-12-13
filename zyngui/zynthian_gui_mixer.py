#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Audio Mixer
#
# Copyright (C) 2015-2020 Fernando Moyano <jofemodo@zynthian.org>
# Copyright (C) 2015-2021 Brian Walton <brian@riban.co.uk>
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
import logging
import tkinter
from time import monotonic
from tkinter import font as tkFont
from PIL import Image, ImageTk
import liblo
import os

# Zynthian specific modules
from zyngine import zynthian_controller
from . import zynthian_gui_base
from . import zynthian_gui_config
from . import zynthian_gui_controller
from zynlibs.zynmixer import *
from zyncoder.zyncore import lib_zyncore

ENC_LAYER		= 0
ENC_BACK		= 1
ENC_SNAPSHOT	= 2
ENC_SELECT		= 3

MAX_NUM_CHANNELS = 16

#------------------------------------------------------------------------------
# Zynthian Mixer Channel Class
#------------------------------------------------------------------------------

class zynthian_gui_mixer_channel():
	# Initialise mixer channel object
	#	canvas: Canvas on which to draw fader
	#	x: Horizontal coordinate of left of fader
	#	y: Vertical coordinate of top of fader
	#	width: Width of fader
	#	height: Height of fader
	#	channel: Index of channel (used for labels)
	#	on_select_cb: Function to call when fader is selected (must accept channel as parameter)
	#	on_edit_cb: Function to call when channel edit is requested

	mute_color = zynthian_gui_config.color_on
	solo_color = "dark green"

	def __init__(self, canvas, x, y, width, height, channel, on_select_cb, on_edit_cb):
		#logging.warning("zynthian_gui_mixer_channel (%d,%d %dx%d) channel %s", x,y,width,height, channel)
		self.main_canvas = canvas
		self.x = x
		self.y = y
		self.width = width
		self.height = height
		self.hidden = False
		self.channel = channel # Channel 0..16, 17=MAIN, None = hidden
		self.redraw_controls_flag = False

		if channel and channel <= MAX_NUM_CHANNELS:
			self.channel = channel
		else:
			self.channel = None
			self.hidden = True

		self.on_select_cb = on_select_cb
		self.on_edit_cb = on_edit_cb

		self.button_height = int(self.height * 0.1)
		self.legend_height = int(self.height * 0.08)
		self.balance_height = int(self.height * 0.03)
		self.fader_height = self.height - self.balance_height - self.legend_height - 2 * self.button_height
		self.fader_bottom = self.height - self.legend_height - self.balance_height
		self.fader_top = self.fader_bottom - self.fader_height
		fader_centre = x + width * 0.5
		self.balance_top = self.fader_bottom
		self.balance_control_centre = int(self.width / 2)
		self.balance_control_width = int(self.width / 4) # Width of each half of balance control

		#Digital Peak Meter (DPM) parameters
		self.dpm_rangedB = 50 # Lowest meter reading in -dBFS
		self.dpm_highdB = 10 # Start of yellow zone in -dBFS
		self.dpm_overdB = 3  # Start of red zone in -dBFS
		self.dpm_high = 1 - self.dpm_highdB / self.dpm_rangedB
		self.dpm_over = 1 - self.dpm_overdB / self.dpm_rangedB
		self.dpm_scale_lm = int(self.dpm_high * self.fader_height)
		self.dpm_scale_lh = int(self.dpm_over * self.fader_height)

		self.dpm_width = int(self.width / 10)
		self.dpm_a_x = x + self.width - self.dpm_width * 2 - 2
		self.dpm_a_y = self.fader_bottom
		self.dpm_b_x = x + self.width - self.dpm_width - 1
		self.dpm_b_y = self.fader_bottom
		self.dpm_zero_y = self.fader_bottom - self.fader_height * self.dpm_high
		self.fader_width = self.width - self.dpm_width * 2 - 2

		self.drag_start = None

		# Default style
		self.fader_bg_color = zynthian_gui_config.color_bg
		#self.fader_color = zynthian_gui_config.color_panel_hl
		#self.fader_color_hl = zynthian_gui_config.color_low_on
		self.fader_color = zynthian_gui_config.color_off
		self.fader_color_hl = zynthian_gui_config.color_on
		self.legend_txt_color = zynthian_gui_config.color_tx
		self.button_bgcol = zynthian_gui_config.color_panel_bg
		self.button_txcol = zynthian_gui_config.color_tx
		self.left_color = "red"
		self.right_color = "dark green"
		self.low_color = "dark green"
		self.medium_color = "#AAAA00" # yellow
		self.high_color = "dark red"

		#font_size = int(0.5 * self.legend_height)
		font_size = int(0.25 * self.width)
		font = (zynthian_gui_config.font_family, font_size)
		font_fader = (zynthian_gui_config.font_family, font_size-1)

		'''
		Create GUI elements
		Tags:
			strip:X All elements within the fader strip used to show/hide strip
			fader:X Elements used for fader drag
			X is the id of this fader's background
		'''

		# Fader
		self.fader_bg = self.main_canvas.create_rectangle(x, self.fader_top, x + self.width, self.fader_bottom, fill=self.fader_bg_color, width=0)
		self.main_canvas.itemconfig(self.fader_bg, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg)))
		self.fader = self.main_canvas.create_rectangle(x, self.fader_top, x + self.width, self.fader_bottom, fill=self.fader_color, width=0, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg)))
		self.legend = self.main_canvas.create_text(x, self.fader_bottom - 2, fill=self.legend_txt_color, text="", tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg)), angle=90, anchor="nw", font=font_fader)

		# DPM
		self.dpm_h_a = self.main_canvas.create_rectangle(x + self.width - 8, self.fader_bottom, x + self.width - 5, self.fader_bottom, width=0, fill=self.high_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg)))
		self.dpm_m_a = self.main_canvas.create_rectangle(x + self.width - 8, self.fader_bottom, x + self.width - 5, self.fader_bottom, width=0, fill=self.medium_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg)))
		self.dpm_l_a = self.main_canvas.create_rectangle(x + self.width - 8, self.fader_bottom, x + self.width - 5, self.fader_bottom, width=0, fill=self.low_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg)))
		self.dpm_h_b = self.main_canvas.create_rectangle(x + self.width - 4, self.fader_bottom, x + self.width - 1, self.fader_bottom, width=0, fill=self.high_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg)))
		self.dpm_m_b = self.main_canvas.create_rectangle(x + self.width - 4, self.fader_bottom, x + self.width - 1, self.fader_bottom, width=0, fill=self.medium_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg)))
		self.dpm_l_b = self.main_canvas.create_rectangle(x + self.width - 4, self.fader_bottom, x + self.width - 1, self.fader_bottom, width=0, fill=self.low_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg)))
		self.dpm_hold_a = self.main_canvas.create_rectangle(self.dpm_a_x, self.fader_bottom, self.dpm_a_x + self.dpm_width, self.fader_bottom, width=0, fill=self.low_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg)), state="hidden")
		self.dpm_hold_b = self.main_canvas.create_rectangle(self.dpm_b_x, self.fader_bottom, self.dpm_b_x + self.dpm_width, self.fader_bottom, width=0, fill=self.low_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg)), state="hidden")

		# 0dB line
		self.main_canvas.create_line(self.dpm_a_x, self.dpm_zero_y, x + self.width, self.dpm_zero_y, fill=self.medium_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg)))

		# Solo button
		self.solo = self.main_canvas.create_rectangle(x, 0, x + self.width, self.button_height, fill=self.button_bgcol, width=0, tags=("solo_button:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg)))
		self.main_canvas.create_text(x + self.width / 2, self.button_height * 0.5, text="solo", fill=self.button_txcol, tags=("solo_button:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg)), font=font)

		# Mute button
		self.mute = self.main_canvas.create_rectangle(x, self.button_height, x + self.width, self.button_height * 2, fill=self.button_bgcol, width=0, tags=("mute_button:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg)))
		self.main_canvas.create_text(x + self.width / 2, self.button_height * 1.5, text="mute", fill=self.button_txcol, tags=("mute_button:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg)), font=font)

		# Legend strip at bottom of screen
		self.legend_strip_bg = self.main_canvas.create_rectangle(x, self.height - self.legend_height, x + self.width, self.height, width=0, tags=("strip:%s"%(self.fader_bg),"legend_strip:%s"%(self.fader_bg)))
		self.legend_strip_txt = self.main_canvas.create_text(int(fader_centre), self.height - self.legend_height / 2, fill=self.legend_txt_color, text="-", tags=("strip:%s"%(self.fader_bg),"legend_strip:%s"%(self.fader_bg)), font=font)

		# Balance indicator
		self.balance_left = self.main_canvas.create_rectangle(x, self.fader_top, int(fader_centre - 0.5), self.fader_top + self.balance_height, fill=self.left_color, width=0, tags=("strip:%s"%(self.fader_bg), "balance:%s"%(self.fader_bg)))
		self.balance_right = self.main_canvas.create_rectangle(int(fader_centre + 0.5), self.fader_top, self.width, self.fader_top + self.balance_height , fill=self.right_color, width=0, tags=("strip:%s"%(self.fader_bg), "balance:%s"%(self.fader_bg)))

		self.main_canvas.tag_bind("fader:%s"%(self.fader_bg), "<ButtonPress-1>", self.on_fader_press)
		self.main_canvas.tag_bind("fader:%s"%(self.fader_bg), "<B1-Motion>", self.on_fader_motion)
		if os.environ.get("ZYNTHIAN_UI_ENABLE_CURSOR") == "1":
			self.main_canvas.tag_bind("fader:%s"%(self.fader_bg), "<Button-5>", self.on_fader_wheel_down)
			self.main_canvas.tag_bind("fader:%s"%(self.fader_bg), "<Button-4>", self.on_fader_wheel_up)
			self.main_canvas.tag_bind("legend_strip:%s"%(self.fader_bg), "<Button-4>", self.on_balance_wheel_up)
			self.main_canvas.tag_bind("balance:%s"%(self.fader_bg), "<Button-4>", self.on_balance_wheel_up)
			self.main_canvas.tag_bind("legend_strip:%s"%(self.fader_bg), "<Button-5>", self.on_balance_wheel_down)
			self.main_canvas.tag_bind("balance:%s"%(self.fader_bg), "<Button-5>", self.on_balance_wheel_down)
		self.main_canvas.tag_bind("mute_button:%s"%(self.fader_bg), "<ButtonPress-1>", self.on_strip_press)
		self.main_canvas.tag_bind("mute_button:%s"%(self.fader_bg), "<ButtonRelease-1>", self.on_mute_release)
		self.main_canvas.tag_bind("solo_button:%s"%(self.fader_bg), "<ButtonPress-1>", self.on_strip_press)
		self.main_canvas.tag_bind("solo_button:%s"%(self.fader_bg), "<ButtonRelease-1>", self.on_solo_release)
		self.main_canvas.tag_bind("legend_strip:%s"%(self.fader_bg), "<ButtonPress-1>", self.on_strip_press)
		self.main_canvas.tag_bind("legend_strip:%s"%(self.fader_bg), "<ButtonRelease-1>", self.on_strip_release)

		self.draw()


	# Function to hide channel
	def hide(self):
		self.main_canvas.itemconfig("strip:%s"%(self.fader_bg), state="hidden")
		self.hidden = True


	# Function to show channel
	def show(self):
		self.main_canvas.itemconfig("strip:%s"%(self.fader_bg), state="normal")
		self.hidden = False
		self.draw()


	# Function to draw channel strip
	def draw(self):
		if self.hidden or self.channel is None:
			return

		self.main_canvas.itemconfig(self.legend, text="")
		self.main_canvas.coords(self.fader_bg_color, self.x, self.fader_top, self.x + self.width, self.fader_bottom)
		if self.channel == MAX_NUM_CHANNELS:
			self.main_canvas.itemconfig(self.legend_strip_txt, text="Main")
			self.main_canvas.itemconfig(self.legend, text="Main")
		else:
			if zynmixer.is_channel_routed(self.channel):
				self.main_canvas.itemconfig(self.legend_strip_txt, text=self.channel+1)
				for layer in zynthian_gui_config.zyngui.screens["layer"].root_layers:
					if layer.midi_chan == self.channel:
						self.main_canvas.itemconfig(self.legend, text="%s\n%s"%(layer.engine.name, layer.preset_name), state="normal")
						break
			else:
				self.hide()
				return

		self.draw_dpm()
		self.draw_controls()


	# Function to draw the DPM level meter for a channel strip
	def draw_dpm(self):
		if self.hidden or self.channel is None:
			return

		# Set color
		if zynmixer.get_mono(self.channel):
			self.main_canvas.itemconfig(self.dpm_l_a, fill="gray80")
			self.main_canvas.itemconfig(self.dpm_l_b, fill="gray80")
		else:
			self.main_canvas.itemconfig(self.dpm_l_a, fill=self.low_color)
			self.main_canvas.itemconfig(self.dpm_l_b, fill=self.low_color)
		# Get audio peaks from zynmixer
		signal = max(0, 1 + zynmixer.get_dpm(self.channel,0) / self.dpm_rangedB)
		llA = int(min(signal, self.dpm_high) * self.fader_height)
		lmA = int(min(signal, self.dpm_over) * self.fader_height)
		lhA = int(min(signal, 1) * self.fader_height)
		signal = max(0, 1 + zynmixer.get_dpm(self.channel,1) / self.dpm_rangedB)
		llB = int(min(signal, self.dpm_high) * self.fader_height)
		lmB = int(min(signal, self.dpm_over) * self.fader_height)
		lhB = int(min(signal, 1) * self.fader_height)
		signal = max(0, 1 + zynmixer.get_dpm_hold(self.channel,0) / self.dpm_rangedB)
		lholdA = int(min(signal, 1) * self.fader_height)
		signal = max(0, 1 + zynmixer.get_dpm_hold(self.channel,1) / self.dpm_rangedB)
		lholdB = int(min(signal, 1) * self.fader_height)

		# Draw Channel A (left)
		self.main_canvas.coords(self.dpm_l_a,(self.dpm_a_x, self.dpm_a_y, self.dpm_a_x + self.dpm_width, self.dpm_a_y - llA))
		self.main_canvas.itemconfig(self.dpm_l_a, state='normal')

		if lmA >= self.dpm_scale_lm:
			self.main_canvas.coords(self.dpm_m_a,(self.dpm_a_x, self.dpm_a_y - self.dpm_scale_lm, self.dpm_a_x + self.dpm_width, self.dpm_a_y - lmA))
			self.main_canvas.itemconfig(self.dpm_m_a, state="normal")
		else:
			self.main_canvas.itemconfig(self.dpm_m_a, state="hidden")

		if lhA >= self.dpm_scale_lh:
			self.main_canvas.coords(self.dpm_h_a,(self.dpm_a_x, self.dpm_a_y - self.dpm_scale_lh, self.dpm_a_x + self.dpm_width, self.dpm_a_y - lhA))
			self.main_canvas.itemconfig(self.dpm_h_a, state="normal")
		else:
			self.main_canvas.itemconfig(self.dpm_h_a, state="hidden")

		self.main_canvas.coords(self.dpm_hold_a,(self.dpm_a_x, self.dpm_a_y - lholdA, self.dpm_a_x + self.dpm_width, self.dpm_a_y - lholdA - 1))
		if lholdA >= self.dpm_scale_lh:
			self.main_canvas.itemconfig(self.dpm_hold_a, state="normal", fill="#FF0000")
		elif lholdA >= self.dpm_scale_lm:
			self.main_canvas.itemconfig(self.dpm_hold_a, state="normal", fill="#FFFF00")
		elif lholdA > 0:
			self.main_canvas.itemconfig(self.dpm_hold_a, state="normal", fill="#00FF00")
		else:
			self.main_canvas.itemconfig(self.dpm_hold_a, state="hidden")

		# Draw Channel B (right)
		self.main_canvas.coords(self.dpm_l_b,(self.dpm_b_x, self.dpm_b_y, self.dpm_b_x + self.dpm_width, self.dpm_b_y - llB))
		self.main_canvas.itemconfig(self.dpm_l_b, state='normal')

		if lmB >= self.dpm_scale_lm:
			self.main_canvas.coords(self.dpm_m_b,(self.dpm_b_x, self.dpm_b_y - self.dpm_scale_lm, self.dpm_b_x + self.dpm_width, self.dpm_b_y - lmB))
			self.main_canvas.itemconfig(self.dpm_m_b, state="normal")
		else:
			self.main_canvas.itemconfig(self.dpm_m_b, state="hidden")

		if lhB >= self.dpm_scale_lh:
			self.main_canvas.coords(self.dpm_h_b,(self.dpm_b_x, self.dpm_b_y - self.dpm_scale_lh, self.dpm_b_x + self.dpm_width, self.dpm_b_y - lhB))
			self.main_canvas.itemconfig(self.dpm_h_b, state="normal")
		else:
			self.main_canvas.itemconfig(self.dpm_h_b, state="hidden")

		self.main_canvas.coords(self.dpm_hold_b,(self.dpm_b_x, self.dpm_b_y - lholdB, self.dpm_b_x + self.dpm_width, self.dpm_b_y - lholdB - 1))
		if lholdB >= self.dpm_scale_lh:
			self.main_canvas.itemconfig(self.dpm_hold_b, state="normal", fill="#FF0000")
		elif lholdB >= self.dpm_scale_lm:
			self.main_canvas.itemconfig(self.dpm_hold_b, state="normal", fill="#FFFF00")
		elif lholdB > 0:
			self.main_canvas.itemconfig(self.dpm_hold_b, state="normal", fill="#00FF00")
		else:
			self.main_canvas.itemconfig(self.dpm_hold_b, state="hidden")


	# Function to draw the UI controls for a channel strip
	def draw_controls(self):
		if self.hidden or self.channel is None:
			return

		self.main_canvas.coords(self.fader, self.x, self.fader_top + self.fader_height * (1 - zynmixer.get_level(self.channel)), self.x + self.fader_width, self.fader_bottom)

		color = self.button_bgcol
		if zynmixer.get_mute(self.channel):
			color = self.mute_color
		self.main_canvas.itemconfig(self.mute, fill=color)
		color = self.button_bgcol
		if zynmixer.get_solo(self.channel):
			color = self.solo_color
		self.main_canvas.itemconfig(self.solo, fill=color)

		balance = zynmixer.get_balance(self.channel)
		if balance > 0:
			self.main_canvas.coords(self.balance_left,
				self.x + balance * self.width / 2, self.balance_top,
				self.x + self.width / 2, self.balance_top + self.balance_height)
			self.main_canvas.coords(self.balance_right,
				self.x + self.width / 2, self.balance_top,
				self.x + self.width, self.balance_top + self.balance_height)
		else:
			self.main_canvas.coords(self.balance_left,
				self.x, self.balance_top,
				self.x + self.width / 2, self.balance_top + self. balance_height)
			self.main_canvas.coords(self.balance_right,
				self.x + self.width / 2, self.balance_top,
				self.x + self.width * balance / 2 + self.width, self.balance_top + self.balance_height)

		self.redraw_controls_flag = False


	# Function to redraw, if needed, the UI controls for a channel strip
	def redraw_controls(self):
		if self.redraw_controls_flag:
			self.draw_controls()


	# Function to flag redrawing of UI controls for a channel strip
	def set_redraw_controls(self, flag = True):
		self.redraw_controls_flag = flag


	#--------------------------------------------------------------------------
	# Mixer Strip functionality
	#--------------------------------------------------------------------------

	# Function to set fader colors
	# fg: Fader foreground color
	# bg: Fader background color (optional - Default: Do not change background color)
	def set_fader_color(self, fg, bg=None):
		self.main_canvas.itemconfig(self.fader, fill=fg)
		if bg:
			self.main_canvas.itemconfig(self.fader_bg_color, fill=bg)


	# Function to set channel
	#	channel: Index of channel
	def set_channel(self, channel):
		self.channel = channel
		if channel is None:
			self.hide()
		else:
			if channel > MAX_NUM_CHANNELS: channel = MAX_NUM_CHANNELS
			self.show()


	# Function to set volume values
	#	value: Volume value (0..1)
	def set_volume(self, value):
		if self.channel is None:
			return
		if value < 0:
			value = 0
		elif value > 1:
			value = 1
		zynmixer.set_level(self.channel, value)
		self.redraw_controls_flag = True


	# Function to set balance values
	#	value: Balance value (-1..1)
	def set_balance(self, value):
		if self.channel is None:
			return
		if value < -1:
			value = -1
		elif value > 1:
			value = 1
		zynmixer.set_balance(self.channel, value)
		self.redraw_controls_flag = True


	# Function to reset volume
	def reset_volume(self):
		if self.channel is None:
			return
		zynmixer.set_level(self.channel, 0.8)
		self.redraw_controls_flag = True


	# Function to reset balance
	def reset_balance(self):
		if self.channel is None:
			return
		zynmixer.set_balance(self.channel, 0)
		self.redraw_controls_flag = True


	# Function to set mute
	#	value: Mute value (True/False)
	def set_mute(self, value):
		if self.channel is None:
			return
		zynmixer.set_mute(self.channel, value)
		self.redraw_controls_flag = True


	# Function to set solo
	#	value: Solo value (True/False)
	def set_solo(self, value):
		if self.channel is None:
			return
		zynmixer.set_solo(self.channel, value)
		self.redraw_controls_flag = True


	# Function to toggle mono
	#	value: Mono value (True/False)
	def set_mono(self, value):
		if self.channel is None:
			return
		zynmixer.set_mono(self.channel, value)
		self.redraw_controls_flag = True


	# Function to toggle mute
	def toggle_mute(self):
		if self.channel is None:
			return
		zynmixer.toggle_mute(self.channel)
		self.redraw_controls_flag = True


	# Function to toggle solo
	def toggle_solo(self):
		if self.channel is None:
			return
		zynmixer.toggle_solo(self.channel)
		self.redraw_controls_flag = True


	# Function to toggle mono
	def toggle_mono(self):
		if self.channel is None:
			return
		zynmixer.toggle_mono(self.channel)
		self.redraw_controls_flag = True


	#--------------------------------------------------------------------------
	# UI event management
	#--------------------------------------------------------------------------

	# Function to handle fader press
	#	event: Mouse event
	def on_fader_press(self, event):
		self.drag_start = event
		self.on_select_cb(self.channel)


	# Function to handle fader drag
	#	event: Mouse event
	def on_fader_motion(self, event):
		if self.channel is None:
			return
		level = zynmixer.get_level(self.channel) + (self.drag_start.y - event.y) / self.fader_height
		self.drag_start = event
		self.set_volume(level)
		self.redraw_controls()


	# Function to handle mouse wheel down over fader
	#	event: Mouse event
	def on_fader_wheel_down(self, event):
		if self.channel is None:
			return
		self.on_select_cb(self.channel)
		self.set_volume(zynmixer.get_level(self.channel) - 0.02)
		self.redraw_controls()


	# Function to handle mouse wheel up over fader
	#	event: Mouse event
	def on_fader_wheel_up(self, event):
		if self.channel is None:
			return
		self.on_select_cb(self.channel)
		self.set_volume(zynmixer.get_level(self.channel) + 0.02)
		self.redraw_controls()


	# Function to handle mouse wheel down over balance
	#	event: Mouse event
	def on_balance_wheel_down(self, event):
		if self.channel is None:
			return
		self.on_select_cb(self.channel)
		self.set_balance(zynmixer.get_balance(self.channel) - 0.02)
		self.redraw_controls()


	# Function to handle mouse wheel up over balance
	#	event: Mouse event
	def on_balance_wheel_up(self, event):
		if self.channel is None:
			return
		self.on_select_cb(self.channel)
		self.set_balance(zynmixer.get_balance(self.channel) + 0.02)
		self.redraw_controls()


	# Function to handle channel strip press
	#	event: Mouse event
	def on_strip_press(self, event):
		self.press_time = monotonic()
		self.on_select_cb(self.channel)


	# Function to handle mute button release
	#	event: Mouse event
	def on_mute_release(self, event):
		if self.press_time:
			delta = monotonic() - self.press_time
			self.press_time = None
			if delta > 0.4:
				self.on_edit_cb()
				return
		self.toggle_mute()
		self.redraw_controls()


	# Function to handle solo button release
	#	event: Mouse event
	def on_solo_release(self, event):
		if self.press_time:
			delta = monotonic() - self.press_time
			self.press_time = None
			if delta > 0.4:
				self.on_edit_cb()
				return
		self.toggle_solo()
		self.redraw_controls()
		#TODO Main channel "solo" should follow ...


	# Function to handle legend strip release
	def on_strip_release(self, event):
		if self.press_time:
			delta = monotonic() - self.press_time
			self.press_time = None
			if delta > 0.4:
				zynthian_gui_config.zyngui.screens['layer'].select(self.channel)
				zynthian_gui_config.zyngui.screens['layer_options'].reset()
				zynthian_gui_config.zyngui.show_modal('layer_options')
				return
		if self.channel is not None and self.channel != MAX_NUM_CHANNELS:
			layer = zynthian_gui_config.zyngui.screens['layer'].get_root_layer_by_midi_chan(self.channel)
			if layer:
				zynthian_gui_config.zyngui.set_curlayer(layer)
				zynthian_gui_config.zyngui.layer_control(layer)


#------------------------------------------------------------------------------
# Zynthian Mixer GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_mixer(zynthian_gui_base.zynthian_gui_base):

	def __init__(self):
		super().__init__()

		# Zyncoder Management
		self.zyncoder_last_value = [None] * 4

		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.body_height

		self.number_layers = 0 # Quantity of layers (routed channels)
		self.max_channels = MAX_NUM_CHANNELS # Maximum quantiy of faders to display (Defines fader width. Main always displayed.)
		#TODO: Get from config and estimate initial value if not in config
		if self.width <= 400: self.max_channels = 4
		elif self.width <= 600: self.max_channels = 8
		elif self.width <= 800: self.max_channels = 10
		elif self.width <= 1024: self.max_channels = 12
		elif self.width <= 1280: self.max_channels = 14

		self.fader_width = (self.width - 6 ) / (self.max_channels + 1)
		self.legend_height = self.height * 0.05
		self.edit_height = self.height * 0.1

		self.fader_height = self.height - self.edit_height - self.legend_height - 2
		self.fader_bottom = self.height - self.legend_height
		self.fader_top = self.fader_bottom - self.fader_height
		self.balance_control_height = self.fader_height * 0.1
		self.balance_top = self.fader_top
		self.balance_control_width = self.width / 4 # Width of each half of balance control
		self.balance_control_centre = self.fader_width + self.balance_control_width

		# Arrays of GUI elements for channel strips - Channels + Main
		self.channels = [None] * self.max_channels
		self.selected_channel = 0
		self.channel_offset = 0 # Index of first channel displayed on far left
		self.selected_layer = None

		self.press_time = None

		self.edit_channel = None
		self.mode = 1 # 1:Mixer, 0:Edit

		# Fader Canvas
		self.main_canvas = tkinter.Canvas(self.main_frame,
			height=self.height,
			width=self.width,
			bd=0, highlightthickness=0,
			bg = zynthian_gui_config.color_panel_bg)
		self.main_canvas.grid()

		# Channel selection highlight
		color_selhl = zynthian_gui_config.color_on
		self.selection_highlight = self.main_canvas.create_rectangle(0,0,0,0, outline=color_selhl, fill=color_selhl, width=1)

		# Channel strips
		for channel in range(self.max_channels):
			self.channels[channel] = zynthian_gui_mixer_channel(self.main_canvas, 1 + self.fader_width * channel, 0, self.fader_width - 1, self.height, channel, self.select_midi_chan, self.set_edit_mode)

		self.main_channel = zynthian_gui_mixer_channel(self.main_canvas, self.width - self.fader_width - 1, 0, self.fader_width - 1, self.height, MAX_NUM_CHANNELS, self.select_midi_chan, self.set_edit_mode)

		# Edit widgets
		font=(zynthian_gui_config.font_family, int(self.edit_height / 4))
		f=tkFont.Font(family=zynthian_gui_config.font_family, size=int(self.edit_height / 4))
		button_width = f.measure(" BALANCE ") # Width of widest text on edit buttons
		balance_control_bg = self.main_canvas.create_rectangle(self.balance_control_centre - self.balance_control_width, 0, self.balance_control_centre + self.balance_control_width, self.balance_control_height, fill=zynthian_gui_config.color_bg, width=0, state="hidden", tags=("edit_control","balance_control"))
		self.balance_control_left = self.main_canvas.create_rectangle(int(self.balance_control_centre - self.balance_control_width), 0, self.balance_control_centre, self.balance_control_height, fill="dark red", width=0, state="hidden", tags=("edit_control","balance_control"))
		self.balance_control_right = self.main_canvas.create_rectangle(self.balance_control_centre, 0, self.balance_control_centre + self.balance_control_width, self.balance_control_height, fill="dark green", width=0, state="hidden", tags=("edit_control","balance_control"))
		self.main_canvas.tag_bind("balance_control", "<ButtonPress-1>", self.on_balance_press)
		self.main_canvas.tag_bind("balance_control", "<ButtonRelease-1>", self.on_balance_release)
		self.main_canvas.tag_bind("balance_control", "<B1-Motion>", self.on_balance_motion)

		edit_button_x = 1 + int(self.fader_width)
		edit_button_y = self.balance_control_height + 1
		# Solo button
		self.main_canvas.create_rectangle(edit_button_x, edit_button_y, edit_button_x + button_width, edit_button_y + self.edit_height, state="hidden", fill=zynthian_gui_mixer_channel.solo_color, tags=("edit_control", "solo_button"))
		self.main_canvas.create_text(edit_button_x + int(button_width / 2), edit_button_y + int(self.edit_height / 2), fill="white", text="SOLO", state="hidden", tags=("edit_control", "solo_button"), font=font, justify='center')
		# Mute button
		edit_button_y += self.edit_height
		self.main_canvas.create_rectangle(edit_button_x, edit_button_y, edit_button_x + button_width, edit_button_y + self.edit_height, state="hidden", fill=zynthian_gui_mixer_channel.mute_color, tags=("edit_control", "mono_button"))
		self.main_canvas.create_text(edit_button_x + int(button_width / 2), edit_button_y + int(self.edit_height / 2), fill="white", text="MONO", state="hidden", tags=("edit_control", "mono_button"), font=font, justify='center')
		# Mute button
		edit_button_y += self.edit_height
		self.main_canvas.create_rectangle(edit_button_x, edit_button_y, edit_button_x + button_width, edit_button_y + self.edit_height, state="hidden", fill=zynthian_gui_mixer_channel.mute_color, tags=("edit_control", "mute_button"))
		self.main_canvas.create_text(edit_button_x + int(button_width / 2), edit_button_y + int(self.edit_height / 2), fill="white", text="MUTE", state="hidden", tags=("edit_control", "mute_button"), font=font, justify='center')
		# Layer button
		edit_button_y += self.edit_height
		self.main_canvas.create_rectangle(edit_button_x, edit_button_y, edit_button_x + button_width, edit_button_y + self.edit_height, state="hidden", fill="dark orange", tags=("edit_control", "layer_button"))
		self.layer_button_text = self.main_canvas.create_text(edit_button_x + int(button_width / 2), edit_button_y + int(self.edit_height / 2), fill="white", text="LAYER", state="hidden", tags=("edit_control", "layer_button"), font=font, justify='center')
		# Reset gain button
		edit_button_y += self.edit_height
		self.main_canvas.create_rectangle(edit_button_x, edit_button_y, edit_button_x + button_width, edit_button_y + self.edit_height, state="hidden", fill="dark blue", tags=("edit_control", "reset_gain_button"))
		self.reset_gain_button_text = self.main_canvas.create_text(edit_button_x + int(button_width / 2), edit_button_y + int(self.edit_height / 2), fill="white", text="RESET\nGAIN", state="hidden", tags=("edit_control", "reset_gain_button"), font=font, justify='center')
		# Reset balance button
		edit_button_y += self.edit_height
		self.main_canvas.create_rectangle(edit_button_x, edit_button_y, edit_button_x + button_width, edit_button_y + self.edit_height, state="hidden", fill="dark blue", tags=("edit_control", "reset_balance_button"))
		self.reset_balance_button_text = self.main_canvas.create_text(edit_button_x + int(button_width / 2), edit_button_y + int(self.edit_height / 2), fill="white", text="RESET\nBALANCE", state="hidden", tags=("edit_control", "reset_balance_button"), font=font, justify='center')
		# Cancel button
		edit_button_y += self.edit_height
		self.main_canvas.create_rectangle(edit_button_x, edit_button_y, edit_button_x + button_width, edit_button_y + self.edit_height, state="hidden", fill=zynthian_gui_config.color_bg, tags=("edit_control", "cancel_button"))
		self.main_canvas.create_text(edit_button_x + int(button_width / 2), edit_button_y + int(self.edit_height / 2), fill="white", text="CANCEL", state="hidden", tags=("edit_control", "cancel_button"), font=font, justify='center')

		if os.environ.get("ZYNTHIAN_UI_ENABLE_CURSOR") == "0":
			self.main_canvas.bind("<Button-5>", self.on_fader_wheel_down)
			self.main_canvas.bind("<Button-4>", self.on_fader_wheel_up)

		self.main_canvas.tag_bind("mute_button", "<ButtonRelease-1>", self.on_mute_release)
		self.main_canvas.tag_bind("solo_button", "<ButtonRelease-1>", self.on_solo_release)
		self.main_canvas.tag_bind("mono_button", "<ButtonRelease-1>", self.on_mono_release)
		self.main_canvas.tag_bind("layer_button", "<ButtonRelease-1>", self.on_layer_release)
		self.main_canvas.tag_bind("reset_gain_button", "<ButtonRelease-1>", self.on_reset_volume_release)
		self.main_canvas.tag_bind("reset_balance_button", "<ButtonRelease-1>", self.on_reset_balance_release)
		self.main_canvas.tag_bind("cancel_button", "<ButtonPress-1>", self.on_cancel_press)

		zynmixer.enable_dpm(False) # Disable DPM by default - they get enabled when mixer is shown
		if zynthian_gui_config.show_cpu_status:
			self.meter_mode = self.METER_CPU
		else:
			self.meter_mode = self.METER_NONE # Don't show meter in status bar

		# Init touchbar
		self.init_buttonbar()


	# Function to refresh (redraw) balance edit control
	def draw_balance_edit(self):
		balance = zynmixer.get_balance(self.get_midi_chan(self.selected_channel))
		if balance > 0:
			self.main_canvas.coords(self.balance_control_left, self.balance_control_centre - (1-balance) * self.balance_control_width, 0, self.balance_control_centre, self.balance_control_height)
			self.main_canvas.coords(self.balance_control_right, self.balance_control_centre, 0, self.balance_control_centre + self.balance_control_width, self.balance_control_height)
		else:
			self.main_canvas.coords(self.balance_control_left, self.balance_control_centre - self.balance_control_width, 0, self.balance_control_centre, self.balance_control_height)
			self.main_canvas.coords(self.balance_control_right, self.balance_control_centre, 0, self.balance_control_centre + self.balance_control_width + self.balance_control_width * balance, self.balance_control_height)


	# Function to force the redrawing of UI controls for all channel strips
	def draw_mixer_controls(self):
		for channel in range(self.max_channels):
			self.channels[channel].draw_controls()
		self.main_channel.draw_controls()


	# Function to redraw, if needed, the UI controls for all channel strips
	def redraw_mixer_controls(self):
		for channel in range(self.max_channels):
			self.channels[channel].redraw_controls()
		self.main_channel.redraw_controls()


	# Function to handle hiding display
	def hide(self):
		zynmixer.enable_dpm(False)
		super().hide()


	# Function to handle showing display
	def show(self):
		self.zyngui.screens["control"].unlock_controllers()

		self.set_mixer_mode()

		self.selected_channel = self.number_layers
		if self.zyngui.curlayer:
			for index, fader in enumerate(self.channels): #TODO: Can remove this iteration and just index directly from self.zyngui.curlayer.midi_chan
				if fader.channel == self.zyngui.curlayer.midi_chan:
					self.selected_channel = index
		if self.selected_channel > self.number_layers and self.selected_channel != self.main_channel:
			self.selected_channel = self.number_layers

		self.setup_zyncoders()
		self.select_channel(self.selected_channel)

		zynmixer.enable_dpm(True)
		super().show()


	# Function to refresh loading animation
	def refresh_loading(self):
		pass


	# Function to refresh screen
	def refresh_status(self, status={}):
		if self.shown:
			super().refresh_status(status)
			self.main_channel.draw_dpm()
			if self.edit_channel is None:
				for ch in range(self.max_channels):
					self.channels[ch].draw_dpm()
			else:
				self.channels[0].draw_dpm()
				self.draw_balance_edit()

	#--------------------------------------------------------------------------
	# Mixer Functionality
	#--------------------------------------------------------------------------

	# Function to get a channel strip object from a "channel index" => @riban, i find a "little bit" confusing the use of the word "channel"
	# channel: Index of gui channel to get. If None, selected channel is used.
	def get_channel_strip(self, chi=None):
		if chi is None:
			chi = self.selected_channel
		if chi < 0:
			return None
		if chi < self.number_layers:
			return self.channels[chi - self.channel_offset]
		else:
			return self.main_channel


	# Function to display selected channel highlight border
	# channel: Index of gui channel to highlight. If None, selected channel is used.
	def highlight_channel(self, channel):
		chan_strip = self.get_channel_strip(channel)
		if chan_strip:
			#chan_strip.select(hl)
			self.main_canvas.coords(self.selection_highlight, chan_strip.x, chan_strip.height - chan_strip.legend_height, chan_strip.x + chan_strip.width + 1, chan_strip.height)


	# Function to select mixer channel by MIDI channel. Lovely naming ;-)
	# midi_chan: MIDI channel
	def select_midi_chan(self, midi_chan, set_curlayer=True):
		if midi_chan == MAX_NUM_CHANNELS:
			self.select_channel(self.number_layers, set_curlayer)
			return
		for i, chan_strip in enumerate(self.channels):
			if chan_strip.channel == midi_chan:
				self.select_channel(i, set_curlayer)
				return


	# Function to get MIDI channel (and hence mixer channel) from gui channel => Amazing naming!! ;-DDD
	#	channel: Index of gui channel.  If None, selected channel is used.
	#	returns: MIDI channel, MAX_NUM_CHANNELS if main bus or None for invalid channel
	def get_midi_chan(self, channel=None):
		if channel is None:
			channel = self.selected_channel
		if channel == self.number_layers:
			return MAX_NUM_CHANNELS
		elif channel > self.number_layers:
			return None
		return self.channels[channel - self.channel_offset].channel


	# Function to select channel by index
	#	channel: Index of gui channel to select
	def select_channel(self, channel, set_curlayer=True):
		if self.mode == 0 or channel is None or channel < 0 or channel > self.number_layers:
			logging.warning("Bad channel index, or something like that => {}".format(channel))
			return

		self.selected_channel = channel

		if self.selected_channel < self.channel_offset:
			self.channel_offset = channel
			self.set_mixer_mode()
		elif self.selected_channel >= self.channel_offset + self.max_channels and self.selected_channel != self.number_layers:
			self.channel_offset = self.selected_channel - self.max_channels + 1
			self.set_mixer_mode()
		self.highlight_channel(self.selected_channel)

		self.update_zyncoders()

		self.selected_layer = None
		
		# Main channel selected
		if channel == self.number_layers:
			return

		# For the rest of channel strips, try to set the active layer
		layer = self.zyngui.screens['layer'].get_root_layer_by_midi_chan(self.get_midi_chan())
		if layer:
			self.selected_layer = layer
			if set_curlayer:
				self.zyngui.set_curlayer(layer)


	# Function change to edit mode
	def set_edit_mode(self, params=None):
		self.mode = 0
		self.edit_channel = self.selected_channel
		for channel in self.channels:
			channel.hide()
		channel = self.max_channels - 1
		self.main_canvas.itemconfig(self.selection_highlight, state="hidden")
		self.channels[channel].set_channel(self.get_midi_chan(self.selected_channel))
		self.channels[channel].show()
		self.main_canvas.itemconfig("edit_control", state="normal")
		self.channels[channel].draw()
		self.draw_balance_edit()
		self.set_title("Edit channel %d" % (self.selected_channel + 1))


	# Function change to mixer mode
	def set_mixer_mode(self):
		self.main_canvas.itemconfig("edit_control", state="hidden")
		for channel in range(self.max_channels):
			self.channels[channel].set_channel(None)
		self.number_layers = 0
		count = 0
		for channel in range(MAX_NUM_CHANNELS):
			if zynmixer.is_channel_routed(channel):
				if self.number_layers >= self.channel_offset and count < self.max_channels:
					self.channels[count].set_channel(channel)
					count += 1
				self.number_layers += 1
		self.main_canvas.itemconfig(self.selection_highlight, state="normal")
		self.mode = 1
		self.edit_channel = None
		self.set_title("Audio Mixer")


	# Function to set volume
	#	value: Volume value (0..1)
	#	ch: channel to set volume. If None, selected channel is used
	def set_volume(self, value, ch=None):
		chan_strip = self.get_channel_strip(ch)
		if chan_strip:
			chan_strip.set_volume(value)
			if ch == self.selected_channel:
				self.update_zyncoders()


	# Function to set volume
	#	value: Balance value (0..1)
	#	ch: channel to set volume. If None, selected channel is used
	def set_balance(self, value, ch=None):
		chan_strip = self.get_channel_strip(ch)
		if chan_strip:
			chan_strip.set_balance(value)
			if ch == self.selected_channel:
				self.update_zyncoders()


	# Function to reset volume
	#	ch: channel to reset volume. If None, selected channel is used
	def reset_volume(self, ch=None):
		chan_strip = self.get_channel_strip(ch)
		if chan_strip:
			chan_strip.reset_volume()
			if ch == self.selected_channel:
				self.update_zyncoders()


	# Function to reset balance
	#	ch: channel to reset volume. If None, selected channel is used
	def reset_balance(self, ch=None):
		chan_strip = self.get_channel_strip(ch)
		if chan_strip:
			chan_strip.reset_balance()
			if ch == self.selected_channel:
				self.update_zyncoders()


	# Function to set mute
	#	value: Mute value (True/False)
	#	ch: channel to toggle mute. If None, selected channel is used
	def set_mute(self, value, ch=None):
		chan_strip = self.get_channel_strip(ch)
		if chan_strip:
			chan_strip.set_mute(value)


	# Function to set solo
	#	value: Solo value (True/False)
	#	ch: channel to toggle solo. If None, selected channel is used
	def set_solo(self, value, ch=None):
		chan_strip = self.get_channel_strip(ch)
		if chan_strip:
			chan_strip.set_solo(value)
			self.main_channel.set_redraw_controls()


	# Function to set mono
	#	value: Mono value (True/False)
	#	ch: channel to toggle mono. If None, selected channel is used
	def set_mono(self, value, ch=None):
		chan_strip = self.get_channel_strip(ch)
		if chan_strip:
			chan_strip.set_mono(value)


	# Function to toggle mute
	#	ch: channel to toggle mute. If None, selected channel is used
	def toggle_mute(self, ch=None):
		chan_strip = self.get_channel_strip(ch)
		if chan_strip:
			chan_strip.toggle_mute()


	# Function to toggle solo
	#	ch: channel to toggle solo. If None, selected channel is used
	def toggle_solo(self, ch=None):
		chan_strip = self.get_channel_strip(ch)
		if chan_strip:
			chan_strip.toggle_solo()
			self.main_channel.set_redraw_controls()

	# Function to toggle mono
	#	ch: channel to toggle mono. If None, selected channel is used
	def toggle_mono(self, ch=None):
		chan_strip = self.get_channel_strip(ch)
		if chan_strip:
			chan_strip.toggle_mono()


	#--------------------------------------------------------------------------
	# Physical UI Control Management: Pots & switches
	#--------------------------------------------------------------------------


	# Function to handle switches press
	#	swi: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	t: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def switch(self, swi, t):
		if swi == ENC_LAYER:
			if t == "S":
				self.toggle_mute()
				self.redraw_mixer_controls()
				return True

		elif swi == ENC_BACK:
			if t == "S":
				if self.mode == 0:
					self.set_mixer_mode()
					return True
				else:
					self.reset_balance()
					self.redraw_mixer_controls()
					return True

		elif swi == ENC_SNAPSHOT:
			if t == "S":
				self.toggle_solo()
				self.redraw_mixer_controls()
				return True
			elif t == "B":
				# Implement MIDI learning!
				self.zyngui.show_modal('snapshot')
				return True

		elif swi == ENC_SELECT:
			if t == "S":
				if self.selected_channel < self.number_layers:
					self.zyngui.screens['layer'].select(self.selected_channel)
					if self.selected_layer is not None:
						self.zyngui.layer_control(self.selected_layer)
				return True
			elif t == "B":
				if self.selected_channel < self.number_layers:
					# Layer Options
					self.zyngui.screens['layer'].select(self.selected_channel)
					self.zyngui.screens['layer_options'].reset()
					self.zyngui.show_modal('layer_options')
				return True

		return False


	def setup_zyncoders(self):
		selected_midich = self.get_midi_chan(self.selected_channel)

		value = int(zynmixer.get_level(selected_midich) * 100)
		lib_zyncore.setup_rangescale_zynpot(ENC_LAYER, 0, 100, value, 0)
		lib_zyncore.setup_midi_zynpot(ENC_LAYER, 0, 0)
		lib_zyncore.setup_osc_zynpot(ENC_LAYER, None)

		value = 50 + int(zynmixer.get_balance(selected_midich) * 50)
		lib_zyncore.setup_rangescale_zynpot(ENC_BACK, 0, 100, value, 0)
		lib_zyncore.setup_midi_zynpot(ENC_BACK, 0, 0)
		lib_zyncore.setup_osc_zynpot(ENC_BACK, None)

		value = int(zynmixer.get_level(self.get_midi_chan(self.number_layers)) * 100)
		lib_zyncore.setup_rangescale_zynpot(ENC_SNAPSHOT, 0, 100, value, 0)
		lib_zyncore.setup_midi_zynpot(ENC_SNAPSHOT, 0, 0)
		lib_zyncore.setup_osc_zynpot(ENC_SNAPSHOT, None)

		lib_zyncore.setup_rangescale_zynpot(ENC_SELECT, 0, self.number_layers, self.selected_channel, 1)
		lib_zyncore.setup_midi_zynpot(ENC_SELECT, 0, 0)
		lib_zyncore.setup_osc_zynpot(ENC_SELECT, None)


	# Update the zyncoders values
	def update_zyncoders(self):
		# Selected channel volume & balance
		selected_midich = self.get_midi_chan(self.selected_channel)
		value = int(zynmixer.get_level(selected_midich) * 100)
		lib_zyncore.set_value_zynpot(ENC_LAYER, value, 0)
		value = 50 + int(zynmixer.get_balance(selected_midich) * 50)
		lib_zyncore.set_value_zynpot(ENC_BACK, value, 0)

		# Master channel volume
		value = int(zynmixer.get_level(self.get_midi_chan(self.number_layers)) * 100)
		lib_zyncore.set_value_zynpot(ENC_SNAPSHOT, value, 0)

		# Selector encoder
		lib_zyncore.set_value_zynpot(ENC_SELECT, self.selected_channel, 0)


	# Function to handle zyncoder polling.
	def zyncoder_read(self):
		if not self.shown:
			return

		redraw_channels = []

		#if value!=self.zyncoder_last_value[ENC_LAYER]:
		if lib_zyncore.get_value_flag_zynpot(ENC_LAYER):
			value = lib_zyncore.get_value_zynpot(ENC_LAYER)
			#logging.debug("Value LAYER: {}".format(value))
			#self.zyncoder_last_value[ENC_LAYER] = value
			channel = self.get_midi_chan(self.selected_channel)
			if channel == MAX_NUM_CHANNELS:
				lib_zyncore.set_value_zynpot(ENC_SNAPSHOT, value, 0)
			zynmixer.set_level(channel, value * 0.01)
			if self.selected_channel == self.number_layers:
				redraw_channels.append(self.main_channel)
			else:
				redraw_channels.append(self.channels[self.selected_channel])

		#if value!=self.zyncoder_last_value[ENC_BACK]:
		if lib_zyncore.get_value_flag_zynpot(ENC_BACK):
			value = lib_zyncore.get_value_zynpot(ENC_BACK)
			#logging.debug("Value BACK: {}".format(value))
			#self.zyncoder_last_value[ENC_BACK] = value
			channel = self.get_midi_chan(self.selected_channel)
			zynmixer.set_balance(channel, (value - 50) * 0.02)
			if self.selected_channel == self.number_layers:
				redraw_channels.append(self.main_channel)
			else:
				redraw_channels.append(self.channels[self.selected_channel])

		#if value!=self.zyncoder_last_value[ENC_SNAPSHOT]:
		if lib_zyncore.get_value_flag_zynpot(ENC_SNAPSHOT):
			value = lib_zyncore.get_value_zynpot(ENC_SNAPSHOT)
			#logging.debug("Value SHOT: {}".format(value))
			#self.zyncoder_last_value[ENC_SNAPSHOT] = value
			channel = self.get_midi_chan(self.number_layers)
			if self.get_midi_chan(self.selected_channel) == MAX_NUM_CHANNELS:
				lib_zyncore.set_value_zynpot(ENC_LAYER, value, 0)
			zynmixer.set_level(channel, value * 0.01)
			redraw_channels.append(self.main_channel)

		#if value!=self.zyncoder_last_value[ENC_SELECT]:
		if lib_zyncore.get_value_flag_zynpot(ENC_SELECT):
			value = lib_zyncore.get_value_zynpot(ENC_SELECT)
			#logging.debug("Value SELECT: {}".format(value))
			#self.zyncoder_last_value[ENC_SELECT] = value
			if (self.mode and value != self.selected_channel):
				self.select_channel(value)

		for ch in set(redraw_channels):
			ch.draw_controls()


	# Increment by inc the zyncoder's value
	def zyncoder_up(self, num, inc = 1):
		lib_zyncore.set_value_zynpot(num, lib_zyncore.get_value_pot(num) + inc, 0)


	# Decrement by dec the zyncoder's value
	def zyncoder_down(self, num, dec = 1):
		value = lib_zyncore.get_value_zynpot(num) - dec
		if value < 0:
			value = 0 #TODO: This should be handled by zyncoder
		lib_zyncore.set_value_zynpot(num, value, 0)


	# Function to handle CUIA SELECT_UP command
	def select_up(self):
		self.zyncoder_up(ENC_SELECT)


	# Function to handle CUIA SELECT_DOWN command
	def select_down(self):
		self.zyncoder_down(ENC_SELECT)


	# Function to handle CUIA BACK_UP command
	def back_up(self):
		self.zyncoder_up(ENC_BACK)


	# Function to handle CUIA BACK_DOWN command
	def back_down(self):
		self.zyncoder_back(ENC_BACK)


	# Function to handle CUIA LAYER_UP command
	def layer_up(self):
		self.zyncoder_up(ENC_LAYER)


	# Function to handle CUIA LAYER_DOWN command
	def layer_down(self):
		self.zyncoder_down(ENC_LAYER)


	# Function to handle CUIA SNAPSHOT_UP command
	def snapshot_up(self):
		self.zyncoder_up(ENC_SNAPSHOT)


	# Function to handle CUIA SNAPSHOT_DOWN command
	def snapshot_down(self):
		self.zyncoder_down(ENC_SNAPSHOT)


	#--------------------------------------------------------------------------
	# OSC message handling
	#--------------------------------------------------------------------------


	# Function to handle OSC messages
	def osc(self, path, args, types, src):
#		print("zynthian_gui_mixer::osc", path, args, types)
		if path[:6] == "volume" or path[:5] == "fader":
			try:
				self.set_volume(args[0], int(path[5:]))
			except:
				pass
		elif path[:7] == "balance":
			try:
				self.set_balance(args[0], int(path[7:]))
			except:
				pass
		elif path[:4] == "mute":
			try:
				self.set_mute(int(args[0]), int(path[4:]))
			except:
				pass
		elif path[:4] == "solo":
			try:
				self.set_solo(int(args[0]), int(path[4:]))
			except:
				pass
		self.redraw_mixer_controls()


	#--------------------------------------------------------------------------
	# State Management (mainly used by snapshots)
	#--------------------------------------------------------------------------

	# Get full mixer state
	# Returns: List of channels containing dictionary of each state value
	def get_state(self):
		state = []
		for channel in range(MAX_NUM_CHANNELS + 1):
			state.append({
				'level':zynmixer.get_level(channel),
				'balance':zynmixer.get_balance(channel),
				'mute':zynmixer.get_mute(channel),
				'solo':zynmixer.get_solo(channel),
				'mono':zynmixer.get_mono(channel)
				})
		return state


	# Set full mixer state
	# state: List of channels containing dictionary of each state value
	def set_state(self, state):
		for channel in range(MAX_NUM_CHANNELS + 1):
			zynmixer.set_level(channel, state[channel]['level'])
			zynmixer.set_balance(channel, state[channel]['balance'])
			zynmixer.set_mute(channel, state[channel]['mute'])
			if channel != MAX_NUM_CHANNELS:
				zynmixer.set_solo(channel, state[channel]['solo'])
			zynmixer.set_mono(channel, state[channel]['mono'])
		self.draw_mixer_controls()


	# Reset mixer to default state
	def reset_state(self):
		for channel in range(MAX_NUM_CHANNELS + 1):
			zynmixer.set_level(channel, 0.8)
			zynmixer.set_balance(channel, 0)
			zynmixer.set_mute(channel, 0)
			zynmixer.set_solo(channel, 0)
			zynmixer.set_mono(channel, 0)
		self.draw_mixer_controls()


	#--------------------------------------------------------------------------
	# GUI Event Management
	#--------------------------------------------------------------------------

	# Function to handle balance press
	#	event: Mouse event
	def on_balance_press(self, event):
		self.balance_drag_start = event


	# Function to handle balance release
	#	event: Mouse event
	def on_balance_release(self, event):
		pass


	# Function to balance fader drag
	#	event: Mouse event
	def on_balance_motion(self, event):
		balance = zynmixer.get_balance(self.get_midi_chan(self.selected_channel)) + (event.x - self.balance_drag_start.x) / self.balance_control_width
		if balance > 1: balance = 1
		if balance < -1: balance = -1
		self.balance_drag_start = event
		zynmixer.set_balance(self.get_midi_chan(self.selected_channel), balance)
		self.draw_balance_edit()


	# Function to handle mute button release
	#	event: Mouse event
	def on_mute_release(self, event):
		self.toggle_mute()
		self.redraw_mixer_controls()


	# Function to handle solo button release
	#	event: Mouse event
	def on_solo_release(self, event):
		self.toggle_solo()
		self.redraw_mixer_controls()


	# Function to handle mono button release
	#	event: Mouse event
	def on_mono_release(self, event):
		self.toggle_mono()
		self.redraw_mixer_controls()


	# Function to handle layer button release
	#	event: Mouse event
	def on_layer_release(self, event):
		self.zyngui.layer_control(self.selected_layer)


	# Function to handle reset volume button release
	#	event: Mouse event
	def on_reset_volume_release(self, event):
		self.reset_volume()
		self.redraw_mixer_controls()


	# Function to handle reset balance button release
	#	event: Mouse event
	def on_reset_balance_release(self, event):
		self.reset_balance()
		self.redraw_controls()


	# Function to handle cancel edit button release
	#	event: Mouse event
	def on_cancel_press(self, event):
		self.set_mixer_mode()


	# Function to handle global mouse wheel down
	#	event: Mouse event
	def on_fader_wheel_down(self, event):
		if self.selected_channel is None:
			return
		channel = self.get_midi_chan()
		level = zynmixer.get_level(channel) - 0.02
		if level > 1: level = 1
		if level < 0: level = 0
		self.set_volume(level)
		self.redraw_mixer_controls()


	# Function to handle global mouse wheel up
	#	event: Mouse event
	def on_fader_wheel_up(self, event):
		if self.selected_channel is None:
			return
		channel = self.get_midi_chan()
		level = zynmixer.get_level(channel) + 0.02
		if level > 1: level = 1
		if level < 0: level = 0
		self.set_volume(level)
		self.redraw_mixer_controls()
