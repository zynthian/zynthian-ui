#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Control Device Manager Class
#
# Copyright (C) 2015-2024 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <brian@riban.co.uk>
#                         Oscar Acena <oscaracena@gmail.com>
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

import time
import logging
from threading import Thread, RLock, Event
from bisect import bisect

from zyncoder.zyncore import lib_zyncore
from zyngui import zynthian_gui_config
from zyngine.zynthian_signal_manager import zynsigman


class CONST:
	# Some MIDI event constants
	MIDI_NOTE_ON   = 0x09
	MIDI_NOTE_OFF  = 0x08
	MIDI_CC        = 0x0B
	MIDI_PC        = 0x0C
	MIDI_SYSEX     = 0xF0
	MIDI_CLOCK     = 0xF8
	MIDI_CONTINUE  = 0xFB

	PT_SHORT       = "short"
	PT_BOLD        = "bold"
	PT_LONG        = "long"
	PT_BOLD_TIME   = 0.3
	PT_LONG_TIME   = 2.0


# ------------------------------------------------------------------------------------------------------------------
# Control device base class
# ------------------------------------------------------------------------------------------------------------------
class zynthian_ctrldev_base:

	dev_ids = []			# String list that could identify the device
	dev_id = None  			# String that identifies the device
	fb_dev_id = None		# Index of zmop connected to controller input
	dev_zynpad = False		# Can act as a zynpad trigger device
	dev_zynmixer = False    # Can act as an audio mixer controller device
	dev_pated = False		# Can act as a pattern editor device
	enabled = False			# True if device driver is enabled
	unroute_from_chains = True		# True if input device must be unrouted from chains when driver is loaded

	# Function to initialise class
	def __init__(self, state_manager, idev_in, idev_out=None):
		self.state_manager = state_manager
		self.chain_manager = state_manager.chain_manager
		self.idev = idev_in		       # Slot index where the input device is connected, starting from 1 (0 = None)
		self.idev_out = idev_out       # Slot index where the output device (feedback), if any, is connected, starting from 1 (0 = None)

	# Send SysEx universal inquiry.
	# It's answered by some devices with a SysEx message.
	def send_sysex_universal_inquiry(self):
		if self.idev_out > 0:
			msg = bytes.fromhex("F0 7E 7F 06 01 F7")
			lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))

	# Initialize control device: setup, register signals, etc
	# It *SHOULD* be implemented by child class
	def init(self):
		self.refresh()

	# End control device: restore initial state, unregister signals, etc
	# It *SHOULD* be implemented by child class
	def end(self):
		logging.debug("End() for {}: NOT IMPLEMENTED!".format(type(self).__name__))

	# Refresh full device status (LED feedback, etc)
	# *SHOULD* be implemented by child class
	def refresh(self):
		logging.debug("Refresh LEDs for {}: NOT IMPLEMENTED!".format(type(self).__name__))

	# Device MIDI event handler
	# *SHOULD* be implemented by child class
	def midi_event(self, ev):
		logging.debug("MIDI EVENT FROM '{}'".format(type(self).__name__))

	# Light-Off LEDs
	# *SHOULD* be implemented by child class
	def light_off(self):
		logging.debug("Lighting Off LEDs for {}: NOT IMPLEMENTED!".format(type(self).__name__))

	# Sleep On
	# *COULD* be improved by child class
	def sleep_on(self):
		self.light_off()

	# Sleep Off
	# *COULD* be improved by child class
	def sleep_off(self):
		self.refresh()

	# Return driver's state dictionary
	# *COULD* be implemented by child class
	def get_state(self):
		return None

	# Restore driver's state
	# *COULD* be implemented by child class
	def set_state(self, state):
		pass

