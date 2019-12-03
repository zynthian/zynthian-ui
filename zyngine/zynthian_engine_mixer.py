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
		zctrls=OrderedDict()
		ctrl_name = None
		ctrl_symbol = None
		ctrl_type = None
		ctrl_value = 50
		ctrl_maxval = 100
		ctrl_minval = 0

		logging.debug("MIXER CTRL LIST: ".format(self.ctrl_list))

		try:
			for byteLine in check_output("amixer -M -c {}".format(self.device_name), shell=True).splitlines():
				line = byteLine.decode("utf-8")

				if line.find('Simple mixer control')>=0:
					if ctrl_name and ctrl_type and (not self.ctrl_list or ctrl_symbol in self.ctrl_list):
						zctrls[ctrl_symbol]=zynthian_controller(self, ctrl_symbol, ctrl_name, {
							'graph_path': "'{}' {}".format(ctrl_symbol, ctrl_type),
							'value': ctrl_value,
							'value_default': 50,
							'value_min': ctrl_minval,
							'value_max': ctrl_maxval,
							'is_toggle': False,
							'is_integer': True
						})

					m = re.match("Simple mixer control '(.*?)'.*", line, re.M | re.I)
					if m:
						ctrl_name = m.group(1).strip()
						ctrl_symbol = ctrl_name.replace(' ', '_')
					else:
						ctrl_name = None
						ctrl_symbol = None

					ctrl_type = None
					ctrl_value = 50


				elif line.find('Playback channels:')>=0:
					ctrl_type = "Playback"
					ctrl_name = "Volume"

				elif line.find('Capture channels:')>=0:
					ctrl_type = "Capture"
					ctrl_name = "Input Gain"

				else:
					m = re.match(".*(Playback|Capture).*\[(\d*)%\].*", line, re.M | re.I)
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

			if ctrl_name and ctrl_type and (not self.ctrl_list or ctrl_symbol in self.ctrl_list):
				zctrls[ctrl_symbol]=zynthian_controller(self, ctrl_symbol, ctrl_name, {
					'graph_path': "'{}' {}".format(ctrl_symbol, ctrl_type),
					'value': ctrl_value,
					'value_default': 50,
					'value_min': ctrl_minval,
					'value_max': ctrl_maxval,
					'is_toggle': False,
					'is_integer': True
				})

		except Exception as err:
			logging.error(err)

		self.generate_ctrl_screens(zctrls)

		return zctrls


	def send_controller_value(self, zctrl):
		try:
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
