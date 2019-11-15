#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI OSC Browser Class => Outdated!!
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
import liblo
import logging

# Zynthian specific modules
from . import zynthian_gui_config
from . import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian OSC Browser GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_osc_browser(zynthian_gui_selector):
	mode=None
	osc_path=None

	def __init__(self):
		super().__init__("OSC Path", True)
		self.mode=None
		self.osc_path=None
		self.index=1
		self.set_select_path()

	def get_list_data(self):
		pass

	def show(self):
		self.index=1
		super().show()

	def select_action(self, i):
		pass

	def get_osc_paths(self, path=''):
		self.list_data=[]
		if path=='root':
			self.osc_path="/part"+str(zyngui.curlayer.get_midi_chan())+"/"
		else:
			self.osc_path=self.osc_path+path
		liblo.send(zyngui.osc_target, "/path-search",self.osc_path,"")
		logging.debug("OSC /path-search "+self.osc_path)

	def select_action(self, i):
		path=self.list_data[i][0]
		tnode=self.list_data[i][1]
		title=self.list_data[i][2]
		logging.info("SELECT PARAMETER: %s (%s)" % (title,tnode))
		if tnode=='dir':
			self.get_osc_paths(path)
		elif tnode=='ctrl':
			parts=self.osc_path.split('/')
			if len(parts)>1:
				title=parts[-2]+" "+title
			zyngui.screens['control'].zcontrollers_config[2]=(title[:-2],self.osc_path+path,64,127) #TODO
			liblo.send(zyngui.osc_target, self.osc_path+path)
			zyngui.show_screen('control')
		elif tnode=='bool':
			#TODO: Toogle the value!!
			liblo.send(zyngui.osc_target, self.osc_path+path,True)
			zyngui.show_screen('control')

	def set_select_path(self):
		self.select_path.set(zyngui.zyngine.get_presetpath())


#-------------------------------------------------------------------------------
