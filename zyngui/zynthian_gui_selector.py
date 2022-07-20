#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Selector Base Class
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
import logging
import tkinter
from datetime import datetime
from tkinter import font as tkFont
from PIL import Image, ImageTk

# Zynthian specific modules
from zyngine import zynthian_controller
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_base import zynthian_gui_base
from zyngui.zynthian_gui_controller import zynthian_gui_controller

#------------------------------------------------------------------------------
# Zynthian Listbox Selector GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_selector(zynthian_gui_base):

	# Scale for listbox swipe action after-roll
	swipe_roll_scale = [1,0,1,1,1,1,4,4,4,4,4,4,4,4,4,4] #1,0,1,0,1,0,1,0,


	def __init__(self, selcap='Select', wide=False, loading_anim=True):

		super().__init__()

		self.index = 0
		self.list_data = []
		self.zselector = None
		self.zselector_hiden = False
		self.swipe_speed = 0
		self.list_entry_height = int(1.8 * zynthian_gui_config.font_size) # Set approx. here to avoid errors. Set accurately when list item selected
		self.listbox_motion_last_dy = 0

		# ListBox
		self.listbox = tkinter.Listbox(self.main_frame,
			font=zynthian_gui_config.font_listbox,
			bd=7,
			highlightthickness=0,
			relief='flat',
			bg=zynthian_gui_config.color_panel_bg,
			fg=zynthian_gui_config.color_panel_tx,
			selectbackground=zynthian_gui_config.color_ctrl_bg_on,
			selectforeground=zynthian_gui_config.color_ctrl_tx,
			selectmode=tkinter.SINGLE)

		# Columns 0 & 2 may contain zctrls. If not then they are empty and hence not visible
		# Column 1 may contain listbox
		self.main_frame.columnconfigure(1, weight=1)

		# Rows 0 & 1 may contain zctrls. Rows 2 & 3 may contain zctrls, e.g. 4 controls on RHS.
		# Row 0 contains list which spans all controller rows
		self.main_frame.rowconfigure(0, weight=1)

		if wide:
			# Do not show controls in column 0
			self.listbox.grid(row=0, column=1, rowspan=4, padx=(0,2), sticky="wens")
		else:
			self.listbox.grid(row=0, column=1, rowspan=4, padx=(2,2), sticky="wens")


		# Bind listbox events
		self.listbox_push_ts = datetime.now()
		self.listbox.bind("<Button-1>",self.cb_listbox_push)
		self.listbox.bind("<ButtonRelease-1>",self.cb_listbox_release)
		self.listbox.bind("<B1-Motion>",self.cb_listbox_motion)
		self.listbox.bind("<Button-4>",self.cb_listbox_wheel)
		self.listbox.bind("<Button-5>",self.cb_listbox_wheel)

		if loading_anim:
			# Canvas for loading image animation
			if zynthian_gui_config.ctrl_both_sides:
				h = zynthian_gui_config.ctrl_height - 1
			else:
				h = 3 * zynthian_gui_config.ctrl_height + 1
			self.loading_canvas = tkinter.Canvas(self.main_frame,
				width = zynthian_gui_config.ctrl_width,
				height = h,
				bd=0,
				highlightthickness=0,
				bg = zynthian_gui_config.color_bg)
			self.loading_canvas.grid(row=0, column=2, sticky="nesw")
			self.loading_push_ts = None
			self.loading_canvas.bind("<Button-1>",self.cb_loading_push)
			self.loading_canvas.bind("<ButtonRelease-1>",self.cb_loading_release)

			# Setup Loading Logo Animation
			self.loading_index = 0
			self.loading_item = self.loading_canvas.create_image(3, 3, image = zynthian_gui_config.loading_imgs[0], anchor=tkinter.NW)
		else:
			self.loading_canvas = None
			self.loading_index = 0
			self.loading_item = None

		# Selector Controller Caption
		self.selector_caption = selcap


	def show(self):
		super().show()
		self.fill_list()
		self.set_selector()
		self.set_select_path()


	def refresh_loading(self):
		if self.shown and self.loading_canvas:
			try:
				if self.zyngui.loading:
					self.loading_index=self.loading_index+1
					if self.loading_index>len(zynthian_gui_config.loading_imgs)+1: self.loading_index=0
					self.loading_canvas.itemconfig(self.loading_item, image=zynthian_gui_config.loading_imgs[self.loading_index])
				else:
					self.reset_loading()
			except:
				self.reset_loading()


	def reset_loading(self, force=False):
		if self.loading_canvas and (self.loading_index>0 or force):
			self.loading_index=0
			self.loading_canvas.itemconfig(self.loading_item, image=zynthian_gui_config.loading_imgs[0])


	def fill_listbox(self):
		self.listbox.delete(0, tkinter.END)
		if not self.list_data:
			self.list_data=[]
		for i, item in enumerate(self.list_data):
			self.listbox.insert(tkinter.END, item[2])


	def set_selector(self, zs_hiden=True):
		if self.shown:
			if self.zselector:
				self.zselector.zctrl.set_options({ 'symbol':self.selector_caption, 'name':self.selector_caption, 'short_name':self.selector_caption, 'value_min':0, 'value_max':len(self.list_data), 'value':self.index })
				self.zselector.config(self.zselector.zctrl)
				self.zselector.show()
			else:
				zselector_ctrl = zynthian_controller(None ,self.selector_caption, self.selector_caption, { 'value_max':len(self.list_data), 'value':self.index })
				self.zselector = zynthian_gui_controller(zynthian_gui_config.select_ctrl, self.main_frame, zselector_ctrl, zs_hiden, selcounter=True)


	def plot_zctrls(self):
		if self.zselector.zctrl.is_dirty:
			self.zselector.calculate_plot_values()
		self.zselector.plot_value()
		if self.swipe_speed > 0:
			self.swipe_speed -= 1
			self.listbox.yview_scroll(self.swipe_dir * self.swipe_roll_scale[self.swipe_speed], tkinter.UNITS)


	def fill_list(self):
		self.fill_listbox()
		self.select()
		self.last_index_change_ts = datetime.min


	def update_list(self):
		yv = self.listbox.yview()
		self.fill_list()
		self.set_selector()
		self.listbox.yview_moveto(yv[0])


	def get_cursel(self):
		cursel = self.listbox.curselection()
		if (len(cursel) > 0):
			index = int(cursel[0])
		else:
			index=0
		return index


	def select_listbox(self, index, see=True):
		if index < 0:
			index = 0
		elif index >= len(self.list_data):
			index = len(self.list_data) - 1
		if not self.skip_separators(index):
			# Set selection
			self.listbox.selection_clear(0 ,tkinter.END)
			self.listbox.selection_set(index)
			# Set window
			if see:
				if index > self.index:
					self.listbox.see(index + 1)
				elif index < self.index:
					self.listbox.see(index - 1)
				else:
					self.listbox.see(index)
				if self.listbox.bbox(index):
					self.list_entry_height = self.listbox.bbox(index)[3]
			# Set index value
			self.index = index
			self.last_index_change_ts = datetime.now()


	def select_listbox_by_name(self, name):
		names = self.listbox.get(0, self.listbox.size())
		try:
			index = names.index(name)
			self.select(index)
		except:
			logging.debug("%s is not in listbox", name)


	def skip_separators(self, index):
		# Skip separator items ...
		if index>=0 and index<len(self.list_data) and self.list_data[index][0] is None:
			if self.index<=index:
				if index<len(self.list_data)-1:
					self.select_listbox(index + 1)
				else:
					self.select_listbox(index - 1)
			elif self.index>index:
				if index>0:
					self.select_listbox(index - 1)
				else:
					self.select_listbox(index + 1)
			return True
		else:
			return False


	def select(self, index=None):
		if index is None: index = self.index
		self.select_listbox(index)
		if self.shown and self.zselector and self.zselector.zctrl.value != self.index:
			self.zselector.zctrl.set_value(self.index, False)
			self.last_index_change_ts = datetime.now()


	def click_listbox(self, index=None, t='S'):
		if index is not None:
			self.select(index)
		else:
			self.skip_separators(self.get_cursel())

		self.select_action(self.index, t)


	# Function to handle select switch press
	#	typ: Press type ["S"=Short, "B"=Bold, "L"=Long]
	def switch_select(self, t='S'):
		self.click_listbox(None, t)


	def select_action(self, index, t='S'):
		pass


	#--------------------------------------------------------------------------
	# Zynpot Callbacks (rotaries!)
	#--------------------------------------------------------------------------

	def zynpot_cb(self, i, dval):
		if self.shown and self.zselector and self.zselector.index==i:
			self.zselector.zynpot_cb(dval)
			if self.index != self.zselector.zctrl.value:
				self.select(self.zselector.zctrl.value)
			return True
		return False


	def arrow_up(self):
		self.select(self.index - 1)


	def arrow_down(self):
		self.select(self.index + 1)


	#--------------------------------------------------------------------------
	# Keyboard & Mouse/Touch Callbacks
	#--------------------------------------------------------------------------

	def cb_listbox_push(self,event):
		self.listbox_push_ts = datetime.now() # Timestamp of initial touch
		#logging.debug("LISTBOX PUSH => %s" % (self.listbox_push_ts))
		self.listbox_y0 = event.y # Touch y-coord of initial touch
		self.swiping = False # True if swipe action in progress (disables press action)
		self.swipe_speed = 0 # Speed of swipe used for rolling after release
		return "break" # Don't select entry on push


	def cb_listbox_release(self, event):
		dts = (datetime.now() - self.listbox_push_ts).total_seconds()
		if self.swiping:
			self.swipe_speed = int(len(self.swipe_roll_scale) - ((dts - 0.02) / 0.06) * len(self.swipe_roll_scale))
			self.swipe_speed = min(self.swipe_speed, len(self.swipe_roll_scale) - 1)
			self.swipe_speed = max(self.swipe_speed, 0)
		else:
			if dts < 0.03:
				return # Debounce
			#logging.debug("LISTBOX RELEASE => %s" % dts)
			cursel = self.listbox.nearest(event.y)
			if self.index != cursel:
				self.select(cursel)
			if dts < zynthian_gui_config.zynswitch_bold_seconds:
				self.zyngui.zynswitch_defered('S',3)
			elif dts >= zynthian_gui_config.zynswitch_bold_seconds and dts < zynthian_gui_config.zynswitch_long_seconds:
				self.zyngui.zynswitch_defered('B',3)


	def cb_listbox_motion(self, event):
			dy = self.listbox_y0 - event.y
			offset = int(dy / self.list_entry_height)
			if offset:
				self.swiping = True
				self.listbox.yview_scroll(offset, tkinter.UNITS)
				self.swipe_dir = abs(dy) // dy
				self.listbox_y0 = event.y + self.swipe_dir * (abs(dy) % self.list_entry_height)
				self.listbox_push_ts = datetime.now() # Use time delta between last motion and release to determine speed of swipe


	def cb_listbox_wheel(self, event):
		if (event.num == 5 or event.delta == -120):
			self.select(self.index + 1)
		elif (event.num == 4 or event.delta == 120):
			self.select(self.index - 1)
		return "break" # Consume event to stop scrolling of listbox


	def cb_loading_push(self, event):
		self.loading_push_ts = datetime.now()
		#logging.debug("LOADING PUSH => %s" % self.loading_push_ts)


	def cb_loading_release(self,event):
		if self.loading_push_ts:
			dts=(datetime.now()-self.loading_push_ts).total_seconds()
			logging.debug("LOADING RELEASE => %s" % dts)
			if dts<zynthian_gui_config.zynswitch_bold_seconds:
				self.zyngui.zynswitch_defered('S',2)
			elif dts>=zynthian_gui_config.zynswitch_bold_seconds and dts<zynthian_gui_config.zynswitch_long_seconds:
				self.zyngui.zynswitch_defered('B',2)
			elif dts>=zynthian_gui_config.zynswitch_long_seconds:
				self.zyngui.zynswitch_defered('L',2)

#------------------------------------------------------------------------------
