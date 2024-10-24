# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_midi_control)
#
# zynthian_engine implementation for a MIDI controller for external devices
#
# Copyright (C) 2015-2024 Fernando Moyano <jofemodo@zynthian.org>
# *******************************************************************************
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

import logging

import zynautoconnect
from . import zynthian_engine
from zyncoder.zyncore import lib_zyncore

# ------------------------------------------------------------------------------
# MIDI Controller Engine Class
# ------------------------------------------------------------------------------


class zynthian_engine_midi_control(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Controllers & Screens
	# ---------------------------------------------------------------------------

	_ctrls = [
		['00 bank change', 0, 0],
		['01 modulation wheel', 1, 0],
		['02 breath', 2, 127],
		['03 undefined', 3, 0],

		['04 foot controller', 4, 127],
		['05 portamento time', 5, 0],
		['06 NRPN', 5, 0],
		['07 volume', 7, 96],

		['08 balance', 8, 64],
		['09 undefined', 9, 0],
		['10 pan', 10, 64],
		['11 expression', 11, 127],

		['12 effect 1', 12, 0],
		['13 effect 2', 13, 0],
		['14 undefined', 14, 0],
		['15 undefined', 15, 0],

		['16 undefined', 16, 0],
		['17 undefined', 17, 0],
		['18 undefined', 18, 0],
		['19 undefined', 19, 0],

		['20 undefined', 20, 0],
		['21 undefined', 21, 0],
		['22 undefined', 22, 0],
		['23 undefined', 23, 0],

		['24 undefined', 24, 0],
		['25 undefined', 25, 0],
		['26 undefined', 26, 0],
		['27 undefined', 27, 0],

		['28 undefined', 28, 0],
		['29 undefined', 29, 0],
		['30 undefined', 30, 0],
		['31 undefined', 31, 0],

		['32 LSB', 32, 0],
		['33 LSB', 33, 0],
		['34 LSB', 34, 0],
		['35 LSB', 35, 0],

		['36 LSB', 36, 0],
		['37 LSB', 37, 0],
		['38 LSB', 38, 0],
		['39 LSB', 39, 0],

		['40 LSB', 40, 0],
		['41 LSB', 41, 0],
		['42 LSB', 42, 0],
		['43 LSB', 43, 0],

		['44 LSB', 44, 0],
		['45 LSB', 45, 0],
		['46 LSB', 46, 0],
		['47 LSB', 47, 0],

		['48 LSB', 48, 0],
		['49 LSB', 49, 0],
		['50 LSB', 50, 0],
		['51 LSB', 51, 0],

		['52 LSB', 52, 0],
		['53 LSB', 53, 0],
		['54 LSB', 54, 0],
		['55 LSB', 55, 0],

		['56 LSB', 56, 0],
		['57 LSB', 57, 0],
		['58 LSB', 58, 0],
		['59 LSB', 59, 0],

		['60 LSB', 60, 0],
		['61 LSB', 61, 0],
		['62 LSB', 62, 0],
		['63 LSB', 63, 0],

		#['64 sustain pedal', 64, 0],
		['64 sustain', 64, 'off', ['off', 'on']],
		['65 portamento', 65, 'off', ['off', 'on']],
		['66 sostenuto', 66, 'off', ['off', 'on']],
		['67 soft pedal', 67, 'off', ['off', 'on']],

		['68 legato', 68, 'off', ['off', 'on']],
		['69 hold2', 69, 0],
		['70 sound variation', 70, 0],
		['71 VCF resonance', 71, 0],

		['72 VCA release', 72, 0],
		['73 VCA attack', 73, 0],
		['74 VCF cutoff', 74, 0],
		['75 sound controller', 75, 0],

		['76 sound controller', 76, 0],
		['77 sound controller', 77, 0],
		['78 sound controller', 78, 0],
		['79 sound controller', 79, 0],

		['80 generic switch', 80, 0],
		['81 generic switch', 81, 0],
		['82 generic switch', 82, 0],
		['83 generic switch', 83, 0],

		['84 portamento amount', 84, 0],
		['85 undefined', 85, 0],
		['86 undefined', 86, 0],
		['87 undefined', 87, 0],

		['88 undefined', 88, 0],
		['89 undefined', 89, 0],
		['90 undefined', 90, 0],
		['91 reverb', 91, 0],

		['92 tremolo', 92, 0],
		['93 chorus', 93, 0],
		['94 detune', 94, 0],
		['95 phaser', 95, 0],

		['96 undefined', 96, 0],
		['97 undefined', 97, 0],
		['98 undefined', 98, 0],
		['99 undefined', 99, 0],

		['100 undefined', 100, 0],
		['101 undefined', 101, 0],
		['102 undefined', 102, 0],
		['103 undefined', 103, 0],

		['104 undefined', 104, 0],
		['105 undefined', 105, 0],
		['106 undefined', 106, 0],
		['107 undefined', 107, 0],

		['108 undefined', 108, 0],
		['109 undefined', 109, 0],
		['110 undefined', 110, 0],
		['111 undefined', 111, 0],

		['112 undefined', 112, 0],
		['113 undefined', 113, 0],
		['114 undefined', 114, 0],
		['115 undefined', 115, 0],

		['116 undefined', 116, 0],
		['117 undefined', 117, 0],
		['118 undefined', 118, 0],
		['119 undefined', 119, 0]
	]
	_ctrl_screens = []

	# ----------------------------------------------------------------------------
	# Config variables
	# ----------------------------------------------------------------------------

	# ----------------------------------------------------------------------------
	# Initialization
	# ----------------------------------------------------------------------------

	def __init__(self, state_manager=None):
		super().__init__(state_manager)

		self.name = "MIDI Control"
		self.nickname = "MC"
		self.jackname = "midicontrol"

		self.base_command = None
		self.generate_ctrl_screens()
		self.reset()

	# ---------------------------------------------------------------------------
	# Processor Management
	# ---------------------------------------------------------------------------

	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	# ----------------------------------------------------------------------------
	# Bank Managament
	# ----------------------------------------------------------------------------

	def get_bank_list(self, processor=None):
		bank_list = []
		bank_list.append([-1, None, "None", None, "None"])
		for i in range(128):
			bank_list.append([i, None, f"Bank {i}", None, f"Bank {i}"])
		return bank_list

	def set_bank(self, processor, bank):
		return True

	# ----------------------------------------------------------------------------
	# Preset Managament
	# ----------------------------------------------------------------------------

	def get_preset_list(self, bank):
		preset_list = []
		preset_list.append([-1, None, "None", None, "None"])
		for i in range(128):
			preset_list.append([[bank[0], i], None, f"Preset {i}", None, f"Preset {i}"])
		return preset_list

	def set_preset(self, processor, preset, preload=False):
		if isinstance(preset[0], list):
			# If no chain's MIDI channel, defaults to MIDI channel 1
			if 0 <= processor.midi_chan < 16:
				midi_chan = processor.midi_chan
			else:
				midi_chan = 1
			for device_name in processor.chain.get_midi_out():
				try:
					idev = zynautoconnect.devices_out_name.index(device_name)
					if preset[0][0] is not None and 0 <= preset[0][0] <= 127:
						lib_zyncore.dev_send_ccontrol_change(idev, midi_chan, 0, preset[0][0])
					if preset[0][1] is not None and 0 <= preset[0][1] <= 127:
						lib_zyncore.dev_send_program_change(idev, midi_chan, preset[0][1])
				except:
					logging.warning(f"Can't send MIDI to {device_name}")
			return True
		else:
			return False

	def cmp_presets(self, preset1, preset2):
		try:
			if preset1[0] == preset2[0]:
				return True
			else:
				return False
		except:
			return False

	# ----------------------------------------------------------------------------
	# Controllers Managament
	# ----------------------------------------------------------------------------

	def generate_ctrl_screens(self):
		if self._ctrl_screens is None:
			self._ctrl_screens = []
		i = 0
		while i < len(self._ctrls):
			title = f"CC#{i:02} - CC#{i+3:02}"
			ctrl_set = []
			for j in range(4):
				ctrl_set.append(self._ctrls[i + j][0])
			self._ctrl_screens.append([title, ctrl_set])
			i += 4

	def send_controller_value(self, zctrl):
		if 0 <= zctrl.midi_chan < 16:
			midi_chan = zctrl.midi_chan
		else:
			midi_chan = 1
		for device_name in zctrl.processor.chain.get_midi_out():
			try:
				idev = zynautoconnect.devices_out_name.index(device_name)
				lib_zyncore.dev_send_ccontrol_change(idev, midi_chan, zctrl.midi_cc, zctrl.value)
			except:
				logging.warning(f"Can't send MIDI CC to {device_name}")

# -----------------------------------------------------------------------------
