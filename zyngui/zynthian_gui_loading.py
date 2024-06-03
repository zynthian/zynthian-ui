#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Loading Class (busy logo animation)
# 
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
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

# ------------------------------------------------------------------------------
# Zynthian Loading GUI Class (busy logo animation)
# ------------------------------------------------------------------------------


class zynthian_gui_loading:

	def __init__(self):
		self.shown = False
		self.zyngui = zynthian_gui_config.zyngui
		self.width = zynthian_gui_config.display_width
		self.height = zynthian_gui_config.display_height
		# Canvas for loading image animation
		self.canvas = tkinter.Canvas(
			zynthian_gui_config.top,
			width=self.width,
			height=self.height,
			bg=zynthian_gui_config.color_bg,
			bd=0,
			highlightthickness=0)
		self.title_text = self.canvas.create_text(
			self.width//2,
			int(0.15 * self.height),
			anchor=tkinter.CENTER,
			justify=tkinter.CENTER,
			font=zynthian_gui_config.font_topbar,
			fill=zynthian_gui_config.color_header_tx,
			text="")
		self.details_text = self.canvas.create_text(
			self.width//2,
			int(0.85 * self.height),
			anchor=tkinter.CENTER,
			justify=tkinter.CENTER,
			font=(zynthian_gui_config.font_family, int(0.8*zynthian_gui_config.font_size)),
			fill=zynthian_gui_config.color_tx_off,
			text="")
		# Setup Loading Logo Animation
		self.loading_index = 0
		self.loading_item = self.canvas.create_image(self.width//2, self.height//2, image=zynthian_gui_config.loading_imgs[0], anchor=tkinter.CENTER)

	def build_view(self):
		return True

	def hide(self):
		if self.shown:
			self.shown = False
			self.canvas.grid_forget()

	def show(self):
		if not self.shown:
			self.shown = True
			self.canvas.grid()

	def set_error(self, txt):
		self.set_title(txt, zynthian_gui_config.color_error)

	def set_warning(self, txt):
		self.set_title(txt, zynthian_gui_config.color_alt2)

	def set_success(self, txt):
		self.set_title(txt, zynthian_gui_config.color_status_play)

	def set_title(self, txt, color=None):
		if txt is None:
			txt = ""
		if color is None:
			color = zynthian_gui_config.color_header_tx
		self.canvas.itemconfig(self.title_text, text=txt, fill=color)
		# Clear details - must be explicitly set after changing title
		self.set_details("")

	def set_details(self, txt, color=None):
		if txt is None:
			txt = ""
		if color is None:
			color = zynthian_gui_config.color_tx_off
		self.canvas.itemconfig(self.details_text, text=txt, fill=color)

	def refresh_loading(self):
		if self.shown:
			if self.zyngui.state_manager.is_busy():
				self.loading_index += 1
				if self.loading_index >= len(zynthian_gui_config.loading_imgs):
					self.loading_index = 0
				self.canvas.itemconfig(self.loading_item, image=zynthian_gui_config.loading_imgs[self.loading_index])
			else:
				self.reset_loading()

	def reset_loading(self, force=False):
		if self.loading_index > 0 or force:
			self.loading_index = 0
			self.canvas.itemconfig(self.loading_item, image=zynthian_gui_config.loading_imgs[0])

	def zynpot_cb(self, i, dval):
		pass

	def zyncoder_read(self):
		pass

	def switch_select(self, t='S'):
		pass

	def back_action(self):
		return False

# -------------------------------------------------------------------------------
