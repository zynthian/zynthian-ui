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
# Zynthian Bank Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_bank(zynthian_gui_selector):

	buttonbar_config = [
		(1, 'BACK'),
		(0, 'LAYER'),
		(2, 'FAVS'),
		(3, 'SELECT')
	]

	def __init__(self, parent = None):
		super(zynthian_gui_bank, self).__init__('Bank', parent)

    
	def fill_list(self):
		if not self.zyngui.curlayer:
			logging.error("Can't fill bank list for None layer!")
			return
		self.zyngui.curlayer.load_bank_list()
		self.list_data=self.zyngui.curlayer.bank_list
		super().fill_list()


	def show(self):
		if not self.zyngui.curlayer:
			logging.error("Can't show bank list for None layer!")
			return
		self.index=self.zyngui.curlayer.get_bank_index()
		logging.debug("BANK INDEX => %s" % self.index)
		super().show()


	def select_action(self, i, t='S'):
		if self.zyngui.curlayer.set_bank(i):
			self.zyngui.screens['preset'].disable_only_favs()
			if self.zyngui.modal_screen=="preset":
				self.zyngui.show_modal('preset')
			else:
				self.zyngui.show_screen('preset')
			# If there is only one preset, jump to instrument control
			if len(self.zyngui.curlayer.preset_list)<=1:
				self.zyngui.screens['preset'].select_action(0)
		else:
			self.show()


	def set_select_path(self):
		if self.zyngui.curlayer:
			self.select_path = (self.zyngui.curlayer.get_basepath())


#-------------------------------------------------------------------------------
