# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_transport)
#
# zynthian_basic_engine implementation for Jack Transport
#
# Copyright (C) 2015-2019 Fernando Moyano <jofemodo@zynthian.org>
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

import pexpect
from . import zynthian_basic_engine

#------------------------------------------------------------------------------
# Zynthian Jack Transport Engine
#------------------------------------------------------------------------------

class zynthian_engine_transport(zynthian_basic_engine):

	def __init__(self, tempo=120):
		super().__init__("JackTransport", "/usr/local/bin/jack_transport", "jack_transport>")

		self.tempo = tempo
		self.state = 0

		self.start()
		self.proc_cmd("master")
		self.proc_cmd("stop")
		self.proc_cmd("locate 0")
		self.set_tempo(tempo)

	def __del__(self):
		self.stop()


	def stop(self):
		try:
			self.proc.sendline("quit")
			self.proc.expect(pexpect.EOF)
			self.proc = None
		except Exception as e:
			logging.error("Can't stop engine {} => {}".format(self.name, e))
			super().stop()


	# Common Transport commands

	def transport_play(self):
		self.proc_cmd("play")
		self.state = 1


	def transport_stop(self):
		self.proc_cmd("stop")
		self.state = 0


	def transport_toggle(self):
		if self.state:
			self.transport_stop()
		else:
			self.transport_play()

	def locate(self, pos_frames=0):
		self.proc_cmd("locate {}".format(pos_frames))


	def set_tempo(self, bpm):
		self.proc_cmd("tempo {}".format(bpm))


	def get_tempo(self):
		return self.tempo


	def get_state(self):
		return self.state


#******************************************************************************
