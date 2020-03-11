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
from os.path import isfile, isdir, join, basename

# Zynthian specific modules
from . import zynthian_gui_config
from . import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian Load/Save Snapshot GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_snapshot(zynthian_gui_selector):

	def __init__(self):
		self.base_dir = os.environ.get('ZYNTHIAN_MY_DATA_DIR',"/zynthian/zynthian-my-data") + "/snapshots"
		self.default_snapshot_fpath = join(self.base_dir,"default.zss")
		self.last_state_snapshot_fpath = join(self.base_dir,"last_state.zss")
		self.bank_dir = None
		self.bankless_mode = False
		self.action = "LOAD"
		self.index_offset = 0
		self.midi_banks = {}
		self.midi_programs = {}
		super().__init__('Bank', True)


	def get_snapshot_fpath(self,f):
		return join(self.base_dir,self.bank_dir,f);


	def get_next_name(self):
		n=max(map(lambda item: int(item[2].split('-')[0]) if item[2].split('-')[0].isdigit() else 0, self.list_data))
		return "{0:03d}".format(n+1)


	def get_new_snapshot(self):
		return self.get_next_name() + '.zss'


	def get_new_bankdir(self):
		return self.get_next_name()


	def change_index_offset(self, i):
		self.index=self.index-self.index_offset+i
		self.index_offset=i
		if self.index<0:
			self.index=0


	def check_bankless_mode(self):
		banks = [ d for d in os.listdir(self.base_dir) if os.path.isdir(os.path.join(self.base_dir, d)) ]
		n_banks = len(banks)

		# If no banks, create the first one and choose it.
		if n_banks == 0:
			self.bank_dir = "000"
			os.makedirs(self.base_dir + "/" + self.bank_dir)
			self.bankless_mode = True

		# If only one bank, choose it.
		elif n_banks == 1:
			self.bank_dir = banks[0]
			self.bankless_mode = True

		# If more than 1, multibank mode
		else:
			self.bankless_mode = False


	def load_bank_list(self):
		self.midi_banks={}
		self.list_data=[]

		i=0
		if self.action=="SAVE" or isfile(self.default_snapshot_fpath):
			self.list_data.append((self.default_snapshot_fpath,i,"Default"))
			i=i+1

		if self.action=="LOAD" and isfile(self.last_state_snapshot_fpath):
			self.list_data.append((self.last_state_snapshot_fpath,i,"Last State"))
			i += 1

		if self.action=="SAVE":
			self.list_data.append(("NEW_BANK",1,"New Bank"))
			i=i+1

		self.change_index_offset(i)

		for f in sorted(os.listdir(self.base_dir)):
			dpath=join(self.base_dir,f)
			if isdir(dpath):
				self.list_data.append((dpath,i,f))
				try:
					bn=self.get_midi_number(f)
					self.midi_banks[str(bn)]=i
					logging.debug("Snapshot Bank '%s' => MIDI bank %d" % (f,bn))
				except:
					logging.warning("Snapshot Bank '%s' don't have a MIDI bank number" % f)
				i=i+1


	def load_snapshot_list(self):
		self.midi_programs={}
		self.list_data = []

		i = 0
		if not self.bankless_mode:
			self.list_data.append((self.base_dir,0,".."))
			i += 1

		else:
			if self.action=="SAVE" or isfile(self.default_snapshot_fpath):
				self.list_data.append((self.default_snapshot_fpath,i,"Default"))
				i += 1

			if self.action=="LOAD" and isfile(self.last_state_snapshot_fpath):
				self.list_data.append((self.last_state_snapshot_fpath,i,"Last State"))
				i += 1

		if self.action=="SAVE":
			self.list_data.append(("NEW_SNAPSHOT",1,"New Snapshot"))
			i += 1

		self.change_index_offset(i)

		head, bname = os.path.split(self.bank_dir)
		for f in sorted(os.listdir(join(self.base_dir,self.bank_dir))):
			fpath=self.get_snapshot_fpath(f)
			if isfile(fpath) and f[-4:].lower()=='.zss':
				#title=str.replace(f[:-4], '_', ' ')
				title=f[:-4]
				self.list_data.append((fpath,i,title))
				try:
					bn=self.get_midi_number(bname)
					pn=self.get_midi_number(title)
					self.midi_programs[str(pn)]=i
					logging.debug("Snapshot '{}' => MIDI bank {}, program {}".format(title,bn,pn))
				except:
					logging.warning("Snapshot '{}' don't have a MIDI program number".format(title))
				i += 1


	def fill_list(self):
		self.check_bankless_mode()

		if self.bank_dir is None:
			self.selector_caption='Bank'
			self.load_bank_list()
		else:
			self.selector_caption='Snapshot'
			self.load_snapshot_list()
		super().fill_list()


	def show(self):
		if not self.zyngui.curlayer:
			self.action="LOAD"

		super().show()

		if len(self.list_data)==0 and self.action=="LOAD":
			self.action="SAVE"
			super().show()


	def load(self):
		self.action="LOAD"
		self.show()


	def save(self):
		self.action="SAVE"
		self.show()


	def select_action(self, i, t='S'):
		try:
			fpath=self.list_data[i][0]
			fname=self.list_data[i][2]
		except:
			logging.warning("List is empty")
			return
		if fpath=='NEW_BANK':
			self.bank_dir=self.get_new_bankdir()
			os.mkdir(join(self.base_dir,self.bank_dir))
			self.show()
		elif isdir(fpath):
			if fpath==self.base_dir:
				self.bank_dir=None
				self.index=i
			else:
				self.bank_dir=self.list_data[i][2]
			self.show()
		elif self.action=="LOAD":
			if fpath=='NEW_SNAPSHOT':
				self.zyngui.screens['layer'].reset()
				self.zyngui.show_screen('layer')
			else:
				self.zyngui.screens['layer'].load_snapshot(fpath)
				#self.zyngui.show_screen('control')
		elif self.action=="SAVE":
			if fpath=='NEW_SNAPSHOT':
				fpath=self.get_snapshot_fpath(self.get_new_snapshot())
				self.zyngui.screens['layer'].save_snapshot(fpath)
				self.zyngui.show_active_screen()
			else:
				if isfile(fpath):
					self.zyngui.show_confirm("Do you really want to overwrite the snapshot %s?" % fname, self.cb_confirm_save_snapshot,[fpath])
				else:
					self.zyngui.screens['layer'].save_snapshot(fpath)
					self.zyngui.show_active_screen()


	def cb_confirm_save_snapshot(self, params):
		self.zyngui.screens['layer'].save_snapshot(params[0])


	def save_default_snapshot(self):
		self.zyngui.screens['layer'].save_snapshot(self.default_snapshot_fpath)


	def save_last_state_snapshot(self):
		self.zyngui.screens['layer'].save_snapshot(self.last_state_snapshot_fpath)


	def delete_last_state_snapshot(self):
		try:
			os.remove(self.last_state_snapshot_fpath)
		except:
			pass


	def get_midi_number(self, f):
		return int(f.split('-')[0])


	def midi_bank_change(self, bn):
		#Get bank list
		old_bank_dir=self.bank_dir
		self.bank_dir=None
		self.fill_list()
		#Load bank dir
		bn=str(bn)
		if bn in self.midi_banks:
			self.bank_dir=self.list_data[self.midi_banks[bn]][2]
			logging.debug("Snapshot Bank Change %s: %s" % (bn,self.bank_dir))
			self.show()
			return True
		else:
			self.bank_dir=old_bank_dir
			return False


	def midi_bank_change_offset(self,offset):
		try:
			bn = self.get_midi_number(self.bank_dir)+offset
			self.midi_bank_change(bn)
		except:
			logging.warning("Can't do Snapshot Bank Change Offset {}".format(offset))


	def midi_bank_change_up(self):
		self.midi_bank_change_offset(1)


	def midi_bank_change_down(self):
		self.midi_bank_change_offset(-1)


	def midi_program_change(self, pn):
		#If no bank selected, default to first bank
		if self.bank_dir is None:
			self.fill_list()
			self.bank_dir=self.list_data[0][2]
			self.fill_list()
		#Load snapshot
		pn=str(pn)
		if pn in self.midi_programs:
			fpath=self.list_data[self.midi_programs[pn]][0]
			logging.debug("Snapshot Program Change %s: %s" % (pn,fpath))
			self.zyngui.show_modal("snapshot")
			self.zyngui.screens['layer'].load_snapshot(fpath)
			return True
		else:
			return False


	def midi_program_change_offset(self,offset):
		try:
			f=basename(self.zyngui.screens['layer'].last_snapshot_fpath)
			pn=self.get_midi_number(f)+offset
		except:
			pn=0
		self.midi_program_change(pn)


	def midi_program_change_up(self):
		self.midi_program_change_offset(1)


	def midi_program_change_down(self):
		self.midi_program_change_offset(-1)


	def next(self):
		if self.action=="SAVE": self.action="LOAD"
		elif self.action=="LOAD": self.action="SAVE"
		self.show()


	def set_select_path(self):
		title=(self.action.lower()+" snapshot").title()
		if not self.bankless_mode and self.bank_dir:
			title=title+": "+self.bank_dir
		self.select_path.set(title)


#------------------------------------------------------------------------------
