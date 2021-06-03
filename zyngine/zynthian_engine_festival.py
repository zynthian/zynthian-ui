# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_festival)
#
# zynthian_basic_engine implementation for Festival Speech Synthesizer
#
# Copyright (C) 2015-2021 Fernando Moyano <jofemodo@zynthian.org>
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

import re
import pexpect
import logging
import threading
from time import sleep
from . import zynthian_basic_engine

#------------------------------------------------------------------------------
# Zynthian Festival Engine
#------------------------------------------------------------------------------

class zynthian_engine_festival(zynthian_basic_engine):

	def __init__(self, voice=None):
		super().__init__("Festival", "/usr/bin/festival", "festival>")

		self.txt_counter_re = re.compile("[a-z0-9]",re.IGNORECASE)
		self.txt_buffer = ""
		self.txt_to_say = ""
		self.speaking_flag = False

		self.start()

		if voice:
			self.set_voice(voice)

		self.start_speaker()


	def __del__(self):
		self.stop_speaker()
		self.stop()


	# Festival commands

	def say_text(self, text, wait=False):
		n = len(re.findall(self.txt_counter_re, text))
		if n>2:
			if self.speaking_flag and not wait:
				self.proc.sendcontrol("c")
			self.txt_buffer = text


	def cancel_cmd(self):
		self.proc.sendcontrol("c")


	def set_voice(self, voice):
		self.voice = voice
		self.proc_cmd("(voice_{})".format(voice))


	# Speaker Thread
	def start_speaker(self):

		def runInThread():
			while self.speaker_enabled:
				sleep(0.1)
				if self.txt_buffer:
					self.txt_to_say = self.txt_buffer
					sleep(0.2)
					if self.txt_to_say == self.txt_buffer:
						self.speaking_flag = True
						logging.debug("SayText \"{}\"".format(self.txt_to_say))
						self.proc.sendline("(SayText \"{}\")".format(self.txt_to_say))
						self.proc_get_output()	
						self.speaking_flag = False
						if self.txt_to_say == self.txt_buffer:
							self.txt_buffer = ""

		self.speaker_enabled = True
		thread = threading.Thread(target=runInThread, daemon=True)
		thread.start()


	def stop_speaker(self):
		self.speaker_enabled = False


#******************************************************************************
