#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Main Class and Program for Zynthian GUI
#
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
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

import sys
import copy
import liblo
import ctypes
import signal
import logging
import importlib
import rpi_ws281x
from time import sleep
from pathlib import Path
from time import monotonic
from datetime import datetime
from threading  import Thread, Lock
from subprocess import check_output

# Zynthian specific modules
import zynconf
from zyngine import zynthian_state_manager
from zyncoder.zyncore import get_lib_zyncore
from zynlibs.zynseq import *

from zyngine.zynthian_chain import *

from zyngui import zynthian_gui_config
from zyngui import zynthian_gui_keyboard
from zyngui.zynthian_gui_base import zynthian_gui_base
from zyngui.zynthian_gui_info import zynthian_gui_info
from zyngui.zynthian_gui_splash import zynthian_gui_splash
from zyngui.zynthian_gui_option import zynthian_gui_option
from zyngui.zynthian_gui_admin import zynthian_gui_admin
from zyngui.zynthian_gui_snapshot import zynthian_gui_snapshot
from zyngui.zynthian_gui_chain_options import zynthian_gui_chain_options
from zyngui.zynthian_gui_processor_options import zynthian_gui_processor_options
from zyngui.zynthian_gui_engine import zynthian_gui_engine
from zyngui.zynthian_gui_midi_chan import zynthian_gui_midi_chan
from zyngui.zynthian_gui_midi_cc import zynthian_gui_midi_cc
from zyngui.zynthian_gui_midi_prog import zynthian_gui_midi_prog
from zyngui.zynthian_gui_midi_key_range import zynthian_gui_midi_key_range
from zyngui.zynthian_gui_audio_out import zynthian_gui_audio_out
from zyngui.zynthian_gui_midi_out import zynthian_gui_midi_out
from zyngui.zynthian_gui_audio_in import zynthian_gui_audio_in
from zyngui.zynthian_gui_bank import zynthian_gui_bank
from zyngui.zynthian_gui_preset import zynthian_gui_preset
from zyngui.zynthian_gui_control import zynthian_gui_control
from zyngui.zynthian_gui_control_xy import zynthian_gui_control_xy
from zyngui.zynthian_gui_midi_profile import zynthian_gui_midi_profile
from zyngui.zynthian_gui_zs3_learn import zynthian_gui_zs3_learn
from zyngui.zynthian_gui_zs3_options import zynthian_gui_zs3_options
from zyngui.zynthian_gui_confirm import zynthian_gui_confirm
from zyngui.zynthian_gui_keybinding import zynthian_gui_keybinding
from zyngui.zynthian_gui_main import zynthian_gui_main
from zyngui.zynthian_gui_midi_recorder import zynthian_gui_midi_recorder
from zyngui.zynthian_gui_zynpad import zynthian_gui_zynpad
from zyngui.zynthian_gui_arranger import zynthian_gui_arranger
from zyngui.zynthian_gui_patterneditor import zynthian_gui_patterneditor
from zyngui.zynthian_gui_mixer import zynthian_gui_mixer
from zyngui.zynthian_gui_touchscreen_calibration import zynthian_gui_touchscreen_calibration
from zyngui.zynthian_gui_control_test import zynthian_gui_control_test

MIXER_MAIN_CHANNEL = 256 #TODO This constant should go somewhere else

