#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Base Class for WS281X LEDs Management
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
#
# ******************************************************************************
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
# ******************************************************************************

import board
import logging
import traceback
import neopixel_spi as neopixel

# Zynthian specific modules
from zyngui import zynthian_gui_config

# ---------------------------------------------------------------------------
# Zynthian GUI Base Class for WS281X LEDs Management
# ---------------------------------------------------------------------------


class zynthian_wsleds_base:

    def __init__(self, zyngui):
        self.zyngui = zyngui

        # LED strip variables
        self.spi_board = None
        self.spi_freq = 6400000
        self.num_leds = 0
        self.wsleds = None

        # LED state variables
        self.blink_count = 0
        self.blink_state = False
        self.pulse_step = 0
        self.last_wsled_state = ""
        self.brightness = 1
        self.setup_colors()

    def setup_colors(self):
        # Predefined colors
        self.wscolor_off = self.create_color(0, 0, 0)
        self.wscolor_white = self.create_color(120, 120, 120)
        self.wscolor_red = self.create_color(140, 0, 0)
        self.wscolor_green = self.create_color(0, 220, 0)
        self.wscolor_yellow = self.create_color(160, 160, 0)
        self.wscolor_orange = self.create_color(190, 80, 0)
        self.wscolor_blue = self.create_color(0, 0, 220)
        self.wscolor_blue_light = self.create_color(0, 130, 130)
        self.wscolor_purple = self.create_color(130, 0, 130)
        self.wscolor_default = self.wscolor_blue
        self.wscolor_alt = self.wscolor_purple
        self.wscolor_active = self.wscolor_green
        self.wscolor_active2 = self.wscolor_orange
        self.wscolor_admin = self.wscolor_red
        self.wscolor_low = self.create_color(0, 100, 0)
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

    def create_color(self, r, g, b):
        r = int(r * self.brightness)
        g = int(g * self.brightness)
        b = int(b * self.brightness)
        return (r << 16) | (g << 8) | b

    def create_color_from_hex(self, hexcolor):
        r = int(self.brightness * ((hexcolor >> 16) & 0xFF))
        g = int(self.brightness * ((hexcolor >> 8) & 0xFF))
        b = int(self.brightness * (hexcolor & 0xFF))
        return (r << 16) | (g << 8) | b

    def set_brightness(self, brightness):
        if brightness < 0:
            self.brightness = 0
        elif brightness > 1:
            self.brightness = 1
        else:
            self.brightness = brightness
        self.setup_colors()

    def get_brightness(self):
        return self.brightness

    def start(self):
        if self.num_leds > 0:
            try:
                self.spi_board = board.SPI()
                self.wsleds = neopixel.NeoPixel_SPI(
                    self.spi_board, self.num_leds, pixel_order=neopixel.GRB, auto_write=False, frequency=self.spi_freq)
                self.light_on_all()
            except Exception as e:
                self.wsleds = None
                logging.error(f"Can't start RGB LEDs => {e}")

    def end(self):
        self.light_off_all()

    def get_num(self):
        return self.num_leds

    def set_led(self, i, wscolor):
        self.wsleds[i] = wscolor

    def get_led(self, i):
        color = self.wsleds[i]
        return (int(color[0]) << 16) | (int(color[1]) << 8) | int(color[2])

    def light_on_all(self):
        if self.num_leds > 0:
            # Light all LEDs
            for i in range(0, self.num_leds):
                self.wsleds[i] = self.wscolor_default
            self.wsleds.show()

    def light_off_all(self):
        if self.num_leds > 0:
            # Light-off all LEDs
            for i in range(0, self.num_leds):
                self.wsleds[i] = self.wscolor_off
            self.wsleds.show()

    def blink(self, i, color):
        if self.blink_state:
            self.wsleds[i] = color
        else:
            self.wsleds[i] = self.wscolor_off

    def pulse(self, i):
        if self.blink_state:
            color = self.create_color(
                0, int(self.brightness * self.pulse_step * 6), 0)
            self.pulse_step += 1
        elif self.pulse_step > 0:
            color = self.create_color(
                0, int(self.brightness * self.pulse_step * 6), 0)
            self.pulse_step -= 1
        else:
            color = self.wscolor_off
            self.pulse_step = 0

        self.wsleds[i] = color

    def update(self):
        # Power Save Mode
        if self.zyngui.state_manager.power_save_mode:
            if self.blink_count % 64 > 44:
                self.blink_state = True
            else:
                self.blink_state = False
            for i in range(0, self.num_leds):
                self.wsleds[i] = self.wscolor_off
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
                logging.exception(traceback.format_exc())
            self.wsleds.show()

            if self.zyngui.capture_log_fname:
                try:
                    wsled_state = []
                    for i in range(self.num_leds):
                        c = str(self.get_led(i))
                        if c in self.wscolors_dict:
                            wsled_state.append(self.wscolors_dict[c])
                    wsled_state = ",".join(wsled_state)
                    if wsled_state != self.last_wsled_state:
                        self.last_wsled_state = wsled_state
                        self.zyngui.write_capture_log(
                            "LEDSTATE:" + wsled_state)
                        # logging.debug(f"Capturing LED state log => {wsled_state}")
                except Exception as e:
                    logging.error(f"Capturing LED state log => {e}")

        self.blink_count += 1

    def reset_last_state(self):
        self.last_wsled_state = ""

    def update_wsleds(self):
        pass

# ------------------------------------------------------------------------------
