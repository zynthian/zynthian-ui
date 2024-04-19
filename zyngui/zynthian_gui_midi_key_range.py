# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI MIDI key-range config class
# 
# Copyright (C) 2015-2024 Fernando Moyano <jofemodo@zynthian.org>
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
from zyncoder.zyncore import lib_zyncore
from zyngine import zynthian_controller
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_base import zynthian_gui_base
from zyngui.zynthian_gui_selector import zynthian_gui_controller

# ------------------------------------------------------------------------------
# Zynthian MIDI key-range GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_midi_key_range(zynthian_gui_base):

	black_keys_pattern = (1, 0, 1, 1, 0, 1, 1)

	def __init__(self):
		super().__init__()

		self.chain = None
		self.zmop_index = None

		self.note_low = 0
		self.note_high = 127
		self.octave_trans = 0
		self.halftone_trans = 0

		self.learn_mode = 0 # [0:Disabled, -1:Awaiting first key, 1-127:Awaiting second key]

		self.zgui_ctrls = [None, None, None, None]
		self.nlow_zgui_ctrl = None
		self.nhigh_zgui_ctrl = None
		self.octave_zgui_ctrl = None
		self.halftone_zgui_ctrl = None

		self.spacer = tkinter.Canvas(self.main_frame,
			height=1,
			width=1,
			bg=zynthian_gui_config.color_panel_bg,
			bd=0,
			highlightthickness=0)
		self.piano_canvas_width = zynthian_gui_config.display_width

		self.piano_canvas_height = self.height // 4
		self.main_frame.rowconfigure(2, weight=1)
		if zynthian_gui_config.layout['columns'] == 3:
			self.spacer.grid(row=0, column=1, padx=(2, 2), sticky='news')
			self.zctrl_pos = [0, 2, 1, 3]
			self.main_frame.columnconfigure(1, weight=1)
		else:
			self.spacer.grid(row=0, column=0, rowspan=2, padx=(0, 2), sticky='news')
			self.zctrl_pos = [0, 1, 3, 2]
			self.main_frame.columnconfigure(0, weight=1)

		self.note_info_frame = tkinter.Frame(self.main_frame,
			bg=zynthian_gui_config.color_panel_bg)
		self.note_info_frame.columnconfigure(1, weight=1)
		self.note_info_frame.grid(row=2, columnspan=3, sticky="nsew", pady=(2, 2))

		# Piano canvas
		self.piano_canvas = tkinter.Canvas(self.main_frame,
			width=self.piano_canvas_width,
			height=self.piano_canvas_height,
			bd=0,
			highlightthickness=0,
			bg="#000099")
		self.piano_canvas.grid(row=3, columnspan=3)

		# Setup Piano's Callback
		self.piano_canvas.bind("<Button-1>", self.cb_piano_press)
		self.piano_canvas.bind("<B1-Motion>", self.on_piano_motion)

		self.replot = True
		self.plot_piano()
		self.plot_text()

	def config(self, chain):
		self.chain = chain
		if self.chain.zmop_index is not None:
			self.zmop_index = self.chain.zmop_index
			self.note_low = lib_zyncore.zmop_get_note_low(self.zmop_index)
			self.note_high = lib_zyncore.zmop_get_note_high(self.zmop_index)
			self.octave_trans = lib_zyncore.zmop_get_transpose_octave(self.zmop_index)
			self.halftone_trans = lib_zyncore.zmop_get_transpose_semitone(self.zmop_index)
		else:
			self.zmop_index = None
		self.set_select_path()

	def plot_piano(self):
		n_wkeys = 52
		key_width = int(self.piano_canvas_width / n_wkeys)
		black_height = int(0.65 * self.piano_canvas_height)

		self.midi_key0 = 21 #A1
		self.piano_keys = []

		i = 0
		x1 = 0
		x2 = key_width - 1
		midi_note = self.midi_key0
		while x1 < self.piano_canvas_width:
			# plot white-key
			if self.note_low > midi_note or self.note_high < midi_note:
				bgcolor = "#D0D0D0"
			else:
				bgcolor = "#FFFFFF"
			key = self.piano_canvas.create_rectangle((x1, 0, x2, self.piano_canvas_height), fill=bgcolor, width=0)
			self.piano_canvas.tag_lower(key)
			midi_note += 1 
			self.piano_keys.append(key)
			#logging.error("PLOTTING PIANO WHITE KEY {}: {}".format(midi_note,x1))

			x1 += key_width
			x2 += key_width

			# plot black key when needed ...
			if self.black_keys_pattern[i % 7]:
				x1b = x1 - int(key_width / 3)
				x2b = x1b + int(2 * key_width / 3)
				if x2b < self.piano_canvas_width:
					if self.note_low > midi_note or self.note_high < midi_note:
						bgcolor = "#707070"
					else:
						bgcolor = "#000000"
					key = self.piano_canvas.create_rectangle((x1b, 0, x2b, black_height), fill=bgcolor, width=0)
					midi_note += 1 
					self.piano_keys.append(key)
					#logging.debug("PLOTTING PIANO BLACK KEY {}: {}".format(midi_note,x1))

			i += 1


	def update_piano(self):
		i = 0
		j = 0
		midi_note = self.midi_key0
		while j < len(self.piano_keys):
			if self.note_low > midi_note or self.note_high < midi_note:
				bgcolor = "#D0D0D0"
			else:
				bgcolor = "#FFFFFF"
			self.piano_canvas.itemconfig(self.piano_keys[j], fill=bgcolor)
			j += 1
			midi_note += 1

			if self.black_keys_pattern[i % 7]:
				if self.note_low > midi_note or self.note_high < midi_note:
					bgcolor = "#707070"
				else:
					bgcolor = "#000000"

				self.piano_canvas.itemconfig(self.piano_keys[j], fill=bgcolor)
				j += 1
				midi_note += 1

			i += 1

	@staticmethod
	def get_midi_note_name(num):
		note_names = ("C","C#","D","D#","E","F","F#","G","G#","A","A#","B")
		scale = int(num / 12) - 2
		num = int(num % 12)
		return "{}{}".format(note_names[num], scale)

	def plot_text(self):
		fs = int(1.7 * zynthian_gui_config.font_size)

		self.nlow_text = tkinter.Label(self.note_info_frame,
			fg=zynthian_gui_config.color_ctrl_tx,
			bg=zynthian_gui_config.color_panel_bg,
			font=(zynthian_gui_config.font_family, fs),
			width=5,
			text=self.get_midi_note_name(self.note_low))
		self.nlow_text.grid(row=0, column=0, sticky='nsw')
		self.nlow_text.bind("<Button-4>", self.cb_nlow_wheel_up)
		self.nlow_text.bind("<Button-5>", self.cb_nlow_wheel_down)

		self.nhigh_text = tkinter.Label(self.note_info_frame,
			fg=zynthian_gui_config.color_ctrl_tx,
			bg=zynthian_gui_config.color_panel_bg,
			font=(zynthian_gui_config.font_family, fs),
			width=5,
			text=self.get_midi_note_name(self.note_high))
		self.nhigh_text.grid(row=0, column=2, sticky='sne')
		self.nhigh_text.bind("<Button-4>", self.cb_nhigh_wheel_up)
		self.nhigh_text.bind("<Button-5>", self.cb_nhigh_wheel_down)

		self.learn_text = tkinter.Label(self.note_info_frame,
			fg='Dark Grey',
			bg=zynthian_gui_config.color_panel_bg,
			font=(zynthian_gui_config.font_family, int(fs*0.6)),
			text='not learning',
			width=1)
		self.learn_text.grid(row=0, column=1, sticky='nsew')
		self.learn_text.bind("<ButtonRelease-1>", lambda e: self.zyngui.cuia_toggle_midi_learn())


	def update_text(self):
		self.nlow_text['text'] = self.get_midi_note_name(self.note_low)
		self.nhigh_text['text'] = self.get_midi_note_name(self.note_high)


	def set_zctrls(self):
		if not self.octave_zgui_ctrl:
			i = zynthian_gui_config.layout['ctrl_order'][0]
			self.octave_zctrl = zynthian_controller(self, 'octave transpose', {'value_min': -5, 'value_max': 6})
			self.octave_zgui_ctrl = zynthian_gui_controller(i, self.main_frame, self.octave_zctrl)
			self.zgui_ctrls[i] = self.octave_zgui_ctrl
		self.octave_zgui_ctrl.setup_zynpot()
		self.octave_zgui_ctrl.erase_midi_bind()
		self.octave_zctrl.set_value(self.octave_trans)

		if not self.halftone_zgui_ctrl:
			i = zynthian_gui_config.layout['ctrl_order'][1]
			self.halftone_zctrl = zynthian_controller(self, 'semitone transpose', {'value_min': -12, 'value_max': 12})
			self.halftone_zgui_ctrl = zynthian_gui_controller(i, self.main_frame, self.halftone_zctrl)
			self.zgui_ctrls[i] = self.halftone_zgui_ctrl
		self.halftone_zgui_ctrl.setup_zynpot()
		self.halftone_zgui_ctrl.erase_midi_bind()
		self.halftone_zctrl.set_value(self.halftone_trans)

		if not self.nlow_zgui_ctrl:
			i = zynthian_gui_config.layout['ctrl_order'][2]
			self.nlow_zctrl = zynthian_controller(self, 'note low', {'nudge_factor': 1})
			self.nlow_zgui_ctrl = zynthian_gui_controller(i, self.main_frame, self.nlow_zctrl, hidden=True)
			self.zgui_ctrls[i] = self.nlow_zgui_ctrl
		self.nlow_zgui_ctrl.setup_zynpot()
		self.nlow_zctrl.set_value(self.note_low)

		if not self.nhigh_zgui_ctrl:
			i = zynthian_gui_config.layout['ctrl_order'][3]
			self.nhigh_zctrl = zynthian_controller(self, 'note high', {'nudge_factor': 1})
			self.nhigh_zgui_ctrl = zynthian_gui_controller(i, self.main_frame, self.nhigh_zctrl, hidden=True)
			self.zgui_ctrls[i] = self.nhigh_zgui_ctrl
		self.nhigh_zgui_ctrl.setup_zynpot()
		self.nhigh_zctrl.set_value(self.note_high)

		if zynthian_gui_config.layout['columns'] == 3:
			self.octave_zgui_ctrl.configure(height=self.height // 2, width=self.width // 4)
			self.halftone_zgui_ctrl.configure(height=self.height // 2, width=self.width // 4)
			self.octave_zgui_ctrl.grid(row=0, column=0)
			self.halftone_zgui_ctrl.grid(row=0, column=2)
		else:
			self.octave_zgui_ctrl.configure(height=self.height // 4, width=self.width // 4)
			self.halftone_zgui_ctrl.configure(height=self.height // 4, width=self.width // 4)
			self.octave_zgui_ctrl.grid(row=0, column=2, pady=(0, 1))
			self.halftone_zgui_ctrl.grid(row=1, column=2, pady=(1, 0))

	def plot_zctrls(self):
		if self.replot:
			for zgui_ctrl in self.zgui_ctrls:
				if zgui_ctrl.zctrl.is_dirty:
					zgui_ctrl.calculate_plot_values()
					zgui_ctrl.plot_value()
					zgui_ctrl.zctrl.is_dirty = False
			self.update_piano()
			self.update_text()
			self.replot = False

	def build_view(self):
		self.set_zctrls()
		self.update_piano()
		self.replot = True
		return True

	def hide(self):
		if self.shown:
			super().hide()
			self.zyngui.cuia_disable_midi_learn()

	def zynpot_cb(self, i, dval):
		if i < len(self.zgui_ctrls):
			self.zgui_ctrls[i].zynpot_cb(dval)
			return True
		else:
			return False

	# Function to back event
	def back_action(self):
		if self.learn_mode:
			self.zyngui.cuia_disable_midi_learn()
			return True

	def enter_midi_learn(self):
		self.learn_mode = -1
		self.learn_text['text'] = "learning..."
		self.learn_text['fg'] = zynthian_gui_config.color_ml

	def exit_midi_learn(self):
		self.learn_mode = 0
		self.learn_text['text'] = "not learning"
		self.learn_text['fg'] = 'Dark Grey'

	def send_controller_value(self, zctrl):
		if self.shown and self.zmop_index is not None:
			# Send ALL-OFF to avoid stuck notes
			lib_zyncore.ui_send_all_notes_off_chain(self.zmop_index)
			if zctrl == self.nlow_zctrl:
				self.note_low = zctrl.value
				if zctrl.value > self.nhigh_zctrl.value:
					self.nlow_zctrl.set_value(self.nhigh_zctrl.value - 1)
				lib_zyncore.zmop_set_note_low(self.zmop_index, zctrl.value)
				logging.debug("SETTING RANGE NOTE LOW: {}".format(zctrl.value))
				self.replot = True

			elif zctrl == self.nhigh_zctrl:
				self.note_high = zctrl.value
				if zctrl.value < self.nlow_zctrl.value:
					self.nhigh_zctrl.set_value(self.nlow_zctrl.value + 1)
				lib_zyncore.zmop_set_note_high(self.zmop_index, zctrl.value)
				logging.debug("SETTING RANGE NOTE HIGH: {}".format(zctrl.value))
				self.replot = True

			elif zctrl == self.octave_zctrl:
				self.octave_trans = zctrl.value
				lib_zyncore.zmop_set_transpose_octave(self.zmop_index, zctrl.value)
				logging.debug("SETTING OCTAVE TRANSPOSE: {}".format(zctrl.value))
				self.replot = True

			elif zctrl == self.halftone_zctrl:
				self.halftone_trans = zctrl.value
				lib_zyncore.zmop_set_transpose_semitone(self.zmop_index, zctrl.value)
				logging.debug("SETTING SEMITONE TRANSPOSE: {}".format(zctrl.value))
				self.replot = True


	def learn_note_range(self, num):
		if self.learn_mode == -1:
			if num < self.nhigh_zctrl.value:
				self.nlow_zctrl.set_value(num)
			else:
				self.nhigh_zctrl.set_value(num)
			self.learn_mode = num
		else:
			if num < self.learn_mode:
				self.nlow_zctrl.set_value(num)
				self.nhigh_zctrl.set_value(self.learn_mode)
			else:
				self.nlow_zctrl.set_value(self.learn_mode)
				self.nhigh_zctrl.set_value(num)
			self.zyngui.cuia_disable_midi_learn()
		self.update_piano()


	def switch_select(self, t='S'):
		self.zyngui.close_screen()


	def set_select_path(self):
		try:
			self.select_path.set("{} > Note Range & Transpose...".format(self.zyngui.screens['processor_options'].processor.get_basepath()))
		except:
			self.select_path.set("Note Range & Transpose...")


	def cb_piano_press(self, event):
		for key,rect in enumerate(self.piano_keys):
			if event.x < event.widget.coords(rect)[2]:
				self.clicked_key = self.midi_key0 + key
				self.nlow_zctrl.set_value(self.clicked_key)
				self.nhigh_zctrl.set_value(self.clicked_key)
				self.nlow_zctrl.set_value(self.clicked_key)
				self.update_piano()
				return


	def on_piano_motion(self, event):
		for key,rect in enumerate(self.piano_keys):
			if event.x < event.widget.coords(rect)[2]:
				vis_key = self.midi_key0 + key
				if vis_key >= self.clicked_key and vis_key != self.nhigh_zctrl.value:
					self.nhigh_zctrl.set_value(vis_key)
					self.update_piano()
				elif vis_key <= self.clicked_key and vis_key != self.nlow_zctrl.value:
					self.nlow_zctrl.set_value(vis_key)
					self.update_piano()
				return


	def cb_nlow_wheel_up(self, event):
		self.nlow_zgui_ctrl.zynpot_cb(1)


	def cb_nlow_wheel_down(self, event):
		self.nlow_zgui_ctrl.zynpot_cb(-1)


	def cb_nhigh_wheel_up(self, event):
		self.nhigh_zgui_ctrl.zynpot_cb(1)


	def cb_nhigh_wheel_down(self, event):
		self.nhigh_zgui_ctrl.zynpot_cb(-1)

#------------------------------------------------------------------------------
