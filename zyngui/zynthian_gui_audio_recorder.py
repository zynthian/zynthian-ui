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
# Zynthian MIDI Channel Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_audio_recorder(zynthian_gui_selector):
	
	sys_dir = os.environ.get('ZYNTHIAN_SYS_DIR',"/zynthian/zynthian-sys")

	def __init__(self):
		self.audio_record_dir=os.environ.get('ZYNTHIAN_MY_DATA_DIR',"/zynthian/zynthian-my-data") + "/capture"
		self.current_audio_record=None
		self.rec_proc=None
		self.play_proc=None
		super().__init__('Audio Recorder', True)


	def is_process_running(self, procname):
		cmd="ps -e | grep %s" % procname
		try:
			result=check_output(cmd, shell=True).decode('utf-8','ignore')
			if len(result)>3: return True
			else: return False
		except Exception as e:
			return False


	def get_audio_record_fpath(self,f):
		return join(self.audio_record_dir,f);


	def fill_list(self):
		self.index=0
		self.list_data=[]
		if self.is_process_running("jack_capture"):
			self.list_data.append(("STOP_AUDIO_RECORD",0,"Stop Audio Record"))
		elif self.current_audio_record:
			self.list_data.append(("STOP_AUDIO_PLAY",0,"Stop Audio Play"))
		else:
			self.list_data.append(("START_AUDIO_RECORD",0,"Start Audio Record"))
		i=1
		for f in sorted(os.listdir(self.audio_record_dir)):
			fpath=self.get_audio_record_fpath(f)
			if isfile(fpath) and f[-4:].lower()=='.wav':
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
		for i, row in enumerate(self.list_data):
			if row[0]==self.current_audio_record:
				self.listbox.itemconfig(i, {'bg':zynthian_gui_config.color_hl})
			else:
				self.listbox.itemconfig(i, {'fg':zynthian_gui_config.color_panel_tx})


	def select_action(self, i):

		fpath=self.list_data[i][0]
		if fpath=="START_AUDIO_RECORD":
			self.start_audio_record()
		elif fpath=="STOP_AUDIO_PLAY":
			self.stop_audio_play()
		elif fpath=="STOP_AUDIO_RECORD":
			self.stop_audio_record()
		else:
			self.start_audio_play(fpath)

		#zynthian_gui_config.zyngui.show_active_screen()


	def start_audio_record(self):
		logging.info("STARTING NEW AUDIO RECORD ...")
		try:
			cmd=self.sys_dir +"/sbin/jack_capture.sh --zui"
			#logging.info("COMMAND: %s" % cmd)
			self.rec_proc=Popen(cmd.split(" "), stdout=PIPE, stderr=PIPE)
			sleep(0.5)
			check_output("echo play | jack_transport", shell=True)
		except Exception as e:
			logging.error("ERROR STARTING AUDIO RECORD: %s" % e)
			zynthian_gui_config.zyngui.show_info("ERROR STARTING AUDIO RECORD:\n %s" % e)
			zynthian_gui_config.zyngui.hide_info_timer(5000)
		self.fill_list()


	def stop_audio_record(self):
		logging.info("STOPPING AUDIO RECORD ...")
		check_output("echo stop | jack_transport", shell=True)
		self.rec_proc.communicate()
		while self.is_process_running("jack_capture"):
			sleep(1)
		self.show()


	def start_audio_play(self, fpath):
		if self.current_audio_record:
			self.stop_audio_play()
		logging.info("PLAY AUDIO PLAY '{}' ...".format(fpath))
		try:
			cmd="/usr/bin/mplayer -nogui -noconsolecontrols -nolirc -nojoystick -really-quiet -slave -ao jack {}".format(fpath)
			logging.info("COMMAND: %s" % cmd)
			self.play_proc=Popen(cmd.split(" "), stdin=PIPE, universal_newlines=True)
			sleep(0.5)
			self.current_audio_record=fpath
		except Exception as e:
			logging.error("ERROR STARTING AUDIO PLAY: %s" % e)
			zynthian_gui_config.zyngui.show_info("ERROR STARTING AUDIO RECORD:\n %s" % e)
			zynthian_gui_config.zyngui.hide_info_timer(5000)
		self.fill_list()


	def stop_audio_play(self):
		logging.info("STOP AUDIO PLAY ...")
		try:
			self.play_proc.stdin.write("quit\n")
			self.play_proc.stdin.flush()
		except:
			pass
		self.current_audio_record=None
		self.fill_list()


	def set_select_path(self):
		self.select_path.set("Audio Recorder")

#------------------------------------------------------------------------------
