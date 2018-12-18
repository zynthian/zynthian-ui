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
from time import sleep
from os.path import isfile, isdir, join, basename
from subprocess import check_output, Popen, PIPE

# Zynthian specific modules
import zynconf
from . import zynthian_gui_config
from . import zynthian_gui_selector

#------------------------------------------------------------------------------
# Configure logging
#------------------------------------------------------------------------------

# Set root logging level
logging.basicConfig(stream=sys.stderr, level=zynthian_gui_config.log_level)

#------------------------------------------------------------------------------
# Zynthian MIDI Recorder GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_midi_recorder(zynthian_gui_selector):
	
	sys_dir = os.environ.get('ZYNTHIAN_SYS_DIR',"/zynthian/zynthian-sys")

	jack_record_port = "ZynMidiRouter:main_out"
	jack_play_port = "ZynMidiRouter:seq_in"

	def __init__(self):
		self.capture_dir=os.environ.get('ZYNTHIAN_MY_DATA_DIR',"/zynthian/zynthian-my-data") + "/capture"
		self.current_record=None
		self.rec_proc=None
		self.play_proc=None
		super().__init__('MIDI Recorder', True)


	def is_process_running(self, procname):
		cmd="ps -e | grep %s" % procname
		try:
			result=check_output(cmd, shell=True).decode('utf-8','ignore')
			if len(result)>3: return True
			else: return False
		except Exception as e:
			return False


	def get_record_fpath(self,f):
		return join(self.capture_dir,f);


	def fill_list(self):
		self.index=0
		self.list_data=[]
		if self.rec_proc and self.rec_proc.poll() is None:
			self.list_data.append(("STOP_RECORDING",0,"Stop Recording"))
		elif self.play_proc and self.play_proc.poll() is None:
			self.list_data.append(("STOP_PLAYING",0,"Stop Playing"))
		else:
			self.list_data.append(("START_RECORDING",0,"Start Recording"))
		i=1
		for f in sorted(os.listdir(self.capture_dir)):
			fpath=self.get_record_fpath(f)
			if isfile(fpath) and f[-4:].lower()=='.mid':
				#title=str.replace(f[:-3], '_', ' ')
				title=f[:-4]
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
			if row[0]==self.current_record:
				self.listbox.itemconfig(i, {'bg':zynthian_gui_config.color_hl})
			else:
				self.listbox.itemconfig(i, {'fg':zynthian_gui_config.color_panel_tx})


	def select_action(self, i, t='S'):
		fpath=self.list_data[i][0]
		if fpath=="START_RECORDING":
			self.start_recording()
		elif fpath=="STOP_PLAYING":
			self.stop_playing()
		elif fpath=="STOP_RECORDING":
			self.stop_recording()
		else:
			self.start_playing(fpath)

		#self.zyngui.show_active_screen()


	def start_recording(self):
		logging.info("STARTING NEW MIDI RECORD ...")
		try:
			cmd=self.sys_dir +"/sbin/jack-smf-recorder.sh --port {}".format(self.jack_record_port)
			#logging.info("COMMAND: %s" % cmd)
			self.rec_proc=Popen(cmd.split(" "), shell=True, preexec_fn=os.setpgrp)
			sleep(0.5)
		except Exception as e:
			logging.error("ERROR STARTING MIDI RECORD: %s" % e)
			self.zyngui.show_info("ERROR STARTING MIDI RECORD:\n %s" % e)
			self.zyngui.hide_info_timer(5000)
		self.fill_list()


	def stop_recording(self):
		logging.info("STOPPING MIDI RECORD ...")
		self.rec_proc.terminate()
		os.killpg(os.getpgid(self.rec_proc.pid), signal.SIGINT)
		while self.rec_proc.poll() is None:
			sleep(1)
		self.show()


	def start_playing(self, fpath):
		if self.play_proc and self.play_proc.poll() is None:
			self.stop_playing()
		logging.info("STARTING MIDI PLAY '{}' ...".format(fpath))
		try:
			cmd="/usr/local/bin/jack-smf-player -t -s -a {} {}".format(self.jack_play_port, fpath)
			logging.info("COMMAND: %s" % cmd)
			self.play_proc=Popen(cmd.split(" "))
			sleep(0.5)
			self.current_record=fpath
		except Exception as e:
			logging.error("ERROR STARTING MIDI PLAY: %s" % e)
			self.zyngui.show_info("ERROR STARTING MIDI PLAY:\n %s" % e)
			self.zyngui.hide_info_timer(5000)
		self.fill_list()


	def stop_playing(self):
		logging.info("STOPPING MIDI PLAY ...")
		try:
			self.play_proc.terminate()
			sleep(0.5)
		except:
			pass
		self.current_record=None
		self.fill_list()


	def set_select_path(self):
		self.select_path.set("MIDI Recorder")

#------------------------------------------------------------------------------
