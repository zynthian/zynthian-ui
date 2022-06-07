#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Main Class and Program for Zynthian GUI
#
# Copyright (C) 2015-2016 Fernando Moyano <jofemodo@zynthian.org>
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
import copy
import liblo
import ctypes
import signal
import logging
import importlib
import threading
import rpi_ws281x
from time import sleep
from pathlib import Path
from time import monotonic
from os.path import isfile
from glob import glob
from datetime import datetime
from threading  import Thread, Lock
from subprocess import check_output


# Zynthian specific modules
import zynconf
import zynautoconnect
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynmixer import zynmixer
from zynlibs.zynmixer.zynmixer import lib_zynmixer
from zynlibs.zynaudioplayer import zynaudioplayer

from zyngine import zynthian_zcmidi
from zyngine import zynthian_midi_filter

from zyngui import zynthian_gui_config
from zyngui import zynthian_gui_keyboard
from zyngui.zynthian_gui_info import zynthian_gui_info
from zyngui.zynthian_gui_option import zynthian_gui_option
from zyngui.zynthian_gui_admin import zynthian_gui_admin
from zyngui.zynthian_gui_snapshot import zynthian_gui_snapshot
from zyngui.zynthian_gui_layer import zynthian_gui_layer
from zyngui.zynthian_gui_layer_options import zynthian_gui_layer_options
from zyngui.zynthian_gui_sublayer_options import zynthian_gui_sublayer_options
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
from zyngui.zynthian_audio_recorder import zynthian_audio_recorder
from zyngui.zynthian_gui_midi_recorder import zynthian_gui_midi_recorder
from zyngui.zynthian_gui_stepsequencer import zynthian_gui_stepsequencer
from zyngui.zynthian_gui_mixer import zynthian_gui_mixer
from zyngui.zynthian_gui_touchscreen_calibration import zynthian_gui_touchscreen_calibration

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
		"101": "LAYER_OPTIONS",
		"102": "MENU",
		"103": "PRESET",
		"104": "FAVS",
		"105": "ZYNPAD"
	}

	def __init__(self):
		self.screens = {}
		self.screen_history = []
		self.current_screen = None
		self.screen_timer_id = None
		
		self.curlayer = None
		self._curlayer = None

		self.dtsw = []
		self.polling = False

		self.loading = 0
		self.loading_thread = None
		self.control_thread = None
		self.status_thread = None
		self.zynread_wait_flag = False
		self.zynswitch_defered_event = None
		self.exit_flag = False
		self.exit_code = 0

		self.zynmidi = None
		self.midi_filter_script = None;
		self.midi_learn_mode = False
		self.midi_learn_zctrl = None

		self.status_info = {}
		self.status_counter = 0

		self.zynautoconnect_audio_flag = False
		self.zynautoconnect_midi_flag = False

		self.get_throttled_file = None

		self.audio_player = None

		# Create Lock object to avoid concurrence problems
		self.lock = Lock()

		# Init LEDs
		self.init_wsleds()

		# Create vcgencmd instance
		#self.vcgencmd = Vcgencmd()

		# Load keyboard binding map
		zynthian_gui_keybinding.getInstance().load()

		# Get Jackd Options
		self.jackd_options = zynconf.get_jackd_options()

		# Dictionary of {OSC clients, last heartbeat} registered for mixer feedback
		self.osc_clients = {}
		self.osc_heartbeat_timeout = 120 # Heartbeat timeout period

		# Initialize peakmeter audio monitor if needed
