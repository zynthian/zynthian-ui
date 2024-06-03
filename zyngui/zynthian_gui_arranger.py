#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Step-Sequencer Arranger Class
#
# Copyright (C) 2015-2024 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <brian@riban.co.uk>
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

import tkinter
import logging
import tkinter.font as tkfont
from time import monotonic, sleep
from threading import Timer
from math import sqrt
from collections import OrderedDict
import os

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zynlibs.zynsmf import zynsmf
from . import zynthian_gui_base
from zyncoder.zyncore import get_lib_zyncore
from zyngine import zynthian_engine
from zynlibs.zynseq import zynseq


# ------------------------------------------------------------------------------
# Zynthian Step-Sequencer Arranger GUI Class
# ------------------------------------------------------------------------------


# Local constants
SELECT_BORDER		= zynthian_gui_config.color_on
PLAYHEAD_CURSOR		= zynthian_gui_config.color_on
CANVAS_BACKGROUND	= zynthian_gui_config.color_panel_bg
CELL_BACKGROUND		= zynthian_gui_config.color_panel_bd
CELL_FOREGROUND		= zynthian_gui_config.color_panel_tx
GRID_LINE			= zynthian_gui_config.color_tx

PLAY_MODES = ['Disabled', 'Oneshot', 'Loop', 'Oneshot all', 'Loop all', 'Oneshot sync', 'Loop sync']


