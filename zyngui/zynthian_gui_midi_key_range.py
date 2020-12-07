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
from zyncoder import *
from zyngine import zynthian_controller
from . import zynthian_gui_config
from . import zynthian_gui_base
from . import zynthian_gui_config
from . import zynthian_gui_controller

#------------------------------------------------------------------------------
# Zynthian MIDI key-range GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_midi_key_range(zynthian_gui_base.zynthian_gui_base):

	black_keys_pattern = (1,0,1,1,0,1,1)


	def __init__(self):
		super().__init__()
		self.chan = None
		self.note_low = 0
		self.note_high = 127
		self.octave = 0

		self.learn_toggle = 0

		self.nlow_zctrl=None
		self.nhigh_zctrl=None
		self.octave_zctrl=None

		self.space_frame_width = zynthian_gui_config.display_width-zynthian_gui_config.ctrl_width
		self.space_frame_height = zynthian_gui_config.ctrl_height - 2

		self.piano_canvas_width = zynthian_gui_config.display_width
		self.piano_canvas_height = int(0.2*zynthian_gui_config.body_height)

		self.note_info_canvas_height = zynthian_gui_config.ctrl_height - self.piano_canvas_height

		self.replot = True

		self.space_frame = tkinter.Frame(self.main_frame,
			width=self.space_frame_width,
			height=self.space_frame_height,
			bg=zynthian_gui_config.color_panel_bg)
		self.space_frame.grid(row=1, column=0, rowspan=1, columnspan=2, padx=(0,2), pady=(0,2), sticky="wens")

		self.note_info_canvas = tkinter.Canvas(self.main_frame,
			width=self.piano_canvas_width,
			height=self.note_info_canvas_height,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg=zynthian_gui_config.color_panel_bg)
		self.note_info_canvas.grid(row=2, column=0, rowspan=1, columnspan=3, sticky="wens")

		# Piano canvas
		self.piano_canvas = tkinter.Canvas(self.main_frame,
			width=self.piano_canvas_width,
			height=self.piano_canvas_height,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg = "#000000")
		self.piano_canvas.grid(row=3, column=0, rowspan=1, columnspan=3, sticky="ws")
		# Setup Piano's Callback
		self.piano_canvas.bind("<Button-1>", self.cb_piano_canvas)

		self.plot_piano()
		self.plot_text()


	def config(self, chan):
		self.chan = chan
		self.note_low = zyncoder.lib_zyncoder.get_midi_filter_note_low(chan)
		self.note_high = zyncoder.lib_zyncoder.get_midi_filter_note_high(chan)
		self.octave = zyncoder.lib_zyncoder.get_midi_filter_octave_trans(chan)
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
			midi_note += 1 
			self.piano_keys.append(key)
			#logging.error("PLOTTING PIANO WHITE KEY {}: {}".format(midi_note,x1))

			x1 += key_width
			x2 += key_width

			# plot black key when needed ...
			if self.black_keys_pattern[i % 7]:
				x1b = x1-int(key_width/2)
				x2b = x2-int(key_width/2)
				if x1b<self.piano_canvas_width:
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


	def update_text(self):
		self.note_info_canvas.itemconfig(self.nlow_text, text=self.get_midi_note_name(self.note_low))
		self.note_info_canvas.itemconfig(self.nhigh_text, text=self.get_midi_note_name(self.note_high))


	def set_zctrls(self):
		if self.shown:
			if self.nlow_zctrl:
				self.nlow_zctrl.setup_zyncoder()
			else:
				self.nlow_ctrl=zynthian_controller(None, 'note_low', 'note_low', { 'midi_cc':0, 'value_max':127 })
				self.nlow_zctrl=zynthian_gui_controller(1, self.main_frame, self.nlow_ctrl, True)
			self.nlow_zctrl.val0=0
			self.nlow_zctrl.set_value(self.note_low, True)
			self.nlow_zctrl.show()

			if self.nhigh_zctrl:
				self.nhigh_zctrl.setup_zyncoder()
			else:
				self.nhigh_ctrl=zynthian_controller(None, 'note_high', 'note_high', { 'midi_cc':0, 'value_max':127 })
				self.nhigh_zctrl=zynthian_gui_controller(3, self.main_frame, self.nhigh_ctrl, True)
			self.nhigh_zctrl.val0=0
			self.nhigh_zctrl.set_value(self.note_high, True)
			self.nhigh_zctrl.show()

			if self.octave_zctrl:
				self.octave_zctrl.setup_zyncoder()
			else:
				self.octave_ctrl=zynthian_controller(None, 'octave transpose', 'octave transpose', { 'midi_cc':0, 'value_max':11 })
				self.octave_zctrl=zynthian_gui_controller(2, self.main_frame, self.octave_ctrl, False)
			self.octave_zctrl.val0=-5
			self.octave_zctrl.erase_midi_bind()
			self.octave_zctrl.set_value(self.octave+5, True)
			self.octave_zctrl.show()


	def plot_zctrls(self):
		if self.replot:
			self.octave_zctrl.plot_value()
			self.update_piano()
			self.update_text()


	def show(self):
		super().show()
		self.set_zctrls()
		zyncoder.lib_zyncoder.set_midi_learning_mode(1)


	def hide(self):
		super().hide()
		zyncoder.lib_zyncoder.set_midi_learning_mode(0)


	def zyncoder_read(self, zcnums=None):
		if self.shown:
			self.nlow_zctrl.read_zyncoder()
			if self.note_low!=self.nlow_zctrl.value:
				if self.nlow_zctrl.value>self.note_high:
					self.nlow_zctrl.set_value(self.note_high-1, True)
					self.note_low = self.note_high-1
				else:
					self.note_low = self.nlow_zctrl.value
					logging.debug("SETTING FILTER NOTE_LOW: {}".format(self.note_low))
					zyncoder.lib_zyncoder.set_midi_filter_note_low(self.chan, self.note_low)
					self.replot = True

			self.nhigh_zctrl.read_zyncoder()
			if self.note_high!=self.nhigh_zctrl.value:
				if self.nhigh_zctrl.value<self.note_low:
					self.nhigh_zctrl.set_value(self.note_low+1, True)
					self.note_high = self.note_low+1
				else:
					self.note_high = self.nhigh_zctrl.value
				logging.debug("SETTING FILTER NOTE_HIGH: {}".format(self.note_high))
				zyncoder.lib_zyncoder.set_midi_filter_note_high(self.chan, self.note_high)
				self.replot = True

			self.octave_zctrl.read_zyncoder()
			if (self.octave+5)!=self.octave_zctrl.value:
				self.octave = self.octave_zctrl.value-5
				logging.debug("SETTING FILTER OCTAVE TRANS.: {}".format(self.octave))
				zyncoder.lib_zyncoder.set_midi_filter_octave_trans(self.chan, self.octave)
				self.replot = True

		return [0]


	def learn_note_range(self, num):
		if self.learn_toggle==0 or num<=self.note_low:
			self.nlow_zctrl.set_value(num, True)
			if self.note_low>self.note_high:
				self.nhigh_zctrl.set_value(127, True)
			self.learn_toggle = 1
		else:
			self.nhigh_zctrl.set_value(num, True)
			self.learn_toggle = 0


	def switch_select(self, t='S'):
		self.zyngui.show_modal('layer_options')


	def back_action(self):
		self.zyngui.show_modal('layer_options')
		return ''


	def set_select_path(self):
		try:
			self.select_path.set("{} > Note Range...".format(self.zyngui.screens['layer_options'].layer.get_basepath()))
		except:
			self.select_path.set("Note Range...")


	def cb_piano_canvas(self,event):
		logging.debug("PIANO CANVAS")

#------------------------------------------------------------------------------
