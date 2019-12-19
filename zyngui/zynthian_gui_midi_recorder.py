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
import threading
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
	jack_play_port = "ZynMidiRouter:seq_in"

	def __init__(self):
		self.capture_dir_sdc = os.environ.get('ZYNTHIAN_MY_DATA_DIR',"/zynthian/zynthian-my-data") + "/capture"
		self.capture_dir_usb = os.environ.get('ZYNTHIAN_EX_DATA_DIR',"/media/usb0")
		self.current_record = None
		self.rec_proc = None
		self.play_proc = None

		super().__init__('MIDI Recorder', True)

		self.bpm_zctrl = zynthian_controller(self, "bpm", "BPM", {
			'value': 120,
			'value_min': 10,
			'value_max': 400,
			'is_toggle': False,
			'is_integer': True
		})
		self.bpm_zgui_ctrl = None


	def get_status(self):
		status = None

		if self.rec_proc and self.rec_proc.poll() is None:
			status = "REC"

		if self.play_proc and self.play_proc.poll() is None:
			if status=="REC":
				status = "PLAY+REC"
			else:
				status = "PLAY"

		return status


	def hide(self):
		super().hide()
		if self.bpm_zgui_ctrl:
			self.bpm_zgui_ctrl.hide()


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
		else:
			self.list_data.append(("LOOP",0,"[  ] Loop Play"))

		self.list_data.append((None,0,"-----------------------------"))


		i = 1
		# Files in SD-Card
		for f in sorted(os.listdir(self.capture_dir_sdc)):
			fpath=join(self.capture_dir_sdc,f)
			if isfile(fpath) and f[-4:].lower()=='.mid':
				#title=str.replace(f[:-3], '_', ' ')
				title="SDC: {}".format(f[:-4])
				self.list_data.append((fpath,i,title))
				i+=1
		# Files on USB-Pendrive
		for f in sorted(os.listdir(self.capture_dir_usb)):
			fpath=join(self.capture_dir_usb,f)
			if isfile(fpath) and f[-4:].lower()=='.mid':
				#title=str.replace(f[:-3], '_', ' ')
				title="USB: {}".format(f[:-4])
				self.list_data.append((fpath,i,title))
				i+=1

		super().fill_list()


	def fill_listbox(self):
		super().fill_listbox()
		self.highlight()


	# Highlight command and current record played, if any ...
	def highlight(self):
		if not self.play_proc or self.play_proc.poll() is not None:
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


	def delete_confirmed(self, fpath):
		logging.info("DELETE MIDI RECORDING: {}".format(fpath))
		
		try:
			os.remove(fpath)
		except Exception as e:
			logging.error(e)

		self.zyngui.show_modal("midi_recorder")


	def start_recording(self):
		logging.info("STARTING NEW MIDI RECORD ...")
		try:
			cmd=self.sys_dir +"/sbin/jack-smf-recorder.sh --port {}".format(self.jack_record_port)
			#logging.info("COMMAND: %s" % cmd)
			self.rec_proc=Popen(cmd.split(" "), shell=True, preexec_fn=os.setpgrp)
			sleep(0.2)
		except Exception as e:
			logging.error("ERROR STARTING MIDI RECORD: %s" % e)
			self.zyngui.show_info("ERROR STARTING MIDI RECORD:\n %s" % e)
			self.zyngui.hide_info_timer(5000)

		self.update_list()


	def stop_recording(self):
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


	def toggle_recording(self):
		logging.info("TOGGLING MIDI RECORDING ...")
		if self.get_status() in ("REC", "PLAY+REC"):
			self.stop_recording()
		else:
			self.start_recording()


	def start_playing(self, fpath=None):
		if self.play_proc and self.play_proc.poll() is None:
			self.stop_playing()

		if fpath is None:
			fpath = self.get_current_track_fpath()
		
		if fpath is None:
			logging.info("No track to play!")
			return

		logging.info("STARTING MIDI PLAY '{}' ...".format(fpath))

		try:
			if zynthian_gui_config.midi_play_loop:
				cmd="/usr/local/bin/jack-smf-player -n -l -s -a \"{}\" -r 63 \"{}\"".format(self.jack_play_port, fpath)
			else:
				cmd="/usr/local/bin/jack-smf-player -n -s -a \"{}\" -r 63 \"{}\"".format(self.jack_play_port, fpath)

			logging.info("COMMAND: %s" % cmd)

			self.zyngui.zyntransport.pause()
			self.zyngui.zyntransport.locate(0)
			self.show_playing_bpm()

			def runInThread(onExit, cmd):
				self.play_proc = Popen(cmd, stdout=PIPE, stderr=STDOUT, shell=True, universal_newlines=True, preexec_fn=os.setpgrp)

				song_bpm = None
				for line in self.play_proc.stdout:
					#logging.debug("JACK-SMF-PLAYER => {}".format(line))
					if line.find("Ready to Play...")>=0:
							self.zyngui.zyntransport.play()
							self.zyngui.zyntransport.locate(0)

					elif not zynthian_gui_config.midi_play_loop and line.find("End of song.")>=0:
						os.killpg(os.getpgid(self.play_proc.pid), signal.SIGTERM)

					elif not song_bpm:
						parts = line.split("SONG BPM:")
						if len(parts)>1:
							try:
								song_bpm = int(float(parts[1].strip()))
								self.bpm_zctrl.set_value(song_bpm)
								self.bpm_zgui_ctrl.zctrl_sync()
							except Exception as e:
								logging.debug(e)

				#self.play_proc.wait()
				self.end_playing()
				return

			thread = threading.Thread(target=runInThread, args=(self.end_playing, cmd), daemon=True)
			thread.start()
			sleep(0.2)
			self.current_record=fpath

		except Exception as e:
			logging.error("ERROR STARTING MIDI PLAY: %s" % e)
			self.zyngui.show_info("ERROR STARTING MIDI PLAY:\n %s" % e)
			self.zyngui.hide_info_timer(5000)

		self.update_list()


	def end_playing(self):
		logging.info("ENDING MIDI PLAY ...")
		self.zyngui.zyntransport.pause()
		self.play_proc = None
		self.current_record=None
		self.bpm_zgui_ctrl.hide()
		self.update_list()


	def stop_playing(self):
		logging.info("STOPPING MIDI PLAY ...")
		try:
			os.killpg(os.getpgid(self.play_proc.pid), signal.SIGTERM)
			while self.play_proc:
				sleep(0.1)
		except Exception as e:
			logging.error("ERROR STOPPING MIDI PLAY: %s" % e)
			self.zyngui.show_info("ERROR STOPPING MIDI PLAY:\n %s" % e)
			self.zyngui.hide_info_timer(5000)


	def show_playing_bpm(self):
		if self.bpm_zgui_ctrl:
			self.bpm_zgui_ctrl.config(self.bpm_zctrl)
			self.bpm_zgui_ctrl.show()
		else:
			self.bpm_zgui_ctrl = zynthian_gui_controller(2, self.main_frame, self.bpm_zctrl)


	# Implement engine's method
	def send_controller_value(self, zctrl):
		if zctrl.symbol=="bpm":
			self.zyngui.zyntransport.tempo(zctrl.value)
			logging.debug("SET PLAYING BPM => {}".format(zctrl.value))


	def zyncoder_read(self):
		super().zyncoder_read()
		if self.shown and self.bpm_zgui_ctrl:
			self.bpm_zgui_ctrl.read_zyncoder()


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
