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
import signal
#import psutil
#import alsaseq
import logging
import threading
import time
from os.path import isfile
from datetime import datetime
from threading  import Thread, Lock
from subprocess import check_output
from ctypes import c_float, c_double, CDLL
import sched


# Qt modules
from PySide2.QtCore import Qt, QObject, Slot, Signal, Property, QTimer
from PySide2.QtGui import QGuiApplication, QPalette, QColor, QIcon
from PySide2.QtQml import QQmlApplicationEngine


sys.path.insert(1, '/zynthian/zynthian-ui/')
sys.path.insert(1, './zynqtgui')

# Zynthian specific modules
import zynconf
import zynautoconnect
from zynlibs.jackpeak import lib_jackpeak, lib_jackpeak_init
from zyncoder import *
from zyncoder.zyncoder import lib_zyncoder, lib_zyncoder_init
from zyngine import zynthian_zcmidi
from zyngine import zynthian_midi_filter
#from zyngine import zynthian_engine_transport
from zynqtgui import zynthian_gui_config
from zynqtgui.zynthian_gui_controller import zynthian_gui_controller
#from zynqtgui.zynthian_gui_selector import zynthian_gui_selector
from zynqtgui.zynthian_gui_info import zynthian_gui_info
#from zynqtgui.zynthian_gui_option import zynthian_gui_option
from zynqtgui.zynthian_gui_admin import zynthian_gui_admin
from zynqtgui.zynthian_gui_snapshot import zynthian_gui_snapshot
from zynqtgui.zynthian_gui_layer import zynthian_gui_layer
from zynqtgui.zynthian_gui_layer_options import zynthian_gui_layer_options
from zynqtgui.zynthian_gui_engine import zynthian_gui_engine
from zynqtgui.zynthian_gui_midi_chan import zynthian_gui_midi_chan
from zynqtgui.zynthian_gui_midi_cc import zynthian_gui_midi_cc
#from zynqtgui.zynthian_gui_midi_key_range import zynthian_gui_midi_key_range
#from zynqtgui.zynthian_gui_audio_out import zynthian_gui_audio_out
#from zynqtgui.zynthian_gui_midi_out import zynthian_gui_midi_out
#from zynqtgui.zynthian_gui_audio_in import zynthian_gui_audio_in
from zynqtgui.zynthian_gui_bank import zynthian_gui_bank
from zynqtgui.zynthian_gui_preset import zynthian_gui_preset
from zynqtgui.zynthian_gui_control import zynthian_gui_control
#from zynqtgui.zynthian_gui_control_xy import zynthian_gui_control_xy
#from zynqtgui.zynthian_gui_midi_profile import zynthian_gui_midi_profile
#from zynqtgui.zynthian_gui_zs3_learn import zynthian_gui_zs3_learn
#from zynqtgui.zynthian_gui_zs3_options import zynthian_gui_zs3_options
from zynqtgui.zynthian_gui_confirm import zynthian_gui_confirm
#from zynqtgui.zynthian_gui_keyboard import zynthian_gui_keyboard
from zynqtgui.zynthian_gui_keybinding import zynthian_gui_keybinding
from zynqtgui.zynthian_gui_main import zynthian_gui_main
from zynqtgui.zynthian_gui_audio_recorder import zynthian_gui_audio_recorder
from zynqtgui.zynthian_gui_midi_recorder import zynthian_gui_midi_recorder
#if "autoeq" in zynthian_gui_config.experimental_features:
	#from zynqtgui.zynthian_gui_autoeq import zynthian_gui_autoeq
#if "zynseq" in zynthian_gui_config.experimental_features:
	#from zynqtgui.zynthian_gui_stepsequencer import zynthian_gui_stepsequencer
#from zynqtgui.zynthian_gui_touchscreen_calibration import zynthian_gui_touchscreen_calibration

#from zynqtgui.zynthian_gui_control_osc_browser import zynthian_gui_osc_browser

#from zynqtgui.zynthian_gui_selector import zynthian_gui_selector as 

from pathlib import Path
from layerswrapper import LayersController
from layerswrapper import LayersListModel
from controlwrapper import ControlWrapper, ControllerWrapper


#-------------------------------------------------------------------------------
# QObject to bridge status data to QML (ie audio levels, cpu levels etc
#-------------------------------------------------------------------------------
class zynthian_gui_status_data(QObject):
	def __init__(self, parent=None):
		super(zynthian_gui_status_data, self).__init__(parent)
		self.status_info = {}
		self.status_info['cpu_load'] = 0
		self.status_info['peakA'] = 0
		self.status_info['peakB'] = 0
		self.status_info['holdA'] = 0
		self.status_info['holdB'] = 0
		self.status_info['xrun'] = False
		self.status_info['undervoltage'] = False
		self.status_info['overtemp'] = False
		self.status_info['audio_recorder'] = False
		self.status_info['midi_recorder'] = False

		self.dpm_rangedB = 30 # Lowest meter reading in -dBFS
		self.dpm_highdB = 10 # Start of yellow zone in -dBFS
		self.dpm_overdB = 3  # Start of red zone in -dBFS
		self.dpm_high = 1 - self.dpm_highdB / self.dpm_rangedB
		self.dpm_over = 1 - self.dpm_overdB / self.dpm_rangedB


	def set_status(self, status):
		self.status_info = status;
		self.status_changed.emit()

	def get_cpu_load(self):
		return self.status_info['cpu_load']

	def get_peakA(self):
		return self.status_info['peakA']

	def get_peakB(self):
		return self.status_info['peakB']

	def get_holdA(self):
		return self.status_info['holdA']

	def get_holdB(self):
		return self.status_info['holdB']

	def get_xrun(self):
		return self.status_info['xrun']

	def get_undervoltage(self):
		if 'undervoltage' in self.status_info:
			return self.status_info['undervoltage']
		else:
			return False

	def get_overtemp(self):
		if 'overtemp' in self.status_info:
			return self.status_info['overtemp']
		else:
			return False

	def get_audio_recorder(self):
		if 'audio_recorder' in self.status_info:
			return self.status_info['audio_recorder']
		else:
			return None

	def get_midi_recorder(self):
		if 'midi_recorder' in self.status_info:
			return self.status_info['midi_recorder']
		else:
			return None


	def get_rangedB(self):
		return self.dpm_rangedB

	def get_highdB(self):
		return self.dpm_highdB

	def get_overdB(self):
		return self.dpm_overdB

	def get_high(self):
		return self.dpm_high

	def get_over(self):
		return self.dpm_over


	status_changed = Signal()

	cpu_load = Property(float, get_cpu_load, notify = status_changed)
	peakA = Property(float, get_peakA, notify = status_changed)
	peakB = Property(float, get_peakB, notify = status_changed)
	holdA = Property(float, get_holdA, notify = status_changed)
	holdB = Property(float, get_holdB, notify = status_changed)
	xrun = Property(bool, get_xrun, notify = status_changed)
	undervoltage = Property(bool, get_undervoltage, notify = status_changed)
	overtemp = Property(bool, get_overtemp, notify = status_changed)
	audio_recorder = Property(str, get_audio_recorder, notify = status_changed)
	midi_recorder = Property(str, get_midi_recorder, notify = status_changed)

	rangedB = Property(float, get_rangedB, constant = True)
	highdB = Property(float, get_highdB, constant = True)
	overdB = Property(float, get_overdB, constant = True)
	high = Property(float, get_high, constant = True)
	over = Property(float, get_over, constant = True)


