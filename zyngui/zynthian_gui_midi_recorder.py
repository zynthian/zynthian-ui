#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI MIDI Recorder Class
# 
# Copyright (C) 2015-2018 Fernando Moyano <jofemodo@zynthian.org>
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
import logging
from threading import Timer
from time import sleep
from os.path import isfile, join, basename
import ctypes

# Zynthian specific modules
import zynconf
from zyngine import zynthian_controller
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector
from zyngui.zynthian_gui_controller import zynthian_gui_controller
from zynlibs.zynseq import zynseq
from zynlibs.zynseq.zynseq import libseq
from zynlibs.zynsmf import zynsmf # Python wrapper for zynsmf (ensures initialised and wraps load() function)
from zynlibs.zynsmf.zynsmf import libsmf # Direct access to shared library 

#------------------------------------------------------------------------------
# Zynthian MIDI Recorder GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_midi_recorder(zynthian_gui_selector):

	def __init__(self):
		self.capture_dir_sdc = os.environ.get('ZYNTHIAN_MY_DATA_DIR',"/zynthian/zynthian-my-data") + "/capture"
		self.capture_dir_usb = os.environ.get('ZYNTHIAN_EX_DATA_DIR',"/media/usb0")
		self.current_playback_fpath = None # Filename of currently playing SMF

		self.smf_player = None # Pointer to SMF player
		self.smf_recorder = None # Pointer to SMF recorder
		self.smf_timer = None # 1s timer used to check end of SMF playback

		super().__init__('MIDI Recorder', True)

		self.bpm_zctrl = zynthian_controller(self, "bpm", "BPM", {
			'value': 120,
			'value_min': 20,
			'value_max': 400,
			'is_toggle': False,
			'is_integer': False,
			'nudge_factor': 0.1
		})
		self.bpm_zgui_ctrl = None

		try:
			self.smf_player = libsmf.addSmf()
			libsmf.attachPlayer(self.smf_player)
		except Exception as e:
			logging.error(e)

		try:
			self.smf_recorder = libsmf.addSmf()
			libsmf.attachRecorder(self.smf_recorder)
		except Exception as e:
			logging.error(e)

		logging.info("midi recorder created")


	def check_playback(self):
		if libsmf.getPlayState() == 0:
			self.end_playing()
		else:
			self.smf_timer = Timer(interval = 1, function=self.check_playback)
			self.smf_timer.start()


	def get_status(self):
		status = None

		if libsmf.isRecording():
			status = "REC"

		if libsmf.getPlayState():
			if status=="REC":
				status = "PLAY+REC"
			else:
				status = "PLAY"

		return status


	def show(self):
		super().show()
		if libsmf.getPlayState():
			self.show_playing_bpm()


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

		self.list_data.append((None,0,"-----------------------------"))

		# Add file list, sorted by mtime
		flist = self.get_filelist(self.capture_dir_sdc, "SD")
		flist += self.get_filelist(self.capture_dir_usb, "USB")
		i=1
		for finfo in sorted(flist, key=lambda d: d['mtime'], reverse=True) :
			self.list_data.append((finfo['fpath'], i, finfo['title']))
			i+=1

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
				title = "{}[{}:{:02d}] {}".format(src_name, int(length/60), int(length%60), fname.replace(";",">",1).replace(";","/"))

				res.append({
					'fpath': fpath,
					'fname': fname,
					'ext': fext,
					'length' : length,
					'mtime' : mtime,
					'title': title
				})

		libsmf.removeSmf(smf)
		return res


	def fill_listbox(self):
		super().fill_listbox()
		self.highlight()


	# Highlight command and current record played, if any ...
	def highlight(self):
		if libsmf.getPlayState() == 0:
			self.current_playback_fpath=None

		for i, row in enumerate(self.list_data):
			if row[0] is not None and row[0]==self.current_playback_fpath:
				self.listbox.itemconfig(i, { 'bg': zynthian_gui_config.color_hl })
			else:
				self.listbox.itemconfig(i, { 'bg': zynthian_gui_config.color_panel_bg })


	def update_status_recording(self, fill=False):
		if libsmf.isRecording():
			self.list_data[0] = ("STOP_RECORDING",0,"Stop Recording")
		else:
			self.list_data[0] = ("START_RECORDING",0,"Start Recording")
		if fill:
			super().fill_list()

	def update_status_loop(self, fill=False):
		if zynthian_gui_config.midi_play_loop:
			self.list_data[1] = ("LOOP",0,"[x] Loop Play")
			libsmf.setLoop(True)
		else:
			self.list_data[1] = ("LOOP",0,"[  ] Loop Play")
			libsmf.setLoop(False)
		if fill:
			super().fill_list()


	def select_action(self, i, t='S'):
		fpath = self.list_data[i][0]

		if fpath=="START_RECORDING":
			self.start_recording()
		elif fpath=="STOP_PLAYING":
			self.stop_playing()
		elif fpath=="STOP_RECORDING":
			self.stop_recording()
		elif fpath=="LOOP":
			self.toggle_loop()
		elif fpath:
			if t=='S':
				self.toggle_playing(fpath)
			else:
				self.zyngui.show_confirm("Do you really want to delete '{}'?".format(self.list_data[i][2]), self.delete_confirmed, fpath)


	# Function to handle *all* switch presses.
	#	swi: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	t: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def switch(self, swi, t='S'):
		if swi == 0:
			if t == 'S':
				self.zyngui.replace_screen('audio_recorder')
				return True


	def get_next_filenum(self):
		try:
			n = max(map(lambda item: int(os.path.basename(item[0])[0:3]) if item[0] and os.path.basename(item[0])[0:3].isdigit() else 0, self.list_data))
		except:
			n = 0
		return "{0:03d}".format(n+1)


	def get_new_filename(self):
		try:
			parts = self.zyngui.curlayer.get_presetpath().split('#',2)
			file_name = parts[1].replace("/",";").replace(">",";").replace(" ; ",";")
		except:
			file_name = "jack_capture"
		return self.get_next_filenum() + '-' + file_name + '.mid'


	def delete_confirmed(self, fpath):
		logging.info("DELETE MIDI RECORDING: {}".format(fpath))
		try:
			os.remove(fpath)
		except Exception as e:
			logging.error(e)


	def start_recording(self):
		if not libsmf.isRecording():
			logging.info("STARTING NEW MIDI RECORD ...")
			libsmf.unload(self.smf_recorder)
			libsmf.startRecording()
			self.update_status_recording(True)
			return True
		else:
			return False


	def stop_recording(self):
		if libsmf.isRecording():
			logging.info("STOPPING MIDI RECORDING ...")
			libsmf.stopRecording()
			if os.path.ismount(self.capture_dir_usb):
				filename = "{}/{}".format(self.capture_dir_usb, self.get_new_filename())
			else:
				filename = "{}/{}".format(self.capture_dir_sdc, self.get_new_filename())
			zynsmf.save(self.smf_recorder, filename)

			self.update_list()
			return True

		else:
			return False


	def toggle_recording(self):
		logging.info("TOGGLING MIDI RECORDING ...")
		if not self.stop_recording():
			self.start_recording()


	def start_playing(self, fpath=None):
		self.stop_playing()

		if fpath is None:
			fpath = self.get_current_track_fpath()
		
		if fpath is None:
			logging.info("No track to play!")
			return

		try:
			zynsmf.load(self.smf_player,fpath)
			tempo = libsmf.getTempo(self.smf_player, 0)
			logging.info("STARTING MIDI PLAY '{}' => {}BPM".format(fpath, tempo))
			libseq.setTempo(ctypes.c_double(tempo)) # TODO This doesn't work!!
			libsmf.startPlayback()
			zynseq.transport_start("zynsmf")
