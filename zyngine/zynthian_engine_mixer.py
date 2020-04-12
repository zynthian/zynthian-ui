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
import shlex
import logging
import threading
from time import sleep
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
	# ZynAPI variables
	#----------------------------------------------------------------------------

	zynapi_instance = None

	#----------------------------------------------------------------------------
	# Initialization
	#----------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__(zyngui)

		self.type = "Mixer"
		self.name = "ALSA Mixer"
		self.nickname = "MX"

		self.audio_out = []
		self.options= {
			'clone': False,
			'transpose': False,
			'audio_route': False,
			'midi_chan': False,
			'indelible' : True
		}

		self.zctrls = None
		self.sender_poll_enabled = False
		self.learned_cc = [[None for c in range(128)] for chan in range(16)]
		self.learned_zctrls = {}

		self.get_soundcard_config()


		def stop(self):
			self.stop_sender_poll()
			super().stop()


	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------

	def add_layer(self, layer):
		layer.listen_midi_cc = False
		super().add_layer(layer)

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

	def get_controllers_dict(self, layer, ctrl_list=None):
		zctrls = OrderedDict()

		if ctrl_list=="*":
			ctrl_list = None
		elif ctrl_list is None:
			ctrl_list = self.ctrl_list

		logging.debug("MIXER CTRL LIST: {}".format(ctrl_list))

		self.stop_sender_poll()

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
				ctrl_caps = None
				ctrl_pchans = []
				ctrl_cchans = []
				ctrl_items = None
				ctrl_item0 = None
				ctrl_ticks = None
				ctrl_limits = None
				ctrl_value = 50
				ctrl_maxval = 100
				ctrl_minval = 0

				#logging.debug("MIXER CONTROL => {}\n{}".format(ctrl_name, ctrl))
				for line in lines[1:]:
					try:
						key, value = line.strip().split(": ",1)
						#logging.debug("  {} => {}".format(key,value))
					except:
						continue

					if key=='Capabilities':
						ctrl_caps = value.split(' ')
						if 'enum' in ctrl_caps:
							ctrl_type = "Selector"
						elif 'volume' in ctrl_caps or 'pvolume' in ctrl_caps:
							ctrl_type = "Playback"
						elif 'cvolume' in ctrl_caps:
							ctrl_type = "Capture"
						elif 'pswitch' in ctrl_caps or 'cswitch' in ctrl_caps:
							ctrl_type = "Toggle"
							ctrl_items = ["off", "on"]
							ctrl_ticks = [0, 1]

					elif key=='Playback channels':
						ctrl_pchans = value.strip().split(' - ')

					elif key=='Capture channels':
						ctrl_cchans = value.strip().split(' - ')

					elif key=='Limits':
						m = re.match(".*(\d+) - (\d+).*", value, re.M | re.I)
						if m:
							ctrl_limits = [int(m.group(1)), int(m.group(2))]
							if ctrl_limits[0]==0 and ctrl_limits[1]==1:
								ctrl_type = "VToggle"
								ctrl_items = ["off", "on"]
								ctrl_ticks = [0, 100]

					elif key=='Items':
						ctrl_items = value[1:-1].split("' '")
						ctrl_ticks = list(range(len(ctrl_items)))

					elif key=='Item0':
						ctrl_item0 = value[1:-1]

					elif key in list(set(ctrl_pchans) | set(ctrl_cchans)):
						if ctrl_type=="Toggle":
							m = re.match(".*\[(off|on)\].*", value, re.M | re.I)
							if m:
								ctrl_item0 = m.group(1)
							else:
								ctrl_item0 = "off"
						else:
							m = re.match(".*\[(\d*)%\].*", value, re.M | re.I)
							if m:
								ctrl_value = int(m.group(1))
								if ctrl_type=="VToggle":
									ctrl_item0 = 'on' if (ctrl_value>0) else 'off'

				if ctrl_symbol and ctrl_type and (not ctrl_list or ctrl_name in ctrl_list):
					if ctrl_type in ("Selector", "Toggle", "VToggle") and len(ctrl_items)>1:
						#logging.debug("ADDING ZCTRL SELECTOR: {} => {}".format(ctrl_symbol, ctrl_item0))
						
						zctrl = zynthian_controller(self, ctrl_symbol, ctrl_name, {
							'graph_path': [ctrl_name, ctrl_type],
							'labels': ctrl_items,
							'ticks': ctrl_ticks,
							'value': ctrl_item0,
							'value_min': ctrl_ticks[0],
							'value_max': ctrl_ticks[-1],
							'is_toggle': (ctrl_type=='Toggle'),
							'is_integer': True
						})
					elif ctrl_type in ("Playback" ,"Capture"):
						#logging.debug("ADDING ZCTRL LEVEL: {} => {}".format(ctrl_symbol, ctrl_value))
						zctrl = zynthian_controller(self, ctrl_symbol, ctrl_name, {
							'graph_path': [ctrl_name, ctrl_type],
							'value': ctrl_value,
							'value_min': ctrl_minval,
							'value_max': ctrl_maxval,
							'is_toggle': False,
							'is_integer': True
						})
					else:
						zctrl = None

					zctrl.last_value_sent = None
					zctrls[ctrl_symbol] = zctrl

		except Exception as err:
			logging.error(err)

		# Sort zctrls to match the configured mixer control list
		if ctrl_list and len(ctrl_list)>0:
			sorted_zctrls = OrderedDict()
			for ctrl_name in ctrl_list:
				ctrl_symbol = ctrl_name.replace(' ', '_')
				try:
					sorted_zctrls[ctrl_symbol] = zctrls[ctrl_symbol]
				except:
					pass
		else:
			sorted_zctrls = zctrls

		# Generate control screens
		self.generate_ctrl_screens(sorted_zctrls)

		self.zctrls = sorted_zctrls
		self.start_sender_poll()

		return sorted_zctrls


	def send_controller_value(self, zctrl):
		pass


	def _send_controller_value(self, zctrl):
		try:
			if zctrl.labels:
				if zctrl.graph_path[1]=="VToggle":
					amixer_command = "amixer -M -c {} set '{}' '{}%'".format(self.device_name, zctrl.graph_path[0], zctrl.value)
				else:
					amixer_command = "amixer -M -c {} set '{}' '{}'".format(self.device_name, zctrl.graph_path[0], zctrl.get_value2label())
			else:
				amixer_command = "amixer -M -c {} set '{}' '{}' {}% unmute".format(self.device_name, zctrl.graph_path[0], zctrl.graph_path[1], zctrl.value)

			logging.debug(amixer_command)
			check_output(shlex.split(amixer_command))
			sleep(0.05)

		except Exception as err:
			logging.error(err)


	def start_sender_poll(self):

		def runInThread():
			while self.sender_poll_enabled:
				counter = 0
				if self.zctrls:
					for sym, zctrl in self.zctrls.items():
						if zctrl.last_value_sent != zctrl.value:
							zctrl.last_value_sent = zctrl.value
							self._send_controller_value(zctrl)
							counter += 1

				if counter==0:
					sleep(0.05)

		thread = threading.Thread(target=runInThread, daemon=True)
		thread.start()


	def stop_sender_poll(self):
		self.sender_poll_enabled = True


	#----------------------------------------------------------------------------
	# MIDI learning
	#----------------------------------------------------------------------------

	def init_midi_learn(self, zctrl):
		if zctrl.graph_path:
			logging.info("Learning '{}' ({}) ...".format(zctrl.symbol,zctrl.graph_path))


	def midi_unlearn(self, zctrl):
		if str(zctrl.graph_path) in self.learned_zctrls:
			logging.info("Unlearning '{}' ...".format(zctrl.symbol))
			try:
				self.learned_cc[zctrl.midi_learn_chan][zctrl.midi_learn_cc] = None
				del self.learned_zctrls[str(zctrl.graph_path)]
				return zctrl._unset_midi_learn()
			except Exception as e:
				logging.warning("Can't unlearn => {}".format(e))


	def set_midi_learn(self, zctrl ,chan, cc):
		try:
			# Clean current binding if any ...
			try:
				self.learned_cc[chan][cc].midi_unlearn()
			except:
				pass
			# Add midi learning info
			self.learned_zctrls[str(zctrl.graph_path)] = zctrl
			self.learned_cc[chan][cc] = zctrl
			return zctrl._set_midi_learn(chan, cc)
		except Exception as e:
			logging.error("Can't learn {} => {}".format(zctrl.symbol, e))


	def reset_midi_learn(self):
		logging.info("Reset MIDI-learn ...")
		self.learned_zctrls = {}
		self.learned_cc = [[None for chan in range(16)] for cc in range(128)]


	def cb_midi_learn(self, zctrl, chan, cc):
		return self.set_midi_learn(zctrl, chan, cc)

	#----------------------------------------------------------------------------
	# MIDI CC processing
	#----------------------------------------------------------------------------

	def midi_control_change(self, chan, ccnum, val):
		if self.zyngui.is_single_active_channel():
			for ch in range(0,16):
				try:
					self.learned_cc[ch][ccnum].midi_control_change(val)
				except:
					pass
		else:
			try:
				self.learned_cc[chan][ccnum].midi_control_change(val)
			except:
				pass


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
			self.ctrl_list = list(filter(str.strip, os.environ.get('SOUNDCARD_MIXER').split(',')))
		except:
			self.ctrl_list = None


	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

	@classmethod
	def init_zynapi_instance(cls):
		if not cls.zynapi_instance:
			cls.zynapi_instance = cls(None)
		else:
			logging.debug("\n\n********** REUSING INSTANCE ***********")


	@classmethod
	def refresh_zynapi_instance(cls):
		if cls.zynapi_instance:
			cls.zynapi_instance.stop()
			cls.zynapi_instance = cls(None)


	@classmethod
	def zynapi_get_controllers(cls, ctrl_list="*"):
		return cls.zynapi_instance.get_controllers_dict(None, ctrl_list)


#******************************************************************************
