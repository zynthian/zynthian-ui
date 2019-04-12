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
		self.index = 0
		self.list_data = []
		self.shown = False
		self.zselector = None
		self.zyngui = zynthian_gui_config.zyngui

		self.status_rect = None
		self.status_flags = None
		self.status_midi = None
		self.status_h = zynthian_gui_config.topbar_height
		self.status_l = zynthian_gui_config.topbar_height
		self.status_rh = max(2,zynthian_gui_config.topbar_height/4)
		self.status_fs = int(zynthian_gui_config.topbar_height/3)
		self.status_lpad = self.status_fs

		self.path_canvas_width=zynthian_gui_config.display_width-self.status_l-self.status_lpad
		self.select_path_font=tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=zynthian_gui_config.font_topbar[1])
		self.select_path_width=0
		self.select_path_offset=0
		self.select_path_dir=2

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
		# Setup Topbar's Callback
		self.tb_frame.bind("<Button-1>", self.cb_topbar)

		# Topbar's Path Canvas
		self.path_canvas = tkinter.Canvas(self.tb_frame,
			width=self.path_canvas_width,
			height=zynthian_gui_config.topbar_height,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg = zynthian_gui_config.color_bg)
		self.path_canvas.grid(row=0, column=0, sticky="wns")
		# Setup Topbar's Callback
		self.path_canvas.bind("<Button-1>", self.cb_topbar)

		# Topbar's Select Path
		self.select_path = tkinter.StringVar()
		self.select_path.trace("w", self.cb_select_path)
		self.label_select_path = tkinter.Label(self.path_canvas,
			font=zynthian_gui_config.font_topbar,
			textvariable=self.select_path,
			justify=tkinter.LEFT,
			bg=zynthian_gui_config.color_header_bg,
			fg=zynthian_gui_config.color_header_tx)
		self.label_select_path.place(x=0, y=0)

		# Canvas for displaying status: CPU, ...
		self.status_canvas = tkinter.Canvas(self.tb_frame,
			width=self.status_l,
			height=self.status_h,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg = zynthian_gui_config.color_bg)
		self.status_canvas.grid(row=0, column=1, sticky="ens", padx=(self.status_lpad,0))

		# Configure Topbar's Frame column widths
		self.tb_frame.grid_columnconfigure(0, minsize=self.path_canvas_width)

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
		self.loading_canvas.bind("<Button-1>",self.cb_loading_push)
		self.loading_canvas.bind("<ButtonRelease-1>",self.cb_loading_release)

		# Setup Loading Logo Animation
		self.loading_index=0
		self.loading_item=self.loading_canvas.create_image(3, 3, image = zynthian_gui_config.loading_imgs[0], anchor=tkinter.NW)

		# Selector Controller Caption
		self.selector_caption=selcap

		# Update Title
		self.set_select_path()
		self.cb_scroll_select_path()


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


	def refresh_status(self, status={}):
		if self.shown:
			# Display CPU-load bar
			l = int(status['cpu_load']*self.status_l/100)
			cr = int(status['cpu_load']*255/100)
			cg = 255-cr
			color = "#%02x%02x%02x" % (cr,cg,0)
			try:
				if self.status_rect:
					self.status_canvas.coords(self.status_rect,(0, 0, l, self.status_rh))
					self.status_canvas.itemconfig(self.status_rect, fill=color)
				else:
					self.status_rect=self.status_canvas.create_rectangle((0, 0, l, self.status_rh), fill=color, width=0)
			except Exception as e:
				logging.error(e)

			# Display flags
			flags = ""
			color = zynthian_gui_config.color_status_error
			if 'xrun' in status and status['xrun']:
				flags = "\U0000f071"
			elif 'undervoltage' in status and status['undervoltage']:
				flags = "\U0000f0e7";
			elif 'overtemp' in status and status['overtemp']:
				flags = "\U0000f2c7"
			else:
				if 'audio_recorder' in status:
					if status['audio_recorder']=='REC':
						flags = "\U0000f192"
						color = zynthian_gui_config.color_status_record
					elif status['audio_recorder']=='PLAY':
						flags = "\U0000f04b"
						color = zynthian_gui_config.color_status_play
					elif status['audio_recorder']=='PLAY+REC':
						flags = "\U0000f144"
						color = zynthian_gui_config.color_status_record
				if not flags and 'midi_recorder' in status:
					if status['midi_recorder']=='REC':
						flags = "\U0000f192"
						color = zynthian_gui_config.color_status_record
					elif status['midi_recorder']=='PLAY':
						flags = "\U0000f04b"
						color = zynthian_gui_config.color_status_play
					elif status['midi_recorder']=='PLAY+REC':
						flags = "\U0000f144"
						color = zynthian_gui_config.color_status_record

			if not self.status_flags:
				self.status_flags = self.status_canvas.create_text(
					int(self.status_fs),
					int(self.status_h*0.6),
					width=int(self.status_fs),
					justify=tkinter.RIGHT,
					fill=color,
					font=(zynthian_gui_config.font_status,self.status_fs),
					text=flags)
			else:
				self.status_canvas.itemconfig(self.status_flags, text=flags, fill=color)

			# Display MIDI flag
			flags=""
			if 'midi' in status and status['midi']:
				flags="\U0000f35a";
			else:
				flags=""
			if not self.status_midi:
				self.status_midi = self.status_canvas.create_text(
					int(self.status_l-self.status_fs*0.7),
					int(self.status_h*0.6),
					width=int(self.status_fs),
					justify=tkinter.RIGHT,
					fill=zynthian_gui_config.color_status_midi,
					font=(zynthian_gui_config.font_status,self.status_fs),
					text=flags)
			else:
				self.status_canvas.itemconfig(self.status_midi, text=flags)


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


	def update_list(self):	
		self.fill_list()
		self.set_selector()


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
			if self.index!=self.zselector.value:
				self.select_listbox(self.zselector.value)


	def select_listbox(self,index):
		self.listbox.selection_clear(0,tkinter.END)
		self.listbox.selection_set(index)
		if index>self.index: self.listbox.see(index+1)
		elif index<self.index: self.listbox.see(index-1)
		else: self.listbox.see(index)
		self.index=index


	def click_listbox(self, index=None, t='S'):
		if index is not None:
			self.select_listbox(index)
		else:
			self.index=self.get_cursel()

		self.select_action(self.index, t)


	def switch_select(self, t='S'):
		self.click_listbox(None, t)


	def select(self, index=None):
		if index is None: index=self.index
		self.select_listbox(index)
		if self.zselector and self.zselector.value!=self.index:
			self.zselector.set_value(self.index, True)


	def select_up(self, n=1):
		self.select(self.index+n)


	def select_down(self, n=1):
		self.select(self.index-n)


	def select_action(self, index, t='S'):
		pass


	def set_select_path(self):
		pass


	def cb_topbar(self,event):
		self.zyngui.zynswitch_defered('S',1)


	def cb_listbox_push(self,event):
		self.listbox_push_ts=datetime.now()
		#logging.debug("LISTBOX PUSH => %s" % (self.listbox_push_ts))


	def cb_listbox_release(self,event):
		dts=(datetime.now()-self.listbox_push_ts).total_seconds()
		#logging.debug("LISTBOX RELEASE => %s" % dts)
		if dts < 0.3:
			self.zyngui.zynswitch_defered('S',3)
		elif dts>=0.3 and dts<2:
			self.zyngui.zynswitch_defered('B',3)


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


	def cb_loading_push(self,event):
		self.loading_push_ts=datetime.now()
		#logging.debug("LOADING PUSH => %s" % self.canvas_push_ts)


	def cb_loading_release(self,event):
		dts=(datetime.now()-self.loading_push_ts).total_seconds()
		logging.debug("LOADING RELEASE => %s" % dts)
		if dts<0.3:
			self.zyngui.zynswitch_defered('S',2)
		elif dts>=0.3 and dts<2:
			self.zyngui.zynswitch_defered('B',2)
		elif dts>=2:
			self.zyngui.zynswitch_defered('L',2)


	def cb_select_path(self, *args):
		self.select_path_width=self.select_path_font.measure(self.select_path.get())
		self.select_path_offset = 0;
		self.select_path_dir = 2
		self.label_select_path.place(x=0, y=0)

	def cb_scroll_select_path(self):
		if self.shown:
			if self.dscroll_select_path():
				zynthian_gui_config.top.after(1000, self.cb_scroll_select_path)
				return

		zynthian_gui_config.top.after(100, self.cb_scroll_select_path)


	def dscroll_select_path(self):

		if self.select_path_width>self.path_canvas_width:
			#Scroll label
			self.select_path_offset += self.select_path_dir
			self.label_select_path.place(x=-self.select_path_offset, y=0)

			#Change direction ...
			if self.select_path_offset > (self.select_path_width-self.path_canvas_width):
				self.select_path_dir = -2
				return True
			elif self.select_path_offset<=0:
				self.select_path_dir = 2
				return True

		elif self.select_path_offset!=0:
			self.select_path_offset = 0;
			self.select_path_dir = 2
			self.label_select_path.place(x=0, y=0)

		return False

#------------------------------------------------------------------------------