#-------------------------------------------------------------------------------
# Zynthian Main GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui:

	SCREEN_HMODE_NONE = 0
	SCREEN_HMODE_ADD = 1
	SCREEN_HMODE_REPLACE = 2
	SCREEN_HMODE_RESET = 3

	note2cuia = {
		"0": "POWER_OFF",
		"1": "REBOOT",
		"2": "RESTART_UI",
		"3": "RELOAD_MIDI_CONFIG",
		"4": "RELOAD_KEY_BINDING",
		"5": "LAST_STATE_ACTION",
		"6": "EXIT_UI",

		"10": "ALL_NOTES_OFF",
		"11": "ALL_SOUNDS_OFF",
		"12": "ALL_OFF",

		"23": "TOGGLE_AUDIO_RECORD",
		"24": "START_AUDIO_RECORD",
		"25": "STOP_AUDIO_RECORD",
		"26": "TOGGLE_AUDIO_PLAY",
		"27": "START_AUDIO_PLAY",
		"28": "STOP_AUDIO_PLAY",

		"35": "TOGGLE_MIDI_RECORD",
		"36": "START_MIDI_RECORD",
		"37": "STOP_MIDI_RECORD",
		"38": "TOGGLE_MIDI_PLAY",
		"39": "START_MIDI_PLAY",
		"40": "STOP_MIDI_PLAY",

		"41": "ARROW_UP",
		"42": "ARROW_DOWN",
		"43": "ARROW_RIGHT",
		"44": "ARROW_LEFT",

		"45": "ZYNPOT_UP",
		"46": "ZYNPOT_DOWN",

		"48": "BACK",
		"49": "NEXT",
		"50": "PREV",
		"51": "SELECT",
		
		"52": "SELECT_UP",
		"53": "SELECT_DOWN",
		"54": "BACK_UP",
		"55": "BACK_DOWN",
		"56": "LAYER_UP",
		"57": "LAYER_DOWN",
		"58": "LEARN_UP",
		"59": "LEARN_DOWN",

		"64": "SWITCH_BACK_SHORT",
		"63": "SWITCH_BACK_BOLD",
		"62": "SWITCH_BACK_LONG",
		"65": "SWITCH_SELECT_SHORT",
		"66": "SWITCH_SELECT_BOLD",
		"67": "SWITCH_SELECT_LONG",
		"60": "SWITCH_LAYER_SHORT",
		"61": "SWITCH_LAYER_BOLD",
		"68": "SWITCH_LAYER_LONG",
		"71": "SWITCH_SNAPSHOT_SHORT",
		"72": "SWITCH_SNAPSHOT_BOLD",
		"73": "SWITCH_SNAPSHOT_LONG",

		"80": "SCREEN_MAIN",
		"81": "SCREEN_ADMIN",
		"82": "SCREEN_AUDIO_MIXER",
		"83": "SCREEN_SNAPSHOT",

		"85": "SCREEN_MIDI_RECORDER",
		"86": "SCREEN_ALSA_MIXER",
		"87": "SCREEN_STEPSEQ",
		"88": "SCREEN_BANK",
		"89": "SCREEN_PRESET",
		"90": "SCREEN_CALIBRATE",

		"100": "LAYER_CONTROL",
		"101": "CHAIN_OPTIONS",
		"102": "MENU",
		"103": "PRESET",
		"104": "FAVS",
		"105": "ZYNPAD"
	}

	def __init__(self):
		self.test_mode = False

		self.power_save_mode = False
		self.last_event_flag = False
		self.last_event_ts = monotonic()

		self.screens = {}
		self.screen_history = []
		self.current_screen = None
		self.screen_timer_id = None
		
		self.current_processor = None

		self.loading = 0
		self.loading_thread = None
		self.control_thread = None
		self.status_thread = None
		self.zynread_wait_flag = False
		self.zynswitch_defered_event = None
		self.exit_flag = False
		self.exit_code = 0
		self.exit_wait_count = 0

		self.zynmidi = None
		self.midi_learn_mode = 0

		self.status_counter = 0

		self.state_manager = zynthian_state_manager.zynthian_state_manager()
		self.chain_manager = self.state_manager.chain_manager
		self.modify_chain_status = {"midi_thru": False, "audio_thru": False, "parallel": False}

		# Create Lock object to avoid concurrence problems
		self.lock = Lock()

		# Init LEDs
		self.init_wsleds()

		# Load keyboard binding map
		zynthian_gui_keybinding.getInstance().load()

		# Get Jackd Options
		self.jackd_options = zynconf.get_jackd_options()

		# OSC config values
		self.osc_proto = liblo.UDP
		self.osc_server_port = 1370

		# Dictionary of {OSC clients, last heartbeat} registered for mixer feedback
		self.osc_clients = {}
		self.osc_heartbeat_timeout = 120 # Heartbeat timeout period

		# Initialize SOC sensors monitoring
		try:
			self.hwmon_thermal_file = open('/sys/class/hwmon/hwmon0/temp1_input')
			self.hwmon_undervolt_file = open('/sys/class/hwmon/hwmon1/in0_lcrit_alarm')
			self.overtemp_warning = 75.0
			self.get_throttled_file = None
		except:
			logging.warning("Can't access sensors. Trying legacy interface...")
			self.hwmon_thermal_file = None
			self.hwmon_undervolt_file = None
			self.overtemp_warning = None
			try:
				self.get_throttled_file = open('/sys/devices/platform/soc/soc:firmware/get_throttled')
				logging.debug("Accessing sensors using legacy interface!")
			except Exception as e:
				logging.error("Can't access monitoring sensors at all!")


	# ---------------------------------------------------------------------------
	# WS281X LEDs
	# ---------------------------------------------------------------------------

	def init_wsleds(self):
		if zynthian_gui_config.wiring_layout == "Z2_V1":
			# LEDS with PWM1 (pin 13, channel 1)
			pin = 13
			chan = 1
		elif zynthian_gui_config.wiring_layout in ("Z2_V2", "Z2_V3"):
			# LEDS with SPI0 (pin 10, channel 0)
			pin = 10
			chan = 0
		else:
			self.wsleds = None
			return 0

		self.wsleds_num = 25
		self.wsleds=rpi_ws281x.PixelStrip(self.wsleds_num, pin, dma=10, channel=chan, strip_type=rpi_ws281x.ws.WS2811_STRIP_GRB)
		self.wsleds.begin()

		self.wscolor_off = rpi_ws281x.Color(0,0,0)
		self.wscolor_light = rpi_ws281x.Color(0,0,255)
		self.wscolor_active = rpi_ws281x.Color(0,255,0)
		self.wscolor_admin = rpi_ws281x.Color(120,0,0)
		self.wscolor_red = rpi_ws281x.Color(120,0,0)
		self.wscolor_green = rpi_ws281x.Color(0,255,0)
		self.wscolor_yellow = rpi_ws281x.Color(160,160,0)
		self.wscolor_low = rpi_ws281x.Color(0, 100, 0)

		# Light all LEDs
		for i in range(0, self.wsleds_num):
			self.wsleds.setPixelColor(i, self.wscolor_light)
		self.wsleds.show()

		self.wsleds_blink_count = 0

		return self.wsleds_num


	def end_wsleds(self):
		self.off_wsleds()


	def off_wsleds(self):
		# Light-off all LEDs
		for i in range(0, self.wsleds_num):
			self.wsleds.setPixelColor(i, self.wscolor_off)
		self.wsleds.show()


	def wsled_blink(self, i, color):
		if self.wsleds_blink:
			self.wsleds.setPixelColor(i, color)
		else:
			self.wsleds.setPixelColor(i, self.wscolor_off)
			#self.wsleds.setPixelColor(i, self.wscolor_light)


	def update_wsleds(self):
		# Power Save Mode
		if self.power_save_mode:
			if self.wsleds_blink_count % 16 > 14:
				self.wsleds_blink = True
			else:
				self.wsleds_blink = False
			for i in range(0, self.wsleds_num):
				self.wsleds.setPixelColor(i, self.wscolor_off)
			self.wsled_blink(0, self.wscolor_low)
			self.wsleds.show()
			self.wsleds_blink_count += 1
			return

		# Normal mode
		if self.wsleds_blink_count % 4 > 1:
			self.wsleds_blink = True
		else:
			self.wsleds_blink = False

		try:
			# Menu
			if self.current_screen=="main":
				self.wsleds.setPixelColor(0, self.wscolor_active)
			elif self.current_screen=="stepseq" and self.screens['stepseq'].is_shown_menu():
				self.wsleds.setPixelColor(0, self.wscolor_active)
			elif self.current_screen=="admin":
				self.wsleds.setPixelColor(0, self.wscolor_admin)
			else:
				self.wsleds.setPixelColor(0, self.wscolor_light)

			# Active Chain
			# => Light non-empty chains
			chain_ids = self.chain_manager.chain_ids_ordered
			for i in range(6):
				if i < len(chain_ids):
					if chain_ids[i] == self.chain_manager.active_chain_id:
						if self.current_screen == "control":
							self.wsleds.setPixelColor(1 + i, self.wscolor_active)
						else:
							self.wsled_blink(1 + i, self.wscolor_active)
					else:
						self.wsleds.setPixelColor(1 + i, self.wscolor_light)
				else:
					self.wsleds.setPixelColor(1 + i, self.wscolor_off)
			# => Light FX layer if not empty
			if self.chain_manager.get_processor_count("main"):
				self.wsleds.setPixelColor(7, self.wscolor_light)
			else:
				self.wsleds.setPixelColor(7, self.wscolor_off)
			# => Light active layer
			if self.chain_manager.active_chain_id is not None:
				if self.chain_manager.active_chain_id == "main":
					if self.current_screen == "control":
						self.wsleds.setPixelColor(7, self.wscolor_active)
					else:
						self.wsled_blink(7, self.wscolor_active)
	
			# Stepseq screen:
			if self.current_screen=="zynpad":
				self.wsleds.setPixelColor(8, self.wscolor_active)
			else:
				self.wsleds.setPixelColor(8, self.wscolor_light)

			# Pattern Editor screen:
			if self.current_screen=="pattern_editor":
				self.wsleds.setPixelColor(9, self.wscolor_active)
			else:
				self.wsleds.setPixelColor(9, self.wscolor_light)

			# MIDI Recorder screen:
			if self.current_screen=="midi_recorder":
				self.wsleds.setPixelColor(10, self.wscolor_active)
			else:
				self.wsleds.setPixelColor(10, self.wscolor_light)

			# Snapshot screen:
			if self.current_screen=="snapshot":
				self.wsleds.setPixelColor(11, self.wscolor_active)
			else:
				self.wsleds.setPixelColor(11, self.wscolor_light)

			# Presets screen:
			if self.current_screen in ("preset", "bank"):
				self.wsleds.setPixelColor(12, self.wscolor_active)
			else:
				self.wsleds.setPixelColor(12, self.wscolor_light)

			# Light ALT button => MIDI LEARN!
			if self.state_manager.midi_learn_zctrl or self.current_screen=="zs3_learn":
				self.wsleds.setPixelColor(13, self.wscolor_yellow)
			elif self.midi_learn_mode:
				self.wsleds.setPixelColor(13, self.wscolor_active)
			else:
				self.wsleds.setPixelColor(13, self.wscolor_light)

			# REC/PLAY Audio buttons:
			if 'audio_recorder' in self.state_manager.status_info:
				self.wsleds.setPixelColor(14, self.wscolor_red)
			else:
				self.wsleds.setPixelColor(14, self.wscolor_light)

			if self.current_screen == "pattern_editor":
				pb_status = self.screens['pattern_editor'].get_playback_status()
				if pb_status == zynseq.SEQ_PLAYING:
					self.wsleds.setPixelColor(15, self.wscolor_green)
				elif pb_status in (zynseq.SEQ_STARTING, zynseq.SEQ_RESTARTING):
					self.wsleds.setPixelColor(15, self.wscolor_yellow)
				elif pb_status in (zynseq.SEQ_STOPPING, zynseq.SEQ_STOPPINGSYNC):
					self.wsleds.setPixelColor(15, self.wscolor_red)
				elif pb_status == zynseq.SEQ_STOPPED:
					self.wsleds.setPixelColor(15, self.wscolor_light)
			elif 'audio_player' in self.state_manager.status_info:
				self.wsleds.setPixelColor(15, self.wscolor_active)
			else:
				self.wsleds.setPixelColor(15, self.wscolor_light)

			# REC/PLAY MIDI buttons:
			if self.state_manager.status_info['midi_recorder']:
				if "REC" in self.state_manager.status_info['midi_recorder']:
					self.wsleds.setPixelColor(16, self.wscolor_red)
				else:
					self.wsleds.setPixelColor(16, self.wscolor_light)

				if "PLAY" in self.state_manager.status_info['midi_recorder']:
					self.wsleds.setPixelColor(17, self.wscolor_active)
				else:
					self.wsleds.setPixelColor(17, self.wscolor_light)
			else:
				self.wsleds.setPixelColor(16, self.wscolor_light)
				self.wsleds.setPixelColor(17, self.wscolor_light)

			# Back/No button
			self.wsleds.setPixelColor(18, self.wscolor_red)

			# Up button
			self.wsleds.setPixelColor(19, self.wscolor_light)

			# Select/Yes button
			self.wsleds.setPixelColor(20, self.wscolor_green)

			# Left, Bottom, Right button
			for i in range(3):
				self.wsleds.setPixelColor(21 + i, self.wscolor_light)

			# Audio Mixer/Levels screen
			if self.current_screen == "audio_mixer":
				self.wsleds.setPixelColor(24, self.wscolor_active)
			elif self.current_screen == "alsa_mixer":
				self.wsleds.setPixelColor(24, self.wscolor_admin)
			else:
				self.wsleds.setPixelColor(24, self.wscolor_light)

			try:
				self.screens[self.current_screen].update_wsleds()
			except:
				pass

			# Refresh LEDs
			self.wsleds.show()

		except Exception as e:
			logging.error(e)

		self.wsleds_blink_count += 1


	# ---------------------------------------------------------------------------
	# OSC Management
	# ---------------------------------------------------------------------------

	def osc_init(self):
		try:
			self.osc_server=liblo.Server(self.osc_server_port, self.osc_proto)
			self.osc_server_port=self.osc_server.get_port()
			self.osc_server_url=liblo.Address('localhost', self.osc_server_port,self.osc_proto).get_url()
			logging.info("ZYNTHIAN-UI OSC server running in port {}".format(self.osc_server_port))
			self.osc_server.add_method(None, None, self.osc_cb_all)
		#except liblo.AddressError as err:
		except Exception as err:
			logging.error("ZYNTHIAN-UI OSC Server can't be started: {}".format(err))


	def osc_end(self):
		if self.osc_server:
			try:
				self.osc_server.free()
				logging.info("ZYNTHIAN-UI OSC server stopped")
			except Exception as err:
				logging.error("ZYNTHIAN-UI OSC server can't be stopped: {}".format(err))
		self.osc_server = None


	def osc_receive(self):
		while self.osc_server and self.osc_server.recv(0):
			pass


	#@liblo.make_method("RELOAD_MIDI_CONFIG", None)
	#@liblo.make_method(None, None)
	def osc_cb_all(self, path, args, types, src):
		logging.info("OSC MESSAGE '{}' from '{}'".format(path, src.url))

		parts = path.split("/", 2)
		part1 = parts[1].upper()
		if parts[0] == "" and part1 == "CUIA":
			#Execute action
			self.callable_ui_action(parts[2].upper(), args)
			#Run autoconnect if needed
			self.state_manager.autoconnect()
		elif part1 in ("MIXER", "DAWOSC"):
			part2 = parts[2].upper()
			if part2 in ("HEARTBEAT", "SETUP"):
				if src.hostname not in self.osc_clients:
					try:
						if self.state_manager.zynmixer.add_osc_client(src.hostname) < 0:
							logging.warning("Failed to add OSC client registration {}".format(src.hostname))
							return
					except:
						logging.warning("Error trying to add OSC client registration {}".format(src.hostname))
						return
				self.osc_clients[src.hostname] = monotonic()
				for chan in range(self.state_manager.zynmixer.get_max_channels()):
					self.state_manager.zynmixer.enable_dpm(chan, True)
			else:
				if part2[:6] == "VOLUME":
					self.state_manager.zynmixer.set_level(int(part2[6:]), float(args[0]))
				if  part2[:5] == "FADER":
					self.state_manager.zynmixer.set_level(int(part2[5:]), float(args[0]))
				if  part2[:5] == "LEVEL":
					self.state_manager.zynmixer.set_level(int(part2[5:]), float(args[0]))
				elif part2[:7] == "BALANCE":
					self.state_manager.zynmixer.set_balance(int(part2[7:]), float(args[0]))
				elif part2[:4] == "MUTE":
					self.state_manager.zynmixer.set_mute(int(part2[4:]), int(args[0]))
				elif part2[:4] == "SOLO":
					self.state_manager.zynmixer.set_solo(int(part2[4:]), int(args[0]))
				elif part2[:4] == "MONO":
					self.state_manager.zynmixer.set_mono(int(part2[4:]), int(args[0]))
		else:
			logging.warning("Not supported OSC call '{}'".format(path))

		#for a, t in zip(args, types):
		#	logging.debug("argument of type '%s': %s" % (t, a))


	# ---------------------------------------------------------------------------
	# GUI Core Management
	# ---------------------------------------------------------------------------

	def start(self):

		# Create Core UI Screens
		self.screens['info'] = zynthian_gui_info()
		self.screens['splash'] = zynthian_gui_splash()
		self.screens['confirm'] = zynthian_gui_confirm()
		self.screens['keyboard'] = zynthian_gui_keyboard.zynthian_gui_keyboard()
		self.screens['option'] = zynthian_gui_option()
		self.screens['engine'] = zynthian_gui_engine()
		self.screens['chain_options'] = zynthian_gui_chain_options()
		self.screens['processor_options'] = zynthian_gui_processor_options()
		self.screens['snapshot'] = zynthian_gui_snapshot()
		self.screens['midi_chan'] = zynthian_gui_midi_chan()
		self.screens['midi_cc'] = zynthian_gui_midi_cc()
		self.screens['midi_prog'] = zynthian_gui_midi_prog()
		self.screens['midi_key_range'] = zynthian_gui_midi_key_range()
		self.screens['audio_out'] = zynthian_gui_audio_out()
		self.screens['midi_out'] = zynthian_gui_midi_out()
		self.screens['audio_in'] = zynthian_gui_audio_in()
		self.screens['bank'] = zynthian_gui_bank()
		self.screens['preset'] = zynthian_gui_preset()
		self.screens['control'] = zynthian_gui_control()
		self.screens['control_xy'] = zynthian_gui_control_xy()
		self.screens['midi_profile'] = zynthian_gui_midi_profile()
		self.screens['zs3_learn'] = zynthian_gui_zs3_learn()
		self.screens['zs3_options'] = zynthian_gui_zs3_options()
		self.screens['main'] = zynthian_gui_main()
		self.screens['admin'] = zynthian_gui_admin()
		self.screens['audio_mixer'] = zynthian_gui_mixer()

		# Create UI Apps Screens
		self.screens['alsa_mixer'] = self.screens['control']
		self.screens['midi_recorder'] = zynthian_gui_midi_recorder()
		self.screens['zynpad'] = zynthian_gui_zynpad()
		self.screens['arranger'] = zynthian_gui_arranger()
		self.screens['pattern_editor'] = zynthian_gui_patterneditor()
		self.screens['touchscreen_calibration'] = zynthian_gui_touchscreen_calibration()
		self.screens['control_test'] = zynthian_gui_control_test()
		
		# Initialize OSC
		self.osc_init()

		# Control Test enabled ...
		init_screen = "main"
		snapshot_loaded = False
		if zynthian_gui_config.control_test_enabled:
			init_screen = "control_test"
		else:
			# TODO: Move this to later (after display shown) and give indication of progress to avoid apparent hang during startup
			# Try to load "last_state" snapshot ...
			if zynthian_gui_config.restore_last_state:
				snapshot_loaded = self.screens['snapshot'].load_last_state_snapshot()
			# Try to load "default" snapshot ...
			if not snapshot_loaded:
				snapshot_loaded = self.screens['snapshot'].load_default_snapshot()

		if snapshot_loaded:
			init_screen = "audio_mixer"
		else:
			# Init MIDI Subsystem => MIDI Profile
			self.state_manager.init_midi()
			self.state_manager.init_midi_services()

		# Show initial screen
		self.show_screen(init_screen)

		# Start polling threads
		self.start_polling()
		self.start_loading_thread()
		self.start_control_thread()
		self.start_status_thread()

		# Initialize MPE Zones
		#self.init_mpe_zones(0, 2)


	def stop(self):
		logging.info("STOPPING ZYNTHIAN-UI ...")
		self.state_manager.reset()
		self.screens['midi_recorder'].stop_playing() # Need to stop timing thread
		#self.zyntransport.stop()


	def hide_screens(self, exclude=None):
		if not exclude:
			exclude = self.current_screen
		exclude_obj = self.screens[exclude]

		for screen_name, screen_obj in self.screens.items():
			if screen_obj != exclude_obj:
				screen_obj.hide()


	def show_screen(self, screen=None, hmode=SCREEN_HMODE_ADD):
		self.cancel_screen_timer()
		self.current_processor = None
		
		if screen is None:
			if self.current_screen:
				screen = self.current_screen
			else:
				screen = "audio_mixer"

		elif screen == "alsa_mixer":
			self.state_manager.alsa_mixer_processor.refresh_controllers()
			self.current_processor = self.state_manager.alsa_mixer_processor

		if screen not in ("bank", "preset", "option"):
			self.chain_manager.restore_presets()

		self.screens[screen].build_view()
		self.hide_screens(exclude=screen)
		if hmode == zynthian_gui.SCREEN_HMODE_ADD:
			if len(self.screen_history) == 0 or self.screen_history[-1] != screen:
				self.screen_history.append(screen)
		elif hmode == zynthian_gui.SCREEN_HMODE_REPLACE:
			self.screen_history.pop()
			self.screen_history.append(screen)
		elif hmode == zynthian_gui.SCREEN_HMODE_RESET:
			self.screen_history = [screen]

		if self.current_screen != screen:
			self.current_screen = screen
			self.screens[screen].show()


	def show_modal(self, screen=None):
		self.show_screen(screen, hmode=zynthian_gui.SCREEN_HMODE_ADD)


	def replace_screen(self, screen=None):
		self.show_screen(screen, hmode=zynthian_gui.SCREEN_HMODE_REPLACE)


	def show_screen_reset(self, screen=None):
		self.show_screen(screen, hmode=zynthian_gui.SCREEN_HMODE_RESET)


	def show_current_screen(self):
		self.show_screen(self.current_screen)


	def is_shown_alsa_mixer(self):
		return self.current_processor == "alsa_mixer"


	def close_screen(self):
		logging.debug("SCREEN HISTORY => {}".format(self.screen_history))
		while True:
			try:
				last_screen = self.screen_history.pop()
				if last_screen != self.current_screen:
					break
			except:
				last_screen = "audio_mixer"
				break

		logging.debug("CLOSE SCREEN '{}' => Back to '{}'".format(self.current_screen, last_screen))
		self.show_screen(last_screen)


	def close_modal(self):
		self.close_screen()


	def back_screen(self):
		try:
			res = self.screens[self.current_screen].back_action()
		except AttributeError as e:
			res = False

		if not res:
			self.close_screen()


	def close_screen_timer(self, tms=3000):
		self.cancel_screen_timer()
		self.screen_timer_id = zynthian_gui_config.top.after(tms, self.close_screen)


	def cancel_screen_timer(self):
		if self.screen_timer_id:
			zynthian_gui_config.top.after_cancel(self.screen_timer_id)
			self.screen_timer_id = None


	def toggle_screen(self, screen, hmode=SCREEN_HMODE_ADD):
		if self.current_screen != screen:
			self.show_screen(screen, hmode)
		else:
			self.close_screen()


	def refresh_screen(self):
		screen = self.current_screen
		if screen == 'preset' and len(self.get_current_processor().preset_list) <= 1:
			screen = 'control'
		self.show_screen(screen)


	def get_current_screen_obj(self):
		try:
			return self.screens[self.current_screen]
		except:
			return None


	def refresh_current_screen(self):
		self.screens[self.current_screen].show()


	def show_confirm(self, text, callback=None, cb_params=None):
		self.screens['confirm'].show(text, callback, cb_params)
		self.current_screen = 'confirm'
		self.hide_screens(exclude = 'confirm')


	def show_keyboard(self, callback, text="", max_chars=None):
		self.screens['keyboard'].set_mode(zynthian_gui_keyboard.OSK_QWERTY)
		self.screens['keyboard'].show(callback, text, max_chars)
		self.current_screen = 'keyboard'
		self.hide_screens(exclude='keyboard')


	def show_numpad(self, callback, text="", max_chars=None):
		self.screens['keyboard'].set_mode(zynthian_gui_keyboard.OSK_NUMPAD)
		self.screens['keyboard'].show(callback, text, max_chars)
		self.current_screen = 'keyboard'
		self.hide_screens(exclude='keyboard')


	def show_info(self, text, tms=None):
		self.screens['info'].show(text)
		self.current_screen = 'info'
		self.hide_screens(exclude='info')
		if tms:
			zynthian_gui_config.top.after(tms, self.hide_info)


	def add_info(self, text, tags=None):
		self.screens['info'].add(text,tags)


	def hide_info(self):
		if self.current_screen == 'info':
			self.close_screen()


	def hide_info_timer(self, tms=3000):
		if self.current_screen == 'info':
			self.cancel_screen_timer()
			self.screen_timer_id = zynthian_gui_config.top.after(tms, self.hide_info)


	def show_splash(self, text):
		self.screens['splash'].show(text)
		self.current_screen = 'splash'
		self.hide_screens(exclude='splash')


	def calibrate_touchscreen(self):
		self.show_screen('touchscreen_calibration')


	def modify_chain(self, status={}): #TODO: Rename - this is called for various chain manipulation purposes
		"""Manage the stages of adding or changing a processor or chain
		
		status - Dictionary of status (Default: continue with current status)
		"""

		if status:
			self.modify_chain_status = status

		if "midi_chan" in self.modify_chain_status:
			# We know the MIDI channel so create a new chain and processor
			if "midi_thru" not in  self.modify_chain_status:
				self.modify_chain_status["midi_thru"] = False
			if "audio_thru" not in  self.modify_chain_status:
				self.modify_chain_status["audio_thru"] = False
			chain_id = self.chain_manager.add_chain(
				None,
				self.modify_chain_status["midi_chan"],
				self.modify_chain_status["midi_thru"],
				self.modify_chain_status["audio_thru"])
			processor = self.chain_manager.add_processor(
				chain_id,
				self.modify_chain_status["engine"]
			)
			self.modify_chain_status = {"midi_thru": False, "audio_thru": False, "parallel": False}
			self.chain_control(chain_id, processor)
		elif "engine" in self.modify_chain_status:
			if "chain_id" in self.modify_chain_status:
				# Modifying an existing chain
				if "processor" in self.modify_chain_status:
					# Replacing processor in existing chain
					chain = self.chain_manager.get_chain(self.modify_chain_status["chain_id"])
					old_processor = self.modify_chain_status["processor"]
					if chain and old_processor:
						slot = chain.get_slot(old_processor)
						processor = self.chain_manager.add_processor(self.modify_chain_status["chain_id"], self.modify_chain_status["engine"], True, slot)
						if processor:
							self.chain_manager.remove_processor(self.modify_chain_status["chain_id"], old_processor)
							self.chain_control(self.modify_chain_status["chain_id"], processor)
				elif "parallel" in self.modify_chain_status:
					# Adding processor to existing chain
					processor = self.chain_manager.add_processor(self.modify_chain_status["chain_id"], self.modify_chain_status["engine"], self.modify_chain_status["parallel"])
					self.chain_control(self.modify_chain_status["chain_id"], processor)
				return
			# Adding a new chain so select its MIDI channel
			self.screens["midi_chan"].set_mode("ADD")
			self.show_screen("midi_chan")
		elif "type" in self.modify_chain_status:
			# We know the type so select the engine
			self.show_screen("engine")
		else:
			#TODO: Offer type selection
			pass

	def chain_control(self, chain_id=None, processor=None):
		if chain_id is None:
			chain_id = self.chain_manager.active_chain_id
		else:
			self.chain_manager.set_active_chain_by_id(chain_id)

		if self.get_current_processor():
			control_screen_name = 'control'

			# Check for a custom GUI (widget)
			module_path = self.get_current_processor().engine.custom_gui_fpath
			if module_path:
				module_name = Path(module_path).stem
				if module_name.startswith("zynthian_gui_"):
					custom_screen_name = module_name[len("zynthian_gui_"):]
					if custom_screen_name not in self.screens:
						try:
							spec = importlib.util.spec_from_file_location(module_name, module_path)
							module = importlib.util.module_from_spec(spec)
							spec.loader.exec_module(module)
							class_ = getattr(module, module_name)
							self.screens[custom_screen_name] = class_()
						except Exception as e:
							logging.error("Can't load custom control screen {} => {}".format(custom_screen_name, e))

					if custom_screen_name in self.screens:
						control_screen_name = custom_screen_name

			# If a preset is selected => control screen
			if self.get_current_processor().get_preset_name():
				self.show_screen_reset(control_screen_name)
			# If not => bank/preset selector screen
			else:
				self.get_current_processor().load_bank_list()
				if len(self.get_current_processor().bank_list) > 1:
					self.show_screen_reset('bank')
				else:
					self.get_current_processor().set_bank(0)
					self.get_current_processor().load_preset_list()
					if len(self.get_current_processor().preset_list) > 1:
						self.show_screen_reset('preset')
					else:
						if len(self.get_current_processor().preset_list):
							self.get_current_processor().set_preset(0)
						self.show_screen_reset(control_screen_name)
		else:
			chain = self.chain_manager.get_chain(chain_id)
			if chain and chain.is_audio():
				self.modify_chain({"chain_id":chain_id, "type":"Audio Effect"})

	def show_control(self):
		self.chain_control()


	def show_control_xy(self, xctrl, yctrl):
		self.screens['control_xy'].set_controllers(xctrl, yctrl)
		self.screens['control_xy'].show()
		self.current_screen = 'control'
		self.hide_screens(exclude='control_xy')
		self.screens['control'].set_mode_control()
		logging.debug("SHOW CONTROL-XY => %s, %s" % (xctrl.symbol, yctrl.symbol))


	def toggle_favorites(self):
		if self.get_current_processor():
			self.get_current_processor().toggle_show_fav_presets()
			self.show_screen("preset")


	def show_favorites(self):
		if self.get_current_processor():
			self.get_current_processor().set_show_fav_presets(True)
			self.show_screen("preset")


	def get_current_processor(self):
		"""Get the currently selected processor object"""
		if self.current_processor:
			return self.current_processor
		try:
			return self.chain_manager.get_active_chain().current_processor
		except:
			return None


	def get_current_processor_wait(self):
		#Try until processor is ready
		for j in range(100):
			if self.get_current_processor():
				return self.get_current_processor()
			else:
				sleep(0.1)


	def is_single_active_channel(self):
		return zynthian_gui_config.midi_single_active_channel


	def clean_all(self):
		self.state_manager.zynmixer.set_mute(256, 1)
		if self.chain_manager.get_chain_count() > 0:
			self.screens['snapshot'].save_last_state_snapshot()
		self.state_manager.reset()
		self.show_screen_reset('main')
		self.state_manager.zynmixer.set_mute(256, 0)


	#------------------------------------------------------------------
	# MIDI learning
	#------------------------------------------------------------------

	def set_midi_learn_mode(self, mode):
		self.midi_learn_mode = mode
		if mode == 1:
			try:
				self.screens[self.current_screen].enter_midi_learn()
			except Exception as e:
				logging.debug(e)
				pass
		elif mode == 0:
			try:
				self.screens[self.current_screen].exit_midi_learn()
			except Exception as e:
				logging.debug(e)
				pass
		elif mode == 2:
			self.screens['zs3_learn'].index = 0
			self.show_screen("zs3_learn")


	def refresh_midi_learn_zctrl(self):
		self.screens['control'].refresh_midi_bind()
		self.screens['control'].set_select_path()


	#------------------------------------------------------------------
	# MIDI learning
	#------------------------------------------------------------------

	def enter_midi_learn(self):
		self.state_manager.enter_midi_learn()
		try:
			logging.debug("ENTER LEARN => {}".format(self.current_screen))
			self.screens[self.current_screen].enter_midi_learn()
		except Exception as e:
			logging.debug(e)
			pass


	def exit_midi_learn(self):
		self.state_manager.exit_midi_learn()
		try:
			self.screens[self.current_screen].exit_midi_learn()
		except:
			pass


	# -------------------------------------------------------------------
	# Callable UI Actions
	# -------------------------------------------------------------------

	def callable_ui_action(self, cuia, params=None):
		logging.debug("CUIA '{}' => {}".format(cuia, params))

		#----------------------------------------------------------------
		# System actions
		#----------------------------------------------------------------
		if cuia == "TEST_MODE":
			self.test_mode = params
			logging.warning('TEST_MODE: {}'.format(params))

		elif cuia == "POWER_OFF":
			self.screens['admin'].power_off_confirmed()

		elif cuia == "REBOOT":
			self.screens['admin'].reboot_confirmed()

		elif cuia == "RESTART_UI":
			self.screens['admin'].restart_gui()

		elif cuia == "EXIT_UI":
			self.screens['admin'].exit_to_console()

		elif cuia == "RELOAD_MIDI_CONFIG":
			self.state_manager.reload_midi_config()

		elif cuia == "RELOAD_KEY_BINDING":
			zynthian_gui_keybinding.getInstance().load()

		elif cuia == "LAST_STATE_ACTION":
			self.screens['admin'].last_state_action()

		# Panic Actions
		elif cuia == "ALL_NOTES_OFF":
			self.all_notes_off()
			sleep(0.1)
			self.raw_all_notes_off()
		elif cuia == "ALL_SOUNDS_OFF" or cuia == "ALL_OFF":
			self.all_notes_off()
			self.all_sounds_off()
			sleep(0.1)
			self.raw_all_notes_off()
		
		elif cuia == "CLEAN_ALL" and params == ['CONFIRM']:
			self.clean_all()
			self.show_screen_reset('main') #TODO: Should send signal so that UI can react

		#----------------------------------------------------------------
		# Audio & MIDI Recording/Playback actions
		#----------------------------------------------------------------
		elif cuia == "START_AUDIO_RECORD":
			self.state_manager.audio_recorder.start_recording()
			self.refresh_signal("AUDIO_RECORD")

		elif cuia == "STOP_AUDIO_RECORD":
			self.state_manager.audio_recorder.stop_recording()
			self.refresh_signal("AUDIO_RECORD")

		elif cuia == "TOGGLE_AUDIO_RECORD":
			self.state_manager.audio_recorder.toggle_recording()
			self.refresh_signal("AUDIO_RECORD")

		elif cuia == "START_AUDIO_PLAY":
			self.state_manager.start_audio_player()
			
		elif cuia == "STOP_AUDIO_PLAY":
			self.state_manager.stop_audio_player()

		elif cuia == "TOGGLE_AUDIO_PLAY":
			if self.current_screen == "pattern_editor":
				self.screens["pattern_editor"].toggle_playback()
			else:
				self.state_manager.toggle_audio_player()

		elif cuia == "START_MIDI_RECORD":
			self.screens['midi_recorder'].start_recording()

		elif cuia == "STOP_MIDI_RECORD":
			self.screens['midi_recorder'].stop_recording()
			if self.current_screen=="midi_recorder":
				self.screens['midi_recorder'].select()

		elif cuia == "TOGGLE_MIDI_RECORD":
			self.screens['midi_recorder'].toggle_recording()
			if self.current_screen=="midi_recorder":
				self.screens['midi_recorder'].select()

		elif cuia == "START_MIDI_PLAY":
			self.screens['midi_recorder'].start_playing()

		elif cuia == "STOP_MIDI_PLAY":
			self.screens['midi_recorder'].stop_playing()

		elif cuia == "TOGGLE_MIDI_PLAY":
			self.screens['midi_recorder'].toggle_playing()

		elif cuia == "START_STEP_SEQ":
			#TODO Implement this correctly or remove CUIA
			#self.state_manager.zynseq.start_transport()
			pass

		elif cuia == "STOP_STEP_SEQ":
			#TODO Implement this correctly or remove CUIA
			#self.state_manager.zynseq.stop_transport()
			pass

		elif cuia == "TOGGLE_STEP_SEQ":
			#TODO Implement this correctly or remove CUIA
			#self.state_manager.zynseq.toggle_transport()
			pass

		elif cuia == "TEMPO":
			try:
				self.state_manager.zynseq.set_tempo(params[0])
			except:
				pass

		#----------------------------------------------------------------
		# Basic UI-Control CUIAs
		#----------------------------------------------------------------
		# 4 x Arrows
		elif cuia == "ARROW_UP":
			try:
				self.get_current_screen_obj().arrow_up()
			except:
				pass
		elif cuia == "ARROW_DOWN" or cuia == "PREV":
			try:
				self.get_current_screen_obj().arrow_down()
			except:
				pass
		elif cuia == "ARROW_RIGHT" or cuia == "NEXT":
			try:
				self.get_current_screen_obj().arrow_right()
			except:
				pass
		elif cuia == "ARROW_LEFT":
			try:
				self.get_current_screen_obj().arrow_left()
			except:
				pass

		# Back action
		elif cuia == "BACK":
			try:
				self.back_screen()
			except:
				pass
		# Select element in list => it receives an integer parameter!
		elif cuia == "SELECT":
			try:
				self.get_current_screen_obj().select(params[0])
			except:
				pass
		# Select switch action (optional press duration parameter: 'S', 'B', 'L')
		elif cuia == "SWITCH_SELECT":
			try:
				if params:
					self.get_current_screen_obj().switch_select(params[0])
				else:
					self.get_current_screen_obj().switch_select()
			except:
				pass

		#----------------------------------------------------------------
		# Rotary Control => it receives the zynpot number as parameter
		#----------------------------------------------------------------
		elif cuia == "ZYNPOT_UP":
			try:
				self.get_current_screen_obj().zynpot_cb(params[0], +1)
			except Exception as err:
				logging.exception(err)
		elif cuia == "ZYNPOT_DOWN":
			try:
				self.get_current_screen_obj().zynpot_cb(params[0], -1)
			except Exception as err:
				logging.exception(err)

		#----------------------------------------------------------------
		# Legacy "4 x rotaries" CUIAs
		#----------------------------------------------------------------

		elif cuia == "SELECT_UP":
			try:
				self.get_current_screen_obj().zynpot_cb(zynthian_gui_config.ENC_SELECT, 1)
			except:
				pass
		elif cuia == "SELECT_DOWN":
			try:
				self.get_current_screen_obj().zynpot_cb(zynthian_gui_config.ENC_SELECT, -1)
			except:
				pass
		elif cuia == "BACK_UP":
			try:
				self.get_current_screen_obj().zynpot_cb(zynthian_gui_config.ENC_BACK, 1)
			except:
				pass
		elif cuia == "BACK_DOWN":
			try:
				self.get_current_screen_obj().zynpot_cb(zynthian_gui_config.ENC_BACK, -1)
			except:
				pass
		elif cuia == "LAYER_UP":
			try:
				self.get_current_screen_obj().zynpot_cb(zynthian_gui_config.ENC_LAYER, 1)
			except:
				pass
		elif cuia == "LAYER_DOWN":
			try:
				self.get_current_screen_obj().zynpot_cb(zynthian_gui_config.ENC_LAYER, -1)
			except:
				pass
		elif cuia in ("SNAPSHOT_UP", "LEARN_UP"):
			try:
				self.get_current_screen_obj().zynpot_cb(zynthian_gui_config.ENC_SNAPSHOT, 1)
			except:
				pass
		elif cuia in ("SNAPSHOT_DOWN", "LEARN_DOWN"):
			try:
				self.get_current_screen_obj().zynpot_cb(zynthian_gui_config.ENC_SNAPSHOT, -1)
			except:
				pass

		#----------------------------------------------------------------
		# Legacy "4 x switches" CUIAs (4 * 3 = 12 CUIAS!)
		#----------------------------------------------------------------

		elif cuia == "SWITCH_LAYER_SHORT":
			self.zynswitch_short(0)
		elif cuia == "SWITCH_LAYER_BOLD":
			self.zynswitch_bold(0)
		elif cuia == "SWITCH_LAYER_LONG":
			self.zynswitch_long(0)
		elif cuia == "SWITCH_BACK_SHORT":
			self.zynswitch_short(1)
		elif cuia == "SWITCH_BACK_BOLD":
			self.zynswitch_bold(1)
		elif cuia == "SWITCH_BACK_LONG":
			self.zynswitch_long(1)
		elif cuia == "SWITCH_SNAPSHOT_SHORT":
			self.zynswitch_short(2)
		elif cuia == "SWITCH_SNAPSHOT_BOLD":
			self.zynswitch_bold(2)
		elif cuia == "SWITCH_SNAPSHOT_LONG":
			self.zynswitch_long(2)
		elif cuia == "SWITCH_SELECT_SHORT":
			self.zynswitch_short(3)
		elif cuia == "SWITCH_SELECT_BOLD":
			self.zynswitch_bold(3)
		elif cuia == "SWITCH_SELECT_LONG":
			self.zynswitch_long(3)

		#----------------------------------------------------------------
		# Screen/Mode management CUIAs
		#----------------------------------------------------------------
		#TODO: Toggle not necessarily desired action. Should we add set-screen options?

		elif cuia == "TOGGLE_VIEW" and params:
			self.toggle_screen(params[0])

		elif cuia == "SHOW_VIEW" and params:
			self.show_screen_reset(params[0])
		
		elif cuia == "SCREEN_MAIN":
			self.toggle_screen("main")

		elif cuia == "SCREEN_ADMIN":
			self.toggle_screen("admin")

		elif cuia == "SCREEN_AUDIO_MIXER":
			self.toggle_screen("audio_mixer")

		elif cuia == "SCREEN_SNAPSHOT":
			self.toggle_screen("snapshot")

		elif cuia == "SCREEN_MIDI_RECORDER":
			self.toggle_screen("midi_recorder")

		elif cuia == "SCREEN_ALSA_MIXER":
			self.toggle_screen("alsa_mixer", hmode=zynthian_gui.SCREEN_HMODE_RESET)

		elif cuia == "SCREEN_ZYNPAD":
			self.toggle_screen("zynpad")

		elif cuia == "SCREEN_PATTERN_EDITOR":
			success = False
			if self.current_screen in ["arranger", "zynpad"]:
				success = self.screens[self.current_screen].show_pattern_editor()
			if not success:
				self.toggle_screen("pattern_editor")

		elif cuia == "SCREEN_ARRANGER":
			self.toggle_screen("arranger")

		elif cuia == "SCREEN_BANK":
			self.toggle_screen("bank")

		elif cuia == "SCREEN_PRESET":
			self.toggle_screen("preset")

		elif cuia == "SCREEN_CALIBRATE":
			self.calibrate_touchscreen()

		elif cuia in ("LAYER_CONTROL", "SCREEN_CONTROL"):
			self.cuia_chain_control(params)

		elif cuia in ["LAYER_OPTIONS", "CHAIN_OPTIONS"]:
			self.cuia_chain_options(params)

		elif cuia == "MENU":
			try:
				self.screens[self.current_screen].toggle_menu()
			except:
				self.toggle_screen("main", hmode=zynthian_gui.SCREEN_HMODE_ADD)

		elif cuia == "PRESET":
			self.cuia_bank_preset(params)

		elif cuia == "PRESET_FAVS":
			self.show_favorites()

		elif cuia == "ZCTRL_TOUCH":
			if params:
				self.screens['control'].midi_learn_zctrl(params[0])

		elif cuia == "ENTER_MIDI_LEARN":
			self.state_manager.enter_midi_learn()

		elif cuia == "EXIT_MIDI_LEARN":
			self.state_manager.exit_midi_learn()

		elif cuia == "TOGGLE_MIDI_LEARN":
			self.state_manager.toggle_midi_learn()

		elif cuia == "ACTION_MIDI_UNLEARN":
			try:
				self.screens[self.current_screen].midi_unlearn_action()
			except:
				pass

		elif cuia == "MIDI_UNLEARN_CONTROL":
			# Unlearn from currently selected (learning) control
			if self.state_manager.midi_learn_zctrl:
				self.state_manager.midi_learn_zctrl.midi_unlearn()

		elif cuia == "MIDI_UNLEARN_MIXER":
			# Unlearn all mixer controls
			try:
				self.screens['audio_mixer'].midi_unlearn_all()
			except Exception as e:
				logging.error(e)

		elif cuia == "MIDI_UNLEARN_NODE":
			try:
				self.screens['control'].screen_layer.midi_unlearn() #TODO
			except Exception as e:
				logging.error(e)

		elif cuia == "MIDI_UNLEARN_CHAIN":
			try:
				self.state_manager.midi_unlearn()
			except Exception as e:
				logging.error(e)

		# Common methods to control views derived from zynthian_gui_base
		elif isinstance(self.screens[self.current_screen], zynthian_gui_base):
			if cuia == "SHOW_TOPBAR":
				self.screens[self.current_screen].show_topbar(True)

			elif cuia == "HIDE_TOPBAR":
				self.screens[self.current_screen].show_topbar(False)

			elif cuia == "SHOW_BUTTONBAR":
				self.screens[self.current_screen].show_buttonbar(True)

			elif cuia == "HIDE_BUTTONBAR":
				self.screens[self.current_screen].show_buttonbar(False)

			elif cuia == "SHOW_SIDEBAR":
				self.screens[self.current_screen].show_sidebar(True)

			elif cuia == "HIDE_SIDEBAR":
				self.screens[self.current_screen].show_sidebar(False)


	def refresh_signal(self, sname):
		try:
			self.screens[self.current_screen].refresh_signal(sname)
		except:
			pass


	def cuia_chain_control(self, params=None):
		chain_id = None
		try:
			# Select chain by index
			index = params[0]
			if index == 0:
				chain_id = "main"
			else:
				chain_id = self.chain_manager.chain_ids_ordered[params[0] - 1]
		except:
			try:
				# Select chain by ID
				chain_id = params[0]
			except:
				pass
		self.chain_control(chain_id)


	def cuia_chain_options(self, params):
		chain_id = None
		try:
			# Select chain by index
			index = params[0]
			if index == 0:
				chain_id = "main"
			else:
				chain_id = self.chain_manager.chain_ids_ordered[params[0] - 1]
		except:
			try:
				# Select chain by ID
				chain_id = params[0]
			except:
				pass
		if chain_id is not None:
			self.screens['chain_options'].setup(chain_id)
			self.toggle_screen('chain_options', hmode=zynthian_gui.SCREEN_HMODE_ADD)


	def cuia_bank_preset(self, params=None):
		if params:
			try:
				self.current_processor = params #TODO: This doesn't do enough
			except:
				logging.error("Can't set chain passed as CUIA parameter!")

		if self.current_screen == 'preset':
			if len(self.get_current_processor().bank_list) > 1:
				self.replace_screen('bank')
			else:
				self.close_screen()
		elif self.current_screen == 'bank':
			#self.replace_screen('preset')
			self.close_screen()
		elif self.get_current_processor():
			if len(self.get_current_processor().preset_list) > 0 and self.get_current_processor().preset_list[0][0] != '':
				self.screens['preset'].index = self.get_current_processor().get_preset_index()
				self.show_screen('preset', hmode=zynthian_gui.SCREEN_HMODE_ADD)
			elif len(self.get_current_processor().bank_list) > 0 and self.get_current_processor().bank_list[0][0] != '':
				self.show_screen('bank', hmode=zynthian_gui.SCREEN_HMODE_ADD)


	def custom_switch_ui_action(self, i, t):
		action_config = zynthian_gui_config.custom_switch_ui_actions[i]
		if t in action_config:
			cuia = action_config[t]
			if cuia and cuia!="NONE":
				parts = cuia.split(" ", 2)
				cmd = parts[0]
				if len(parts) > 1:
					params = []
					for i,p in enumerate(parts[1].split(",")):
						try:
							params.append(int(p))
						except:
							params.append(p.strip())
				else:
					params = None

				self.callable_ui_action(cmd, params)


	# -------------------------------------------------------------------
	# Switches
	# -------------------------------------------------------------------

	def zynswitches(self):
		if not get_lib_zyncore(): return
		i = 0
		while i <= zynthian_gui_config.last_zynswitch_index:
			dtus = get_lib_zyncore().get_zynswitch(i, zynthian_gui_config.zynswitch_long_us)
			if dtus < 0:
				pass
			elif dtus == 0:
				self.zynswitch_push(i)
			elif dtus > zynthian_gui_config.zynswitch_long_us:
				self.zynswitch_long(i)
			elif dtus > zynthian_gui_config.zynswitch_bold_us:
				# Double switches must be bold!!! => by now ...
				if not self.zynswitch_double(i):
					self.zynswitch_bold(i)
			elif dtus > 0:
				#print("Switch "+str(i)+" dtus="+str(dtus))
				self.zynswitch_short(i)
			i += 1


	def zynswitch_long(self, i):
		logging.debug('Looooooooong Switch '+str(i))
		self.start_loading()

		# Standard 4 ZynSwitches
		if i == 0:
			self.show_screen_reset("zynpad")

		elif i == 1:
			self.show_screen_reset("admin")

		elif i == 2:
			self.callable_ui_action("ALL_OFF")

		elif i == 3:
			self.screens['admin'].power_off()

		# Custom ZynSwitches
		elif i >= 4:
			self.custom_switch_ui_action(i-4, "L")

		self.stop_loading()


	def zynswitch_bold(self, i):
		logging.debug('Bold Switch '+str(i))

		self.start_loading()

		try:
			if self.screens[self.current_screen].switch(i, 'B'):
				self.stop_loading()
				return
		except AttributeError as e:
			pass

		# Default actions for the 4 standard ZynSwitches
		if i == 0:
			self.show_screen('main')

		elif i == 1:
			try:
				self.screens[self.current_screen].disable_param_editor()
			except:
				pass
			self.show_screen_reset('audio_mixer')

		elif i == 2:
			self.show_screen('snapshot')

		elif i == 3:
			self.screens[self.current_screen].switch_select('B')

		# Custom ZynSwitches
		elif i >= 4:
			self.custom_switch_ui_action(i-4, "B")

		self.stop_loading()


	def zynswitch_short(self, i):
		logging.debug('Short Switch '+str(i))

		self.start_loading()

		try:
			if self.screens[self.current_screen].switch(i, 'S'):
				self.stop_loading()
				return
		except AttributeError as e:
			pass

		# Default actions for the standard 4 ZynSwitches
		if i == 0:
			pass

		elif i == 1:
			self.back_screen()

		elif i == 2:
			self.state_manager.toggle_midi_learn()

		elif i == 3:
			self.screens[self.current_screen].switch_select('S')

		# Custom ZynSwitches
		elif i >= 4:
			self.custom_switch_ui_action(i-4, "S")

		self.stop_loading()


	def zynswitch_push(self, i):
		self.last_event_flag = True

		try:
			if self.screens[self.current_screen].switch(i, 'P'):
				return
		except AttributeError as e:
			pass

		# Standard 4 ZynSwitches
		if i >= 0 and i <= 3:
			pass

		# Custom ZynSwitches
		elif i >= 4:
			logging.debug('Push Switch ' + str(i))
			self.start_loading()
			self.custom_switch_ui_action(i-4, "P")
			self.stop_loading()


	def zynswitch_double(self, i):
		self.state_manager.dtsw[i] = datetime.now()
		for j in range(4):
			if j == i: continue
			if abs((self.state_manager.dtsw[i] - self.state_manager.dtsw[j]).total_seconds()) < 0.3:
				self.start_loading()
				dswstr = str(i) + '+' + str(j)
				logging.debug('Double Switch ' + dswstr)
				#self.show_control_xy(i, j)
				self.show_screen('control')
				self.screens['control'].set_xyselect_mode(i, j)
				self.stop_loading()
				return True


	def zynswitch_X(self, i):
		logging.debug('X Switch %d' % i)
		if self.current_screen == 'control' and self.screens['control'].mode == 'control':
			self.screens['control'].midi_learn(i)


	def zynswitch_Y(self,i):
		logging.debug('Y Switch %d' % i)
		if self.current_screen == 'control' and self.screens['control'].mode == 'control':
			try:
				zctrl = self.screens['control'].zgui_controllers[i].zctrl
				options = {
					"Unlearn '{}' control".format(zctrl.name): zctrl,
					"Unlearn all controls": 0
				}
				self.screens['option'].config("MIDI Unlearn", options, self.midi_unlearn_options_cb)
				self.show_screen('option')
			except:
				pass


	def midi_unlearn_options_cb(self, option, param):
		if param:
			self.screens['control'].midi_unlearn(param)
		else:
			self.show_confirm("Do you want to clean MIDI-learn for ALL controls in {} on MIDI channel {}?".format(self.get_current_processor().engine.name, self.get_current_processor().midi_chan + 1), self.screens['control'].midi_unlearn)



	#------------------------------------------------------------------
	# Switch Defered Events
	#------------------------------------------------------------------


	def zynswitch_defered(self, t, i):
		self.zynswitch_defered_event = (t, i)


	def zynswitch_defered_exec(self):
		if self.zynswitch_defered_event is not None:
			#Copy event and clean variable
			event = copy.deepcopy(self.zynswitch_defered_event)
			self.zynswitch_defered_event=None
			#Process event
			if event[0] == 'P':
				self.zynswitch_push(event[1])
			elif event[0] == 'S':
				self.zynswitch_short(event[1])
			elif event[0] == 'B':
				self.zynswitch_bold(event[1])
			elif event[0] == 'L':
				self.zynswitch_long(event[1])
			elif event[0] == 'X':
				self.zynswitch_X(event[1])
			elif event[0] == 'Y':
				self.zynswitch_Y(event[1])


	#------------------------------------------------------------------
	# Read Physical Zynswitches
	#------------------------------------------------------------------

	def zynswitch_read(self):
		if self.loading:
			return

		#Read Zynswitches
		try:
			self.zynswitch_defered_exec()
			self.zynswitches()

		except Exception as err:
			logging.exception(err)

		self.reset_loading()


	#------------------------------------------------------------------
	# MIDI processing
	#------------------------------------------------------------------

	def zynmidi_read(self):
		try:
			while get_lib_zyncore():
				ev = get_lib_zyncore().read_zynmidi()
				if ev == 0:
					break

				#logging.info("MIDI_UI MESSAGE: {}".format(hex(ev)))

				if (ev & 0xFF0000) == 0xF80000:
					self.state_manager.status_info['midi_clock'] = True
				else:
					self.state_manager.status_info['midi'] = True
					self.last_event_flag = True

				evtype = (ev & 0xF00000) >> 20
				chan = (ev & 0x0F0000) >> 16

				#logging.info("MIDI_UI MESSAGE DETAILS: {}, {}".format(chan,evtype))

				# System Messages
				if zynthian_gui_config.midi_sys_enabled and evtype == 0xF:
					# Song Position Pointer...
					if chan == 0x1:
						timecode = (ev & 0xFF) >> 8;
					elif chan == 0x2:
						pos = ev & 0xFFFF;
					# Song Select...
					elif chan == 0x3:
						song_number = (ev & 0xFF) >> 8;
					# Timeclock
					elif chan == 0x8:
						pass
					# MIDI tick
					elif chan == 0x9:
						pass
					# Start
					elif chan == 0xA:
						pass
					# Continue
					elif chan == 0xB:
						pass
					# Stop
					elif chan == 0xC:
						pass
					# Active Sensing
					elif chan == 0xE:
						pass
					# Reset
					elif chan == 0xF:
						pass

				# Master MIDI Channel ...
				elif chan == zynthian_gui_config.master_midi_channel:
					logging.info("MASTER MIDI MESSAGE: %s" % hex(ev))
					self.start_loading()
					# Webconf configured messages for Snapshot Control ...
					if ev == zynthian_gui_config.master_midi_program_change_up:
						logging.debug("PROGRAM CHANGE UP!")
						self.screens['snapshot'].midi_program_change_up()
					elif ev == zynthian_gui_config.master_midi_program_change_down:
						logging.debug("PROGRAM CHANGE DOWN!")
						self.screens['snapshot'].midi_program_change_down()
					elif ev == zynthian_gui_config.master_midi_bank_change_up:
						logging.debug("BANK CHANGE UP!")
						self.screens['snapshot'].midi_bank_change_up()
					elif ev == zynthian_gui_config.master_midi_bank_change_down:
						logging.debug("BANK CHANGE DOWN!")
						self.screens['snapshot'].midi_bank_change_down()
					# Program Change => Snapshot Load
					elif evtype == 0xC:
						pgm = ((ev & 0x7F00) >> 8)
						logging.debug("PROGRAM CHANGE %d" % pgm)
						self.screens['snapshot'].midi_program_change(pgm)
					# Control Change ...
					elif evtype == 0xB:
						ccnum = (ev & 0x7F00) >> 8
						ccval = (ev & 0x007F)
						if ccnum == zynthian_gui_config.master_midi_bank_change_ccnum:
							bnk = (ev & 0x7F)
							logging.debug("BANK CHANGE %d" % bnk)
							self.screens['snapshot'].midi_bank_change(bnk)
						elif ccnum == 120:
							self.all_sounds_off()
						elif ccnum == 123:
							self.all_notes_off()
						if self.state_manager.midi_learn_zctrl:
							self.state_manager.midi_learn_zctrl.cb_midi_learn(chan, ccnum)
							self.show_current_screen()
						else:
							self.state_manager.zynmixer.midi_control_change(chan, ccnum, ccval)
					# Note-on => CUIA
					elif evtype == 0x9:
						note = str((ev & 0x7F00) >> 8)
						vel = (ev & 0x007F)
						if vel != 0 and note in self.note2cuia:
							self.callable_ui_action(self.note2cuia[note], [vel])

					# Stop logo animation
					self.stop_loading()

				# Program Change ...
				elif evtype == 0xC:
					pgm = (ev & 0x7F00) >> 8
					logging.info("MIDI PROGRAM CHANGE: CH#{}, PRG#{}".format(chan,pgm))

					# SubSnapShot (ZS3) MIDI learn ...
					if self.midi_learn_mode and self.current_screen == 'zs3_learn':
						self.state_manager.save_zs3(f"{chan}/{pgm}")
						self.exit_midi_learn()
						self.close_screen()
					# Set Preset or ZS3 (sub-snapshot), depending of config option
					else:
						if zynthian_gui_config.midi_prog_change_zs3:
							res = self.state_manager.set_midi_prog_zs3(chan, pgm)
						else:
							res = self.chain_manager.set_midi_prog_preset(chan, pgm)
						if res:
							if self.current_screen == 'audio_mixer':
								self.screens['audio_mixer'].refresh_visible_strips()
							elif self.current_screen == 'control':
								self.screens['control'].build_view()

						#if self.get_current_processor() and chan == self.get_current_processor().get_midi_chan():
						#	self.show_screen('control')

				# Control Change ...
				elif evtype == 0xB:
					self.screens['midi_chan'].midi_chan_activity(chan)
					ccnum = (ev & 0x7F00) >> 8
					ccval = (ev & 0x007F)
					#logging.debug("MIDI CONTROL CHANGE: CH{}, CC{} => {}".format(chan,ccnum,ccval))
					if ccnum < 120:
						# If MIDI learn pending ...
						if self.state_manager.midi_learn_zctrl:
							self.state_manager.midi_learn_zctrl.cb_midi_learn(chan, ccnum)
							self.show_current_screen()
						# Try chains's zctrls
						else:
							self.chain_manager.midi_control_change(chan, ccnum, ccval)
							self.state_manager.zynmixer.midi_control_change(chan, ccnum, ccval)
					# Special CCs >= Channel Mode
					elif ccnum == 120:
						self.all_sounds_off_chan(chan)
					elif ccnum == 123:
						self.all_notes_off_chan(chan)

				# Note-On ...
				elif evtype == 0x9:
					self.screens['midi_chan'].midi_chan_activity(chan)
					#Preload preset (note-on)
					if self.current_screen == 'preset' and zynthian_gui_config.preset_preload_noteon and chan == self.get_current_processor().get_midi_chan():
						self.start_loading()
						self.screens['preset'].preselect_action()
						self.stop_loading()
					#Note Range Learn
					elif self.current_screen == 'midi_key_range' and self.midi_learn_mode:
						self.screens['midi_key_range'].learn_note_range((ev & 0x7F00) >> 8)
					elif self.current_screen == 'pattern_editor' and self.state_manager.zynseq.libseq.getInputChannel() < 16:
						self.screens['pattern_editor'].midi_note((ev & 0x7F00) >> 8)

				# Pitch Bending ...
				elif evtype == 0xE:
					pass

		except Exception as err:
			self.reset_loading()
			logging.exception(err)


	#------------------------------------------------------------------
	# Control Thread
	#------------------------------------------------------------------

	def start_control_thread(self):
		self.control_thread = Thread(target=self.control_thread_task, args=())
		self.control_thread.name = "control"
		self.control_thread.daemon = True # thread dies with the program
		self.control_thread.start()


	def control_thread_task(self):
		j = 0
		while not self.exit_flag:
			# Read zynswitches, MIDI & OSC events
			self.zynswitch_read()
			self.zynmidi_read()
			self.osc_receive()

			# Every 4 cycles ...
			if j > 4:
				j = 0

				# Refresh GUI Controllers
				try:
					self.screens[self.current_screen].plot_zctrls()
				except AttributeError:
					pass
				except Exception as e:
					logging.error(e)

				# Power Save Mode
				if zynthian_gui_config.power_save_secs > 0:
					if self.last_event_flag:
						self.last_event_ts = monotonic()
						self.last_event_flag = False
						if self.power_save_mode:
							self.set_power_save_mode(False)
					elif not self.power_save_mode and (monotonic() - self.last_event_ts) > zynthian_gui_config.power_save_secs:
						self.set_power_save_mode(True)
			else:
				j += 1

			# Wait a little bit ...
			sleep(0.01)

		# End Thread task
		self.osc_end()


	def set_power_save_mode(self, psm=True):
		self.power_save_mode = psm
		if psm:
			logging.info("Power Save Mode: ON")
			check_output("powersave_control.sh on", shell=True)
		else:
			logging.info("Power Save Mode: OFF")
			check_output("powersave_control.sh off", shell=True)

	#------------------------------------------------------------------
	# "Busy" Animated Icon Thread
	#------------------------------------------------------------------

	def start_loading_thread(self):
		self.loading_thread=Thread(target=self.loading_refresh, args=())
		self.loading_thread.name = "loading"
		self.loading_thread.daemon = True # thread dies with the program
		self.loading_thread.start()


	def start_loading(self):
		self.loading = self.loading + 1
		if self.loading < 1: self.loading = 1
		#logging.debug("START LOADING %d" % self.loading)


	def stop_loading(self):
		self.loading = self.loading - 1
		if self.loading < 0: self.loading = 0
		#logging.debug("STOP LOADING %d" % self.loading)


	def reset_loading(self):
		self.loading = 0


	def loading_refresh(self):
		while not self.exit_flag:
			try:
				self.screens[self.current_screen].refresh_loading()
			except Exception as err:
				logging.error("zynthian_gui.loading_refresh() => %s" % err)
			sleep(0.1)

	#------------------------------------------------------------------
	# Status Refresh Thread
	#------------------------------------------------------------------

	def start_status_thread(self):
		self.status_thread = Thread(target=self.status_thread_task, args=())
		self.status_thread.name = "status"
		self.status_thread.daemon = True # thread dies with the program
		self.status_thread.start()


	def status_thread_task(self):
		while not self.exit_flag:
			self.refresh_status()
			if self.wsleds:
				self.update_wsleds()
			if self.midi_learn_mode != self.state_manager.midi_learn_mode:
				self.set_midi_learn_mode(self.state_manager.midi_learn_mode)
			sleep(0.2)
		if self.wsleds:
			self.end_wsleds()


	def refresh_status(self):
		try:
			if zynthian_gui_config.show_cpu_status:
				# Get CPU Load
				#self.state_manager.status_info['cpu_load'] = max(psutil.cpu_percent(None, True))
				self.state_manager.status_info['cpu_load'] = self.status_counter.zynautoconnect.get_jackd_cpu_load()
			else:
				# Get audio peak level
				self.state_manager.status_info['peakA'] = self.state_manager.zynmixer.get_dpm(MIXER_MAIN_CHANNEL, 0)
				self.state_manager.status_info['peakB'] = self.state_manager.zynmixer.get_dpm(MIXER_MAIN_CHANNEL, 1)
				self.state_manager.status_info['holdA'] = self.state_manager.zynmixer.get_dpm_hold(MIXER_MAIN_CHANNEL, 0)
				self.state_manager.status_info['holdB'] = self.state_manager.zynmixer.get_dpm_hold(MIXER_MAIN_CHANNEL, 1)

			# Get SOC sensors (once each 5 refreshes)
			if self.status_counter>5:
				self.status_counter = 0

				self.state_manager.status_info['overtemp'] = False
				self.state_manager.status_info['undervoltage'] = False

				if self.hwmon_thermal_file and self.hwmon_undervolt_file:
					try:
						self.hwmon_thermal_file.seek(0)
						res = int(self.hwmon_thermal_file.read())/1000
						#logging.debug("CPU Temperature => {}".format(res))
						if res > self.overtemp_warning:
							self.state_manager.status_info['overtemp'] = True
					except Exception as e:
						logging.error(e)

					try:
						self.hwmon_undervolt_file.seek(0)
						res = self.hwmon_undervolt_file.read()
						if res == "1":
							self.state_manager.status_info['undervoltage'] = True
					except Exception as e:
						logging.error(e)

				elif self.get_throttled_file:
					try:
						self.get_throttled_file.seek(0)
						thr = int('0x%s' % self.get_throttled_file.read(), 16)
						if thr & 0x1:
							self.state_manager.status_info['undervoltage'] = True
						elif thr & (0x4 | 0x2):
							self.state_manager.status_info['overtemp'] = True
					except Exception as e:
						logging.error(e)

				else:
					self.state_manager.status_info['overtemp'] = True
					self.state_manager.status_info['undervoltage'] = True

			else:
				self.status_counter += 1

			# Get Recorder Status
			try:
				self.state_manager.status_info['midi_recorder'] = self.screens['midi_recorder'].get_status()
			except Exception as e:
				logging.error(e)
			
			# Refresh On-Screen Status
			try:
				self.screens[self.current_screen].refresh_status(self.state_manager.status_info)
			except AttributeError:
				pass

			# Clean some state_manager.status_info
			self.state_manager.status_info['xrun'] = False
			self.state_manager.status_info['midi'] = False
			self.state_manager.status_info['midi_clock'] = False

		except Exception as e:
			logging.exception(e)


	#------------------------------------------------------------------
	# Thread ending on Exit
	#------------------------------------------------------------------

	def exit(self, code=0):
		self.stop()
		self.exit_code = code
		self.exit_flag = True


	#------------------------------------------------------------------
	# Polling
	#------------------------------------------------------------------

	def start_polling(self):
		self.zyngine_refresh()
		self.osc_timeout()


	def after(self, msec, func):
		zynthian_gui_config.top.after(msec, func)


	def zyngine_refresh(self):
		# Capture exit event and finish
		if self.exit_flag:
			timeout = 10
			if self.exit_wait_count == 0:
				logging.info("EXITING ZYNTHIAN-UI...")
			if self.exit_wait_count < timeout and (self.control_thread.is_alive() or self.status_thread.is_alive() or self.loading_thread.is_alive() or self.state_manager.zynautoconnect.is_running()):
				self.exit_wait_count += 1
			else:
				if self.exit_wait_count == timeout:
					# Exceeded wait time for threads to stop
					if self.control_thread.is_alive():
						logging.error("Control thread failed to terminate")
					if self.status_thread.is_alive():
						logging.error("Status thread failed to terminate")
					if self.loading_thread.is_alive():
						logging.error("Loading thread failed to terminate")
					if self.state_manager.zynautoconnect.is_running():
						logging.error("Auto-connect thread failed to terminate")
				zynthian_gui_config.top.quit()
				return
		# Refresh Current Chain
		elif self.get_current_processor() and not self.loading:
			try:
				#TODO: self.get_current_processor().refresh()
				pass
			except Exception as e:
				self.reset_loading()
				logging.exception(e)

		# Poll
		zynthian_gui_config.top.after(160, self.zyngine_refresh)


	def osc_timeout(self):
		if not self.exit_flag:
			self.watchdog_last_check = monotonic()
			for client in list(self.osc_clients):
				if self.osc_clients[client] < self.watchdog_last_check - self.osc_heartbeat_timeout:
					self.osc_clients.pop(client)
					try:
						self.state_manager.zynmixer.remove_osc_client(client)
					except:
						pass

			if not self.osc_clients and self.current_screen != "audio_mixer":
				for chan in range(self.state_manager.zynmixer.get_max_channels()):
					self.state_manager.zynmixer.enable_dpm(chan, False)

			# Poll
			zynthian_gui_config.top.after(self.osc_heartbeat_timeout * 1000, self.osc_timeout)


	#------------------------------------------------------------------
	# All Notes/Sounds Off => PANIC!
	#------------------------------------------------------------------


	def all_sounds_off(self):
		logging.info("All Sounds Off!")
		for chan in range(16):
			get_lib_zyncore().ui_send_ccontrol_change(chan, 120, 0)


	def all_notes_off(self):
		logging.info("All Notes Off!")
		for chan in range(16):
			get_lib_zyncore().ui_send_ccontrol_change(chan, 123, 0)


	def raw_all_notes_off(self):
		logging.info("Raw All Notes Off!")
		get_lib_zyncore().ui_send_all_notes_off()


	def all_sounds_off_chan(self, chan):
		logging.info("All Sounds Off for channel {}!".format(chan))
		get_lib_zyncore().ui_send_ccontrol_change(chan, 120, 0)


	def all_notes_off_chan(self, chan):
		logging.info("All Notes Off for channel {}!".format(chan))
		get_lib_zyncore().ui_send_ccontrol_change(chan, 123, 0)


	def raw_all_notes_off_chan(self, chan):
		logging.info("Raw All Notes Off for channel {}!".format(chan))
		get_lib_zyncore().ui_send_all_notes_off_chan(chan)


	#------------------------------------------------------------------
	# MPE initialization
	#------------------------------------------------------------------

	def init_mpe_zones(self, lower_n_chans, upper_n_chans):
		# Configure Lower Zone
		if not isinstance(lower_n_chans, int) or lower_n_chans < 0 or lower_n_chans > 0xF:
			logging.error("Can't initialize MPE Lower Zone. Incorrect num of channels ({})".format(lower_n_chans))
		else:
			get_lib_zyncore().ctrlfb_send_ccontrol_change(0x0, 0x79, 0x0)
			get_lib_zyncore().ctrlfb_send_ccontrol_change(0x0, 0x64, 0x6)
			get_lib_zyncore().ctrlfb_send_ccontrol_change(0x0, 0x65, 0x0)
			get_lib_zyncore().ctrlfb_send_ccontrol_change(0x0, 0x06, lower_n_chans)

		# Configure Upper Zone
		if not isinstance(upper_n_chans, int) or upper_n_chans < 0 or upper_n_chans > 0xF:
			logging.error("Can't initialize MPE Upper Zone. Incorrect num of channels ({})".format(upper_n_chans))
		else:
			get_lib_zyncore().ctrlfb_send_ccontrol_change(0xF, 0x79, 0x0)
			get_lib_zyncore().ctrlfb_send_ccontrol_change(0xF, 0x64, 0x6)
			get_lib_zyncore().ctrlfb_send_ccontrol_change(0xF, 0x65, 0x0)
			get_lib_zyncore().ctrlfb_send_ccontrol_change(0xF, 0x06, upper_n_chans)



	#------------------------------------------------------------------
	# Zynthian Config Info
	#------------------------------------------------------------------

	def get_zynthian_config(self, varname):
		return eval("zynthian_gui_config.{}".format(varname))


	def allow_rbpi_headphones(self):
		try:
			#TODO: Add alsa mixer
			self.state_manager.alsa_mixer_processor.engine.allow_rbpi_headphones()
		except:
			pass