#-------------------------------------------------------------------------------
# Zynthian Main GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui(QObject):

	screens_sequence = ("main","layer","bank","preset","control")

	note2cuia = {
		"0": "POWER_OFF",
		"1": "REBOOT",
		"2": "RESTART_UI",
		"3": "RELOAD_MIDI_CONFIG",
		"4": "RELOAD_KEY_BINDING",
		"5": "LAST_STATE_ACTION",

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

		"51": "SELECT",
		"52": "SELECT_UP",
		"53": "SELECT_DOWN",
		"54": "BACK_UP",
		"55": "BACK_DOWN",
		"56": "LAYER_UP",
		"57": "LAYER_DOWN",
		"58": "SNAPSHOT_UP",
		"59": "SNAPSHOT_DOWN",

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

		"80": "SCREEN_ADMIN",
		"81": "SCREEN_LAYER",
		"82": "SCREEN_BANK",
		"83": "SCREEN_PRESET",
		"84": "SCREEN_CONTROL",

		"90": "MODAL_SNAPSHOT_LOAD",
		"91": "MODAL_SNAPSHOT_SAVE",
		"92": "MODAL_AUDIO_RECORDER",
		"93": "MODAL_MIDI_RECORDER",
		"94": "MODAL_ALSA_MIXER",
		"95": "MODAL_STEPSEQ",

		"96": "NEXT_SCREEN",

		"101": "LAYER_ONE",
		"102": "LAYER_TWO",
		"103": "LAYER_THREE",
		"104": "LAYER_FOUR",
		"105": "LAYER_FIVE",
		"106": "LAYER_SIX",
	}



	def __init__(self, parent=None):
		super(zynthian_gui, self).__init__(parent)
		self.zynmidi = None
		self.screens = {}
		self.active_screen = None
		self.modal_screen = None
		self.modal_screen_back = None

		self.modal_timer = QTimer(self)
		self.modal_timer.setInterval(3000)
		self.modal_timer.setSingleShot(False)
		self.modal_timer.timeout.connect(self.close_modal)

		self.info_timer = QTimer(self)
		self.info_timer.setInterval(3000)
		self.info_timer.setSingleShot(False)
		self.info_timer.timeout.connect(self.hide_info)
		# HACK: in order to start the timer from the proper thread
		self.current_modal_screen_id_changed.connect(self.info_timer.start)

		self.curlayer = None
		self._curlayer = None

		self.dtsw = []
		self.polling = False
		self.polling_timer = QTimer(self)
		self.polling_timer.setInterval(200)
		self.polling_timer.setSingleShot(False)
		self.polling_timer.timeout.connect(self.polling_timer_expired)

		self.loading = 0
		self.loading_thread = None
		self.zyncoder_thread = None
		self.zynread_wait_flag = False
		self.zynswitch_defered_event = None
		self.exit_flag = False
		self.exit_code = 0

		self.midi_filter_script = None;
		self.midi_learn_mode = False
		self.midi_learn_zctrl = None

		self.status_info = {}
		self.status_object = zynthian_gui_status_data(self)
		self.status_counter = 0

		self.zynautoconnect_audio_flag = False
		self.zynautoconnect_midi_flag = False

		# Create Lock object to avoid concurrence problems
		self.lock = Lock()

		# Load keyboard binding map
		zynthian_gui_keybinding.getInstance(self).load()

		# Get Jackd Options
		self.jackd_options = zynconf.get_jackd_options()

		# Initialize peakmeter audio monitor if needed
		if not zynthian_gui_config.show_cpu_status:
			try:
				global lib_jackpeak
				lib_jackpeak = lib_jackpeak_init()
				lib_jackpeak.setDecay(c_float(0.2))
				lib_jackpeak.setHoldCount(10)
			except Exception as e:
				logging.error("ERROR initializing jackpeak: %s" % e)

		# Initialize Controllers (Rotary & Switches) & MIDI-router
		try:
			global lib_zyncoder
			#Init Zyncoder Library
			lib_zyncoder_init()
			lib_zyncoder=zyncoder.get_lib_zyncoder()
			self.zynmidi=zynthian_zcmidi()
			#Init Switches
			self.zynswitches_init()
			self.zynswitches_midi_setup()
		except Exception as e:
			logging.error("ERROR initializing Controllers & MIDI-router: %s" % e)

		if "zynseq" in zynthian_gui_config.experimental_features:
			self.libseq = CDLL("/zynthian/zynthian-ui/zynlibs/zynseq/build/libzynseq.so")
			self.libseq.init(True)

	# ---------------------------------------------------------------------------
	# MIDI Router Init & Config
	# ---------------------------------------------------------------------------

	def init_midi(self):
		try:
			global lib_zyncoder
			#Set Global Tuning
			self.fine_tuning_freq = zynthian_gui_config.midi_fine_tuning
			lib_zyncoder.set_midi_filter_tuning_freq(c_double(self.fine_tuning_freq))
			#Set MIDI Master Channel
			lib_zyncoder.set_midi_master_chan(zynthian_gui_config.master_midi_channel)
			#Set MIDI CC automode
			lib_zyncoder.set_midi_ctrl_automode(zynthian_gui_config.midi_cc_automode)
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
		if not hasattr(self, 'osc_server'):
			return
		while self.osc_server.recv(0):
			pass


	#@liblo.make_method("RELOAD_MIDI_CONFIG", None)
	#@liblo.make_method(None, None)
	def osc_cb_all(self, path, args, types, src):
		logging.info("OSC MESSAGE '%s' from '%s'" % (path, src.url))

		parts = path.split("/", 2)
		if parts[0]=="" and parts[1].upper()=="CUIA":
			#Execute action
			self.callable_ui_action(parts[2].upper(), args)
			#Run autoconnect if needed
			self.zynautoconnect_do()
		else:
			logging.warning("Not supported OSC call '{}'".format(path))

		#for a, t in zip(args, types):
		#	logging.debug("argument of type '%s': %s" % (t, a))


	# ---------------------------------------------------------------------------
	# GUI Core Management
	# ---------------------------------------------------------------------------

	def start(self):
		# Initialize jack Transport
		#self.zyntransport = zynthian_engine_transport()

		# Create Core UI Screens
		self.screens['info'] = zynthian_gui_info(self)
		self.screens['confirm'] = zynthian_gui_confirm(self)
		#self.screens['keyboard'] = zynthian_gui_keyboard(self)
		#self.screens['option'] = zynthian_gui_option(self)
		self.screens['engine'] = zynthian_gui_engine(self)
		self.screens['layer'] = zynthian_gui_layer(self)
		self.screens['layer_options'] = zynthian_gui_layer_options(self)
		self.screens['snapshot'] = zynthian_gui_snapshot(self)
		self.screens['midi_chan'] = zynthian_gui_midi_chan(self)
		self.screens['midi_cc'] = zynthian_gui_midi_cc(self)
		#self.screens['midi_key_range'] = zynthian_gui_midi_key_range(self)
		#self.screens['audio_out'] = zynthian_gui_audio_out(self)
		#self.screens['midi_out'] = zynthian_gui_midi_out(self)
		#self.screens['audio_in'] = zynthian_gui_audio_in(self)
		self.screens['bank'] = zynthian_gui_bank(self)
		self.screens['preset'] = zynthian_gui_preset(self)
		self.screens['control'] = zynthian_gui_control(self)
		#self.screens['control_xy'] = zynthian_gui_control_xy(self)
		#self.screens['midi_profile'] = zynthian_gui_midi_profile(self)
		#self.screens['zs3_learn'] = zynthian_gui_zs3_learn(self)
		#self.screens['zs3_options'] = zynthian_gui_zs3_options(self)
		self.screens['main'] = zynthian_gui_main(self)
		self.screens['admin'] = zynthian_gui_admin(self)
		#self.screens['touchscreen_calibration'] = zynthian_gui_touchscreen_calibration(self)
		# Create UI Apps Screens
		#self.screens['alsa_mixer'] = self.screens['control']
		self.screens['audio_recorder'] = zynthian_gui_audio_recorder(self)
		self.screens['midi_recorder'] = zynthian_gui_midi_recorder(self)
		#if "autoeq" in zynthian_gui_config.experimental_features:
			#self.screens['autoeq'] = zynthian_gui_autoeq(self)
		#if "zynseq" in zynthian_gui_config.experimental_features:
			#self.screens['stepseq'] = zynthian_gui_stepsequencer(self)

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
		# Set empty state
		if not snapshot_loaded:
			# Init MIDI Subsystem => MIDI Profile
			self.init_midi()
			self.init_midi_services()
			self.zynautoconnect()
			# Show initial screen
			self.show_screen('main')

		# Start polling threads
		self.start_polling()
		self.start_loading_thread()
		self.start_zyncoder_thread()

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
			exclude = self.active_screen

		exclude_obj = self.screens[exclude]


	def show_screen(self, screen=None):
		if screen is None:
			if self.active_screen:
				screen = self.active_screen
			else:
				screen = "main"

		if screen=="layer" or screen=="bank"  or screen=="preset"  or screen=="control" :
			self.restore_curlayer()

		self.lock.acquire()
		self.hide_screens(exclude=screen)
		self.screens[screen].show()
		self.active_screen = screen
		self.modal_screen = None
		self.modal_screen_back = None
		self.lock.release()
		self.current_screen_id_changed.emit()
		self.current_modal_screen_id_changed.emit()


	def show_active_screen(self):
		self.show_screen()


	def show_modal(self, screen, mode=None):
		if screen=="alsa_mixer":
			if self.modal_screen!=screen and self.screens['layer'].amixer_layer:
				self._curlayer = self.curlayer
				self.screens['layer'].amixer_layer.refresh_controllers()
				self.set_curlayer(self.screens['layer'].amixer_layer)
			else:
				return

		elif screen=="snapshot":
			if mode is None:
				mode = "LOAD"
			self.screens['snapshot'].set_action(mode)

		if self.modal_screen!=screen and self.modal_screen not in ("info","confirm"):
			self.modal_screen_back = self.modal_screen
		self.modal_screen=screen
		self.screens[screen].show()
		self.hide_screens(exclude=screen)
		self.current_modal_screen_id_changed.emit()
		self.current_screen_id_changed.emit()

	def close_modal(self):
		self.cancel_modal_timer()
		if self.modal_screen_back:
			self.show_modal(self.modal_screen_back)
			self.modal_screen_back = None
		else:
			self.show_screen()
		self.current_modal_screen_id_changed.emit()


	def close_modal_timer(self, tms=3000):
		self.cancel_modal_timer()
		self.modal_timer.setInterval(tms)
		self.modal_timer.start()


	def cancel_modal_timer(self):
		self.modal_timer.stop()


	def toggle_modal(self, screen, mode=None):
		if self.modal_screen != screen:
			self.show_modal(screen, mode)
		else:
			self.close_modal()


	def refresh_screen(self):
		screen = self.active_screen
		if screen=='preset' and len(self.curlayer.preset_list)<=1:
			screen='control'
		self.show_screen(screen)


	def get_current_screen(self):
		if self.modal_screen:
			return self.screens[self.modal_screen]
		else:
			return self.screens[self.active_screen]


	def show_confirm(self, text, callback=None, cb_params=None):
		self.modal_screen_back = self.modal_screen
		self.modal_screen='confirm'
		self.screens['confirm'].show(text, callback, cb_params)
		self.hide_screens(exclude='confirm')
		self.current_modal_screen_id_changed.emit()


	def show_keyboard(self, callback, text="", max_chars=None):
		self.modal_screen_back = self.modal_screen
		self.modal_screen="keyboard"
		self.screens['keyboard'].show(callback, text, max_chars)
		self.hide_screens(exclude='keyboard')
		self.current_modal_screen_id_changed.emit()


	def show_info(self, text, tms=None):
		self.modal_screen_back = self.modal_screen
		self.modal_screen = 'info'
		self.screens['info'].show(text)
		self.hide_screens(exclude='info')
		self.current_modal_screen_id_changed.emit()
		logging.error(tms)
		if tms:
			self.hide_info_timer()


	def add_info(self, text, tags=None):
		self.screens['info'].add(text,tags)


	def hide_info(self):
		if self.modal_screen=='info':
			self.close_modal()


	def hide_info_timer(self, tms=3000):
		if self.modal_screen=='info':
			self.cancel_info_timer()
			self.info_timer.setInterval(tms)
			self.info_timer.start()


	def cancel_info_timer(self):
		self.info_timer.stop()


	def calibrate_touchscreen(self):
		self.show_modal('touchscreen_calibration')


	def load_snapshot(self):
		self.show_modal("snapshot","LOAD")


	def save_snapshot(self):
		self.show_modal("snapshot","SAVE")


	def layer_control(self, layer=None):
		modal = False
		if layer is not None:
			if layer in self.screens['layer'].root_layers:
				self._curlayer = None
			else:
				modal = True
				self._curlayer = self.curlayer

			self.set_curlayer(layer)

		if self.curlayer:
			# If there is a preset selection for the active layer ...
			if zynthian_gui_config.automatically_show_control_page and self.curlayer.get_preset_name():
				self.show_screen('control')
			else:
				if self.curlayer.get_preset_name():
					self.screens['control'].show()

				if self.screens['layer'].auto_next_screen:
					if modal:
						self.show_modal('bank')
					else:
						self.show_screen('bank')
				else:
					if modal:
						self.show_modal('layer')
					else:
						self.show_screen('layer')
				# If there is only one bank, jump to preset selection
				if len(self.curlayer.bank_list)<=1:
					self.screens['bank'].select_action(0)


	def show_control(self):
		self.restore_curlayer()
		self.layer_control()


	def enter_midi_learn_mode(self):
		self.midi_learn_mode = True
		self.midi_learn_zctrl = None
		lib_zyncoder.set_midi_learning_mode(1)
		self.screens['control'].refresh_midi_bind()
		self.screens['control'].set_select_path()
		#self.show_modal('zs3_learn')


	def exit_midi_learn_mode(self):
		self.midi_learn_mode = False
		self.midi_learn_zctrl = None
		lib_zyncoder.set_midi_learning_mode(0)
		self.screens['control'].refresh_midi_bind()
		self.screens['control'].set_select_path()
		self.show_active_screen()


	def show_control_xy(self, xctrl, yctrl):
		self.modal_screen='control_xy'
		self.screens['control_xy'].set_controllers(xctrl, yctrl)
		self.screens['control_xy'].show()
		self.hide_screens(exclude='control_xy')
		self.active_screen='control'
		self.screens['control'].set_mode_control()
		logging.debug("SHOW CONTROL-XY => %s, %s" % (xctrl.symbol, yctrl.symbol))
		self.current_modal_screen_id_changed.emit()


	def set_curlayer(self, layer, save=False):
		if layer is not None:
			if save:
				self._curlayer = self.curlayer
			self.curlayer = layer
			self.screens['bank'].fill_list()
			self.screens['bank'].show()
			self.screens['preset'].fill_list()
			self.screens['preset'].show()
			self.screens['control'].fill_list()
			self.screens['control'].show()
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
			if curlayer_chan is not None and zynthian_gui_config.midi_single_active_channel:
				active_chan = curlayer_chan 
				cur_active_chan = lib_zyncoder.get_midi_active_chan()
				if cur_active_chan==active_chan:
					return
				else:
					logging.debug("ACTIVE CHAN: {} => {}".format(cur_active_chan, active_chan))
					#if cur_active_chan>=0:
					#	self.all_notes_off_chan(cur_active_chan)

		lib_zyncoder.set_midi_active_chan(active_chan)
		self.zynswitches_midi_setup(curlayer_chan)


	def get_curlayer_wait(self):
		#Try until layer is ready
		for j in range(100):
			if self.curlayer:
				return self.curlayer
			else:
				time.sleep(0.1)


	def is_single_active_channel(self):
		return zynthian_gui_config.midi_single_active_channel

	# -------------------------------------------------------------------
	# Callable UI Actions
	# -------------------------------------------------------------------

	def callable_ui_action(self, cuia, params=None):
		logging.debug("CUIA '{}' => {}".format(cuia,params))

		if cuia == "POWER_OFF":
			self.screens['admin'].power_off_confirmed()

		elif cuia == "REBOOT":
			self.screens['admin'].reboot_confirmed()

		elif cuia == "RESTART_UI":
			self.screens['admin'].restart_gui()

		elif cuia == "RELOAD_MIDI_CONFIG":
			self.reload_midi_config()

		elif cuia == "RELOAD_KEY_BINDING":
			zynthian_gui_keybinding.getInstance(self).load()

		elif cuia == "LAST_STATE_ACTION":
			self.screens['admin'].last_state_action()

		elif cuia == "ALL_NOTES_OFF":
			self.all_notes_off()
			time.sleep(0.1)
			self.raw_all_notes_off()

		elif cuia == "ALL_SOUNDS_OFF" or cuia == "ALL_OFF":
			self.all_notes_off()
			self.all_sounds_off()
			time.sleep(0.1)
			self.raw_all_notes_off()

		elif cuia == "START_AUDIO_RECORD":
			self.screens['audio_recorder'].start_recording()

		elif cuia == "STOP_AUDIO_RECORD":
			self.screens['audio_recorder'].stop_recording()

		elif cuia == "TOGGLE_AUDIO_RECORD":
			self.screens['audio_recorder'].toggle_recording()

		elif cuia == "START_AUDIO_PLAY":
			self.screens['audio_recorder'].start_playing()

		elif cuia == "STOP_AUDIO_PLAY":
			self.screens['audio_recorder'].stop_playing()

		elif cuia == "TOGGLE_AUDIO_PLAY":
			self.screens['audio_recorder'].toggle_playing()

		elif cuia == "START_MIDI_RECORD":
			self.screens['midi_recorder'].start_recording()

		elif cuia == "STOP_MIDI_RECORD":
			self.screens['midi_recorder'].stop_recording()

		elif cuia == "TOGGLE_MIDI_RECORD":
			self.screens['midi_recorder'].toggle_recording()

		elif cuia == "START_MIDI_PLAY":
			self.screens['midi_recorder'].start_playing()

		elif cuia == "STOP_MIDI_PLAY":
			self.screens['midi_recorder'].stop_playing()

		elif cuia == "TOGGLE_MIDI_PLAY":
			self.screens['midi_recorder'].toggle_playing()

		elif cuia == "SELECT":
			try:
				self.get_current_screen().select(params[0])
			except:
				pass

		elif cuia == "SELECT_UP":
			try:
				self.get_current_screen().select_up()
			except:
				pass

		elif cuia == "SELECT_DOWN":
			try:
				self.get_current_screen().select_down()
			except:
				pass

		elif cuia == "BACK_UP":
			try:
				self.get_current_screen().back_up()
			except:
				pass

		elif cuia == "BACK_DOWN":
			try:
				self.get_current_screen().back_down()
			except:
				pass

		elif cuia == "LAYER_UP":
			try:
				self.screens['layer'].layer_up()
			except:
				pass

		elif cuia == "LAYER_DOWN":
			try:
				self.screens['layer'].layer_down()
			except:
				pass

		elif cuia == "SNAPSHOT_UP":
			try:
				self.get_current_screen().snapshot_up()
			except:
				pass

		elif cuia == "SNAPSHOT_DOWN":
			try:
				self.get_current_screen().snapshot_down()
			except:
				pass

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

		elif cuia == "SCREEN_ADMIN":
			self.show_screen("admin")

		elif cuia == "SCREEN_LAYER":
			self.show_screen("layer")

		elif cuia == "SCREEN_BANK":
			self.show_screen("bank")

		elif cuia == "SCREEN_PRESET":
			self.show_screen("preset")

		elif cuia == "SCREEN_CONTROL":
			self.show_screen("control")

		elif cuia == "MODAL_SNAPSHOT_LOAD":
			self.toggle_modal("snapshot", "LOAD")

		elif cuia == "MODAL_SNAPSHOT_SAVE":
			self.toggle_modal("snapshot", "SAVE")

		elif cuia == "MODAL_AUDIO_RECORDER":
			self.toggle_modal("audio_recorder")

		elif cuia == "MODAL_MIDI_RECORDER":
			self.toggle_modal("midi_recorder")

		elif cuia == "MODAL_ALSA_MIXER":
			self.toggle_modal("alsa_mixer")

		elif cuia == "MODAL_STEPSEQ" and "zynseq" in zynthian_gui_config.experimental_features:
			self.toggle_modal("stepseq")

		elif cuia == "NEXT_SCREEN":
			# Try to call next_action method:
			if self.modal_screen:
				try:
					self.screens[self.modal_screen].next_action()
				except:
					pass
			else:
				try:
					self.screens[self.active_screen].next_action()
					logging.error(self.screens[self.active_screen].next_action)
				except:
					pass

		elif cuia == "LAYER_ONE":
			self.screens['layer'].activate_layer(0)
		elif cuia == "LAYER_TWO":
			self.screens['layer'].activate_layer(1)
		elif cuia == "LAYER_THREE":
			self.screens['layer'].activate_layer(2)
		elif cuia == "LAYER_FOUR":
			self.screens['layer'].activate_layer(3)
		elif cuia == "LAYER_FIVE":
			self.screens['layer'].activate_layer(4)
		elif cuia == "LAYER_SIX":
			self.screens['layer'].activate_layer(5)




	def custom_switch_ui_action(self, i, t):
		try:
			if t in zynthian_gui_config.custom_switch_ui_actions[i]:
				self.callable_ui_action(zynthian_gui_config.custom_switch_ui_actions[i][t])
		except Exception as e:
			logging.warning(e)


	# -------------------------------------------------------------------
	# Switches
	# -------------------------------------------------------------------


	# Init GPIO Switches
	def zynswitches_init(self):
		if lib_zyncoder:
			ts=datetime.now()
			logging.info("SWITCHES INIT...")
			for i,pin in enumerate(zynthian_gui_config.zynswitch_pin):
				self.dtsw.append(ts)
				lib_zyncoder.setup_zynswitch(i,pin)
				logging.info("SETUP ZYNSWITCH {} => wpGPIO {}".format(i, pin))


	def zynswitches_midi_setup(self, curlayer_chan=None):
		logging.info("MIDI SWITCHES SETUP...")

		# Configure Custom Switches
		for i in range(0, zynthian_gui_config.n_custom_switches):
			swi = 4 + i
			event = zynthian_gui_config.custom_switch_midi_events[i]
			if event is not None:
				if event['chan'] is not None:
					midi_chan = event['chan']
				else:
					midi_chan = curlayer_chan

				if midi_chan is not None:
					lib_zyncoder.setup_zynswitch_midi(swi, event['type'], midi_chan, event['num'])
					logging.info("MIDI ZYNSWITCH {}: {} CH#{}, {}".format(swi, event['type'], midi_chan, event['num']))
				else:
					lib_zyncoder.setup_zynswitch_midi(swi, 0, 0, 0)
					logging.info("MIDI ZYNSWITCH {}: DISABLED!".format(swi))

		# Configure Zynaptik Analog Inputs (CV-IN)
		for i, event in enumerate(zynthian_gui_config.zynaptik_ad_midi_events):
			if event is not None:
				if event['chan'] is not None:
					midi_chan = event['chan']
				else:
					midi_chan = curlayer_chan

				if midi_chan is not None:
					lib_zyncoder.setup_zynaptik_cvin(i, event['type'], midi_chan, event['num'])
					logging.info("ZYNAPTIK CV-IN {}: {} CH#{}, {}".format(i, event['type'], midi_chan, event['num']))
				else:
					lib_zyncoder.disable_zynaptik_cvin(i)
					logging.info("ZYNAPTIK CV-IN {}: DISABLED!".format(i))

		# Configure Zyntof Inputs (Distance Sensor)
		for i, event in enumerate(zynthian_gui_config.zyntof_midi_events):
			if event is not None:
				if event['chan'] is not None:
					midi_chan = event['chan']
				else:
					midi_chan = curlayer_chan

				if midi_chan is not None:
					lib_zyncoder.setup_zyntof(i, event['type'], midi_chan, event['num'])
					logging.info("ZYNTOF {}: {} CH#{}, {}".format(i, event['type'], midi_chan, event['num']))
				else:
					lib_zyncoder.disable_zyntof(i)
					logging.info("ZYNTOF {}: DISABLED!".format(i))


	def zynswitches(self):
		if lib_zyncoder:
			for i in range(len(zynthian_gui_config.zynswitch_pin)):
				dtus=lib_zyncoder.get_zynswitch_dtus(i, zynthian_gui_config.zynswitch_long_us)
				if dtus>zynthian_gui_config.zynswitch_long_us:
					self.zynswitch_long(i)
					return
				if dtus>zynthian_gui_config.zynswitch_bold_us:
					# Double switches must be bold!!! => by now ...
					if self.zynswitch_double(i):
						return
					self.zynswitch_bold(i)
					return
				if dtus>0:
					#print("Switch "+str(i)+" dtus="+str(dtus))
					self.zynswitch_short(i)


	def zynswitch_long(self,i):
		logging.info('Looooooooong Switch '+str(i))
		self.start_loading()

		# Standard 4 ZynSwitches
		if i==0 and "zynseq" in zynthian_gui_config.experimental_features:
			self.toggle_modal("stepseq")

		elif i==1:
			#self.callable_ui_action("ALL_OFF")
			self.show_modal("admin")

		elif i==2:
			self.show_modal("alsa_mixer")

		elif i==3:
			self.screens['admin'].power_off()

		# Custom ZynSwitches
		elif i>=4:
			self.custom_switch_ui_action(i-4, "L")

		self.stop_loading()


	def zynswitch_bold(self,i):
		logging.info('Bold Switch '+str(i))
		self.start_loading()

		if self.modal_screen in ['stepseq', 'keyboard']:
			self.stop_loading()
			if self.screens[self.modal_screen].switch(i, 'B'):
				return

		# Standard 4 ZynSwitches
		if i==0:
			if self.active_screen=='layer' and self.modal_screen!='stepseq':
				self.show_modal('stepseq')
			else:
				if self.active_screen=='preset':
					self.screens['preset'].restore_preset()
				self.show_screen('layer')

		elif i==1:
			if self.modal_screen:
				logging.debug("CLOSE MODAL => " + self.modal_screen)
				self.show_screen('main')

			elif self.active_screen=='preset':
				self.screens['preset'].restore_preset()
				self.show_screen('control')

			elif self.active_screen in ['main', 'admin'] and len(self.screens['layer'].layers)>0:
				self.show_control()

			else:
				self.show_screen('main')

		elif i==2:
			self.load_snapshot()

		elif i==3:
			if self.modal_screen:
				self.screens[self.modal_screen].switch_select('B')
			else:
				self.screens[self.active_screen].switch_select('B')

		# Custom ZynSwitches
		elif i>=4:
			self.custom_switch_ui_action(i-4, "B")

		self.stop_loading()


	def zynswitch_short(self,i):
		logging.info('Short Switch '+str(i))
		print('Short Switch Triggered'+str(i))
		if self.modal_screen in ['stepseq']:
			if self.screens[self.modal_screen].switch(i, 'S'):
				return

		self.start_loading()

		# Standard 4 ZynSwitches
		if i==0:
			if self.active_screen=='control' or self.modal_screen=='alsa_mixer':
				if self.screens['layer'].get_num_root_layers()>1:
					logging.info("Next layer")
					self.screens['layer'].next(True)
				else:
					self.show_screen('layer')

			elif self.active_screen=='layer':
				if self.modal_screen is not None:
					self.show_screen('layer')
				elif self.screens['layer'].get_num_root_layers()>1:
					logging.info("Next layer")
					self.screens['layer'].next(False)

			else:
				if self.active_screen=='preset':
					self.screens['preset'].restore_preset()
				self.show_screen('layer')

		elif i==1:
			screen_back = None
			# If modal screen ...
			if self.modal_screen:
				logging.debug("CLOSE MODAL => " + self.modal_screen)

				# Try to call modal back_action method:
				try:
					screen_back = self.screens[self.modal_screen].back_action()
					logging.debug("SCREEN BACK => " + screen_back)
				except:
					pass

				# Back to previous screen or modal
				if screen_back is None:
					if self.modal_screen_back:
						screen_back = self.modal_screen_back
					else:
						screen_back = self.active_screen

			else:
				try:
					screen_back = self.screens[self.active_screen].back_action()
				except:
					pass

				# Back to screen-1 by default ...
				if screen_back is None:
					j = self.screens_sequence.index(self.active_screen)-1
					if j<0: 
						if len(self.screens['layer'].layers)>0 and self.curlayer:
							j = len(self.screens_sequence)-1
						else:
							j = 0
					screen_back = self.screens_sequence[j]

			# If there is only one preset, go back to bank selection
			if screen_back=='preset' and len(self.curlayer.preset_list)<=1:
				screen_back = 'bank'

			# If there is only one bank, go back to layer selection
			if screen_back=='bank' and len(self.curlayer.bank_list)<=1:
				screen_back = 'layer'

			if screen_back:
				logging.debug("BACK TO SCREEN => {}".format(screen_back))
				if screen_back in self.screens_sequence:
					self.show_screen(screen_back)
				else:
					self.show_modal(screen_back)
					self.modal_screen_back = None

		elif i==2:
			if self.modal_screen=='snapshot':
				self.screens['snapshot'].next()

			elif self.modal_screen=='audio_recorder':
				self.show_modal('midi_recorder')

			elif self.modal_screen=='midi_recorder':
				self.show_modal('audio_recorder')

			elif (self.active_screen=='control' or self.modal_screen=='alsa_mixer') and self.screens['control'].mode=='control':
				if self.midi_learn_mode or self.midi_learn_zctrl:
					if self.modal_screen=='zs3_learn':
						self.show_screen('control')
					elif zynthian_gui_config.midi_prog_change_zs3:
						self.show_modal('zs3_learn')
				else:
					self.enter_midi_learn_mode()

			elif self.active_screen=='bank':
				self.screens['preset'].enable_only_favs()
				self.show_screen('preset')

			elif self.active_screen=='preset':
				self.screens['preset'].toggle_only_favs()

			elif len(self.screens['layer'].layers)>0:
				self.enter_midi_learn_mode()
				self.show_modal("zs3_learn")

			else:
				self.load_snapshot()

		elif i==3:
			if self.modal_screen:
				self.screens[self.modal_screen].switch_select('S')
			else:
				self.screens[self.active_screen].switch_select('S')

		# Custom ZynSwitches
		elif i>=4:
			self.custom_switch_ui_action(i-4, "S")

		self.stop_loading()


	def zynswitch_double(self,i):
		self.dtsw[i]=datetime.now()
		for j in range(4):
			if j==i: continue
			if abs((self.dtsw[i]-self.dtsw[j]).total_seconds())<0.3:
				self.start_loading()
				dswstr=str(i)+'+'+str(j)
				logging.info('Double Switch '+dswstr)
				#self.show_control_xy(i,j)
				self.show_screen('control')
				self.screens['control'].set_xyselect_mode(i,j)
				self.stop_loading()
				return True


	def zynswitch_X(self,i):
		logging.info('X Switch %d' % i)
		if self.active_screen=='control' and self.screens['control'].mode=='control':
			self.screens['control'].midi_learn(i)


	def zynswitch_Y(self,i):
		logging.info('Y Switch %d' % i)
		if self.active_screen=='control' and self.screens['control'].mode=='control':
			self.screens['control'].midi_unlearn(i)


	#------------------------------------------------------------------
	# Switch Defered Event
	#------------------------------------------------------------------


	def zynswitch_defered(self, t, i):
		self.zynswitch_defered_event=(t,i)


	def zynswitch_defered_exec(self):
		if self.zynswitch_defered_event is not None:
			#Copy event and clean variable
			event=copy.deepcopy(self.zynswitch_defered_event)
			self.zynswitch_defered_event=None
			#Process event
			if event[0]=='S':
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
	# Threads
	#------------------------------------------------------------------


	def start_zyncoder_thread(self):
		if lib_zyncoder:
			self.zyncoder_thread=Thread(target=self.zyncoder_thread_task, args=())
			self.zyncoder_thread.daemon = True # thread dies with the program
			self.zyncoder_thread.start()


	def zyncoder_thread_task(self):
		while not self.exit_flag:
			self.zyncoder_read()
			self.zynmidi_read()
			self.osc_receive()
			self.plot_zctrls()
			time.sleep(0.04)
			if self.zynread_wait_flag:
				time.sleep(0.3)
				self.zynread_wait_flag=False


	def zyncoder_read(self):
		if not self.loading: #TODO Es necesario???
			try:
				# TODO: figure out the multithreading error

				#Read Zyncoders
				self.lock.acquire()
				if self.modal_screen:
					free_zyncoders = self.screens[self.modal_screen].zyncoder_read()
				else:
					free_zyncoders = self.screens[self.active_screen].zyncoder_read()

				if free_zyncoders:
					self.screens["control"].zyncoder_read(free_zyncoders)

				self.lock.release()
				
				#Zynswitches
				self.zynswitch_defered_exec()
				self.zynswitches()

			except Exception as err:
				self.reset_loading()
				logging.exception(err)

			#Run autoconnect if needed
			self.zynautoconnect_do()


	def zynmidi_read(self):
		try:
			while lib_zyncoder:
				ev=lib_zyncoder.read_zynmidi()
				if ev==0: break

				evtype = (ev & 0xF00000) >> 20
				chan = (ev & 0x0F0000) >> 16

				if evtype==0xF and chan==0x8:
					self.status_info['midi_clock'] = True
				else:
					self.status_info['midi'] = True

				#logging.info("MIDI_UI MESSAGE: {}".format(hex(ev)))
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
					if self.midi_learn_mode and self.modal_screen=='zs3_learn':
						if self.screens['layer'].save_midi_chan_zs3(chan, pgm):
							logging.info("ZS3 Saved: CH{} => {}".format(chan,pgm))
							self.exit_midi_learn_mode()

					# Set Preset or ZS3 (sub-snapshot), depending of config option
					else:
						if zynthian_gui_config.midi_prog_change_zs3:
							self.screens['layer'].set_midi_chan_zs3(chan, pgm)
						else:
							self.screens['layer'].set_midi_chan_preset(chan, pgm)

						#if not self.modal_screen and self.curlayer and chan==self.curlayer.get_midi_chan():
						#	self.show_screen('control')

				# Note-On ...
				elif evtype==0x9:
					self.screens['midi_chan'].midi_chan_activity(chan)
					#Preload preset (note-on)
					if zynthian_gui_config.preset_preload_noteon and self.active_screen=='preset' and chan==self.curlayer.get_midi_chan():
						self.start_loading()
						self.screens['preset'].preselect_action()
						self.stop_loading()
					#Note Range Learn
					if self.modal_screen=='midi_key_range':
						note = (ev & 0x7F00)>>8
						self.screens['midi_key_range'].learn_note_range(note)

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

		except Exception as err:
			self.reset_loading()
			logging.exception(err)


	def plot_zctrls(self):
		try:
			if self.modal_screen:
				self.screens[self.modal_screen].plot_zctrls()
			else:
				self.screens[self.active_screen].plot_zctrls()
		except AttributeError:
			pass
		except Exception as e:
			logging.error(e)


	def start_loading_thread(self):
		self.loading_thread=Thread(target=self.loading_refresh, args=())
		self.loading_thread.daemon = True # thread dies with the program
		self.loading_thread.start()


	def start_loading(self):
		self.loading=self.loading+1
		if self.loading<1: self.loading=1
		self.is_loading_changed.emit()
		#logging.debug("START LOADING %d" % self.loading)


	def stop_loading(self):
		self.loading=self.loading-1
		if self.loading<0: self.loading=0
		self.is_loading_changed.emit()
		#logging.debug("STOP LOADING %d" % self.loading)


	def reset_loading(self):
		self.is_loading_changed.emit()
		self.loading=0

	def get_is_loading(self):
		return self.loading > 0

	# FIXME: is this necessary?
	def loading_refresh(self):
		while not self.exit_flag:
			try:
				if self.modal_screen:
					self.screens[self.modal_screen].refresh_loading()
				else:
					self.screens[self.active_screen].refresh_loading()
			except Exception as err:
				logging.error("zynthian_gui.loading_refresh() => %s" % err)
			time.sleep(0.1)


	def wait_threads_end(self, n=20):
		logging.debug("Awaiting threads to end ...")

		while (self.loading_thread.is_alive() or self.zyncoder_thread.is_alive() or zynautoconnect.is_running()) and n>0:
			time.sleep(0.1)
			n -= 1

		if n<=0:
			logging.error("Reached maximum count while awaiting threads to end!")
			return False
		else:
			logging.debug("Remaining {} active threads...".format(threading.active_count()))
			time.sleep(0.5)
			return True


	def exit(self, code=0):
		self.exit_flag=True
		self.exit_code=code


	#------------------------------------------------------------------
	# Polling
	#------------------------------------------------------------------


	def start_polling(self):
		self.polling=True
		self.polling_timer.start()
		self.zyngine_refresh()
		self.refresh_status()


	def stop_polling(self):
		self.polling=False
		self.polling_timer.stop()

	def polling_timer_expired(self):
		self.zyngine_refresh()
		self.refresh_status()
		#logging.error("refreshed status")

	# FIXME: is this actually used?
	def after(self, msec, func):
		QTimer.singleShot(msec, func)


	def zyngine_refresh(self):
		try:
			# Capture exit event and finish
			if self.exit_flag:
				self.stop()
				self.wait_threads_end()
				logging.info("EXITING ZYNTHIAN-UI ...")
				zynthian_gui_config.app.exit(self.exit_code)
				return
			# Refresh Current Layer
			elif self.curlayer and not self.loading:
				self.curlayer.refresh()

		except Exception as e:
			self.reset_loading()
			logging.exception(e)

		# Poll
		#if self.polling:
			#QTimer.singleShot(160, self.zyngine_refresh)


	def refresh_status(self):
		if self.exit_flag:
			return

		try:
			if zynthian_gui_config.show_cpu_status:
				# Get CPU Load
				#self.status_info['cpu_load'] = max(psutil.cpu_percent(None, True))
				self.status_info['cpu_load'] = zynautoconnect.get_jackd_cpu_load()
			else:
				# Get audio peak level
				self.status_info['peakA'] = lib_jackpeak.getPeak(0)
				self.status_info['peakB'] = lib_jackpeak.getPeak(1)
				self.status_info['holdA'] = lib_jackpeak.getHold(0)
				self.status_info['holdB'] = lib_jackpeak.getHold(1)

			# Get Status Flags (once each 5 refreshes)
			if self.status_counter>5:
				self.status_counter = 0

				self.status_info['undervoltage'] = False
				self.status_info['overtemp'] = False
				try:
					# Get ARM flags
					res = check_output(("vcgencmd", "get_throttled")).decode('utf-8','ignore')
					thr = int(res[12:],16)
					if thr & 0x1:
						self.status_info['undervoltage'] = True
					elif thr & (0x4 | 0x2):
						self.status_info['overtemp'] = True

				except Exception as e:
					logging.error(e)

				try:
					# Get Recorder Status
					self.status_info['audio_recorder'] = self.screens['audio_recorder'].get_status()
					self.status_info['midi_recorder'] = self.screens['midi_recorder'].get_status()

				except Exception as e:
					logging.error(e)

			else:
				self.status_counter += 1

			# Refresh On-Screen Status
			try:
				self.status_object.set_status(self.status_info)

				if self.modal_screen:
					self.screens[self.modal_screen].refresh_status(self.status_info)
				elif self.active_screen:
					self.screens[self.active_screen].refresh_status(self.status_info)
			except AttributeError:
				pass

			# Clean some status_info
			self.status_info['xrun'] = False
			self.status_info['midi'] = False
			self.status_info['midi_clock'] = False

			#if self.polling:
				#QTimer.singleShot(200, self.refresh_status)

		except Exception as e:
			logging.exception(e)

		# Poll
		#if self.polling:
			#QTimer.singleShot(200, self.refresh_status)


	@Slot(str)
	def process_keybinding_shortcut(self, keyseq):
		action = zynthian_gui_keybinding.getInstance().get_key_action(keyseq)

		if action != None:
			zyngui.callable_ui_action(action)


	#------------------------------------------------------------------
	# Engine OSC callbacks => No concurrency!! 
	#------------------------------------------------------------------


	def cb_osc_bank_view(self, path, args):
		pass


	def cb_osc_ctrl(self, path, args):
		#print ("OSC CTRL: " + path + " => "+str(args[0]))
		if path in self.screens['control'].zgui_controllers_map.keys():
			self.screens['control'].zgui_controllers_map[path].set_init_value(args[0])


	#------------------------------------------------------------------
	# All Notes/Sounds Off => PANIC!
	#------------------------------------------------------------------


	def all_sounds_off(self):
		logging.info("All Sounds Off!")
		for chan in range(16):
			lib_zyncoder.ui_send_ccontrol_change(chan, 120, 0)


	def all_notes_off(self):
		logging.info("All Notes Off!")
		for chan in range(16):
			lib_zyncoder.ui_send_ccontrol_change(chan, 123, 0)


	def raw_all_notes_off(self):
		logging.info("Raw All Notes Off!")
		lib_zyncoder.ui_send_all_notes_off()


	def all_sounds_off_chan(self, chan):
		logging.info("All Sounds Off for channel {}!".format(chan))
		lib_zyncoder.ui_send_ccontrol_change(chan, 120, 0)


	def all_notes_off_chan(self, chan):
		logging.info("All Notes Off for channel {}!".format(chan))
		lib_zyncoder.ui_send_ccontrol_change(chan, 123, 0)


	def raw_all_notes_off_chan(self, chan):
		logging.info("Raw All Notes Off for channel {}!".format(chan))
		lib_zyncoder.ui_send_all_notes_off_chan(chan)


	#------------------------------------------------------------------
	# MPE initialization
	#------------------------------------------------------------------

	def init_mpe_zones(self, lower_n_chans, upper_n_chans):
		# Configure Lower Zone 
		if not isinstance(lower_n_chans, int) or lower_n_chans<0 or lower_n_chans>0xF:
			logging.error("Can't initialize MPE Lower Zone. Incorrect num of channels ({})".format(lower_n_chans))
		else:
			lib_zyncoder.ctrlfb_send_ccontrol_change(0x0, 0x79, 0x0)
			lib_zyncoder.ctrlfb_send_ccontrol_change(0x0, 0x64, 0x6)
			lib_zyncoder.ctrlfb_send_ccontrol_change(0x0, 0x65, 0x0)
			lib_zyncoder.ctrlfb_send_ccontrol_change(0x0, 0x06, lower_n_chans)

		# Configure Upper Zone 
		if not isinstance(upper_n_chans, int) or upper_n_chans<0 or upper_n_chans>0xF:
			logging.error("Can't initialize MPE Upper Zone. Incorrect num of channels ({})".format(upper_n_chans))
		else:
			lib_zyncoder.ctrlfb_send_ccontrol_change(0xF, 0x79, 0x0)
			lib_zyncoder.ctrlfb_send_ccontrol_change(0xF, 0x64, 0x6)
			lib_zyncoder.ctrlfb_send_ccontrol_change(0xF, 0x65, 0x0)
			lib_zyncoder.ctrlfb_send_ccontrol_change(0xF, 0x06, upper_n_chans)

	#------------------------------------------------------------------
	# MIDI learning
	#------------------------------------------------------------------


	def init_midi_learn(self, zctrl):
		self.midi_learn_zctrl = zctrl
		lib_zyncoder.set_midi_learning_mode(1)
		self.screens['control'].refresh_midi_bind()
		self.screens['control'].set_select_path()


	def end_midi_learn(self):
		self.midi_learn_zctrl = None
		lib_zyncoder.set_midi_learning_mode(0)
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


	def allow_headphones(self):
		return self.screens['layer'].amixer_layer.engine.allow_headphones()


	def get_current_screen_id(self):
		if self.modal_screen:
			return self.modal_screen
		else:
			return self.active_screen

	def get_current_modal_screen_id(self):
		return self.modal_screen

	def get_status_information(self):
		return self.status_object

	def get_keybinding(self):
		return zynthian_gui_keybinding.getInstance(self)


	def get_info(self):
		return self.screens['info']

	def get_confirm(self):
		return self.screens['confirm']

	def get_main(self):
		return self.screens['main']

	def get_engine(self):
		return self.screens['engine']

	def get_layer(self):
		return self.screens['layer']

	def get_layer_options(self):
		return self.screens['layer_options']

	def get_admin(self):
		return self.screens['admin']

	def get_snapshot(self):
		return self.screens['snapshot']

	def get_midi_chan(self):
		return self.screens['midi_chan']

	def get_bank(self):
		return self.screens['bank']

	def get_preset(self):
		return self.screens['preset']

	def get_control(self):
		return self.screens['control']

	def get_audio_recorder(self):
		return self.screens['audio_recorder']

	def get_midi_recorder(self):
		return self.screens['midi_recorder']


	current_screen_id_changed = Signal()
	current_modal_screen_id_changed = Signal()
	is_loading_changed = Signal()
	status_info_changed = Signal()

	current_screen_id = Property(str, get_current_screen_id, show_screen, notify = current_screen_id_changed)
	current_modal_screen_id = Property(str, get_current_modal_screen_id, notify = current_modal_screen_id_changed)

	is_loading = Property(bool, get_is_loading, notify = is_loading_changed)

	status_information = Property(QObject, get_status_information, constant = True)

	keybinding = Property(QObject, get_keybinding, constant = True)

	info = Property(QObject, get_info, constant = True)
	confirm = Property(QObject, get_confirm, constant = True)
	main = Property(QObject, get_main, constant = True)
	engine = Property(QObject, get_engine, constant = True)
	layer = Property(QObject, get_layer, constant = True)
	layer_options = Property(QObject, get_layer_options, constant = True)
	admin = Property(QObject, get_admin, constant = True)
	snapshot = Property(QObject, get_snapshot, constant = True)
	midi_chan = Property(QObject, get_midi_chan, constant = True)
	bank = Property(QObject, get_bank, constant = True)
	preset = Property(QObject, get_preset, constant = True)
	control = Property(QObject, get_control, constant = True)
	audio_recorder = Property(QObject, get_audio_recorder, constant = True)
	midi_recorder = Property(QObject, get_midi_recorder, constant = True)



