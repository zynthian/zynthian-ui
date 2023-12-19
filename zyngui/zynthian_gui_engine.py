#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Engine Selector Class
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

import os
import logging
from time import sleep
from collections import OrderedDict

# Zynthian specific modules
from zyngine import *
from zyngine.zynthian_engine_pianoteq import *
from zyngine.zynthian_engine_pianoteq6 import *
from zyngine.zynthian_engine_jalv import *
from zyngine.zynthian_engine_sooperlooper import zynthian_engine_sooperlooper
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian Engine Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_engine(zynthian_gui_selector):

	check_channels_engines = []#"AE"]

	def __init__(self):
		self.reset_index = True
		super().__init__('Engine', True)


	def fill_list(self):
		self.zyngui.chain_manager.get_engine_info() # Update the available engines
		self.list_data=[]

		if self.zyngui.modify_chain_status["type"] in ("MIDI Tool", "Audio Effect"):
			self.list_data.append(("None", 0, "None", "None"))
		# Sort category headings, but headings starting with "Zynthian" are shown first

		for cat, infos in sorted(self.zyngui.chain_manager.filtered_engines_by_cat(self.zyngui.modify_chain_status["type"]).items(), key = lambda kv:"!" if kv[0] is None else kv[0]):
			# Add category header...
			if cat:
				if self.zyngui.modify_chain_status["type"] == "MIDI Synth":
					self.list_data.append((None,len(self.list_data),"> LV2 {}".format(cat)))
				else:
					self.list_data.append((None,len(self.list_data),"> {}".format(cat)))

			# Add engines on this category...
			for eng, info in infos.items():
				i = len(self.list_data)
				self.list_data.append((eng, i, info[1], info[0]))
					
		# Display help if no engines are enabled ...
		if len(self.list_data) == 0:
			self.list_data.append((None,len(self.list_data),"Enable LV2-plugins on webconf".format(os.uname().nodename)))

		if self.reset_index:
			self.index = 0
			self.reset_index = False

		super().fill_list()


	def fill_listbox(self):
		super().fill_listbox()
		for i, val in enumerate(self.list_data):
			if val[0]==None:
				self.listbox.itemconfig(i, {'bg':zynthian_gui_config.color_panel_hl,'fg':zynthian_gui_config.color_tx_off})


	def select_action(self, i, t='S'):
		if i is not None and self.list_data[i][0]:
			self.zyngui.modify_chain_status["engine"] = self.list_data[i][0]
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
				if self.zyngui.modify_chain_status["engine"] == "AP":
					self.zyngui.modify_chain_status["audio_thru"] = False #TODO: Better done with engine flag
			if self.zyngui.modify_chain_status["type"] == "Audio Generator":
				self.zyngui.modify_chain_status["midi_chan"] = None
			self.zyngui.modify_chain()


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
			chain = self.zyngui.chain_manager.chains[self.zyngui.modify_chain_status["chain_id"]]
			path = f"{chain}#{path}"
		except:
			pass
		self.select_path.set(path)

#------------------------------------------------------------------------------
