#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Main Menu Class
#
# Copyright (C) 2015-2020 Fernando Moyano <jofemodo@zynthian.org>
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

import logging

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector
from zynlibs.zynseq import zynseq

#------------------------------------------------------------------------------
# Zynthian App Selection GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_main(zynthian_gui_selector):

	def __init__(self):
		super().__init__('Main', True)


	def fill_list(self):
		self.list_data=[]

		# Main Apps
		self.list_data.append((self.new_synth_layer,0,"New Synth Chain"))
		self.list_data.append((self.new_audiofx_layer,0,"New Audio Chain"))
		self.list_data.append((self.new_midifx_layer,0,"New MIDI Chain"))
		self.list_data.append((self.new_generator_layer,0,"New Generator Chain"))
		self.list_data.append((self.new_special_layer,0,"New Special Chain"))
		self.list_data.append((self.snapshots,0,"Snapshots"))
		self.list_data.append((self.clean_all,0,"Clean All"))

		# Add list of Apps
		self.list_data.append((None,0,"-----------------------------"))
		self.list_data.append((self.step_sequencer,0,"Sequencer"))
		self.list_data.append((self.midi_recorder,0,"MIDI Recorder"))
		self.list_data.append((self.alsa_mixer,0,"Audio Levels"))

		self.list_data.append((None,0,"-----------------------------"))
		self.list_data.append((self.admin,0,"Admin"))
		self.list_data.append((self.all_notes_off,0,"PANIC! All Notes Off"))

		super().fill_list()


	def select_action(self, i, t='S'):
		if self.list_data[i][0]:
			self.last_action=self.list_data[i][0]
			self.last_action(t)


	def new_synth_layer(self, t='S'):
		self.zyngui.screens['layer'].add_layer("MIDI Synth")


	def new_audiofx_layer(self, t='S'):
		self.zyngui.screens['layer'].add_layer("Audio Effect")


	def new_midifx_layer(self, t='S'):
		self.zyngui.screens['layer'].add_layer("MIDI Tool")


	def new_generator_layer(self, t='S'):
		self.zyngui.screens['layer'].add_layer("Audio Generator")


	def new_special_layer(self, t='S'):
		self.zyngui.screens['layer'].add_layer("Special")


	def snapshots(self, t='S'):
		logging.info("Snapshots")
		self.zyngui.show_screen_reset("snapshot")


	def clean_all(self, t='S'):
		self.zyngui.show_confirm("Do you really want to clean all?", self.clean_all_confirmed)


	def clean_all_confirmed(self, params=None):
		if len(self.zyngui.screens['layer'].layers)>0:
			self.zyngui.screens['snapshot'].save_last_state_snapshot()
		self.zyngui.screens['layer'].reset()
		self.zyngui.screens['audio_mixer'].reset_state()
		if zynseq.libseq:
			zynseq.load("")
		self.index = 0
		self.zyngui.show_screen_reset('main')


	def audio_mixer(self, t='S'):
		logging.info("Audio Mixer")
		self.zyngui.show_screen_reset('audio_mixer')


	def step_sequencer(self, t='S'):
		logging.info("Step Sequencer")
		self.zyngui.show_screen_reset('stepseq')


	def midi_recorder(self, t='S'):
		logging.info("MIDI Recorder")
		self.zyngui.show_screen_reset("midi_recorder")


	def alsa_mixer(self, t='S'):
		logging.info("ALSA Mixer")
		self.zyngui.show_screen_reset("alsa_mixer")


	def admin(self, t='S'):
		logging.info("Admin")
		self.zyngui.show_screen_reset("admin")


	def all_notes_off(self, t='S'):
		logging.info("All Notes Off")
		self.zyngui.callable_ui_action("ALL_OFF")


	def set_select_path(self):
		self.select_path.set("Main")


#------------------------------------------------------------------------------