# ------------------------------------------------------------------------------------------------------------------
# Zynpad control device base class
# ------------------------------------------------------------------------------------------------------------------
class zynthian_ctrldev_zynpad(zynthian_ctrldev_base):

	dev_zynpad = True		# Can act as a zynpad trigger device

	def __init__(self, state_manager, idev_in, idev_out=None):
		self.cols = 8
		self.rows = 8
		self.zynseq = state_manager.zynseq
		super().__init__(state_manager, idev_in, idev_out)

	def init(self):
		super().init()
		# Register for zynseq updates
		zynsigman.register_queued(zynsigman.S_STEPSEQ, self.zynseq.SS_SEQ_PLAY_STATE, self.update_seq_state)
		zynsigman.register_queued(zynsigman.S_STEPSEQ, self.zynseq.SS_SEQ_REFRESH, self.refresh)

	def end(self):
		# Unregister from zynseq updates
		zynsigman.unregister(zynsigman.S_STEPSEQ, self.zynseq.SS_SEQ_PLAY_STATE, self.update_seq_state)
		zynsigman.unregister(zynsigman.S_STEPSEQ, self.zynseq.SS_SEQ_REFRESH, self.refresh)
		self.light_off()

	def update_seq_bank(self):
		"""Update hardware indicators for active bank and refresh sequence state as needed.
		*COULD* be implemented by child class
		"""
		pass

	def update_seq_state(self, bank, seq, state=None, mode=None, group=None):
		"""Update hardware indicators for a sequence (pad): playing state etc.
		*SHOULD* be implemented by child class

		bank - bank
		seq - sequence index
		state - sequence's state
		mode - sequence's mode
		group - sequence's group
		"""
		logging.debug("Update sequence playing state for {}: NOT IMPLEMENTED!".format(type(self).__name__))

	def pad_off(self, col, row):
		"""Light-Off the pad specified with column & row
		*SHOULD* be implemented by child class
		"""
		pass

	def refresh(self):
		"""Refresh full device status (LED feedback, etc)
		*COULD* be implemented by child class
		"""
		if self.idev_out is None:
			return
		self.update_seq_bank()
		for i in range(self.cols):
			for j in range(self.rows):
				if i >= self.zynseq.col_in_bank or j >= self.zynseq.col_in_bank:
					self.pad_off(i, j)
				else:
					seq = i * self.zynseq.col_in_bank + j
					state = self.zynseq.libseq.getSequenceState(self.zynseq.bank, seq)
					mode = (state >> 8) & 0xFF
					group = (state >> 16) & 0xFF
					state &= 0xFF
					self.update_seq_state(bank=self.zynseq.bank, seq=seq, state=state, mode=mode, group=group)


# ------------------------------------------------------------------------------------------------------------------
# Zynmixer control device base class
# ------------------------------------------------------------------------------------------------------------------
class zynthian_ctrldev_zynmixer(zynthian_ctrldev_base):

	dev_zynmixer = True		# Can act as a zynmixer trigger device

	def __init__(self, state_manager, idev_in, idev_out=None):
		self.zynmixer = state_manager.zynmixer
		super().__init__(state_manager, idev_in, idev_out)

	def init(self):
		super().init()
		zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_SET_ACTIVE_CHAIN, self.update_mixer_active_chain)
		zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_MOVE_CHAIN, self.refresh)
		zynsigman.register_queued(zynsigman.S_AUDIO_MIXER, self.zynmixer.SS_ZCTRL_SET_VALUE, self.update_mixer_strip)

	def end(self):
		zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_SET_ACTIVE_CHAIN, self.update_mixer_active_chain)
		zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_MOVE_CHAIN, self.refresh)
		zynsigman.unregister(zynsigman.S_AUDIO_MIXER, self.zynmixer.SS_ZCTRL_SET_VALUE, self.update_mixer_strip)
		self.light_off()

	def update_mixer_strip(self, chan, symbol, value):
		"""Update hardware indicators for a mixer strip: mute, solo, level, balance, etc.
		*SHOULD* be implemented by child class

		chan - Mixer strip index
		symbol - Control name
		value - Control value
		"""
		logging.debug(f"Update mixer strip for {type(self).__name__}: NOT IMPLEMENTED!")

	def update_mixer_active_chain(self, active_chain):
		"""Update hardware indicators for active_chain
		*SHOULD* be implemented by child class

		active_chain - Active chain
		"""
		logging.debug(f"Update mixer active chain for {type(self).__name__}: NOT IMPLEMENTED!")


