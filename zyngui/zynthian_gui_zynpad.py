#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Step-Sequencer Pad Trigger Class
#
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <brian@riban.co.uk>
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

import tkinter
import logging
import tkinter.font as tkFont
from math import sqrt
from PIL import Image, ImageTk
from time import sleep
from threading import Timer
from collections import OrderedDict

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_patterneditor import EDIT_MODE_NONE
from . import zynthian_gui_base
from zyncoder.zyncore import get_lib_zyncore
from zynlibs.zynseq import zynseq

SELECT_BORDER	= zynthian_gui_config.color_on
INPUT_CHANNEL_LABELS = ['OFF','1','2','3','4','5','6','7','8','9','10','11','12','13','14','15','16']
NOTE_NAMES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]

#------------------------------------------------------------------------------
# Zynthian Step-Sequencer Sequence / Pad Trigger GUI Class
#------------------------------------------------------------------------------

# Class implements step sequencer
class zynthian_gui_zynpad(zynthian_gui_base.zynthian_gui_base):

	# Function to initialise class
	def __init__(self):
		logging.getLogger('PIL').setLevel(logging.WARNING)

		self.columns = 4 # Quantity of columns in grid
		self.selected_pad = 0 # Index of selected pad
		self.redraw_pending = 2 # 0=no refresh pending, 1=update grid, 2=rebuild grid
		self.redrawing = False # True to block further redraws until complete
		self.bank = None # The last successfully selected bank - used to update stale views

		super().__init__()
		self.zynseq = self.zyngui.state_manager.zynseq

		# Geometry vars
		self.select_thickness = 1 + int(self.width / 400) # Scale thickness of select border based on screen
		self.column_width = self.width / self.columns
		self.row_height = self.height / self.columns

		# Pad grid
		self.grid_canvas = tkinter.Canvas(self.main_frame,
			width=self.width,
			height=self.height,
			bd=0,
			highlightthickness=0,
			bg = zynthian_gui_config.color_bg)
		self.main_frame.columnconfigure(0, weight=1)
		self.main_frame.rowconfigure(0, weight=1)
		self.grid_canvas.grid()
		self.grid_timer = Timer(1.4, self.on_grid_timer) # Grid press and hold timer

		# Icons
		self.mode_icon = [tkinter.PhotoImage() for i in range(7)]
		self.state_icon = [tkinter.PhotoImage() for i in range(4)]
		self.empty_icon = tkinter.PhotoImage()

		# Selection highlight
		self.selection = self.grid_canvas.create_rectangle(0, 0, self.column_width, self.row_height, fill="", outline=SELECT_BORDER, width=self.select_thickness, tags="selection")

		self.zynseq.add_event_cb(self.seq_cb)


	def seq_cb(self, event):
		if event == zynseq.SEQ_EVENT_LOAD:
			self.redraw_pending = 2
		elif event == zynseq.SEQ_EVENT_BANK:
			self.title = "Bank {}".format(self.zynseq.bank)
			self.bank = None
			if self.zynseq.libseq.getSequencesInBank(self.zynseq.bank) != self.columns ** 2:
				self.redraw_pending = 2
			else:
				self.redraw_pending = 1
		elif self.redraw_pending < 2 and event in [
					zynseq.SEQ_EVENT_CHANNEL,
					zynseq.SEQ_EVENT_GROUP,
					zynseq.SEQ_EVENT_SEQUENCE]:
			self.redraw_pending = 1
		elif event == zynseq.SEQ_EVENT_MIDI_LEARN:
			if self.param_editor_zctrl:
				self.disable_param_editor()
    		

	#Function to set values of encoders
	def setup_zynpots(self):
		get_lib_zyncore().setup_behaviour_zynpot(zynthian_gui_config.ENC_LAYER, 0)
		get_lib_zyncore().setup_behaviour_zynpot(zynthian_gui_config.ENC_BACK, 0)
		get_lib_zyncore().setup_behaviour_zynpot(zynthian_gui_config.ENC_SNAPSHOT, 0)
		get_lib_zyncore().setup_behaviour_zynpot(zynthian_gui_config.ENC_SELECT, 0)


	# Function to show GUI
	#   params: Misc parameters
	def build_view(self):
		self.zynseq.libseq.updateSequenceInfo()
		self.setup_zynpots()
		if self.param_editor_zctrl == None:
			self.set_title("Bank {}".format(self.zynseq.bank))


	# Function to hide GUI
	def hide(self):
		super().hide()


	# Function to set quantity of pads
	def set_grid_size(self, value):
		columns = value + 1
		if columns > 8:
			columns = 8
		if self.zynseq.libseq.getSequencesInBank(self.zynseq.bank) > columns ** 2:
			self.zyngui.show_confirm("Reducing the quantity of sequences in bank {} will delete sequences but patterns will still be available. Continue?".format(self.zynseq.bank), self.zynseq.update_bank_grid, columns)
		else:
			self.zynseq.update_bank_grid(columns)


	# Function to name selected sequence
	def rename_sequence(self, params=None):
		self.zyngui.show_keyboard(self.do_rename_sequence, self.zynseq.get_sequence_name(self.zynseq.bank, self.selected_pad), 16)


	# Function to rename selected sequence
	def do_rename_sequence(self, name):
		self.zynseq.set_sequence_name(self.zynseq.bank, self.selected_pad, name)


	# Function to get trigger MIDI channel
	def get_trigger_channel(self):
		if(self.zynseq.libseq.getTriggerChannel() > 15):
			return 0
		return self.zynseq.libseq.getTriggerChannel() + 1


	# Function to get tally MIDI channel
	def get_tally_channel(self):
		if(self.zynseq.libseq.getTallyChannel() > 15):
			return 0
		return self.zynseq.libseq.getTallyChannel() + 1


	def update_layout(self):
		super().update_layout()
		self.redraw_pending = 2
		self.update_grid()


	# Function to clear and calculate grid sizes
	def update_grid(self):
		if self.redrawing:
			return
		pads = self.zynseq.libseq.getSequencesInBank(self.zynseq.bank)
		if pads < 1:
			return
		
		self.redrawing = True
		try:
			if self.redraw_pending == 2:
				self.columns = int(sqrt(pads))
				self.grid_canvas.delete(tkinter.ALL)
				self.column_width = self.width / self.columns
				self.row_height = self.height / self.columns
				self.selection = self.grid_canvas.create_rectangle(0, 0, int(self.column_width), int(self.row_height), fill="", outline=SELECT_BORDER, width=self.select_thickness, tags="selection")

				iconsize = (int(self.column_width * 0.5), int(self.row_height * 0.2))
				img = (Image.open("/zynthian/zynthian-ui/icons/oneshot.png").resize(iconsize))
				self.mode_icon[1] = ImageTk.PhotoImage(img)
				img = (Image.open("/zynthian/zynthian-ui/icons/loop.png").resize(iconsize))
				self.mode_icon[2] = ImageTk.PhotoImage(img)
				img = (Image.open("/zynthian/zynthian-ui/icons/oneshotall.png").resize(iconsize))
				self.mode_icon[3] = ImageTk.PhotoImage(img)
				img = (Image.open("/zynthian/zynthian-ui/icons/loopall.png").resize(iconsize))
				self.mode_icon[4] = ImageTk.PhotoImage(img)
				img = (Image.open("/zynthian/zynthian-ui/icons/oneshotsync.png").resize(iconsize))
				self.mode_icon[5] = ImageTk.PhotoImage(img)
				img = (Image.open("/zynthian/zynthian-ui/icons/loopsync.png").resize(iconsize))
				self.mode_icon[6] = ImageTk.PhotoImage(img)

				iconsize = (int(self.row_height * 0.2), int(self.row_height * 0.2))
				img = (Image.open("/zynthian/zynthian-ui/icons/stopped.png").resize(iconsize))
				self.state_icon[zynseq.SEQ_STOPPED] = ImageTk.PhotoImage(img)
				img = (Image.open("/zynthian/zynthian-ui/icons/starting.png").resize(iconsize))
				self.state_icon[zynseq.SEQ_STARTING] = ImageTk.PhotoImage(img)
				img = (Image.open("/zynthian/zynthian-ui/icons/playing.png").resize(iconsize))
				self.state_icon[zynseq.SEQ_PLAYING] = ImageTk.PhotoImage(img)
				img = (Image.open("/zynthian/zynthian-ui/icons/stopping.png").resize(iconsize))
				self.state_icon[zynseq.SEQ_STOPPING] = ImageTk.PhotoImage(img)

			# Draw pads
			for pad in range(self.columns**2):
				pad_x = int(pad / self.columns) * self.column_width
				pad_y = pad % self.columns * self.row_height
				if self.redraw_pending == 2:
					fs1 = int(self.row_height * 0.15)
					fs2 = int(self.row_height * 0.2)
					self.grid_canvas.create_rectangle(pad_x, pad_y, pad_x + self.column_width - 2, pad_y + self.row_height - 2,
						fill='grey', width=0, tags=("pad:%d"%(pad), "gridcell", "trigger_%d"%(pad)))
					self.grid_canvas.create_text(pad_x + int(self.column_width / 2), pad_y + int(0.02 * self.row_height),
						width=self.column_width,
						anchor="n", justify="center",
						font=(zynthian_gui_config.font_family, fs1),
						size=int(self.row_height * 0.2),
						fill=zynthian_gui_config.color_panel_tx,
						tags=("lbl_pad:%d"%(pad),"trigger_%d"%(pad)))
					self.grid_canvas.create_text(pad_x + int(self.column_width / 2), pad_y + 2 * fs1,
						width=self.column_width,
						anchor="n", justify="center",
						font=(zynthian_gui_config.font_family, fs2),
						fill=zynthian_gui_config.color_panel_tx,
						tags=("pat_num:%d"%(pad),"trigger_%d"%(pad)))
					self.grid_canvas.create_text(pad_x + int(1.5 * fs1), pad_y + int(0.94 * self.row_height),
						anchor="s",
						font=(zynthian_gui_config.font_family, fs1),
						fill=zynthian_gui_config.color_panel_tx,
						tags=("group:%d"%(pad),"trigger_%d"%(pad)))
					self.grid_canvas.create_image(int(pad_x + self.column_width * 0.23), int(pad_y + 0.9 * self.row_height), tags=("mode:%d"%(pad),"trigger_%d"%(pad)), anchor="sw")
					self.grid_canvas.create_image(int(pad_x + self.column_width * 0.92), int(pad_y + 0.9 * self.row_height), tags=("state:%d"%(pad),"trigger_%d"%(pad)), anchor="se")
					self.grid_canvas.tag_bind("trigger_%d"%(pad), '<Button-1>', self.on_pad_press)
					self.grid_canvas.tag_bind("trigger_%d"%(pad), '<ButtonRelease-1>', self.on_pad_release)
				self.refresh_pad(pad, True)
			self.select_pad()
		except Exception as e:
			logging.warning(e)

		self.redraw_pending = 0
		self.redrawing = False


	# Function to refresh pad if it has changed
	#   pad: Pad index
	#	force: True to force refresh
	def refresh_pad(self, pad, force=False):
		if pad >= self.zynseq.libseq.getSequencesInBank(self.zynseq.bank):
			return
		cell = self.grid_canvas.find_withtag("pad:%d"%(pad))
		if cell:
			if force or self.zynseq.libseq.hasSequenceChanged(self.zynseq.bank, pad):
				mode = self.zynseq.libseq.getPlayMode(self.zynseq.bank, pad)
				state = self.zynseq.libseq.getPlayState(self.zynseq.bank, pad)
				if state == zynseq.SEQ_RESTARTING:
					state = zynseq.SEQ_PLAYING
				if state == zynseq.SEQ_STOPPINGSYNC:
					state = zynseq.SEQ_STOPPING
				group = self.zynseq.libseq.getGroup(self.zynseq.bank, pad)
				foreground = "white"
				if self.zynseq.libseq.getSequenceLength(self.zynseq.bank, pad) == 0 or mode == zynseq.SEQ_DISABLED:
					self.grid_canvas.itemconfig(cell, fill=zynthian_gui_config.PAD_COLOUR_DISABLED)
				else:
					self.grid_canvas.itemconfig(cell, fill=zynthian_gui_config.PAD_COLOUR_STOPPED[group%16])
				pad_x = (pad % self.columns) * self.column_width
				pad_y = int(pad / self.columns) * self.row_height
				if self.zynseq.libseq.getSequenceLength(self.zynseq.bank, pad) == 0:
					mode = 0
				chan = self.zyngui.zynseq.libseq.getChannel(self.zyngui.zynseq.bank, pad, 0)
				label = self.zyngui.zynseq.get_sequence_name(self.zyngui.zynseq.bank, pad)
				try:
					patnum = str(int(label))
					layer = self.zyngui.screens['layer'].get_root_layer_by_midi_chan(chan)
					if layer:
						label = str(layer.preset_name)
					else:
						label = ""
				except:
					patnum = self.zyngui.zynseq.libseq.getPatternAt(self.zyngui.zynseq.bank, pad, 0, 0)
				self.grid_canvas.itemconfig("lbl_pad:%d"%(pad), text=label, fill=foreground)
				self.grid_canvas.itemconfig("pat_num:%d" % (pad), text=patnum, fill=foreground)
				#self.grid_canvas.itemconfig("group:%s"%(pad), text=chr(65 + self.zyngui.zynseq.libseq.getGroup(self.zyngui.zynseq.bank, pad)), fill=foreground)
				self.grid_canvas.itemconfig("group:%s" % (pad), text="{}".format(chan+1), fill=foreground)				self.grid_canvas.itemconfig("mode:%d"%pad, image=self.mode_icon[mode])
				if state == 0 and self.zynseq.libseq.isEmpty(self.zynseq.bank, pad):
					self.grid_canvas.itemconfig("state:%d"%pad, image=self.empty_icon)
				else:
					self.grid_canvas.itemconfig("state:%d"%pad, image=self.state_icon[state])


	# Function to handle pad press
	def on_pad_press(self, event):
		tags = self.grid_canvas.gettags(self.grid_canvas.find_withtag(tkinter.CURRENT))
		pad = int(tags[0].split(':')[1])
		self.select_pad(pad)
		if self.param_editor_zctrl:
			self.disable_param_editor()
		self.grid_timer = Timer(1.4, self.on_grid_timer)
		self.grid_timer.start()


	# Function to handle pad release
	def on_pad_release(self, event):
		if self.grid_timer.isAlive():
			self.toggle_pad()
		self.grid_timer.cancel()


	# Function to toggle pad
	def toggle_pad(self):
		self.zynseq.libseq.togglePlayState(self.zynseq.bank, self.selected_pad)


	# Function to handle grid press and hold
	def on_grid_timer(self):
		self.gridDragStart = None
		self.show_pattern_editor()


	# Function to add menus
	def show_menu(self):
		self.disable_param_editor()
		options = OrderedDict()
		options[f'Tempo ({self.zynseq.libseq.getTempo():0.1f})'] = 'Tempo'
		options['Arranger'] = 'Arranger'
		options['Beats per bar ({})'.format(self.zyngui.zynseq.libseq.getBeatsPerBar())] = 'Beats per bar'
		options['Bank ({})'.format(self.zyngui.zynseq.bank)] = 'Bank'
		options['> PADS'] = None
		options['Play mode ({})'.format(zynseq.PLAY_MODES[self.zynseq.libseq.getPlayMode(self.zynseq.bank, self.selected_pad)])] = 'Play mode'
		options['MIDI channel ({})'.format(1 + self.zynseq.libseq.getChannel(self.zynseq.bank, self.selected_pad, 0))] = 'MIDI channel'
		trigger_channel = self.get_trigger_channel()
		if trigger_channel == 0:
			options['Trigger channel (OFF)'] = 'Trigger channel'
		else:
			options['Trigger channel ({})'.format(trigger_channel)] = 'Trigger channel'
			note = self.zynseq.libseq.getTriggerNote(self.zynseq.bank, self.selected_pad)
			if note < 128:
				trigger_note = "{}{}".format(NOTE_NAMES[note % 12], note // 12 - 1)
			else:
				trigger_note = "None"
			options['Trigger note ({})'.format(trigger_note)] = 'Trigger note'
		tally_channel = self.get_tally_channel()
		if tally_channel == 0:
			tally_channel = 'OFF'
		options['Tally channel ({})'.format(tally_channel)] = 'Tally channel'
		options['> MISC'] = None
		options['Grid size ({}x{})'.format(self.columns, self.columns)] = 'Grid size'
		options['Rename sequence'] = 'Rename sequence'
		self.zyngui.screens['option'].config("ZynPad Menu", options, self.menu_cb)
		self.zyngui.show_screen('option')


	def toggle_menu(self):
		if self.shown:
			self.show_menu()
		elif self.zyngui.current_screen == "option":
			self.close_screen()


	def menu_cb(self, option, params):
		if params == 'Tempo':
			self.zyngui.show_screen('tempo')
		elif params == 'Arranger':
			self.zyngui.show_screen('arranger')
		elif params == 'Beats per bar':
			self.enable_param_editor(self, 'bpb', 'Beats per bar', {'value_min':1, 'value_max':64, 'value_default':4, 'value':self.zyngui.zynseq.libseq.getBeatsPerBar()})
		elif params == 'Bank':
			self.enable_param_editor(self, 'bank', 'Bank', {'value_min':1, 'value_max':64, 'value':self.zynseq.bank})
		elif params == 'Play mode':
			self.enable_param_editor(self, 'playmode', 'Play mode', {'labels':zynseq.PLAY_MODES, 'value':self.zynseq.libseq.getPlayMode(self.zynseq.bank, self.selected_pad), 'value_default':zynseq.SEQ_LOOPALL}, self.set_play_mode)
		elif params == 'MIDI channel':
			labels = []
			for chan in range(16):
				chain = self.zyngui.chain_manager.midi_chan_2_chain[chan]
				try:
					labels.append(f"{chan + 1} {chain.get_processors('Synth', 0)[0].get_preset_name()}")
				except:
					labels.append(f"{chan + 1}")
			self.enable_param_editor(self, 'midi_chan', 'MIDI channel', {'labels':labels, 'value_default':self.zynseq.libseq.getChannel(self.zynseq.bank, self.selected_pad, 0), 'value':self.zynseq.libseq.getChannel(self.zynseq.bank, self.selected_pad, 0)})
		elif params == 'Trigger channel':
			self.enable_param_editor(self, 'trigger_chan', 'Trigger channel', {'labels':INPUT_CHANNEL_LABELS, 'value':self.get_trigger_channel()})
		elif params == 'Trigger note':
			labels = ['None']
			for note in range(128):
				labels.append("{}{}".format(NOTE_NAMES[note % 12], note // 12 - 1))
			value = self.zynseq.libseq.getTriggerNote(self.zynseq.bank, self.selected_pad) + 1
			if value > 128:
				value = 0
			self.enable_param_editor(self, 'trigger_note', 'Trigger note', {'labels':labels, 'value':value})
			self.zynseq.enable_midi_learn(self.zynseq.bank, self.selected_pad)
		elif params == 'Tally channel':
			self.enable_param_editor(self, 'tally_chan', 'Tally channel', {'labels':INPUT_CHANNEL_LABELS, 'value':self.get_tally_channel()})
		elif params == 'Grid size':
			labels = []
			for i in range(1, 9):
				labels.append("{}x{}".format(i,i))
			self.enable_param_editor(self, 'grid_size', 'Grid size', {'labels':labels, 'value':self.columns - 1, 'value_default':3}, self.set_grid_size)
		elif params == 'Rename sequence':
			self.rename_sequence()


	def send_controller_value(self, zctrl):
		if zctrl.symbol == 'bank':
			self.zynseq.select_bank(zctrl.value)
		elif zctrl.symbol == 'tempo':
			self.zynseq.set_tempo(zctrl.value)
		elif zctrl.symbol == 'metro_vol':
			self.zynseq.libseq.setMetronomeVolume(zctrl.value / 100.0)
		elif zctrl.symbol == 'bpb':
			self.zynseq.libseq.setBeatsPerBar(zctrl.value)
		elif zctrl.symbol == 'playmode':
			self.set_play_mode(zctrl.value)
		elif zctrl.symbol == 'midi_chan':
			self.zynseq.set_midi_channel(self.zynseq.bank, self.selected_pad, 0, zctrl.value)
			self.zynseq.set_group(self.zynseq.bank, self.selected_pad, zctrl.value)
		elif zctrl.symbol == 'trigger_chan':
			if zctrl.value:
				self.zynseq.libseq.setTriggerChannel(zctrl.value - 1)
			else:
				self.zynseq.libseq.setTriggerChannel(0xFF)
		elif zctrl.symbol == 'trigger_note':
			if zctrl.value == 0:
				value = 128
			else:
				value = zctrl.value - 1
			self.zynseq.libseq.setTriggerNote(self.zynseq.bank, self.selected_pad, value)
		elif zctrl.symbol == 'tally_chan':
			if zctrl.value:
				self.zynseq.libseq.setTallyChannel(zctrl.value - 1)
			else:
				self.zynseq.libseq.setTallyChannel(0xFF)

	#	Function to set the playmode of the selected pad
	def set_play_mode(self, mode):
		self.zynseq.set_play_mode(self.zynseq.bank, self.selected_pad, mode)


	# Function to show the editor (pattern or arranger based on sequence content)
	def show_pattern_editor(self):
		tracks_in_sequence = self.zynseq.libseq.getTracksInSequence(self.zynseq.bank, self.selected_pad)
		patterns_in_track = self.zynseq.libseq.getPatternsInTrack(self.zynseq.bank, self.selected_pad, 0)
		pattern = self.zynseq.libseq.getPattern(self.zynseq.bank, self.selected_pad, 0, 0)
		if tracks_in_sequence != 1 or patterns_in_track !=1 or pattern == -1:
			self.zyngui.screens["arranger"].sequence = self.selected_pad
			self.zyngui.toggle_screen("arranger")
			return True
		self.zyngui.screens['pattern_editor'].channel = self.zynseq.libseq.getChannel(self.zynseq.bank, self.selected_pad, 0)
		self.zyngui.screens['pattern_editor'].load_pattern(pattern)
		self.zyngui.screens['pattern_editor'].bank = self.bank
		self.zyngui.screens['pattern_editor'].sequence = self.selected_pad
		self.zyngui.show_screen("pattern_editor")
		return True


	# Function to refresh status
	def refresh_status(self, status={}):
		super().refresh_status(status)
		if self.redraw_pending:
			self.update_grid()
		force = self.zynseq.bank != self.bank
		if not self.redrawing:
			self.bank = self.zynseq.bank
			for pad in range(0, self.columns**2):
				self.refresh_pad(pad, force)


	# Function to select a pad
	#	pad: Index of pad to select (Default: refresh existing selection)
	def select_pad(self, pad=None):
		if pad is not None:
			self.selected_pad = pad
		if self.selected_pad >= self.zynseq.libseq.getSequencesInBank(self.zynseq.bank):
			self.selected_pad = self.zynseq.libseq.getSequencesInBank(self.zynseq.bank) - 1
		col = int(self.selected_pad / self.columns)
		row = self.selected_pad % self.columns
		self.grid_canvas.coords(self.selection,
			1 + col * self.column_width, 1 + row * self.row_height,
			(1 + col) * self.column_width - self.select_thickness, (1 + row) * self.row_height - self.select_thickness)
		self.grid_canvas.tag_raise(self.selection)


	# Function to handle zynpots value change
	#   encoder: Zynpot index [0..n]
	#   dval: Zynpot value change
	def zynpot_cb(self, encoder, dval):
		if super().zynpot_cb(encoder, dval):
			return
		if encoder == zynthian_gui_config.ENC_SELECT:
			# BACK encoder adjusts horizontal pad selection
			pad = self.selected_pad + self.columns * dval
			col = int(pad / self.columns)
			row = pad % self.columns
			if col >= self.columns:
				col = 0
				row += 1
				pad = row + self.columns * col
			elif pad < 0:
				col = self.columns -1
				row -= 1
				pad = row + self.columns * col
			if row < 0 or row >= self.columns or col >= self.columns:
				return
			self.select_pad(pad)
		elif encoder == zynthian_gui_config.ENC_BACK:
			# SELECT encoder adjusts vertical pad selection
			pad = self.selected_pad + dval
			if pad < 0 or pad >= self.zynseq.libseq.getSequencesInBank(self.zynseq.bank):
				return
			self.select_pad(pad)
		elif encoder == zynthian_gui_config.ENC_SNAPSHOT and zynthian_gui_config.transport_clock_source == 0:
			self.zynseq.update_tempo()
			self.zynseq.nudge_tempo(dval)
			self.set_title("Tempo: {:.1f}".format(self.zynseq.get_tempo()), None, None, 2)
		elif encoder == zynthian_gui_config.ENC_LAYER:
			self.zynseq.select_bank(self.zynseq.bank + dval)
			self.set_title("Bank {}".format(self.zynseq.bank))


	# Function to handle SELECT button press
	#	type: Button press duration ["S"=Short, "B"=Bold, "L"=Long]
	def switch_select(self, type='S'):
		if super().switch_select(type):
			return True
		if type == 'S':
			self.toggle_pad()
		elif type == "B":
			self.show_pattern_editor()


	# Function to handle switch press
	#	switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def switch(self, switch, type):
		self.zynseq.disable_midi_learn()
		if switch == zynthian_gui_config.ENC_LAYER and type == 'B':
			self.show_menu()
			return True
		return False


	#	CUIA Actions
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


#------------------------------------------------------------------------------
