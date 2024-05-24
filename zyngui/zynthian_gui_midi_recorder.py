#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI MIDI Recorder Class
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
from os.path import isfile, join
import tkinter

# Zynthian specific modules
import zynconf
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector
from zyngui.zynthian_gui_controller import zynthian_gui_controller
from zynlibs.zynsmf import zynsmf # Python wrapper for zynsmf (ensures initialised and wraps load() function)
from zynlibs.zynsmf.zynsmf import libsmf # Direct access to shared library 

# ------------------------------------------------------------------------------
# Zynthian MIDI Recorder GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_midi_recorder(zynthian_gui_selector):

	def __init__(self):
		self.capture_dir_sdc = os.environ.get('ZYNTHIAN_MY_DATA_DIR', "/zynthian/zynthian-my-data") + "/capture"
		self.ex_data_dir = os.environ.get('ZYNTHIAN_EX_DATA_DIR', "/media/root")
		self.recording = False
		self.playing = False

		self.smf_timer = None # 1s timer used to check end of SMF playback

		super().__init__('MIDI Recorder', True)

		self.bpm_zgui_ctrl = None

	def refresh_status(self):
		super().refresh_status()
		update = False
		if self.recording != self.zyngui.state_manager.status_midi_recorder:
			self.recording = self.zyngui.state_manager.status_midi_recorder
			update = True
		if self.playing != self.zyngui.state_manager.status_midi_player:
			self.playing = self.zyngui.state_manager.status_midi_player
			update = True
		if update:
			self.update_list()

	def hide(self):
		self.hide_playing_bpm()
		super().hide()

	def fill_list(self):
		#self.index = 0
		self.list_data = []

		self.list_data.append(None)
		self.update_status_recording()

		self.list_data.append(None)
		self.update_status_loop()

		self.list_data.append((None, 0, "> MIDI Tracks"))

		# Generate file list, sorted by mtime
		flist = self.get_filelist(self.capture_dir_sdc, "SD")
		for exd in zynthian_gui_config.get_external_storage_dirs(self.ex_data_dir):
			flist += self.get_filelist(exd, "USB")
		i = 1
		for finfo in sorted(flist, key=lambda d: d['mtime'], reverse=True) :
			self.list_data.append((finfo['fpath'], i, finfo['title']))
			i += 1

		super().fill_list()

	def get_filelist(self, src_dir, src_name):
		res = []
		smf = libsmf.addSmf()

		for f in os.listdir(src_dir):
			fpath = join(src_dir, f)
			fname = f[:-4]
			fext = f[-4:].lower()
			if isfile(fpath) and fext in ('.mid'):
				# Get mtime
				mtime = os.path.getmtime(fpath)

				# Get duration
				try:
					zynsmf.load(smf, fpath)
					length = libsmf.getDuration(smf)
				except Exception as e:
					length = 0
					logging.warning(e)

				# Generate title
				title = "{}[{}:{:02d}] {}".format(src_name, int(length / 60), int(length % 60), fname.replace(";", ">", 1).replace(";", "/"))

				res.append({
					'fpath': fpath,
					'fname': fname,
					'ext': fext,
					'length': length,
					'mtime': mtime,
					'title': title
				})

		libsmf.removeSmf(smf)
		return res

	def fill_listbox(self):
		super().fill_listbox()
		self.update_status_playback()

	def update_status_playback(self):
		item_labels = self.listbox.get(0, tkinter.END)
		for i, row in enumerate(self.list_data):
			if self.playing and row[0] and row[0] == self.zyngui.state_manager.last_midi_file:
				item_label = '▶ ' + row[2]
			else:
				item_label = row[2]

			if item_labels[i] != item_label:
				self.listbox.delete(i)
				self.listbox.insert(i, item_label)

		if self.playing:
			if zynthian_gui_config.transport_clock_source == 0:
				self.show_playing_bpm()
		else:
			self.hide_playing_bpm()

		self.select_listbox(self.index)

	def update_status_recording(self, fill=False):
		if self.list_data:
			if self.zyngui.state_manager.status_midi_recorder:
				self.list_data[0] = ("STOP_RECORDING", 0, "■ Stop MIDI Recording")
			else:
				self.list_data[0] = ("START_RECORDING", 0, "⬤ Start MIDI Recording")
			if fill:
				self.listbox.delete(0)
				self.listbox.insert(0, self.list_data[0][2])
				self.select_listbox(self.index)

	def update_status_loop(self, fill=False):
		if self.list_data:
			if zynthian_gui_config.midi_play_loop:
				self.list_data[1] = ("LOOP", 0, "\u2612 Loop Play")
				libsmf.setLoop(True)
			else:
				self.list_data[1] = ("LOOP", 0, "\u2610 Loop Play")
				libsmf.setLoop(False)
			if fill:
				self.listbox.delete(1)
				self.listbox.insert(1, self.list_data[1][2])
				self.select_listbox(self.index)

	def select_action(self, i, t='S'):
		fpath = self.list_data[i][0]

		if fpath == "START_RECORDING":
			self.zyngui.state_manager.start_midi_record()
		elif fpath == "STOP_PLAYING":
			self.zyngui.state_manager.stop_midi_playback()
		elif fpath == "STOP_RECORDING":
			self.zyngui.state_manager.stop_midi_record()
		elif fpath == "LOOP":
			self.toggle_loop()
		elif fpath:
			if t == 'S':
				self.zyngui.state_manager.toggle_midi_playback(fpath)
			else:
				self.show_smf_options()

	# Function to handle *all* switch presses.
	# swi: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	# t: Press type ["S"=Short, "B"=Bold, "L"=Long]
	# returns True if action fully handled or False if parent action should be triggered
	def switch(self, swi, t='S'):
		if swi == 0:
			if t == 'S':
				return True  # Block short layer press

	def show_smf_options(self):
		smf = self.list_data[self.index]
		smf_fname = smf[2]
		options = {}
		options["Rename"] = smf
		options["Delete"] = smf
		self.zyngui.screens['option'].config(f"MIDI file {smf_fname}", options, self.smf_options_cb)
		self.zyngui.show_screen('option')

	def show_menu(self):
		self.show_smf_options()

	def toggle_menu(self):
		if self.shown:
			self.show_menu()
		elif self.zyngui.current_screen == "option":
			self.close_screen()

	def smf_options_cb(self, option, smf):
		if option == "Rename":
			self.zyngui.show_keyboard(self.rename_smf, smf[2])
		elif option == "Delete":
			self.delete_smf(smf)

	def rename_smf(self, new_name):
		smf = self.list_data[self.index]
		new_name = new_name.strip()
		if new_name != smf[2]:
			try:
				# TODO: Confirm rename if overwriting existing file
				parts = os.path.split(smf[0])
				new_fpath = f"{parts[0]}/{new_name}.mid"
				os.rename(smf[0], new_fpath)
				self.update_list()
			except Exception as e:
				logging.error("Failed to rename MIDI file => {}".format(e))

	def delete_smf(self, smf):
		self.zyngui.show_confirm(f"Do you really want to delete '{smf[2]}'?", self.delete_smf_confirmed, smf)

	def delete_smf_confirmed(self, smf):
		logging.info("DELETE MIDI FILE: {}".format(smf[0]))
		try:
			os.remove(smf[0])
			self.update_list()
		except Exception as e:
			logging.error(f"Failed to delete MIDI file => {e}")

	def toggle_recording(self):
		self.zyngui.state_manager.toggle_midi_record()

	def show_playing_bpm(self):
		if self.bpm_zgui_ctrl:
			self.bpm_zgui_ctrl.config(self.zyngui.state_manager.zynseq.zctrl_tempo)
			self.bpm_zgui_ctrl.show()
			self.bpm_zgui_ctrl.grid()
			self.loading_canvas.grid_remove()
		else:
			if zynthian_gui_config.layout['name'] == 'Z2':
				bmp_ctrl_index = 0
			else:
				bmp_ctrl_index = 2
			self.bpm_zgui_ctrl = zynthian_gui_controller(bmp_ctrl_index, self.main_frame, self.zyngui.state_manager.zynseq.zctrl_tempo)
			self.loading_canvas.grid_remove()
			self.bpm_zgui_ctrl.grid(
				row=zynthian_gui_config.layout['ctrl_pos'][bmp_ctrl_index][0],
				column=zynthian_gui_config.layout['ctrl_pos'][bmp_ctrl_index][1],
				sticky='news'
			)
		self.zyngui.state_manager.zynseq.update_tempo()

	def hide_playing_bpm(self):
		if self.bpm_zgui_ctrl:
			self.bpm_zgui_ctrl.hide()
			self.bpm_zgui_ctrl.grid_remove()
			self.loading_canvas.grid()

	# Implement engine's method
	def send_controller_value(self, zctrl):
		if zctrl.symbol == "bpm":
			self.zyngui.state_manager.zynseq.set_tempo(zctrl.value)
			logging.debug("SET PLAYING BPM => {}".format(zctrl.value))

	def zynpot_cb(self, i ,dval):
		if not self.shown:
			return False
		
		if self.bpm_zgui_ctrl and self.bpm_zgui_ctrl.index == i:
			self.bpm_zgui_ctrl.zynpot_cb(dval)
			return True
		else:
			return super().zynpot_cb(i, dval)

	def plot_zctrls(self, force=False):
		super().plot_zctrls()
		if self.bpm_zgui_ctrl:
			if self.zyngui.state_manager.zynseq.zctrl_tempo.is_dirty or force:
				self.bpm_zgui_ctrl.calculate_plot_values()
			self.bpm_zgui_ctrl.plot_value()

	def toggle_loop(self):
		if zynthian_gui_config.midi_play_loop:
			logging.info("MIDI play loop OFF")
			zynthian_gui_config.midi_play_loop = False
		else:
			logging.info("MIDI play loop ON")
			zynthian_gui_config.midi_play_loop = True
		zynconf.save_config({"ZYNTHIAN_MIDI_PLAY_LOOP": str(int(zynthian_gui_config.midi_play_loop))})
		self.update_status_loop(True)

	# -------------------------------------------------------------------------
	# CUIA & LEDs methods
	# -------------------------------------------------------------------------

	def cuia_toggle_record(self, params=None):
		self.zyngui.state_manager.toggle_midi_record()
		return True

	def cuia_stop(self, params=None):
		self.zyngui.state_manager.stop_midi_playback()
		return True

	def cuia_toggle_play(self, params=None):
		self.zyngui.state_manager.toggle_midi_playback()
		return True

	def update_wsleds(self, leds):
		wsl = self.zyngui.wsleds
		# REC button
		if self.zyngui.state_manager.status_midi_recorder:
			wsl.set_led(leds[1], wsl.wscolor_red)
		else:
			wsl.set_led(leds[1], wsl.wscolor_alt)
		# STOP button
		wsl.set_led(leds[2], wsl.wscolor_alt)
		# PLAY button:
		if self.zyngui.state_manager.status_midi_player:
			wsl.set_led(leds[3], wsl.wscolor_green)
		else:
			wsl.set_led(leds[3], wsl.wscolor_alt)

	# -------------------------------------------------------------------------

	def set_select_path(self):
		self.select_path.set("MIDI Recorder")

# ------------------------------------------------------------------------------
