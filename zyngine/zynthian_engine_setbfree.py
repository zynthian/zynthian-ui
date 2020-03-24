# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_setbfree)
# 
# zynthian_engine implementation for setBfree Hammond Emulator
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

import re
import logging
import pexpect

from . import zynthian_engine

#------------------------------------------------------------------------------
# setBfree Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_setbfree(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Banks
	# ---------------------------------------------------------------------------

	bank_manuals_list = [
		['Upper', 0, 'Upper', '_', [False, False, 59]],
		['Lower + Upper', 1, 'Lower + Upper', '_', [True, False, 59]],
		['Pedals + Upper', 2, 'Pedals + Upper', '_', [False, True, 59]],
		['Pedals + Lower + Upper', 3, 'Pedals + Lower + Upper', '_', [True, True, 59]],
		['Split: Lower + Upper', 4, 'Split Lower + Upper', '_', [True, False, 56]],
		['Split: Pedals + Upper', 5, 'Split Pedals + Upper', '_', [False, True, 58]],
		['Split: Pedals + Lower + Upper', 6, 'Split Pedals + Lower + Upper', '_', [True, True, 57]]
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

	drawbar_values = [ ['0','1','2','3','4','5','6','7','8'], [127,119,103,87,71,55,39,23,7] ]

	# MIDI Controllers
	_ctrls = [
		['volume',7,96,127],
#		['swellpedal 2',11,96],
		['reverb',91,4,127],
		['convol. mix',94,64,127],

		['rotary toggle',64,'off','off|on'],
#		['rotary speed',1,64,127],
		['rotary speed',1,'off','slow|off|fast'],
#		['rotary speed',1,'off',[['slow','off','fast'],[0,43,86]]],
#		['rotary select',67,0,127],
#		['rotary select',67,'off/off','off/off|slow/off|fast/off|off/slow|slow/slow|fast/slow|off/fast|slow/fast|fast/fast'],
		['rotary select',67,'off/off',[['off/off','slow/off','fast/off','off/slow','slow/slow','fast/slow','off/fast','slow/fast','fast/fast'],[0,15,30,45,60,75,90,105,120]]],

		['DB 16',70,'8',drawbar_values],
		['DB 5 1/3',71,'8',drawbar_values],
		['DB 8',72,'8',drawbar_values],
		['DB 4',73,'0',drawbar_values],
		['DB 2 2/3',74,'0',drawbar_values],
		['DB 2',75,'0',drawbar_values],
		['DB 1 3/5',76,'0',drawbar_values],
		['DB 1 1/3',77,'0',drawbar_values],
		['DB 1',78,'0',drawbar_values],

		['vibrato upper',31,'off','off|on'],
		['vibrato lower',30,'off','off|on'],
		['vibrato routing',95,'off','off|lower|upper|both'],
		#['vibrato selector',92,'c3','v1|v2|v3|c1|c2|c3'],
		['vibrato selector',92,'c3',[['v1','v2','v3','c1','c2','c3'],[0,23,46,69,92,115]]],

		#['percussion',66,'off','off|on'],
		['percussion',80,'off','off|on'],
		['percussion volume',81,'soft','soft|hard'],
		['percussion decay',82,'slow','slow|fast'],
		['percussion harmonic',83,'3rd','2nd|3rd'],

		['overdrive',65,'off','off|on'],
		['overdrive character',93,64,127],
		['overdrive inputgain',21,64,127],
		['overdrive outputgain',22,64,127]
	]

	# Controller Screens
	_ctrl_screens = [
		['main',['volume','percussion','rotary speed','vibrato routing']],
		['drawbars low',['volume','DB 16','DB 5 1/3','DB 8']],
		['drawbars medium',['volume','DB 4','DB 2 2/3','DB 2']],
		['drawbars high',['volume','DB 1 3/5','DB 1 1/3','DB 1']],
		['rotary',['rotary toggle','rotary select','rotary speed','convol. mix']],
		['vibrato',['vibrato upper','vibrato lower','vibrato routing','vibrato selector']],
		['percussion',['percussion','percussion decay','percussion harmonic','percussion volume']],
		['overdrive',['overdrive','overdrive character','overdrive inputgain','overdrive outputgain']],
		['reverb',['volume','convol. mix','reverb']],
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

	#----------------------------------------------------------------------------
	# Config variables
	#----------------------------------------------------------------------------

	base_dir = zynthian_engine.data_dir + "/setbfree"
	presets_fpath = base_dir + "/pgm/all.pgm"
	config_tpl_fpath = base_dir + "/cfg/zynthian.cfg.tpl"
	config_my_fpath = zynthian_engine.config_dir + "/setbfree/zynthian.cfg"
	config_autogen_fpath = zynthian_engine.config_dir + "/setbfree/.autogen.cfg"

	#----------------------------------------------------------------------------
	# Initialization
	#----------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__(zyngui)
		self.name = "setBfree"
		self.nickname = "BF"
		self.jackname = "setBfree"

		self.options['midi_chan']=False

		self.manuals_config = None
		self.tonewheel_model = None

		#Process command ...
		if self.config_remote_display():
			self.command = "/usr/local/bin/setBfree -p \"{}\" -c \"{}\"".format(self.presets_fpath, self.config_autogen_fpath)
		else:
			self.command = "/usr/local/bin/setBfree -p \"{}\" -c \"{}\"".format(self.presets_fpath, self.config_autogen_fpath)

		self.command_prompt = "\nAll systems go."

		self.reset()


	def generate_config_file(self, midi_chans):
		# Get user's config
		try:
			with open(self.config_my_fpath, 'r') as my_cfg_file:
				my_cfg_data=my_cfg_file.read()
		except:
			my_cfg_data=""

		# Generate on-the-fly config
		with open(self.config_tpl_fpath, 'r') as cfg_tpl_file:
			cfg_data = cfg_tpl_file.read()
			cfg_data = cfg_data.replace('#OSC.TUNING#', str(self.zyngui.fine_tuning_freq))
			cfg_data = cfg_data.replace('#MIDI.UPPER.CHANNEL#', str(1 + midi_chans[0]))
			cfg_data = cfg_data.replace('#MIDI.LOWER.CHANNEL#', str(1 + midi_chans[1]))
			cfg_data = cfg_data.replace('#MIDI.PEDALS.CHANNEL#', str(1 + midi_chans[2]))
			cfg_data = cfg_data.replace('#TONEWHEEL.CONFIG#', self.tonewheel_config[self.tonewheel_model])
			cfg_data += "\n" + my_cfg_data
			with open(self.config_autogen_fpath, 'w+') as cfg_file:
				cfg_file.write(cfg_data)

	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------

	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	#----------------------------------------------------------------------------
	# Bank Managament
	#----------------------------------------------------------------------------

	def get_bank_list(self, layer):
		if not self.manuals_config:
			return self.bank_manuals_list
		elif not self.tonewheel_model:
			return self.bank_twmodels_list
		else:
			if layer.bank_name == "Upper":
				return [[self.base_dir + "/pgm-banks/upper/most_popular.pgm",0, "Upper", "_"]]
			elif layer.bank_name == "Lower":
				return [[self.base_dir + "/pgm-banks/lower/lower_voices.pgm",0, "Lower", "_"]]
			elif layer.bank_name == "Pedals":
				return [[self.base_dir + "/pgm-banks/pedals/pedals.pgm",0, "Pedals", "_"]]

		#return self.get_filelist(self.get_bank_dir(layer),"pgm")


	def set_bank(self, layer, bank):
		if not self.manuals_config:
			self.manuals_config = bank
			self.layers[0].load_bank_list()
			self.layers[0].reset_bank()
			return False

		elif not self.tonewheel_model:
			self.tonewheel_model = bank[0]

		if not self.proc:
			midi_chans = [self.layers[0].get_midi_chan(), 15, 15]
			free_chans = self.zyngui.screens['layer'].get_free_midi_chans()

			logging.info("Upper Layer in chan {}".format(midi_chans[0]))
			self.layers[0].bank_name = "Upper"
			self.layers[0].load_bank_list()
			self.layers[0].set_bank(0)

			# Extra layers
			if self.manuals_config[4][0]:
				try:
					# Adding Lower Manual Layer
					midi_chans[1] = free_chans.pop(0)
					logging.info("Lower Manual Layer in chan {}".format(midi_chans[1]))
					self.zyngui.screens['layer'].add_layer_midich(midi_chans[1], False)
					self.layers[1].bank_name = "Lower"
					self.layers[1].load_bank_list()
					self.layers[1].set_bank(0)

				except Exception as e:
					logging.error("Lower Manual Layer can't be added! => {}".format(e))

			if self.manuals_config[4][1]:
				try:
					# Adding Pedal Layer
					midi_chans[2] = free_chans.pop(0)
					logging.info("Pedal Layer in chan {}".format(midi_chans[2]))
					self.zyngui.screens['layer'].add_layer_midich(midi_chans[2], False)
					i=len(self.layers)-1
					self.layers[i].bank_name = "Pedals"
					self.layers[i].load_bank_list()
					self.layers[i].set_bank(0)

				except Exception as e:
					logging.error("Pedal Layer can't be added! => {}".format(e))

			# Start engine
			logging.debug("STARTING SETBFREE!!")
			self.generate_config_file(midi_chans)
			self.start()
			self.zyngui.zynautoconnect()

			midi_prog = self.manuals_config[4][2]
			if midi_prog and isinstance(midi_prog, int):
				logging.debug("Loading manuals configuration program: {}".format(midi_prog))
				self.zyngui.zynmidi.set_midi_prg(midi_chans[0], midi_prog)

			#self.zyngui.screens['layer'].fill_list()

			return True

	#----------------------------------------------------------------------------
	# Preset Managament
	#----------------------------------------------------------------------------

	def get_preset_list(self, bank):
		logging.debug("Preset List for Bank {}".format(bank[0]))
		return self.load_program_list(bank[0])


	def set_preset(self, layer, preset, preload=False):
		if super().set_preset(layer,preset):
			self.update_controller_values(layer, preset)
			return True
		else:
			return False


	def cmp_presets(self, preset1, preset2):
		try:
			if preset1[1][2]==preset2[1][2]:
				return True
			else:
				return False
		except:
			return False

	#----------------------------------------------------------------------------
	# Controller Managament
	#----------------------------------------------------------------------------

	def update_controller_values(self, layer, preset):
		#Get values from preset params and set them into controllers
		for param, v in preset[3].items():
			try:
				zcsymbol=self._param2zcsymbol[param]
			except Exception as e:
				logging.debug("No controller for param {}".format(param))
				continue

			try:
				zctrl=layer.controllers_dict[zcsymbol]

				if zctrl.symbol=='rotary speed':
					if v=='tremolo': v='fast'
					elif v=='chorale': v='slow'
					else: v='off'

				#logging.debug("Updating controller '{}' ({}) => {}".format(zctrl.symbol,zctrl.name,zctrl.value))
				zctrl.set_value(v, True)

				#Refresh GUI controller in screen when needed ...
				if self.zyngui.active_screen=='control' and self.zyngui.screens['control'].mode=='control':
					self.zyngui.screens['control'].set_controller_value(zctrl)

			except Exception as e:
				logging.debug("Can't update controller '{}' => {}".format(zcsymbol,e))


	def midi_zctrl_change(self, zctrl, val):
		try:
			if val!=zctrl.get_value():
				zctrl.set_value(val)
				#logging.debug("MIDI CC {} -> '{}' = {}".format(zctrl.midi_cc, zctrl.name, val))

				#Refresh GUI controller in screen when needed ...
				if self.zyngui.active_screen=='control' and self.zyngui.screens['control'].mode=='control':
					self.zyngui.screens['control'].set_controller_value(zctrl)

		except Exception as e:
			logging.debug(e)

	#----------------------------------------------------------------------------
	# Specific functionality
	#----------------------------------------------------------------------------

	def get_chan_name(self, chan):
		try:
			return self.chan_names[chan]
		except:
			return None


	def get_bank_dir(self, layer):
		bank_dir=self.base_dir+"/pgm-banks"
		chan_name=self.get_chan_name(layer.get_midi_chan())
		if chan_name:
			bank_dir=bank_dir+'/'+chan_name
		return bank_dir


	def load_program_list(self,fpath):
		pgm_list=None
		try:
			with open(fpath) as f:
				pgm_list=[]
				lines = f.readlines()
				ptrn1=re.compile("^([\d]+)[\s]*\{[\s]*name\=\"([^\"]+)\"")
				ptrn2=re.compile("[\s]*[\{\}\,]+[\s]*")
				i=0
				for line in lines:
					#Test with first pattern
					m=ptrn1.match(line)
					if not m: continue

					#Get line parts...
					fragments=ptrn2.split(line)

					params={}
					try:
						#Get program MIDI number
						prg=int(fragments[0])-1
						if prg>=0:
							#Get params from line parts ...
							for frg in fragments[1:]:
								parts=frg.split('=')
								try:
									params[parts[0].lower()]=parts[1].strip("\"\'")
								except:
									pass

							#Extract program name
							title=params['name']
							del params['name']

							#Complete program params ...
							#if 'vibrato' in params:
							#	params['vibratoupper']='on'
							#	params['vibratorouting']='upper'

							#Extract drawbars values
							if 'drawbars' in params:
								j=1
								for v in params['drawbars']:
									if v in ['0','1','2','3','4','5','6','7','8']:
										params['drawbar_'+str(j)]=v
										j=j+1
								del params['drawbars']

							#Add program to list
							pgm_list.append([i,[0,0,prg],title,params])
							i=i+1
					except:
						#print("Ignored line: %s" % line)
						pass

		except Exception as err:
			pgm_list=None
			logging.error("Getting program info from %s => %s" % (fpath,err))

		return pgm_list

	# ---------------------------------------------------------------------------
	# Extended Config
	# ---------------------------------------------------------------------------

	def get_extended_config(self):
		xconfig = { 
			'manuals_config': self.manuals_config,
			'tonewheel_model': self.tonewheel_model
		}
		return xconfig


	def set_extended_config(self, xconfig):
		try:
			self.manuals_config = xconfig['manuals_config']
			self.tonewheel_model = xconfig['tonewheel_model']

		except Exception as e:
			logging.error("Can't setup extended config => {}".format(e))

	# ---------------------------------------------------------------------------
	# Layer "Path" String
	# ---------------------------------------------------------------------------

	def get_path(self, layer):
		path = self.nickname
		if not self.manuals_config:
			path += "/Manuals"
		elif not self.tonewheel_model:
			path += "/Tonewheel"
		else:
			path += "/" + self.tonewheel_model
		return path


#******************************************************************************
