#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Main Menu Grid Class
#
# Copyright (C) 2025-2026 Fernando Moyano <jofemodo@zynthian.org>
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

from time import sleep

from zyngine.zynthian_signal_manager import zynsigman
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector_grid import zynthian_gui_selector_grid


class zynthian_gui_main_menu(zynthian_gui_selector_grid):
    """
    Fast menu presented as a grid of buttons.
    """
    def __init__(self):
        super().__init__()
        self.get_config = self._get_config
        self.title = "Main Menu"
        if zynthian_gui_config.check_wiring_layout(("V5", "Z2")) or zynthian_gui_config.screen_width < 800:
            self.columns = 3
        else:
            self.columns = 4

    def build_view(self):
        zynsigman.register_queued(zynsigman.S_AUDIO_RECORDER, zynsigman.SS_AUDIO_RECORDER_STATE, self.update_status_audio_recording)
        zynsigman.register_queued(zynsigman.S_STATE_MAN, zynsigman.SS_MIDI_RECORDER_STATE, self.update_status_midi_recording)
        return super().build_view()

    def update_status_audio_recording(self, state):
        if self.columns == 3:
            scr = self.zyngui.screens["grid_sel"]
            if scr.shown and scr.title == "Play & Record":
                scr.update_node(0, self.get_node_toggle_audio_rec(state))
        elif self.columns == 4 and self.shown:
            self.update_node(8, self.get_node_toggle_audio_rec(state))

    def update_status_midi_recording(self, state):
        if self.columns == 3:
            scr = self.zyngui.screens["grid_sel"]
            if scr.shown and scr.title == "Play & Record":
                scr.update_node(2, self.get_node_toggle_midi_rec(state))
        elif self.columns == 4 and self.shown:
            self.update_node(10, self.get_node_toggle_midi_rec(state))

    def _get_config(self):
        if self.columns == 3:
            config = [{
                "title": "Add\nChain",
                "icon": "add_chain.png",
                "action": self.zyngui.cuia_add_chain
            }, {
                "title": "Chain\nManager",
                "icon": "chain_manager.png",
                "action": self.zyngui.cuia_screen_chain_manager
            }, {
                "title": "Clean",
                "icon": "delete.png",
                "action": self.clean_menu
            },
            {
                "title": "MIDI\nInput",
                "icon": "midi_input.png",
                "action": self.zyngui.midi_in_config
            },{
                "title": "MIDI\nOutput",
                "icon": "midi_output.png",
                "action": self.zyngui.midi_out_config
            }, {
                "title": "Play &\nRecord",
                "icon": "recorder.png",
                "action": self.playrec_menu
            },
            {
                "title": "Admin",
                "icon": "settings.png",
                "action": self.zyngui.cuia_screen_admin
            }, {
                "title": "Capturing\nWorkflow" if self.zyngui.capture_log_fname else "Capture\nWorkflow",
                "icon": "capturing.png" if self.zyngui.capture_log_fname else "capture.png",
                "action": self.toggle_capture_log
            }, {
                "title": "Power",
                "icon": "poweroff.png",
                "action": self.zyngui.cuia_power
            }]
        elif self.columns == 4:
            config = [{
                "title": "Add\nChain",
                "icon": "add_chain.png",
                "action": self.zyngui.cuia_add_chain
            }, {
                "title": "Chain\nManager",
                "icon": "chain_manager.png",
                "action": self.zyngui.cuia_screen_chain_manager
            }, {
                "title": "Snapshots",
                "icon": "snapshot.png",
                "action": self.zyngui.cuia_screen_snapshot
            }, {
                "title": "Clean",
                "icon": "delete.png",
                "action": self.clean_menu
            },
            {
                "title": "MIDI\nInput",
                "icon": "midi_input.png",
                "action": self.zyngui.midi_in_config
            }, {
                "title": "MIDI\nOutput",
                "icon": "midi_output.png",
                "action": self.zyngui.midi_in_config
            }, {
                "title": "Tempo",
                "icon": "metronome.png",
                "action": self.zyngui.cuia_tempo
            }, {
                "title": "ZS3s",
                "icon": "zs3.png",
                "action": self.zyngui.cuia_screen_zs3
            }]
            config += self.get_playrec_options()
            config += [{
                "title": "Admin",
                "icon": "settings.png",
                "action": self.zyngui.cuia_screen_admin
            }, {
                "title": "Audio\nLevels",
                "icon": "audio_options.png",
                "action": self.zyngui.cuia_screen_alsa_mixer
            }, {
                "title": "Capturing\nWorkflow" if self.zyngui.capture_log_fname else "Capture\nWorkflow",
                "icon": "capturing.png" if self.zyngui.capture_log_fname else "capture.png",
                "action": self.toggle_capture_log
            }, {
                "title": "Power",
                "icon": "poweroff.png",
                "action": self.zyngui.cuia_power
            }]
        return config

    # Claen submenu

    def clean_menu(self):
        self.zyngui.screens["grid_sel"].setup("Confirm Clean", [
                { "icon": "delete_chains.png", "title": "Clean All Chains", "action": self.clean_chains_confirmed },
                { "icon": "delete_sequences.png", "title": "Clean All Sequences", "action": self.clean_sequences_confirmed },
                { "icon": "delete_all.png", "title": "Clean All Chains & Sequences", "action": self.clean_all_confirmed },
                None, None, None,
                { "icon": "cancel.png", "title": "Cancel", "action": self.zyngui.close_screen }
            ], cols=3, select=2)
        self.zyngui.show_screen("grid_sel")

    def clean_chains_confirmed(self, params=None):
        self.zyngui.clean_chains()
        self.zyngui.show_screen_reset('mixer')

    def clean_sequences_confirmed(self, params=None):
        self.zyngui.clean_sequences()
        self.zyngui.show_screen_reset('launcher')

    def clean_all_confirmed(self, params=None):
        self.zyngui.clean_all()
        self.zyngui.show_screen_reset('root')

    # Play & Record

    def playrec_menu(self, select=0):
        self.zyngui.screens["grid_sel"].setup("Play & Record", self.get_playrec_options, cols=2, select=select)
        self.zyngui.show_screen("grid_sel")

    def get_playrec_options(self):
        return [
            self.get_node_toggle_audio_rec(),
            {
                "icon": "folder_audio.png",
                "title": "Audio\nPlayer",
                "action": self.zyngui.cuia_audio_file_list
            },
            self.get_node_toggle_midi_rec(),
            {
                "icon": "folder_midi.png",
                "title": "MIDI\nPlayer",
                "action": self.zyngui.cuia_screen_midi_recorder
            }
        ]

    def get_node_toggle_audio_rec(self, state=None):
        if state is None:
            state = self.state_manager.audio_recorder.status
        return {
            "icon": "audio_recording.png" if state else "audio_recorder.png",
            "title": "Stop Audio\nRecording" if state else "Start Audio\nRecording",
            "action": self.zyngui.cuia_toggle_audio_record
        }

    def get_node_toggle_midi_rec(self, state=None):
        if state is None:
            state = self.state_manager.status_midi_recorder
        return  {
            "icon": "midi_recording.png" if state else "midi_recorder.png",
            "title": "Stop MIDI\nRecording" if state else "Start MIDI\nRecording",
            "action": self.zyngui.cuia_toggle_midi_record
        }

    # Workflow Capture

    def toggle_capture_log(self):
        if self.zyngui.capture_log_fname:
            self.zyngui.stop_capture_log()
            self.build_view()
        else:
            self.zyngui.start_capture_log()
            self.zyngui.close_screen()
