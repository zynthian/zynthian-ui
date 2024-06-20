#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Instrument-Control Class
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

import logging
import importlib
from pathlib import Path
from time import monotonic

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_controller import zynthian_gui_controller
from zyngui.zynthian_gui_selector import zynthian_gui_selector
import zynautoconnect

# ------------------------------------------------------------------------------
# Zynthian Instrument Controller GUI Class
# ------------------------------------------------------------------------------

MIDI_LEARNING_DISABLED = 0
MIDI_LEARNING_CHAIN = 1
MIDI_LEARNING_GLOBAL = 2


class zynthian_gui_control(zynthian_gui_selector):

	def __init__(self, selcap='Controllers'):
		self.mode = None

		self.screen_info = None
		self.screen_title = None
		self.screen_processor = None  # TODO: Refactor

		self.widgets = {}
		self.current_widget = None
		self.ctrl_screens = {}
		self.zcontrollers = []
		self.screen_name = None
		self.zgui_controllers = []
		self.midi_learning = MIDI_LEARNING_DISABLED

		self.buttonbar_config = [
			(0, 'NEXT CHAIN\n[menu]'),
			(1, 'PRESETS\n[mixer]'),
			(2, 'LEARN\n[zs3]'),
			(3, 'PAGE\n[options]')
		]

		if zynthian_gui_config.layout['columns'] == 3:
			super().__init__(selcap, False, False)
		else:
			super().__init__(selcap, True, False)

		# xyselect mode vars
		self.xyselect_mode = False
		self.x_zctrl = None
		self.y_zctrl = None

		# Configure layout
		for ctrl_pos in zynthian_gui_config.layout['ctrl_pos']:
			self.main_frame.columnconfigure(ctrl_pos[1], weight=1, uniform='ctrl_col')
			self.main_frame.rowconfigure(ctrl_pos[0], weight=1, uniform='ctrl_row')
		self.main_frame.columnconfigure(zynthian_gui_config.layout['list_pos'][1], weight=2)

	def update_layout(self):
		super().update_layout()
		for pos in zynthian_gui_config.layout['ctrl_pos']:
			self.main_frame.columnconfigure(pos[1], minsize=int((self.width * 0.25 - 1) * self.sidebar_shown), weight=self.sidebar_shown)
		
	def build_view(self):
		if self.zyngui.get_current_processor():
			super().build_view()
			self.click_listbox()
			return True
		else:
			return False

	def hide(self):
		self.exit_midi_learn()
		super().hide()

	def show_sidebar(self, show):
		self.sidebar_shown = show
		for zctrl in self.zgui_controllers:
			if self.sidebar_shown:
				zctrl.grid()
			else:
				zctrl.grid_remove()
		self.update_layout()

	def fill_list(self):
		self.list_data = []
		curproc = self.zyngui.get_current_processor()

		if not curproc:
			logging.error("Can't fill control screen list for None processor!")
			return

		if curproc in (self.zyngui.state_manager.alsa_mixer_processor, self.zyngui.state_manager.audio_player):
			self.processors = [curproc]
		else:
			self.processors = self.zyngui.chain_manager.get_processors(curproc.chain_id)

		i = 0
		for processor in self.processors:
			j = 0
			screen_list = processor.get_ctrl_screens()
			if len(screen_list) > 0:
				if len(self.processors) > 1:
					self.list_data.append((None, None, f"> {processor.engine.name.split('/')[-1]}"))
				for cscr in screen_list:
					self.list_data.append((cscr, i, cscr, processor, j))
					i += 1
					j += 1

		self.index = curproc.get_current_screen_index()
		self.get_screen_info()
		super().fill_list()

	def get_screen_info(self):
		if 0 <= self.index < len(self.list_data):
			self.screen_info = self.list_data[self.index]
			if len(self.screen_info) < 5:
				if self.index + 1 < len(self.list_data):
					self.index += 1
					self.screen_info = self.list_data[self.index]
				else:
					self.screen_info = None
			if self.screen_info and len(self.screen_info) == 5:
				self.screen_title = self.screen_info[2]
				self.screen_processor = self.screen_info[3]
				return True
			else:
				logging.error("Can't get screen info!!")
		self.screen_title = ""
		self.screen_processor = self.zyngui.get_current_processor()
		return False

	def fill_listbox(self):
		super().fill_listbox()
		for i, val in enumerate(self.list_data):
			if val[0] is None:
				#self.listbox.itemconfig(i, {'bg': zynthian_gui_config.color_off,'fg': zynthian_gui_config.color_tx_off})
				self.listbox.itemconfig(i, {'bg': zynthian_gui_config.color_panel_hl, 'fg': zynthian_gui_config.color_tx_off})

	def set_selector(self, zs_hiden=True):
		if self.mode == 'select':
			super().set_selector(zs_hiden)

	def show_widget(self, processor):
		module_path = processor.engine.custom_gui_fpath
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
						self.widgets[widget_name] = class_(self.main_frame)
					except Exception as e:
						logging.error(f"Can't load custom widget {widget_name} => {e}")

				if widget_name in self.widgets:
					self.widgets[widget_name].set_processor(processor)
				else:
					widget_name = None

				if self.wide:
					padx = (0, 2)
				else:
					padx = (2, 2)
				for k, widget in self.widgets.items():
					if k == widget_name:
						self.listbox.grid_remove()
						widget.grid(row=zynthian_gui_config.layout['list_pos'][0], column=zynthian_gui_config.layout['list_pos'][1], rowspan=4, padx=padx, sticky="news")
						widget.show()
						self.set_current_widget(widget)
					else:
						widget.grid_remove()
						widget.hide()
				return
		self.hide_widgets()

	def hide_widgets(self):
		for k, widget in self.widgets.items():
			widget.grid_remove()
			widget.hide()
		self.set_current_widget(None)
		self.listbox.grid()

	def set_current_widget(self, widget):
		if widget == self.current_widget:
			return
		self.current_widget = widget
		# Clean dynamic CUIA methods from widgets
		for fn in dir(self):
			if fn.startswith('cuia_') or fn == 'update_wsleds':
				delattr(self, fn)
				#logging.debug(f"DELATTR {fn}")
		# Create new dynamix CUIA methods
		if self.current_widget:
			for fn in dir(self.current_widget):
				if fn.startswith('cuia_') or fn == 'update_wsleds':
					func = getattr(self.current_widget, fn)
					if callable(func):
						setattr(self, fn, func)
						#logging.debug(f"SETATTR {fn}")

	def set_controller_screen(self):
		# Get screen info
		if self.get_screen_info():
			try:
				self.zyngui.chain_manager.get_active_chain().set_current_processor(self.screen_processor)
				self.zyngui.current_processor = self.screen_processor
			except:
				pass

			# Show the widget for the current processor
			if self.mode == 'control':
				self.show_widget(self.screen_processor)

			# Get controllers for the current screen
			self.zyngui.get_current_processor().set_current_screen_index(self.index)
			self.zcontrollers = self.screen_processor.get_ctrl_screen(self.screen_title)

		else:
			self.zcontrollers = []
			self.screen_title = ""
			self.hide_widgets()

		# Setup GUI Controllers
		logging.debug(f"SET CONTROLLER SCREEN {self.screen_title}")
		# Configure zgui_controllers
		for i in range(4):
			if i < len(self.zcontrollers):
				ctrl = self.zcontrollers[i]
				try:
					#logging.debug(f"CONTROLLER ARRAY {i} => {ctrl.symbol} ({ctrl.short_name})")
					self.set_zcontroller(i, ctrl)
				except Exception as e:
					logging.exception("Controller %s (%d) => %s" % (ctrl.short_name, i, e))
					self.zgui_controllers[i].hide()
			else:
				self.set_zcontroller(i, None)
			pos = zynthian_gui_config.layout['ctrl_pos'][i]
			self.zgui_controllers[i].grid(row=pos[0], column=pos[1], pady=(0, 1), sticky='news')

		# Set/Restore XY controllers highlight
		if self.mode == 'control':
			self.set_xyselect_controllers()

		self.update_layout()

	def set_zcontroller(self, i, ctrl):
		if i < len(self.zgui_controllers):
			self.zgui_controllers[i].config(ctrl)
			self.zgui_controllers[i].show()
		else:
			self.zgui_controllers.append(zynthian_gui_controller(i, self.main_frame, ctrl))

	def get_zcontroller(self, i):
		if i < len(self.zgui_controllers):
			return self.zgui_controllers[i].zctrl
		else:
			return None

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
		self.exit_midi_learn()
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
		if self.zselector:
			self.zselector.hide()
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
		# Set XY controllers highlight
		self.set_xyselect_controllers()

	def unset_xyselect_mode(self):
		self.xyselect_mode = False
		# Set XY controllers highlight
		self.set_xyselect_controllers()

	def set_xyselect_x(self, xctrl_i):
		zctrl = self.zgui_controllers[xctrl_i].zctrl
		if self.x_zctrl != zctrl and self.y_zctrl != zctrl:
			self.x_zctrl = zctrl
			# Set XY controllers highlight
			self.set_xyselect_controllers()
			return True

	def set_xyselect_y(self, yctrl_i):
		zctrl = self.zgui_controllers[yctrl_i].zctrl
		if self.y_zctrl != zctrl and self.x_zctrl != zctrl:
			self.y_zctrl = zctrl
			# Set XY controllers highlight
			self.set_xyselect_controllers()
			return True

	def previous_page(self, wrap=False):
		i = self.index - 1
		if i < 0:
			i = 0
		self.select(i)
		self.click_listbox()

	def next_page(self, wrap=False):
		i = self.index + 1
		if i >= len(self.list_data):
			if wrap:
				i = 0
			else:
				i = len(self.list_data) - 1
		self.select(i)
		self.click_listbox()

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
			self.build_view()
			self.show()
			return True
		# If in MIDI-learn mode, back to instrument control
		elif self.midi_learning:
			self.exit_midi_learn()
			return True
		else:
			return False

	def arrow_up(self):
		self.previous_page()
		return True

	def arrow_down(self):
		self.next_page()
		return True

	def arrow_right(self):
		self.exit_midi_learn()
		self.zyngui.chain_manager.next_chain()
		self.zyngui.chain_control()

	def arrow_left(self):
		self.exit_midi_learn()
		self.zyngui.chain_manager.previous_chain()
		self.zyngui.chain_control()

	def rotate_chain(self):
		self.exit_midi_learn()
		self.zyngui.chain_manager.rotate_chain()
		self.zyngui.chain_control()

	# Function to handle *all* switch presses.
	#  swi: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#  t: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#  returns True if action fully handled or False if parent action should be triggered
	def switch(self, swi, t='S'):
		if swi == 0:
			if t == 'S':
				self.rotate_chain()
				return True

		elif swi == 1:
			if t == 'S':
				if self.back_action():
					return True
				elif not self.zyngui.is_shown_alsa_mixer():
					self.zyngui.cuia_bank_preset()
					return True
			elif t == 'B':
				self.back_action()
				return False

		elif swi == 2:
			if t == 'S':
				if self.mode == 'control':
					return False
			elif t == 'B':
				if self.midi_learning and self.zyngui.state_manager.midi_learn_cc:
					self.midi_unlearn_action()
					return True

	def switch_select(self, t):
		if t == 'S':
			if self.mode in ('control', 'xyselect'):
				if len(self.list_data) > 3:
					self.set_mode_select()
				else:
					self.next_page(True)
			elif self.mode == 'select':
				self.click_listbox()
		elif t == 'B':
			self.zyngui.cuia_chain_options()

		return True

	def select(self, index=None):
		super().select(index)
		if self.mode == 'select':
			self.set_controller_screen()
			self.set_selector_screen()

	def zynpot_cb(self, i, dval):
		if self.mode == 'control' and self.zcontrollers:
			if self.zgui_controllers[i].zynpot_cb(dval):
				if self.midi_learning:
					self.midi_learn(i, self.midi_learning)
				elif self.xyselect_mode:
					self.zynpot_read_xyselect(i)
		elif self.mode == 'select':
			super().zynpot_cb(i, dval)

	def zynpot_read_xyselect(self, i):
		# Detect a serie of changes in the same controller
		if self.zgui_controllers[i].zctrl == self.xyselect_zread_last_zctrl:
			self.xyselect_zread_counter += 1
		else:
			self.xyselect_zread_last_zctrl = self.zgui_controllers[i].zctrl
			self.xyselect_zread_counter = 0

		# If the change counter is major of ...
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

	def refresh_midi_bind(self, preselect=False):
		for i, zgui_controller in enumerate(self.zgui_controllers):
			if preselect:
				zgui_controller.set_midi_bind(i)
			else:
				zgui_controller.set_midi_bind()

	def plot_zctrls(self, force=False):
		if self.mode == 'select':
			super().plot_zctrls()
		elif self.zgui_controllers:
			self.swipe_update()
			for zgui_ctrl in self.zgui_controllers:
				if zgui_ctrl.zctrl and zgui_ctrl.zctrl.is_dirty or force:
					zgui_ctrl.calculate_plot_values()
				zgui_ctrl.plot_value()
		for k, widget in self.widgets.items():
			widget.update()

	# --------------------------------------------------------------------------
	# Options Menu
	# --------------------------------------------------------------------------

	def show_menu(self):
		self.zyngui.cuia_chain_options()


	def toggle_menu(self):
		if self.shown:
			self.show_menu()
		elif self.zyngui.current_screen.endswith("_options"):
			self.close_screen()

	# --------------------------------------------------------------------------
	# MIDI learn management
	# --------------------------------------------------------------------------

	def enter_midi_learn(self, mlmode=MIDI_LEARNING_CHAIN, preselect=True):
		if mlmode > MIDI_LEARNING_DISABLED:
			self.midi_learning = mlmode
			self.set_buttonbar_label(0, "CANCEL")
			self.refresh_midi_bind(preselect)
			self.set_select_path()

	def exit_midi_learn(self):
		if self.midi_learning != MIDI_LEARNING_DISABLED:
			self.midi_learning = MIDI_LEARNING_DISABLED
			self.zyngui.state_manager.disable_learn_cc()
			self.refresh_midi_bind()
			self.set_select_path()
			self.set_buttonbar_label(0, "PRESETS\n[mixer]")

	def toggle_midi_learn(self, i=None):
		if self.mode != 'control':
			return

		if i is not None:
			# Restart MIDI learn with a new controller
			if self.zgui_controllers[i].zctrl != self.zyngui.state_manager.get_midi_learn_zctrl():
				self.midi_learn(i, MIDI_LEARNING_CHAIN)
				return self.midi_learning

		# TODO: Handle alsa mixer
		#if zynthian_gui_config.midi_prog_change_zs3 and not self.zyngui.is_shown_alsa_mixer():

		if self.midi_learning == MIDI_LEARNING_CHAIN:
			self.midi_learning = MIDI_LEARNING_GLOBAL
			if i is not None:
				self.refresh_midi_bind(False)
			else:
				self.refresh_midi_bind(True)
			self.set_select_path()
		elif self.midi_learning == MIDI_LEARNING_GLOBAL:
			self.exit_midi_learn()
		else:
			if i is not None:
				self.enter_midi_learn(MIDI_LEARNING_CHAIN, False)
			else:
				self.enter_midi_learn(MIDI_LEARNING_CHAIN, True)

		return self.midi_learning

	def get_midi_learn(self):
		return self.midi_learning

	def zctrl_touch(self, i):
		if self.midi_learning:
			self.midi_learn(i, self.midi_learning)

	def midi_learn(self, i, mlmode=MIDI_LEARNING_CHAIN):
		if self.mode == 'control' and mlmode > MIDI_LEARNING_DISABLED:
			learn_zctrl = self.zgui_controllers[i].zctrl
			if learn_zctrl:
				self.zyngui.state_manager.enable_learn_cc(learn_zctrl)
				self.enter_midi_learn(mlmode, False)

	def midi_learn_bind(self, zmip, chan, midi_cc):
		if self.midi_learning:
			if self.midi_learning == MIDI_LEARNING_CHAIN:
				self.zyngui.chain_manager.add_midi_learn(chan, midi_cc, self.zyngui.state_manager.get_midi_learn_zctrl())
			else:
				self.zyngui.chain_manager.add_midi_learn(chan, midi_cc, self.zyngui.state_manager.get_midi_learn_zctrl(), zmip)
			self.exit_midi_learn()

	def midi_unlearn(self, param=None):
		if param:
			self.zyngui.chain_manager.clean_midi_learn(param)
		else:
			self.zyngui.chain_manager.clean_midi_learn(self.zyngui.get_current_processor())
		self.refresh_midi_bind()

	def midi_unlearn_action(self):
		curproc = self.zyngui.get_current_processor()
		if curproc:
			engine_name = curproc.get_name()
			if engine_name:
				question_str = f"Do you want to clean MIDI-learn for ALL controls in {engine_name}"
				if curproc.midi_chan is not None and 0 <= curproc.midi_chan < 16:
					question_str += f"on MIDI channel {curproc.midi_chan + 1}"
				self.zyngui.show_confirm(question_str + "?", self.midi_unlearn)
			else:
				logging.error("Can't get processor name.")

	def midi_learn_options(self, i, unlearn_only=False):
		self.exit_midi_learn()
		try:
			options = {}
			zctrl = self.zgui_controllers[i].zctrl
			if zctrl is None:
				return
			title = "Control options"
			if not unlearn_only:
				if zctrl.is_toggle:
					if zctrl.midi_cc_momentary_switch:
						options[f"\u2612 Momentary => Latch"] = i
					else:
						options[f"\u2610 Momentary => Latch"] = i
				options["X-Y touchpad"] = i
				options[f"Chain learn '{zctrl.name}'..."] = i
				options[f"Global learn '{zctrl.name}'..."] = i
			else:
				title = "Control unlearn"
			params = self.zyngui.chain_manager.get_midi_learn_from_zctrl(zctrl)
			if params:
				if params[1]:
					dev_name = zynautoconnect.get_midi_in_devid(params[0] >> 24)
					options[f"Unlearn '{zctrl.name}' from {dev_name}"] = zctrl
				else:
					options[f"Unlearn '{zctrl.name}'"] = zctrl
			options["Unlearn all controls"] = ""
			self.zyngui.screens['option'].config(title, options, self.midi_learn_options_cb)
			self.zyngui.show_screen('option')
		except Exception as e:
			logging.error(f"Can't show control options => {e}")

	def midi_learn_options_cb(self, option, param):
		parts = option.split(" ")
		if parts[0] == "Chain":
			self.midi_learn(param, MIDI_LEARNING_CHAIN)
		elif parts[0] == "Global":
			self.midi_learn(param, MIDI_LEARNING_GLOBAL)
		elif parts[0] == "Unlearn":
			if param:
				self.midi_unlearn(param)
			else:
				self.midi_unlearn_action()
		elif parts[0] == "X-Y":
			if param > 2:
				param = 2
			self.set_xyselect_mode(param, param + 1)
		elif parts[1] == "Momentary":
			if parts[0] == '\u2612':
				self.zgui_controllers[param].zctrl.midi_cc_momentary_switch = 0
			else:
				self.zgui_controllers[param].zctrl.midi_cc_momentary_switch = 1
			self.midi_learn_options(param)

	# -------------------------------------------------------------------------
	# GUI Callback function
	# --------------------------------------------------------------------------

	def cb_listbox_push(self, event):
		if self.xyselect_mode:
			logging.debug("XY-Controller Mode ...")
			self.zyngui.show_control_xy(self.x_zctrl, self.y_zctrl)
		else:
			return super().cb_listbox_push(event)

	def cb_listbox_release(self, event):
		if self.zyngui.cb_touch_release(event):
			return "break"

		if self.xyselect_mode:
			return
		else:
			now = monotonic()
			dts = now - self.listbox_push_ts
			rdts = now - self.last_release
			self.last_release = now
			if self.swiping:
				self.swipe_nudge(dts)
			else:
				if rdts < 0.03:
					return  # Debounce
				cursel = self.listbox.nearest(event.y)
				if self.index != cursel:
					self.select(cursel)
				self.select_listbox(self.get_cursel(), False)
				self.click_listbox()
				return "break"

	def cb_listbox_motion(self, event):
		if self.xyselect_mode:
			return
		return super().cb_listbox_motion(event)

	def cb_listbox_wheel(self, event):
		# Override with default listbox behaviour to allow scrolling of listbox without selection (expected UX)
		return

	def set_select_path(self):
		processor = self.zyngui.get_current_processor()
		if processor:
			if self.mode == 'control' and self.midi_learning:
				if self.midi_learning == MIDI_LEARNING_CHAIN:
					self.select_path.set(processor.get_basepath() + "/CHAIN Control MIDI-Learn")
				elif self.midi_learning == MIDI_LEARNING_GLOBAL:
					self.select_path.set(processor.get_basepath() + "/GLOBAL Control MIDI-Learn")
			else:
				self.select_path.set(processor.get_presetpath())

# ------------------------------------------------------------------------------
