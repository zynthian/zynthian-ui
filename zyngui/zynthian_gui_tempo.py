#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Tempo class
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
from time import monotonic
from collections import deque

# Zynthian specific modules
import zynconf
from zynlibs.zynaudioplayer import *
from zyncoder.zyncore import lib_zyncore
from zyngine import zynthian_controller
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_base import zynthian_gui_base
from zyngui.zynthian_gui_selector import zynthian_gui_controller


# ------------------------------------------------------------------------------
# Zynthian Tempo GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_tempo(zynthian_gui_base):

	NUM_TAPS = 4

	def __init__(self):
		super().__init__()

		self.state_manager = self.zyngui.state_manager
		self.libseq = self.state_manager.zynseq.libseq

		self.tap_buf = None
		self.last_tap_ts = 0

		self.zgui_ctrls = []
		self.bpm_zgui_ctrl = None
		self.clk_source_zgui_ctrl = None
		self.mtr_enable_zgui_ctrl = None
		self.mtr_volume_zgui_ctrl = None

		self.info_canvas = tkinter.Canvas(self.main_frame,
			height=1,
			width=1,
			bg=zynthian_gui_config.color_panel_bg,
			bd=0,
			highlightthickness=0)
		self.main_frame.rowconfigure(2, weight=1)
		if zynthian_gui_config.layout['columns'] == 3:
			self.info_canvas.grid(row=0, column=1, rowspan=2, padx=(2, 2), sticky='news')
			self.main_frame.columnconfigure(1, weight=1)
		else:
			self.info_canvas.grid(row=0, column=0, rowspan=4, padx=(0, 2), sticky='news')
			self.main_frame.columnconfigure(0, weight=1)

		self.bpm_text = self.info_canvas.create_text(
			0,
			0,
			anchor=tkinter.N,
			width=0,
			text="",
			font=(zynthian_gui_config.font_family, 10),
			fill=zynthian_gui_config.color_panel_tx)

		self.replot = True

	def set_zctrls(self):
		if not self.bpm_zgui_ctrl:
			self.bpm_zctrl = zynthian_controller(self, 'bpm', {'name': 'BPM', 'value_min': 10, 'value_max': 420, 'is_integer': False, 'nudge_factor': 0.1, 'value': self.libseq.getTempo()})
			self.bpm_zgui_ctrl = zynthian_gui_controller(0, self.main_frame, self.bpm_zctrl)
			self.zgui_ctrls.append(self.bpm_zgui_ctrl)

		if not self.clk_source_zgui_ctrl:
			self.clk_source_zctrl = zynthian_controller(self, 'clock_source', {'name': 'Clock Source', 'labels': ['Internal', 'Internal Send', 'MIDI', 'Analogue'], 'ticks': [0, 1, 2, 3], 'value': self.state_manager.get_transport_clock_source()})
			self.clk_source_zgui_ctrl = zynthian_gui_controller(1, self.main_frame, self.clk_source_zctrl)
			self.zgui_ctrls.append(self.clk_source_zgui_ctrl)

		if not self.mtr_enable_zgui_ctrl:
			self.mtr_enable_zctrl = zynthian_controller(self, 'metronome_enable', {'name': 'Metronome On/Off', 'labels': ['Off', 'On'], 'ticks': [0, 1], 'is_toggle': True, 'value': self.libseq.isMetronomeEnabled()})
			self.mtr_enable_zgui_ctrl = zynthian_gui_controller(2, self.main_frame, self.mtr_enable_zctrl)
			self.zgui_ctrls.append(self.mtr_enable_zgui_ctrl)

		if not self.mtr_volume_zgui_ctrl:
			self.mtr_volume_zctrl = zynthian_controller(self, 'metronome_volume', {'name': 'Metronome Volume', 'value_min': 0, 'value_max': 100, 'value': int(100 * self.libseq.getMetronomeVolume())})
			self.mtr_volume_zgui_ctrl = zynthian_gui_controller(3, self.main_frame, self.mtr_volume_zctrl)
			self.zgui_ctrls.append(self.mtr_volume_zgui_ctrl)

		layout = zynthian_gui_config.layout
		for zgui_ctrl in self.zgui_ctrls:
			i = zgui_ctrl.index
			zgui_ctrl.setup_zynpot()
			zgui_ctrl.erase_midi_bind()
			zgui_ctrl.configure(height=self.height // layout['rows'], width=self.width // 4)
			zgui_ctrl.grid(row=layout['ctrl_pos'][i][0], column=layout['ctrl_pos'][i][1])

	def update_text(self):
		self.info_canvas.itemconfigure(self.bpm_text, text="{:.1f} BPM".format(self.bpm_zctrl.get_value()))

	def update_layout(self):
		super().update_layout()
		fs = self.width // 20
		if zynthian_gui_config.layout['columns'] == 3:
			self.info_canvas.coords(self.bpm_text, int(0.25*self.width), int(0.375*self.height))
		else:
			self.info_canvas.coords(self.bpm_text, int(0.375*self.width), int(0.375*self.height))
		self.info_canvas.itemconfigure(self.bpm_text, width=9*fs, font=(zynthian_gui_config.font_family, fs))

	def plot_zctrls(self):
		self.refresh_bpm_value()
		if self.replot:
			for zgui_ctrl in self.zgui_ctrls:
				if zgui_ctrl.zctrl.is_dirty:
					zgui_ctrl.calculate_plot_values()
					zgui_ctrl.plot_value()
					zgui_ctrl.zctrl.is_dirty = False
			self.update_text()
			self.replot = False

	def build_view(self):
		self.set_zctrls()
		self.last_tap_ts = 0
		return True

	def zynpot_cb(self, i, dval):
		if i < 4:
			self.zgui_ctrls[i].zynpot_cb(dval)
			return True
		else:
			return False

	def send_controller_value(self, zctrl):
		if self.shown:
			if zctrl == self.bpm_zctrl:
				self.libseq.setTempo(zctrl.value)
				zynaudioplayer.set_tempo(zctrl.value)
				logging.debug("SETTING TEMPO BPM: {}".format(zctrl.value))
				self.replot = True

			elif zctrl == self.clk_source_zctrl:
				self.state_manager.set_transport_clock_source(zctrl.value, save_config=True)
				logging.debug("SETTING CLOCK SOURCE: {}".format(zctrl.value))
				self.replot = True

			elif zctrl == self.mtr_enable_zctrl:
				self.libseq.enableMetronome(zctrl.value)
				logging.debug("SETTING METRONOME ENABLE: {}".format(zctrl.value))
				self.replot = True

			elif zctrl == self.mtr_volume_zctrl:
				self.libseq.setMetronomeVolume(zctrl.value/100.0)
				logging.debug("SETTING METRONOME VOLUME: {}".format(zctrl.value))
				self.replot = True

	def tap(self):
		now = monotonic()
		tap_dur = now - self.last_tap_ts
		if self.last_tap_ts == 0 or tap_dur < 0.14285 or tap_dur > 2:
			self.last_tap_ts = now
			self.tap_buf = deque(maxlen=self.NUM_TAPS)
		else:
			self.last_tap_ts = now
			self.tap_buf.append(tap_dur)
			logging.debug("TAP TEMPO BUFFER: {}".format(self.tap_buf))
			bpm = 60 * len(self.tap_buf) / sum(self.tap_buf)
			self.libseq.setTempo(bpm)
			logging.debug("SETTING TAP TEMPO BPM: {}".format(bpm))

	def refresh_bpm_value(self):
		self.bpm_zctrl.set_value(self.libseq.getTempo(), send=False)
		if self.bpm_zctrl.is_dirty:
			self.replot = True

	def switch_select(self, t='S'):
		self.zyngui.close_screen()

	def set_select_path(self):
		self.select_path.set("Tempo Settings")


# ------------------------------------------------------------------------------