#		if not zynthian_gui_config.show_cpu_status:
#			try:
#				global lib_jackpeak
#				lib_jackpeak = lib_jackpeak_init()
#				lib_jackpeak.setDecay(ctypes.c_float(0.2))
#				lib_jackpeak.setHoldCount(10)
#			except Exception as e:
#				logging.error("ERROR initializing jackpeak: %s" % e)

		# Initialize MIDI & Switches
		try:
			self.zynmidi = zynthian_zcmidi()
			self.zynswitches_init()
			self.zynswitches_midi_setup()
		except Exception as e:
			logging.error("ERROR initializing MIDI & Switches: {}".format(e))


	# ---------------------------------------------------------------------------
	# WS281X LEDs
	# ---------------------------------------------------------------------------

	def init_wsleds(self):
		if zynthian_gui_config.wiring_layout=="Z2_V1":
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

		# Light all LEDs
		for i in range(0, self.wsleds_num):
			self.wsleds.setPixelColor(i,self.wscolor_light)
		self.wsleds.show()

		self.wsleds_blink_count = 0

		return self.wsleds_num


	def end_wsleds(self):
		# Light-off all LEDs
		for i in range(0, self.wsleds_num):
			self.wsleds.setPixelColor(i,self.wscolor_off)
		self.wsleds.show()


	def wsled_blink(self, i, color):
		if self.wsleds_blink:
			self.wsleds.setPixelColor(i, color)
		else:
			self.wsleds.setPixelColor(i, self.wscolor_light)


	def update_wsleds(self):
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

			# Active Layer
			# => Light non-empty layers
			n = self.screens['layer'].get_num_root_layers()
			main_fxchain = self.screens['layer'].get_main_fxchain_root_layer()
			if main_fxchain:
				n -= 1
			for i in range(6):
				if i<n:
					self.wsleds.setPixelColor(1+i, self.wscolor_light)
				else:
					self.wsleds.setPixelColor(1+i, self.wscolor_off)
			# => Light FX layer if not empty
			if main_fxchain:
				self.wsleds.setPixelColor(7, self.wscolor_light)
			else:
				self.wsleds.setPixelColor(7, self.wscolor_off)
			# => Light active layer
			i = self.screens['layer'].get_root_layer_index()
			if i is not None:
				if main_fxchain and i==n:
					if self.current_screen=="control":
						self.wsleds.setPixelColor(7, self.wscolor_active)
					else:
						self.wsled_blink(7, self.wscolor_active)
				elif i<6:
					if self.current_screen=="control":
						self.wsleds.setPixelColor(1+i, self.wscolor_active)
					else:
						self.wsled_blink(1+i, self.wscolor_active)

			# Stepseq screen:
			if self.current_screen=="stepseq":
				self.wsleds.setPixelColor(8, self.wscolor_active)
			else:
				self.wsleds.setPixelColor(8, self.wscolor_light)

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

			# Light ALT button
			self.wsleds.setPixelColor(13, self.wscolor_light)

			# REC/PLAY Audio buttons:
			if 'audio_recorder' in self.status_info:
				self.wsleds.setPixelColor(14, self.wscolor_red)
			else:
				self.wsleds.setPixelColor(14, self.wscolor_light)

			if 'audio_player' in self.status_info:
				self.wsleds.setPixelColor(15, self.wscolor_active)
			else:
				self.wsleds.setPixelColor(15, self.wscolor_light)

			# REC/PLAY MIDI buttons:
			if self.status_info['midi_recorder']:
				if "REC" in self.status_info['midi_recorder']:
					self.wsleds.setPixelColor(16, self.wscolor_red)
				else:
					self.wsleds.setPixelColor(16, self.wscolor_light)

				if "PLAY" in self.status_info['midi_recorder']:
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
				self.wsleds.setPixelColor(21+i, self.wscolor_light)

			# Audio Mixer/Levels screen
			if self.current_screen=="audio_mixer":
				self.wsleds.setPixelColor(24, self.wscolor_active)
			elif self.current_screen=="alsa_mixer":
				self.wsleds.setPixelColor(24, self.wscolor_admin)
			else:
				self.wsleds.setPixelColor(24, self.wscolor_light)

			# Refresh LEDs
			self.wsleds.show()

		except Exception as e:
			logging.error(e)

		self.wsleds_blink_count += 1
		

	# ---------------------------------------------------------------------------
	# MIDI Router Init & Config
	# ---------------------------------------------------------------------------

	def init_midi(self):
		try:
			#Set Global Tuning
			self.fine_tuning_freq = zynthian_gui_config.midi_fine_tuning
			lib_zyncore.set_midi_filter_tuning_freq(ctypes.c_double(self.fine_tuning_freq))
			#Set MIDI Master Channel
			lib_zyncore.set_midi_master_chan(zynthian_gui_config.master_midi_channel)
			#Set MIDI CC automode
			lib_zyncore.set_midi_filter_cc_automode(zynthian_gui_config.midi_cc_automode)
			#Set MIDI System Messages flag
			lib_zyncore.set_midi_filter_system_events(zynthian_gui_config.midi_sys_enabled)
			#Setup MIDI filter rules
			if self.midi_filter_script:
				self.midi_filter_script.clean()
			self.midi_filter_script = zynthian_midi_filter.MidiFilterScript(zynthian_gui_config.midi_filter_rules)

		except Exception as e:
			logging.error("ERROR initializing MIDI : %s" % e)


	def init_midi_services(self):
		#Start/Stop MIDI aux. services
		self.screens['admin'].default_rtpmidi()
		self.screens['admin'].default_qmidinet()
		self.screens['admin'].default_touchosc()
		self.screens['admin'].default_aubionotes()


	def reload_midi_config(self):
		zynconf.load_config()
		midi_profile_fpath=zynconf.get_midi_config_fpath()
		if midi_profile_fpath:
			zynconf.load_config(True,midi_profile_fpath)
			zynthian_gui_config.set_midi_config()
			self.init_midi()
			self.init_midi_services()
			self.zynautoconnect()

	# ---------------------------------------------------------------------------
	# OSC Management
	# ---------------------------------------------------------------------------

	def osc_init(self, port=1370, proto=liblo.UDP):
		try:
			self.osc_server=liblo.Server(port,proto)
			self.osc_server_port=self.osc_server.get_port()
			self.osc_server_url=liblo.Address('localhost',self.osc_server_port,proto).get_url()
			logging.info("ZYNTHIAN-UI OSC server running in port {}".format(self.osc_server_port))
			self.osc_server.add_method(None, None, self.osc_cb_all)
			#self.osc_server.start()
		#except liblo.AddressError as err:
		except Exception as err:
			logging.error("ZYNTHIAN-UI OSC Server can't be started: {}".format(err))


	def osc_end(self):
		if self.osc_server:
			try:
				#self.osc_server.stop()
				logging.info("ZYNTHIAN-UI OSC server stopped")
			except Exception as err:
				logging.error("Can't stop ZYNTHIAN-UI OSC server => %s" % err)


	def osc_receive(self):
		while self.osc_server.recv(0):
			pass


	#@liblo.make_method("RELOAD_MIDI_CONFIG", None)
	#@liblo.make_method(None, None)
	def osc_cb_all(self, path, args, types, src):
		logging.info("OSC MESSAGE '%s' from '%s'" % (path, src.url))

		parts = path.split("/", 2)
		part1 = parts[1].upper()
		if parts[0]=="" and part1=="CUIA":
			#Execute action
			self.callable_ui_action(parts[2].upper(), args)
			#Run autoconnect if needed
			self.zynautoconnect_do()
		elif part1 in ("MIXER", "DAWOSC"):
			part2 = parts[2].upper()
			if part2 in ("HEARTBEAT", "SETUP"):
				if src.hostname not in self.osc_clients:
					try:
						lib_zynmixer.addOscClient(ctypes.c_char_p(src.hostname.encode('utf-8')))
					except:
						logging.warning("Failed to add OSC client registration %s", src.hostname)
				self.osc_clients[src.hostname] = monotonic()
			else:
				self.screens['audio_mixer'].osc(part2, args, types, src)
		else:
			logging.warning("Not supported OSC call '{}'".format(path))

		#for a, t in zip(args, types):
		#	logging.debug("argument of type '%s': %s" % (t, a))


	# ---------------------------------------------------------------------------
	# GUI Core Management
	# ---------------------------------------------------------------------------

	def start(self):

		# Create global objects first
		self.audio_recorder = zynthian_audio_recorder()

		# Create Core UI Screens
		self.screens['info'] = zynthian_gui_info()
		self.screens['confirm'] = zynthian_gui_confirm()
		self.screens['keyboard'] = zynthian_gui_keyboard.zynthian_gui_keyboard()
		self.screens['option'] = zynthian_gui_option()
		self.screens['engine'] = zynthian_gui_engine()
		self.screens['layer'] = zynthian_gui_layer()
		self.screens['layer_options'] = zynthian_gui_layer_options()
		self.screens['sublayer_options'] = zynthian_gui_sublayer_options()
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
		self.screens['stepseq'] = zynthian_gui_stepsequencer()
		self.screens['touchscreen_calibration'] = zynthian_gui_touchscreen_calibration()

		# Init Auto-connector
		zynautoconnect.start()

		# Initialize OSC
		self.osc_init()

		# Initial snapshot...
		snapshot_loaded=False
		# Try to load "last_state" snapshot ...
		if zynthian_gui_config.restore_last_state:
			snapshot_loaded=self.screens['snapshot'].load_last_state_snapshot()
		# Try to load "default" snapshot ...
		if not snapshot_loaded:
			snapshot_loaded=self.screens['snapshot'].load_default_snapshot()

		# Show mixer
		if snapshot_loaded:
			self.show_screen('audio_mixer')
		# or set empty state & show main menu
		else:
			# Init MIDI Subsystem => MIDI Profile
			self.init_midi()
			self.init_midi_services()
			self.zynautoconnect()
			# Show initial screen
			self.show_screen('main')

		# Start polling threads
		self.start_polling()
		self.start_loading_thread()
		self.start_control_thread()
		self.start_status_thread()

		# Run autoconnect if needed
		self.zynautoconnect_do()

		# Initialize MPE Zones
		#self.init_mpe_zones(0, 2)


	def stop(self):
		logging.info("STOPPING ZYNTHIAN-UI ...")
		self.stop_polling()
		self.osc_end()
		zynautoconnect.stop()
		self.screens['layer'].reset()
		self.screens['midi_recorder'].stop_playing() # Need to stop timing thread
		#self.zyntransport.stop()


	def hide_screens(self, exclude=None):
		if not exclude:
			exclude = self.current_screen
		exclude_obj = self.screens[exclude]

		for screen_name, screen_obj in self.screens.items():
			if screen_obj!=exclude_obj:
				screen_obj.hide()


	def show_screen(self, screen=None, hmode=SCREEN_HMODE_ADD):
		self.cancel_screen_timer()

		if screen is None:
			if self.current_screen:
				screen = self.current_screen
			else:
				screen = "audio_mixer"

		if screen=="control":
			self.restore_curlayer()

		elif screen=="alsa_mixer":
			if self.screens['layer'].amixer_layer:
				self.screens['layer'].amixer_layer.refresh_controllers()
				self.set_curlayer(self.screens['layer'].amixer_layer, True)
			else:
				return

		self.hide_screens(exclude = screen)
		if hmode == zynthian_gui.SCREEN_HMODE_ADD:
			if len(self.screen_history)==0 or self.screen_history[-1]!=screen:
				self.screen_history.append(screen)
		elif hmode == zynthian_gui.SCREEN_HMODE_REPLACE:
			self.screen_history.pop()
			self.screen_history.append(screen)
		elif hmode == zynthian_gui.SCREEN_HMODE_RESET:
			self.screen_history = [screen]

		self.current_screen = screen
		self.screens[screen].show()


	def show_modal(self, screen=None):
		self.show_screen(screen, hmode=zynthian_gui.SCREEN_HMODE_NONE)


	def replace_screen(self, screen=None):
		self.show_screen(screen, hmode=zynthian_gui.SCREEN_HMODE_REPLACE)


	def show_screen_reset(self, screen=None):
		self.show_screen(screen, hmode=zynthian_gui.SCREEN_HMODE_RESET)


	def show_current_screen(self):
		self.show_screen(self.current_screen)


	def is_shown_alsa_mixer(self):
		return self.curlayer == self.screens['layer'].amixer_layer


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
		if self.current_screen!=screen:
			self.show_screen(screen, hmode)
		else:
			self.close_screen()


	def refresh_screen(self):
		screen = self.current_screen
		if screen=='preset' and len(self.curlayer.preset_list) <= 1:
			screen='control'
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
		self.current_screen='confirm'
		self.hide_screens(exclude = 'confirm')


	def show_keyboard(self, callback, text="", max_chars=None):
		self.screens['keyboard'].set_mode(zynthian_gui_keyboard.OSK_QWERTY)
		self.screens['keyboard'].show(callback, text, max_chars)
		self.current_screen='keyboard'
		self.hide_screens(exclude='keyboard')


	def show_numpad(self, callback, text="", max_chars=None):
		self.screens['keyboard'].set_mode(zynthian_gui_keyboard.OSK_NUMPAD)
		self.screens['keyboard'].show(callback, text, max_chars)
		self.current_screen='keyboard'
		self.hide_screens(exclude='keyboard')


	def show_info(self, text, tms=None):
		self.screens['info'].show(text)
		self.current_screen='info'
		self.hide_screens(exclude='info')
		if tms:
			zynthian_gui_config.top.after(tms, self.hide_info)


	def add_info(self, text, tags=None):
		self.screens['info'].add(text,tags)


	def hide_info(self):
		if self.current_screen=='info':
			self.close_screen()


	def hide_info_timer(self, tms=3000):
		if self.current_screen=='info':
			self.cancel_screen_timer()
			self.screen_timer_id = zynthian_gui_config.top.after(tms, self.hide_info)


	def calibrate_touchscreen(self):
		self.show_screen('touchscreen_calibration')


	def layer_control(self, layer=None):
		if layer is not None:
			if layer in self.screens['layer'].root_layers:
				self._curlayer = None
			else:
				self._curlayer = self.curlayer

			self.set_curlayer(layer)

		if self.curlayer:
			module_path = self.curlayer.engine.custom_gui_fpath
			if module_path:
				module_name = Path(module_path).stem
				if module_name.startswith("zynthian_gui_"):
					screen_name = module_name[len("zynthian_gui_"):]
					if screen_name not in self.screens:
						try:
							spec = importlib.util.spec_from_file_location(module_name, module_path)
							module = importlib.util.module_from_spec(spec)
							spec.loader.exec_module(module)
							class_ = getattr(module, module_name)
							self.screens[screen_name] = class_()
						except Exception as e:
							logging.error("Can't load custom control screen {} => {}".format(screen_name, e))

					if screen_name in self.screens:
						self.show_screen_reset(screen_name)
						return

			# If there is a preset selection for the active layer ...
			if self.curlayer.get_preset_name():
				self.show_screen_reset('control')
			else:
				self.show_screen_reset('bank')
				# If there is only one bank, jump to preset selection
				if len(self.curlayer.bank_list)<=1:
					self.screens['bank'].select_action(0)


	def show_control(self):
		self.restore_curlayer()
		self.layer_control()


	def enter_midi_learn_mode(self):
		self.midi_learn_mode = True
		self.midi_learn_zctrl = None
		lib_zyncore.set_midi_learning_mode(1)
		self.screens['control'].refresh_midi_bind()
		self.screens['control'].set_select_path()
		#self.show_screen('zs3_learn')


	def exit_midi_learn_mode(self):
		self.midi_learn_mode = False
		self.midi_learn_zctrl = None
		lib_zyncore.set_midi_learning_mode(0)
		self.screens['control'].refresh_midi_bind()
		self.screens['control'].set_select_path()
		self.show_current_screen()


	def show_control_xy(self, xctrl, yctrl):
		self.screens['control_xy'].set_controllers(xctrl, yctrl)
		self.screens['control_xy'].show()
		self.current_screen='control'
		self.hide_screens(exclude='control_xy')
		self.screens['control'].set_mode_control()
		logging.debug("SHOW CONTROL-XY => %s, %s" % (xctrl.symbol, yctrl.symbol))


	def toggle_favorites(self):
		if self.curlayer:
			self.curlayer.toggle_show_fav_presets()
			self.show_screen("preset")


	def show_favorites(self):
		if self.curlayer:
			self.curlayer.set_show_fav_presets(True)
			self.show_screen("preset")


	def set_curlayer(self, layer, save=False):
		if layer is not None:
			if save and not self.is_shown_alsa_mixer():
				self._curlayer = self.curlayer
			self.curlayer = layer
			self.screens['bank'].fill_list()
			self.screens['preset'].fill_list()
			self.screens['control'].fill_list()
			self.screens['audio_mixer'].select_chain_by_layer(layer, set_curlayer=False)
			self.set_active_channel()
		else:
			self.curlayer = None


	def restore_curlayer(self):
		if self._curlayer:
			self.set_curlayer(self._curlayer)
			self._curlayer = None


	#If "MIDI Single Active Channel" mode is enabled, set MIDI Active Channel to layer's one
	def set_active_channel(self):
		curlayer_chan = None
		active_chan = -1

		if self.curlayer:
			# Don't change nothing for MIXER
			if self.curlayer.engine.nickname=='MX':
				return
			curlayer_chan = self.curlayer.get_midi_chan()
			if zynthian_gui_config.midi_single_active_channel and curlayer_chan is not None:
				if curlayer_chan>=16:
					return
				active_chan = curlayer_chan
				cur_active_chan = lib_zyncore.get_midi_active_chan()
				if cur_active_chan==active_chan:
					return
				logging.debug("ACTIVE CHAN: {} => {}".format(cur_active_chan, active_chan))
				#if cur_active_chan>=0:
				#	self.all_notes_off_chan(cur_active_chan)

		lib_zyncore.set_midi_active_chan(active_chan)
		self.zynswitches_midi_setup(curlayer_chan)


	def get_curlayer_wait(self):
		#Try until layer is ready
		for j in range(100):
			if self.curlayer:
				return self.curlayer
			else:
				sleep(0.1)


	def is_single_active_channel(self):
		return zynthian_gui_config.midi_single_active_channel


	def start_audio_player(self):
		filename = self.audio_recorder.filename
		if not filename or not os.path.exists(filename):
			if os.path.ismount(self.audio_recorder.capture_dir_usb):
				path = self.audio_recorder.capture_dir_usb
			else:
				path = self.audio_recorder.capture_dir_sdc
			files = glob('{}/*.wav'.format(path))
			if files:
				filename = max(files, key=os.path.getctime)
			else:
				return

		if not self.audio_player:
			try:
				self.audio_player = zynaudioplayer.zynaudioplayer()
				zynautoconnect.audio_connect_aux(self.audio_player.get_jack_client_name())
			except Exception as e:
				self.stop_audio_player()
				return
		self.audio_player.load(filename)
		self.audio_player.set_control_cb(lambda id,value:self.stop_audio_player() if id==1 and value==0 else None)
		self.audio_player.start_playback()
		if self.audio_player.get_playback_state():
			self.status_info['audio_player'] = 'PLAY'


	def stop_audio_player(self):
		if self.audio_player:
			self.audio_player.remove_player()
			self.audio_player = None
			if 'audio_player' in self.status_info:
				self.status_info.pop('audio_player')

	# -------------------------------------------------------------------
	# Callable UI Actions
	# -------------------------------------------------------------------

	def callable_ui_action(self, cuia, params=None):
		logging.debug("CUIA '{}' => {}".format(cuia,params))

		#----------------------------------------------------------------
		# System actions
		#----------------------------------------------------------------
		if cuia == "POWER_OFF":
			self.screens['admin'].power_off_confirmed()

		elif cuia == "REBOOT":
			self.screens['admin'].reboot_confirmed()

		elif cuia == "RESTART_UI":
			self.screens['admin'].restart_gui()

		elif cuia == "EXIT_UI":
			self.screens['admin'].exit_to_console()

		elif cuia == "RELOAD_MIDI_CONFIG":
			self.reload_midi_config()

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

		#----------------------------------------------------------------
		# Audio & MIDI Recording/Playback actions
		#----------------------------------------------------------------
		elif cuia == "START_AUDIO_RECORD":
			self.audio_recorder.start_recording()

		elif cuia == "STOP_AUDIO_RECORD":
			self.audio_recorder.stop_recording()

		elif cuia == "TOGGLE_AUDIO_RECORD":
			self.audio_recorder.toggle_recording()

		elif cuia == "START_AUDIO_PLAY":
			self.start_audio_player()
			
		elif cuia == "STOP_AUDIO_PLAY":
			self.stop_audio_player()

		elif cuia == "TOGGLE_AUDIO_PLAY":
			if self.audio_player and self.audio_player.get_playback_state():
				self.stop_audio_player()
			else:
				self.start_audio_player()

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
			self.screens['stepseq'].start()

		elif cuia == "PAUSE_STEP_SEQ":
			self.screens['stepseq'].pause()

		elif cuia == "STOP_STEP_SEQ":
			self.screens['stepseq'].stop()

		elif cuia == "TOGGLE_STEP_SEQ":
			self.screens['stepseq'].toggle_transport()

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

		#----------------------------------------------------------------
		# Rotary Control => it receives the zynpot number as parameter
		#----------------------------------------------------------------
		elif cuia == "ZYNPOT_UP":
			try:
				self.screens[self.current_screen].zynpot_cb(params[0], +1)
			except Exception as err:
				logging.exception(err)
		elif cuia == "ZYNPOT_DOWN":
			try:
				self.screens[self.current_screen].zynpot_cb(params[0], -1)
			except Exception as err:
				logging.exception(err)

		#----------------------------------------------------------------
		# Legacy "4 x rotaries" CUIAs
		#----------------------------------------------------------------

		elif cuia == "SELECT_UP":
			try:
				self.get_current_screen_obj().select_up()
			except:
				pass
		elif cuia == "SELECT_DOWN":
			try:
				self.get_current_screen_obj().select_down()
			except:
				pass
		elif cuia == "BACK_UP":
			try:
				self.get_current_screen_obj().back_up()
			except:
				pass
		elif cuia == "BACK_DOWN":
			try:
				self.get_current_screen_obj().back_down()
			except:
				pass
		elif cuia == "LAYER_UP":
			try:
				self.get_current_screen_obj().layer_up()
			except:
				pass
		elif cuia == "LAYER_DOWN":
			try:
				self.get_current_screen_obj().layer_down()
			except:
				pass
		elif cuia in ("SNAPSHOT_UP", "LEARN_UP"):
			try:
				self.get_current_screen_obj().snapshot_up()
			except:
				pass
		elif cuia in ("SNAPSHOT_DOWN", "LEARN_DOWN"):
			try:
				self.get_current_screen_obj().snapshot_down()
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

		elif cuia in ("MODAL_MAIN", "SCREEN_MAIN"):
			self.toggle_screen("main")

		elif cuia in ("MODAL_ADMIN", "SCREEN_ADMIN"):
			self.toggle_screen("admin")

		elif cuia in ("MODAL_AUDIO_MIXER", "SCREEN_AUDIO_MIXER"):
			self.toggle_screen("audio_mixer")

		elif cuia in ("MODAL_SNAPSHOT", "SCREEN_SNAPSHOT"):
			self.toggle_screen("snapshot")

		elif cuia in ("MODAL_MIDI_RECORDER", "SCREEN_MIDI_RECORDER"):
			self.toggle_screen("midi_recorder")

		elif cuia in ("MODAL_ALSA_MIXER", "SCREEN_ALSA_MIXER"):
			self.toggle_screen("alsa_mixer", hmode=zynthian_gui.SCREEN_HMODE_RESET)

		elif cuia in ("MODAL_STEPSEQ", "SCREEN_STEPSEQ"):
			self.toggle_screen("stepseq")

		elif cuia in ("MODAL_BANK", "SCREEN_BANK"):
			self.toggle_screen("bank")

		elif cuia in ("MODAL_PRESET", "SCREEN_PRESET"):
			self.toggle_screen("preset")

		elif cuia in ("MODAL_CALIBRATE", "SCREEN_CALIBRATE"):
			self.calibrate_touchscreen()

		elif cuia in ("LAYER_CONTROL", "SCREEN_CONTROL"):
			self.cuia_layer_control(params)

		elif cuia == "LAYER_OPTIONS":
			self.cuia_layer_options(params)

		elif cuia == "MENU":
			try:
				self.screens[self.current_screen].toggle_menu()
			except:
				self.toggle_screen("main", hmode=zynthian_gui.SCREEN_HMODE_ADD)

		elif cuia == "PRESET":
			self.cuia_bank_preset()

		elif cuia == "PRESET_FAVS":
			self.show_favorites()

		elif cuia == "ZYNPAD":
			self.show_screen('stepseq')
			self.screens['stepseq'].show_child(self.screens['stepseq'].zynpad)

		elif cuia == "ZCTRL_TOUCH":
			if params:
				self.screens['control'].midi_learn_zctrl(params[0])

		elif cuia == "LEARN":
			self.cuia_learn(params)


	def cuia_layer_control(self, params=None):
		if params:
			try:
				i = params[0]-1
				n = self.screens['layer'].get_num_root_layers()
				main_fxchain = self.screens['layer'].get_main_fxchain_root_layer()
				if main_fxchain:
					n -= 1
				if i>=0 and i<n:
					self.layer_control(self.screens['layer'].root_layers[i])
				elif i<0:
					if main_fxchain:
						self.layer_control(main_fxchain)
					else:
						#self.screens['layer'].add_fxchain_layer(16)
						self.screens['audio_mixer'].show_mainfx_options()
			except Exception as e:
				logging.warning("Can't change to layer {}! => {}".format(params[0],e))
		else:
			self.layer_control()


	def cuia_layer_options(self, params):
		try:
			if params:
				i = params[0]-1
				n = self.screens['layer'].get_num_root_layers()
				main_fxchain = self.screens['layer'].get_main_fxchain_root_layer()
				if main_fxchain:
					n -= 1
				if i>=0 and i<n:
					self.screens['layer'].select(i)
				elif i<0:
					if main_fxchain:
						self.screens['layer'].select(n)
					else:
						#self.screens['layer'].add_fxchain_layer(16)
						self.screens['audio_mixer'].show_mainfx_options()
						return
			self.screens['layer_options'].reset()
			self.toggle_screen('layer_options', hmode=zynthian_gui.SCREEN_HMODE_ADD)
		except Exception as e:
			logging.warning("Can't show options for layer ({})! => {}".format(params,e))


	def cuia_learn(self, params=None):
		try:
			self.screens[self.current_screen].toggle_midi_learn()
		except:
			if not self.is_shown_alsa_mixer():
				if self.current_screen == "zs3_learn":
					self.close_screen()
				elif self.current_screen != "control":
					self.show_screen_reset("control")
				else:
					if zynthian_gui_config.midi_prog_change_zs3 and (self.midi_learn_mode or self.midi_learn_zctrl):
						self.show_screen("zs3_learn")
						return

			self.enter_midi_learn_mode()


	def cuia_bank_preset(self, params=None):
		if self.current_screen=='preset':
			if len(self.curlayer.bank_list)>1:
				self.replace_screen('bank')
			else:
				self.close_screen()
		elif self.current_screen=='bank':
			#self.replace_screen('preset')
			self.close_screen()
		else:
			if len(self.curlayer.preset_list) > 0 and self.curlayer.preset_list[0][0] != '':
				self.screens['preset'].index=self.curlayer.get_preset_index()
				self.show_screen('preset', hmode=zynthian_gui.SCREEN_HMODE_ADD)
			elif len(self.curlayer.bank_list) > 0 and self.curlayer.bank_list[0][0] != '':
				self.show_screen('bank', hmode=zynthian_gui.SCREEN_HMODE_ADD)


	def custom_switch_ui_action(self, i, t):
		#try:
			action_config = zynthian_gui_config.custom_switch_ui_actions[i]
			if t in action_config:
				cuia = action_config[t]
				if cuia and cuia!="NONE":
					parts = cuia.split(" ", 2)
					cmd = parts[0]
					if len(parts)>1:
						params = []
						for i,p in enumerate(parts[1].split(",")):
							try:
								params.append(int(p))
							except:
								params.append(p.strip())
					else:
						params = None

					self.callable_ui_action(cmd, params)

		#except Exception as e:
		#	logging.warning(e)


	# -------------------------------------------------------------------
	# Switches
	# -------------------------------------------------------------------

	# Init Standard Zynswitches
	def zynswitches_init(self):
		if not lib_zyncore: return
		logging.info("INIT {} ZYNSWITCHES ...".format(zynthian_gui_config.num_zynswitches))
		ts=datetime.now()
		self.dtsw = [ts] * (zynthian_gui_config.num_zynswitches + 4)


	# Initialize custom switches, analog I/O, TOF sensors, etc.
	def zynswitches_midi_setup(self, curlayer_chan=None):
		if not lib_zyncore: return
		logging.info("CUSTOM I/O SETUP...")

		# Configure Custom Switches
		for i, event in enumerate(zynthian_gui_config.custom_switch_midi_events):
			if event is not None:
				swi = 4 + i
				if event['chan'] is not None:
					midi_chan = event['chan']
				else:
					midi_chan = curlayer_chan

				if midi_chan is not None:
					lib_zyncore.setup_zynswitch_midi(swi, event['type'], midi_chan, event['num'], event['val'])
					logging.info("MIDI ZYNSWITCH {}: {} CH#{}, {}, {}".format(swi, event['type'], midi_chan, event['num'], event['val']))
				else:
					lib_zyncore.setup_zynswitch_midi(swi, 0, 0, 0, 0)
					logging.info("MIDI ZYNSWITCH {}: DISABLED!".format(swi))

		# Configure Zynaptik Analog Inputs (CV-IN)
		for i, event in enumerate(zynthian_gui_config.zynaptik_ad_midi_events):
			if event is not None:
				if event['chan'] is not None:
					midi_chan = event['chan']
				else:
					midi_chan = curlayer_chan

				if midi_chan is not None:
					lib_zyncore.setup_zynaptik_cvin(i, event['type'], midi_chan, event['num'])
					logging.info("ZYNAPTIK CV-IN {}: {} CH#{}, {}".format(i, event['type'], midi_chan, event['num']))
				else:
					lib_zyncore.disable_zynaptik_cvin(i)
					logging.info("ZYNAPTIK CV-IN {}: DISABLED!".format(i))

		# Configure Zynaptik Analog Outputs (CV-OUT)
		for i, event in enumerate(zynthian_gui_config.zynaptik_da_midi_events):
			if event is not None:
				if event['chan'] is not None:
					midi_chan = event['chan']
				else:
					midi_chan = curlayer_chan

				if midi_chan is not None:
					lib_zyncore.setup_zynaptik_cvout(i, event['type'], midi_chan, event['num'])
					logging.info("ZYNAPTIK CV-OUT {}: {} CH#{}, {}".format(i, event['type'], midi_chan, event['num']))
				else:
					lib_zyncore.disable_zynaptik_cvout(i)
					logging.info("ZYNAPTIK CV-OUT {}: DISABLED!".format(i))

		# Configure Zyntof Inputs (Distance Sensor)
		for i, event in enumerate(zynthian_gui_config.zyntof_midi_events):
			if event is not None:
				if event['chan'] is not None:
					midi_chan = event['chan']
				else:
					midi_chan = curlayer_chan

				if midi_chan is not None:
					lib_zyncore.setup_zyntof(i, event['type'], midi_chan, event['num'])
					logging.info("ZYNTOF {}: {} CH#{}, {}".format(i, event['type'], midi_chan, event['num']))
				else:
					lib_zyncore.disable_zyntof(i)
					logging.info("ZYNTOF {}: DISABLED!".format(i))


	def zynswitches(self):
		if not lib_zyncore: return
		i = 0
		while i<=zynthian_gui_config.last_zynswitch_index:
			dtus = lib_zyncore.get_zynswitch(i, zynthian_gui_config.zynswitch_long_us)
			if dtus < 0:
				pass
			elif dtus == 0:
				self.zynswitch_push(i)
			elif dtus>zynthian_gui_config.zynswitch_long_us:
				self.zynswitch_long(i)
			elif dtus>zynthian_gui_config.zynswitch_bold_us:
				# Double switches must be bold!!! => by now ...
				if not self.zynswitch_double(i):
					self.zynswitch_bold(i)
			elif dtus>0:
				#print("Switch "+str(i)+" dtus="+str(dtus))
				self.zynswitch_short(i)
			i += 1


	def zynswitch_long(self,i):
		logging.debug('Looooooooong Switch '+str(i))
		self.start_loading()

		# Standard 4 ZynSwitches
		if i==0:
			self.show_screen("stepseq")

		elif i==1:
			self.show_screen("admin")

		elif i==2:
			self.callable_ui_action("ALL_OFF")

		elif i==3:
			self.screens['admin'].power_off()

		# Custom ZynSwitches
		elif i>=4:
			self.custom_switch_ui_action(i-4, "L")

		self.stop_loading()


	def zynswitch_bold(self,i):
		logging.debug('Bold Switch '+str(i))

		self.start_loading()

		try:
			if self.screens[self.current_screen].switch(i, 'B'):
				self.stop_loading()
				return
		except AttributeError as e:
			pass

		# Default actions for the 4 standard ZynSwitches
		if i==0:
			self.show_screen('main')

		elif i==1:
			self.restore_curlayer()
			self.show_screen_reset('audio_mixer')

		elif i==2:
			self.show_screen('snapshot')

		elif i==3:
			self.screens[self.current_screen].switch_select('B')

		# Custom ZynSwitches
		elif i>=4:
			self.custom_switch_ui_action(i-4, "B")

		self.stop_loading()


	def zynswitch_short(self,i):
		logging.debug('Short Switch '+str(i))

		self.start_loading()

		try:
			if self.screens[self.current_screen].switch(i, 'S'):
				self.stop_loading()
				return
		except AttributeError as e:
			pass

		# Default actions for the standard 4 ZynSwitches
		if i==0:
			pass

		elif i==1:
			self.back_screen()

		elif i==2:
			self.cuia_learn()

		elif i==3:
			self.screens[self.current_screen].switch_select('S')

		# Custom ZynSwitches
		elif i>=4:
			self.custom_switch_ui_action(i-4, "S")

		self.stop_loading()


	def zynswitch_push(self,i):
		# Standard 4 ZynSwitches
		if i>=0 and i<=3:
			pass

		# Custom ZynSwitches
		elif i>= 4:
			logging.debug('Push Switch '+str(i))
			self.start_loading()
			self.custom_switch_ui_action(i-4, "P")
			self.stop_loading()


	def zynswitch_double(self,i):
		self.dtsw[i]=datetime.now()
		for j in range(4):
			if j==i: continue
			if abs((self.dtsw[i]-self.dtsw[j]).total_seconds())<0.3:
				self.start_loading()
				dswstr=str(i)+'+'+str(j)
				logging.debug('Double Switch '+dswstr)
				#self.show_control_xy(i,j)
				self.show_screen('control')
				self.screens['control'].set_xyselect_mode(i,j)
				self.stop_loading()
				return True


	def zynswitch_X(self,i):
		logging.debug('X Switch %d' % i)
		if self.current_screen=='control' and self.screens['control'].mode=='control':
			self.screens['control'].midi_learn(i)


	def zynswitch_Y(self,i):
		logging.debug('Y Switch %d' % i)
		if self.current_screen=='control' and self.screens['control'].mode=='control':
			self.screens['control'].midi_unlearn(i)


	#------------------------------------------------------------------
	# Switch Defered Events
	#------------------------------------------------------------------


	def zynswitch_defered(self, t, i):
		self.zynswitch_defered_event=(t,i)


	def zynswitch_defered_exec(self):
		if self.zynswitch_defered_event is not None:
			#Copy event and clean variable
			event=copy.deepcopy(self.zynswitch_defered_event)
			self.zynswitch_defered_event=None
			#Process event
			if event[0]=='P':
				self.zynswitch_push(event[1])
			elif event[0]=='S':
				self.zynswitch_short(event[1])
			elif event[0]=='B':
				self.zynswitch_bold(event[1])
			elif event[0]=='L':
				self.zynswitch_long(event[1])
			elif event[0]=='X':
				self.zynswitch_X(event[1])
			elif event[0]=='Y':
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
			while lib_zyncore:
				ev=lib_zyncore.read_zynmidi()
				if ev==0: break

				#logging.info("MIDI_UI MESSAGE: {}".format(hex(ev)))

				if (ev & 0xFF0000)==0xF80000:
					self.status_info['midi_clock'] = True
				else:
					self.status_info['midi'] = True

				evtype = (ev & 0xF00000) >> 20
				chan = (ev & 0x0F0000) >> 16

				#logging.info("MIDI_UI MESSAGE DETAILS: {}, {}".format(chan,evtype))

				# System Messages
				if zynthian_gui_config.midi_sys_enabled and evtype==0xF:
					# Song Position Pointer...
					if chan==0x1:
						timecode = (ev & 0xFF) >> 8;
					elif chan==0x2:
						pos = ev & 0xFFFF;
					# Song Select...
					elif chan==0x3:
						song_number = (ev & 0xFF) >> 8;
					# Timeclock
					elif chan==0x8:
						pass
					# MIDI tick
					elif chan==0x9:
						pass
					# Start
					elif chan==0xA:
						pass
					# Continue
					elif chan==0xB:
						pass
					# Stop
					elif chan==0xC:
						pass
					# Active Sensing
					elif chan==0xE:
						pass
					# Reset
					elif chan==0xF:
						pass

				# Master MIDI Channel ...
				elif chan==zynthian_gui_config.master_midi_channel:
					logging.info("MASTER MIDI MESSAGE: %s" % hex(ev))
					self.start_loading()
					# Webconf configured messages for Snapshot Control ...
					if ev==zynthian_gui_config.master_midi_program_change_up:
						logging.debug("PROGRAM CHANGE UP!")
						self.screens['snapshot'].midi_program_change_up()
					elif ev==zynthian_gui_config.master_midi_program_change_down:
						logging.debug("PROGRAM CHANGE DOWN!")
						self.screens['snapshot'].midi_program_change_down()
					elif ev==zynthian_gui_config.master_midi_bank_change_up:
						logging.debug("BANK CHANGE UP!")
						self.screens['snapshot'].midi_bank_change_up()
					elif ev==zynthian_gui_config.master_midi_bank_change_down:
						logging.debug("BANK CHANGE DOWN!")
						self.screens['snapshot'].midi_bank_change_down()
					# Program Change => Snapshot Load
					elif evtype==0xC:
						pgm = ((ev & 0x7F00)>>8)
						logging.debug("PROGRAM CHANGE %d" % pgm)
						self.screens['snapshot'].midi_program_change(pgm)
					# Control Change ...
					elif evtype==0xB:
						ccnum=(ev & 0x7F00)>>8
						if ccnum==zynthian_gui_config.master_midi_bank_change_ccnum:
							bnk = (ev & 0x7F)
							logging.debug("BANK CHANGE %d" % bnk)
							self.screens['snapshot'].midi_bank_change(bnk)
						elif ccnum==120:
							self.all_sounds_off()
						elif ccnum==123:
							self.all_notes_off()
					# Note-on => CUIA
					elif evtype==0x9:
						note = str((ev & 0x7F00)>>8)
						vel = (ev & 0x007F)
						if vel != 0 and note in self.note2cuia:
							self.callable_ui_action(self.note2cuia[note], [vel])

					#Run autoconnect (if needed) and stop logo animation
					self.zynautoconnect_do()
					self.stop_loading()

				# Program Change ...
				elif evtype==0xC:
					pgm = (ev & 0x7F00)>>8
					logging.info("MIDI PROGRAM CHANGE: CH{} => {}".format(chan,pgm))

					# SubSnapShot (ZS3) MIDI learn ...
					if self.midi_learn_mode and self.current_screen=='zs3_learn':
						if self.screens['layer'].save_midi_chan_zs3(chan, pgm):
							self.close_screen()
							self.exit_midi_learn_mode()

					# Set Preset or ZS3 (sub-snapshot), depending of config option
					else:
						if zynthian_gui_config.midi_prog_change_zs3:
							self.screens['layer'].set_midi_chan_zs3(chan, pgm)
						else:
							self.screens['layer'].set_midi_chan_preset(chan, pgm)

						#if self.curlayer and chan==self.curlayer.get_midi_chan():
						#	self.show_screen('control')

				# Control Change ...
				elif evtype==0xB:
					self.screens['midi_chan'].midi_chan_activity(chan)
					ccnum=(ev & 0x7F00)>>8
					ccval=(ev & 0x007F)
					#logging.debug("MIDI CONTROL CHANGE: CH{}, CC{} => {}".format(chan,ccnum,ccval))
					# If MIDI learn pending ...
					if self.midi_learn_zctrl:
						self.midi_learn_zctrl.cb_midi_learn(chan, ccnum)
					# Try layer's zctrls
					else:
						self.screens['layer'].midi_control_change(chan,ccnum,ccval)

				# Note-On ...
				elif evtype==0x9:
					self.screens['midi_chan'].midi_chan_activity(chan)
					#Preload preset (note-on)
					if self.current_screen=='preset' and zynthian_gui_config.preset_preload_noteon and chan==self.curlayer.get_midi_chan():
						self.start_loading()
						self.screens['preset'].preselect_action()
						self.stop_loading()
					#Note Range Learn
					elif self.current_screen=='midi_key_range':
						note = (ev & 0x7F00)>>8
						self.screens['midi_key_range'].learn_note_range(note)

				# Pitch Bending ...
				elif evtype==0xE:
					pass

		except Exception as err:
			self.reset_loading()
			logging.exception(err)


	#------------------------------------------------------------------
	# Control Thread
	#------------------------------------------------------------------

	def start_control_thread(self):
		self.control_thread=Thread(target=self.control_thread_task, args=())
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

			# Run autoconnect if pending
			self.zynautoconnect_do()

			# Refresh GUI controllers every 4 cycles
			if j>4:
				j = 0
				self.plot_zctrls()
			else:
				j += 1

			# Wait a little bit ...
			sleep(0.01)
			if self.zynread_wait_flag:
				sleep(0.3)
				self.zynread_wait_flag=False


	def plot_zctrls(self):
		try:
			self.screens[self.current_screen].plot_zctrls()
		except AttributeError:
			pass
		except Exception as e:
			logging.error(e)


	#------------------------------------------------------------------
	# "Busy" Animated Icon Thread
	#------------------------------------------------------------------

	def start_loading_thread(self):
		self.loading_thread=Thread(target=self.loading_refresh, args=())
		self.loading_thread.name = "loading"
		self.loading_thread.daemon = True # thread dies with the program
		self.loading_thread.start()


	def start_loading(self):
		self.loading=self.loading+1
		if self.loading<1: self.loading=1
		#logging.debug("START LOADING %d" % self.loading)


	def stop_loading(self):
		self.loading=self.loading-1
		if self.loading<0: self.loading=0
		#logging.debug("STOP LOADING %d" % self.loading)


	def reset_loading(self):
		self.loading=0


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
		self.status_thread=Thread(target=self.status_thread_task, args=())
		self.status_thread.name = "status"
		self.status_thread.daemon = True # thread dies with the program
		self.status_thread.start()


	def status_thread_task(self):
		while not self.exit_flag:
			self.refresh_status()
			if self.wsleds:
				self.update_wsleds()
			sleep(0.2)
		if self.wsleds:
			self.end_wsleds()


	def refresh_status(self):
		try:
			if zynthian_gui_config.show_cpu_status:
				# Get CPU Load
				#self.status_info['cpu_load'] = max(psutil.cpu_percent(None, True))
				self.status_info['cpu_load'] = zynautoconnect.get_jackd_cpu_load()
			else:
				# Get audio peak level
				self.status_info['peakA'] = lib_zynmixer.getDpm(MIXER_MAIN_CHANNEL, 0)
				self.status_info['peakB'] = lib_zynmixer.getDpm(MIXER_MAIN_CHANNEL, 1)
				self.status_info['holdA'] = lib_zynmixer.getDpmHold(MIXER_MAIN_CHANNEL, 0)
				self.status_info['holdB'] = lib_zynmixer.getDpmHold(MIXER_MAIN_CHANNEL, 1)

			# Get Status Flags (once each 5 refreshes)
			if self.status_counter>5:
				self.status_counter = 0

				self.status_info['undervoltage'] = False
				self.status_info['overtemp'] = False
				try:
					if not self.get_throttled_file:
						self.get_throttled_file = open('/sys/devices/platform/soc/soc:firmware/get_throttled')
					self.get_throttled_file.seek(0)
					thr = int('0x%s' % self.get_throttled_file.read(), 16)
					if thr & 0x1:
						self.status_info['undervoltage'] = True
					elif thr & (0x4 | 0x2):
						self.status_info['overtemp'] = True

				except Exception as e:
					logging.error(e)

			else:
				self.status_counter += 1

			# Get Recorder Status
			try:
				self.status_info['midi_recorder'] = self.screens['midi_recorder'].get_status()
			except Exception as e:
				logging.error(e)

			# Refresh On-Screen Status
			try:
				self.screens[self.current_screen].refresh_status(self.status_info)
			except AttributeError:
				pass

			# Clean some status_info
			self.status_info['xrun'] = False
			self.status_info['midi'] = False
			self.status_info['midi_clock'] = False

		except Exception as e:
			logging.exception(e)


	#------------------------------------------------------------------
	# Thread ending on Exit
	#------------------------------------------------------------------


	def wait_threads_end(self, n=20):
		logging.debug("Awaiting threads to end ...")

		while (self.loading_thread.is_alive() or self.status_thread.is_alive() or self.control_thread.is_alive() or zynautoconnect.is_running()) and n>0:
			sleep(0.1)
			n -= 1

		if n<=0:
			logging.error("Reached maximum count! Remaining {} active threads.".format(threading.active_count()))
			return False
		else:
			logging.debug("Remaining {} active threads.".format(threading.active_count()))
			sleep(0.5)
			return True


	def exit(self, code=0):
		self.exit_flag=True
		self.exit_code=code


	#------------------------------------------------------------------
	# Polling
	#------------------------------------------------------------------

	def start_polling(self):
		self.polling=True
		self.zyngine_refresh()
		self.osc_timeout()


	def stop_polling(self):
		self.polling=False


	def after(self, msec, func):
		zynthian_gui_config.top.after(msec, func)


	def zyngine_refresh(self):
		try:
			# Capture exit event and finish
			if self.exit_flag:
				self.stop()
				self.wait_threads_end()
				logging.info("EXITING ZYNTHIAN-UI ...")
				zynthian_gui_config.top.quit()
				return
			# Refresh Current Layer
			elif self.curlayer and not self.loading:
				self.curlayer.refresh()

		except Exception as e:
			self.reset_loading()
			logging.exception(e)

		# Poll
		if self.polling:
			zynthian_gui_config.top.after(160, self.zyngine_refresh)


	def osc_timeout(self):
		self.watchdog_last_check = monotonic()
		for client in list(self.osc_clients):
			if self.osc_clients[client] < self.watchdog_last_check - self.osc_heartbeat_timeout:
				self.osc_clients.pop(client)
				try:
					lib_zynmixer.removeOscClient(ctypes.c_char_p(client.encode('utf-8')))
				except:
					pass
		# Poll
		if self.polling:
			zynthian_gui_config.top.after(self.osc_heartbeat_timeout * 1000, self.osc_timeout)


	#------------------------------------------------------------------
	# All Notes/Sounds Off => PANIC!
	#------------------------------------------------------------------


	def all_sounds_off(self):
		logging.info("All Sounds Off!")
		for chan in range(16):
			lib_zyncore.ui_send_ccontrol_change(chan, 120, 0)


	def all_notes_off(self):
		logging.info("All Notes Off!")
		for chan in range(16):
			lib_zyncore.ui_send_ccontrol_change(chan, 123, 0)


	def raw_all_notes_off(self):
		logging.info("Raw All Notes Off!")
		lib_zyncore.ui_send_all_notes_off()


	def all_sounds_off_chan(self, chan):
		logging.info("All Sounds Off for channel {}!".format(chan))
		lib_zyncore.ui_send_ccontrol_change(chan, 120, 0)


	def all_notes_off_chan(self, chan):
		logging.info("All Notes Off for channel {}!".format(chan))
		lib_zyncore.ui_send_ccontrol_change(chan, 123, 0)


	def raw_all_notes_off_chan(self, chan):
		logging.info("Raw All Notes Off for channel {}!".format(chan))
		lib_zyncore.ui_send_all_notes_off_chan(chan)


	#------------------------------------------------------------------
	# MPE initialization
	#------------------------------------------------------------------

	def init_mpe_zones(self, lower_n_chans, upper_n_chans):
		# Configure Lower Zone
		if not isinstance(lower_n_chans, int) or lower_n_chans<0 or lower_n_chans>0xF:
			logging.error("Can't initialize MPE Lower Zone. Incorrect num of channels ({})".format(lower_n_chans))
		else:
			lib_zyncore.ctrlfb_send_ccontrol_change(0x0, 0x79, 0x0)
			lib_zyncore.ctrlfb_send_ccontrol_change(0x0, 0x64, 0x6)
			lib_zyncore.ctrlfb_send_ccontrol_change(0x0, 0x65, 0x0)
			lib_zyncore.ctrlfb_send_ccontrol_change(0x0, 0x06, lower_n_chans)

		# Configure Upper Zone
		if not isinstance(upper_n_chans, int) or upper_n_chans<0 or upper_n_chans>0xF:
			logging.error("Can't initialize MPE Upper Zone. Incorrect num of channels ({})".format(upper_n_chans))
		else:
			lib_zyncore.ctrlfb_send_ccontrol_change(0xF, 0x79, 0x0)
			lib_zyncore.ctrlfb_send_ccontrol_change(0xF, 0x64, 0x6)
			lib_zyncore.ctrlfb_send_ccontrol_change(0xF, 0x65, 0x0)
			lib_zyncore.ctrlfb_send_ccontrol_change(0xF, 0x06, upper_n_chans)

	#------------------------------------------------------------------
	# MIDI learning
	#------------------------------------------------------------------


	def init_midi_learn(self, zctrl):
		self.midi_learn_zctrl = zctrl
		lib_zyncore.set_midi_learning_mode(1)
		self.screens['control'].refresh_midi_bind()
		self.screens['control'].set_select_path()


	def end_midi_learn(self):
		self.midi_learn_zctrl = None
		lib_zyncore.set_midi_learning_mode(0)
		self.screens['control'].refresh_midi_bind()
		self.screens['control'].set_select_path()


	def refresh_midi_learn(self):
		self.screens['control'].refresh_midi_bind()
		self.screens['control'].set_select_path()


	#------------------------------------------------------------------
	# Autoconnect
	#------------------------------------------------------------------


	def zynautoconnect(self, force=False):
		if force:
			zynautoconnect.midi_autoconnect(True)
			zynautoconnect.audio_autoconnect(True)
		else:
			self.zynautoconnect_midi_flag = True
			self.zynautoconnect_audio_flag = True


	def zynautoconnect_midi(self, force=False):
		if force:
			zynautoconnect.midi_autoconnect(True)
		else:
			self.zynautoconnect_midi_flag = True


	def zynautoconnect_audio(self, force=False):
		if force:
			zynautoconnect.audio_autoconnect(True)
		else:
			self.zynautoconnect_audio_flag = True


	def zynautoconnect_do(self):
		if self.zynautoconnect_midi_flag:
			self.zynautoconnect_midi_flag = False
			zynautoconnect.midi_autoconnect(True)

		if self.zynautoconnect_audio_flag:
			self.zynautoconnect_audio_flag = False
			zynautoconnect.audio_autoconnect(True)


	def zynautoconnect_acquire_lock(self):
		#Get Mutex Lock
		zynautoconnect.acquire_lock()


	def zynautoconnect_release_lock(self):
		#Release Mutex Lock
		zynautoconnect.release_lock()


	#------------------------------------------------------------------
	# Jackd Info
	#------------------------------------------------------------------

	def get_jackd_samplerate(self):
		return zynautoconnect.get_jackd_samplerate()


	def get_jackd_blocksize(self):
		return zynautoconnect.get_jackd_blocksize()


	#------------------------------------------------------------------
	# Zynthian Config Info
	#------------------------------------------------------------------

	def get_zynthian_config(self, varname):
		return eval("zynthian_gui_config.{}".format(varname))


	def allow_rbpi_headphones(self):
		return self.screens['layer'].amixer_layer.engine.allow_rbpi_headphones()


