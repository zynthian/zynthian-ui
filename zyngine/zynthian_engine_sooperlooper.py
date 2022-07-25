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

#------------------------------------------------------------------------------
# Sooper Looper Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_sooperlooper(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Config variables
	# ---------------------------------------------------------------------------
	SL_PORT = 9951
	SL_CONTROLS = [
		'rec_thresh',			# range 0 -> 1
		'feedback',				# range 0 -> 1
		'dry',					# range 0 -> 1
		'wet',					# range 0 -> 1
		'input_gain',			# range 0 -> 1
		'rate',        			# range 0.25 -> 4.0
		'scratch_pos',			# range 0 -> 1
		'delay_trigger',		# any changes
		'quantize',				# 0 = off, 1 = cycle, 2 = 8th, 3 = loop
		'round',				# 0 = off,  not 0 = on
		'redo_is_tap'			# 0 = off,  not 0 = on
  		'sync',					# 0 = off,  not 0 = on
  	#	'playback_sync',		# 0 = off,  not 0 = on
  	#	'use_rate',				# 0 = off,  not 0 = on
  	#	'fade_samples',			# 0 -> ...
  	#	'use_feedback_play',	# 0 = off,  not 0 = on
  	#	'use_common_ins',		# 0 = off,  not 0 = on
  	#	'use_common_outs',		# 0 = off,  not 0 = on
  	#	'relative_sync',		# 0 = off, not 0 = on
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
  	#	'discrete_prefader',	# 0 == off, not 0 = on
	#	'next_state,'			# same as state
		'loop_len',				# in seconds
  		'loop_pos',				# in seconds
  		'cycle_len',			# in seconds
  		'free_time',			# in seconds
  		'total_time',			# in seconds
  		'rate_output',
	#	'in_peak_meter',		# absolute float sample value 0.0 -> 1.0 (or higher)
  	#	'out_peak_meter',		# absolute float sample value 0.0 -> 1.0 (or higher)
  		'is_soloed'				# 1 if soloed, 0 if not
	]

	SL_STATES ={
		-1: {'name': 'unknown', 'symbol': None},
		0: {'name': 'Off','symbol': None},
		1: {'name': 'WaitStart', 'symbol': None},
		2: {'name': 'Recording', 'symbol': 'record'},
		3: {'name': 'WaitStop', 'symbol': None},
		4: {'name': 'Playing', 'symbol': None},
		5: {'name': 'Overdubbing', 'symbol': 'overdub'},
		6: {'name': 'Multiplying', 'symbol': 'multiply'},
		7: {'name': 'Inserting', 'symbol': 'insert'},
		8: {'name': 'Replacing', 'symbol': 'replace'},
		9: {'name': 'Delay', 'symbol': 'delay'},
		10: {'name': 'Muted', 'symbol': 'mute'},
		11: {'name': 'Scratching', 'symbol': 'scratch'},
		12: {'name': 'OneShot', 'symbol': 'oneshot'},
		13: {'name': 'Substitute', 'symbol': 'substitute'},
		14: {'name': 'Paused', 'symbol': 'pause'}
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

		#self.custom_gui_fpath = "/zynthian/zynthian-ui/zyngui/zynthian_widget_sooperlooper.py"
		self.start()

		# MIDI Controllers
		self._ctrls=[
			['record', None, 'off', [['off', 'on'],[0.0, 1.0]]],
			['overdub', None, 'off', [['off', 'on'],[0.0, 1.0]]],
			['multiply', None, 'off', [['off', 'on'],[0.0, 1.0]]],
			['replace', None, 'off', [['off', 'on'],[0.0, 1.0]]],
			['substitute', None, 'off', [['off', 'on'],[0.0, 1.0]]],
			['insert', None, 'off', [['off', 'on'],[0.0, 1.0]]],
			['delay', None, 'off', [['off', 'on'],[0, 1]]],
			['undo/redo', None, '<>', ['<', '<>', '>']],
			['redo', None, 'off', [['off', 'on'],[0.0, 1.0]]],
			['trigger', None, 'off', [['off', 'on'],[0.0, 1.0]]],
			['mute', None, 'off', [['off', 'on'],[0.0, 1.0]]],
			['oneshot', None, 'off', [['off', 'on'],[0.0, 1.0]]],
			['solo', None, 'off', [['off', 'on'],[0.0, 1.0]]],
			['pause', None, 'off', [['off', 'on'],[0.0, 1.0]]],
			['reverse', None, 'forward', [['forward', 'reverse'],[0.0, 1.0]]],
			['scratch', None, 'normal', [['normal', 'scratch'],[0.0, 1.0]]],
			['rate', None, 0.0, 4.0], #TODO: Set min val=0.25
			['stretch_ratio', None, 0.0, 4.0], #TODO: Set min val=0.5
			['position', None, 0.0, 0.0], #TODO: Set position max value (dynamic)
			['pitch_shift', None, 0.0, 12], #TODO: Set min val=-12
			['sync', None, 'None', [['None','Internal','MidiClock','Jack/Host','Loop1'],[0,0,1.0,2.0,3.0,4.0]]],
            ['tempo', None, 120, 240],
            ['8th/cycle', None, 16, 32], #TODO: Set min val=1
            ['quantize', None, 'off', [['off', 'cycle', '8th', 'loop'],[0.0, 1.0, 2.0, 3.0]]],
            ['mute_quantized', None, 'off', [['off', 'on'],[0.0, 1.0]]],
            ['overdub_quantized', None, 'off', [['off', 'on'],[0.0, 1.0]]],
            ['repl quant', None, 'off', [['off', 'on'],[0.0, 1.0]]],
            ['round', None, 'off', [['off', 'on'],[0.0, 1.0]]],
            ['ref sync', None, 'off', [['off', 'on'],[0.0, 1.0]]],
            ['auto 8th', None, 'on', [['off', 'on'],[0.0, 1.0]]],
            ['sync', None, 'off', [['off', 'on'],[0.0, 1.0]]],
            ['play sync', None, 'off', [['off', 'on'],[0.0, 1.0]]],
            ['p.feedb', None, 'off', [['off', 'on'],[0.0, 1.0]]],
            ['t.stretch', None, 'off', [['off', 'on'],[0.0, 1.0]]],
			['rec_thresh', None, 0.0, 1.0],
			['feedback', None, 0.0, 1.0],
			['dry', None, 0.0, 1.0],
			['wet', None, 0.0, 1.0]
		]

		# Controller Screens
		self._ctrl_screens = [
			['Rec 1',['record','overdub','multiply','undo/redo']],
			['Rec 2',['replace','substitute','insert','delay']],
			['Play 1',['trigger','oneshot','mute','pause']],
			['Play 2',['solo','reverse','scratch',None]],
			['Play 3',['position','pitch_shift','rate','stretch_ratio']],
			['Misc 1',['sync','tempo','8th/cycle',None]],
			['Misc 2',['round','ref sync','auto 8th','sync']],
			['Misc 3',['play sync','p.feedb','t.stretch',None]],
			['Quantize',['quantize','mute quant','odub quant','repl quant']],
			['Levels',['rec_thresh', 'feedback', 'dry', 'wet']]
		]

        #TODO: Monitors
		self.monitors_dict = OrderedDict()


	# ---------------------------------------------------------------------------
	# Subproccess Management & IPC
	# ---------------------------------------------------------------------------

	def start(self):
		logging.warning("Starting SooperLooper")
		self.osc_init(self.SL_PORT)
		super().start()
		sleep(1)
		liblo.send(self.osc_target, '/sl/0/register_auto_update', ('s', 'state'), ('i', 100), ('s', self.osc_server_url), ('s', '/sl/state'))
		for symbol in self.SL_CONTROLS:
			liblo.send(self.osc_target, '/sl/0/register_update', ('s', symbol), ('s', self.osc_server_url), ('s', '/sl/control'))


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

	def send_controller_value(self, zctrl):
		logging.warning("{} {}".format(zctrl.symbol, zctrl.value))
		if zctrl.symbol == 'delay':
			if zctrl.value:
				liblo.send(self.osc_target, '/sl/0/set', ('s', 'delay_trigger', ('f', 1.0)))
		elif zctrl.is_toggle:
			liblo.send(self.osc_target, '/sl/0/hit', ('s', zctrl.symbol))
		elif zctrl.symbol == 'undo/redo':
			if zctrl.value == 0:
				liblo.send(self.osc_target, '/sl/0/hit', ('s', 'undo'))
			elif zctrl.value == 2:
				liblo.send(self.osc_target, '/sl/0/hit', ('s', 'redo'))
			zctrl.set_value(1, False) #TODO: This should be triggered by redo_is_tap but does not seem to work
		else:
			liblo.send(self.osc_target, '/sl/0/set', ('s', zctrl.symbol), ('f', zctrl.value))


	def get_monitors_dict(self):
		return self.monitors_dict


	# ---------------------------------------------------------------------------
	# Specific functions
	# ---------------------------------------------------------------------------

	# Update each mutually exclusive 'state' controller to match current state
	def update_state(self):
		for state in self.SL_STATES:
			if self.SL_STATES[state]['symbol']:
				if state == self.state:
					self.zctrls[self.SL_STATES[state]['symbol']].set_value(1, False)
				else:
					self.zctrls[self.SL_STATES[state]['symbol']].set_value(0, False)


	def cb_osc_all(self, path, args, types, src):
		logging.warning(path)
		if path == '/sl/state':
			# args: i:Loop index, s:control, f:value
			self.state = int(args[2])
			self.update_state()

			if args[2] == 0:
    				# Off
				logging.warning("OFF")
			elif args[2] == 1:
				# WaitStart
				logging.warning("WAIT START")
			elif args[2] == 2:
				# Recording
				logging.warning("RECORDING")
			elif args[2] == 3:
				# WaitStop
				logging.warning("WAIT STOP")
			elif args[2] == 4:
				# Playing
				logging.warning("PLAYING")
			elif args[2] == 5:
				# Overdubbing
				logging.warning("OVERDUBBING")
			elif args[2] == 6:
				# Multiplying
				logging.warning("MULTIPLYING")
			elif args[2] == 7:
    				# Inserting
				logging.warning("INSERTING")
			elif args[2] == 8:
    				# Replacing
				logging.warning("REPLACING")
			elif args[2] == 9:
    				# Delay
				logging.warning("DELAY")
			elif args[2] == 10:
    				# Muted
				logging.warning("MUTED")
			elif args[2] == 11:
    				# Scratching
				logging.warning("SCRATCHING")
			elif args[2] == 12:
    				# OneShot
				logging.warning("ONE SHOT")
			elif args[2] == 13:
    				# Substitute
				logging.warning("SUBSTITUTE")
			elif args[2] == 14:
    				# Paused
				logging.warning("PAUSED")

		elif path == '/sl/control':
			if args[1] == 'rate_output':
				logging.warning('rate: %f', args[2])
				if args[2] < 0.0:
					self.zctrls['reverse'].set_value(1.0, False)
				else:
					self.zctrls['reverse'].set_value(0.0, False)
			elif args[1] == 'delay_trigger':
				self.zctrls['delay'].set_value(1.0, False)
			elif args[1] in ['redo_is_tap', 'undo_is_tap']:
				self.zctrls['undo/redo'].set_value(1, False)
			elif args[1] in self.SL_CONTROLS:
				try:
					self.zctrls[args[1]].set_value(args[2], False)
				except Exception as e:
					logging.warning("Unsupported tally %s (%f)", args[1], args[2])


	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

#******************************************************************************
