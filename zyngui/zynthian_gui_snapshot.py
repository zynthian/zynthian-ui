#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Snapshot Selector (load/save)) Class
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
import logging
from datetime import datetime
from os.path import isfile, isdir, join, basename, dirname, splitext
from glob import glob
import shutil


# Zynthian specific modules
from zyngui.zynthian_gui_selector import zynthian_gui_selector

# ------------------------------------------------------------------------------
# Zynthian Load/Save Snapshot GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_snapshot(zynthian_gui_selector):

	def __init__(self):
		self.bankless_mode = False
		self.index_offset = 0
		super().__init__('Bank', True)
		self.sm = self.zyngui.state_manager

		self.check_bankless_mode()

	def get_snapshot_fpath(self, f):
		if f in ["last_state.zss", "default.zss"]:
			return join(self.sm.snapshot_dir, f)
		return join(self.sm.snapshot_dir, self.sm.snapshot_bank, f)

	def get_next_program(self, offset):
		"""Get the next available program number
		offset : Minimum program number to return
		Returns : Next available program mumber as integer or None if none available
		"""
		
		files = os.listdir(self.get_snapshot_fpath(''))
		files.sort()
		for filename in files:
			if offset > 127:
				return None
			program = self.get_midi_number(filename)
			if type(program) != int:
				continue
			if program < offset:
				continue
			if program == offset:
				offset += 1
		return offset

	def get_parts_from_path(self, path):
		"""Get an list of parts of a snapshot filename

		path : Full path and filename of snapshot file
		Returns : List of parts: [program, display name, filename, path] or None for invalid path
		"""

		if path[-4:].lower() != '.zss':
			return None

		filename = os.path.basename(path)
		name = filename[:-4].replace(';','>',1).replace(';','/')

		# Check if prefix is program-
		try:
			program = int(filename.split('-')[0])
			name = name.split('-',1)[1]
		except:
			program = None

		return [program, name, filename, path]

	def get_path_from_parts(self, parts):
		"""Get full path and filename from parts
		
		parts : List of parts [program, display name, filename, path]
		returns : Valid filename or None if invalid parts
		"""

		if type(parts) != list or len(parts) != 4:
			return None

		name = parts[1] + '.zss'
		if type(parts[0]) == int and 0 <= parts[0] < 128:
			name = format(parts[0], "03") + '-' + name
		path = self.get_snapshot_fpath(name.replace('>', ';').replace('/', ';'))

		return path

	def change_index_offset(self, i):
		self.index = self.index - self.index_offset + i
		self.index_offset = i
		if self.index < 0:
			self.index = 0

	def check_bankless_mode(self):
		bank_dirs = [d for d in os.listdir(self.sm.snapshot_dir) if os.path.isdir(join(self.sm.snapshot_dir, d))]
		n_banks = len(bank_dirs)
		# If no banks, create the first one and choose it.
		if n_banks == 0:
			os.makedirs(f"{self.sm.snapshot_dir}/000")
			self.bankless_mode = True
		# If only one bank, choose it.
		elif n_banks == 1:
			self.bankless_mode = True
			self.sm.snapshot_bank = bank_dirs[0]
		# If more than 1, multibank mode
		else:
			self.bankless_mode = False

	def load_bank_list(self):
		self.list_data = []
		i = 0
		if isfile(self.sm.default_snapshot_fpath):
			self.list_data.append((self.sm.default_snapshot_fpath, i, "Default"))
			i = i + 1
		if isfile(self.sm.last_state_snapshot_fpath):
			self.list_data.append((self.sm.last_state_snapshot_fpath, i, "Last State"))
			i = i + 1
		self.list_data.append(("NEW_BANK", i, "New Bank"))
		i = i + 1
		self.change_index_offset(i)

		for dpath in sorted(glob(f"{self.sm.snapshot_dir}/[0-9][0-9][0-9]*")):
			if isdir(dpath):
				bank_name = basename(dpath)
				if bank_name.startswith('.'):
					continue

				self.list_data.append((dpath, i, bank_name))
				try:
					bank_number = self.get_midi_number(bank_name)
					logging.debug("Snapshot Bank '%s' => MIDI bank %d" % (bank_name, bank_number))
				except:
					logging.warning("Snapshot Bank '%s' don't have a MIDI bank number" % bank_name)
				if bank_name == self.sm.snapshot_bank:
					self.index = i
				i = i + 1

	def load_snapshot_list(self):
		self.list_data = []
		i = 0
		if not self.bankless_mode:
			self.list_data.append((self.sm.snapshot_dir, i, ".."))
			i += 1

		if self.zyngui.chain_manager.get_chain_count() or self.zyngui.chain_manager.get_processor_count() > 0:
			# TODO: Add better validation of populated state, e.g. sequences
			self.list_data.append(("SAVE", i, "Save as new snapshot"))
		if self.bankless_mode:
			if isfile(self.sm.default_snapshot_fpath):
				self.list_data.append((self.sm.default_snapshot_fpath, i, "Default"))
				i += 1
			if isfile(self.sm.last_state_snapshot_fpath):
				self.list_data.append((self.sm.last_state_snapshot_fpath, i, "Last State"))
				i += 1

		self.change_index_offset(i)

		for fpath in sorted(glob(f"{self.sm.snapshot_dir}/{self.sm.snapshot_bank}/*.zss")):
			if isfile(fpath):
				title = basename(fpath)[:-4].replace(';', '>', 1).replace(';', '/')
				self.list_data.append((fpath, i, title))
				i += 1

	def fill_list(self):
		self.check_bankless_mode()
		if self.sm.snapshot_bank is None:
			self.load_bank_list()
		else:
			self.load_snapshot_list()
		super().fill_list()

	def select_action(self, i, t='S'):
		fpath = self.list_data[i][0]
		if fpath == 'NEW_BANK':
			self.zyngui.show_keyboard(self.new_bank, "")
		elif isdir(fpath):
			if fpath == self.sm.snapshot_dir:
				self.sm.snapshot_bank = None
			elif t == 'B':
				self.show_bank_options(self.list_data[i][2])
			else:
				self.sm.snapshot_bank = self.list_data[i][2]
			self.build_view()
		else:
			if fpath:
				if fpath == "SAVE":
					self.zyngui.show_keyboard(self.save_snapshot_by_name, "New Snapshot")
				else:
					self.show_options(i, self.list_data[i][2] == "Last State")

	def new_bank(self, title):
		full_title = f"{max(map(lambda item: int(item[2].split('-')[0]) if item[2].split('-')[0].isdigit() else 0, self.list_data)) + 1:03d}"
		if title:
			full_title = f"{full_title}-{title}"
		try:
			os.mkdir(join(self.sm.snapshot_dir, full_title))
			self.sm.snapshot_bank = full_title
		except:
			logging.warning("Failed to create new snapshot bank")
		self.build_view()

	def show_bank_options(self, bank):
		if not isdir(f"{self.sm.snapshot_dir}/{bank}"):
			return
		options = {
			"Delete Bank": bank,
			"Rename Bank": bank
		}
		self.zyngui.screens['option'].config(bank, options, self.bank_options_cb)
		self.zyngui.show_screen('option')

	def bank_options_cb(self, option, param):
		if option == "Delete Bank":
			snapshots = glob(f"{self.sm.snapshot_dir}/{param}/*.zss")
			self.zyngui.show_confirm(f"Do you really want to delete bank {param} with {len(snapshots)} snapshots", self.delete_bank, param)
		elif option == "Rename Bank":
			parts = param.split("-", 1)
			if len(parts) > 1:
				self.old_prog = parts[0]
				name = parts[1]
			else:
				self.old_prog = parts[0]
				name = ""
			self.old_path = f"{self.sm.snapshot_dir}/{param}"
			self.zyngui.show_keyboard(self.rename_bank, name)

	def delete_bank(self, bank):
		try:
			shutil.rmtree(f"{self.sm.snapshot_dir}/{bank}")
			if self.sm.snapshot_bank == bank:
				self.sm.snapshot_dir = None
			self.fill_list()
		except:
			pass

	def rename_bank(self, name):
		if name:
			new_path = f"{self.sm.snapshot_dir}/{self.old_prog}-{name}"
		else:
			new_path = f"{self.sm.snapshot_dir}/{self.old_prog}"
		try:
			os.rename(self.old_path, new_path)
			self.fill_list()
		except:
			logging.warning("Failed to rename snapshot")

	def show_options(self, i, restrict_options):
		fpath = self.list_data[i][0]
		fname = self.list_data[i][2]
		options = {
			"Load": fpath,
			"Load Chains": fpath,
			"Load Sequences": fpath,
			"Save": fname
		}
		budir = dirname(fpath) + "/.backup"
		if isdir(budir):
			options["Restore Backup"] = fpath
		if not restrict_options:
			options.update({
				"Rename": fname,
				"Set Program": fname,
				"Delete": fname
			})
		self.zyngui.screens['option'].config(fname, options, self.options_cb)
		self.zyngui.show_screen('option')

	def options_cb(self, option, param):
		fpath = self.list_data[self.index][0]
		fname = self.list_data[self.index][2]
		parts = self.get_parts_from_path(fpath)
		if parts is None:
			logging.warning("Wrong snapshot {} => {}".format(self.index, fpath))
			return
		if option == "Load":
			#self.zyngui.show_confirm("Loading '%s' will destroy current chains & sequences..." % (fname), self.load_snapshot, fpath)
			self.load_snapshot(fpath)
		elif option == "Load Chains":
			#self.zyngui.show_confirm("Loading chains from '%s' will destroy current chains..." % (fname), self.load_snapshot_chains, fpath)
			self.load_snapshot_chains(fpath)
		elif option == "Load Sequences":
			#self.zyngui.show_confirm("Loading sequences from '%s' will destroy current sequences..." % (fname), self.load_snapshot_sequences, fpath)
			self.load_snapshot_sequences(fpath)
		elif option == "Save":
			#self.zyngui.show_confirm("Do you really want to overwrite '%s'?" % (fname), self.save_snapshot, fpath)
			self.save_snapshot(fpath)
		elif option == "Restore Backup":
			budir = dirname(fpath) + "/.backup"
			fbase, fext = splitext(parts[2])
			fpat = "{}.*.zss".format(fbase)
			self.zyngui.screens['option'].config_file_list("Restore backup: {}".format(fname), budir, fpat, self.restore_backup_cb)
			self.zyngui.show_screen('option')
		elif option == "Rename":
			self.zyngui.show_keyboard(self.rename_snapshot, parts[1])
		elif option == "Set Program":
			self.zyngui.screens['midi_prog'].config(parts[0], self.set_program)
			self.zyngui.show_screen('midi_prog')
		elif option == "Delete":
			self.zyngui.show_confirm("Do you really want to delete '%s'" % fname, self.delete_confirmed, fpath)

	def load_snapshot(self, fpath):
		self.sm.save_last_state_snapshot()
		state = self.sm.load_snapshot(fpath)
		if state is None:
			self.zyngui.clean_all()
		elif "zyngui" in state:
			if self.load_zyngui(state["zyngui"]):
				return
		self.zyngui.show_screen('audio_mixer', self.zyngui.SCREEN_HMODE_RESET)

	def load_snapshot_chains(self, fpath):
		self.sm.save_last_state_snapshot()
		self.sm.load_snapshot(fpath, load_sequences=False)
		self.zyngui.show_screen('audio_mixer', self.zyngui.SCREEN_HMODE_RESET)

	def load_snapshot_sequences(self, fpath):
		self.sm.save_last_state_snapshot()
		self.sm.load_snapshot(fpath, load_chains=False)
		self.zyngui.show_screen('zynpad', hmode=self.zyngui.SCREEN_HMODE_RESET)

	def restore_backup_cb(self, fname, fpath):
		logging.debug("Restoring snapshot backup '{}'".format(fname))
		self.load_snapshot(fpath)

	def rename_snapshot(self, new_name):
		fpath = self.list_data[self.index][0]
		parts = self.get_parts_from_path(fpath)
		if parts is None:
			logging.warning("Wrong snapshot {} => {}".format(self.index, fpath))
			return
		if parts[1] == new_name:
			self.zyngui.close_screen()
			return
		if type(parts[0]) == int and parts[0] < 128:
			new_name = format(parts[0], "03") + '-' + new_name
		new_path = self.get_snapshot_fpath(new_name.replace('>', ';').replace('/', ';'))
		if new_path[-4:].lower() != '.zss':
			new_path += '.zss'
		if isfile(new_path):
			self.zyngui.show_confirm("Do you really want to overwrite '%s'?" % new_name, self.do_rename, [parts[3], new_path])
		else:
			self.do_rename([parts[3], new_path])
		self.select_listbox_by_name(parts[2][:-4])

	def do_rename(self, data):
		try:
			os.rename(data[0], data[1])
			self.fill_list()
		except Exception as e:
			logging.warning("Failed to rename snapshot '{}' to '{}' => {}".format(data[0], data[1], e))

	def set_program(self, value):
		fpath = self.list_data[self.index][0]
		parts = self.get_parts_from_path(fpath)
		if parts is None:
			logging.warning("Wrong snapshot '{}' => '{}'".format(self.index, fpath))
			return

		try:
			program = int(value)
			if program < 0 or program > 127:
				program = None
		except:
			program = None

		parts[0] = program
		dfpath = self.get_path_from_parts(parts)
		files_to_change = []

		try:
			if isinstance(program, int):
				path = self.get_snapshot_fpath('')
				files = os.listdir(path)
				files.sort()
				first_gap = program
				for filename in files:
					dparts = self.get_parts_from_path(path + filename)
					if dparts is None or dparts[0] is None or dparts[0] < program or dparts[3] == parts[3]:
						continue
					if dparts[0] > first_gap:
						break  # Found a gap above required program so don't move any more files
					dparts[0] += 1
					first_gap = dparts[0]
					fullname = self.get_path_from_parts(dparts)
					files_to_change.append([dparts[3], fullname])
				if len(files_to_change):
					self.zyngui.show_confirm("Do you want to move {} snapshots up to next available program?".format(len(files_to_change)), self.do_set_program_number, (fpath, dfpath, files_to_change))
					return
			self.do_set_program_number((fpath, dfpath, files_to_change))
		except Exception as e:
			logging.warning("Failed to set program for snapshot {} to {} => {}".format(fpath, program, e))

	def do_set_program_number(self, params):
		try:
			fpath = params[0]
			dfpath = params[1]
			files_to_change = params[2]
		except Exception as e:
			logging.error(e)
			return
		files_to_change.sort(reverse=True)
		for files in files_to_change:
			os.rename(files[0], files[1])

		os.rename(fpath, dfpath)
		parts = self.get_parts_from_path(dfpath)
		
		self.zyngui.close_screen()
		self.select_listbox_by_name(parts[2][:-4])

	def save_snapshot_by_name(self, name):
		program = self.get_next_program(1)
		if type(program) == int and program < 128:
			name = format(program, "03") + "-" + name
		path = self.get_snapshot_fpath(name.replace('>', ';').replace('/', ';')) + '.zss'
		self.save_snapshot(path)
		self.fill_list()

	def save_snapshot(self, path):
		self.sm.backup_snapshot(path)
		self.sm.save_snapshot(path)
		self.zyngui.show_screen('audio_mixer', self.zyngui.SCREEN_HMODE_RESET)

	def delete_confirmed(self, fpath):
		logging.info("DELETE SNAPSHOT: {}".format(fpath))
		try:
			os.remove(fpath)
			self.fill_list()
		except Exception as e:
			logging.error(e)
		self.zyngui.close_screen()

	def get_midi_number(self, f):
		try:
			return int(f.split('-')[0])
		except:
			return None

	def set_select_path(self):
		title = "Snapshots"
		if not self.bankless_mode:
			if self.zyngui.state_manager.snapshot_bank is None:
				title = "Snapshot Bank"
			else:
				title = f"Snapshots: {self.zyngui.state_manager.snapshot_bank}"
		self.select_path.set(title)

	def load_zyngui(self, state):
		"""Load zyngui configuration from snapshot state
		
		state : zyngui state dictionary
		Returns : True if screen navigation performed
		TODO: Parse zyngui configuration from snapshot
		"""

		try:
			self.zyngui.show_screen(state["current_screen"], self.zyngui.SCREEN_HMODE_RESET)
			return True
		except:
			return False

# ------------------------------------------------------------------------------
