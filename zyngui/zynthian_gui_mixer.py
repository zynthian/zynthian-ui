#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Audio Mixer
#
# Copyright (C) 2015-2025 Fernando Moyano <jofemodo@zynthian.org>
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

from os.path import basename, splitext
import tkinter
import logging
from math import log10
from time import monotonic
from PIL import Image, ImageTk

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynaudioplayer import *

from . import zynthian_gui_base
from . import zynthian_gui_config
from zynlibs.zynseq import zynseq
from zyngui.zynthian_gui_dpm import zynthian_gui_dpm
from zyngine import zynthian_controller
from zyngine.zynthian_signal_manager import zynsigman
from zyngine.zynthian_audio_recorder import zynthian_audio_recorder
from zyngine.zynthian_engine_audioplayer import zynthian_engine_audioplayer

logging.getLogger('PIL').setLevel(logging.WARNING)

# ------------------------------------------------------------------------------
# Zynthian Mixer Strip Class
# This provides a UI element that represents a mixer strip, one used per chain
# ------------------------------------------------------------------------------

class zynthian_gui_mixer_strip():

    def __init__(self, parent, x, y, width, height):
        logging.getLogger('PIL').setLevel(logging.WARNING)
        """ Initialise mixer strip object
        parent: Parent object
        x: Horizontal coordinate of left of fader
        y: Vertical coordinate of top of fader
        width: Width of fader
        height: Height of fader
        """
        self.parent = parent
        self.zyngui = parent.zyngui
        self.zynmixer = parent.zynmixer
        self.state_manager = parent.state_manager
        self.chain_manager = parent.chain_manager
        self.zynseq = parent.zynseq
        self.zctrls = None

        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.hidden = False
        self.chain_id = None
        self.chain = None

        self.hidden = True

        self.button_height = int(self.height * 0.07)
        self.legend_height = int(self.height * 0.08)
        self.balance_height = int(self.height * 0.03)
        self.fader_height = self.height - self.balance_height - self.legend_height - 2 * self.button_height
        self.fader_bottom = self.height - self.legend_height - self.balance_height
        self.fader_top = self.fader_bottom - self.fader_height
        self.fader_centre_x = int(x + width * 0.5)
        self.fader_centre_y = int(y + height * 0.5)
        self.balance_top = self.fader_bottom
        self.balance_control_centre = int(self.width / 2)
        # Width of each half of balance control
        self.balance_control_width = int(self.width / 4)

        # Digital Peak Meter (DPM) parameters
        self.dpm_width = int(self.width / 13)  # Width of each DPM
        self.dpm_length = self.fader_height
        self.dpm_y0 = self.fader_top
        self.dpm_a_x0 = x + self.width - self.dpm_width * 2 - 2
        self.dpm_b_x0 = x + self.width - self.dpm_width - 1

        self.fader_width = self.width - self.dpm_width * 2 - 2

        self.fader_drag_start = None
        self.strip_drag_start = None
        self.dragging = False

        # Default style
        # self.fader_bg_color = zynthian_gui_config.color_bg
        self.fader_bg_color = zynthian_gui_config.color_panel_bg
        self.fader_bg_color_hl = "#6a727d"  # "#207024"
        # self.fader_color = zynthian_gui_config.color_panel_hl
        # self.fader_color_hl = zynthian_gui_config.color_low_on
        self.fader_color = zynthian_gui_config.color_off
        self.fader_color_hl = zynthian_gui_config.color_on
        self.legend_txt_color = zynthian_gui_config.color_tx
        self.legend_bg_color = zynthian_gui_config.color_panel_bg
        self.legend_bg_color_hl = zynthian_gui_config.color_on
        self.button_bgcol = zynthian_gui_config.color_panel_bg
        self.button_txcol = zynthian_gui_config.color_tx
        self.left_color = "#00AA00"
        self.right_color = "#00EE00"
        self.learn_color_hl = "#999999"
        self.learn_color = "#777777"
        self.high_color = "#CCCC00"  # yellow
        self.rec_color = "#CC0000"  # red

        self.mute_color = zynthian_gui_config.color_on  # "#3090F0"
        self.solo_color = "#D0D000"
        self.mono_color = "#B0B0B0"

        # font_size = int(0.5 * self.legend_height)
        font_size = int(0.25 * self.width)
        self.font = (zynthian_gui_config.font_family, font_size)
        self.font_fader = (zynthian_gui_config.font_family,int(0.9 * font_size))
        self.font_clip_state = (zynthian_gui_config.font_family, int(0.8 * font_size))
        self.font_clip_title = (zynthian_gui_config.font_family, int(0.7 * font_size))
        self.font_icons = (zynthian_gui_config.font_family, int(0.3 * self.width))
        self.font_learn = (zynthian_gui_config.font_family,int(0.7 * font_size))

        self.fader_text_limit = self.fader_top + int(0.1 * self.fader_height)

        """
        Create GUI elements
        Tags:
            strip:X All elements within the fader strip used to hide (not show) strip
            mixer:X Elements to show in mixer view
            fader:X Elements in the fader
            audio_strip:X Elements of audio mixer strips
            launcher:X Elements to show in launcher view
            launcher:X_ROW Elements within launcher button
            launcher:X_ROW_ELEMENT Specific element within launcher button
            launcher_sel Used to hide launcher select cursors
            X is the id of this fader's background
            ROW the launcher row
        """

        self.canvas = self.parent.main_canvas

        # Fader - self.fader_bg is used to tag all elements of the strip
        id = self.fader_bg = self.canvas.create_rectangle(x, self.fader_top, x + self.width, self.fader_bottom, fill=self.fader_bg_color, width=0)
        self.canvas.itemconfig(self.fader_bg, tags=(f"strip:{id}", f"fader:{id}"))
        self.fader = self.canvas.create_rectangle(x, self.fader_top, x + self.width, self.fader_bottom, fill=self.fader_color, width=0,
                                             tags=(f"strip:{id}", f"fader:{id}"))
        self.fader_text = self.canvas.create_text(x, self.fader_bottom - 2, fill=self.legend_txt_color, angle=90, anchor="nw", font=self.font_fader, text="",
                                             tags=(f"strip:{id}", f"mixer:{id}", f"fader:{id}"))

        # Launcher pads
        height_slot = (self.fader_bottom - self.fader_top - 4) // zynthian_gui_config.visible_launchers
        ypos = self.fader_top + 2
        # Scroll up available indicator
        self.canvas.create_rectangle(x, ypos - 2, x + self.fader_width, ypos, width=0, state=tkinter.HIDDEN,
                                        fill="white", tags=(f"strip:{id}", f"launcher_scroll_top_{id}"))
        for row in range(0, zynthian_gui_config.visible_launchers):
            # Launcher pad (background)
            launcher_bg = self.canvas.create_rectangle(x, ypos, x + self.fader_width, ypos + height_slot - 1, width=0, state=tkinter.HIDDEN)
            self.canvas.itemconfig(launcher_bg, tags=(f"strip:{id}", f"launcher:{id}", f"launcher:{id}_{row}", f"launcher:{id}_{row}_bg"))
            # Play state text
            self.canvas.create_text(x + self.fader_width,  ypos - height_slot // 6, text="", anchor=tkinter.NE, font=self.font_clip_state,
                    state=tkinter.HIDDEN, tags=(f"strip:{id}", f"launcher:{id}", f"launcher:{id}_{row}", f"launcher:{id}_{row}_state"))
            # Title text
            self.canvas.create_text(x + self.fader_width // 2, ypos + 0.60 * height_slot, text="", anchor=tkinter.CENTER,
                                            font=self.font_clip_title, state=tkinter.HIDDEN, fill=self.legend_txt_color,
                                            tags=(f"strip:{id}", f"launcher:{id}", f"launcher:{id}_{row}", f"launcher:{id}_{row}_title"))
            # Play mode image
            self.canvas.create_image(x + 3, ypos, anchor=tkinter.NW, state=tkinter.HIDDEN,
                                            tags=(f"strip:{id}", f"launcher:{id}", f"launcher_{row}", f"launcher_{row}_mode", f"launcher:{id}_{row}", f"launcher:{id}_{row}_mode"))
            # Selected/highlighted cursor
            self.canvas.create_rectangle(x, ypos, x + 3, ypos + height_slot - 1, width=0, fill=self.legend_txt_color, state=tkinter.HIDDEN,
                                                  tags=(f"strip:{id}", "launcher_sel", f"launcher_sel:{id}_{row}"))

            self.canvas.tag_bind(f"launcher:{id}_{row}", '<ButtonPress-1>', lambda e, row=row: self.on_clip_slot_press(row, e))
            self.canvas.tag_bind(f"launcher:{id}_{row}", '<ButtonRelease-1>', lambda e, row=row: self.on_clip_slot_release(row, e))
            self.canvas.tag_bind(f"launcher:{id}_{row}", '<B1-Motion>', lambda e, row=row: self.on_clip_slot_motion(row, e))
            ypos += height_slot
        # Scroll down available indicator
        self.canvas.create_rectangle(x, ypos - 2, x + self.fader_width, ypos, width=0, state=tkinter.HIDDEN,
                                        fill="white", tags=(f"strip:{id}", f"launcher_scroll_bottom_{id}"))

        # DPM
        self.dpm_a = zynthian_gui_dpm(self.zynmixer, None, 0, self.canvas, self.dpm_a_x0, self.dpm_y0, self.dpm_width, self.fader_height,
                                      True, (f"strip:{id}", f"audio_strip:{id}"))
        self.dpm_b = zynthian_gui_dpm(self.zynmixer, None, 1, self.canvas, self.dpm_b_x0, self.dpm_y0, self.dpm_width, self.fader_height,
                                      True, (f"strip:{id}", f"audio_strip:{id}"))

        # Solo button
        self.solo = self.canvas.create_rectangle(x, 0, x + self.width, self.button_height, fill=self.button_bgcol, width=0,
                                            tags=(f"strip:{id}", f"solo_button:{id}", f"audio_strip:{id}"))
        self.solo_text = self.canvas.create_text(x + self.width / 2, self.button_height * 0.5, text="S", fill=self.button_txcol, font=self.font,
                                            tags=(f"strip:{id}", f"solo_button:{id}", f"audio_strip:{id}"))

        # Mute button
        self.mute = self.canvas.create_rectangle(x, self.button_height, x + self.width, self.button_height * 2, fill=self.button_bgcol, width=0,
                                            tags=(f"strip:{id}", f"mute:{id}", f"audio_strip:{id}"))
        self.mute_text = self.canvas.create_text(x + self.width / 2, self.button_height * 1.5, text="M", fill=self.button_txcol, font=self.font,
                                            tags=(f"strip:{id}", f"mute:{id}", f"audio_strip:{id}"))

        # Legend strip at bottom of screen
        self.legend_strip_bg = self.canvas.create_rectangle(x, self.height - self.legend_height, x + self.width, self.height, width=0, fill=self.legend_bg_color,
                                                       tags=(f"strip:{id}", f"mixer:{id}", f"launcher:{id}", f"legend_strip:{id}"))
        self.legend_strip_txt = self.canvas.create_text(self.fader_centre_x, self.height - self.legend_height / 2, fill=self.legend_txt_color, text="-",
                                                   tags=(f"strip:{id}", f"mixer:{id}", f"launcher:{id}", f"legend_strip:{id}"), font=self.font)
        self.legend_sel = self.canvas.create_rectangle(x, self.height - self.legend_height, x + 3, self.height, width=0, fill=self.legend_txt_color, state=tkinter.HIDDEN,
                                                  tags=(f"strip:{id}", "launcher_sel", f"legend_sel:{id}"))

        self.pedals = []
        for row in range(4):
            self.pedals.append(self.canvas.create_rectangle(
                int(x + self.fader_width / 4 * row),
                self.fader_bottom,
                int(x + self.fader_width / 4 * (row + 1)),
                self.fader_bottom - 4,
                fill="yellow",
                state="hidden",
                tags=(f"strip:{id})"))
            )

        # Clip Launcher Progress Bar
        self.clip_progress = self.canvas.create_rectangle(x, self.height - self.legend_height, x, self.height - self.legend_height + 4, width=0,
                             fill=self.legend_txt_color, tags=(f"strip:{id}", f"mixer:{id}", f"launcher:{id}"))
        # Balance indicator
        self.balance_left = self.canvas.create_rectangle(x, self.balance_top, self.fader_centre_x, self.balance_top + self.balance_height,
                                                    fill=self.left_color, width=0, tags=(f"strip:{id}", f"mixer:{id}", f"launcher:{id}", f"balance:{id}", f"audio_strip:{id}"))
        self.balance_right = self.canvas.create_rectangle(self.fader_centre_x + 1, self.balance_top, self.width, self.balance_top + self.balance_height,
                                                     fill=self.right_color, width=0, tags=(f"strip:{id}", f"mixer:{id}", f"launcher:{id}", f"balance:{id}", f"audio_strip:{id}"))
        self.balance_text = self.canvas.create_text(self.fader_centre_x, int(self.balance_top + self.balance_height / 2) - 1,
                                               text="??", font=self.font_learn, state=tkinter.HIDDEN)

        # Fader indicators
        self.record_indicator = self.canvas.create_text(x + 2, self.height - 16, text="⚫", fill="#009000", anchor="sw",
                                                   tags=(f"strip:{id}"), state=tkinter.HIDDEN)
        self.play_indicator = self.canvas.create_text(x + 2, self.height - 2, text="⏹", fill="#009000", anchor="sw",
                                                 tags=(f"strip:{id}"), state=tkinter.HIDDEN)

        """
        self.zyngui.multitouch.tag_bind(self.canvas, f"fader:{id}", "press", self.on_fader_press)
        self.zyngui.multitouch.tag_bind(self.canvas, f"fader:{id}", "motion", self.on_fader_motion)
        self.canvas.tag_bind(f"fader:{id}", "<ButtonPress-1>", self.on_fader_press)
        self.canvas.tag_bind(f"fader:{id}", "<ButtonRelease-1>", self.on_fader_release)
        self.canvas.tag_bind(f"fader:{id}", "<B1-Motion>", self.on_fader_motion)
        """
        self.canvas.tag_bind(f"balance:{id}", "<ButtonPress-1>", self.on_balance_press)
        self.canvas.tag_bind(f"fader:{id}", "<Button-4>", self.on_fader_wheel_up)
        self.canvas.tag_bind(f"fader:{id}", "<Button-5>", self.on_fader_wheel_down)
        self.canvas.tag_bind(f"balance:{id}", "<Button-4>", self.on_balance_wheel_up)
        self.canvas.tag_bind(f"balance:{id}", "<Button-5>", self.on_balance_wheel_down)
        self.canvas.tag_bind(f"legend_strip:{id}", "<Button-4>", self.parent.on_wheel)
        self.canvas.tag_bind(f"legend_strip:{id}", "<Button-5>", self.parent.on_wheel)
        self.canvas.tag_bind(f"mute:{id}", "<ButtonRelease-1>", self.on_mute_release)
        self.canvas.tag_bind(f"solo_button:{id}", "<ButtonRelease-1>", self.on_solo_release)
        self.canvas.tag_bind(f"legend_strip:{id}", "<ButtonPress-1>", self.on_strip_press)
        self.canvas.tag_bind(f"legend_strip:{id}", "<ButtonRelease-1>", self.on_strip_release)
        self.canvas.tag_bind(f"legend_strip:{id}", "<Motion>", self.on_strip_motion)
        self.canvas.tag_bind(f"launcher:{id}", "<Button-4>", self.on_launcher_wheel)
        self.canvas.tag_bind(f"launcher:{id}", "<Button-5>", self.on_launcher_wheel)

        self.draw_control()

    def hide(self):
        """ Function to hide mixer strip
        """
        self.canvas.itemconfig(f"strip:{self.fader_bg}", state=tkinter.HIDDEN)
        self.hidden = True

    def show(self):
        """ Function to show mixer strip
        """
        self.dpm_a.set_strip(self.chain.mixer_chan)
        self.dpm_b.set_strip(self.chain.mixer_chan)
        self.hidden = False
        self.draw_control()

    def get_ctrl_learn_text(self, ctrl):
        if not self.chain.is_audio():
            return ""
        try:
            param = self.zynmixer.get_learned_cc(self.zctrls[ctrl])
            return f"{param[0] + 1}#{param[1]}"
        except:
            return "??"

    def draw_dpm(self, state):
        """ Function to draw the DPM level meter for a mixer strip
        state = [dpm_a, dpm_b, hold_a, hold_b, mono]
        """
        if self.hidden or self.chain.mixer_chan is None:
            return
        self.dpm_a.refresh(state[0], state[2], state[4])
        self.dpm_b.refresh(state[1], state[3], state[4])

    def draw_balance(self):
        balance = self.zynmixer.get_balance(self.chain.mixer_chan)
        if balance is None:
            return
        if balance > 0:
            self.canvas.coords(self.balance_left,
                                           self.x + balance * self.width / 2, self.balance_top,
                                           self.x + self.width / 2, self.balance_top + self.balance_height)
            self.canvas.coords(self.balance_right,
                                           self.x + self.width / 2, self.balance_top,
                                           self.x + self.width, self.balance_top + self.balance_height)
        else:
            self.canvas.coords(self.balance_left,
                                           self.x, self.balance_top,
                                           self.x + self.width / 2, self.balance_top + self. balance_height)
            self.canvas.coords(self.balance_right,
                                           self.x + self.width / 2, self.balance_top,
                                           self.x + self.width * balance / 2 + self.width, self.balance_top + self.balance_height)

        if self.parent.zynmixer.midi_learn_zctrl == self.zctrls["balance"]:
            lcolor = self.learn_color_hl
            rcolor = self.learn_color
            txcolor = zynthian_gui_config.color_ml
            txstate = tkinter.NORMAL
            text = "??"
        elif self.parent.zynmixer.midi_learn_zctrl:
            lcolor = self.learn_color_hl
            rcolor = self.learn_color
            txcolor = zynthian_gui_config.color_hl
            txstate = tkinter.NORMAL
            text = f"{self.get_ctrl_learn_text('balance')}"
        else:
            lcolor = self.left_color
            rcolor = self.right_color
            txcolor = self.button_txcol
            txstate = tkinter.HIDDEN
            text = ""

        self.canvas.itemconfig(self.balance_left, fill=lcolor)
        self.canvas.itemconfig(self.balance_right, fill=rcolor)
        self.canvas.itemconfig(self.balance_text, state=txstate, text=text, fill=txcolor)

    def draw_level(self):
        level = self.zynmixer.get_level(self.chain.mixer_chan)
        if level is not None:
            self.canvas.coords(self.fader, self.x, self.fader_top + self.fader_height * (1 - level),
                                           self.x + self.fader_width, self.fader_bottom)

    def draw_fader(self):
        # Hide clip slots
        self.canvas.itemconfig(f"strip:{self.fader_bg}", state=tkinter.HIDDEN)
        self.canvas.itemconfig(f"mixer:{self.fader_bg}", state=tkinter.NORMAL)
        if self.chain.mixer_chan is not None:
            self.canvas.itemconfig(f"fader:{self.fader_bg}", state=tkinter.NORMAL)
            self.zyngui.multitouch.tag_bind(self.canvas, f"fader:{self.fader_bg}", "press", self.on_fader_press)
            self.zyngui.multitouch.tag_bind(self.canvas, f"fader:{self.fader_bg}", "motion", self.on_fader_motion)
            self.canvas.tag_bind(f"fader:{self.fader_bg}", "<ButtonPress-1>", self.on_fader_press)
            self.canvas.tag_bind(f"fader:{self.fader_bg}", "<ButtonRelease-1>", self.on_fader_release)
            self.canvas.tag_bind(f"fader:{self.fader_bg}", "<B1-Motion>", self.on_fader_motion)
        # Draw Fader
        if self.zctrls and self.parent.zynmixer.midi_learn_zctrl == self.zctrls["level"]:
            self.canvas.coords(self.fader_text, self.fader_centre_x, self.fader_centre_y - 2)
            self.canvas.itemconfig(self.fader_text, text="??", font=self.font_learn, angle=0,
                                               fill=zynthian_gui_config.color_ml, justify=tkinter.CENTER, anchor=tkinter.CENTER)
        elif self.parent.zynmixer.midi_learn_zctrl:
            text = self.get_ctrl_learn_text('level')
            self.canvas.coords(self.fader_text, self.fader_centre_x, self.fader_centre_y - 2)
            self.canvas.itemconfig(self.fader_text, text=text, font=self.font_learn, angle=0,
                                               fill=zynthian_gui_config.color_hl, justify=tkinter.CENTER, anchor=tkinter.CENTER)
        else:
            if self.chain is not None:
                label_parts = self.chain.get_description(2).split("\n") + [""]  # TODO
            else:
                label_parts = ["No info"]

            for i, label in enumerate(label_parts):
                self.canvas.itemconfig(self.fader_text, text=label)
                bounds = self.canvas.bbox(self.fader_text)
                if bounds[1] < self.fader_text_limit:
                    while bounds and bounds[1] < self.fader_text_limit:
                        label = label[:-1]
                        self.canvas.itemconfig(self.fader_text, text=label)
                        bounds = self.canvas.bbox(self.fader_text)
                    label_parts[i] = label + "..."
            self.canvas.itemconfig(self.fader_text, text="\n".join(label_parts), font=self.font_fader,
                                               angle=90, fill=self.legend_txt_color, justify=tkinter.LEFT, anchor=tkinter.NW)
            self.canvas.coords(self.fader_text, self.x, self.fader_bottom - 2)

    def draw_launcher(self):
        self.canvas.itemconfig(f"strip:{self.fader_bg}", state=tkinter.HIDDEN)
        self.canvas.itemconfig(f"launcher:{self.fader_bg}", state=tkinter.NORMAL)
        self.zyngui.multitouch.tag_unbind(self.canvas, f"fader:{self.fader_bg}", "press")
        self.zyngui.multitouch.tag_unbind(self.canvas, f"fader:{self.fader_bg}", "motion")
        self.canvas.tag_unbind(f"fader:{self.fader_bg}", "<ButtonPress-1>")
        self.canvas.tag_unbind(f"fader:{self.fader_bg}", "<ButtonRelease-1>")
        self.canvas.tag_unbind(f"fader:{self.fader_bg}", "<B1-Motion>")

        # Clip Launcher
        for row in range(zynthian_gui_config.visible_launchers):
            try:
                slot = self.parent.launcher_offset + row
                if slot < self.zynseq.slots:
                    self.draw_sequence_slot(slot)
                else:
                    self.canvas.itemconfig(f"launcher:{self.fader_bg}_{row}", state=tkinter.HIDDEN)
            except:
                self.canvas.itemconfig(f"launcher:{self.fader_bg}_{row}", state=tkinter.HIDDEN)

    def draw_sequence_slot(self, slot):
        mode_image = None
        row = slot - self.parent.launcher_offset
        try:
            info = self.zynseq.launcher_info[slot][self.chan]
            sequence = info["sequence"]
            empty = self.zynseq.libseq.isEmpty(self.zynseq.bank, sequence)
            if empty or info["repeat"] == 0:
                color = zynthian_gui_config.PAD_COLOUR_DISABLED_LIGHT
            else:
                color = zynthian_gui_config.LAUNCHER_COLOUR[info["group"] % 16]["rgb"]
            if self.parent.moving_scene and slot == self.parent.launcher_highlighted_slot:
                if slot == 0:
                    title = f"⇓ {self.zynseq.get_sequence_name(self.zynseq.bank, sequence)[:5]}"
                elif slot == self.zynseq.slots - 1:
                    title = f"⇑ {self.zynseq.get_sequence_name(self.zynseq.bank, sequence)[:5]}"
                else:
                    title = f"⇕ {self.zynseq.get_sequence_name(self.zynseq.bank, sequence)[:5]}"
            elif info["repeat"]:
                title = self.zynseq.get_sequence_name(self.zynseq.bank, sequence)[:5]
                if info["follow_seq"] == -1:
                    mode_image = self.parent.mode_icons["oneshot"]
                elif info["follow_bank"] != self.zynseq.bank:
                    pass #TODO: Show icon for changing bank
                elif info["follow_seq"] == info["sequence"]:
                    mode_image = self.parent.mode_icons["loopsync"]
                else:
                    mode_image = self.parent.mode_icons["oneshotall"]
            else:
                title = "⏹"
                mode_image = self.parent.mode_icons["empty"]
            match info["state"]:
                case zynseq.SEQ_PLAYING:
                    color_state = zynthian_gui_config.PAD_COLOUR_PLAYING
                    state_text = "▶"
                case zynseq.SEQ_STARTING:
                    color_state = zynthian_gui_config.PAD_COLOUR_STARTING
                    state_text = "▶"
                case zynseq.SEQ_STOPPING:
                    color_state = zynthian_gui_config.PAD_COLOUR_STOPPING
                    state_text = "▶"
                case zynseq.SEQ_STOPPINGSYNC:
                    color_state = zynthian_gui_config.PAD_COLOUR_STOPPING
                    state_text = "▶"
                case zynseq.SEQ_CHILD_PLAYING:
                    color_state = zynthian_gui_config.PAD_COLOUR_STOPPED
                    state_text = "▶"
                case zynseq.SEQ_CHILD_STOPPING:
                    color_state = zynthian_gui_config.PAD_COLOUR_STOPPED
                    state_text = "▶"
                case _:
                    color_state = zynthian_gui_config.PAD_COLOUR_DISABLED
                    state_text = ""
        except:
            color = zynthian_gui_config.PAD_COLOUR_DISABLED_LIGHT
            color_state = "#F0F0F0"
            title = "---"
            state_text = ""
        self.canvas.itemconfig(f"launcher:{self.fader_bg}_{row}", state=tkinter.NORMAL)
        self.canvas.itemconfig(f"launcher:{self.fader_bg}_{row}_bg", fill=color)
        self.canvas.itemconfig(f"launcher:{self.fader_bg}_{row}_state", text=state_text, fill=color_state)
        self.canvas.itemconfig(f"launcher:{self.fader_bg}_{row}_title", text=title)
        self.canvas.itemconfig(f"launcher:{self.fader_bg}_{row}_mode", image=mode_image)
        if self.parent.launcher_offset:
            self.canvas.itemconfig(f"launcher_scroll_top_{self.fader_bg}", state=tkinter.NORMAL)
        if self.parent.launcher_offset + zynthian_gui_config.visible_launchers < self.zynseq.slots:
            self.canvas.itemconfig(f"launcher_scroll_bottom_{self.fader_bg}", state=tkinter.NORMAL)

    def update_clip_progress(self, bank, seq, progress):
        if bank != self.zynseq.bank or self.chan is None or self.chan > 16:
            return
        x0 = self.x
        y0 = self.height - self.legend_height
        x1 = x0
        y1 = self.height - self.legend_height + 4
        playing = False
        for slot in range(len(self.zynseq.launcher_info)):
            info = self.zynseq.launcher_info[slot][self.chan]
            if info['state'] != zynseq.SEQ_STOPPED:
                if info['sequence'] == seq:
                    x1 = x0 + int(progress * self.width / 100)
                    self.canvas.coords(self.clip_progress, x0, y0, x1, y1)
                    return
                else:
                    playing = True
        if not playing:
            self.canvas.coords(self.clip_progress, x0, y0, x1, y1)

    def draw_solo(self):
        txcolor = self.button_txcol
        font = self.font
        text = "S"
        if self.zynmixer.get_solo(self.chain.mixer_chan):
            if self.parent.zynmixer.midi_learn_zctrl:
                bgcolor = self.learn_color_hl
            else:
                bgcolor = self.solo_color
        else:
            if self.parent.zynmixer.midi_learn_zctrl:
                bgcolor = self.learn_color
            else:
                bgcolor = self.button_bgcol

        if self.parent.zynmixer.midi_learn_zctrl == self.zctrls["solo"]:
            txcolor = zynthian_gui_config.color_ml
        elif self.parent.zynmixer.midi_learn_zctrl:
            txcolor = zynthian_gui_config.color_hl
            font = self.font_learn
            text = f"S {self.get_ctrl_learn_text('solo')}"

        self.canvas.itemconfig(self.solo, fill=bgcolor)
        self.canvas.itemconfig(self.solo_text, text=text, font=font, fill=txcolor)

    def draw_mute(self):
        txcolor = self.button_txcol
        font = self.font_icons
        if self.zynmixer.get_mute(self.chain.mixer_chan):
            if self.parent.zynmixer.midi_learn_zctrl:
                bgcolor = self.learn_color_hl
            else:
                bgcolor = self.mute_color
            text = "\uf32f"
        else:
            if self.parent.zynmixer.midi_learn_zctrl:
                bgcolor = self.learn_color
            else:
                bgcolor = self.button_bgcol
            text = "\uf028"

        if self.parent.zynmixer.midi_learn_zctrl == self.zctrls["mute"]:
            txcolor = zynthian_gui_config.color_ml
        elif self.parent.zynmixer.midi_learn_zctrl:
            txcolor = zynthian_gui_config.color_hl
            font = self.font_learn
            text = f"\uf32f {self.get_ctrl_learn_text('mute')}"

        self.canvas.itemconfig(self.mute, fill=bgcolor)
        self.canvas.itemconfig(self.mute_text, text=text, font=font, fill=txcolor)

    def draw_mono(self):
        """
        if self.zynmixer.get_mono(self.chain.mixer_chan):
                self.canvas.itemconfig(self.dpm_l_a, fill=self.mono_color)
                self.canvas.itemconfig(self.dpm_l_b, fill=self.mono_color)
                self.dpm_hold_color = "#FFFFFF"
        else:
                self.canvas.itemconfig(self.dpm_l_a, fill=self.low_color)
                self.canvas.itemconfig(self.dpm_l_b, fill=self.low_color)
                self.dpm_hold_color = "#00FF00"
        """

    def draw_control(self, control=None):
        """ Function to draw a mixer strip UI control
        control: Name of control or None to redraw all controls in the strip
        """
        if self.hidden or self.chain is None:  # or self.zctrls is None:
            return

        if control == None:
            if self.chain_id == 0:
                self.canvas.itemconfig(
                    self.legend_strip_txt, text="Main", font=self.font)
            else:
                font = self.font
                if self.parent.moving_chain and self.chain_id == self.chain_manager.active_chain_id:
                    strip_txt = f"⇦⇨"
                elif isinstance(self.chan, int):
                    if 0 <= self.chan < 16:
                        strip_txt = f"♫ {self.chain.midi_chan + 1}"
                    elif self.chain.midi_chan == 0xffff:
                        strip_txt = f"♫ All"
                    else:
                        strip_txt = f"♫ Err"
                elif self.chain.is_audio:
                    strip_txt = "\uf130"
                    font = self.font_icons
                else:
                    strip_txt = "\uf0ae"
                    font = self.font_icons
                    # procs = self.chain.get_processor_count() - 1
                self.canvas.itemconfig(self.legend_strip_txt, text=strip_txt, font=font)
            if self.parent.launcher_mode:
                self.draw_launcher()
            else:
                self.draw_fader()
            if self.chain.is_audio():
                self.canvas.itemconfig(f"audio_strip:{self.fader_bg}", state=tkinter.NORMAL)
            else:
                self.canvas.itemconfig(f"audio_strip:{self.fader_bg}", state=tkinter.HIDDEN)
                try:
                    self.canvas.itemconfig(self.record_indicator, state=tkinter.HIDDEN)
                    self.canvas.itemconfig(self.play_indicator, state=tkinter.HIDDEN)
                except Exception as e:
                    logging.error(e)

        if self.zctrls:
            if self.parent.launcher_mode:
                pass
            elif control in [None, 'level']:
                self.draw_level()

            if control in [None, 'solo']:
                self.draw_solo()

            if control in [None, 'mute']:
                self.draw_mute()

            if control in [None, 'balance']:
                self.draw_balance()

            if control in [None, 'mono']:
                self.draw_mono()

        if control in [None, 'rec']:
            if self.chain.is_audio() and self.state_manager.audio_recorder.is_armed(self.chain.mixer_chan):
                if self.state_manager.audio_recorder.status:
                    self.canvas.itemconfig(self.record_indicator, fill=self.rec_color, state=tkinter.NORMAL)
                else:
                    self.canvas.itemconfig(self.record_indicator, fill=self.high_color, state=tkinter.NORMAL)
            else:
                self.canvas.itemconfig(self.record_indicator, state=tkinter.HIDDEN)

        if control in [None, 'play']:
            try:
                processor = self.chain.synth_slots[0][0]
                if processor.eng_code == "AP":
                    if zynaudioplayer.get_playback_state(processor.handle):
                        self.canvas.itemconfig(self.play_indicator, text="▶", fill="#009000", state=tkinter.NORMAL)
                    else:
                        self.canvas.itemconfig(self.play_indicator, text="⏹", fill="#909090", state=tkinter.NORMAL)
                else:
                    self.canvas.itemconfig(self.play_indicator, state=tkinter.HIDDEN)
            except:
                self.canvas.itemconfig(self.play_indicator, state=tkinter.HIDDEN)

    # --------------------------------------------------------------------------
    # Mixer Strip functionality
    # --------------------------------------------------------------------------

    def set_highlight(self, hl=True):
        """ Function to highlight/downlight the strip
        hl: Boolean => True=highlight, False=downlight
        """
        if hl:
            self.set_fader_color(self.fader_bg_color_hl)
            self.canvas.itemconfig(self.legend_strip_bg, fill=self.legend_bg_color_hl)
        else:
            self.set_fader_color(self.fader_color)
            self.canvas.itemconfig(self.legend_strip_bg, fill=self.fader_bg_color)

    def set_fader_color(self, fg, bg=None):
        """ Function to set fader colors
        fg: Fader foreground color
        bg: Fader background color (optional - Default: Do not change background color)
        """
        self.canvas.itemconfig(self.fader, fill=fg)
        if bg:
            self.canvas.itemconfig(self.fader_bg_color, fill=bg)

    def set_chain(self, chain_id):
        """ Function to set chain associated with mixer strip
        chain: Chain object
        """

        self.chain_id = chain_id
        self.chain = self.chain_manager.get_chain(chain_id)
        if self.chain is None:
            self.hide()
            self.dpm_a.set_strip(None)
            self.dpm_b.set_strip(None)
            self.chan = None
        else:
            if self.chain.mixer_chan is not None and self.chain.mixer_chan < len(self.parent.zynmixer.zctrls):
                self.zctrls = self.parent.zynmixer.zctrls[self.chain.mixer_chan]
            if self.chain_id == 0:
                self.chan = 16
            else:
                self.chan = self.chain.midi_chan
            self.show()

    def set_volume(self, value):
        """ Function to set volume value
        value: Volume value (0..1)
        """
        if self.parent.zynmixer.midi_learn_zctrl:
            self.parent.enter_midi_learn(self.zctrls["level"])
        elif self.zctrls:
            self.zctrls['level'].set_value(value)

    def get_volume(self):
        """ Function to get volume value
        """
        if self.zctrls:
            return self.zctrls['level'].value

    def nudge_volume(self, dval):
        """ Function to nudge volume
        """
        if self.parent.zynmixer.midi_learn_zctrl:
            self.parent.enter_midi_learn(self.zctrls["level"])
        elif self.zctrls:
            self.zctrls["level"].nudge(dval)

    def set_balance(self, value):
        """ Function to set balance value
        value: Balance value (-1..1)
        """
        if self.parent.zynmixer.midi_learn_zctrl:
            self.parent.enter_midi_learn(self.zctrls["balance"])
        elif self.zctrls:
            self.zctrls["balance"].set_value(value)

    def get_balance(self):
        """ Function to get balance value
        """
        if self.zctrls:
            return self.zctrls['balance'].value

    def nudge_balance(self, dval):
        """ Function to nudge balance
        """
        if self.parent.zynmixer.midi_learn_zctrl:
            self.parent.enter_midi_learn(self.zctrls["balance"])
            self.parent.refresh_visible_strips()
        elif self.zctrls:
            self.zctrls['balance'].nudge(dval)

    def reset_volume(self):
        """ Function to reset volume
        """
        self.set_volume(0.8)

    # Function to reset balance
    def reset_balance(self):
        self.set_balance(0.0)

    def set_mute(self, value):
        """ Function to set mute
        value: Mute value (True/False)
        """
        if self.parent.zynmixer.midi_learn_zctrl:
            self.parent.enter_midi_learn(self.zctrls["mute"])
        elif self.zctrls:
            self.zctrls['mute'].set_value(value)
        # self.parent.refresh_visible_strips()

    def set_solo(self, value):
        """ Function to set solo
        value: Solo value (True/False)
        """
        if self.parent.zynmixer.midi_learn_zctrl:
            self.parent.enter_midi_learn(self.zctrls["solo"])
        elif self.zctrls:
            self.zctrls['solo'].set_value(value)
        if self.chain_id == 0:
            self.parent.refresh_visible_strips()

    def set_mono(self, value):
        """ Function to toggle mono
        value: Mono value (True/False)
        """
        if self.parent.zynmixer.midi_learn_zctrl:
            self.parent.enter_midi_learn(self.zctrls["mono"])
        elif self.zctrls:
            self.zctrls['mono'].set_value(value)
        self.parent.refresh_visible_strips()

    def toggle_mute(self):
        """ Function to toggle mute
        """
        if self.zctrls:
            self.set_mute(int(not self.zctrls['mute'].value))

    def toggle_solo(self):
        """ Function to toggle solo
        """
        if self.zctrls:
            self.set_solo(int(not self.zctrls['solo'].value))

    def toggle_mono(self):
        """ Function to toggle mono
        """
        if self.zctrls:
            self.set_mono(int(not self.zctrls['mono'].value))

    # --------------------------------------------------------------------------
    # Clip launcher functionality
    # --------------------------------------------------------------------------

    def highlight_launcher(self, slot=None):
        if slot is None:
            slot = self.parent.launcher_highlighted_slot
        self.canvas.itemconfig(f"launcher_sel", state=tkinter.HIDDEN)
        if slot is not None and self.chain is not None:
            if self.chain_id == self.parent.chain_manager.active_chain_id:
                if slot >= self.zynseq.slots:
                    self.canvas.itemconfig(f"legend_sel:{self.parent.highlighted_strip.fader_bg}", state=tkinter.NORMAL)
                else:
                    row = slot - self.parent.launcher_offset
                    self.canvas.itemconfig(f"launcher_sel:{self.parent.highlighted_strip.fader_bg}_{row}", state=tkinter.NORMAL)
                    if self.chan is not None and self.chan < 16 and self.zynseq.launcher_info[slot][self.chan]["clippy"]:
                        self.zynseq.launcher_info[slot][self.chan]["clippy"].set_current_screen_index(slot + 1)

    # --------------------------------------------------------------------------
    # Launcher UI event management
    # --------------------------------------------------------------------------

    def on_clip_slot_press(self, row, event):
        self.touch_y = event.y
        self.touch_x = event.x
        self.drag_axis = None  # +1=dragging in y-axis, -1=dragging in x-axis
        self.touch_ts = monotonic()

    def on_clip_slot_release(self, row, event):
        now = monotonic()
        ts = now - self.touch_ts
        self.touch_ts = None
        if self.drag_axis:
            self.drag_axis = None
            return
        slot = row + self.parent.launcher_offset
        if self.parent.moving_scene:
            prev_slot = self.parent.launcher_select_info["slot"]
            self.zynseq.move_scene(prev_slot, slot - prev_slot)
            self.parent.end_moving_scene()
            return
        self.parent.highlight_launcher_slot(slot)
        if self.chain:
            self.chain_manager.set_active_chain_by_object(self.chain)
        if ts < zynthian_gui_config.zynswitch_bold_seconds:
            self.on_clip_short_press(slot)
        elif ts < zynthian_gui_config.zynswitch_long_seconds:
            self.on_clip_bold_press(slot)
        else:
            self.on_clip_long_press(slot)

    def on_clip_slot_motion(self, row, event):
        dY = int((event.y - self.touch_y) / self.parent.slot_height)
        if dY:
            self.drag_axis = 1
            self.touch_y = event.y
            self.parent.drag_launcher(dY)

    def on_clip_short_press(self, slot):
        #logging.debug(f"CLIP PRESSED => chain_id:{self.chain_id}, slot:{slot}")
        if self.chan is None or self.chan > 16:
            return
        info = self.zynseq.launcher_info[slot][self.chan]
        seq = info['sequence']
        proc = info['clippy']
        if info['repeat'] == 0:
            # Disabled so act like immediate stop button
            if info["chan"] == 16:
                # Scene launcher so stop all running clips.
                for seq in range(len(self.zynseq.launcher_info) * zynseq.LAUNCHER_COLS):
                    self.zynseq.libseq.setPlayState(self.zynseq.bank, seq, zynseq.SEQ_STOPPED)
                return
            for i in range(len(self.zynseq.launcher_info)):
                seq = info["chan"] * len(self.zynseq.launcher_info) + i
                self.zynseq.libseq.setPlayState(self.zynseq.bank, seq, zynseq.SEQ_STOPPED)
            if proc:
                proc.engine.lscp_send_single(f"SEND CHANNEL MIDI_DATA CC 0 120 0")
        else:
            if info["state"] == zynseq.SEQ_CHILD_PLAYING:
                self.zynseq.libseq.setPlayState(self.zynseq.bank, seq, zynseq.SEQ_STOPPING)
            else:
                self.zynseq.libseq.togglePlayState(self.zynseq.bank, seq)

    def on_clip_bold_press(self, slot):
        if self.chan is None or self.chan > 16:
            return
        self.parent.set_clip_info(self.chan, slot)
        if self.chan < 16:
            self.parent.edit_clip()
        else:
            self.parent.launcher_menu()

    def on_clip_long_press(self, slot):
        pass

    # --------------------------------------------------------------------------
    # Mixer UI event management
    # --------------------------------------------------------------------------

    def on_fader_press(self, event):
        """ Function to handle fader press
        event: Mouse event
        """
        self.touch_y = event.y
        self.touch_x = event.x
        self.drag_axis = None  # +1=dragging in y-axis, -1=dragging in x-axis
        self.touch_ts = monotonic()
        if zynthian_gui_config.zyngui.cb_touch(event):
            return "break"

        self.fader_drag_start = event
        if self.chain:
            self.chain_manager.set_active_chain_by_object(self.chain)

    # Function to handle fader press
    # event: Mouse event
    def on_fader_release(self, event):
        self.touch_ts = None

    def on_fader_motion(self, event):
        """ Function to handle fader drag
        event: Mouse event
        """
        if self.touch_ts:
            dts = monotonic() - self.touch_ts

        if dts < 0.1:  # debounce initial touch
            return
        dy = self.touch_y - event.y
        dx = event.x - self.touch_x

        # Lock drag to x or y axis only after one has been started
        if self.drag_axis is None:
            if abs(dy) > 2:
                self.drag_axis = "y"
            elif abs(dx) > 2:
                self.drag_axis = "x"

        if self.drag_axis == "y":
            self.set_volume(
                self.zctrls['level'].value + (self.touch_y - event.y) / self.fader_height)
            self.touch_y = event.y
        elif self.drag_axis == "x":
            self.set_balance(
                self.zctrls['balance'].value - (self.touch_x - event.x) / self.fader_width)
            self.touch_x = event.x

    # Function to handle mouse wheel down over fader
    # event: Mouse event
    def on_fader_wheel_down(self, event):
        self.nudge_volume(-1)

    def on_fader_wheel_up(self, event):
        """ Function to handle mouse wheel up over fader
        event: Mouse event
        """
        self.nudge_volume(1)

    def on_balance_press(self, event):
        """ Function to handle mouse click / touch of balance
        event: Mouse event
        """
        if self.parent.zynmixer.midi_learn_zctrl:
            if self.parent.zynmixer.midi_learn_zctrl != self.zctrls["selfbalance"]:
                self.parent.zynmixer.midi_learn_zctrl = self.zctrls["balance"]

    def on_balance_wheel_down(self, event):
        """  Function to handle mouse wheel down over balance
        event: Mouse event
        """
        self.nudge_balance(-1)

    def on_balance_wheel_up(self, event):
        """ Function to handle mouse wheel up over balance
        event: Mouse event
        """
        self.nudge_balance(1)

    def on_launcher_wheel(self, event):
        """  Function to handle mouse wheel over launcher
        event: Mouse event
        """
        if event.num == 4:
            self.parent.arrow_up()
        else:
            self.parent.arrow_down()

    def on_strip_press(self, event):
        """ Function to handle mixer strip press
        event: Mouse event
        """
        if zynthian_gui_config.zyngui.cb_touch(event):
            return "break"

        self.strip_drag_start = event
        self.dragging = False
        if self.chain:
            self.chain_manager.set_active_chain_by_object(
                self.chain)

    def on_strip_release(self, event):
        """ Function to handle legend strip release
        """
        if zynthian_gui_config.zyngui.cb_touch_release(event):
            return "break"

        if self.parent.zynmixer.midi_learn_zctrl:
            return
        if self.strip_drag_start and not self.dragging:
            delta = event.time - self.strip_drag_start.time
            if delta > 400:
                zynthian_gui_config.zyngui.screens['chain_options'].setup(self.chain_id)
                zynthian_gui_config.zyngui.show_screen('chain_options')
            else:
                zynthian_gui_config.zyngui.chain_control(self.chain_id)
        self.dragging = False
        self.strip_drag_start = None
        self.parent.end_moving_chain()

    def on_strip_motion(self, event):
        """ Function to handle legend strip drag
        """
        if self.strip_drag_start:
            delta = event.x - self.strip_drag_start.x
            if delta > self.width:
                offset = +1
            elif delta < -self.width:
                offset = -1
            else:
                return
            # Dragged more than one strip width
            self.dragging = True
            if self.parent.moving_chain:
                self.chain_manager.move_chain(offset)
            elif self.parent.mixer_strip_offset - offset >= 0 and self.parent.mixer_strip_offset - offset + len(self.parent.visible_mixer_strips) <= len(self.chain_manager.chains):
                self.parent.mixer_strip_offset -= offset
            self.strip_drag_start.x = event.x
            self.parent.refresh_visible_strips()

    def on_mute_release(self, event):
        """ Function to handle mute button release
        event: Mouse event
        """
        self.toggle_mute()

    def on_solo_release(self, event):
        """ Function to handle solo button release
        event: Mouse event
        """
        self.toggle_solo()