#******************************************************************************
#------------------------------------------------------------------------------
# Start Zynthian!
#------------------------------------------------------------------------------
#******************************************************************************

logging.info("STARTING ZYNTHIAN-UI ...")
zynthian_gui_config.zyngui = zyngui = zynthian_gui()
zyngui.start()


#------------------------------------------------------------------------------
# Zynlib Callbacks
#------------------------------------------------------------------------------

@ctypes.CFUNCTYPE(None, ctypes.c_ubyte, ctypes.c_int)
def zynpot_cb(i, dval):
	#logging.debug("Zynpot {} Callback => {}".format(i, dval))
	try:
		zyngui.screens[zyngui.current_screen].zynpot_cb(i, dval)
		zyngui.last_event_flag = True

	except Exception as err:
		pass # Some screens don't use controllers
		logging.exception(err)


get_lib_zyncore().setup_zynpot_cb(zynpot_cb)


#------------------------------------------------------------------------------
# Reparent Top Window using GTK XEmbed protocol features
#------------------------------------------------------------------------------

def flushflush():
	for i in range(1000):
		print("FLUSHFLUSHFLUSHFLUSHFLUSHFLUSHFLUSH")
	zynthian_gui_config.top.after(200, flushflush)


if zynthian_gui_config.wiring_layout=="EMULATOR":
	top_xid = zynthian_gui_config.top.winfo_id()
	print("Zynthian GUI XID: " + str(top_xid))
	if len(sys.argv) > 1:
		parent_xid = int(sys.argv[1])
		print("Parent XID: " + str(parent_xid))
		zynthian_gui_config.top.geometry('-10000-10000')
		zynthian_gui_config.top.overrideredirect(True)
		zynthian_gui_config.top.wm_withdraw()
		flushflush()
		zynthian_gui_config.top.after(1000, zynthian_gui_config.top.wm_deiconify)


