#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Main Class for Zynthian GUI
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

import os
import copy
import liblo
import ctypes
import logging
import importlib
from pathlib import Path
from time import sleep, monotonic
from datetime import datetime
from threading  import Thread, Lock
from subprocess import check_output

import zyncoder
# Zynthian specific modules
import zynconf
import zynautoconnect

from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq

from zyngine import zynthian_zcmidi
from zyngine import zynthian_midi_filter
from zyngine import zynthian_engine_audio_mixer
from zyngine import zynthian_layer

from zyngui import zynthian_gui_config
from zyngui import zynthian_gui_keyboard
from zyngui.zynthian_gui_info import zynthian_gui_info
from zyngui.zynthian_gui_splash import zynthian_gui_splash
from zyngui.zynthian_gui_loading import zynthian_gui_loading
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
from zyngui.zynthian_gui_zs3 import zynthian_gui_zs3
from zyngui.zynthian_gui_zs3_options import zynthian_gui_zs3_options
from zyngui.zynthian_gui_confirm import zynthian_gui_confirm
from zyngui.zynthian_gui_main_menu import zynthian_gui_main_menu
from zyngui.zynthian_gui_chain_menu import zynthian_gui_chain_menu
from zyngui.zynthian_audio_recorder import zynthian_audio_recorder
from zyngui.zynthian_gui_midi_recorder import zynthian_gui_midi_recorder
from zyngui.zynthian_gui_zynpad import zynthian_gui_zynpad
from zyngui.zynthian_gui_arranger import zynthian_gui_arranger
from zyngui.zynthian_gui_patterneditor import zynthian_gui_patterneditor
from zyngui.zynthian_gui_mixer import zynthian_gui_mixer
from zyngui.zynthian_gui_tempo import zynthian_gui_tempo
from zyngui.zynthian_gui_cv_config import zynthian_gui_cv_config
from zyngui.zynthian_gui_touchscreen_calibration import zynthian_gui_touchscreen_calibration
from zyngui.zynthian_gui_control_test import zynthian_gui_control_test
from zyngui import zynthian_gui_keybinding

MIXER_MAIN_CHANNEL = 256 #TODO This constant should go somewhere else

# -------------------------------------------------------------------------------
# Zynthian Main GUI Class
# -------------------------------------------------------------------------------

