#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Controller Class
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

import sys
import math
import liblo
import ctypes
import tkinter
import logging
from time import sleep
from string import Template
from datetime import datetime
from tkinter import font as tkFont

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore
from zyngine import zynthian_controller
from zyngui import zynthian_gui_config

#------------------------------------------------------------------------------
# Controller GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_controller:

	def __init__(self, indx, frm, zctrl, hidden=False, selcounter=False):
		self.zyngui=zynthian_gui_config.zyngui
		self.zctrl = None
		self.step = 0

		self.value_plot = 0 # Normalised position of plot start point
		self.value_print = None
		self.value_font_size = zynthian_gui_config.font_size

		self.hidden = hidden # Always hidden => in such a case, self.shown means "enabled"
		self.shown = False # Currently shown/enabled
		self.rectangle = None
		self.triangle = None
		self.arc = None
		self.value_text = None
		self.label_title = None
		self.midi_bind = None
		self.selector_counter = selcounter
		self.refresh_plot_value = False

		self.width=zynthian_gui_config.ctrl_width
		self.height=zynthian_gui_config.ctrl_height

		self.pixels_per_div = self.height // 20
		self.touch_accel = 300

		if zynthian_gui_config.ctrl_both_sides:
			self.trw = zynthian_gui_config.ctrl_width-6
			self.trh = int(0.1*zynthian_gui_config.ctrl_height)
			self.titw = self.trw
		else:
			self.trw = 0.8 * (zynthian_gui_config.ctrl_width / 2)
			self.trh = 1.06 * self.trw
			self.titw = 0.6 * zynthian_gui_config.ctrl_width

		#TODO: Allow configuration of value widget style (arc, triangle, rectangle, etc.)
		self.plot_value_func = self.plot_value_arc
		self.erase_value_func = self.erase_value_arc

		self.index = indx
		self.main_frame = frm
		self.row = zynthian_gui_config.ctrl_pos[indx][0]
		self.col = zynthian_gui_config.ctrl_pos[indx][1]
		self.sticky = zynthian_gui_config.ctrl_pos[indx][2]

		# Configure row height
		self.main_frame.rowconfigure(self.row, weight=self.row*10, minsize=self.height)

		# Create Canvas
		self.canvas = tkinter.Canvas(self.main_frame,
			width=self.width,
			height=self.height,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg = zynthian_gui_config.color_panel_bg)
		# Bind canvas events
		self.canvas_push_ts = None
		self.canvas.bind("<Button-1>",self.cb_canvas_push)
		self.canvas.bind("<ButtonRelease-1>",self.cb_canvas_release)
		self.canvas.bind("<B1-Motion>",self.cb_canvas_motion)
		self.canvas.bind("<Button-4>",self.cb_canvas_wheel)
		self.canvas.bind("<Button-5>",self.cb_canvas_wheel)
		# Setup Controller and Zyncoder
		self.config(zctrl)
		# Show Controller
		self.show()


	def show(self):
		if not self.shown:
			self.shown=True
			if not self.hidden:
				if zynthian_gui_config.ctrl_both_sides:
					if self.index%2==0:
						pady = (0,2)
					else:
						pady = (0,0)
				else:
					pady = (0,2)
				self.canvas.grid(row=self.row, column=self.col, sticky=self.sticky, pady=pady)
		if self.zctrl:
			self.calculate_plot_values()
			self.plot_value()
		else:
			self.erase_value()


	def hide(self):
		if self.shown:
			self.shown=False
			self.canvas.grid_forget()


	def set_hl(self, color=zynthian_gui_config.color_hl):
		try:
			self.canvas.itemconfig(self.arc, outline=color)
			#self.canvas.itemconfig(self.label_title, fill=color)
			#self.canvas.itemconfig(self.value_text, fill=color)
		except:
			pass


	def unset_hl(self):
		try:
			self.canvas.itemconfig(self.arc, outline=zynthian_gui_config.color_ctrl_bg_on)
			#self.canvas.itemconfig(self.label_title, fill=zynthian_gui_config.color_panel_tx)
			#self.canvas.itemconfig(self.value_text, fill=zynthian_gui_config.color_panel_tx)
		except:
			pass


	def calculate_plot_values(self):
		val = None
		if self.hidden or self.zctrl is None:
			return

		if self.zctrl.ticks:
			valplot=None
			val=self.zctrl.value
			n = len(self.zctrl.ticks)
			try:
				i = self.zctrl.get_value2index()
				self.value_print = self.zctrl.labels[i]
				if n > 2:
					self.value_plot = (i + 1) / n
				else:
					self.value_plot = i

			except Exception as err:
				logging.error("Calc Error => %s" % (err))
				self.value_plot=self.zctrl.value
				self.value_print="ERR"

		else:
			if self.zctrl.is_logarithmic:
				self.value_plot = math.log10((9 * self.zctrl.value - (10 * self.zctrl.value_min - self.zctrl.value_max)) / self.zctrl.value_range)
			else:
				self.value_plot = (self.zctrl.value - self.zctrl.value_min) / self.zctrl.value_range

			if self.selector_counter:
				val = self.zctrl.value + 1
			else:
				val = self.zctrl.value

			if self.format_print and val<1000 and val>-1000:
				self.value_print = self.format_print.format(val)
			else:
				self.value_print = str(int(val))

		self.refresh_plot_value = True


	def plot_value(self):
		if self.shown and self.zctrl and (self.zctrl.is_dirty or self.refresh_plot_value):
			self.plot_value_func()
			self.refresh_plot_value = False
			self.zctrl.is_dirty = False


	def erase_value(self):
		if self.shown:
			self.erase_value_func()


	def plot_value_rectangle(self):
		x1 = 6
		y1 = self.height-5
		lx = self.trw - 4
		ly = 2 * self.trh
		y2 = y1 - ly

		x2 = x1 + lx * self.value_plot

		if not self.selector_counter:
			if self.rectangle:
					self.canvas.coords(self.rectangle, (x1, y1, x2, y2))
			else:
				self.rectangle_bg = self.canvas.create_rectangle(
					(x1, y1, x1 + lx, y2),
					fill = zynthian_gui_config.color_ctrl_bg_off,
					width = 0
				)
				self.rectangle = self.canvas.create_rectangle(
					(x1, y1, x2, y2),
					fill = zynthian_gui_config.color_ctrl_bg_on,
					width = 0
				)
				self.canvas.tag_lower(self.rectangle)
				self.canvas.tag_lower(self.rectangle_bg)

		if self.value_text:
			self.canvas.itemconfig(self.value_text, text=self.value_print)
		else:
			self.value_text=self.canvas.create_text(
				x1 + self.trw / 2 - 1,
				y1 - self.trh,
				width=self.trw,
				justify=tkinter.CENTER,
				fill = zynthian_gui_config.color_ctrl_tx,
				font = (zynthian_gui_config.font_family, self.value_font_size),
				text = self.value_print)


	def erase_value_rectangle(self):
		if self.rectangle:
			self.canvas.delete(self.rectangle_bg)
			self.canvas.delete(self.rectangle)
			self.rectangle_bg = self.rectangle = None
		if self.value_text:
			self.canvas.itemconfig(self.value_text, text="")


	def plot_value_triangle(self):
		x1 = 2
		y1 = int(0.8 * self.height) + self.trh

		x2 = x1 + int(self.trw * self.value_plot)
		y2 = y1 - int(self.trh * self.value_plot)

		if not self.selector_counter:
			if self.triangle:
					#self.canvas.coords(self.triangle_bg,(x1, y1, x1+self.trw, y1, x1+self.trw, y1-self.trh))
					self.canvas.coords(
						self.triangle,
						(x1, y1, x2, y1, x2, y2)
					)
			else:
				self.triangle_bg = self.canvas.create_polygon(
					(x1, y1, x1 + self.trw, y1, x1 + self.trw, y1 - self.trh),
					fill = zynthian_gui_config.color_ctrl_bg_off
				)
				self.triangle = self.canvas.create_polygon(
					(x1, y1, x2, y1, x2, y2),
					fill = zynthian_gui_config.color_ctrl_bg_on
				)
				self.canvas.tag_lower(self.triangle)
				self.canvas.tag_lower(self.triangle_bg)

		if self.value_text:
			self.canvas.itemconfig(self.value_text, text=self.value_print)
		else:
			self.value_text=self.canvas.create_text(
				x1 + self.trw / 2 - 1,
				y1 - self.trh - 8, width = self.trw,
				justify=tkinter.CENTER,
				fill=zynthian_gui_config.color_ctrl_tx,
				font=(zynthian_gui_config.font_family,self.value_font_size),
				text=self.value_print
			)


	def erase_value_triangle(self):
		if self.triangle:
			self.canvas.delete(self.triangle_bg)
			self.canvas.delete(self.triangle)
			self.triangle_bg = self.triangle = None
		if self.value_text:
			self.canvas.itemconfig(self.value_text, text="")


	def plot_value_arc(self):
		#thickness = 1.1 * zynthian_gui_config.font_size
		thickness = self.height / 10
		degmax = 300

		degd = -degmax * self.value_plot

		deg0 = 90 + degmax / 2
		if isinstance(self.zctrl.labels, list):
			n = len(self.zctrl.labels)
			if n>2:
				arc_len = max(5, degmax / n)
				deg0 += degd + arc_len
				degd = -arc_len

		if (not self.arc and not self.selector_counter) or not self.value_text:
			if zynthian_gui_config.ctrl_both_sides:
				x1 = 0.18*self.trw
				y1 = self.height - int(0.7*self.trw) - 6
				x2 = x1 + int(0.7*self.trw)
				y2 = self.height - 6
			else:
				x1 = self.width/2 + 0.1*self.trw
				y1 = 0.7*(self.height - self.trh)
				x2 = x1 + self.trw
				y2 = y1 + self.trh

		if not self.selector_counter:
			if self.arc:
				self.canvas.itemconfig(self.arc, start=deg0, extent=degd)
			else:
				self.arc=self.canvas.create_arc(x1, y1, x2, y2,
					style=tkinter.ARC,
					outline=zynthian_gui_config.color_ctrl_bg_on,
					width=thickness,
					start=deg0,
					extent=degd)
				self.canvas.tag_lower(self.arc)

		if self.value_text:
			self.canvas.itemconfig(self.value_text, text=self.value_print)
		else:
			self.value_text=self.canvas.create_text(x1+(x2-x1)/2-1, y1-(y1-y2)/2, width=x2-x1,
				justify=tkinter.CENTER,
				fill=zynthian_gui_config.color_ctrl_tx,
				font=(zynthian_gui_config.font_family,self.value_font_size),
				text=self.value_print)


	def erase_value_arc(self):
		if self.arc:
			self.canvas.delete(self.arc)
			self.arc=None
		if self.value_text:
			self.canvas.itemconfig(self.value_text, text="")
		x2=self.width
		y2=self.height


	def plot_midi_bind(self, midi_cc, color=zynthian_gui_config.color_ctrl_tx):
		if not self.midi_bind:
			self.midi_bind = self.canvas.create_text(
				self.width/2,
				self.height-8,
				width=int(4*0.9*zynthian_gui_config.font_size),
				justify=tkinter.CENTER,
				fill=color,
				font=(zynthian_gui_config.font_family,int(0.7*zynthian_gui_config.font_size)),
				text=str(midi_cc))
		else:
			self.canvas.itemconfig(self.midi_bind, text=str(midi_cc), fill=color)


	def erase_midi_bind(self):
		if self.midi_bind:
			self.canvas.itemconfig(self.midi_bind, text="")


	def set_midi_bind(self):
		if self.zctrl:
			if self.selector_counter:
				#self.erase_midi_bind()
				self.plot_midi_bind("/{}".format(self.zctrl.value_range))
			elif self.zyngui.midi_learn_mode:
				self.plot_midi_bind("??",zynthian_gui_config.color_ml)
			elif self.zyngui.midi_learn_zctrl and self.zctrl==self.zyngui.midi_learn_zctrl:
				self.plot_midi_bind("??",zynthian_gui_config.color_hl)
			elif self.zctrl.midi_learn_cc and self.zctrl.midi_learn_cc>0:
				midi_cc = self.zctrl.midi_learn_cc
				if not self.zyngui.is_single_active_channel():
					midi_cc = "{}#{}".format(self.zctrl.midi_learn_chan+1,midi_cc)
				self.plot_midi_bind(midi_cc)
			elif self.zctrl.midi_cc and self.zctrl.midi_cc>0:
				#midi_cc = self.zctrl.midi_cc
				swap_info= lib_zyncore.get_midi_filter_cc_swap(self.zctrl.midi_chan, self.zctrl.midi_cc)
				midi_chan = swap_info >> 8
				midi_cc = swap_info & 0xFF
				if not self.zyngui.is_single_active_channel():
					midi_cc = "{}#{}".format(midi_chan+1,midi_cc)
				self.plot_midi_bind(midi_cc)
			else:
				self.erase_midi_bind()
				return False
			return True
		return False


	def set_title(self, tit):
		self.title = str(tit)
		#Calculate the font size ...
		max_fs = int(1.0*zynthian_gui_config.font_size)
		words = self.title.split()
		n_words = len(words)
		rfont=tkFont.Font(family=zynthian_gui_config.font_family,size=max_fs)
		if n_words==0:
			maxlen=1
		elif n_words==1:
			maxlen=rfont.measure(self.title)
		elif n_words==2:
			maxlen=max([rfont.measure(w) for w in words])
		elif n_words==3:
			maxlen=max([rfont.measure(w) for w in [words[0]+' '+words[1], words[1]+' '+words[2]]])
			max_fs=max_fs-1
		elif n_words>=4:
			maxlen=max([rfont.measure(w) for w in [words[0]+' '+words[1], words[2]+' '+words[3]]])
			max_fs=max_fs-1
		fs=int(self.titw*max_fs/maxlen)
		fs=min(max_fs,max(int(0.8*zynthian_gui_config.font_size),fs))
		#logging.debug("TITLE %s => MAXLEN=%d, FONTSIZE=%d" % (self.title,maxlen,fs))
		#Set title label
		if not self.label_title:
			self.label_title = self.canvas.create_text(3, 4,
				anchor=tkinter.NW,
				justify=tkinter.LEFT,
				width=self.titw,
				text=self.title,
				font=(zynthian_gui_config.font_family,fs),
				fill=zynthian_gui_config.color_panel_tx)
		else:
			self.canvas.itemconfigure(self.label_title,
				width=self.titw,
				text=self.title,
				font=(zynthian_gui_config.font_family,fs))


	def calculate_value_font_size(self):
		if self.zctrl.labels:
			maxlen=len(max(self.zctrl.labels, key=len))
			if maxlen>3:
				rfont=tkFont.Font(family=zynthian_gui_config.font_family,size=zynthian_gui_config.font_size)
				maxlen=max([rfont.measure(w) for w in self.zctrl.labels])
			#print("LONGEST VALUE: %d" % maxlen)
			if maxlen>100:
				font_scale=0.7
			elif maxlen>85:
				font_scale=0.8
			elif maxlen>70:
				font_scale=0.9
			elif maxlen>55:
				font_scale=1.0
			elif maxlen>40:
				font_scale=1.1
			elif maxlen>30:
				font_scale=1.2
			elif maxlen>20:
				font_scale=1.3
			else:
				font_scale=1.4
		else:
			if self.format_print:
				maxlen=5
			else:
				maxlen=max(len(str(self.zctrl.value_min)),len(str(self.zctrl.value_max)))
			if maxlen>5:
				font_scale=0.8
			elif maxlen>4:
				font_scale=0.9
			elif maxlen>3:
				font_scale=1.1
			else:
				if self.zctrl.value_min>=0 and self.zctrl.value_max<200:
					font_scale=1.4
				else:
					font_scale=1.3
		#Calculate value font size
		self.value_font_size=int(font_scale*zynthian_gui_config.font_size)
		#Update font config in text object
		if self.value_text:
			self.canvas.itemconfig(self.value_text, font=(zynthian_gui_config.font_family,self.value_font_size))


	def config(self, zctrl):
		#logging.debug("CONFIG CONTROLLER %s => %s" % (self.index,zctrl.name))
		
		self.step = 0				#By default, use adaptative step size based on rotary speed
		self.format_print = None

		self.zctrl = zctrl
		if zctrl is None:
			self.set_title("")
			self.erase_midi_bind()
			return

		self.set_title(zctrl.short_name)
		self.set_midi_bind()

		logging.debug("ZCTRL '%s': %s (%s -> %s), %s, %s" % (zctrl.short_name,zctrl.value,zctrl.value_min,zctrl.value_max,zctrl.labels,zctrl.ticks))

		#List of values => Selector
		if isinstance(zctrl.ticks, list):
			n = len(zctrl.ticks)
			if n>0:
				self.pixels_per_div = self.height // n
			# If few values => use fixed step=1 (no adaptative step size!)
			if n <= 32:
				self.step=1

		#Numeric value
		else:
			#Integer
			if zctrl.is_integer:
				self.pixels_per_div = self.height // zctrl.value_range
				# If few values => use fixed step=1 (no adaptative step size!)
				if zctrl.value_range <= 32:
					self.step=1

			#Float
			else:
				self.pixels_per_div = int(self.height * zctrl.nudge_factor / zctrl.value_range)
				if zctrl.nudge_factor < 0.1:
					self.format_print="{0:.2f}"
				else:
					self.format_print="{0:.1f}"

		if zctrl.is_toggle:
			self.pixels_per_div = 20
		elif self.pixels_per_div == 0:
			self.pixels_per_div = 1

		self.calculate_value_font_size()
		self.setup_zynpot()


	#--------------------------------------------------------------------------
	# Zynpot Callbacks (rotaries!)
	#--------------------------------------------------------------------------

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

	#--------------------------------------------------------------------------
	# Keyboard & Mouse/Touch Callbacks
	#--------------------------------------------------------------------------

	def cb_canvas_push(self,event):
		if self.zctrl:
			self.canvas_push_ts = datetime.now()
			self.canvas_motion_y0 = event.y
			self.canvas_motion_x0 = event.x
			self.active_motion_axis = 0 # +1=dragging in y-axis, -1=dragging in x-axis
			self.canvas_motion_dx = 0
			self.canvas_motion_count = 0
			self.canvas_motion_val0 = self.zctrl.value
			self.motion_swipe_y = 0
			#logging.debug("CONTROL {} PUSH => {} ({},{})".format(self.index, self.canvas_push_ts, self.canvas_motion_x0, self.canvas_motion_y0))


	def cb_canvas_release(self,event):
		if self.canvas_push_ts:
			dts = (datetime.now()-self.canvas_push_ts).total_seconds()
			motion_rate = self.canvas_motion_count / dts
			#logging.debug("CONTROL {} RELEASE => {}, {}".format(self.index, dts, motion_rate))
			if self.active_motion_axis == 0:
				if not zynthian_gui_config.enable_onscreen_buttons:
					if dts < 0.3:
						self.zyngui.zynswitch_defered('S',self.index)
					elif dts >= 0.3 and dts < 2:
						self.zyngui.zynswitch_defered('B',self.index)
					elif dts >= 2:
						self.zyngui.zynswitch_defered('L',self.index)
			elif self.canvas_motion_dx > self.width // 2:
				self.zyngui.zynswitch_defered('X', self.index)
			elif self.canvas_motion_dx < -self.width // 2:
				self.zyngui.zynswitch_defered('Y', self.index)
			self.canvas_push_ts = None


	def cb_canvas_motion(self,event):
		if self.canvas_push_ts:
			now = datetime.now()
			dts = (now - self.canvas_push_ts).total_seconds()
			if dts > 0.1: # debounce initial touch
				dy = self.canvas_motion_y0 - event.y
				dx = event.x - self.canvas_motion_x0

				# Lock drag to x or y axis only after one has been started
				if self.active_motion_axis == 0:
					if abs(dy) > self.pixels_per_div:
						self.active_motion_axis = 1
					elif abs(dx) > self.pixels_per_div:
						self.active_motion_axis = -1

				if self.active_motion_axis == 1:
					# Y-axis drag active
					if abs(dy) >= self.pixels_per_div:
						if self.zctrl.range_reversed:
							self.zctrl.nudge(-dy // self.pixels_per_div)
						else:
							self.zctrl.nudge(dy // self.pixels_per_div)
						self.canvas_motion_y0 = event.y + dy % self.pixels_per_div

				elif self.active_motion_axis == -1:
					# X-axis drag active
					self.canvas_motion_dx = dx


	def cb_canvas_wheel(self,event):
		if self.zctrl:
			if event.num == 5 or event.delta == -120:
				self.zctrl.nudge(-1)
			if event.num == 4 or event.delta == 120:
				self.zctrl.nudge(1)

#------------------------------------------------------------------------------
