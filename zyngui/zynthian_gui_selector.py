#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Selector Base Class
# 
# Copyright (C) 2015-2020 Fernando Moyano <jofemodo@zynthian.org>
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

	def __init__(self, selcap='Select', wide=False):
		super().__init__()

		self.index = 0
		self.list_data = []
		self.zselector = None
		self.zselector_hiden = False

		# Listbox Size
		self.lb_height=zynthian_gui_config.body_height+1
		self.wide=wide
		if self.wide:
			self.lb_width=zynthian_gui_config.display_width-zynthian_gui_config.ctrl_width
		else:
			self.lb_width=zynthian_gui_config.display_width-2*zynthian_gui_config.ctrl_width-2

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
		self.lb_frame.columnconfigure(0, weight=10)
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
		self.listbox_push_ts = None
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
		self.loading_push_ts = None
		self.loading_canvas.bind("<Button-1>",self.cb_loading_push)
		self.loading_canvas.bind("<ButtonRelease-1>",self.cb_loading_release)

		# Init touchbar
		self.init_buttonbar()

		# Setup Loading Logo Animation
		self.loading_index=0
		self.loading_item=self.loading_canvas.create_image(3, 3, image = zynthian_gui_config.loading_imgs[0], anchor=tkinter.NW)

		# Selector Controller Caption
		self.selector_caption=selcap


	def show(self):
		super().show()
		self.fill_list()
		self.set_selector()
		self.set_select_path()


	def refresh_loading(self):
		if self.shown:
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
		if self.loading_index>0 or force:
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
				self.zselector_ctrl.set_options({ 'symbol':self.selector_caption, 'name':self.selector_caption, 'short_name':self.selector_caption, 'midi_cc':0, 'value_max':len(self.list_data), 'value':self.index })
				self.zselector.config(self.zselector_ctrl)
				self.zselector.show()
			else:
				self.zselector_ctrl=zynthian_controller(None,self.selector_caption,self.selector_caption,{ 'midi_cc':0, 'value_max':len(self.list_data), 'value':self.index })
				self.zselector=zynthian_gui_controller(zynthian_gui_config.select_ctrl,self.main_frame,self.zselector_ctrl,zs_hiden)


	def plot_zctrls(self):
		self.zselector.plot_value()


	def fill_list(self):
		self.fill_listbox()
		self.select()
		#self.set_selector()
		self.last_index_change_ts = datetime.min


	def update_list(self):
		yv = self.listbox.yview()
		self.fill_list()
		self.set_selector()
		self.listbox.yview_moveto(yv[0])


	def get_cursel(self):
		cursel=self.listbox.curselection()
		if (len(cursel)>0):
			index=int(cursel[0])
		else:
			index=0
		return index


	def zyncoder_read(self):
		if self.shown and self.zselector:
			self.zselector.read_zyncoder()
			if self.index!=self.zselector.value:
				self.select(self.zselector.value)
		return [0,1,2]


	def select_listbox(self,index):
		if index>=0 and index<len(self.list_data):
			if not self.skip_separators(index):
				# Set selection
				self.listbox.selection_clear(0,tkinter.END)
				self.listbox.selection_set(index)
				# Set window
				if index>self.index: self.listbox.see(index+1)
				elif index<self.index: self.listbox.see(index-1)
				else: self.listbox.see(index)
				# Set index value
				self.index=index
				self.last_index_change_ts=datetime.now()


	def skip_separators(self, index):
		# Skip separator items ...
		if self.list_data[index][0] is None:
			if self.index<=index:
				self.select_listbox(index+1)
			elif self.index>index:
				self.select_listbox(index-1)
			return True
		else:
			return False


	def select(self, index=None):
		if index is None: index=self.index
		self.select_listbox(index)
		if self.shown and self.zselector and self.zselector.value!=self.index:
			self.zselector.set_value(self.index, True, False)


	def select_up(self, n=1):
		self.select(self.index-n)


	def select_down(self, n=1):
		self.select(self.index+n)


	def click_listbox(self, index=None, t='S'):
		if index is not None:
			self.select(index)
		else:
			self.skip_separators(self.get_cursel())

		self.select_action(self.index, t)


	def switch_select(self, t='S'):
		self.click_listbox(None, t)


	def select_action(self, index, t='S'):
		pass


	def cb_listbox_push(self,event):
		self.listbox_push_ts=datetime.now()
		#logging.debug("LISTBOX PUSH => %s" % (self.listbox_push_ts))


	def cb_listbox_release(self,event):
		if self.listbox_push_ts:
			dts=(datetime.now()-self.listbox_push_ts).total_seconds()
			#logging.debug("LISTBOX RELEASE => %s" % dts)
			self.zselector.set_value(self.get_cursel(), True, False)
			if dts < 0.3:
				self.zyngui.zynswitch_defered('S',3)
			elif dts>=0.3 and dts<2:
				self.zyngui.zynswitch_defered('B',3)


	def cb_listbox_motion(self,event):
		if self.listbox_push_ts:
			dts=(datetime.now()-self.listbox_push_ts).total_seconds()
			if dts > 0.1:
				#logging.debug("LISTBOX MOTION => %d" % self.index)
				self.zselector.set_value(self.get_cursel(), True, False)


	def cb_listbox_wheel(self,event):
		index = self.index
		if (event.num == 5 or event.delta == -120) and self.index>0:
			index -= 1
		if (event.num == 4 or event.delta == 120) and self.index < (len(self.list_data)-1):
			index += 1
		if index!=self.index:
			self.zselector.set_value(index, True, False)


	def cb_loading_push(self,event):
		self.loading_push_ts=datetime.now()
		#logging.debug("LOADING PUSH => %s" % self.canvas_push_ts)


	def cb_loading_release(self,event):
		if self.loading_push_ts:
			dts=(datetime.now()-self.loading_push_ts).total_seconds()
			logging.debug("LOADING RELEASE => %s" % dts)
			if dts<0.3:
				self.zyngui.zynswitch_defered('S',2)
			elif dts>=0.3 and dts<2:
				self.zyngui.zynswitch_defered('B',2)
			elif dts>=2:
				self.zyngui.zynswitch_defered('L',2)

#------------------------------------------------------------------------------
