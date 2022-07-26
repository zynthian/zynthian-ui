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
import logging
from zyngine.zynthian_engine_sooperlooper import zynthian_engine_sooperlooper
from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base
import liblo
from functools import partial


class zynthian_widget_sooperlooper(zynthian_widget_base.zynthian_widget_base):
	
	SLIDER_BG = '#444'
	SLIDER_FG = '#26b'
	SLIDER_TEXT = '#ccc'
	BUTTON_ASSERTED = '#900'

	def __init__(self, parent):
		super().__init__(parent)

		self.tri_size = 5
		self.slider_press_event = None
		self.state = 0

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
			font=(zynthian_gui_config.font_family, int(0.7 * zynthian_gui_config.font_size)),
			text='avail: 00:00.00',
			bg=zynthian_gui_config.color_bg,
			fg=self.SLIDER_TEXT,
			anchor='w'
		)

		self.loop_len_label = tkinter.Label(self,
			font=(zynthian_gui_config.font_family, int(0.7 * zynthian_gui_config.font_size)),
			text='len: 00:00.00',
			bg=zynthian_gui_config.color_bg,
			fg=self.SLIDER_TEXT,
			anchor='e',
		)

		self.button_frame = tkinter.Frame(self, bg='#000')
		for col in range(4):
			self.button_frame.columnconfigure(col, weight=1, uniform='btn_col')

		self.buttons = {}
		for i,btn in enumerate(['record','overdub','multiply','replace','substitute','insert','undo','redo','trigger','oneshot','mute','pause']):
			if btn == 'substitute':
				fs = int(0.5 * zynthian_gui_config.font_size)
			else:
				fs = int(0.7 * zynthian_gui_config.font_size)
			command = partial(lambda a:self.on_button(a), btn)
			self.buttons[btn] = tkinter.Button(self.button_frame,
				text=btn,
				background=self.SLIDER_BG,
				activebackground=self.SLIDER_BG,
				highlightbackground=self.SLIDER_BG,
				foreground=self.SLIDER_TEXT,
				activeforeground=self.SLIDER_TEXT,
				highlightcolor=self.SLIDER_TEXT,
				bd=0,
				relief=tkinter.FLAT,
				overrelief=tkinter.FLAT,
				font=(zynthian_gui_config.font_family, fs),
				command=command
			)
			self.buttons[btn].grid(row=int(i/4), column=i%4, sticky='nsew', padx=(0,1), pady=(0,1))

		self.canvas_reverse = tkinter.Canvas( self,
			height=20,
			bd=0,
			highlightthickness=0,
			bg=self.SLIDER_BG
		)
		self.text_reverse = self.canvas_reverse.create_text(
			1, 10,
			anchor = 'w',
			text='reverse',
			fill=self.SLIDER_TEXT,
			font=(zynthian_gui_config.font_family, int(0.7 * zynthian_gui_config.font_size))
		)
		self.canvas_reverse.bind("<ButtonPress-1>", self.toggle_reverse)

		for col in range(4):
			self.columnconfigure(col, weight=1, uniform='col')

		self.state_label.grid(columnspan=4, sticky='ew')
		self.button_frame.grid(columnspan=4, sticky='ew')
		self.loop_len_label.grid(row=2, column=0, columnspan=2, sticky='w')
		self.available_label.grid(row=2, column=2, columnspan=2, sticky='w')
		self.pos_canvas.grid(columnspan=3, sticky='ew', padx=(2,1))
		self.canvas_reverse.grid(row=3, column=3, sticky='ew', padx=(1,2))
		self.input_level_canvas.grid(columnspan=2,sticky='ew', padx=(2,1), pady=(2,2))
		self.feedback_canvas.grid(row=4, column=2, columnspan=2, sticky='ew', padx=(1,2), pady=(2,2))
		self.wet_canvas.grid(columnspan=2, sticky='ew', padx=(2,1), )
		self.dry_canvas.grid(row=5, column=2, columnspan=2, sticky='ew', padx=(1,2))


		self.symbol_map = {
			self.dry_canvas:'dry',
			self.wet_canvas:'wet',
			self.feedback_canvas:'feedback',
			self.input_level_canvas:'input_gain'
		}

		for slider in self.symbol_map:
			slider.bind("<Button-4>", self.on_slider_wheel)
			slider.bind("<Button-5>", self.on_slider_wheel)
			slider.bind("<ButtonPress-1>", self.on_slider_press)
			slider.bind("<ButtonRelease-1>", self.on_slider_release)
			slider.bind("<B1-Motion>", self.on_slider_motion)


	def on_button(self, btn):
		liblo.send('osc.udp://zynthian1:9951', '/sl/-3/hit', ('s', btn))


	def toggle_reverse(self, event):
		liblo.send('osc.udp://zynthian1:9951', '/sl/-3/hit', ('s', 'reverse'))


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
				zctrl.set_value(zctrl.value + (event.x - self.slider_press_event.x) / event.widget.winfo_width())
				self.slider_press_event = event
			except Exception as e:
				logging.warning(e)


	def on_size(self, event):
		if event.width == self.width and event.height == self.height:
			return
		super().on_size(event)
		#self.input_level_canvas.configure(width=self.width)
		#self.pos_canvas.configure(width=self.width)
		self.tri_size = 5 #TODO: Scale widgets like marker triangle


	def refresh_gui(self):
		#TODO: Change GUI on event, not on periodic refresh
		try:
			state = int(self.monitors['state'])
			if state in [2, 5, 6, 7, 8, 9, 13]:
				self.state_label.configure(text = zynthian_engine_sooperlooper.SL_STATES[state]['name'], bg=self.BUTTON_ASSERTED)
			elif state in [1, 3]:
				self.state_label.configure(text = zynthian_engine_sooperlooper.SL_STATES[state]['name'], bg='#c90')
			elif state in [0, 10 , 14]:
				self.state_label.configure(text = zynthian_engine_sooperlooper.SL_STATES[state]['name'], bg='#444')
			else:
				self.state_label.configure(text = zynthian_engine_sooperlooper.SL_STATES[state]['name'], bg='#090')
			loop_len = self.monitors['loop_len']
			loop_pos = self.monitors['loop_pos']
			self.pos_canvas.itemconfigure(self.pos_label, text='pos: {:02}:{:05.2f}'.format(int(loop_pos/60), loop_pos%60))
			self.loop_len_label.configure(text='len: {:02}:{:05.2f}'.format(int(loop_len/60), loop_len%60))
			free = self.monitors['free_time']
			self.available_label.configure(text='avail: {:02}:{:05.2f}'.format(int(free/60), free%60))
			if loop_len:
				x = int(loop_pos / loop_len * self.pos_canvas.winfo_width())
				self.pos_canvas.coords(self.pos_line, x, 0, x, 20)
			self.input_level_canvas.coords(self.input_level_fg, 0, 0, int(self.width * self.monitors['in_peak_meter']), 20)
			thresh_x = int(self.monitors['rec_thresh'] * self.input_level_canvas.winfo_width())
			self.input_level_canvas.coords(self.threshold_line, thresh_x, 0, thresh_x, 20)
			x = int(self.monitors['dry'] * self.dry_canvas.winfo_width())
			self.dry_canvas.coords(self.dry_fg, 0, 0, x, 20)
			x = int(self.monitors['wet'] * self.wet_canvas.winfo_width())
			self.wet_canvas.coords(self.wet_fg, 0, 0, x, 20)
			x = int(self.monitors['feedback'] * self.feedback_canvas.winfo_width())
			self.feedback_canvas.coords(self.feedback_fg, 0, 0, x, 20)
			x = int(self.monitors['input_gain'] * self.input_level_canvas.winfo_width())
			self.input_level_canvas.coords(self.in_gain_marker, x-self.tri_size, 0, x+self.tri_size, 0, x, self.tri_size)
			if self.monitors['rate_output'] < 0:
				self.canvas_reverse.configure(bg=self.BUTTON_ASSERTED)
			else:
				self.canvas_reverse.configure(bg=self.SLIDER_BG)
			state = self.monitors['state']
			if state != self.state:
				for b in self.buttons:
					self.buttons[b].configure(bg=self.SLIDER_BG, highlightbackground=self.SLIDER_BG, activebackground=self.SLIDER_BG)
				if state == 2:
					self.buttons['record'].configure(bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
				elif state == 5:
					self.buttons['overdub'].configure(bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
				elif state == 6:
					self.buttons['multiply'].configure(bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
				elif state == 7:
					self.buttons['insert'].configure(bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
				elif state == 8:
					self.buttons['replace'].configure(bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
				elif state == 10:
					self.buttons['mute'].configure(bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
				elif state == 12:
					self.buttons['oneshot'].configure(bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
				elif state == 13:
					self.buttons['substitute'].configure(bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
				elif state == 14:
					self.buttons['pause'].configure(bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
				self.state = state


		except KeyError:
			logging.debug("KeyError ignored")
		except Exception as e:
			logging.warning(e)