#			libseq.transportLocate(0)
			self.current_playback_fpath=fpath
			self.show_playing_bpm()
			self.smf_timer = Timer(interval = 1, function=self.check_playback)
			self.smf_timer.start()
		except Exception as e:
			logging.error("ERROR STARTING MIDI PLAY: %s" % e)
			self.zyngui.show_info("ERROR STARTING MIDI PLAY:\n %s" % e)
			self.zyngui.hide_info_timer(5000)

		#self.update_list()
		self.highlight()
		return True


	def end_playing(self):
		logging.info("ENDING MIDI PLAY ...")
		zynseq.transport_stop("zynsmf")
		if self.smf_timer:
			self.smf_timer.cancel()
			self.smf_timer = None
		self.current_playback_fpath=None
		self.hide_playing_bpm()
		#self.update_list()
		self.highlight()


	def stop_playing(self):
		if libsmf.getPlayState()!=zynsmf.PLAY_STATE_STOPPED:
			logging.info("STOPPING MIDI PLAY ...")
			libsmf.stopPlayback()
			sleep(0.1)
			self.end_playing()
			return True

		else:
			return False


	def toggle_playing(self, fpath=None):
		logging.info("TOGGLING MIDI PLAY ...")
		
		if fpath is None:
			fpath = self.get_current_track_fpath()

		if fpath and fpath!=self.current_playback_fpath:
			self.start_playing(fpath)
		else:
			self.stop_playing()


	def show_playing_bpm(self):
		self.bpm_zctrl.set_value(libseq.getTempo())
		if self.bpm_zgui_ctrl:
			self.bpm_zgui_ctrl.config(self.bpm_zctrl)
			self.bpm_zgui_ctrl.show()
		else:
			self.bpm_zgui_ctrl = zynthian_gui_controller(2, self.main_frame, self.bpm_zctrl)


	def hide_playing_bpm(self):
		if self.bpm_zgui_ctrl:
			self.bpm_zgui_ctrl.hide()


	# Implement engine's method
	def send_controller_value(self, zctrl):
		if zctrl.symbol=="bpm":
			libseq.setTempo(ctypes.c_double(zctrl.value))
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
			if self.bpm_zctrl.is_dirty or force:
				self.bpm_zgui_ctrl.calculate_plot_values()
			self.bpm_zgui_ctrl.plot_value()


	def get_current_track_fpath(self):
		if not self.list_data:
			self.fill_list()
		#if selected track ...
		if self.list_data[self.index][1]>0:
			return self.list_data[self.index][0]
		#return first track in list if there is one ...
		fti = self.get_first_track_index()
		if fti is not None:
			return self.list_data[fti][0]
		#else return None
		else:
			return None


	def get_first_track_index(self):
		for i, row in enumerate(self.list_data):
			if row[1]>0:
				return i
		return None


	def toggle_loop(self):
		if zynthian_gui_config.midi_play_loop:
			logging.info("MIDI play loop OFF")
			zynthian_gui_config.midi_play_loop=False
		else:
			logging.info("MIDI play loop ON")
			zynthian_gui_config.midi_play_loop=True
		zynconf.save_config({"ZYNTHIAN_MIDI_PLAY_LOOP": str(int(zynthian_gui_config.midi_play_loop))})
		self.update_status_loop(True)


	def set_select_path(self):
		self.select_path.set("MIDI Recorder")

#------------------------------------------------------------------------------