# --------------------------------------------------------------------------
# A timer for running delayed actions
# --------------------------------------------------------------------------
class RunTimer(Thread):
	RESOLUTION = 0.1

	def __init__(self):
		super().__init__()
		self._lock = RLock()
		self._awake = Event()
		self._actions = {}

		self.daemon = True
		self.start()

	def __contains__(self, b):
		return b in self._actions

	def add(self, name, timeout, callback, *args, **kwargs):
		with self._lock:
			self._actions[name] = [timeout, callback, name, args, kwargs]
		self._awake.set()

	def update(self, name, timeout):
		with self._lock:
			action = self._actions.get(name)
			if action is None:
				return
			action[0] = timeout

	def remove(self, name):
		with self._lock:
			self._actions.pop(name, None)

	def run(self):
		while True:
			if not self._actions:
				self._awake.wait()
			self._awake.clear()
			for action in self._get_expired():
				self._run_action(*action[1:])
			time.sleep(self.RESOLUTION)
			self._update_timeouts(-self.RESOLUTION)

	def _update_timeouts(self, delta):
		delta *= 1000
		with self._lock:
			for action in self._actions.values():
				action[0] += delta

	def _get_expired(self):
		retval = []
		with self._lock:
			to_remove = []
			for name, spec in self._actions.items():
				if spec[0] > 0:
					continue
				to_remove.append(name)
				retval.append(spec)
			for name in to_remove:
				self._actions.pop(name, None)
		return retval

	def _run_action(self, callback, name, args, kwargs):
		try:
			callback(name, *args, **kwargs)
		except Exception as ex:
			logging.error(f" error in handler: {ex}")


# --------------------------------------------------------------------------
#  A timer for running repeated actions
# --------------------------------------------------------------------------
class IntervalTimer(RunTimer):
	RESOLUTION = 0.05

	def add(self, name, timeout, callback, *args, **kwargs):
		with self._lock:
			self._actions[name] = [timeout, timeout, callback, name, args, kwargs]
		self._awake.set()

	def update(self, name, timeout):
		with self._lock:
			action = self._actions.get(name)
			if action is None:
				return
			action[1] = timeout

	def run(self):
		while True:
			if not self._actions:
				self._awake.wait()
			self._awake.clear()
			for action in self._get_expired():
				self._run_action(*action[2:])
			time.sleep(self.RESOLUTION)
			self._update_timeouts(self.RESOLUTION)

	def _get_expired(self):
		retval = []
		with self._lock:
			for spec in self._actions.values():
				if spec[0] < spec[1]:
					continue
				retval.append(spec)
				spec[0] = 0

		return retval


# --------------------------------------------------------------------------
# A handy timer for triggering short/bold/long push actions
# --------------------------------------------------------------------------
class ButtonTimer(Thread):
	def __init__(self, callback):
		super().__init__()
		self._callback = callback
		self._lock = RLock()
		self._awake = Event()
		self._pressed = {}

		self.daemon = True
		self.start()

	def is_pressed(self, btn, ts):
		with self._lock:
			self._pressed[btn] = ts
		self._awake.set()

	def is_released(self, btn):
		with self._lock:
			ts = self._pressed.pop(btn, None)
		if ts is not None:
			elapsed = time.time() - ts
			self._run_callback(btn, elapsed)

	def run(self):
		while True:
			with self._lock:
				expired, elapsed = self._get_expired()
			if expired is not None:
				self._run_callback(expired, elapsed)

			time.sleep(0.1)
			if not self._pressed:
				self._awake.wait()
			self._awake.clear()

	def _get_expired(self):
		now = time.time()
		retval = None
		for btn, ts in self._pressed.items():
			elapsed = now - ts
			if elapsed > CONST.PT_LONG_TIME:
				retval = btn
				break
		if retval:
			self._pressed.pop(btn, None)
		return retval, elapsed if retval else 0

	def _run_callback(self, note, elapsed):
		ptype = [CONST.PT_SHORT, CONST.PT_BOLD, CONST.PT_LONG][
			bisect([CONST.PT_BOLD_TIME, CONST.PT_LONG_TIME], elapsed)]
		try:
			self._callback(note, ptype)
		except Exception as ex:
			logging.error(f" error in handler: {ex}")


