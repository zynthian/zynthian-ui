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
from shutil import copy

# Zynthian specific modules
from . import zynthian_gui_config
from . import zynthian_gui_selector
from zynlibs.zynseq import zynseq

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
		return join(self.base_dir,self.bank_dir,f)


	#	Get the next available program number
	#	offset: Minimum program number to return
	#	returns: Next available program mumber as integer or 255 if none available
	def get_next_program(self, offset):
		files = os.listdir(self.get_snapshot_fpath(''))
		files.sort()
		for filename in files:
			if offset > 127:
				return 255
			program = self.get_midi_number(filename)
			if program < offset:
				continue
			if program == offset:
				offset += 1
			else:
				return offset
		return 255


	#	Rename files to ensure unique MIDI program numbers - renames files moving each conflicting file to next program
	#	program: Index of first program to validate - will move this index if it exists
	def fix_program(self, program):
		path = self.get_snapshot_fpath('')
		files = os.listdir(path)
		files.sort()
		for filename in files:
			parts = self.get_parts_from_path(path + filename)
			if parts[0] < program:
				continue
			if parts[0] == program:
				if program > 127:
					parts[0] = 255
				else:
					parts[0] += 1
				fullname = self.get_path_from_parts(parts)
				os.rename(parts[3], fullname)
			program = parts[0]


	#	Get an list of parts of a snapshot filename
	#	path: Full path and filename of snapshot file
	#	returns: List of parts: [program, display name, filename, path] or None for invalid path
	def get_parts_from_path(self, path):
		if path[-4:].lower() != '.zss':
			return None
		filename = os.path.basename(path)
		# Check if prefix is program-
		try:
			program = int(filename.split('-')[0])
		except:
			program = 255
		name = filename[:-4].replace(';','>',1).replace(';','/')
		if program != 255:
			name = name.split('-',1)[1]
		return [program, name, filename, path]


	#	Get full path and filename from parts
	#	parts: List of parts [program, display name, filename, path]
	#	returns: Valid filename or None if invalid parts
	def get_path_from_parts(self, parts):
		if type(parts) != list or len(parts) != 4:
			return None
		if parts == None:
			return
		name = parts[1] + '.zss'
		if parts[0] < 128:
			name = format(parts[0], "03") + '-' + name
		path = self.get_snapshot_fpath(name.replace('>',';').replace('/',';'))
		return path


	def get_next_name(self):
		n=max(map(lambda item: int(item[2].split('-')[0]) if item[2].split('-')[0].isdigit() else 0, self.list_data))
		return "{0:03d}".format(n+1)


	def get_new_snapshot(self):
		parts = self.zyngui.screens['layer'].layers[0].get_presetpath().split('#',2)
		name = parts[1].replace("/",";").replace(">",";").replace(" ; ",";")
		return self.get_next_name() + '-' + name + '.zss'


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
		if self.action=="SAVE":
			self.list_data.append((self.default_snapshot_fpath,i,"Default"))
			i=i+1
			self.list_data.append((self.last_state_snapshot_fpath,i,"Last State"))
			i=i+1
			self.list_data.append(("NEW_BANK",i,"New Bank"))
			i=i+1

		if self.action=="LOAD":
			if isfile(self.default_snapshot_fpath):
				self.list_data.append((self.default_snapshot_fpath,i,"Default"))
				i += 1
			if isfile(self.last_state_snapshot_fpath):
				self.list_data.append((self.last_state_snapshot_fpath,i,"Last State"))
				i += 1

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
			self.list_data.append((self.base_dir,i,".."))
			i += 1

		if self.action=="SAVE":
			self.list_data.append(("NEW_SNAPSHOT",i,"NEW"))
			i += 1
			if self.bankless_mode:
				self.list_data.append((self.default_snapshot_fpath,i,"Default"))
				i += 1
				self.list_data.append((self.last_state_snapshot_fpath,i,"Last State"))
				i += 1
		elif self.action=="LOAD": 
			self.list_data.append(("NEW_SNAPSHOT",i,"NEW"))
			if self.bankless_mode:
				if isfile(self.default_snapshot_fpath):
					self.list_data.append((self.default_snapshot_fpath,i,"Default"))
					i += 1
				if isfile(self.last_state_snapshot_fpath):
					self.list_data.append((self.last_state_snapshot_fpath,i,"Last State"))
					i += 1

		self.change_index_offset(i)

		head, bname = os.path.split(self.bank_dir)
		for f in sorted(os.listdir(join(self.base_dir,self.bank_dir))):
			fpath=self.get_snapshot_fpath(f)
			if isfile(fpath) and f[-4:].lower()=='.zss':
				title = f[:-4].replace(';','>',1).replace(';','/')
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


	def set_action(self, act):
		self.action = act


	def show(self):
		if not self.zyngui.curlayer:
			self.action="LOAD"

		super().show()

		if len(self.list_data)==0 and self.action=="LOAD":
			self.action="SAVE"
			super().show()


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
			if fpath:
				if t=='S':
					if fpath == 'NEW_SNAPSHOT':
						if len(self.zyngui.screens['layer'].layers) > 0:
							self.save_last_state_snapshot()
							self.zyngui.screens['layer'].reset()
						if zynseq.libseq:
							zynseq.load("")
						self.zyngui.show_screen('layer')
					else:
						self.zyngui.screens['layer'].load_snapshot(fpath)
						#self.zyngui.show_screen('control')
				else:
					if fpath == 'NEW_SNAPSHOT':
						options = {"Save as":fname}
					else:
						options = {"Delete":fname, "Rename":fname, "Create copy":fname, "Overwrite":fname, "Set program":fname}
					self.zyngui.screens['option'].config(fname, options, self.context_cb)
					self.zyngui.show_modal('option')
		elif self.action=="SAVE":
			if fpath=='NEW_SNAPSHOT':
				fpath=self.get_snapshot_fpath(self.get_new_snapshot())
				self.zyngui.screens['layer'].save_snapshot(fpath)
				self.zyngui.show_active_screen()
			elif fpath:
				if isfile(fpath):
					self.zyngui.show_confirm("Do you really want to overwrite the snapshot %s?" % fname, self.cb_confirm_save_snapshot,fpath)
				else:
					self.zyngui.screens['layer'].save_snapshot(fpath)
					self.zyngui.show_active_screen()


	def context_cb(self, option, param):
		fpath=self.list_data[self.index][0]
		fname=self.list_data[self.index][2]
		parts=self.get_parts_from_path(self.list_data[self.index][0])
		if option == "Delete":
			self.zyngui.show_confirm("Do you really want to delete %s" % (fname), self.delete_confirmed, self.get_snapshot_fpath(fpath))
		elif option == "Rename":
			if parts == None:
				return
			self.zyngui.show_keyboard(self.rename_snapshot, parts[1])
		elif option == "Create copy":
			self.zyngui.show_keyboard(self.copy_snapshot, parts[1] + ' (copy)')
		elif option == "Overwrite":
			self.zyngui.show_confirm("Do you really want to overwrite %s with current configuration" % (fname), self.cb_confirm_save_snapshot, self.get_snapshot_fpath(fpath))
		elif option == "Set program":
			self.zyngui.show_keyboard(self.set_program, fname.split('-')[0])
		elif option == "Save as":
			parts = self.get_parts_from_path(self.get_new_snapshot())
			self.zyngui.show_keyboard(self.save_snapshot, parts[1])


	def rename_snapshot(self, new_name):
		parts = self.get_parts_from_path(self.list_data[self.index][0])
		if parts == None:
			return
		fpath = parts[3]
		if parts[0] < 128:
			new_name = format(parts[0], "03") + '-' + new_name
		new_path = self.get_snapshot_fpath(new_name).replace('>',';')
		if new_path[-4:].lower() != '.zss':
			new_path += '.zss'
		if isfile(new_path):
			self.zyngui.show_confirm("Do you really want to overwrite the snapshot %s?" % new_name, self.do_rename,[self.list_data[self.index][0],new_path])
		else:
			try:
				os.rename(fpath, new_path)
				self.fill_list()
			except:
				logging.warning("Failed to rename snapshot %s to %s", fpath, new_path)


	def copy_snapshot(self, new_name):
		parts = self.get_parts_from_path(self.list_data[self.index][0])
		if parts == None:
			logging.warning("Cannot find path of %d", self.index)
			return
		parts[0] = self.get_next_program(parts[0])
		if parts[0] < 128:
			new_name = format(parts[0], "03") + '-' + new_name
		new_path=self.get_snapshot_fpath(new_name.replace('>',';').replace('/',';'))
		if new_path[-4:].lower() != '.zss':
			new_path += '.zss'
		if isfile(new_path):
			self.zyngui.show_confirm("Do you really want to overwrite the snapshot %s?" % new_name, self.do_copy,[self.list_data[self.index][0],new_path])
		else:
			self.do_copy([parts[3], new_path])


	def do_rename(self, data):
		try:
			os.rename(data[0], data[1])
			self.fill_list()
		except:
			logging.warning("Failed to rename snapshot")


	def do_copy(self, data):
		try:
			copy(data[0], data[1])
			self.show()
		except:
			logging.warning("Failed to copy snapshot")


	def set_program(self, value):
		try:
			program = int(value)
		except:
			logging.warning("Invalid program")
			return
		if program < 0 or program > 127:
			return
		parts = self.get_parts_from_path(self.list_data[self.index][0])
		if parts == None:
			return
		fpath = self.get_snapshot_fpath(format(program, "03") + '-' + parts[1].replace('>',';',1).replace('/',';') + '.zss')
		os.rename(self.list_data[self.index][0], "/tmp/snapshot.tmp")
		self.fix_program(program)
		os.rename("/tmp/snapshot.tmp", fpath)
		self.show()


	def save_snapshot(self, name):
		program = self.get_next_program(1)
		if program < 128:
			name = format(program, "03") + "-" + name + '.zss'
		path = self.get_snapshot_fpath(name.replace('>',';').replace('/',';'))
		self.zyngui.screens['layer'].save_snapshot(path)
		self.zyngui.show_active_screen()


	def cb_confirm_save_snapshot(self, params):
		self.zyngui.screens['layer'].save_snapshot(params)
		self.zyngui.show_active_screen()


	def save_default_snapshot(self):
		self.zyngui.screens['layer'].save_snapshot(self.default_snapshot_fpath)


	def load_default_snapshot(self, quiet=False):
		if isfile(self.default_snapshot_fpath):
			return self.zyngui.screens['layer'].load_snapshot(self.default_snapshot_fpath, quiet)


	def save_last_state_snapshot(self):
		self.zyngui.screens['layer'].save_snapshot(self.last_state_snapshot_fpath)


	def load_last_state_snapshot(self, quiet=False):
		if isfile(self.last_state_snapshot_fpath):
			return self.zyngui.screens['layer'].load_snapshot(self.last_state_snapshot_fpath, quiet)


	def delete_last_state_snapshot(self):
		try:
			os.remove(self.last_state_snapshot_fpath)
		except:
			pass


	def delete_confirmed(self, fpath):
		logging.info("DELETE SNAPSHOT: {}".format(fpath))
		try:
			os.remove(fpath)
		except Exception as e:
			logging.error(e)


	def get_midi_number(self, f):
		try:
			return int(f.split('-')[0])
		except:
			return 255


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
