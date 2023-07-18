#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Base Class for WS281X LEDs Management
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

import logging
import rpi_ws281x

# Zynthian specific modules
from zyngui import zynthian_gui_config

# ---------------------------------------------------------------------------
# Zynthian GUI Base Class for WS281X LEDs Management
# ---------------------------------------------------------------------------
class zynthian_wsleds_base:
	
	def __init__(self, zyngui):
		self.zyngui = zyngui
		# LED strip variables
		self.dma = None
		self.pin = None
		self.chan = None
		self.wsleds = None
		self.num_leds = 0
		self.blink_count = 0
		self.blink_state = False
		self.pulse_step = 0
		self.last_wsled_state = ""
		# Predefined colors
		self.wscolor_off = rpi_ws281x.Color(0, 0, 0)
		self.wscolor_white = rpi_ws281x.Color(120, 120, 120)
		self.wscolor_red = rpi_ws281x.Color(140, 0, 0)
		self.wscolor_green = rpi_ws281x.Color(0, 220, 0)
		self.wscolor_yellow = rpi_ws281x.Color(160, 160, 0)
		self.wscolor_orange = rpi_ws281x.Color(190, 80, 0)
		self.wscolor_blue = rpi_ws281x.Color(0, 0, 220)
		self.wscolor_blue_light = rpi_ws281x.Color(0, 130, 130)
		self.wscolor_purple = rpi_ws281x.Color(130, 0, 130)
		self.wscolor_default = self.wscolor_blue
		self.wscolor_alt = self.wscolor_purple
		self.wscolor_active = self.wscolor_green
		self.wscolor_active2 = self.wscolor_orange
		self.wscolor_admin = self.wscolor_red
		self.wscolor_low = rpi_ws281x.Color(0, 100, 0)
		# Color Codes
		self.wscolors_dict = {
			str(self.wscolor_off): "0",
			str(self.wscolor_blue): "B",
			str(self.wscolor_green): "G",
			str(self.wscolor_red): "R",
			str(self.wscolor_orange): "O",
			str(self.wscolor_yellow): "Y",
			str(self.wscolor_purple): "P"
		}


	def start(self):
		if self.num_leds > 0 and self.pin is not None:
			self.wsleds = rpi_ws281x.PixelStrip(self.num_leds, self.pin, dma=self.dma, channel=self.chan,
												strip_type=rpi_ws281x.ws.WS2811_STRIP_GRB)
			self.wsleds.begin()
			self.light_on_all()


	def end(self):
		self.light_off_all()


	def get_num(self):
		return self.num_leds


	def setPixelColor(self, i , wscolor):
		self.wsleds.setPixelColor(i, wscolor)


	def light_on_all(self):
		if self.num_leds > 0:
			# Light all LEDs
			for i in range(0, self.num_leds):
				self.wsleds.setPixelColor(i, self.wscolor_default)
			self.wsleds.show()


	def light_off_all(self):
		if self.num_leds > 0:
			# Light-off all LEDs
			for i in range(0, self.num_leds):
				self.wsleds.setPixelColor(i, self.wscolor_off)
			self.wsleds.show()


	def blink(self, i, color):
		if self.blink_state:
			self.wsleds.setPixelColor(i, color)
		else:
			self.wsleds.setPixelColor(i, self.wscolor_off)


	def pulse(self, i):
		if self.blink_state:
			color = rpi_ws281x.Color(0, self.pulse_step * 6, 0)
			self.pulse_step += 1
		elif self.pulse_step > 0:
			color = rpi_ws281x.Color(0, self.pulse_step * 6, 0)
			self.pulse_step -= 1
		else:
			color = self.wscolor_off
			self.pulse_step = 0

		self.wsleds.setPixelColor(i, color)

	def update(self):
		# Power Save Mode
		if self.zyngui.power_save_mode:
			if self.blink_count % 64 > 44:
				self.blink_state = True
			else:
				self.blink_state = False
			for i in range(0, self.num_leds):
				self.wsleds.setPixelColor(i, self.wscolor_off)
			self.pulse(0)
			self.wsleds.show()

		# Normal mode
		else:
			if self.blink_count % 4 > 1:
				self.blink_state = True
			else:
				self.blink_state = False

			try:
				self.update_wsleds()
			except Exception as e:
				logging.error(e)

			self.wsleds.show()

			if self.zyngui.capture_log_fname:
				try:
					wsled_state = []
					for i in range(self.num_leds):
						c = str(self.wsleds.getPixelColor(i))
						if c in self.wscolors_dict:
							wsled_state.append(self.wscolors_dict[c])
					wsled_state = ",".join(wsled_state)
					if wsled_state != self.last_wsled_state:
						self.last_wsled_state = wsled_state
						self.zyngui.write_capture_log("LEDSTATE:" + wsled_state)
				except Exception as e:
					logging.error(e)

		self.blink_count += 1

	def update_wsleds(self):
		pass


#------------------------------------------------------------------------------
