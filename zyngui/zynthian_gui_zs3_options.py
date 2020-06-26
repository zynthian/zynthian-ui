#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI ZS3 options selector Class
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

import logging

# Zynthian specific modules
from . import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian App Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_zs3_options(zynthian_gui_selector):

	def __init__(self):
		self.midi_chan = None
		self.zs3_index = None
		super().__init__('Option', True)


	def config(self, midich, i):
		self.midi_chan = midich
		self.zs3_index = i


	def fill_list(self):
		self.list_data=[]

		self.list_data.append((self.zs3_update,0,"Update"))
		self.list_data.append((self.zs3_delete,0,"Delete"))

		super().fill_list()


	def select_action(self, i, t='S'):
		if self.list_data[i][0]:
			self.last_action=self.list_data[i][0]
			self.last_action()


	def zs3_update(self):
		logging.info("Updating ZS3 CH#{}".format(self.midi_chan, self.zs3_index))
		self.zyngui.screens['layer'].save_midi_chan_zs3(self.midi_chan, self.zs3_index)
		self.zyngui.show_screen("control")
		self.zyngui.exit_midi_learn_mode()


	def zs3_delete(self):
		logging.info("Deleting ZS3 CH#{} {}".format(self.midi_chan, self.zs3_index))
		self.zyngui.screens['layer'].delete_midi_chan_zs3(self.midi_chan, self.zs3_index)
		self.zyngui.show_modal("zs3_learn")


	def back_action(self):
		self.zyngui.show_modal("zs3_learn")
		return ''


	def set_select_path(self):
		self.select_path.set("PROG Options")


#------------------------------------------------------------------------------
