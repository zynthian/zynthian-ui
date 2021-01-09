#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Step-Sequencer Class
#
# Copyright (C) 2015-2020 Fernando Moyano <jofemodo@zynthian.org>
# Copyright (C) 2020 Brian Walton <brian@riban.co.uk>
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

# Zynthian specific modules
from . import zynthian_gui_config
from . import zynthian_gui_stepsequencer
from zyncoder import *

#------------------------------------------------------------------------------
# Zynthian Step-Sequencer Song Editor GUI Class
#------------------------------------------------------------------------------

# Local constants
SELECT_BORDER		= zynthian_gui_config.color_on
PLAYHEAD_CURSOR		= zynthian_gui_config.color_on
CANVAS_BACKGROUND	= zynthian_gui_config.color_panel_bg
CELL_BACKGROUND		= zynthian_gui_config.color_panel_bd
CELL_FOREGROUND		= zynthian_gui_config.color_panel_tx
GRID_LINE			= zynthian_gui_config.color_tx


# Class implements step sequencer song editor
class zynthian_gui_songeditor():

	# Function to initialise class
	def __init__(self, parent):
		self.parent = parent
		self.libseq = parent.zyngui.libseq

		#TODO: Put colours in a common file
		self.play_modes = ['Disabled', 'Oneshot', 'Loop', 'Oneshot all', 'Loop all', 'Oneshot sync', 'Loop sync']

		self.vertical_zoom = 4 # Quantity of rows (tracks) displayed in grid
		self.horizontal_zoom = 8 # Quantity of columns (time divisions) displayed in grid
		self.copy_source = 1 # Index of song to copy (add 1000 for pad editor)
		self.row_offset = 0 # Index of track at top row in grid
		self.col_offset = 0 # Index of time division at left column in grid
		self.selected_cell = [0, 0] # Location of selected cell (time div,track)
		self.pattern = 1 # Index of current pattern to add to sequence
		self.position = 0 # Current playhead position
		self.grid_timer = Timer(0.5, self.on_grid_timer) # Grid press and hold timer
		self.editor_mode = "song" # Editor mode [song | pads]
		self.song = 1 # Index of song being edited (1000 * editorMode + libseq.getSong)
		self.trigger = 60 # MIDI note number to set trigger
		#TODO: Populate tracks from file
		self.track_drag_start = None # Set to loaction of mouse during drag
		self.time_drag_start = None # Set to time of click to test for bold click
		self.grid_drag_start = None # Set to location of click during drag
		self.clocks_per_division = 24
		self.icon = [tkinter.PhotoImage(),tkinter.PhotoImage(),tkinter.PhotoImage(),tkinter.PhotoImage(),tkinter.PhotoImage(),tkinter.PhotoImage(),tkinter.PhotoImage()]
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
		self.track_title_width = self.width - self.grid_width
		self.update_cell_size()

		# Create main frame
		self.main_frame = tkinter.Frame(self.parent.main_frame)
		self.main_frame.grid(column=0, row=1, sticky="nsew")

		# Create track titles canvas
		self.track_title_canvas = tkinter.Canvas(self.main_frame,
			width=self.track_title_width,
			height=self.grid_height,
			bg=CANVAS_BACKGROUND,
			bd=0,
			highlightthickness=0)
		self.track_title_canvas.bind("<ButtonPress-1>", self.on_track_drag_start)
		self.track_title_canvas.bind("<ButtonRelease-1>", self.on_track_drag_end)
		self.track_title_canvas.bind("<B1-Motion>", self.on_track_drag_motion)
		self.track_title_canvas.grid(column=1, row=0)

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
				width=self.track_title_width,
				height=self.timebase_track_height,
				bg=CELL_BACKGROUND,
				bd=0,
				highlightthickness=0)
		self.pattern_canvas.create_text(self.track_title_width / 2, self.timebase_track_height / 2, tags="patternIndicator", fill='white', text='%d'%(self.pattern), font=tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=int(0.9 * self.timebase_track_height)))
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
		if self.editor_mode == "pad":
			return "pad editor"
		return "song editor"


	# Function to load and resize icons
	def load_icons(self):
		if self.row_height > self.track_title_width / 3:
			icon_height = self.track_title_width / 3
		else:
			icon_height = self.row_height
		iconsize = (int(icon_height), int(icon_height))
		img = (Image.open("/zynthian/zynthian-ui/icons/endnoline.png").resize(iconsize))
		self.icon[1] = ImageTk.PhotoImage(img)
		img = (Image.open("/zynthian/zynthian-ui/icons/loop.png").resize(iconsize))
		self.icon[2] = ImageTk.PhotoImage(img)
		img = (Image.open("/zynthian/zynthian-ui/icons/end.png").resize(iconsize))
		self.icon[3] = ImageTk.PhotoImage(img)
		img = (Image.open("/zynthian/zynthian-ui/icons/loopstop.png").resize(iconsize))
		self.icon[4] = ImageTk.PhotoImage(img)
		img = (Image.open("/zynthian/zynthian-ui/icons/end.png").resize(iconsize))
		self.icon[5] = ImageTk.PhotoImage(img)
		img = (Image.open("/zynthian/zynthian-ui/icons/loopstop.png").resize(iconsize))
		self.icon[6] = ImageTk.PhotoImage(img)


	# Function to register encoders
	def setup_encoders(self):
		self.parent.register_zyncoder(zynthian_gui_stepsequencer.ENC_BACK, self)
		self.parent.register_zyncoder(zynthian_gui_stepsequencer.ENC_SELECT, self)
		self.parent.register_zyncoder(zynthian_gui_stepsequencer.ENC_LAYER, self)
		self.parent.register_switch(zynthian_gui_stepsequencer.ENC_SELECT, self, 'S')
		self.parent.register_switch(zynthian_gui_stepsequencer.ENC_SELECT, self, 'B')


	# Function to populate menu
	def populate_menu(self):
		# Only show song editor menu entries if we have a song selected
		self.parent.add_menu({'Copy song': {'method':self.parent.show_param_editor, 'params': {'min':1, 'max':999, 'value':self.copy_source, 'on_change':self.on_menu_change,'on_assert':self.copy_song}}})
		self.parent.add_menu({'Clear song': {'method':self.parent.show_param_editor, 'params': {'min':0, 'max':1, 'value':0, 'on_change':self.on_menu_change, 'on_assert':self.clear_song}}})
		self.parent.add_menu({'Vertical zoom': {'method':self.parent.show_param_editor, 'params': {'min':1, 'max':64, 'value':self.vertical_zoom, 'on_change':self.on_menu_change,'on_assert':self.assert_and_redraw}}})
		self.parent.add_menu({'Horizontal zoom': {'method':self.parent.show_param_editor, 'params': {'min':1, 'max':999 
		, 'value':64, 'on_change':self.on_menu_change,'on_assert':self.assert_and_redraw}}})
		self.parent.add_menu({'MIDI channel': {'method':self.parent.show_param_editor, 'params': {'min':1, 'max':16, 'get_value':self.get_track_channel, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Tracks': {'method':self.parent.show_param_editor, 'params': {'min':0, 'max':64, 'get_value':self.get_tracks, 'on_change':self.on_menu_change, 'on_assert':self.set_tracks}}})
		self.parent.add_menu({'Tempo': {'method':self.parent.show_param_editor, 'params': {'min':0, 'max':999, 'get_value':self.get_tempo, 'on_change':self.on_menu_change, 'on_assert':self.assert_tempo}}})
		self.parent.add_menu({'Bar / sync': {'method':self.parent.show_param_editor, 'params': {'min':1, 'max':999, 'get_value':self.get_beats_per_bar, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Group': {'method':self.parent.show_param_editor, 'params': {'min':0, 'max':25, 'get_value':self.get_group, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Mode': {'method':self.parent.show_param_editor, 'params': {'min':0, 'max':len(self.play_modes)-1, 'get_value':self.getMode, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Trigger': {'method':self.parent.show_param_editor, 'params': {'min':0, 'max':128, 'get_value':self.get_trigger, 'on_change':self.on_menu_change, 'on_assert':self.set_trigger}}})
		self.parent.add_menu({'Pattern': {'method':self.parent.show_param_editor, 'params': {'min':1, 'max':999, 'get_value':self.get_pattern, 'on_change':self.on_menu_change}}})


	# Function to show GUI
	#	song: Song to show
	def show(self, params=None):
		try:
			self.editor_mode = params["mode"]
		except:
			pass # No parameter "mode" passed
		try:
			self.selected_cell[1] = params["track"]
			self.redraw_pending = 2
		except:
			pass # No parameter "mode" passed
		self.main_frame.tkraise()
		self.select_song()
#		self.redraw_pending = 2
		self.setup_encoders()


	# Function to hide GUI
	def hide(self):
		#TODO: Move unregister_zyncoder to panel manager
		self.parent.unregister_zyncoder(zynthian_gui_stepsequencer.ENC_BACK)
		self.parent.unregister_zyncoder(zynthian_gui_stepsequencer.ENC_SELECT)
		self.parent.unregister_zyncoder(zynthian_gui_stepsequencer.ENC_LAYER)
#		self.libseq.solo(self.song, 0, False)


	# Function to get tempo at current cursor position
	def get_tempo(self):
		return self.libseq.getTempo(self.song, self.selected_cell[0] * self.clocks_per_division)


	# Function to assert zoom changes and redraw screen
	def assert_and_redraw(self):
		self.update_cell_size()
		self.redraw_pending = 2


	# Function to assert tempo change
	def assert_tempo(self):
		value = self.parent.get_param('Tempo', 'value')
		if self.position == self.selected_cell[0]:
			self.libseq.setTempo(value)
		#TODO: Need to use measure + tick to set tempo - and all other song timebase operations
		self.libseq.addTempoEvent(self.song, value, self.selected_cell[0] * self.clocks_per_division)
		self.redraw_pending = 1


	# Function to get group of selected track
	def get_group(self):
		sequence = self.libseq.getSequence(self.song, self.selected_cell[1])
		return int(self.libseq.getGroup(sequence))


	# Function to get play mode of selected track
	def getMode(self):
		sequence = self.libseq.getSequence(self.song, self.selected_cell[1])
		return int(self.libseq.getPlayMode(sequence))


	# Function to get trigger note of selected track
	def get_trigger(self):
		sequence = self.libseq.getSequence(self.song, self.selected_cell[1])
		trigger = int(self.libseq.getTriggerNote(sequence))
		if trigger > 127:
			trigger = 128
		return trigger


	# Function to set trigger note of selected track
	def set_trigger(self):
		sequence = self.libseq.getSequence(self.song, self.selected_cell[1])
		self.libseq.setTriggerNote(sequence, self.trigger)
		self.redraw_pending = 1


	# Function to get bar duration
	def get_beats_per_bar(self):
		#TODO: Do we want beats per bar at cursor or play position?
		return int(self.libseq.getBeatsPerBar(self.song, self.song_position))


	# Function to get pattern (to add to song)
	def get_pattern(self):
		return self.pattern


	# Function to set pattern (to add to song)
	def set_pattern(self, pattern):
		if pattern < 1:
			self.pattern = 1
		else:
			self.pattern = pattern
		self.pattern_canvas.itemconfig("patternIndicator", text="%d"%(self.pattern))
		self.parent.set_param('Pattern', 'value', self.pattern)
		self.select_cell()


	# Function to set quantity of tracks in song
	#	tracks: Quantity of tracks in song
	#	Note: Tracks will be deleted from or added to end of track list as necessary
	def set_tracks(self):
		tracks = self.parent.get_param('Tracks', 'value')
		# Remove surplus tracks
		while self.libseq.getTracks(self.song) > tracks:
			self.libseq.removeTrack(self.song, tracks)
		# Add extra tracks
		while self.libseq.getTracks(self.song) < tracks:
			track = self.libseq.addTrack(self.song)
			sequence = self.libseq.getSequence(self.song, track)
			if self.editor_mode == "pad":
				self.libseq.setGroup(sequence, int(track / 4))
				self.libseq.setChannel(sequence, int(track / 4))
				self.libseq.setPlayMode(sequence, 6)
			else:
				if track < 26:
					self.libseq.setGroup(sequence, track)
				if track <= 16:
					self.libseq.setChannel(sequence, track)
				self.libseq.setPlayMode(sequence, 1)
		self.redraw_pending = 2


	# Function to get quantity of tracks in song
	#	returns: Quantity of tracks in song
	def get_tracks(self):
		return self.libseq.getTracks(self.song)


	# Function to handle start of track drag
	def on_track_drag_start(self, event):
		if self.parent.lst_menu.winfo_viewable():
			self.parent.hide_menu()
			return
		if self.libseq.getTracks(self.song) > self.vertical_zoom:
			self.track_drag_start = event


	# Function to handle track drag motion
	def on_track_drag_motion(self, event):
		if not self.track_drag_start:
			return
		offset = int((event.y - self.track_drag_start.y) / self.row_height)
		if not offset:
			return
		self.track_drag_start.y = event.y
		pos = self.row_offset - offset
		if pos < 0:
			pos = 0
		if pos + self.vertical_zoom >= self.libseq.getTracks(self.song):
			pos = self.libseq.getTracks(self.song) - self.vertical_zoom
		if self.row_offset == pos:
			return
		self.row_offset = pos
		self.redraw_pending = 1
		track=self.selected_cell[1]
		if self.selected_cell[1] < self.row_offset:
			track = self.row_offset
		elif self.selected_cell[1] >= self.row_offset + self.vertical_zoom:
			track = self.row_offset + self.vertical_zoom - 1
		self.select_cell(self.selected_cell[0], track)


	# Function to handle end of track drag
	def on_track_drag_end(self, event):
		self.track_drag_start = None


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
		col = self.selected_cell[0]
		duration = int(self.libseq.getPatternLength(self.pattern) / self.clocks_per_division)
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
			self.parent.hideMenu()
			return
		if self.parent.param_editor_item != None:
			self.parent.hideParamEditor()
			return

		self.grid_drag_start = event

		self.grid_timer = Timer(0.4, self.on_grid_timer)
		self.grid_timer.start()
		tags = self.grid_canvas.gettags(self.grid_canvas.find_withtag(tkinter.CURRENT))
		if not tags:
			return
		col, row = tags[0].split(',')
		self.select_cell(self.col_offset + int(col), self.row_offset + int(row), False)


	# Function to handle grid mouse release
	#	event: Mouse event
	def on_grid_release(self, event):
		self.grid_timer.cancel()
		if not self.grid_drag_start:
			return
		self.grid_drag_start = None

		self.toggle_event(self.selected_cell[0], self.selected_cell[1])


	# Function to handle grid mouse motion
	#	event: Mouse event
	def on_grid_motion(self, event):
		if self.grid_drag_start == None:
			return
		col = self.col_offset + int(event.x / self.column_width)
		row = self.row_offset + int(event.y / self.row_height)
		if col != self.selected_cell[0] or row != self.selected_cell[1]:
			self.grid_timer.cancel()
			self.grid_drag_start.x = event.x
			self.grid_drag_start.y = event.y
			self.select_cell(col, row, False)


	# Function to handle grid press and hold
	def on_grid_timer(self):
		self.grid_drag_start = None
		self.show_pattern_editor()


	# Function to show pattern editor
	def show_pattern_editor(self):
		time = self.selected_cell[0] * self.clocks_per_division # time in clock cycles
		sequence = self.libseq.getSequence(self.song, self.selected_cell[1])
		pattern = self.libseq.getPattern(sequence, time)
		channel = self.libseq.getChannel(sequence)
		if pattern > 0:
			self.parent.show_child("pattern editor", {'pattern':pattern, 'channel':channel})


	# Function to handle pattern click
	#	event: Mouse event
	def on_pattern_click(self, event):
		self.populate_menu() # Probably better way but this ensures 'Pattern' is in the menu
		self.parent.show_param_editor('Pattern')


	# Function to toggle note event
	#	col: Column
	#	track: Track number
	def toggle_event(self, div, track):
		time = div * self.clocks_per_division
		sequence = self.libseq.getSequence(self.song, track)
		if self.libseq.getPattern(sequence, time) == -1:
			self.add_event(div, track)
		else:
			self.remove_event(div, track)
		self.select_cell(div, track)


	# Function to remove an event
	#	div: Time division index (column + columun offset)
	#	track: Track number
	def remove_event(self, div, track):
		time = div * self.clocks_per_division
		sequence = self.libseq.getSequence(self.song, track)
		self.libseq.removePattern(sequence, time)
		self.draw_track(track)


	# Function to add an event
	#	div: Time division index (column + columun offset)
	#	track: Track number
	def add_event(self, div, track):
		time = div * self.clocks_per_division
		sequence = self.libseq.getSequence(self.song, track)
		if self.libseq.addPattern(sequence, time, self.pattern, False):
			self.draw_track(track)


	# Function to draw track
	#	track: Track index
	def draw_track(self, track):
		self.draw_row(track - self.row_offset)


	# Function to draw track label
	#	track: Track index
	def draw_track_label(self, track):
		row = track - self.row_offset
		sequence = self.libseq.getSequence(self.song, track)
		channel = self.libseq.getChannel(sequence) + 1
		group = self.libseq.getGroup(sequence)
		mode = self.libseq.getPlayMode(sequence)

		self.track_title_canvas.delete('rowtitle:%d'%(row))
		self.track_title_canvas.delete('rowicon:%d'%(row))
		self.track_title_canvas.delete('rowback:%d'%(row))
		title_back = self.track_title_canvas.create_rectangle(0, self.row_height * row, self.track_title_width, (1 + row) * self.row_height, tags=('rowback:%d'%(row), 'tracktitle'))
		font = tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=self.fontsize)
		title = self.track_title_canvas.create_text((0, self.row_height * (row + 0.5)), font=font, fill=CELL_FOREGROUND, tags=("rowtitle:%d" % (row),"trackname", 'tracktitle'), anchor="w")
		mode_icon = self.track_title_canvas.create_image(self.track_title_width, row * self.row_height, anchor='ne', tags=('rowicon:%d'%(row), 'tracktitle'))

		trigger = self.libseq.getTriggerNote(sequence)
		if trigger < 128:
			self.track_title_canvas.itemconfig(title, text="%s%d\n(%d,%s)" % (chr(65+group), track + 1, channel, self.get_note(trigger)))
		else:
			self.track_title_canvas.itemconfig(title, text="%s%d\n(%d)" % (chr(65+group), track + 1, channel))
		self.track_title_canvas.itemconfig(mode_icon, image=self.icon[mode])
		if group % 2:
			fill = zynthian_gui_stepsequencer.PAD_COLOUR_STOPPED_EVEN
		else:
			fill = zynthian_gui_stepsequencer.PAD_COLOUR_STOPPED_ODD
		self.track_title_canvas.itemconfig(title_back, fill=fill)
		self.track_title_canvas.tag_bind('tracktitle', "<Button-1>", self.on_track_click)


	# Function to draw a grid row
	#	row: Grid row to draw
	#	redrawTrackTitles: True to redraw track titles (Default: True)
	def draw_row(self, row, redraw_track_titles = True):
		if row + self.row_offset >= self.libseq.getTracks(self.song):
			return
		track = self.row_offset + row
		if(redraw_track_titles):
			self.draw_track_label(track)
		for col in range(self.horizontal_zoom):
			self.draw_cell(col, row)


	# Function to handle track title click
	def on_track_click(self, event):
		tags = self.track_title_canvas.gettags(self.track_title_canvas.find_withtag(tkinter.CURRENT))
		if not tags:
			return
		dummy, row = tags[0].split(':')
		track = int(row) + self.row_offset
		sequence = self.libseq.getSequence(self.song, track)
		print("Song %d, track %d, sequence:%d, trigger:%d, playstate:%d"%(self.song, track, sequence, self.libseq.getTriggerNote(sequence), self.libseq.getPlayState(sequence)))
		self.selected_cell[1] = track
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
	#	col: Column index
	#	row: Row index
	def draw_cell(self, col, row):
		cell_index = row * self.horizontal_zoom + col # Cells are stored in array sequentially: 1st row, 2nd row...
		if cell_index >= len(self.cells):
			return

		track = self.row_offset + row
		time = (self.col_offset + col) * self.clocks_per_division # time in clock cycles
		sequence = self.libseq.getSequence(self.song, track)

		pattern = self.libseq.getPattern(sequence, time)
		if pattern == -1:
			fill = CANVAS_BACKGROUND
			duration = 1
			if col == 0:
				for t in range(time, -1, -self.clocks_per_division):
					pattern = self.libseq.getPattern(sequence, t)
					if pattern != -1:
						duration = int((self.libseq.getPatternLength(pattern) + t) / self.clocks_per_division) - self.col_offset
						if duration > 0:
							fill = CELL_BACKGROUND
						else:
							pattern = -1
						break
		else:
			duration = int(self.libseq.getPatternLength(pattern) / self.clocks_per_division)
			fill = CELL_BACKGROUND
			#print("Drawing cell %d,%d for track %d, sequence %d, pattern %d, duration %d"%(col,row,track,sequence,pattern,duration))
		if col + duration > self.col_offset + self.horizontal_zoom:
			duration = self.col_offset + self.horizontal_zoom - col
		if duration < 1:
			duration = 1

		#print("draw cell time=%d track=%d col=%d row=%d sequence=%d pattern=%d, duration=%d" % (time,track,col, row, sequence, pattern, duration))
		cell = self.cells[cell_index][0]
		celltext = self.cells[cell_index][1]
		coord = self.get_cell_coord(col, row, duration)
		if not cell:
			# Create new cell
			cell = self.grid_canvas.create_rectangle(coord, fill=fill, width=0, tags=("%d,%d"%(col,row), "gridcell"))
			celltext = self.grid_canvas.create_text(coord[0] + 1, coord[1] + self.row_height / 2, fill=CELL_FOREGROUND, tags=("celltext:%d,%d"%(col,row)))
			self.grid_canvas.tag_bind(cell, '<ButtonPress-1>', self.on_grid_press)
			self.grid_canvas.tag_bind(cell, '<ButtonRelease-1>', self.on_grid_release)
			self.grid_canvas.tag_bind(cell, '<B1-Motion>', self.on_grid_motion)
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
#				self.grid_canvas.itemconfig("lastpatterntext%d" % row, text="+%d" % (duration - self.libseq.getPatternLength() + time), state="normal")


	# Function to draw grid
	def draw_grid(self):
		if self.redraw_pending == 2:
			self.grid_canvas.delete(tkinter.ALL)
			self.track_title_canvas.delete(tkinter.ALL)
			self.column_width = self.grid_width / self.horizontal_zoom
			self.grid_canvas.create_line(0, 0, 0, self.grid_height, fill=PLAYHEAD_CURSOR, tags='playheadline')
			self.cells = [[None] * 2 for _ in range(self.vertical_zoom * self.horizontal_zoom)]
			self.select_cell()
		self.redraw_pending = 0

		# Draw rows of grid
		self.grid_canvas.itemconfig("gridcell", fill=CANVAS_BACKGROUND)
		for row in range(self.vertical_zoom):
			if row >= self.libseq.getTracks(self.song):
				break
			self.draw_row(row, True)

		# Vertical (bar / sync) lines
		self.grid_canvas.delete('barlines')
		self.timebase_track_canvas.delete('barlines')
		font = tkFont.Font(size=self.small_font_size)
		tempo_y = font.metrics('linespace')
		offset = 0 - int(self.col_offset % self.horizontal_zoom)
		for bar in range(offset, self.horizontal_zoom, int(self.libseq.getBarLength(self.song) / self.clocks_per_division)):
			self.grid_canvas.create_line(bar * self.column_width, 0, bar * self.column_width, self.grid_height, fill='white', tags='barlines')
			if bar:
				self.timebase_track_canvas.create_text(bar * self.column_width, 0, fill='white', text="%d"%(bar+self.col_offset), anchor='n', tags='barlines')
			else:
				self.timebase_track_canvas.create_text(bar * self.column_width, 0, fill='white', text="%d"%(bar+self.col_offset), anchor='nw', tags='barlines')

		# Hide selection if not in view - #TODO: WHEN WOULD THAT BE???
		if self.selected_cell[0] < self.col_offset or self.selected_cell[0] > self.col_offset + self.horizontal_zoom or self.selected_cell[1] < self.row_offset or self.selected_cell[1] > self.row_offset + self.vertical_zoom:
			self.grid_canvas.itemconfig('selection', state='hidden')

		# Timebase track
		self.timebase_track_canvas.delete('bpm')
		print("Drawing timebase track")
		for event in range(self.libseq.getTimebaseEvents(self.song)):
			time = self.libseq.getTimebaseEventTime(self.song, event) / self.clocks_per_division
			if time >= self.col_offset and time <= self.col_offset + self.horizontal_zoom:
				command = self.libseq.getTimebaseEventCommand(self.song, event)
				if command == 1: # Tempo
					tempoX = (time - self.col_offset) * self.column_width
					data = self.libseq.getTimebaseEventData(self.song, event)
					if tempoX:
						self.timebase_track_canvas.create_text(tempoX, tempo_y, fill='red', text=data, anchor='n', tags='bpm')
					else:
						self.timebase_track_canvas.create_text(tempoX, tempo_y, fill='red', text=data, anchor='nw', tags='bpm')


	# Function to select a cell within the grid
	#	time: Time (column) of selected cell (Optional - default to reselect current column)
	#	track: Track number of selected cell (Optional - default to reselect current row)
	#	snap: True to snap to closest pattern (Optional - default True)
	def select_cell(self, time=None, track=None, snap=True):
		if time == None:
			time = self.selected_cell[0]
		if track == None:
			track = self.selected_cell[1]
		duration = int(self.libseq.getPatternLength(self.pattern) / self.clocks_per_division)
		if not duration:
			duration = 1
		forward = time > self.selected_cell[0]
		backward = None
		if time < self.selected_cell[0]:
			backward = time
		# Skip cells if pattern won't fit
		if snap:
			sequence = self.libseq.getSequence(self.song, track)
			prev_start = 0
			prev_end = 0
			next_start = time
			for previous in range(time - 1, -1, -1):
				# Iterate time divs back to start
				prev_pattern = self.libseq.getPattern(sequence, previous * self.clocks_per_division)
				if prev_pattern == -1:
					continue
				prev_duration = int(self.libseq.getPatternLength(prev_pattern, track) / self.clocks_per_division)
				prev_start = previous
				prev_end = prev_start + prev_duration
				break
			for next in range(time + 1, time + duration * 2):
				next_pattern = self.libseq.getPattern(sequence, next * self.clocks_per_division)
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

		if track >= self.libseq.getTracks(self.song):
			track = self.libseq.getTracks(self.song) - 1
		if track < 0:
			track = 0
		if time < 0:
			time = 0
		if time < 0:
			time = 0
		if time + duration > self.col_offset + self.horizontal_zoom:
			# time is off right of display
			self.col_offset = time + duration - self.horizontal_zoom
			self.redraw_pending = 1
		if time < self.col_offset:
			# time is off left of display
			self.col_offset = time
			self.redraw_pending = 1
		if track >= self.row_offset + self.vertical_zoom:
			# track is off bottom of display
			self.row_offset = track - self.vertical_zoom + 1
			self.redraw_pending = 1
		elif track < self.row_offset:
			self.row_offset = track
			self.redraw_pending = 1
		if backward != None and self.col_offset > 0 and time > backward:
			self.col_offset = self.col_offset - 1
			self.redraw_pending = 1
		self.selected_cell = [time, track]
		coord = self.get_cell_coord(time - self.col_offset, track - self.row_offset, duration)
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

#		if self.song > 1000: # Solo will stop playback which may be undesirable
#			self.libseq.solo(self.song, track, True)


	# Function to calculate cell size
	def update_cell_size(self):
		self.row_height = (self.grid_height - 2) / self.vertical_zoom
		self.column_width = self.grid_width / self.horizontal_zoom
		self.fontsize = int(self.row_height * 0.3)
		if self.fontsize > self.track_title_width * 0.3:
			self.fontsize = int(self.track_title_width * 0.3) # Ugly font scale limiting
		self.load_icons()


	# Function to clear song
	def clear_song(self):
		self.libseq.clearSong(self.song)
		self.redraw_pending = 2
		if zyncoder.lib_zyncoder:
			zyncoder.lib_zyncoder.zynmidi_send_all_notes_off()
		self.select_cell(0,0)


	# Function to copy song
	def copy_song(self):
		if(self.song > 1000):
			self.libseq.copySong(self.copy_source + 1000, self.song)
		else:
			self.libseq.copySong(self.copy_source, self.song)
		self.select_song()


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
		if menu_item == 'Clear song':
			if self.song < 1000:
				return "Clear song %d?" % (self.song)
			else:
				return "Clear song %d?" % (self.song - 1000)
		elif menu_item =='Copy song':
			self.libseq.selectSong(value) 
			self.select_song(False)
			return "Copy %d=>%d?" % (self.copy_source, value)
		elif menu_item == 'Vertical zoom':
			self.vertical_zoom = value
		elif menu_item == 'Horizontal zoom':
			self.horizontal_zoom = value
		elif menu_item == 'MIDI channel':
			sequence = self.libseq.getSequence(self.song, self.selected_cell[1])
			self.libseq.setChannel(sequence, value - 1)
			self.draw_track(self.selected_cell[1])
		elif menu_item == 'Tempo':
			pass
		elif menu_item == 'Bar / sync':
			self.libseq.setBeatsPerBar(self.song, value)
			if self.editor_mode == "pad":
				self.libseq.setBeatsPerBar(self.song - 1000, value)
			else:
				self.libseq.setBeatsPerBar(self.song + 1000, value)
			self.redraw_pending = 1
		elif menu_item == "Group":
			sequence = self.libseq.getSequence(self.song, self.selected_cell[1])
			self.libseq.setGroup(sequence, value)
			self.draw_track_label(self.selected_cell[1])
			return "Group: %s" % (chr(65 + value))
		elif menu_item == "Mode":
			sequence = self.libseq.getSequence(self.song, self.selected_cell[1])
			self.libseq.setPlayMode(sequence, value)
			self.draw_track_label(self.selected_cell[1])
			return "Mode: %s" % (self.play_modes[value])
		elif menu_item == "Trigger":
			self.trigger = value
			sequence = self.libseq.getSequence(self.song, self.selected_cell[1])
			self.libseq.setTriggerNote(sequence, self.trigger)
			self.draw_track_label(self.selected_cell[1])
			if value > 127:
				return "Trigger: None"
			else:
				return "Trigger: %s" % self.get_note(value)
		elif menu_item == "Pattern":
			self.set_pattern(value)
#		elif menu_item == "Tracks":
#			self.set_tracks(value)
		return "%s: %d" % (menu_item, value)


	# Function to get (note name, octave)
	#	note: MIDI note number
	#	returns: String containing note name and octave number, e.g. "C#4"
	def get_note(self, note):
		notes = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
		note_name = notes[note % 12]
		octave = int(note / 12) - 1
		return "%s%d" % (note_name, octave)


	# Function to get MIDI channel of selected track
	#	returns: MIDI channel
	def get_track_channel(self):
		track = self.selected_cell[1]
		sequence = self.libseq.getSequence(self.song, track)
		channel = self.libseq.getChannel(sequence) + 1
		return channel


	# Function to display song
	def select_song(self, update_copy_source = True):
		song = self.libseq.getSong()
		if song != 0:
			self.song = song
		if self.editor_mode == "pad":
			self.parent.set_title("Pad Editor (%d)" % (self.song))
			self.song = self.song + 1000
		else:
			self.parent.set_titlele("Song Editor (%d)" % (self.song))
#			self.libseq.solo(self.song + 1000, 0, False) # Clear solo from pad editor when switching to song editor
		if update_copy_source:
			if self.song > 1000:
				self.copy_source = self.song - 1000
			else:
				self.copy_source = self.song
		self.redraw_pending = 2


	# Function called when new file loaded from disk
	def on_load(self):
		#TODO: Redraw song
		pass


	# Function to scroll grid to show position in song
	#	pos: Song position in divisions
	def show_pos(self, pos):
		if pos >= self.col_offset and pos < self.col_offset + self.horizontal_zoom:
			return
		self.col_offset = int(pos)
		self.position = int(pos)
		if self.col_offset < 0:
			self.col_offset = 0
		self.redraw_pending = 1


	# Function to refresh playhead
	def refresh_status(self):
		if self.redraw_pending:
			self.draw_grid()
#		if self.song < 1000:
#			pos = self.libseq.getSongPosition()# / self.clocks_per_division
#		else:
#			sequence = self.libseq.getSequence(self.song, self.selected_cell[1]) #TODO: Offset?
#			pos = self.libseq.getPlayPosition(sequence)# / self.clocks_per_division
#		if self.position != pos:
#			self.showPos(pos)
#			self.position = pos
#		self.grid_canvas.coords('playheadline', (pos - self.col_offset) * self.column_width, 0, (pos - self.col_offset) * self.column_width, self.grid_height)


	# Function to handle zyncoder value change
	#	encoder: Zyncoder index [0..4]
	#	value: Current value of zyncoder
	def on_zyncoder(self, encoder, value):
		if encoder == zynthian_gui_stepsequencer.ENC_BACK:
			# BACK encoder adjusts track selection
			track = self.selected_cell[1] + value
			self.select_cell(self.selected_cell[0], track)
		elif encoder == zynthian_gui_stepsequencer.ENC_SELECT:
			# SELECT encoder adjusts time selection
			time = self.selected_cell[0] + value
			self.select_cell(time, self.selected_cell[1])
		elif encoder == zynthian_gui_stepsequencer.ENC_LAYER:
			self.set_pattern(self.pattern + value)


	# Function to handle switch press
	#	switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def on_switch(self, switch, type):
		if switch == zynthian_gui_stepsequencer.ENC_SELECT and type == 'B':
			self.show_pattern_editor()
		elif switch == zynthian_gui_stepsequencer.ENC_SELECT:
			self.toggle_event(self.selected_cell[0], self.selected_cell[1])
		else:
			return False
		return True
#------------------------------------------------------------------------------
