#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Mackie Control Protocol"
#
# Copyright (C) 2024 Christopher Matthews <chris@matthewsnet.de>
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

import logging
import os
import shutil
import oyaml as yaml
from pathlib import Path
from collections import OrderedDict
from time import sleep

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore
from zyngine.zynthian_signal_manager import zynsigman
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynmixer


# --------------------------------------------------------------------------
# Makiecontrol - Behringer X-Touch Integration
# --------------------------------------------------------------------------
def load_yaml_config(path, file):
	if not os.path.isfile(file):
		logging.info(f"Yaml config file '{file}' not found, copying default file")
		Path(path).mkdir(parents=True, exist_ok=True)
		config_source = f'{os.environ["ZYNTHIAN_UI_DIR"]}/zyngine/ctrldev/mackiecontrol/mackiecontrol.yaml'
		shutil.copy(config_source, f'{path}', )
		while not os.path.isfile(file):
			sleep(0.1)

	try:
		fh = open(file, "r")
		data = fh.read()
		logging.debug(f"Loading yaml config file '{file}' =>\n{data}")
		return yaml.load(data, Loader=yaml.SafeLoader)
	except Exception as e:
		logging.error(f"Bad formatted yaml in config file '{file}' => {e}")
		return {}


class zynthian_ctrldev_mackiecontrol(zynthian_ctrldev_zynmixer):
	# dev_ids = ["X-Touch IN 1"]
	dev_ids = ["*"]
	midi_chan = 0x0  # zero is the default don't change
	sysex_answer_cb = None
	unroute_from_chains = True
	rec_mode = 0
	shift = False

	mackie_config_path = f"{os.environ['ZYNTHIAN_CONFIG_DIR']}/ctrldev"
	mackie_config_file = f"{mackie_config_path}/mackiecontrol.yaml"
	my_settings = load_yaml_config(mackie_config_path, mackie_config_file)

	device_settings = {
		'number_of_strips': int(my_settings['device_settings']['number_of_strips']),
		'masterfader': bool(my_settings['device_settings']['masterfader']),
		'masterfader_fader_num': int(my_settings['device_settings']['masterfader_fader_num']) -1,
		'xtouch': bool(my_settings['device_settings']['xtouch']),
		'touchsensefaders': bool(my_settings['device_settings']['touchsensefaders'])
	}

	cuia_mappings = my_settings['ccnum_buttons']
	cuia_names = OrderedDict()
	for cuia in sorted(cuia_mappings.keys()):
		if cuia_mappings[cuia]['command'] != 'None':
			command = '_'.join(cuia_mappings[cuia]['command'].split('_')[1:])
			cuia_names[command] = cuia_mappings[cuia]
			cuia_names[command]['num'] = int(cuia)

	# TODO: there must be a better way
	rec_ccnums = []
	solo_ccnums = []
	mute_ccnums = []
	select_ccnums = []
	encoders_press_ccnum = []
	faderstouch_ccnum = []
	encoder_assign_dict_rev = {}
	strip_view_dict_rev = {}
	transport_dict_rev = {}
	# shift_ccnum = 70
	for name in cuia_names.keys():
		if name.startswith('shift'):
			shift_ccnum = cuia_names[name]['num']
		elif name.startswith('rec'):
			rec_ccnums.append(cuia_names[name]['num'])
		elif name.startswith('solo'):
			solo_ccnums.append(cuia_names[name]['num'])
		elif name.startswith('mute'):
			mute_ccnums.append(cuia_names[name]['num'])
		elif name.startswith('select'):
			if name == 'select':
				select_ccnum = cuia_names[name]['num']
			else:
				select_ccnums.append(cuia_names[name]['num'])
		elif name.startswith('encoderpress'):
			encoders_press_ccnum.append(cuia_names[name]['num'])
		elif name.startswith('fadertouch'):
			faderstouch_ccnum.append(cuia_names[name]['num'])
		elif name.startswith('encoderassign'):
			function = name.split('_')[-1]
			encoder_assign_dict_rev[function] = cuia_names[name]['num']
		elif name.startswith('viewassign'):
			function = name.split('_')[-1]
			strip_view_dict_rev[function] = cuia_names[name]['num']
		elif name.startswith('transport'):
			function = name.split('_')[-1]
			transport_dict_rev[function] = cuia_names[name]['num']
		elif name.startswith('globalview'):
			strip_view_dict_rev['global_view'] = cuia_names[name]['num']

	# My globals some perhaps temp and to be reviewed
	ZMOP_DEV0 = 19  # no dev_send_pitchbend_change in zynmidirouter had to use zmop_send_pitchbend_change instead
	if device_settings['touchsensefaders']:
		fader_touch_active = [False, False, False, False, False, False, False, False, False]
	else:
		fader_touch_active = [True, True, True, True, True, True, True, True, True]
	max_fader_value = 16383.0  # I think this is default Mackie
	first_zyn_channel_fader = 0  # To be able to scroll around the channels
	encoder_assign = 'global_view'  # Set as default
	strip_view = 'global_view'  # Set default
	gui_screen = 'audio_mixer'  # Set as default, it's needed to correct an issue when starting  up
	# TODO: add to yaml file
	encoders_ccnum = [16, 17, 18, 19, 20, 21, 22, 23]
	scroll_encoder = 60

	# Function to initialise class
	def __init__(self, state_manager, idev_in, idev_out=None):
		super().__init__(state_manager, idev_in, idev_out)

	def _on_gui_show_screen(self, **kwargs):
		logging.debug(f'got screen change: {kwargs}')
		if 'screen' in kwargs.keys():
			self.gui_screen = kwargs['screen']
		self.refresh()  # I'm using the screen change signal to refresh all channels particularly at the beginning

	def send_syx(self, data='00'):
		msg = bytes.fromhex(f"F0 00 00 66 14 {data} f7")
		lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))

	def delete_lcd_text(self):
		data_top = ['12', '00']
		data_bottom = []
		for i in range(0, 8):
			text_top = ''
			for letter in list(text_top.center(7)):
				hex = letter.encode('utf-8').hex()
				data_top.append(hex)
			text_bottom = ''
			for letter in list(text_bottom.center(7)):
				hex = letter.encode('utf-8').hex()
				data_bottom.append(hex)
		data = data_top + data_bottom
		self.send_syx(data=' '.join(data))

	def update_lcd_text(self, pos, text):
		data = ['12', pos]
		for num in range(7):  # Make sure that only 7 letters are used
			letter = list(text.center(7))[num]
			hex = letter.encode('utf-8').hex()
			data.append(hex)
		self.send_syx(data=' '.join(data))

	def update_top_lcd_text(self, channel, top_text=''):
		pos_top = ['00', '07', '0e', '15', '1c', '23', '2a', '31']
		self.update_lcd_text(pos_top[channel], top_text)

	def gernerate_top_lcd_text(self):
		if self.encoder_assign == 'pan':
			for i in range(self.device_settings['number_of_strips']):
				self.update_top_lcd_text(i, top_text='PAN')
		else:  # "global_view"
			for i in range(self.device_settings['number_of_strips']):
				if i >= 4:
					self.update_top_lcd_text(i, top_text='       ')
				else:
					self.update_top_lcd_text(i, top_text=f'ZYNPOT{i-4}')

	def update_bottom_lcd_text(self, channel, bottom_text=''):
		pos_bottom = ['38', '3f', '46', '4d', '54', '5b', '62', '69']
		self.update_lcd_text(pos_bottom[channel], bottom_text)

	def get_master_chain_audio_channel(self):
		master_chain = self.chain_manager.get_chain(0)
		if master_chain is not None:
			return master_chain.mixer_chan
		else:
			return 255

	# mkc Functions
	def buttonled_on(self, ccnum):
		lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, ccnum, 127)

	def buttonled_off(self, ccnum):
		lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, ccnum, 0)

	def rec(self, id, ccnum, ccval):
		if ccval == 127:
			col = int(id) + self.first_zyn_channel_fader
			if col < len(self.get_ordered_chain_ids_filtered()):
				chain = self.get_chain_by_position(col)
				mixer_chan = chain.mixer_chan
				if mixer_chan is not None:
					self.state_manager.audio_recorder.toggle_arm(mixer_chan)
					# Send LED feedback
					if self.idev_out is not None:
						val = self.state_manager.audio_recorder.is_armed(mixer_chan) * 0x7F
						lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, ccnum, val)

	def solo(self, id, ccnum, ccval):
		if ccval == 127:
			col = int(id) + self.first_zyn_channel_fader
			if col < len(self.get_ordered_chain_ids_filtered()):
				chain = self.get_chain_by_position(col)
				mixer_chan = chain.mixer_chan
				if mixer_chan is not None:
					if self.zynmixer.get_solo(mixer_chan):
						val = 0
					else:
						val = 1
					self.zynmixer.set_solo(mixer_chan, val, True)
					if self.idev_out is not None:
						lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, ccnum, val * 0x7F)
				elif self.idev_out is not None:
					lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, ccnum, 0)

	def mute(self, id, ccnum, ccval):
		if ccval == 127:
			col = int(id) + self.first_zyn_channel_fader
			if col < len(self.get_ordered_chain_ids_filtered()):
				chain = self.get_chain_by_position(col)
				mixer_chan = chain.mixer_chan
				if mixer_chan is not None:
					if self.zynmixer.get_mute(mixer_chan):
						val = 0
					else:
						val = 1
					self.zynmixer.set_mute(mixer_chan, val, True)
					if self.idev_out is not None:
						lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, ccnum, val * 0x7F)
				elif self.idev_out is not None:
					lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, ccnum, 0)

	def select(self, id, ccnum, ccval):
		if ccval == 127:
			col = int(id) + self.first_zyn_channel_fader
			if col < len(self.get_ordered_chain_ids_filtered()):
				chain = self.get_chain_by_position(col)
				self.chain_manager.set_active_chain_by_id(chain_id=chain.chain_id)

	def encoderpress(self, id, ccnum, ccval):
		if self.encoder_assign == 'global_view':
			encoder_num = int(id)
			if encoder_num < 4:
				if ccval == 127:
					self.state_manager.send_cuia("ZYNSWITCH", params=[encoder_num, 'P'])
				else:
					self.state_manager.send_cuia("ZYNSWITCH", params=[encoder_num, 'R'])

	def globalview(self, id, ccnum, ccval):
		self.strip_view = 'global_view'
		self.refresh()

	def encoderassign(self, id, ccnum, ccval):
		if ccval == 127:
			if self.encoder_assign == id:
				self.encoder_assign = 'global_view'
			else:
				self.encoder_assign = id
			self.refresh()

	def viewassign(self, id, ccnum, ccval):
		self.strip_view = id
		self.refresh()

	def faderbank(self, direction, ccnum, ccval):
		if ccval == 127:
			if direction == 'left':
				if self.first_zyn_channel_fader > 0:
					self.first_zyn_channel_fader -= self.device_settings['number_of_strips']
					if self.first_zyn_channel_fader < 0:
						self.first_zyn_channel_fader = 0
					self.refresh()
			elif direction == 'right':
				for n in range(1, int(len(self.get_ordered_chain_ids_filtered()) / self.device_settings[
					'number_of_strips'] + 1)):
					if self.first_zyn_channel_fader < self.device_settings['number_of_strips'] * n:
						self.first_zyn_channel_fader = self.device_settings['number_of_strips'] * n
						self.refresh()

	def channel(self, direction, ccnum, ccval):
		if ccval == 127:
			if direction == 'left':
				if self.first_zyn_channel_fader > 0:
					self.first_zyn_channel_fader -= 1
					self.refresh()
			elif direction == 'right':
				if self.first_zyn_channel_fader < len(self.get_ordered_chain_ids_filtered()) - self.device_settings[
					'number_of_strips']:
					self.first_zyn_channel_fader += 1
					self.refresh()

	def transport(self, command, ccnum, ccval):
		if ccval == 127:
			if command == 'play':
				if self.shift:
					self.state_manager.send_cuia("TOGGLE_MIDI_PLAY")
				else:
					self.state_manager.send_cuia("TOGGLE_AUDIO_PLAY")
			elif command == 'rec':
				if self.shift:
					self.state_manager.send_cuia("TOGGLE_MIDI_RECORD")
				else:
					self.state_manager.send_cuia("TOGGLE_AUDIO_RECORD")
			elif command == 'stop':
				if self.shift:
					self.state_manager.send_cuia("STOP_MIDI_PLAY")
					self.state_manager.send_cuia("STOP_MIDI_RECORD")
				else:
					self.state_manager.send_cuia("STOP_AUDIO_PLAY")
					self.state_manager.send_cuia("STOP_AUDIO_RECORD")

	def shiftassign(self, id, ccnum, ccval):
		if ccval == 127:
			self.shift = not self.shift
			self.rec_mode = self.shift
			self.refresh()

	def fadertouch(self, id, ccnum, ccval):
		if ccval == 127:
			self.fader_touch_active[int(id)] = True
		elif ccval == 64:
			self.fader_touch_active[int(id)] = False

	def get_ordered_chain_ids_filtered(self):
		chain_ids = list(self.chain_manager.ordered_chain_ids)
		if self.device_settings['masterfader']:
			try:
				chain_ids.pop()
			except:
				pass
		if self.strip_view == 'global_view':
			return chain_ids
		ordered_chain_ids_filtered = []
		for chain_id in chain_ids:
			chain = self.chain_manager.chains[chain_id]
			if self.strip_view == 'midi' and chain.is_midi() and not chain.is_synth():
				ordered_chain_ids_filtered.append(chain_id)
			elif self.strip_view == 'audio' and chain.is_audio() and not chain.is_synth():
				ordered_chain_ids_filtered.append(chain_id)
			elif self.strip_view == 'inst' and chain.is_synth():
				ordered_chain_ids_filtered.append(chain_id)
		return ordered_chain_ids_filtered

	def get_chain_by_position(self, pos):
		ordered_chain_ids_filtered = self.get_ordered_chain_ids_filtered()
		if pos < len(ordered_chain_ids_filtered):
			return self.chain_manager.chains[ordered_chain_ids_filtered[pos]]
		else:
			return None

	def get_mixer_chan_from_device_col(self, col):
		chain = self.get_chain_by_position(col)
		if chain is not None:
			if chain.is_audio() or chain.synth_slots:
				return chain.mixer_chan
		return None

	def init(self):
		self.sleep_off()  # Added this to perhaps stop losing the other registered signals
		# Register signals
		zynsigman.register_queued(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_SCREEN, self._on_gui_show_screen)
		zynsigman.register_queued(zynsigman.S_AUDIO_PLAYER, self.state_manager.SS_AUDIO_PLAYER_STATE, self.refresh_audio_transport)
		zynsigman.register_queued(zynsigman.S_AUDIO_RECORDER, self.state_manager.SS_AUDIO_RECORDER_STATE, self.refresh_audio_transport)
		zynsigman.register_queued(zynsigman.S_STATE_MAN, self.state_manager.SS_MIDI_PLAYER_STATE, self.refresh_midi_transport)
		zynsigman.register_queued(zynsigman.S_STATE_MAN, self.state_manager.SS_MIDI_RECORDER_STATE, self.refresh_midi_transport)
		super().init()

	def end(self):
		super().end()
		zynsigman.unregister(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_SCREEN, self._on_gui_show_screen)
		zynsigman.unregister(zynsigman.S_AUDIO_PLAYER, self.state_manager.SS_AUDIO_PLAYER_STATE, self.refresh_audio_transport)
		zynsigman.unregister(zynsigman.S_AUDIO_RECORDER, self.state_manager.SS_AUDIO_RECORDER_STATE, self.refresh_audio_transport)
		zynsigman.unregister(zynsigman.S_STATE_MAN, self.state_manager.SS_MIDI_PLAYER_STATE, self.refresh_midi_transport)
		zynsigman.unregister(zynsigman.S_STATE_MAN, self.state_manager.SS_MIDI_RECORDER_STATE, self.refresh_midi_transport)

	def refresh_audio_transport(self, **kwargs):
		if self.shift:
			return
		# REC Button
		if self.state_manager.audio_recorder.rec_proc:
			lib_zyncore.dev_send_note_on(
				self.idev_out, self.midi_chan, self.transport_dict_rev['rec'], 127)
			lib_zyncore.dev_send_note_on(
				self.idev_out, self.midi_chan, self.transport_dict_rev['play'], 127)
			lib_zyncore.dev_send_note_on(
				self.idev_out, self.midi_chan, self.transport_dict_rev['stop'], 0)
			return
		else:
			lib_zyncore.dev_send_note_on(
				self.idev_out, self.midi_chan, self.transport_dict_rev['rec'], 0)
			lib_zyncore.dev_send_note_on(
				self.idev_out, self.midi_chan, self.transport_dict_rev['stop'], 127)
		# PLAY button:
		if self.state_manager.status_audio_player:
			lib_zyncore.dev_send_note_on(
				self.idev_out, self.midi_chan, self.transport_dict_rev['play'], 127)
			lib_zyncore.dev_send_note_on(
				self.idev_out, self.midi_chan, self.transport_dict_rev['stop'], 0)
			return
		else:
			lib_zyncore.dev_send_note_on(
				self.idev_out, self.midi_chan, self.transport_dict_rev['play'], 0)
			lib_zyncore.dev_send_note_on(
				self.idev_out, self.midi_chan, self.transport_dict_rev['stop'], 127)


	def refresh_midi_transport(self, **kwargs):
		if not self.shift:
			return
		# REC Button
		if self.state_manager.status_midi_recorder:
			lib_zyncore.dev_send_note_on(
				self.idev_out, self.midi_chan, self.transport_dict_rev['rec'], 127)
			lib_zyncore.dev_send_note_on(
				self.idev_out, self.midi_chan, self.transport_dict_rev['play'], 127)
			lib_zyncore.dev_send_note_on(
				self.idev_out, self.midi_chan, self.transport_dict_rev['stop'], 0)
			return
		else:
			lib_zyncore.dev_send_note_on(
				self.idev_out, self.midi_chan, self.transport_dict_rev['rec'], 0)
			lib_zyncore.dev_send_note_on(
				self.idev_out, self.midi_chan, self.transport_dict_rev['stop'], 127)

		# PLAY button:
		if self.state_manager.status_midi_player:
			lib_zyncore.dev_send_note_on(
				self.idev_out, self.midi_chan, self.transport_dict_rev['play'], 127)
			lib_zyncore.dev_send_note_on(
				self.idev_out, self.midi_chan, self.transport_dict_rev['stop'], 0)
			return
		else:
			lib_zyncore.dev_send_note_on(
				self.idev_out, self.midi_chan, self.transport_dict_rev['play'], 0)
			lib_zyncore.dev_send_note_on(
				self.idev_out, self.midi_chan, self.transport_dict_rev['stop'], 127)
		# STOP button
		lib_zyncore.dev_send_note_on(
			self.idev_out, self.midi_chan, self.transport_dict_rev['stop'], 127)

	def get_lcd_bottom_text(self, channel, chain):
		bottom_text = ''
		if self.encoder_assign == 'global_view':
			# global_view - Get channel Name
			try:
				bottom_text = chain.get_title()
			except:
				bottom_text = ''
		elif self.encoder_assign == 'pan':  # Get Balance Value
			mixer_chan = chain.mixer_chan
			if mixer_chan is not None:
				balance_value = self.zynmixer.get_balance(mixer_chan)
				bottom_text = f'{round(balance_value * 100, 0)}%'
			else:
				bottom_text = '---'

		return bottom_text

	# Update LED and Fader status for a single strip
	def update_mixer_strip(self, chan, symbol, value):
		logging.debug(f"update_mixer_strip made chan: {chan} symbol: {symbol} value: {value} ")
		if self.idev_out is None:
			return

		chain_id = self.chain_manager.get_chain_id_by_mixer_chan(chan)
		logging.debug(f'chain_id: {chain_id}')

		if chain_id is not None:
			# Master Strip Level
			if chain_id == 0 and symbol == "level" and self.device_settings['masterfader']:
				if not self.fader_touch_active[self.device_settings['masterfader_fader_num']]:
					lib_zyncore.zmop_send_pitchbend_change(self.ZMOP_DEV0 + self.idev_out,
														   self.device_settings['masterfader_fader_num'],
														   int(value * self.max_fader_value))
				return
			else:
				if not (chain_id == 0 and self.device_settings['masterfader']):
					logging.debug(f'get_ordered_chain_ids_filtered: {self.get_ordered_chain_ids_filtered()}')
					col = self.get_ordered_chain_ids_filtered().index(chain_id)
					col -= self.first_zyn_channel_fader
					if 0 <= col < self.device_settings['number_of_strips']:
						logging.debug(f'update_mixer_strip chain_id: {chain_id}')
						if symbol == "mute":
							lib_zyncore.dev_send_note_on(self.idev_out,
														 self.midi_chan,
														 self.mute_ccnums[col],
														 value * 0x7F)
						elif symbol == "solo":
							lib_zyncore.dev_send_note_on(self.idev_out,
														 self.midi_chan,
														 self.solo_ccnums[col],
														 value * 0x7F)

						elif symbol == "rec":
							lib_zyncore.dev_send_note_on(self.idev_out,
														 self.midi_chan,
														 self.rec_ccnums[col],
														 value * 0x7F)

						elif symbol == "balance":
							if self.encoder_assign == "pan":
								self.update_bottom_lcd_text(col, f'{int(value * 100)}%')

						elif symbol == "level":
							if not self.fader_touch_active[col]:
								lib_zyncore.zmop_send_pitchbend_change(self.ZMOP_DEV0 + self.idev_out,
																	   col,
																	   int(value * self.max_fader_value))

	# Update LED status for active chain
	def update_mixer_active_chain(self, active_chain):
		logging.debug(f'update_mixer_active_chain: {active_chain}')
		if active_chain == 0:
			left_led, right_led = [77 - 48, 77 - 48]
		else:
			left_led, right_led = list(f"{active_chain:02}")
		lib_zyncore.dev_send_ccontrol_change(self.idev_out, self.midi_chan, 75, int(left_led) + 48)
		lib_zyncore.dev_send_ccontrol_change(self.idev_out, self.midi_chan, 74, int(right_led) + 48)

		# Set correct select led, if within the mixer range
		for i in range(0, self.device_settings['number_of_strips']):
			sel = 0
			try:
				ordered_chain_ids_filtered = self.get_ordered_chain_ids_filtered()
				chain_id = ordered_chain_ids_filtered[i + self.first_zyn_channel_fader]
				if chain_id == active_chain:
					sel = 0x7F
					if active_chain == 0 and self.device_settings['masterfader']:
						sel = 0
			except:
				sel = 0
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.select_ccnums[i], sel)

	# Update full LED, Faders and Display status
	def refresh(self):
		logging.debug(f"~~~ refresh ~~~")
		if self.idev_out is None:
			return

		# Shift Key LED and refresh transport
		if self.shift:
			lib_zyncore.dev_send_note_on(
				self.idev_out, self.midi_chan, self.shift_ccnum, 127)
			self.refresh_midi_transport()
		else:
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.shift_ccnum, 0)
			self.refresh_audio_transport()

		# Set Encoder Assign Selected Button LED - Global View, Tracks, PAN, etc
		for key, value in self.encoder_assign_dict_rev.items():
			if self.encoder_assign == key:
				lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, value, 127)
			else:
				lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, value, 0)

		# Set Fader Strip View Buttons
		for key, value in self.strip_view_dict_rev.items():
			if self.strip_view == key:
				lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, value, 127)
			else:
				lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, value, 0)

		# Master Channel Strip
		if self.device_settings['masterfader']:
			master_chain = self.chain_manager.get_chain(0)
			if master_chain is not None:
				zyn_volume_main = self.zynmixer.get_level(master_chain.mixer_chan)  # The Master Chain doesn't have a mixer_chan defined
				logging.debug(f'Master Channel Volume Level: {zyn_volume_main}')
				lib_zyncore.zmop_send_pitchbend_change(
					self.ZMOP_DEV0 + self.idev_out,
					self.device_settings['masterfader_fader_num'],
					int(zyn_volume_main * self.max_fader_value)
				)

		# Strips Leds, Faders and Displays
		col0 = self.first_zyn_channel_fader
		self.gernerate_top_lcd_text()
		if self.shift:
			lib_zyncore.dev_send_note_on(
				self.idev_out, self.midi_chan, self.shift_ccnum, 127)
			self.refresh_midi_transport()
		else:
			lib_zyncore.dev_send_note_on(
				self.idev_out, self.midi_chan, self.shift_ccnum, 0)
			self.refresh_audio_transport()

		for i in range(0, self.device_settings['number_of_strips']):
			rec = 0
			mute = 0
			solo = 0
			sel = 0
			bottom_text = '       '
			zyn_volume = 0

			chain = self.get_chain_by_position(col0 + i)

			if chain is not None:
				if chain.mixer_chan is not None:
					mute = self.zynmixer.get_mute(chain.mixer_chan) * 0x7F
					solo = self.zynmixer.get_solo(chain.mixer_chan) * 0x7F

				# LEDs
				if chain.mixer_chan is not None:
					rec = self.state_manager.audio_recorder.is_armed(chain.mixer_chan) * 0x7F

				# Select LED and Left/Right LED Chain Number
				if chain == self.chain_manager.get_active_chain():
					sel = 0x7F
					if chain.chain_id == 0:
						left_led, right_led = [77 - 48, 77 - 48]
					else:
						left_led, right_led = list(f"{chain.chain_id:02}")
					lib_zyncore.dev_send_ccontrol_change(self.idev_out, self.midi_chan, 75, int(left_led) + 48)
					lib_zyncore.dev_send_ccontrol_change(self.idev_out, self.midi_chan, 74, int(right_led) + 48)

				# Chain LCD-Displays
				top_text = f'CH {i + 1 + self.first_zyn_channel_fader}'
				bottom_text = self.get_lcd_bottom_text(i, chain)

				# Chain Volume
				if chain.is_audio() or chain.synth_slots:
					zyn_volume = self.zynmixer.get_level(chain.mixer_chan)
					if zyn_volume == None:
						zyn_volume = 0

			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.mute_ccnums[i], mute)
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.solo_ccnums[i], solo)
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.rec_ccnums[i], rec)
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.select_ccnums[i], sel)
			self.update_bottom_lcd_text(i, bottom_text)
			lib_zyncore.zmop_send_pitchbend_change(self.ZMOP_DEV0 + self.idev_out, i, int(zyn_volume * self.max_fader_value))
		logging.debug(f"~~~ end refresh ~~~")


	def midi_event(self, ev):
		evtype = (ev[0] >> 4) & 0x0F

		# TODO: Faders move to a funtion
		if evtype == 14:
			fader_channel = ev[0] - 0xE0
			logging.debug(f'midi_event fader_channel: {fader_channel}')
			if self.fader_touch_active[fader_channel]:
				logging.debug(f'{self.fader_touch_active}')
				mackie_vol_level = (ev[2] * 256 + ev[1])
				if self.device_settings['xtouch']:
					zyn_vol_level = mackie_vol_level / (self.max_fader_value * 2)
					mackie_vol_level = int(mackie_vol_level / 2)
				else:
					zyn_vol_level = mackie_vol_level / self.max_fader_value
				if fader_channel == self.device_settings['masterfader_fader_num'] and self.device_settings['masterfader']:
					self.zynmixer.set_level(self.get_master_chain_audio_channel(), zyn_vol_level)
					lib_zyncore.zmop_send_pitchbend_change(self.ZMOP_DEV0 + self.idev_out, fader_channel, mackie_vol_level)
				else:
					mixer_chan = self.get_mixer_chan_from_device_col(fader_channel + self.first_zyn_channel_fader)
					if mixer_chan is not None:
						self.zynmixer.set_level(mixer_chan, zyn_vol_level)
						lib_zyncore.zmop_send_pitchbend_change(self.ZMOP_DEV0 + self.idev_out, fader_channel, mackie_vol_level)

			return True

		# TODO: Encoders move to function
		elif evtype == 11:
			ccnum = ev[1] & 0x7F
			ccval = ev[2] & 0x7F
			logging.debug(f'Got encoders ccnum: {ccnum}, ccval: {ccval}')
			if ccnum in self.encoders_ccnum:
				# Encoders Zynthian 1 to 8
				if self.encoder_assign == 'global_view':
					if ccnum in self.encoders_ccnum[:4]:  # first 4 encoders
						encoder_num = self.encoders_ccnum.index(ccnum)
						if ccval > 64:  # Encoder turned left
							for interation in range(ccval - 64):
								self.state_manager.send_cuia("ZYNPOT", params=[encoder_num, -1])
						else:  # Encoder turned rigth
							for interation in range(ccval):
								self.state_manager.send_cuia("ZYNPOT", params=[encoder_num, 1])
					return True

				# Encoder PAN
				if self.encoder_assign == 'pan':
					col = self.encoders_ccnum.index(ccnum)
					chain = self.get_chain_by_position(col + self.first_zyn_channel_fader)
					mixer_chan = chain.mixer_chan
					if mixer_chan is not None:
						balance_value = self.zynmixer.get_balance(mixer_chan)
						# encoder_num = ccnum - self.encoders_ccnum[0] + self.first_zyn_channel_fader
						if ccval > 64:  # Encoder turned left
							new_balance_value = round(balance_value - (ccval - 64) / 100.0, 2)
							if new_balance_value < -1.0:
								new_balance_value = -1.0
						else:  # Encoder turned right
							new_balance_value = balance_value + ccval / 100.0
							if new_balance_value > 1.0:
								new_balance_value = 1.0
						self.zynmixer.set_balance(mixer_chan, new_balance_value, True)
						self.update_bottom_lcd_text(col, f'{round(new_balance_value * 100, 0)}%')
				return True

			elif ccnum == self.scroll_encoder:
				if ccval > 64:
					for i in range(ccval - 64):
						if self.gui_screen in ['audio_mixer']:
							self.state_manager.send_cuia("ARROW_LEFT")
						else:
							self.state_manager.send_cuia('ARROW_UP')
				else:
					for i in range(ccval):
						if self.gui_screen in ['audio_mixer']:
							self.state_manager.send_cuia('ARROW_RIGHT')
						else:
							self.state_manager.send_cuia('ARROW_DOWN')
				return True
			return True

		elif ev[0] != 0xF0:
			ccnum = ev[1] & 0x7F
			ccval = ev[2] & 0x7F
			logging.debug(f"midid_event - evtype:{evtype} ccnum:{ccnum} ccval:{ccval}")

			# Catch all the ccnum buttons listed in the yaml file
			if ccnum in self.my_settings['ccnum_buttons'].keys():
				logging.debug(f'Got ccnum: {ccnum}')
				event = self.my_settings['ccnum_buttons'][ccnum]
				logging.debug(f'got event: {event}')
				cmd = event['command']
				logging.debug(f'got command: {cmd}')
				if self.shift and 'shiftcmd' in event.keys():
					cmd = event['shiftcmd']

				if cmd.startswith('cuia') and ccval == 127:
					logging.debug(f'got cura command: {cmd}')
					self.state_manager.send_cuia(cmd.lstrip('cuia_'))
					return True

				elif cmd.startswith('ZYNSWITCH'):
					if ccval == 127:
						self.state_manager.send_cuia("ZYNSWITCH", params=[cmd.lstrip('ZYNSWITCH_'), 'P'])
					else:
						self.state_manager.send_cuia("ZYNSWITCH", params=[cmd.lstrip('ZYNSWITCH_'), 'R'])
					return True

				elif cmd.startswith('mkc'):
					func_and_value = cmd.split('_')
					my_method_ref = getattr(zynthian_ctrldev_mackiecontrol, func_and_value[1])  # my function
					my_method_ref(self, func_and_value[2], ccnum, ccval)  # called with value
					return True

		# SysEx
		elif ev[0] == 0xF0:
			if callable(self.sysex_answer_cb):
				self.sysex_answer_cb(ev)
			else:
				logging.debug(f"Received SysEx (unprocessed) => {ev.hex(' ')}")
			return True

		return True

	# Light-Off all LEDs
	def light_off(self):
		if self.idev_out is None:
			return
		for ccnum in self.cuia_mappings.keys():
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, ccnum, 0)
		self.delete_lcd_text()
		# Left and Right LED Display
		lib_zyncore.dev_send_ccontrol_change(self.idev_out, self.midi_chan, 75, 0)
		lib_zyncore.dev_send_ccontrol_change(self.idev_out, self.midi_chan, 74, 0)
		# Strip Faders
		for i in range(0, self.device_settings['number_of_strips']):
			lib_zyncore.zmop_send_pitchbend_change(self.ZMOP_DEV0 + self.idev_out, i, 0)
		if self.device_settings['masterfader']:
			lib_zyncore.zmop_send_pitchbend_change(self.ZMOP_DEV0 + self.idev_out, self.device_settings['masterfader_fader_num'], 0)

