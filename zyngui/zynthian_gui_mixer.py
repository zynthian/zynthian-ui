#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Audio Mixer
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

import os
import tkinter
import logging

# Zynthian specific modules
from . import zynthian_gui_base
from . import zynthian_gui_config
from zyncoder.zyncore import get_lib_zyncore

#------------------------------------------------------------------------------
# Zynthian Mixer Strip Class
# This provides a UI element that represents a mixer strip, one used per chain
#------------------------------------------------------------------------------

class zynthian_gui_mixer_strip():

	# Initialise mixer strip object
	#	parent: Parent object
	#	x: Horizontal coordinate of left of fader
	#	y: Vertical coordinate of top of fader
	#	width: Width of fader
	#	height: Height of fader
	def __init__(self, parent, x, y, width, height):
		self.parent = parent
		self.zynmixer = parent.zynmixer
		self.zctrls = None
		self.x = x
		self.y = y
		self.width = width
		self.height = height
		self.hidden = False
		self.chain_id = None
		self.chain = None
		self.midi_learning = False # False: Not learning, True: Preselection, gui_control: Learning
		self.MAIN_MIXBUS_STRIP_INDEX = self.zynmixer.get_max_channels()

		self.hidden = True

		self.button_height = int(self.height * 0.07)
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
		self.dpm_a_x = int(x + self.width - self.dpm_width * 2 - 2)
		self.dpm_a_y = self.fader_bottom
		self.dpm_b_x = x + self.width - self.dpm_width - 1
		self.dpm_b_y = self.fader_bottom
		self.dpm_zero_y = int(self.fader_bottom - self.fader_height * self.dpm_high)
		self.fader_width = self.width - self.dpm_width * 2 - 2

		self.fader_drag_start = None
		self.strip_drag_start = None
		self.dragging = False

		# Default style
		#self.fader_bg_color = zynthian_gui_config.color_bg
		self.fader_bg_color = zynthian_gui_config.color_panel_bg
		self.fader_bg_color_hl = "#6a727d" #"#207024"
		#self.fader_color = zynthian_gui_config.color_panel_hl
		#self.fader_color_hl = zynthian_gui_config.color_low_on
		self.fader_color = zynthian_gui_config.color_off
		self.fader_color_hl = zynthian_gui_config.color_on
		self.legend_txt_color = zynthian_gui_config.color_tx
		self.legend_bg_color = zynthian_gui_config.color_panel_bg
		self.legend_bg_color_hl = zynthian_gui_config.color_on
		self.button_bgcol = zynthian_gui_config.color_panel_bg
		self.button_txcol = zynthian_gui_config.color_tx
		self.left_color = "#00AA00"
		self.right_color = "#00EE00"
		self.left_color_learn = "#AAAA00"
		self.right_color_learn = "#EEEE00"
		self.low_color = "#00AA00"
		self.medium_color = "#CCCC00" # yellow
		self.high_color = "#CC0000"
		self.dpm_hold_color = self.low_color

		self.mute_color = zynthian_gui_config.color_on #"#3090F0"
		self.solo_color = "#D0D000"
		self.mono_color = "#B0B0B0"

		#font_size = int(0.5 * self.legend_height)
		font_size = int(0.25 * self.width)
		self.font = (zynthian_gui_config.font_family, font_size)
		self.font_fader = (zynthian_gui_config.font_family, int(0.9 * font_size))
		self.font_icons = ("forkawesome", int(0.3 * self.width))
		self.font_learn = (zynthian_gui_config.font_family, int(0.7 * font_size))

		self.fader_text_limit = self.fader_top + int(0.1 * self.fader_height)

		'''
		Create GUI elements
		Tags:
			strip:X All elements within the fader strip used to show/hide strip
			fader:X Elements used for fader drag
			X is the id of this fader's background
		'''

		# Fader
		self.fader_bg = self.parent.main_canvas.create_rectangle(x, self.fader_top, x + self.width, self.fader_bottom, fill=self.fader_bg_color, width=0)
		self.parent.main_canvas.itemconfig(self.fader_bg, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg)))
		self.fader = self.parent.main_canvas.create_rectangle(x, self.fader_top, x + self.width, self.fader_bottom, fill=self.fader_color, width=0, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)))
		self.fader_text = self.parent.main_canvas.create_text(int(fader_centre), int(self.fader_top + self.fader_height / 2), text="??", font=self.font_learn, angle=90, state=tkinter.HIDDEN)
		self.legend = self.parent.main_canvas.create_text(x, self.fader_bottom - 2, fill=self.legend_txt_color, text="", tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg)), angle=90, anchor="nw", font=self.font_fader)

		# DPM
		self.dpm_h_a = self.parent.main_canvas.create_rectangle(self.dpm_a_x, self.fader_top, self.dpm_a_x + self.dpm_width, self.dpm_a_y - self.dpm_scale_lh, width=0, fill=self.high_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg), "dpm"))
		self.dpm_m_a = self.parent.main_canvas.create_rectangle(self.dpm_a_x, self.dpm_a_y - self.dpm_scale_lh, self.dpm_a_x + self.dpm_width, self.dpm_a_y - self.dpm_scale_lm, width=0, fill=self.medium_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg), "dpm"))
		self.dpm_l_a = self.parent.main_canvas.create_rectangle(self.dpm_a_x, self.dpm_a_y - self.dpm_scale_lm, self.dpm_a_x + self.dpm_width,  self.fader_bottom, width=0, fill=self.low_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg), "dpm"))
		self.dpm_b_a = self.parent.main_canvas.create_rectangle(self.dpm_a_x, self.fader_bottom, self.dpm_a_x + self.dpm_width, self.fader_top, width=0, fill=self.fader_bg_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg), "dpm"))
		self.dpm_h_b = self.parent.main_canvas.create_rectangle(self.dpm_b_x, self.fader_top, self.dpm_b_x + self.dpm_width, self.dpm_b_y - self.dpm_scale_lh, width=0, fill=self.high_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg), "dpm"))
		self.dpm_m_b = self.parent.main_canvas.create_rectangle(self.dpm_b_x, self.dpm_b_y - self.dpm_scale_lh, self.dpm_b_x + self.dpm_width, self.dpm_b_y - self.dpm_scale_lm, width=0, fill=self.medium_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg), "dpm"))
		self.dpm_l_b = self.parent.main_canvas.create_rectangle(self.dpm_b_x, self.dpm_b_y - self.dpm_scale_lm, self.dpm_b_x + self.dpm_width,  self.fader_bottom, width=0, fill=self.low_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg), "dpm"))
		self.dpm_b_b = self.parent.main_canvas.create_rectangle(self.dpm_b_x, self.fader_bottom, self.dpm_b_x + self.dpm_width, self.fader_top, width=0, fill=self.fader_bg_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg), "dpm"))
		self.dpm_hold_a = self.parent.main_canvas.create_rectangle(self.dpm_a_x, self.fader_bottom, self.dpm_a_x + self.dpm_width, self.fader_bottom, width=0, fill=self.low_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)), state=tkinter.HIDDEN)
		self.dpm_hold_b = self.parent.main_canvas.create_rectangle(self.dpm_b_x, self.fader_bottom, self.dpm_b_x + self.dpm_width, self.fader_bottom, width=0, fill=self.low_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)), state=tkinter.HIDDEN)
		self.mono_text = self.parent.main_canvas.create_text(int(self.dpm_b_x + self.dpm_width / 2), int(self.fader_top + self.fader_height / 2), text="??", state=tkinter.HIDDEN)

		# 0dB line
		self.parent.main_canvas.create_line(self.dpm_a_x, self.dpm_zero_y, x + self.width, self.dpm_zero_y, fill=self.medium_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)))

		# Solo button
		self.solo = self.parent.main_canvas.create_rectangle(x, 0, x + self.width, self.button_height, fill=self.button_bgcol, width=0, tags=("solo_button:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)))
		self.solo_text = self.parent.main_canvas.create_text(x + self.width / 2, self.button_height * 0.5, text="S", fill=self.button_txcol, tags=("solo_button:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)), font=self.font)

		# Mute button
		self.mute = self.parent.main_canvas.create_rectangle(x, self.button_height, x + self.width, self.button_height * 2, fill=self.button_bgcol, width=0, tags=("mute_button:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)))
		self.mute_text = self.parent.main_canvas.create_text(x + self.width / 2, self.button_height * 1.5, text="M", fill=self.button_txcol, tags=("mute_button:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)), font=self.font_icons)

		# Legend strip at bottom of screen
		self.legend_strip_bg = self.parent.main_canvas.create_rectangle(x, self.height - self.legend_height, x + self.width, self.height, width=0, tags=("strip:%s"%(self.fader_bg),"legend_strip:%s"%(self.fader_bg)), fill=self.legend_bg_color)
		self.legend_strip_txt = self.parent.main_canvas.create_text(int(fader_centre), self.height - self.legend_height / 2, fill=self.legend_txt_color, text="-", tags=("strip:%s"%(self.fader_bg),"legend_strip:%s"%(self.fader_bg)), font=self.font)

		# Balance indicator
		self.balance_left = self.parent.main_canvas.create_rectangle(x, self.balance_top, int(fader_centre - 0.5), self.balance_top + self.balance_height, fill=self.left_color, width=0, tags=("strip:%s"%(self.fader_bg), "balance:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)))
		self.balance_right = self.parent.main_canvas.create_rectangle(int(fader_centre + 0.5), self.balance_top, self.width, self.balance_top + self.balance_height , fill=self.right_color, width=0, tags=("strip:%s"%(self.fader_bg), "balance:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)))
		self.balance_text = self.parent.main_canvas.create_text(int(fader_centre), int(self.balance_top + self.balance_height / 2) - 1, text="??", font=self.font_learn, state=tkinter.HIDDEN)
		self.parent.main_canvas.tag_bind("balance:%s"%(self.fader_bg), "<ButtonPress-1>", self.on_balance_press)


		# Fader indicators
		self.status_indicator = self.parent.main_canvas.create_text(x + 2, self.fader_top + 2, fill="#009000", anchor="nw", tags=("strip:%s"%(self.fader_bg)))

		self.parent.main_canvas.tag_bind("fader:%s"%(self.fader_bg), "<ButtonPress-1>", self.on_fader_press)
		self.parent.main_canvas.tag_bind("fader:%s"%(self.fader_bg), "<B1-Motion>", self.on_fader_motion)
		if os.environ.get("ZYNTHIAN_UI_ENABLE_CURSOR") == "1":
			self.parent.main_canvas.tag_bind("fader:%s"%(self.fader_bg), "<Button-4>", self.on_fader_wheel_up)
			self.parent.main_canvas.tag_bind("fader:%s"%(self.fader_bg), "<Button-5>", self.on_fader_wheel_down)
			self.parent.main_canvas.tag_bind("balance:%s"%(self.fader_bg), "<Button-4>", self.on_balance_wheel_up)
			self.parent.main_canvas.tag_bind("balance:%s"%(self.fader_bg), "<Button-5>", self.on_balance_wheel_down)
			self.parent.main_canvas.tag_bind("legend_strip:%s"%(self.fader_bg), "<Button-4>", self.parent.on_wheel)
			self.parent.main_canvas.tag_bind("legend_strip:%s"%(self.fader_bg), "<Button-5>", self.parent.on_wheel)
		self.parent.main_canvas.tag_bind("mute_button:%s"%(self.fader_bg), "<ButtonRelease-1>", self.on_mute_release)
		self.parent.main_canvas.tag_bind("solo_button:%s"%(self.fader_bg), "<ButtonRelease-1>", self.on_solo_release)
		self.parent.main_canvas.tag_bind("legend_strip:%s"%(self.fader_bg), "<ButtonPress-1>", self.on_strip_press)
		self.parent.main_canvas.tag_bind("legend_strip:%s"%(self.fader_bg), "<ButtonRelease-1>", self.on_strip_release)
		self.parent.main_canvas.tag_bind("legend_strip:%s"%(self.fader_bg), "<Motion>", self.on_strip_motion)

		self.draw_control()


	# Function to hide mixer strip
	def hide(self):
		self.parent.main_canvas.itemconfig("strip:%s"%(self.fader_bg), state=tkinter.HIDDEN)
		self.hidden = True


	# Function to show mixer strip
	def show(self):
		self.parent.main_canvas.itemconfig("strip:%s"%(self.fader_bg), state=tkinter.NORMAL)
		try:
			if not self.chain.is_audio():
				self.parent.main_canvas.itemconfig("audio_strip:%s"%(self.fader_bg), state=tkinter.HIDDEN)
		except:
			pass
		self.hidden = False
		self.draw_control()


	def get_legend_text(self):
		if self.chain is not None:
			res1 = self.chain.get_title()
			res2 = "" #TODO
			return res1+res2
		return "No info"


	def get_ctrl_learn_text(self, ctrl):
		try:
			param = self.zynmixer.get_learned_cc(self.zctrls[ctrl])
			return f"{param[0] + 1}#{param[1]}"
		except:
			return "??"


	def refresh_status(self):
		if self.parent.zyngui.state_manager.audio_recorder.is_armed(self.chain.mixer_chan):
			self.parent.main_canvas.itemconfig(self.status_indicator, text="{}\uf111".format(self.chain.status), fill=self.high_color)
		else:
			self.parent.main_canvas.itemconfig(self.status_indicator, text=self.chain.status, fill="#009000")
	

	# Function to draw the DPM level meter for a mixer strip
	def draw_dpm(self):
		if self.hidden or self.chain.mixer_chan is None:
			return

		# Get audio peaks from zynmixer
		signal = max(0, 1 + self.zynmixer.get_dpm(self.chain.mixer_chan, 0) / self.dpm_rangedB)
		level_a = int((1 - signal) * self.fader_height)
		signal = max(0, 1 + self.zynmixer.get_dpm(self.chain.mixer_chan, 1) / self.dpm_rangedB)
		level_b = int((1 - signal) * self.fader_height)
		signal = max(0, 1 + self.zynmixer.get_dpm_hold(self.chain.mixer_chan, 0) / self.dpm_rangedB)
		hold_a = int(min(signal, 1) * self.fader_height)
		signal = max(0, 1 + self.zynmixer.get_dpm_hold(self.chain.mixer_chan, 1) / self.dpm_rangedB)
		hold_b = int(min(signal, 1) * self.fader_height)

		# Draw left meter
		self.parent.main_canvas.coords(self.dpm_b_a, (self.dpm_a_x, self.fader_top, self.dpm_a_x + self.dpm_width, self.fader_top + level_a))
		self.parent.main_canvas.coords(self.dpm_hold_a, (self.dpm_a_x, self.dpm_a_y - hold_a, self.dpm_a_x + self.dpm_width, self.dpm_a_y - hold_a - 1))
		if hold_a >= self.dpm_scale_lh:
			self.parent.main_canvas.itemconfig(self.dpm_hold_a, state=tkinter.NORMAL, fill="#FF0000")
		elif hold_a >= self.dpm_scale_lm:
			self.parent.main_canvas.itemconfig(self.dpm_hold_a, state=tkinter.NORMAL, fill="#FFFF00")
		elif hold_a > 0:
			self.parent.main_canvas.itemconfig(self.dpm_hold_a, state=tkinter.NORMAL, fill=self.dpm_hold_color)
		else:
			self.parent.main_canvas.itemconfig(self.dpm_hold_a, state=tkinter.HIDDEN)

		# Draw right meter
		self.parent.main_canvas.coords(self.dpm_b_b, (self.dpm_b_x, self.fader_top, self.dpm_b_x + self.dpm_width, self.fader_top + level_b))
		self.parent.main_canvas.coords(self.dpm_hold_b, (self.dpm_b_x, self.dpm_b_y - hold_b, self.dpm_b_x + self.dpm_width, self.dpm_b_y - hold_b - 1))
		if hold_b >= self.dpm_scale_lh:
			self.parent.main_canvas.itemconfig(self.dpm_hold_b, state=tkinter.NORMAL, fill="#FF0000")
		elif hold_b >= self.dpm_scale_lm:
			self.parent.main_canvas.itemconfig(self.dpm_hold_b, state=tkinter.NORMAL, fill="#FFFF00")
		elif hold_b > 0:
			self.parent.main_canvas.itemconfig(self.dpm_hold_b, state=tkinter.NORMAL, fill=self.dpm_hold_color)
		else:
			self.parent.main_canvas.itemconfig(self.dpm_hold_b, state=tkinter.HIDDEN)


	def draw_balance(self):
		balance = self.zynmixer.get_balance(self.chain.mixer_chan)
		if balance > 0:
			self.parent.main_canvas.coords(self.balance_left,
				self.x + balance * self.width / 2, self.balance_top,
				self.x + self.width / 2, self.balance_top + self.balance_height)
			self.parent.main_canvas.coords(self.balance_right,
				self.x + self.width / 2, self.balance_top,
				self.x + self.width, self.balance_top + self.balance_height)
		else:
			self.parent.main_canvas.coords(self.balance_left,
				self.x, self.balance_top,
				self.x + self.width / 2, self.balance_top + self. balance_height)
			self.parent.main_canvas.coords(self.balance_right,
				self.x + self.width / 2, self.balance_top,
				self.x + self.width * balance / 2 + self.width, self.balance_top + self.balance_height)

		if self.midi_learning is True:
			lcolor = self.fader_bg_color
			rcolor = self.fader_bg_color
			txcolor = zynthian_gui_config.color_hl
			txstate = tkinter.NORMAL
			text = f"<-> {self.get_ctrl_learn_text('balance')}"

		elif self.midi_learning == 'balance':
			lcolor = self.left_color_learn
			rcolor = self.right_color_learn
			txcolor = zynthian_gui_config.color_ml
			txstate = tkinter.NORMAL
			text = ""
		else:
			lcolor = self.left_color
			rcolor = self.right_color
			txcolor = self.button_txcol
			txstate = tkinter.HIDDEN
			text = ""

		self.parent.main_canvas.itemconfig(self.balance_left, fill=lcolor)
		self.parent.main_canvas.itemconfig(self.balance_right, fill=rcolor)
		self.parent.main_canvas.itemconfig(self.balance_text, state=txstate, text=text, fill=txcolor)


	def draw_fader(self):
		self.parent.main_canvas.coords(self.fader, self.x, self.fader_top + self.fader_height * (1 - self.zynmixer.get_level(self.chain.mixer_chan)), self.x + self.fader_width, self.fader_bottom)


	def draw_level(self):
		self.draw_fader()

		if self.midi_learning is True:
			text = self.get_ctrl_learn_text('level')
			self.parent.main_canvas.itemconfig(self.fader_text, fill=zynthian_gui_config.color_hl, text=text, state=tkinter.NORMAL)
			self.parent.main_canvas.itemconfig(self.legend, state=tkinter.HIDDEN)
		elif self.midi_learning == 'level':
			if self.get_legend_text():
				self.parent.main_canvas.itemconfig(self.fader_text, state=tkinter.HIDDEN)
				self.parent.main_canvas.itemconfig(self.legend, state=tkinter.NORMAL, fill=zynthian_gui_config.color_ml)
			else:
				self.parent.main_canvas.itemconfig(self.fader_text, state=tkinter.NORMAL, text="Learing...", fill=zynthian_gui_config.color_ml)
				self.parent.main_canvas.itemconfig(self.legend, state=tkinter.HIDDEN)
		else:
			self.parent.main_canvas.itemconfig(self.fader_text, state=tkinter.HIDDEN)
			self.parent.main_canvas.itemconfig(self.legend, state=tkinter.NORMAL, fill=self.legend_txt_color)


	def draw_solo(self):
		txcolor = self.button_txcol
		font = self.font
		text = "S"
		if self.zynmixer.get_solo(self.chain.mixer_chan):
			bgcolor = self.solo_color
		else:
			bgcolor = self.button_bgcol

		if self.midi_learning is True:
			bgcolor = self.button_bgcol
			txcolor = zynthian_gui_config.color_hl
			font = self.font_learn
			text = f"S {self.get_ctrl_learn_text('solo')}"
		elif self.midi_learning == 'solo':
			txcolor = zynthian_gui_config.color_ml

		self.parent.main_canvas.itemconfig(self.solo, fill=bgcolor)
		self.parent.main_canvas.itemconfig(self.solo_text, text=text, font=font, fill=txcolor)


	def draw_mute(self):
		txcolor = self.button_txcol
		font = self.font_icons
		if self.zynmixer.get_mute(self.chain.mixer_chan):
			bgcolor = self.mute_color
			text = "\uf32f"
		else:
			bgcolor = self.button_bgcol
			text = "\uf028"

		if self.midi_learning is True:
			bgcolor = self.button_bgcol
			txcolor = zynthian_gui_config.color_hl
			font = self.font_learn
			text = f"\uf32f {self.get_ctrl_learn_text('mute')}"
		elif self.midi_learning == 'mute':
			txcolor = zynthian_gui_config.color_ml

		self.parent.main_canvas.itemconfig(self.mute, fill=bgcolor)
		self.parent.main_canvas.itemconfig(self.mute_text, text=text, font=font, fill=txcolor)


	def draw_mono(self):
		if self.zynmixer.get_mono(self.chain.mixer_chan):
			self.parent.main_canvas.itemconfig(self.dpm_l_a, fill=self.mono_color)
			self.parent.main_canvas.itemconfig(self.dpm_l_b, fill=self.mono_color)
			self.dpm_hold_color = "#FFFFFF"
		else:
			self.parent.main_canvas.itemconfig(self.dpm_l_a, fill=self.low_color)
			self.parent.main_canvas.itemconfig(self.dpm_l_b, fill=self.low_color)
			self.dpm_hold_color = "#00FF00"


	# Function to draw a mixer strip UI control
	#	control: Name of control or None to redraw all controls in the strip
	def draw_control(self, control=None):
		if self.hidden or self.chain is None:
			return

		if control == None:
			self.parent.main_canvas.itemconfig(self.legend, text="")
			if self.chain_id == "main":
				self.parent.main_canvas.itemconfig(self.legend_strip_txt, text="Main")
				self.parent.main_canvas.itemconfig(self.legend, text=self.get_legend_text(), state=tkinter.NORMAL)
			else:
				if isinstance(self.chain.midi_chan, int):
					strip_txt = str(self.chain.midi_chan + 1)
				else:
					strip_txt = "X"
				self.parent.main_canvas.itemconfig(self.legend_strip_txt, text=strip_txt)
				label_parts = self.get_legend_text().split("\n")
				for i, label in enumerate(label_parts):
					self.parent.main_canvas.itemconfig(self.legend, text=label, state=tkinter.NORMAL)
					bounds = self.parent.main_canvas.bbox(self.legend)
					if bounds[1] < self.fader_text_limit:
						while bounds and bounds[1] < self.fader_text_limit:
							label = label[:-1]
							self.parent.main_canvas.itemconfig(self.legend, text=label)
							bounds = self.parent.main_canvas.bbox(self.legend)
						label_parts[i] = label + "..."
				self.parent.main_canvas.itemconfig(self.legend, text="\n".join(label_parts))

		try:
			if not self.chain.is_audio():
				return
		except Exception as e:
			logging.error(e)

		if control == None:
			self.draw_dpm()
			#self.refresh_status()

		if control in [None, 'level']:
			self.draw_level()

		if control in [None, 'solo']:
			self.draw_solo()

		if control in [None, 'mute']:
			self.draw_mute()

		if control in [None, 'balance']:
			self.draw_balance()

		if control in [None, 'mono']:
			self.draw_mono()


	#--------------------------------------------------------------------------
	# Mixer Strip functionality
	#--------------------------------------------------------------------------

	# Function to highlight/downlight the strip
	# hl: Boolean => True=highlight, False=downlight
	def set_highlight(self, hl=True):
		if hl:
			self.set_fader_color(self.fader_bg_color_hl)
			self.parent.main_canvas.itemconfig(self.legend_strip_bg, fill=self.legend_bg_color_hl)
		else:
			self.set_fader_color(self.fader_color)
			self.parent.main_canvas.itemconfig(self.legend_strip_bg, fill=self.fader_bg_color)


	# Function to set fader colors
	# fg: Fader foreground color
	# bg: Fader background color (optional - Default: Do not change background color)
	def set_fader_color(self, fg, bg=None):
		self.parent.main_canvas.itemconfig(self.fader, fill=fg)
		if bg:
			self.parent.main_canvas.itemconfig(self.fader_bg_color, fill=bg)


	# Function to set chain associated with mixer strip
	#	chain: Chain object
	def set_chain(self, chain_id):
		self.chain_id = chain_id
		self.chain = self.parent.zyngui.chain_manager.get_chain(chain_id)
		if self.chain is None:
			self.hide()
		else:
			self.show()


	# Function to set volume value
	#	value: Volume value (0..1)
	def set_volume(self, value):
		if self.midi_learning is True:
			self.enable_midi_learn('level')
		elif not self.midi_learning:
			if self.zctrls:
				self.zctrls['level'].set_value(value)
		self.parent.pending_refresh_queue.add((self, 'level'))


	# Function to get volume value
	def get_volume(self):
		if self.zctrls:
			return self.zctrls['level'].value


	# Function to nudge volume
	def nudge_volume(self, dval):
		if self.midi_learning is True:
			self.enable_midi_learn('level')
		elif not self.midi_learning:
			if self.zctrls:
				self.zctrls['level'].nudge(dval)
		self.draw_fader()


	# Function to set balance value
	#	value: Balance value (-1..1)
	def set_balance(self, value):
		if self.midi_learning is True:
			self.enable_midi_learn('balance')
		elif not self.midi_learning:
			if self.zctrls:
				self.zctrls['balance'].set_value(value)
		self.draw_balance()


	# Function to get balance value
	def get_balance(self):
		if self.zctrls:
			return self.zctrls['balance'].value


	# Function to nudge balance
	def nudge_balance(self, dval):
		if self.midi_learning is True:
			self.enable_midi_learn('balance')
		elif not self.midi_learning:
			if self.zctrls:
				self.zctrls['balance'].nudge(dval)
		self.draw_balance()


	# Function to reset volume
	def reset_volume(self):
		self.set_volume(0.8)


	# Function to reset balance
	def reset_balance(self):
		self.set_balance(0.0)


	# Function to set mute
	#	value: Mute value (True/False)
	def set_mute(self, value):
		if self.midi_learning is True:
			self.enable_midi_learn('mute')
		elif not self.midi_learning:
			if self.zctrls:
				self.zctrls['mute'].set_value(value)
		self.parent.pending_refresh_queue.add((self, 'mute'))


	# Function to set solo
	#	value: Solo value (True/False)
	def set_solo(self, value):
		if self.midi_learning is True:
			self.enable_midi_learn('solo')
		elif not self.midi_learning:
			if self.zctrls:
				self.zctrls['solo'].set_value(value)
		for strip in self.parent.visible_mixer_strips:
			self.parent.pending_refresh_queue.add((strip, 'solo'))
		self.parent.pending_refresh_queue.add((self.parent.main_mixbus_strip, 'solo'))


	# Function to toggle mono
	#	value: Mono value (True/False)
	def set_mono(self, value):
		if self.zctrls:
			self.zctrls['mono'].set_value(value)
		self.parent.pending_refresh_queue.add((self, 'mono'))


	# Function to toggle mute
	def toggle_mute(self):
		if self.zctrls:
			self.set_mute(int(not self.zctrls['mute'].value))


	# Function to toggle solo
	def toggle_solo(self):
		if self.zctrls:
			self.set_solo(int(not self.zctrls['solo'].value))


	# Function to toggle mono
	def toggle_mono(self):
		if self.zctrls:
			self.set_mono(int(not self.zctrls['mono'].value))


	#--------------------------------------------------------------------------
	# UI event management
	#--------------------------------------------------------------------------

	# Function to handle fader press
	#	event: Mouse event
	def on_fader_press(self, event):
		self.fader_drag_start = event

		if zynthian_gui_config.zyngui.cb_touch(event):
			return "break"

		if self.midi_learning is True:
			self.enable_midi_learn('level')
		self.fader_drag_start = event
		if self.chain:
			self.parent.zyngui.chain_manager.set_active_chain_by_object(self.chain)
			self.parent.highlight_active_chain()


	# Function to handle fader drag
	#	event: Mouse event
	def on_fader_motion(self, event):
		if self.zctrls and self.fader_drag_start:
			self.set_volume(self.zctrls['level'].value + (self.fader_drag_start.y - event.y) / self.fader_height)
			self.fader_drag_start = event
			self.draw_fader()


	# Function to handle mouse wheel down over fader
	#	event: Mouse event
	def on_fader_wheel_down(self, event):
		if self.midi_learning is True:
			self.enable_midi_learn('level')
		self.nudge_volume(-1)


	# Function to handle mouse wheel up over fader
	#	event: Mouse event
	def on_fader_wheel_up(self, event):
		if self.midi_learning is True:
			self.enable_midi_learn('level')
		self.nudge_volume(1)


	# Function to handle mouse click / touch of balance
	#	event: Mouse event
	def on_balance_press(self, event):
		if self.midi_learning is True:
			self.enable_midi_learn('balance')


	# Function to handle mouse wheel down over balance
	#	event: Mouse event
	def on_balance_wheel_down(self, event):
		if self.midi_learning is True:
			self.enable_midi_learn('balance')
		self.nudge_balance(-1)


	# Function to handle mouse wheel up over balance
	#	event: Mouse event
	def on_balance_wheel_up(self, event):
		if self.midi_learning is True:
			self.enable_midi_learn('balance')
		self.nudge_balance(1)


	# Function to handle mixer strip press
	#	event: Mouse event
	def on_strip_press(self, event):
		self.strip_drag_start = event
		self.dragging = False

		if zynthian_gui_config.zyngui.cb_touch(event):
			return "break"


	# Function to handle legend strip release
	def on_strip_release(self, event):
		if zynthian_gui_config.zyngui.cb_touch_release(event):
			return "break"

		if self.dragging:
			self.dragging = False
		elif self.midi_learning:
			return
		else:
			if self.chain:
				self.parent.zyngui.chain_manager.set_active_chain_by_object(self.chain)
			if self.strip_drag_start:
				delta = event.time - self.strip_drag_start.time
				self.strip_drag_start = None
				if delta > 400:
					zynthian_gui_config.zyngui.screens['chain_options'].setup(self.chain_id)
					zynthian_gui_config.zyngui.show_screen('chain_options')
				else:
					zynthian_gui_config.zyngui.chain_control(self.chain_id)


	# Function to handle legend strip drag
	def on_strip_motion(self, event):
		if self.strip_drag_start:
			delta = event.x - self.strip_drag_start.x
			if delta < -self.width and self.parent.mixer_strip_offset + len(self.parent.visible_mixer_strips) < self.parent.number_chains:
				# Dragged more than one strip width to left
				self.parent.mixer_strip_offset += 1
				self.parent.highlight_active_chain()
				self.dragging = True
				self.strip_drag_start.x = event.x
			elif delta > self.width and self.parent.mixer_strip_offset > 0:
				# Dragged more than one strip width to right
				self.parent.mixer_strip_offset -= 1
				self.parent.highlight_active_chain()
				self.dragging = True
				self.strip_drag_start.x = event.x


	# Function to handle mute button release
	#	event: Mouse event
	def on_mute_release(self, event):
		self.toggle_mute()


	# Function to handle solo button release
	#	event: Mouse event
	def on_solo_release(self, event):
		self.toggle_solo()


	# Function to set channel strip MIDI learn mode
	#	mode: True for learning [False|True|zctrl_name]
	def enable_midi_learn(self, mode):
		self.midi_learning = mode
		if mode in ['level', 'balance', 'mute', 'solo']:
			self.zynmixer.enable_midi_learn(self.zctrls[mode])
			self.parent.update_learning(self, mode)
		self.parent.pending_refresh_queue.add((self, None))


#------------------------------------------------------------------------------
# Zynthian Mixer GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_mixer(zynthian_gui_base.zynthian_gui_base):

	def __init__(self):	
		
		super().__init__()

		self.zynmixer = self.zyngui.state_manager.zynmixer
		self.zynmixer.set_ctrl_update_cb(self.ctrl_change_cb)
		self.zynmixer.set_midi_learn_cb(self.exit_midi_learn)
		self.MAIN_MIXBUS_STRIP_INDEX = self.zynmixer.get_max_channels()
		self.chan2strip = [None] * (self.MAIN_MIXBUS_STRIP_INDEX + 1)
		self.highlighted_strip = None # highligted mixer strip object

		self.pending_refresh_queue = set() # List of (strip,control) requiring gui refresh (control=None for whole strip refresh)
		self.midi_learning = False

		visible_chains = zynthian_gui_config.visible_mixer_strips # Maximum quantity of mixer strips to display (Defines strip width. Main always displayed.)
		if visible_chains < 1:
			# Automatic sizing if not defined in config
			if self.width <= 400: visible_chains = 6
			elif self.width <= 600: visible_chains = 8
			elif self.width <= 800: visible_chains = 10
			elif self.width <= 1024: visible_chains = 12
			elif self.width <= 1280: visible_chains = 14
			else: visible_chains = 16

		self.fader_width = (self.width - 6 ) / (visible_chains + 1)
		self.legend_height = self.height * 0.05
		self.edit_height = self.height * 0.1
		
		self.fader_height = self.height - self.edit_height - self.legend_height - 2
		self.fader_bottom = self.height - self.legend_height
		self.fader_top = self.fader_bottom - self.fader_height
		self.balance_control_height = self.fader_height * 0.1
		self.balance_top = self.fader_top
		self.balance_control_width = self.width / 4 # Width of each half of balance control
		self.balance_control_centre = self.fader_width + self.balance_control_width

		# Arrays of GUI elements for mixer strips - Chains + Main
		self.visible_mixer_strips = [None] * visible_chains # List of mixer strip objects indexed by horizontal position on screen
		self.mixer_strip_offset = 0 # Index of first mixer strip displayed on far left

		# Fader Canvas
		self.main_canvas = tkinter.Canvas(self.main_frame,
			height=1,
			width=1,
			bd=0, highlightthickness=0,
			bg = zynthian_gui_config.color_panel_bg)
		self.main_frame.rowconfigure(0, weight=1)
		self.main_frame.columnconfigure(0, weight=1)
		self.main_canvas.grid(row=0, sticky='nsew')

		# Create mixer strip UI objects
		for strip in range(len(self.visible_mixer_strips)):
			self.visible_mixer_strips[strip] = zynthian_gui_mixer_strip(self, 1 + self.fader_width * strip, 0, self.fader_width - 1, self.height)

		self.main_mixbus_strip = zynthian_gui_mixer_strip(self, self.width - self.fader_width - 1, 0, self.fader_width - 1, self.height)
		self.main_mixbus_strip.set_chain("main")
		self.main_mixbus_strip.zctrls = self.zynmixer.zctrls[self.zynmixer.get_max_channels()]

		for chan in range(self.zynmixer.get_max_channels()):
			self.zynmixer.enable_dpm(chan, False)

		if zynthian_gui_config.show_cpu_status:
			self.set_meter_mode(self.METER_CPU)
		else:
			self.set_meter_mode(self.METER_NONE) # Don't show meter in status bar (there are meters all over the mixer)

		self.set_title()
		self.refresh_visible_strips()


	# Redefine set_title
	def set_title(self, title = "Mixer", fg=None, bg=None, timeout = None):
		if self.zyngui.state_manager.last_snapshot_fpath:
			fparts = os.path.splitext(self.zyngui.state_manager.last_snapshot_fpath)
			if self.zyngui.screens['snapshot'].bankless_mode:
				ssname = os.path.basename(fparts[0])
			else:
				ssname = fparts[0].rsplit("/", 1)[-1]
			title +=  ": " + ssname.replace("last_state", "Last State")

		super().set_title(title, fg, bg, timeout)


	# Function to handle hiding display
	def hide(self):
		if not self.zyngui.osc_clients:
			for chan in range(self.zynmixer.get_max_channels()):
				self.zynmixer.enable_dpm(chan, False)
		self.exit_midi_learn()
		super().hide()


	# Function to handle showing display
	def build_view(self):
		self.set_title()
		#TODO: Check user setting to enable DPM
		for chan in range(self.zynmixer.get_max_channels()):
			self.zynmixer.enable_dpm(chan, True)
		self.highlight_active_chain(True)
		self.setup_zynpots()


	# Function to update display, e.g. after geometry changes
	def update_layout(self):
		super().update_layout()
		#TODO: Update mixer layout


	# Function to refresh screen (slow)
	def refresh_status(self, status={}):
		if self.shown:
			super().refresh_status(status)
			self.main_mixbus_strip.draw_dpm()
			self.main_mixbus_strip.refresh_status()
			for strip in self.visible_mixer_strips:
				if not strip.hidden:
					if zynthian_gui_config.enable_dpm:
						strip.draw_dpm()
					strip.refresh_status()


	# Function to refresh display (fast)
	def plot_zctrls(self):
		while self.pending_refresh_queue:
			ctrl = self.pending_refresh_queue.pop()
			ctrl[0].draw_control(ctrl[1])


	#--------------------------------------------------------------------------
	# Mixer Functionality
	#--------------------------------------------------------------------------

	# Function to highlight the selected chain's strip
	def highlight_active_chain(self, refresh=False):
		"""Higlights active chain, redrawing strips if required"""
		chain_keys = sorted(self.zyngui.chain_manager.chains)
		try:
			active_index = chain_keys.index(self.zyngui.chain_manager.active_chain_id)
		except:
			active_index = 0
		if active_index < self.mixer_strip_offset:
			self.mixer_strip_offset = active_index
			refresh = True
		elif active_index >= self.mixer_strip_offset + len(self.visible_mixer_strips) and self.zyngui.chain_manager.active_chain_id != "main":
			self.mixer_strip_offset = active_index - len(self.visible_mixer_strips) + 1
			refresh = True
		#TODO: Handle aux

		strip = None
		if self.zyngui.chain_manager.active_chain_id == "main":
			strip = self.main_mixbus_strip
		else:
			chain = self.zyngui.chain_manager.get_chain(self.zyngui.chain_manager.active_chain_id)
			count = 0
			for s in self.visible_mixer_strips:
				if s.chain:
					count +=1
				if s.chain == chain:
					strip = s
			if strip is None or count < len(chain_keys) and count < len(self.visible_mixer_strips):
				refresh = True
		if refresh:
			chan_strip = self.refresh_visible_strips()
			if chan_strip:
				strip = chan_strip
		if self.highlighted_strip and self.highlighted_strip != strip:
			self.highlighted_strip.set_highlight(False)
		if strip is None:
			strip = self.main_mixbus_strip
		self.highlighted_strip = strip
		if strip:
			strip.set_highlight(True)


	# Function refresh and populate visible mixer strips
	def refresh_visible_strips(self):
		"""Update the structures describing the visible strips
		
		Returns - Active strip object
		"""

		active_strip = None
		strip_index = 0
		for chain_id in self.zyngui.chain_manager.chain_ids_ordered[self.mixer_strip_offset:self.mixer_strip_offset + len(self.visible_mixer_strips)]:
			strip = self.visible_mixer_strips[strip_index]
			strip.set_chain(chain_id)
			if strip.chain.mixer_chan is not None and strip.chain.mixer_chan < len(self.zynmixer.zctrls):
				strip.zctrls = self.zynmixer.zctrls[strip.chain.mixer_chan]
			strip.draw_control()
			if strip.chain.mixer_chan is not None and strip.chain.mixer_chan < len(self.chan2strip):
				self.chan2strip[strip.chain.mixer_chan] = strip
			if chain_id == self.zyngui.chain_manager.active_chain_id:
				active_strip = strip
			strip_index += 1
			
		for strip in self.visible_mixer_strips[strip_index:len(self.visible_mixer_strips)]:
			strip.set_chain(None)
			strip.zctrls = None
			strip.draw_control()

		self.chan2strip[self.MAIN_MIXBUS_STRIP_INDEX] = self.main_mixbus_strip
		self.main_mixbus_strip.draw_control()
		return active_strip


	#--------------------------------------------------------------------------
	# Physical UI Control Management: Pots & switches
	#--------------------------------------------------------------------------

	# Function to handle SELECT button press
	#	type: Button press duration ["S"=Short, "B"=Bold, "L"=Long]
	def switch_select(self, type='S'):
		if type == "S" and not self.midi_learning:
			self.zyngui.chain_control()
		elif type == "B":
			# Chain Options
			self.zyngui.screens['chain_options'].setup(self.zyngui.chain_manager.active_chain_id)
			self.zyngui.show_screen('chain_options')


	# Function to handle BACK action
	def back_action(self):
		if self.midi_learning:
			self.exit_midi_learn()
			return True


	# Function to handle switches press
	#	swi: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	t: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def switch(self, swi, t):
		if swi == 0:
			if t == "S":
				if self.highlighted_strip is not None:
					self.highlighted_strip.toggle_solo()
				return True

		elif swi == 1:
			# This is ugly, but it's the only way i figured for MIDI-learning "mute" without touch.
			# Moving the "learn" button to back is not an option. It's a labeled button on V4!!
			if (t == "S" and not self.midi_learning) or t == "B":
				if self.highlighted_strip is not None:
					self.highlighted_strip.toggle_mute()
				return True

		elif swi == 2:
			if t == 'B':
				if self.midi_learning:
					self.midi_unlearn_action()
					return True

		elif swi == 3:
			self.switch_select(t)
			return True

		return False


	def setup_zynpots(self):
		get_lib_zyncore().setup_behaviour_zynpot(0, 0)
		get_lib_zyncore().setup_behaviour_zynpot(1, 0)
		get_lib_zyncore().setup_behaviour_zynpot(2, 0)
		get_lib_zyncore().setup_behaviour_zynpot(3, 1)


	# Function to handle zynpot CB
	def zynpot_cb(self, i, dval):
		if not self.shown:
			return

		# LAYER encoder adjusts selected chain's level
		if i == 0:
			if self.highlighted_strip is not None:
				self.highlighted_strip.nudge_volume(dval)

		# BACK encoder adjusts selected chain's balance/pan
		if i == 1:
			if self.highlighted_strip is not None:
				self.highlighted_strip.nudge_balance(dval)

		# SNAPSHOT encoder adjusts main mixbus level
		elif i == 2:
			self.main_mixbus_strip.nudge_volume(dval)

		# SELECT encoder moves chain selection
		elif i == 3:
			self.zyngui.chain_manager.next_chain(dval)
			self.highlight_active_chain()



	# Function to handle CUIA ARROW_LEFT
	def arrow_left(self):
		self.zyngui.chain_manager.previous_chain()
		self.highlight_active_chain()


	# Function to handle CUIA ARROW_RIGHT
	def arrow_right(self):
		self.zyngui.chain_manager.next_chain()
		self.highlight_active_chain()


	# Function to handle CUIA ARROW_UP
	def arrow_up(self):
		if self.highlighted_strip is not None:
			self.highlighted_strip.nudge_volume(1)
		

	# Function to handle CUIA ARROW_DOWN
	def arrow_down(self):
		if self.highlighted_strip is not None:
			self.highlighted_strip.nudge_volume(-1)


	#--------------------------------------------------------------------------
	# GUI Event Management
	#--------------------------------------------------------------------------


	# Function to override topbar touch action
	def topbar_touch_action(self):
		# Avoid toggle mute when touchbar pressed
		if self.midi_learning:
			super().topbar_touch_action()
		else:
			self.topbar_bold_touch_action()


	# Function to handle mouse wheel event when not over fader strip
	#	event: Mouse event
	def on_wheel(self, event):
		if event.num == 5:
			if self.mixer_strip_offset < 1:
				return
			self.mixer_strip_offset -= 1
		elif event.num == 4:
			if self.mixer_strip_offset +  len(self.visible_mixer_strips) >= self.zyngui.chain_manager.get_chain_count() - 1:
				return
			self.mixer_strip_offset += 1
		self.highlight_active_chain()


	def ctrl_change_cb(self, chan, ctrl, value):
		if chan is not None:
			self.pending_refresh_queue.add((self.chan2strip[chan], ctrl))
			self.pending_refresh_queue.add((self.chan2strip[self.MAIN_MIXBUS_STRIP_INDEX], "solo"))


	#--------------------------------------------------------------------------
	# MIDI learning management
	#--------------------------------------------------------------------------

	# Pre-select all controls in a chain to allow selection of actual control to MIDI learn
	def toggle_midi_learn(self):
		self.midi_learning = not self.midi_learning
		for strip in self.visible_mixer_strips:
			if strip.chain:
				strip.enable_midi_learn(self.midi_learning)
		self.main_mixbus_strip.enable_midi_learn(self.midi_learning)


	# Respond to a strip being configured to midi learn
	def update_learning(self, modified_strip, control):
		for strip in self.visible_mixer_strips:
			if strip != modified_strip:
				strip.enable_midi_learn(False)
		if modified_strip != self.main_mixbus_strip:
			self.main_mixbus_strip.enable_midi_learn(False)

    
	def exit_midi_learn(self):
		for strip in self.visible_mixer_strips:
			strip.enable_midi_learn(False)
		self.main_mixbus_strip.enable_midi_learn(False)
		self.midi_learning = False


	def midi_unlearn_action(self):
		if self.zynmixer.midi_learn_zctrl:
			self.zyngui.show_confirm(f"Do you want to clear MIDI-learn for '{self.zynmixer.midi_learn_zctrl.name}' control?", self.zynmixer.midi_unlearn, self.zynmixer.midi_learn_zctrl)
		else:
			self.zyngui.show_confirm("Do you want to clean MIDI-learn for ALL mixer controls?", self.zynmixer.midi_unlearn_all)


#--------------------------------------------------------------------------
