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
from threading import Timer

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynaudioplayer import *
from zyngine.zynthian_signal_manager import zynsigman
from zynlibs.zynmixer.zynmixer import SS_ZYNMIXER_SET_VALUE

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


class zynthian_gui_mixer_strip:

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
        self.state_manager = parent.state_manager
        self.chain_manager = parent.chain_manager
        self.zynseq = parent.zynseq
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
        self.high_color = "#CCCC00"  # yellow
        self.rec_color = "#CC0000"  # red

        self.mute_color = zynthian_gui_config.color_on  # "#3090F0"
        self.solo_color = "#D0D000"
        self.mono_color = "#B0B0B0"

        # font_size = int(0.5 * self.legend_height)
        font_size = int(0.25 * self.width)
        self.font = (zynthian_gui_config.font_family, font_size)
        self.font_fader = (zynthian_gui_config.font_family, int(0.9 * font_size))
        self.font_clip_state = (zynthian_gui_config.font_family, int(0.8 * font_size))
        self.font_clip_title = (zynthian_gui_config.font_family, int(0.7 * font_size))
        self.font_icons = ("forkawesome", int(0.3 * self.width))
        self.font_timbase = (zynthian_gui_config.font_family, int(0.45 * font_size))

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
        height_phrase = (self.fader_bottom - self.fader_top - 4) // zynthian_gui_config.visible_launchers
        ypos = self.fader_top + 2
        # Scroll up available indicator
        self.canvas.create_rectangle(x, ypos - 2, x + self.fader_width, ypos, width=0, state=tkinter.HIDDEN,
                                        fill="white", tags=(f"strip:{id}", f"launcher_scroll_top_{id}"))
        for row in range(0, zynthian_gui_config.visible_launchers):
            # Launcher pad (background)
            launcher_bg = self.canvas.create_rectangle(x, ypos, x + self.fader_width, ypos + height_phrase - 1, width=0, state=tkinter.HIDDEN)
            self.canvas.itemconfig(launcher_bg, tags=(f"strip:{id}", f"launcher:{id}", f"launcher:{id}_{row}", f"launcher:{id}_{row}_bg"))
            # Play state text
            self.canvas.create_text(x + self.fader_width,  ypos - height_phrase // 6, text="", anchor=tkinter.NE, font=self.font_clip_state,
                    state=tkinter.HIDDEN, tags=(f"strip:{id}", f"launcher:{id}", f"launcher:{id}_{row}", f"launcher:{id}_{row}_state"))
            # Title text
            self.canvas.create_text(x + self.fader_width // 2, ypos + 0.5 * height_phrase, text="", anchor=tkinter.CENTER,
                                            font=self.font_clip_title, state=tkinter.HIDDEN, fill=self.legend_txt_color,
                                            tags=(f"strip:{id}", f"launcher:{id}", f"launcher:{id}_{row}", f"launcher:{id}_{row}_title"))
            # Play mode image
            self.canvas.create_image(x + 3, ypos, anchor=tkinter.NW, state=tkinter.HIDDEN,
                                            tags=(f"strip:{id}", f"launcher:{id}", f"launcher_{row}", f"launcher_{row}_mode_icon", f"launcher:{id}_{row}", f"launcher:{id}_{row}_mode_icon"))
            # Play mode text
            self.canvas.create_text(x + 2, ypos - height_phrase // 10, anchor=tkinter.NW, state=tkinter.HIDDEN, fill=self.legend_txt_color, font=self.font_clip_state,
                                            tags=(f"strip:{id}", f"launcher:{id}", f"launcher_{row}", f"launcher_{row}_mode_text", f"launcher:{id}_{row}", f"launcher:{id}_{row}_mode_text"))
            # Timesig text
            self.canvas.create_text(x + 2, ypos + height_phrase - 1, anchor=tkinter.SW, state=tkinter.HIDDEN, fill=self.legend_txt_color, font=self.font_timbase,
                                            tags=(f"strip:{id}", f"launcher:{id}", f"launcher_{row}", f"launcher_{row}_timesig_text", f"launcher:{id}_{row}", f"launcher:{id}_{row}_timesig_text"))
            # Tempo text
            self.canvas.create_text(x + self.fader_width - 1, ypos + height_phrase - 1, anchor=tkinter.SE, state=tkinter.HIDDEN, fill=self.legend_txt_color, justify=tkinter.RIGHT, font=self.font_timbase,
                                            tags=(f"strip:{id}", f"launcher:{id}", f"launcher_{row}", f"launcher_{row}_tempo_text", f"launcher:{id}_{row}", f"launcher:{id}_{row}_tempo_text"))
            # Selected/highlighted cursor
            self.canvas.create_rectangle(x, ypos, x + 3, ypos + height_phrase - 1, width=0, fill=self.legend_txt_color, state=tkinter.HIDDEN,
                                                  tags=(f"strip:{id}", "launcher_sel", f"launcher_sel:{id}_{row}"))

            self.canvas.tag_bind(f"launcher:{id}_{row}", '<ButtonPress-1>', lambda e, row=row: self.on_clip_press(row, e))
            self.canvas.tag_bind(f"launcher:{id}_{row}", '<ButtonRelease-1>', lambda e, row=row: self.on_clip_release(row, e))
            self.canvas.tag_bind(f"launcher:{id}_{row}", '<B1-Motion>', lambda e, row=row: self.on_clip_motion(row, e))
            ypos += height_phrase
        # Scroll down available indicator
        self.canvas.create_rectangle(x, ypos - 2, x + self.fader_width, ypos, width=0, state=tkinter.HIDDEN,
                                        fill="white", tags=(f"strip:{id}", f"launcher_scroll_bottom_{id}"))

        # DPM
        self.dpm_a = zynthian_gui_dpm(0, self.parent.main_canvas, self.dpm_a_x0, self.dpm_y0,
                                      self.dpm_width, self.fader_height, True, (f"strip:{self.fader_bg}", f"audio_strip:{self.fader_bg}"))
        self.dpm_b = zynthian_gui_dpm(1, self.parent.main_canvas, self.dpm_b_x0, self.dpm_y0,
                                      self.dpm_width, self.fader_height, True, (f"strip:{self.fader_bg}", f"audio_strip:{self.fader_bg}"))

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
                                                       tags=(f"strip:{id}", f"mixer:{id}", f"legend_strip:{id}"))
        self.legend_strip_txt = self.canvas.create_text(self.fader_centre_x, self.height - self.legend_height / 2, fill=self.legend_txt_color, text="-",
                                                   tags=(f"strip:{id}", f"mixer:{id}", f"legend_strip:{id}"), font=self.font)
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
                tags=(f"strip:{id}",)
            ))

        # Clip Launcher Progress Bar
        self.clip_progress = self.canvas.create_rectangle(x, self.height - self.legend_height, x, self.height - self.legend_height + 4, width=0,
                             fill=self.legend_txt_color, tags=(f"strip:{id}", f"mixer:{id}", f"legend_strip:{id}"))
        # Balance indicator
        self.balance_left = self.canvas.create_rectangle(x, self.balance_top, self.fader_centre_x, self.balance_top + self.balance_height,
                                                    fill=self.left_color, width=0, tags=(f"strip:{id}", f"mixer:{id}", f"balance:{id}", f"audio_strip:{id}"))
        self.balance_right = self.canvas.create_rectangle(self.fader_centre_x + 1, self.balance_top, self.width, self.balance_top + self.balance_height,
                                                     fill=self.right_color, width=0, tags=(f"strip:{id}", f"mixer:{id}", f"balance:{id}", f"audio_strip:{id}"))

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

        self.parent.main_canvas.itemconfig(f"strip:{self.fader_bg}", state=tkinter.NORMAL)
        try:
            if not self.chain.is_audio():
                self.parent.main_canvas.itemconfig(f"audio_strip:{self.fader_bg}", state=tkinter.HIDDEN)
        except:
            pass
        self.hidden = False
        self.draw_control()

    def draw_dpm(self, state):
        """ Function to draw the DPM level meter for a mixer strip
        state = [dpm_a, dpm_b, hold_a, hold_b, mono]
        """

        if self.hidden:
            return
        self.dpm_a.refresh(state[0], state[2], state[4])
        self.dpm_b.refresh(state[1], state[3], state[4])

    def draw_balance(self):
        """
        Draws the mixer strip balance indication
        """

        balance = self.chain.zynmixer_proc.controllers_dict["balance"].value
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
                                           self.x + self.width / 2, self.balance_top + self.balance_height)
            self.canvas.coords(self.balance_right,
                                           self.x + self.width / 2, self.balance_top,
                                           self.x + self.width * balance / 2 + self.width, self.balance_top + self.balance_height)

        self.parent.main_canvas.itemconfig(self.balance_left, fill=self.left_color)
        self.parent.main_canvas.itemconfig(self.balance_right, fill=self.right_color)

    """Draws the mixer strip level"""
    def draw_level(self):
        level = self.chain.zynmixer_proc.controllers_dict["level"].value
        if level is not None:
            self.canvas.coords(self.fader, self.x, self.fader_top + self.fader_height * (1 - level),
                                           self.x + self.fader_width, self.fader_bottom)

    def draw_fader(self):
        # Hide clip phrases
        self.canvas.itemconfig(f"strip:{self.fader_bg}", state=tkinter.HIDDEN)
        self.canvas.itemconfig(f"mixer:{self.fader_bg}", state=tkinter.NORMAL)
        if self.chain.zynmixer_proc:
            self.canvas.itemconfig(f"fader:{self.fader_bg}", state=tkinter.NORMAL)
            self.zyngui.multitouch.tag_bind(self.canvas, f"fader:{self.fader_bg}", "press", self.on_fader_press)
            self.zyngui.multitouch.tag_bind(self.canvas, f"fader:{self.fader_bg}", "motion", self.on_fader_motion)
            self.canvas.tag_bind(f"fader:{self.fader_bg}", "<ButtonPress-1>", self.on_fader_press)
            self.canvas.tag_bind(f"fader:{self.fader_bg}", "<ButtonRelease-1>", self.on_fader_release)
            self.canvas.tag_bind(f"fader:{self.fader_bg}", "<B1-Motion>", self.on_fader_motion)
        # Draw Fader
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
        self.canvas.itemconfig(f"legend_strip:{self.fader_bg}", state=tkinter.NORMAL)
        self.canvas.itemconfig(f"launcher:{self.fader_bg}", state=tkinter.NORMAL)
        self.zyngui.multitouch.tag_unbind(self.canvas, f"fader:{self.fader_bg}", "press")
        self.zyngui.multitouch.tag_unbind(self.canvas, f"fader:{self.fader_bg}", "motion")
        self.canvas.tag_unbind(f"fader:{self.fader_bg}", "<ButtonPress-1>")
        self.canvas.tag_unbind(f"fader:{self.fader_bg}", "<ButtonRelease-1>")
        self.canvas.tag_unbind(f"fader:{self.fader_bg}", "<B1-Motion>")

        # Clip Launcher
        for row in range(zynthian_gui_config.visible_launchers):
            try:
                phrase = self.parent.launcher_offset + row
                if phrase < self.zynseq.phrases:
                    self.draw_sequence_phrase(phrase)
                else:
                    self.canvas.itemconfig(f"launcher:{self.fader_bg}_{row}", state=tkinter.HIDDEN)
            except:
                self.canvas.itemconfig(f"launcher:{self.fader_bg}_{row}", state=tkinter.HIDDEN)

    def draw_sequence_phrase(self, phrase):
        if self.chain is None:
            return
        mode_image = None
        mode_text = ""
        timesig_text = ""
        tempo_text = ""
        row = phrase - self.parent.launcher_offset
        disabled = False
        if self.chain_id == 0:
            state_seq = self.zynseq.state["scenes"][self.zynseq.scene]["phrases"][phrase]
        elif type(self.chan) is not int:
            state_seq = None # This will raise an exception later and draw empty block
        else:
            state_seq = self.zynseq.state["scenes"][self.zynseq.scene]["phrases"][phrase]["sequences"][self.chain.midi_chan]
            """
            if self.chain.midi_chan > 15:
                note = phrase + 1
                try:
                    disabled |= self.chain.synth_slots[0][0].controllers_dict[f"file {note}"].value == ""
                except:
                    disabled = True
            """
        try:
            name = state_seq["name"]
            disabled |= state_seq["repeat"] == 0
            if disabled:
                color = zynthian_gui_config.PAD_COLOUR_DISABLED_LIGHT
            elif self.chain_id == 0:
                color = zynthian_gui_config.PAD_COLOUR_PHRASE
            else:
                color = zynthian_gui_config.LAUNCHER_COLOUR[self.chan]["rgb"]
            if self.parent.moving_phrase and phrase == self.parent.zynseq.phrase:
                if phrase == 0:
                    title = f"⇓ {name[:5]}"
                elif phrase == self.zynseq.phrases - 1:
                    title = f"⇑ {name[:5]}"
                else:
                    title = f"⇕ {name[:5]}"
            else:
                title = name[:5]
                if state_seq["repeat"]:
                    mode_text = f"x{state_seq['repeat']}"
                    match state_seq["followAction"]:
                        case zynseq.FOLLOW_ACTION_NONE:
                            mode_image = self.parent.mode_icons["oneshot"]
                            mode_text += "→"
                        case zynseq.FOLLOW_ACTION_RELATIVE:
                            if state_seq["followParam"] < 0:
                                mode_image = self.parent.mode_icons["oneshotall"]
                                mode_text += "↑"
                            elif state_seq["followParam"] > 0:
                                mode_image = self.parent.mode_icons["oneshotall"]
                                mode_text += "↓"
                            else:
                                mode_image = self.parent.mode_icons["loopsync"]
                                mode_text = "↻"
                        case _:
                            mode_image = self.parent.mode_icons["oneshotall"]
                            mode_text += "↦"
                else:
                    title = "⏹"
                    mode_image = self.parent.mode_icons["empty"]
                if self.chain_id == 0:
                    # Phrase launcher
                    if "sig" in state_seq:
                        sig = state_seq["sig"]
                        if sig:
                            timesig_text = f"{state_seq['sig']}/4"
                    if "tempo" in state_seq:
                        tempo = state_seq["tempo"]
                        if tempo:
                            tempo_text = f"{tempo}"
            match state_seq["state"]:
                case zynseq.SEQ_PLAYING:
                    color_state = zynthian_gui_config.PAD_COLOUR_PLAYING
                    state_text = "▶"
                case zynseq.SEQ_STARTING:
                    color_state = zynthian_gui_config.PAD_COLOUR_STARTING
                    state_text = "▶"
                case zynseq.SEQ_STOPPING:
                    color_state = zynthian_gui_config.PAD_COLOUR_STOPPING
                    state_text = "▶"
                case zynseq.SEQ_STOPPING_SYNC:
                    color_state = zynthian_gui_config.PAD_COLOUR_STOPPING
                    state_text = "▶"
                case zynseq.SEQ_CHILD_PLAYING:
                    color_state = zynthian_gui_config.PAD_COLOUR_STOPPED
                    state_text = "▶"
                case zynseq.SEQ_CHILD_STOPPING:
                    color_state = zynthian_gui_config.PAD_COLOUR_STOPPING
                    state_text = "▶"
                case zynseq.SEQ_STOPPED:
                    color_state = zynthian_gui_config.PAD_COLOUR_STOPPED
                    try:
                        pattern = state_seq["tracks"][0]["patns"]["0"]
                        if self.zynseq.state["patns"][str(pattern)]["events"]:
                            state_text = "⏹"
                        else: # Pattern empty
                            state_text = ""
                    except:
                        state_text = "" # Pattern does not exist
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
        if self.chain_id:
            # Chain sequence launcher
            self.canvas.itemconfig(f"launcher:{self.fader_bg}_{row}_mode_text", state=tkinter.HIDDEN)
            self.canvas.itemconfig(f"launcher:{self.fader_bg}_{row}_timebase_text", state=tkinter.HIDDEN)
            self.canvas.itemconfig(f"launcher:{self.fader_bg}_{row}_mode_icon", image=mode_image)
        else:
            # Phrase launcher
            self.canvas.itemconfig(f"launcher:{self.fader_bg}_{row}_mode_text", text=mode_text)
            self.canvas.itemconfig(f"launcher:{self.fader_bg}_{row}_timesig_text", text=timesig_text, state=tkinter.NORMAL)
            self.canvas.itemconfig(f"launcher:{self.fader_bg}_{row}_tempo_text", text=tempo_text, state=tkinter.NORMAL)
            self.canvas.itemconfig(f"launcher:{self.fader_bg}_{row}_mode_icon", state=tkinter.HIDDEN)
        if self.parent.launcher_offset:
            self.canvas.itemconfig(f"launcher_scroll_top_{self.fader_bg}", state=tkinter.NORMAL)
        if self.parent.launcher_offset + zynthian_gui_config.visible_launchers < self.zynseq.phrases:
            self.canvas.itemconfig(f"launcher_scroll_bottom_{self.fader_bg}", state=tkinter.NORMAL)

    def update_clip_progress(self, progress):
        x0 = self.x
        y0 = self.height - self.legend_height
        x1 = x0
        y1 = self.height - self.legend_height + 4
        x1 = x0 + int(progress * self.width / 100)
        self.canvas.coords(self.clip_progress, x0, y0, x1, y1)

    def draw_solo(self):
        txcolor = self.button_txcol
        font = self.font
        text = "S"
        if self.chain.zynmixer_proc.controllers_dict["solo"].value:
            bgcolor = self.solo_color
        else:
            bgcolor = self.button_bgcol

        self.canvas.itemconfig(self.solo, fill=bgcolor)
        self.canvas.itemconfig(self.solo_text, text=text, font=font, fill=txcolor)

    def draw_mute(self):
        txcolor = self.button_txcol
        font = self.font_icons
        if self.chain.zynmixer_proc.controllers_dict["mute"].value:
            bgcolor = self.mute_color
            text = "\uf32f"
        else:
            bgcolor = self.button_bgcol
            text = "\uf028"

        self.canvas.itemconfig(self.mute, fill=bgcolor)
        self.canvas.itemconfig(self.mute_text, text=text, font=font, fill=txcolor)

    def draw_control(self, control=None):
        """ Function to draw a mixer strip UI control
        control: Name of control or None to redraw all controls in the strip
        """
        if self.hidden or self.chain is None:  # or self.chain.zynmixer_proc.controllers_dict is None:
            return

        if control is None:
            if self.chain_id == 0:
                self.canvas.itemconfig(
                    self.legend_strip_txt, text="Main", font=self.font)
            else:
                font = self.font
                if self.parent.moving_chain and self.chain_id == self.chain_manager.active_chain_id:
                    strip_txt = f"⇦⇨"
                elif self.chain.synth_slots and self.chain.synth_slots[0][0].type == "Audio Generator":
                    strip_txt = "\uf028" # Speaker icon
                    font = self.font_icons
                elif isinstance(self.chain.midi_chan, int):
                    if 0 <= self.chain.midi_chan < 16:
                        strip_txt = f"♫ {self.chain.midi_chan + 1}"
                    elif self.chain.midi_chan == 0xffff:
                        strip_txt = f"♫ All"
                    else:
                        strip_txt = f"♫ Err"
                elif self.chain.is_audio():
                    if self.chain.zynmixer_proc.eng_code == "MI":
                        strip_txt = "\uf130" # Microphone icon
                    else:
                        strip_txt = "\uf1de" # Sliders
                    font = self.font_icons
                else:
                    strip_txt = ""
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

        if self.chain.zynmixer_proc:
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

            if control in [None, 'record']:
                if self.chain.zynmixer_proc.controllers_dict['record'].value:
                    if self.parent.zyngui.state_manager.audio_recorder.status:
                        self.parent.main_canvas.itemconfig(
                            self.record_indicator, fill=self.rec_color, state=tkinter.NORMAL)
                    else:
                        self.parent.main_canvas.itemconfig(
                            self.record_indicator, fill=self.high_color, state=tkinter.NORMAL)
                else:
                    self.parent.main_canvas.itemconfig(
                        self.record_indicator, state=tkinter.HIDDEN)

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
            self.chan = None
        else:
            if self.chain_id == 0:
                self.chan = 32
            else:
                self.chan = self.chain.midi_chan
            self.show()

    def set_volume(self, value):
        """ Function to set volume value
        value: Volume value (0..1)
        """
        if self.chain.zynmixer_proc:
            self.chain.zynmixer_proc.controllers_dict['level'].set_value(value)

    def get_volume(self):
        """ Function to get volume value
        """
        if self.chain.zynmixer_proc:
            return self.chain.zynmixer_proc.controllers_dict['level'].value

    def nudge_volume(self, dval):
        """ Function to nudge volume
        """
        if self.chain.zynmixer_proc:
            self.chain.zynmixer_proc.controllers_dict["level"].nudge(dval)

    def set_balance(self, value):
        """ Function to set balance value
        value: Balance value (-1..1)
        """
        if self.chain.zynmixer_proc:
            self.chain.zynmixer_proc.controllers_dict["balance"].set_value(value)
    def get_balance(self):
        """ Function to get balance value
        """
        if self.chain.zynmixer_proc:
            return self.chain.zynmixer_proc.controllers_dict['balance'].value

    def nudge_balance(self, dval):
        """ Function to nudge balance
        """
        if self.chain.zynmixer_proc:
            self.chain.zynmixer_proc.controllers_dict['balance'].nudge(dval)

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
        if self.chain.zynmixer_proc:
            self.chain.zynmixer_proc.controllers_dict['mute'].set_value(value)

    def set_solo(self, value):
        """ Function to set solo
        value: Solo value (True/False)
        """
        if self.chain.zynmixer_proc:
            self.chain.zynmixer_proc.controllers_dict['solo'].set_value(value)
            if self.chain_id == 0:
                self.parent.refresh_visible_strips()

    def toggle_mute(self):
        """ Function to toggle mute
        """
        if self.chain.zynmixer_proc:
            self.set_mute(int(not self.chain.zynmixer_proc.controllers_dict['mute'].value))

    def toggle_solo(self):
        """ Function to toggle solo
        """
        if self.chain.zynmixer_proc:
            self.set_solo(int(not self.chain.zynmixer_proc.controllers_dict['solo'].value))

    # --------------------------------------------------------------------------
    # Clip launcher functionality
    # --------------------------------------------------------------------------

    def highlight_launcher(self, phrase=None):
        if phrase is None:
            phrase = self.parent.zynseq.phrase
        self.canvas.itemconfig(f"launcher_sel", state=tkinter.HIDDEN)
        if phrase is not None and self.chain is not None:
            if self.chain_id == self.parent.chain_manager.active_chain_id:
                if phrase >= self.zynseq.phrases:
                    self.canvas.itemconfig(f"legend_sel:{self.parent.highlighted_strip.fader_bg}", state=tkinter.NORMAL)
                else:
                    row = phrase - self.parent.launcher_offset
                    self.canvas.itemconfig(f"launcher_sel:{self.parent.highlighted_strip.fader_bg}_{row}", state=tkinter.NORMAL)

    # --------------------------------------------------------------------------
    # Launcher UI event management
    # --------------------------------------------------------------------------

    def on_clip_press(self, row, event):
        self.touch_y = event.y
        self.touch_x = event.x
        self.drag_axis = None  # +1=dragging in y-axis, -1=dragging in x-axis
        self.touch_ts = monotonic()
        if self.chain:
            self.chain_manager.set_active_chain_by_object(self.chain)

    def on_clip_release(self, row, event):
        now = monotonic()
        ts = now - self.touch_ts
        self.touch_ts = None
        if self.drag_axis:
            self.drag_axis = None
            return
        phrase = row + self.parent.launcher_offset
        if self.parent.moving_phrase:
            self.parent.end_moving_phrase()
            return
        self.parent.select_launcher(phrase)
        if ts < zynthian_gui_config.zynswitch_bold_seconds:
            self.on_clip_short_press(phrase)
        elif ts < zynthian_gui_config.zynswitch_long_seconds:
            self.on_clip_bold_press(phrase)
        else:
            self.on_clip_long_press(phrase)

    def on_clip_motion(self, row, event):
        dY = int((event.y - self.touch_y) / self.parent.phrase_height)
        if dY:
            self.drag_axis = 1
            self.touch_y = event.y
            self.parent.drag_launcher(dY)

    def on_clip_short_press(self, phrase):
        if self.chan is None or self.chan > 32:
            return
        self.parent.phrase = phrase
        self.parent.highlighted_strip = self
        self.zynseq.libseq.togglePlayState(self.zynseq.scene, phrase, self.chan)

    def on_clip_bold_press(self, phrase):
        if self.chan is None or self.chan > 32:
            return
        self.parent.phrase = phrase
        self.parent.highlighted_strip = self
        self.parent.edit_clip()

    def on_clip_long_press(self, phrase):
        self.parent.edit_clip()

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
                self.chain.zynmixer_proc.controllers_dict['level'].value + (self.touch_y - event.y) / self.fader_height)
            self.touch_y = event.y
        elif self.drag_axis == "x":
            self.set_balance(
                self.chain.zynmixer_proc.controllers_dict['balance'].value - (self.touch_x - event.x) / self.fader_width)
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
        pass

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
            self.chain_manager.set_active_chain_by_object(self.chain)

    def on_strip_release(self, event):
        """ Function to handle legend strip release
        """
        if zynthian_gui_config.zyngui.cb_touch_release(event):
            return "break"

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
        self.ctrl_order = zynthian_gui_config.layout['ctrl_order']

        self.state_manager = self.zyngui.state_manager
        self.chain_manager = self.zyngui.chain_manager
        self.zynseq = self.state_manager.zynseq
        self.timesig = 4
        self.beat = 0

        self.launcher_mode = self.zyngui.alt_mode

        self.chan2strip = {} # Map of audio strips, indexed by [is_mixbus, mixer_channel]
        self.highlighted_strip = None  # highligted mixer strip object
        self.moving_chain = False  # True if moving a chain left/right
        self.moving_phrase = False # True if moving a launcher phrase up/down

        # List of (strip,control) requiring gui refresh (control=None for whole strip refresh)
        self.pending_refresh_queue = set()

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

        self.status_tempo = self.status_canvas.create_text(
            int(self.status_l - self.status_fs * 3.5), 2,
            anchor=tkinter.NE,
            fill=zynthian_gui_config.color_header_tx,
            font=("forkawesome", int(0.25 * self.status_h)),
            text="120.0 bpm",
            state=tkinter.NORMAL)

        self.status_timesig = self.status_canvas.create_text(
            int(self.status_l - self.status_fs * 8.5), 2,
            anchor=tkinter.NE,
            fill=zynthian_gui_config.color_header_tx,
            font=("forkawesome", int(0.25 * self.status_h)),
            text="[1] 4/4",
            state=tkinter.NORMAL)

        zynsigman.register_queued(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_TEMPO, self.set_tempo)
        zynsigman.register_queued(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_TIMESIG, self.set_timesig)

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
        self.launcher_offset = 0  # Index of first launcher phrase shown at top

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
        self.phrase_height = self.height // (zynthian_gui_config.visible_launchers + 3)
        iconsize = (int(self.fader_width * 0.4), int(self.phrase_height * 0.30))
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

        self.zyngui.state_manager.zynmixer_bus.enable_dpm(0, 0, False)

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
            self.moving_chain = self.moving_phrase = False
            if not self.zyngui.osc_clients:
                self.zyngui.state_manager.zynmixer_chan.enable_dpm(
                    0, self.zyngui.state_manager.zynmixer_chan.MAX_NUM_CHANNELS - 1, False)
                self.zyngui.state_manager.zynmixer_bus.enable_dpm(
                    1, self.zyngui.state_manager.zynmixer_bus.MAX_NUM_CHANNELS - 1, False)
            zynsigman.unregister(
                zynsigman.S_AUDIO_MIXER, SS_ZYNMIXER_SET_VALUE, self.update_control)
            zynsigman.unregister(
                zynsigman.S_STATE_MAN, self.state_manager.SS_LOAD_ZS3, self.cb_load_zs3)
            zynsigman.unregister(
                zynsigman.S_CHAIN_MAN, self.chain_manager.SS_SET_ACTIVE_CHAIN, self.update_active_chain)
            zynsigman.unregister(
                zynsigman.S_AUDIO_RECORDER, zynthian_audio_recorder.SS_AUDIO_RECORDER_STATE, self.update_control_rec)
            zynsigman.unregister(
                zynsigman.S_AUDIO_PLAYER, zynthian_engine_audioplayer.SS_AUDIO_PLAYER_STATE, self.update_control_play)
            zynsigman.unregister(
                zynsigman.S_MIDI, zynsigman.SS_MIDI_CC, self.midi_cc_cb)
            zynsigman.unregister(
                zynsigman.S_MIDI, zynsigman.SS_MIDI_PC, self.midi_pc_cb)
            zynsigman.unregister(
                zynsigman.S_STATE_MAN, self.state_manager.SS_ALL_NOTES_OFF, self.all_notes_off_cb)
            zynsigman.unregister(
                zynsigman.S_STEPSEQ, zynseq.SS_SEQ_PLAY_STATE, self.launcher_play_state_cb)
            zynsigman.unregister(
                zynsigman.S_STEPSEQ, zynseq.SS_SEQ_STATE, self.cb_launcher_refresh)
            zynsigman.unregister(
                zynsigman.S_MIDI, zynsigman.SS_MIDI_PC, self.midi_pc_cb)
            zynsigman.unregister(
                zynsigman.S_STATE_MAN, self.zyngui.state_manager.SS_ALL_NOTES_OFF, self.all_notes_off_cb)
            zynsigman.unregister(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_SELECT_PHRASE, self.select_phrase_cb)
            zynsigman.unregister(zynsigman.S_AUDIO_RECORDER, self.state_manager.audio_recorder.SS_AUDIO_RECORDER_ARM, self.audio_recorder_arm_cb)
            super().hide()

    def build_view(self):
        """ Function to handle showing display"""

        if len(self.visible_mixer_strips) != zynthian_gui_config.visible_mixer_strips or self.visible_launchers != zynthian_gui_config.visible_launchers:
                self.set_visible_chains(zynthian_gui_config.visible_mixer_strips)
        #self.launcher_mode = self.zyngui.alt_mode
        if zynthian_gui_config.enable_touch_navigation and self.moving_chain or self.moving_phrase:
            self.show_back_button()

        self.set_title()
        if zynthian_gui_config.enable_dpm:
            self.zyngui.state_manager.zynmixer_chan.enable_dpm(0, self.zyngui.state_manager.zynmixer_chan.MAX_NUM_CHANNELS - 1, True)
            self.zyngui.state_manager.zynmixer_bus.enable_dpm(0, self.zyngui.state_manager.zynmixer_bus.MAX_NUM_CHANNELS - 1, True)
        else:
            # Reset all DPM which will not be updated by refresh
            for strip in self.visible_mixer_strips:
                strip.draw_dpm([-200, -200, -200, -200, False])

        self.highlight_active_chain(True)
        self.setup_zynpots()
        if not self.shown:
            zynsigman.register(
                zynsigman.S_AUDIO_MIXER, SS_ZYNMIXER_SET_VALUE, self.update_control)
            zynsigman.register_queued(
                zynsigman.S_STATE_MAN, self.state_manager.SS_LOAD_ZS3, self.cb_load_zs3)
            zynsigman.register_queued(
                zynsigman.S_CHAIN_MAN, self.chain_manager.SS_SET_ACTIVE_CHAIN, self.update_active_chain)
            zynsigman.register_queued(
                zynsigman.S_AUDIO_RECORDER, zynthian_audio_recorder.SS_AUDIO_RECORDER_STATE, self.update_control_rec)
            zynsigman.register_queued(
                zynsigman.S_AUDIO_PLAYER, zynthian_engine_audioplayer.SS_AUDIO_PLAYER_STATE, self.update_control_play)
            zynsigman.register_queued(
                zynsigman.S_MIDI, zynsigman.SS_MIDI_CC, self.midi_cc_cb)
            zynsigman.register_queued(
                zynsigman.S_MIDI, zynsigman.SS_MIDI_PC, self.midi_pc_cb)
            zynsigman.register_queued(
                zynsigman.S_STATE_MAN, self.state_manager.SS_ALL_NOTES_OFF, self.all_notes_off_cb)
            zynsigman.register_queued(
                zynsigman.S_STEPSEQ, zynseq.SS_SEQ_PLAY_STATE, self.launcher_play_state_cb)
            zynsigman.register_queued(
                    zynsigman.S_STEPSEQ, zynseq.SS_SEQ_STATE, self.cb_launcher_refresh)
            zynsigman.register_queued(
                zynsigman.S_MIDI, zynsigman.SS_MIDI_PC, self.midi_pc_cb)
            zynsigman.register_queued(
                zynsigman.S_STATE_MAN, self.zyngui.state_manager.SS_ALL_NOTES_OFF, self.all_notes_off_cb)
            zynsigman.register_queued(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_SELECT_PHRASE, self.select_phrase_cb)
            zynsigman.register_queued(zynsigman.S_AUDIO_RECORDER, self.state_manager.audio_recorder.SS_AUDIO_RECORDER_ARM, self.audio_recorder_arm_cb)
        return True

    def update_layout(self):
        """Function to update display, e.g. after geometry changes
        """
        super().update_layout()
        # TODO: Update mixer layout

    def set_tempo(self, tempo):
        self.status_canvas.itemconfig(self.status_tempo, fill=zynthian_gui_config.color_ml, text=f"{tempo:.1f} bpm")
        Timer(0.6, self.clear_tempo_highlight).start()

    def clear_tempo_highlight(self):
        self.status_canvas.itemconfig(self.status_tempo, fill=zynthian_gui_config.color_header_tx)

    def set_timesig(self, timesig):
        self.timesig = timesig
        self.status_canvas.itemconfig(self.status_timesig, fill=zynthian_gui_config.color_ml, text=f"[{self.beat}] {timesig}/4")
        Timer(0.6, self.clear_timesig_highlight).start()

    def clear_timesig_highlight(self):
        self.status_canvas.itemconfig(self.status_timesig, fill=zynthian_gui_config.color_header_tx)

    def refresh_status(self):
        """Function to refresh screen (slow)
        """
        if self.shown:
            super().refresh_status()
            # Update main chain DPM
            state = self.zyngui.state_manager.zynmixer_bus.get_dpm_states(0, 0)[0]
            self.main_mixbus_strip.draw_dpm(state)
            # Update other chains DPM
            if zynthian_gui_config.enable_dpm:
                chan_states = self.zyngui.state_manager.zynmixer_chan.get_dpm_states(
                    0, self.zyngui.state_manager.zynmixer_chan.MAX_NUM_CHANNELS - 1)
                mixbus_states = self.zyngui.state_manager.zynmixer_bus.get_dpm_states(
                    0, self.zyngui.state_manager.zynmixer_bus.MAX_NUM_CHANNELS - 1)
                for strip in self.visible_mixer_strips:
                    if not strip.hidden and strip.chain.is_audio():
                        if strip.chain.zynmixer_proc.zynmixer == self.zyngui.state_manager.zynmixer_chan:
                            strip.draw_dpm(chan_states[strip.chain.zynmixer_proc.mixer_chan])
                        else:
                            strip.draw_dpm(mixbus_states[strip.chain.zynmixer_proc.mixer_chan])
                        if strip.chain.midi_chan is not None and strip.chain.midi_chan < 32:
                            strip.update_clip_progress(self.zynseq.progress[strip.chain.midi_chan])
            self.main_mixbus_strip.update_clip_progress(self.zynseq.progress[zynseq.PHRASE_CHANNEL])
            if self.beat != self.zynseq.beat:
                self.beat = self.zynseq.beat
                self.status_canvas.itemconfig(self.status_timesig, text=f"{self.beat} | {self.timesig}/4")
 
    def plot_zctrls(self):
        """Function to refresh display (fast)
        """
        while self.pending_refresh_queue:
            ctrl = self.pending_refresh_queue.pop()
            if ctrl[0]:
                ctrl[0].draw_control(ctrl[1])

    def update_control(self, mixbus, chan, symbol, value):
        """Mixer control update signal handler
        chan: Mixer channel
        symbol: Mixer control symbol
        value: Control value
        """

        try:
            strip = self.chan2strip[(mixbus, chan)]
        except:
            strip = None
        if not strip or not strip.chain or strip.chain.zynmixer_proc.mixer_chan is None:
            return
        self.pending_refresh_queue.add((strip, symbol))
        if symbol == "level":
            #value = strip.zctrls["level"].value
            if value > 0:
                level_db = 20 * log10(value)
                self.set_title(f"Volume: {level_db:.2f}dB ({strip.chain.get_description(1)})", None, None, 1)
            else:
                self.set_title(f"Volume: -∞dB ({strip.chain.get_description(1)})", None, None, 1)
        elif symbol == "balance":
            strip.parent.set_title(f"Balance: {int(value * 100)}% ({strip.chain.get_description(1)})", None, None, 1)

    def update_control_rec(self, state):
        """ Function to handle audio recorder status
        """
        for strip in self.visible_mixer_strips:
            self.pending_refresh_queue.add((strip, "record"))

    def update_control_play(self, handle, state):
        """ Function to handle audio play status
        """
        for strip in self.visible_mixer_strips:
            self.pending_refresh_queue.add((strip, "play"))

    def update_active_chain(self, active_chain):
        """ Function to handle active chain changes
        """
        self.highlight_active_chain(False, active_chain)
        self.select_launcher()
        for cc in (64, 66, 67, 69):
            self.midi_cc_cb(0, 0, cc, 0)

    def midi_cc_cb(self, izmip, chan, num, val):
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

    def midi_pc_cb(self, izmip, chan, num):
        if zynthian_gui_config.midi_prog_change_zs3 or self.launcher_mode:
            return
        for strip in self.visible_mixer_strips:
            if strip.chain and strip.chain.midi_chan == chan:
                strip.draw_fader()

    def cb_load_zs3(self, zs3_id):
        self.refresh_visible_strips()
        self.set_title()

    def all_notes_off_cb(self, chan=None):
        for strip in self.visible_mixer_strips:
            if strip.chain and strip.chain.is_midi() and (chan is None or strip.chain.midi_chan == chan):
                for i in range(0, 4):
                    self.main_canvas.itemconfig(strip.pedals[i], state=tkinter.HIDDEN)

    def select_phrase_cb(self, phrase):
        self.highlighted_strip.highlight_launcher(phrase)

    def audio_recorder_arm_cb(self, channel, arm):
        self.refresh_visible_strips()

    def launcher_play_state_cb(self, phrase, chan):
        if not self.launcher_mode:
            return
        try:
            if chan == zynseq.PHRASE_CHANNEL:
                self.main_mixbus_strip.draw_sequence_phrase(phrase)
                return
        except:
            pass
        for strip in self.visible_mixer_strips:
            try:
                if not strip.hidden and strip.chain.midi_chan == chan:
                    strip.draw_sequence_phrase(phrase)
            except:
                pass

    def cb_launcher_refresh(self):
        if not self.launcher_mode:
            return
        for strip in self.visible_mixer_strips:
            strip.draw_sequence_phrase(self.zynseq.phrase)
        self.select_launcher()

    def topbar_bold_touch_action(self):
        self.toggle_launcher_mode()

    def toggle_menu(self):
        if self.shown:
            self.zyngui.toggle_screen("main_menu")
        elif self.zyngui.current_screen == "option":
            self.zyngui.close_screen()

    def item_menu(self):
        if self.launcher_mode and self.zynseq.phrase < self.zynseq.phrases:
            # Launcher Options
            self.phrase_menu()
        else:
            # Chain Options
            self.zyngui.screens['chain_options'].setup(self.chain_manager.active_chain_id)
            self.zyngui.show_screen('chain_options')

    # --------------------------------------------------------------------------
    # Mixer Functionality
    # --------------------------------------------------------------------------

    def highlight_active_chain(self, refresh=False, chain_id=None):
        """ Higlights active chain, redrawing strips if required
        """
        if chain_id is None:
            chain_id = self.chain_manager.active_chain_id
        try:
            active_index = self.chain_manager.ordered_chain_ids.index(chain_id)
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
        if strip is None:
            strip = self.main_mixbus_strip
        self.highlighted_strip = strip
        if strip:
            strip.set_highlight(True)
            if self.launcher_mode:
                strip.highlight_launcher(self.zynseq.phrase)

    # Function refresh and populate visible mixer strips
    def refresh_visible_strips(self):
        """ Update the structures describing the visible strips

        returns - Active strip object
        """
        active_strip = None
        strip_index = 0
        if self.launcher_offset + zynthian_gui_config.visible_launchers > self.zynseq.phrases:
            self.launcher_offset = max(0, self.zynseq.phrases - zynthian_gui_config.visible_launchers)
        for chain_id in self.chain_manager.ordered_chain_ids[:-1][self.mixer_strip_offset:self.mixer_strip_offset + len(self.visible_mixer_strips)]:
            strip = self.visible_mixer_strips[strip_index]
            strip.set_chain(chain_id)
            # strip.draw_control()
            if strip.chain.is_audio():
                self.chan2strip[(strip.chain.zynmixer_proc.eng_code=="MR", strip.chain.zynmixer_proc.mixer_chan)] = strip
            if chain_id == self.chain_manager.active_chain_id:
                active_strip = strip
            strip_index += 1

        # Hide unpopulated strips
        for strip in self.visible_mixer_strips[strip_index:len(self.visible_mixer_strips)]:
            strip.set_chain(None)
            strip.zctrls = None

        strip = self.main_mixbus_strip
        strip.set_chain(0)
        self.chan2strip[(strip.chain.zynmixer_proc.eng_code=="MR", strip.chain.zynmixer_proc.mixer_chan)] = self.main_mixbus_strip

        self.main_mixbus_strip.draw_control()
        if self.highlighted_strip and self.launcher_mode:
            self.highlighted_strip.highlight_launcher(self.zynseq.phrase)
        return active_strip

    # --------------------------------------------------------------------------
    # Launcher Functionality
    # --------------------------------------------------------------------------

    def set_launcher_mode(self, launcher_mode=True):
        self.launcher_mode = launcher_mode
        if self.shown:
            for strip in self.visible_mixer_strips:
                if not strip.hidden:
                    strip.draw_control()
            self.main_mixbus_strip.draw_control()
            if self.highlighted_strip and self.launcher_mode:
                self.highlighted_strip.highlight_launcher(self.zynseq.phrase)

    def toggle_launcher_mode(self):
        if self.launcher_mode:
            self.zyngui.show_screen("audio_mixer")
        else:
            self.zyngui.show_screen("launcher")

    def phrase_menu(self):
        try:
            if self.highlighted_strip.chan == zynseq.PHRASE_CHANNEL:
                info = self.zynseq.state["scenes"][self.zynseq.scene]["phrases"][self.zynseq.phrase]
            else:
                info = self.zynseq.state["scenes"][self.zynseq.scene]["phrases"][self.zynseq.phrase]["sequences"][self.highlighted_strip.chan]
        except Exception as e:
            info = None
        if not info:
            return
        options = {}
        phrase = self.zynseq.phrase
        name = info["name"]
        repeat = info["repeat"]
        follow_action = info["followAction"]
        follow_phrase = info["followParam"]
        pattern = self.zynseq.libseq.getPattern(self.zynseq.scene, phrase, zynseq.PHRASE_CHANNEL, 0, 0)
        self.zynseq.libseq.selectPattern(pattern)
        title = f"Phrase options ({name})"
        if repeat == 0:
            options["Duration (DISABLED)"] = repeat
        else:
            if repeat == 1:
                options["Duration (1 bar)"] = repeat
            else:
                options[f"Duration ({repeat} bars)"] = repeat
            if follow_action == zynseq.FOLLOW_ACTION_NONE:
                options[f"Follow action (None)"] = 0
            elif follow_action == zynseq.FOLLOW_ACTION_RELATIVE:
                match follow_phrase:
                    case 0:  # Loop
                        options[f"Follow action (LOOP)"] = 1
                    case 1:  # Next
                        options[f"Follow action (NEXT)"] = 2
                    case -1:  # Previous
                        options[f"Follow action (PREV)"] = 3
            if 'tempo' not in info or info['tempo'] == 0.0:
                options[f"Tempo (NONE)"] = False
            else:
                options[f"Tempo ({info['tempo']})"] = info['tempo']
                options["Remove tempo"] = self.zynseq.phrase
            if 'sig' not in info or not info['sig']:
                options[f"Time signature (None)"] = 0
            else:
                options[f"Time signature ({info['sig']}/4)"] = info["sig"]
        options[f"Edit name ({name})"] = name
        options["Manipulate phrase"] = None
        options["Insert phrase"] = phrase
        if self.zynseq.phrases > 1:
            options["Remove phrase"] = phrase
            options["Move phrase"] = phrase

        self.zyngui.screens['option'].config(title, options, self.phrase_menu_cb, close_on_select=False)
        self.zyngui.show_screen('option')

    def phrase_menu_cb(self, option, params):
        option_screen = self.zyngui.screens["option"]
        if option.startswith("Edit name"):
            self.zyngui.show_keyboard(self.rename_phrase, params, 8)
        elif option.startswith("Append phrase"):
            self.zynseq.insert_phrase(self.zynseq.scene, self.zynseq.phrases)
            self.refresh_visible_strips()
            self.zyngui.show_screen("launcher")
        elif option.startswith("Insert phrase"):
            self.zynseq.insert_phrase(self.zynseq.scene, params)
            self.refresh_visible_strips()
            self.zyngui.show_screen("launcher")
        elif option.startswith("Remove phrase"):
            self.zyngui.show_confirm(f"Remove phrase {params + 1}?", self.remove_phrase, params)
        elif option.startswith("Move phrase"):
            self.moving_phrase = True
            self.zyngui.show_screen("launcher")
        elif option.startswith("Tempo"):
            if not params:
                params = self.zynseq.get_tempo()
            option_screen.enable_param_editor(option_screen, "tempo", {
                'name': 'BPM',
                'is_integer': False,
                'value_min': 10.0,
                'value_max': 420,
                'value': params,
                'nudge_factor': 1.0,
            }, assert_cb=self.cb_assert_param_editor)
        elif option == "Remove tempo":
            self.zynseq.set_sequence_param(self.zynseq.scene, params, zynseq.PHRASE_CHANNEL, "tempo", 0)
            index = option_screen.index
            self.phrase_menu()
            option_screen.select(index - 1)
        elif option.startswith("Duration"):
            labels = ["DISABLED", "1 bar"]
            for i in range(2, 256):
                labels.append(f"{i} bars")
            option_screen.enable_param_editor(option_screen, "duration", {
                'name': 'Duration',
                'value': params,
                'labels': labels
            }, assert_cb=self.cb_assert_param_editor)
        elif option.startswith("Time signature"):
            labels = ["None"]
            for i in range(1, 25):
                labels.append(f"{i}/4")
            option_screen.enable_param_editor(option_screen, "timeSig", {
                'name': 'Time signature',
                'value_min': 0,
                'value_max': 24,
                'labels': labels,
                'value': params
            }, assert_cb=self.cb_assert_param_editor)
        elif option.startswith("Follow action"):
            labels = ["NONE", "LOOP"]
            if (self.zynseq.phrase < self.zynseq.phrases - 1):
                labels.append("NEXT")
            if (self.zynseq.phrase > 0):
                labels.append("PREV")
            option_screen.enable_param_editor(option_screen, "follow", {
                "name": "Follow action",
                "labels": labels,
                "value": params
            }, assert_cb=self.cb_assert_param_editor)

    def remove_phrase(self, phrase):
        self.zynseq.remove_phrase(self.zynseq.scene, phrase)
        self.refresh_visible_strips()
        self.zyngui.show_screen("launcher")

    def drag_launcher(self, dy):
        new_pos = self.launcher_offset - dy
        if 0 <= new_pos <= len(self.zynseq.state["scenes"][self.zynseq.scene]["phrases"]) - self.visible_launchers:
            self.launcher_offset = new_pos
            self.refresh_visible_strips()

    def edit_pattern(self):
        pated = self.zyngui.screens['pattern_editor']
        pated.refresh_sequence_info()
        pated.load_pattern(self.zynseq.libseq.getPattern(self.zynseq.scene, self.zynseq.phrase, self.zynseq.chan, 0, 0))
        self.zyngui.show_screen("pattern_editor")
        return True

    def edit_clip(self):
        if self.highlighted_strip.chain_id == 0:
            self.item_menu()
            return True
        if type(self.highlighted_strip.chain.midi_chan) is int and self.highlighted_strip.chain.midi_chan < zynseq.PHRASE_CHANNEL:
            if self.highlighted_strip.chain.midi_chan > 15:
                proc = self.highlighted_strip.chain.get_processors()[0]
                proc.engine.set_phrase(proc, self.zynseq.phrase)
                self.zyngui.chain_control()
                return True
            else:
                return self.edit_pattern()

    def rename_phrase(self, name):
        self.zynseq.set_sequence_param(self.zynseq.scene, self.zynseq.phrase, zynseq.PHRASE_CHANNEL, "name", name)
        index = self.zyngui.screens['option'].index
        self.phrase_menu()
        self.zyngui.screens['option'].select(index)

    def cb_assert_param_editor(self, val=None):
        self.send_controller_value(self.zyngui.screens['option'].param_editor_zctrl)
        index = self.zyngui.screens['option'].index
        self.phrase_menu()
        self.zyngui.screens['option'].select(index)

    def send_controller_value(self, zctrl):
        """ Handle param editor value change """

        phrase = self.zynseq.phrase
        chan = self.highlighted_strip.chain.midi_chan
        if chan is None:
            chan = zynseq.PHRASE_CHANNEL
        match zctrl.symbol:
            case "tempo":
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, zynseq.PHRASE_CHANNEL, "tempo", zctrl.value)
                if "CL" in self.chain_manager.zyngines:
                    # Warp clips in this phrase to match tempo
                    clippy_engine = self.chain_manager.zyngines["CL"]
                    for processor in clippy_engine.processors:
                        try:
                            pattern = self.zynseq.get_pattern(self.zynseq.scene, phrase, processor.midi_chan, 0, 0)
                            note = self.zynseq.get_pattern_param(pattern, 0, "val1Start")
                            if processor.controllers_dict[f"warp {note}"]:
                                clippy_engine.set_file(processor, note, phrase=phrase)
                        except:
                            continue
            case "timeSig":
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, chan, "sig", zctrl.value)
            case "duration":
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, chan, "repeat", zctrl.value)
            case "follow":
                match zctrl.value2label[str(zctrl.value)]:
                    case "NONE":
                        followAction = zynseq.FOLLOW_ACTION_NONE
                        followParam = 0
                    case "LOOP":
                        followAction = zynseq.FOLLOW_ACTION_RELATIVE
                        followParam = 0
                    case "NEXT":
                        followAction = zynseq.FOLLOW_ACTION_RELATIVE
                        followParam = +1
                    case "PREV":
                        followAction = zynseq.FOLLOW_ACTION_RELATIVE
                        followParam = -1
                    case _:
                        return
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, chan, "followAction", followAction)
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, chan, "followParam", followParam)

        self.main_mixbus_strip.draw_sequence_phrase(phrase)

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
        elif self.moving_phrase:
            self.end_moving_phrase()
            return True
        elif type == "S":
            if self.launcher_mode:
                if self.zynseq.phrase < self.zynseq.phrases:
                    self.highlighted_strip.on_clip_short_press(self.zynseq.phrase)
                else:
                    self.zyngui.chain_control()
            else:
                self.zyngui.chain_control()
        elif type == "B":
            if self.launcher_mode and self.highlighted_strip.chan is not None and self.highlighted_strip.chan < 32 and self.zynseq.phrase < self.zynseq.phrases:
                self.edit_clip()
            else:
                self.item_menu()
        else:
            return False
        return True

    def back_action(self):
        """ Function to handle BACK action

        returns True if event is managed, False if it's not
        """

        if self.moving_chain:
            self.end_moving_chain()
            return True
        if self.moving_phrase:
            self.end_moving_phrase()
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

        elif swi == 1:
            # This is ugly, but it's the only way i figured for MIDI-learning "mute" without touch.
            # Moving the "learn" button to back is not an option. It's a labeled button on V4!!
            if t == "S" and not self.moving_chain and not self.moving_phrase:
                if self.highlighted_strip is not None and not self.back_action():
                    self.highlighted_strip.toggle_mute()
                return True
            elif t == "B":
                self.toggle_launcher_mode()
                return True

        elif swi == 3:
            return self.switch_select(t)

        return False

    def setup_zynpots(self):
        if zynthian_gui_config.num_zynpots > 3:
            npots = len(self.ctrl_order)
            for i in range(npots - 1):
                lib_zyncore.setup_behaviour_zynpot(self.ctrl_order[i], 0)
            lib_zyncore.setup_behaviour_zynpot(self.ctrl_order[npots - 1], 1)

    def zynpot_cb(self, i, dval):
        """ Function to handle zynpot callback
        """
        if not self.shown:
            return

        # Handle parameter editor
        if super().zynpot_cb(i, dval):
            return

        # Knob#1 adjusts selected chain's level
        elif i == 0:
            if self.highlighted_strip is not None:
                self.highlighted_strip.nudge_volume(dval)

        # Knob#2 adjusts selected chain's balance/pan
        elif i == 1:
            if self.highlighted_strip is not None:
                self.highlighted_strip.nudge_balance(dval)

        # Knob#3 adjusts main mixbus level
        elif i == 2:
            if self.launcher_mode:
                if dval < 0:
                    self.arrow_up(-dval)
                else:
                    self.arrow_down(-dval)
            else:
                self.main_mixbus_strip.nudge_volume(dval)

        # Knob#4 moves chain selection
        elif i == 3:
            if self.moving_chain:
                self.chain_manager.move_chain(dval)
                self.refresh_visible_strips()
            elif self.moving_phrase:
                self.zynseq.swap_phrase(self.zynseq.scene, self.zynseq.phrase, self.zynseq.phrase + dval) #TODO: This swaps, not moves
                self.select_launcher(self.zynseq.phrase +dval)
                #self.zynseq.phrase += dval
                self.refresh_visible_strips()
            else:
                self.chain_manager.next_chain(dval)

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
            if self.zynseq.phrase > 0:
                if self.moving_phrase:
                    self.zynseq.swap_phrase(self.zynseq.scene, self.zynseq.phrase, self.zynseq.phrase - nudge)
                    self.select_launcher(self.zynseq.phrase - nudge)
                    self.refresh_visible_strips()
                else:
                    self.select_launcher(self.zynseq.phrase - nudge)
        else:
            if self.highlighted_strip is not None:
                self.highlighted_strip.nudge_volume(nudge)

    def arrow_down(self, nudge=-1):
        """ Function to handle CUIA ARROW_DOWN
        """
        if self.launcher_mode:
            if self.zynseq.phrase < self.zynseq.phrases:
                if self.moving_phrase:
                    if self.zynseq.phrase < self.zynseq.phrases - 1:
                        self.zynseq.swap_phrase(self.zynseq.scene, self.zynseq.phrase, self.zynseq.phrase - nudge)
                        self.select_launcher(self.zynseq.phrase - nudge)
                        self.refresh_visible_strips()
                else:
                    self.select_launcher(self.zynseq.phrase - nudge)
        else:
            if self.highlighted_strip is not None:
                self.highlighted_strip.nudge_volume(nudge)

    def backbutton_short_touch_action(self):
        if not self.back_action():
            self.zyngui.back_screen()

    def select_launcher(self, phrase=None, strip=None):
        """
        Selects the current launcher
        """

        if self.zynseq.phrase == phrase:
            return
        if phrase is None:
            phrase = self.zynseq.phrase
        if phrase < 0:
            phrase = 0
        elif phrase > self.zynseq.phrases:
            phrase = self.zynseq.phrases
        if phrase != self.zynseq.phrase:
            self.zynseq.select_phrase(phrase)
        if strip is None:
            strip = self.highlighted_strip
        if strip != self.highlighted_strip:
            #TODO: Careful of looping code
            self.update_active_chain(strip.chain_id)
        refresh_strips = False
        offset = self.launcher_offset
        # This could be simplified, but it works ;-)
        if offset > phrase:
            offset = min(phrase, self.zynseq.phrases - zynthian_gui_config.visible_launchers)
        elif offset <= phrase - zynthian_gui_config.visible_launchers:
            offset = max(0, phrase - zynthian_gui_config.visible_launchers + 1)
        if offset > self.zynseq.phrases - zynthian_gui_config.visible_launchers:
            offset = max(0, self.zynseq.phrases - zynthian_gui_config.visible_launchers)
        if self.launcher_offset != offset:
            self.launcher_offset = offset
            refresh_strips = True
        if self.launcher_mode:
            self.highlighted_strip.highlight_launcher(phrase)
        if refresh_strips:
            self.refresh_visible_strips()

    def end_moving_chain(self):
        if not self.moving_chain:
            return
        if zynthian_gui_config.enable_touch_navigation:
            self.show_back_button(False)
        self.moving_chain = False
        self.strip_drag_start = None
        self.refresh_visible_strips()

    def end_moving_phrase(self):
        if zynthian_gui_config.enable_touch_navigation:
            self.show_back_button(False)
        self.moving_phrase = False
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
