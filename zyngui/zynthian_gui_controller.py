#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Controller Class
#
# Copyright (C) 2015-2024 Fernando Moyano <jofemodo@zynthian.org>
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

import math
import tkinter
import logging
from datetime import datetime
from tkinter import font as tkFont

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore
from zyngui import zynthian_gui_config

# ------------------------------------------------------------------------------
# Controller GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_controller(tkinter.Canvas):
	
	GUI_CTRL_NONE		= 0
	GUI_CTRL_ARC		= 1
	GUI_CTRL_TRIANGLE	= 2
	GUI_CTRL_RECTANGLE	= 3

	# Instantiate an instance of a gui controller
	#  index: Index of zynpot
	#  parent: GUI element hosting this controller
	#  zctrl: zynthian_controller to control
	#  hidden: True to disable GUI display (only use zynpot/zctrl interface)
	#  selcounter: True to configure as a counter - no value graph and value is 1-based (otherwise zero-based)
	#  graph: Type of graph to plot [GUI_CTRL_NONE, GUI_CTRL_ARC, GUI_CTRL_TRIANGLE, GUI_CTRL_RECTANGLE] Default: GUI_CTRL_ARC
	def __init__(self, index, parent, zctrl, hidden=False, selcounter=False, graph=zynthian_gui_config.ctrl_graph, orientation=None):
		self.zyngui = zynthian_gui_config.zyngui
		self.zctrl = None

		self.step = 0
		self.selector_counter = selcounter
		self.value_plot = 0  # Normalised position of plot start point
		self.value_print = None
		self.value_font_size = zynthian_gui_config.font_size
		if orientation:
			self.vertical = (orientation == 'vertical' and not selcounter)
		else:
			self.vertical = (zynthian_gui_config.layout['ctrl_orientation'] == 'vertical' and not selcounter)

		self.hidden = hidden  # Always hidden => in such a case, self.shown means "enabled"
		self.shown = False  # Currently shown/enabled
		self.refresh_plot_value = False
		self.title = ""
		self.preselection = None

		self.pixels_per_div = 1
		self.touch_accel = 300

		# Initialise dimensions here but set to correct values in on_size
		self.title_width = 1

		self.index = index

		# Create Canvas
		if not hidden:
			super().__init__(parent,
				width=1,
				height=1,
				bd=0,
				highlightthickness=0,
				bg=zynthian_gui_config.color_panel_bg)
			if graph == self.GUI_CTRL_ARC:
				self.graph = self.create_arc(0, 0, 1, 1,
					style=tkinter.ARC,
					outline=zynthian_gui_config.color_ctrl_bg_on,
					tags='gui')
				self.plot_value_func = self.plot_value_arc
				self.on_size_graph = self.on_size_arc
			elif graph == self.GUI_CTRL_RECTANGLE:
				self.rectangle_bg = self.create_rectangle(
					(0, 0, 0, 0),
					fill=zynthian_gui_config.color_ctrl_bg_off,
					width=0
				)
				self.rectangle = self.create_rectangle(
					(0, 0, 0, 0),
					fill=zynthian_gui_config.color_ctrl_bg_on,
					width=0
				)
				self.plot_value_func = self.plot_value_rectangle
				self.on_size_graph = self.on_size_rectangle
			elif graph == self.GUI_CTRL_TRIANGLE:
				self.triangle_bg = self.create_polygon(
					(0, 0, 0, 0),
					fill=zynthian_gui_config.color_ctrl_bg_off
				)
				self.triangle = self.create_polygon(
					(0, 0, 0, 0),
					fill=zynthian_gui_config.color_ctrl_bg_on
				)
				self.plot_value_func = self.plot_value_triangle
				self.on_size_graph = self.on_size_triangle
			else:
				self.plot_value_func = lambda self: False
				self.on_size_graph = lambda self : False

			self.label_title = self.create_text(0, 0,
				fill=zynthian_gui_config.color_panel_tx,
				tags='gui')
			self.set_title(self.title)

			self.value_text = self.create_text(0, 0, width=1,
				justify=tkinter.CENTER,
				fill=zynthian_gui_config.color_ctrl_tx,
				font=(zynthian_gui_config.font_family,self.value_font_size),
				text=self.value_print,
				tags='gui')

			self.midi_bind = self.create_text(
				0, 0,
				width=int(4*0.9*zynthian_gui_config.font_size),
				anchor=tkinter.S,
				justify=tkinter.CENTER,
				font=(zynthian_gui_config.font_family, int(0.7*zynthian_gui_config.font_size)),
				tags='gui')

			# Bind canvas events
			self.canvas_push_ts = None
			self.bind("<Button-1>", self.cb_canvas_push)
			self.bind("<ButtonRelease-1>", self.cb_canvas_release)
			self.bind("<B1-Motion>", self.cb_canvas_motion)
			self.bind("<Button-4>", self.cb_canvas_wheel)
			self.bind("<Button-5>", self.cb_canvas_wheel)
			self.bind("<Configure>", self.on_size)

		# Setup Controller and Zyncoder
		self.config(zctrl)

		# Show / enable controller
		self.show()

	# Handle resize
	def on_size(self, event):
		self.on_size_graph(event)
		self.plot_value_func()
		self.set_title(self.title)
		if self.zctrl:
			self.calculate_value_font_size()
			self.calculate_plot_values()
			self.set_drag_scale()

	def set_drag_scale(self):
		hh = self.winfo_height()
		self.pixels_per_div = hh // 20
		if self.zctrl:
			if isinstance(self.zctrl.ticks, list):
				n = len(self.zctrl.ticks)
				if n > 0:
					self.pixels_per_div = hh // n
			else:
				# Integer
				if self.zctrl.value_range == 0:
					self.pixels_per_div = 1
				elif self.zctrl.is_integer:
					self.pixels_per_div = hh // self.zctrl.value_range
				# Float
				else:
					self.pixels_per_div = int(hh * self.zctrl.nudge_factor / self.zctrl.value_range)
			if self.zctrl.is_toggle:
				self.pixels_per_div = hh // 3
		if self.pixels_per_div == 0:
			self.pixels_per_div = 1

	# Handle resize of arc graph
	def on_size_arc(self, event):
		ww = self.winfo_width()
		hh = self.winfo_height()
		radius = min(ww, hh) // 2
		if radius > 4:
			radius -= 4
		arc_width = radius // 4

		# x0, y0 center of arc
		if self.vertical:
			x0 = ww // 2
			y0 = hh - radius + arc_width - 4
			self.title_width = ww - 4
			self.coords(self.label_title, 4, 2)
			self.itemconfigure(self.label_title, width=self.title_width, anchor='nw', justify=tkinter.LEFT)
		else:
			x0 = ww - radius - 2
			y0 = hh // 2
			if self.selector_counter:
				y0 -= radius // 3 + 2
			self.title_width = int(ww - radius * 1.8)
			self.coords(self.label_title, 4, 4)
			self.itemconfigure(self.label_title, width=self.title_width, anchor='nw', justify=tkinter.LEFT)

		self.coords(self.value_text, x0, y0)
		self.itemconfigure(self.value_text, font=(zynthian_gui_config.font_family, self.value_font_size), width=radius*2)
		if not self.selector_counter:
			# x1,y1 top left of arc, x2,y2 bottom right of arc
			x1 = x0 - radius
			y1 = y0 - radius
			x2 = x0 + radius
			y2 = y0 + radius
			self.coords(self.graph, x1 + arc_width, y1 + arc_width, x2 - arc_width, y2 - arc_width)
			self.itemconfigure(self.graph, width=arc_width)
		self.coords(self.midi_bind, x0, hh - 2)

	# Handle resize of rectangle graph
	def on_size_rectangle(self, event):
		ww = self.winfo_width()
		hh = self.winfo_height()
		hrect = int(0.35 * hh)

		self.title_width = ww - 4
		self.coords(self.label_title, 2, 2)
		self.itemconfigure(self.label_title, width=self.title_width, anchor='nw', justify=tkinter.LEFT)

		vty = hh // 2 - hrect // 4 + self.value_font_size + 4
		vtx = ww // 2
		self.coords(self.value_text, vtx, vty)
		self.itemconfigure(self.value_text, font=(zynthian_gui_config.font_family, self.value_font_size), width=ww - 8)

		self.plot_value_rectangle()
		self.coords(self.midi_bind, ww // 2, hh - 2)

	# Handle resize of triangle graph
	def on_size_triangle(self, event):
		ww = self.winfo_width()
		hh = self.winfo_height()
		htri = int(0.4 * hh)
		
		self.title_width = ww - 4
		self.coords(self.label_title, 2, 2)
		self.itemconfigure(self.label_title, width=self.title_width, anchor='nw', justify=tkinter.LEFT)

		vty = hh // 2 - htri // 4 + self.value_font_size + 4
		vtx = ww // 2
		self.coords(self.value_text, vtx, vty)
		self.itemconfigure(self.value_text, font=(zynthian_gui_config.font_family, self.value_font_size), width=ww - 8)

		self.plot_value_triangle()
		self.coords(self.midi_bind, ww // 2, hh - 2)

	def show(self):
		self.shown = True
		if self.hidden:
			return
		if self.zctrl:
			self.calculate_value_font_size()
			self.calculate_plot_values()
			self.plot_value()
			self.set_drag_scale()
			# TODO: calculate_value_font_size, calculate_plot_values, set_drag_scale always called together - optimse to single function?
			self.itemconfig('gui', state=tkinter.NORMAL)
			if self.selector_counter:
				self.itemconfig(self.graph, state=tkinter.HIDDEN)
		else:
			self.itemconfig('gui', state=tkinter.HIDDEN)

	def hide(self):
		self.shown = False
		if self.hidden:
			return

	def set_hl(self, color=zynthian_gui_config.color_hl):
		try:
			self.itemconfig(self.graph, outline=color)
			#self.itemconfig(self.label_title, fill=color)
			#self.itemconfig(self.value_text, fill=color)
		except:
			pass

	def unset_hl(self):
		try:
			self.itemconfig(self.graph, outline=zynthian_gui_config.color_ctrl_bg_on)
			#self.itemconfig(self.label_title, fill=zynthian_gui_config.color_panel_tx)
			#self.itemconfig(self.value_text, fill=zynthian_gui_config.color_panel_tx)
		except:
			pass

	def calculate_plot_values(self):
		if self.hidden or self.zctrl is None:
			return
		if self.zctrl.ticks:
			n = len(self.zctrl.ticks)
			try:
				i = self.zctrl.get_value2index()
				self.value_print = self.zctrl.labels[i]
				if n > 2:
					self.value_plot = (i + 1) / n
				else:
					self.value_plot = i
			except Exception as err:
				logging.error(f"Calc Error => {err}")
				self.value_plot = self.zctrl.value
				self.value_print = "ERR"
		else:
			if self.zctrl.value_range == 0:
				self.value_plot = 0
			elif self.zctrl.is_logarithmic:
				if self.zctrl.value_min < 0:
					self.value_plot = math.log10((9 * self.zctrl.value - (10 * self.zctrl.value_min)) / self.zctrl.value_range)
				else:
					self.value_plot = math.log10((9 * self.zctrl.value - (10 * self.zctrl.value_min - self.zctrl.value_max)) / self.zctrl.value_range)
			else:
				if self.zctrl.value_min < 0:
					self.value_plot = (self.zctrl.value) / self.zctrl.value_range
				else:
					self.value_plot = (self.zctrl.value - self.zctrl.value_min) / self.zctrl.value_range
			if self.selector_counter:
				val = self.zctrl.value + 1
			else:
				val = self.zctrl.value
			if self.format_print and -1000 < val < 1000:
				self.value_print = self.format_print.format(val)
			else:
				self.value_print = str(int(val))
		self.refresh_plot_value = True

	def plot_value(self):
		if self.shown and self.zctrl and (self.zctrl.is_dirty or self.refresh_plot_value):
			if not self.hidden:
				if self.zctrl.readonly:
					self.set_hl(zynthian_gui_config.color_ctrl_bg_off)
				else:
					self.unset_hl()
				self.plot_value_func()
			self.refresh_plot_value = False
			self.zctrl.is_dirty = False

	def plot_value_rectangle(self):
		if not self.selector_counter:
			ww = self.winfo_width()
			hh = self.winfo_height()
			hrect = int(0.35 * hh)
			x1 = 4
			y1 = hh // 2 - hrect // 4
			x2 = 4 + int((ww - 8) * self.value_plot)
			y2 = y1 + hrect
			self.coords(self.rectangle, (x1, y1, x2, y2))
		self.itemconfig(self.value_text, text=self.value_print)

	def plot_value_triangle(self):
		if not self.selector_counter:
			ww = self.winfo_width()
			hh = self.winfo_height()
			htri = int(0.4 * hh)
			x1 = 4
			y1 = hh // 2 + 3 * htri // 4
			x2 = 4 + int((ww - 8) * self.value_plot)
			y2 = y1 - int(htri * self.value_plot)
			self.coords(self.triangle, (x1, y1, x2, y1, x2, y2))
		self.itemconfig(self.value_text, text=self.value_print)

	def plot_value_arc(self):
		if not self.selector_counter:
			degmax = 300
			degd = -degmax * self.value_plot
			deg0 = 90 + degmax / 2
			if self.zctrl:
				if isinstance(self.zctrl.labels, list):
					n = len(self.zctrl.labels)
					if n > 2:
						arc_len = max(5, degmax // n)
						deg0 += degd + arc_len
						degd = -arc_len
				elif self.zctrl.value_range and self.zctrl.value_min <= 0 and self.zctrl.value_max >= 0:
					deg0 += degmax * self.zctrl.value_min / self.zctrl.value_range
			self.itemconfig(self.graph, start=deg0, extent=degd)
		self.itemconfig(self.value_text, text=self.value_print)

	def plot_midi_bind(self, midi_cc, color=zynthian_gui_config.color_ctrl_tx):
		if self.hidden:
			return
		self.itemconfig(self.midi_bind, text=str(midi_cc), fill=color)

	def erase_midi_bind(self):
		if self.hidden:
			return
		self.itemconfig(self.midi_bind, text="")

	def set_midi_bind(self, preselection=None):
		self.preselection = preselection
		if self.hidden:
			return
		if self.zctrl:
			midi_learn_params = self.zyngui.chain_manager.get_midi_learn_from_zctrl(self.zctrl)
			if self.selector_counter:
				#self.erase_midi_bind()
				self.plot_midi_bind(f"/{self.zctrl.value_range + 1}")
			elif preselection is not None or self.zctrl == self.zyngui.state_manager.get_midi_learn_zctrl():
				if self.zyngui.screens["control"].get_midi_learn() > 1:
					self.plot_midi_bind("??#??", zynthian_gui_config.color_ml)
				else:
					self.plot_midi_bind("??", zynthian_gui_config.color_hl)
			elif midi_learn_params:
				zmip = (midi_learn_params[0] >> 24) & 0xff
				chan = (midi_learn_params[0] >> 16) & 0xff
				cc = (midi_learn_params[0] >> 8) & 0xff
				if midi_learn_params[1]:
					self.plot_midi_bind(f"{chan + 1}#{cc}")
				else:
					self.plot_midi_bind(f"{cc}")
			else:
				self.erase_midi_bind()
				return False
			return True
		return False

	def set_title(self, title):
		if self.hidden:
			return
		self.title = str(title)
		# Calculate the font size ...
		max_fs = int(1.0*zynthian_gui_config.font_size)
		words = self.title.split()
		n_words = len(words)
		rfont = tkFont.Font(family=zynthian_gui_config.font_family, size=max_fs)
		if n_words == 0:
			maxlen = 1
		elif n_words == 1:
			maxlen = rfont.measure(self.title)
		elif n_words == 2:
			maxlen = max([rfont.measure(w) for w in words])
		elif n_words == 3:
			maxlen = max([rfont.measure(w) for w in [words[0]+' '+words[1], words[1]+' '+words[2]]])
			max_fs = max_fs - 1
		elif n_words >= 4:
			maxlen = max([rfont.measure(w) for w in [words[0]+' '+words[1], words[2]+' '+words[3]]])
			max_fs = max_fs-1
		else:
			maxlen = 1
		fs = int(self.title_width * max_fs / maxlen)
		fs = min(max_fs,max(int(0.8*zynthian_gui_config.font_size), fs))
		#logging.debug("TITLE %s => MAXLEN=%d, FONTSIZE=%d" % (self.title,maxlen,fs))

		# Set title label
		self.itemconfigure(self.label_title,
			text=self.title,
			font=(zynthian_gui_config.font_family, fs))

	def calculate_value_font_size(self):
		if self.zctrl.labels:
			maxlen = len(max(self.zctrl.labels, key=len))
			if maxlen > 3:
				rfont = tkFont.Font(family = zynthian_gui_config.font_family, size=zynthian_gui_config.font_size)
				maxlen = max([rfont.measure(w) for w in self.zctrl.labels])
			#print("LONGEST VALUE: %d" % maxlen)
			if maxlen > 100:
				font_scale = 0.7
			elif maxlen > 85:
				font_scale = 0.8
			elif maxlen > 70:
				font_scale = 0.9
			elif maxlen > 55:
				font_scale = 1.0
			elif maxlen > 40:
				font_scale = 1.1
			elif maxlen > 30:
				font_scale = 1.2
			elif maxlen > 20:
				font_scale = 1.3
			else:
				font_scale = 1.4
		else:
			if self.format_print:
				maxlen = 5
			else:
				maxlen = max(len(str(self.zctrl.value_min)), len(str(self.zctrl.value_max)))
			if maxlen > 5:
				font_scale = 0.8
			elif maxlen > 4:
				font_scale = 0.9
			elif maxlen > 3:
				font_scale = 1.1
			else:
				if self.zctrl.value_min >= 0 and self.zctrl.value_max < 200:
					font_scale = 1.4
				else:
					font_scale = 1.3
		# Calculate value font size
		self.value_font_size = int(font_scale * zynthian_gui_config.font_size)
		# Update font config in text object
		if self.value_text:
			self.itemconfig(self.value_text, font=(zynthian_gui_config.font_family, self.value_font_size))

	def config(self, zctrl):
		#logging.debug("CONFIG CONTROLLER %s => %s" % (self.index,zctrl.name))

		self.step = 0  # By default, use adaptative step size based on rotary speed
		self.format_print = None
		self.zctrl = zctrl
		if zctrl is None:
			self.set_title("")
			self.erase_midi_bind()
			return

		self.set_title(zctrl.short_name)
		self.set_midi_bind()

		# List of values => Selector
		if isinstance(zctrl.ticks, list):
			if len(zctrl.ticks) <= 32:
				# If few values => use fixed step=1 (no adaptative step size!)
				self.step = 1
		# Numeric value
		else:
			# Integer
			if zctrl.is_integer:
				# If few values => use fixed step=1 (no adaptative step size!)
				if zctrl.value_range <= 32:
					self.step = 1
			# Float
			else:
				if zctrl.nudge_factor < 0.1:
					self.format_print = "{:.2f}"
				else:
					self.format_print = "{:.1f}"

		#logging.debug(f"ZCTRL '{zctrl.short_name}' = {zctrl.value} ({zctrl.value_min} -> {zctrl.value_max}, {self.step}); {zctrl.labels}; {zctrl.ticks}")
		self.setup_zynpot()

	# --------------------------------------------------------------------------
	# Zynpot Callbacks (rotaries!)
	# --------------------------------------------------------------------------

	def setup_zynpot(self):
		try:
			lib_zyncore.setup_behaviour_zynpot(self.index, self.step)
		except Exception as err:
			logging.error("%s" % err)

	def zynpot_cb(self, dval):
		if self.zctrl:
			return self.zctrl.nudge(dval)
		else:
			return False

	# This is used by touch interface
	def nudge(self, dval):
		if self.preselection is not None:
			self.zyngui.screens["control"].zctrl_touch(self.preselection)
		if self.zctrl:
			return self.zctrl.nudge(dval)
		else:
			return False

	# --------------------------------------------------------------------------
	# Keyboard & Mouse/Touch Callbacks
	# --------------------------------------------------------------------------

	def cb_canvas_push(self, event):
		self.canvas_push_ts = datetime.now()
		self.active_motion_axis = 0  # +1=dragging in y-axis, -1=dragging in x-axis
		self.canvas_motion_y0 = event.y
		self.canvas_motion_x0 = event.x
		self.canvas_motion_dx = 0
		#logging.debug(f"CONTROL {self.index} PUSH => {self.canvas_push_ts} ({self.canvas_motion_x0},{self.canvas_motion_y0})")

	def cb_canvas_release(self, event):
		if self.canvas_push_ts:
			dts = (datetime.now()-self.canvas_push_ts).total_seconds()
			self.canvas_push_ts = None
			#logging.debug(f"CONTROL {self.index} RELEASE => {dts}, {motion_rate}")
			if self.active_motion_axis == 0:
				if zynthian_gui_config.enable_touch_controller_switches:
					if dts < zynthian_gui_config.zynswitch_bold_seconds:
						self.zyngui.zynswitch_defered('S', self.index)
					elif zynthian_gui_config.zynswitch_bold_seconds <= dts < zynthian_gui_config.zynswitch_long_seconds:
						self.zyngui.zynswitch_defered('B', self.index)
					elif dts >= zynthian_gui_config.zynswitch_long_seconds:
						self.zyngui.zynswitch_defered('L', self.index)
			elif self.canvas_motion_dx > self.winfo_width() // 2:
				self.zyngui.zynswitch_defered('X', self.index)
			elif self.canvas_motion_dx < -self.winfo_width() // 2:
				self.zyngui.zynswitch_defered('Y', self.index)

	def cb_canvas_motion(self, event):
		if self.canvas_push_ts:
			dts = (datetime.now() - self.canvas_push_ts).total_seconds()
			if dts > 0.1:  # debounce initial touch
				dy = self.canvas_motion_y0 - event.y
				dx = event.x - self.canvas_motion_x0

				# Lock drag to x or y axis only after one has been started
				if self.active_motion_axis == 0:
					if abs(dy) > self.pixels_per_div:
						self.active_motion_axis = 1
					elif abs(dx) > self.pixels_per_div:
						self.active_motion_axis = -1

				if self.zctrl and self.active_motion_axis == 1:
					# Y-axis drag active
					if abs(dy) >= self.pixels_per_div:
						if self.zctrl.range_reversed:
							self.nudge(-dy // self.pixels_per_div)
						else:
							self.nudge(dy // self.pixels_per_div)
						self.canvas_motion_y0 = event.y + dy % self.pixels_per_div

				elif self.active_motion_axis == -1:
					# X-axis drag active
					self.canvas_motion_dx = dx

	def cb_canvas_wheel(self, event):
		if self.zctrl:
			if event.num == 5 or event.delta == -120:
				self.nudge(-1)
			if event.num == 4 or event.delta == 120:
				self.nudge(1)

# ------------------------------------------------------------------------------
