# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_sooperlooper)
#
# zynthian_engine implementation for sooper looper
#
# Copyright (C) 2022-2025 Brian Walton <riban@zynthian.org>
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

from collections import OrderedDict
import logging

from . import zynthian_engine
import os
from glob import glob
from subprocess import Popen, DEVNULL
from time import sleep, monotonic
from threading import Timer

from . import zynthian_controller
from zynconf import ServerPort
from zyngine.zynthian_signal_manager import zynsigman

# ------------------------------------------------------------------------------
# Sooper Looper State Codes
# ------------------------------------------------------------------------------

SL_STATE_UNKNOWN = -1
SL_STATE_OFF = 0
SL_STATE_REC_STARTING = 1
SL_STATE_RECORDING = 2
SL_STATE_REC_STOPPING = 3
SL_STATE_PLAYING = 4
SL_STATE_OVERDUBBING = 5
SL_STATE_MULTIPLYING = 6
SL_STATE_INSERTING = 7
SL_STATE_REPLACING = 8
SL_STATE_DELAYING = 9
SL_STATE_MUTED = 10
SL_STATE_SCRATCHING = 11
SL_STATE_PLAYING_ONCE = 12
SL_STATE_SUBSTITUTING = 13
SL_STATE_PAUSED = 14
SL_STATE_UNDO_ALL = 15
SL_STATE_TRIGGER_PLAY = 16
SL_STATE_UNDO = 17
SL_STATE_REDO = 18
SL_STATE_REDO_ALL = 19
SL_STATE_OFF_MUTED = 20

# ------------------------------------------------------------------------------
# Sooper Looper Engine Class
# ------------------------------------------------------------------------------