class zynthian_gui:

	SCREEN_HMODE_NONE = 0
	SCREEN_HMODE_ADD = 1
	SCREEN_HMODE_REPLACE = 2
	SCREEN_HMODE_RESET = 3

	def __init__(self):
		self.test_mode = False
		self.alt_mode = False

		self.power_save_mode = False
		self.last_event_flag = False
		self.last_event_ts = monotonic()
		self.ignore_next_touch_release = False

		self.screens = {}
		self.screen_history = []
		self.current_screen = None
		self.screen_timer_id = None
		
		self.curlayer = None
		self._curlayer = None

		self.dtsw = []

		self.loading = 0
		self.loading_thread = None
		self.control_thread = None
		self.status_thread = None
		self.zynread_wait_flag = False
		self.zynswitch_defered_event = None
		self.zynswitch_cuia_ts = []
		self.exit_flag = False
		self.exit_code = 0
		self.exit_wait_count = 0

		self.zynmidi = None
		self.midi_filter_script = None
		self.midi_learn_mode = False
		self.midi_learn_zctrl = None

		self.status_info = {}
		self.status_counter = 0

		self.zynautoconnect_audio_flag = False
		self.zynautoconnect_midi_flag = False

		self.audio_player = None

		# Create Lock object to avoid concurrence problems
		self.lock = Lock()

		# Init LEDs
		self.init_wsleds()

		# Load keyboard binding map
		zynthian_gui_keybinding.load()

		# Get Jackd Options
		self.jackd_options = zynconf.get_jackd_options()

		# OSC config values
		self.osc_proto = liblo.UDP
		self.osc_server_port = 1370

		# Dictionary of {OSC clients, last heartbeat} registered for mixer feedback
		self.osc_clients = {}
		self.osc_heartbeat_timeout = 120 # Heartbeat timeout period

		# Initialize Wiring MIDI & Switches
		try:
			self.zynmidi = zynthian_zcmidi()
			self.wiring_midi_setup()
			self.zynswitches_init()
		except Exception as e:
			logging.error("ERROR initializing MIDI & Switches: {}".format(e))

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
	# WSLeds Init
	# ---------------------------------------------------------------------------

	def init_wsleds(self):
		if zynthian_gui_config.check_wiring_layout(["Z2"]):
			from zyngui.zynthian_wsleds_z2 import zynthian_wsleds_z2
			self.wsleds = zynthian_wsleds_z2(self)
			self.wsleds.start()
		elif zynthian_gui_config.check_wiring_layout(["V5"]):
			from zyngui.zynthian_wsleds_v5 import zynthian_wsleds_v5
			self.wsleds = zynthian_wsleds_v5(self)
			self.wsleds.start()
		else:
			self.wsleds = None

	# ---------------------------------------------------------------------------
	# Wiring Layout Init & Config
	# ---------------------------------------------------------------------------

	def reload_wiring_layout(self):
		try:
			zynconf.load_config()
			zynthian_gui_config.config_custom_switches()
			zynthian_gui_config.config_zynaptik()
			zynthian_gui_config.config_zyntof()
			self.wiring_midi_setup()
			self.alt_mode = False
		except Exception as e:
			logging.error("ERROR configuring wiring: {}".format(e))


	# Initialize custom switches, analog I/O, TOF sensors, etc.
	def wiring_midi_setup(self, curlayer_chan=None):
		# Configure Custom Switches
		for i, event in enumerate(zynthian_gui_config.custom_switch_midi_events):
			if event is not None:
				swi = 4 + i
				if event['type'] >= 0xF8:
					lib_zyncore.setup_zynswitch_midi(swi, event['type'], 0, 0, 0)
					logging.info("MIDI ZYNSWITCH {}: SYSRT {}".format(swi, event['type']))
				else:
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
					lib_zyncore.zynaptik_setup_cvin(i, event['type'], midi_chan, event['num'])
					logging.info("ZYNAPTIK CV-IN {}: {} CH#{}, {}".format(i, event['type'], midi_chan, event['num']))
				else:
					lib_zyncore.zynaptik_disable_cvin(i)
					logging.info("ZYNAPTIK CV-IN {}: DISABLED!".format(i))

		# Configure Zynaptik Analog Outputs (CV-OUT)
		for i, event in enumerate(zynthian_gui_config.zynaptik_da_midi_events):
			if event is not None:
				if event['chan'] is not None:
					midi_chan = event['chan']
				else:
					midi_chan = curlayer_chan

				if midi_chan is not None:
					lib_zyncore.zynaptik_setup_cvout(i, event['type'], midi_chan, event['num'])
					logging.info("ZYNAPTIK CV-OUT {}: {} CH#{}, {}".format(i, event['type'], midi_chan, event['num']))
				else:
					lib_zyncore.zynaptik_disable_cvout(i)
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


	# ---------------------------------------------------------------------------
	# MIDI Router Init & Config
	# ---------------------------------------------------------------------------

	def init_midi(self):
		try:
			# Set Global Tuning
			self.fine_tuning_freq = zynthian_gui_config.midi_fine_tuning
			lib_zyncore.set_midi_filter_tuning_freq(ctypes.c_double(self.fine_tuning_freq))
			# Set MIDI Master Channel
			lib_zyncore.set_midi_master_chan(zynthian_gui_config.master_midi_channel)
			# Set MIDI CC automode
			lib_zyncore.set_midi_filter_cc_automode(zynthian_gui_config.midi_cc_automode)
			# Setup MIDI filter rules
			if self.midi_filter_script:
				self.midi_filter_script.clean()
			self.midi_filter_script = zynthian_midi_filter.MidiFilterScript(zynthian_gui_config.midi_filter_rules)
			# Setup transport, MIDI clock & sys message options
			self.screens['tempo'].set_transport_clock_source(zynthian_gui_config.transport_clock_source)

		except Exception as e:
			logging.error("ERROR initializing MIDI : {}".format(e))


	def init_midi_services(self):
		# Start/Stop MIDI aux. services
		self.screens['admin'].default_rtpmidi()
		self.screens['admin'].default_qmidinet()
		self.screens['admin'].default_touchosc()
		self.screens['admin'].default_aubionotes()


	def reload_midi_config(self):
		zynconf.load_config()
		midi_profile_fpath = zynconf.get_midi_config_fpath()
		if midi_profile_fpath:
			zynconf.load_config(True, midi_profile_fpath)
			zynthian_gui_config.set_midi_config()
			self.init_midi()
			self.init_midi_services()
			self.zynautoconnect()

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
			self.set_event_flag()
			# Execute action
			cuia = parts[2].upper()
			if self.loading:
				logging.debug("BUSY! Ignoring OSC CUIA '{}' => {}".format(cuia, args))
				return
			self.callable_ui_action(cuia, args)
			# Run autoconnect if needed
			self.zynautoconnect_do()
		elif part1 in ("MIXER", "DAWOSC"):
			self.set_event_flag()
			part2 = parts[2].upper()
			if part2 in ("HEARTBEAT", "SETUP"):
				if src.hostname not in self.osc_clients:
					try:
						if self.zynmixer.add_osc_client(src.hostname) < 0:
							logging.warning("Failed to add OSC client registration {}".format(src.hostname))
							return
					except:
						logging.warning("Error trying to add OSC client registration {}".format(src.hostname))
						return
				self.osc_clients[src.hostname] = monotonic()
				for chan in range(self.zynmixer.get_max_channels()):
					self.zynmixer.enable_dpm(chan, True)
			else:
				if part2[:6] == "VOLUME":
					self.zynmixer.set_level(int(part2[6:]), float(args[0]))
				if  part2[:5] == "FADER":
					self.zynmixer.set_level(int(part2[5:]), float(args[0]))
				if  part2[:5] == "LEVEL":
					self.zynmixer.set_level(int(part2[5:]), float(args[0]))
				elif part2[:7] == "BALANCE":
					self.zynmixer.set_balance(int(part2[7:]), float(args[0]))
				elif part2[:4] == "MUTE":
					self.zynmixer.set_mute(int(part2[4:]), int(args[0]))
				elif part2[:4] == "SOLO":
					self.zynmixer.set_solo(int(part2[4:]), int(args[0]))
				elif part2[:4] == "MONO":
					self.zynmixer.set_mono(int(part2[4:]), int(args[0]))
		else:
			logging.warning("Not supported OSC call '{}'".format(path))

		#for a, t in zip(args, types):
		#	logging.debug("argument of type '%s': %s" % (t, a))

	# ---------------------------------------------------------------------------
	# GUI Core Management
	# ---------------------------------------------------------------------------

	def create_screens(self):
		# Init Auto-connector
		zynautoconnect.start()

		# Create global objects first
		self.audio_recorder = zynthian_audio_recorder()
		self.zynmixer = zynthian_engine_audio_mixer.zynmixer()
		self.zynseq = zynseq.zynseq()

		# Create Core UI Screens
		self.screens['info'] = zynthian_gui_info()
		self.screens['splash'] = zynthian_gui_splash()
		self.screens['loading'] = zynthian_gui_loading()
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
		self.screens['zs3'] = zynthian_gui_zs3()
		self.screens['zs3_options'] = zynthian_gui_zs3_options()
		self.screens['tempo'] = zynthian_gui_tempo()
		self.screens['admin'] = zynthian_gui_admin()
		self.screens['audio_mixer'] = zynthian_gui_mixer()

		# Create the right main menu screen
		if zynthian_gui_config.check_wiring_layout(["Z2", "V5"]):
			self.screens['main_menu'] = zynthian_gui_chain_menu()
		else:
			self.screens['main_menu'] = zynthian_gui_main_menu()

		# Create UI Apps Screens
		self.create_audio_player()
		self.screens['audio_player'] = self.screens['control']
		self.screens['midi_recorder'] = zynthian_gui_midi_recorder()
		self.screens['alsa_mixer'] = self.screens['control']
		self.screens['zynpad'] = zynthian_gui_zynpad()
		self.screens['arranger'] = zynthian_gui_arranger()
		self.screens['pattern_editor'] = zynthian_gui_patterneditor()
		self.screens['touchscreen_calibration'] = zynthian_gui_touchscreen_calibration()
		self.screens['control_test'] = zynthian_gui_control_test()

		# Create Zynaptik-related screens
		try:
			if callable(lib_zyncore.init_zynaptik):
				self.screens['cv_config'] = zynthian_gui_cv_config()
		except:
			pass

		# Initialize OSC
		self.osc_init()

		# Loading screen
		self.show_loading("starting user interface ...")

		# Start polling & threads
		self.start_polling()
		self.start_loading_thread()
		self.start_control_thread()
		self.start_status_thread()


	#--------------------------------------------------------------------------
	# Start task => Must run as a thread, so we can go into tkinter loop
	#**************************************************************************

	def run_start_thread(self):
		self.start_thread = Thread(target=self.start_task, args=())
		self.start_thread.name = "start"
		self.start_thread.daemon = True # thread dies with the program
		self.start_thread.start()


	def start_task(self):
		self.start_loading()

		snapshot_loaded = False
		# Control Test enabled ...
		if zynthian_gui_config.control_test_enabled:
			init_screen = "control_test"
		else:
			init_screen = "main_menu"
			# Try to load "last_state" snapshot ...
			if zynthian_gui_config.restore_last_state:
				snapshot_loaded = self.screens['snapshot'].load_last_state_snapshot()
			# Try to load "default" snapshot ...
			if not snapshot_loaded:
				snapshot_loaded = self.screens['snapshot'].load_default_snapshot()

		if snapshot_loaded:
			init_screen = "audio_mixer"
		else:
			# Add main mixbus chain in case no valid snapshot is loaded
			self.screens['layer'].add_layer_eng = "AI"
			self.screens['layer'].add_layer_midich(256, False)
			self.screens['layer'].refresh()
			# Init MIDI Subsystem => MIDI Profile
			self.init_midi()
			self.init_midi_services()
			self.zynautoconnect()

		# Show initial screen
		self.show_screen(init_screen, self.SCREEN_HMODE_RESET)

		self.stop_loading()

		# Run autoconnect if needed
		self.zynautoconnect_do()


	def stop(self):
		logging.info("STOPPING ZYNTHIAN-UI ...")
		zynautoconnect.stop()
		self.screens['layer'].reset()
		self.screens['midi_recorder'].stop_playing() # Need to stop timing thread
		self.zynseq.transport_stop("ALL")


	def hide_screens(self, exclude=None):
		if not exclude:
			exclude = self.current_screen
		exclude_obj = self.screens[exclude]

		for screen_name, screen_obj in self.screens.items():
			if screen_obj != exclude_obj:
				screen_obj.hide()


	def show_screen(self, screen=None, hmode=SCREEN_HMODE_ADD):
		self.cancel_screen_timer()

		if screen is None:
			if self.current_screen:
				screen = self.current_screen
			else:
				screen = "audio_mixer"

		if screen == "control":
			self.restore_curlayer()

		elif screen == "alsa_mixer":
			if self.screens['layer'].amixer_layer:
				self.screens['layer'].amixer_layer.refresh_controllers()
				self.set_curlayer(self.screens['layer'].amixer_layer, save=True, populate_screens=False)
			else:
				return
		elif screen == "audio_player":
			if self.audio_player:
				self.set_curlayer(self.audio_player, save=True, populate_screens=False)
			else:
				logging.error("Audio Player not created!")
				return

		if screen not in ("bank", "preset", "option"):
			self.screens['layer'].restore_presets()

		self.screens[screen].build_view()
		self.hide_screens(exclude=screen)
		if hmode == zynthian_gui.SCREEN_HMODE_ADD:
			if len(self.screen_history) == 0 or self.screen_history[-1] != screen:
				self.purge_screen_history(screen)
				self.screen_history.append(screen)
		elif hmode == zynthian_gui.SCREEN_HMODE_REPLACE:
			self.screen_history.pop()
			self.purge_screen_history(screen)
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

		if last_screen in self.screens:
			logging.debug("CLOSE SCREEN '{}' => Back to '{}'".format(self.current_screen, last_screen))
			self.show_screen(last_screen)
		else:
			self.hide_screens()


	def close_modal(self):
		self.close_screen()


	def purge_screen_history(self, screen):
		self.screen_history = list(filter(lambda i: i != screen, self.screen_history))


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
		if screen == 'preset' and len(self.curlayer.preset_list) <= 1:
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


	def show_loading(self, title="", details=""):
		self.screens['loading'].set_title(title)
		self.screens['loading'].set_details(details)
		self.screens['loading'].show()
		self.current_screen = 'loading'
		self.hide_screens(exclude='loading')


	def show_loading_error(self, title="", details=""):
		self.screens['loading'].set_error(title)
		self.screens['loading'].set_details(details)
		self.screens['loading'].show()
		self.current_screen = 'loading'
		self.hide_screens(exclude='loading')


	def show_loading_warning(self, title="", details=""):
		self.screens['loading'].set_warning(title)
		self.screens['loading'].set_details(details)
		self.screens['loading'].show()
		self.current_screen = 'loading'
		self.hide_screens(exclude='loading')


	def show_loading_success(self, title="", details=""):
		self.screens['loading'].set_warning(title)
		self.screens['loading'].set_details(details)
		self.screens['loading'].show()
		self.current_screen = 'loading'
		self.hide_screens(exclude='loading')


	def set_loading_title(self, title):
		self.screens['loading'].set_title(title)


	def set_loading_error(self, title):
		self.screens['loading'].set_error(title)


	def set_loading_warning(self, title):
		self.screens['loading'].set_waning(title)


	def set_loading_success(self, title):
		self.screens['loading'].set_success(title)


	def set_loading_details(self, details):
		self.screens['loading'].set_details(details)


	def calibrate_touchscreen(self):
		self.show_screen('touchscreen_calibration')


	def layer_control(self, layer=None):
		if layer is not None:
			if layer in self.screens['layer'].root_layers:
				self._curlayer = None
			elif self.curlayer != layer:
				self._curlayer = self.curlayer

			self.set_curlayer(layer)

		if self.curlayer:
			control_screen_name = 'control'

			# Check for a custom GUI
			module_path = self.curlayer.engine.custom_gui_fpath
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

			# If Empty Audio Input layer => Add Audio-FX
			if self.curlayer.engine.nickname == "AI" and not self.screens['layer'].get_fxchain_downstream(self.curlayer):
				self.show_screen_reset('audio_mixer')
				self.screens['layer'].add_fxchain_layer(self.curlayer)
			# If a preset is selected => control screen
			elif self.curlayer.get_preset_name():
				self.show_screen_reset(control_screen_name)
			# If not => bank/preset selector screen
			else:
				self.curlayer.load_bank_list()
				if len(self.curlayer.bank_list) > 1:
					self.show_screen_reset('bank')
				else:
					self.curlayer.set_bank(0)
					self.curlayer.load_preset_list()
					if len(self.curlayer.preset_list) > 1:
						self.show_screen_reset('preset')
					else:
						if len(self.curlayer.preset_list):
							self.curlayer.set_preset(0)
						self.show_screen_reset(control_screen_name)
		

	def show_control(self):
		self.restore_curlayer()
		self.layer_control()


	def show_control_xy(self, xctrl, yctrl):
		self.screens['control_xy'].set_controllers(xctrl, yctrl)
		self.screens['control_xy'].show()
		self.current_screen = 'control'
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


	def set_curlayer(self, layer, save=False, populate_screens=True):
		if layer is not None:
			if self.curlayer != layer:
				#if save and not self.is_shown_alsa_mixer():
				if save and self.curlayer in self.screens['layer'].layers:
					self._curlayer = self.curlayer
				self.curlayer = layer
			if populate_screens:
				self.screens['layer'].refresh_index()
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
			if self.curlayer.engine.nickname == 'MX':
				return
			curlayer_chan = self.curlayer.get_midi_chan()
			if zynthian_gui_config.midi_single_active_channel and curlayer_chan is not None:
				if curlayer_chan >= 16:
					return
				active_chan = curlayer_chan
				cur_active_chan = lib_zyncore.get_midi_active_chan()
				if cur_active_chan == active_chan:
					return
				logging.debug("ACTIVE CHAN: {} => {}".format(cur_active_chan, active_chan))
				#if cur_active_chan >= 0:
				#	self.all_notes_off_chan(cur_active_chan)

		lib_zyncore.set_midi_active_chan(active_chan)
		self.wiring_midi_setup(curlayer_chan)


	def get_curlayer_wait(self):
		# Try until layer is ready
		for j in range(100):
			if self.curlayer:
				return self.curlayer
			else:
				sleep(0.1)


	def is_single_active_channel(self):
		return zynthian_gui_config.midi_single_active_channel


	def clean_all(self):
		self.show_loading("cleaning all")
		if len(self.screens['layer'].layers) > 0:
			self.screens['snapshot'].save_last_state_snapshot()
		self.screens['layer'].reset()
		self.screens['layer'].add_layer_engine("AI", 256)
		self.zynmixer.reset_state()
		self.zynseq.load("")
		self.show_screen_reset('main_menu')


	def create_audio_player(self):
		if not self.audio_player:
			try:
				zyngine = self.screens['engine'].start_engine('AP')
				self.audio_player = zynthian_layer(zyngine, 16, None)
				zynautoconnect.audio_connect_aux(self.audio_player.jackname)
			except Exception as e:
				logging.error("Can't create global Audio Player instance")


	def destroy_audio_player(self):
		if self.audio_player:
			try:
				self.audio_player.engine.del_layer(self.audio_player)
				self.audio_player = None
				self.screens['engine'].stop_unused_engines()
			except Exception as e:
				logging.error("Can't destroy global Audio Player instance")


	def start_audio_player(self):
		filename = self.audio_recorder.filename
		if filename and os.path.exists(filename):
			self.audio_player.engine.set_preset(self.audio_player, [filename])
			self.audio_player.engine.player.set_position(self.audio_player.handle, 0.0)
			self.audio_player.engine.player.start_playback(self.audio_player.handle)
			self.audio_recorder.filename = None
		elif (self.audio_player.preset_name and os.path.exists(self.audio_player.preset_info[0])) or self.audio_player.engine.player.get_filename(self.audio_player.handle):
			self.audio_player.engine.player.start_playback(self.audio_player.handle)
		else:
			self.audio_player.reset_preset()
			self.cuia_audio_file_list()

	def stop_audio_player(self):
		self.audio_player.engine.player.stop_playback(self.audio_player.handle)

	# ------------------------------------------------------------------
	# MIDI learning
	# ------------------------------------------------------------------

	def enter_midi_learn(self):
		if not self.midi_learn_mode:
			logging.debug("ENTER LEARN")
			self.midi_learn_mode = True
			self.midi_learn_zctrl = None
			lib_zyncore.set_midi_learning_mode(1)
			try:
				logging.debug("ENTER LEARN => {}".format(self.current_screen))
				self.screens[self.current_screen].enter_midi_learn()
			except Exception as e:
				logging.debug(e)
				pass


	def exit_midi_learn(self):
		if self.midi_learn_mode or self.midi_learn_zctrl:
			self.midi_learn_mode = False
			self.midi_learn_zctrl = None
			lib_zyncore.set_midi_learning_mode(0)
			try:
				self.screens[self.current_screen].exit_midi_learn()
			except:
				pass


	def toggle_midi_learn(self):
		try:
			self.screens[self.current_screen].toggle_midi_learn()
		except:
			if self.midi_learn_mode:
				self.exit_midi_learn()
			else:
				self.enter_midi_learn()


	def init_midi_learn_zctrl(self, zctrl):
		self.midi_learn_zctrl = zctrl
		lib_zyncore.set_midi_learning_mode(1)


	def refresh_midi_learn_zctrl(self):
		self.screens['control'].refresh_midi_bind()
		self.screens['control'].set_select_path()

	# -------------------------------------------------------------------
	# Callable UI Actions
	# -------------------------------------------------------------------

	@classmethod
	def get_cuia_list(cls):
		return [method[5:].upper() for method in dir(cls) if method.startswith('cuia_') is True]

	def callable_ui_action(self, cuia, params=None):
		logging.debug("CUIA '{}' => {}".format(cuia, params))
		cuia_func = getattr(self, "cuia_" + cuia.lower(), None)
		if callable(cuia_func):
			cuia_func(params)
		else:
			logging.error("Unknown CUIA '{}'".format(cuia))

	def parse_cuia_params(self, params_str):
		params = []
		for i, p in enumerate(params_str.split(",")):
			try:
				params.append(int(p))
			except:
				params.append(p.strip())
		return params

	def callable_ui_action_params(self, cuia_str):
		parts = cuia_str.split(" ", 2)
		cuia = parts[0]
		if len(parts) > 1:
			params = self.parse_cuia_params(parts[1])
		else:
			params = None
		self.callable_ui_action(cuia, params)

	# System actions CUIA
	def cuia_test_mode(self, params):
		self.test_mode = params
		logging.warning('TEST_MODE: {}'.format(params))

	def cuia_toggle_alt_mode(self, params=None):
		if self.alt_mode:
			self.alt_mode = False
		else:
			self.alt_mode = True

	def cuia_power_off(self, params=None):
		self.screens['admin'].power_off_confirmed()

	def cuia_reboot(self, params=None):
		self.screens['admin'].reboot_confirmed()

	def cuia_restart_ui(self, params=None):
		self.screens['admin'].restart_gui()

	def cuia_exit_ui(self, params=None):
		self.screens['admin'].exit_to_console()

	def cuia_reload_wiring_layout(self, params=None):
		self.reload_wiring_layout()

	def cuia_reload_midi_config(self, params=None):
		self.reload_midi_config()

	def cuia_reload_key_binding(self, params=None):
		zynthian_gui_keybinding.load()

	def cuia_last_state_action(self, params=None):
		self.screens['admin'].last_state_action()

	# Panic Actions
	def cuia_all_notes_off(self, params=None):
		self.all_notes_off()
		sleep(0.1)
		self.raw_all_notes_off()

	def cuia_all_sounds_off(self, params=None):
		self.all_notes_off()
		self.all_sounds_off()
		sleep(0.1)
		self.raw_all_notes_off()

	def cuia_clean_all(self, params=None):
		if params == ['CONFIRM']:
			self.clean_all()
			self.show_screen_reset('main_menu') #TODO: Should send signal so that UI can react

	# Audio & MIDI Recording/Playback actions
	def cuia_start_audio_record(self, params=None):
		self.audio_player.controllers_dict['record'].set_value("recording")

	def cuia_stop_audio_record(self, params=None):
		self.audio_player.controllers_dict['record'].set_value("stopped")

	def cuia_toggle_audio_record(self, params=None):
		if self.audio_recorder.get_status():
			self.audio_player.controllers_dict['record'].set_value("stopped")
		else:
			self.audio_player.controllers_dict['record'].set_value("recording")

	def cuia_start_audio_play(self, params=None):
		self.start_audio_player()

	def cuia_stop_audio_play(self, params=None):
		self.stop_audio_player()
		self.audio_player.engine.player.set_position(self.audio_player.handle, 0.0)

	def cuia_toggle_audio_play(self, params=None):
		if self.audio_player.engine.player.get_playback_state(self.audio_player.handle):
			self.stop_audio_player()
		else:
			self.start_audio_player()

	def cuia_audio_file_list(self, params=None):
		self.show_screen("audio_player")
		self.show_screen('bank')
		#self.replace_screen('bank')
		if len(self.audio_player.bank_list) == 1 or self.audio_player.bank_name:
			self.screens['bank'].click_listbox()

	def cuia_start_midi_record(self, params=None):
		self.screens['midi_recorder'].start_recording()

	def cuia_stop_midi_record(self, params=None):
		self.screens['midi_recorder'].stop_recording()
		if self.current_screen == "midi_recorder":
			self.screens['midi_recorder'].select()

	def cuia_toggle_midi_record(self, params=None):
		self.screens['midi_recorder'].toggle_recording()
		if self.current_screen == "midi_recorder":
			self.screens['midi_recorder'].select()

	def cuia_start_midi_play(self, params=None):
		self.screens['midi_recorder'].start_playing()

	def cuia_stop_midi_play(self, params=None):
		self.screens['midi_recorder'].stop_playing()

	def cuia_toggle_midi_play(self, params=None):
		self.screens['midi_recorder'].toggle_playing()

	def cuia_toggle_record(self, params=None):
		cuia_func = getattr(self.get_current_screen_obj(), "cuia_toggle_record", None)
		if callable(cuia_func):
			cuia_func()
		elif self.alt_mode:
			self.cuia_toggle_midi_record()
		else:
			self.cuia_toggle_audio_record()

	def cuia_stop(self, params=None):
		cuia_func = getattr(self.get_current_screen_obj(), "cuia_stop", None)
		if callable(cuia_func):
			cuia_func()
		elif self.alt_mode:
			self.cuia_stop_midi_play()
		else:
			self.cuia_stop_audio_play()

	def cuia_toggle_play(self, params=None):
		cuia_func = getattr(self.get_current_screen_obj(), "cuia_toggle_play", None)
		if callable(cuia_func):
			cuia_func()
		elif self.alt_mode:
			self.cuia_toggle_midi_play()
		else:
			self.cuia_toggle_audio_play()

	def cuia_tempo(self, params=None):
		self.screens["tempo"].tap()
		if self.current_screen != "tempo":
			self.show_screen("tempo")

	def cuia_set_tempo(self, params):
		try:
			self.zynseq.set_tempo(params[0])
		except (AttributeError, TypeError) as err:
			pass

	def cuia_tempo_up(self, params):
		if params:
			try:
				self.zynseq.set_tempo(self.zynseq.get_tempo() + params[0])
			except (AttributeError, TypeError) as err:
				pass
		else:
			self.zynseq.set_tempo(self.zynseq.get_tempo() + 1)

	def cuia_tempo_down(self, params):
		if params:
			try:
				self.zynseq.set_tempo(self.zynseq.get_tempo() - params[0])
			except (AttributeError, TypeError) as err:
				pass
		else:
			self.zynseq.set_tempo(self.zynseq.get_tempo() - 1)

	def cuia_tap_tempo(self, params=None):
		self.screens["tempo"].tap()

	# Zynpot & Zynswitch emulation CUIAs (low level)
	def cuia_zynpot(self, params):
		try:
			i = params[0]
			d = params[1]
		except Exception as e:
			logging.error("Need 2 parameters: index, delta")

		try:
			self.get_current_screen_obj().zynpot_cb(i, d)
		except Exception as e:
			logging.error(e)

	def cuia_zynswitch(self, params):
		try:
			i = params[0]
			t = params[1]
		except Exception as err:
			logging.error("Need 2 parameters: index, action_type")
			return

		if t == 'P':
			self.zynswitch_cuia_ts[i] = datetime.now()
			self.zynswitch_timing(i, 0)
		elif t == 'R':
			if self.zynswitch_cuia_ts[i]:
				dtus = int(1000000 * (datetime.now() - self.zynswitch_cuia_ts[i]).total_seconds())
				self.zynswitch_cuia_ts[i] = None
				self.zynswitch_timing(i, dtus)
		elif t == 'S':
			self.zynswitch_cuia_ts[i] = None
			self.zynswitch_short(i)
		elif t == 'B':
			self.zynswitch_cuia_ts[i] = None
			self.zynswitch_bold(i)
		elif t == 'L':
			self.zynswitch_cuia_ts[i] = None
			self.zynswitch_long(i)
		else:
			self.zynswitch_cuia_ts[i] = None
			logging.warning("Unknown Action Type: {}".format(t))

	# Basic UI-Control CUIAs
	# 4 x Arrows
	def cuia_arrow_up(self, params=None):
		try:
			self.get_current_screen_obj().arrow_up()
		except (AttributeError, TypeError) as err:
			pass

	def	cuia_arrow_down(self, params=None):
		try:
			self.get_current_screen_obj().arrow_down()
		except (AttributeError, TypeError) as err:
			pass

	def cuia_arrow_right(self, params=None):
		try:
			self.get_current_screen_obj().arrow_right()
		except (AttributeError, TypeError) as err:
			pass

	def cuia_arrow_left(self, params=None):
		try:
			self.get_current_screen_obj().arrow_left()
		except (AttributeError, TypeError) as err:
			pass

	cuia_arrow_next = cuia_arrow_right
	cuia_arrow_prev = cuia_arrow_left

	# Back action
	def cuia_back(self, params=None):
		try:
			self.back_screen()
		except:
			pass

	# Select element in list => it receives an integer parameter!
	def cuia_select(self, params):
		try:
			self.get_current_screen_obj().select(params[0])
		except (AttributeError, TypeError) as err:
			pass

	# Screen/Mode management CUIAs
	def cuia_toggle_screen(self, params):
		if params:
			self.toggle_screen(params[0])

	def cuia_show_screen(self, params):
		if params:
			self.show_screen_reset(params[0])

	def cuia_screen_main_menu(self, params=None):
		self.toggle_screen("main_menu")

	def cuia_screen_admin(self, params=None):
		self.toggle_screen("admin")

	def cuia_screen_audio_mixer(self, params=None):
		self.toggle_screen("audio_mixer")

	def cuia_screen_snapshot(self, params=None):
		self.toggle_screen("snapshot")

	def cuia_screen_zs3(self, params=None):
		self.toggle_screen("zs3")

	def cuia_screen_midi_recorder(self, params=None):
		self.toggle_screen("midi_recorder")

	def cuia_screen_alsa_mixer(self, params):
		self.toggle_screen("alsa_mixer", hmode=zynthian_gui.SCREEN_HMODE_RESET)

	def cuia_screen_zynpad(self, params=None):
		self.toggle_screen("zynpad")

	def cuia_screen_pattern_editor(self, params=None):
		success = False
		if self.current_screen in ["arranger", "zynpad"]:
			success = self.screens[self.current_screen].show_pattern_editor()
		if not success:
			self.toggle_screen("pattern_editor")

	def cuia_screen_arranger(self, params=None):
		self.toggle_screen("arranger")

	def cuia_screen_bank(self, params=None):
		self.toggle_screen("bank")

	def cuia_screen_preset(self, params=None):
		self.toggle_screen("preset")

	def cuia_screen_calibrate(self, params=None):
		self.calibrate_touchscreen()

	def cuia_chain_control(self, params=None):
		if params:
			try:
				i = params[0] - 1
				n = self.screens['layer'].get_num_root_layers()
				main_fxchain = self.screens['layer'].get_main_fxchain_root_layer()
				if main_fxchain:
					n -= 1
				if i >= 0 and i < n:
					self.layer_control(self.screens['layer'].root_layers[i])
				elif i < 0 and main_fxchain:
					self.layer_control(main_fxchain)
			except Exception as e:
				logging.warning("Can't change to layer {}! => {}".format(params[0], e))
		else:
			self.layer_control()

	cuia_layer_control = cuia_chain_control
	cuia_screen_control = cuia_chain_control

	def cuia_chain_options(self, params=None):
		try:
			if params:
				i = params[0] - 1
				n = self.screens['layer'].get_num_root_layers()
				main_fxchain = self.screens['layer'].get_main_fxchain_root_layer()
				if main_fxchain:
					n -= 1
				if i >= 0 and i < n:
					self.screens['layer'].select(i)
				elif i < 0 and main_fxchain:
					self.screens['layer'].select(n)
			self.screens['layer_options'].reset()
			self.toggle_screen('layer_options', hmode=zynthian_gui.SCREEN_HMODE_ADD)
		except Exception as e:
			logging.warning("Can't show options for layer ({})! => {}".format(params, e))

	cuia_layer_options = cuia_chain_options

	def cuia_menu(self, params=None):
		if self.current_screen != "alsa_mixer":
			toggle_menu_func = getattr(self.screens[self.current_screen], "toggle_menu", None)
			if callable(toggle_menu_func):
				toggle_menu_func()
				return
		self.toggle_screen("main_menu", hmode=zynthian_gui.SCREEN_HMODE_ADD)

	def cuia_bank_preset(self, params=None):
		if params:
			try:
				self.set_curlayer(params, True)
			except:
				logging.error("Can't set layer passed as CUIA parameter!")
		elif self.current_screen == 'control':
			try:
				self.set_curlayer(self.screens['control'].screen_layer, True)
			except:
				logging.warning("Can't set control screen layer! ")

		if self.current_screen == 'preset':
			if len(self.curlayer.bank_list) > 1:
				self.replace_screen('bank')
			else:
				self.close_screen()
		elif self.current_screen == 'bank':
			#self.replace_screen('preset')
			self.close_screen()
		elif self.curlayer:
			if len(self.curlayer.preset_list) > 0 and self.curlayer.preset_list[0][0] != '':
				self.screens['preset'].index = self.curlayer.get_preset_index()
				self.show_screen('preset', hmode=zynthian_gui.SCREEN_HMODE_ADD)
			elif len(self.curlayer.bank_list) > 0 and self.curlayer.bank_list[0][0] != '':
				self.show_screen('bank', hmode=zynthian_gui.SCREEN_HMODE_ADD)
			else:
				self.restore_curlayer()

	cuia_preset = cuia_bank_preset

	def cuia_preset_fav(self, params=None):
		self.show_favorites()

	def cuia_enter_midi_learn(self, params=None):
		self.enter_midi_learn()

	def cuia_exit_midi_learn(self, params=None):
		self.exit_midi_learn()

	def cuia_toggle_midi_learn(self, params=None):
		self.toggle_midi_learn()

	def cuia_action_midi_unlearn(self, params=None):
		try:
			self.screens[self.current_screen].midi_unlearn_action()
		except (AttributeError, TypeError) as err:
			pass

	# Learn control options
	def cuia_midi_learn_control_options(self, params):
		if self.current_screen in ("control", "alsa_mixer"):
			self.screens[self.current_screen].midi_learn_options(params[0])

	# Learn control
	def cuia_midi_learn_control(self, params):
		if self.current_screen in ("control", "alsa_mixer"):
			self.screens[self.current_screen].midi_learn(params[0])

	# Unlearn control
	def cuia_midi_unlearn_control(self, params=None):
		if self.current_screen in ("control", "alsa_mixer"):
			if params:
				self.midi_learn_zctrl = self.screens[self.current_screen].get_zcontroller(params[0])
			# if not parameter, unlearn selected learning control
			if self.midi_learn_zctrl:
				self.screens[self.current_screen].midi_unlearn_action()

	# Unlearn all mixer controls
	def cuia_midi_unlearn_mixer(self, params=None):
		try:
			self.screens['audio_mixer'].midi_unlearn_all()
		except (AttributeError, TypeError) as err:
			logging.error(err)

	def cuia_midi_unlearn_node(self, params=None):
		try:
			self.screens['control'].screen_layer.midi_unlearn()
		except (AttributeError, TypeError) as err:
			logging.error(err)

	def cuia_midi_unlearn_chain(self, params=None):
		try:
			self.screens['layer'].midi_unlearn()
		except (AttributeError, TypeError) as err:
			logging.error(err)

	# Z2 knob touch
	def cuia_z2_zynpot_touch(self, params):
		if params:
			self.screens['control'].midi_learn_zctrl(params[0])

	# V5 knob click
	def cuia_v5_zynpot_switch(self, params):
		i = params[0]
		t = params[1].upper()

		if self.current_screen in ("control", "alsa_mixer"):
			#if i < 3 and t == 'S':
			if t == 'S':
				self.screens[self.current_screen].midi_learn(i)
				return
			elif t == 'B':
				self.screens[self.current_screen].midi_learn_options(i)
				return
		elif self.current_screen == "audio_mixer":
			if t == 'S':
				self.zynswitch_short(i)
				return
			elif i == 2 and t == 'B':
				self.screens["audio_mixer"].midi_learn_menu()
				return
		elif self.current_screen == "zynpad":
			if i == 2 and t == 'S':
				self.zynswitch_short(i)
				return
		if i == 3:
			if t == 'S':
				self.zynswitch_short(i)
				return
			elif t == 'B':
				self.zynswitch_bold(i)
				return


	# MIDI CUIAs
	def cuia_program_change(self, params):
		if len(params) > 0:
			pgm = int(params[0])
			if len(params) > 1:
				chan = int(params[1])
			else:
				chan = lib_zyncore.get_midi_active_chan()
			if chan >= 0 and chan < 16 and pgm >= 0 and pgm < 128:
				lib_zyncore.write_zynmidi_program_change(chan, pgm)

	# Common methods to control views derived from zynthian_gui_base
	def cuia_show_topbar(self, params=None):
		try:
			self.screens[self.current_screen].show_topbar(True)
		except (AttributeError, TypeError) as err:
			pass

	def cuia_hide_topbar(self, params=None):
		try:
			self.screens[self.current_screen].show_topbar(False)
		except (AttributeError, TypeError) as err:
			pass

	def cuia_show_buttonbar(self, params=None):
		try:
			self.screens[self.current_screen].show_buttonbar(True)
		except (AttributeError, TypeError) as err:
			pass

	def cuia_hide_buttonbar(self, params=None):
		try:
			self.screens[self.current_screen].show_buttonbar(False)
		except (AttributeError, TypeError) as err:
			pass

	def cuia_show_sidebar(self, params=None):
		try:
			self.screens[self.current_screen].show_sidebar(True)
		except (AttributeError, TypeError) as err:
			pass

	def cuia_hide_sidebar(self, params=None):
		try:
			self.screens[self.current_screen].show_sidebar(False)
		except (AttributeError, TypeError) as err:
			pass

	def cuia_zynaptik_cvin_set_volts_octave(self, params):
		try:
			lib_zyncore.zynaptik_cvin_set_volts_octave(float(params[0]))
		except Exception as err:
			logging.debug(err)

	def cuia_zynaptik_cvin_set_note0(self, params):
		try:
			lib_zyncore.zynaptik_cvin_set_note0(int(params[0]))
		except Exception as err:
			logging.debug(err)

	def cuia_zynaptik_cvout_set_volts_octave(self, params):
		try:
			lib_zyncore.zynaptik_cvout_set_volts_octave(float(params[0]))
		except Exception as err:
			logging.debug(err)

	def cuia_zynaptik_cvout_set_note0(self, params):
		try:
			lib_zyncore.zynaptik_cvout_set_note0(int(params[0]))
		except Exception as err:
			logging.debug(err)

	def refresh_signal(self, sname):
		try:
			self.screens[self.current_screen].refresh_signal(sname)
		except (AttributeError, TypeError) as err:
			pass

	def custom_switch_ui_action(self, i, t):
		action_config = zynthian_gui_config.custom_switch_ui_actions[i]
		if not action_config:
			return

		if t == "S" and self.check_current_screen_switch(action_config):
			cuia = action_config['B']
			if cuia:
				self.callable_ui_action_params(cuia)
				return

		if self.alt_mode:
			at = "A" + t
			if at in action_config:
				cuia = action_config[at]
				if cuia:
					self.callable_ui_action_params(cuia)
					return

		if t in action_config:
			cuia = action_config[t]
			if cuia:
				self.callable_ui_action_params(cuia)


	def is_current_screen_menu(self):
		if self.current_screen in ("main_menu", "engine", "midi_cc", "midi_chan", "midi_key_range", "audio_in", "audio_out", "midi_out", "midi_prog") or \
				self.current_screen.endswith("_options"):
			return True
		if self.current_screen == "option" and len(self.screen_history) > 1 and self.screen_history[-2] in ("zynpad", "pattern_editor", "preset", "bank"):
			return True
		return False


	def check_current_screen_switch(self, action_config):
		# BIG ÑAPA!!
		if action_config['B'] and action_config['B'].lower() == 'bank_preset' and self.current_screen in ("bank", "preset", "audio_player"):
			return True
		#if self.is_current_screen_menu():
		if self.current_screen == "main_menu":
			screen_name = "menu"
		else:
			screen_name = self.current_screen
		if action_config['S'] and action_config['S'].lower().endswith(screen_name):
			return True
		return False


	# -------------------------------------------------------------------
	# Zynswitch Event Management
	# -------------------------------------------------------------------

	# Init Standard Zynswitches
	def zynswitches_init(self):
		logging.info("INIT {} ZYNSWITCHES ...".format(zynthian_gui_config.num_zynswitches))
		self.dtsw = [datetime.now()] * (zynthian_gui_config.num_zynswitches + 4)
		self.zynswitch_cuia_ts = [None] * (zynthian_gui_config.num_zynswitches + 4)

	def zynswitches(self):
		i = 0
		while i <= zynthian_gui_config.last_zynswitch_index:
			if i < 4 or zynthian_gui_config.custom_switch_ui_actions[i-4]:
				dtus = lib_zyncore.get_zynswitch(i, zynthian_gui_config.zynswitch_long_us)
				self.zynswitch_timing(i, dtus)
			i += 1

	def zynswitch_timing(self, i, dtus):
		if dtus < 0:
			pass
		elif dtus == 0:
			self.zynswitch_push(i)
		elif dtus > zynthian_gui_config.zynswitch_long_us:
			self.zynswitch_long(i)
		elif dtus > zynthian_gui_config.zynswitch_bold_us:
			# Double switches must be bold
			if not self.zynswitch_double(i):
				self.zynswitch_bold(i)
		elif dtus > 0:
			self.zynswitch_short(i)


	def zynswitch_push(self, i):
		self.set_event_flag()

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
			#logging.debug('Push Switch ' + str(i))
			self.start_loading()
			self.custom_switch_ui_action(i-4, "P")
			self.stop_loading()


	def zynswitch_long(self, i):
		logging.debug('Looooooooong Switch '+str(i))
		self.start_loading()

		# Standard 4 ZynSwitches
		if i == 0:
			self.show_screen_reset("admin")

		elif i == 1:
			self.cuia_all_sounds_off()

		elif i == 2:
			self.show_screen_reset("zynpad")

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
			self.show_screen('main_menu')

		elif i == 1:
			try:
				self.screens[self.current_screen].disable_param_editor()
			except:
				pass
			self.restore_curlayer()
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
			self.cuia_menu()

		elif i == 1:
			self.back_screen()

		elif i == 2:
			self.toggle_midi_learn()

		elif i == 3:
			self.screens[self.current_screen].switch_select('S')

		# Custom ZynSwitches
		elif i >= 4:
			self.custom_switch_ui_action(i-4, "S")

		self.stop_loading()


	def zynswitch_double(self, i):
		self.dtsw[i] = datetime.now()
		for j in range(4):
			if j == i: continue
			if abs((self.dtsw[i] - self.dtsw[j]).total_seconds()) < 0.3:
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
		if self.current_screen in ("control", "alsa_mixer") and self.screens[self.current_screen].mode == 'control':
			self.screens['control'].midi_learn(i)


	def zynswitch_Y(self,i):
		logging.debug('Y Switch %d' % i)
		if self.current_screen in ("control", "alsa_mixer") and self.screens[self.current_screen].mode == 'control':
			self.screens['control'].midi_learn_options(i, unlearn_only=True)


	def midi_unlearn_options_cb(self, option, param):
		self.screens['control'].midi_unlearn(param)


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

		#self.reset_loading()


	#------------------------------------------------------------------
	# MIDI processing
	#------------------------------------------------------------------

	def zynmidi_read(self):
		try:
			while True:
				ev = lib_zyncore.read_zynmidi()
				if ev == 0:
					break

				#logging.info("MIDI_UI MESSAGE: {}".format(hex(ev)))

				if self.screens['zynpad'].midi_event(ev):
					self.status_info['midi'] = True
					self.last_event_flag = True
					continue

				evtype = (ev & 0xF00000) >> 20
				chan = (ev & 0x0F0000) >> 16
				#logging.info("UI-MIDI MESSAGE: DEV#{} CH#{} => {}".format(idev, chan, evtype))

				# System Messages (Common & RT)
				if evtype == 0xF:
					# Clock
					if chan == 0x8:
						self.status_info['midi_clock'] = True
						continue
					# Tick
					elif chan == 0x9:
						continue
					# Active Sense
					elif chan == 0xE:
						continue
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
						if self.midi_learn_zctrl:
							self.midi_learn_zctrl.cb_midi_learn(chan, ccnum)
							self.show_current_screen()
						else:
							self.zynmixer.midi_control_change(chan, ccnum, ccval)
					# Note-on/off => CUIA
					elif evtype == 0x8 or evtype == 0x9:
						note = str((ev & 0x7F00) >> 8)
						vel = (ev & 0x007F)
						if note in zynthian_gui_config.master_midi_note_cuia:
							cuia_str = zynthian_gui_config.master_midi_note_cuia[note]
							parts = cuia_str.split(" ", 2)
							cuia = parts[0].lower()
							if len(parts) > 1:
								params = self.parse_cuia_params(parts[1])
							else:
								params = None
							# Emulate Zynswitch Push/Release with Note On/Off
							if cuia == "zynswitch" and len(params) == 1:
								if evtype == 0x8 or vel == 0:
									params.append('R')
								else:
									params.append('P')
								self.cuia_zynswitch(params)
							# Or normal CUIA
							elif evtype == 0x9 and vel > 0:
								self.callable_ui_action(cuia, params)

					# Stop logo animation
					self.stop_loading()

				# Control Change ...
				elif evtype == 0xB:
					self.screens['midi_chan'].midi_chan_activity(chan)
					ccnum = (ev & 0x7F00) >> 8
					ccval = (ev & 0x007F)
					#logging.debug("MIDI CONTROL CHANGE: CH{}, CC{} => {}".format(chan,ccnum,ccval))
					if ccnum < 120:
						# If MIDI learn pending ...
						if self.midi_learn_zctrl:
							self.midi_learn_zctrl.cb_midi_learn(chan, ccnum)
							self.show_current_screen()
						# Try layer's zctrls
						else:
							self.screens['layer'].midi_control_change(chan, ccnum, ccval)
							self.zynmixer.midi_control_change(chan, ccnum, ccval)
					# Special CCs >= Channel Mode
					elif ccnum == 120:
						self.all_sounds_off_chan(chan)
					elif ccnum == 123:
						self.all_notes_off_chan(chan)

				# Program Change ...
				elif evtype == 0xC:
					pgm = (ev & 0x7F00) >> 8
					logging.info("MIDI PROGRAM CHANGE: CH#{}, PRG#{}".format(chan,pgm))

					# SubSnapShot (ZS3) MIDI learn ...
					if self.midi_learn_mode and self.current_screen == 'zs3':
						if self.screens['layer'].save_midi_prog_zs3(chan, pgm) is not None:
							self.exit_midi_learn()
							self.close_screen()
					# Set Preset or ZS3 (sub-snapshot), depending of config option
					else:
						if zynthian_gui_config.midi_prog_change_zs3:
							res = self.screens['layer'].set_midi_prog_zs3(chan, pgm)
						else:
							res = self.screens['layer'].set_midi_prog_preset(chan, pgm)
						if res:
							if self.current_screen == 'audio_mixer':
								self.screens['audio_mixer'].refresh_visible_strips()
							elif self.current_screen == 'control':
								self.screens['control'].build_view()

						#if self.curlayer and chan == self.curlayer.get_midi_chan():
						#	self.show_screen('control')

				# Note-On ...
				elif evtype == 0x9:
					self.screens['midi_chan'].midi_chan_activity(chan)
					#Preload preset (note-on)
					if self.current_screen == 'preset' and zynthian_gui_config.preset_preload_noteon and chan == self.curlayer.get_midi_chan():
						self.start_loading()
						self.screens['preset'].preselect_action()
						self.stop_loading()
					#Note Range Learn
					elif self.current_screen == 'midi_key_range' and self.midi_learn_mode:
						self.screens['midi_key_range'].learn_note_range((ev & 0x7F00) >> 8)
					#Update pattern editor display
					elif self.current_screen == 'pattern_editor' and self.zynseq.libseq.isMidiRecord():
						self.screens['pattern_editor'].midi_note((ev >> 8) & 0x7F)

				self.status_info['midi'] = True
				self.last_event_flag = True

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
			self.screens["zynpad"].light_off_trigger_device()
			check_output("powersave_control.sh on", shell=True)
		else:
			logging.info("Power Save Mode: OFF")
			check_output("powersave_control.sh off", shell=True)
			self.screens["zynpad"].refresh_trigger_device(force=True)


	def set_event_flag(self):
		self.last_event_flag = True


	def reset_event_flag(self):
		self.last_event_flag = False


	def cb_touch(self, event):
		#logging.debug("CB EVENT TOUCH!!!")
		if self.power_save_mode:
			self.set_event_flag()
			self.ignore_next_touch_release = True
			return "break"
		self.set_event_flag()


	def cb_touch_release(self, event):
		#logging.debug("CB EVENT TOUCH RELEASE!!!")
		self.set_event_flag()
		if self.ignore_next_touch_release:
			#logging.debug("IGNORING EVENT TOUCH RELEASE!!!")
			self.ignore_next_touch_release = False
			return "break"


	#------------------------------------------------------------------
	# "Busy" Animated Icon Thread
	#------------------------------------------------------------------

	def start_loading_thread(self):
		self.loading_thread = Thread(target=self.loading_refresh, args=())
		self.loading_thread.name = "loading"
		self.loading_thread.daemon = True # thread dies with the program
		self.loading_thread.start()


	def start_loading(self):
		if self.loading > 0:
			self.loading += 1
		else:
			self.loading = 1
		#logging.debug("START LOADING %d" % self.loading)


	def stop_loading(self):
		if self.loading > 0:
			self.loading -= 1
		else:
			self.loading = 0
		#logging.debug("STOP LOADING %d" % self.loading)


	def reset_loading(self):
		self.loading = 0


	def loading_refresh(self):
		while not self.exit_flag:
			try:
				if self.current_screen:
					self.screens[self.current_screen].refresh_loading()
			except Exception as err:
				logging.error("Screen {} => {}".format(self.current_screen, err))
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
				self.wsleds.update()
			sleep(0.2)
		# On exit ...
		# Release zynpad trigger device
		self.screens["zynpad"].end_trigger_device()
		# Light-off LEDs
		if self.wsleds:
			self.wsleds.end()

	def refresh_status(self):
		try:
			# Get CPU Load
			#self.status_info['cpu_load'] = max(psutil.cpu_percent(None, True))
			self.status_info['cpu_load'] = zynautoconnect.get_jackd_cpu_load()

			# Get SOC sensors (once each 5 refreshes)
			if self.status_counter > 5:
				self.status_counter = 0

				self.status_info['overtemp'] = False
				self.status_info['undervoltage'] = False

				if self.hwmon_thermal_file and self.hwmon_undervolt_file:
					try:
						self.hwmon_thermal_file.seek(0)
						res = int(self.hwmon_thermal_file.read())/1000
						#logging.debug("CPU Temperature => {}".format(res))
						if res > self.overtemp_warning:
							self.status_info['overtemp'] = True
					except Exception as e:
						logging.error(e)

					try:
						self.hwmon_undervolt_file.seek(0)
						res = self.hwmon_undervolt_file.read()
						if res == "1":
							self.status_info['undervoltage'] = True
					except Exception as e:
						logging.error(e)

				elif self.get_throttled_file:
					try:
						self.get_throttled_file.seek(0)
						thr = int('0x%s' % self.get_throttled_file.read(), 16)
						if thr & 0x1:
							self.status_info['undervoltage'] = True
						elif thr & (0x4 | 0x2):
							self.status_info['overtemp'] = True
					except Exception as e:
						logging.error(e)

				else:
					self.status_info['overtemp'] = True
					self.status_info['undervoltage'] = True

			else:
				self.status_counter += 1

			# Audio Player Status
			if self.audio_player.engine.player.get_playback_state(self.audio_player.handle):
				self.status_info['audio_player'] = 'PLAY'
			elif 'audio_player' in self.status_info:
				self.status_info.pop('audio_player')

			# Audio Recorder Status => Implemented in zyngui/zynthian_audio_recorder.py

			# Get MIDI Player/Recorder Status
			try:
				self.status_info['midi_recorder'] = self.screens['midi_recorder'].get_status()
			except Exception as e:
				logging.error(e)

			# Refresh on-screen status
			try:
				self.screens[self.current_screen].refresh_status(self.status_info)
			except AttributeError:
				pass

			# Refresh status of external controllers
			try:
				self.screens["zynpad"].refresh_trigger_device()
			except Exception as err:
				logging.error(err)

			# Clean some status_info
			self.status_info['xrun'] = False
			self.status_info['midi'] = False
			self.status_info['midi_clock'] = False

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
			if self.exit_wait_count < timeout and (self.control_thread.is_alive() or self.status_thread.is_alive() or self.loading_thread.is_alive() or zynautoconnect.is_running()):
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
					if zynautoconnect.is_running():
						logging.error("Auto-connect thread failed to terminate")
				zynthian_gui_config.top.quit()
				return
		# Refresh Current Layer
		elif self.curlayer and not self.loading:
			try:
				self.curlayer.refresh()
			except Exception as e:
				#self.reset_loading()
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
						self.zynmixer.remove_osc_client(client)
					except:
						pass

			if not self.osc_clients and self.current_screen != "audio_mixer":
				for chan in range(self.zynmixer.get_max_channels()):
					self.zynmixer.enable_dpm(chan, False)

			# Poll
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
		self.zynseq.libseq.stop()
		for chan in range(16):
			lib_zyncore.ui_send_ccontrol_change(chan, 123, 0)
		try:
			lib_zyncore.zynaptik_all_gates_off()
		except:
			pass


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
		if not isinstance(lower_n_chans, int) or lower_n_chans < 0 or lower_n_chans > 0xF:
			logging.error("Can't initialize MPE Lower Zone. Incorrect num of channels ({})".format(lower_n_chans))
		else:
			lib_zyncore.ctrlfb_send_ccontrol_change(0x0, 0x79, 0x0)
			lib_zyncore.ctrlfb_send_ccontrol_change(0x0, 0x64, 0x6)
			lib_zyncore.ctrlfb_send_ccontrol_change(0x0, 0x65, 0x0)
			lib_zyncore.ctrlfb_send_ccontrol_change(0x0, 0x06, lower_n_chans)

		# Configure Upper Zone
		if not isinstance(upper_n_chans, int) or upper_n_chans < 0 or upper_n_chans > 0xF:
			logging.error("Can't initialize MPE Upper Zone. Incorrect num of channels ({})".format(upper_n_chans))
		else:
			lib_zyncore.ctrlfb_send_ccontrol_change(0xF, 0x79, 0x0)
			lib_zyncore.ctrlfb_send_ccontrol_change(0xF, 0x64, 0x6)
			lib_zyncore.ctrlfb_send_ccontrol_change(0xF, 0x65, 0x0)
			lib_zyncore.ctrlfb_send_ccontrol_change(0xF, 0x06, upper_n_chans)


	#------------------------------------------------------------------
	# Autoconnect
	#------------------------------------------------------------------


	def zynautoconnect(self, force=False):
		if force:
			self.zynautoconnect_midi_flag = False
			zynautoconnect.midi_autoconnect(True)
			self.zynautoconnect_audio_flag = False
			zynautoconnect.audio_autoconnect(True)
		else:
			self.zynautoconnect_midi_flag = True
			self.zynautoconnect_audio_flag = True


	def zynautoconnect_midi(self, force=False):
		if force:
			self.zynautoconnect_midi_flag = False
			zynautoconnect.midi_autoconnect(True)
		else:
			self.zynautoconnect_midi_flag = True


	def zynautoconnect_audio(self, force=False):
		if force:
			self.zynautoconnect_audio_flag = False
			zynautoconnect.audio_autoconnect(True)
		else:
			self.zynautoconnect_audio_flag = True


	def zynautoconnect_do(self):
		if self.exit_flag:
			return
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


#------------------------------------------------------------------------------
