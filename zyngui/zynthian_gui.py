#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Main Class for Zynthian GUI
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

import copy
import liblo
import ctypes
import logging
import importlib
from time import sleep
from pathlib import Path
from time import monotonic
from datetime import datetime
from threading  import Thread, Lock
from subprocess import check_output
from queue import SimpleQueue, Empty

# Zynthian specific modules
import zynconf
from zyngine import zynthian_state_manager
from zyncoder.zyncore import get_lib_zyncore
from zynlibs.zynseq import *
import zynautoconnect

from zyngine.zynthian_chain import *

from zyngui import zynthian_gui_config
from zyngui import zynthian_gui_keyboard
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
from zyngui.zynthian_gui_main_menu import zynthian_gui_main_menu
from zyngui.zynthian_gui_chain_menu import zynthian_gui_chain_menu
from zyngui.zynthian_gui_midi_recorder import zynthian_gui_midi_recorder
from zyngui.zynthian_gui_zynpad import zynthian_gui_zynpad
from zyngui.zynthian_gui_arranger import zynthian_gui_arranger
from zyngui.zynthian_gui_patterneditor import zynthian_gui_patterneditor
from zyngui.zynthian_gui_mixer import zynthian_gui_mixer
from zyngui.zynthian_gui_tempo import zynthian_gui_tempo
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
		
		self.current_processor = None

		self.loading_thread = None
		self.control_thread = None
		self.status_thread = None
		self.cuia_thread = None
		self.cuia_queue = SimpleQueue()
		self.zynread_wait_flag = False
		self.exit_flag = False
		self.exit_code = 0
		self.exit_wait_count = 0

		self.zynmidi = None

		self.status_counter = 0

		self.state_manager = zynthian_state_manager.zynthian_state_manager()
		self.chain_manager = self.state_manager.chain_manager
		self.modify_chain_status = {"midi_thru": False, "audio_thru": False, "parallel": False}

		# Create Lock object to avoid concurrence problems
		self.lock = Lock()

		# Init LEDs
		self.init_wsleds()

		# Load keyboard binding map
		zynthian_gui_keybinding.load()

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
	# WSLeds Init
	# ---------------------------------------------------------------------------

	def init_wsleds(self):
		if zynthian_gui_config.wiring_layout.startswith("Z2"):
			from zyngui.zynthian_wsleds_z2 import zynthian_wsleds_z2
			self.wsleds = zynthian_wsleds_z2(self)
			self.wsleds.start()
		elif zynthian_gui_config.wiring_layout.startswith("V5"):
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
					get_lib_zyncore().setup_zynswitch_midi(swi, event['type'], midi_chan, event['num'], event['val'])
					logging.info("MIDI ZYNSWITCH {}: {} CH#{}, {}, {}".format(swi, event['type'], midi_chan, event['num'], event['val']))
				else:
					get_lib_zyncore().setup_zynswitch_midi(swi, 0, 0, 0, 0)
					logging.info("MIDI ZYNSWITCH {}: DISABLED!".format(swi))

		# Configure Zynaptik Analog Inputs (CV-IN)
		for i, event in enumerate(zynthian_gui_config.zynaptik_ad_midi_events):
			if event is not None:
				if event['chan'] is not None:
					midi_chan = event['chan']
				else:
					midi_chan = curlayer_chan

				if midi_chan is not None:
					get_lib_zyncore().setup_zynaptik_cvin(i, event['type'], midi_chan, event['num'])
					logging.info("ZYNAPTIK CV-IN {}: {} CH#{}, {}".format(i, event['type'], midi_chan, event['num']))
				else:
					get_lib_zyncore().disable_zynaptik_cvin(i)
					logging.info("ZYNAPTIK CV-IN {}: DISABLED!".format(i))

		# Configure Zynaptik Analog Outputs (CV-OUT)
		for i, event in enumerate(zynthian_gui_config.zynaptik_da_midi_events):
			if event is not None:
				if event['chan'] is not None:
					midi_chan = event['chan']
				else:
					midi_chan = curlayer_chan

				if midi_chan is not None:
					get_lib_zyncore().setup_zynaptik_cvout(i, event['type'], midi_chan, event['num'])
					logging.info("ZYNAPTIK CV-OUT {}: {} CH#{}, {}".format(i, event['type'], midi_chan, event['num']))
				else:
					get_lib_zyncore().disable_zynaptik_cvout(i)
					logging.info("ZYNAPTIK CV-OUT {}: DISABLED!".format(i))

		# Configure Zyntof Inputs (Distance Sensor)
		for i, event in enumerate(zynthian_gui_config.zyntof_midi_events):
			if event is not None:
				if event['chan'] is not None:
					midi_chan = event['chan']
				else:
					midi_chan = curlayer_chan

				if midi_chan is not None:
					get_lib_zyncore().setup_zyntof(i, event['type'], midi_chan, event['num'])
					logging.info("ZYNTOF {}: {} CH#{}, {}".format(i, event['type'], midi_chan, event['num']))
				else:
					get_lib_zyncore().disable_zyntof(i)
					logging.info("ZYNTOF {}: DISABLED!".format(i))



	# ---------------------------------------------------------------------------
	# MIDI Router Init & Config
	# ---------------------------------------------------------------------------

	def init_midi(self):
		try:
			# Set Global Tuning
			self.fine_tuning_freq = zynthian_gui_config.midi_fine_tuning
			get_lib_zyncore().set_midi_filter_tuning_freq(ctypes.c_double(self.fine_tuning_freq))
			#Set MIDI Master Channel
			get_lib_zyncore().set_midi_master_chan(zynthian_gui_config.master_midi_channel)
			#Set MIDI CC automode
			get_lib_zyncore().set_midi_filter_cc_automode(zynthian_gui_config.midi_cc_automode)
			#Set MIDI System Messages flag
			get_lib_zyncore().set_midi_filter_system_events(zynthian_gui_config.midi_sys_enabled)
			#Setup MIDI filter rules
			if self.state_manager.midi_filter_script:
				self.state_manager.midi_filter_script.clean()
			self.midi_filter_script = self.state_manager.zynthian_midi_filter_script.MidiFilterScript(zynthian_gui_config.midi_filter_rules)

		except Exception as e:
			logging.error("ERROR initializing MIDI : {}".format(e))


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

		parts = path.upper().split("/", 2)
		#TODO: message may have fewer parts than expected
		if parts[0] == "" and parts[1] == "CUIA":
			self.set_event_flag()
			# Execute action
			self.cuia_queue.put_nowait([parts[2], args])
			#Run autoconnect if needed
			zynautoconnect.request_audio_connect()
			zynautoconnect.request_midi_connect()
		elif parts[1] in ("MIXER", "DAWOSC"):
			self.set_event_flag()
			part2 = parts[2]
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
			logging.warning(f"Not supported OSC call '{path}'")

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
		self.screens['tempo'] = zynthian_gui_tempo()
		self.screens['admin'] = zynthian_gui_admin()
		self.screens['audio_mixer'] = zynthian_gui_mixer()

		# Create the right main menu screen
		if zynthian_gui_config.layout['menu'] == 'chain_menu':
			self.screens['main_menu'] = zynthian_gui_chain_menu()
		else:
			self.screens['main_menu'] = zynthian_gui_main_menu()

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
		init_screen = "main_menu"
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
		self.start_cuia_thread()

		# Initialize MPE Zones
		#self.state_manager.init_mpe_zones(0, 2)


	def stop(self):
		logging.info("STOPPING ZYNTHIAN-UI ...")
		self.state_manager.stop()
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
				if len(self.get_current_processor().get_bank_list()) > 1:
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
		self.show_screen_reset('main_menu')
		self.state_manager.zynmixer.set_mute(256, 0)


	# -------------------------------------------------------------------
	# Callable UI Actions
	# -------------------------------------------------------------------

	@classmethod
	def get_cuia_list(cls):
		return [method[5:].upper() for method in dir(cls) if method.startswith('cuia_') is True]


	def callable_ui_action(self, cuia, params=None):
		logging.debug("CUIA '{}' => {}".format(cuia, params))
		try:
			cuia_func = getattr(self, "cuia_" + cuia.lower())
		except AttributeError:
			logging.error("Unknown CUIA '{}'".format(cuia))

		cuia_func(params)


	# System actions CUIA
	def cuia_test_mode(self, params):
		self.test_mode = params
		logging.warning('TEST_MODE: {}'.format(params))

	def cuia_toggle_alt_mode(self, params):
		if self.alt_mode:
			self.alt_mode = False
		else:
			self.alt_mode = True

	def cuia_power_off(self, params):
		self.screens['admin'].power_off_confirmed()

	def cuia_reboot(self, params):
		self.screens['admin'].reboot_confirmed()

	def cuia_restart_ui(self, params):
		self.screens['admin'].restart_gui()

	def cuia_exit_ui(self, params):
		self.screens['admin'].exit_to_console()

	def cuia_reload_wiring_layout(self, params):
		self.reload_wiring_layout()

	def cuia_reload_midi_config(self, params):
		self.state_manager.reload_midi_config()

	def cuia_reload_key_binding(self, params):
		zynthian_gui_keybinding.load()

	def cuia_last_state_action(self, params):
		self.screens['admin'].last_state_action()

	# Panic Actions
	def cuia_all_notes_off(self, params):
		self.state_manager.all_notes_off()
		sleep(0.1)
		self.state_manager.raw_all_notes_off()

	def cuia_all_sounds_off(self, params):
		self.state_manager.all_notes_off()
		self.state_manager.all_sounds_off()
		sleep(0.1)
		self.state_manager.raw_all_notes_off()

	def cuia_clean_all(self, params):
		if params == ['CONFIRM']:
			self.clean_all()
			self.show_screen_reset('main_menu') #TODO: Should send signal so that UI can react

	# Audio & MIDI Recording/Playback actions
	def cuia_start_audio_record(self, params):
		self.state_manager.audio_recorder.start_recording()
		self.refresh_signal("AUDIO_RECORD")

	def cuia_stop_audio_record(self, params):
		self.state_manager.audio_recorder.stop_recording()
		self.refresh_signal("AUDIO_RECORD")

	def cuia_toggle_audio_record(self, params):
		self.state_manager.audio_recorder.toggle_recording()
		self.refresh_signal("AUDIO_RECORD")

	def cuia_start_audio_play(self, params):
		self.state_manager.start_audio_player()

	def cuia_stop_audio_play(self, params):
		self.state_manager.stop_audio_player()

	def cuia_toggle_audio_play(self, params):
		#TODO: This logic should not be here
		if self.current_screen == "pattern_editor":
			self.screens["pattern_editor"].toggle_playback()
		else:
			self.state_manager.toggle_audio_player()

	def cuia_start_midi_record(self, params):
		self.screens['midi_recorder'].start_recording()

	def cuia_stop_midi_record(self, params):
		self.screens['midi_recorder'].stop_recording()
		if self.current_screen=="midi_recorder":
			self.screens['midi_recorder'].select()

	def cuia_toggle_midi_record(self, params):
		self.screens['midi_recorder'].toggle_recording()
		if self.current_screen=="midi_recorder":
			self.screens['midi_recorder'].select()

	def cuia_start_midi_play(self, params):
		self.screens['midi_recorder'].start_playing()

	def cuia_stop_midi_play(self, params):
		self.screens['midi_recorder'].stop_playing()

	def cuia_toggle_midi_play(self, params):
		self.screens['midi_recorder'].toggle_playing()

	def cuia_start_step_seq(self, params):
		#TODO Implement this correctly or remove CUIA
		#self.state_manager.zynseq.start_transport()
		pass

	def cuia_stop_step_seq(self, params):
		#TODO Implement this correctly or remove CUIA
		#self.state_manager.zynseq.stop_transport()
		pass

	def cuia_toggle_step_seq(self, params):
		#TODO Implement this correctly or remove CUIA
		#self.state_manager.zynseq.toggle_transport()
		pass

	def cuia_tempo(self, params):
		self.screens["tempo"].tap()
		if self.current_screen != "tempo":
			self.show_screen("tempo")

	def cuia_set_tempo(self, params):
		try:
			self.state_manager.zynseq.set_tempo(params[0])
		except (AttributeError, TypeError) as err:
			pass

	def cuia_tempo_up(self, params):
		if params:
			try:
				self.state_manager.zynseq.set_tempo(self.state_manager.zynseq.get_tempo() + params[0])
			except (AttributeError, TypeError) as err:
				pass
		else:
			self.state_manager.zynseq.set_tempo(self.state_manager.zynseq.get_tempo() + 1)

	def cuia_tempo_down(self, params):
		if params:
			try:
				self.state_manager.zynseq.set_tempo(self.state_manager.zynseq.get_tempo() - params[0])
			except (AttributeError, TypeError) as err:
				pass
		else:
			self.state_manager.zynseq.set_tempo(self.state_manager.zynseq.get_tempo() - 1)

	def cuia_tap_tempo(self, params):
		self.screens["tempo"].tap()


	# Zynpot & Zynswitch emulation CUIAs (low level)
	def cuia_zynpot(self, params):
		try:
			i = params[0]
			d = params[1]
			self.get_current_screen_obj().zynpot_cb(i, d)
		except IndexError:
			logging.error("zynpot requires 2 parameters: index, delta, not {params}")
			return
		except Exception as e:
			logging.error(e)

	def cuia_zynswitch(self, params):
		try:
			i = params[0]
			d = params[1]
			self.cuia_queue.put_nowait(f"zynswitch i d")
		except IndexError:
			logging.error("zynswitch requires 2 parameters: index, delta, not {params}")
			return
		except Exception as e:
			logging.error(e)

	# Basic UI-Control CUIAs
	# 4 x Arrows
	def cuia_arrow_up(self, params):
		try:
			self.get_current_screen_obj().arrow_up()
		except (AttributeError, TypeError) as err:
			pass

	def	cuia_arrow_down(self, params):
		try:
			self.get_current_screen_obj().arrow_down()
		except (AttributeError, TypeError) as err:
			pass

	def cuia_arrow_right(self, params):
		try:
			self.get_current_screen_obj().arrow_right()
		except (AttributeError, TypeError) as err:
			pass

	def cuia_arrow_next(self, params):
		self.cuia_arrow_right(params)

	def cuia_arrow_left(self, params):
		try:
			self.get_current_screen_obj().arrow_left()
		except (AttributeError, TypeError) as err:
			pass

	def cuia_arrow_prev(self, params):
		self.cuia_arrow_left(params)

	# Back action
	def cuia_back(self, params):
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

	def cuia_screen_main_menu(self, params):
		self.toggle_screen("main_menu")

	def cuia_screen_admin(self, params):
		self.toggle_screen("admin")

	def cuia_screen_audio_mixer(self, params):
		self.toggle_screen("audio_mixer")

	def cuia_screen_snapshot(self, params):
		self.toggle_screen("snapshot")

	def cuia_screen_midi_recorder(self, params):
		self.toggle_screen("midi_recorder")

	def cuia_screen_alsa_mixer(self, params):
		self.toggle_screen("alsa_mixer", hmode=zynthian_gui.SCREEN_HMODE_RESET)

	def cuia_screen_zynpad(self, params):
		self.toggle_screen("zynpad")

	def cuia_screen_pattern_editor(self, params):
		success = False
		if self.current_screen in ["arranger", "zynpad"]:
			success = self.screens[self.current_screen].show_pattern_editor()
		if not success:
			self.toggle_screen("pattern_editor")

	def cuia_screen_arranger(self, params):
		self.toggle_screen("arranger")

	def cuia_screen_bank(self, params):
		self.toggle_screen("bank")

	def cuia_screen_preset(self, params):
		self.toggle_screen("preset")

	def cuia_screen_calibrate(self, params):
		self.calibrate_touchscreen()

	def cuia_chain_control(self, params=None):
		if params:
			try:
				# Select chain by ID
				chain_id = params[0]
			except:
				pass
		self.chain_control(chain_id)

	def cuia_layer_control(self, params):
		self.cuia_chain_control(params)

	def cuia_screen_control(self, params):
		self.cuia_chain_control(params)

	def cuia_chain_options(self, params):
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

	def cuia_layer_options(self, params):
		self.cuia_chain_options(params)

	def cuia_menu(self, params):
		try:
			self.screens[self.current_screen].toggle_menu()
		except (AttributeError, TypeError) as err:
			self.toggle_screen("main_menu", hmode=zynthian_gui.SCREEN_HMODE_ADD)

	def cuia_bank_preset(self, params=None):
		if params:
			try:
				self.current_processor = params #TODO: This doesn't do enough
			except:
				logging.error("Can't set chain passed as CUIA parameter!")

		if self.current_screen == 'preset':
			if len(self.get_current_processor().get_bank_list()) > 1:
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
			elif len(self.get_current_processor().get_bank_list()) > 0 and self.get_current_processor().get_bank_list()[0][0] != '':
				self.show_screen('bank', hmode=zynthian_gui.SCREEN_HMODE_ADD)

	def cuia_preset(self, params):
		self.cuia_bank_preset(params)

	def cuia_preset_fav(self, params):
		self.show_favorites()

	def cuia_zctrl_touch(self, params):
		if params:
			self.screens[self.current_screen].zctrl_touch(params[0])

	def cuia_enable_midi_learn_cc(self, params):
		if len(params) == 2:
			self.state_manager.enable_learn_cc(params[0], params[1])

	def cuia_disable_midi_learn_cc(self, params):
		self.state_manager.disable_learn_cc()

	def cuia_enable_midi_learn_pc(self, params):
		if params:
			self.state_manager.enable_learn_pc(params[0])
		else:
			self.state_manager.enable_learn_pc("")

	def cuia_disable_midi_learn_pc(self, params):
		self.state_manager.disable_learn_pc()

	def cuia_enable_midi_learn(self, params=None):
		self.state_manager.set_midi_learn(True)
		self.screens[self.current_screen].enter_midi_learn()

	def cuia_disable_midi_learn(self, params=None):
		self.state_manager.set_midi_learn(False)
		self.screens[self.current_screen].exit_midi_learn()

	def cuia_toggle_midi_learn(self, params=None):
		try:
			state = self.screens[self.current_screen].toggle_midi_learn()
			self.state_manager.set_midi_learn(state)
		except:
			if self.state_manager.midi_learn_state:
				self.cuia_disable_midi_learn(params)
			else:
				self.cuia_enable_midi_learn(params)

	def cuia_action_midi_unlearn(self, params):
		try:
			self.screens[self.current_screen].midi_unlearn_action()
		except (AttributeError, TypeError) as err:
			pass

	# Unlearn from currently selected (learning) control
	def cuia_midi_unlearn_control(self, params):
		#TODO: Implement cuia_midi_unlearn_control
		pass

	# Unlearn all mixer controls
	def cuia_midi_unlearn_mixer(self, params):
		try:
			self.screens['audio_mixer'].midi_unlearn_all()
		except (AttributeError, TypeError) as err:
			logging.error(err)

	def cuia_midi_unlearn_node(self, params):
		if params:
			self.chain_manager.remove_midi_learn([params[0], params[1]])

	def cuia_midi_unlearn_chain(self, params):
		if params:
			self.chain_manager.clean_midi_learn(params[0])
		else:
			self.chain_manager.clean_midi_learn(self.chain_manager.active_chain_id)

	# MIDI CUIAs
	def cuia_program_change(self, params):
		if len(params) > 0:
			pgm = int(params[0])
			if len(params) > 1:
				chan = int(params[1])
			else:
				chan = get_lib_zyncore().get_midi_active_chan()
			if chan >= 0 and chan < 16 and pgm >= 0 and pgm < 128:
				get_lib_zyncore().write_zynmidi_program_change(chan, pgm)

	# Common methods to control views derived from zynthian_gui_base
	def cuia_show_topbar(self, params):
		try:
			self.screens[self.current_screen].show_topbar(True)
		except (AttributeError, TypeError) as err:
			pass

	def cuia_hide_topbar(self, params):
		try:
			self.screens[self.current_screen].show_topbar(False)
		except (AttributeError, TypeError) as err:
			pass

	def cuia_show_buttonbar(self, params):
		try:
			self.screens[self.current_screen].show_buttonbar(True)
		except (AttributeError, TypeError) as err:
			pass

	def cuia_hide_buttonbar(self, params):
		try:
			self.screens[self.current_screen].show_buttonbar(False)
		except (AttributeError, TypeError) as err:
			pass

	def cuia_show_sidebar(self, params):
		try:
			self.screens[self.current_screen].show_sidebar(True)
		except (AttributeError, TypeError) as err:
			pass

	def cuia_hide_sidebar(self, params):
		try:
			self.screens[self.current_screen].show_sidebar(False)
		except (AttributeError, TypeError) as err:
			pass

	def refresh_signal(self, sname):
		try:
			self.screens[self.current_screen].refresh_signal(sname)
		except (AttributeError, TypeError) as err:
			pass

	def custom_switch_ui_action(self, i, t):
		action_config = zynthian_gui_config.custom_switch_ui_actions[i]
		if t in action_config:
			cuia = action_config[t]
			if cuia and cuia != "NONE":
				self.cuia_queue.put_nowait(cuia)
				return True

	# -------------------------------------------------------------------
	# Switches
	# -------------------------------------------------------------------

	def zynswitches(self):
		"""Process physical switch triggers"""

		if not get_lib_zyncore(): return
		i = 0
		while i <= zynthian_gui_config.last_zynswitch_index:
			# dtus is 0 of switched pressed, dur of last press or -1 if already processed
			dtus = get_lib_zyncore().get_zynswitch(i, zynthian_gui_config.zynswitch_long_us)
			if dtus >= 0:
				self.cuia_queue.put_nowait(f"zynswitch {i} {self.zynswitch_timing(dtus)}")
			i += 1

	def zynswitch_timing(self, dtus):
		"""Get action based on switch held time
		
		dtus : Duration switch has been pressed
		Return : Letter indicating the action to take
		#TODO: Does not support Release which means that press and hold expires when Long press is reached
		"""
		if dtus == 0:
			return "P"
		elif dtus > zynthian_gui_config.zynswitch_long_us:
			return "L"
		elif dtus > zynthian_gui_config.zynswitch_bold_us:
			return "B"
		elif dtus > 0:
			return "S"


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
			logging.debug('Push Switch ' + str(i))
			return self.custom_switch_ui_action(i-4, "P")


	def zynswitch_long(self, i):
		logging.debug('Looooooooong Switch '+str(i))

		# Standard 4 ZynSwitches
		if i == 0:
			self.show_screen_reset("zynpad")

		elif i == 1:
			self.show_screen_reset("admin")

		elif i == 2:
			self.callable_ui_action("all_sounds_off")

		elif i == 3:
			self.screens['admin'].power_off()

		# Custom ZynSwitches
		elif i >= 4:
			return self.custom_switch_ui_action(i-4, "L")


	def zynswitch_bold(self, i):
		logging.debug('Bold Switch '+str(i))

		try:
			if self.screens[self.current_screen].switch(i, 'B'):
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
			self.show_screen_reset('audio_mixer')

		elif i == 2:
			self.show_screen('snapshot')

		elif i == 3:
			self.screens[self.current_screen].switch_select('B')

		# Custom ZynSwitches
		elif i >= 4:
			return self.custom_switch_ui_action(i-4, "B")


	def zynswitch_short(self, i):
		logging.debug('Short Switch '+str(i))

		try:
			if self.screens[self.current_screen].switch(i, 'S'):
				return
		except AttributeError as e:
			pass

		# Default actions for the standard 4 ZynSwitches
		if i == 0:
			pass

		elif i == 1:
			self.back_screen()

		elif i == 2:
			self.cuia_queue.put_nowait("cuia_toggle_midi_learn")

		elif i == 3:
			self.screens[self.current_screen].switch_select('S')

		# Custom ZynSwitches
		elif i >= 4:
			return self.custom_switch_ui_action(i-4, "S")


	def zynswitch_double(self, i):
		self.state_manager.dtsw[i] = datetime.now()
		for j in range(4):
			if j == i: continue
			if abs((self.state_manager.dtsw[i] - self.state_manager.dtsw[j]).total_seconds()) < 0.3:
				dswstr = str(i) + '+' + str(j)
				logging.debug('Double Switch ' + dswstr)
				#self.show_control_xy(i, j)
				self.show_screen('control')
				self.screens['control'].set_xyselect_mode(i, j)
				return True


	def zynswitch_X(self, i):
		logging.debug('X Switch %d' % i)
		if self.current_screen == 'control' and self.screens['control'].mode == 'control':
			self.screens['control'].midi_learn(i) #TODO: Check zynswitch_X/Y learn


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
	# Defered Switch Events
	#------------------------------------------------------------------

	def zynswitch_defered(self, t, i):
		self.cuia_queue.put_nowait(["zynswitch", [i, t]])


	#------------------------------------------------------------------
	# Read Physical Zynswitches
	#------------------------------------------------------------------

	def zynswitch_read(self):
		#TODO: Block control when busy but avoid ui lock-up
		#if self.state_manager.is_busy():
		#	return

		#Read Zynswitches
		try:
			self.zynswitches()
		except Exception as err:
			logging.exception(err)


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
				evtype = (ev & 0xF00000) >> 20
				chan = (ev & 0x0F0000) >> 16
				#logging.info("MIDI_UI MESSAGE DETAILS: {}, {}".format(chan,evtype))

				# System Messages (Common & RT)
				if evtype == 0xF:
					# Clock
					if chan == 0x8:
						self.state_manager.status_info['midi_clock'] = True
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
					# Webconf configured messages for Snapshot Control ...
					if ev == zynthian_gui_config.master_midi_program_change_up:
						logging.debug("PROGRAM CHANGE UP!")
						self.state_manager.load_snapshot_by_prog(self.state_manager.snapshot_program + 1)
					elif ev == zynthian_gui_config.master_midi_program_change_down:
						logging.debug("PROGRAM CHANGE DOWN!")
						self.state_manager.load_snapshot_by_prog(self.state_manager.snapshot_program - 1)
					elif ev == zynthian_gui_config.master_midi_bank_change_up:
						logging.debug("BANK CHANGE UP!")
						self.state_manager.set_snapshot_midi_bank(self.state_manager.snapshot_bank + 1)
					elif ev == zynthian_gui_config.master_midi_bank_change_down:
						logging.debug("BANK CHANGE DOWN!")
						self.state_manager.set_snapshot_midi_bank(self.state_manager.snapshot_bank - 1)
					# Program Change => Snapshot Load
					elif evtype == 0xC:
						pgm = ((ev & 0x7F00) >> 8)
						logging.debug("PROGRAM CHANGE %d" % pgm)
						self.replace_screen("main") #TODO: Use dedicated loading screen
						self.state_manager.load_snapshot_by_prog(pgm)
						self.replace_screen("audio_mixer")
					# Control Change ...
					elif evtype == 0xB:
						ccnum = (ev & 0x7F00) >> 8
						ccval = (ev & 0x007F)
						if ccnum == zynthian_gui_config.master_midi_bank_change_ccnum:
							bnk = (ev & 0x7F)
							logging.debug("BANK CHANGE %d" % bnk)
							self.state_manager.set_snapshot_midi_bank(bnk)
						elif ccnum == 120:
							self.state_manager.all_sounds_off()
						elif ccnum == 123:
							self.state_manager.all_notes_off()

						if self.state_manager.midi_learn_cc:
							self.chain_manager.add_midi_learn(chan, ccnum, self.state_manager.midi_learn_cc[0], self.state_manager.midi_learn_cc[1])
						else:
							self.state_manager.zynmixer.midi_control_change(chan, ccnum, ccval)
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
								self.cuia_queue.put_nowait(cuia, params)
							# Or normal CUIA
							elif evtype == 0x9 and vel > 0:
								self.cuia_queue.put_nowait([cuia, params])


				# Control Change ...
				elif evtype == 0xB:
					self.screens['midi_chan'].midi_chan_activity(chan)
					ccnum = (ev & 0x7F00) >> 8
					ccval = (ev & 0x007F)
					#logging.debug("MIDI CONTROL CHANGE: CH{}, CC{} => {}".format(chan,ccnum,ccval))
					if ccnum < 120:
						# If MIDI learn pending ...
						if self.state_manager.midi_learn_cc:
							#TODO: Could optimise by sending ev & 0x7f00 to addt_midi_learn()
							self.chain_manager.add_midi_learn(chan, ccnum, self.state_manager.midi_learn_cc[0], self.state_manager.midi_learn_cc[1])
							self.screens['control'].exit_midi_learn()
							self.show_current_screen()
						# Try processor parameter
						else:
							self.chain_manager.midi_control_change(chan, ccnum, ccval)
							self.state_manager.zynmixer.midi_control_change(chan, ccnum, ccval)
					# Special CCs >= Channel Mode
					elif ccnum == 120:
						self.state_manager.all_sounds_off_chan(chan)
					elif ccnum == 123:
						self.state_manager.all_notes_off_chan(chan)

				# Program Change ...
				elif evtype == 0xC:
					pgm = (ev & 0x7F00) >> 8
					logging.info("MIDI PROGRAM CHANGE: CH#{}, PRG#{}".format(chan,pgm))

					# SubSnapShot (ZS3) MIDI learn ...
					if self.state_manager.midi_learn_pc:
						self.state_manager.save_zs3(f"{chan}/{pgm} {self.state_manager.midi_learn_pc}")
					elif self.state_manager.midi_learn_pc == "":
						self.state_manager.save_zs3(f"{chan}/{pgm}")
					# Set Preset or ZS3 (sub-snapshot), depending of config option
					else:
						if zynthian_gui_config.midi_prog_change_zs3:
							res = self.state_manager.set_midi_prog_zs3(chan, pgm)
						else:
							if zynthian_gui_config.midi_single_active_channel:
								try:
									chan = self.chain_manager.get_active_chain().midi_chan
								except:
									return
							res = self.chain_manager.set_midi_prog_preset(chan, pgm)
						if res:
							if self.current_screen == 'audio_mixer':
								self.screens['audio_mixer'].refresh_visible_strips()
							elif self.current_screen == 'control':
								self.screens['control'].build_view()

					if self.current_screen == 'zs3_learn':
						self.state_manager.disable_learn_pc()
						self.close_screen()

				# Note-On ...
				elif evtype == 0x9:
					self.screens['midi_chan'].midi_chan_activity(chan)
					#Preload preset (note-on)
					if self.current_screen == 'preset' and zynthian_gui_config.preset_preload_noteon and chan == self.get_current_processor().get_midi_chan():
						self.screens['preset'].preselect_action()
					#Note Range Learn
					elif self.current_screen == 'midi_key_range' and self.state_manager.midi_learn_state:
						self.screens['midi_key_range'].learn_note_range((ev & 0x7F00) >> 8)
					elif self.current_screen == 'pattern_editor' and self.state_manager.zynseq.libseq.isMidiRecord():
						self.screens['pattern_editor'].midi_note((ev & 0x7F00) >> 8)

				self.state_manager.status_info['midi'] = True
				self.last_event_flag = True

		except Exception as err:
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


	def loading_refresh(self):
		busy_timeout = 0
		busy_warn_time = 200
		while not self.exit_flag:
			try:
				self.screens[self.current_screen].refresh_loading()
			except Exception as err:
				logging.error("zynthian_gui.loading_refresh() => %s" % err)
			if self.state_manager.is_busy():
				busy_timeout += 1
			else:
				busy_timeout = 0
			if busy_timeout == busy_warn_time:
				logging.warning("Clients have been busy for longer than %ds: %s", busy_warn_time / 10, self.state_manager.busy)
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
	# CUIA Thread
	#------------------------------------------------------------------

	def start_cuia_thread(self):
		self.cuia_thread = Thread(target=self.cuia_thread_task, args=())
		self.cuia_thread.name = "cuia"
		self.cuia_thread.daemon = True # thread dies with the program
		self.cuia_thread.start()


	def cuia_thread_task(self):
		"""Thread task to handle CUIA events
		
		Events are passed via cuia_queue and may be a space separated list:'cuia, param, param...' or list: [cuia, [params]]
		"""

		zynswitch_cuia_ts = [None] * (zynthian_gui_config.num_zynswitches + 4)
		REPEAT_DELAY = 3 # Quantity of repeat intervals to delay before triggering auto repeat
		REPEAT_INTERVAL = 0.15 # Auto repeat interval in seconds

		while not self.exit_flag:
			try:
				event = self.cuia_queue.get(True, REPEAT_INTERVAL)
				params = None
				if isinstance(event, str):
					if event == "__EXIT__":
						break
					# comma seperated cuia, params...
					parts = event.split(' ')
					cuia = parts.pop(0).lower()
					if parts:
						params = []
						for p in parts:
							try:
								params.append(int(p))
							except:
								params.append(p.strip())
				else:
					# list [cuia, [params]]
					cuia = event[0].lower()
					if len(event) > 1:
						params = event[1]

				if cuia == "zynswitch":
					# zynswitch has parameters: [switch, action] where action is P(ressed), R(eleased), S(hort), B(old), L(ong), X or Y
					try:
						i = params[0]
						t = params[1]
						if t == 'R':
							val = zynswitch_cuia_ts[i]
							zynswitch_cuia_ts[i] = None
							if val > 0:
								dtus = int(1000000 * (monotonic() - val))
								t = self.zynswitch_timing(dtus)
						if t == 'P':
							if self.zynswitch_push(i):
								zynswitch_cuia_ts[i] = -REPEAT_DELAY
							else:
								zynswitch_cuia_ts[i] = monotonic()
						elif t == 'S':
							zynswitch_cuia_ts[i] = None
							self.zynswitch_short(i)
						elif t == 'B':
							zynswitch_cuia_ts[i] = None
							# Double switches must be bold
							if not self.zynswitch_double(i):
								self.zynswitch_bold(i)
						elif t == 'L':
							zynswitch_cuia_ts[i] = None
							self.zynswitch_long(i)
						elif t == 'X':
							self.zynswitch_X(i)
						elif t == 'Y':
							self.zynswitch_Y(i)
						else:
							zynswitch_cuia_ts[i] = None
							logging.warning("Unknown Action Type: {}".format(t))
					except Exception as err:
						logging.error(f"CUIA zynswitch needs 2 parameters: index, action_type, not {params}")

				else:
					try:
						cuia_func = getattr(self, "cuia_" + cuia)
						cuia_func(params)
					except AttributeError:
						logging.error("Unknown of faulty CUIA '{}'".format(cuia))

				self.set_event_flag()

			except Empty:
				for i, ts in enumerate(zynswitch_cuia_ts):
					if ts is None:
						continue
					if ts < 0:
						zynswitch_cuia_ts[i] += 1
					if ts == 0:
						self.zynswitch_push(i)
			except:
				pass

	#------------------------------------------------------------------
	# Thread ending on Exit
	#------------------------------------------------------------------

	def exit(self, code=0):
		self.stop()
		self.exit_code = code
		self.exit_flag = True
		self.cuia_queue.put_nowait("__EXIT__")


	#------------------------------------------------------------------
	# Polling
	#------------------------------------------------------------------

	def start_polling(self):
		self.poll()
		self.osc_timeout()


	def after(self, msec, func):
		zynthian_gui_config.top.after(msec, func)


	def poll(self):
		# Capture exit event and finish
		if self.exit_flag:
			timeout = 10
			if self.exit_wait_count == 0:
				logging.info("EXITING ZYNTHIAN-UI...")
			if self.exit_wait_count < timeout and (self.control_thread.is_alive() or self.status_thread.is_alive() or self.loading_thread.is_alive() or zynautoconnect.is_running() or self.state_manager.thread.is_alive() or self.cuia_thread.is_alive()):
				self.exit_wait_count += 1
			else:
				if self.control_thread.is_alive():
					logging.error("Control thread failed to terminate")
				if self.status_thread.is_alive():
					logging.error("Status thread failed to terminate")
				if self.loading_thread.is_alive():
					logging.error("Loading thread failed to terminate")
				if zynautoconnect.is_running():
					logging.error("Autoconnect thread failed to terminate")
				if self.state_manager.thread.is_alive():
					logging.error("State manager thread failed to terminate")
				if self.cuia_thread.is_alive():
					logging.error("CUIA thread failed to terminate")
				zynthian_gui_config.top.quit()
				return

		# Poll
		zynthian_gui_config.top.after(160, self.poll)


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


#------------------------------------------------------------------------------
