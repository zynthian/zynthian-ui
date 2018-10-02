#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Bank Selector Class
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

# Zynthian specific modules
from . import zynthian_gui_config
from . import zynthian_gui_selector

#------------------------------------------------------------------------------
# Configure logging
#------------------------------------------------------------------------------

# Set root logging level
logging.basicConfig(stream=sys.stderr, level=zynthian_gui_config.log_level)

#------------------------------------------------------------------------------
# Zynthian Bank Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_bank(zynthian_gui_selector):

	def __init__(self):
		super().__init__('Bank', True)
    
	def fill_list(self):
		zynthian_gui_config.zyngui.curlayer.load_bank_list()
		self.list_data=zynthian_gui_config.zyngui.curlayer.bank_list
		super().fill_list()

	def show(self):
		self.index=zynthian_gui_config.zyngui.curlayer.get_bank_index()
		logging.debug("BANK INDEX => %s" % self.index)
		super().show()

	def select_action(self, i):
		if self.list_data[i][0] is not None:
			zynthian_gui_config.zyngui.curlayer.set_bank(i)
			zynthian_gui_config.zyngui.show_screen('preset')
			# If there is only one preset, jump to instrument control
			if len(zynthian_gui_config.zyngui.curlayer.preset_list)==1:
				zynthian_gui_config.zyngui.screens['preset'].select_action(0)

	def set_select_path(self):
		if zynthian_gui_config.zyngui.curlayer:
			self.select_path.set(zynthian_gui_config.zyngui.curlayer.get_basepath())

#-------------------------------------------------------------------------------