#------------------------------------------------------------------------------
# Reparent Top Window using GTK XEmbed protocol features
#------------------------------------------------------------------------------


#def flushflush():
	#for i in range(1000):
		#print("FLUSHFLUSHFLUSHFLUSHFLUSHFLUSHFLUSH")
	#zynthian_gui_config.top.after(200, flushflush)


#if zynthian_gui_config.wiring_layout=="EMULATOR":
	#top_xid=zynthian_gui_config.top.winfo_id()
	#print("Zynthian GUI XID: "+str(top_xid))
	#if len(sys.argv)>1:
		#parent_xid=int(sys.argv[1])
		#print("Parent XID: "+str(parent_xid))
		#zynthian_gui_config.top.geometry('-10000-10000')
		#zynthian_gui_config.top.overrideredirect(True)
		#zynthian_gui_config.top.wm_withdraw()
		#flushflush()
		#zynthian_gui_config.top.after(1000, zynthian_gui_config.top.wm_deiconify)


#------------------------------------------------------------------------------
# Catch SIGTERM
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


#Function to handle computer keyboard key press
#	event: Key event
#def cb_keybinding(event):
	#logging.debug("Key press {} {}".format(event.keycode, event.keysym))
	#zynthian_gui_config.top.focus_set() # Must remove focus from listbox to avoid interference with physical keyboard

	#if not zynthian_gui_keybinding.getInstance().isEnabled():
		#logging.debug("Key binding is disabled - ignoring key press")
		#return

	## Ignore TAB key (for now) to avoid confusing widget focus change
	#if event.keysym == "Tab":
		#return

	## Space is not recognised as keysym so need to convert keycode
	#if event.keycode == 65:
		#keysym = "Space"
	#else:
		#keysym = event.keysym

	#action = zynthian_gui_keybinding.getInstance().get_key_action(keysym, event.state)
	#if action != None:
		#zyngui.callable_ui_action(action)


