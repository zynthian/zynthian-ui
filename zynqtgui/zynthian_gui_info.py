#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Info Class
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
import tkinter
import logging

# Zynthian specific modules
from . import zynthian_gui_config


# Qt modules
from PySide2.QtCore import Qt, QObject, Slot, Signal, Property


#------------------------------------------------------------------------------
# Zynthian Info GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_info(QObject):

	def __init__(self, parent=None):
		super(zynthian_gui_info, self).__init__(parent)
		self.shown=False
		self.zyngui=zynthian_gui_config.zyngui

		self.prop_text = ''


	def clean(self):
		self.prop_text = ''
		self.text_changed.emit()


	def add(self, text, tags=None):
		self.prop_text += '\n' + text
		self.text_changed.emit()


	def set(self, text, tags=None):
		self.clean()
		self.add(text+"\n",tags)
		self.text_changed.emit()


	def hide(self):
		if self.shown:
			self.shown=False


	def show(self, text = ''):
		self.set(text)
		if not self.shown:
			self.shown=True


	def zyncoder_read(self):
		pass


	def refresh_loading(self):
		pass


	def switch_select(self, t='S'):
		pass

	@Slot('void')
	def back_action(self):
		self.zyngui.cancel_modal_timer()
		self.zyngui.screens['admin'].kill_command()
		self.zyngui.show_modal('admin')
		return None


	def cb_push(self,event):
		self.zyngui.zynswitch_defered('S',1)

	def get_text(self):
		return self.prop_text

	text_changed = Signal()

	text = Property(str, get_text, notify = text_changed)

#-------------------------------------------------------------------------------