#------------------------------------------------------------------------------
# Signal Catching
#------------------------------------------------------------------------------

def exit_handler(signo, stack_frame):
	logging.info("Catch Exit Signal ({}) ...".format(signo))
	if signo == signal.SIGHUP:
		exit_code = 0
	elif signo == signal.SIGINT:
		exit_code = 100
	elif signo == signal.SIGQUIT:
		exit_code = 102
	elif signo == signal.SIGTERM:
		exit_code = 101

	zyngui.exit(exit_code)


signal.signal(signal.SIGHUP, exit_handler)
signal.signal(signal.SIGINT, exit_handler)
signal.signal(signal.SIGQUIT, exit_handler)
signal.signal(signal.SIGTERM, exit_handler)


def delete_window():
	exit_code = 101
	zyngui.exit(exit_code)


zynthian_gui_config.top.protocol("WM_DELETE_WINDOW", delete_window)


#------------------------------------------------------------------------------
# Key Bindings
#------------------------------------------------------------------------------

#Function to handle computer keyboard key press
#	event: Key event
def cb_keybinding(event):
	logging.debug("Key press {} {}".format(event.keycode, event.keysym))
	zynthian_gui_config.top.focus_set() # Must remove focus from listbox to avoid interference with physical keyboard

	if not zynthian_gui_keybinding.getInstance().isEnabled():
		logging.debug("Key binding is disabled - ignoring key press")
		return

	# Ignore TAB key (for now) to avoid confusing widget focus change
	if event.keysym == "Tab":
		return

	# Space is not recognised as keysym so need to convert keycode
	if event.keycode == 65:
		keysym = "Space"
	else:
		keysym = event.keysym

	action = zynthian_gui_keybinding.getInstance().get_key_action(keysym, event.state)
	if action != None:
		if isinstance(action, list) and len(action) > 1:
			zyngui.callable_ui_action(action[0], [action[1]])
		else:
			zyngui.callable_ui_action(action)


zynthian_gui_config.top.bind("<Key>", cb_keybinding)


#------------------------------------------------------------------------------
# TKinter Main Loop
#------------------------------------------------------------------------------

#import cProfile
#cProfile.run('zynthian_gui_config.top.mainloop()')

zynthian_gui_config.top.mainloop()

#------------------------------------------------------------------------------
# Exit
#------------------------------------------------------------------------------

logging.info("Exit with code {} ...\n\n".format(zyngui.exit_code))
exit(zyngui.exit_code)

#------------------------------------------------------------------------------
