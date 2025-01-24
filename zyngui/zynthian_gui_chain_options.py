#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Chain Options Class
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
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

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector_info import zynthian_gui_selector_info

# ------------------------------------------------------------------------------
# Zynthian Chain Options GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_chain_options(zynthian_gui_selector_info):

    def __init__(self):
        super().__init__('Option')
        self.index = 0
        self.chain = None
        self.chain_id = None
        self.processor = None

    def setup(self, chain_id=None, proc=None):
        self.index = 0
        self.chain = self.zyngui.chain_manager.get_chain(chain_id)
        self.chain_id = self.chain.chain_id
        self.processor = proc

    def fill_list(self):
        self.list_data = []

        synth_proc_count = self.chain.get_processor_count("Synth")
        midi_proc_count = self.chain.get_processor_count("MIDI Tool")
        audio_proc_count = self.chain.get_processor_count("Audio Effect")

        if self.chain.is_midi():
            self.list_data.append((self.chain_note_range, None, "Note Range & Transpose",
                                   ["Configure note range and transpose by octaves and semitones.", "note_range.png"]))
            self.list_data.append((self.chain_midi_capture, None, "MIDI In",
                                   ["Manage MIDI input sources. Enable/disable MIDI sources, toggle active/multi-timbral mode, load controller drivers, etc.", "midi_input.png"]))

        if self.chain.midi_thru:
            self.list_data.append((self.chain_midi_routing, None, "MIDI Out",
                                   ["Manage MIDI output routing to external devices and other chains.", "midi_output.png"]))

        if self.chain.is_midi():
            try:
                if synth_proc_count == 0 or self.chain.synth_slots[0][0].engine.options["midi_chan"]:
                    self.list_data.append((self.chain_midi_chan, None, "MIDI Channel",
                                           ["Select MIDI channel to receive from.", "midi_settings.png"]))
            except Exception as e:
                logging.error(e)

        if synth_proc_count:
            self.list_data.append((self.chain_midi_cc, None, "MIDI CC",
                                   ["Select MIDI CC numbers passed-thru to chain processors. It could interfere with MIDI-learning. Use with caution!", "midi_settings.png"]))

        if self.chain.get_processor_count() and not zynthian_gui_config.check_wiring_layout(["Z2", "V5"]):
            # TODO Disable midi learn for some chains???
            self.list_data.append((self.midi_learn, None, "MIDI Learn",
                                   ["Enter MIDI-learning mode for processor parameters.", "midi_learn.png"]))

        if self.chain.audio_thru and self.chain_id != 0:
            self.list_data.append((self.chain_audio_capture, None, "Audio In",
                                  ["Manage audio capture sources.", "audio_input.png"]))

        if self.chain.is_audio():
            self.list_data.append((self.chain_audio_routing, None, "Audio Out",
                                   ["Manage audio output routing.", "audio_output.png"]))

        if self.chain.is_audio():
            self.list_data.append((self.audio_options, None, "Mixer Options",
                                   ["Extra audio mixer options.", "audio_options.png"]))

        # TODO: Catch signal for Audio Recording status change
        if self.chain_id == 0 and not zynthian_gui_config.check_wiring_layout(["Z2", "V5"]):
            if self.zyngui.state_manager.audio_recorder.status:
                self.list_data.append((self.toggle_recording, None, "■ Stop Audio Recording",
                                       ["Stop audio recording", "audio_recorder.png"]))
            else:
                self.list_data.append((self.toggle_recording, None, "⬤ Start Audio Recording",
                                       ["Start audio recording", "audio_recorder.png"]))

        self.list_data.append((None, None, "> Processors"))

        if self.chain.is_midi():
            # Add MIDI-FX options
            self.list_data.append((self.midifx_add, None, "Add MIDI-FX",
                                   ["Add a new MIDI processor to process chain's MIDI input.", "midi_processor.png"]))

        self.list_data += self.generate_chaintree_menu()

        if self.chain.is_audio():
            # Add Audio-FX options
            self.list_data.append((self.audiofx_add, None, "Add Pre-fader Audio-FX",
                                   ["Add a new audio processor to process chain's audio before the mixer's fader.", "audio_processor.png"]))
            self.list_data.append((self.postfader_add, None, "Add Post-fader Audio-FX",
                                   ["Add a new audio processor to process chain's audio after the mixer's fader.", "audio_processor.png"]))

        if self.chain_id != 0:
            if synth_proc_count * midi_proc_count + audio_proc_count == 0:
                self.list_data.append((self.remove_chain, None, "Remove Chain",
                                       ["Remove this chain and all its processors.", "delete_chains.png"]))
            else:
                self.list_data.append((self.remove_cb, None, "Remove...",
                                       ["Remove chain or processors.", "delete_chains.png"]))
            self.list_data.append((self.export_chain, None, "Export chain as snapshot...",
                                   ["Save the selected chain as a snapshot which may then be imported into another snapshot.", "snapshot_chains.png"]))
        elif audio_proc_count > 0:
            self.list_data.append((self.remove_all_audiofx, None, "Remove all Audio-FX",
                                   ["Remove all audio-FX processors in this chain.", "delete_audio_processors.png"]))

        self.list_data.append((None, None, "> GUI"))
        self.list_data.append((self.rename_chain, None, "Rename chain",
                               ["Rename the chain. Clear name to reset to default name.", "rename.png"]))
        if self.chain_id:
            if len(self.zyngui.chain_manager.ordered_chain_ids) > 2:
                self.list_data.append((self.move_chain, None, "Move chain ⇦ ⇨",
                                       ["Reposition the chain in the mixer view.", "move_left_right.png"]))

        super().fill_list()

    # Generate chain tree menu
    def generate_chaintree_menu(self):
        res = []
        indent = 0
        # Build MIDI chain
        for slot in range(self.chain.get_slot_count("MIDI Tool")):
            procs = self.chain.get_processors("MIDI Tool", slot)
            num_procs = len(procs)
            for index, processor in enumerate(procs):
                name = processor.get_name()
                if index == num_procs - 1:
                    text = "  " * indent + "╰─ " + name
                else:
                    text = "  " * indent + "├─ " + name

                res.append((self.processor_options, processor, text,
                            [f"Options for MIDI processor '{name}'", "midi_processor.png"]))

            indent += 1
        # Add synth processor
        for slot in self.chain.synth_slots:
            for processor in slot:
                name = processor.get_name()
                text = "  " * indent + "╰━ " + name
                res.append((self.processor_options, processor, text,
                            [f"Options for synth processor '{name}'", "synth_processor.png"]))
                indent += 1
        # Build pre-fader audio effects chain
        for slot in range(self.chain.fader_pos):
            if self.chain.fader_pos <= slot:
                break
            procs = self.chain.get_processors("Audio Effect", slot)
            num_procs = len(procs)
            for index, processor in enumerate(procs):
                name = processor.get_name()
                if index == num_procs - 1:
                    text = "  " * indent + "┗━ " + name
                else:
                    text = "  " * indent + "┣━ " + name
                res.append((self.processor_options, processor, text,
                            [f"Options for pre-fader audio processor '{name}'", "audio_processor.png"]))
            indent += 1
        # Add FADER mark
        if self.chain.audio_thru or self.chain.synth_slots:
            res.append((None, None, "  " * indent + "┗━ FADER"))
            indent += 1
        # Build post-fader audio effects chain
        for slot in range(self.chain.fader_pos, len(self.chain.audio_slots)):
            procs = self.chain.get_processors("Audio Effect", slot)
            num_procs = len(procs)
            for index, processor in enumerate(procs):
                name = processor.get_name()
                if index == num_procs - 1:
                    text = "  " * indent + "┗━ " + name
                else:
                    text = "  " * indent + "┣━ " + name
                res.append((self.processor_options, processor, text,
                            [f"Options for post-fader audio processor '{name}'", "audio_processor.png"]))
            indent += 1
        return res

    def fill_listbox(self):
        super().fill_listbox()
        for i, val in enumerate(self.list_data):
            if val[0] == None:
                self.listbox.itemconfig(
                    i, {'bg': zynthian_gui_config.color_panel_hl, 'fg': zynthian_gui_config.color_tx_off})

    def build_view(self):
        if self.chain is None:
            self.setup()

        if self.chain is not None:
            super().build_view()
            if self.index >= len(self.list_data):
                self.index = len(self.list_data) - 1
            return True
        else:
            return False

    def select_action(self, i, t='S'):
        self.index = i
        if self.list_data[i][0] is None:
            pass
        elif self.list_data[i][1] is None:
            self.list_data[i][0]()
        else:
            self.list_data[i][0](self.list_data[i][1], t)

    # Function to handle zynpots value change
    #   i: Zynpot index [0..n]
    #   dval: Current value of zyncoder
    def zynpot_cb(self, i, dval):
        if i == 2:
            try:
                processor = self.list_data[self.index][1]
                if processor is not None and self.zyngui.chain_manager.nudge_processor(self.chain_id, processor, dval < 0):
                    self.fill_list()
                    for index, data in enumerate(self.list_data):
                        if processor == data[1]:
                            self.select(index)
                            break
            except:
                pass  # Ignore failure to move processor
        else:
            super().zynpot_cb(i, dval)

    def arrow_right(self):
        chain_keys = self.zyngui.chain_manager.ordered_chain_ids
        try:
            index = chain_keys.index(self.chain_id) + 1
        except:
            index = len(chain_keys) - 1
        if index < len(chain_keys):
            # We don't call setup() because it reset the list position (index)
            self.chain_id = chain_keys[index]
            self.chain = self.zyngui.chain_manager.get_chain(self.chain_id)
            self.processor = None
            self.set_select_path()
            self.fill_list()

    def arrow_left(self):
        chain_keys = self.zyngui.chain_manager.ordered_chain_ids
        try:
            index = chain_keys.index(self.chain_id) - 1
        except:
            index = 0
        if index >= 0:
            # We don't call setup() because it reset the list position (index)
            self.chain_id = chain_keys[index]
            self.chain = self.zyngui.chain_manager.get_chain(self.chain_id)
            self.processor = None
            self.set_select_path()
            self.fill_list()

    def processor_options(self, subchain, t='S'):
        self.zyngui.screens['processor_options'].setup(self.chain_id, subchain)
        self.zyngui.show_screen("processor_options")

    def chain_midi_chan(self):
        #if self.chain.get_type() == "MIDI Tool":
        #    chan_all = True
        #else:
        #    chan_all = False
        self.zyngui.screens['midi_chan'].set_mode("SET", self.chain.midi_chan, chan_all=True)
        self.zyngui.show_screen('midi_chan')

    def chain_midi_cc(self):
        self.zyngui.screens['midi_cc'].set_chain(self.chain)
        self.zyngui.show_screen('midi_cc')

    def chain_note_range(self):
        self.zyngui.screens['midi_key_range'].config(self.chain)
        self.zyngui.show_screen('midi_key_range')

    def midi_learn(self):
        options = {}
        options['Enter MIDI-learn'] = "enable_midi_learn"
        options['Enter Global MIDI-learn'] = "enable_global_midi_learn"
        if self.processor:
            options[f'Clear {self.processor.name} MIDI-learn'] = "clean_proc"
        options['Clear chain MIDI-learn'] = "clean_chain"
        self.zyngui.screens['option'].config(
            "MIDI-learn", options, self.midi_learn_menu_cb)
        self.zyngui.show_screen('option')

    def midi_learn_menu_cb(self, options, params):
        if params == 'enable_midi_learn':
            self.zyngui.close_screen()
            self.zyngui.cuia_toggle_midi_learn()
        elif params == 'enable_global_midi_learn':
            self.zyngui.close_screen()
            self.zyngui.cuia_toggle_midi_learn()
            self.zyngui.cuia_toggle_midi_learn()
        elif params == 'clean_proc':
            self.zyngui.show_confirm(
                f"Do you want to clean MIDI-learn for ALL controls in processor {self.processor.name}?", self.zyngui.chain_manager.clean_midi_learn, self.processor)
        elif params == 'clean_chain':
            self.zyngui.show_confirm(
                f"Do you want to clean MIDI-learn for ALL controls in ALL processors within chain {self.chain_id:02d}?", self.zyngui.chain_manager.clean_midi_learn, self.chain_id)

    def chain_midi_routing(self):
        self.zyngui.screens['midi_config'].set_chain(self.chain)
        self.zyngui.screens['midi_config'].input = False
        self.zyngui.show_screen('midi_config')

    def chain_audio_routing(self):
        self.zyngui.screens['audio_out'].set_chain(self.chain)
        self.zyngui.show_screen('audio_out')

    def audio_options(self):
        options = {}
        if self.zyngui.state_manager.zynmixer.get_mono(self.chain.mixer_chan):
            options['\u2612 Mono'] = ['mono', ["Chain is mono.\n\nLeft and right inputs are summed and fed as mono to left and right outputs", None]]
        else:
            options['\u2610 Mono'] = ['mono', ["Chain is stereo.\n\nLeft input feeds left output and right input feeds right output.", None]]
        if self.zyngui.state_manager.zynmixer.get_phase(self.chain.mixer_chan):
            options['\u2612 Phase reverse'] = ['phase', ["Chain is phase reversed.\n\nRight output is inverted, making it 180° out of phase with its input.", None]]
        else:
            options['\u2610 Phase reverse'] = ['phase', ["Chain is not phase reversed.\n\nLeft and right inputs feed left and right outputs without phase modification.", None]]
        if self.zyngui.state_manager.zynmixer.get_ms(self.chain.mixer_chan):
            options['\u2612 M+S'] = ['ms', ["Mid/Side mode is enabled.\n\nLeft output carries the 'Mid' signal. Right output carries the 'Side' signal.", None]]
        else:
            options['\u2610 M+S'] = ['ms', ["Mid/Side mode is disabled.\n\nLeft and right inputs feed left and right outputs.", None]]

        self.zyngui.screens['option'].config(
            "Mixer options", options, self.audio_menu_cb, False, False, None)
        self.zyngui.show_screen('option')

    def audio_menu_cb(self, options, params):
        if params == 'mono':
            self.zyngui.state_manager.zynmixer.toggle_mono(
                self.chain.mixer_chan)
        elif params == 'phase':
            self.zyngui.state_manager.zynmixer.toggle_phase(
                self.chain.mixer_chan)
        elif params == 'ms':
            self.zyngui.state_manager.zynmixer.toggle_ms(self.chain.mixer_chan)
        self.audio_options()

    def chain_audio_capture(self):
        self.zyngui.screens['audio_in'].set_chain(self.chain)
        self.zyngui.show_screen('audio_in')

    def chain_midi_capture(self):
        self.zyngui.screens['midi_config'].set_chain(self.chain)
        self.zyngui.screens['midi_config'].input = True
        self.zyngui.show_screen('midi_config')

    def toggle_recording(self):
        if self.processor and self.processor.engine and self.processor.engine.name == 'AudioPlayer':
            self.zyngui.state_manager.audio_recorder.toggle_recording(
                self.processor)
        else:
            self.zyngui.state_manager.audio_recorder.toggle_recording(
                self.zyngui.state_manager.audio_player)
        self.fill_list()

    def move_chain(self):
        self.zyngui.screens["audio_mixer"].moving_chain = True
        self.zyngui.show_screen_reset('audio_mixer')

    def rename_chain(self):
        self.zyngui.show_keyboard(self.do_rename_chain, self.chain.title)

    def do_rename_chain(self, title):
        self.chain.title = title
        self.zyngui.show_screen_reset('audio_mixer')

    def export_chain(self):
        options = {}
        dirs = os.listdir(self.zyngui.state_manager.snapshot_dir)
        dirs.sort()
        for dir in dirs:
            if dir.startswith(".") or not os.path.isdir(f"{self.zyngui.state_manager.snapshot_dir}/{dir}"):
                continue
            options[dir] = [dir, ["Choose folder to store snapshot.", "folder.png"]]
        self.zyngui.screens['option'].config(
            "Select location for export", options, self.name_export)
        self.zyngui.show_screen('option')

    def name_export(self, param1, param2):
        self.export_dir = param1
        self.zyngui.show_keyboard(self.confirm_export_chain, self.chain.get_title())

    def confirm_export_chain(self, title):
        path = f"{self.zyngui.state_manager.snapshot_dir}/{self.export_dir}/{title}.zss"
        if os.path.isfile(path):
            self.zyngui.show_confirm(f"File {path} already exists.\n\nOverwrite?", self.do_export_chain, path)
        else:
            self.do_export_chain(path)

    def do_export_chain(self, path):
        self.zyngui.state_manager.export_chain(path, self.chain_id)

    # Remove submenu

    def remove_cb(self):
        options = {}
        if self.chain.synth_slots and self.chain.get_processor_count("MIDI Tool"):
            options['Remove All MIDI-FXs'] = "midifx"
        if self.chain.get_processor_count("Audio Effect"):
            options['Remove All Audio-FXs'] = "audiofx"
        if self.chain_id != 0:
            options['Remove Chain'] = "chain"
        self.zyngui.screens['option'].config(
            "Remove...", options, self.remove_all_cb)
        self.zyngui.show_screen('option')

    def remove_all_cb(self, options, params):
        if params == 'midifx':
            self.remove_all_midifx()
        elif params == 'audiofx':
            self.remove_all_audiofx()
        elif params == 'chain':
            self.remove_chain()

    def remove_chain(self, params=None):
        self.zyngui.show_confirm(
            "Do you really want to remove this chain?", self.chain_remove_confirmed)

    def chain_remove_confirmed(self, params=None):
        self.zyngui.chain_manager.remove_chain(self.chain_id)
        self.zyngui.show_screen_reset('audio_mixer')

    # FX-Chain management

    def audiofx_add(self):
        self.zyngui.modify_chain(
            {"type": "Audio Effect", "chain_id": self.chain_id, "post_fader": False})

    def postfader_add(self):
        self.zyngui.modify_chain(
            {"type": "Audio Effect", "chain_id": self.chain_id, "post_fader": True})

    def remove_all_audiofx(self):
        self.zyngui.show_confirm(
            "Do you really want to remove all audio effects from this chain?", self.remove_all_procs_cb, "Audio Effect")

    def remove_all_procs_cb(self, type=None):
        for processor in self.chain.get_processors(type):
            self.zyngui.chain_manager.remove_processor(
                self.chain_id, processor)
        self.build_view()
        self.show()

    # MIDI-Chain management

    def midifx_add(self):
        self.zyngui.modify_chain(
            {"type": "MIDI Tool", "chain_id": self.chain_id})

    def remove_all_midifx(self):
        self.zyngui.show_confirm(
            "Do you really want to remove all MIDI effects from this chain?", self.remove_all_procs_cb, "MIDI Tool")

    # Select Path
    def set_select_path(self):
        try:
            self.select_path.set(f"Chain Options: {self.chain.get_name()}")
        except:
            self.select_path.set("Chain Options")

# ------------------------------------------------------------------------------