# ------------------------------------------------------------------------------
# Zynthian Mixer GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_mixer(zynthian_gui_base.zynthian_gui_base):

    def __init__(self):
        super().__init__(has_backbutton=False)

        self.state_manager = self.zyngui.state_manager
        self.chain_manager = self.zyngui.chain_manager
        self.zynmixer = self.state_manager.zynmixer
        self.zynseq = self.state_manager.zynseq

        self.launcher_mode = self.zyngui.alt_mode
        self.launcher_highlighted_slot = 0
        self.launcher_select_info = None
        self.clippy_file_zctrl = None

        self.zynmixer.set_midi_learn_cb(self.enter_midi_learn)
        self.MAIN_MIXBUS_STRIP_INDEX = self.zynmixer.MAX_NUM_CHANNELS - 1
        self.chan2strip = [None] * (self.MAIN_MIXBUS_STRIP_INDEX + 1)
        self.highlighted_strip = None  # highligted mixer strip object
        self.moving_chain = False  # True if moving a chain left/right
        self.moving_scene = False # True if moving a launcher slot up/down

        # List of (strip,control) requiring gui refresh (control=None for whole strip refresh)
        self.pending_refresh_queue = set()
        # TODO: Should avoid duplicating midi_learn_zctrl from zynmixer but would need more safeguards to make change.
        self.midi_learn_sticky = None

        self.visible_launchers = zynthian_gui_config.visible_launchers
        # Maximum quantity of mixer strips to display (Defines strip width. Main always displayed.)
        visible_chains = zynthian_gui_config.visible_mixer_strips
        if visible_chains < 1:
            # Automatic sizing if not defined in config
            if self.width <= 400:
                visible_chains = 6
            elif self.width <= 600:
                visible_chains = 8
            elif self.width <= 800:
                visible_chains = 10
            elif self.width <= 1024:
                visible_chains = 12
            elif self.width <= 1280:
                visible_chains = 14
            else:
                visible_chains = 16
        self.set_visible_chains(visible_chains)

    def set_visible_chains(self, visible_chains):
        self.fader_width = (self.width - 6) / (visible_chains + 1)
        self.legend_height = self.height * 0.05
        self.edit_height = self.height * 0.1

        self.fader_height = self.height - self.edit_height - self.legend_height - 2
        self.fader_bottom = self.height - self.legend_height
        self.fader_top = self.fader_bottom - self.fader_height
        self.balance_control_height = self.fader_height * 0.1
        self.balance_top = self.fader_top
        # Width of each half of balance control
        self.balance_control_width = self.width / 4
        self.balance_control_centre = self.fader_width + self.balance_control_width

        # Arrays of GUI elements for mixer strips - Chains + Main
        # List of mixer strip objects indexed by horizontal position on screen
        self.visible_mixer_strips = [None] * visible_chains
        self.mixer_strip_offset = 0  # Index of first mixer strip displayed on far left
        self.launcher_offset = 0 # Index of first launcher slot shown at top

        # Fader Canvas
        self.main_canvas = tkinter.Canvas(self.main_frame,
                                          height=1,
                                          width=1,
                                          bd=0, highlightthickness=0,
                                          bg=zynthian_gui_config.color_panel_bg)
        self.main_frame.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_canvas.grid(row=0, sticky='nsew')

        # Clip Mode Icons
        empty_icon = tkinter.PhotoImage()
        self.slot_height = self.height // (zynthian_gui_config.visible_launchers + 3)
        iconsize = (int(self.fader_width * 0.4), int(self.slot_height * 0.30))
        self.mode_icons = {}
        for f in ("empty", "loopsync", "oneshot", "oneshotall"):
            try:
                img = Image.open(f"/zynthian/zynthian-ui/icons/zynpad_mode_{f}.png")
                self.mode_icons[f] = ImageTk.PhotoImage(img.resize(iconsize))
            except:
                self.mode_icons[f] = empty_icon

        # Create mixer strip UI objects
        for strip in range(len(self.visible_mixer_strips)):
            self.visible_mixer_strips[strip] = zynthian_gui_mixer_strip(self, 1 + self.fader_width * strip, 0, self.fader_width - 1, self.height)
        self.main_mixbus_strip = zynthian_gui_mixer_strip(self, self.width - self.fader_width - 1, 0, self.fader_width - 1, self.height)
        self.main_mixbus_strip.set_chain(0)
        self.main_mixbus_strip.zctrls = self.zynmixer.zctrls[self.MAIN_MIXBUS_STRIP_INDEX]
        self.zynmixer.enable_dpm(0, self.MAIN_MIXBUS_STRIP_INDEX, False)
        zynthian_gui_config.visible_mixer_strips = visible_chains
        self.visible_launchers = zynthian_gui_config.visible_launchers
        self.refresh_visible_strips()

    def init_dpmeter(self):
        self.dpm_a = self.dpm_b = None

    def set_title(self, title="", fg=None, bg=None, timeout=None):
        """ Redefine set_title
        """
        if title == "" and self.state_manager.last_snapshot_fpath:
            fparts = splitext(self.state_manager.last_snapshot_fpath)
            if self.zyngui.screens['snapshot'].bankless_mode:
                ssname = basename(fparts[0])
            else:
                ssname = fparts[0].rsplit("/", 1)[-1]
            title = ssname.replace("last_state", "Last State")
            zs3_name = self.state_manager.get_zs3_title()
            if zs3_name and zs3_name != "Last state":
                title += f": {zs3_name}"

        super().set_title(title, fg, bg, timeout)

    def hide(self):
        """ Function to handle hiding display
        """
        if self.shown:
            self.moving_chain = self.moving_scene = False
            if not self.zyngui.osc_clients:
                self.zynmixer.enable_dpm(0, self.MAIN_MIXBUS_STRIP_INDEX - 1, False)
            if not self.midi_learn_sticky:
                self.exit_midi_learn()
                zynsigman.unregister(
                    zynsigman.S_AUDIO_MIXER, self.zynmixer.SS_ZCTRL_SET_VALUE, self.update_control)
                zynsigman.unregister(
                    zynsigman.S_STATE_MAN, self.state_manager.SS_LOAD_ZS3, self.cb_load_zs3)
                zynsigman.unregister(
                    zynsigman.S_CHAIN_MAN, self.chain_manager.SS_SET_ACTIVE_CHAIN, self.update_active_chain)
                zynsigman.unregister(
                    zynsigman.S_AUDIO_RECORDER, zynthian_audio_recorder.SS_AUDIO_RECORDER_ARM, self.update_control_arm)
                zynsigman.unregister(
                    zynsigman.S_AUDIO_RECORDER, zynthian_audio_recorder.SS_AUDIO_RECORDER_STATE, self.update_control_rec)
                zynsigman.unregister(
                    zynsigman.S_AUDIO_PLAYER, zynthian_engine_audioplayer.SS_AUDIO_PLAYER_STATE, self.update_control_play)
                zynsigman.unregister(
                    zynsigman.S_MIDI, zynsigman.SS_MIDI_CC, self.midi_cc_cb)
                zynsigman.unregister(
                    zynsigman.S_STATE_MAN, self.state_manager.SS_ALL_NOTES_OFF, self.cb_all_notes_off)
                zynsigman.unregister(
                    zynsigman.S_STEPSEQ, zynseq.SS_SEQ_PLAY_STATE, self.cb_launcher_play_state)
                zynsigman.unregister(
                    zynsigman.S_STEPSEQ, zynseq.SS_SEQ_PROGRESS, self.cb_launcher_progress)

            super().hide()

    def build_view(self):
        """ Function to handle showing display"""

        if len(self.visible_mixer_strips) != zynthian_gui_config.visible_mixer_strips or self.visible_launchers != zynthian_gui_config.visible_launchers:
                self.set_visible_chains(zynthian_gui_config.visible_mixer_strips)
        #self.launcher_mode = self.zyngui.alt_mode
        if zynthian_gui_config.enable_touch_navigation and self.moving_chain or self.moving_scene or self.zynmixer.midi_learn_zctrl:
            self.show_back_button()

        self.set_title()
        if zynthian_gui_config.enable_dpm:
            self.zynmixer.enable_dpm(0, self.MAIN_MIXBUS_STRIP_INDEX, True)
        else:
            # Reset all DPM which will not be updated by refresh
            for strip in self.visible_mixer_strips:
                strip.draw_dpm([-200, -200, -200, -200, False])

        self.highlight_active_chain(True)
        self.setup_zynpots()
        if self.midi_learn_sticky:
            self.enter_midi_learn(self.midi_learn_sticky)
        elif not self.shown:
            zynsigman.register(
                zynsigman.S_AUDIO_MIXER, self.zynmixer.SS_ZCTRL_SET_VALUE, self.update_control)
            zynsigman.register_queued(
                zynsigman.S_STATE_MAN, self.state_manager.SS_LOAD_ZS3, self.cb_load_zs3)
            zynsigman.register_queued(
                zynsigman.S_CHAIN_MAN, self.chain_manager.SS_SET_ACTIVE_CHAIN, self.update_active_chain)
            zynsigman.register_queued(
                zynsigman.S_AUDIO_RECORDER, zynthian_audio_recorder.SS_AUDIO_RECORDER_ARM, self.update_control_arm)
            zynsigman.register_queued(
                zynsigman.S_AUDIO_RECORDER, zynthian_audio_recorder.SS_AUDIO_RECORDER_STATE, self.update_control_rec)
            zynsigman.register_queued(
                zynsigman.S_AUDIO_PLAYER, zynthian_engine_audioplayer.SS_AUDIO_PLAYER_STATE, self.update_control_play)
            zynsigman.register_queued(
                zynsigman.S_MIDI, zynsigman.SS_MIDI_CC, self.midi_cc_cb)
            zynsigman.register_queued(
                zynsigman.S_STATE_MAN, self.state_manager.SS_ALL_NOTES_OFF, self.cb_all_notes_off)
            zynsigman.register_queued(
                zynsigman.S_STEPSEQ, zynseq.SS_SEQ_PLAY_STATE, self.cb_launcher_play_state)
            zynsigman.register_queued(
                zynsigman.S_STEPSEQ, zynseq.SS_SEQ_PROGRESS, self.cb_launcher_progress)
        return True

    def update_layout(self):
        """Function to update display, e.g. after geometry changes
        """
        super().update_layout()
        # TODO: Update mixer layout

    def refresh_status(self):
        """Function to refresh screen (slow)
        """
        if self.shown:
            super().refresh_status()
            # Update main chain DPM
            state = self.zynmixer.get_dpm_states(255, 255)[0]
            self.main_mixbus_strip.draw_dpm(state)
            # Update other chains DPM
            if zynthian_gui_config.enable_dpm:
                states = self.zynmixer.get_dpm_states(0, self.MAIN_MIXBUS_STRIP_INDEX - 1)
                for strip in self.visible_mixer_strips:
                    if not strip.hidden and strip.chain.mixer_chan is not None:
                        state = states[strip.chain.mixer_chan]
                        strip.draw_dpm(state)

    def plot_zctrls(self):
        """Function to refresh display (fast)
        """
        while self.pending_refresh_queue:
            ctrl = self.pending_refresh_queue.pop()
            if ctrl[0]:
                ctrl[0].draw_control(ctrl[1])

    def update_control(self, chan, symbol, value):
        """Mixer control update signal handler
        """
        strip = self.chan2strip[chan]
        if not strip or not strip.chain or strip.chain.mixer_chan is None:
            return
        self.pending_refresh_queue.add((strip, symbol))
        if symbol == "level":
            value = strip.zctrls["level"].value
            if value > 0:
                level_db = 20 * log10(value)
                self.set_title(f"Volume: {level_db:.2f}dB ({strip.chain.get_description(1)})", None, None, 1)
            else:
                self.set_title(f"Volume: -∞dB ({strip.chain.get_description(1)})", None, None, 1)
        elif symbol == "balance":
            strip.parent.set_title(f"Balance: {int(value * 100)}% ({strip.chain.get_description(1)})", None, None, 1)

    def update_control_arm(self, chan, value):
        """Function to handle audio recorder arm
        """
        self.update_control(chan, "rec", value)

    def update_control_rec(self, state):
        """ Function to handle audio recorder status
        """
        for strip in self.visible_mixer_strips:
            self.pending_refresh_queue.add((strip, "rec"))

    def update_control_play(self, handle, state):
        """ Function to handle audio play status
        """
        for strip in self.visible_mixer_strips:
            self.pending_refresh_queue.add((strip, "play"))

    def update_active_chain(self, active_chain):
        """ Funtion to handle active chain changes
        """
        self.highlight_active_chain()
        for cc in (64, 66, 67, 69):
            self.midi_cc_cb(0, 0, cc, 0)

    def midi_cc_cb(self, izmip, chan, num, val):
        if self.launcher_mode:
            return
        try:
            index = (64, 66, 67, 69).index(num)
        except:
            return
        try:
            flags = lib_zyncore.get_cc_pedal(index)
            for strip in self.visible_mixer_strips:
                if strip.chain and strip.chain.is_midi():
                    if flags & (1 << strip.chain.zmop_index):
                        self.main_canvas.itemconfig(strip.pedals[index], state=tkinter.NORMAL)
                    else:
                        self.main_canvas.itemconfig(strip.pedals[index], state=tkinter.HIDDEN)
        except Exception as e:
            logging.warning(e)

    def cb_load_zs3(self, zs3_id):
        self.refresh_visible_strips()
        self.set_title()

    def cb_all_notes_off(self, chan=None):
        for strip in self.visible_mixer_strips:
            if strip.chain and strip.chain.is_midi() and (chan is None or strip.chain.midi_chan == chan):
                for i in range(0, 4):
                    self.main_canvas.itemconfig(strip.pedals[i], state=tkinter.HIDDEN)

    def cb_launcher_play_state(self, bank, seq, state, mode, group):
        #logging.warning(f"bank:{bank} seq:{seq} state:{state} mode:{mode} group:{group}")
        if not self.launcher_mode or bank != self.zynseq.bank:
            return
        try:
            info = self.zynseq.sequence_info[seq]
            slot = info["slot"]
        except:
            return
        if info["chan"] == zynseq.SCENE_LAUNCHER_COL:
            self.main_mixbus_strip.draw_sequence_slot(slot)
        else:
            for strip in self.visible_mixer_strips:
                if not strip.hidden and strip.chain_id in info["chains"]:
                    strip.draw_sequence_slot(slot)

    def cb_launcher_progress(self, bank, seq, progress):
        info = self.zynseq.sequence_info[seq]
        for strip in self.visible_mixer_strips:
            if not strip.hidden and strip.chain_id in info["chains"]:
                strip.update_clip_progress(bank, seq, progress)
        self.main_mixbus_strip.update_clip_progress(bank, seq, progress)

    def topbar_bold_touch_action(self):
        self.toggle_launcher_mode()

    def toggle_menu(self):
        if self.shown:
            if self.zynmixer.midi_learn_zctrl:
                self.midi_learn_menu()
            else:
                self.zyngui.toggle_screen("main_menu")
        elif self.zyngui.current_screen == "option":
            self.zyngui.close_screen()

    def item_menu(self):
        if self.launcher_mode and self.launcher_highlighted_slot < self.zynseq.slots:
            # Launcher Options
            self.set_clip_info(self.highlighted_strip.chan, self.launcher_highlighted_slot)
            self.launcher_menu()
        else:
            # Chain Options
            self.zyngui.screens['chain_options'].setup(self.chain_manager.active_chain_id)
            self.zyngui.show_screen('chain_options')

    # --------------------------------------------------------------------------
    # Mixer Functionality
    # --------------------------------------------------------------------------

    # Function to highlight the selected chain's strip
    def highlight_active_chain(self, refresh=False):
        """ Higlights active chain, redrawing strips if required
        """
        try:
            active_index = self.chain_manager.ordered_chain_ids.index(
                self.chain_manager.active_chain_id)
        except:
            active_index = 0
        if active_index < self.mixer_strip_offset:
            self.mixer_strip_offset = active_index
            refresh = True
        elif active_index >= self.mixer_strip_offset + len(self.visible_mixer_strips) and self.chain_manager.active_chain_id != 0:
            self.mixer_strip_offset = active_index - len(self.visible_mixer_strips) + 1
            refresh = True
        # TODO: Handle aux

        strip = None
        if self.chain_manager.active_chain_id == 0:
            strip = self.main_mixbus_strip
        else:
            chain = self.chain_manager.get_chain(self.chain_manager.active_chain_id)
            for s in self.visible_mixer_strips:
                if s.chain == chain:
                    strip = s
                    break
            if strip is None:
                refresh = True
        if refresh:
            chan_strip = self.refresh_visible_strips()
            if chan_strip:
                strip = chan_strip
        if self.highlighted_strip and self.highlighted_strip != strip:
            self.highlighted_strip.set_highlight(False)
            if self.launcher_mode:
                self.highlighted_strip.highlight_launcher(None)
        if strip is None:
            strip = self.main_mixbus_strip
        self.highlighted_strip = strip
        if strip:
            strip.set_highlight(True)
            if self.launcher_mode:
                strip.highlight_launcher(self.launcher_highlighted_slot)
                self.set_highlighted_clip_info()

    # Function refresh and populate visible mixer strips
    def refresh_visible_strips(self):
        """ Update the structures describing the visible strips

        returns - Active strip object
        """
        active_strip = None
        strip_index = 0
        if self.launcher_offset + zynthian_gui_config.visible_launchers > self.zynseq.slots:
            self.launcher_offset = max(0, self.zynseq.slots - zynthian_gui_config.visible_launchers)
        for chain_id in self.chain_manager.ordered_chain_ids[:-1][self.mixer_strip_offset:self.mixer_strip_offset + len(self.visible_mixer_strips)]:
            strip = self.visible_mixer_strips[strip_index]
            strip.set_chain(chain_id)
            # strip.draw_control()
            if strip.chain.mixer_chan is not None and strip.chain.mixer_chan < len(self.chan2strip):
                self.chan2strip[strip.chain.mixer_chan] = strip
            if chain_id == self.chain_manager.active_chain_id:
                active_strip = strip
            strip_index += 1

        # Hide unpopulated strips
        for strip in self.visible_mixer_strips[strip_index:len(self.visible_mixer_strips)]:
            strip.set_chain(None)
            strip.zctrls = None

        self.chan2strip[self.MAIN_MIXBUS_STRIP_INDEX] = self.main_mixbus_strip
        self.main_mixbus_strip.draw_control()
        if self.highlighted_strip and self.launcher_mode:
            self.highlighted_strip.highlight_launcher(self.launcher_highlighted_slot)
        return active_strip

    # --------------------------------------------------------------------------
    # Launcher Functionality
    # --------------------------------------------------------------------------

    def set_launcher_mode(self, launcher_mode=True):
        self.launcher_mode = launcher_mode
        if self.launcher_select_info == None:
            self.set_highlighted_clip_info()
        if self.shown:
            for strip in self.visible_mixer_strips:
                if not strip.hidden:
                    strip.draw_control()
            self.main_mixbus_strip.draw_control()
            if self.highlighted_strip and self.launcher_mode:
                self.highlighted_strip.highlight_launcher(self.launcher_highlighted_slot)


    def toggle_launcher_mode(self):
        if self.launcher_mode:
            self.zyngui.show_screen("audio_mixer")
        else:
            self.zyngui.show_screen("launcher")

    def set_highlighted_clip_info(self):
        try:
            self.launcher_select_info = self.zynseq.launcher_info[self.launcher_highlighted_slot][self.highlighted_strip.chan]
        except Exception as e:
            self.launcher_select_info = None
            #logging.error(f"Can't get info for slot {self.launcher_highlighted_slot} in column {self.highlighted_strip.chan} => {e}")

    def set_clip_info(self, chan, slot):
        try:
            self.launcher_select_info = self.zynseq.launcher_info[slot][chan]
            self.launcher_select_info["slot"] = slot
        except Exception as e:
            self.launcher_select_info = None
            #logging.error(f"Can't get info for slot {slot} in column {chan} => {e}")

    def launcher_menu(self):
        info = self.launcher_select_info
        if not info:
            return
        options = {}
        name = self.zynseq.get_sequence_name(self.zynseq.bank, info['sequence'])
        if info['chan'] == zynseq.SCENE_LAUNCHER_COL:
            title = f"Scene options ({name})"
            repeat = info["repeat"]
            if repeat == 0:
                options["Repeat (DISABLED)"] = info
            else:
                if repeat == 1:
                    options[f"Repeat (PLAY ONCE)"] = info
                elif repeat == 2:
                    options[f"Repeat (PLAY TWICE)"] = info
                else:
                    options[f"Repeat (PLAY {repeat} TIMES)"] = info
                follow_seq = info["follow_seq"]
                follow_slot = follow_seq // zynseq.LAUNCHER_COLS
                #TODO: Handle switching bank
                if follow_seq == -1:
                    options["Follow action (STOP)"] = info
                elif follow_seq == info['sequence']:
                    options["Follow action (LOOP)"] = info
                else:
                    options[f"Follow action (PLAY SCENE {follow_slot + 1})"] = info
                if info['tempo'] is None:
                    options[f"Tempo (NONE)"] = info
                else:
                    options[f"Tempo ({info['tempo']})"] = info
                    options["Remove tempo"] = info
                options[f"Beats per bar ({info['bpb']})"] = info
        elif info["clippy"]:
            title = f"Audio clip options ({name})"
            zctrl = self.get_clippy_zctrl("file")
            filename = basename(zctrl.value)
            options[f"File ({filename})"] = info
            zctrl = self.get_clippy_zctrl("warp")
            val = "ON" if zctrl.value else "OFF"
            options[f"Warp ({val})"] = info
        options[f"Edit name ({name})"] = info
        options["Add scene"] = info
        if self.zynseq.slots > 1:
            options["Remove scene"] = info
            options["Move scene"] = info

        self.zyngui.screens['option'].config(title, options, self.launcher_menu_cb, close_on_select=False)
        self.zyngui.show_screen('option')

    def launcher_menu_cb(self, option, params):
        self.launcher_select_info = params
        option_screen = self.zyngui.screens['option']
        if params['clippy']:
            if option.startswith("File"):
                # Show file selector. Callback has path. Must set path of this zctrl.
                zctrl = self.get_clippy_zctrl("file")
                self.clippy_file_zctrl = zctrl
                self.zyngui.cb_show_file_selector(self.on_clippy_file_sel,
                    fexts=zctrl.path_file_types,
                    dirnames=zctrl.path_dir_names,
                    path=zctrl.value)
            elif option.startswith("Warp"):
                zctrl = self.get_clippy_zctrl("warp")
                zctrl.toggle()
        elif option.startswith("Edit name"):
            name = self.zynseq.get_sequence_name(self.zynseq.bank, params["sequence"])
            self.zyngui.show_keyboard(self.rename_sequence, name, 8)
        elif option.startswith("Add scene"):
            self.zynseq.add_scene(params["slot"] + 1)
            self.refresh_visible_strips()
            self.zyngui.show_screen("launcher")
        elif option.startswith("Remove scene"):
            slot = params['slot']
            self.zyngui.show_confirm(f"Remove scene {slot + 1}?", self.remove_scene, slot)
        elif option.startswith("Move scene"):
            slot = params['slot']
            self.moving_scene = True
            self.zyngui.show_screen("launcher")
        elif option.startswith("Tempo"):
            tempo = params["tempo"]
            if not tempo:
                tempo = self.zynseq.get_tempo()
            option_screen.enable_param_editor(option_screen, "tempo", {
                'name': 'BPM',
                'is_integer': False,
                'value_min': 10.0,
                'value_max': 420,
                'value': tempo,
                'nudge_factor': 1.0,
            }, assert_cb=self.cb_assert_param_editor)
        elif option == "Remove tempo":
            slot = params["slot"]
            self.zynseq.libseq.removeTempoEvent(self.zynseq.bank, len(self.zynseq.launcher_info) * zynseq.LAUNCHER_COLS + slot, 1, 0)
            self.launcher_select_info["tempo"] = None
            index = option_screen.index
            self.launcher_menu()
            option_screen.select(index - 1)
        elif option.startswith("Repeat"):
            labels = ["DISABLED", "PLAY ONCE", "PLAY TWICE"]
            for i in range(3, 256):
                labels.append(f"PLAY {i} TIMES")
            option_screen.enable_param_editor(option_screen, "repeat", {
                'name': 'Repeat',
                'value': params["repeat"],
                'labels': labels
            }, assert_cb=self.cb_assert_param_editor)
        elif option.startswith("Beats per bar"):
            bpb = params["bpb"]
            option_screen.enable_param_editor(option_screen, "bpb", {
                'name': 'Beats per bar',
                'value_min': 2,
                'value_max': 24,
                'value': bpb
            }, assert_cb=self.cb_assert_param_editor)
        elif option.startswith("Follow action"):
            ticks = [-1]
            labels = ["STOP",]
            for i, slot_info in enumerate(self.zynseq.launcher_info):
                seq = slot_info[16]["sequence"]
                if seq != params["sequence"]:
                    ticks.append(slot_info[16]["sequence"])
                    labels.append(f"PLAY SCENE {i + 1}")
            val = params["follow_seq"]
            #TODO: Handle switching bank
            option_screen.enable_param_editor(option_screen, "follow", {
                "name": "Follow action",
                "ticks": ticks,
                "labels": labels,
                "value": val
            }, assert_cb=self.cb_assert_param_editor)

    def remove_scene(self, slot):
        self.zynseq.remove_scene(slot)
        self.refresh_visible_strips()
        self.zyngui.show_screen("launcher")

    def drag_launcher(self, dY):
        new_pos = self.launcher_offset - dY
        if 0 <= new_pos <= len(self.zynseq.launcher_info) - self.visible_launchers:
            self.launcher_offset = new_pos
            self.refresh_visible_strips()

    def get_clippy_zctrl(self, zctrl_name):
        try:
            clippy_proc = self.launcher_select_info['clippy']
            return clippy_proc.controllers_dict[f"{zctrl_name} {self.launcher_select_info['slot'] + 1:02}"]
        except:
            return None

    # Handle file selector callback
    def on_clippy_file_sel(self, path):
        self.clippy_file_zctrl.set_value(path)

    def edit_pattern(self):
        if self.launcher_select_info:
            pated = self.zyngui.screens['pattern_editor']
            pated.set_sequence_info(self.launcher_select_info)
            pated.load_pattern(self.launcher_select_info["pattern"])
            self.zyngui.show_screen("pattern_editor")
            return True
        else:
            return False

    def edit_clip(self):
        if self.launcher_mode and self.launcher_select_info:
            if self.launcher_select_info['clippy']:
                self.zyngui.chain_control(self.highlighted_strip.chain_id)
                return True
            elif self.launcher_select_info['chan'] < zynseq.SCENE_LAUNCHER_COL:
                return self.edit_pattern()
            else:
                self.item_menu()
                return True

    def rename_sequence(self, name):
        self.zynseq.set_sequence_name(self.zynseq.bank, self.launcher_select_info["sequence"], name)
        index = self.zyngui.screens['option'].index
        self.launcher_menu()
        self.zyngui.screens['option'].select(index)

    def addTempo(self, tempo):
        try:
            slot = self.launcher_select_info["slot"]
            self.launcher_select_info["tempo"] = tempo
            self.zynseq.libseq.addTempoEvent(self.zynseq.bank, len(self.zynseq.launcher_info) * zynseq.LAUNCHER_COLS + slot, tempo, 1, 0)
            for chan in range(16):
                info = self.zynseq.launcher_info[slot][chan]
                if info["tempo"] != tempo:
                    info["tempo"] = tempo
                    proc = info["clippy"]
                    if proc and proc.controllers_dict[f"warp {slot+1:02}"].value:
                        proc.engine.on_tempo_cb()
        except Exception as e:
            logging.warning(f"Error setting scene tempo: {e}")

    def cb_assert_param_editor(self, val=None):
        self.send_controller_value(self.zyngui.screens['option'].param_editor_zctrl)
        index = self.zyngui.screens['option'].index
        self.launcher_menu()
        self.zyngui.screens['option'].select(index)

    def send_controller_value(self, zctrl):
        """ Handle param editor value change """

        slot = self.launcher_select_info["slot"]
        match zctrl.symbol:
            case "tempo":
                self.addTempo(zctrl.value)
            case "bpb":
                for chan in range(zynseq.LAUNCHER_COLS):
                    info = self.zynseq.launcher_info[slot][chan]
                    self.zynseq.libseq.setBeatsInPattern(info["pattern"], zctrl.value)
                    info["bpb"] = zctrl.value
            case "repeat":
                self.zynseq.libseq.setRepeat(self.zynseq.bank, self.launcher_select_info["sequence"], zctrl.value)
                self.launcher_select_info["repeat"] = zctrl.value
            case "follow":
                if zctrl.value == -1:
                    bank = -1
                else:
                    bank = self.zynseq.bank
                self.zynseq.libseq.setFollowAction(self.zynseq.bank, self.launcher_select_info["sequence"], bank, zctrl.value)
                self.launcher_select_info["follow_bank"] = bank
                self.launcher_select_info["follow_seq"] = zctrl.value

        self.main_mixbus_strip.draw_sequence_slot(slot)

    # --------------------------------------------------------------------------
    # Physical UI Control Management: Pots & switches
    # --------------------------------------------------------------------------

    def switch_select(self, type='S'):
        """ Function to handle SELECT button press
        type: Button press duration ["S"=Short, "B"=Bold, "L"=Long]

        returns True if event is managed, False if it's not
        """

        if super().switch_select(type):
            return True
        if self.moving_chain:
            self.end_moving_chain()
            return True
        elif self.moving_scene:
            self.end_moving_scene()
            return True
        elif type == "S":
            if self.launcher_mode:
                if self.launcher_highlighted_slot < self.zynseq.slots:
                    self.highlighted_strip.on_clip_short_press(self.launcher_highlighted_slot)
                else:
                    self.zyngui.chain_control()
            else:
                if self.zynmixer.midi_learn_zctrl:
                    self.midi_learn_menu()
                else:
                    self.zyngui.chain_control()
        elif type == "B":
            if self.launcher_mode and self.highlighted_strip.chan is not None and self.highlighted_strip.chan < 16 and self.launcher_highlighted_slot < self.zynseq.slots:
                self.edit_clip()
            else:
                self.item_menu()
        else:
            return False
        return True

    # Handle onscreen back button press => Should we use it for entering MIDI learn?
    # def backbutton_short_touch_action(self):
    #   if not self.back_action():
    #   self.enter_midi_learn()

    def back_action(self):
        """ Function to handle BACK action

        returns True if event is managed, False if it's not
        """

        if self.moving_chain:
            self.end_moving_chain()
            return True
        if self.moving_scene:
            self.end_moving_scene()
            return True
        elif self.zynmixer.midi_learn_zctrl:
            self.exit_midi_learn()
            return True
        elif self.param_editor_zctrl:
            self.disable_param_editor()
            return True

    def switch(self, swi, t):
        """ Function to handle switches press
        swi: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
        t: Press type ["S"=Short, "B"=Bold, "L"=Long]

        returns True if action fully handled or False if parent action should be triggered
        """

        if super().switch(swi, t):
            return True
        if swi == 0:
            if t == "S":
                if self.highlighted_strip is not None:
                    self.highlighted_strip.toggle_solo()
                return True
            elif t == "B" and self.zynmixer.midi_learn_zctrl:
                self.midi_learn_menu()
                return True

        elif swi == 1:
            # if zynthian_gui_config.enable_touch_navigation and self.zynmixer.midi_learn_zctrl:
            # return False
            # This is ugly, but it's the only way i figured for MIDI-learning "mute" without touch.
            # Moving the "learn" button to back is not an option. It's a labeled button on V4!!
            if t == "S" and not self.moving_chain and not self.moving_scene:
                if self.zynmixer.midi_learn_zctrl or self.highlighted_strip is not None and not self.back_action():
                    self.highlighted_strip.toggle_mute()
                return True
            elif t == "B":
                if self.zynmixer.midi_learn_zctrl:
                    self.back_action()
                else:
                    self.toggle_launcher_mode()
                return True

        elif swi == 3:
            return self.switch_select(t)

        return False

    def setup_zynpots(self):
        for i in range(zynthian_gui_config.num_zynpots):
            lib_zyncore.setup_behaviour_zynpot(i, 0)

    def zynpot_cb(self, i, dval):
        """ Function to handle zynpot callback
        """
        if not self.shown:
            return

        # Handle parameter editor
        if super().zynpot_cb(i, dval):
            return

        # LAYER encoder adjusts selected chain's level
        elif i == 0:
            if self.highlighted_strip is not None:
                self.highlighted_strip.nudge_volume(dval)

        # BACK encoder adjusts selected chain's balance/pan
        elif i == 1:
            if self.highlighted_strip is not None:
                self.highlighted_strip.nudge_balance(dval)

        # SNAPSHOT encoder adjusts main mixbus level
        elif i == 2:
            if self.launcher_mode:
                dval = -dval
            if dval > 0:
                self.arrow_up(dval)
            else:
                self.arrow_down(dval)

        # SELECT encoder moves chain selection
        elif i == 3:
            if self.moving_chain:
                self.chain_manager.move_chain(dval)
                self.refresh_visible_strips()
            elif self.moving_scene:
                self.launcher_highlighted_slot = self.zynseq.move_scene(self.launcher_highlighted_slot, dval)
                self.refresh_visible_strips()
            else:
                self.chain_manager.next_chain(dval)
            self.set_highlighted_clip_info()

    def arrow_left(self):
        """ Function to handle CUIA ARROW_LEFT
        """
        if self.moving_chain:
            self.chain_manager.move_chain(-1)
            self.refresh_visible_strips()
        else:
            self.chain_manager.previous_chain()

    def arrow_right(self):
        """ Function to handle CUIA ARROW_RIGHT
        """
        if self.moving_chain:
            self.chain_manager.move_chain(1)
            self.refresh_visible_strips()
        else:
            self.chain_manager.next_chain()

    def arrow_up(self, nudge=1):
        """ Function to handle CUIA ARROW_UP
        """
        if self.launcher_mode:
            if self.launcher_highlighted_slot > 0:
                if self.moving_scene:
                    slot = self.zynseq.move_scene(self.launcher_highlighted_slot, -1)
                else:
                    slot = self.launcher_highlighted_slot - nudge
                self.highlight_launcher_slot(slot)
        else:
            if self.highlighted_strip is not None:
                self.highlighted_strip.nudge_volume(nudge)

    def arrow_down(self, nudge=-1):
        """ Function to handle CUIA ARROW_DOWN
        """
        if self.launcher_mode:
            if self.launcher_highlighted_slot < len(self.zynseq.launcher_info):
                if self.moving_scene:
                    slot = self.zynseq.move_scene(self.launcher_highlighted_slot, 1)
                else:
                    slot = self.launcher_highlighted_slot - nudge
                self.highlight_launcher_slot(slot)
        else:
            if self.highlighted_strip is not None:
                self.highlighted_strip.nudge_volume(nudge)

    def backbutton_short_touch_action(self):
        if not self.back_action():
            self.zyngui.back_screen()

    def highlight_launcher_slot(self, slot):
        if slot < 0 or slot > self.zynseq.slots:
            return
        if self.launcher_offset > slot:
            self.launcher_offset = min(slot, self.zynseq.slots - zynthian_gui_config.visible_launchers)
        elif self.launcher_offset <= slot - zynthian_gui_config.visible_launchers:
            self.launcher_offset = max(0, slot - zynthian_gui_config.visible_launchers + 1)
        self.launcher_highlighted_slot = slot
        self.highlighted_strip.highlight_launcher(slot)
        self.set_highlighted_clip_info()

    def end_moving_chain(self):
        if zynthian_gui_config.enable_touch_navigation:
            self.show_back_button(False)
        self.moving_chain = False
        self.strip_drag_start = None
        self.refresh_visible_strips()

    def end_moving_scene(self):
        if zynthian_gui_config.enable_touch_navigation:
            self.show_back_button(False)
        self.moving_scene = False
        self.strip_drag_start = None
        self.refresh_visible_strips()

    # --------------------------------------------------------------------------
    # GUI Event Management
    # --------------------------------------------------------------------------

    def on_wheel(self, event):
        """ Function to handle mouse wheel event when not over fader strip
        event: Mouse event
        """
        if event.num == 5:
            if self.mixer_strip_offset < 1:
                return
            self.mixer_strip_offset -= 1
        elif event.num == 4:
            if self.mixer_strip_offset + len(self.visible_mixer_strips) >= self.chain_manager.get_chain_count() - 1:
                return
            self.mixer_strip_offset += 1
        self.highlight_active_chain()

    # --------------------------------------------------------------------------
    # MIDI learning management
    # --------------------------------------------------------------------------

    def midi_learn_menu(self):
        options = {}
        try:
            strip_id = self.zynmixer.midi_learn_zctrl.graph_path[0] + 1
            if strip_id == 17:
                strip_id = "Main"
            title = f"MIDI Learn Options ({strip_id})"
        except:
            title = f"MIDI Learn Options"

        if not self.zynmixer.midi_learn_zctrl:
            options["Enable MIDI learn" ] = "enable"

        if isinstance(self.zynmixer.midi_learn_zctrl, zynthian_controller):
            if self.zynmixer.midi_learn_zctrl.is_toggle:
                if self.zynmixer.midi_learn_zctrl.midi_cc_momentary_switch:
                    options["\u2612 Momentary => Latch"] = "latched"
                else:
                    options["\u2610 Momentary => Latch"] = "momentary"
        if isinstance(self.zynmixer.midi_learn_zctrl, zynthian_controller):
            options[f"Clean MIDI-learn ({self.zynmixer.midi_learn_zctrl.symbol})"] = "clean"
        else:
            options["Clean MIDI-learn (ALL)"] = "clean"

        self.midi_learn_sticky = self.zynmixer.midi_learn_zctrl
        self.zyngui.screens['option'].config(title, options, self.midi_learn_menu_cb)
        self.zyngui.show_screen('option')

    def midi_learn_menu_cb(self, options, params):
        if params == 'clean':
            self.midi_unlearn_action()
        elif params == 'enable':
            self.enter_midi_learn()
            self.zyngui.show_screen("audio_mixer")
        elif params == "latched":
            self.zynmixer.midi_learn_zctrl.midi_cc_momentary_switch = 0
        elif params == "momentary":
            self.zynmixer.midi_learn_zctrl.midi_cc_momentary_switch = 1

    def enter_midi_learn(self, zctrl=True):
        self.midi_learn_sticky = None
        if self.zynmixer.midi_learn_zctrl == zctrl:
            return
        self.zynmixer.midi_learn_zctrl = zctrl
        if zctrl != True:
            self.zynmixer.enable_midi_learn(zctrl)
        self.refresh_visible_strips()
        if zynthian_gui_config.enable_touch_navigation:
            self.show_back_button(True)

    def exit_midi_learn(self):
        if self.zynmixer.midi_learn_zctrl:
            self.zynmixer.midi_learn_zctrl = None
            self.zynmixer.disable_midi_learn()
            self.refresh_visible_strips()
            if zynthian_gui_config.enable_touch_navigation:
                self.show_back_button(False)

    def toggle_midi_learn(self):
        """ Pre-select all controls in a chain to allow selection of actual control to MIDI learn
        """
        match self.zynmixer.midi_learn_zctrl:
            case True:
                self.exit_midi_learn()
            case None:
                self.enter_midi_learn(True)
            case _:
                self.enter_midi_learn()

    def midi_unlearn_action(self):
        self.midi_learn_sticky = self.zynmixer.midi_learn_zctrl
        if isinstance(self.zynmixer.midi_learn_zctrl, zynthian_controller):
            self.zyngui.show_confirm(
                f"Do you want to clear MIDI-learn for '{self.zynmixer.midi_learn_zctrl.name}' control?",
                self.midi_unlearn_cb, self.zynmixer.midi_learn_zctrl)
        else:
            self.zyngui.show_confirm(
                "Do you want to clean MIDI-learn for ALL mixer controls?", self.midi_unlearn_cb)

    def midi_unlearn_cb(self, zctrl=None):
        if zctrl:
            self.zynmixer.midi_unlearn(zctrl)
        else:
            self.zynmixer.midi_unlearn_all()
        self.zynmixer.midi_learn_zctrl = True
        self.refresh_visible_strips()

# --------------------------------------------------------------------------
