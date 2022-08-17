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
from turtle import pos
from zyngine.zynthian_engine_sooperlooper import zynthian_engine_sooperlooper
from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base
import liblo
from threading import Timer
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
		self.selected_loop = 0
		self.loop_count = 0
		self.click_timer = None
		self.row_height = 20

		self.input_level_canvas = tkinter.Canvas(self,
			height = 1,
			bd=0,
			highlightthickness=0,
			bg=self.SLIDER_BG)
		self.input_level_fg = self.input_level_canvas.create_rectangle(
			0, 0, 0, self.row_height,
			fill = '#0a0')
		self.input_level_label = self.input_level_canvas.create_text(
			1, 10,
			fill = self.SLIDER_TEXT,
			text = 'input level',
			anchor='w'
		)
		self.threshold_line = self.input_level_canvas.create_line(
			0, 0, 0, self.row_height,
			fill = '#ff0',
			width = 2
		)
		self.in_gain_marker = self.input_level_canvas.create_polygon(
			-self.tri_size,0,
			self.tri_size,0,
			0,self.tri_size,
			fill='#d00'
		)

		self.pos_canvas = []
		for loop in range(zynthian_engine_sooperlooper.MAX_LOOPS):
			pos_canvas = tkinter.Canvas(self,
				height=1,
				bd=0,
				highlightthickness=0,
				bg=self.SLIDER_BG)
			pos_label = pos_canvas.create_text(
				0, 4,
				fill = self.SLIDER_TEXT,
				text = ' 0.00 / 0.00',
				anchor = 'nw'
			)
			pos_line = pos_canvas.create_line(
				0, 0, 0, self.row_height,
				fill='#ff0',
				width = 2
			)
			pos_border = pos_canvas.create_rectangle(
				2,2,2,2,
				width = 2,
				outline = zynthian_gui_config.color_on,
				state = tkinter.HIDDEN)

			mute_canvas = tkinter.Canvas( self,
				height=self.row_height,
				bd=0,
				highlightthickness=0,
				bg=self.SLIDER_BG
			)
			mute_canvas.create_text(
				4, 4,
				anchor = 'nw',
				text='mute',
				fill=self.SLIDER_TEXT,
				font=(zynthian_gui_config.font_family, int(0.7 * zynthian_gui_config.font_size))
			)
			self.pos_canvas.append({'canvas':pos_canvas, 'border':pos_border, 'label':pos_label, 'line':pos_line, 'mute':mute_canvas})
			pos_canvas.bind("<ButtonPress-1>", self.on_loop_click)
			pos_canvas.bind("<ButtonRelease-1>", self.on_loop_release)
			mute_canvas.bind("<ButtonPress-1>", self.on_loop_click)

		self.add_canvas = tkinter.Canvas( self,
			height=self.row_height,
			bd=0,
			highlightthickness=0,
			bg=self.SLIDER_BG
		)
		self.add_canvas.create_text(
			1, 2,
			anchor = 'nw',
			text='add loop',
			fill=self.SLIDER_TEXT,
			font=(zynthian_gui_config.font_family, int(0.7 * zynthian_gui_config.font_size))
		)
		self.add_canvas.bind('<ButtonPress-1>', self.on_add_click)

		self.wet_canvas = tkinter.Canvas(self,
			height = 1,
			bd=0,
			highlightthickness=0,
			bg=self.SLIDER_BG)
		self.wet_fg = self.wet_canvas.create_rectangle(
			0, 0, 0, self.row_height,
			fill = self.SLIDER_FG
		)
		self.wet_label = self.wet_canvas.create_text(
			1, 2,
			fill = self.SLIDER_TEXT,
			text = 'wet',
			anchor='nw'
		)

		self.dry_canvas = tkinter.Canvas(self,
			height = 1,
			bd=0,
			highlightthickness=0,
			bg=self.SLIDER_BG)
		self.dry_fg = self.dry_canvas.create_rectangle(
			0, 0, 0, self.row_height,
			fill = self.SLIDER_FG
		)
		self.dry_label = self.dry_canvas.create_text(
			1, 2,
			fill = self.SLIDER_TEXT,
			text = 'dry (monitor)',
			anchor='nw'
		)

		self.feedback_canvas = tkinter.Canvas(self,
			height = 1,
			bd=0,
			highlightthickness=0,
			bg=self.SLIDER_BG)
		self.feedback_fg = self.feedback_canvas.create_rectangle(
			0, 0, 0, self.row_height,
			fill = self.SLIDER_FG
		)
		self.feedback_label = self.feedback_canvas.create_text(
			1, 2,
			fill = self.SLIDER_TEXT,
			text = 'feedback',
			anchor='nw'
		)


		self.button_frame = tkinter.Frame(self, bg='#000')
		for col in range(4):
			self.button_frame.columnconfigure(col, weight=1, uniform='btn_col')

		self.buttons = {}
		for i,btn in enumerate(['record','overdub','multiply','replace','substitute','insert','undo','redo','trigger','oneshot','reverse','pause']):
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
			row = int(i / 4)
			col = i % 4
			self.buttons[btn].grid(row=row, column=col, sticky='news', padx=(0,1), pady=(0,1))
			self.button_frame.rowconfigure(row, weight=1, uniform='btn_row')
			self.button_frame.columnconfigure(col, weight=1, uniform='btn_col')

		for col in range(4):
			self.columnconfigure(col, weight=1, uniform='col')
		self.rowconfigure(zynthian_engine_sooperlooper.MAX_LOOPS + 1, weight=1)

		self.button_frame.grid(columnspan=4, sticky='news', padx=(1,1)) #1
		for loop in range(zynthian_engine_sooperlooper.MAX_LOOPS):
			self.pos_canvas[loop]['canvas'].grid(row=1 + loop, columnspan=3, sticky='news', padx=(1,1), pady=(1,0))
			self.pos_canvas[loop]['mute'].grid(row=1 + loop, column=3, sticky='news', padx=(1,1), pady=(1,0))
			self.pos_canvas[loop]['canvas'].grid_remove()
			self.pos_canvas[loop]['mute'].grid_remove()

		self.add_canvas.grid(row=zynthian_engine_sooperlooper.MAX_LOOPS, sticky='news', padx=(1,1), pady=(1,1))
		self.input_level_canvas.grid(row=2 + zynthian_engine_sooperlooper.MAX_LOOPS, columnspan=2, sticky='news', padx=(1,1), pady=(1,1))
		self.feedback_canvas.grid(row=2 + zynthian_engine_sooperlooper.MAX_LOOPS, column=2, columnspan=2, sticky='news', padx=(1,1), pady=(1,1))
		self.wet_canvas.grid(row=3 + zynthian_engine_sooperlooper.MAX_LOOPS, columnspan=2, sticky='news', padx=(1,1), pady=(1,1))
		self.dry_canvas.grid(row=3 + zynthian_engine_sooperlooper.MAX_LOOPS, column=2, columnspan=2, sticky='news', padx=(1,1), pady=(1,1))

		self.symbol_map = {
			self.dry_canvas:'dry',
			self.wet_canvas:'wet',
			self.feedback_canvas:'feedback',
			self.input_level_canvas:'rec_thresh',
		}

		for slider in self.symbol_map:
			slider.bind("<Button-4>", self.on_slider_wheel)
			slider.bind("<Button-5>", self.on_slider_wheel)
			slider.bind("<ButtonPress-1>", self.on_slider_press)
			slider.bind("<ButtonRelease-1>", self.on_slider_release)
			slider.bind("<B1-Motion>", self.on_slider_motion)


	def on_size(self, event):
		super().on_size(event)
		self.row_height = self.height  // (zynthian_engine_sooperlooper.MAX_LOOPS + 5)
		self.rowconfigure(0, minsize=self.row_height * 3)
		for row in range(1, zynthian_engine_sooperlooper.MAX_LOOPS + 1):
			self.rowconfigure(row, minsize=self.row_height)
		self.rowconfigure(row + 2, minsize=self.row_height)
		self.rowconfigure(row + 3, minsize=self.row_height)


	def on_loop_click(self, event):
		for loop,slider in enumerate(self.pos_canvas):
			if event.widget == slider['canvas']:
				self.selected_loop = loop
				liblo.send('osc.udp://localhost:9951', '/set', ('s', 'selected_loop_num'), ('f', loop))
				self.click_timer = Timer(1.4, self.on_click_timer)
				self.click_timer.start()
			if event.widget == slider['mute']:
				liblo.send('osc.udp://localhost:9951', '/sl/{}/hit'.format(loop), ('s', 'mute'))


	def on_loop_release(self, event):
		if self.click_timer and self.click_timer.isAlive():
			self.click_timer.cancel()


	def on_click_timer(self):
		if self.monitors['loop_count'] > 1:
			self.zyngui.show_confirm("Remove loop {}?".format(self.selected_loop + 1), self.remove_loop)


	def on_add_click(self, event):
		liblo.send('osc.udp://localhost:9951', '/loop_add', ('i', 2), ('f', 30), ('i', 0))


	def remove_loop(self, params):
		liblo.send('osc.udp://localhost:9951', '/loop_del', ('i', self.selected_loop))


	def on_button(self, btn):
		liblo.send('osc.udp://localhost:9951', '/sl/-3/hit', ('s', btn))


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


	def refresh_gui(self):
		#TODO: Change GUI on event, not on periodic refresh
		for loop in range(zynthian_engine_sooperlooper.MAX_LOOPS):
			loop_pos_symbol = 'loop_pos_{}'.format(loop)
			loop_len_symbol = 'loop_len_{}'.format(loop)
			state_symbol = 'state_{}'.format(loop)
			if loop_pos_symbol in self.monitors and loop_len_symbol in self.monitors and state_symbol in self.monitors:
				len = self.monitors[loop_len_symbol]
				pos = self.monitors[loop_pos_symbol]
				state = self.monitors[state_symbol]
				if state in [2, 5, 6, 7, 8, 9, 13]:
					bg = self.BUTTON_ASSERTED
				elif state in [1, 3]:
					bg='#c90'
				elif state in [0, 10 , 14, 20]:
					bg = '#444'
				else:
					bg = '#090'
				self.pos_canvas[loop]['canvas'].coords(self.pos_canvas[loop]['border'], 2, 2, self.pos_canvas[loop]['canvas'].winfo_width() - 2, self.row_height - 2)
				if loop == self.selected_loop:
					self.pos_canvas[loop]['canvas'].itemconfigure(self.pos_canvas[loop]['border'], state=tkinter.NORMAL)
				else:
					self.pos_canvas[loop]['canvas'].itemconfigure(self.pos_canvas[loop]['border'], state=tkinter.HIDDEN)
				x = 0
				if len:
					x = int(pos / len * self.pos_canvas[loop]['canvas'].winfo_width())
				self.pos_canvas[loop]['canvas'].coords(self.pos_canvas[loop]['line'], x, 0, x, self.row_height)
				self.pos_canvas[loop]['canvas'].configure(bg=bg)
				self.pos_canvas[loop]['canvas'].itemconfigure(self.pos_canvas[loop]['label'], text=' {:.2f} / {:.2f} {}'.format(pos, len, zynthian_engine_sooperlooper.SL_STATES[state]['name']))
				if state in [10,20]:
					self.pos_canvas[loop]['mute']['bg'] = self.BUTTON_ASSERTED
				else:
					self.pos_canvas[loop]['mute']['bg'] = self.SLIDER_BG
		try:
			free = self.monitors['free_time']
			self.input_level_canvas.coords(self.input_level_fg, 0, 0, int(self.width * self.monitors['in_peak_meter']), self.row_height)
			thresh_x = int(self.monitors['rec_thresh'] * self.input_level_canvas.winfo_width())
			self.input_level_canvas.coords(self.threshold_line, thresh_x, 0, thresh_x, self.row_height)
			x = int(self.monitors['dry'] * self.dry_canvas.winfo_width())
			self.dry_canvas.coords(self.dry_fg, 0, 0, x, self.row_height)
			x = int(self.monitors['wet'] * self.wet_canvas.winfo_width())
			self.wet_canvas.coords(self.wet_fg, 0, 0, x, self.row_height)
			x = int(self.monitors['feedback'] * self.feedback_canvas.winfo_width())
			self.feedback_canvas.coords(self.feedback_fg, 0, 0, x, self.row_height)
			x = int(self.monitors['input_gain'] * self.input_level_canvas.winfo_width())
			self.input_level_canvas.coords(self.in_gain_marker, x-self.tri_size, 0, x+self.tri_size, 0, x, self.tri_size)
			if self.monitors['rate_output'] < 0:
				self.buttons['reverse'].configure(bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
			else:
				self.buttons['reverse'].configure(bg=self.SLIDER_BG, highlightbackground=self.SLIDER_BG, activebackground=self.SLIDER_BG)
			state = self.monitors['state']
			if state != self.state or self.selected_loop != self.monitors['selected_loop_num']:
				for b in self.buttons:
					if b != 'reverse':
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
				elif state == 12:
					self.buttons['oneshot'].configure(bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
				elif state == 13:
					self.buttons['substitute'].configure(bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
					self.buttons['substitute'].configure(bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
				elif state == 14:
					self.buttons['pause'].configure(bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
				self.state = state
				self.selected_loop = int(self.monitors['selected_loop_num'])
				#TODO: Indicate selected loop
			if self.loop_count != self.monitors['loop_count']:
				self.loop_count = self.monitors['loop_count']
				for loop in range(self.loop_count):
					self.pos_canvas[loop]['canvas'].grid()
					self.pos_canvas[loop]['mute'].grid()
				for loop in range(self.loop_count, zynthian_engine_sooperlooper.MAX_LOOPS):
					self.pos_canvas[loop]['canvas'].grid_remove()
					self.pos_canvas[loop]['mute'].grid_remove()
				if self.loop_count < zynthian_engine_sooperlooper.MAX_LOOPS:
					self.add_canvas.grid()
				else:
					self.add_canvas.grid_remove()

		except KeyError:
			logging.debug("KeyError ignored")
		except Exception as e:
			logging.warning(e)

