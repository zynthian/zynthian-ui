#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Engine Selector Class
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

import os
import tkinter
import logging
from random import randrange

# Zynthian specific modules
from zyngine import *
from zyngine import zynthian_lv2
from zyngine.zynthian_engine_jalv import *
from zyngine.zynthian_engine_pianoteq import *
from zyngine.zynthian_engine_pianoteq6 import *
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

# ------------------------------------------------------------------------------
# Zynthian Engine Selection GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_engine(zynthian_gui_selector):

	check_channels_engines = []#"AE"]

	def __init__(self):
		self.reset_index = True
		super().__init__('Engine', True)
		self.context_index = {}
		self.engine_info = self.zyngui.chain_manager.engine_info
		self.engine_info_dirty = False
		self.show_all = False

		# Canvas for engine info
		self.info_canvas = tkinter.Canvas(
			self.main_frame,
			width=1,  # zynthian_gui_config.fw2, #self.width // 4 - 2,
			height=1,  # zynthian_gui_config.fh2, #self.height // 2 - 1,
			bd=0,
			highlightthickness=0,
			bg=zynthian_gui_config.color_bg)
		# Position at top of column containing selector
		self.info_canvas.grid(row=2, column=zynthian_gui_config.layout['list_pos'][1] + 1, rowspan=2, sticky="news")

		# Info layout
		star_fs = int(1.4 * zynthian_gui_config.font_size)
		#color_star = zynthian_gui_config.color_ml
		color_star = zynthian_gui_config.color_on
		color_star_off = zynthian_gui_config.color_off
		xpos = int(0.5 * zynthian_gui_config.font_size)
		ypos = 0
		info_width = 0.25 * self.width - xpos
		"""
		self.quality_label = self.info_canvas.create_text(
			xpos,
			ypos,
			anchor=tkinter.NW,
			justify=tkinter.LEFT,
			width=info_width,
			text="Quality:",
			font=(zynthian_gui_config.font_family, zynthian_gui_config.font_size),
			fill=zynthian_gui_config.color_panel_tx)
		ypos += int(1.2 * zynthian_gui_config.font_size)
		"""
		self.quality_stars_bg_label = self.info_canvas.create_text(
			xpos,
			ypos,
			anchor=tkinter.NW,
			justify=tkinter.CENTER,
			width=info_width,
			text="★★★★★",
			#text="✱✱✱✱✱",
			font=(zynthian_gui_config.font_family, star_fs),
			fill=color_star_off)
		self.quality_stars_label = self.info_canvas.create_text(
			xpos,
			ypos,
			anchor=tkinter.NW,
			justify=tkinter.CENTER,
			width=info_width,
			text="",
			font=(zynthian_gui_config.font_family, star_fs),
			fill=color_star)
		ypos += int(1.4 * star_fs)
		"""
		self.complexity_label = self.info_canvas.create_text(
			xpos,
			ypos,
			anchor=tkinter.NW,
			justify=tkinter.LEFT,
			width=info_width,
			text="Complex:",
			font=(zynthian_gui_config.font_family, zynthian_gui_config.font_size),
			fill=zynthian_gui_config.color_panel_tx)
		ypos += int(1.2 * zynthian_gui_config.font_size)
		"""
		self.complexity_stars_bg_label = self.info_canvas.create_text(
			xpos,
			ypos,
			anchor=tkinter.NW,
			justify=tkinter.CENTER,
			width=info_width,
			text="⚈⚈⚈⚈⚈",
			font=(zynthian_gui_config.font_family, star_fs),
			fill=color_star_off)
		self.complexity_stars_label = self.info_canvas.create_text(
			xpos,
			ypos,
			anchor=tkinter.NW,
			justify=tkinter.CENTER,
			width=info_width,
			text="",
			font=(zynthian_gui_config.font_family, star_fs),
			fill=color_star)
		ypos += int(2 * star_fs)
		self.description_label = self.info_canvas.create_text(
			xpos,
			ypos,
			anchor=tkinter.NW,
			justify=tkinter.LEFT,
			width=info_width,
			text="",
			font=(zynthian_gui_config.font_family, int(0.8 * zynthian_gui_config.font_size)),
			fill=zynthian_gui_config.color_panel_tx)

	def update_layout(self):
		super().update_layout()

	def update_info(self):
		eng_code = self.list_data[self.index][0]
		try:
			eng_info = self.engine_info[eng_code]
		except:
			logging.info(f"Can't get info for engine '{eng_code}'")
			eng_info = {"QUALITY": 0, "COMPLEX": 0, "DESCR": ""}

		quality_stars = "★" * eng_info["QUALITY"]
		self.info_canvas.itemconfigure(self.quality_stars_label, text=quality_stars)
		complexity_stars = "⚈" * eng_info["COMPLEX"]
		self.info_canvas.itemconfigure(self.complexity_stars_label, text=complexity_stars)
		self.info_canvas.itemconfigure(self.description_label, text=eng_info["DESCR"])

	def build_view(self):
		self.show_all = False
		try:
			self.index = self.context_index[self.zyngui.modify_chain_status["type"]]
		except:
			self.index = 0
			self.context_index[self.zyngui.modify_chain_status["type"]] = self.index
		return super().build_view()

	def hide(self):
		try:
			self.context_index[self.zyngui.modify_chain_status["type"]] = self.index
		except:
			pass
		super().hide()

	def fill_list(self):
		self.list_data = []

		proc_type = self.zyngui.modify_chain_status["type"]
		if proc_type in ("MIDI Tool", "Audio Effect"):
			self.list_data.append(("None", 0, "None", "None"))

		# Sort category headings, but headings starting with "Zynthian" are shown first
		self.zyngui.chain_manager.get_engine_info()
		for cat, infos in sorted(self.zyngui.chain_manager.filtered_engines_by_cat(proc_type, all=self.show_all).items(), key=lambda kv:"!" if kv[0] is None else kv[0]):
			# Add category header...
			if cat:
				self.list_data.append((None, len(self.list_data), "> {}".format(cat)))

			# Add engines on this category...
			if self.show_all:
				for eng, info in infos.items():
					i = len(self.list_data)
					if info["ENABLED"]:
						self.list_data.append((eng, i, "\u2612 " + info["TITLE"], info["NAME"]))
					else:
						self.list_data.append((eng, i, "\u2610 " + info["TITLE"], info["NAME"]))
			else:
				for eng, info in infos.items():
					i = len(self.list_data)
					self.list_data.append((eng, i, info["TITLE"], info["NAME"]))

		# Display help if no engines are enabled ...
		if len(self.list_data) == 0:
			self.list_data.append((None, len(self.list_data), "Bold-push to enable some LV2-plugins".format(os.uname().nodename)))
			self.index = 0

		if self.reset_index:
			self.index = 0
			self.reset_index = False

		if not self.show_all:
			self.engine_info_dirty = False

		super().fill_list()

	def select(self, index=None):
		super().select(index)
		self.update_info()

	def select_action(self, i, t='S'):
		if t == 'S':
			if i is not None and self.list_data[i][0]:
				engine = self.list_data[i][0]
				if self.show_all:
					self.engine_info[engine]['ENABLED'] = not self.engine_info[engine]['ENABLED']
					self.engine_info_dirty = True
					self.update_list()
				else:
					self.zyngui.modify_chain_status["engine"] = engine
					if "chain_id" in self.zyngui.modify_chain_status:
						# Modifying existing chain
						if "processor" in self.zyngui.modify_chain_status:
							# Replacing processor
							pass
						elif self.zyngui.chain_manager.get_slot_count(self.zyngui.modify_chain_status["chain_id"], self.zyngui.modify_chain_status["type"]):
							# Adding to slot with existing processor - choose parallel/series
							self.zyngui.screens['option'].config("Chain Mode", {"Series": False, "Parallel": True}, self.cb_add_parallel)
							self.zyngui.show_screen('option')
							return
						else:
							self.zyngui.modify_chain_status["parallel"] = False
					else:
						# Adding engine to new chain
						self.zyngui.modify_chain_status["parallel"] = False
						if engine == "AP":
							self.zyngui.modify_chain_status["audio_thru"] = False #TODO: Better done with engine flag
						if self.zyngui.modify_chain_status["type"] in ("Audio Effect", "Audio Generator") and not self.zyngui.modify_chain_status["midi_thru"]:
							self.zyngui.modify_chain_status["midi_chan"] = None
					self.zyngui.modify_chain()
		elif t == 'B':
			if not self.back_action():
				self.show_all = True
				self.update_list()

	def back_action(self):
		if self.show_all:
			if self.engine_info_dirty:
				self.zyngui.chain_manager.save_engine_info()
				self.engine_info_dirty = False
			self.show_all = False
			self.update_list()
			return True
		else:
			return False

	def arrow_right(self):
		if "chain_id" in self.zyngui.modify_chain_status:
			self.zyngui.chain_manager.next_chain()
			self.zyngui.chain_control()

	def arrow_left(self):
		if "chain_id" in self.zyngui.modify_chain_status:
			self.zyngui.chain_manager.previous_chain()
			self.zyngui.chain_control()

	def cb_add_parallel(self, option, value):
		self.zyngui.modify_chain_status['parallel'] = value
		self.zyngui.modify_chain()

	def switch(self, swi, t='S'):
		if swi == 0:
			if t == 'S':
				self.arrow_right()
				return True

	def set_select_path(self):
		path = ""
		try:
			path = self.zyngui.modify_chain_status["type"]
			chain = self.zyngui.chain_manager.chains[self.zyngui.modify_chain_status["chain_id"]].get_name()
			path = f"{chain}#{path}"
		except:
			pass
		self.select_path.set(path)

# ------------------------------------------------------------------------------
