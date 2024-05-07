# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_setbfree)
# 
# zynthian_engine implementation for setBfree Hammond Emulator
# 
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
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

import re
import logging
from zyngine.zynthian_processor import zynthian_processor

from . import zynthian_engine
import zynautoconnect

# ------------------------------------------------------------------------------
# setBfree Engine Class
# ------------------------------------------------------------------------------


class zynthian_engine_setbfree(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Banks
	# ---------------------------------------------------------------------------

	bank_manuals_list = [
		['Upper', 0, 'Upper', '_', [False, False, 59]],
		['Upper + Lower', 1, 'Upper + Lower', '_', [True, False, 59]],
		['Upper + Pedals', 2, 'Upper + Pedals', '_', [False, True, 59]],
		['Upper + Lower + Pedals', 3, 'Upper + Lower + Pedals', '_', [True, True, 59]],
		['Split Lower/Upper', 4, 'Split Lower/Upper', '_', [True, False, 56]],
		['Split Pedals/Upper', 5, 'Split Pedals/Upper', '_', [False, True, 58]],
		['Split Pedals/Lower/Upper', 6, 'Split Pedals/Lower/Upper', '_', [True, True, 57]]
	]

	bank_twmodels_list = [
		['Sin', 0, 'Sine', '_'],
		['Sqr', 1, 'Square', '_'],
		['Tri', 2, 'Triangle', '_']
	]

	tonewheel_config = {
		"Sin": "",

		"Sqr": """
			osc.harmonic.1=1.0
			osc.harmonic.3=0.333333333333
			osc.harmonic.5=0.2
			osc.harmonic.7=0.142857142857
			osc.harmonic.9=0.111111111111
			osc.harmonic.11=0.090909090909""",

		"Tri": """
			osc.harmonic.1=1.0
			osc.harmonic.3=0.111111111111
			osc.harmonic.5=0.04
			osc.harmonic.7=0.02040816326530612
			osc.harmonic.9=0.012345679012345678
			osc.harmonic.11=0.008264462809917356"""
	}

	# ---------------------------------------------------------------------------
	# Controllers & Screens
	# ---------------------------------------------------------------------------

	drawbar_ticks = [['0', '1', '2', '3', '4', '5', '6', '7', '8'], [127, 119, 103, 87, 71, 55, 39, 23, 7]]

	# MIDI Controllers
	_ctrls = [
		['volume', 7, 96, 127],
		#['swellpedal 2', 11, 96],
		['reverb', 91, 4, 127],
		['convol. mix', 94, 64, 127],

		['rotary toggle', 64, 'off', 'off|on'],
		#['rotary speed', 1, 64, 127],
		#['rotary speed', 1, 'off', 'slow|off|fast'],
		['rotary speed', 1, 'off', [['slow', 'off', 'fast'], [0, 43, 86]]],
		#['rotary select', 67, 0, 127],
		#['rotary select', 67, 'off/off', 'off/off|slow/off|fast/off|off/slow|slow/slow|fast/slow|off/fast|slow/fast|fast/fast'],
		['rotary select', 67, 'off/off', [['off/off', 'slow/off', 'fast/off', 'off/slow', 'slow/slow', 'fast/slow', 'off/fast', 'slow/fast', 'fast/fast'], [0, 15, 30, 45, 60, 75, 90, 105, 120]]],
		['DB 16', 70, '8', drawbar_ticks],
		['DB 5 1/3', 71, '8', drawbar_ticks],
		['DB 8', 72, '8', drawbar_ticks],
		['DB 4', 73, '0', drawbar_ticks],
		['DB 2 2/3', 74, '0', drawbar_ticks],
		['DB 2', 75, '0', drawbar_ticks],
		['DB 1 3/5', 76, '0', drawbar_ticks],
		['DB 1 1/3', 77, '0', drawbar_ticks],
		['DB 1', 78, '0', drawbar_ticks],

		['vibrato upper', 31, 'off', 'off|on'],
		['vibrato lower', 30, 'off', 'off|on'],
		['vibrato routing', 95, 'off', 'off|lower|upper|both'],
		#['vibrato selector', 92, 'c3', 'v1|v2|v3|c1|c2|c3'],
		['vibrato selector', 92, 'c3', [['v1', 'v2', 'v3', 'c1', 'c2', 'c3'], [0, 23, 46, 69, 92, 115]]],

		#['percussion', 66, 'off' ,'off|on'],
		['percussion', 80, 'off', 'off|on'],
		['percussion volume', 81, 'soft', 'soft|hard'],
		['percussion decay', 82, 'slow', 'slow|fast'],
		['percussion harmonic', 83, '2nd', '2nd|3rd'],

		['overdrive', 65, 'off', 'off|on'],
		['overdrive character', 93, 0, 127],
		['overdrive inputgain', 21, 45, 127],
		['overdrive outputgain', 22, 10, 127]
	]

	# Controller Screens
	_ctrl_screens = [
		['main', ['volume', 'percussion', 'rotary speed', 'vibrato routing']],
		['drawbars 1', ['DB 16', 'DB 5 1/3', 'DB 8', 'DB 4']],
		['drawbars 2', ['DB 2 2/3', 'DB 2', 'DB 1 3/5', 'DB 1 1/3']],
		['drawbars 3 & reverb', ['DB 1', 'reverb', 'convol. mix']],
		['rotary', ['rotary toggle', 'rotary select', 'rotary speed']],
		['vibrato', ['vibrato upper', 'vibrato lower', 'vibrato routing', 'vibrato selector']],
		['percussion', ['percussion', 'percussion decay', 'percussion harmonic', 'percussion volume']],
		['overdrive', ['overdrive', 'overdrive character', 'overdrive inputgain', 'overdrive outputgain']]
	]

	# setBfree preset params => controllers
	_param2zcsymbol = {
		'reverbmix': 'reverb',
		'rotaryspeed': 'rotary speed',
		'drawbar_1': 'DB 16',
		'drawbar_2': 'DB 5 1/3',
		'drawbar_3': 'DB 8',
		'drawbar_4': 'DB 4',
		'drawbar_5': 'DB 2 2/3',
		'drawbar_6': 'DB 2',
		'drawbar_7': 'DB 1 3/5',
		'drawbar_8': 'DB 1 1/3',
		'drawbar_9': 'DB 1',
		'vibratoupper': 'vibrato upper',
		'vibratolower': 'vibrato lower',
		'vibratorouting': 'vibrato routing',
		'vibrato': 'vibrato selector',
		'perc': 'percussion',
		'percvol': 'percussion volume',
		'percspeed': 'percussion decay',
		'percharm': 'percussion harmonic',
		'overdrive': 'overdrive',
		'overdrive_char': 'overdrive character',
		'overdrive_igain': 'overdrive inputgain',
		'overdrive_ogain': 'overdrive outputgain'
	}

	# ----------------------------------------------------------------------------
	# Config variables
	# ----------------------------------------------------------------------------

	base_dir = zynthian_engine.data_dir + "/setbfree"
	presets_fpath = base_dir + "/pgm/all.pgm"
	config_tpl_fpath = base_dir + "/cfg/zynthian.cfg.tpl"
	config_my_fpath = zynthian_engine.config_dir + "/setbfree/zynthian.cfg"
	config_autogen_fpath = zynthian_engine.config_dir + "/setbfree/.autogen.cfg"

	# ----------------------------------------------------------------------------
	# Initialization
	# ----------------------------------------------------------------------------

	def __init__(self, state_manager=None):
		super().__init__(state_manager)
		self.name = "setBfree"
		self.nickname = "BF"
		self.jackname = "setBfree"

		self.options['midi_chan'] = False
		self.options['replace'] = False
		self.options['ctrl_fb'] = True

		self.manuals_config = None
		self.tonewheel_model = None
		self.show_favs_bank = False

		# Process command ...
		if self.config_remote_display():
			self.command = f"setBfree -p \"{self.presets_fpath}\" -c \"{self.config_autogen_fpath}\""
		else:
			self.command = f"setBfree -p \"{self.presets_fpath}\" -c \"{self.config_autogen_fpath}\"" 

		self.command_prompt = "\nAll systems go."

		self.reset()

	def start(self):
		self.state_manager.start_busy("setBfree")
		chain_manager = self.state_manager.chain_manager
		midi_chan = self.processors[0].get_midi_chan()
		self.midi_chans = [midi_chan, None, None]
		self.chan_names = {
			str(midi_chan): 'Upper'
		}
		logging.info("Upper manual processor in chan %d", midi_chan)
		i = 0
		self.processors[i].bank_name = "Upper"
		self.processors[i].get_bank_list()
		self.processors[i].set_bank(0, False)

		# Extra processors
		for j, manual in enumerate(["Lower", "Pedals"]):
			if self.manuals_config[4][j]:
				i += 1
				if len(self.processors) == i:
					try:
						midi_chan = chain_manager.get_next_free_midi_chan(midi_chan)
						if midi_chan is None:
							break
						self.midi_chans[j + 1] = midi_chan
						self.chan_names[str(midi_chan)] = manual
						logging.info("%s manual processor in chan %s", manual, midi_chan)
						chain_id = chain_manager.add_chain(None, midi_chan)
						chain = chain_manager.get_chain(chain_id)
						proc_id = chain_manager.get_available_processor_id()
						processor = zynthian_processor("BF", chain_manager.engine_info["BF"], proc_id)
						chain.insert_processor(processor)
						chain_manager.processors[proc_id] = processor
						self.processors.append(processor)
						self.processors[i].bank_name = manual
						self.processors[i].engine = self
						self.processors[i].get_bank_list()
						self.processors[i].set_bank(0, False)
						self.processors[i].refresh_controllers()
						chain.audio_out = []
						chain.mixer_chan = None
					except Exception as e:
						logging.error("%s Manual processor can't be added! => %s", manual, e)
				else:
					midi_chan = self.processors[i].get_midi_chan()
					self.midi_chans[j + 1] = midi_chan
					self.chan_names[str(midi_chan)] = manual

		# Start engine
		logging.debug("STARTING SETBFREE!!")
		self.generate_config_file(self.midi_chans)
		super().start()
		# Need to call autoconnect because engine starts later than chain/processor autorouting
		zynautoconnect.request_midi_connect(True)
		zynautoconnect.request_audio_connect()

		# Load manuals configuration program
		midi_prog = self.manuals_config[4][2]
		if midi_prog and isinstance(midi_prog, int):
			logging.debug("Loading manuals configuration program: {}".format(midi_prog))
			self.state_manager.zynmidi.set_midi_prg(self.midi_chans[0], midi_prog)

		# Load preset list for each manual and load preset 0
		for processor in self.processors:
			processor.load_preset_list()
			processor.set_preset(0)

		# Select first chain so that preset selection is on "Upper" manual
		chain_manager.set_active_chain_by_id(self.processors[0].chain_id)
		self.state_manager.end_busy("setBfree")

	def generate_config_file(self, chans):
		midi_chans = chans.copy()
		# Get user's config
		try:
			with open(self.config_my_fpath, 'r') as my_cfg_file:
				my_cfg_data = my_cfg_file.read()
		except:
			my_cfg_data = ""
		
		# Dummy MIDI channel to use for disabled manuals
		for disabled_midi_chan in range(15, -1, -1):
			if disabled_midi_chan not in midi_chans:
				break
		for i in range(len(midi_chans)):
			if midi_chans[i] is None:
				midi_chans[i] = disabled_midi_chan

		# Generate on-the-fly config
		with open(self.config_tpl_fpath, 'r') as cfg_tpl_file:
			cfg_data = cfg_tpl_file.read()
			cfg_data = cfg_data.replace('#OSC.TUNING#', str(int(self.state_manager.fine_tuning_freq)))
			cfg_data = cfg_data.replace('#MIDI.UPPER.CHANNEL#', str(1 + midi_chans[0]))
			cfg_data = cfg_data.replace('#MIDI.LOWER.CHANNEL#', str(1 + midi_chans[1]))
			cfg_data = cfg_data.replace('#MIDI.PEDALS.CHANNEL#', str(1 + midi_chans[2]))
			cfg_data = cfg_data.replace('#TONEWHEEL.CONFIG#', self.tonewheel_config[self.tonewheel_model])
			cfg_data += "\n" + my_cfg_data
			with open(self.config_autogen_fpath, 'w+') as cfg_file:
				cfg_file.write(cfg_data)

	# ---------------------------------------------------------------------------
	# Processor Management
	# ---------------------------------------------------------------------------

	def get_name(self, processor=None):
		res = self.name
		if processor:
			chan_name = self.get_chan_name(processor.midi_chan)
			if chan_name:
				res = res + '/' + chan_name
		return res

	def get_path(self, processor=None):
		path = self.name
		if not self.manuals_config:
			path += "/Manuals"
		elif not self.tonewheel_model:
			path += "/Tonewheel"
		elif processor:
			#chan_name = self.get_chan_name(processor.get_midi_chan())
			#if chan_name:
			#	path = path + '/' + chan_name
			pass
			#path += "/" + self.tonewheel_model
		return path

	def remove_processor(self, processor):
		try:
			if processor.bank_name == "Upper":
				self.midi_chans[0] = None
			elif processor.bank_name == "Lower":
				self.midi_chans[1] = None
				self.manuals_config[4][0] = False
			elif processor.bank_name == "Pedals":
				self.midi_chans[2] = None
				self.manuals_config[4][1] = False
			self.chan_names.pop(str(processor.midi_chan))
		except:
			pass
		super().remove_processor(processor)

	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	def get_chan_name(self, chan):
		try:
			return self.chan_names[str(chan)]
		except:
			return None

	# ----------------------------------------------------------------------------
	# Bank Management
	# ----------------------------------------------------------------------------

	def get_bank_list(self, processor):
		if not self.manuals_config:
			free_chans = len(self.state_manager.chain_manager.get_free_midi_chans())
			if free_chans > 1:
				return self.bank_manuals_list
			elif free_chans > 0:
				return self.bank_manuals_list[:3]
			else:
				self.manuals_config = self.bank_manuals_list[0]
				return self.bank_twmodels_list
		elif not self.tonewheel_model:
			return self.bank_twmodels_list
		else:
			#self.show_favs_bank = True
			if processor.bank_name == "Upper":
				return [[self.base_dir + "/pgm-banks/upper/most_popular.pgm", 0, "Upper", "_"]]
			elif processor.bank_name == "Lower":
				return [[self.base_dir + "/pgm-banks/lower/lower_voices.pgm", 0, "Lower", "_"]]
			elif processor.bank_name == "Pedals":
				return [[self.base_dir + "/pgm-banks/pedals/pedals.pgm", 0, "Pedals", "_"]]

		#return self.get_filelist(self.get_bank_dir(processor), "pgm")

	def set_bank(self, processor, bank):
		if not self.manuals_config:
			self.manuals_config = bank
			self.processors[0].reset_bank()
			return None

		elif not self.tonewheel_model:
			self.tonewheel_model = bank[0]

		if not self.proc:
			self.start()

		return True

	# ----------------------------------------------------------------------------
	# Preset Managament
	# ----------------------------------------------------------------------------

	def get_preset_list(self, bank):
		logging.debug(f"Preset List for Bank {bank[0]}")
		return self.load_program_list(bank[0])

	def set_preset(self, processor, preset, preload=False):
		if super().set_preset(processor, preset):
			self.update_controller_values(processor, preset)
			return True
		else:
			return False

	def cmp_presets(self, preset1, preset2):
		try:
			if preset1[1][2] == preset2[1][2]:
				return True
			else:
				return False
		except:
			return False

	# ----------------------------------------------------------------------------
	# Controller Managament
	# ----------------------------------------------------------------------------

	def update_controller_values(self, processor, preset):
		#Get values from preset params and set them into controllers
		for param, v in preset[3].items():
			try:
				zcsymbol=self._param2zcsymbol[param]
			except Exception as e:
				logging.debug(f"No controller for param {param}")
				continue

			try:
				zctrl=processor.controllers_dict[zcsymbol]

				if zctrl.symbol == 'rotary speed':
					if v == 'tremolo':
						v = 'fast'
					elif v == 'chorale':
						v = 'slow'
					else:
						v = 'off'

				#logging.debug(f"Updating controller '{zctrl.symbol}' ({zctrl.name}) => {zctrl.value}")
				zctrl.set_value(v, True)

				#Refresh GUI controller in screen when needed ...
				#if self.state_manager.current_screen == 'control':
				#TODO:	self.state_manager.screens['control'].set_controller_value(zctrl)

			except Exception as e:
				logging.debug(f"Can't update controller '{zcsymbol}' => {e}")

	def midi_zctrl_change(self, zctrl, val):
		try:
			if val != zctrl.get_value():
				zctrl.set_value(val)
				#logging.debug(f"MIDI CC {zctrl.midi_cc} -> '{zctrl.name}' = {val}")

		except Exception as e:
			logging.debug(e)

	# ----------------------------------------------------------------------------
	# Specific functionality
	# ----------------------------------------------------------------------------

	def get_bank_dir(self, processor):
		bank_dir = self.base_dir+"/pgm-banks"
		chan_name = self.get_chan_name(processor.get_midi_chan())
		if chan_name:
			bank_dir = bank_dir + '/' + chan_name
		return bank_dir

	def load_program_list(self, fpath):
		try:
			with open(fpath) as f:
				pgm_list = []
				lines = f.readlines()
				ptrn1 = re.compile("^([\d]+)[\s]*\{[\s]*name\=\"([^\"]+)\"")
				ptrn2 = re.compile("[\s]*[\{\}\,]+[\s]*")
				i=0
				for line in lines:
					# Test with first pattern
					m = ptrn1.match(line)
					if not m: continue

					# Get line parts...
					fragments = ptrn2.split(line)

					params = {}
					try:
						# Get program MIDI number
						prg = int(fragments[0]) - 1
						if prg >= 0:
							# Get params from line parts ...
							for frg in fragments[1:]:
								parts = frg.split('=')
								try:
									params[parts[0].lower()] = parts[1].strip("\"\'")
								except:
									pass

							# Extract program name
							title = params['name']
							del params['name']

							# Complete program params ...
							#if 'vibrato' in params:
							#	params['vibratoupper'] = 'on'
							#	params['vibratorouting'] = 'upper'

							# Extract drawbars values
							if 'drawbars' in params:
								j = 1
								for v in params['drawbars']:
									if v in ['0','1','2','3','4','5','6','7','8']:
										params['drawbar_'+str(j)]=v
										j = j + 1
								del params['drawbars']

							# Add program to list
							pgm_list.append([i, [0, 0, prg], title, params])
							i = i + 1
					except:
						#print("Ignored line: %s" % line)
						pass

		except Exception as err:
			pgm_list = None
			logging.error("Getting program info from %s => %s" % (fpath, err))

		return pgm_list

	# ---------------------------------------------------------------------------
	# Extended Config
	# ---------------------------------------------------------------------------

	def get_extended_config(self):
		engine_state = { 
			'manuals_config': self.manuals_config,
			'tonewheel_model': self.tonewheel_model
		}
		return engine_state

	def set_extended_config(self, engine_state):
		try:
			self.manuals_config = engine_state['manuals_config']
			self.tonewheel_model = engine_state['tonewheel_model']
			for i, processor in enumerate(self.processors):
				if i:
					self.state_manager.chain_manager.get_chain(processor.chain_id).mixer_chan = None

		except Exception as e:
			logging.error(f"Can't setup extended config => {e}")

# -------------------------------------------------------------------------------