class zynthian_engine_sooperlooper(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Config variables
	# ---------------------------------------------------------------------------
	SL_PORT = ServerPort["sooperlooper_osc"]
	MAX_LOOPS = 6

	# SL_LOOP_SEL_PARAM act on the selected loop - send with osc command /sl/#/set where #=-3 for selected or index of loop (0..5)
	SL_LOOP_SEL_PARAM = [
		'record',
		'overdub',
		'multiply',
		'replace',
		'substitute',
		'insert',
		'trigger',
		'mute',
		'oneshot',
		'pause',
		'reverse',
		'single_pedal'
	]

	# SL_LOOP_PARAMS act on individual loops - sent with osc command /sl/#/set
	SL_LOOP_PARAMS = [
		'feedback',					# range 0 -> 1
		#'dry',						# range 0 -> 1
		'wet',						# range 0 -> 1
		#'input_gain',				# range 0 -> 1
		'rate',                                 # range 0.25 -> 4.0
		#'scratch_pos',				# range 0 -> 1
		#'delay_trigger',			# any changes
		#'quantize',				# 0 = off, 1 = cycle, 2 = 8th, 3 = loop
		#'round',					# 0 = off,  not 0 = on
		#'redo_is_tap'				# 0 = off,  not 0 = on
		'sync',						# 0 = off,  not 0 = on
		'playback_sync',			# 0 = off,  not 0 = on
		#'use_rate',				# 0 = off,  not 0 = on
		#'fade_samples',			# 0 -> ...
		'use_feedback_play',		# 0 = off,  not 0 = on
		#'use_common_ins',			# 0 = off,  not 0 = on
		#'use_common_outs',			# 0 = off,  not 0 = on
		#'relative_sync',			# 0 = off, not 0 = on
		#'use_safety_feedback',		# 0 = off, not 0 = on
		#'pan_1',					# range 0 -> 1
		#'pan_2',					# range 0 -> 1
		#'pan_3',					# range 0 -> 1
		#'pan_4',					# range 0 -> 1
		#'input_latency',			# range 0 -> ...
		#'output_latency',			# range 0 -> ...
		#'trigger_latency',			# range 0 -> ...
		#'autoset_latency',			# 0 = off, not 0 = on
		#'mute_quantized',			# 0 = off, not 0 = on
		#'overdub_quantized',		# 0 == off, not 0 = on
		#'replace_quantized',		# 0 == off, not 0 = on (undocumented)
		#'discrete_prefader',		# 0 == off, not 0 = on
		#'next_state,'				# same as state
		'stretch_ratio',			# 0.5 -> 4.0 (undocumented)
		#'tempo_stretch',			# 0 = off, not 0 = on (undocumented)
		'pitch_shift'				# -12 -> 12 (undocumented)
	]

	# SL_LOOP_GLOBAL_PARAMS act on all loops - sent with osc command /sl/-1/set
	SL_LOOP_GLOBAL_PARAMS = [
		'rec_thresh',				# range 0 -> 1
		'round',					# 0 = off,  not 0 = on
		'relative_sync',			# 0 = off, not 0 = on
		'quantize',					# 0 = off, 1 = cycle, 2 = 8th, 3 = loop
		'mute_quantized',			# 0 = off, not 0 = on
		'overdub_quantized',		# 0 == off, not 0 = on
		'replace_quantized',		# 0 == off, not 0 = on (undocumented)
	]

	# SL_GLOBAL_PARAMS act on whole engine - sent with osc command /set
	SL_GLOBAL_PARAMS = [
		#'tempo',					# bpm
		#'eighth_per_cycle',
		'dry',						# range 0 -> 1 affects common input passthru
		#'wet',						# range 0 -> 1  affects common output level
		'input_gain',				# range 0 -> 1  affects common input gain
		'sync_source',				# -3 = internal,  -2 = midi, -1 = jack, 0 = none, # > 0 = loop number (1 indexed)
		#'tap_tempo',				# any changes
		#'save_loop',				# any change triggers quick save, be careful
		#'auto_disable_latency',	# when 1, disables compensation when monitoring main inputs
		#'select_next_loop',		# any changes
		#'select_prev_loop',		# any changes
		#'select_all_loops',		# any changes
		'selected_loop_num',		# -1 = all, 0->N selects loop instances (first loop is 0, etc)
		#'smart_eighths',			# 0 = off, not 0 = on (undocumented)
	]

	SL_MONITORS = [
		'rate_output',				# Used to detect direction but must use register_auto_update
		'in_peak_meter',			# absolute float sample value 0.0 -> 1.0 (or higher)
		#'out_peak_meter',			# absolute float sample value 0.0 -> 1.0 (or higher)
		#'loop_len',				# in seconds
		#'loop_pos',				# in seconds
		#'cycle_len',				# in seconds
		#'free_time',				# in seconds
		#'total_time',				# in seconds
		#'is_soloed',				# 1 if soloed, 0 if not
	]

	SL_STATES = {
		# Dictionary of SL states with indication of which controllers are on/off in this SL state
		SL_STATE_UNKNOWN: {
			'name': 'unknown',
			'ctrl_off': [],
			'ctrl_on': [],
			'next_state': False,
			'icon': ''
		},
		SL_STATE_OFF: {
			'name': 'off',
			'ctrl_off': ['mute'],
			'ctrl_on': [],
			'next_state': False,
			'icon': ''
		},
		SL_STATE_REC_STARTING: {
			'name': 'rec starting...',
			'ctrl_off': ['overdub', 'multiply', 'insert', 'replace', 'substitute', 'pause', 'mute', 'trigger', 'oneshot'],
			'ctrl_on': ['record'],
			'next_state': False,
			'icon': '\u23EF'
		},
		SL_STATE_RECORDING: {
			'name': 'recording',
			'ctrl_off': ['overdub', 'multiply', 'insert', 'replace', 'substitute', 'pause', 'mute', 'trigger', 'oneshot'],
			'ctrl_on': ['record'],
			'next_state': False,
			'icon': '\u26AB'
		},
		SL_STATE_REC_STOPPING: {
			'name': 'rec stopping...',
			'ctrl_off': ['overdub', 'multiply', 'insert', 'replace', 'substitute', 'pause', 'mute', 'trigger', 'oneshot'],
			'ctrl_on': ['record'],
			'next_state': False,
			'icon': '\u23EF'
		},
		SL_STATE_PLAYING: {
			'name': 'playing',
			'ctrl_off': ['record','overdub', 'multiply', 'insert', 'replace', 'substitute', 'pause', 'mute', 'trigger', 'oneshot'],
			'ctrl_on': [],
			'next_state': False,
			'icon': '\uF04B'
		},
		SL_STATE_OVERDUBBING: {
			'name': 'overdubbing',
			'ctrl_off': ['record', 'multiply', 'insert', 'replace', 'substitute', 'pause', 'mute', 'trigger', 'oneshot'],
			'ctrl_on': ['overdub'],
			'next_state': False,
			'icon': '\u26AB'
		},
		SL_STATE_MULTIPLYING: {
			'name': 'multiplying',
			'ctrl_off': ['record', 'overdub', 'insert', 'replace', 'substitute', 'pause', 'mute', 'trigger', 'oneshot'],
			'ctrl_on': ['multiply'],
			'next_state': True,
			'icon': '\u26AB'
		},
		SL_STATE_INSERTING: {
			'name': 'inserting',
			'ctrl_off': ['record', 'overdub', 'multiply', 'replace', 'substitute', 'pause', 'mute', 'trigger', 'oneshot'],
			'ctrl_on': ['insert'],
			'next_state': True,
			'icon': '\u26AB'
		},
		SL_STATE_REPLACING: {
			'name': 'replacing',
			'ctrl_off': ['record', 'overdub', 'insert', 'multiply', 'substitute', 'pause', 'mute', 'trigger', 'oneshot'],
			'ctrl_on': ['replace'],
			'next_state': True,
			'icon': '\u26AB'
		},
		SL_STATE_DELAYING: {
			'name': 'delaying',
			'ctrl_off': [],
			'ctrl_on': [],
			'next_state': False,
			'icon': 'delay'
		},
		SL_STATE_MUTED: {
			'name': 'muted',
			'ctrl_off': ['record', 'overdub', 'insert', 'multiply', 'replace', 'substitute', 'pause', 'trigger', 'oneshot'],
			'ctrl_on': ['mute'],
			'next_state': False,
			'icon': 'mute'
		},
		SL_STATE_SCRATCHING: {
			'name': 'scratching',
			'ctrl_off': ['record', 'overdub', 'multiply', 'insert', 'replace', 'substitute', 'pause', 'mute', 'trigger', 'oneshot'],
			'ctrl_on': [],
			'next_state': False,
			'icon': 'scratch'
		},
		SL_STATE_PLAYING_ONCE: {
			'name': 'playing once',
			'ctrl_off': ['record', 'overdub', 'multiply', 'insert', 'replace', 'substitute', 'pause', 'mute', 'trigger'],
			'ctrl_on': ['oneshot'],
			'next_state': True,
			'icon': '\uF04B'
		},
		SL_STATE_SUBSTITUTING: {
			'name': 'substituting',
			'ctrl_off': ['record', 'overdub', 'multiply', 'insert', 'replace', 'pause', 'mute', 'trigger','oneshot'],
			'ctrl_on': ['substitute'],
			'next_state': True,
			'icon': '\u26AB'
		},
		SL_STATE_PAUSED: {
			'name': 'paused',
			'ctrl_off': ['record', 'overdub', 'insert', 'multiply', 'replace', 'substitute', 'mute', 'trigger', 'oneshot'],
			'ctrl_on': ['pause'],
			'next_state': False,
			'icon': '\u23F8'},
		SL_STATE_UNDO_ALL: {
			'name': 'undo all',
			'ctrl_off': [],
			'ctrl_on': [],
			'next_state': False,
			'icon': ''
		},
		SL_STATE_TRIGGER_PLAY: {
			'name': 'trigger play...',
			'ctrl_off': ['record', 'overdub', 'multiply', 'insert', 'replace', 'substitute', 'pause', 'mute', 'oneshot'],
			'ctrl_on': ['trigger'],
			'next_state': False,
			'icon': ''
		},
		SL_STATE_UNDO: {
			'name': 'undo',
			'ctrl_off': [],
			'ctrl_on': [],
			'next_state': False,
			'icon': ''
		},
		SL_STATE_REDO: {
			'name': 'redo',
			'ctrl_off': [],
			'ctrl_on': [],
			'next_state': False,
			'icon': ''
		},
		SL_STATE_REDO_ALL: {
			'name': 'redo all',
			'ctrl_off': [],
			'ctrl_on': [],
			'next_state': False,
			'icon': ''
		},
		SL_STATE_OFF_MUTED: {
			'name': 'off muted',
			'ctrl_off': ['record', 'overdub', 'insert', 'multiply', 'replace', 'substitute', 'pause', 'trigger', 'oneshot'],
			'ctrl_on': ['mute'],
			'next_state': False,
			'icon': 'mute'
		}
	}

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------

	def __init__(self, state_manager=None):
		super().__init__(state_manager)
		self.name = "SooperLooper"
		self.nickname = "SL"
		self.jackname = "sooperlooper"
		self.type = "Audio Effect"

		self.osc_target_port = self.SL_PORT

		# Load custom MIDI bindings
		custom_slb_fpath = self.config_dir + "/sooperlooper/zynthian.slb"
		if os.path.exists(custom_slb_fpath):
			logging.info(f"loading sooperlooper custom MIDI bindings: {custom_slb_fpath}")
		else:
			custom_slb_fpath = None

		# Build SL command line
		#if self.config_remote_display():
		#	self.command = ["slgui", "-l 0", f"-P {self.osc_target_port}", f"-J {self.jackname}"]
		#else:
			#self.command = ["sooperlooper", "-q", "-l 0", "-D no", f"-p {self.osc_target_port}", f"-j {self.jackname}"]
		self.command = ["sooperlooper", "-q", "-D no", f"-p {self.osc_target_port}", f"-j {self.jackname}"]

		if custom_slb_fpath:
			self.command += ["-m", custom_slb_fpath]

		self.state = [-1] * self.MAX_LOOPS  # Current SL state for each loop
		self.next_state = [-1] * self.MAX_LOOPS  # Next SL state for each loop (-1 if no state change pending)
		self.waiting = [0] * self.MAX_LOOPS  # 1 if a change of state is pending
		self.selected_loop = None
		self.loop_count = 1
		self.channels = 2
		self.selected_loop_cc_binding = True # True for MIDI CC to control selected loop. False to target all loops

		ui_dir = os.environ.get('ZYNTHIAN_UI_DIR', "/zynthian/zynthian-ui")
		self.custom_gui_fpath = f"{ui_dir}/zyngui/zynthian_widget_sooperlooper.py"
		self.monitors_dict = OrderedDict({
			"state": 0,
			"next_state": -1,
			"loop_count": 0
		})
		self.pedal_time = 0  # Time single pedal was asserted
		self.pedal_taps = 0  # Quantity of taps on single pedal
		self.single_pedal_timer = None # Timer used for long pedal press

		# MIDI Controllers
		loop_labels = []
		for i in range(self.MAX_LOOPS):
			loop_labels.append(str(i + 1))
		self._ctrls = [
			#symbol, {options}, midi_cc
			['record', {'name': 'record', 'value': 0, 'value_max': 1, 'labels': ['off', 'on'], 'is_toggle': True}],
			['overdub', {'name': 'overdub', 'value': 0, 'value_max': 1, 'labels': ['off', 'on'], 'is_toggle': True}],
			['multiply', {'name': 'multiply', 'value': 0, 'value_max': 1, 'labels': ['off', 'on'], 'is_toggle': True}],
			['replace', {'name': 'replace', 'value': 0, 'value_max': 1, 'labels': ['off', 'on'], 'is_toggle': True}],
			['substitute', {'name': 'substitute', 'value': 0, 'value_max': 1, 'labels': ['off', 'on'], 'is_toggle': True}],
			['insert', {'name': 'insert', 'value': 0, 'value_max': 1, 'labels': ['off', 'on'], 'is_toggle': True}],
			['undo/redo', {'value': 1, 'labels': ['<', '<>', '>']}],
			['next_loop', {'name': 'next loop', 'value': 0, 'value_max': 127, 'labels': ['>', '']}],
			['trigger', {'name': 'trigger', 'value': 0, 'value_max': 1, 'labels': ['off', 'on'], 'is_toggle': True}],
			['mute', {'name': 'mute', 'value': 0, 'value_max': 1, 'labels': ['off', 'on'], 'is_toggle': True}],
			['oneshot', {'name': 'oneshot', 'value': 0, 'value_max': 1, 'labels': ['off', 'on'], 'is_toggle': True}],
			['pause', {'name': 'pause', 'value': 0, 'value_max': 1, 'labels': ['off', 'on'], 'is_toggle': True}],
			['reverse', {'name': 'direction', 'value': 0, 'labels': ['reverse', 'forward'], 'ticks':[1, 0], 'is_toggle': True}],
			['rate', {'name': 'speed', 'value': 1.0, 'value_min': 0.25, 'value_max': 4.0, 'is_integer': False, 'nudge_factor': 0.01}],
			['stretch_ratio', {'name': 'stretch', 'value': 1.0, 'value_min': 0.5, 'value_max': 4.0, 'is_integer': False, 'nudge_factor': 0.01}],
			['pitch_shift', {'name': 'pitch', 'value': 0.0, 'value_min': -12, 'value_max': 12, 'is_integer': False, 'nudge_factor': 0.05}],
			['sync_source', {'name': 'sync to', 'value': 1, 'value_min': -3, 'value_max': 1, 'labels': ['Internal', 'MidiClock', 'Jack/Host', 'None', 'Loop1'], 'is_integer': True}],
			['sync', {'name': 'enable sync', 'value': 1, 'value_max': 1, 'labels': ['off', 'on']}],
			['eighth_per_cycle', {'name': '8th/cycle', 'value': 16, 'value_min': 1, 'value_max': 600}],  # TODO: What makes sense for max val?
			['quantize', {'value': 1, 'value_max': 3, 'labels': ['off', 'cycle', '8th', 'loop']}],
			['mute_quantized', {'name': 'mute quant', 'value': 0, 'value_max': 1, 'labels': ['off', 'on']}],
			['overdub_quantized', {'name': 'overdub quant', 'value': 0, 'value_max': 1, 'labels': ['off', 'on']}],
			['replace_quantized', {'name': 'replace quant', 'value': 0, 'value_max': 1, 'labels': ['off', 'on']}],
			['round', {'value': 0, 'value_max': 1, 'labels': ['off', 'on']}],
			['relative_sync', {'value': 0, 'value_max': 1, 'labels': ['off', 'on']}],
			['smart_eighths', {'name': 'auto 8th', 'value': 1, 'value_max': 1, 'labels': ['off', 'on']}],
			['playback_sync', {'value': 0, 'value_max': 1, 'labels': ['off', 'on']}],
			['use_feedback_play', {'name': 'play feedback', 'value': 0, 'value_max': 1, 'labels': ['off', 'on']}],
			['rec_thresh', {'name': 'threshold', 'value': 0.0, 'value_max': 1.0, 'is_integer': False, 'is_logarithmic': True}],
			['feedback', {'value': 1.0, 'value_max': 1.0, 'is_integer': False, 'is_logarithmic': True}],
			['dry', {'value': 1.0, 'value_max': 1.0, 'is_integer': False, 'is_logarithmic': True}],
			['wet', {'value': 1.0, 'value_max': 1.0, 'is_integer': False, 'is_logarithmic': True}],
			['input_gain', {'name': 'input gain', 'value': 1.0, 'value_max': 1.0, 'is_integer': False, 'is_logarithmic': True}],
			['loop_count', {'name': 'loop count', 'value': 1, 'value_min': 1, 'value_max': self.MAX_LOOPS}],
			['selected_loop_num', {'name': 'selected loop', 'value': 1, 'value_min': 1, 'value_max': 6}],
			['single_pedal', {'name': 'single pedal', 'value': 0, 'value_max': 1, 'labels': ['>', '<'], 'is_toggle': True}],
			['selected_loop_cc', {'name': 'midi cc to selected loop', 'value': 127, 'labels':['off', 'on']}],
			['load_file', {'name': 'load file', 'is_path': True, 'path_file_types': ["wav"], 'path_dir_names': []}]
		]

		# Controller Screens
		self._ctrl_screens = [
			['Loop record 1', ['record', 'overdub', 'multiply', 'undo/redo']],
			['Loop record 2', ['replace', 'substitute', 'insert', 'undo/redo']],
			['Loop control', ['trigger', 'oneshot', 'mute', 'pause']],
			['Loop time/pitch', ['reverse', 'rate', 'stretch_ratio', 'pitch_shift']],
			['Loop levels', ['wet', 'dry', 'feedback', 'selected_loop_num']],
			['Global loop', ['selected_loop_num', 'loop_count', 'next_loop', 'single_pedal']],
			['Global levels', ['rec_thresh', 'input_gain', 'load_file']],
			['Global quantize', ['quantize', 'mute_quantized', 'overdub_quantized', 'replace_quantized']],
			['Global sync 1', ['sync_source', 'sync', 'playback_sync', 'relative_sync']],
			['Global sync 2', ['round', 'use_feedback_play', 'selected_loop_cc']]
		]

		self.start()

	# ---------------------------------------------------------------------------
	# Subproccess Management & IPC
	# ---------------------------------------------------------------------------

	def start(self):
		logging.debug(f"Starting SooperLooper with command: {self.command}")
		self.osc_init()
		self.proc = Popen(self.command, stdout=DEVNULL, stderr=DEVNULL, env=self.command_env, cwd=self.command_cwd)
		sleep(1)  # TODO: Cludgy wait - maybe should perform periodic check for server until reachable

		# Register for common events from sooperlooper server - request changes to the currently selected loop
		for symbol in self.SL_MONITORS:
			self.osc_server.send(self.osc_target, '/sl/-3/register_auto_update', ('s', symbol), ('i', 100), ('s', self.osc_server_url), ('s', '/monitor'))
		for symbol in self.SL_LOOP_PARAMS:
			self.osc_server.send(self.osc_target, '/sl/-3/register_auto_update', ('s', symbol), ('i', 100), ('s', self.osc_server_url), ('s', '/control'))
		for symbol in self.SL_LOOP_GLOBAL_PARAMS:
			# Register for tallies of commands sent to all channels
			self.osc_server.send(self.osc_target, '/sl/-3/register_auto_update', ('s', symbol), ('i', 100), ('s', self.osc_server_url), ('s', '/control'))

		# Register for global events from sooperlooper
		for symbol in self.SL_GLOBAL_PARAMS:
			self.osc_server.send(self.osc_target, '/register_auto_update', ('s', symbol), ('i', 100), ('s', self.osc_server_url), ('s', '/control'))
		self.osc_server.send(self.osc_target, '/register', ('s', self.osc_server_url), ('s', '/info'))

		# Request current quantity of loops
		self.osc_server.send(self.osc_target, '/ping', ('s', self.osc_server_url), ('s', '/info'))

	def stop(self):
		if self.proc:
			try:
				logging.info("Stoping Engine " + self.name)
				self.proc.terminate()
				try:
					self.proc.wait(0.2)
				except:
					self.proc.kill()
				self.proc = None
			except Exception as err:
				logging.error(f"Can't stop engine {self.name} => {err}")
		self.osc_end()

	# ---------------------------------------------------------------------------
	# Processor Management
	# ---------------------------------------------------------------------------

	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	# ---------------------------------------------------------------------------
	# Bank Management
	# ---------------------------------------------------------------------------

	# No bank support for sooperlooper
	def get_bank_list(self, processor=None):
		return [("", None, "", None)]

	# ---------------------------------------------------------------------------
	# Preset Management
	# ---------------------------------------------------------------------------

	def get_preset_list(self, bank, processor=None):
		presets = self.get_filelist(f"{self.data_dir}/presets/sooperlooper", "slsess")
		presets += self.get_filelist(f"{self.my_data_dir}/presets/sooperlooper", "slsess")
		return presets

	def set_preset(self, processor, preset, preload=False):
		if self.osc_server is None:
			return
		self.osc_server.send(self.osc_target, '/load_session', ('s', preset[0]),  ('s', self.osc_server_url), ('s', '/error'))
		sleep(0.5)  # Wait for session to load to avoid consequent controller change conflicts

		# Request quantity of loops in session
		self.osc_server.send(self.osc_target, '/ping', ('s', self.osc_server_url), ('s', '/info'))

		for symbol in self.SL_MONITORS:
			self.osc_server.send(self.osc_target, '/sl/-3/get', ('s', symbol), ('s', self.osc_server_url), ('s', '/monitor'))
		for symbol in self.SL_LOOP_PARAMS:
			self.osc_server.send(self.osc_target, '/sl/-3/get', ('s', symbol), ('s', self.osc_server_url), ('s', '/control'))
		for symbol in self.SL_LOOP_GLOBAL_PARAMS:
			self.osc_server.send(self.osc_target, '/sl/-3/get', ('s', symbol), ('s', self.osc_server_url), ('s', '/control'))
		for symbol in self.SL_GLOBAL_PARAMS:
			self.osc_server.send(self.osc_target, '/get', ('s', symbol), ('s', self.osc_server_url), ('s', '/control'))

		sleep(0.5)  # Wait for controls to update

		# Start loops (muted) to synchronise
		self.osc_server.send(self.osc_target, '/sl/-1/hit', ('s', 'mute'))

	def preset_exists(self, bank_info, preset_name):
		return os.path.exists(f"{self.my_data_dir}/presets/sooperlooper/{preset_name}.slsess")

	def save_preset(self, bank_name, preset_name):
		if self.osc_server is None:
			return
		path = f"{self.my_data_dir}/presets/sooperlooper"
		if not os.path.exists(path):
			try:
				os.mkdir(path)
			except Exception as e:
				logging.warning(f"Failed to create SooperLooper user preset directory: {e}")
		uri = f"{path}/{preset_name}.slsess"
		# Undocumented feature: set 4th (int) parameter to 1 to save loop audio
		self.osc_server.send(self.osc_target, '/save_session', ('s', uri),  ('s', self.osc_server_url), ('s', '/error'), ('i', 1))
		return uri

	def delete_preset(self, bank, preset):
		try:
			os.remove(preset[0])
			wavs = glob(f"{preset[0]}_loop*.wav")
			for file in wavs:
				os.remove(file)
		except Exception as e:
			logging.debug(e)

	def rename_preset(self, bank_info, preset, new_name):
		try:
			os.rename(preset[0], f"{self.my_data_dir}/presets/sooperlooper/{new_name}.slsess")
			return True
		except Exception as e:
			logging.debug(e)
			return False

	# ----------------------------------------------------------------------------
	# Controllers Management
	# ----------------------------------------------------------------------------

	def get_controllers_dict(self, processor):
		if not processor.controllers_dict:
			for ctrl in self._ctrls:
				ctrl[1]['processor'] = processor
				if ctrl[0] in self.SL_LOOP_SEL_PARAM:
					# Create a zctrl for each loop
					for i in range(self.MAX_LOOPS):
						name = ctrl[1].get('name')
						specs = ctrl[1].copy()
						specs['name'] = f"{name} ({i + 1})"
						zctrl = zynthian_controller(self, f"{ctrl[0]}:{i}", specs)
						processor.controllers_dict[zctrl.symbol] = zctrl
				zctrl = zynthian_controller(self, ctrl[0], ctrl[1])
				processor.controllers_dict[zctrl.symbol] = zctrl
		return processor.controllers_dict

	def adjust_controller_bindings(self):
		if self.selected_loop_cc_binding:
			self._ctrl_screens[0][1] = [f'record', f'overdub', f'multiply', 'undo/redo']
			self._ctrl_screens[1][1] = [f'replace', f'substitute', f'insert', 'undo/redo']
			self._ctrl_screens[2][1] = [f'trigger', f'oneshot', f'mute', f'pause']
			self._ctrl_screens[3][1][0] = f'reverse'
			self._ctrl_screens[5][1][3] = f'single_pedal'
		else:
			self._ctrl_screens[0][1] = [f'record:{self.selected_loop}', f'overdub:{self.selected_loop}', f'multiply:{self.selected_loop}', 'undo/redo']
			self._ctrl_screens[1][1] = [f'replace:{self.selected_loop}', f'substitute:{self.selected_loop}', f'insert:{self.selected_loop}', 'undo/redo']
			self._ctrl_screens[2][1] = [f'trigger:{self.selected_loop}', f'oneshot:{self.selected_loop}', f'mute:{self.selected_loop}', f'pause:{self.selected_loop}']
			self._ctrl_screens[3][1][0] = f'reverse:{self.selected_loop}'
			self._ctrl_screens[5][1][3] = f'single_pedal:{self.selected_loop}'
		return

	def send_controller_value(self, zctrl):
		try:
			processor = self.processors[0]
		except IndexError:
			return
		if zctrl.symbol == "selected_loop_cc":
			self.selected_loop_cc_binding = zctrl.value != 0
			self.adjust_controller_bindings()
			for symbol in self.SL_LOOP_SEL_PARAM:
				self.osc_server.send(self.osc_target, '/sl/-1/get', ('s', symbol), ('s', self.osc_server_url), ('s', '/control'))
			processor.refresh_controllers()
			self.state_manager.send_cuia("refresh_screen", ["control"])
			return
		elif zctrl.symbol == "load_file":
			self.osc_server.send(self.osc_target, f"/sl/{self.selected_loop}/load_loop", ("s", zctrl.value), ('s', self.osc_server_url), ('s', '/error'))
			zctrl.value = os.path.dirname(zctrl.value)
			return

		if ":" in zctrl.symbol:
			if processor.controllers_dict["selected_loop_cc"].value:
				return
			symbol, loop = zctrl.symbol.split(":")
			loop = int(loop)
		else:
			symbol = zctrl.symbol
			loop = self.selected_loop
			if not processor.controllers_dict["selected_loop_cc"].value and zctrl.symbol in self.SL_LOOP_SEL_PARAM:
				return

		if self.osc_server is None or symbol in ['oneshot', 'trigger'] and zctrl.value == 0:
			# Ignore off signals
			return
		elif symbol in ("mute", "pause"):
			self.osc_server.send(self.osc_target, f'/sl/{loop}/hit', ('s', symbol))
		elif symbol == 'single_pedal':
			""" Single pedal logic
				Idle -> Record
				Record->Play
				Play->Overdub
				Overdub->Play
				Double press: pause
				Triple press or double press and hold: Clear
				Press once and hold to record/overdub until release
			"""
			ts = monotonic()
			pedal_dur = ts - self.pedal_time
			self.pedal_time = ts
			if zctrl.value:
				# Pedal push
				if pedal_dur < 0.5:
					self.pedal_taps += 1
				else:
					self.pedal_taps = 1

				try:
					self.single_pedal_timer.cancel()
					self.single_pedal_timer = None
				except:
					pass

				match self.pedal_taps:
					case 1:
					# Single tap
						if self.state[loop] in (SL_STATE_PLAYING, SL_STATE_OVERDUBBING, SL_STATE_MUTED):
							self.osc_server.send(self.osc_target, f'/sl/{loop}/hit', ('s', 'overdub'))
						if self.state[loop] in (SL_STATE_UNKNOWN, SL_STATE_OFF, SL_STATE_OFF_MUTED):
							self.osc_server.send(self.osc_target, f'/sl/{loop}/hit', ('s', 'record'))
						elif self.state[loop] == SL_STATE_RECORDING:
							self.osc_server.send(self.osc_target, f'/sl/{loop}/hit', ('s', 'record'))
						elif self.state[loop] == SL_STATE_PAUSED:
							self.osc_server.send(self.osc_target, f'/sl/{loop}/hit', ('s', 'trigger'))
					case 2:
					# Double tap
						self.osc_server.send(self.osc_target, f'/sl/{loop}/hit', ('s', 'pause'))
					case 3:
						# Triple tap
						self.osc_server.send(self.osc_target, f'/sl/{loop}/hit', ('s', 'undo_all'))
				self.single_pedal_timer = Timer(1.5, self.single_pedal_cb)
				self.single_pedal_timer.start()
			else:
				# Pedal release: so check loop state, pedal press duration, etc.
				try:
					self.single_pedal_timer.cancel()
					self.single_pedal_timer = None
				except:
					pass
				if pedal_dur > 1.5:
					# Handle press and hold record
					if self.state[loop] == SL_STATE_OVERDUBBING:
						self.osc_server.send(self.osc_target, f'/sl/{loop}/hit', ('s', 'overdub'))
					elif self.state[loop] == SL_STATE_RECORDING:
							self.osc_server.send(self.osc_target, f'/sl/{loop}/hit', ('s', 'record'))

		elif symbol == 'selected_loop_num':
			self.select_loop(zctrl.value - 1, True)
		elif symbol in self.SL_LOOP_PARAMS:  # Selected loop
			self.osc_server.send(self.osc_target, f'/sl/{loop}/set', ('s', symbol), ('f', zctrl.value))
		elif symbol in self.SL_LOOP_GLOBAL_PARAMS:  # All loops
			self.osc_server.send(self.osc_target, '/sl/-1/set', ('s', symbol), ('f', zctrl.value))
		elif symbol in self.SL_GLOBAL_PARAMS:  # Global params
			self.osc_server.send(self.osc_target, '/set', ('s', symbol), ('f', zctrl.value))

		elif symbol == 'next_loop':
			# Use single controller to perform next (CW)
			if zctrl.value:
				self.select_loop(self.selected_loop + 1, True, True)
			zctrl.set_value(0, False)
		elif zctrl.is_toggle:
			# Use is_toggle to indicate the SL function is a toggle, i.e. press to engage, press to release
			if symbol == 'record' and zctrl.value == 0 and self.state[loop] == SL_STATE_REC_STARTING:
				# TODO: Implement better toggle of pending state
				self.osc_server.send(self.osc_target, f'/sl/{loop}/hit', ('s', 'undo'))
				return
			self.osc_server.send(self.osc_target, f'/sl/{loop}/hit', ('s', symbol))
			#if symbol == 'trigger':
			#zctrl.set_value(0, False)  # Make trigger a pulse
		elif symbol == 'undo/redo':
			# Use single controller to perform undo (CCW) and redo (CW)
			if zctrl.value == 0:
				self.osc_server.send(self.osc_target, f'/sl/{loop}/hit', ('s', 'undo'))
			elif zctrl.value == 2:
				self.osc_server.send(self.osc_target, f'/sl/{loop}/hit', ('s', 'redo'))
			zctrl.set_value(1, False)
		elif symbol == 'loop_count':
			for loop in range(self.loop_count, zctrl.value):
				self.osc_server.send(self.osc_target, '/loop_add', ('i', self.channels), ('f', 30), ('i', 0))
			if zctrl.value < self.loop_count:
				# Don't remove loops - let GUI offer option to (confirm and) remove
				zctrl.set_value(self.loop_count, False)
				self.monitors_dict['loop_del'] = True

	def single_pedal_cb(self):
		match self.pedal_taps:
			case 2:
				# Double tap + hold - clear loop
				self.osc_server.send(self.osc_target, f'/sl/-3/hit', ('s', 'undo_all'))
		self.pedal_taps = 0
		self.single_pedal_timer = None

	def get_monitors_dict(self):
		return self.monitors_dict

	# ----------------------------------------------------------------------------
	# OSC Managament
	# ----------------------------------------------------------------------------

	def cb_osc_all(self, path, args, types, src):
		if self.osc_server is None:
			return
		try:
			processor = self.processors[0]
			if path == '/state':
				# args: i:Loop index, s:control, f:value
				logging.debug("Loop State: %d %s=%0.1f", args[0], args[1], args[2])
				if args[0] < 0 or args[0] >= self.MAX_LOOPS:
					return
				state = int(args[2])
				loop = args[0]
				if args[1] == 'next_state':
					self.next_state[loop] = state
				elif args[1] == 'state':
					self.state[loop] = state
					if state in [0, 4]:
						self.next_state[loop] = -1
				elif args[1] == 'waiting':
					self.waiting[loop] = state

				if self.next_state[loop] == self.state[loop]:
					self.next_state[loop] = -1

				self.monitors_dict[f"state_{loop}"] = self.state[loop]
				self.monitors_dict[f"next_state_{loop}"] = self.next_state[loop]
				self.monitors_dict[f"waiting_{loop}"] = self.waiting[loop]
				if self.selected_loop == loop:
					self.monitors_dict['state'] = self.state[loop]
					self.monitors_dict['next_state'] = self.next_state[loop]
					self.monitors_dict['waiting'] = self.waiting[loop]
				self.update_state(loop)

			elif path == '/info':
				# args: s:hosturl  s:version  i:loopcount
				#logging.debug("Info: from %s ver: %s loops: %d", args[0], args[1], args[2])
				self.sl_version = args[1]
				loop_count_changed = int(args[2]) - self.loop_count  # +/- quantity of added/removed loops
				self.loop_count = int(args[2])
				if loop_count_changed:
					labels = ['Internal', 'MidiClock', 'Jack/Host', 'None']
					for loop in range(self.loop_count):
						labels.append(f"Loop {loop + 1}")
					try:
							processor.controllers_dict['sync_source'].set_options({'labels': labels, 'ticks':[], 'value_max': self.loop_count})
							processor.controllers_dict['loop_count'].set_value(self.loop_count, False)
							processor.controllers_dict['selected_loop_num'].value_max = self.loop_count
					except:
						pass  # zctrls may not yet be initialised
					if loop_count_changed > 0:
						for i in range(loop_count_changed):
							self.osc_server.send(self.osc_target, f"/sl/{self.loop_count - 1 - i}/register_auto_update", ('s', 'loop_pos'), ('i', 100), ('s', self.osc_server_url), ('s', '/monitor'))
							self.osc_server.send(self.osc_target, f"/sl/{self.loop_count - 1 - i}/register_auto_update", ('s', 'loop_len'), ('i', 100), ('s', self.osc_server_url), ('s', '/monitor'))
							self.osc_server.send(self.osc_target, f"/sl/{self.loop_count - 1 - i}/register_auto_update", ('s', 'mute'), ('i', 100), ('s', self.osc_server_url), ('s', '/monitor'))
							self.osc_server.send(self.osc_target, f"/sl/{self.loop_count - 1 - i}/register_auto_update", ('s', 'state'), ('i', 100), ('s', self.osc_server_url), ('s', '/state'))
							self.osc_server.send(self.osc_target, f"/sl/{self.loop_count - 1 - i}/register_auto_update", ('s', 'next_state'), ('i', 100), ('s', self.osc_server_url), ('s', '/state'))
							self.osc_server.send(self.osc_target, f"/sl/{self.loop_count - 1 - i}/register_auto_update", ('s', 'waiting'), ('i', 100), ('s', self.osc_server_url), ('s', '/state'))
							if self.loop_count > 1:
								# Set defaults for new loops
								self.osc_server.send(self.osc_target, f"/sl/{self.loop_count - 1 - i}/set", ('s', 'sync'), ('f', 1))
						self.select_loop(self.loop_count - 1, True)

					self.osc_server.send(self.osc_target, '/get', ('s', 'sync_source'), ('s', self.osc_server_url), ('s', '/control'))
					if self.selected_loop is not None and self.selected_loop > self.loop_count:
						self.select_loop(self.loop_count - 1, True)

				self.monitors_dict['loop_count'] = self.loop_count
				self.monitors_dict['version'] = self.sl_version
			elif path == '/control':
				# args: i:Loop index, s:control, f:value
				#logging.debug("Control: Loop %d %s=%0.2f", args[0], args[1], args[2])
				self.monitors_dict[args[1]] = args[2]
				if args[1] == 'selected_loop_num':
					self.select_loop(args[2])
					return
				try:
					processor.controllers_dict[args[1]].set_value(args[2], False)
					processor.controllers_dict[f"{args[1]}:{self.selected_loop}"].set_value(args[2], False)
				except Exception as e:
					pass
					#logging.warning("Unsupported tally (or zctrl not yet configured) %s (%f)", args[1], args[2])
			elif path == '/monitor':
				# args: i:Loop index, s:control, f:value
				# Handle events registered for selected loop
				#logging.debug("Monitor: Loop %d %s=%0.2f", args[0], args[1], args[2])
				if args[0] == -3:
					if args[1] == 'rate_output':
						try:
							if args[2] < 0.0:
								processor.controllers_dict['reverse'].set_value(1, False)
							else:
								processor.controllers_dict['reverse'].set_value(0, False)
						except:
							pass  # zctrls may not yet be initialised
					self.monitors_dict[args[1]] = args[2]
				else:
					self.monitors_dict[f"{args[1]}_{args[0]}"] = args[2]
			elif path == 'error':
				logging.error(f"SooperLooper daemon error: {args[0]}")
		except Exception as e:
			logging.warning(e)

	# ---------------------------------------------------------------------------
	# Specific functions
	# ---------------------------------------------------------------------------

	# Update 'state' controllers of loop
	def update_state(self, loop):
		try:
			processor = self.processors[0]
		except:
			return
		try:
			current_state = self.state[loop]
			#logging.warning(f"loop: {loop} state: {current_state}")
			# Turn off all controllers that are off in this state
			for symbol in self.SL_STATES[current_state]['ctrl_off']:
				if symbol in self.SL_LOOP_SEL_PARAM:
					if self.selected_loop == loop:
						processor.controllers_dict[symbol].set_readonly(False)
						processor.controllers_dict[symbol].set_value(0, False)
					symbol += f":{loop}"
					processor.controllers_dict[symbol].set_readonly(False)
					processor.controllers_dict[symbol].set_value(0, False)
			# Turn on all controllers that are on in this state
			for symbol in self.SL_STATES[current_state]['ctrl_on']:
				if symbol in self.SL_LOOP_SEL_PARAM:
					if self.selected_loop == loop:
						processor.controllers_dict[symbol].set_readonly(False)
						processor.controllers_dict[symbol].set_value(1, False)
					symbol += f":{loop}"
					processor.controllers_dict[symbol].set_readonly(False)
					processor.controllers_dict[symbol].set_value(1, False)
			next_state = self.next_state[loop]
			# Set next_state for controllers that are part of logical sequence
			if self.SL_STATES[next_state]['next_state']:
				for symbol in self.SL_STATES[next_state]['ctrl_on']:
					if symbol in self.SL_LOOP_SEL_PARAM:
						if self.selected_loop == loop:
							processor.controllers_dict[symbol].set_value(1, False)
							processor.controllers_dict[symbol].set_readonly(True)
						symbol += f":{loop}"
						processor.controllers_dict[symbol].set_value(1, False)
						processor.controllers_dict[symbol].set_readonly(True)

		except Exception as e:
			logging.error(e)
		#self.processors[0].status = self.SL_STATES[self.state]['icon']

	def select_loop(self, loop, send=False, wrap=False):
		try:
			processor = self.processors[0]
		except IndexError:
			return
		if wrap and loop >= self.loop_count:
			loop = 0
		if loop < 0 or loop >= self.loop_count:
			return  # TODO: Handle -1 == all loops
		self.selected_loop = int(loop)
		self.monitors_dict['state'] = self.state[self.selected_loop]
		self.monitors_dict['next_state'] = self.next_state[self.selected_loop]
		self.monitors_dict['waiting'] = self.waiting[self.selected_loop]
		self.update_state(self.selected_loop)
		processor.controllers_dict['selected_loop_num'].set_value(loop + 1, False)
		self.adjust_controller_bindings()
		if send and self.osc_server:
			self.osc_server.send(self.osc_target, '/set', ('s', 'selected_loop_num'), ('f', self.selected_loop))
		processor.refresh_controllers()
		self.state_manager.send_cuia("refresh_screen", ["control"])
		zynsigman.send_queued(zynsigman.S_GUI, zynsigman.SS_GUI_CONTROL_MODE, mode='control')

	def prev_loop(self):
		self.select_loop(self.selected_loop - 1, True)

	def next_loop(self):
		self.select_loop(self.selected_loop + 1, True)

	def undo(self):
		self.processors[0].controllers_dict['undo/redo'].nudge(-1)

	def redo(self):
		self.processors[0].controllers_dict['undo/redo'].nudge(1)

	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

# *******************************************************************************
