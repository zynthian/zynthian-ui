#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Porcessor Options Class
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
import random
from copy import copy

# Zynthian specific modules
import zynautoconnect
from zyngine.zynthian_signal_manager import zynsigman
from zyngui.zynthian_gui_selector_info import zynthian_gui_selector_info


# ------------------------------------------------------------------------------
# Zynthian processor Options GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_processor_options(zynthian_gui_selector_info):

    def __init__(self, parent=None, topbar=None):
        self.reset()
        super().__init__('Option', parent=parent, topbar=topbar)

    def reset(self):
        self.index = 0
        self.processor = None
        self.last_random = {}

    def fill_list(self):
        self.list_data = []

        self.list_data.append((None, None, "> Manage this processor"))

        # TODO Implement bypass for MIDI processors!!
        if self.processor.type == "Audio Effect" and self.processor.eng_code not in ("MI", "MR"):
                if self.processor.is_bypassed():
                    title = "\u2612 Bypass"
                else:
                    title = "\u2610 Bypass"
                self.list_data.append((self.processor.toggle_bypass, None, title, ["Bypass this processor.", "bypass.png"]))

        # Move processor
        if self.processor.type not in ("MIDI Synth", "Audio Generator") and self.processor.chain is not None:
            if self.processor.chain.get_processor_count(self.processor.type) > 1:
                self.list_data.append((self.start_move, None, "Move",
                                       ["Move processor position within chain.\n\nUse knob 3 to nudge along chain, moving between parallel and serial positioning. Use knob 4 to move to another chain.", "move_up_down.png"]))

        # Replace and Remove processor
        if self.processor.eng_code not in ("MI", "MR"):
            if self.processor.type == "MIDI Synth":
                eng_options = self.processor.engine.get_options()
                if eng_options['replace']:
                    self.list_data.append((self.replace, None, f"Replace {self.processor.name}",
                                           ["Replace this processor with another of similar type.\n\nThe engine selection list will show, allowing selection of a new engine type.", "replace_processor.png"]))
            else:
                self.list_data.append((self.replace, None, "Replace",
                                           ["Replace this processor with another of similar type.\n\nThe engine selection list will show, allowing selection of a new engine type.", "replace_processor.png"]))

            if self.processor.type in ("MIDI Tool", "Audio Effect"):
                self.list_data.append((self.processor_remove, None, "Remove", ["Remove this processor from the chain.", "delete.png"]))

        #if len(self.processor.get_bank_list()) > 1 or len(self.processor.preset_list) > 0 and self.processor.preset_list[0][0] != '':
        #    self.list_data.append((self.preset_list, None, "Presets"))

        if self.processor.type == "MIDI Synth":
            self.list_data.append((self.randomize, None, "Randomize parameters",
                                   ["Change all processor parameters to random values.\n\nThis is truely random so may produce undesirable effect, but can undo randomization.", "dice.png"]))
            if self.last_random:
                self.list_data.append((self.undo_randomize, None, "Undo Randomize", ["Undo the last parameter randomization.", "back.png"]))

        self.list_data.append((self.midi_clean, None, "Clean MIDI-learn",
                               ["Remove CC bindings from all parameters in this processor.", "delete_presets.png"]))
        #self.list_data.append((self.control_view, None, "Control View"))
        # Processor info
        self.list_data.append((self.show_details, None, "Info", ["Show information about this processor.", "info.png"]))

        self.list_data.append((None, None, "> Add to chain"))
        pos = "series" if self.processor.type in ["MIDI Synth", "MIDI Tool"] or self.processor.eng_code in ["MI", "MX"] else "parallel"
        if self.processor.type in ("MIDI Synth", "MIDI Tool"):
            self.list_data.append((self.add_midi_processor, None, "Insert MIDI Processor",
                                   [f"Insert a new MIDI processor in the chain in {pos} with this processor.", "midi_processor.png"]))
        if self.processor.type in ("MIDI Synth", "Audio Effect", "Audio Generator"):
            self.list_data.append((self.add_audio_processor, None, "Insert Audio Processor",
                                   [f"Insert a new audio processor in the chain in {pos} with this processor.", "audio_processor.png"]))

        super().fill_list()

    def build_view(self):
        if self.processor != self.zyngui.get_current_processor():
            self.processor = self.zyngui.get_current_processor()
            self.last_random = {}
        super().build_view()
        zynsigman.register_queued(zynsigman.S_PROCESSOR, zynsigman.SS_PROCESSOR_BYPASS, self.bypass_cb)
        if self.index >= len(self.list_data):
            self.index = len(self.list_data) - 1
        return True

    def hide(self):
        zynsigman.unregister(zynsigman.S_PROCESSOR, zynsigman.SS_PROCESSOR_BYPASS, self.bypass_cb)
        super().hide()

    def bypass_cb(self, zctrl):
        if self.processor and self.processor.type == "Audio Effect" and self.processor.eng_code not in ("MI", "MR"):
            self.update_list()

    def select_action(self, i, t='S'):
        self.index = i

        if self.list_data[i][0] is None:
            pass
        elif self.list_data[i][1] is None:
            self.list_data[i][0]()
        else:
            self.list_data[i][0](self.list_data[i][1])

    def show_details(self):
        self.zyngui.screens["engine"].show_details(self.processor.eng_code)

    def add_processor(self, proc_type=None):
        if proc_type is None:
            proc_type = self.processor.type
        try:
            chain_idx, row, column = self.zyngui.screens["chain_manager"].selected_node
            node = self.zyngui.screens["chain_manager"].nodes[chain_idx][row][column]
            proc = node["proc"]
            if proc.type == "MIDI Synth":
                if proc_type == "Audio Effect":
                    slot = -1
                else:
                    slot = None
            else:
                slot = self.zyngui.screens["chain_manager"].nodes[chain_idx][row][column]["slot"]
        except:
            slot = None
        self.zyngui.modify_chain({
            "chain_id": self.zyngui.chain_manager.active_chain.chain_id,
            "type": proc_type,
            "midi_thru": self.processor.midi_chan is not None,
            "audio_thru": proc_type == "Audio Effect",
            "slot": slot
        })
        self.processor = self.zyngui.get_current_processor()

    def add_midi_processor(self):
        self.add_processor("MIDI Tool")

    def add_audio_processor(self):
        self.add_processor("Audio Effect")

    def processor_remove(self):
        self.zyngui.show_confirm(f"Do you want to remove {self.processor.engine.name} from chain?", self.do_remove)

    def do_remove(self, unused=None):
        self.zyngui.chain_manager.remove_processor(self.zyngui.chain_manager.active_chain.chain_id, self.processor)
        zynautoconnect.request_audio_connect(True)
        zynautoconnect.request_midi_connect(True)
        self.processor = None
        self.zyngui.close_screen()

    def preset_list(self):
        self.zyngui.cuia_bank_preset(self.processor)

    def midi_clean(self):
        if self.processor:
            self.zyngui.show_confirm(f"Do you want to clean MIDI-learn for ALL controls in {self.processor.name}?",
                                     self.zyngui.chain_manager.clean_midi_learn, self.processor)

    def control_view(self):
        self.zyngui.chain_control(hmode=self.zyngui.SCREEN_HMODE_REPLACE)

    # FX-Chain management

    def replace(self):
        self.zyngui.modify_chain({
            "chain_id": self.zyngui.chain_manager.active_chain.chain_id,
            "processor": self.processor,
            "type": self.processor.type
        })

    def start_move(self, proc=None):
        self.zyngui.screens.get('chain_manager').start_moving_processor()
        self.zyngui.show_screen('chain_manager')

    def randomize(self):
        refresh = not self.last_random
        for zctrl in self.processor.controllers_dict.values():
            if zctrl.is_integer:
                value = random.randint(zctrl.value_min, zctrl.value_max)
            else:
                value = random.random() * (zctrl.value_max - zctrl.value_min)
            self.last_random[zctrl.symbol] = zctrl.value
            zctrl.set_value(value)
        if refresh:
            self.fill_list()

    def undo_randomize(self):
        for zctrl in self.processor.controllers_dict.values():
            try:
                value = self.last_random[zctrl.symbol]
                self.last_random[zctrl.symbol] = zctrl.value
                zctrl.set_value(value)
            except:
                pass

    # Select Path

    def set_select_path(self):
        if self.processor:
            self.select_path.set("{} > Processor Options".format(self.processor.get_basepath()))
        else:
            self.select_path.set("Processor Options")

# ------------------------------------------------------------------------------
