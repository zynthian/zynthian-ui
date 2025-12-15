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

import os
import shutil
import logging
import oyaml as yaml
from time import sleep
from pathlib import Path

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore
from zyngine.zynthian_signal_manager import zynsigman
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynmixer


# --------------------------------------------------------------------------
# Mackiecontrol - MCU desks, Behringer X-Touch and many others!
# --------------------------------------------------------------------------


class zynthian_ctrldev_mackiecontrol(zynthian_ctrldev_zynmixer):
	# dev_ids = ["X-Touch IN 1"]
	dev_ids = ["*"]
	unroute_from_chains = True

	mackie_config_path = f"{os.environ['ZYNTHIAN_CONFIG_DIR']}/ctrldev"
	mackie_config_file = f"{mackie_config_path}/mackiecontrol.yaml"

	# Function to initialise class
	def __init__(self, state_manager, idev_in, idev_out=None):
		super().__init__(state_manager, idev_in, idev_out)

		self.sysex_answer_cb = None
		self.midi_chan = 0x0  # zero is the default don't change
		self.shift = False

		self.my_settings = self.load_yaml_config(self.mackie_config_path, self.mackie_config_file)
		self.device_settings = {
			'number_of_strips': int(self.my_settings['device_settings']['number_of_strips']),
			'masterfader': bool(self.my_settings['device_settings']['masterfader']),
			'masterfader_fader_num': int(self.my_settings['device_settings']['masterfader_fader_num']) - 1,
			'touchsensefaders': bool(self.my_settings['device_settings']['touchsensefaders']),
			'xtouch': bool(self.my_settings['device_settings']['xtouch']),  # Not used anymore!!
		}

		self.cuia_mappings = self.my_settings['ccnum_buttons']
		self.cuia_names = {}
		for cuia in sorted(self.cuia_mappings.keys()):
			if self.cuia_mappings[cuia]['command'] != 'None':
				command = '_'.join(self.cuia_mappings[cuia]['command'].split('_')[1:])
				self.cuia_names[command] = self.cuia_mappings[cuia]
				self.cuia_names[command]['num'] = int(cuia)

		# TODO: there must be a better way
		self.rec_ccnums = []
		self.solo_ccnums = []
		self.mute_ccnums = []
		self.select_ccnums = []
		self.encoders_press_ccnum = []
		self.faderstouch_ccnum = []
		self.encoder_assign_dict_rev = {}
		self.strip_view_dict_rev = {}
		self.transport_dict_rev = {}
		self.shift_ccnum = 70
		for name in self.cuia_names.keys():
			if name.startswith('shift'):
				self.shift_ccnum = self.cuia_names[name]['num']
			elif name.startswith('rec'):
				self.rec_ccnums.append(self.cuia_names[name]['num'])
			elif name.startswith('solo'):
				self.solo_ccnums.append(self.cuia_names[name]['num'])
			elif name.startswith('mute'):
				self.mute_ccnums.append(self.cuia_names[name]['num'])
			elif name.startswith('select'):
				if name == 'select':
					self.select_ccnums = self.cuia_names[name]['num']
				else:
					self.select_ccnums.append(self.cuia_names[name]['num'])
			elif name.startswith('encoderpress'):
				self.encoders_press_ccnum.append(self.cuia_names[name]['num'])
			elif name.startswith('fadertouch'):
				self.faderstouch_ccnum.append(self.cuia_names[name]['num'])
			elif name.startswith('encoderassign'):
				function = name.split('_')[-1]
				self.encoder_assign_dict_rev[function] = self.cuia_names[name]['num']
			elif name.startswith('viewassign'):
				function = name.split('_')[-1]
				self.strip_view_dict_rev[function] = self.cuia_names[name]['num']
			elif name.startswith('transport'):
				function = name.split('_')[-1]
				self.transport_dict_rev[function] = self.cuia_names[name]['num']
			elif name.startswith('globalview'):
				self.strip_view_dict_rev['global_view'] = self.cuia_names[name]['num']

		if self.device_settings['touchsensefaders']:
			self.fader_touch_active = [False, False, False, False, False, False, False, False, False]
		else:
			self.fader_touch_active = [True, True, True, True, True, True, True, True, True]
		self.max_fader_value = 16383.0  # I think this is default Mackie
		self.encoder_assign = 'global_view'  # Set as default
		self.strip_view = 'global_view'  # Set default
		self.gui_screen = 'mixer'  # Set as default, it's needed to correct an issue when starting  up
		# TODO: add to yaml file
		self.encoders_ccnum = [16, 17, 18, 19, 20, 21, 22, 23]
		self.scroll_encoder = 60

	@staticmethod
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
			logging.debug(f"Loading yaml config file '{file}'")
			return yaml.load(data, Loader=yaml.SafeLoader)
		except Exception as e:
			logging.error(f"Bad formatted yaml in config file '{file}' => {e}")
			return {}

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

	def update_all_lcd_text(self, text1, text2):
		data = ['12', '00']
		text = f"{text1: <56}{text2: <56}"
		for num in range(56):
			letter = text[num]
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

	# mkc Functions
	def buttonled_on(self, ccnum):
		lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, ccnum, 127)

	def buttonled_off(self, ccnum):
		lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, ccnum, 0)

	def rec(self, id, ccnum, ccval):
		if ccval == 127:
			col = int(id) + self.mixer_col_offset
			val = self.toggle_mixer_param("record", col)
			# Send LED feedback
			if self.idev_out is not None:
				lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, ccnum, val * 0x7F)

	def solo(self, id, ccnum, ccval):
		if ccval == 127:
			col = int(id) + self.mixer_col_offset
			val = self.toggle_mixer_param("solo", col)
			# Send LED feedback
			if self.idev_out is not None:
				lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, ccnum, val * 0x7F)

	def mute(self, id, ccnum, ccval):
		if ccval == 127:
			col = int(id) + self.mixer_col_offset
			val = self.toggle_mixer_param("mute", col)
			# Send LED feedback
			if self.idev_out is not None:
				lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, ccnum, val * 0x7F)

	def select(self, id, ccnum, ccval):
		if ccval == 127:
			col = int(id) + self.mixer_col_offset
			self.chain_manager.set_active_chain_by_index(col)

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
		self.chain_type_filter = []
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
		match self.strip_view:
			case "audio":
				self.chain_type_filter = ["generator"]
			case "midi":
				self.chain_type_filter = ["midi"]
			case "inst":
				self.chain_type_filter = ["synth"]
			case "inputs":
				self.chain_type_filter = ["audio_in"]
			case "outputs":
				self.chain_type_filter = ["audio_out"]
			case "aux":
				self.chain_type_filter = ["mixbus"]
			case "buses":
				self.chain_type_filter = ["mixbus"]
			case "user":
				pass
			case _:
				self.chain_type_filter = []
		self.refresh()

	def faderbank(self, direction, ccnum, ccval):
		if ccval == 127:
			n_strips = self.device_settings['number_of_strips']
			if direction == 'left':
				if self.mixer_col_offset > 0:
					self.mixer_col_offset -= n_strips
					if self.mixer_col_offset < 0:
						self.mixer_col_offset = 0
					self.refresh()
			elif direction == 'right':
				n_chains = len(self.chain_manager.ordered_chain_ids)
				if self.mixer_col_offset < n_chains - n_strips:
					self.mixer_col_offset += n_strips
					self.refresh()

	def channel(self, direction, ccnum, ccval):
		if ccval == 127:
			n_strips = self.device_settings['number_of_strips']
			if direction == 'left':
				if self.mixer_col_offset > 0:
					self.mixer_col_offset -= 1
					self.refresh()
			elif direction == 'right':
				n_chains = len(self.chain_manager.ordered_chain_ids)
				if self.mixer_col_offset < n_chains - n_strips:
					self.mixer_col_offset += 1
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
			self.refresh()

	def display(self, id, ccnum, ccval):
		pass

	def fadertouch(self, id, ccnum, ccval):
		#logging.debug(f"FADERTOUCH => ID {id}, {ccnum}, {ccval}")
		if ccval == 127:
			self.fader_touch_active[int(id)] = True
		else:
			self.fader_touch_active[int(id)] = False

	def init_fader_touch(self):
		if self.idev_out is None:
			return
		for ccnum in self.faderstouch_ccnum:
			lib_zyncore.dev_send_note_on(self.idev_out, 0, ccnum, 127)

	def init(self):
		self.sleep_off()  # Added this to perhaps stop losing the other registered signals
		# Register signals
		zynsigman.register_queued(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_SCREEN, self._on_gui_show_screen)
		zynsigman.register_queued(zynsigman.S_AUDIO_PLAYER, self.state_manager.SS_AUDIO_PLAYER_STATE, self.refresh_audio_transport)
		zynsigman.register_queued(zynsigman.S_AUDIO_RECORDER, self.state_manager.SS_AUDIO_RECORDER_STATE, self.refresh_audio_transport)
		zynsigman.register_queued(zynsigman.S_STATE_MAN, self.state_manager.SS_MIDI_PLAYER_STATE, self.refresh_midi_transport)
		zynsigman.register_queued(zynsigman.S_STATE_MAN, self.state_manager.SS_MIDI_RECORDER_STATE, self.refresh_midi_transport)
		super().init()
		self.init_fader_touch()
		self.update_all_lcd_text("Zynthian CTRLDEV driver for Mackie Control", "Enjoy and play the waves")

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
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.transport_dict_rev['rec'], 127)
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.transport_dict_rev['play'], 127)
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.transport_dict_rev['stop'], 0)
			return
		else:
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.transport_dict_rev['rec'], 0)
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.transport_dict_rev['stop'], 127)
		# PLAY button:
		if self.state_manager.status_audio_player:
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.transport_dict_rev['play'], 127)
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.transport_dict_rev['stop'], 0)
			return
		else:
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.transport_dict_rev['play'], 0)
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.transport_dict_rev['stop'], 127)

	def refresh_midi_transport(self, **kwargs):
		if not self.shift:
			return
		# REC Button
		if self.state_manager.status_midi_recorder:
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.transport_dict_rev['rec'], 127)
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.transport_dict_rev['play'], 127)
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.transport_dict_rev['stop'], 0)
			return
		else:
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.transport_dict_rev['rec'], 0)
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.transport_dict_rev['stop'], 127)

		# PLAY button:
		if self.state_manager.status_midi_player:
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.transport_dict_rev['play'], 127)
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.transport_dict_rev['stop'], 0)
			return
		else:
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.transport_dict_rev['play'], 0)
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.transport_dict_rev['stop'], 127)
		# STOP button
		lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.transport_dict_rev['stop'], 127)

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
	def update_mixer_strip(self, chan, symbol, value, mixbus=False):
		if self.idev_out is None:
			return
		if mixbus:
			chain_id = chan
		else:
			chain_id = self.chain_manager.get_chain_id_by_mixer_chan(chan)
		#logging.debug(f"update_mixer_strip chan: {chan} symbol: {symbol} value: {value}, mixbus: {mixbus} => chain ID: {chain_id}")
		if chain_id is not None:
			# Master Strip Level
			if chain_id == 0 and self.device_settings['masterfader']:
				if symbol == "level" and not self.fader_touch_active[self.device_settings['masterfader_fader_num']]:
					lib_zyncore.dev_send_pitchbend_change(self.idev_out, self.device_settings['masterfader_fader_num'], int(value * self.max_fader_value))
				return
			else:
				col = self.get_filtered_index_by_chain_id(chain_id) - self.mixer_col_offset
				if 0 <= col < self.device_settings['number_of_strips']:
					if symbol == "mute":
						lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.mute_ccnums[col], value * 0x7F)
					elif symbol == "solo":
						lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.solo_ccnums[col], value * 0x7F)
					elif symbol == "rec":
						lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.rec_ccnums[col], value * 0x7F)
					elif symbol == "balance":
						if self.encoder_assign == "pan":
							self.update_bottom_lcd_text(col, f'{int(value * 100)}%')
					elif symbol == "level":
						if not self.fader_touch_active[col]:
							lib_zyncore.dev_send_pitchbend_change(self.idev_out, col, int(value * self.max_fader_value))

	# Update LED status for active chain
	def update_mixer_active_chain(self, active_chain):
		if self.idev_out is None:
			return
		if active_chain == 0:
			left_led, right_led = [77 - 48, 77 - 48]
		else:
			left_led, right_led = list(f"{active_chain:02}")
		lib_zyncore.dev_send_ccontrol_change(self.idev_out, self.midi_chan, 75, int(left_led) + 48)
		lib_zyncore.dev_send_ccontrol_change(self.idev_out, self.midi_chan, 74, int(right_led) + 48)

		# Set correct select led, if within the mixer range
		for i in range(0, self.device_settings['number_of_strips']):
			chain_id = self.get_filtered_chain_id_by_index(self.mixer_col_offset + i)
			if chain_id == active_chain:
				sel = 0x7F
				if chain_id == 0 and self.device_settings['masterfader']:
					sel = 0
			else:
				sel = 0
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.select_ccnums[i], sel)

	# Update full LED, Faders and Display status
	def refresh(self):
		super().refresh()
		if self.idev_out is None:
			return

		# Shift Key LED and refresh transport
		if self.shift:
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.shift_ccnum, 127)
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
			val = self.get_mixer_param("level", -1)
			lib_zyncore.dev_send_pitchbend_change(self.idev_out, self.device_settings['masterfader_fader_num'], int(val * self.max_fader_value))

		# Strips Leds, Faders and Displays
		self.gernerate_top_lcd_text()
		if self.shift:
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.shift_ccnum, 127)
			self.refresh_midi_transport()
		else:
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.shift_ccnum, 0)
			self.refresh_audio_transport()

		for i in range(0, self.device_settings['number_of_strips']):
			pos = self.mixer_col_offset + i

			mute = self.get_mixer_param("mute", pos)
			solo = self.get_mixer_param("solo", pos)
			rec = self.get_mixer_param("record", pos)
			volume = self.get_mixer_param("level", pos)

			# Select LED and Left/Right LED Chain Number
			chain_id = self.get_filtered_chain_id_by_index(pos)
			if chain_id == self.chain_manager.get_active_chain().chain_id:
				sel = 1
				if chain_id == 0:
					left_led, right_led = [77 - 48, 77 - 48]
				else:
					left_led, right_led = list(f"{chain_id:02}")
				lib_zyncore.dev_send_ccontrol_change(self.idev_out, self.midi_chan, 75, int(left_led) + 48)
				lib_zyncore.dev_send_ccontrol_change(self.idev_out, self.midi_chan, 74, int(right_led) + 48)
			else:
				sel = 0

			# Chain LCD-Displays
			top_text = f'CH {pos + 1}'
			try:
				bottom_text = self.get_lcd_bottom_text(i, self.chain_manager.chains[chain_id])
			except:
				bottom_text = '       '

			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.mute_ccnums[i], mute * 0x7F)
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.solo_ccnums[i], solo * 0x7F)
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.rec_ccnums[i], rec * 0x7F)
			lib_zyncore.dev_send_note_on(self.idev_out, self.midi_chan, self.select_ccnums[i], sel * 0x7F)
			lib_zyncore.dev_send_pitchbend_change(self.idev_out, i, int(volume * self.max_fader_value))
			self.update_top_lcd_text(i, top_text)
			self.update_bottom_lcd_text(i, bottom_text)

	def midi_event(self, ev):
		evtype = (ev[0] >> 4) & 0x0F

		# TODO: Faders move to a funtion
		if evtype == 14:
			fader_channel = ev[0] - 0xE0
			#logging.debug(f'fader_channel {fader_channel}')
			if self.fader_touch_active[fader_channel]:
				mackie_vol_level = (ev[2] * 128 + ev[1])
				zyn_vol_level = mackie_vol_level / self.max_fader_value
				if self.device_settings['masterfader'] and fader_channel == self.device_settings['masterfader_fader_num']:
					pos = -1
				else:
					pos = self.mixer_col_offset + fader_channel
				self.set_mixer_param("level", pos, zyn_vol_level)
				if self.idev_out is not None:
					lib_zyncore.dev_send_pitchbend_change(self.idev_out, fader_channel, mackie_vol_level)
			return True

		# TODO: Encoders move to function
		elif evtype == 11:
			ccnum = ev[1] & 0x7F
			ccval = ev[2] & 0x7F
			#logging.debug(f'Got encoders ccnum: {ccnum}, ccval: {ccval}')
			if ccnum in self.encoders_ccnum:
				# Encoders Zynthian 1 to 8
				if self.encoder_assign == 'global_view':
					if ccnum in self.encoders_ccnum[:4]:  # first 4 encoders
						encoder_num = self.encoders_ccnum.index(ccnum)
						if ccval > 64:  # Encoder turned left
							ccval = 64 - ccval
						else:			# Encoder turned rigth
							pass
						self.state_manager.send_cuia("ZYNPOT", params=[encoder_num, ccval])
					return True
				# Encoder PAN
				if self.encoder_assign == 'pan':
					col = self.encoders_ccnum.index(ccnum)
					pos = self.mixer_col_offset + col
					balance_value = self.get_mixer_param("balance", pos)
					# encoder_num = ccnum - self.encoders_ccnum[0] + self.mixer_col_offset
					if ccval > 64:  # Encoder turned left
						new_balance_value = round(balance_value - (ccval - 64) / 100.0, 2)
						if new_balance_value < -1.0:
							new_balance_value = -1.0
					else:           # Encoder turned right
						new_balance_value = round(balance_value + ccval / 100.0, 2)
						if new_balance_value > 1.0:
							new_balance_value = 1.0
					self.set_mixer_param("balance", col, new_balance_value)
					self.update_bottom_lcd_text(col, f'{round(new_balance_value * 100, 0)}%')
				return True

			elif ccnum == self.scroll_encoder:
				if ccval > 64:
					for i in range(ccval - 64):
						if self.gui_screen in ['mixer']:
							self.state_manager.send_cuia("ARROW_LEFT")
						else:
							self.state_manager.send_cuia('ARROW_UP')
				else:
					for i in range(ccval):
						if self.gui_screen in ['mixer']:
							self.state_manager.send_cuia('ARROW_RIGHT')
						else:
							self.state_manager.send_cuia('ARROW_DOWN')
				return True
			return True

		elif ev[0] != 0xF0:
			ccnum = ev[1] & 0x7F
			ccval = ev[2] & 0x7F
			#logging.debug(f"midid_event - evtype:{evtype} ccnum:{ccnum} ccval:{ccval}")

			# Catch all the ccnum buttons listed in the yaml file
			if ccnum in self.my_settings['ccnum_buttons'].keys():
				event = self.my_settings['ccnum_buttons'][ccnum]
				if self.shift and 'shiftcmd' in event.keys():
					cmd = event['shiftcmd']
				else:
					cmd = event['command']
				logging.debug(f'Got ccnum {ccnum}, event {event} => command {cmd}')
				if cmd.startswith('cuia') and ccval == 127:
					self.state_manager.send_cuia(cmd.lstrip('cuia_'))
					return True
				elif cmd.startswith('ZYNSWITCH'):
					if ccval == 127:
						self.state_manager.send_cuia("ZYNSWITCH", params=[cmd.lstrip('ZYNSWITCH_'), 'P'])
					else:
						self.state_manager.send_cuia("ZYNSWITCH", params=[cmd.lstrip('ZYNSWITCH_'), 'R'])
					return True
				elif cmd.startswith('mkc'):
					parts = cmd.split('_')
					my_func = getattr(zynthian_ctrldev_mackiecontrol, parts[1])  # my function
					my_func(self, parts[2], ccnum, ccval)  # call function with arguments
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
			lib_zyncore.dev_send_pitchbend_change(self.idev_out, i, 0)
		if self.device_settings['masterfader']:
			lib_zyncore.dev_send_pitchbend_change(self.idev_out, self.device_settings['masterfader_fader_num'], 0)

