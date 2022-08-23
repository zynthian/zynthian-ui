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
import os
from glob import glob
from  subprocess import Popen,DEVNULL
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
	MAX_LOOPS = 6

	# SL_LOOP_PARAMS act on individual loops - sent with osc command /sl/#/set
	SL_LOOP_PARAMS = [
		'feedback',				# range 0 -> 1
	#	'dry',					# range 0 -> 1
		'wet',					# range 0 -> 1
	#	'input_gain',			# range 0 -> 1
		'rate',        			# range 0.25 -> 4.0
	#	'scratch_pos',			# range 0 -> 1
	#	'delay_trigger',		# any changes
	#	'quantize',				# 0 = off, 1 = cycle, 2 = 8th, 3 = loop
	#	'round',				# 0 = off,  not 0 = on
	#	'redo_is_tap'			# 0 = off,  not 0 = on
  		'sync',					# 0 = off,  not 0 = on
  		'playback_sync',		# 0 = off,  not 0 = on
  	#	'use_rate',				# 0 = off,  not 0 = on
  	#	'fade_samples',			# 0 -> ...
  		'use_feedback_play',	# 0 = off,  not 0 = on
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
  		'replace_quantized',	# 0 == off, not 0 = on (undocumented)
  	#	'discrete_prefader',	# 0 == off, not 0 = on
	#	'next_state,'			# same as state
		'stretch_ratio',		# 0.5 -> 4.0 (undocumented)
	#	'tempo_stretch',		# 0 = off, not 0 = on (undocumented)
		'pitch_shift'			# -12 -> 12 (undocumented)
	]

	# SL_LOOP_GLOBAL_PARAMS act on all loops - sent with osc command /sl/-1/set
	SL_LOOP_GLOBAL_PARAMS = [
		'rec_thresh',			# range 0 -> 1
		'round',				# 0 = off,  not 0 = on
  		'relative_sync',		# 0 = off, not 0 = on
		'quantize',				# 0 = off, 1 = cycle, 2 = 8th, 3 = loop
  	#	'mute_quantized',		# 0 = off, not 0 = on
  	#	'overdub_quantized',	# 0 == off, not 0 = on
  	#	'replace_quantized',	# 0 == off, not 0 = on (undocumented)
	]

	# SL_GLOBAL_PARAMS act on whole engine - sent with osc command /set
	SL_GLOBAL_PARAMS = [
	#	'tempo',				# bpm
	#	'eighth_per_cycle',
		'dry',					# range 0 -> 1 affects common input passthru
	#	'wet',					# range 0 -> 1  affects common output level
		'input_gain',			# range 0 -> 1  affects common input gain
		'sync_source',			# -3 = internal,  -2 = midi, -1 = jack, 0 = none, # > 0 = loop number (1 indexed) 
	#	'tap_tempo',			# any changes
	#	'save_loop',			# any change triggers quick save, be careful
	#	'auto_disable_latency',	# when 1, disables compensation when monitoring main inputs
	#	'select_next_loop',		# any changes
	#	'select_prev_loop',		# any changes
	#	'select_all_loops',		# any changes
		'selected_loop_num',	# -1 = all, 0->N selects loop instances (first loop is 0, etc) 
	#	'smart_eighths',		# 0 = off, not 0 = on (undocumented)
	]

	SL_MONITORS = [
  		'rate_output',			# Used to detect direction but must use register_auto_update
		'in_peak_meter',		# absolute float sample value 0.0 -> 1.0 (or higher)
  	#	'out_peak_meter',		# absolute float sample value 0.0 -> 1.0 (or higher)
	#	'loop_len',				# in seconds
  	#	'loop_pos',				# in seconds
  	#	'cycle_len',			# in seconds
  	#	'free_time',			# in seconds
  	#	'total_time',			# in seconds
  	#	'is_soloed',			# 1 if soloed, 0 if not
	]


	SL_STATES = {
		-1: {'name': 'unknown', 'symbol': None, 'icon':''},
		0: {'name': 'off','symbol': None, 'icon':''},
		1: {'name': 'rec starting...', 'symbol': None, 'icon':'\u23EF'},
		2: {'name': 'recording', 'symbol': 'record', 'icon':'\u26ab'},
		3: {'name': 'rec stopping...', 'symbol': None, 'icon':'\u23EF'},
		4: {'name': 'playing', 'symbol': None, 'icon':'\uf04b'},
		5: {'name': 'overdubbing', 'symbol': 'overdub', 'icon':'\u26ab'},
		6: {'name': 'multiplying', 'symbol': 'multiply', 'icon':'\u26abx'},
		7: {'name': 'inserting', 'symbol': 'insert', 'icon':'\u26ab'},
		8: {'name': 'replacing', 'symbol': 'replace', 'icon':'\u26ab'},
		9: {'name': 'delaying', 'symbol': None, 'icon':'delay'},
		10: {'name': 'muted', 'symbol': None, 'icon':'mute'},
		11: {'name': 'scratching', 'symbol': None, 'icon':'scratch'},
		12: {'name': 'playing once', 'symbol': 'oneshot', 'icon':'\uf04b'},
		13: {'name': 'substituting', 'symbol': 'substitute', 'icon':'\u26ab'},
		14: {'name': 'paused', 'symbol': 'pause', 'icon':'\u23F8'},
		15: {'name': 'undo all', 'symbol': None, 'icon':''},
		16: {'name': 'trigger play...', 'symbol': None, 'icon':''},
		17: {'name': 'undo', 'symbol': None, 'icon':''},
		18: {'name': 'redo', 'symbol': None, 'icon':''},
		19: {'name': 'redo all', 'symbol': None, 'icon':''},
		20: {'name': 'off muted', 'symbol': None, 'icon':'mute'},
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
		self.options['audio_capture'] = True
		self.options['drop_pc'] = True
		self.options['clone'] = False

		self.command = ['sooperlooper', '-q', '-l 0', '-D no', '-p {}'.format(self.SL_PORT), '-j {}'.format(self.jackname)]

		self.state = [-1] * self.MAX_LOOPS # Current SL state for each loop
		self.next_state = [-1] * self.MAX_LOOPS # Next SL state for each loop (-1 if no state change pending)
		self.waiting = [0] * self.MAX_LOOPS # 1 if a change of state is pending
		self.selected_loop = 0
		self.loop_count = 1
		self.channels = 2

		self.custom_gui_fpath = "/zynthian/zynthian-ui/zyngui/zynthian_widget_sooperlooper.py"
		self.monitors_dict = OrderedDict({
			'state':0,
			'next_state':-1,
			'loop_count':0
		})

		# MIDI Controllers
		loop_labels = []
		for i in range(self.MAX_LOOPS):
			loop_labels.append(str(i + 1))
		self._ctrls=[
			#symbol, name, {options}, midi_cc
			['record', 'record', {'value':0, 'value_max':1, 'labels':['off', 'on'], 'is_toggle':True, 'is_toggle':True}, 102],
			['overdub', 'overdub', {'value':0, 'value_max':1, 'labels':['off', 'on'], 'is_toggle':True}, 103],
			['multiply', 'multiply', {'value':0, 'value_max':1, 'labels':['off', 'on'], 'is_toggle':True}, 104],
			['replace', 'replace', {'value':0, 'value_max':1, 'labels':['off', 'on'], 'is_toggle':True}, 105],
			['substitute', 'substitute', {'value':0, 'value_max':1, 'labels':['off', 'on'], 'is_toggle':True}, 106],
			['insert', 'insert', {'value':0, 'value_max':1, 'labels':['off', 'on'], 'is_toggle':True}, 107],
			['undo/redo', 'undo/redo', {'value':1, 'labels':['<', '<>', '>']}],
			['trigger', 'trigger', {'value':0, 'value_max':1, 'labels':['off', 'on'], 'is_toggle':True}, 108],
			['mute', 'mute', {'value':0, 'value_max':1, 'labels':['off', 'on'], 'is_toggle':True}, 109],
			['oneshot', 'oneshot', {'value':0, 'value_max':1, 'labels':['off', 'on'], 'is_toggle':True}, 110],
			['pause', 'pause', {'value':0, 'value_max':1, 'labels':['off', 'on'], 'is_toggle':True}, 111],
			['reverse', 'direction', {'value':0, 'labels':['reverse', 'forward'], 'ticks':[1, 0], 'is_toggle':True}],
			['rate', 'speed', {'value':1.0, 'value_min':0.25, 'value_max':4.0, 'is_integer':False, 'nudge_factor':0.01}],
			['stretch_ratio', 'stretch', {'value':1.0, 'value_min':0.5, 'value_max':4.0, 'is_integer':False, 'nudge_factor':0.01}],
			['pitch_shift', 'pitch', {'value':0.0, 'value_min':-12, 'value_max':12, 'is_integer':False, 'nudge_factor':0.1}],
			['sync_source', 'sync to', {'value':1, 'value_min':-3, 'value_max':1, 'labels':['Internal','MidiClock','Jack/Host','None','Loop1'], 'is_integer':True}],
			['sync', 'enable sync', {'value':1, 'value_max':1, 'labels':['off', 'on']}],
            ['eighth_per_cycle', '8th/cycle', {'value':16, 'value_min':1, 'value_max':600}], #TODO: What makes sense for max val?
            ['quantize', 'quantize', {'value':1, 'value_max':3, 'labels':['off', 'cycle', '8th', 'loop']}],
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
			['dry', 'dry', {'value':1.0, 'value_max':1.0, 'is_integer':False, 'is_logarithmic': True}],
			['wet', 'wet', {'value':1.0, 'value_max':1.0, 'is_integer':False, 'is_logarithmic': True}],
			['input_gain', 'input gain', {'value':1.0, 'value_max':1.0, 'is_integer':False, 'is_logarithmic': True}],
			['loop_count', 'loop count', {'value':1, 'value_min':1, 'value_max':self.MAX_LOOPS}],
			['selected_loop_num', 'selected loop', {'value':1, 'value_min':1, 'value_max': 1}]
		]

		# Controller Screens
		self._ctrl_screens = [
			['Rec 1',['record','overdub','multiply','undo/redo']],
			['Rec 2',['replace','substitute','insert','undo/redo']],
			['Play 1',['trigger','oneshot','mute','pause']],
			['Play 2',['reverse','pitch_shift','rate','stretch_ratio']],
			['Sync 1',['sync_source','sync','playback_sync','relative_sync']],
			['Sync 2',['round', 'use_feedback_play']],
			['Quantize',['quantize','mute_quantized','overdub_quantized','replace_quantized']],
			['Levels 1',['rec_thresh', 'feedback', 'wet', 'dry']],
			['Levels 2',['input_gain', 'selected_loop_num', 'loop_count']]
		]

		self.zctrls = OrderedDict()
		self.start()


	# ---------------------------------------------------------------------------
	# Subproccess Management & IPC
	# ---------------------------------------------------------------------------

	def start(self):
		#logging.warning("Starting SooperLooper")
		self.osc_init(self.SL_PORT)
		self.proc = Popen(self.command, stdout=DEVNULL, stderr=DEVNULL)
		sleep(1) #TODO: Cludgy wait - maybe should perform periodic check for server until reachable

		# Register for common events from sooperlooper server - request changes to the currently selected loop
		for symbol in self.SL_MONITORS:
			liblo.send(self.osc_target, '/sl/-3/register_auto_update', ('s', symbol), ('i', 100), ('s', self.osc_server_url), ('s', '/monitor'))
		for symbol in self.SL_LOOP_PARAMS:
			liblo.send(self.osc_target, '/sl/-3/register_auto_update', ('s', symbol), ('i', 100), ('s', self.osc_server_url), ('s', '/control'))
		for symbol in self.SL_LOOP_GLOBAL_PARAMS:
			# Register for tallies of commands sent to all channels
			liblo.send(self.osc_target, '/sl/-3/register_auto_update', ('s', symbol), ('i', 100), ('s', self.osc_server_url), ('s', '/control'))

		# Register for global events from sooperlooper
		for symbol in self.SL_GLOBAL_PARAMS:
			liblo.send(self.osc_target, '/register_auto_update', ('s', symbol), ('i', 100), ('s', self.osc_server_url), ('s', '/control'))
		liblo.send(self.osc_target, '/register', ('s', self.osc_server_url), ('s', '/info'))

		# Request current quantity of loops
		liblo.send(self.osc_target, '/ping', ('s', self.osc_server_url), ('s', '/info'))


	def stop(self):
		if self.proc:
			try:
				logging.info("Stoping Engine " + self.name)
				self.proc.terminate()
				sleep(0.2)
				self.proc.kill()
				self.proc = None
			except Exception as err:
				logging.error("Can't stop engine {} => {}".format(self.name, err))


	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------


	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------


	# ---------------------------------------------------------------------------
	# Bank Management
	# ---------------------------------------------------------------------------

	# No bank support for sooperlooper
	def get_bank_list(self, layer=None):
		return [("", None, "", None)]


	# ---------------------------------------------------------------------------
	# Preset Management
	# ---------------------------------------------------------------------------

	def get_preset_list(self, bank):
		presets = self.get_filelist('{}/presets/sooperlooper'.format(self.data_dir), 'slsess')
		presets += self.get_filelist('{}/presets/sooperlooper'.format(self.my_data_dir), 'slsess')
		return presets


	def set_preset(self, layer, preset, preload=False):
		liblo.send(self.osc_target, '/load_session', ('s', preset[0]),  ('s', self.osc_server_url), ('s', '/error'))
		sleep(0.3) # Wait for session to load to avoid consequent controller change conflicts
		liblo.send(self.osc_target, '/ping', ('s', self.osc_server_url), ('s', '/info'))

		for symbol in self.SL_MONITORS:
			liblo.send(self.osc_target, '/sl/-3/get', ('s', symbol), ('s', self.osc_server_url), ('s', '/monitor'))
		for symbol in self.SL_LOOP_PARAMS:
			liblo.send(self.osc_target, '/sl/-3/get', ('s', symbol), ('s', self.osc_server_url), ('s', '/control'))
		for symbol in self.SL_LOOP_GLOBAL_PARAMS:
			liblo.send(self.osc_target, '/sl/-3/get', ('s', symbol), ('s', self.osc_server_url), ('s', '/control'))
		for symbol in self.SL_GLOBAL_PARAMS:
			liblo.send(self.osc_target, '/get', ('s', symbol), ('s', self.osc_server_url), ('s', '/control'))
		sleep(0.3) # Wait for session to load to avoid consequent controller change conflicts


	def preset_exists(self, bank_info, preset_name):
		return os.path.exists('{}/presets/sooperlooper/{}.slsess'.format(self.my_data_dir, preset_name))


	def save_preset(self, bank_name, preset_name):
		path = '{}/presets/sooperlooper'.format(self.my_data_dir)
		if not os.path.exists(path):
			try:
				os.mkdir(path)
			except Exception as e:
				logging.warning("Failed to create SooperLooper user preset directory: {}".format(e))
		uri = '{}/{}.slsess'.format(path, preset_name)
		liblo.send(self.osc_target, '/save_session', ('s', uri),  ('s', self.osc_server_url), ('s', '/error'), ('i', 1))
		return uri


	def delete_preset(self, bank, preset):
		try:
			os.remove(preset[0])
			wavs = glob('{}_loop*.wav'.format(preset[0]))
			for file in wavs:
				os.remove(file)
		except Exception as e:
			logging.debug(e)


	def rename_preset(self, bank_info, preset, new_name):
		try:
			os.rename(preset[0], '{}/presets/sooperlooper/{}.slsess'.format(self.my_data_dir, new_name))
			return True
		except Exception as e:
			logging.debug(e)
			return False


	#----------------------------------------------------------------------------
	# Controllers Management
	#----------------------------------------------------------------------------

	def get_controllers_dict(self, layer):
		if not self.zctrls:
			for ctrl in self._ctrls:
				zctrl = zynthian_controller(self, ctrl[0], ctrl[1], ctrl[2])
				self.zctrls[zctrl.symbol] = zctrl
				if len(ctrl) > 3:
					zctrl.set_midi_learn(layer.midi_chan, ctrl[3])
		return self.zctrls


	def send_controller_value(self, zctrl):
		#logging.warning("{} {}".format(zctrl.symbol, zctrl.value))
		if zctrl.symbol in ['oneshot', 'oneshot', 'trigger'] and zctrl.value == 0:
			# Ignore off signals
			return
		elif zctrl.is_toggle:
			# Use is_toggle to indicate the SL function is a toggle, i.e. press to engage, press to release
			if zctrl.symbol == 'record' and zctrl.value == 0 and self.state[self.selected_loop] == 1:
    			#TODO: Implement better toggle of pending state
				liblo.send(self.osc_target, '/sl/-3/hit', ('s', 'undo'))
				return
			liblo.send(self.osc_target, '/sl/-3/hit', ('s', zctrl.symbol))
			if zctrl.symbol == 'trigger':
				zctrl.set_value(0, False) # Make trigger a pulse
		elif zctrl.symbol == 'undo/redo':
			# Use single controller to perform undo (CCW) and redo (CW)
			if zctrl.value == 0:
				liblo.send(self.osc_target, '/sl/-3/hit', ('s', 'undo'))
			elif zctrl.value == 2:
				liblo.send(self.osc_target, '/sl/-3/hit', ('s', 'redo'))
			zctrl.set_value(1, False)
		elif zctrl.symbol == 'selected_loop_num':
			self.select_loop(zctrl.value - 1, True)
		elif zctrl.symbol == 'loop_count':
			for loop in range(self.loop_count, zctrl.value):
				liblo.send(self.osc_target, '/loop_add', ('i', self.channels), ('f', 30), ('i', 0))
			if zctrl.value < self.loop_count:
				# Don't remove loops - let GUI offer option to (confirm and) remove
				zctrl.set_value(self.loop_count, False)
				self.monitors_dict['loop_del'] = True
		else:
			if zctrl.symbol in self.SL_LOOP_PARAMS: # Selected loop
				liblo.send(self.osc_target, '/sl/-3/set', ('s', zctrl.symbol), ('f', zctrl.value))
			if zctrl.symbol in self.SL_LOOP_GLOBAL_PARAMS: # All loops
				liblo.send(self.osc_target, '/sl/-1/set', ('s', zctrl.symbol), ('f', zctrl.value))
			if zctrl.symbol in self.SL_GLOBAL_PARAMS: # Global params
				liblo.send(self.osc_target, '/set', ('s', zctrl.symbol), ('f', zctrl.value))


	def get_monitors_dict(self):
		return self.monitors_dict


	# ---------------------------------------------------------------------------
	# Specific functions
	# ---------------------------------------------------------------------------

	# Update each mutually exclusive 'state' controller to match state of selected loop
	def update_state(self):
		for state in self.SL_STATES:
			if state < 0:
				continue
			if self.SL_STATES[state]['symbol']:
				if state == self.state[self.selected_loop]:
					self.zctrls[self.SL_STATES[state]['symbol']].set_value(1, False)
				else:
					self.zctrls[self.SL_STATES[state]['symbol']].set_value(0, False)
		#self.layers[0].status = self.SL_STATES[self.state]['icon']


	def cb_osc_all(self, path, args, types, src):
		try:
			#logging.warning("Rx OSC: {} {}".format(path,args))
			if path == '/state':
				# args: i:Loop index, s:control, f:value
				#logging.warning("Loop: %d %s=%0.1f", args[0], args[1], args[2])
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

				self.monitors_dict['state_{}'.format(loop)] = self.state[loop]
				self.monitors_dict['next_state_{}'.format(loop)] = self.next_state[loop]
				self.monitors_dict['waiting_{}'.format(loop)] = self.waiting[loop]
				if self.selected_loop == loop:
					self.monitors_dict['state'] = self.state[loop]
					self.monitors_dict['next_state'] = self.next_state[loop]
					self.monitors_dict['waiting'] = self.waiting[loop]
					self.update_state()

			elif path == '/info':
				# args: s:hosturl  s:version  i:loopcount
				#logging.warning("Info: from %s ver: %s loops: %d", args[0], args[1], args[2])
				self.sl_version = args[1]
				loop_count_changed = int(args[2]) - self.loop_count # +/- quantity of added/removed loops
				self.loop_count = int(args[2])
				if loop_count_changed:
					labels = ['Internal','MidiClock','Jack/Host','None']
					for loop in range(self.loop_count):
						labels.append('Loop {}'.format(loop + 1))
					try:
							self.zctrls['sync_source'].set_options({'labels':labels, 'ticks':[], 'value_max':self.loop_count})
							self.zctrls['loop_count'].set_value(self.loop_count, False)
							self.zctrls['selected_loop_num'].value_max = self.loop_count
					except:
						pass # zctrls may not yet be initialised
					if loop_count_changed > 0:
						for i in range(loop_count_changed):
							liblo.send(self.osc_target, '/sl/{}/register_auto_update'.format(self.loop_count - 1 - i), ('s', 'loop_pos'), ('i', 100), ('s', self.osc_server_url), ('s', '/monitor'))
							liblo.send(self.osc_target, '/sl/{}/register_auto_update'.format(self.loop_count - 1 - i), ('s', 'loop_len'), ('i', 100), ('s', self.osc_server_url), ('s', '/monitor'))
							liblo.send(self.osc_target, '/sl/{}/register_auto_update'.format(self.loop_count - 1 - i), ('s', 'mute'), ('i', 100), ('s', self.osc_server_url), ('s', '/monitor'))
							liblo.send(self.osc_target, '/sl/{}/register_auto_update'.format(self.loop_count - 1 - i), ('s', 'state'), ('i', 100), ('s', self.osc_server_url), ('s', '/state'))
							liblo.send(self.osc_target, '/sl/{}/register_auto_update'.format(self.loop_count - 1 - i), ('s', 'next_state'), ('i', 100), ('s', self.osc_server_url), ('s', '/state'))
							liblo.send(self.osc_target, '/sl/{}/register_auto_update'.format(self.loop_count - 1 - i), ('s', 'waiting'), ('i', 100), ('s', self.osc_server_url), ('s', '/state'))
							if self.loop_count > 1:
								# Set defaults for new loops
								liblo.send(self.osc_target, '/sl/{}/set'.format(self.loop_count - 1 - i), ('s', 'sync'), ('f', 1))
						if self.loop_count > 1:
							self.select_loop(self.loop_count - 1, True)

					liblo.send(self.osc_target, '/get', ('s', 'sync_source'), ('s', self.osc_server_url), ('s', '/control'))
					if self.selected_loop > self.loop_count:
						self.select_loop(self.loop_count - 1, True)

				self.monitors_dict['loop_count'] = self.loop_count
				self.monitors_dict['version'] = self.sl_version
			elif path == '/control':
				# args: i:Loop index, s:control, f:value
				#logging.warning("Control: Loop %d %s=%0.2f", args[0], args[1], args[2])
				self.monitors_dict[args[1]] = args[2]
				if args[1] == 'selected_loop_num':
					self.select_loop(args[2])
					return
				try:
					self.zctrls[args[1]].set_value(args[2], False)
				except Exception as e:
					logging.warning("Unsupported tally (or zctrl not yet configured) %s (%f)", args[1], args[2])
			elif path == '/monitor':
				# args: i:Loop index, s:control, f:value
				# Handle events registered for selected loop
				if args[0] == -3:
					if args[1] == 'rate_output':
						try:
							if args[2] < 0.0:
								self.zctrls['reverse'].set_value(1, False)
							else:
								self.zctrls['reverse'].set_value(0, False)
						except:
							pass # zctrls may not yet be initialised
					self.monitors_dict[args[1]] = args[2]
				else:
					self.monitors_dict['{}_{}'.format(args[1], args[0])] = args[2]
					#if args[1] in ['loop_len', 'rate_output', 'mute']:
					#	logging.warning("Monitor: Loop %d %s=%0.2f", args[0], args[1], args[2])
			elif path == 'error':
				logging.warning("SooperLooper daemon error: {}".format(args[0]))
		except Exception as e:
			logging.warning(e)


	def select_loop(self, loop, send=False):
		if loop < 0 or loop >= self.MAX_LOOPS:
			return #TODO: Handle -1 == all loops
		self.selected_loop = int(loop)
		self.monitors_dict['state'] = self.state[self.selected_loop]
		self.monitors_dict['next_state'] = self.next_state[self.selected_loop]
		self.monitors_dict['waiting'] = self.waiting[self.selected_loop]
		try:
			self.zctrls['selected_loop_num'].set_value(loop + 1, False)
		except:
			pass
		if send:
			liblo.send(self.osc_target, '/set', ('s', 'selected_loop_num'), ('f', self.selected_loop))

	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

#******************************************************************************
