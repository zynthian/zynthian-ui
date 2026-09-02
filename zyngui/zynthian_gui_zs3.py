#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI ZS3 screen
#
# Copyright (C) 2018-2026 Fernando Moyano <jofemodo@zynthian.org>
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
from tkinter import font as tkFont

# Zynthian specific modules
from zyngine.zynthian_signal_manager import zynsigman
from zyngui import zynthian_gui_config
from zyngui import zs3_performance
from zyngui.zynthian_gui_selector_info import zynthian_gui_selector_info

# ------------------------------------------------------------------------------
# Zynthian Sub-SnapShot (ZS3) GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_zs3(zynthian_gui_selector_info):

    def __init__(self):
        super().__init__('Program', default_icon="zs3.png")

        self.zs3_waiting_label = tkinter.Label(self.main_frame,
                                               text='Waiting for MIDI Program Change...',
                                               font=(zynthian_gui_config.font_family,
                                                     int(0.85 * zynthian_gui_config.font_size)),
                                               fg=zynthian_gui_config.color_ml,
                                               bg=zynthian_gui_config.color_panel_bg)

        # ALT mode draws a performance face over the list: the current ZS3's
        # title, large enough to read from across a room, its program change
        # and its position in the stepping order. It is display only, and holds
        # no state of its own beyond the id last announced by SS_LOAD_ZS3.
        self.perf_zs3_id = None
        self.perf_canvas = tkinter.Canvas(
            self.main_frame,
            bd=0,
            highlightthickness=0,
            bg=zynthian_gui_config.color_bg)
        self.perf_title = self.perf_canvas.create_text(
            0, 0,
            anchor=tkinter.CENTER,
            justify=tkinter.CENTER,
            fill=zynthian_gui_config.color_ml)
        self.perf_subtitle = self.perf_canvas.create_text(
            0, 0,
            anchor=tkinter.CENTER,
            justify=tkinter.CENTER,
            fill=zynthian_gui_config.color_tx_off)
        # The one colour here not taken from zynthian_gui_config: the palette
        # has a single green, color_hl (#00c000), and nothing dimmer in that
        # hue, and color_hl is bright enough to be part of what this is fixing.
        # Happy to use color_off instead, or to add a ZYNTHIAN_UI_COLOR_*
        # constant for it - see the pull request.
        color_readout = "#008000"
        self.perf_prog = self.perf_canvas.create_text(
            0, 0,
            anchor=tkinter.SW,
            fill=color_readout)
        self.perf_pos = self.perf_canvas.create_text(
            0, 0,
            anchor=tkinter.SE,
            fill=color_readout)

    def show_waiting_label(self):
        if self.wide:
            padx = (0, 2)
        else:
            padx = (2, 2)
        self.zs3_waiting_label.grid(row=self.layout['list_pos'][0] + 4, column=self.layout['list_pos'][1],
                                    padx=padx, sticky='ew')

    def hide_waiting_label(self):
        self.zs3_waiting_label.grid_forget()

    def build_view(self):
        if super().build_view():
            zynsigman.register_queued(
                zynsigman.S_STATE_MAN, zynsigman.SS_LOAD_ZS3, self.cb_load_zs3)
            zynsigman.register_queued(
                zynsigman.S_STATE_MAN, zynsigman.SS_SAVE_ZS3, self.cb_save_zs3)
            self.perf_zs3_id = self.zyngui.state_manager.last_zs3_id
            self.show_performance(self.alt_mode)
            return True
        else:
            return False

    def hide(self):
        if self.shown:
            self.disable_midi_learn()
            zynsigman.unregister(
                zynsigman.S_STATE_MAN, zynsigman.SS_LOAD_ZS3, self.cb_load_zs3)
            zynsigman.unregister(
                zynsigman.S_STATE_MAN, zynsigman.SS_SAVE_ZS3, self.cb_save_zs3)
            super().hide()

    def fill_list(self):
        self.list_data = []
        self.list_data.append(("SAVE_ZS3", None, "Save as new ZS3", ["Save current state as a new ZS3.", "zs3_new.png"]))
        idx = 2
        try:
            self.list_data.append(
                ("zs3-0", self.zyngui.state_manager.zs3["zs3-0"], "Default state", ["Load default ZS3 state.\n\nBold select to show ZS3 options.", "zs3_default.png"]))
            idx += 1
        except:
            pass

        # Add list of programs
        if len(self.zyngui.state_manager.zs3) > 1:
            self.list_data.append((None, None, "> SAVED ZS3s"))
        for id, state in self.zyngui.state_manager.zs3.items():
            if id == "zs3-0":
                continue
            elif id.startswith("zs3"):
                title = f"{state['title']}"
            else:
                parts = id.split('/')
                if len(parts) > 1:
                    if parts[0] == "*":
                        title = f"{state['title']} -> PRG#{parts[1]}"
                    else:
                        title = f"{state['title']} -> CH#{int(parts[0]) + 1}:PRG#{parts[1]}"
                else:
                    title = f"{state['title']} ({id})"
            self.list_data.append((id, state, title, ["Load ZS3.\n\nBold select to show ZS3 options.", None]))
            if id == self.zyngui.state_manager.last_zs3_id:
                self.index = idx
            idx += 1

        super().fill_list()

    def cb_load_zs3(self, zs3_id):
        self.perf_zs3_id = zs3_id
        self.update_performance()
        if self.shown:
            for i, row in enumerate(self.list_data):
                if row[0] == zs3_id:
                    self.select(i)
                    break

    def cb_save_zs3(self, zs3_id):
        if self.shown:
            self.update_list()
            self.disable_midi_learn()
            self.cb_load_zs3(zs3_id)

    def select_action(self, i, t='S'):
        zs3_index = self.list_data[i][0]
        if t == 'S':
            self.zyngui.state_manager.disable_learn_pc()
            if zs3_index == "SAVE_ZS3":
                self.zyngui.state_manager.save_zs3()
                return True
            else:
                self.zyngui.state_manager.load_zs3(zs3_index)
                self.zyngui.close_screen()
                return True
        elif t == 'B':
            self.show_menu()
            return True

    def switch(self, swi, t='S'):
        if swi == 2 and t == 'S':
            self.toggle_midi_learn()
            return True
        return False

    def cuia_v5_zynpot_switch(self, params):
        i = params[0]
        t = params[1].upper()
        if i == 2 and t == 'S':
            self.toggle_midi_learn()
            return True
        return False

    def show_menu(self):
        try:
            zs3_index = self.list_data[self.index][0]
            if zs3_index == "SAVE_ZS3":
                return
            self.zyngui.state_manager.disable_learn_pc()
            self.zyngui.screens['zs3_options'].config(zs3_index)
            self.zyngui.show_screen('zs3_options')
        except:
            pass

    def toggle_menu(self):
        if self.shown:
            self.show_menu()
        elif self.zyngui.get_current_screen() == "zs3_options":
            self.zyngui.close_screen()

    def enable_midi_learn(self):
        self.zyngui.state_manager.enable_learn_pc()
        self.show_waiting_label()

    def disable_midi_learn(self):
        self.zyngui.state_manager.disable_learn_pc()
        self.hide_waiting_label()

    def toggle_midi_learn(self):
        if self.zyngui.state_manager.midi_learn_state:
            self.disable_midi_learn()
        else:
            self.enable_midi_learn()

    def back_action(self):
        self.zyngui.state_manager.disable_learn_pc()
        return False

    def set_select_path(self):
        self.select_path.set("ZS3 (SubSnapShots)")

    def get_alt_mode(self):
        return self.alt_mode

    def cuia_toggle_alt_mode(self, params=None):
        super().cuia_toggle_alt_mode(params)
        self.show_performance(self.alt_mode)
        return True

    # In the performance face the list is hidden, so the arrows have no list to
    # move. Repurpose them to step cues — a manual backup for the foot pedal if
    # it fails or is kicked out of reach. Down/Right advance, Up/Left go back,
    # both wrapping, matching the pedal's ZS3_NEXT 1 / ZS3_PREV 1. Outside ALT
    # mode they fall through to normal list navigation.
    def arrow_down(self):
        if self.alt_mode:
            self.zyngui.state_manager.load_next_zs3(True)
            return True
        return super().arrow_down()

    def arrow_up(self):
        if self.alt_mode:
            self.zyngui.state_manager.load_prev_zs3(True)
            return True
        return super().arrow_up()

    def arrow_right(self):
        if self.alt_mode:
            self.zyngui.state_manager.load_next_zs3(True)
            return True

    def arrow_left(self):
        if self.alt_mode:
            self.zyngui.state_manager.load_prev_zs3(True)
            return True

    def show_performance(self, show):
        """Swap between the ZS3 list and the performance face

        show: True for the performance face, False for the list
        """

        # The topbar stays the house topbar, but during a show its title is
        # furniture: dim it so the cue name is the brightest thing on screen.
        # Set it the way set_title() does rather than calling set_title(), which
        # silently early-returns under its own 30fps rate limit.
        if self.topbar_allowed:
            if show:
                self.title_fg = zynthian_gui_config.color_off
            else:
                self.title_fg = zynthian_gui_config.color_panel_tx
            self.label_select_path.config(fg=self.title_fg)

        if show:
            self.listbox.grid_remove()
            self.info_canvas.grid_remove()
            # The PC-learn banner sits along the bottom and would cover the
            # position readout; the performance face takes no input, so hide it.
            self.hide_waiting_label()
            self.show_sidebar(False)
            self.perf_canvas.grid(
                row=self.layout['list_pos'][0],
                column=self.layout['list_pos'][1],
                rowspan=self.layout['rows'],
                columnspan=2,
                padx=self.padx,
                pady=self.pady,
                sticky="news")
            self.update_performance()
        else:
            self.perf_canvas.grid_remove()
            self.listbox.grid()
            self.info_canvas.grid()
            self.show_sidebar(True)
            # Restore the banner only if PC-learn is still waiting for a change.
            if self.zyngui.state_manager.midi_learn_state:
                self.show_waiting_label()

    def update_layout(self):
        super().update_layout()
        self.update_performance()

    def update_performance(self):
        """Redraw the performance face

        Called on ZS3 load and save, on entering ALT mode, and on geometry
        changes. Never polled: with no ZS3 activity this screen does nothing.
        """

        if not self.alt_mode:
            return

        state = zs3_performance.performance_state(
            self.zyngui.state_manager.zs3, self.perf_zs3_id)

        # 44px at 800x480, which is what reads from ten feet away. Taken from
        # the configured font size rather than hardcoded, so a themed or
        # differently sized panel scales with it.
        title_fs = int(2.2 * zynthian_gui_config.font_size)
        label_fs = int(1.1 * zynthian_gui_config.font_size)
        # The bottom line (program change + position) is glanced at from a few
        # feet mid-performance, so it is larger than the "no cue" hint above it.
        bottom_fs = int(1.6 * zynthian_gui_config.font_size)
        title_font = tkFont.Font(family=zynthian_gui_config.font_family, size=title_fs)
        pad = int(0.6 * zynthian_gui_config.font_size)

        if state["is_loaded"]:
            title = state["title"]
            subtitle = ""
        elif state["is_default"]:
            title = "DEFAULT STATE"
            subtitle = ""
        else:
            # Nothing loaded: at power on, and after a snapshot load, until the
            # first step. A statement rather than an affordance, since the
            # pedal reaches the first ZS3 from here on its own.
            title = "NO CUE"
            first_id = zs3_performance.first_cue_id(self.zyngui.state_manager.zs3)
            if first_id:
                subtitle = "press the pedal to start — {}".format(
                    self.zyngui.state_manager.get_zs3_title(first_id))
            else:
                subtitle = "no ZS3s in this snapshot"

        self.perf_canvas.itemconfigure(
            self.perf_title,
            font=(zynthian_gui_config.font_family, title_fs),
            text=self.fit_title(title, title_font, self.width - 2 * pad))
        self.perf_canvas.coords(self.perf_title, self.width // 2, int(0.38 * self.height))

        self.perf_canvas.itemconfigure(
            self.perf_subtitle,
            font=(zynthian_gui_config.font_family, label_fs),
            text=subtitle)
        self.perf_canvas.coords(self.perf_subtitle, self.width // 2, int(0.62 * self.height))

        self.perf_canvas.itemconfigure(
            self.perf_prog,
            font=(zynthian_gui_config.font_family, bottom_fs),
            text=state["pc_label"])
        self.perf_canvas.coords(self.perf_prog, pad, self.height - pad)

        self.perf_canvas.itemconfigure(
            self.perf_pos,
            font=(zynthian_gui_config.font_family, bottom_fs),
            text=state["position_label"])
        self.perf_canvas.coords(self.perf_pos, self.width - pad, self.height - pad)

    def fit_title(self, title, font, max_width):
        """Shorten a title until it fits the available width

        How many characters fit is a rendering question and needs font metrics,
        so it lives here; how to shorten a string is zs3_performance's.

        Returns : String
        """

        if max_width < 1 or font.measure(title) <= max_width:
            return title
        limit = len(title)
        text = title
        while limit > 1 and font.measure(text) > max_width:
            limit -= 1
            text = zs3_performance.ellipsize(title, limit)
        return text

# -------------------------------------------------------------------------------
