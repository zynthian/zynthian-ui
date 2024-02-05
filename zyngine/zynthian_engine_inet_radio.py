# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_inetradio)
#
# zynthian_engine implementation for internet radio streamer
#
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

from collections import OrderedDict
import logging
import json
import re
import pexpect
from threading  import Thread
from time import sleep

from . import zynthian_engine
from . import zynthian_controller
import zynautoconnect

#------------------------------------------------------------------------------
# Internet Radio Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_inet_radio(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Config variables
	# ---------------------------------------------------------------------------

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__(zyngui)
		self.name = "InternetRadio"
		self.nickname = "IR"
		self.jackname = "inetradio"
		self.type = "MIDI Synth" # TODO: Should we override this? With what value?
		self.uri = None

		self.monitors_dict = OrderedDict()
		self.monitors_dict['info'] = ""
		self.monitors_dict['audio'] = ""
		self.monitors_dict['codec'] = ""
		self.monitors_dict['bitrate'] = ""
		self.custom_gui_fpath = "/zynthian/zynthian-ui/zyngui/zynthian_widget_inet_radio.py"

		self.cmd = "mplayer -nogui -nolirc -nojoystick -quiet -slave"
		self.command_prompt = "Starting playback..."
		self.proc_timeout = 5
		self.mon_thread = None
		self.handle = 0
		
		# MIDI Controllers
		self._ctrls=[
			['volume',None,50,100],
			['stream',None,'streaming',['stopped','streaming']],
			['wait for stream',None, 5, 15]
		]

		# Controller Screens
		self._ctrl_screens=[
			['main',['volume','stream','wait for stream']]
		]

		self.reset()


	# ---------------------------------------------------------------------------
	# Subproccess Management & IPC
	# ---------------------------------------------------------------------------

	def mon_thread_task(self, handle):
		if self.proc and self.proc.isalive():
			self.proc.sendline('q')
			sleep(0.2)
		if self.proc and self.proc.isalive():
			self.proc.terminate()
			sleep(0.2)
		if self.proc and self.proc.isalive():
			self.proc.terminate(True)
			sleep(0.2)
		self.proc = None

		self.jackname = "inetradio_{}".format(handle)
		self.command = "{} -ao jack:noconnect:name={}".format(self.command, self.jackname)
		output = super().start()
		if output:
			self.monitors_dict['info'] = "no info"
			self.update_info(output)
			# Set streaming contoller value
			for processor in self.processors:
				ctrl_dict = processor.controllers_dict
				ctrl_dict['stream'].set_value('streaming', False)
			zynautoconnect.request_audio_connect(True)

			while self.handle == handle:
				sleep(1)
				try:
					self.proc.expect("\n", timeout=1)
					res = self.proc.before.decode()
					self.update_info(res)
				except pexpect.EOF:
					handle = 0
				except pexpect.TIMEOUT:
					pass
				except Exception as e:
					pass
		else:
			self.monitors_dict['info'] = "stream unavailable"

		if self.proc and self.proc.isalive():
			self.proc.sendline('q')
			sleep(0.2)
		if self.proc and self.proc.isalive():
			self.proc.terminate()
			sleep(0.2)
		if self.proc and self.proc.isalive():
			self.proc.terminate(True)
			sleep(0.2)
		self.proc = None
		# Set streaming contoller value
		for processor in self.processors:
			ctrl_dict = processor.controllers_dict
			ctrl_dict['stream'].set_value('stopped', False)



	def update_info(self, output):
		info = re.search("StreamTitle='(.+?)';", output)
		if info:
			self.monitors_dict['info'] = info.group(1)
		info = re.search("\nSelected audio codec: (.+?)\r", output)
		if info:
			self.monitors_dict['codec'] = info.group(1)
		info = re.search("\nAUDIO: (.+?)\r", output)
		if info:
			self.monitors_dict['audio'] = info.group(1)
		info = re.search("\nBitrate: (.+?)\r", output)
		if info:
			self.monitors_dict['bitrate'] = info.group(1)


	def start(self):
		self.handle += 1
		self.monitors_dict['info'] = "waiting for stream..."
		self.mon_thread = Thread(target=self.mon_thread_task, args=[self.handle])
		self.mon_thread.name = "internet radio {}".format(self.handle)
		self.mon_thread.daemon = True # thread dies with the program
		self.monitors_dict['codec'] = ""
		self.monitors_dict['audio'] = ""
		self.monitors_dict['bitrate'] = ""
		self.mon_thread.start()
		

	def stop(self):
		self.handle += 1
		self.mon_thread.join()

		self.monitors_dict['info'] = ""
		self.monitors_dict['codec'] = ""
		self.monitors_dict['audio'] = ""
		self.monitors_dict['bitrate'] = ""


	# ---------------------------------------------------------------------------
	# Processor Management
	# ---------------------------------------------------------------------------


	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------


	# ---------------------------------------------------------------------------
	# Bank Management
	# ---------------------------------------------------------------------------

	def get_bank_list(self, processor=None):
		try:
			with open(self.my_data_dir + "/presets/inet_radio/presets.json", "r") as f:
				self.presets = json.load(f)
		except:
			# Preset file missing or corrupt
			self.presets = {
				"Music": [
					["http://stream.radiotime.com/listen.m3u?streamId=10555650", 0, "FIP", "auto", ""],
					["http://icecast.radiofrance.fr/fipgroove-hifi.aac", 0, "FIP Groove", "aac", ""],
					["http://direct.fipradio.fr/live/fip-webradio4.mp3", 0, "FIP Radio 4", "auto", ""],
					["http://jazzblues.ice.infomaniak.ch/jazzblues-high.mp3", 0, "Jazz Blues", "auto", ""],
					["http://relax.stream.publicradio.org/relax.mp3", 0, "Relax", "auto", ""],
					["http://icy.unitedradio.it/VirginRock70.mp3", 0, "Virgin Rock 70's", "auto", ""],
					["https://peacefulpiano.stream.publicradio.org/peacefulpiano.aac", 0, "Peaceful Piano", "aac", ""],
					["https://chambermusic.stream.publicradio.org/chambermusic.aac", 0, "Chamber Music", "aac", ""],
					["http://sc3.radiocaroline.net:8030/listen.m3u", 0, "Radio Caroline", "auto", ""]
				],
				"Speech": [
					["http://direct.franceculture.fr/ts/franceculture-midfi.mp3", 0, "France Culture", "auto", ""],
					["http://wsdownload.bbc.co.uk/worldservice/meta/live/shoutcast/mp3/eieuk.pls", 0, "BBC Radio World Service (English)", "auto", ""]
				]
			}
		self.banks = []
		for bank in self.presets:
			self.banks.append([bank, None, bank, None])
		return self.banks

	# ---------------------------------------------------------------------------
	# Preset Management
	# ---------------------------------------------------------------------------

	def get_preset_list(self, bank):
		presets = []
		for preset in self.presets[bank[0]]:
			presets.append(preset)
		return presets


	def set_preset(self, processor, preset, preload=False):		
		if self.uri == preset[0]:
			return
		self.uri = preset[0]
		demux = preset[3]
		volume = None
		for processor in self.processors:
			try:
				ctrl_dict = processor.controllers_dict
				volume = ctrl_dict['volume'].value
				break
			except:
				pass
		if volume is None:
			volume = 50
		self.command = "{} -volume {}".format(self.cmd, volume)
		if self.uri.endswith("m3u") or self.uri.endswith("pls"):
			self.command += " -playlist"
		if demux and demux != 'auto':
			self.command += " -demuxer {}".format(demux)
		self.command += " {}".format(self.uri)
		self.start()


	#----------------------------------------------------------------------------
	# Controllers Management
	#----------------------------------------------------------------------------

	def get_controllers_dict(self, processor):
		dict = super().get_controllers_dict(processor)
		return dict


	def send_controller_value(self, zctrl):
		if zctrl.symbol == "volume":
			if self.proc:
				self.proc.sendline("volume {} 1".format(zctrl.value))
		elif zctrl.symbol == "stream":
			if zctrl.value == 0:
				self.stop()
			elif self.proc == None:
				self.start()
		elif zctrl.symbol == "wait for stream":
			self.proc_timeout = zctrl.value


	def get_monitors_dict(self):
    		return self.monitors_dict

	# ---------------------------------------------------------------------------
	# Specific functions
	# ---------------------------------------------------------------------------


	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

#******************************************************************************
