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
import logging
import tkinter
from time import sleep
from string import Template
from datetime import datetime

# Zynthian specific modules
from zyngine import zynthian_controller
from . import zynthian_gui_config
from . import zynthian_gui_controller
from . import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian Instrument Controller GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_control(zynthian_gui_selector):

	def __init__(self, selcap='Controllers'):
		super().__init__(selcap, False)

		self.mode=None

		self.ctrl_screens={}
		self.zcontrollers=[]
		self.screen_name=None

		self.zgui_controllers=[]
		self.zgui_controllers_map={}

		# xyselect mode vars
		self.xyselect_mode=False
		self.x_zctrl=None
		self.y_zctrl=None

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
		super().hide()
		#if self.shown:
		#	for zc in self.zgui_controllers: zc.hide()
		#	if self.zselector: self.zselector.hide()


	def fill_list(self):
		self.list_data = []

		self.layers = self.zyngui.screens['layer'].get_fxchain_layers()
		# If no FXChain layers, then use the curlayer itself (probably amixer_layer)
		if len(self.layers)==0:
			self.layers = [self.zyngui.curlayer]

		i = 0
		for layer in self.layers:
			j = 0
			for cscr in layer.get_ctrl_screens():
				self.list_data.append((cscr,i,cscr,layer,j))
				i += 1
				j += 1
		self.index = self.zyngui.curlayer.get_active_screen_index()
		super().fill_list()


	def set_selector(self):
		if self.mode=='select': super().set_selector()


	def set_controller_screen(self):
		#Get Mutex Lock 
		#self.zyngui.lock.acquire()

		#Get screen info
		if self.index < len(self.list_data):
			screen_info = self.list_data[self.index]
			screen_title = screen_info[2]
			screen_layer = screen_info[3]

			#Get controllers for the current screen
			self.zyngui.curlayer.set_active_screen_index(self.index)
			self.zcontrollers = screen_layer.get_ctrl_screen(screen_title)

		else:
			self.zcontrollers = None


		#Setup GUI Controllers
		if self.zcontrollers:
			logging.debug("SET CONTROLLER SCREEN {}".format(screen_title))
			#Configure zgui_controllers
			i=0
			for ctrl in self.zcontrollers:
				try:
					#logging.debug("CONTROLLER ARRAY {} => {} ({})".format(i, ctrl.symbol, ctrl.short_name))
					self.set_zcontroller(i,ctrl)
					i=i+1
				except Exception as e:
					logging.exception("Controller %s (%d) => %s" % (ctrl.short_name,i,e))
					self.zgui_controllers[i].hide()

			#Hide rest of GUI controllers
			for i in range(i,len(self.zgui_controllers)):
				self.zgui_controllers[i].hide()

			#Set/Restore XY controllers highlight
			self.set_xyselect_controllers()

		#Hide All GUI controllers
		else:
			for zgui_controller in self.zgui_controllers:
				zgui_controller.hide()

		#Release Mutex Lock
		#self.zyngui.lock.release()


	def set_zcontroller(self, i, ctrl):
		if i < len(self.zgui_controllers):
			self.zgui_controllers[i].config(ctrl)
			self.zgui_controllers[i].show()
		else:
			self.zgui_controllers.append(zynthian_gui_controller(i,self.main_frame,ctrl))
		self.zgui_controllers_map[ctrl]=self.zgui_controllers[i]


	def set_xyselect_controllers(self):
		for i in range(0,len(self.zgui_controllers)):
			try:
				if self.xyselect_mode:
					zctrl=self.zgui_controllers[i].zctrl
					if zctrl==self.x_zctrl or zctrl==self.y_zctrl:
						self.zgui_controllers[i].set_hl()
						continue
				self.zgui_controllers[i].unset_hl()
			except:
				pass


	def set_mode_select(self):
		self.mode='select'
		for i in range(0,len(self.zgui_controllers)):
			self.zgui_controllers[i].hide()
		if zynthian_gui_config.select_ctrl>1:
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


	def set_xyselect_mode(self, xctrl_i, yctrl_i):
		self.xyselect_mode=True
		self.xyselect_zread_axis='X'
		self.xyselect_zread_counter=0
		self.xyselect_zread_last_zctrl=None
		self.x_zctrl=self.zgui_controllers[xctrl_i].zctrl
		self.y_zctrl=self.zgui_controllers[yctrl_i].zctrl
		#Set XY controllers highlight
		self.set_xyselect_controllers()
		
		
	def unset_xyselect_mode(self):
		self.xyselect_mode=False
		#Set XY controllers highlight
		self.set_xyselect_controllers()


	def set_xyselect_x(self, xctrl_i):
		zctrl=self.zgui_controllers[xctrl_i].zctrl
		if self.x_zctrl!=zctrl and self.y_zctrl!=zctrl:
			self.x_zctrl=zctrl
			#Set XY controllers highlight
			self.set_xyselect_controllers()
			return True


	def set_xyselect_y(self, yctrl_i):
		zctrl=self.zgui_controllers[yctrl_i].zctrl
		if self.y_zctrl!=zctrl and self.x_zctrl!=zctrl:
			self.y_zctrl=zctrl
			#Set XY controllers highlight
			self.set_xyselect_controllers()
			return True


	def select_action(self, i, t='S'):
		self.set_mode_control()


	def back_action(self):
		# If in controller map selection, back to instrument control
		if self.mode=='select':
			self.set_mode_control()
			return ''

		# If control xyselect mode active, disable xyselect mode
		elif self.xyselect_mode:
			logging.debug("DISABLE XYSELECT MODE")
			self.unset_xyselect_mode()
			return 'control'

		# If in MIDI-learn mode, back to instrument control
		elif self.zyngui.midi_learn_mode or self.zyngui.midi_learn_zctrl:
			self.zyngui.exit_midi_learn_mode()
			return ''

		else:
			self.zyngui.screens['layer'].restore_curlayer()
			return None


	def next(self):
		self.index+=1
		if self.index>=len(self.list_data):
			self.index=0
		self.select(self.index)
		self.click_listbox()
		return True


	def switch_select(self, t='S'):
		if t=='S':
			if self.mode in ('control','xyselect'):
				self.next()
				logging.info("Next Control Screen")
			elif self.mode=='select':
				self.click_listbox()

		elif t=='B':
			#if self.mode=='control':
			if self.mode in ('control','xyselect'):
				self.set_mode_select()
			elif self.mode=='select':
				self.click_listbox()



	def zyncoder_read(self):
		#Read Controller
		if self.mode=='control' and self.zcontrollers:
			for i, zctrl in enumerate(self.zcontrollers):
				#print('Read Control ' + str(self.zgui_controllers[i].title))

				res=self.zgui_controllers[i].read_zyncoder()
				
				if res and self.zyngui.midi_learn_mode:
					logging.debug("MIDI-learn ZController {}".format(i))
					self.zyngui.midi_learn_mode = False
					self.midi_learn(i)

				if res and self.xyselect_mode:
					self.zyncoder_read_xyselect(zctrl, i)

		elif self.mode=='select':
			super().zyncoder_read()


	def zyncoder_read_xyselect(self, zctrl, i):
		#Detect a serie of changes in the same controller
		if zctrl==self.xyselect_zread_last_zctrl:
			self.xyselect_zread_counter+=1
		else:
			self.xyselect_zread_last_zctrl=zctrl
			self.xyselect_zread_counter=0

		#If the change counter is major of ...
		if self.xyselect_zread_counter>5:
			if self.xyselect_zread_axis=='X' and self.set_xyselect_x(i):
				self.xyselect_zread_axis='Y'
				self.xyselect_zread_counter=0
			elif self.xyselect_zread_axis=='Y' and self.set_xyselect_y(i):
				self.xyselect_zread_axis='X'
				self.xyselect_zread_counter=0


	def get_zgui_controller(self, zctrl):
		for zgui_controller in self.zgui_controllers:
			if zgui_controller.zctrl==zctrl:
				return zgui_controller


	def get_zgui_controller_by_index(self, i):
		return self.zgui_controllers[i]


	def refresh_midi_bind(self):
		for zgui_controller in self.zgui_controllers:
			zgui_controller.set_midi_bind()


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
			self.zgui_controllers[i].zctrl.init_midi_learn()


	def midi_unlearn(self, i):
		if self.mode=='control':
			self.zgui_controllers[i].zctrl.midi_unlearn()


	def cb_listbox_push(self,event):
		if self.xyselect_mode:
			logging.debug("XY-Controller Mode ...")
			self.zyngui.show_control_xy(self.x_zctrl, self.y_zctrl)
		else:
			super().cb_listbox_push(event)


	def cb_listbox_release(self, event):
		if self.xyselect_mode:
			return
		if self.mode=='select':
			super().cb_listbox_release(event)
		elif self.listbox_push_ts:
			dts=(datetime.now()-self.listbox_push_ts).total_seconds()
			#logging.debug("LISTBOX RELEASE => %s" % dts)
			if dts<0.3:
				self.zyngui.start_loading()
				self.click_listbox()
				self.zyngui.stop_loading()


	def cb_listbox_motion(self, event):
		if self.xyselect_mode:
			return
		if self.mode=='select':
			super().cb_listbox_motion(event)
		elif self.listbox_push_ts:
			dts=(datetime.now()-self.listbox_push_ts).total_seconds()
			if dts>0.1:
				index=self.get_cursel()
				if index!=self.index:
					#logging.debug("LISTBOX MOTION => %d" % self.index)
					self.zyngui.start_loading()
					self.select_listbox(self.get_cursel())
					self.zyngui.stop_loading()
					sleep(0.04)


	def cb_listbox_wheel(self, event):
		index = self.index
		if (event.num == 5 or event.delta == -120) and self.index>0:
			index -= 1
		if (event.num == 4 or event.delta == 120) and self.index < (len(self.list_data)-1):
			index += 1
		if index!=self.index:
			self.zyngui.start_loading()
			self.select_listbox(index)
			self.zyngui.stop_loading()


	def set_select_path(self):
		if self.zyngui.curlayer:
			if self.mode=='control' and self.zyngui.midi_learn_mode:
				self.select_path.set(self.zyngui.curlayer.get_basepath() + "/CTRL MIDI-Learn")
			else:
				self.select_path.set(self.zyngui.curlayer.get_presetpath())


#------------------------------------------------------------------------------
