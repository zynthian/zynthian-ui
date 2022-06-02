#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Instrument-Control Class
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
import importlib
from time import sleep
from pathlib import Path
from string import Template
from datetime import datetime

# Zynthian specific modules
from zyngine import zynthian_controller
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_controller import zynthian_gui_controller
from zyngui.zynthian_gui_selector import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian Instrument Controller GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_control(zynthian_gui_selector):

	def __init__(self, selcap='Controllers'):
		self.mode = None

		self.buttonbar_config = [
			(1, 'PRESETS\n[mixer]'),
			(0, 'NEXT CHAIN\n[menu]'),
			(2, 'LEARN\n[snapshot]'),
			(3, 'PAGE\n[options]')
		]

		if zynthian_gui_config.ctrl_both_sides:
			super().__init__(selcap, False, False)
		else:
			super().__init__(selcap, True, False)


		self.widgets = {}
		self.ctrl_screens = {}
		self.zcontrollers = []
		self.screen_name = None
		self.controllers_lock = False

		self.zgui_controllers = []

		# xyselect mode vars
		self.xyselect_mode = False
		self.x_zctrl = None
		self.y_zctrl = None

		self.topbar_bold_touch_action = lambda: self.zyngui.zynswitch_defered('B', 1)


	def show(self):
		if self.zyngui.curlayer:
			super().show()
			self.click_listbox()
		else:
			self.zyngui.close_screen()


	def hide(self):
		super().hide()
		#if self.shown:
		#	for zc in self.zgui_controllers: zc.hide()
		#	if self.zselector: self.zselector.hide()


	def fill_list(self):
		self.list_data = []

		if not self.zyngui.curlayer:
			logging.error("Can't fill control screen list for None layer!")
			return

		self.layers = self.zyngui.screens['layer'].get_fxchain_layers()
		# If no FXChain layers, then use the curlayer itself
		if self.layers is None or len(self.layers) == 0:
			self.layers = [self.zyngui.curlayer]

		midichain_layers = self.zyngui.screens['layer'].get_midichain_layers()
		if midichain_layers is not None and len(midichain_layers) > 1:
			try:
				midichain_layers.remove(self.zyngui.curlayer)
			except:
				pass
			self.layers += midichain_layers

		i = 0
		for layer in self.layers:
			j = 0
			if len(self.layers) > 1:
				self.list_data.append((None, None, "> {}".format(layer.engine.name.split("/")[-1])))
			for cscr in layer.get_ctrl_screens():
				self.list_data.append((cscr, i, cscr, layer, j))
				i += 1
				j += 1
		self.index = self.zyngui.curlayer.get_current_screen_index()
		super().fill_list()


	def fill_listbox(self):
		super().fill_listbox()
		for i, val in enumerate(self.list_data):
			if val[0] == None:
				#self.listbox.itemconfig(i, {'bg':zynthian_gui_config.color_off,'fg':zynthian_gui_config.color_tx_off})
				self.listbox.itemconfig(i, {'bg':zynthian_gui_config.color_panel_hl, 'fg':zynthian_gui_config.color_tx_off})


	def set_selector(self, zs_hiden=True):
		if self.mode=='select': super().set_selector(zs_hiden)


	def lock_controllers(self):
		self.controllers_lock = True


	def unlock_controllers(self):
		self.controllers_lock = False


	def show_widget(self, layer):
		module_path = layer.engine.custom_gui_fpath
		if module_path:
			module_name = Path(module_path).stem
			if module_name.startswith("zynthian_widget_"):
				widget_name = module_name[len("zynthian_widget_"):]
				if widget_name not in self.widgets:
					try:
						spec = importlib.util.spec_from_file_location(module_name, module_path)
						module = importlib.util.module_from_spec(spec)
						spec.loader.exec_module(module)
						class_ = getattr(module, module_name)
						self.widgets[widget_name] = class_()
					except Exception as e:
						logging.error("Can't load custom widget {} => {}".format(widget_name, e))

				if widget_name in self.widgets:
					self.widgets[widget_name].set_layer(layer)
				else:
					widget_name = None

				for k, widget in self.widgets.items():
					if k == widget_name:
						widget.show()
					else:
						widget.hide()
				return
		self.hide_widgets()


	def hide_widgets(self):
		for k, widget in self.widgets.items():
			widget.hide()


	def set_controller_screen(self):
		# Get Mutex Lock 
		#self.zyngui.lock.acquire()

		# Get screen info
		if 0 <= self.index < len(self.list_data):
			screen_info = self.list_data[self.index]
			screen_title = screen_info[2]
			screen_layer = screen_info[3]

			# Show the widget for the current sublayer
			if self.mode=='control':
				self.show_widget(screen_layer)

			# Get controllers for the current screen
			self.zyngui.curlayer.set_current_screen_index(self.index)
			self.zcontrollers = screen_layer.get_ctrl_screen(screen_title)

		else:
			self.zcontrollers = None

		# Setup GUI Controllers
		if self.zcontrollers:
			logging.debug("SET CONTROLLER SCREEN {}".format(screen_title))
			# Configure zgui_controllers
			i = 0
			for ctrl in self.zcontrollers:
				try:
					#logging.debug("CONTROLLER ARRAY {} => {} ({})".format(i, ctrl.symbol, ctrl.short_name))
					self.set_zcontroller(i, ctrl)
					i += 1
				except Exception as e:
					logging.exception("Controller %s (%d) => %s" % (ctrl.short_name, i, e))
					self.zgui_controllers[i].hide()

			# Empty rest of GUI controllers
			for i in range(i, 4):
				self.set_zcontroller(i, None)

			# Set/Restore XY controllers highlight
			if self.mode == 'control':
				self.set_xyselect_controllers()

		# Empty All GUI controllers
		else:
			for i in range(4):
				self.set_zcontroller(i, None)

		self.lock_controllers() #TODO: Is mutex (fully) implemented

		# Release Mutex Lock
		#self.zyngui.lock.release()


	def set_zcontroller(self, i, ctrl):
		if i < len(self.zgui_controllers):
			self.zgui_controllers[i].config(ctrl)
			self.zgui_controllers[i].show()
		else:
			self.zgui_controllers.append(zynthian_gui_controller(i, self.main_frame, ctrl))


	def set_xyselect_controllers(self):
		for i in range(0, len(self.zgui_controllers)):
			try:
				if self.xyselect_mode:
					zctrl = self.zgui_controllers[i].zctrl
					if zctrl == self.x_zctrl or zctrl == self.y_zctrl:
						self.zgui_controllers[i].set_hl()
						continue
				self.zgui_controllers[i].unset_hl()
			except:
				pass


	def set_selector_screen(self): 
		for i in range(0, len(self.zgui_controllers)):
			self.zgui_controllers[i].set_hl(zynthian_gui_config.color_ctrl_bg_off)
		self.set_selector()


	def set_mode_select(self):
		self.mode = 'select'
		self.hide_widgets()
		self.set_selector_screen()
		self.listbox.config(selectbackground=zynthian_gui_config.color_ctrl_bg_off,
			selectforeground=zynthian_gui_config.color_ctrl_tx,
			fg=zynthian_gui_config.color_ctrl_tx_off)
		self.select(self.index)
		self.set_select_path()


	def set_mode_control(self):
		self.mode = 'control'
		if self.zselector: self.zselector.hide()
		self.set_controller_screen()
		self.listbox.config(selectbackground=zynthian_gui_config.color_ctrl_bg_on,
			selectforeground=zynthian_gui_config.color_ctrl_tx,
			fg=zynthian_gui_config.color_ctrl_tx)
		self.set_select_path()


	def set_xyselect_mode(self, xctrl_i, yctrl_i):
		self.xyselect_mode = True
		self.xyselect_zread_axis = 'X'
		self.xyselect_zread_counter = 0
		self.xyselect_zread_last_zctrl = None
		self.x_zctrl = self.zgui_controllers[xctrl_i].zctrl
		self.y_zctrl = self.zgui_controllers[yctrl_i].zctrl
		#Set XY controllers highlight
		self.set_xyselect_controllers()
		
		
	def unset_xyselect_mode(self):
		self.xyselect_mode = False
		#Set XY controllers highlight
		self.set_xyselect_controllers()


	def set_xyselect_x(self, xctrl_i):
		zctrl = self.zgui_controllers[xctrl_i].zctrl
		if self.x_zctrl != zctrl and self.y_zctrl != zctrl:
			self.x_zctrl = zctrl
			#Set XY controllers highlight
			self.set_xyselect_controllers()
			return True


	def set_xyselect_y(self, yctrl_i):
		zctrl = self.zgui_controllers[yctrl_i].zctrl
		if self.y_zctrl != zctrl and self.x_zctrl != zctrl:
			self.y_zctrl = zctrl
			#Set XY controllers highlight
			self.set_xyselect_controllers()
			return True


	def select_action(self, i, t='S'):
		self.set_mode_control()


	def back_action(self):
		if self.mode == 'select':
			self.set_mode_control()
			return True
		# If control xyselect mode active, disable xyselect mode
		elif self.xyselect_mode:
			logging.debug("DISABLE XYSELECT MODE")
			if self.zyngui.screens['control_xy'].shown:
				self.zyngui.screens['control_xy'].hide()
			else:
				self.unset_xyselect_mode()
			self.show()
			return True
		# If in MIDI-learn mode, back to instrument control
		elif self.zyngui.midi_learn_mode or self.zyngui.midi_learn_zctrl:
			self.zyngui.exit_midi_learn_mode()
			return True
		else:
			return False


	def arrow_up(self):
		i = self.index - 1
		if i < 0:
			i = 0
		self.select(i)
		self.click_listbox()
		return True


	def arrow_down(self):
		i = self.index + 1
		if i >= len(self.list_data):
			i = 0
		self.select(i)
		self.click_listbox()
		return True


	def arrow_right(self):
		if self.zyngui.screens['layer'].get_num_root_layers() > 1:
			self.zyngui.screens['layer'].next(True)


	def arrow_left(self):
		if self.zyngui.screens['layer'].get_num_root_layers() > 1:
			self.zyngui.screens['layer'].prev(True)


	# Function to handle *all* switch presses.
	#	swi: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	t: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def switch(self, swi, t='S'):
		if swi == 0:
			if t == 'S':
				self.arrow_right()
				return True

		elif swi == 1:
			if t == 'S':
				if self.back_action():
					return True
				elif not self.zyngui.is_shown_alsa_mixer():
					self.zyngui.cuia_bank_preset()
					return True
			else:
				self.back_action()
				return False

		elif swi == 2:
			if t == 'S':
				if self.mode == 'control':
					self.zyngui.cuia_learn()
				return True

		elif swi == 3:
			if t == 'S':
				if self.mode in ('control', 'xyselect'):
					if len(self.list_data) > 3:
						self.set_mode_select()
					else:
						self.arrow_down()
				elif self.mode == 'select':
					self.click_listbox()
			elif t == 'B':
				if not self.zyngui.is_shown_alsa_mixer():
					self.zyngui.screens['layer_options'].reset()
					self.zyngui.show_screen('layer_options')
			return True


	def select(self, index=None):
		super().select(index)
		if self.mode == 'select':
			self.set_controller_screen()
			self.set_selector_screen()
		

	def zynpot_cb(self, i, dval):
		if self.mode == 'control' and self.zcontrollers:
			if self.zgui_controllers[i].zynpot_cb(dval):
				self.midi_learn_zctrl(i)
				if self.xyselect_mode:
					self.zynpot_read_xyselect(i)
		elif self.mode == 'select':
			super().zynpot_cb(i, dval)


	def zynpot_read_xyselect(self, i):
		#Detect a serie of changes in the same controller
		if self.zgui_controllers[i].zctrl == self.xyselect_zread_last_zctrl:
			self.xyselect_zread_counter += 1
		else:
			self.xyselect_zread_last_zctrl = self.zgui_controllers[i].zctrl
			self.xyselect_zread_counter = 0

		#If the change counter is major of ...
		if self.xyselect_zread_counter > 5:
			if self.xyselect_zread_axis == 'X' and self.set_xyselect_x(i):
				self.xyselect_zread_axis = 'Y'
				self.xyselect_zread_counter = 0
			elif self.xyselect_zread_axis == 'Y' and self.set_xyselect_y(i):
				self.xyselect_zread_axis = 'X'
				self.xyselect_zread_counter = 0


	def get_zgui_controller(self, zctrl):
		for zgui_controller in self.zgui_controllers:
			if zgui_controller.zctrl == zctrl:
				return zgui_controller


	def get_zgui_controller_by_index(self, i):
		return self.zgui_controllers[i]


	def refresh_midi_bind(self):
		learning = False
		for zgui_controller in self.zgui_controllers:
			learning |= zgui_controller.set_midi_bind()
		if learning:
			self.set_buttonbar_label(0, "CANCEL")
		else:
			self.set_buttonbar_label(0, "PRESETS\n[mixer]")


	def plot_zctrls(self, force=False):
		if self.mode == 'select':
			super().plot_zctrls()
		elif self.zgui_controllers:
			for zgui_ctrl in self.zgui_controllers:
				if zgui_ctrl.zctrl and zgui_ctrl.zctrl.is_dirty or force:
					zgui_ctrl.calculate_plot_values()
				zgui_ctrl.plot_value()
		for k, widget in self.widgets.items():
			widget.update()


	def midi_learn_zctrl(self, i):
		if self.zyngui.midi_learn_mode:
			logging.debug("MIDI-learn ZController {}".format(i))
			self.zyngui.midi_learn_mode = False
			self.midi_learn(i)


	def midi_learn(self, i):
		if self.mode == 'control':
			self.zgui_controllers[i].zctrl.init_midi_learn()


	def midi_unlearn(self, i):
		if self.mode == 'control':
			self.zgui_controllers[i].zctrl.midi_unlearn()


	def cb_listbox_push(self, event):
		if self.xyselect_mode:
			logging.debug("XY-Controller Mode ...")
			self.zyngui.show_control_xy(self.x_zctrl, self.y_zctrl)
		else:
			super().cb_listbox_push(event)


	def cb_listbox_release(self, event):
		if self.xyselect_mode:
			return
		else:
			self.select(self.get_cursel())
			self.click_listbox()


	def cb_listbox_motion(self, event):
		if self.xyselect_mode:
			return
		if self.mode == 'select':
			super().cb_listbox_motion(event)
		elif self.listbox_push_ts:
			dts = (datetime.now()-self.listbox_push_ts).total_seconds()
			if dts > 0.1:
				index = self.get_cursel()
				if index != self.index:
					#logging.debug("LISTBOX MOTION => %d" % index)
					self.select_listbox(index)
					sleep(0.04)


	def cb_listbox_wheel(self, event):
		# Override with default listbox behaviour to allow scrolling of listbox without selection (expected UX)
		return


	def set_select_path(self):
		if self.zyngui.curlayer:
			if self.mode == 'control' and self.zyngui.midi_learn_mode:
				self.select_path.set(self.zyngui.curlayer.get_basepath() + "/CTRL MIDI-Learn")
			else:
				self.select_path.set(self.zyngui.curlayer.get_presetpath())


#------------------------------------------------------------------------------