# --------------------------------------------------------------------------
#  Helper class to handle knobs speed
# --------------------------------------------------------------------------
class KnobSpeedControl:
	def __init__(self, steps_normal=3, steps_shifted=8):
		self._steps_normal = steps_normal
		self._steps_shifted = steps_shifted
		self._knobs_ease = {}

	def feed(self, ccnum, ccval, is_shifted=False):
		delta = ccval if ccval < 64 else (ccval - 128)
		count = self._knobs_ease.get(ccnum, 0)
		steps = self._steps_shifted if is_shifted else self._steps_normal

		if (delta < 0 and count > 0) or (delta > 0 and count < 0):
			count = 0
		count += delta

		if abs(count) < steps:
			self._knobs_ease[ccnum] = count
			return

		self._knobs_ease[ccnum] = 0
		return delta


# --------------------------------------------------------------------------
# Base class for mode handlers
# --------------------------------------------------------------------------
class ModeHandlerBase:

	SCREEN_CUIA_MAP = {
		"option":         "MENU",
		"main_menu":      "MENU",
		"admin":          "SCREEN_ADMIN",
		"audio_mixer":    "SCREEN_AUDIO_MIXER",
		"alsa_mixer":     "SCREEN_ALSA_MIXER",
		"control":        "SCREEN_CONTROL",
		"preset":         "PRESET",
		"zs3":            "SCREEN_ZS3",
		"snapshot":       "SCREEN_SNAPSHOT",
		"zynpad":         "SCREEN_ZYNPAD",
		"pattern_editor": "SCREEN_PATTERN_EDITOR",
		"tempo":          "TEMPO",
	}

	# These are actions requested to other handlers (shared between everyone)
	_pending_actions = []

	def __init__(self, state_manager):
		self._state_manager = state_manager
		self._chain_manager = state_manager.chain_manager
		self._zynmixer = state_manager.zynmixer
		self._zynseq = state_manager.zynseq

		self._timer = None
		self._current_screen = None
		self._is_shifted = False
		self._is_active = False

	def refresh(self):
		pass

	def set_active(self, active):
		self._is_active = active

	def note_on(self, note, velocity, shifted_override=None):
		pass

	def note_off(self, note, shifted_override=None):
		pass

	def cc_change(self, ccnum, ccval):
		pass

	def pg_change(self, program):
		pass

	def sysex_message(self, payload):
		pass

	def get_state(self):
		return {}

	def set_state(self, state):
		pass

	def on_media_change(self, media, kind, state):
		pass

	def on_shift_changed(self, state):
		self._is_shifted = state
		return True

	def on_screen_change(self, screen):
		self._current_screen = screen

	def pop_action_request(self):
		if not self._pending_actions:
			return None
		return self._pending_actions.pop(0)

	def run_action(self, action, args, kwargs):
		action = "_action_" + action.replace("-", "_")
		action = getattr(self, action, None)
		if callable(action):
			try:
				action(*args, **kwargs)
			except Exception as ex:
				logging.error(f" error in handler: {ex}")

	def _request_action(self, receiver, action, *args, **kwargs):
		self._pending_actions.append((receiver, action, args, kwargs))

	def _stop_all_sounds(self):
		self._state_manager.send_cuia("ALL_SOUNDS_OFF")
		self._state_manager.stop_midi_playback()
		self._state_manager.stop_audio_player()

	def _on_shifted_override(self, override=None):
		if override is not None:
			self._is_shifted = override

	# FIXME: Could this be in chain_manager?
	def _get_chain_id_by_sequence(self, bank, seq):
		channel = self._libseq.getChannel(bank, seq, 0)
		return next(
			(id for id, c in self._chain_manager.chains.items()
				if c.midi_chan == channel),
			None
		)

	# FIXME: Could this (or part of this) be in zynseq?
	def _get_sequence_patterns(self, bank, seq, create=False):
		seq_len = self._libseq.getSequenceLength(bank, seq)
		pattern = -1
		retval = []

		if seq_len == 0:
			if create:
				pattern = self._libseq.createPattern()
				self._libseq.addPattern(bank, seq, 0, 0, pattern)
				retval.append(pattern)
			return retval

		n_tracks = self._libseq.getTracksInSequence(bank, seq)
		for track in range(n_tracks):
			retval.extend(self._get_patterns_in_track(bank, seq, track))
		return retval

	# FIXME: Could this be in libseq?
	def _get_patterns_in_track(self, bank, seq, track):
		retval = []
		n_patts = self._libseq.getPatternsInTrack(bank, seq, track)
		if n_patts == 0:
			return retval

		seq_len = self._libseq.getSequenceLength(bank, seq)
		pos = 0
		while pos < seq_len:
			pattern = self._libseq.getPatternAt(bank, seq, track, pos)
			if pattern != -1:
				retval.append(pattern)
				pos += self._libseq.getPatternLength(pattern)
			else:
				# Arranger's offset step is a quarter note (24 clocks)
				pos += 24
		return retval

	# FIXME: Could this be in libseq?
	def _add_pattern_to_end_of_track(self, bank, seq, track, pattern):
		pos = 0
		if self._libseq.getTracksInSequence(bank, seq) != 0:
			pos = self._libseq.getSequenceLength(bank, seq)
			while pos > 0:
				# Arranger's offset step is a quarter note (24 clocks)
				if self._libseq.getPatternAt(bank, seq, track, pos - 24) != -1:
					break
				pos -= 24

		return self._libseq.addPattern(bank, seq, track, pos, pattern)

	# FIXME: Could this be in zynseq?
	def _set_note_duration(self, step, note, duration):
		velocity = self._libseq.getNoteVelocity(step, note)
		stutt_count = self._libseq.getStutterCount(step, note)
		stutt_duration = self._libseq.getStutterDur(step, note)
		self._libseq.removeNote(step, note)
		self._libseq.addNote(step, note, velocity, duration)
		self._libseq.setStutterCount(step, note, stutt_count)
		self._libseq.setStutterDur(step, note, stutt_duration)

	# FIXME: This way avoids to show Zynpad every time, BUT is coupled to UI!
	def _show_pattern_editor(self, seq=None, skip_arranger=False):
		if self._current_screen != 'pattern_editor':
			self._state_manager.send_cuia("SCREEN_ZYNPAD")
		if seq is not None:
			self._select_pad(seq)
		if not skip_arranger:
			zynthian_gui_config.zyngui.screens["zynpad"].show_pattern_editor()
		else:
			zynthian_gui_config.zyngui.show_screen("pattern_editor")

	# FIXME: This is coupled to UI!
	def force_show_pattern_editor(self):
		self._refresh_pattern_editor()
		zynthian_gui_config.zyngui.show_screen("pattern_editor")

	# FIXME: This SHOULD be a CUIA, not this hack! (is coupled with UI)
	def _select_pad(self, pad):
		zynthian_gui_config.zyngui.screens["zynpad"].select_pad(pad)

	# This SHOULD not be coupled to UI! This is needed because when the pattern is changed in
	# zynseq, it is not reflected in pattern editor.
	def _refresh_pattern_editor(self):
		index = self._zynseq.libseq.getPatternIndex()
		zynthian_gui_config.zyngui.screens["pattern_editor"].load_pattern(index)

	# FIXME: This SHOULD not be coupled to UI!
	def _get_selected_sequence(self):
		return zynthian_gui_config.zyngui.screens["zynpad"].selected_pad

	# FIXME: This SHOULD not be coupled to UI!
	def _get_selected_step(self):
		pe = zynthian_gui_config.zyngui.screens["pattern_editor"]
		return pe.keymap[pe.selected_cell[1]]['note'], pe.selected_cell[0]

	# FIXME: This SHOULD be a CUIA, not this hack! (is coupled with UI)
	# NOTE: It runs in a thread to avoid lagging the hardware interface
	def _update_ui_arranger(self, cell_selected=(None, None)):
		def run():
			arranger = zynthian_gui_config.zyngui.screens["arranger"]
			arranger.select_cell(*cell_selected)
			if cell_selected[1] is not None:
				arranger.draw_row(cell_selected[1])
		Thread(target=run, daemon=True).start()

	def _show_screen_briefly(self, screen, cuia, timeout):
		# Only created when/if needed
		if self._timer is None:
			self._timer = RunTimer()

		timer_name = "change-screen"
		prev_screen = "BACK"

		# If brief screen is audio mixer, there is no back, so try to get the screen
		# name. Not all screens may be mapped, so it will fail there (only corner-cases).
		if screen == "audio_mixer":
			prev_screen = self.SCREEN_CUIA_MAP.get(self._current_screen, "BACK")

		if screen != self._current_screen:
			self._state_manager.send_cuia(cuia)
			self._timer.add(timer_name, timeout,
				lambda _: self._state_manager.send_cuia(prev_screen))
		else:
			self._timer.update(timer_name, timeout)
