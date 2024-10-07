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

		# Create custom GUI elements (position and size set when canvas is grid and size applied)
		adsr_outline_color = zynthian_gui_config.color_low_on
		adsr_color = zynthian_gui_config.color_variant(zynthian_gui_config.color_low_on, -70)
		self.adsr_polygon = self.widget_canvas.create_polygon([0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
															outline=adsr_outline_color, fill=adsr_color, width=3)

	def on_size(self, event):
		if event.width == self.width and event.height == self.height:
			return
		super().on_size(event)
		self.widget_canvas.grid(row=0, column=0, sticky='news')
		self.last_adsr_values = []
		self.refresh_gui()

	def refresh_gui(self):
		zctrls = self.zyngui_control.zcontrollers
		adsr_values = [zctrls[0].value, zctrls[1].value, zctrls[2].value, zctrls[3].value]
		# TODO => Normalize (0.0 to 1.0) ADSR values if needed
		if adsr_values != self.last_adsr_values:
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

	def get_monitors(self):
		pass

# ------------------------------------------------------------------------------
