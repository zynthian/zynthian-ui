#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Snapshot Selector (load/save)) Class
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
import sys
import logging
from os.path import isfile, isdir, join

# Zynthian specific modules
from . import zynthian_gui_config
from . import zynthian_gui_selector

#------------------------------------------------------------------------------
# Configure logging
#------------------------------------------------------------------------------

# Set root logging level
logging.basicConfig(stream=sys.stderr, level=zynthian_gui_config.log_level)

#------------------------------------------------------------------------------
# Zynthian Load/Save Snapshot GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_snapshot(zynthian_gui_selector):
	snapshot_dir=os.getcwd()+"/my-data/snapshots"

	def __init__(self):
		self.action="LOAD"
		super().__init__('Snapshot', True)
        
	def fill_list(self):
		self.list_data=[("NEW",0,"New")]
		i=1
		if self.action=="SAVE" or isfile(join(self.snapshot_dir,"default.zss")):
			self.list_data.append((join(self.snapshot_dir,"default.zss"),i,"Default"))
			i=i+1
		for f in sorted(os.listdir(self.snapshot_dir)):
			if isfile(join(self.snapshot_dir,f)) and f[-4:].lower()=='.zss' and f!="default.zss":
				title=str.replace(f[:-4], '_', ' ')
				#print("snapshot list => %s" % title)
				self.list_data.append((join(self.snapshot_dir,f),i,title))
				i=i+1
		super().fill_list()

	def show(self):
		if not zynthian_gui_config.zyngui.curlayer:
			self.action=="LOAD"
		super().show()
		
	def load(self):
		self.action="LOAD"
		self.show()

	def save(self):
		self.action="SAVE"
		self.show()
		
	def get_new_fpath(self):
		try:
			n=int(self.list_data[-1][2][3:])
		except:
			n=0;
		fname='{0:04d}'.format(n+1) + '.zss'
		fpath=join(self.snapshot_dir,fname)
		return fpath

	def select_action(self, i):
		fpath=self.list_data[i][0]
		if self.action=="LOAD":
			if fpath=='NEW':
				zynthian_gui_config.zyngui.screens['layer'].reset()
				zynthian_gui_config.zyngui.show_screen('layer')
			else:
				zynthian_gui_config.zyngui.screens['layer'].load_snapshot(fpath)
				#zynthian_gui_config.zyngui.show_screen('control')
		elif self.action=="SAVE":
			if fpath=='NEW':
				fpath=self.get_new_fpath()
			zynthian_gui_config.zyngui.screens['layer'].save_snapshot(fpath)
			zynthian_gui_config.zyngui.show_active_screen()

	def next(self):
		if self.action=="SAVE": self.action="LOAD"
		elif self.action=="LOAD": self.action="SAVE"
		self.show()

	def set_select_path(self):
		title=self.action.lower().title()
		self.select_path.set(title)

#------------------------------------------------------------------------------