#******************************************************************************
#------------------------------------------------------------------------------
# Start Zynthian!
#------------------------------------------------------------------------------
#******************************************************************************

logging.info("STARTING ZYNTHIAN-UI ...")
zynthian_gui_config.zyngui=zyngui=zynthian_gui()
zyngui.start()


#------------------------------------------------------------------------------
# Zynlib Callbacks
#------------------------------------------------------------------------------

@ctypes.CFUNCTYPE(None, ctypes.c_ubyte, ctypes.c_int)
def zynpot_cb(i, dval):
	#logging.debug("Zynpot {} Callback => {}".format(i, dval))
	try:
		#zyngui.lock.acquire()
		zyngui.screens[zyngui.current_screen].zynpot_cb(i, dval)
		#zyngui.lock.release()

	except Exception as err:
		#zyngui.lock.release()
		logging.exception(err)


lib_zyncore.setup_zynpot_cb(zynpot_cb)


#------------------------------------------------------------------------------
# Reparent Top Window using GTK XEmbed protocol features
#------------------------------------------------------------------------------

def flushflush():
	for i in range(1000):
		print("FLUSHFLUSHFLUSHFLUSHFLUSHFLUSHFLUSH")
	zynthian_gui_config.top.after(200, flushflush)


if zynthian_gui_config.wiring_layout=="EMULATOR":
	top_xid=zynthian_gui_config.top.winfo_id()
	print("Zynthian GUI XID: "+str(top_xid))
	if len(sys.argv)>1:
		parent_xid=int(sys.argv[1])
		print("Parent XID: "+str(parent_xid))
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
	if signo==signal.SIGHUP:
		exit_code = 0
	elif signo==signal.SIGINT:
		exit_code = 100
	elif signo==signal.SIGQUIT:
		exit_code = 102
	elif signo==signal.SIGTERM:
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
