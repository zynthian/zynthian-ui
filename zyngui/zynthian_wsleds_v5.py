#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian WSLeds Class for V5
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
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

# Zynthian specific modules
from zyngui.zynthian_wsleds_base import zynthian_wsleds_base
from zyngui import zynthian_gui_config
from zynlibs.zynseq import zynseq

# ---------------------------------------------------------------------------
# Zynthian WSLeds class for Z2
# ---------------------------------------------------------------------------
class zynthian_wsleds_v5(zynthian_wsleds_base):
	
	def __init__(self, zyngui):
		super().__init__(zyngui)
		# LEDS with SPI0 (pin 10, channel 0)
		self.dma = 10
		self.pin = 10
		self.chan = 0
		self.num_leds = 20


	def update_wsleds(self):
		curscreen = self.zyngui.current_screen

		if self.zyngui.alt_mode:
			wscolor_light = self.wscolor_alt
		else:
			wscolor_light = self.wscolor_light

		# Menu / Admin
		if curscreen == "main":
			self.wsleds.setPixelColor(0, self.wscolor_active)
		elif curscreen == "stepseq" and self.zyngui.screens['stepseq'].is_shown_menu():
			self.wsleds.setPixelColor(0, self.wscolor_active)
		elif curscreen == "admin":
			self.wsleds.setPixelColor(0, self.wscolor_admin)
		else:
			self.wsleds.setPixelColor(0, wscolor_light)

		# Audio Mixer / ALSA Mixer
		if curscreen == "audio_mixer":
			self.wsleds.setPixelColor(1, self.wscolor_active)
		elif curscreen == "alsa_mixer":
			self.wsleds.setPixelColor(1, self.wscolor_admin)
		else:
			self.wsleds.setPixelColor(1, wscolor_light)

		# Control / Preset Screen:
		if curscreen == "control":
			self.wsleds.setPixelColor(2, self.wscolor_active)
		elif curscreen in ("preset", "bank"):
			self.wsleds.setPixelColor(2, self.wscolor_admin)
		else:
			self.wsleds.setPixelColor(2, wscolor_light)

		# ZS3 / Snapshot:
		if curscreen == "zs3_learn":
			self.wsleds.setPixelColor(3, self.wscolor_active)
		elif curscreen == "snapshot":
			self.wsleds.setPixelColor(3, self.wscolor_admin)
		else:
			self.wsleds.setPixelColor(3, wscolor_light)

		# F1 button
		self.wsleds.setPixelColor(4, wscolor_light)

		# Zynseq: Zynpad /Pattern Editor
		if curscreen == "zynpad":
			self.wsleds.setPixelColor(5, self.wscolor_active)
		elif curscreen == "pattern_editor":
			self.wsleds.setPixelColor(5, self.wscolor_admin)
		else:
			self.wsleds.setPixelColor(5, wscolor_light)

		# Tempo Screen
		if curscreen == "tempo":
			self.wsleds.setPixelColor(6, self.wscolor_active)
		else:
			self.wsleds.setPixelColor(6, wscolor_light)

		# ALT button:
		self.wsleds.setPixelColor(7, wscolor_light)


		# REC button:
		if 'audio_recorder' in self.zyngui.status_info:
			self.wsleds.setPixelColor(8, self.wscolor_red)
		elif self.zyngui.status_info['midi_recorder'] and "REC" in self.zyngui.status_info['midi_recorder']:
			self.wsleds.setPixelColor(8, self.wscolor_blue)
		else:
			self.wsleds.setPixelColor(8, wscolor_light)

		# STOP button
		self.wsleds.setPixelColor(9, wscolor_light)

		# PLAY button:
		if curscreen == "pattern_editor":
			pb_status = self.zyngui.screens['pattern_editor'].get_playback_status()
			if pb_status == zynseq.SEQ_PLAYING:
				self.wsleds.setPixelColor(10, self.wscolor_green)
			elif pb_status in (zynseq.SEQ_STARTING, zynseq.SEQ_RESTARTING):
				self.wsleds.setPixelColor(10, self.wscolor_yellow)
			elif pb_status in (zynseq.SEQ_STOPPING, zynseq.SEQ_STOPPINGSYNC):
				self.wsleds.setPixelColor(10, self.wscolor_red)
			elif pb_status == zynseq.SEQ_STOPPED:
				self.wsleds.setPixelColor(10, wscolor_light)
		elif 'audio_player' in self.zyngui.status_info:
			self.wsleds.setPixelColor(10, self.wscolor_active)
		elif self.zyngui.status_info['midi_recorder'] and "PLAY" in self.zyngui.status_info['midi_recorder']:
			self.wsleds.setPixelColor(10, self.wscolor_blue)
		elif curscreen == "midi_recorder":
			self.wsleds.setPixelColor(10, self.wscolor_active)
		else:
			self.wsleds.setPixelColor(10, wscolor_light)

		# F2 button
		self.wsleds.setPixelColor(11, wscolor_light)

		# F3 button
		self.wsleds.setPixelColor(12, wscolor_light)

		# Select/Yes button
		self.wsleds.setPixelColor(13, self.wscolor_green)

		# Up button
		self.wsleds.setPixelColor(14, self.wscolor_yellow)

		# Back/No button
		self.wsleds.setPixelColor(15, self.wscolor_red)

		# Left, Bottom, Right button
		self.wsleds.setPixelColor(16, self.wscolor_yellow)
		self.wsleds.setPixelColor(17, self.wscolor_yellow)
		self.wsleds.setPixelColor(18, self.wscolor_yellow)

		# F4 button
		self.wsleds.setPixelColor(19, wscolor_light)

		try:
			self.screens[curscreen].update_wsleds()
		except:
			pass

#------------------------------------------------------------------------------
