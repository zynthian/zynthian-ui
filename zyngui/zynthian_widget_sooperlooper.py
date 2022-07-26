#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian Widget Class for "Zynthian Audio Player" (zynaudioplayer#one)
# 
# Copyright (C) 2022 Brian Walton <riban@zynthian.org>
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

import tkinter
import re
import string
import logging
from zyngine.zynthian_engine_sooperlooper import zynthian_engine_sooperlooper
from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base


class zynthian_widget_sooperlooper(zynthian_widget_base.zynthian_widget_base):
	
	SLIDER_BG = '#444'
	SLIDER_FG = '#26b'
	SLIDER_TEXT = '#ccc'

	def __init__(self, parent):
		super().__init__(parent)

		self.tri_size = 5
		self.slider_press_event = None

		self.input_level_canvas = tkinter.Canvas(self,
			height = 20,
			bd=0,
			highlightthickness=0,
			bg=self.SLIDER_BG)
		self.input_level_fg = self.input_level_canvas.create_rectangle(
			0, 0, 0, 20,
			fill = '#0a0')
		self.input_level_label = self.input_level_canvas.create_text(
			1, 10,
			fill = self.SLIDER_TEXT,
			text = 'input level',
			anchor='w'
		)
		self.threshold_line = self.input_level_canvas.create_line(
			0, 0, 0, 20,
			fill = '#ff0',
			width = 2
		)
		self.in_gain_marker = self.input_level_canvas.create_polygon(
			-self.tri_size,0,
			self.tri_size,0,
			0,self.tri_size,
			fill='#d00'
		)

		self.pos_canvas = tkinter.Canvas(self,
			height=20,
			bd=0,
			highlightthickness=0,
			bg=self.SLIDER_BG)
		self.pos_label = self.pos_canvas.create_text(
			1, 10,
			fill = self.SLIDER_TEXT,
			text = 'pos: 0.0',
			anchor = 'w'
		)
		self.pos_line = self.pos_canvas.create_line(
			0, 0, 0, 20,
			fill='#0a0',
			width = 2
		)

		self.wet_canvas = tkinter.Canvas(self,
			height = 20,
			bd=0,
			highlightthickness=0,
			bg=self.SLIDER_BG)
		self.wet_fg = self.wet_canvas.create_rectangle(
			0, 0, 0, 20,
			fill = self.SLIDER_FG
		)
		self.wet_label = self.wet_canvas.create_text(
			1, 10,
			fill = self.SLIDER_TEXT,
			text = 'wet',
			anchor='w'
		)

		self.dry_canvas = tkinter.Canvas(self,
			height = 20,
			bd=0,
			highlightthickness=0,
			bg=self.SLIDER_BG)
		self.dry_fg = self.dry_canvas.create_rectangle(
			0, 0, 0, 20,
			fill = self.SLIDER_FG
		)
		self.dry_label = self.dry_canvas.create_text(
			1, 10,
			fill = self.SLIDER_TEXT,
			text = 'dry (monitor)',
			anchor='w'
		)

		self.feedback_canvas = tkinter.Canvas(self,
			height = 20,
			bd=0,
			highlightthickness=0,
			bg=self.SLIDER_BG)
		self.feedback_fg = self.feedback_canvas.create_rectangle(
			0, 0, 0, 20,
			fill = self.SLIDER_FG
		)
		self.feedback_label = self.feedback_canvas.create_text(
			1, 10,
			fill = self.SLIDER_TEXT,
			text = 'feedback',
			anchor='w'
		)

		self.state_label = tkinter.Label(self,
			font=(zynthian_gui_config.font_family, zynthian_gui_config.font_size),
			text='',
			bg=zynthian_gui_config.color_bg,
			fg='#fff',
			anchor='w',
			width=14
		)

		self.available_label = tkinter.Label(self,
			font=(zynthian_gui_config.font_family, int(0.8 * zynthian_gui_config.font_size)),
			text='avail: 0.0',
			bg=zynthian_gui_config.color_bg,
			fg='#999',
			anchor='w'
		)

		self.loop_len_label = tkinter.Label(self,
			font=(zynthian_gui_config.font_family, int(0.8 * zynthian_gui_config.font_size)),
			text='len: 0.0',
			bg=zynthian_gui_config.color_bg,
			fg='#999',
			anchor='e'
		)

		self.state_label.grid(row=0, columnspan=2, sticky='w')
		self.input_level_canvas.grid(row=1, columnspan=2,sticky='ew', padx=(2,2), pady=(2,2))
		self.available_label.grid(row=2, column=0, sticky='w')
		self.loop_len_label.grid(row=2, column=1, sticky='e', padx=(0,2))
		self.pos_canvas.grid(row=3, columnspan=2, sticky='ew', padx=(2,2))
		self.feedback_canvas.grid(columnspan=2, sticky='ew', padx=(2,2), pady=(2,0))
		self.wet_canvas.grid(columnspan=2, sticky='ew', padx=(2,2), pady=(2,0))
		self.dry_canvas.grid(columnspan=2, sticky='ew', padx=(2,2), pady=(2,0))


		self.symbol_map = {
			self.dry_canvas:'dry',
			self.wet_canvas:'wet',
			self.feedback_canvas:'feedback',
			self.input_level_canvas:'input_gain'
		}

		for slider in self.symbol_map:
			slider.bind("<Button-4>",self.on_slider_wheel)
			slider.bind("<Button-5>",self.on_slider_wheel)
			slider.bind("<ButtonPress-1>", self.on_slider_press)
			slider.bind("<ButtonRelease-1>", self.on_slider_release)
			slider.bind("<B1-Motion>", self.on_slider_motion)


	def on_slider_wheel(self, event):
		try:
			symbol = self.symbol_map[event.widget]
			if event.num == 5 or event.delta == -120:
				self.zyngui_control.layers[0].controllers_dict[symbol].nudge(-1)
			if event.num == 4 or event.delta == 120:
				self.zyngui_control.layers[0].controllers_dict[symbol].nudge(1)
		except Exception as e:
			logging.warning(e)


	def on_slider_press(self, event):
		self.slider_press_event = event


	def on_slider_release(self, event):
		self.slider_press_event = None


	def on_slider_motion(self, event):
		if self.slider_press_event:
			try:
				symbol = self.symbol_map[event.widget]
				zctrl = self.zyngui_control.layers[0].controllers_dict[symbol]
				zctrl.set_value(zctrl.value + (event.x - self.slider_press_event.x) / (self.width - 4))
				self.slider_press_event = event
			except Exception as e:
				logging.warning(e)


	def on_size(self, event):
		if event.width == self.width and event.height == self.height:
			return
		super().on_size(event)
		self.input_level_canvas.configure(width=self.width)
		self.pos_canvas.configure(width=self.width)
		self.tri_size = 5 #TODO: Scale widgets like marker triangle


	def refresh_gui(self):
		try:
			state = int(self.monitors['state'])
			if state in [2, 5, 6, 7, 8, 9, 13]:
				self.state_label.configure(text = zynthian_engine_sooperlooper.SL_STATES[state]['name'], bg='#900')
			elif state in [1, 3]:
				self.state_label.configure(text = zynthian_engine_sooperlooper.SL_STATES[state]['name'], bg='#c90')
			elif state in [0, 10 , 14]:
				self.state_label.configure(text = zynthian_engine_sooperlooper.SL_STATES[state]['name'], bg='#444')
			else:
				self.state_label.configure(text = zynthian_engine_sooperlooper.SL_STATES[state]['name'], bg='#090')
			loop_len = self.monitors['loop_len']
			loop_pos = self.monitors['loop_pos']
			self.pos_canvas.itemconfigure(self.pos_label, text = 'pos: {:.1f}'.format(loop_pos))
			self.loop_len_label.configure(text='len: {:.1f}s'.format(loop_len))
			self.available_label.configure(text='avail: {}s'.format(int(self.monitors['free_time'])))
			if loop_len:
				pos_x = int(loop_pos / loop_len * (self.width - 4))
				self.pos_canvas.coords(self.pos_line, pos_x, 0, pos_x, 20)
			self.input_level_canvas.coords(self.input_level_fg, 0, 0, int(self.width * self.monitors['in_peak_meter']), 20)
			thresh_x = int(self.monitors['rec_thresh'] * (self.width - 4))
			self.input_level_canvas.coords(self.threshold_line, thresh_x, 0, thresh_x, 20)
			x = int(self.monitors['dry'] * (self.width - 4))
			self.dry_canvas.coords(self.dry_fg, 0, 0, x, 20)
			x = int(self.monitors['wet'] * (self.width - 4))
			self.wet_canvas.coords(self.wet_fg, 0, 0, x, 20)
			x = int(self.monitors['feedback'] * (self.width - 4))
			self.feedback_canvas.coords(self.feedback_fg, 0, 0, x, 20)
			x = int(self.monitors['input_gain'] * (self.width - 4))
			self.input_level_canvas.coords(self.in_gain_marker, x-self.tri_size, 0, x+self.tri_size, 0, x, self.tri_size)

		except KeyError:
			logging.debug("KeyError ignored")
		except Exception as e:
			logging.warning(e)
