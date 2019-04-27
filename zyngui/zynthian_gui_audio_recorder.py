#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Audio Recorder Class
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
# Zynthian Audio Recorder GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_audio_recorder(zynthian_gui_selector):
	
	sys_dir = os.environ.get('ZYNTHIAN_SYS_DIR',"/zynthian/zynthian-sys")

	def __init__(self):
		self.capture_dir_sdc = os.environ.get('ZYNTHIAN_MY_DATA_DIR',"/zynthian/zynthian-my-data") + "/capture"
		self.capture_dir_usb = "/media/usb0"
		self.current_record = None
		self.rec_proc = None
		self.play_proc = None
		super().__init__('Audio Recorder', True)


	def is_process_running(self, procname):
		cmd = "ps -e | grep %s" % procname

		try:
			result = check_output(cmd, shell=True).decode('utf-8','ignore')
			if len(result)>3: return True
			else: return False

		except Exception as e:
			return False


	def get_status(self):
		if self.is_process_running("jack_capture"):
			return "REC"
		elif self.current_record:
			return "PLAY"
		else:
			return None


	def get_status(self):
		status=None

		if self.is_process_running("jack_capture"):
			status="REC"

		if self.current_record:
			if status=="REC":
				status="PLAY+REC"
			else:
				status="PLAY"

		return status


	def fill_list(self):
		self.index=0
		self.list_data=[]

		status=self.get_status()
		if status=="REC" or status=="PLAY+REC":
			self.list_data.append(("STOP_RECORDING",0,"Stop Recording"))
		else:
			self.list_data.append(("START_RECORDING",0,"Start Recording"))

		if status=="PLAY" or status=="PLAY+REC":
			self.list_data.append(("STOP_PLAYING",0,"Stop Playing"))

		self.list_data.append((None,0,"-----------------------------"))

		i=1
		# Files on SD-Card
		for f in sorted(os.listdir(self.capture_dir_sdc)):
			fpath=join(self.capture_dir_sdc,f)
			if isfile(fpath) and f[-4:].lower()=='.wav':
				#title=str.replace(f[:-3], '_', ' ')
				title="SDC: {}".format(f[:-4])
				self.list_data.append((fpath,i,title))
				i+=1
		# Files on USB-Pendrive
		for f in sorted(os.listdir(self.capture_dir_usb)):
			fpath=join(self.capture_dir_usb,f)
			if isfile(fpath) and f[-4:].lower()=='.wav':
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
		for i, row in enumerate(self.list_data):
			if row[0] is not None and row[0]==self.current_record:
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
		elif fpath:
			if t=='S':
				self.start_playing(fpath)
			else:
				self.zyngui.show_confirm("Do you really want to delete '{}'?".format(self.list_data[i][2]), self.delete_confirmed, fpath)


	def delete_confirmed(self, fpath):
		logging.info("DELETE AUDIO RECORDING: {}".format(fpath))

		try:
			os.remove(fpath)
		except Exception as e:
			logging.error(e)

		self.zyngui.show_modal("audio_recorder")


	def start_recording(self):
		logging.info("STARTING NEW AUDIO RECORD ...")
		try:
			cmd=self.sys_dir +"/sbin/jack_capture.sh --zui"
			#logging.info("COMMAND: %s" % cmd)
			self.rec_proc=Popen(cmd.split(" "), stdout=PIPE, stderr=PIPE)
			sleep(0.5)
			check_output("echo play | jack_transport", shell=True)
		except Exception as e:
			logging.error("ERROR STARTING AUDIO RECORD: %s" % e)
			self.zyngui.show_info("ERROR STARTING AUDIO RECORD:\n %s" % e)
			self.zyngui.hide_info_timer(5000)
		self.update_list()


	def stop_recording(self):
		logging.info("STOPPING AUDIO RECORD ...")
		check_output("echo stop | jack_transport", shell=True)
		self.rec_proc.communicate()
		while self.is_process_running("jack_capture"):
			sleep(1)
		self.update_list()


	def start_playing(self, fpath):
		if self.current_record:
			self.stop_playing()
		logging.info("STARTING AUDIO PLAY '{}' ...".format(fpath))
		try:
			cmd="/usr/bin/mplayer -nogui -noconsolecontrols -nolirc -nojoystick -really-quiet -slave -loop 0 -ao jack {}".format(fpath)
			logging.info("COMMAND: %s" % cmd)
			self.play_proc=Popen(cmd.split(" "), stdin=PIPE, universal_newlines=True)
			sleep(0.5)
			self.current_record=fpath
		except Exception as e:
			logging.error("ERROR STARTING AUDIO PLAY: %s" % e)
			self.zyngui.show_info("ERROR STARTING AUDIO PLAY:\n %s" % e)
			self.zyngui.hide_info_timer(5000)
		self.update_list()


	def stop_playing(self):
		logging.info("STOPPING AUDIO PLAY ...")
		try:
			self.play_proc.stdin.write("quit\n")
			self.play_proc.stdin.flush()
		except:
			pass
		self.current_record=None
		self.update_list()


	def set_select_path(self):
		self.select_path.set("Audio Recorder")

#------------------------------------------------------------------------------
