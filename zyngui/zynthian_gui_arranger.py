#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Step-Sequencer Class
#
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
# Copyright (C) 2020-2022 Brian Walton <brian@riban.co.uk>
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

import inspect
import tkinter
import logging
import threading
import tkinter.font as tkFont
from PIL import Image, ImageTk
from time import monotonic, sleep
from threading import Timer
import traceback
from math import sqrt

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui import zynthian_gui_stepsequencer
from zyngui import zynthian_gui_layer
from zyngui import zynthian_gui_fileselector
from zynlibs.zynseq import zynseq
from zynlibs.zynseq.zynseq import libseq
from zynlibs.zynsmf import zynsmf
from zynlibs.zynsmf.zynsmf import libsmf


#------------------------------------------------------------------------------
# Zynthian Step-Sequencer Arranger GUI Class
#------------------------------------------------------------------------------

# Local constants
SELECT_BORDER		= zynthian_gui_config.color_on
PLAYHEAD_CURSOR		= zynthian_gui_config.color_on
CANVAS_BACKGROUND	= zynthian_gui_config.color_panel_bg
CELL_BACKGROUND		= zynthian_gui_config.color_panel_bd
CELL_FOREGROUND		= zynthian_gui_config.color_panel_tx
GRID_LINE			= zynthian_gui_config.color_tx


