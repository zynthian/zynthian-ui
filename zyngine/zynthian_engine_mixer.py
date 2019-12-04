# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_mixer)
#
# zynthian_engine implementation for Alsa Mixer
#
# Copyright (C) 2015-2019 Fernando Moyano <jofemodo@zynthian.org>
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
import re
import logging
from subprocess import check_output
from collections import OrderedDict

from . import zynthian_engine
from . import zynthian_controller

#------------------------------------------------------------------------------
# Mixer Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_mixer(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Controllers & Screens
	# ---------------------------------------------------------------------------

	_ctrl_screens = []

	#----------------------------------------------------------------------------
	# Config variables
	#----------------------------------------------------------------------------

	#----------------------------------------------------------------------------
	# Initialization
	#----------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__(zyngui)

		self.type = "Mixer"
		self.name = "MIXER"
		self.nickname = "MX"

		self.audio_out = []
		self.options= {
			'clone': False,
			'transpose': False,
			'audio_route': False,
			'midi_chan': False
		}

		self.get_soundcard_config()

	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------

	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	#----------------------------------------------------------------------------
	# Bank Managament
	#----------------------------------------------------------------------------

	def get_bank_list(self, layer=None):
		return [("", None, "", None)]


	def set_bank(self, layer, bank):
		return True

	#----------------------------------------------------------------------------
	# Preset Managament
	#----------------------------------------------------------------------------

	def get_preset_list(self, bank):
		return [("", None, "", None)]


	def set_preset(self, layer, preset, preload=False):
		return True


	def cmp_presets(self, preset1, preset2):
		return True

	#----------------------------------------------------------------------------
	# Controllers Managament
	#----------------------------------------------------------------------------

	def get_controllers_dict(self, layer):
		zctrls = {}

		logging.debug("MIXER CTRL LIST: {}".format(self.ctrl_list))

		try:
			ctrls = check_output("amixer -M -c {}".format(self.device_name), shell=True).decode("utf-8").split("Simple mixer control ")
			for ctrl in ctrls:
				lines = ctrl.splitlines()
				if len(lines)==0:
					continue

				m = re.match("'(.*?)'.*", lines[0], re.M | re.I)
				if m:
					ctrl_name = m.group(1).strip()
					ctrl_symbol = ctrl_name.replace(' ', '_')
				else:
					ctrl_name = None
					ctrl_symbol = None
	
				ctrl_type = None
				ctrl_chans = None
				ctrl_items = None
				ctrl_item0 = None
				ctrl_value = 50
				ctrl_maxval = 100
				ctrl_minval = 0

				logging.debug("MIXER CONTROL => {}\n{}".format(ctrl_name, ctrl))
				for line in lines[1:]:
					try:
						key, value = line.strip().split(": ",1)
						logging.debug("  {} => {}".format(key,value))
					except:
						continue

					if key=='Playback channels':
						ctrl_type = "Playback"
						#ctrl_name = "Volume"
						ctrl_chans = value.strip().split(' - ')

					elif key=='Capture channels':
						ctrl_type = "Capture"
						#ctrl_name = "Input Gain"
						ctrl_chans = value.strip().split(' - ')

					elif key=='Capabilities' and value=='enum':
						ctrl_type = "Selector"

					elif key=='Items':
						ctrl_items = value[1:-1].split("' '")

					elif key=='Item0':
						ctrl_item0 = value[1:-1]

					elif ctrl_chans and key in ctrl_chans:
						m = re.match(".*(Playback|Capture).*\[(\d*)%\].*", value, re.M | re.I)
						if m:
							ctrl_value = int(m.group(2))
							if m.group(1) == 'Capture':
								ctrl_type = "Capture"
							else:
								ctrl_type = "Playback"
						else:
							m = re.match(".*\[(\d*)%\].*", line, re.M | re.I)
							if m:
								ctrl_value = int(m.group(1))

				if ctrl_symbol and ctrl_type and (not self.ctrl_list or ctrl_name in self.ctrl_list):
					if ctrl_type=='Selector' and len(ctrl_items)>1:
						logging.debug("ADDING ZCTRL SELECTOR: {} => {} ({})".format(ctrl_symbol, ctrl_item0, ctrl_value))
						zctrls[ctrl_symbol]=zynthian_controller(self, ctrl_symbol, ctrl_name, {
							'graph_path': "'{}'".format(ctrl_name),
							'labels': ctrl_items,
							'ticks': list(range(len(ctrl_items))),
							'value': ctrl_item0,
							'value_min': 0,
							'value_max': len(ctrl_items)-1,
							'is_toggle': False,
							'is_integer': True
						})
					elif ctrl_type in ("Playback" ,"Capture"):
						logging.debug("ADDING ZCTRL LEVEL: {} => {}".format(ctrl_symbol, ctrl_value))
						zctrls[ctrl_symbol]=zynthian_controller(self, ctrl_symbol, ctrl_name, {
							'graph_path': "'{}' {}".format(ctrl_name, ctrl_type),
							'value': ctrl_value,
							'value_default': 50,
							'value_min': ctrl_minval,
							'value_max': ctrl_maxval,
							'is_toggle': False,
							'is_integer': True
						})

		except Exception as err:
			logging.error(err)

		# Sort zctrls to match the configured mixer control list
		sorted_zctrls = OrderedDict()
		for ctrl_name in self.ctrl_list:
			ctrl_symbol = ctrl_name.replace(' ', '_')
			sorted_zctrls[ctrl_symbol] = zctrls[ctrl_symbol]

		# Generate control screens
		self.generate_ctrl_screens(sorted_zctrls)

		return sorted_zctrls


	def send_controller_value(self, zctrl):
		try:
			if zctrl.labels:
				amixer_command = "amixer -M -c {} set {} '{}'".format(self.device_name, zctrl.graph_path, zctrl.get_value2label())
			else:
				amixer_command = "amixer -M -c {} set {} {}% unmute".format(self.device_name, zctrl.graph_path, zctrl.value)

			logging.debug(amixer_command)
			check_output(amixer_command, shell=True)

		except Exception as err:
			logging.error(err)


	# ---------------------------------------------------------------------------
	# Layer "Path" String
	# ---------------------------------------------------------------------------


	def get_path(self, layer):
		return self.name


	#--------------------------------------------------------------------------
	# Special
	#--------------------------------------------------------------------------

	def get_soundcard_config(self):
		try:
			jack_opts = os.environ.get('JACKD_OPTIONS')
			res = re.compile(r" hw:([^\s]+) ").search(jack_opts)
			self.device_name = res.group(1)
		except:
			self.device_name = "0"

		try:
			self.ctrl_list = os.environ.get('SOUNDCARD_MIXER').split(',')
		except:
			self.ctrl_list = None


#******************************************************************************
