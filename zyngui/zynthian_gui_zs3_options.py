#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI ZS3 options selector Class
#
# Copyright (C) 2015-2020 Fernando Moyano <jofemodo@zynthian.org>
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

# Zynthian specific modules
from zyngui.zynthian_gui_selector_info import zynthian_gui_selector_info

# ------------------------------------------------------------------------------
# Zynthian ZS3 options GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_zs3_options(zynthian_gui_selector_info):

    def __init__(self):
        self.last_action = None
        self.zs3_id = None
        super().__init__('Option', default_icon="zs3.png")
        self.prog_chan = self.prog_num = 0

    def config(self, id):
        self.last_action = None
        self.zs3_id = id

        self.prog_chan = self.prog_num = 0
        if not id.startswith("zs3"):
            parts = id.split('/')
            if len(parts) > 1:
                if parts[0] == "*":
                    self.prog_num = int(parts[1]) + 1
                else:
                    self.prog_chan = int(parts[0]) + 1
                    self.prog_num = int(parts[1]) + 1

    def fill_list(self):
        self.list_data = []
        if self.zs3_id == "zs3-0":
            self.list_data.append((self.zs3_update, 2, "Overwrite", ["Save current state, overwritting this ZS3.", "zs3_overwrite.png"]))
        else:
            self.list_data.append((self.zs3_restoring_submenu, 1, "Restore options...", ["Select which elements will be restored from this ZS3.", "zs3_settings.png"]))
            self.list_data.append((self.zs3_update, 2, "Overwrite", ["Save current state, overwritting this ZS3.", "zs3_overwrite.png"]))
            self.list_data.append((self.zs3_rename, 3, "Rename", ["Rename this ZS3.", "zs3_rename.png"]))
            self.list_data.append((self.zs3_note, 4, "Note", ["Add a note to this ZS3, shown by the ZS3 performance view.", "zs3_rename.png"]))
            self.list_data.append((self.zs3_delete, 5, "Delete", ["Delete this ZS3.", "zs3_delete.png"]))

            if "/" in self.zs3_id:
                if self.prog_num:
                    self.list_data.append((self.zs3_prog_num, 6, f"Program Change Number [{self.prog_num - 1}]", ["Assign MIDI Program Change number to this ZS3.", "zs3_overwrite.png"]))
                else:
                    self.list_data.append((self.zs3_prog_num, 6, "Program Change Number [None]", ["Assign MIDI Program Change number to this ZS3.", "zs3_overwrite.png"]))
                if self.prog_chan:
                    self.list_data.append((self.zs3_prog_chan, 7, f"Program Change Channel [{self.prog_chan}]", ["Assign MIDI Program Change channel to this ZS3.", "zs3_overwrite.png"]))
                else:
                    self.list_data.append((self.zs3_prog_chan, 7, "Program Change Channel [Any]", ["Assign MIDI Program Change channel to this ZS3.", "zs3_overwrite.png"]))
            elif id != "zs3-0":
                self.list_data.append((self.zs3_prog_num, 6, "Program Change Number [None]", ["Assign MIDI Program Change number to this ZS3.", "zs3_overwrite.png"]))
            self.preselect_last_action()
        super().fill_list()

    def preselect_last_action(self, force_select=False):
        for i, data in enumerate(self.list_data):
            if self.last_action and self.last_action == data[0]:
                if force_select:
                    self.select_listbox(i)
                else:
                    self.index = i
                return i
        return 0

    def select_action(self, i, t='S'):
        self.index = i
        if self.list_data[i][0]:
            self.last_action = self.list_data[i][0]
            self.last_action()

    def zs3_restoring_submenu(self):
        try:
            state = self.zyngui.state_manager.zs3[self.zs3_id]
        except:
            logging.error("Bad ZS3 id ({}).".format(self.zs3_id))
            return

        title = self.zyngui.state_manager.get_zs3_title(self.zs3_id)
        self.zyngui.screens['option'].config(f"ZS3 Restore: {title}", self.zs3_restoring_options_cb,
                                             self.zs3_restoring_options_select_cb, close_on_select=False, click_type=True)
        self.zyngui.show_screen('option')

    def zs3_restoring_options_cb(self):
        """ Create a tree of chains/processors defined within zs3 to toggle restore flag"""
        try:
            state = self.zyngui.state_manager.zs3[self.zs3_id]
        except:
            logging.error(f"Bad ZS3 id ({self.zs3_id}).")
            return

        options = {"Toggle All Mixer": ["",["Toggle the selection of all audio mixer parameters that will be restored.", None]]}
        mixer_list = []

        for idx, chain_id in enumerate(self.zyngui.chain_manager.chains):
            chain = self.zyngui.chain_manager.get_chain(chain_id)
            if chain is None:
                continue
            if chain_id:
                label = f"{idx + 1} {chain.get_name()}"
            else:
                label = chain.get_name()
            if "chains" in state and chain_id in state["chains"]:
                try:
                    restore = state["chains"][chain_id]["restore"]
                except:
                    restore = True
                info = "Toggle whether chain parameters will be restored.\n\nBold SELECT to toggle all."
                if restore:
                    options[f"\u2612 {label}"] = [f"chains_{chain_id}", [info, None]]
                else:
                    options[f"\u2610 {label}"] = [f"chains_{chain_id}", [info, None]]
            else:
                options[label] = None
            for proc in chain.get_processors():
                if proc.id in state["processors"]:
                    try:
                        restore = state["processors"][proc.id]["restore"]
                    except:
                        restore = True
                    if proc.eng_code in ("MI", "MR"):
                        label = f"{proc.name}"
                        mixer_list.append(str(proc.id))
                    else:
                        label = f"{proc.name} ({proc.id})"
                    info = "Toggle whether processor parameters will be restored..\n\nBold SELECT to toggle all."
                    if restore:
                        options[f"\u2612   ⤷{label}"] = [f"processors_{proc.id}", [info, None]]
                    else:
                        options[f"\u2610   ⤷{label}"] = [f"processors_{proc.id}", [info, None]]
        options["Toggle All Mixer"][0] = ",".join(mixer_list)
        prefix = "\u2612" if state.get("restore_midi_learn", False) else "\u2610"
        options[f"{prefix} MIDI learn"] = ["midi_learn", ["Toggle whether MIDI learn (CC binding) is restored.", None]]

        return options

    def zs3_restoring_options_select_cb(self, label, param, ct):
        if label == "Toggle All Mixer":
            ids = param.split(",")
            for id in ids:
                self.zyngui.state_manager.toggle_zs3_restore_flag(self.zs3_id, "processors", id)
            return
        elif param == "midi_learn":
            self.zyngui.state_manager.toggle_zs3_restore_flag(self.zs3_id, "midi_learn")
            return
        type, id = param.split("_")
        if ct == "S":
            self.zyngui.state_manager.toggle_zs3_restore_flag(self.zs3_id, type, id)
        elif ct == "B":
            try:
                state = self.zyngui.state_manager.zs3[self.zs3_id]
            except:
                logging.error("Bad ZS3 ID ({}).".format(self.zs3_id))
                return
            # Invert selection (toggle all elements in list)
            for chain_id in list(state["chains"]):
                self.zyngui.state_manager.toggle_zs3_restore_flag(self.zs3_id, "chains", chain_id)
            for proc_id in list(state["processors"]):
                self.zyngui.state_manager.toggle_zs3_restore_flag(self.zs3_id, "processors", proc_id)

    def zs3_rename(self):
        title = self.zyngui.state_manager.get_zs3_title(self.zs3_id)
        self.zyngui.show_keyboard(self.zs3_rename_cb, title)

    def zs3_rename_cb(self, title):
        logging.info("Renaming ZS3 '{}'".format(self.zs3_id))
        self.zyngui.state_manager.set_zs3_title(self.zs3_id, title)
        self.zyngui.close_screen()

    def zs3_note(self):
        note = self.zyngui.state_manager.get_zs3_note(self.zs3_id)
        self.zyngui.show_keyboard(self.zs3_note_cb, note)

    def zs3_note_cb(self, note):
        logging.info("Setting note for ZS3 '{}'".format(self.zs3_id))
        self.zyngui.state_manager.set_zs3_note(self.zs3_id, note)
        self.zyngui.close_screen()

    def zs3_update(self):
        logging.info("Updating ZS3 '{}'".format(self.zs3_id))
        self.zyngui.state_manager.save_zs3(self.zs3_id)
        self.zyngui.close_screen()

    def zs3_delete(self):
        self.zyngui.show_confirm(
            f"Do you really want to delete ZS3: {self.zs3_id}?", self.do_delete)

    def do_delete(self, params):
        if self.zs3_id == "zs3-0":
            logging.info("Can't delete ZS3 '{}'!".format(self.zs3_id))
        else:
            logging.info("Deleting ZS3 '{}'".format(self.zs3_id))
            self.zyngui.state_manager.delete_zs3(self.zs3_id)
        self.zyngui.close_screen()

    def zs3_prog_num(self):
        labels = ["None"]
        for i in range(128):
            labels.append(i)
        self.enable_param_editor(self, 'prog_num', {'name': 'Program Change Number', 'labels': labels, 'value': self.prog_num}, self.on_prog_num)

    def on_prog_num(self, value):
        self.update_prog(None, value)

    def zs3_prog_chan(self):
        labels = ['Any']
        for i in range(1, 17):
            labels.append(i)
        self.enable_param_editor(self, 'prog_chan', {'name': 'Program Change Channel', 'labels': labels, 'value': self.prog_chan}, self.on_prog_chan)

    def on_prog_chan(self, value):
        self.update_prog(value, None)

    def update_prog(self, chan, prog):
        if chan is None:
            chan = self.prog_chan
        if prog is None:
            prog = self.prog_num
        if prog == 0:
            # Remove program change
            zs3_id = self.zs3_id.split('/')[-1]
        else:
            if chan == 0:
                # Any channel
                zs3_id = f"*/{prog - 1}"
            else:
                zs3_id = f"{chan - 1}/{prog - 1}"
        if zs3_id == self.zs3_id:
            return
        if zs3_id in self.zyngui.state_manager.zs3:
            title = self.zyngui.state_manager.zs3[zs3_id]["title"]
            self.zyngui.show_confirm(f"Overwrite existing ZS3: {title}?", self.do_update_prog, [prog, chan, zs3_id])
        else:
            self.do_update_prog([prog, chan, zs3_id])

    def do_update_prog(self, params):
        """ Rename a ZS3 id
            params: [prog, chan, id]
        """
        zs3 = self.zyngui.state_manager.zs3.pop(self.zs3_id)
        self.zs3_id = params[2]
        self.zyngui.state_manager.zs3[self.zs3_id] = zs3
        self.prog = params[0]
        self.chan = params[1]
        self.zyngui.close_screen()

    def set_select_path(self):
        title = self.zyngui.state_manager.get_zs3_title(self.zs3_id)
        self.select_path.set(f"ZS3 Options: {title}")

# ------------------------------------------------------------------------------
