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
import sys
import logging
import signal
from threading import Timer
import ctypes
from time import sleep
from os.path import isfile, isdir, join, basename
from subprocess import check_output, Popen, PIPE, STDOUT

# Zynthian specific modules
import zynconf
from . import zynthian_gui_config
from . import zynthian_gui_selector
from . import zynthian_gui_controller
from zyngine import zynthian_controller

#------------------------------------------------------------------------------
# Zynthian MIDI Recorder GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_midi_recorder(zynthian_gui_selector):
	
	sys_dir = os.environ.get('ZYNTHIAN_SYS_DIR',"/zynthian/zynthian-sys")

	jack_record_port = "ZynMidiRouter:main_out"

	def __init__(self):
		self.capture_dir_sdc = os.environ.get('ZYNTHIAN_MY_DATA_DIR',"/zynthian/zynthian-my-data") + "/capture"
		self.capture_dir_usb = os.environ.get('ZYNTHIAN_EX_DATA_DIR',"/media/usb0")
		self.current_record = None
		self.rec_proc = None
		self.libsmf = ctypes.CDLL("/zynthian/zynthian-ui/zynlibs/zynsmf/build/libzynsmf.so")
		self.libsmf.getDuration.restype = ctypes.c_double
		self.libsmf.getTempo.restype = ctypes.c_float
		self.smfplayer = None
		self.smf_timer = None

		super().__init__('MIDI Recorder', True)

		self.bpm_zctrl = zynthian_controller(self, "bpm", "BPM", {
			'value': 120,
			'value_min': 10,
			'value_max': 400,
			'is_toggle': False,
			'is_integer': True
		})
		self.bpm_zgui_ctrl = None
		logging.info("midi recorder created")


	def check_playback(self):
		if self.shown and self.libsmf.getPlayState() == 0:
			self.end_playing()
		else:
			self.smf_timer = Timer(interval = 1, function=self.check_playback)
			self.smf_timer.start()


	def get_status(self):
		status = None

		if self.rec_proc and self.rec_proc.poll() is None:
			status = "REC"

		if self.libsmf.getPlayState():
			if status=="REC":
				status = "PLAY+REC"
			else:
				status = "PLAY"

		return status

	def show(self):
		super().show()
		try:
			if self.smfplayer == None:
				self.smfplayer = self.libsmf.addSmf()
				self.libsmf.attachPlayer(self.smfplayer)
				self.zyngui.zynautoconnect()
		except:
			pass


	def hide(self):
		super().hide()
		if self.bpm_zgui_ctrl:
			self.bpm_zgui_ctrl.hide()
		if self.libsmf.getPlayState() == 0:
			self.libsmf.removePlayer()
			self.libsmf.removeSmf(self.smfplayer)
			self.smfplayer = None


	def fill_list(self):
		self.index = 0
		self.list_data = []

		status = self.get_status()
		if status=="REC" or status=="PLAY+REC":
			self.list_data.append(("STOP_RECORDING",0,"Stop Recording"))
		else:
			self.list_data.append(("START_RECORDING",0,"Start Recording"))

		if status=="PLAY" or status=="PLAY+REC":
			self.list_data.append(("STOP_PLAYING",0,"Stop Playing"))
			self.show_playing_bpm()

		if zynthian_gui_config.midi_play_loop:
			self.list_data.append(("LOOP",0,"[x] Loop Play"))
			self.libsmf.setLoop(True)
		else:
			self.list_data.append(("LOOP",0,"[  ] Loop Play"))
			self.libsmf.setLoop(False)

		self.list_data.append((None,0,"-----------------------------"))

		i=1
		# Files on SD-Card
		for fname, finfo in self.get_filelist(self.capture_dir_sdc).items():
			l = finfo['length']
			title="SD[{}:{:02d}] {}".format(int(l/60), int(l%60),fname.replace(";",">",1).replace(";","/"))
			self.list_data.append((finfo['fpath'],i,title))
			i+=1

		# Files on USB-Pendrive
		for fname, finfo in self.get_filelist(self.capture_dir_usb).items():
			l = finfo['length']
			title="USB[{}:{:02d}] {}".format(int(l/60), int(l%60),fname.replace(";",">",1).replace(";","/"))
			self.list_data.append((finfo['fpath'],i,title))
			i+=1

		super().fill_list()


	def get_filelist(self, src_dir):
		res = {}
		for f in sorted(os.listdir(src_dir)):
			fpath = join(src_dir, f)
			fname = f[:-4]
			fext = f[-4:].lower()
			if isfile(fpath) and fext in ('.mid'):
				res[fname] = {
					'fpath': fpath,
					'ext': fext
				}

		smf = self.libsmf.addSmf()
		for fname in res:
			try:
				self.libsmf.load(smf, bytes(res[fname]['fpath'], "utf-8"))
				res[fname]['length'] = self.libsmf.getDuration(smf)
			except Exception as e:
				res[fname]['length'] = 0
				logging.warning(e)
		
		self.libsmf.removeSmf(smf)

		return res


	def fill_listbox(self):
		super().fill_listbox()
		self.highlight()


	# Highlight command and current record played, if any ...
	def highlight(self):
		logging.info("Play state: %d", self.libsmf.getPlayState())
		if self.libsmf.getPlayState() == 0:
			self.current_record=None
		for i, row in enumerate(self.list_data):
			if row[0] is not None and row[0]==self.current_record:
				self.listbox.itemconfig(i, {'bg':zynthian_gui_config.color_hl})
			else:
				self.listbox.itemconfig(i, {'fg':zynthian_gui_config.color_panel_tx})


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
				self.start_playing(fpath)
			else:
				self.zyngui.show_confirm("Do you really want to delete '{}'?".format(self.list_data[i][2]), self.delete_confirmed, fpath)


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

		self.zyngui.show_modal("midi_recorder")


	def start_recording(self):
		if self.get_status() not in ("REC", "PLAY+REC"):
			logging.info("STARTING NEW MIDI RECORD ...")
			try:
				cmd = [self.sys_dir + "/sbin/jack-smf-recorder.sh", self.jack_record_port, self.get_new_filename()]
				#logging.info("COMMAND: %s" % cmd)
				self.rec_proc = Popen(cmd, preexec_fn=os.setpgrp)
				sleep(0.2)
			except Exception as e:
				logging.error("ERROR STARTING MIDI RECORD: %s" % e)
				self.zyngui.show_info("ERROR STARTING MIDI RECORD:\n %s" % e)
				self.zyngui.hide_info_timer(5000)

			self.update_list()
			return True

		else:
			return False


	def stop_recording(self):
		if self.get_status() in ("REC", "PLAY+REC"):
			logging.info("STOPPING MIDI RECORDING ...")
			try:
				os.killpg(os.getpgid(self.rec_proc.pid), signal.SIGINT)
				while self.rec_proc.poll() is None:
					sleep(0.2)
				self.rec_proc = None
			except Exception as e:
				logging.error("ERROR STOPPING MIDI RECORD: %s" % e)
				self.zyngui.show_info("ERROR STOPPING MIDI RECORD:\n %s" % e)
				self.zyngui.hide_info_timer(5000)

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

		logging.info("STARTING MIDI PLAY '{}' ...".format(fpath))

		try:
			self.libsmf.load(self.smfplayer, bytes(fpath, "utf-8"))
			self.zyngui.libseq.setTempo(int(self.libsmf.getTempo(self.smfplayer, 0))) #TODO: This isn't working
			self.libsmf.startPlayback()
			self.zyngui.libseq.transportStart(bytes("midi_rec","utf-8"))
			self.zyngui.libseq.transportLocate(0)
			self.show_playing_bpm()
			self.current_record=fpath
			self.smf_timer = Timer(interval = 1, function=self.check_playback)
			self.smf_timer.start()
		except Exception as e:
			logging.error("ERROR STARTING MIDI PLAY: %s" % e)
			self.zyngui.show_info("ERROR STARTING MIDI PLAY:\n %s" % e)
			self.zyngui.hide_info_timer(5000)

		self.update_list()
		return True


	def end_playing(self):
		logging.info("ENDING MIDI PLAY ...")
		self.zyngui.libseq.transportStop(bytes("midi_rec","utf-8"))
		if self.smf_timer:
			self.smf_timer.cancel()
			self.smf_timer = None
		self.current_record=None
		self.bpm_zgui_ctrl.hide()
		self.update_list()


	def stop_playing(self):
		if self.get_status() in ("PLAY", "PLAY+REC"):
			logging.info("STOPPING MIDI PLAY ...")
			try:
				self.libsmf.stopPlayback()
				sleep(0.1)
				self.end_playing()
			except Exception as e:
				logging.error("ERROR STOPPING MIDI PLAY: %s" % e)
				self.zyngui.show_info("ERROR STOPPING MIDI PLAY:\n %s" % e)
				self.zyngui.hide_info_timer(5000)
			return True

		else:
			return False


	def toggle_playing(self):
		logging.info("TOGGLING MIDI PLAY ...")
		if not self.stop_playing():
			self.start_playing()


	def show_playing_bpm(self):
		if self.bpm_zgui_ctrl:
			self.bpm_zgui_ctrl.config(self.bpm_zctrl)
			self.bpm_zgui_ctrl.show()
		else:
			self.bpm_zgui_ctrl = zynthian_gui_controller(2, self.main_frame, self.bpm_zctrl)


	# Implement engine's method
	def send_controller_value(self, zctrl):
		if zctrl.symbol=="bpm":
			self.zyngui.libseq.setTempo(zctrl.value)
			logging.debug("SET PLAYING BPM => {}".format(zctrl.value))


	def zyncoder_read(self):
		super().zyncoder_read()
		if self.shown and self.bpm_zgui_ctrl:
			self.bpm_zgui_ctrl.read_zyncoder()
		return [0,1]


	def plot_zctrls(self):
		super().plot_zctrls()
		if self.bpm_zgui_ctrl:
			self.bpm_zgui_ctrl.plot_value()


	def get_current_track_fpath(self):
		if not self.list_data:
			self.fill_list()
		#if selected track ...
		if self.list_data[self.index][1]>0:
			return self.list_data[self.index][0]
		#return last track if there is one ...
		elif self.list_data[-1][1]>0:
			return self.list_data[-1][0]
		#else return None
		else:
			return None


	def toggle_loop(self):
		if zynthian_gui_config.midi_play_loop:
			logging.info("MIDI play loop OFF")
			zynthian_gui_config.midi_play_loop=False
		else:
			logging.info("MIDI play loop ON")
			zynthian_gui_config.midi_play_loop=True
		zynconf.save_config({"ZYNTHIAN_MIDI_PLAY_LOOP": str(int(zynthian_gui_config.midi_play_loop))})
		self.update_list()


	def set_select_path(self):
		self.select_path.set("MIDI Recorder")

#------------------------------------------------------------------------------
