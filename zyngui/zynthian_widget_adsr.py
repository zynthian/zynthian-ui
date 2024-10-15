#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian Widget Class for ADSR screen type
# 
# Copyright (C) 2015-2024 Fernando Moyano <fernando@zynthian.org>
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

import tkinter
import logging

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base

# ------------------------------------------------------------------------------
# Zynthian Widget Class for ADSR screen type
# ------------------------------------------------------------------------------


class zynthian_widget_adsr(zynthian_widget_base.zynthian_widget_base):

	def __init__(self, parent):
		super().__init__(parent)

		# Geometry vars set accurately during resize
		self.rows = self.zyngui_control.layout['rows'] // 2

		self.widget_canvas = tkinter.Canvas(self,
			highlightthickness=0,
			relief='flat',
			bg=zynthian_gui_config.color_bg)
		self.widget_canvas.grid(sticky='news')

		self.last_adsr_values = []
		self.drag_zctrl = None

		# Create custom GUI elements (position and size set when canvas is grid and size applied)
		adsr_outline_color = zynthian_gui_config.color_low_on
		adsr_color = zynthian_gui_config.color_variant(zynthian_gui_config.color_low_on, -70)
		#drag_color = zynthian_gui_config.color_hl
		self.adsr_polygon = self.widget_canvas.create_polygon([0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
															outline=adsr_outline_color, fill=adsr_color, width=3)
		self.drag_polygon = self.widget_canvas.create_polygon([0, 0, 0, 0, 0, 0, 0, 0],
															outline=adsr_outline_color, fill=adsr_outline_color, width=3, state='hidden')
		self.widget_canvas.bind('<ButtonPress-1>', self.on_canvas_press)
		self.widget_canvas.bind('<B1-Motion>', self.on_canvas_drag)
		self.widget_canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

	def on_size(self, event):
		if event.width == self.width and event.height == self.height:
			return
		super().on_size(event)
		self.widget_canvas.grid(row=0, column=0, sticky='news')
		self.last_adsr_values = []
		self.refresh_gui()

	def refresh_gui(self):
		zctrls = self.zyngui_control.zcontrollers
		adsr_values = [zctrls[0].value/zctrls[0].value_range, zctrls[1].value/zctrls[1].value_range,
					zctrls[2].value/zctrls[2].value_range, zctrls[3].value/zctrls[3].value_range]
		if adsr_values != self.last_adsr_values or self.drag_zctrl:
			dx = self.width // 4
			dy = int(0.95 * self.height)
			x0 = 0
			y0 = self.height
			x1 = adsr_values[0] * dx
			y1 = y0 - dy
			x2 = x1 + adsr_values[1] * dx
			y2 = y0 - adsr_values[2] * dy
			x3 = self.width - adsr_values[3] * dx
			y3 = y2
			x4 = self.width
			y4 = y0
			self.widget_canvas.coords(self.adsr_polygon, x0, y0, x1, y1, x2, y2, x3, y3, x4, y4)
			self.last_adsr_values = adsr_values
			# Highlight dragged section
			if self.drag_zctrl:
				self.widget_canvas.itemconfig(self.drag_polygon, state="normal")
			if self.drag_zctrl == self.zyngui_control.zcontrollers[0]:
				self.widget_canvas.coords(self.drag_polygon, x0, y0, x1, y1, x1, y0, x0, y0)
			elif self.drag_zctrl == self.zyngui_control.zcontrollers[1]:
				self.widget_canvas.coords(self.drag_polygon, x1, y0, x1, y1, x2, y2, x2, y0)
			elif self.drag_zctrl == self.zyngui_control.zcontrollers[2]:
				self.widget_canvas.coords(self.drag_polygon, x2, y0, x2, y2, x3, y3, x3, y0)
			elif self.drag_zctrl == self.zyngui_control.zcontrollers[3]:
				self.widget_canvas.coords(self.drag_polygon, x3, y0, x3, y3, x4, y4, x4, y0)

	def on_canvas_press(self, event):
		dx = self.width // 4
		dy = int(0.95 * self.height)
		zctrls = self.zyngui_control.zcontrollers
		self.last_click = event
		self.adsr_click_values = [zctrls[0].value/zctrls[0].value_range, zctrls[1].value/zctrls[1].value_range,
					zctrls[2].value/zctrls[2].value_range, zctrls[3].value/zctrls[3].value_range]
		x1 = self.adsr_click_values[0] * dx
		x2 = x1 + self.adsr_click_values[1] * dx
		x3 = self.width - self.adsr_click_values[3] * dx
		if event.x > x3 - dx / 4:
			# Release - up to a 1/4 into the sustain range
			self.drag_zctrl = zctrls[3]
		elif event.x > x2 + dx / 4:
			# Sustain - within the centre 1/2 of the sustain range
			self.drag_zctrl = zctrls[2]
		elif event.x > x1 + (x2 - x1) / 2:
			# Decay - from 1/2 way through the decay slope
			self.drag_zctrl = zctrls[1]
		else:
			# Attack - up to 1/4 way through the decay slop
			self.drag_zctrl = zctrls[0]

	def on_canvas_drag(self, event):
		if self.drag_zctrl == None:
			return
		dx = (event.x - self.last_click.x) / (self.width / 4)
		dy = (event.y - self.last_click.y) / int(0.95 * self.height)
		if self.drag_zctrl == self.zyngui_control.zcontrollers[0]:
			self.drag_zctrl.set_value(self.drag_zctrl.value_range * (self.adsr_click_values[0] + dx))
		elif self.drag_zctrl == self.zyngui_control.zcontrollers[1]:
			self.drag_zctrl.set_value(self.drag_zctrl.value_range * (self.adsr_click_values[1] + dx))
		elif self.drag_zctrl == self.zyngui_control.zcontrollers[2]:
			self.drag_zctrl.set_value(self.drag_zctrl.value_range * (self.adsr_click_values[2] - dy))
		elif self.drag_zctrl == self.zyngui_control.zcontrollers[3]:
			self.drag_zctrl.set_value(self.drag_zctrl.value_range * (self.adsr_click_values[3] - dx))
		else:
			return

	def on_canvas_release(self, event):
		self.drag_zctrl = None
		self.widget_canvas.itemconfig(self.drag_polygon, state="hidden")

	def get_monitors(self):
		pass

# ------------------------------------------------------------------------------
