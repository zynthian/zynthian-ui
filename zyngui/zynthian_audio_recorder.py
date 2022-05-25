#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Core
# 
# Zynthian Audio Recorder Class
# 
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
# Copyright (C) 2022 Brian Walton <riban@zynthian.org>
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
from subprocess import Popen
from datetime import datetime

# Zynthian specific modules
from zyngui import zynthian_gui_config

#------------------------------------------------------------------------------
# Zynthian Audio Recorder Class
#------------------------------------------------------------------------------

class zynthian_audio_recorder():


	def __init__(self):
		self.capture_dir_sdc = os.environ.get('ZYNTHIAN_MY_DATA_DIR',"/zynthian/zynthian-my-data") + "/capture"
		self.capture_dir_usb = os.environ.get('ZYNTHIAN_EX_DATA_DIR',"/media/usb0")
		self.rec_proc = None
		self.primed = set() # List of chains primed to record
		self.zyngui = zynthian_gui_config.zyngui
		self.filename = None


	def get_status(self):
		#TODO: This could provide different status now that playback has been removed
		if self.rec_proc:
			return "REC"
		return None


	def get_new_filename(self):
		if os.path.ismount(self.capture_dir_usb):
			path = self.capture_dir_usb
		else:
			path = self.capture_dir_sdc
		try:
			self.zyngui.get_snapshot_name() #TODO: Implement get_snapshot_name()
		except:
			filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
		filename = filename.replace("/",";").replace(">",";").replace(" ; ",";")
		# Append index to file to make unique
		index = 1
		files = os.listdir(path)
		while "{}.{:03d}.wav".format(filename, index) in files:
			index += 1
		return "{}/{}.{:03d}.wav".format(path, filename, index)


	def prime(self, channel):
		self.primed.add(channel)


	def unprime(self, channel):
		try:
			self.primed.remove(channel)
		except:
			logging.info("Channel %d not primed", channel)


	def toggle_prime(self, channel):
		if self.is_primed(channel):
			self.unprime(channel)
		else:
			self.prime(channel)


	def is_primed(self, channel):
		return channel in self.primed


	def start_recording(self):
		if self.rec_proc:
			# Already recording
			return False

		cmd = ["/usr/local/bin/jack_capture", "--daemon"]
		for port in sorted(self.primed):
			cmd.append("--port")
			if port == 256:
				cmd.append("zynmixer:output_a")
			else:
				cmd.append("zynmixer:input_{:02d}a".format(port + 1))
			cmd.append("--port")
			if port == 256:
				cmd.append("zynmixer:output_b")
			else:
				cmd.append("zynmixer:input_{:02d}b".format(port + 1))

		self.filename = self.get_new_filename()
		cmd.append(self.filename)

		logging.info("STARTING NEW AUDIO RECORD ...")
		try:
			self.rec_proc = Popen(cmd)
		except Exception as e:
			logging.error("ERROR STARTING AUDIO RECORD: %s" % e)
			self.proc = None
			return False

		self.zyngui.status_info['audio_recorder'] = "REC"
		return True


	def stop_recording(self):
		if self.rec_proc:
			logging.info("STOPPING AUDIO RECORD ...")
			try:
				self.rec_proc.terminate()
				self.rec_proc = None
			except Exception as e:
				logging.error("ERROR STOPPING AUDIO RECORD: %s" % e)
				return False
			if 'audio_recorder' in self.zyngui.status_info:
				self.zyngui.status_info.pop('audio_recorder')
			return True

		return False


	def toggle_recording(self):
		logging.info("TOGGLING AUDIO RECORDING ...")
		if self.get_status():
			self.stop_recording()
		else:
			self.start_recording()


#------------------------------------------------------------------------------
