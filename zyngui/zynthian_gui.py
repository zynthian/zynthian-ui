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

import os
import liblo
import ctypes
import ffmpeg
import logging
import importlib
from time import sleep
from pathlib import Path
from time import monotonic
from datetime import datetime
from threading import Thread, Lock, Event
from queue import SimpleQueue, Empty

# Zynthian specific modules
import zynconf
import zynautoconnect

from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import *

from zyngine import zynthian_state_manager

from zyngui import zynthian_gui_config
from zyngui import zynthian_gui_keyboard
from zyngui import zynthian_gui_keybinding
from zyngui.multitouch import MultiTouch
from zyngui.zynthian_gui_info import zynthian_gui_info
from zyngui.zynthian_gui_splash import zynthian_gui_splash
from zyngui.zynthian_gui_loading import zynthian_gui_loading
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
from zyngui.zynthian_gui_midi_in import zynthian_gui_midi_in
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
from zyngui.zynthian_gui_midi_recorder import zynthian_gui_midi_recorder
from zyngui.zynthian_gui_zynpad import zynthian_gui_zynpad
from zyngui.zynthian_gui_arranger import zynthian_gui_arranger
from zyngui.zynthian_gui_patterneditor import zynthian_gui_patterneditor
from zyngui.zynthian_gui_mixer import zynthian_gui_mixer
from zyngui.zynthian_gui_tempo import zynthian_gui_tempo
from zyngui.zynthian_gui_brightness_config import zynthian_gui_brightness_config
from zyngui.zynthian_gui_touchscreen_calibration import zynthian_gui_touchscreen_calibration
from zyngui.zynthian_gui_cv_config import zynthian_gui_cv_config
from zyngui.zynthian_gui_control_test import zynthian_gui_control_test

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
		self.capture_dir_sdc = os.environ.get('ZYNTHIAN_MY_DATA_DIR', "/zynthian/zynthian-my-data") + "/capture"
		self.ex_data_dir = os.environ.get('ZYNTHIAN_EX_DATA_DIR', "/media/root")
	
		if zynthian_gui_config.check_wiring_layout(["Z2"]):
			self.multitouch = MultiTouch(invert_x_axis=True, invert_y_axis=True)
		else:
			self.multitouch = MultiTouch()
		self.test_mode = False
		self.alt_mode = False

		self.last_event_flag = False
		self.last_event_ts = monotonic()
		self.ignore_next_touch_release = False

		self.screens = {}
		self.screen_history = []
		self.current_screen = None
		self.screen_timer_id = None
		
		self.current_processor = None

		self.busy_thread = None
		self.control_thread = None
		self.status_thread = None
		self.cuia_thread = None
		self.cuia_queue = SimpleQueue()
		self.zynread_wait_flag = False
		self.exit_flag = False
		self.exit_code = 0

		self.zynmidi = None

		self.status_counter = 0

		self.state_manager = zynthian_state_manager.zynthian_state_manager()
		self.chain_manager = self.state_manager.chain_manager
		self.modify_chain_status = {"midi_thru": False, "audio_thru": False, "parallel": False}

		self.capture_log_ts0 = None
		self.capture_log_fname = None
		self.capture_ffmpeg_proc = None

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

		self.zynpot_dval = zynthian_gui_config.num_zynpots * [0]
		self.zynpot_event = Event()
		self.zynpot_lock = Lock()
		self.zynpot_thread = None

	# ---------------------------------------------------------------------------
	# Capture Log
	# ---------------------------------------------------------------------------

	def start_capture_log(self, title):
		if not title:
			title = "ui_sesion"
		now = datetime.now()
		self.capture_log_ts0 = now
		self.capture_log_fname = "{}-{}".format(title, now.strftime("%Y%m%d%H%M%S"))
		self.start_capture_ffmpeg()
		if self.wsleds:
			self.wsleds.reset_last_state()
		self.write_capture_log("LAYOUT: {}".format(zynthian_gui_config.wiring_layout))
		self.write_capture_log("TITLE: {}".format(self.capture_log_fname))
		# Capture video + jack audio is not working yet
		# zynautoconnect.audio_connect_ffmpeg(timeout=2.0)


	def start_capture_ffmpeg(self):
		fbdev = os.environ.get("FRAMEBUFFER", "/dev/fb0")
		fpath = "{}/{}.mp4".format(self.capture_dir_sdc, self.capture_log_fname)
		self.capture_ffmpeg_proc = ffmpeg.output(
			# ffmpeg.input(":0", r=25, f="x11grab"),
			ffmpeg.input(fbdev, r=20, f="fbdev"),
			# ffmpeg.input("sine=frequency=500", f="lavfi"),
			# ffmpeg.input("ffmpeg", f="jack"),
			# fpath, vcodec="h264_v4l2m2m", acodec="aac", preset="ultrafast", pix_fmt="nv21", sample_fmt="s16") \
			fpath, vcodec="libx264", acodec="aac", preset="ultrafast", pix_fmt="yuv420p") \
			.global_args('-nostdin', '-hide_banner', '-nostats') \
			.run_async(quiet=True, overwrite_output=True)


	def stop_capture_ffmpeg(self):
		if self.capture_ffmpeg_proc:
			self.capture_ffmpeg_proc.terminate()
		self.capture_ffmpeg_proc = None


	def stop_capture_log(self):
		self.stop_capture_ffmpeg()
		self.capture_log_fname = None
		self.capture_log_ts0 = None


	def write_capture_log(self, message):
		if self.capture_log_fname:
			try:
				rts = str(datetime.now() - self.capture_log_ts0)
				fh = open("{}/{}.log".format(self.capture_dir_sdc, self.capture_log_fname), 'a')
				fh.write("{} {}\n".format(rts, message))
				fh.close()
			except Exception as e:
				logging.error("Can't write to capture log: {}".format(e))


	# ---------------------------------------------------------------------------
	# WSLeds Init
	# ---------------------------------------------------------------------------

	def init_wsleds(self):
		if zynthian_gui_config.check_wiring_layout("Z2"):
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
			#Set MIDI Master Channel
			lib_zyncore.set_midi_master_chan(zynthian_gui_config.master_midi_channel)
			#Set MIDI CC automode
			lib_zyncore.set_midi_filter_cc_automode(zynthian_gui_config.midi_cc_automode)
			#Setup MIDI filter rules
			if self.state_manager.midi_filter_script:
				self.state_manager.midi_filter_script.clean()
			self.midi_filter_script = self.state_manager.zynthian_midi_filter_script.MidiFilterScript(zynthian_gui_config.midi_filter_rules)
			# Setup transport, MIDI clock & sys message options
			self.screens['tempo'].set_transport_clock_source(zynthian_gui_config.transport_clock_source)

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
			cuia = parts[2].upper()
			if self.state_manager.is_busy():
				logging.debug("BUSY! Ignoring OSC CUIA '{}' => {}".format(cuia, args))
				return
			self.cuia_queue.put_nowait([cuia, args])
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

	def create_screens(self):

		# Create Core UI Screens
		self.screens['info'] = zynthian_gui_info()
		self.screens['splash'] = zynthian_gui_splash()
		self.screens['loading'] = zynthian_gui_loading()
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
		self.screens['midi_in'] = zynthian_gui_midi_in()
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
		self.screens['audio_player'] = self.screens['control']
		self.screens['midi_recorder'] = zynthian_gui_midi_recorder()
		self.screens['alsa_mixer'] = self.screens['control']
		self.screens['zynpad'] = zynthian_gui_zynpad()
		self.screens['arranger'] = zynthian_gui_arranger()
		self.screens['pattern_editor'] = zynthian_gui_patterneditor()
		self.screens['brightness_config'] = zynthian_gui_brightness_config()
		self.screens['touchscreen_calibration'] = zynthian_gui_touchscreen_calibration()
		self.screens['control_test'] = zynthian_gui_control_test()

		# Create Zynaptik-related screens
		try:
			if callable(lib_zyncore.init_zynaptik):
				self.screens['cv_config'] = zynthian_gui_cv_config()
		except:
			pass

		# Initialize Control device Manager
		self.state_manager.create_ctrldev_manager()
		self.ctrldev_manager = self.state_manager.ctrldev_manager

		# Initialize OSC
		self.osc_init()

		# Loading screen
		self.show_loading("Starting user interface...")

		# Start polling & threads
		self.start_polling()
		self.start_busy_thread()
		self.start_control_thread()
		self.start_status_thread()
		self.start_cuia_thread()
		self.start_zynpot_thread()


	#--------------------------------------------------------------------------
	# Start task => Must run as a thread, so we can go into tkinter loop
	#**************************************************************************

	def run_start_thread(self):
		self.start_thread = Thread(target=self.start_task, args=())
		self.start_thread.name = "start"
		self.start_thread.daemon = True # thread dies with the program
		self.start_thread.start()


	def start_task(self):
		self.state_manager.start_busy("ui startup")

		snapshot_loaded = False
		if zynthian_gui_config.control_test_enabled:
			init_screen = "control_test"
		else:
			init_screen = "main_menu"
			# Try to load "last_state" snapshot...
			if zynthian_gui_config.restore_last_state:
				snapshot_loaded = self.screens['snapshot'].load_last_state_snapshot()
			# Try to load "default" snapshot...
			if not snapshot_loaded:
				snapshot_loaded = self.screens['snapshot'].load_default_snapshot()


		if snapshot_loaded:
			init_screen = "audio_mixer"
		else:
			# Init MIDI Subsystem => MIDI Profile
			self.state_manager.init_midi()
			self.state_manager.init_midi_services()

		# Show initial screen
		self.show_screen(init_screen, self.SCREEN_HMODE_RESET)

		self.state_manager.end_busy("ui startup")
		
		#Run autoconnect if needed
		zynautoconnect.request_audio_connect()
		zynautoconnect.request_midi_connect()

		# Initialize MPE Zones
		#self.state_manager.init_mpe_zones(0, 2)


	def hide_screens(self, exclude=None):
		if not exclude:
			exclude = self.current_screen
		exclude_obj = self.screens[exclude]

		for screen_name, screen_obj in self.screens.items():
			if screen_obj != exclude_obj:
				screen_obj.hide()


	def show_screen(self, screen=None, hmode=SCREEN_HMODE_ADD):
		self.cancel_screen_timer()
		#self.current_processor = None
		
		if screen is None:
			if self.current_screen:
				screen = self.current_screen
			else:
				screen = "audio_mixer"

		elif screen == "alsa_mixer":
			self.state_manager.alsa_mixer_processor.refresh_controllers()
			self.current_processor = self.state_manager.alsa_mixer_processor

		elif screen == "audio_player":
			if self.state_manager.audio_player:
				self.current_processor = self.state_manager.audio_player
				#self.state_manager.audio_player.refresh_controllers()
			else:
				logging.error("Audio Player not created!")
				return
		else:
			self.current_processor = self.get_current_processor()

		if screen not in ("bank", "preset", "option"):
			self.chain_manager.restore_presets()

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


	def brightness_config(self):
		self.show_screen('brightness_config')


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
		if processor:
			self.current_processor = processor
		elif processor not in self.chain_manager.get_processors(chain_id):
			self.current_processor = None
			for type in ["MIDI Synth", "MIDI Tool", "Audio Effect"]:
				processors = self.chain_manager.get_processors(chain_id, type)
				if processors:
					self.current_processor = processors[0]
					break

		if self.current_processor:
			control_screen_name = 'control'

			# Check for a custom GUI
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
			self.cuia_bank_preset()
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


	def clean_all(self):
		self.show_loading("cleaning all...")
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
		cuia_func = getattr(self, "cuia_" + cuia.lower(), None)
		if callable(cuia_func):
			cuia_func(params)
			if self.capture_log_fname:
				self.write_capture_log("CUIA:{},{}".format(cuia, str(params)))
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
		self.state_manager.reload_midi_config()

	def cuia_reload_key_binding(self, params=None):
		zynthian_gui_keybinding.load()

	def cuia_last_state_action(self, params=None):
		self.screens['admin'].last_state_action()

	# Panic Actions
	def cuia_all_notes_off(self, params=None):
		self.state_manager.all_notes_off()
		sleep(0.1)
		self.state_manager.raw_all_notes_off()

	def cuia_all_sounds_off(self, params=None):
		self.state_manager.all_notes_off()
		self.state_manager.all_sounds_off()
		sleep(0.1)
		self.state_manager.raw_all_notes_off()

	def cuia_clean_all(self, params=None):
		if params == ['CONFIRM']:
			self.clean_all()
			self.show_screen_reset('main_menu') #TODO: Should send signal so that UI can react

	# Audio & MIDI Recording/Playback actions
	def cuia_start_audio_record(self, params=None):
		self.state_manager.audio_recorder.start_recording()

	def cuia_stop_audio_record(self, params=None):
		self.state_manager.audio_recorder.stop_recording()

	def cuia_toggle_audio_record(self, params=None):
		if self.current_screen == 'control' and self.current_processor.engine.name == 'AudioPlayer':
			self.state_manager.audio_recorder.toggle_recording(self.current_processor)
			self.get_current_screen_obj().set_mode_control()
		else:
			self.state_manager.audio_recorder.toggle_recording()

	def cuia_start_audio_play(self, params=None):
		self.state_manager.start_audio_player()

	def cuia_stop_audio_play(self, params=None):
		if self.current_screen == "pattern_editor":
			self.screens["pattern_editor"].stop_playback()
		else:
			self.state_manager.stop_audio_player()
			self.state_manager.audio_player.engine.player.set_position(self.state_manager.audio_player.handle, 0.0)

	def cuia_toggle_audio_play(self, params=None):
		#TODO: This logic should not be here
		if self.current_screen == "pattern_editor":
			self.screens["pattern_editor"].toggle_playback()
		else:
			self.state_manager.toggle_audio_player()

	def cuia_audio_file_list(self, params=None):
		self.show_screen("audio_player")
		self.show_screen('bank')
		if len(self.state_manager.audio_player.bank_list) == 1 or self.state_manager.audio_player.bank_name:
			self.screens['bank'].click_listbox()

	def cuia_start_midi_record(self, params=None):
		self.state_manager.start_midi_record()

	def cuia_stop_midi_record(self, params=None):
		self.state_manager.stop_midi_record()
		if self.current_screen == "midi_recorder":
			self.screens['midi_recorder'].select()

	def cuia_toggle_midi_record(self, params=None):
		self.state_manager.toggle_midi_record()
		if self.current_screen == "midi_recorder":
			self.screens['midi_recorder'].select()

	def cuia_start_midi_play(self, params=None):
		self.state_manager.start_midi_playback()

	def cuia_stop_midi_play(self, params=None):
		self.state_manager.stop_midi_playback()

	def cuia_toggle_midi_play(self, params=None):
		self.state_manager.toggle_midi_playback()

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

	def cuia_set_tempo(self, params=None):
		try:
			self.state_manager.zynseq.set_tempo(params[0])
		except (AttributeError, TypeError) as err:
			pass

	def cuia_tempo_up(self, params=None):
		if params:
			try:
				self.state_manager.zynseq.set_tempo(self.state_manager.zynseq.get_tempo() + params[0])
			except (AttributeError, TypeError) as err:
				pass
		else:
			self.state_manager.zynseq.set_tempo(self.state_manager.zynseq.get_tempo() + 1)

	def cuia_tempo_down(self, params=None):
		if params:
			try:
				self.state_manager.zynseq.set_tempo(self.state_manager.zynseq.get_tempo() - params[0])
			except (AttributeError, TypeError) as err:
				pass
		else:
			self.state_manager.zynseq.set_tempo(self.state_manager.zynseq.get_tempo() - 1)

	def cuia_tap_tempo(self, params=None):
		self.screens["tempo"].tap()


	# Zynpot & Zynswitch emulation CUIAs (low level)
	def cuia_zynpot(self, params=None):
		try:
			i = int(params[0])
			d = int(params[1])
			self.get_current_screen_obj().zynpot_cb(i, d)
		except IndexError:
			logging.error("zynpot requires 2 parameters: index, delta, not {params}")
			return
		except Exception as e:
			logging.error(e)

	def cuia_zynswitch(self, params=None):
		try:
			i = params[0]
			d = params[1]
			self.cuia_queue.put_nowait(["zynswitch", [i,d]])
		except IndexError:
			logging.error("zynswitch requires 2 parameters: index, delta, not {params}")
			return
		except Exception as e:
			logging.error(e)

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
	def cuia_select(self, params=None):
		try:
			self.get_current_screen_obj().select(params[0])
		except (AttributeError, TypeError) as err:
			pass

	# Screen/Mode management CUIAs
	def cuia_toggle_screen(self, params=None):
		if params:
			self.toggle_screen(params[0])

	def cuia_show_screen(self, params=None):
		if params:
			self.show_screen_reset(params[0])

	def cuia_screen_main_menu(self, params=None):
		self.show_screen("main_menu")

	def cuia_screen_admin(self, params=None):
		self.show_screen("admin")

	def cuia_screen_audio_mixer(self, params=None):
		self.toggle_screen("audio_mixer")

	def cuia_screen_snapshot(self, params=None):
		self.show_screen("snapshot")

	def cuia_screen_zs3(self, params=None):
		self.show_screen("zs3")

	def cuia_screen_midi_recorder(self, params=None):
		self.show_screen("midi_recorder")

	def cuia_screen_alsa_mixer(self, params=None):
		self.show_screen("alsa_mixer", hmode=zynthian_gui.SCREEN_HMODE_RESET)

	def cuia_screen_zynpad(self, params=None):
		self.show_screen("zynpad")

	def cuia_screen_pattern_editor(self, params=None):
		success = False
		if self.current_screen in ["arranger", "zynpad"]:
			success = self.screens[self.current_screen].show_pattern_editor()
		if not success:
			self.show_screen("pattern_editor")

	def cuia_screen_arranger(self, params=None):
		self.show_screen("arranger")

	def cuia_screen_bank(self, params=None):
		self.show_screen("bank")

	def cuia_screen_preset(self, params=None):
		self.show_screen("preset")

	def cuia_screen_calibrate(self, params=None):
		self.calibrate_touchscreen()

	def cuia_chain_control(self, params=None):
		try:
			# Select chain by ID
			chain_id = params[0]
			# Select chain by index
			if isinstance(chain_id, int):
				index = params[0]
				if index == 0:
					chain_id = "main"
				else:
					chain_id = self.chain_manager.chain_ids_ordered[params[0] - 1]
		except:
			chain_id = self.chain_manager.active_chain_id
		self.chain_control(chain_id)

	cuia_layer_control = cuia_chain_control
	cuia_screen_control = cuia_chain_control

	def cuia_chain_options(self, params=None):
		try:
			# Select chain by ID
			chain_id = params[0]
			# Select chain by index
			if isinstance(chain_id, int):
				index = params[0]
				if index == 0:
					chain_id = "main"
				else:
					chain_id = self.chain_manager.chain_ids_ordered[params[0] - 1]
		except:
			chain_id = self.chain_manager.active_chain_id

		if chain_id is not None:
			self.screens['chain_options'].setup(chain_id)
			self.show_screen('chain_options', hmode=zynthian_gui.SCREEN_HMODE_ADD)

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
				self.chain_manager.get_active_chain().set_current_processor(params)
			except:
				logging.error("Can't set chain passed as CUIA parameter!")
		elif self.current_screen != 'audio_player':
			self.screens["control"].fill_list()
			try:
				self.chain_manager.get_active_chain().set_current_processor(self.screens['control'].screen_processor)
			except:
				logging.warning("Can't set control screen layer! ")

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

	cuia_preset = cuia_bank_preset

	def cuia_preset_fav(self, params=None):
		self.show_favorites()

	def cuia_enable_midi_learn_cc(self, params=None):
		#TODO: Find zctrl
		if len(params) == 2:
			self.state_manager.enable_learn_cc(params[0], params[1])

	def cuia_disable_midi_learn_cc(self, params=None):
		self.state_manager.disable_learn_cc()

	def cuia_enable_midi_learn_pc(self, params=None):
		if params:
			self.state_manager.enable_learn_pc(params[0])
		else:
			self.state_manager.enable_learn_pc("")

	def cuia_disable_midi_learn_pc(self, params=None):
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

	def cuia_action_midi_unlearn(self, params=None):
		try:
			self.screens[self.current_screen].midi_unlearn_action()
		except (AttributeError, TypeError) as err:
			pass

	# Learn control options
	def cuia_midi_learn_control_options(self, params=None):
		if self.current_screen in ("control", "alsa_mixer"):
			self.screens[self.current_screen].midi_learn_options(params[0])

	# Learn control
	def cuia_midi_learn_control(self, params=None):
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

	# Z2 knob touch
	def cuia_z2_zynpot_touch(self, params=None):
		if params:
			try:
				self.screens[self.current_screen].zctrl_touch(params[0])
			except AttributeError:
				pass #TODO: Should all screens be derived from base?

	# V5 knob click
	def cuia_v5_zynpot_switch(self, params):
		i = params[0]
		t = params[1].upper()

		if self.current_screen in ("control", "alsa_mixer"):
			#if i < 3 and t == 'S':
			if t == 'S':
				self.screens[self.current_screen].toggle_midi_learn(i)
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

	def cuia_midi_unlearn_node(self, params=None):
		if params:
			self.chain_manager.remove_midi_learn([params[0], params[1]])

	def cuia_midi_unlearn_chain(self, params=None):
		if params:
			self.chain_manager.clean_midi_learn(params[0])
		else:
			self.chain_manager.clean_midi_learn(self.chain_manager.active_chain_id)

	# MIDI CUIAs
	def cuia_program_change(self, params=None):
		if len(params) > 0:
			pgm = int(params[0])
			if len(params) > 1:
				chan = int(params[1])
			else:
				chan = lib_zyncore.get_midi_active_chan()
			if chan >= 0 and chan < 16 and pgm >= 0 and pgm < 128:
				lib_zyncore.write_zynmidi_program_change(chan, pgm)

	def cuia_zyn_cc(self, params=None):
		if len(params) > 2:
			chan = int(params[0])
			cc = int(params[1])
			if params[-1] == 'R':
				if len(params) > 3:
					lib_zyncore.write_zynmidi_ccontrol_change(chan, cc, int(params[3]))
			else:
				lib_zyncore.write_zynmidi_ccontrol_change(chan, cc, int(params[2]))


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

	# -------------------------------------------------------------------
	# Zynswitch Event Management
	# -------------------------------------------------------------------

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
				return True

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
	# Switches
	# -------------------------------------------------------------------

	def zynswitches(self):
		"""Process physical switch triggers"""

		if not lib_zyncore:
			return
		i = 0
		while i <= zynthian_gui_config.last_zynswitch_index:
			# dtus is 0 if switched pressed, dur of last press or -1 if already processed
			if i < 4 or zynthian_gui_config.custom_switch_ui_actions[i - 4]:
				dtus = lib_zyncore.get_zynswitch(i, zynthian_gui_config.zynswitch_long_us)
				if dtus >= 0:
					self.cuia_queue.put_nowait(["zynswitch", [i, self.zynswitch_timing(dtus)]])
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

		if self.capture_log_fname:
			self.write_capture_log("ZYNSWITCH:P,{}".format(i))

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
			return self.custom_switch_ui_action(i - 4, "P")


	def zynswitch_long(self, i):
		logging.debug('Looooooooong Switch '+str(i))

		if self.capture_log_fname:
			self.write_capture_log("ZYNSWITCH:L,{}".format(i))

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
			return self.custom_switch_ui_action(i-4, "L")


	def zynswitch_bold(self, i):
		logging.debug('Bold Switch '+str(i))

		if self.capture_log_fname:
			self.write_capture_log("ZYNSWITCH:B,{}".format(i))

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
			return self.custom_switch_ui_action(i - 4, "B")


	def zynswitch_short(self, i):
		logging.debug('Short Switch ' + str(i))

		if self.capture_log_fname:
			self.write_capture_log("ZYNSWITCH:S,{}".format(i))

		try:
			if self.screens[self.current_screen].switch(i, 'S'):
				return
		except AttributeError as e:
			pass

		# Default actions for the standard 4 ZynSwitches
		if i == 0:
			self.cuia_menu()

		elif i == 1:
			self.back_screen()

		elif i == 2:
			self.cuia_toggle_midi_learn()

		elif i == 3:
			self.screens[self.current_screen].switch_select('S')

		# Custom ZynSwitches
		elif i >= 4:
			return self.custom_switch_ui_action(i - 4, "S")


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
		if self.current_screen in ("control", "alsa_mixer") and self.screens[self.current_screen].mode == 'control':
			self.screens['control'].midi_learn(i) #TODO: Check zynswitch_X/Y learn

	def zynswitch_Y(self,i):
		logging.debug('Y Switch %d' % i)
		if self.current_screen in ("control", "alsa_mixer") and self.screens[self.current_screen].mode == 'control':
			self.screens['control'].midi_learn_options(i, unlearn_only=True)

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
			while True:
				ev = lib_zyncore.read_zynmidi()
				if ev == 0:
					break

				# Try to manage with configured control devices
				if self.ctrldev_manager.midi_event(ev):
					self.state_manager.status_midi = True
					self.last_event_flag = True
					continue

				evtype = (ev & 0xF00000) >> 20
				chan = (ev & 0x0F0000) >> 16
				#logging.info("MIDI_UI MESSAGE DETAILS: {}, {}".format(chan,evtype))

				# System Messages (Common & RT)
				if evtype == 0xF:
					# Clock
					if chan == 0x8:
						self.state_manager.status_midi_clock = True
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

				# Master MIDI Channel...
				elif chan == zynthian_gui_config.master_midi_channel:
					logging.info("MASTER MIDI MESSAGE: %s" % hex(ev))
					# Webconf configured messages for Snapshot Control...
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
					# Control Change...
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

						if self.state_manager.midi_learn_zctrl:
							self.chain_manager.add_midi_learn(chan, ccnum, self.state_manager.midi_learn_zctrl)
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
								self.cuia_queue.put_nowait([cuia, params])
							# Or normal CUIA
							elif evtype == 0x9 and vel > 0:
								self.cuia_queue.put_nowait([cuia, params])


				# Control Change...
				elif evtype == 0xB:
					self.screens['midi_chan'].midi_chan_activity(chan)
					ccnum = (ev & 0x7F00) >> 8
					ccval = (ev & 0x007F)
					#logging.debug("MIDI CONTROL CHANGE: CH{}, CC{} => {}".format(chan,ccnum,ccval))
					if ccnum < 120:
						# If MIDI learn pending...
						if self.state_manager.midi_learn_zctrl:
							self.screens['control'].midi_learn_bind(chan, ccnum)
							self.show_current_screen()
						# Try processor parameter
						else:
							self.chain_manager.midi_control_change(chan, ccnum, ccval)
							self.state_manager.zynmixer.midi_control_change(chan, ccnum, ccval)
							self.state_manager.alsa_mixer_processor.midi_control_change(chan, ccnum, ccval)
					# Special CCs >= Channel Mode
					elif ccnum == 120:
						self.state_manager.all_sounds_off_chan(chan)
					elif ccnum == 123:
						self.state_manager.all_notes_off_chan(chan)

				# Program Change...
				elif evtype == 0xC:
					pgm = (ev & 0x7F00) >> 8
					logging.info("MIDI PROGRAM CHANGE: CH#{}, PRG#{}".format(chan,pgm))

					# SubSnapShot (ZS3) MIDI learn...
					if self.state_manager.midi_learn_pc is not None:
						self.state_manager.save_zs3(f"{chan}/{pgm}")
						if self.current_screen == "zs3":
							self.screens['zs3'].update_list()
							self.screens['zs3'].disable_midi_learn()
					# Set Preset or ZS3 (sub-snapshot), depending of config option
					else:
						if zynthian_gui_config.midi_prog_change_zs3:
							res = self.state_manager.load_zs3_by_midi_prog(chan, pgm)
						else:
							chan = self.chain_manager.get_active_chain().midi_chan
							res = self.chain_manager.set_midi_prog_preset(chan, pgm)
						if res:
							if self.current_screen == 'audio_mixer':
								self.screens['audio_mixer'].refresh_visible_strips()
							elif self.current_screen == 'control':
								self.chain_control()

				# Note-On...
				elif evtype == 0x9:
					self.screens['midi_chan'].midi_chan_activity(chan)
					#Preload preset (note-on)
					if self.current_screen == 'preset' and zynthian_gui_config.preset_preload_noteon and chan == self.get_current_processor().get_midi_chan():
						self.state_manager.start_busy("preselect preset")
						self.screens['preset'].preselect_action()
						self.state_manager.end_busy("preselect preset")
					#Note Range Learn
					elif self.current_screen == 'midi_key_range' and self.state_manager.midi_learn_state:
						self.screens['midi_key_range'].learn_note_range((ev & 0x7F00) >> 8)
					elif self.current_screen == 'pattern_editor' and self.state_manager.zynseq.libseq.isMidiRecord():
						self.screens['pattern_editor'].midi_note((ev & 0x7F00) >> 8)

				# Flag MIDI event
				self.state_manager.status_midi = True
				self.last_event_flag = True

		except Exception as err:
			logging.exception(err)


	#------------------------------------------------------------------
	# Zynpot Thread
	#------------------------------------------------------------------

	def start_zynpot_thread(self):
		self.zynpot_thread = Thread(target=self.zynpot_thread_task, args=())
		self.zynpot_thread.name = "zynpot"
		self.zynpot_thread.daemon = True # thread dies with the program
		self.zynpot_thread.start()


	def zynpot_thread_task(self):
		while not self.exit_flag:
			self.zynpot_event.wait()
			self.zynpot_event.clear()
			for i in range(0, zynthian_gui_config.num_zynpots):
				if self.zynpot_dval[i] != 0:
					try:
						self.zynpot_lock.acquire()
						dval = self.zynpot_dval[i]
						self.zynpot_dval[i] = 0
						self.zynpot_lock.release()
						self.screens[self.current_screen].zynpot_cb(i, dval)
						self.last_event_flag = True
						if self.capture_log_fname:
							self.write_capture_log("ZYNPOT:{},{}".format(i, dval))
					except Exception as err:
						pass  # Some screens don't use controllers
						logging.exception(err)


	#------------------------------------------------------------------
	# Control Thread
	#------------------------------------------------------------------

	def start_control_thread(self):
		self.control_thread = Thread(target=self.control_thread_task, args=())
		self.control_thread.name = "Control"
		self.control_thread.daemon = True # thread dies with the program
		self.control_thread.start()


	def control_thread_task(self):
		j = 0
		while not self.exit_flag:
			# Read zynswitches, MIDI & OSC events
			self.zynswitch_read()
			self.zynmidi_read()
			self.osc_receive()

			# Every 4 cycles...
			if j > 4:
				j = 0

				# Refresh GUI Controllers
				try:
					self.screens[self.current_screen].plot_zctrls()
				except AttributeError as e:
					#logging.warning(e)
					pass
				except Exception as e:
					logging.error(e)

				# Power Save Mode
				if zynthian_gui_config.power_save_secs > 0:
					if self.last_event_flag:
						self.last_event_ts = monotonic()
						self.last_event_flag = False
						if self.state_manager.power_save_mode:
							self.state_manager.set_power_save_mode(False)
					elif not self.state_manager.power_save_mode and (monotonic() - self.last_event_ts) > zynthian_gui_config.power_save_secs:
						self.state_manager.set_power_save_mode(True)
			else:
				j += 1

			# Wait a little bit...
			sleep(0.01)

		# End Thread task
		self.osc_end()


	def set_event_flag(self):
		self.last_event_flag = True


	def reset_event_flag(self):
		self.last_event_flag = False


	def cb_touch(self, event):
		#logging.debug("CB EVENT TOUCH!!!")
		if self.state_manager.power_save_mode:
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

	def start_busy_thread(self):
		self.busy_thread = Thread(target=self.busy_thread_task, args=())
		self.busy_thread.name = "Busy"
		self.busy_thread.daemon = True # thread dies with the program
		self.busy_thread.start()
		#logging.debug(f"START BUSY {self.busy_thread}")


	def busy_thread_task(self):
		busy_timeout = 0
		busy_warn_time = 200
		while not self.exit_flag:
			try:
				if self.current_screen:
					self.screens[self.current_screen].refresh_loading()
			except Exception as err:
				logging.error(f"zynthian_gui.busy_thread_task() => {err}")
			if self.state_manager.is_busy():
				busy_timeout += 1
			else:
				busy_timeout = 0
			if busy_timeout == busy_warn_time:
				logging.warning(f"Clients have been busy for longer than {int(busy_warn_time / 10)}s: {self.state_manager.busy}")
			sleep(0.1)

	#------------------------------------------------------------------
	# Status Refresh Thread
	#------------------------------------------------------------------

	def start_status_thread(self):
		self.status_thread = Thread(target=self.status_thread_task, args=())
		self.status_thread.name = "Status"
		self.status_thread.daemon = True # thread dies with the program
		self.status_thread.start()


	def status_thread_task(self):
		while not self.exit_flag:
			# When in power save mode:
			# + Make LED refresh faster so the fading effect looks smooth
			# + Don't need to refresh status info because it's not shown
			if self.state_manager.power_save_mode:
				if self.wsleds:
					self.wsleds.update()
				sleep(0.05)
			else:
				self.refresh_status()
				if self.wsleds:
					self.wsleds.update()
				sleep(0.2)


	def refresh_status(self):
		try:
			# Refresh on-screen status
			try:
				self.screens[self.current_screen].refresh_status()
			except AttributeError:
				pass

			# Refresh control device list
			if zynautoconnect.get_mididev_changed():
				zynautoconnect.set_mididev_changed(False)
				try:
					self.ctrldev_manager.refresh_device_list()
				except Exception as err:
					logging.error(err)

			# Refresh status of control devices
			try:
				self.ctrldev_manager.refresh_all()
			except Exception as err:
				logging.error(err)

		except Exception as e:
			logging.exception(e)


	#------------------------------------------------------------------
	# CUIA Thread
	#------------------------------------------------------------------

	def start_cuia_thread(self):
		self.cuia_thread = Thread(target=self.cuia_thread_task, args=())
		self.cuia_thread.name = "CUIA"
		self.cuia_thread.daemon = True # thread dies with the program
		self.cuia_thread.start()


	def cuia_thread_task(self):
		"""Thread task to handle CUIA events
		
		Events are passed via cuia_queue and may be a space separated list:'cuia, param, param...' or list: [cuia, [params]]
		"""

		zynswitch_cuia_ts = [None] * (zynthian_gui_config.num_zynswitches + 4)
		zynswitch_repeat = {}
		zynpot_repeat = {}
		REPEAT_DELAY = 3 # Quantity of repeat intervals to delay before triggering auto repeat
		REPEAT_INTERVAL = 0.15 # Auto repeat interval in seconds

		while not self.exit_flag:
			try:
				event = self.cuia_queue.get(True, REPEAT_INTERVAL)
				params = None
				if isinstance(event, str):
					if event == "__EXIT__":
						break
					# space seperated cuia param,param...
					parts = event.split(" ", 2)
					cuia = parts[0].lower()
					if len(parts) > 1:
						params = parts[1].split(",")
				else:
					# list [cuia, [params]]
					cuia = event[0].lower()
					if len(event) > 1:
						params = event[1]

				if cuia == "zynswitch":
					# zynswitch has parameters: [switch, action] where action is P(ressed), R(eleased), S(hort), B(old), L(ong), X or Y
					try:
						i = int(params[0])
						t = params[1]
						if t == 'R':
							if zynswitch_cuia_ts[i] is None:
								del zynswitch_repeat[i]
								continue
							else:
								dtus = int(1000000 * (monotonic() - zynswitch_cuia_ts[i]))
								zynswitch_cuia_ts[i] = None
								t = self.zynswitch_timing(dtus)
						if t == 'P':
							if self.zynswitch_push(i):
								zynswitch_repeat[i] = REPEAT_DELAY
							else:
								zynswitch_cuia_ts[i] = monotonic()
						else:
							if t == 'S':
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
							if i in zynswitch_repeat:
								del zynswitch_repeat[i]
					except Exception as err:
						logging.error(f"CUIA zynswitch failed with params: {params} and error {err}")

				elif cuia == "zynpot":
					# zynpot has parameters: [pot, delta, 'P'|'R'] 'P','R' is only used for keybinding to zynpot
					if len(params) > 2:
						if params[2] == 'R':
							del zynpot_repeat[i]
						elif params[2] == 'P':
							self.cuia_zynpot(params[:2])
							zynpot_repeat[i] = [REPEAT_DELAY, params]
					else:
						self.cuia_zynpot(params[0], params[1])

				else:
					try:
						cuia_func = getattr(self, "cuia_" + cuia)
						cuia_func(params)
					except AttributeError:
						logging.error(f"Unknown or faulty CUIA '{cuia}' with params {params}")

				self.set_event_flag()

			except Empty:
				for i in zynswitch_repeat:
					if zynswitch_repeat[i]:
						zynswitch_repeat[i] -= 1
					else:
						self.zynswitch_push(i)
				for i in zynpot_repeat:
					if zynpot_repeat[i][0]:
						zynpot_repeat[i][0] -= 1
					else:
						self.cuia_zynpot(zynpot_repeat[i][1])
			except:
				pass

	#------------------------------------------------------------------
	# Thread ending on Exit
	#------------------------------------------------------------------

	def exit(self, code=0):
		# Log exit message
		logging.info("STOPPING ZYNTHIAN-UI...")

		# Signal zynpot thread so it can unlock and finish normally
		self.zynpot_event.set()
		# Light-off LEDs
		if self.wsleds:
			self.wsleds.end()
		# Stop Multitouch driver
		self.multitouch.stop()
		# Stop State manager
		self.state_manager.stop()

		self.exit_code = code
		self.exit_flag = True
		self.cuia_queue.put_nowait("__EXIT__")
		self.exit_wait_count = 0
		self.stop()


	def stop(self):
		running_thread_names = []
		for t in [self.control_thread, self.status_thread, self.busy_thread, self.cuia_thread, self.state_manager.thread, self.multitouch.thread, self.zynpot_thread]:
			if t and t.is_alive():
				running_thread_names.append(t.name)
		if zynautoconnect.is_running():
			running_thread_names.append("Autoconect")
		self.exit_wait_count += 1
		if self.exit_wait_count > 10:
			for i in running_thread_names:
				logging.error(f"{i} thread failed to terminate")
			zynthian_gui_config.top.quit()
			return

		zynthian_gui_config.top.after(160, self.stop)


	#------------------------------------------------------------------
	# Polling
	#------------------------------------------------------------------

	def start_polling(self):
		self.osc_timeout()


	def after(self, msec, func):
		zynthian_gui_config.top.after(msec, func)


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
