#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Selector Base Class
# 
# Copyright (C) 2015-2016 Fernando Moyano <jofemodo@zynthian.org>
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
from . import zynthian_gui_config
from . import zynthian_gui_controller

#------------------------------------------------------------------------------
# Configure logging
#------------------------------------------------------------------------------

# Set root logging level
logging.basicConfig(stream=sys.stderr, level=zynthian_gui_config.log_level)

#------------------------------------------------------------------------------
# Zynthian Listbox Selector GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_selector:

	def __init__(self, selcap='Select', wide=False):
		self.index=0
		self.list_data=[]
		self.shown=False
		self.zselector=None

		# Listbox Size
		self.lb_height=zynthian_gui_config.display_height-zynthian_gui_config.topbar_height
		self.wide=wide
		if self.wide:
			self.lb_width=zynthian_gui_config.display_width-zynthian_gui_config.ctrl_width
		else:
			self.lb_width=zynthian_gui_config.display_width-2*zynthian_gui_config.ctrl_width-2

		# Main Frame
		self.main_frame = tkinter.Frame(zynthian_gui_config.top,
			width=zynthian_gui_config.display_width,
			height=zynthian_gui_config.display_height,
			bg=zynthian_gui_config.color_bg)

		# Topbar's frame
		self.tb_frame = tkinter.Frame(self.main_frame, 
			width=zynthian_gui_config.display_width,
			height=zynthian_gui_config.topbar_height,
			bg=zynthian_gui_config.color_bg)
		self.tb_frame.grid(row=0, column=0, columnspan=3)
		self.tb_frame.grid_propagate(False)

		# Topbar's Select Path
		self.select_path = tkinter.StringVar()
		self.label_select_path = tkinter.Label(self.tb_frame,
			font=zynthian_gui_config.font_topbar,
			textvariable=self.select_path,
			#wraplength=80,
			justify=tkinter.LEFT,
			bg=zynthian_gui_config.color_header_bg,
			fg=zynthian_gui_config.color_header_tx)
		self.label_select_path.grid(sticky="wns")
		# Setup Topbar's Callback
		self.label_select_path.bind("<Button-1>", self.cb_topbar)

		# ListBox's frame
		self.lb_frame = tkinter.Frame(self.main_frame,
			width=self.lb_width,
			height=self.lb_height,
			bg=zynthian_gui_config.color_bg)
		if self.wide:
			if zynthian_gui_config.select_ctrl>1:
				self.lb_frame.grid(row=1, column=0, rowspan=2, columnspan=2, padx=(0,2), sticky="w")
			else:
				self.lb_frame.grid(row=1, column=1, rowspan=2, columnspan=2, padx=(2,0), sticky="e")
		else:
			if zynthian_gui_config.select_ctrl>1:
				self.lb_frame.grid(row=1, column=1, rowspan=2, padx=(2,2), sticky="w")
			else:
				self.lb_frame.grid(row=1, column=1, rowspan=2, padx=(2,2), sticky="e")
		#self.lb_frame.columnconfigure(0, weight=10)
		self.lb_frame.rowconfigure(0, weight=10)
		self.lb_frame.grid_propagate(False)

		# ListBox
		self.listbox = tkinter.Listbox(self.lb_frame,
			font=zynthian_gui_config.font_listbox,
			bd=7,
			highlightthickness=0,
			relief='flat',
			bg=zynthian_gui_config.color_panel_bg,
			fg=zynthian_gui_config.color_panel_tx,
			selectbackground=zynthian_gui_config.color_ctrl_bg_on,
			selectforeground=zynthian_gui_config.color_ctrl_tx,
			selectmode=tkinter.BROWSE)
		self.listbox.grid(sticky="wens")
		# Bind listbox events
		self.listbox.bind("<Button-1>",self.cb_listbox_push)
		self.listbox.bind("<ButtonRelease-1>",self.cb_listbox_release)
		self.listbox.bind("<B1-Motion>",self.cb_listbox_motion)
		self.listbox.bind("<Button-4>",self.cb_listbox_wheel)
		self.listbox.bind("<Button-5>",self.cb_listbox_wheel)

		# Canvas for loading image animation
		self.loading_canvas = tkinter.Canvas(self.main_frame,
			width=zynthian_gui_config.ctrl_width,
			height=zynthian_gui_config.ctrl_height-1,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg = zynthian_gui_config.color_bg)
		self.loading_canvas.grid(row=1,column=2,sticky="ne")

		# Setup Loading Logo Animation
		self.loading_index=0
		self.loading_item=self.loading_canvas.create_image(3, 3, image = zynthian_gui_config.loading_imgs[0], anchor=tkinter.NW)

		# Selector Controller Caption
		self.selector_caption=selcap

		# Update Title
		self.set_select_path()

	def show(self):
		if not self.shown:
			self.shown=True
			self.main_frame.grid()
		self.fill_list()
		self.set_selector()
		self.set_select_path()

	def hide(self):
		if self.shown:
			self.shown=False
			self.main_frame.grid_forget()

	def is_shown(self):
		try:
			self.main_frame.grid_info()
			return True
		except:
			return False

	def refresh_loading(self):
		if self.shown:
			try:
				if zynthian_gui_config.zyngui.loading:
					self.loading_index=self.loading_index+1
					if self.loading_index>len(zynthian_gui_config.loading_imgs)+1: self.loading_index=0
					self.loading_canvas.itemconfig(self.loading_item, image=zynthian_gui_config.loading_imgs[self.loading_index])
				else:
					self.reset_loading()
			except:
				self.reset_loading()

	def reset_loading(self, force=False):
		if self.loading_index>0 or force:
			self.loading_index=0
			self.loading_canvas.itemconfig(self.loading_item, image=zynthian_gui_config.loading_imgs[0])

	def fill_listbox(self):
		self.listbox.delete(0, tkinter.END)
		if not self.list_data:
			self.list_data=[]
		for item in self.list_data:
			self.listbox.insert(tkinter.END, item[2])

	def set_selector(self):
		if self.zselector:
			self.zselector_ctrl.set_options({ 'symbol':self.selector_caption, 'name':self.selector_caption, 'short_name':self.selector_caption, 'midi_cc':0, 'value_max':len(self.list_data), 'value':self.index })
			self.zselector.config(self.zselector_ctrl)
			self.zselector.show()
		else:
			self.zselector_ctrl=zynthian_controller(None,self.selector_caption,self.selector_caption,{ 'midi_cc':0, 'value_max':len(self.list_data), 'value':self.index })
			self.zselector=zynthian_gui_controller(zynthian_gui_config.select_ctrl,self.main_frame,self.zselector_ctrl)

	def fill_list(self):
		self.fill_listbox()
		self.select()
		#self.set_selector()

	def get_cursel(self):
		cursel=self.listbox.curselection()
		if (len(cursel)>0):
			index=int(cursel[0])
		else:
			index=0
		return index

	def zyncoder_read(self):
		if self.zselector:
			self.zselector.read_zyncoder()
			if (self.index!=self.zselector.value):
				self.select_listbox(self.zselector.value)

	def select_listbox(self,index):
		self.listbox.selection_clear(0,tkinter.END)
		self.listbox.selection_set(index)
		if index>self.index: self.listbox.see(index+1)
		elif index<self.index: self.listbox.see(index-1)
		else: self.listbox.see(index)
		self.index=index

	def click_listbox(self, index=None):
		if index is not None:
			self.select_listbox(index)
		else:
			self.index=self.get_cursel()
		self.select_action(self.index)

	def switch_select(self):
		self.click_listbox()

	def select(self, index=None):
		if index is None: index=self.index
		self.select_listbox(index)

	def select_action(self, index):
		pass

	def set_select_path(self):
		pass

	def cb_topbar(self,event):
		zynthian_gui_config.zyngui.zynswitch_defered('S',1)

	def cb_listbox_push(self,event):
		self.listbox_push_ts=datetime.now()
		#logging.debug("LISTBOX PUSH => %s" % (self.listbox_push_ts))

	def cb_listbox_release(self,event):
		dts=(datetime.now()-self.listbox_push_ts).total_seconds()
		#logging.debug("LISTBOX RELEASE => %s" % dts)
		if dts < 0.3:
			zynthian_gui_config.zyngui.zynswitch_defered('S',3)

	def cb_listbox_motion(self,event):
		dts=(datetime.now()-self.listbox_push_ts).total_seconds()
		if dts > 0.1:
			#logging.debug("LISTBOX MOTION => %d" % self.index)
			self.zselector.set_value(self.get_cursel(), True)

	def cb_listbox_wheel(self,event):
		index = self.index
		if (event.num == 5 or event.delta == -120) and self.index>0:
			index -= 1
		if (event.num == 4 or event.delta == 120) and self.index < (len(self.list_data)-1):
			index += 1
		if index!=self.index:
			self.zselector.set_value(index, True)

#------------------------------------------------------------------------------
