# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_sooperlooper)
#
# zynthian_engine implementation for sooper looper
#
# Copyright (C) 2022-2022 Brian Walton <riban@zynthian.org>
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

from collections import OrderedDict
import logging
from . import zynthian_engine
import liblo
from time import sleep

from . import zynthian_controller

#------------------------------------------------------------------------------
# Sooper Looper Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_sooperlooper(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Config variables
	# ---------------------------------------------------------------------------
	SL_PORT = 9951
	SL_LOOP_PARAMS = [
		'rec_thresh',			# range 0 -> 1
		'feedback',				# range 0 -> 1
	#	'dry',					# range 0 -> 1
		'wet',					# range 0 -> 1
	#	'input_gain',			# range 0 -> 1
		'rate',        			# range 0.25 -> 4.0
	#	'scratch_pos',			# range 0 -> 1
	#	'delay_trigger',		# any changes
		'quantize',				# 0 = off, 1 = cycle, 2 = 8th, 3 = loop
		'round',				# 0 = off,  not 0 = on
	#	'redo_is_tap'			# 0 = off,  not 0 = on
  		'sync',					# 0 = off,  not 0 = on
  		'playback_sync',		# 0 = off,  not 0 = on
  	#	'use_rate',				# 0 = off,  not 0 = on
  	#	'fade_samples',			# 0 -> ...
  		'use_feedback_play',	# 0 = off,  not 0 = on
  	#	'use_common_ins',		# 0 = off,  not 0 = on
  	#	'use_common_outs',		# 0 = off,  not 0 = on
  		'relative_sync',		# 0 = off, not 0 = on
  	#	'use_safety_feedback',	# 0 = off, not 0 = on
  	#	'pan_1',				# range 0 -> 1
  	#	'pan_2',				# range 0 -> 1
  	#	'pan_3',				# range 0 -> 1
  	#	'pan_4',				# range 0 -> 1
  	#	'input_latency',		# range 0 -> ...
  	#	'output_latency',		# range 0 -> ...
  	#	'trigger_latency',		# range 0 -> ...
  	#	'autoset_latency',		# 0 = off, not 0 = on
  		'mute_quantized',		# 0 = off, not 0 = on
  		'overdub_quantized',	# 0 == off, not 0 = on
  		'replace_quantized',	# 0 == off, not 0 = on (undocumented)
  	#	'discrete_prefader',	# 0 == off, not 0 = on
	#	'next_state,'			# same as state
		'loop_len',				# in seconds
  		'loop_pos',				# in seconds
  		'cycle_len',			# in seconds
  		'free_time',			# in seconds
  		'total_time',			# in seconds
  	#	'rate_output',			# Used to detect direction but must use register_auto_update
	#	'in_peak_meter',		# absolute float sample value 0.0 -> 1.0 (or higher)
  	#	'out_peak_meter',		# absolute float sample value 0.0 -> 1.0 (or higher)
  	#	'is_soloed',			# 1 if soloed, 0 if not
		'stretch_ratio',		# 0.5 -> 4.0 (undocumented)
	#	'tempo_stretch',		# 0 = off, not 0 = on (undocumented)
		'pitch_shift'			# -12 -> 12 (undocumented)
	]

	SL_GLOBAL_PARAMS = [
	#	'tempo',				# bpm
		'eighth_per_cycle',
		'dry',					# range 0 -> 1 affects common input passthru
		'wet',					# range 0 -> 1  affects common output level
		'input_gain',			# range 0 -> 1  affects common input gain
		'sync_source',			# -3 = internal,  -2 = midi, -1 = jack, 0 = none, # > 0 = loop number (1 indexed) 
	#	'tap_tempo',			# any changes
		'save_loop',			# any change triggers quick save, be careful
		'auto_disable_latency',	# when 1, disables compensation when monitoring main inputs
		'select_next_loop',		# any changes
		'select_prev_loop',		# any changes
		'select_all_loops',		# any changes
		'selected_loop_num',	# -1 = all, 0->N selects loop instances (first loop is 0, etc) 
		'smart_eighths',		# 0 = off, not 0 = on (undocumented)
	]

	SL_STATES ={
		-1: {'name': 'unknown', 'symbol': None, 'icon':''},
		0: {'name': 'Off','symbol': None, 'icon':''},
		1: {'name': 'WaitStart', 'symbol': None, 'icon':'\u23EF'},
		2: {'name': 'Recording', 'symbol': 'record', 'icon':'\u26ab'},
		3: {'name': 'WaitStop', 'symbol': None, 'icon':'\u23EF'},
		4: {'name': 'Playing', 'symbol': None, 'icon':'\uf04b'},
		5: {'name': 'Overdubbing', 'symbol': 'overdub', 'icon':'\u26ab'},
		6: {'name': 'Multiplying', 'symbol': 'multiply', 'icon':'\u26abx'},
		7: {'name': 'Inserting', 'symbol': 'insert', 'icon':'\u26ab'},
		8: {'name': 'Replacing', 'symbol': 'replace', 'icon':'\u26ab'},
		9: {'name': 'Delay', 'symbol': None, 'icon':'delay'},
		10: {'name': 'Muted', 'symbol': 'mute', 'icon':'mute'},
		11: {'name': 'Scratching', 'symbol': None, 'icon':'scratch'},
		12: {'name': 'OneShot', 'symbol': 'oneshot', 'icon':'\uf04b'},
		13: {'name': 'Substitute', 'symbol': 'substitute', 'icon':'\u26ab'},
		14: {'name': 'Paused', 'symbol': 'pause', 'icon':'\u23F8'},
	}

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__(zyngui)
		self.name = "SooperLooper"
		self.nickname = "SL"
		self.jackname = "sooperlooper"
		self.type = "Audio Effect"

		self.options['note_range'] = False
		self.options['midi_chan'] = False
		self.options['drop_pc'] = True

		self.command = 'sooperlooper -q -D no -p {}'.format(self.SL_PORT)
		self.command_prompt = ''

		self.state = 0 # Current SL state - need to keep this synchonised with SL
		self.selected_loop = 0

		#self.custom_gui_fpath = "/zynthian/zynthian-ui/zyngui/zynthian_widget_sooperlooper.py"
		self.start()

		# MIDI Controllers
		self._ctrls=[
			#symbol, name, options
			['record', 'record', {'value':0, 'value_max':1, 'labels':['off', 'on'], 'is_toggle':True, 'is_toggle':True}],
			['overdub', 'overdub', {'value':0, 'value_max':1, 'labels':['off', 'on'], 'is_toggle':True}],
			['multiply', 'multiply', {'value':0, 'value_max':1, 'labels':['off', 'on'], 'is_toggle':True}],
			['replace', 'replace', {'value':0, 'value_max':1, 'labels':['off', 'on'], 'is_toggle':True}],
			['substitute', 'substitute', {'value':0, 'value_max':1, 'labels':['off', 'on'], 'is_toggle':True}],
			['insert', 'insert', {'value':0, 'value_max':1, 'labels':['off', 'on'], 'is_toggle':True}],
			['undo/redo', 'undo/redo', {'value':1, 'labels':['<', '<>', '>']}],
			['trigger', 'trigger;', {'value':0, 'value_max':1, 'labels':['off', 'on'], 'is_toggle':True}],
			['mute', 'mute', {'value':0, 'value_max':1, 'labels':['off', 'on'], 'is_toggle':True}],
			['oneshot', 'once', {'value':0, 'value_max':1, 'labels':['off', 'on'], 'is_toggle':True}],
			['pause', 'pause', {'value':0, 'value_max':1, 'labels':['off', 'on'], 'is_toggle':True}],
			['reverse', 'direction', {'value':1, 'labels':['reverse', 'forward'], 'ticks':[1, 0], 'is_toggle':True}],
			['rate', 'speed', {'value':1.0, 'value_min':0.25, 'value_max':4.0, 'is_integer':False, 'nudge_factor':0.01}],
			['stretch_ratio', 'stretch', {'value':1.0, 'value_min':0.5, 'value_max':4.0, 'is_integer':False, 'nudge_factor':0.01}],
			['pitch_shift', 'pitch', {'value':0.0, 'value_min':-12, 'value_max':12, 'is_integer':False, 'nudge_factor':0.1}],
			['sync_source', 'sync source', {'value':1, 'value_min':-3, 'value_max':1, 'labels':['Internal','MidiClock','Jack/Host','None','Loop1'], 'is_integer':True}], #TODO: Dynamically offer more loops
			['sync', 'sync operations', {'value':0, 'value_max':1, 'labels':['off', 'on']}],
            ['eighth_per_cycle', '8th/cycle', {'value':16, 'value_min':1, 'value_max':600}], #TODO: What makes sense for max val?
            ['quantize', 'quantize', {'value':0, 'value_max':3, 'labels':['off', 'cycle', '8th', 'loop']}],
            ['mute_quantized', 'mute quant', {'value':0, 'value_max':1, 'labels':['off', 'on'],}],
            ['overdub_quantized', 'overdub quant', {'value':0, 'value_max':1, 'labels':['off', 'on']}],
            ['replace_quantized', 'replace quant', {'value':0, 'value_max':1, 'labels':['off', 'on']}],
            ['round', 'round', {'value':0, 'value_max':1, 'labels':['off', 'on']}],
            ['relative_sync', 'relative sync', {'value':0, 'value_max':1, 'labels':['off', 'on']}],
            ['smart_eighths', 'auto 8th', {'value':1, 'value_max':1, 'labels':['off', 'on']}],
            ['playback_sync', 'playback sync', {'value':0, 'value_max':1, 'labels':['off', 'on']}],
            ['use_feedback_play', 'play feedback', {'value':0, 'value_max':1, 'labels':['off', 'on']}],
            ['rec_thresh', 'threshold', {'value':0.0, 'value_max':1.0, 'is_integer':False, 'is_logarithmic': True}],
			['feedback', 'feedback', {'value':1.0, 'value_max':1.0, 'is_integer':False, 'is_logarithmic': True}],
			['dry', 'dry', {'value':0.0, 'value_max':1.0, 'is_integer':False, 'is_logarithmic': True}],
			['wet', 'wet', {'value':1.0, 'value_max':1.0, 'is_integer':False, 'is_logarithmic': True}],
			['input_gain', 'input gain', {'value':1.0, 'value_max':1.0, 'is_integer':False, 'is_logarithmic': True}]
		]

		# Controller Screens
		self._ctrl_screens = [
			['Rec 1',['record','overdub','multiply','undo/redo']],
			['Rec 2',['replace','substitute','insert','undo/redo']],
			['Play 1',['trigger','oneshot','mute','pause']],
			['Play 2',['reverse','pitch_shift','rate','stretch_ratio']],
			['Sync 1',['sync_source','sync','eighth_per_cycle','playback_sync']],
			['Sync 2',['round','relative_sync','smart_eighths', 'use_feedback_play']],
			['Quantize',['quantize','mute_quantized','overdub_quantized','replace_quantized']],
			['Levels 1',['rec_thresh', 'feedback', 'dry', 'wet']],
			['Levels 2',['input_gain', None, None, None]]
		]

        #TODO: Monitors
		self.monitors_dict = OrderedDict()


	# ---------------------------------------------------------------------------
	# Subproccess Management & IPC
	# ---------------------------------------------------------------------------

	def start(self):
		#logging.warning("Starting SooperLooper")
		self.osc_init(self.SL_PORT)
		self.proc_start_sleep = 1 #TODO: Cludgy wait - maybe should perform periodic check for server until reachable
		super().start()
		liblo.send(self.osc_target, '/sl/0/register_auto_update', ('s', 'state'), ('i', 100), ('s', self.osc_server_url), ('s', '/sl/state'))
		liblo.send(self.osc_target, '/sl/0/register_auto_update', ('s', 'rate_output'), ('i', 100), ('s', self.osc_server_url), ('s', '/sl/control'))
		for symbol in self.SL_LOOP_PARAMS:
			liblo.send(self.osc_target, '/sl/0/register_update', ('s', symbol), ('s', self.osc_server_url), ('s', '/sl/control'))
		for symbol in self.SL_GLOBAL_PARAMS:
			liblo.send(self.osc_target, '/register_update', ('s', symbol), ('s', self.osc_server_url), ('s', '/sl/control'))
		self.select_loop(0, True)

	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------


	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------


	# ---------------------------------------------------------------------------
	# Bank Management
	# ---------------------------------------------------------------------------

	def get_bank_list(self, layer=None):
		return []

	# ---------------------------------------------------------------------------
	# Preset Management
	# ---------------------------------------------------------------------------

	def get_preset_list(self, bank):
		return []

	#----------------------------------------------------------------------------
	# Controllers Management
	#----------------------------------------------------------------------------

	def get_controllers_dict(self, layer):
		for ctrl in self._ctrls:
			zctrl = zynthian_controller(self, ctrl[0], ctrl[1], ctrl[2])
			#engine, symbol, name=None, options=None
			self.zctrls[zctrl.symbol] = zctrl
		return self.zctrls


	def send_controller_value(self, zctrl):
		#logging.warning("{} {}".format(zctrl.symbol, zctrl.value))
		if zctrl.symbol in ['oneshot', 'once', 'trigger'] and zctrl.value == 0:
			# Ignore off signals
			return
		elif zctrl.is_toggle:
			liblo.send(self.osc_target, '/sl/-3/hit', ('s', zctrl.symbol))
			if zctrl.symbol == 'trigger':
				zctrl.set_value(0, False) # Make trigger a pulse
		elif zctrl.symbol == 'undo/redo':
			if zctrl.value == 0:
				liblo.send(self.osc_target, '/sl/-3/hit', ('s', 'undo'))
			elif zctrl.value == 2:
				liblo.send(self.osc_target, '/sl/-3/hit', ('s', 'redo'))
			zctrl.set_value(1, False)
		elif zctrl.symbol in self.SL_LOOP_PARAMS:
			liblo.send(self.osc_target, '/sl/-3/set', ('s', zctrl.symbol), ('f', zctrl.value))
		elif zctrl.symbol in self.SL_GLOBAL_PARAMS:
			liblo.send(self.osc_target, '/set', ('s', zctrl.symbol), ('f', zctrl.value))


	def get_monitors_dict(self):
		return self.monitors_dict


	# ---------------------------------------------------------------------------
	# Specific functions
	# ---------------------------------------------------------------------------

	# Update each mutually exclusive 'state' controller to match current state
	def update_state(self):
		#logging.warning("State: {}".format(self.state))
		for state in self.SL_STATES:
			if self.SL_STATES[state]['symbol']:
				if state == self.state:
					self.zctrls[self.SL_STATES[state]['symbol']].set_value(1, False)
				else:
					self.zctrls[self.SL_STATES[state]['symbol']].set_value(0, False)
		self.layers[0].status = self.SL_STATES[self.state]['icon']


	def cb_osc_all(self, path, args, types, src):
		#logging.warning("Rx OSC: {} {}".format(path,args))
		if path == '/sl/state':
			# args: i:Loop index, s:control, f:value
			self.state = int(args[2])
			try:
				self.update_state()
			except:
				pass # May be called before zctrls are configured

		elif path == '/sl/control':
			if args[1] == 'rate_output':
				if args[2] < 0.0:
					self.zctrls['reverse'].set_value(1, False)
				else:
					self.zctrls['reverse'].set_value(0, False)
			elif args[1] in self.SL_LOOP_PARAMS or args[1] in self.SL_GLOBAL_PARAMS:
				if args[1] == 'selected_loop_num':
					self.select_loop(args[2])
				try:
					self.zctrls[args[1]].set_value(args[2], False)
				except Exception as e:
					logging.warning("Unsupported tally %s (%f)", args[1], args[2])


	def select_loop(self, loop, send=False):
		#TODO: Validate loop < quant_loops
		self.select_loop = loop
		if send:
			liblo.send(self.osc_target, '/set', ('s', 'selected_loop_num'), ('f', self.selected_loop))

	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

#******************************************************************************