# Class implements step sequencer arranger
class zynthian_gui_arranger(zynthian_gui_base.zynthian_gui_base):

	# Function to initialise class
	def __init__(self):

		super().__init__()
		self.state_manager = self.zyngui.state_manager
		self.zynseq = self.state_manager.zynseq
		self.status_canvas.bind("<ButtonRelease-1>", self.cb_status_release)

		self.ctrl_order = zynthian_gui_config.layout['ctrl_order']

		self.sequence_tracks = []  # Array of [Sequence,Track] that are visible within bank
		self.sequence = 0  # Index of selected sequence
		self.track = 0  # Index of selected track
		
		self.vertical_zoom = self.zynseq.libseq.getVerticalZoom()  # Quantity of rows (tracks) displayed in grid
		self.horizontal_zoom = self.zynseq.libseq.getHorizontalZoom()  # Quantity of columns (time divisions) displayed in grid
		self.row_offset = 0  # Index of sequence_track at top row in grid
		self.col_offset = 0  # Index of time division at left column in grid
		self.selected_cell = [0, 0]  # Location of selected cell (time div, row)
		self.pattern = 1  # Index of current pattern to add to sequence
		self.pattern_to_add = 1  # Index of pattern to actually add (may be copied / moved pattern)
		self.position = 0  # Current playhead position
		self.grid_timer = Timer(1.0, self.on_grid_timer)  # Grid press and hold timer
		# TODO: Populate tracks from file
		self.sequence_drag_start = None  # Set to loaction of mouse during drag
		self.time_drag_start = None  # Set to time of click to test for bold click
		self.clocks_per_division = 24
		self.cells = [[None] * 2 for _ in range(self.vertical_zoom * self.horizontal_zoom)]  # 2D array of cells 0:cell, 1:cell label

		# Geometry vars
		self.timebase_track_height = int(self.height / 10)
		self.small_font_size = int(self.timebase_track_height / 3)
		self.select_thickness = 1 + int(self.width / 500)  # Scale thickness of select border based on screen resolution
		self.grid_height = self.height - self.timebase_track_height
		self.grid_width = int(self.width * 0.9)
		self.seq_track_title_width = self.width - self.grid_width
		self.sequence_title_width = int(0.4 * self.seq_track_title_width)
		self.track_title_width = self.seq_track_title_width - self.sequence_title_width
		self.update_cell_size()

		# Create sequence titles canvas
		self.sequence_title_canvas = tkinter.Canvas(self.main_frame,
			width=self.seq_track_title_width,
			height=self.grid_height,
			bg=CANVAS_BACKGROUND,
			bd=0,
			highlightthickness=0)
		self.sequence_title_canvas.bind("<ButtonPress-1>", self.on_sequence_drag_start)
		self.sequence_title_canvas.bind("<ButtonRelease-1>", self.on_sequence_drag_end)
		self.sequence_title_canvas.bind("<B1-Motion>", self.on_sequence_drag_motion)
		self.sequence_title_canvas.bind("<Button-4>", self.on_seq_mouse_scroll)
		self.sequence_title_canvas.bind("<Button-5>", self.on_seq_mouse_scroll)
		self.sequence_title_canvas.grid(column=0, row=0)

		# Create grid canvas
		self.grid_canvas = tkinter.Canvas(self.main_frame, 
				width=self.grid_width, 
				height=self.grid_height,
				bg=CANVAS_BACKGROUND,
				bd=0,
				highlightthickness=0)
		self.grid_canvas.grid(column=1, row=0)

		# Create pattern entry indicator
		self.pattern_canvas = tkinter.Canvas(self.main_frame,
				width=self.seq_track_title_width,
				height=self.timebase_track_height,
				bg=CELL_BACKGROUND,
				bd=0,
				highlightthickness=0)
		self.pattern_canvas.create_text(self.seq_track_title_width / 2, self.timebase_track_height / 2, tags="patternIndicator", fill="white", text=f"{self.pattern}", font=tkfont.Font(family=zynthian_gui_config.font_topbar[0], size=int(0.6 * self.timebase_track_height)))
		self.pattern_canvas.grid(column=0, row=1)
		self.pattern_canvas.bind('<ButtonPress-1>', self.on_pattern_click)

		# Create timebase track canvas
		self.timebase_track_canvas = tkinter.Canvas(self.main_frame,
				width=self.grid_width, 
				height=self.timebase_track_height,
				bg=CANVAS_BACKGROUND,
				bd=0,
				highlightthickness=0)
		self.timebase_track_canvas.bind("<ButtonPress-1>", self.on_time_drag_start)
		self.timebase_track_canvas.bind("<ButtonRelease-1>", self.on_time_drag_end)
		self.timebase_track_canvas.bind("<B1-Motion>", self.on_time_drag_motion)
		self.timebase_track_canvas.grid(column=1, row=1)

		self.bank = self.zynseq.bank  # Local copy so we know if it has changed and grid needs redrawing
		self.update_sequence_tracks()
		self.redraw_pending = 4   # 0:No refresh, 1:Refresh cell, 2:Refresh row, 3:Refresh grid, 4: Redraw grid

	# Function to set values of encoders
	def setup_zynpots(self):
		get_lib_zyncore().setup_behaviour_zynpot(zynthian_gui_config.ENC_LAYER, 0)
		get_lib_zyncore().setup_behaviour_zynpot(zynthian_gui_config.ENC_BACK, 0)
		get_lib_zyncore().setup_behaviour_zynpot(zynthian_gui_config.ENC_SNAPSHOT, 0)
		get_lib_zyncore().setup_behaviour_zynpot(zynthian_gui_config.ENC_SELECT, 0)

	# Function to add menus
	def show_menu(self):
		self.disable_param_editor()
		options = OrderedDict()
		options[f'Tempo ({self.zynseq.libseq.getTempo():0.1f})'] = 'Tempo'
		options['Beats per bar ({})'.format(self.zyngui.state_manager.zynseq.libseq.getBeatsPerBar())] = 'Beats per bar'
		options[f'Scene ({self.zynseq.bank})'] = 'Scene'
		options['> ARRANGER'] = None
		if self.zynseq.libseq.isMuted(self.zynseq.bank, self.sequence, self.track):
			options['Unmute track'] = 'Unmute track'
		else:
			options['Mute track'] = 'Mute track'
		options['MIDI channel ({})'.format(1 + self.zynseq.libseq.getChannel(self.zynseq.bank, self.sequence, self.track))] = 'MIDI channel'
		options['Vertical zoom ({})'.format(self.vertical_zoom)] = 'Vertical zoom'
		options['Horizontal zoom ({})'.format(self.horizontal_zoom)] = 'Horizontal zoom'
		options['Group ({})'.format(list(map(chr, range(65, 91)))[self.zynseq.libseq.getGroup(self.zynseq.bank, self.sequence)])] = 'Group'
		options['Play mode ({})'.format(zynseq.PLAY_MODES[self.zynseq.libseq.getPlayMode(self.zynseq.bank, self.sequence)])] = 'Play mode'
		options['Pattern ({})'.format(self.pattern)] = 'Pattern'
		options['Add track'] = 'Add track'
		if self.zynseq.libseq.getTracksInSequence(self.zynseq.bank, self.sequence) > 1:
			options['Remove track {}'.format(self.track + 1)] = 'Remove track'
		options['Clear sequence'] = 'Clear sequence'
		options['Clear scene'] = 'Clear scene'
		options['Import SMF'] = 'Import SMF'
		self.zyngui.screens['option'].config("Arranger Menu", options, self.menu_cb)
		self.zyngui.show_screen('option')

	def toggle_menu(self):
		if self.shown:
			self.show_menu()
		elif self.zyngui.current_screen == "option":
			self.close_screen()

	def menu_cb(self, option, params):
		if params == 'Tempo':
			self.zyngui.show_screen('tempo')
		elif params == 'Beats per bar':
			self.enable_param_editor(self, 'bpb', {'name': 'Beats per bar', 'value_min': 1, 'value_max': 64, 'value_default': 4, 'value': self.zynseq.libseq.getBeatsPerBar()})
		elif params == 'Scene':
			self.enable_param_editor(self, 'scene', {'name': 'Scene', 'value_min': 1, 'value_max': 64, 'value': self.zynseq.bank})
		elif 'ute track' in params:
			self.toggle_mute()
		elif params == 'MIDI channel':
			labels = []
			for midi_chan in range(16):
				preset_name = self.zyngui.chain_manager.get_synth_preset_name(midi_chan)
				if preset_name:
					labels.append(f"{midi_chan + 1} ({preset_name})")
				else:
					labels.append(f"{midi_chan + 1}")
			self.enable_param_editor(self, 'midi_chan', {'name': 'MIDI channel', 'labels': labels, 'value_default': self.zynseq.libseq.getChannel(self.zynseq.bank, self.sequence, self.track), 'value': self.zynseq.libseq.getChannel(self.zynseq.bank, self.sequence, self.track)})
		elif params == 'Play mode':
			self.enable_param_editor(self, 'playmode', {'name': 'Play mode', 'labels': zynseq.PLAY_MODES, 'value': self.zynseq.libseq.getPlayMode(self.zynseq.bank, self.sequence), 'value_default': zynseq.SEQ_LOOPALL})
		elif params == 'Vertical zoom':
			self.enable_param_editor(self, 'vzoom', {'name': 'Vertical zoom', 'value_min': 1, 'value_max': 127, 'value_default': 8, 'value': self.vertical_zoom})
		elif params == 'Horizontal zoom':
			self.enable_param_editor(self, 'hzoom', {'name': 'Horizontal zoom', 'value_min': 1, 'value_max': 64, 'value_default': 16, 'value': self.horizontal_zoom})
		elif params == 'Group':
			self.enable_param_editor(self, 'group', {'name': 'Group', 'labels': list(map(chr, range(65, 91))), 'default': self.zynseq.libseq.getGroup(self.zynseq.bank, self.sequence), 'value': self.zynseq.libseq.getGroup(self.zynseq.bank, self.sequence)})
		elif params == 'Pattern':
			self.enable_param_editor(self, 'pattern', {'name': 'Pattern', 'value_min': 1, 'value_max': zynseq.SEQ_MAX_PATTERNS, 'value_default': self.pattern, 'value': self.pattern})
		elif params == 'Add track':
			self.add_track()
		elif params == 'Remove track':
			self.remove_track()
		elif params == 'Clear sequence':
			self.clear_sequence()
		elif params == 'Clear scene':
			self.zyngui.show_confirm(f"Clear all sequences from scene {self.zynseq.bank} and reset to 4x4 grid of new sequences?\n\nThis will also remove all patterns and tracks from sequences in scene.", self.do_clear_bank)
		elif params == 'Import SMF':
			self.select_smf()

	def send_controller_value(self, zctrl):
		if zctrl.symbol == 'scene':
			self.zynseq.select_bank(zctrl.value)
			#self.title = "Scene {}".format(self.zynseq.bank)
			self.bank = self.zynseq.bank
			self.update_sequence_tracks()
			self.redraw_pending = 4
		elif zctrl.symbol == 'tempo':
			self.zynseq.libseq.setTempo(zctrl.value)
		if zctrl.symbol == 'metro_vol':
			self.zynseq.libseq.setMetronomeVolume(zctrl.value / 100.0)
		elif zctrl.symbol == 'bpb':
			self.zynseq.set_beats_per_bar(zctrl.value)
			self.draw_vertical_lines()
		elif zctrl.symbol == 'midi_chan':
			self.zynseq.set_midi_channel(self.zynseq.bank, self.sequence, self.track, zctrl.value)
			self.draw_sequence_label(self.selected_cell[1] - self.row_offset)
		elif zctrl.symbol == 'playmode':
			self.zynseq.set_play_mode(self.zynseq.bank, self.sequence, zctrl.value)
		elif zctrl.symbol == 'vzoom':
			self.vertical_zoom = zctrl.value
			self.zynseq.libseq.setVerticalZoom(zctrl.value)
			self.redraw_pending = 4
		elif zctrl.symbol == 'hzoom':
			self.horizontal_zoom = zctrl.value
			self.zynseq.libseq.setHorizontalZoom(zctrl.value)
			self.update_cell_size()
			self.redraw_pending = 3
		elif zctrl.symbol == 'group':
			self.zynseq.set_group(self.zynseq.bank, self.sequence, zctrl.value)
			self.redraw_pending = 2
		elif zctrl.symbol == 'pattern':
			self.set_pattern(zctrl.value)

	# Function to toggle mute of selected track
	def toggle_mute(self, params=None):
		self.zynseq.libseq.toggleMute(self.zynseq.bank, self.sequence, self.track)
		self.redraw_pending = 2

	# Function to actually clear bank
	def do_clear_bank(self, params=None):
		self.zynseq.libseq.clearBank(self.zynseq.bank)
		self.zynseq.select_bank(self.zynseq.bank, True)
		self.update_sequence_tracks()
		self.zynseq.libseq.setPlayPosition(self.zynseq.bank, self.sequence, 0)
		self.redraw_pending = 4

	# Function to clear sequence
	def clear_sequence(self, params=None):
		name = self.zynseq.get_sequence_name(self.zynseq.bank, self.sequence)
		if len(name) == 0:
			name = f"{self.sequence + 1}"
		self.zyngui.show_confirm(f"Clear all tracks and patterns from sequence '{name}'?", self.do_clear_sequence)

	# Function to actually clear selected sequence
	def do_clear_sequence(self, params=None):
		self.zynseq.libseq.clearSequence(self.zynseq.bank, self.sequence)
		self.update_sequence_tracks()
		self.redraw_pending = 4

	# Function to add track to selected sequence immediately after selected track
	def add_track(self, params=None):
		self.zynseq.libseq.addTrackToSequence(self.zynseq.bank, self.sequence, self.track)
		self.update_sequence_tracks()
		self.redraw_pending = 4

	# Function to remove selected track
	def remove_track(self, params=None):
		self.zyngui.show_confirm("Remove track {} from sequence {}?".format(self.track + 1, self.sequence + 1), self.do_remove_track)

	# Function to actually remove selected track
	def do_remove_track(self, params=None):
		self.zynseq.libseq.removeTrackFromSequence(self.zynseq.bank, self.sequence, self.track)
		self.update_sequence_tracks()
		self.redraw_pending = 4

	# Function to import SMF
	def select_smf(self, params=None):
		file_list = zynthian_engine.get_filelist(os.environ.get('ZYNTHIAN_MY_DATA_DIR', '/zynthian/zynthian-my-data') + '/capture', 'mid')
		options = OrderedDict()
		for i in file_list:
			options[i[4]] = i[0]
		self.zyngui.screens['option'].config("Import SMF", options, self.smf_file_cb)
		self.zyngui.show_screen('option')

	# Function to  check if SMF will overwrite tracks in sequence
	#  fname: Filename
	#  fpath: Full file path of SMF to import
	def smf_file_cb(self, fname, fpath):
		#logging.warning(f"Seq len:{self.zynseq.libseq.getSequenceLength(self.zynseq.bank, self.sequence)} pos:{self.selected_cell[0]}")
		if self.zynseq.libseq.getSequenceLength(self.zynseq.bank, self.sequence) > self.selected_cell[0] * 24:
			self.zyngui.show_confirm("Import will overwrite part of existing sequence. Do you want to continue?", self.do_import_smf, fpath)
		else:
			self.do_import_smf(fpath)

	# Function to actually import SMF
	def do_import_smf(self, fpath):
		smf = zynsmf.libsmf.addSmf()
		if not zynsmf.load(smf, fpath):
			logging.warning(f"Failed to load file {fpath}")
			return
		event_count = zynsmf.libsmf.getEvents(smf, -1)
		if event_count == 0:
			return
		self.zyngui.show_info("Importing SMF...")
		event_index = 0
		event_next_update = 0
		event_inc = event_count // 100 + 1
		progress = 0
		progress_step = event_inc * 100 / event_count
		pattern_count = 0
		bank = self.zynseq.bank
		sequence = self.sequence
		ticks_per_beat = zynsmf.libsmf.getTicksPerQuarterNote(smf)
		steps_per_beat = 24
		ticks_per_step = ticks_per_beat / steps_per_beat
		beats_in_pattern = self.zynseq.libseq.getBeatsPerBar()
		ticks_in_pattern = beats_in_pattern * ticks_per_beat
		clocks_per_step = 1 # For 24 steps per beat
		ticks_per_clock = ticks_per_step / clocks_per_step
		empty_tracks = [False for i in range(16)]  # Array of boolean flags indicating if track should be removed at end of import
		#self.zynseq.libseq.clearSequence(bank, sequence)  # TODO Do not clear sequence, get sequence length, start at next bar position or current cursor position

		# Add tracks to populate - we will delete unpopulated tracks at end
		for track in range(16):
			if self.zynseq.libseq.getChannel(bank, sequence, track) != track:
				self.zynseq.libseq.addTrackToSequence(bank, sequence, track - 1)
				self.zynseq.libseq.setChannel(bank, sequence, track, track)
				empty_tracks[track] = True

		# Do import
		zynsmf.libsmf.setPosition(smf, 0)
		# Create arrays to hold currently processing element for each MIDI channel
		pattern = [None for i in range(16)]
		note_on = [0x90 | channel for channel in range(16)]
		note_off = [0x80 | channel for channel in range(16)]
		note_on_info = [[[None, None, None, None] for i in range(127)] for i in range(16)]  # Array of [pattern,time,velocity,step] indicating time that note on event received for matching note off and deriving duration
		pattern_position = [self.selected_cell[0] * ticks_per_beat for i in range(16)]   # Position of current pattern within track in ticks

		while zynsmf.libsmf.getEvent(smf, True):
			event_index += 1
			if event_index > event_next_update:
				progress += progress_step
				self.zyngui.add_info(f"\nImporting SMF - {int(progress)}%")
				event_next_update += event_inc
			type = zynsmf.libsmf.getEventType()
			time = zynsmf.libsmf.getEventTime()
			status = zynsmf.libsmf.getEventStatus()
			if type == 0x01:
				# MIDI event
				channel = zynsmf.libsmf.getEventChannel()
				note = zynsmf.libsmf.getEventValue1()
				velocity = zynsmf.libsmf.getEventValue2()
				if status in note_on and velocity:
					# Found note-on event
					if time >= pattern_position[channel] + ticks_in_pattern or pattern[channel] is None:
						# Create new pattern
						while time >= pattern_position[channel] + ticks_in_pattern:
							pattern_position[channel] += ticks_in_pattern
						pattern[channel] = self.zynseq.libseq.createPattern()
						self.zynseq.libseq.selectPattern(pattern[channel])
						self.zynseq.libseq.setBeatsInPattern(beats_in_pattern)
						self.zynseq.libseq.setStepsPerBeat(steps_per_beat)
						position = int(pattern_position[channel] / ticks_per_clock)
						self.zynseq.libseq.addPattern(bank, sequence, channel, position, pattern[channel], True)
						pattern_count += 1
					step = int((time - pattern_position[channel]) / ticks_per_step)
					note_on_info[channel][note] = [pattern[channel], time, velocity, step]
					self.zynseq.libseq.selectPattern(pattern[channel])
					self.zynseq.libseq.addNote(step, note, velocity, 1, 0)  # Add short event, may overwrite later when note-off detected
				elif status in note_off or status in note_on and velocity == 0:
					# Found note-off event
					if note_on_info[channel][note][0] is None:
						continue  # Do not have corresponding note-on for this note-off event
					current_pattern = pattern[channel]
					old_pattern = note_on_info[channel][note][0]
					trigger_time = note_on_info[channel][note][1]
					velocity = note_on_info[channel][note][2]
					step = note_on_info[channel][note][3]
					self.zynseq.libseq.selectPattern(old_pattern)
					duration = int((time - trigger_time) / ticks_per_step)
					if duration < 1:
						duration = 1
					self.zynseq.libseq.addNote(step, note, velocity, duration, 0)
					note_on_info[channel][note] = [None, None, None, None]
					pattern[channel] = current_pattern
					self.zynseq.libseq.selectPattern(pattern[channel])
				if empty_tracks[channel]:
					empty_tracks[channel] = False

		self.zyngui.add_info("\n\nSMF import complete - {} patterns added\n\n".format(pattern_count))

		# Remove empty tracks
		for track in range(15, -1, -1):
			if empty_tracks[track]:
				self.zynseq.libseq.removeTrackFromSequence(bank, sequence, track)
		
		zynsmf.libsmf.removeSmf(smf)
		self.update_sequence_tracks()
		self.redraw_pending = 4
		self.zyngui.hide_info_timer()

	# Handle resize event
	def update_layout(self):
		super().update_layout()
		self.redraw_pending = 4
		self.draw_grid()

	# Function to show GUI
	def build_view(self):
		self.vertical_zoom = self.zynseq.libseq.getVerticalZoom()
		self.horizontal_zoom = self.zynseq.libseq.getHorizontalZoom()
		self.setup_zynpots()
		if not self.param_editor_zctrl:
			self.set_title(f"Scene {self.zynseq.bank}")
		self.redraw_pending = 3
		self.bank = self.zynseq.bank
		self.title = f"Scene {self.bank}"
		self.update_sequence_tracks()
		self.redraw_pending = 4
		self.select_position()
		return True

	# Function to hide GUI
	def hide(self):
		super().hide()

	# Function to set current pattern
	def set_pattern(self, pattern):
		if pattern < 1:
			self.pattern = 1
		elif pattern > 999:
			pattern = 999
		else:
			self.pattern = pattern
		self.pattern_canvas.itemconfig("patternIndicator", text=f"{self.pattern}")
		self.pattern_to_add = self.pattern
		self.select_cell()

	# Function to get quantity of sequences in bank
	#  returns: Quantity of sequences in bank
	def get_seqeuences(self):
		return self.zynseq.libseq.getSequencesInBank(self.zynseq.bank)

	# Function to handle start of sequence drag
	def on_sequence_drag_start(self, event):
		if self.param_editor_zctrl:
			self.disable_param_editor()
			return
		if self.zynseq.libseq.getSequencesInBank(self.zynseq.bank) > self.vertical_zoom:
			self.sequence_drag_start = event

	# Function to handle sequence drag motion
	def on_sequence_drag_motion(self, event):
		if not self.sequence_drag_start:
			return
		offset = int((event.y - self.sequence_drag_start.y) / self.row_height)
		if not offset:
			return
		self.sequence_drag_start.y = event.y
		pos = self.row_offset - offset
		if pos < 0:
			pos = 0
		if pos + self.vertical_zoom >= self.zynseq.libseq.getSequencesInBank(self.zynseq.bank):
			pos = self.zynseq.libseq.getSequencesInBank(self.zynseq.bank) - self.vertical_zoom
		if self.row_offset == pos:
			return
		self.row_offset = pos
		sequence = self.selected_cell[1]
		if self.selected_cell[1] < self.row_offset:
			sequence = self.row_offset
		elif self.selected_cell[1] >= self.row_offset + self.vertical_zoom:
			sequence = self.row_offset + self.vertical_zoom - 1
		self.select_cell(self.selected_cell[0], sequence, False)
		self.redraw_pending = 4

	# Function to handle end of sequence drag
	def on_sequence_drag_end(self, event):
		self.sequence_drag_start = None

	# Function to handle mouse wheel on sequence titles
	def on_seq_mouse_scroll(self, event):
		if event.num == 4:
			# Scroll up
			# TODO: Need to validate vertical range of tracks, not sequences
			if self.row_offset + self.vertical_zoom < self.zynseq.libseq.getSequencesInBank(self.zynseq.bank):
				self.row_offset += 1
				if self.selected_cell[1] < self.row_offset:
					self.select_cell(self.selected_cell[0], self.row_offset)
				self.redraw_pending = 4
		else:
			# Scroll down
			if self.row_offset: 
				self.row_offset -= 1
				if self.selected_cell[1] >= self.row_offset + self.vertical_zoom:
					self.select_cell(self.selected_cell[0], self.row_offset + self.vertical_zoom - 1)
				self.redraw_pending = 4

	# Function to handle start of time drag
	def on_time_drag_start(self, event):
		if self.param_editor_zctrl:
			self.disable_param_editor()
			return
		self.time_drag_start = event

	# Function to handle time drag motion
	def on_time_drag_motion(self, event):
		if not self.time_drag_start:
			return
		offset = int((self.time_drag_start.x - event.x) / self.column_width)
		if not offset:
			return
		self.time_drag_start.x = event.x
		pos = self.col_offset + offset
		if pos < 0:
			pos = 0
		if self.col_offset == pos:
			return
		self.col_offset = pos
		self.redraw_pending = 3
		duration = int(self.zynseq.libseq.getPatternLength(self.pattern_to_add) / self.clocks_per_division)
		if self.selected_cell[0] < self.col_offset:
			self.select_cell(self.col_offset, self.selected_cell[1])
		elif self.selected_cell[0] > self.col_offset + self.horizontal_zoom - duration:
			self.select_cell(self.col_offset + self.horizontal_zoom - duration, self.selected_cell[1])
		else:
			self.select_cell()

	# Function to handle end of time drag
	def on_time_drag_end(self, event):
		self.time_drag_start = None

	# Function to handle grid mouse press
	#  event: Mouse event
	def on_grid_press(self, event):
		if self.param_editor_zctrl:
			self.disable_param_editor()
			return

		self.grid_timer = Timer(1.2, self.on_grid_timer)
		self.grid_timer.start()
		tags = self.grid_canvas.gettags(self.grid_canvas.find_withtag(tkinter.CURRENT))
		if not tags:
			return
		c, r = tags[0].split(',')
		self.source_col = self.col_offset + int(event.x / self.column_width)
		self.source_row = self.row_offset + int(event.y / self.row_height)
		self.select_cell(self.col_offset + int(c), self.row_offset + int(r), False)
		self.source_col = self.selected_cell[0]
		self.source_seq = self.sequence
		self.source_track = self.track
		self.pattern_to_add = self.zynseq.libseq.getPattern(self.zynseq.bank, self.sequence, self.track, self.source_col * self.clocks_per_division)
		if self.pattern_to_add == -1:
			self.pattern_to_add = self.pattern

	# Function to handle grid mouse release
	#  event: Mouse event
	def on_grid_release(self, event):
		if self.grid_timer.is_alive():
			# Haven't moved cursor so just toggle current pattern
			self.toggle_event(self.selected_cell[0], self.selected_cell[1])
			self.grid_timer.cancel()
			return
		self.grid_timer.cancel()
		if self.add_event(self.selected_cell[0], self.sequence, self.track):
			if self.source_col != self.selected_cell[0] or self.source_row != self.selected_cell[1]:
				self.remove_event(self.source_col, self.source_seq, self.source_track)
				self.draw_row(self.source_seq - self.row_offset)
		else:
			self.select_cell(self.source_col, self.source_row) # Failed to add pattern so reselect original cells
		self.pattern_to_add = self.pattern

	# Function to handle grid mouse motion
	#  event: Mouse event
	def on_grid_drag(self, event):
		col = self.col_offset + int(event.x / self.column_width)
		row = self.row_offset + int(event.y / self.row_height)
		if col < self.col_offset or col >= self.col_offset + self.horizontal_zoom or row < self.row_offset or row >= self.row_offset + self.vertical_zoom:
			return  # Avoid scrolling display
		if self.grid_timer.is_alive():
			if col == self.source_col and row == self.source_row:
				return  # Haven't moved from original cell
			self.grid_timer.cancel()
			time = self.selected_cell[0] * self.clocks_per_division
			self.pattern_to_add = self.zynseq.libseq.getPattern(self.zynseq.bank, self.sequence, self.track, time)
			if self.pattern_to_add == -1:
				self.pattern_to_add = self.pattern
		if col != self.selected_cell[0] or row != self.selected_cell[1]:
			self.select_cell(col, row, False, False)  # Move selection to show wireframe of moving (dragging) pattern

	# Function to handle grid press and hold
	def on_grid_timer(self):
		self.pattern_to_add = self.pattern
		self.show_pattern_editor()

	# Function to show pattern editor
	def show_pattern_editor(self):
		time = self.selected_cell[0] * self.clocks_per_division # time in clock cycles
		pattern = self.zynseq.libseq.getPattern(self.zynseq.bank, self.sequence, self.track, time)
		channel = self.zynseq.libseq.getChannel(self.zynseq.bank, self.sequence, self.track)
		if pattern > 0:
			self.zyngui.screens['pattern_editor'].channel = channel
			self.zyngui.screens['pattern_editor'].load_pattern(pattern)
			self.zynseq.libseq.enableMidiRecord(False)
			self.zyngui.screens['pattern_editor'].bank = 0
			self.zyngui.screens['pattern_editor'].sequence = 0
			self.zynseq.libseq.enableMidiRecord(False)
			self.zyngui.show_screen("pattern_editor")
			return True

	# Function to handle pattern click
	#  event: Mouse event
	def on_pattern_click(self, event):
		if zynthian_gui_config.enable_touch_widgets:
			self.enable_param_editor('Pattern')  # TODO: Populate parameters

	# Toggle playback of selected sequence
	def toggle_play(self):
		#if self.zynseq.libseq.getPlayState(self.zynseq.bank, self.sequence) == zynseq.SEQ_STOPPED:
		#	bars = int(self.selected_cell[0] / self.zynseq.libseq.getBeatsPerBar())
		#	pos = bars * self.zynseq.libseq.getBeatsPerBar() * self.clocks_per_division
		#	if self.zynseq.libseq.getSequenceLength(self.zynseq.bank, self.sequence) > pos:
		#		self.zynseq.libseq.setPlayPosition(self.zynseq.bank, self.sequence, pos)
		self.zynseq.libseq.togglePlayState(self.zynseq.bank, self.sequence)

	# Function to toggle note event
	#  col: Grid column relative to start of song
	#  row: Grid row
	def toggle_event(self, col, row):
		time = col * self.clocks_per_division
		if self.zynseq.libseq.getPattern(self.zynseq.bank, self.sequence, self.track, time) == -1:
			self.add_event(col, self.sequence, self.track)
		else:
			self.remove_event(col, self.sequence, self.track)
		self.select_cell(col, row)

	# Function to remove an event
	#  col: Time division index (column + columun offset)
	#  sequence: Sequence number
	#  track: Track within sequence
	def remove_event(self, col, sequence, track):
		time = col * self.clocks_per_division
		self.zynseq.remove_pattern(self.zynseq.bank, sequence, track, time)
		self.redraw_pending = 2

	# Function to add an event
	#  col: Time division index (column + columun offset)
	#  sequence: Sequence number
	#  track: Track within sequence
	#  returns: True on success
	def add_event(self, col, sequence, track):
		time = col * self.clocks_per_division
		if self.zynseq.add_pattern(self.zynseq.bank, sequence, track, time, self.pattern_to_add):
			self.redraw_pending = 2
			return True
		return False

	# Function to draw seqeuence / track labels
	#  row: Row (0..vertical zoom)
	def draw_sequence_label(self, row):
		if row >= self.vertical_zoom:
			return
		self.sequence_title_canvas.delete(f"rowtitle:{row}")
		self.sequence_title_canvas.delete(f"rowback:{row}")

		if row + self.row_offset > len(self.sequence_tracks):
			return
		sequence = self.sequence_tracks[row + self.row_offset][0]
		track = self.sequence_tracks[row + self.row_offset][1]
		group = self.zynseq.libseq.getGroup(self.zynseq.bank, sequence)
		fill = zynthian_gui_config.PAD_COLOUR_GROUP_LIGHT[group % 16]
		font = tkfont.Font(family=zynthian_gui_config.font_topbar[0], size=self.fontsize)
		midi_chan = self.zynseq.libseq.getChannel(self.zynseq.bank, sequence, track)
		track_name = self.zyngui.chain_manager.get_synth_preset_name(midi_chan)

		self.sequence_title_canvas.create_rectangle(0, self.row_height * row + 1, 
			self.seq_track_title_width, (1 + row) * self.row_height - 1, tags=(f"rowback:{row}", "sequence_title"),
			fill=fill)
		if track == 0 or row == 0:
			# Create sequence title label from first visible track of sequence
			self.sequence_title_canvas.create_text((0, self.row_height * row + 1),
				font=font, fill=CELL_FOREGROUND, tags=(f"rowtitle:{row}", "sequence_title"), anchor="nw",
				text=self.zynseq.get_sequence_name(self.zynseq.bank, sequence))
			self.grid_canvas.delete(f"playheadline-{row}")
			self.grid_canvas.create_line(0, self.row_height * (row + 1), 0, self.row_height * row, fill=PLAYHEAD_CURSOR, tags=("playheadline", f"playheadline-{row}"), state='hidden')
		else:
			# Don't show track number on track 1 to allow sequence name to be longer and simplify display when single tracks are use
			self.sequence_title_canvas.create_text((self.seq_track_title_width - 2, self.row_height * row + 1),
				font=font, fill=CELL_FOREGROUND, tags=(f"rowtitle:{row}", "sequence_title"), anchor="ne",
				text=f"{track + 1}")
		self.sequence_title_canvas.create_text((0, self.row_height * (row + 1) - 1),
			font=tkfont.Font(family=zynthian_gui_config.font_topbar[0], size=int(self.fontsize * 0.9)),
			fill=CELL_FOREGROUND, tags=(f"rowtitle:{row}", "sequence_title"), anchor="sw",
			text=f"{track_name}")
		self.sequence_title_canvas.tag_bind('sequence_title', "<Button-1>", self.on_sequence_click)

	# Function to draw a grid row
	#  row: Grid row to draw (0..vertical zoom)
	#  redraw_sequence_titles: True to redraw sequence titles (Default: True)
	def draw_row(self, row, redraw_sequence_titles=True):
		if row >= len(self.sequence_tracks):
			return
		if redraw_sequence_titles:
			self.draw_sequence_label(row)
		for col in range(self.horizontal_zoom):
			self.draw_cell(col, row)

	# Function to handle sequence title click
	def on_sequence_click(self, event):
		elms = self.sequence_title_canvas.find_withtag(tkinter.CURRENT)
		tags = self.sequence_title_canvas.gettags(elms)
		if not tags:
			return
		dummy, seq_track = tags[0].split(':')
		row = int(seq_track) + self.row_offset
		self.selected_cell[1] = row
		self.select_cell()

	# Function to get cell coordinates
	#  col: Column index
	#  row: Row index
	#  duration: Duration of cell in time divisions
	#  return: Coordinates required to draw cell
	def get_cell_coord(self, col, row, duration):
		x1 = col * self.column_width + 1
		y1 = self.row_height * row + 1
		x2 = x1 + self.column_width * duration - 1 
		y2 = y1 + self.row_height - 1
		return [x1, y1, x2, y2]

	# Function to draw a grid cell
	#  col: Column index (0..horizontal zoom)
	#  row: Row index (0..vertical zoom)
	def draw_cell(self, col, row):
		if row >= self.vertical_zoom:
			return
		cell_index = row * self.horizontal_zoom + col  # Cells are stored in array sequentially: 1st row, 2nd row...
		if cell_index >= len(self.cells):
			return

		sequence = self.sequence_tracks[row + self.row_offset][0]
		track = self.sequence_tracks[row + self.row_offset][1]
		time = (self.col_offset + col) * self.clocks_per_division  # time in clock cycles

		pattern = self.zynseq.libseq.getPattern(self.zynseq.bank, sequence, track, time)
		if pattern == -1 and col == 0:
			# Search for earlier pattern that extends into view
			pattern = self.zynseq.libseq.getPatternAt(self.zynseq.bank, sequence, track, time)
			if pattern != -1:
				duration = int(self.zynseq.libseq.getPatternLength(pattern) / self.clocks_per_division)
				while time > 0 and duration > 1:
					time -= self.clocks_per_division
					duration -= 1
					if pattern == self.zynseq.libseq.getPattern(self.zynseq.bank, sequence, track, time):
						break
		elif pattern != -1:
			duration = int(self.zynseq.libseq.getPatternLength(pattern) / self.clocks_per_division)
		if pattern == -1:
			duration = 1
			fill = CANVAS_BACKGROUND
		elif self.zynseq.libseq.isMuted(self.zynseq.bank, sequence, track):
			fill = zynthian_gui_config.PAD_COLOUR_DISABLED
		else:
			fill = CELL_BACKGROUND
		if col + duration > self.col_offset + self.horizontal_zoom:
			duration = self.col_offset + self.horizontal_zoom - col
		if duration < 1:
			duration = 1

		cell = self.cells[cell_index][0]
		celltext = self.cells[cell_index][1]
		coord = self.get_cell_coord(col, row, duration)
		if not cell:
			# Create new cell
			cell = self.grid_canvas.create_rectangle(coord, fill=fill, width=0, tags=(f"{col},{row}", "gridcell", "pattern"))
			celltext = self.grid_canvas.create_text(coord[0] + 1, coord[1] + self.row_height / 2, fill=CELL_FOREGROUND, tags=(f"{col},{row}", "pattern"))
			self.grid_canvas.tag_bind("pattern", '<ButtonPress-1>', self.on_grid_press)
			self.grid_canvas.tag_bind("pattern", '<ButtonRelease-1>', self.on_grid_release)
			self.grid_canvas.tag_bind("pattern", '<B1-Motion>', self.on_grid_drag)
			self.grid_canvas.tag_lower(cell)  # Assume cells are always created left to right
			self.cells[cell_index][0] = cell
			self.cells[cell_index][1] = celltext
		# Update existing cell
		else:
			self.grid_canvas.itemconfig(cell, fill=fill)
			self.grid_canvas.coords(cell, coord)
		if pattern == -1:
			self.grid_canvas.itemconfig(celltext, state='hidden')
		else:
			self.grid_canvas.itemconfig(celltext, text=pattern, state='normal', font=tkfont.Font(family=zynthian_gui_config.font_topbar[0], size=self.fontsize))
			self.grid_canvas.coords(celltext, coord[0] + int(duration * self.column_width / 2), int(coord[1] + self.row_height / 2))
			#if time + duration > self.horizontalZoom:
			#	if duration > 1:
			#		self.grid_canvas.itemconfig(f"lastpatterntext{row}", text=f"+{duration - self.zynseq.libseq.getPatternLength() + time}", state="normal")

	# Function to draw grid
	def draw_grid(self):
		if self.redraw_pending == 1:
			# Refresh cell
			self.redraw_pending = 0
			#self.grid_canvas.itemconfig("{},{}".format(self.selected_cell[0], self.selected_cell[1]), fill=CANVAS_BACKGROUND)
			self.draw_cell(self.selected_cell[0] - self.col_offset, self.selected_cell[1] - self.row_offset)
			return
		elif self.redraw_pending == 2:
			# Refresh row
			self.redraw_pending = 0
			#for column in range(self.horizontal_zoom):
			#	self.grid_canvas.itemconfig("{},{}".format(column, self.selected_cell[1]), fill=CANVAS_BACKGROUND)
			self.draw_row(self.selected_cell[1] - self.row_offset, True)
			return
		elif self.redraw_pending == 3:
			# Refresh grid
			pass
		elif self.redraw_pending == 4:
			# Redraw grid
			self.grid_canvas.delete(tkinter.ALL)
			self.sequence_title_canvas.delete(tkinter.ALL)
			self.column_width = self.grid_width / self.horizontal_zoom
			self.cells = [[None] * 2 for _ in range(self.vertical_zoom * self.horizontal_zoom)]
			self.update_cell_size()

		self.redraw_pending = 0

		# Draw rows of grid
		self.grid_canvas.itemconfig("gridcell", fill=CANVAS_BACKGROUND)
		for row in range(0, self.vertical_zoom):
			if row + self.row_offset >= len(self.sequence_tracks):
				break
			self.draw_row(row, True)

		self.draw_vertical_lines()

		# Hide selection if not in view - #TODO: WHEN WOULD THAT BE???
		if self.selected_cell[0] < self.col_offset or self.selected_cell[0] > self.col_offset + self.horizontal_zoom or self.selected_cell[1] < self.row_offset or self.selected_cell[1] > self.row_offset + self.vertical_zoom:
			self.grid_canvas.itemconfig('selection', state='hidden')

		# Timebase track
		self.timebase_track_canvas.delete('bpm')
		'''
		#TODO: Implement timebase events - not yet implemented in library
		for event in range(self.zynseq.libseq.getTimebaseEvents(self.zynseq.bank)):
			time = self.zynseq.libseq.getTimebaseEventTime(self.zynseq.bank, event) / self.clocks_per_division
			if time >= self.col_offset and time <= self.col_offset + self.horizontal_zoom:
				command = self.zynseq.libseq.getTimebaseEventCommand(self.zynseq.bank, event)
				if command == 1: # Tempo
					tempoX = (time - self.col_offset) * self.column_width
					data = self.zynseq.libseq.getTimebaseEventData(self.zynseq.bank, event)
					if tempoX:
						self.timebase_track_canvas.create_text(tempoX, tempo_y, fill='red', text=data, anchor='n', tags='bpm')
					else:
						self.timebase_track_canvas.create_text(tempoX, tempo_y, fill='red', text=data, anchor='nw', tags='bpm')
		'''
		self.grid_canvas.tag_lower('barlines')
		self.select_cell()

	def draw_vertical_lines(self):
		# Vertical (bar / sync) lines
		self.grid_canvas.delete('barlines')
		self.timebase_track_canvas.delete('barlines')
		font = tkfont.Font(size=self.small_font_size)
		tempo_y = font.metrics('linespace')
		offset = 0 - int(self.col_offset % self.horizontal_zoom)
		for bar in range(offset, self.horizontal_zoom, self.zynseq.libseq.getBeatsPerBar()):
			self.grid_canvas.create_line(bar * self.column_width, 0, bar * self.column_width, self.grid_height, fill='#808080', tags='barlines')
			if bar:
				self.timebase_track_canvas.create_text(bar * self.column_width, 0, fill='white', text=f"{bar+self.col_offset}", anchor='n', tags='barlines')
			else:
				self.timebase_track_canvas.create_text(bar * self.column_width, 0, fill='white', text=f"{bar+self.col_offset}", anchor='nw', tags='barlines')

	# Function to move selection to specified position
	#  sequence: Index of sequence (Default is reselect current sequence)
	#  track: Index of track (Default is reselect current track)
	#  time: Position in timeline (Default is None to keep current time)
	# If track not available then selects first track in sequence
	def select_position(self, sequence=None, track=None, time=None):
		found_row = None
		if track is None:
			track = self.track
		if sequence is None:
			sequence = self.sequence
		for row, seqtrack in enumerate(self.sequence_tracks):
			if seqtrack[0] == sequence:
				if found_row is None:
					found_row = row
				if seqtrack[1] == track:
					found_row = row
					break
		if found_row is None:
			return False
		self.select_cell(time, found_row)

	# Function to select a cell within the grid
	#  time: Time (column) of selected cell (Optional - default to reselect current column)
	#  row: Row of selected cell (0..quantity of tracks. Optional - default to reselect current row)
	#  snap: True to snap to closest pattern (Optional - default True)
	#  scroll: True to scroll to show selected cell (Optional - default True)
	def select_cell(self, time=None, row=None, snap=True, scroll=True):
		if time is None:
			time = self.selected_cell[0]
		if row is None:
			row = self.selected_cell[1]
		if row >= len(self.sequence_tracks):
			row = len(self.sequence_tracks) - 1
		if row < 0:
			row = 0
		duration = int(self.zynseq.libseq.getPatternLength(self.pattern_to_add) / self.clocks_per_division)
		sequence = self.sequence_tracks[row][0]
		track = self.sequence_tracks[row][1]
		if not duration:
			duration = 1
		forward = time > self.selected_cell[0]
		backward = None
		if time < self.selected_cell[0]:
			backward = time
		# Skip cells if pattern won't fit
		if snap:
			prev_start = 0
			prev_end = 0
			next_start = time
			for previous in range(time - 1, -1, -1):
				# Iterate time divs back to start
				prev_pattern = self.zynseq.libseq.getPattern(self.zynseq.bank, sequence, track, previous * self.clocks_per_division)
				if prev_pattern == -1:
					continue
				prev_duration = int(self.zynseq.libseq.getPatternLength(prev_pattern) / self.clocks_per_division)
				prev_start = previous
				prev_end = prev_start + prev_duration
				break
			for nxt in range(time + 1, time + duration * 2):
				next_pattern = self.zynseq.libseq.getPattern(self.zynseq.bank, sequence, track, nxt * self.clocks_per_division)
				if next_pattern == -1:
					continue
				next_start = nxt
				break
			if next_start < prev_end:
				next_start = prev_end
			if prev_end <= time < next_start:
				# Between patterns
				if time + duration > next_start:
					# Insufficient space for new pattern between pattern
					if forward:
						time = next_start
					else:
						if next_start - prev_end < duration:
							time = prev_start
						else:
							time = next_start - duration
			elif time == prev_start:
				# At start of previous
				pass
			elif prev_start < time < prev_end:
				# Within pattern
				if forward:
					if prev_end + duration > next_start:
						time = next_start
					else:
						time = prev_end
				else:
					time = prev_start
			if time == 0 and duration > next_start:
				time = next_start

		if time < 0:
			time = 0
		if scroll:
			if time + duration > self.col_offset + self.horizontal_zoom:
				# time is off right of display
				self.col_offset = time + duration - self.horizontal_zoom
				self.redraw_pending = 3
			if time < self.col_offset:
				# time is off left of display
				self.col_offset = time
				self.redraw_pending = 3
			if row >= self.row_offset + self.vertical_zoom:
				# row is off bottom of display
				self.row_offset = row - self.vertical_zoom + 1
				self.redraw_pending = 4
			elif row < self.row_offset:
				self.row_offset = row
				self.redraw_pending = 4
			if backward is not None and self.col_offset > 0 and time > backward:
				self.col_offset = self.col_offset - 1
				self.redraw_pending = 3
		self.selected_cell = [time, row]
		self.sequence = self.sequence_tracks[row][0]
		self.track = self.sequence_tracks[row][1]
		coord = self.get_cell_coord(time - self.col_offset, row - self.row_offset, duration)
		coord[0] = coord[0] - 1
		coord[1] = coord[1] - 1
		coord[2] = coord[2]
		coord[3] = coord[3]
		selection_border = self.grid_canvas.find_withtag("selection")
		if not selection_border:
			selection_border = self.grid_canvas.create_rectangle(coord, fill="", outline=SELECT_BORDER, width=self.select_thickness, tags="selection")
		else:
			self.grid_canvas.coords(selection_border, coord)
		self.grid_canvas.itemconfig(selection_border, state='normal')
		self.grid_canvas.tag_raise(selection_border)
		if scroll and not self.redraw_pending:
			if row < self.row_offset:
				self.row_offset = row
				self.redraw_pending = 3
			if row > self.row_offset + self.vertical_zoom:
				self.row_offset = row + self.vertical_zoom
				self.redraw_pending = 3

	# Function to calculate cell size
	def update_cell_size(self):
		self.row_height = (self.grid_height - 2) / self.vertical_zoom
		self.column_width = self.grid_width / self.horizontal_zoom
		self.fontsize = int(self.row_height * 0.3)
		if self.fontsize > self.row_height * 0.3:
			self.fontsize = int(self.row_height * 0.3)  # Ugly font scale limiting

	# Function to get (note name, octave)
	#  note: MIDI note number
	#  returns: String containing note name and octave number, e.g. "C#4"
	def get_note(self, note):
		if note > 127:
			return ""
		notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
		note_name = notes[note % 12]
		octave = int(note / 12) - 1
		return f"{note_name}{octave}"

	# Function to update array of sequences, tracks
	#  Returns: Quanity of tracks in bank
	def update_sequence_tracks(self):
		old_tracks = self.sequence_tracks.copy()
		self.sequence_tracks.clear()
		for sequence in range(self.zynseq.libseq.getSequencesInBank(self.zynseq.bank)):
			for track in range(self.zynseq.libseq.getTracksInSequence(self.zynseq.bank, sequence)):
				self.sequence_tracks.append((sequence, track))
		if old_tracks != self.sequence_tracks:
			self.redraw_pending = 4
		return len(self.sequence_tracks)

	# Function to refresh playhead
	def refresh_status(self):
		super().refresh_status()
		if self.redraw_pending:
			self.draw_grid()
		previous_sequence = -1
		x = 0
		y1 = 0
		y2 = 0
		seq_row = 0
		for row in range(self.vertical_zoom):
			if row + self.row_offset >= len(self.sequence_tracks):
				break
			sequence = self.sequence_tracks[row + self.row_offset][0]
			if sequence != previous_sequence and sequence != -1:
				self.grid_canvas.coords(f"playheadline-{seq_row}", x, y1, x, y2)
				self.grid_canvas.itemconfig(f"playheadline-{seq_row}", state="normal")
			pos = self.zynseq.libseq.getPlayPosition(self.zynseq.bank, sequence) / self.clocks_per_division
			x = (pos - self.col_offset) * self.column_width
			if sequence == previous_sequence:
				y2 = self.row_height * (row + 1)
			else:
				y1 = self.row_height * row
				y2 = self.row_height * (row + 1)
				seq_row = row
			previous_sequence = sequence
			if sequence == self.sequence and self.zynseq.libseq.getPlayState(self.zynseq.bank, sequence) in [zynseq.SEQ_PLAYING, zynseq.SEQ_STOPPING]:
				if x > self.grid_width:
					self.select_cell(int(pos), self.selected_cell[1])
				elif x < 0:
					self.select_cell(0, self.selected_cell[1])
		self.grid_canvas.coords(f"playheadline-{seq_row}", x, y1, x, y2)
		self.grid_canvas.itemconfig(f"playheadline-{seq_row}", state="normal")

	# Function to handle zyncoder value change
	#  i: Zyncoder index [0..4]
	#  dval: Offset value of zyncoder
	def zynpot_cb(self, i, dval):
		if super().zynpot_cb(i, dval):
			return
		if i == self.ctrl_order[0] and zynthian_gui_config.transport_clock_source <= 1:
			# Tempo change
			self.zynseq.update_tempo()
			self.zynseq.nudge_tempo(dval)
			self.set_title("Tempo: {:.1f}".format(self.zynseq.get_tempo()), None, None, 2)
		elif i == self.ctrl_order[1]:
			self.set_pattern(self.pattern + dval)
		elif i == self.ctrl_order[2]:
			# Adjusts track selection
			self.select_cell(self.selected_cell[0], self.selected_cell[1] + dval)
		elif i == self.ctrl_order[3]:
			# Time-axis selection
			self.select_cell(self.selected_cell[0] + dval, self.selected_cell[1])

	# Function to handle SELECT button press
	#  t: Button press duration ["S"=Short, "B"=Bold, "L"=Long]
	def switch_select(self, t='S'):
		if super().switch_select(t):
			return True
		self.toggle_event(self.selected_cell[0], self.selected_cell[1])

	# Function to handle switch press
	#  i: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#  t: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#  returns True if action fully handled or False if parent action should be triggered
	def switch(self, i, t):
		if i == 1 and t == 'B':
			self.show_pattern_editor()
			return True
		elif i == 2:
			if t == 'S':
				self.zynseq.libseq.togglePlayState(self.zynseq.bank, self.sequence)
			elif t == 'B':
				self.zynseq.libseq.setPlayPosition(self.zynseq.bank, self.sequence, 0)
			else:
				return False
			return True

	# CUIA Actions
	# Function to handle CUIA ARROW_RIGHT
	def arrow_right(self):
		self.zynpot_cb(zynthian_gui_config.ENC_SELECT, 1)

	# Function to handle CUIA ARROW_LEFT
	def arrow_left(self):
		self.zynpot_cb(zynthian_gui_config.ENC_SELECT, -1)

	# Function to handle CUIA ARROW_UP
	def arrow_up(self):
		if self.param_editor_zctrl:
			self.zynpot_cb(zynthian_gui_config.ENC_SELECT, 1)
		else:
			self.zynpot_cb(zynthian_gui_config.ENC_BACK, -1)

	# Function to handle CUIA ARROW_DOWN
	def arrow_down(self):
		if self.param_editor_zctrl:
			self.zynpot_cb(zynthian_gui_config.ENC_SELECT, -1)
		else:
			self.zynpot_cb(zynthian_gui_config.ENC_BACK, 1)

	def start_playback(self):
		self.zynseq.libseq.setPlayState(self.bank, self.sequence, zynseq.SEQ_STARTING)

	def stop_playback(self):
		self.zynseq.libseq.setPlayState(self.bank, self.sequence, zynseq.SEQ_STOPPED)

	def toggle_playback(self):
		if self.zynseq.libseq.getPlayState(self.bank, self.sequence) == zynseq.SEQ_STOPPED:
			self.start_playback()
		else:
			self.stop_playback()

	# Default status area release callback
	def cb_status_release(self, params=None):
		self.toggle_playback()

# ------------------------------------------------------------------------------