#zynthian_gui_config.top.bind("<Key>", cb_keybinding)

#zynthian_gui_config.top.protocol("WM_DELETE_WINDOW", delete_window)

#------------------------------------------------------------------------------
# TKinter Main Loop
#------------------------------------------------------------------------------

#import cProfile
#cProfile.run('zynthian_gui_config.top.mainloop()')

#zynthian_gui_config.top.mainloop()

#logging.info("Exit with code {} ...\n\n".format(zyngui.exit_code))
#exit(zyngui.exit_code)






#------------------------------------------------------------------------------
# GUI & Synth Engine initialization
#------------------------------------------------------------------------------

if __name__ == "__main__":
	app = QGuiApplication(sys.argv)
	engine = QQmlApplicationEngine()

	logging.info("STARTING ZYNTHIAN-UI ...")
	zynthian_gui_config.zyngui=zyngui=zynthian_gui()
	zyngui.start()

	QIcon.setThemeName("breeze")

	palette = app.palette()
	bgColor = QColor(zynthian_gui_config.color_bg)
	txColor = QColor(zynthian_gui_config.color_tx)
	palette.setColor(QPalette.Window, bgColor)
	palette.setColor(QPalette.WindowText, txColor)
	ratio = 0.2
	btnColor = QColor(
		bgColor.red() * (1 - ratio) + txColor.red() * ratio,
		bgColor.green() * (1 - ratio) + txColor.green() * ratio,
		bgColor.blue() * (1 - ratio) + txColor.blue() * ratio,
		255)
	palette.setColor(QPalette.Button, btnColor)
	palette.setColor(QPalette.ButtonText, QColor(zynthian_gui_config.color_tx))
	palette.setColor(QPalette.Highlight, QColor(zynthian_gui_config.color_on))
	palette.setColor(QPalette.Base, QColor(zynthian_gui_config.color_panel_bd))
	palette.setColor(QPalette.Text, QColor(zynthian_gui_config.color_tx))
	palette.setColor(QPalette.HighlightedText, zynthian_gui_config.color_tx)
	app.setPalette(palette)

	zyngui.show_screen('layer')
	zyngui.screens['preset'].disable_show_fav_presets()

	engine.rootContext().setContextProperty("zynthian", zyngui)

	engine.load(os.fspath(Path(__file__).resolve().parent / "qml-ui/main.qml"))

	if not engine.rootObjects() or not app.topLevelWindows():
		sys.exit(-1)

	# assuming there is one and only one window for now
	zynthian_gui_config.top = app.topLevelWindows()[0]
	zynthian_gui_config.app = app

	sys.exit(app.exec_())



#------------------------------------------------------------------------------
