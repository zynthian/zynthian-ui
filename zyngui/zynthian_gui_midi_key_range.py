#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI MIDI key-range config class
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
import tkinter
import logging
from ctypes import c_ubyte, c_byte

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore
from zyngine import zynthian_controller
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_base import zynthian_gui_base
from zyngui.zynthian_gui_selector import zynthian_gui_controller

#------------------------------------------------------------------------------
# Zynthian MIDI key-range GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_midi_key_range(zynthian_gui_base):

	black_keys_pattern = (1,0,1,1,0,1,1)


	def __init__(self):
		super().__init__()
		self.chan = None
		self.note_low = 0
		self.note_high = 127
		self.octave_trans = 0
		self.halftone_trans = 0

		self.learn_toggle = 0
		self.learn_mode = True

		self.nlow_zgui_ctrl=None
		self.nhigh_zgui_ctrl=None
		self.octave_zgui_ctrl=None
		self.halftone_zgui_ctrl=None

		if zynthian_gui_config.ctrl_both_sides:
			self.space_frame_width = zynthian_gui_config.display_width-2*zynthian_gui_config.ctrl_width
			self.space_frame_height = zynthian_gui_config.ctrl_height - 2
			self.piano_canvas_width = zynthian_gui_config.display_width
			self.piano_canvas_height = int(zynthian_gui_config.ctrl_height/2)
			self.note_info_canvas_height = zynthian_gui_config.ctrl_height - self.piano_canvas_height
			self.zctrl_pos = [0, 2, 1, 3]
		else:
			self.space_frame_width = zynthian_gui_config.display_width-zynthian_gui_config.ctrl_width
			self.space_frame_height = 2 * zynthian_gui_config.ctrl_height - 1
			self.piano_canvas_width = zynthian_gui_config.display_width
			self.piano_canvas_height = zynthian_gui_config.ctrl_height
			self.note_info_canvas_height = zynthian_gui_config.ctrl_height
			self.zctrl_pos = [0, 1, 3, 2]

		self.space_frame = tkinter.Frame(self.main_frame,
			width=self.space_frame_width,
			height=self.space_frame_height,
			bg=zynthian_gui_config.color_panel_bg)
		if zynthian_gui_config.ctrl_both_sides:
			self.space_frame.grid(row=1, column=1, rowspan=1, columnspan=1, padx=(2,2), pady=(0,2), sticky="wens")
		else:
			self.space_frame.grid(row=1, column=0, rowspan=2, columnspan=1, padx=(0,2), pady=(0,2), sticky="wens")

		self.note_info_canvas = tkinter.Canvas(self.main_frame,
			width=self.piano_canvas_width,
			height=self.note_info_canvas_height,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg=zynthian_gui_config.color_panel_bg)
		if zynthian_gui_config.ctrl_both_sides:
			self.note_info_canvas.grid(row=2, column=0, rowspan=1, columnspan=3, sticky="wens")
		else:
			self.note_info_canvas.grid(row=3, column=0, rowspan=1, columnspan=3, sticky="wens")

		# Piano canvas
		self.piano_canvas = tkinter.Canvas(self.main_frame,
			width=self.piano_canvas_width,
			height=self.piano_canvas_height,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg = "#000000")
		if zynthian_gui_config.ctrl_both_sides:
			self.piano_canvas.grid(row=2, column=0, rowspan=1, columnspan=3, sticky="ws")
		else:
			self.piano_canvas.grid(row=4, column=0, rowspan=1, columnspan=3, sticky="ws")

		# Setup Piano's Callback
		self.piano_canvas.bind("<Button-1>", self.cb_piano_canvas)

		self.replot = True
		self.plot_piano()
		self.plot_text()


	def config(self, chan):
		self.chan = chan
		self.note_low = lib_zyncore.get_midi_filter_note_low(chan)
		self.note_high = lib_zyncore.get_midi_filter_note_high(chan)
		self.octave_trans = lib_zyncore.get_midi_filter_octave_trans(chan)
		self.halftone_trans = lib_zyncore.get_midi_filter_halftone_trans(chan)
		self.set_select_path()


	def plot_piano(self):
		n_wkeys = 52
		key_width = int(self.piano_canvas_width/n_wkeys)
		black_height = int(0.65*self.piano_canvas_height)

		self.midi_key0 = 21 #A1
		self.piano_keys = []

		i = 0
		x1 = 0
		x2 = key_width-1
		midi_note = self.midi_key0
		while x1<self.piano_canvas_width:
			# plot white-key
			if self.note_low>midi_note or self.note_high<midi_note:
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
				x1b = x1-int(key_width/3)
				x2b = x1b+int(2*key_width/3)
				if x2b<self.piano_canvas_width:
					if self.note_low>midi_note or self.note_high<midi_note:
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
		while j<len(self.piano_keys):
			if self.note_low>midi_note or self.note_high<midi_note:
				bgcolor = "#D0D0D0"
			else:
				bgcolor = "#FFFFFF"
			self.piano_canvas.itemconfig(self.piano_keys[j], fill=bgcolor)
			j += 1
			midi_note += 1

			if self.black_keys_pattern[i % 7]:
				if self.note_low>midi_note or self.note_high<midi_note:
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
		scale = int(num/12)-2
		num = int(num%12)
		return "{}{}".format(note_names[num],scale)


	def plot_text(self):
		fs = int(1.7*zynthian_gui_config.font_size)

		self.nlow_text=self.note_info_canvas.create_text(
			int(zynthian_gui_config.ctrl_width/2),
			int((self.note_info_canvas_height-fs)/1.5),
			width=5*fs,
			justify=tkinter.CENTER,
			fill=zynthian_gui_config.color_ctrl_tx,
			font=(zynthian_gui_config.font_family,fs),
			text=self.get_midi_note_name(self.note_low))

		self.nhigh_text=self.note_info_canvas.create_text(
			self.piano_canvas_width-int(zynthian_gui_config.ctrl_width/2),
			int((self.note_info_canvas_height-fs)/1.5),
			width=5*fs,
			justify=tkinter.CENTER,
			fill=zynthian_gui_config.color_ctrl_tx,
			font=(zynthian_gui_config.font_family,fs),
			text=self.get_midi_note_name(self.note_high))


		self.learn_text=self.note_info_canvas.create_text(
			zynthian_gui_config.display_width  / 2,
			int((self.note_info_canvas_height-fs) / 1.5),
			width=5*fs,
			justify=tkinter.CENTER,
			fill=zynthian_gui_config.color_ml,
			font=(zynthian_gui_config.font_family, int(fs * 0.7)),
			text="learning...")


	def update_text(self):
		self.note_info_canvas.itemconfig(self.nlow_text, text=self.get_midi_note_name(self.note_low))
		self.note_info_canvas.itemconfig(self.nhigh_text, text=self.get_midi_note_name(self.note_high))


	def set_zctrls(self):
		if self.shown:
			if not self.halftone_zgui_ctrl:
				self.halftone_zctrl=zynthian_controller(self, 'semitone transpose', 'semitone transpose', { 'value_min':-12, 'value_max':12 })
				self.halftone_zgui_ctrl=zynthian_gui_controller(self.zctrl_pos[0], self.main_frame, self.halftone_zctrl, False)
			self.halftone_zgui_ctrl.setup_zynpot()
			self.halftone_zgui_ctrl.erase_midi_bind()
			self.halftone_zctrl.set_value(self.halftone_trans)
			self.halftone_zgui_ctrl.show()

			if not self.octave_zgui_ctrl:
				self.octave_zctrl = zynthian_controller(self, 'octave transpose', 'octave transpose', { 'value_min':-5, 'value_max':6 })
				self.octave_zgui_ctrl = zynthian_gui_controller(self.zctrl_pos[1], self.main_frame, self.octave_zctrl, False)
			self.octave_zgui_ctrl.setup_zynpot()
			self.octave_zgui_ctrl.erase_midi_bind()
			self.octave_zctrl.set_value(self.octave_trans)
			self.octave_zgui_ctrl.show()

			if not self.nlow_zgui_ctrl:
				self.nlow_zctrl = zynthian_controller(self, 'note low', 'note low', {'nudge_factor':1})
				self.nlow_zgui_ctrl = zynthian_gui_controller(self.zctrl_pos[2], self.main_frame, self.nlow_zctrl, True)
			self.nlow_zgui_ctrl.setup_zynpot()
			self.nlow_zctrl.set_value(self.note_low)
			self.nlow_zgui_ctrl.show()

			if not self.nhigh_zgui_ctrl:
				self.nhigh_zctrl = zynthian_controller(self, 'note high', 'note high', {'nudge_factor':1})
				self.nhigh_zgui_ctrl = zynthian_gui_controller(self.zctrl_pos[3], self.main_frame, self.nhigh_zctrl, True)
			self.nhigh_zgui_ctrl.setup_zynpot()
			self.nhigh_zctrl.set_value(self.note_high)
			self.nhigh_zgui_ctrl.show()


	def plot_zctrls(self):
		if self.replot:
			for zgui_ctrl in [self.halftone_zgui_ctrl, self.octave_zgui_ctrl, self.nlow_zgui_ctrl, self.nhigh_zgui_ctrl]:
				if zgui_ctrl.zctrl.is_dirty:
					zgui_ctrl.calculate_plot_values()
					zgui_ctrl.plot_value()
					zgui_ctrl.zctrl.is_dirty = False
			self.update_piano()
			self.update_text()
			self.replot = False


	def show(self):
		super().show()
		self.zyngui.screens["control"].unlock_controllers()
		self.set_zctrls()
		lib_zyncore.set_midi_learning_mode(self.learn_mode)


	def hide(self):
		super().hide()
		lib_zyncore.set_midi_learning_mode(0)


	def zynpot_cb(self, i, dval):
		if i == 0:
			self.halftone_zgui_ctrl.zynpot_cb(dval)
		elif i ==1:
			self.octave_zgui_ctrl.zynpot_cb(dval)
		elif i ==2:
			self.nlow_zgui_ctrl.zynpot_cb(dval)
		elif i ==3:
			self.nhigh_zgui_ctrl.zynpot_cb(dval)
		else:
			return False
		return True


	def toggle_midi_learn(self):
		if self.learn_mode:
			self.learn_mode = False
			#lib_zyncore.set_midi_learning_mode(0)
			self.note_info_canvas.itemconfig(self.learn_text, state=tkinter.HIDDEN)
		else:
			self.learn_mode = True
			#lib_zyncore.set_midi_learning_mode(1)
			self.note_info_canvas.itemconfig(self.learn_text, state=tkinter.NORMAL)


	def send_controller_value(self, zctrl):
		if self.shown:
			if zctrl == self.nlow_zctrl:
				self.note_low = zctrl.value #TODO: Try to loose these variables
				if zctrl.value > self.nhigh_zctrl.value:
					self.nlow_zctrl.set_value(self.nhigh_zctrl.value - 1)
				else:
					logging.debug("SETTING FILTER NOTE_LOW: {}".format(zctrl.value))
				lib_zyncore.set_midi_filter_note_low(self.chan, zctrl.value)
				self.replot = True

			if zctrl == self.nhigh_zctrl:
				self.note_high = zctrl.value #TODO: Try to loose these variables
				if zctrl.value < self.nlow_zctrl.value:
					self.nhigh_zctrl.set_value(self.nlow_zctrl.value + 1)
				else:
					logging.debug("SETTING FILTER NOTE_HIGH: {}".format(zctrl.value))
				lib_zyncore.set_midi_filter_note_high(self.chan, zctrl.value)
				self.replot = True

			if zctrl == self.octave_zctrl:
				self.octave_trans = zctrl.value #TODO: Try to loose these variables
				logging.debug("SETTING FILTER OCTAVE TRANS.: {}".format(zctrl.value))
				lib_zyncore.ui_send_ccontrol_change(self.chan, 120, 0)
				lib_zyncore.set_midi_filter_octave_trans(self.chan, zctrl.value)
				self.replot = True

			if zctrl == self.halftone_zctrl:
				self.halftone_trans = zctrl.value #TODO: Try to loose these variables
				logging.debug("SETTING FILTER HALFTONE TRANS.: {}".format(zctrl.value))
				lib_zyncore.ui_send_ccontrol_change(self.chan, 120, 0)
				lib_zyncore.set_midi_filter_halftone_trans(self.chan, zctrl.value)
				self.replot = True


	def learn_note_range(self, num):
		if not self.learn_mode:
			return
		if self.learn_toggle == 0 or num <= self.note_low:
			self.nlow_zctrl.set_value(num)
			if self.note_low > self.note_high:
				self.nhigh_zctrl.set_value(127)
			self.learn_toggle = 1
		else:
			self.nhigh_zctrl.set_value(num)
			self.learn_toggle = 0


	def switch_select(self, t='S'):
		self.zyngui.close_screen()


	def set_select_path(self):
		try:
			self.select_path.set("{} > Note Range & Transpose...".format(self.zyngui.screens['layer_options'].layer.get_basepath()))
		except:
			self.select_path.set("Note Range & Transpose...")


	def cb_piano_canvas(self,event):
		logging.debug("PIANO CANVAS")

#------------------------------------------------------------------------------
