#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Instrument-Control Class
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
import copy
import logging
import tkinter
from time import sleep
from string import Template
from datetime import datetime
from threading  import Lock

# Zynthian specific modules
from zyngine import zynthian_controller
from . import zynthian_gui_config
from . import zynthian_gui_controller
from . import zynthian_gui_selector

#------------------------------------------------------------------------------
# Configure logging
#------------------------------------------------------------------------------

# Set root logging level
logging.basicConfig(stream=sys.stderr, level=zynthian_gui_config.log_level)

#------------------------------------------------------------------------------
# Zynthian Instrument Controller GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_control(zynthian_gui_selector):
	mode=None

	ctrl_screens={}
	zcontrollers=[]
	screen_name=None

	zgui_controllers=[]
	zgui_controllers_map={}

	def __init__(self):
		super().__init__('Controllers',False)
		# Create Lock object to avoid concurrence problems
		self.lock=Lock();
		# Create "pusher" canvas => used in mode "select"
		self.pusher= tkinter.Frame(self.main_frame,
			width=zynthian_gui_config.ctrl_width,
			height=zynthian_gui_config.ctrl_height-1,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg = zynthian_gui_config.color_bg)

	def show(self):
		super().show()
		self.click_listbox()

	def hide(self):
		if self.shown:
			super().hide()
			for zc in self.zgui_controllers: zc.hide()
			if self.zselector: self.zselector.hide()

	def fill_list(self):
		self.list_data=[]
		i=0
		for cscr in zynthian_gui_config.zyngui.curlayer.get_ctrl_screens():
			self.list_data.append((cscr,i,cscr))
			i=i+1
		self.index=zynthian_gui_config.zyngui.curlayer.get_active_screen_index()
		super().fill_list()

	def set_selector(self):
		if self.mode=='select': super().set_selector()

	#def get_controllers(self):
	#	return 

	def set_controller_screen(self):
		#Get Mutex Lock 
		self.lock.acquire()
		#Get controllers for the current screen
		zynthian_gui_config.zyngui.curlayer.set_active_screen_index(self.index)
		self.zcontrollers=zynthian_gui_config.zyngui.curlayer.get_active_screen()
		#Setup GUI Controllers
		if self.zcontrollers:
			logging.debug("SET CONTROLLER SCREEN %s" % (zynthian_gui_config.zyngui.curlayer.ctrl_screen_active))
			#Configure zgui_controllers
			i=0
			for ctrl in self.zcontrollers:
				try:
					#logging.debug("CONTROLLER ARRAY %d => %s" % (i,ctrl.name))
					self.set_zcontroller(i,ctrl)
					i=i+1
				except Exception as e:
					if zynthian_gui_config.raise_exceptions:
						raise e
					else:
						logging.error("Controller %s (%d) => %s" % (ctrl.short_name,i,e))
						self.zgui_controllers[i].hide()
			#Hide rest of GUI controllers
			for i in range(i,len(self.zgui_controllers)):
				self.zgui_controllers[i].hide()
		#Hide All GUI controllers
		else:
			for zgui_controller in self.zgui_controllers:
				zgui_controller.hide()
		#Release Mutex Lock
		self.lock.release()

	def set_zcontroller(self, i, ctrl):
		if i < len(self.zgui_controllers):
			self.zgui_controllers[i].config(ctrl)
			self.zgui_controllers[i].show()
		else:
			self.zgui_controllers.append(zynthian_gui_controller(i,self.main_frame,ctrl))
		self.zgui_controllers_map[ctrl]=self.zgui_controllers[i]

	def set_mode_select(self):
		self.mode='select'
		for i in range(0,4):
			self.zgui_controllers[i].hide()
		if select_ctrl>1:
			self.pusher.grid(row=2,column=0)
		else:
			self.pusher.grid(row=2,column=2)
		self.set_selector()
		self.listbox.config(selectbackground=zynthian_gui_config.color_ctrl_bg_on,
			selectforeground=zynthian_gui_config.color_ctrl_tx,
			fg=zynthian_gui_config.color_ctrl_tx)
		#self.listbox.config(selectbackground=zynthian_gui_config.color_ctrl_bg_off,
		#	selectforeground=zynthian_gui_config.color_ctrl_tx,
		#	fg=zynthian_gui_config.color_ctrl_tx_off)
		self.select(self.index)
		self.set_select_path()

	def set_mode_control(self):
		self.mode='control'
		if self.zselector: self.zselector.hide()
		self.pusher.grid_forget();
		self.set_controller_screen()
		self.listbox.config(selectbackground=zynthian_gui_config.color_ctrl_bg_on,
			selectforeground=zynthian_gui_config.color_ctrl_tx,
			fg=zynthian_gui_config.color_ctrl_tx)
		self.set_select_path()

	def select_action(self, i):
		self.set_mode_control()

	def next(self):
		self.index+=1
		if self.index>=len(self.list_data):
			self.index=0
		self.select(self.index)
		self.click_listbox()
		return True

	def switch_select(self):
		if self.mode=='control':
			self.set_mode_select()
		elif self.mode=='select':
			self.click_listbox()

	def zyncoder_read(self):
		#Get Mutex Lock
		self.lock.acquire()
		#Read Controller
		if self.mode=='control' and self.zcontrollers:
			for i, ctrl in enumerate(self.zcontrollers):
				#print('Read Control ' + str(self.zgui_controllers[i].title))
				self.zgui_controllers[i].read_zyncoder()
		elif self.mode=='select':
			super().zyncoder_read()
		#Release Mutex Lock
		self.lock.release()

	def get_zgui_controller(self, zctrl):
		for zgui_controller in self.zgui_controllers:
			if zgui_controller.zctrl==zctrl:
				return zgui_controller

	def get_zgui_controller_by_index(self, i):
		return self.zgui_controllers[i]

	def set_controller_value(self, zctrl, val=None):
		if val is not None:
			zctrl.set_value(val)
		for zgui_controller in self.zgui_controllers:
			if zgui_controller.zctrl==zctrl:
				zgui_controller.zctrl_sync()

	def set_controller_value_by_index(self, i, val=None):
		zgui_controller=self.zgui_controllers[i]
		if val is not None:
			zgui_controller.zctrl.set_value(val)
		zgui_controller.zctrl_sync()

	def get_controller_value(self, zctrl):
		for i in self.zgui_controllers:
			if self.zgui_controllers[i].zctrl==zctrl:
				return zctrl.get_value()

	def get_controller_value_by_index(self, i):
		return self.zgui_controllers[i].zctrl.get_value()

	def midi_learn(self, i):
		if self.mode=='control':
			zynthian_gui_config.zyngui.curlayer.midi_learn(self.zgui_controllers[i].zctrl)

	def midi_unlearn(self, i):
		if self.mode=='control':
			zynthian_gui_config.zyngui.curlayer.midi_unlearn(self.zgui_controllers[i].zctrl)

	def cb_listbox_release(self,event):
		if self.mode=='select':
			super().cb_listbox_release(event)
		else:
			dts=(datetime.now()-self.listbox_push_ts).total_seconds()
			#logging.debug("LISTBOX RELEASE => %s" % dts)
			if dts<0.3:
				zynthian_gui_config.zyngui.start_loading()
				self.click_listbox()
				zynthian_gui_config.zyngui.stop_loading()

	def cb_listbox_motion(self,event):
		if self.mode=='select':
			super().cb_listbox_motion(event)
		else:
			dts=(datetime.now()-self.listbox_push_ts).total_seconds()
			if dts>0.1:
				index=self.get_cursel()
				if index!=self.index:
					#logging.debug("LISTBOX MOTION => %d" % self.index)
					zynthian_gui_config.zyngui.start_loading()
					self.select_listbox(self.get_cursel())
					zynthian_gui_config.zyngui.stop_loading()
					sleep(0.04)

	def set_select_path(self):
		if zynthian_gui_config.zyngui.curlayer:
			self.select_path.set(zynthian_gui_config.zyngui.curlayer.get_fullpath())

#------------------------------------------------------------------------------