# Class implements step sequencer arranger
class zynthian_gui_arranger():

	# Function to initialise class
	def __init__(self, parent):
		self.parent = parent
		self.play_modes = ['Disabled', 'Oneshot', 'Loop', 'Oneshot all', 'Loop all', 'Oneshot sync', 'Loop sync']
		
		self.sequence_tracks = [] # Array of [Sequence,Track] that are visible within bank
		self.sequence = 0 # Index of selected sequence
		self.track = 0 # Index of selected track

		self.vertical_zoom = libseq.getVerticalZoom() # Quantity of rows (tracks) displayed in grid
		self.horizontal_zoom = libseq.getHorizontalZoom() # Quantity of columns (time divisions) displayed in grid
		self.copy_source = 1 # Index of bank to copy (add 1000 for pad editor)
		self.row_offset = 0 # Index of sequence_track at top row in grid
		self.col_offset = 0 # Index of time division at left column in grid
		self.selected_cell = [0, 0] # Location of selected cell (time div, row)
		self.pattern = 1 # Index of current pattern to add to sequence
		self.pattern_to_add = 1 # Index of pattern to actually add (may be copied / moved pattern
		self.position = 0 # Current playhead position
		self.grid_timer = Timer(1.0, self.on_grid_timer) # Grid press and hold timer
		#TODO: Populate tracks from file
		self.sequence_drag_start = None # Set to loaction of mouse during drag
		self.time_drag_start = None # Set to time of click to test for bold click
		self.clocks_per_division = 24
		self.cells = [[None] * 2 for _ in range(self.vertical_zoom * self.horizontal_zoom)] # 2D array of cells 0:cell, 1:cell label
		self.redraw_pending = 0

		self.zyngui = zynthian_gui_config.zyngui # Zynthian GUI configuration

		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.body_height
		self.timebase_track_height = int(self.height / 10)
		self.small_font_size = int(self.timebase_track_height / 3)
		self.select_thickness = 1 + int(self.width / 500) # Scale thickness of select border based on screen resolution
		self.grid_height = self.height - self.timebase_track_height
		self.grid_width = int(self.width * 0.9)
		self.seq_track_title_width = self.width - self.grid_width
		self.sequence_title_width = int(0.4 * self.seq_track_title_width)
		self.track_title_width = self.seq_track_title_width - self.sequence_title_width
		self.update_cell_size()

		# Create main frame
		self.main_frame = tkinter.Frame(self.parent.main_frame)
		self.main_frame.grid(column=0, row=1, sticky="nsew")

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
		self.sequence_title_canvas.grid(column=1, row=0)

		# Create grid canvas
		self.grid_canvas = tkinter.Canvas(self.main_frame, 
				width=self.grid_width, 
				height=self.grid_height,
				bg=CANVAS_BACKGROUND,
				bd=0,
				highlightthickness=0)
		self.grid_canvas.grid(column=2, row=0)
		self.grid_canvas.bind("<ButtonPress-1>", self.parent.hide_menu)

		# Create pattern entry indicator
		self.pattern_canvas = tkinter.Canvas(self.main_frame,
				width=self.seq_track_title_width,
				height=self.timebase_track_height,
				bg=CELL_BACKGROUND,
				bd=0,
				highlightthickness=0)
		self.pattern_canvas.create_text(self.seq_track_title_width / 2, self.timebase_track_height / 2, tags="patternIndicator", fill='white', text='%d'%(self.pattern), font=tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=int(0.6 * self.timebase_track_height)))
		self.pattern_canvas.grid(column=1, row=1)
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
		self.timebase_track_canvas.grid(column=2, row=1)


	# Function to get name of this view
	def get_name(self):
		return "arranger"


	# Function to register encoders
	def setup_encoders(self):
		self.parent.register_zyncoder(zynthian_gui_config.ENC_BACK, self)
		self.parent.register_zyncoder(zynthian_gui_config.ENC_SELECT, self)
		self.parent.register_zyncoder(zynthian_gui_config.ENC_LAYER, self)
		self.parent.register_switch(zynthian_gui_config.ENC_SELECT, self, 'SB')
		self.parent.register_switch(zynthian_gui_config.ENC_SNAPSHOT, self, 'SB')


	# Function to register encoders
	def unregister_encoders(self):
		self.parent.unregister_zyncoder(zynthian_gui_config.ENC_BACK)
		self.parent.unregister_zyncoder(zynthian_gui_config.ENC_SELECT)
		self.parent.unregister_zyncoder(zynthian_gui_config.ENC_LAYER)
		self.parent.unregister_switch(zynthian_gui_config.ENC_SELECT)
		self.parent.unregister_switch(zynthian_gui_config.ENC_SNAPSHOT)


	# Function to populate menu
	def populate_menu(self):
		self.parent.add_menu({'Mute track': {'method':self.toggle_mute}})
		self.parent.add_menu({'Vertical zoom': {'method':self.parent.show_param_editor, 'params': {'min':1, 'max':64, 'value':self.vertical_zoom, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Horizontal zoom': {'method':self.parent.show_param_editor, 'params': {'min':1, 'max':64, 'value':self.horizontal_zoom, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'MIDI channel': {'method':self.parent.show_param_editor, 'params': {'min':1, 'max':16, 'get_value':self.get_track_channel, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Group': {'method':self.parent.show_param_editor, 'params': {'min':0, 'max':25, 'get_value':self.get_group, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Play mode': {'method':self.parent.show_param_editor, 'params': {'min':0, 'max':len(self.play_modes)-1, 'get_value':self.getMode, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Pattern': {'method':self.parent.show_param_editor, 'params': {'min':1, 'max':999, 'get_value':self.get_pattern, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Add track': {'method':self.add_track}})
		self.parent.add_menu({'Remove track': {'method':self.remove_track}})
		self.parent.add_menu({'Clear sequence':{'method':self.clear_sequence}})
		self.parent.add_menu({'Clear bank':{'method':self.clear_bank}})
		self.parent.add_menu({'Import SMF':{'method':self.get_smf}})


	# Function to toggle mute of selected track
	def toggle_mute(self, params=None):
		libseq.toggleMute(self.parent.bank, self.sequence, self.track)
		self.redraw_pending = 1


	# Function to clear bank
	def clear_bank(self, params=None):
		self.zyngui.show_confirm("Clear all sequences from bank %d and reset to 4x4 grid of new sequences?" % (self.parent.bank), self.do_clear_bank)


	# Function to actually clear bank
	def do_clear_bank(self, params=None):
		libseq.clearBank(self.parent.bank)
		self.parent.select_bank(self.parent.bank)
		self.select_cell(0,0)
		self.redraw_pending = 2


	# Function to clear sequence
	def clear_sequence(self, params=None):
		name = zynseq.get_sequence_name(self.parent.bank, self.sequence)
		if len(name) == 0:
			name = "%d" % (self.sequence + 1)
		self.zyngui.show_confirm('Clear all patterns from sequence "%s"?' %(name), self.do_clear_sequence)


	# Function to actually clear selected sequence
	def do_clear_sequence(self, params=None):
		libseq.clearSequence(self.parent.bank, self.sequence)
		self.parent.select_bank(self.parent.bank)
		self.select_cell(0,self.sequence)
		self.redraw_pending = 2


	# Function to add track to selected sequence immediately after selected track
	def add_track(self, params=None):
		libseq.addTrackToSequence(self.parent.bank, self.sequence, self.track)
		self.update_sequence_tracks()
		self.redraw_pending = 2


	# Function to remove selected track
	def remove_track(self, params=None):
		self.zyngui.show_confirm("Remove track from sequence?", self.do_remove_track)


	# Function to actually remove selected track
	def do_remove_track(self, params=None):
		libseq.removeTrackFromSequence(self.parent.bank, self.sequence, self.track)
		self.update_sequence_tracks()
		self.redraw_pending = 2


	# Function to import SMF
	def get_smf(self, params=None):
		zynthian_gui_fileselector.zynthian_gui_fileselector(self.parent, self.import_smf, zynthian_gui_stepsequencer.os.environ.get('ZYNTHIAN_MY_DATA_DIR',"/zynthian/zynthian-my-data") + "/capture", "mid", None, True)


	# Function to  check if SMF will overwrite tracks in sequence
	#	filename: Filename of SMF to import
	def import_smf(self, filename):
		logging.warning("Seq len:%d pos:%d", libseq.getSequenceLength(self.parent.bank, self.sequence), self.selected_cell[0])
		if libseq.getSequenceLength(self.parent.bank, self.sequence) > self.selected_cell[0] * 24:
			self.zyngui.show_confirm("Import will overwrite part of existing sequence. Do you want to continue?", self.do_import_smf, filename)
		else:
			self.do_import_smf(filename)


	def do_import_smf(self, filename):
	# Function to actually import SMF
		smf = libsmf.addSmf()
		if not zynsmf.load(smf, filename):
			logging.warning("Failed to load file %s", filename)
			return
		bank = self.parent.bank
		sequence = self.sequence
		ticks_per_beat = libsmf.getTicksPerQuarterNote(smf)
		steps_per_beat = 24
		ticks_per_step = ticks_per_beat / steps_per_beat
		beats_in_pattern = libseq.getBeatsPerBar()
		ticks_in_pattern = beats_in_pattern * ticks_per_beat
		clocks_per_step = 1 # For 24 steps per beat
		ticks_per_clock = ticks_per_step / clocks_per_step
		empty_tracks = [False for i in range(16)] # Array of boolean flags indicating if track should be removed at end of import
#		libseq.clearSequence(bank, sequence) # TODO Do not clear sequence, get sequence length, start at next bar position or current cursor position

		# Add tracks to populate - we will delete unpopulated tracks at end
		for track in range(16):
			if libseq.getChannel(bank, sequence, track) != track:
				libseq.addTrackToSequence(bank, sequence, track - 1)
				libseq.setChannel(bank, sequence, track, track)
				empty_tracks[track] = True

		# Do import
		for channel in range(16):
			# Iterate through each MIDI channel
			libsmf.setPosition(smf, 0)
			pattern = None
			note_on = 0x90 | channel
			note_off = 0x80 | channel
			note_on_info = [[None,None,None,None] for i in range(127)] # Array of [pattern,time,velocity,step] indicating time that note on event received for matching note off and deriving duration
			pattern_position = self.selected_cell[0] * ticks_per_beat # Position of current pattern within track in ticks

			while libsmf.getEvent(smf, True):
				type = libsmf.getEventType()
				time = libsmf.getEventTime()
				status = libsmf.getEventStatus()
				if type == 0x01:
					# MIDI event
					if channel != libsmf.getEventChannel():
						continue
					note = libsmf.getEventValue1()
					velocity = libsmf.getEventValue2()
					if status == note_on and velocity:
						# Found note-on event
						if time >= pattern_position + ticks_in_pattern or pattern == None:
							while time >= pattern_position + ticks_in_pattern:
								pattern_position += ticks_in_pattern
							pattern = libseq.createPattern()
							libseq.selectPattern(pattern)
							libseq.setBeatsInPattern(beats_in_pattern)
							libseq.setStepsPerBeat(steps_per_beat)
							position = int(pattern_position / ticks_per_clock)
							libseq.addPattern(bank, sequence, channel, position, pattern, True)
						step = int((time - pattern_position) / ticks_per_step)
						note_on_info[note] = [pattern,time,velocity,step]
						libseq.addNote(step, note, velocity, 1) # Add short event, may overwrite later when note-off detected
					elif status == note_off or status == note_on and velocity == 0:
						# Found note-off event
						if note_on_info[note][0] == None:
							continue # Do not have corresponding note-on for this note-off event
						current_pattern = pattern
						old_pattern = note_on_info[note][0]
						trigger_time = note_on_info[note][1]
						velocity = note_on_info[note][2]
						step = note_on_info[note][3]
						libseq.selectPattern(old_pattern)
						duration = int((time - trigger_time) / ticks_per_step)
						if duration < 1:
							duration = 1
						libseq.addNote(step, note, velocity, duration)
						note_on_info[note] = [None,None,None,None]
						pattern = current_pattern
						libseq.selectPattern(pattern)
					if(empty_tracks[channel]):
						empty_tracks[channel] = False

		# Remove empty tracks
		for track in range(15, -1, -1):
			if empty_tracks[track]:
				libseq.removeTrackFromSequence(bank, sequence, track)
		self.redraw_pending = 2


	# Function to show GUI
	#	params: Optional dictionary of configuration, e.g. "sequence":number
	def show(self, params={}):
		self.main_frame.tkraise()
		self.select_bank()
		self.setup_encoders()
		if "sequence" in params:
			for row in range(len(self.sequence_tracks)):
				if self.sequence_tracks[row][0] == params["sequence"]:
					self.selected_cell[1] = row
					break


	# Function to hide GUI
	def hide(self):
		#TODO: Move unregister_zyncoder to panel manager
		self.unregister_encoders()


	# Function to assert zoom changes and redraw screen
	def assert_and_redraw(self):
		self.update_cell_size()
		self.redraw_pending = 2


	# Function to get group of selected sequence
	def get_group(self):
		return int(libseq.getGroup(self.parent.bank, self.sequence))


	# Function to get play mode of selected sequence
	def getMode(self):
		return int(libseq.getPlayMode(self.parent.bank, self.sequence))


	# Function to get current pattern
	def get_pattern(self):
		return self.pattern


	# Function to set current pattern
	def set_pattern(self, pattern):
		if pattern < 1:
			self.pattern = 1
		elif pattern > 999:
			pattern = 999
		else:
			self.pattern = pattern
		self.pattern_canvas.itemconfig("patternIndicator", text="%d"%(self.pattern))
		self.parent.set_param('Pattern', 'value', self.pattern)
		self.pattern_to_add = self.pattern
		self.select_cell()


	# Function to get quantity of sequences in bank
	#	returns: Quantity of sequences in bank
	def get_seqeuences(self):
		return libseq.getSequencesInBank(self.parent.bank)


	# Function to handle start of sequence drag
	def on_sequence_drag_start(self, event):
		if self.parent.lst_menu.winfo_viewable():
			self.parent.hide_menu()
			return
		if self.parent.param_editor_item:
			self.parent.show_param_editor(self.parent.param_editor_item)
		if libseq.getSequencesInBank(self.parent.bank) > self.vertical_zoom:
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
		if pos + self.vertical_zoom >= libseq.getSequencesInBank(self.parent.bank):
			pos = libseq.getSequencesInBank(self.parent.bank) - self.vertical_zoom
		if self.row_offset == pos:
			return
		self.row_offset = pos
		self.redraw_pending = 1
		sequence = self.selected_cell[1]
		if self.selected_cell[1] < self.row_offset:
			sequence = self.row_offset
		elif self.selected_cell[1] >= self.row_offset + self.vertical_zoom:
			sequence = self.row_offset + self.vertical_zoom - 1
		self.select_cell(self.selected_cell[0], sequence, False)


	# Function to handle end of sequence drag
	def on_sequence_drag_end(self, event):
		self.sequence_drag_start = None


	# Function to handle start of time drag
	def on_time_drag_start(self, event):
		if self.parent.lst_menu.winfo_viewable():
			self.parent.hide_menu()
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
		self.redraw_pending = 1
		duration = int(libseq.getPatternLength(self.pattern_to_add) / self.clocks_per_division)
		if self.selected_cell[0] < self.col_offset:
			self.select_cell(self.col_offset, self.selected_cell[1])
		elif self.selected_cell[0] > self.col_offset + self.horizontal_zoom  - duration:
			self.select_cell(self.col_offset + self.horizontal_zoom - duration, self.selected_cell[1])
		else:
			self.select_cell()


	# Function to handle end of time drag
	def on_time_drag_end(self, event):
		self.time_drag_start = None


	# Function to handle grid mouse press
	#	event: Mouse event
	def on_grid_press(self, event):
		if self.parent.lst_menu.winfo_viewable():
			self.parent.hide_menu()
			return
		if self.parent.param_editor_item != None:
			self.parent.hide_param_editor()
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
		self.pattern_to_add = libseq.getPattern(self.parent.bank, self.sequence, self.track, self.source_col * self.clocks_per_division)
		if self.pattern_to_add == -1:
			self.pattern_to_add = self.pattern


	# Function to handle grid mouse release
	#	event: Mouse event
	def on_grid_release(self, event):
		if self.grid_timer.isAlive():
			# Haven't moved cursor so just toggle current pattern
			self.toggle_event(self.selected_cell[0], self.selected_cell[1])
			self.grid_timer.cancel()
			return
		self.grid_timer.cancel()
		if self.add_event(self.selected_cell[0], self.sequence, self.track):
			if self.source_col != self.selected_cell[0] or self.source_row != self.selected_cell[1]:
				self.remove_event(self.source_col, self.source_seq, self.source_track)
		else:
			self.select_cell(self.source_col, self.source_row) # Failed to add pattern so reselect original cells
		self.pattern_to_add = self.pattern


	# Function to handle grid mouse motion
	#	event: Mouse event
	def on_grid_drag(self, event):
		col = self.col_offset + int(event.x / self.column_width)
		row = self.row_offset + int(event.y / self.row_height)
		if col < self.col_offset or col >= self.col_offset + self.horizontal_zoom or row < self.row_offset or row >= self.row_offset + self.vertical_zoom:
			return # Avoid scrolling display
		if self.grid_timer.isAlive():
			if col == self.source_col and row == self.source_row:
				return # Haven't moved from original cell
			self.grid_timer.cancel()
			time = self.selected_cell[0] * self.clocks_per_division
			self.pattern_to_add = libseq.getPattern(self.parent.bank, self.sequence, self.track, time)
			if self.pattern_to_add == -1:
				self.pattern_to_add = self.pattern
		if col != self.selected_cell[0] or row != self.selected_cell[1]:
			self.select_cell(col, row, False, False) # Move selection to show wireframe of moving (dragging) pattern


	# Function to handle grid press and hold
	def on_grid_timer(self):
		self.pattern_to_add = self.pattern
		self.show_pattern_editor()


	# Function to show pattern editor
	def show_pattern_editor(self):
		time = self.selected_cell[0] * self.clocks_per_division # time in clock cycles
		pattern = libseq.getPattern(self.parent.bank, self.sequence, self.track, time)
		channel = libseq.getChannel(self.parent.bank, self.sequence, self.track)
		if pattern > 0:
			self.parent.show_child(self.parent.pattern_editor, {'pattern':pattern, 'channel':channel})


	# Function to handle pattern click
	#	event: Mouse event
	def on_pattern_click(self, event):
		if zynthian_gui_config.enable_touch_widgets:
			self.populate_menu() # Probably better way but this ensures 'Pattern' is in the menu
			self.parent.show_param_editor('Pattern')


	# Toggle playback of selected sequence
	def toggle_play(self):
		if libseq.getPlayState(self.parent.bank, self.sequence) == zynthian_gui_stepsequencer.SEQ_STOPPED:
			bars = int(self.selected_cell[0] / libseq.getBeatsPerBar())
			pos = bars * libseq.getBeatsPerBar() * self.clocks_per_division
			if libseq.getSequenceLength(self.parent.bank, self.sequence) > pos:
				libseq.setPlayPosition(self.parent.bank, self.sequence, pos)
		libseq.togglePlayState(self.parent.bank, self.sequence)


	# Function to toggle note event
	#	col: Grid column relative to start of song
	#	row: Grid row
	def toggle_event(self, col, row):
		time = col * self.clocks_per_division
		if libseq.getPattern(self.parent.bank, self.sequence, self.track, time) == -1:
			self.add_event(col, self.sequence, self.track)
		else:
			self.remove_event(col, self.sequence, self.track)
		self.select_cell(col, row)


	# Function to remove an event
	#	col: Time division index (column + columun offset)
	#	sequence: Sequence number
	#	track: Track within sequence
	def remove_event(self, col, sequence, track):
		time = col * self.clocks_per_division
		libseq.removePattern(self.parent.bank, sequence, track, time)
		self.redraw_pending = 1 #TODO: Optimise redraw


	# Function to add an event
	#	col: Time division index (column + columun offset)
	#	sequence: Sequence number
	#	track: Track within sequence
	#	returns: True on success
	def add_event(self, col, sequence, track):
		time = col * self.clocks_per_division
		if libseq.addPattern(self.parent.bank, sequence, track, time, self.pattern_to_add, False):
			self.redraw_pending = 1 #TODO: Optimise redraw
			return True
		return False


	# Function to draw seqeuence / track labels
	#	row: Row (0..vertical zoom)
	def draw_sequence_label(self, row):
		if row >= self.vertical_zoom:
			return
		self.sequence_title_canvas.delete('rowtitle:%d'%(row))
		self.sequence_title_canvas.delete('rowback:%d'%(row))

		if row + self.row_offset > len(self.sequence_tracks):
			return
		sequence = self.sequence_tracks[row + self.row_offset][0]
		track = self.sequence_tracks[row + self.row_offset][1]
		group = libseq.getGroup(self.parent.bank, sequence)
		fill = zynthian_gui_stepsequencer.PAD_COLOUR_STOPPED[group % 16]
		font = tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=self.fontsize)
		channel = libseq.getChannel(self.parent.bank, sequence, track)
		if channel < 16 and self.parent.layers[channel]:
			track_name = self.parent.layers[channel].preset_name
		else:
			track_name = ""

		self.sequence_title_canvas.create_rectangle(0, self.row_height * row + 1, 
				self.seq_track_title_width, (1 + row) * self.row_height - 1, tags=('rowback:%d'%(row), 'sequence_title'),
				fill=fill)
		if track == 0 or row == 0:
			# Create sequence title label from first visible track of sequence
			self.sequence_title_canvas.create_text((0, self.row_height * row + 1),
					font=font, fill=CELL_FOREGROUND, tags=("rowtitle:%d" % (row), "sequence_title"), anchor="nw",
					text=zynseq.get_sequence_name(self.parent.bank, sequence))
			self.grid_canvas.delete('playheadline-%d'%(row))
			self.grid_canvas.create_line(0, self.row_height * (row + 1), 0, self.row_height * (row), fill=PLAYHEAD_CURSOR, tags=('playheadline','playheadline-%d'%(row)), state='hidden')
		else:
			# Don't show track number on track 1 to allow sequence name to be longer and simplify display when single tracks are use
			self.sequence_title_canvas.create_text((self.seq_track_title_width - 2, self.row_height * row + 1),
				font=font, fill=CELL_FOREGROUND, tags=("rowtitle:%d" % (row), "sequence_title"), anchor="ne",
				text="%d" % (track + 1))
		self.sequence_title_canvas.create_text((0, self.row_height * (row + 1) - 1),
				font=tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=int(self.fontsize * 0.9)),
				fill=CELL_FOREGROUND, tags=("rowtitle:%d" % (row), "sequence_title"), anchor="sw",
				text="%s" % (track_name))
		self.sequence_title_canvas.tag_bind('sequence_title', "<Button-1>", self.on_sequence_click)


	# Function to draw a grid row
	#	row: Grid row to draw (0..vertical zoom)
	#	redraw_sequence_titles: True to redraw sequence titles (Default: True)
	def draw_row(self, row, redraw_sequence_titles = True):
		if row >= len(self.sequence_tracks):
			return
		if(redraw_sequence_titles):
			self.draw_sequence_label(row)
		for col in range(self.horizontal_zoom):
			self.draw_cell(col, row)


	# Function to handle sequence title click
	def on_sequence_click(self, event):
		tags = self.sequence_title_canvas.gettags(self.sequence_title_canvas.find_withtag(tkinter.CURRENT))
		if not tags:
			return
		dummy, seq_track = tags[0].split(':')
		row = int(seq_track) + self.row_offset
		self.selected_cell[1] = row
		self.select_cell()


	# Function to get cell coordinates
	#	col: Column index
	#	row: Row index
	#	duration: Duration of cell in time divisions
	#	return: Coordinates required to draw cell
	def get_cell_coord(self, col, row, duration):
		x1 = col * self.column_width + 1
		y1 = self.row_height * row + 1
		x2 = x1 + self.column_width * duration - 1 
		y2 = y1 + self.row_height - 1
		return [x1, y1, x2, y2]


	# Function to draw a grid cell
	#	col: Column index (0..horizontal zoom)
	#	row: Row index (0..vertical zoom)
	def draw_cell(self, col, row):
		if row >= self.vertical_zoom:
			return
		cell_index = row * self.horizontal_zoom + col # Cells are stored in array sequentially: 1st row, 2nd row...
		if cell_index >= len(self.cells):
			return

		sequence = self.sequence_tracks[row + self.row_offset][0]
		track = self.sequence_tracks[row + self.row_offset][1]
		time = (self.col_offset + col) * self.clocks_per_division # time in clock cycles

		pattern = libseq.getPattern(self.parent.bank, sequence, track, time)
		if pattern == -1 and col == 0:
			# Search for earlier pattern that extends into view
			pattern = libseq.getPatternAt(self.parent.bank, sequence, track, time)
			if pattern != -1:
				duration = int(libseq.getPatternLength(pattern) / self.clocks_per_division)
				while time > 0 and duration > 1:
					time -= self.clocks_per_division
					duration -= 1
					if pattern == libseq.getPattern(self.parent.bank, sequence, track, time):
						break
		elif pattern != -1:
				duration = int(libseq.getPatternLength(pattern) / self.clocks_per_division)
		if pattern == -1:
			duration = 1
			fill = CANVAS_BACKGROUND
		elif libseq.isMuted(self.parent.bank, sequence, track):
			fill = zynthian_gui_stepsequencer.PAD_COLOUR_DISABLED
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
			cell = self.grid_canvas.create_rectangle(coord, fill=fill, width=0, tags=("%d,%d"%(col,row), "gridcell", "pattern"))
			celltext = self.grid_canvas.create_text(coord[0] + 1, coord[1] + self.row_height / 2, fill=CELL_FOREGROUND, tags=("%d,%d"%(col,row), "pattern"))
			self.grid_canvas.tag_bind("pattern", '<ButtonPress-1>', self.on_grid_press)
			self.grid_canvas.tag_bind("pattern", '<ButtonRelease-1>', self.on_grid_release)
			self.grid_canvas.tag_bind("pattern", '<B1-Motion>', self.on_grid_drag)
			self.grid_canvas.tag_lower(cell) # Assume cells are always created left to right
			self.cells[cell_index][0] = cell
			self.cells[cell_index][1] = celltext
		# Update existing cell
		else:
			self.grid_canvas.itemconfig(cell, fill=fill)
			self.grid_canvas.coords(cell, coord)
		if pattern == -1:
			self.grid_canvas.itemconfig(celltext, state='hidden')
		else:
			self.grid_canvas.itemconfig(celltext, text=pattern, state='normal', font=tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=self.fontsize))
			self.grid_canvas.coords(celltext, coord[0] + int(duration * self.column_width / 2), int(coord[1] + self.row_height / 2))
#		if time + duration > self.horizontalZoom:
#			if duration > 1:
#				self.grid_canvas.itemconfig("lastpatterntext%d" % row, text="+%d" % (duration - libseq.getPatternLength() + time), state="normal")


	# Function to draw grid
	def draw_grid(self):
		if self.redraw_pending == 2:
			self.grid_canvas.delete(tkinter.ALL)
			self.sequence_title_canvas.delete(tkinter.ALL)
			self.column_width = self.grid_width / self.horizontal_zoom
			self.cells = [[None] * 2 for _ in range(self.vertical_zoom * self.horizontal_zoom)]
			self.select_cell()
		self.redraw_pending = 0

		# Draw rows of grid
		self.grid_canvas.itemconfig("gridcell", fill=CANVAS_BACKGROUND)
		for row in range(0, self.vertical_zoom):
			if row + self.row_offset >= len(self.sequence_tracks):
				break
			self.draw_row(row, True)


		# Vertical (bar / sync) lines
		self.grid_canvas.delete('barlines')
		self.timebase_track_canvas.delete('barlines')
		font = tkFont.Font(size=self.small_font_size)
		tempo_y = font.metrics('linespace')
		offset = 0 - int(self.col_offset % self.horizontal_zoom)
		for bar in range(offset, self.horizontal_zoom, libseq.getBeatsPerBar()):
			self.grid_canvas.create_line(bar * self.column_width, 0, bar * self.column_width, self.grid_height, fill='#808080', tags='barlines')
			if bar:
				self.timebase_track_canvas.create_text(bar * self.column_width, 0, fill='white', text="%d"%(bar+self.col_offset), anchor='n', tags='barlines')
			else:
				self.timebase_track_canvas.create_text(bar * self.column_width, 0, fill='white', text="%d"%(bar+self.col_offset), anchor='nw', tags='barlines')

		# Hide selection if not in view - #TODO: WHEN WOULD THAT BE???
		if self.selected_cell[0] < self.col_offset or self.selected_cell[0] > self.col_offset + self.horizontal_zoom or self.selected_cell[1] < self.row_offset or self.selected_cell[1] > self.row_offset + self.vertical_zoom:
			self.grid_canvas.itemconfig('selection', state='hidden')

		# Timebase track
		self.timebase_track_canvas.delete('bpm')
		for event in range(libseq.getTimebaseEvents(self.parent.bank)):
			time = libseq.getTimebaseEventTime(self.parent.bank, event) / self.clocks_per_division
			if time >= self.col_offset and time <= self.col_offset + self.horizontal_zoom:
				command = libseq.getTimebaseEventCommand(self.parent.bank, event)
				if command == 1: # Tempo
					tempoX = (time - self.col_offset) * self.column_width
					data = libseq.getTimebaseEventData(self.parent.bank, event)
					if tempoX:
						self.timebase_track_canvas.create_text(tempoX, tempo_y, fill='red', text=data, anchor='n', tags='bpm')
					else:
						self.timebase_track_canvas.create_text(tempoX, tempo_y, fill='red', text=data, anchor='nw', tags='bpm')
		
		self.grid_canvas.tag_lower('barlines')


	# Function to select a cell within the grid
	#	time: Time (column) of selected cell (Optional - default to reselect current column)
	#	row: Row of selected cell (0..quantity of tracks. Optional - default to reselect current row)
	#	snap: True to snap to closest pattern (Optional - default True)
	#	scroll: True to scroll to show selected cell (Optional - default True)
	def select_cell(self, time=None, row=None, snap=True, scroll=True):
		if time == None:
			time = self.selected_cell[0]
		if row == None:
			row = self.selected_cell[1]
		if row >= len(self.sequence_tracks):
			row = len(self.sequence_tracks) - 1
		if row < 0:
			row = 0
		duration = int(libseq.getPatternLength(self.pattern_to_add) / self.clocks_per_division)
		sequence = self.sequence_tracks[row][0]
		track = self.sequence_tracks[row][1]
		self.parent.set_title("Bank %d %s%d-%d (%d) %s" % (self.parent.bank, chr(65 + libseq.getGroup(self.parent.bank,sequence)), sequence+1, track + 1, libseq.getChannel(self.parent.bank,sequence, track) + 1, self.get_note(libseq.getTriggerNote(self.parent.bank,sequence))))
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
				prev_pattern = libseq.getPattern(self.parent.bank, sequence, track, previous * self.clocks_per_division)
				if prev_pattern == -1:
					continue
				prev_duration = int(libseq.getPatternLength(prev_pattern) / self.clocks_per_division)
				prev_start = previous
				prev_end = prev_start + prev_duration
				break
			for next in range(time + 1, time + duration * 2):
				next_pattern = libseq.getPattern(self.parent.bank, sequence, track, next * self.clocks_per_division)
				if next_pattern == -1:
					continue
				next_start = next
				break
			if next_start < prev_end:
				next_start = prev_end
			if time >= prev_end and time < next_start:
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
			elif time > prev_start and time < prev_end:
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
				self.redraw_pending = 1
			if time < self.col_offset:
				# time is off left of display
				self.col_offset = time
				self.redraw_pending = 1
			if row >= self.row_offset + self.vertical_zoom:
				# row is off bottom of display
				self.row_offset = row - self.vertical_zoom + 1
				self.redraw_pending = 2
			elif row < self.row_offset:
				self.row_offset = row
				self.redraw_pending = 2
			if backward != None and self.col_offset > 0 and time > backward:
				self.col_offset = self.col_offset - 1
				self.redraw_pending = 1
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
		if scroll:
			if row < self.row_offset:
				self.row_offset = row
				self.redraw_pending = 1
			if row > self.row_offset + self.vertical_zoom:
				self.row_offset = row + self.vertical_zoom
				self.redraw_pending = 1


	# Function to calculate cell size
	def update_cell_size(self):
		self.row_height = (self.grid_height - 2) / self.vertical_zoom
		self.column_width = self.grid_width / self.horizontal_zoom
		self.fontsize = int(self.row_height * 0.3)
		if self.fontsize > self.row_height * 0.3:
			self.fontsize = int(self.row_height * 0.3) # Ugly font scale limiting


	# Function to handle menu editor value change and get display label text
	#	params: Menu item's parameters
	#	returns: String to populate menu editor label
	#	note: params is a dictionary with required fields: min, max, value
	def on_menu_change(self, params):
		value = params['value']
		if value < params['min']:
			value = params['min']
		if value > params['max']:
			value = params['max']
		menu_item = self.parent.param_editor_item
		self.parent.set_param(menu_item, 'value', value)
		if menu_item == 'Vertical zoom':
			self.vertical_zoom = value
			libseq.setVerticalZoom(value)
			self.assert_and_redraw()
		elif menu_item == 'Horizontal zoom':
			self.horizontal_zoom = value
			libseq.setHorizontalZoom(value)
			self.assert_and_redraw()
		elif menu_item == 'MIDI channel':
			libseq.setChannel(self.parent.bank, self.sequence, self.track, value - 1)
			self.redraw_pending = 2
			try:
				return "MIDI channel: %d (%s)"%(value, self.parent.layers[value-1].preset_name)
			except:
				pass # No layer so just show MIDI channel
		elif menu_item == "Group":
			libseq.setGroup(self.parent.bank, self.sequence, value)
			self.redraw_pending = 2
			return "Group: %s" % (chr(65 + value))
		elif menu_item == "Play mode":
			libseq.setPlayMode(self.parent.bank, self.sequence, value)
			self.redraw_pending = 2
			return "Play mode: %s" % (self.play_modes[value])
		elif menu_item == "Pattern":
			self.set_pattern(value)

		return "%s: %d" % (menu_item, value)


	# Function to get (note name, octave)
	#	note: MIDI note number
	#	returns: String containing note name and octave number, e.g. "C#4"
	def get_note(self, note):
		if note > 127:
			return ""
		notes = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
		note_name = notes[note % 12]
		octave = int(note / 12) - 1
		return "%s%d" % (note_name, octave)


	# Function to get MIDI channel of selected track
	#	returns: MIDI channel (1..16)
	def get_track_channel(self):
		channel = libseq.getChannel(self.parent.bank, self.sequence, self.track) + 1
		return channel


	# Function to display bank
	def select_bank(self, bank = None, update_copy_source = True):
		if(bank != None):
			self.parent.bank = bank
		if update_copy_source:
			self.copy_source = self.parent.bank
		self.update_sequence_tracks()
		self.redraw_pending = 2


	# Function to update array of sequences, tracks
	#	Returns: Quanity of tracks in bank
	def update_sequence_tracks(self):
		self.sequence_tracks.clear()
		for sequence in range(libseq.getSequencesInBank(self.parent.bank)):
			for track in range(libseq.getTracksInSequence(self.parent.bank, sequence)):
				self.sequence_tracks.append((sequence, track))
		return len(self.sequence_tracks)


	# Function called when new file loaded from disk
	def on_load(self):
		self.vertical_zoom = libseq.getVerticalZoom()
		self.horizontal_zoom = libseq.getHorizontalZoom()
		self.assert_and_redraw()


	# Function to refresh playhead
	def refresh_status(self):
		if self.redraw_pending:
			self.draw_grid()
		previous_sequence = -1
		x = 0
		y1 = 0
		y2 = 0
		seq_row = 0
		for row in range(self.vertical_zoom):
			sequence = self.sequence_tracks[row + self.row_offset][0]
			if sequence != previous_sequence and sequence != -1:
				self.grid_canvas.coords('playheadline-%d'%seq_row, x, y1, x, y2)
				self.grid_canvas.itemconfig('playheadline-%d'%seq_row, state='normal')
			pos = libseq.getPlayPosition(self.parent.bank, sequence) / self.clocks_per_division
			x = (pos - self.col_offset) * self.column_width
			if sequence == previous_sequence:
				y2 = self.row_height * (row + 1)
			else:
				y1 = self.row_height * row
				y2 = self.row_height * (row + 1)
				seq_row = row
			previous_sequence = sequence
			if sequence == self.sequence and libseq.getPlayState(self.parent.bank, sequence) in [zynthian_gui_stepsequencer.SEQ_PLAYING,zynthian_gui_stepsequencer.SEQ_STOPPING]:
				if x > self.grid_width:
					self.select_cell(int(pos), self.selected_cell[1])
				elif x < 0:
					self.select_cell(0, self.selected_cell[1])
		self.grid_canvas.coords('playheadline-%d'%seq_row, x, y1, x, y2)
		self.grid_canvas.itemconfig('playheadline-%d'%seq_row, state='normal')


	# Function to handle zyncoder value change
	#	encoder: Zyncoder index [0..4]
	#	value: Current value of zyncoder
	def zynpot_cb(self, encoder, value):
		if encoder == zynthian_gui_config.ENC_BACK:
			# BACK encoder adjusts track selection
			self.select_cell(self.selected_cell[0], self.selected_cell[1] + value)
		elif encoder == zynthian_gui_config.ENC_SELECT:
			# SELECT encoder adjusts time selection
			self.select_cell(self.selected_cell[0] + value, self.selected_cell[1])
		elif encoder == zynthian_gui_config.ENC_LAYER:
			self.set_pattern(self.pattern + value)


	# Function to handle switch press
	#	switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def on_switch(self, switch, type):
		if self.parent.lst_menu.winfo_viewable():
			return False
		if self.parent.param_editor_item:
			return False
		if switch == zynthian_gui_config.ENC_SELECT and type == 'B':
			self.show_pattern_editor()
		elif switch == zynthian_gui_config.ENC_SELECT:
			self.toggle_event(self.selected_cell[0], self.selected_cell[1])
		elif switch == zynthian_gui_config.ENC_SNAPSHOT:
			if type == 'B':
				self.toggle_mute()
			else:
				self.toggle_play()
		else:
			return False
		return True


#------------------------------------------------------------------------------
