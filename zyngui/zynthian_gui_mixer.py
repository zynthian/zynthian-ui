#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Audio Mixer
#
# Copyright (C) 2015-2026 Fernando Moyano <jofemodo@zynthian.org>
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


import tkinter
import logging
#import traceback
from math import log10
from time import monotonic
from threading import Timer
from PIL import Image, ImageTk
from os.path import basename, splitext

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq
from zynlibs.zynaudioplayer import *
from zynlibs.zynmixer.zynmixer import SS_ZYNMIXER_SET_VALUE
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_base import zynthian_gui_base
from zyngui.zynthian_gui_dpm import zynthian_gui_dpm
from zyngine.zynthian_signal_manager import zynsigman
from zyngine.zynthian_audio_recorder import zynthian_audio_recorder
from zyngine.zynthian_engine_audioplayer import zynthian_engine_audioplayer

logging.getLogger('PIL').setLevel(logging.WARNING)


# --------------------------------------------------------------
# Zynthian sequence launcher button class
# This provides a UI element that represents a launcher button
# --------------------------------------------------------------

DRAG_THRESHOLD = 5

class zynthian_gui_launcher_pad():

    def __init__(self, parent, canvas, x, y, width, height, chain, phrase):
        logging.getLogger('PIL').setLevel(logging.WARNING)
        """ Initialise mixer strip object
        args:
            parent: Parent object (zyngui_mixer)
            canvas: Canvas to draw onto
            x: Horizontal coordinate of left of launcher
            y: Vertical coordinate of top of launcher
            width: Width of launcher
            height: Height of launcher
            chain: Chain object for the strip that contains this launcher
            phrase: Phrase (row) index
        """

        self.gui_mixer = parent
        self.canvas = canvas
        self.x = x
        self.y = y
        self.height = height
        self.width = width
        self.chain = chain
        self.phrase = phrase

        id = self.chain.chain_id
        tags = ("launcher", f"strip_{id}", f"launcher_{id}_{phrase}")
        # Launcher pad (background)
        self.pad = self.canvas.create_rectangle(x, y, x + self.width - 1, y + self.height - 1,
                                                width=3,
                                                fill=zynthian_gui_config.color_panel_bg,
                                                tags=(*tags, "launcher_pad"))
        # Play state text
        self.play_state = self.canvas.create_text(x + self.width - 3,  y - 3, text="",
                                                  anchor=tkinter.NE,
                                                  font=self.gui_mixer.font_clip_state,
                                                  tags=(*tags, "launcher_play_state"))
        # Title text
        self.title = self.canvas.create_text(x + self.width // 2, y + 0.5 * self.height, text="",
                                             anchor=tkinter.CENTER,
                                             font=self.gui_mixer.font_clip_title,
                                             fill=self.gui_mixer.legend_txt_color,
                                             tags=(*tags, "launcher_title"))
        # Play mode image
        self.mode_icon = self.canvas.create_image(x + 3, y + 2,
                                                  anchor=tkinter.NW,
                                                  tags=(*tags, "launcher_mode_icon"))
        # Play mode text
        self.mode_text = self.canvas.create_text(x + 3, y - 3,
                                                 anchor=tkinter.NW,
                                                 fill=self.gui_mixer.legend_txt_color,
                                                 font=self.gui_mixer.font_clip_state,
                                                 tags=(*tags, "launcher_mode_text"))
        # Timesig text
        self.timesig = self.canvas.create_text(x + 3, y + self.height,
                                               anchor=tkinter.SW,
                                               fill=self.gui_mixer.legend_txt_color,
                                               font=self.gui_mixer.font_timebase,
                                               tags=(*tags, "launcher_timesig"))
        # Tempo text
        self.tempo = self.canvas.create_text(x + self.width - 1, y + self.height,
                                             anchor=tkinter.SE,
                                             fill=self.gui_mixer.legend_txt_color,
                                             justify=tkinter.RIGHT,
                                             font=self.gui_mixer.font_timebase,
                                             tags=(*tags, "launcher_tempo"))

        self.canvas.tag_bind(f"launcher_{id}_{phrase}", '<ButtonRelease-1>', self.on_clip_release)

    def highlight(self):
        """ Show selection cursor highlight"""

        self.canvas.itemconfig(self.pad, outline="yellow")

    def get_pattern_length(self, beats, bpb):
        if not bpb:
            bpb = 4
        if bpb > 1:
            bars = beats // bpb
        else:
            bars = 0
        extra_beats = beats % bpb
        if extra_beats == 0:
            beats_text = ""
        else:
            beats_text = f"{extra_beats}♩"
        if bars == 0:
            bars_text = ""
        else:
            bars_text = f"{bars}"
        if bars and extra_beats:
            return f"{bars_text} + {beats_text}"
        else:
            return bars_text + beats_text

    def draw(self):
        """ Update the launcher button elements"""

        mode_image = None
        mode_text = ""
        timesig_text = ""
        tempo_text = ""
        color_text = self.gui_mixer.legend_txt_color
        try:
            state_phrase = self.gui_mixer.zynseq.state["scenes"][self.gui_mixer.zynseq.scene]["phrases"][self.phrase]
            if self.chain.chain_id == 0:
                state_seq = state_phrase
            elif self.chain.midi_chan is None or self.chain.midi_chan > 31:
                state_seq = None  # This will raise an exception later and draw empty block
            else:
                state_seq = state_phrase["sequences"][self.chain.midi_chan]
            name = state_seq["name"]

            disabled = state_seq["repeat"] == 0
            empty = False

            # Moving phrase
            if self.gui_mixer.moving_phrase and self.phrase == self.gui_mixer.zynseq.phrase:
                if self.phrase == 0:
                    title = f"⇓ {name[:5]}"
                elif self.phrase == self.gui_mixer.zynseq.phrases - 1:
                    title = f"⇑ {name[:5]}"
                else:
                    title = f"⇕ {name[:5]}"
            # Normal draw
            else:
                title = name[:5]

                # Chain launcher =>
                if self.chain.chain_id:
                    # Zynstep pattern
                    if state_seq["group"] < 16:
                        try:
                            pattern = state_seq["tracks"][0]["patns"]["0"]
                            n_beats = self.gui_mixer.zynseq.libseq.getBeatsInPattern(pattern)
                            timesig_text = self.get_pattern_length(n_beats, state_phrase["bpb"])
                            try:
                                empty = len(self.gui_mixer.zynseq.state["patns"][str(pattern)]["events"]) == 0
                            except:
                                empty = True
                        except Exception as e:
                            logging.error(e)
                            disabled = True
                    # Clippy
                    else:
                        # TODO => Fix this!!
                        timesig_text = "1"
                        empty = False

                    match state_seq["followAction"]:
                        case zynseq.FOLLOW_ACTION_NONE:
                            if state_seq["repeat"] <= 1:
                                mode_text = "↦"
                            elif state_seq["repeat"] > 1:
                                mode_text = "x" + str(state_seq["repeat"])
                        case zynseq.FOLLOW_ACTION_RELATIVE:
                            if state_seq["followParam"] == 0:
                                mode_text = "↻"
                            else:
                                mode_text = "→"
                        case _:
                            mode_text = "→"

                    # Launcher background color
                    if empty:
                        color = zynthian_gui_config.PAD_COLOUR_EMPTY
                    else:
                        color = zynthian_gui_config.LAUNCHER_COLOUR[state_seq["group"]]["rgb"]

                # Phrase launcher =>
                else:
                    color = zynthian_gui_config.PAD_COLOUR_PHRASE
                    if state_seq["repeat"]:
                        if state_seq["repeat"] == 255:
                            mode_text = "a"
                        else:
                            mode_text = f"{state_seq['repeat']}"
                    else:
                        #title = "⏹"
                        pass

                    match state_seq["followAction"]:
                        case zynseq.FOLLOW_ACTION_NONE:
                            #mode_text += "→"
                            pass
                        case zynseq.FOLLOW_ACTION_RELATIVE:
                            if state_seq["followParam"] < 0:
                                mode_text += "↑"
                            elif state_seq["followParam"] > 0:
                                mode_text += "↓"
                            else:
                                mode_text = "↻"
                        case _:
                            #mode_text += "↦"
                            mode_text += ""

                    if "bpb" in state_seq:
                        sig = state_seq["bpb"]
                        if sig:
                            timesig_text = f"{state_seq['bpb']}/4"
                    if "tempo" in state_seq:
                        tempo = state_seq["tempo"]
                        if tempo:
                            tempo_text = f"{tempo:.1f}"

                if disabled:
                    color = zynthian_gui_config.PAD_COLOUR_DISABLED
                    color_text = zynthian_gui_config.PAD_COLOUR_STATE_DISABLED
                    color_state = zynthian_gui_config.PAD_COLOUR_STATE_DISABLED
                    state_text = ""
                else:
                    # Play state
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
                            state_text = "⏹"
                        case _:
                            color_text = zynthian_gui_config.PAD_COLOUR_STATE_DISABLED
                            color_state = zynthian_gui_config.PAD_COLOUR_STATE_DISABLED
                            state_text = "?"
        except:
            #logging.exception(traceback.format_exc())
            title = ""
            color = zynthian_gui_config.PAD_COLOUR_DISABLED
            color_text = zynthian_gui_config.PAD_COLOUR_STATE_DISABLED
            color_state = zynthian_gui_config.PAD_COLOUR_STATE_DISABLED
            state_text = "?"

        self.canvas.itemconfig(self.pad, fill=color)
        self.canvas.itemconfig(self.title, text=title, fill=color_text)
        self.canvas.itemconfig(self.play_state, text=state_text, fill=color_state)
        if self.chain.chain_id:
            # Chain sequence launcher
            self.canvas.itemconfig(self.mode_text, text=mode_text, fill=color_text, state=tkinter.NORMAL)
            self.canvas.itemconfig(self.timesig, text=timesig_text, fill=color_text, state=tkinter.NORMAL)
            self.canvas.itemconfig(self.tempo, state=tkinter.HIDDEN)
            self.canvas.itemconfig(self.mode_icon, state=tkinter.HIDDEN)
        else:
            # Phrase launcher
            self.canvas.itemconfig(self.mode_text, text=mode_text, fill=color_text, state=tkinter.NORMAL)
            self.canvas.itemconfig(self.timesig, text=timesig_text, fill=color_text, state=tkinter.NORMAL)
            self.canvas.itemconfig(self.tempo, text=tempo_text, fill=color_text, state=tkinter.NORMAL)
            self.canvas.itemconfig(self.mode_icon, state=tkinter.HIDDEN)

    def on_clip_release(self, event):
        if not self.gui_mixer.press_event or self.gui_mixer.dragging:
            return
        ts = event.time - self.gui_mixer.press_event.time
        ts /= 1000.0
        self.gui_mixer.select_launcher(self.phrase)
        self.gui_mixer.update_active_chain(self.chain.chain_id, True)
        if ts < zynthian_gui_config.zynswitch_bold_seconds:
            self.on_clip_short_press()
        elif ts < zynthian_gui_config.zynswitch_long_seconds:
            self.on_clip_bold_press()
        else:
            self.on_clip_long_press()

    def on_clip_short_press(self):
        if self.chain.chain_id:
            midi_chan = self.chain.midi_chan
        else:
            midi_chan = 32
        if midi_chan is None or midi_chan > 32:
            return
        self.gui_mixer.zynseq.libseq.togglePlayState(self.gui_mixer.zynseq.scene, self.phrase, midi_chan)

    def on_clip_bold_press(self):
        if self.chain.chain_id:
            midi_chan = self.chain.midi_chan
        else:
            midi_chan = 32
        if midi_chan is None or midi_chan > 32:
            return
        self.gui_mixer.edit_clip()

    def on_clip_long_press(self):
        self.gui_mixer.edit_clip()


# ------------------------------------------------------------------------------
# Zynthian Mixer Strip Class
# This provides a UI element that represents a mixer strip, one used per chain
# ------------------------------------------------------------------------------


class zynthian_gui_mixer_strip():

    def __init__(self, parent, canvas, x, width, height, chain):
        logging.getLogger('PIL').setLevel(logging.WARNING)
        """ Initialise mixer strip object
        args:
            parent: Parent object (zyngui_mixer)
            canvas: Canvas to draw onto
            x: Horizontal coordinate of left of fader
            width: Width of fader
            height: Height of fader
            chain: Chain object for this mixer strip
        """

        self.canvas = canvas
        self.gui_mixer = parent
        self.zyngui = parent.zyngui
        self.state_manager = self.zyngui.state_manager
        self.chain_manager = self.zyngui.chain_manager
        self.zynseq = self.state_manager.zynseq
        self.x = x
        self.width = width
        self.height = height

        self.chain = chain
        if self.chain.chain_id == 0:
            self.chan = 32
        else:
            self.chan = self.chain.midi_chan

        self.button_height = self.gui_mixer.button_height
        self.legend_height = self.gui_mixer.legend_height
        self.balance_height = self.gui_mixer.balance_height
        self.balance_width = (self.width - 2) / 2 # Width of each half of the balance indicator
        self.solo_y = parent.solo_y
        self.mute_y = parent.mute_y
        self.balance_y = parent.balance_y
        self.fader_y = parent.fader_y
        self.legend_y = parent.legend_y
        self.centre_x = x + int(self.width * 0.5)
        self.fader_text_limit = int(0.95 * self.gui_mixer.fader_height)
        self.dragging = False

        # Digital Peak Meter (DPM) parameters
        if zynthian_gui_config.enable_dpm or self.chain.chain_id == 0:
            self.dpm_width = int(self.width / 13)  # Width of each DPM
        else:
            self.dpm_width = 0
        self.dpm_length = self.gui_mixer.fader_height
        self.dpm_y0 = self.fader_y
        self.dpm_a_x0 = x + self.width - self.dpm_width * 2 - 2
        self.dpm_b_x0 = x + self.width - self.dpm_width - 1

        self.fader_width = self.width - self.dpm_width * 2 - 2

        self.fader_press_event = None
        self.launchers = [] # List of launcher button objects, indexed by phrase

        #Create GUI elements
        id = self.chain.chain_id

        # Block background to hide scrolling launchers, etc.
        self.audio_bg = self.canvas.create_rectangle(x, self.solo_y, x + self.width, parent.launcher_y, fill=self.gui_mixer.button_bgcol, width=0)
        # Fader background defines height of fader
        self.fader_bg = self.canvas.create_rectangle(x, self.fader_y, x + self.width, self.legend_y, fill=self.gui_mixer.fader_bg_color, width=0, tags=("fader", f"fader_{id}"))
        # Audio mixer elements
        if self.chain.zynmixer_proc:
            # Solo button
            self.solo = self.canvas.create_rectangle(x, self.solo_y, x + self.width, self.mute_y, fill=self.gui_mixer.button_bgcol, width=0,
                                                tags=(f"solo_{id}",))
            self.solo_text = self.canvas.create_text(x + self.width / 2, self.solo_y + self.button_height * 0.5, text="S", fill=self.gui_mixer.button_txcol, font=self.gui_mixer.font,
                                                tags=(f"solo_{id}",))

            # Mute button
            self.mute = self.canvas.create_rectangle(x, self.mute_y, x + self.width, self.balance_y, fill=self.gui_mixer.button_bgcol, width=0, tags=(f"mute_{id}",))
            self.mute_text = self.canvas.create_text(x + self.width / 2, self.mute_y + self.button_height * 0.5, text="M", fill=self.gui_mixer.button_txcol, font=self.gui_mixer.font, tags=(f"mute_{id}",))

            # Balance indicator
            self.balance_bg = self.canvas.create_rectangle(self.x + 1, self.balance_y, self.x + self.width - 1, self.fader_y, fill=self.gui_mixer.balance_bg_color, width=0, tags=(f"balance_{id}",))
            self.balance_fg = self.canvas.create_rectangle(self.centre_x - 1, self.balance_y, self.centre_x + 1, self.fader_y, fill=self.gui_mixer.balance_fg_color, width=0, tags=(f"balance_{id}",))
            # Fader
            self.fader_overlay = self.canvas.create_rectangle(x, self.fader_y, x + self.width, self.legend_y, fill=self.gui_mixer.fader_color, width=0, tags=("fader", "fader_overlay", f"fader_{id}"))
            self.fader_horizontal = self.canvas.create_rectangle(x, self.fader_y, x + self.width, self.fader_y + self.balance_height, fill=self.gui_mixer.fader_color, width=0, tags=("fader_horizontal",), state=tkinter.HIDDEN)

            # DPM
            if self.chain.chain_id:
                dpm_tags = ("dpm")
            else:
                dpm_tags = ("dpm_0")
            self.dpm_bg = self.canvas.create_rectangle(self.dpm_a_x0, self.dpm_y0, self.x + self.width + self.dpm_width, self.dpm_y0 + self.dpm_length, width=0, fill=self.gui_mixer.fader_bg_color)
            self.dpm_a = zynthian_gui_dpm(self.canvas, self.dpm_a_x0, self.dpm_y0, self.dpm_width, self.dpm_length, tags=dpm_tags)
            self.dpm_b = zynthian_gui_dpm(self.canvas, self.dpm_b_x0, self.dpm_y0, self.dpm_width, self.dpm_length, tags=dpm_tags)

        # Chain title
        self.fader_text = self.canvas.create_text(x, self.legend_y - 2, fill=self.gui_mixer.legend_txt_color, angle=90, anchor="nw", font=self.gui_mixer.font_fader, text="",
            tags=("fader", f"fader_{id}"), justify=tkinter.LEFT)

        # Legend strip at bottom of screen
        if self.chain.chain_id == 0:
            tags = ("legend", f"legend_strip_{id}", "legend_strip_main")
        elif self.chain.zynmixer_proc and self.chain.zynmixer_proc.eng_code=="MR":
            tags = ("legend", f"legend_strip_{id}", "legend_strip_bus")
        else:
            tags = ("legend", f"legend_strip_{id}")
        self.legend_strip_bg = self.canvas.create_rectangle(x, self.gui_mixer.legend_y, x + self.width, self.gui_mixer.legend_y + self.legend_height, width=0, fill=self.gui_mixer.legend_bg_color, tags=tags)
        self.legend_strip_txt = self.canvas.create_text(self.centre_x, self.gui_mixer.legend_y + self.legend_height / 2, fill=self.gui_mixer.legend_txt_color, text="-", tags=(f"legend_strip_{id}",), font=self.gui_mixer.font)

        # MIDI pedal indicators
        self.pedals = []
        for col in range(4):
            self.pedals.append(
                self.canvas.create_rectangle(
                    int(x + self.width / 5 * col),
                    self.gui_mixer.legend_y + self.legend_height - 4,
                    int(x + self.width / 5 * (col + 1)),
                    self.gui_mixer.legend_y + self.legend_height,
                    width=0,
                    fill="yellow",
                    state=tkinter.HIDDEN
                )
            )
        self.midi_indicator = self.canvas.create_rectangle(
            int(x + self.width / 5 * 4),
            self.gui_mixer.legend_y + self.legend_height - 4,
            int(x + self.width),
            self.gui_mixer.legend_y + self.legend_height,
            width=0,
            fill=zynthian_gui_config.color_status_midi,
            state=tkinter.HIDDEN
        )

        # Clip Launcher Progress Bar
        self.clip_progress = self.canvas.create_rectangle(x, self.gui_mixer.legend_y, x, self.gui_mixer.legend_y + 4, width=0, fill=self.gui_mixer.legend_txt_color, tags=(f"legend_strip_{id}",))

        # Indicators
        self.record_indicator = self.canvas.create_text(x + 2, self.gui_mixer.legend_y + self.gui_mixer.legend_height - 16, text="⚫", fill="#009000", anchor="sw", state=tkinter.HIDDEN)
        self.play_indicator = self.canvas.create_text(x + 2, self.gui_mixer.legend_y + self.gui_mixer.legend_height - 2, text="⏹", fill="#009000", anchor="sw", state=tkinter.HIDDEN)

        # Bind events to gui elements
        self.canvas.tag_bind(f"fader_{id}", "<ButtonPress-1>", self.on_fader_press)
        self.canvas.tag_bind(f"fader_{id}", "<ButtonRelease-1>", self.on_fader_release)
        self.canvas.tag_bind(f"fader_{id}", "<B1-Motion>", self.on_fader_motion)
        self.canvas.tag_bind(f"fader_{id}", "<Button-4>", self.on_fader_wheel_up)
        self.canvas.tag_bind(f"fader_{id}", "<Button-5>", self.on_fader_wheel_down)
        if self.chain.zynmixer_proc:
            self.canvas.tag_bind(self.fader_horizontal, "<Button-4>", self.on_fader_wheel_up)
            self.canvas.tag_bind(self.fader_horizontal, "<Button-5>", self.on_fader_wheel_down)
        self.canvas.tag_bind(f"balance_{id}", "<Button-4>", self.on_balance_wheel_up)
        self.canvas.tag_bind(f"balance_{id}", "<Button-5>", self.on_balance_wheel_down)
        self.canvas.tag_bind(f"mute_{id}", "<ButtonRelease-1>", self.on_mute_release)
        self.canvas.tag_bind(f"solo_{id}", "<ButtonRelease-1>", self.on_solo_release)
        self.canvas.tag_bind(f"legend_strip_{id}", "<ButtonRelease-1>", self.on_strip_release)

        self.draw_control()

    def set_launcher_mode(self, mode):
        try:
            if mode:
                self.canvas.coords(self.dpm_bg, self.dpm_a_x0, 0, self.x + self.width, self.balance_y)
                self.dpm_a.move(self.dpm_a_x0, 0, self.dpm_width, self.balance_y)
                self.dpm_b.move(self.dpm_b_x0, 0, self.dpm_width, self.balance_y)
                #self.canvas.coords(self.solo, self.x, self.solo_y, self.dpm_a_x0, self.mute_y)
                #self.canvas.coords(self.mute, self.x, self.mute_y, self.dpm_a_x0, self.balance_y)
            else:
                self.canvas.coords(self.dpm_bg, self.dpm_a_x0, self.dpm_y0, self.x + self.width, self.dpm_y0 + self.dpm_length)
                self.dpm_a.move(self.dpm_a_x0, self.dpm_y0, self.dpm_width, self.dpm_length)
                self.dpm_b.move(self.dpm_b_x0, self.dpm_y0, self.dpm_width, self.dpm_length)
                #self.canvas.coords(self.solo, self.x, self.solo_y, self.x + self.width, self.mute_y)
                #self.canvas.coords(self.mute, self.x, self.mute_y, self.x + self.width, self.balance_y)
        except:
            pass # meters not yet created?

    def draw_dpm(self):
        """ Function to draw the DPM level meter for a mixer strip
        """

        dpm = self.chain.zynmixer_proc.zynmixer.dpm[self.chain.zynmixer_proc.mixer_chan]
        self.dpm_a.refresh(dpm.a, dpm.a_hold, dpm.mono)
        self.dpm_b.refresh(dpm.b, dpm.b_hold, dpm.mono)

    def draw_balance(self):
        """
        Draws the mixer strip balance indication
        """

        balance = self.chain.zynmixer_proc.controllers_dict["balance"].value
        if balance is None:
            return
        if balance > 0:
            x = self.centre_x + balance * self.balance_width + 1
        else:
            x = self.centre_x + balance * self.balance_width - 1
        self.canvas.coords(self.balance_fg,
            self.centre_x, self.balance_y,
            x, self.balance_y + self.balance_height)

    """Draws the mixer strip level"""
    def draw_level(self):
        level = self.chain.zynmixer_proc.controllers_dict["level"].value
        if level is not None:
            self.canvas.coords(self.fader_overlay,
                self.x, self.fader_y + self.gui_mixer.fader_height * (1 - level),
                self.x + self.fader_width, self.legend_y)
            self.canvas.coords(self.fader_horizontal,
                self.x, self.fader_y,
                self.x + self.width * level, self.fader_y + self.balance_height)

    def draw_fader_text(self):
        label_parts = self.chain.get_description(2).split("\n") + [""]
        for i, label in enumerate(label_parts):
            self.canvas.itemconfig(self.fader_text, text=label)
            bounds = self.canvas.bbox(self.fader_text)
            if bounds and bounds[3] - bounds[1] > self.fader_text_limit:
                while bounds and bounds[3] - bounds[1] > self.fader_text_limit:
                    label = label[:-1]
                    self.canvas.itemconfig(self.fader_text, text=label)
                    bounds = self.canvas.bbox(self.fader_text)
                label_parts[i] = label + "..."
        self.canvas.itemconfig(self.fader_text, text="\n".join(label_parts))

    def update_clip_progress(self, progress):
        x1 = self.x + int(progress * self.width / 100)
        self.canvas.coords(self.clip_progress, self.x, self.gui_mixer.legend_y, x1, self.gui_mixer.legend_y + 4)

    def draw_solo(self):
        txcolor = self.gui_mixer.button_txcol
        font = self.gui_mixer.font
        text = "S"
        if self.chain.zynmixer_proc.eng_code == "MR" and self.chain.chain_id == 0:
            # Main mixbus so use the global solo state
            solo = self.state_manager.zynmixer_bus.get_global_solo() > 0
        else:
            solo = self.chain.zynmixer_proc.controllers_dict["solo"].value
        if solo:
            bgcolor = self.gui_mixer.solo_color
        else:
            bgcolor = self.gui_mixer.button_bgcol

        self.canvas.itemconfig(self.solo, fill=bgcolor)
        self.canvas.itemconfig(self.solo_text, text=text, font=font, fill=txcolor)

    def draw_mute(self):
        txcolor = self.gui_mixer.button_txcol
        font = self.gui_mixer.font_icons
        if self.chain.zynmixer_proc.controllers_dict["mute"].value:
            bgcolor = self.gui_mixer.mute_color
            text = "\uf32f"
        else:
            bgcolor = self.gui_mixer.button_bgcol
            text = "\uf028"

        self.canvas.itemconfig(self.mute, fill=bgcolor)
        self.canvas.itemconfig(self.mute_text, text=text, font=font, fill=txcolor)

    def draw_control(self, control=None):
        """
        Function to draw a mixer strip UI control
        Args:
            control: Name of control or None to redraw all controls in the strip
        """

        if control is None:
            # Draw the common elements used by all strips
            if self.chain.chain_id == 0:
                self.canvas.itemconfig(self.legend_strip_txt, text="Main", font=self.gui_mixer.font)
            else:
                if self.chain.is_generator():
                    font = self.gui_mixer.font_icons
                    strip_txt = "\uf028"  # Speaker icon
                elif self.chain.is_midi():
                    font = self.gui_mixer.font
                    if self.chain.audio_thru:
                        strip_txt = "\uf130♫"   # Add microphone icon for MIDI+Audio chains
                    else:
                        strip_txt = "♫ "
                    if 0 <= self.chain.midi_chan < 16:
                        strip_txt += f"{self.chain.midi_chan + 1}"
                    elif self.chain.midi_chan == 0xffff:
                        strip_txt += f"All"
                    else:
                        strip_txt += f"Err"
                elif self.chain.is_audio():
                    font = self.gui_mixer.font_icons
                    if self.chain.zynmixer_proc.eng_code == "MI":
                        strip_txt = "\uf130"  # Microphone icon
                    else:
                        strip_txt = "\uf1de"  # Sliders
                else:
                    font = self.gui_mixer.font_icons
                    strip_txt = ""
                    # procs = self.chain.get_processor_count() - 1
                self.canvas.itemconfig(self.legend_strip_txt, text=strip_txt, font=font)
            self.draw_fader_text()

        if self.chain.zynmixer_proc:
            if control in [None, 'level']:
                self.draw_level()

            if control in [None, 'solo']:
                self.draw_solo()

            if control in [None, 'mute']:
                self.draw_mute()

            if control in [None, 'balance']:
                self.draw_balance()

            if control in [None, 'record']:
                if self.chain.zynmixer_proc.controllers_dict['record'].value:
                    if self.state_manager.audio_recorder.status:
                        self.canvas.itemconfig(
                            self.record_indicator, fill=self.gui_mixer.rec_color, state=tkinter.NORMAL)
                    else:
                        self.canvas.itemconfig(
                            self.record_indicator, fill=self.gui_mixer.high_color, state=tkinter.NORMAL)
                else:
                    self.canvas.itemconfig(
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
    # Mixer UI event management
    # --------------------------------------------------------------------------

    def on_fader_press(self, event):
        """ Function to handle fader press
        Args:
            event: Mouse event
        """

        self.dragging = False
        if self.zyngui.cb_touch(event):
            return "break"
        if self.chain.is_audio():
            self.fader_start_value = self.chain.zynmixer_proc.controllers_dict['level'].value
            self.fader_press_event = event
        self.chain_manager.set_active_chain_by_object(self.chain)

    # Function to handle fader press
    # event: Mouse event
    def on_fader_release(self, event):
        self.fader_press_event = None

    def on_fader_motion(self, event):
        """ Function to handle fader drag
        Args:
            event: Mouse event
        """

        if not self.fader_press_event or not self.chain.is_audio():
            return
        if event.time - self.fader_press_event.time < 100:  # debounce initial touch
            return
        dy = event.y - self.fader_press_event.y
        if not self.dragging:
            if abs(dy) > 2:
                self.dragging = True
        if self.dragging:
            self.set_volume(self.fader_start_value + (self.fader_press_event.y - event.y) / self.gui_mixer.fader_height)

    # Function to handle mouse wheel down over fader
    # event: Mouse event
    def on_fader_wheel_down(self, event):
        if not event.state:
            self.nudge_volume(-1)

    def on_fader_wheel_up(self, event):
        """ Function to handle mouse wheel up over fader
        Args:
            event: Mouse event
        """

        if not event.state:
            self.nudge_volume(1)

    def on_balance_wheel_down(self, event):
        """  Function to handle mouse wheel down over balance
        Args:
            event: Mouse event
        """

        if not event.state:
            self.nudge_balance(-1)

    def on_balance_wheel_up(self, event):
        """ Function to handle mouse wheel up over balance
        Args:
            event: Mouse event
        """

        if not event.state:
            self.nudge_balance(1)

    def on_strip_release(self, event):
        """ Function to handle legend strip release
        Args:
            event: Mouse event
        """
        if self.zyngui.cb_touch_release(event):
            return "break" #TODO: "break" does not work with tab binding!
        if not self.gui_mixer.press_event or self.gui_mixer.dragging:
            return

        self.chain_manager.set_active_chain_by_id(self.chain.chain_id)
        if not self.gui_mixer.dragging:
            delta = event.time - self.gui_mixer.press_event.time
            self.gui_mixer.press_event = None
            if delta > 400:
                self.zyngui.screens['chain_manager'].select_chain_options_node()
                self.zyngui.show_screen('chain_manager')
            else:
                self.zyngui.chain_control(self.chain.chain_id)

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

class zynthian_gui_mixer(zynthian_gui_base):

    def __init__(self):
        super().__init__(has_backbutton=False)

        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=0)
        self.main_frame.rowconfigure(0, weight=1)
        self.left_canvas = tkinter.Canvas(
            self.main_frame,
            bd=0,
            highlightthickness=0,
            bg=zynthian_gui_config.color_panel_bg
        )
        self.left_canvas.grid(row=0, column=0, sticky="news")
        self.right_canvas = tkinter.Canvas(
            self.main_frame,
            bd=0,
            highlightthickness=0,
            bg=zynthian_gui_config.color_panel_bg
        )
        self.right_canvas.grid(row=0, column=1, sticky="nes", padx=(4,0))

        self.ctrl_order = zynthian_gui_config.layout['ctrl_order'] # List of encoder indices

        self.state_manager = self.zyngui.state_manager
        self.chain_manager = self.zyngui.chain_manager
        self.zynseq = self.state_manager.zynseq
        self.bpb = 4
        self.beat = 0
        self.chain_strips = [] # List of channel strips excluding main mixbus, indexed by strip position
        self.state_changed = True
        self.press_event = None
        self.dragging = False # True if click/touch dragging
        self._scroll_gen = 0 # Identifier for current scroll job - avoid concurrent thread conflicts
        self._scroll_y = 0 # Current vertial scroll offset in pixels
        self.scrollable_strips = 0 # Quantity of strips in left, scrollable canvas
        self._top_phrase = 0 # Index of phrase currently displayed at top of view
        self._left_chain = 0 # Index of chain currently displayed at left of view

        self.alt_mode = False
        self.launcher_mode = self.zyngui.alt_mode

        self.chan2strip = {} # Map of audio strips, indexed by [is_mixbus, mixer_channel]
        self.highlighted_strip = None  # Highligted mixer strip object
        self.moving_phrase = False # True if moving a launcher phrase up/down

        # List of (strip,control) requiring gui refresh (control=None for whole strip refresh)
        self.pending_refresh_queue = set()

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
            text="1 | 4/4",
            state=tkinter.NORMAL)

        self.left_canvas.bind("<Button-1>", self.on_press)
        self.left_canvas.bind("<B1-Motion>", self.on_motion)
        self.left_canvas.bind("<ButtonRelease-1>", self.on_release)
        self.left_canvas.bind("<Button-4>", self.on_wheel)
        self.left_canvas.bind("<Button-5>", self.on_wheel)
        self.right_canvas.bind("<Button-1>", self.on_press)
        self.right_canvas.bind("<B1-Motion>", self.on_motion)
        self.right_canvas.bind("<ButtonRelease-1>", self.on_release)
        self.right_canvas.bind("<Button-4>", self.on_wheel)
        self.right_canvas.bind("<Button-5>", self.on_wheel)

        self.update_layout()

    def cb_rename_chain(self, chain_id, title):
        for strip in self.chain_strips:
            if strip.chain.chain_id == chain_id:
                strip.draw_fader_text()
                return

    def cb_state_change(self):
        # Flag for deferred update to throttle expensive screen updates
        self.state_changed = True

    def update_layout(self):
        """Function to update display, e.g. after geometry or chain changes
        """

        self.state_changed = True
        super().update_layout()

        # Update geometry
        if zynthian_gui_config.visible_mixer_strips < 1:
            # Automatic sizing if not defined in config
            if self.width <= 400:
                self.visible_chains = 6
            elif self.width <= 600:
                self.visible_chains = 8
            elif self.width <= 800:
                self.visible_chains = 10
            elif self.width <= 1024:
                self.visible_chains = 12
            elif self.width <= 1280:
                self.visible_chains = 14
            else:
                self.visible_chains = 16
        else:
            self.visible_chains = zynthian_gui_config.visible_mixer_strips

        self.strip_width = self.width / (self.visible_chains + 0.2)
        self.button_height = int(self.height * 0.07)
        self.legend_height = int(self.height * 0.08)
        self.balance_height = int(self.height * 0.03)
        self.solo_y = 0
        self.mute_y = self.solo_y + self.button_height
        self.balance_y = self.mute_y + self.button_height
        self.fader_y = self.balance_y + self.balance_height
        self.launcher_y = self.fader_y + self.balance_height
        self.legend_y = self.height - self.legend_height
        self.fader_height = self.legend_y - self.fader_y

        # Style
        self.fader_bg_color = zynthian_gui_config.color_panel_bg
        self.fader_color = zynthian_gui_config.color_off
        self.fader_color_hl = "#6a727d"  # "#207024"
        self.legend_txt_color = zynthian_gui_config.color_tx
        self.legend_bg_color = zynthian_gui_config.color_panel_bg
        self.legend_bg_color_hl = zynthian_gui_config.color_on
        self.main_legend_bg_color = "#550000"
        self.bus_legend_bg_color = "#000055"
        self.button_bgcol = zynthian_gui_config.color_panel_bg
        self.button_txcol = zynthian_gui_config.color_tx
        self.balance_bg_color = "#888888"
        self.balance_fg_color = "#00EE00"
        self.high_color = "#CCCCCC"  # yellow
        self.rec_color = "#CC0000"  # red
        self.mute_color = zynthian_gui_config.color_on  # "#3090F0"
        self.solo_color = "#D0D000"
        self.mono_color = "#B0B0B0"
        font_size = min(int(0.5 * self.legend_height), int(0.25 * self.width))
        self.font = (zynthian_gui_config.font_family, font_size)
        self.font_fader = (zynthian_gui_config.font_family, int(0.9 * font_size))
        self.font_clip_state = (zynthian_gui_config.font_family, int(0.6 * font_size))
        self.font_clip_title = (zynthian_gui_config.font_family, int(0.7 * font_size))
        self.font_timebase = (zynthian_gui_config.font_family, int(0.5 * font_size))
        self.font_icons = ("forkawesome", int(1.2 * font_size))

        if zynthian_gui_config.visible_launchers < 1:
            # Automatic sizing if not defined in config
            if self.fader_height <= 400:
                visible_launchers = 4
            elif self.width <= 600:
                visible_launchers = 6
            elif self.width <= 800:
                visible_launchers = 8
            elif self.width <= 1024:
                visible_launchers = 10
            elif self.width <= 1280:
                visible_launchers = 12
            else:
                visible_launchers = 14
        else:
            visible_launchers = zynthian_gui_config.visible_launchers

        self.launcher_height = int((self.legend_y - self.launcher_y) / (visible_launchers + 0.2))

        #self.load_mode_icons()
        self.build_mixer()

    # Clip Mode Icons
    def load_mode_icons(self):
        empty_icon = tkinter.PhotoImage()
        iconsize = (int(self.strip_width * 0.4), int(self.launcher_height * 0.30))
        self.mode_icons = {}
        for f in ("empty", "loopsync", "oneshot", "oneshotall"):
            try:
                img = Image.open(f"/zynthian/zynthian-ui/icons/zynpad_mode_{f}.png")
                self.mode_icons[f] = ImageTk.PhotoImage(img.resize(iconsize))
            except:
                self.mode_icons[f] = empty_icon

    def build_mixer(self):
        """ Draw chain strips"""

        self.state_changed = True

        # Create mixer strip UI objects
        self.chan2strip = {}
        self.chain_strips = []
        self.left_canvas.delete("all")
        self.right_canvas.delete("all")
        self.right_canvas.configure(width=self.strip_width * self.chain_manager.get_pinned_count())
        self.scrollable_strips = len(self.chain_manager.chains) - self.chain_manager.get_pinned_count()
        div = self.chain_manager.get_pinned_pos()
        x0 = 0
        canvas = self.left_canvas
        for idx, chain in enumerate(list(self.chain_manager.chains.values())):
            if idx == div:
                x0 = 0
                canvas = self.right_canvas
            # Create the strip object
            strip = zynthian_gui_mixer_strip(self, canvas, x0, self.strip_width, self.height, chain)
            x0 += self.strip_width
            self.chain_strips.append(strip)
            # Add to optimisation map
            if chain.zynmixer_proc:
                self.chan2strip[chain.zynmixer_proc.eng_code=="MR", chain.zynmixer_proc.mixer_chan] = self.chain_strips[idx]

        self.build_launchers()
        self.state_changed = False
        self.left_canvas.configure(scrollregion=(0, 0, self.chain_manager.get_pinned_pos() * self.strip_width, self.height))
        self.refresh_launchers()
        self.refresh_mixer_controls()
        self.set_launcher_mode()

    def build_launchers(self):
        """ Build the sequence launcher buttons """
        self.left_canvas.delete("launcher")
        self.right_canvas.delete("launcher")
        self.launcher_total_height = self.launcher_height * self.zynseq.phrases

        canvas = self.left_canvas
        div = self.chain_manager.get_pinned_pos()
        for col, strip in enumerate(self.chain_strips):
            if col == div:
                canvas = self.right_canvas
            strip.launchers = []
            y = self.launcher_y - self._scroll_y
            for idx in range(self.zynseq.phrases):
                strip.launchers.append(zynthian_gui_launcher_pad(self, canvas, strip.x, y, self.strip_width, self.launcher_height, strip.chain, idx))
                y += self.launcher_height
        self.refresh_launchers()

    def refresh_launchers(self):
        if self.state_changed:
            return # Avoid refreshing controls whilst rebuilding state
        if not self.launcher_mode:
            return
        for strip in self.chain_strips:
            for launcher in strip.launchers:
                launcher.draw()
        self.highlight_launcher()

    def refresh_mixer_controls(self):
        for strip in self.chain_strips:
            strip.draw_control()
        self.highlight_chain(self.chain_manager.active_chain.chain_id)

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

    def build_view(self):
        """ Function to handle showing display"""
        #try:
        #    self.build_mixer() #TODO: Don't do full rebuild
        #except Exception as e:
        #    logging.warning(e)
        #self.set_launcher_mode()

        self.build_mixer()
        if zynthian_gui_config.enable_touch_navigation and self.moving_phrase:
            self.show_back_button()
        self.set_title()
        if zynthian_gui_config.enable_dpm:
            self.state_manager.zynmixer_chan.enable_dpm(True)
            self.state_manager.zynmixer_bus.enable_dpm(True)
            self.left_canvas.itemconfig("dpm", state=tkinter.NORMAL)
            self.right_canvas.itemconfig("dpm", state=tkinter.NORMAL)
        else:
            # Hide DPMs
            self.left_canvas.itemconfig("dpm", state=tkinter.HIDDEN)
            self.right_canvas.itemconfig("dpm", state=tkinter.HIDDEN)

        self.setup_zynpots()

        if not self.shown:
            self.set_tempo()
            zynsigman.register(zynsigman.S_MIXER, SS_ZYNMIXER_SET_VALUE, self.update_control)
            zynsigman.register_queued(zynsigman.S_MIDI, zynsigman.SS_MIDI_CC, self.midi_cc_cb)
            zynsigman.register_queued(zynsigman.S_MIDI, zynsigman.SS_MIDI_PC, self.midi_pc_cb)
            zynsigman.register_queued(zynsigman.S_STATE_MAN, self.state_manager.SS_LOAD_ZS3, self.cb_load_zs3)
            zynsigman.register_queued(zynsigman.S_STATE_MAN, self.state_manager.SS_ALL_NOTES_OFF, self.all_notes_off_cb)
            zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_SET_ACTIVE_CHAIN, self.update_active_chain)
            zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_RENAME_CHAIN, self.cb_rename_chain)
            zynsigman.register_queued(zynsigman.S_AUDIO_RECORDER, zynthian_audio_recorder.SS_AUDIO_RECORDER_STATE, self.update_control_rec)
            zynsigman.register_queued(zynsigman.S_AUDIO_RECORDER, self.state_manager.audio_recorder.SS_AUDIO_RECORDER_ARM, self.audio_recorder_arm_cb)
            zynsigman.register_queued(zynsigman.S_AUDIO_PLAYER, zynthian_engine_audioplayer.SS_AUDIO_PLAYER_STATE, self.update_control_play)
            zynsigman.register_queued(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_SELECT_PHRASE, self.highlight_launcher)
            zynsigman.register_queued(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_TEMPO, self.set_tempo)
            zynsigman.register_queued(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_TIMESIG, self.set_bpb)
            zynsigman.register_queued(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_PLAY_STATE, self.launcher_play_state_cb)
            zynsigman.register_queued(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_STATE, self.refresh_launchers)

        return True

    def hide(self):
        """ Function to handle hiding display
        """
        if self.shown:
            if not self.zyngui.osc_clients:
                self.zyngui.state_manager.zynmixer_chan.enable_dpm(False)
                self.zyngui.state_manager.zynmixer_bus.enable_dpm(False)
            zynsigman.unregister(zynsigman.S_MIXER, SS_ZYNMIXER_SET_VALUE, self.update_control)
            zynsigman.unregister(zynsigman.S_MIDI, zynsigman.SS_MIDI_CC, self.midi_cc_cb)
            zynsigman.unregister(zynsigman.S_MIDI, zynsigman.SS_MIDI_PC, self.midi_pc_cb)
            zynsigman.unregister(zynsigman.S_STATE_MAN, self.state_manager.SS_LOAD_ZS3, self.cb_load_zs3)
            zynsigman.unregister(zynsigman.S_STATE_MAN, self.state_manager.SS_ALL_NOTES_OFF, self.all_notes_off_cb)
            zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_SET_ACTIVE_CHAIN, self.update_active_chain)
            zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_RENAME_CHAIN, self.cb_rename_chain)
            zynsigman.unregister(zynsigman.S_AUDIO_RECORDER, zynthian_audio_recorder.SS_AUDIO_RECORDER_STATE, self.update_control_rec)
            zynsigman.unregister(zynsigman.S_AUDIO_RECORDER, self.state_manager.audio_recorder.SS_AUDIO_RECORDER_ARM, self.audio_recorder_arm_cb)
            zynsigman.unregister(zynsigman.S_AUDIO_PLAYER, zynthian_engine_audioplayer.SS_AUDIO_PLAYER_STATE, self.update_control_play)
            zynsigman.unregister(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_SELECT_PHRASE, self.highlight_launcher)
            zynsigman.unregister(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_TEMPO, self.set_tempo)
            zynsigman.unregister(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_TIMESIG, self.set_bpb)
            zynsigman.unregister(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_PLAY_STATE, self.launcher_play_state_cb)
            zynsigman.unregister(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_STATE, self.refresh_launchers)
            super().hide()

    def set_tempo(self, tempo=None):
        if tempo is None:
            self.status_canvas.itemconfig(self.status_tempo, text=f"{self.zynseq.get_tempo():.1f} bpm")
        else:
            self.status_canvas.itemconfig(self.status_tempo, fill=zynthian_gui_config.color_ml, text=f"{tempo:.1f} bpm")
            Timer(0.6, self.clear_tempo_highlight).start()

    def clear_tempo_highlight(self):
        self.status_canvas.itemconfig(self.status_tempo, fill=zynthian_gui_config.color_header_tx)

    def set_bpb(self, bpb):
        self.bpb = bpb
        self.status_canvas.itemconfig(self.status_timesig, fill=zynthian_gui_config.color_ml, text=f"{self.beat} | {bpb}/4")
        Timer(0.6, self.clear_timesig_highlight).start()

    def clear_timesig_highlight(self):
        self.status_canvas.itemconfig(self.status_timesig, fill=zynthian_gui_config.color_header_tx)

    def refresh_status(self):
        """Function to refresh screen (slow)
        """

        if self.shown:
            super().refresh_status()
            if zynthian_gui_config.enable_dpm:
                # Update all chains DPM
                self.zyngui.state_manager.zynmixer_chan.update_dpm_states()
                self.zyngui.state_manager.zynmixer_bus.update_dpm_states()
                if zynthian_gui_config.enable_dpm:
                    for strip in self.chain_strips:
                        if strip.chain.is_audio():
                            strip.draw_dpm()
            else:
                # Update main chain DPM
                self.state_manager.zynmixer_bus.update_dpm_states(1)
                self.chain_strips[-1].draw_dpm()
            if self.beat != self.zynseq.beat:
                self.beat = self.zynseq.beat
                self.status_canvas.itemconfig(self.status_timesig, text=f"{self.beat} | {self.bpb}/4")
            for strip in self.chain_strips:
                # Update MIDI activity indicators
                if strip.chain.midi_chan is not None:
                    if strip.chain.midi_chan < 16:
                        midi_act = self.zyngui.state_manager.status_midi_ch & (1 << strip.chain.midi_chan)
                    elif strip.chain.midi_chan > 32:
                        midi_act = self.zyngui.state_manager.status_midi_ch != 0
                    else:
                        midi_act = False
                    if midi_act:
                        strip.canvas.itemconfig(strip.midi_indicator, state=tkinter.NORMAL)
                    else:
                        strip.canvas.itemconfig(strip.midi_indicator, state=tkinter.HIDDEN)
                # Update progress indicators
                if strip.chain.midi_chan is not None and strip.chain.midi_chan < 32:
                    strip.update_clip_progress(self.zynseq.progress[strip.chain.midi_chan])
                elif strip.chain.chain_id == 0:
                    strip.update_clip_progress(self.zynseq.progress[32])

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
        if symbol == "solo" and strip.chain.chain_id == 0:
            for s in self.chain_strips:
                self.pending_refresh_queue.add((s, symbol))
        else:
            self.pending_refresh_queue.add((strip, symbol))
        if symbol == "level":
            #value = strip.zctrls["level"].value
            if value > 0:
                level_db = 20 * log10(value)
                self.set_title(f"Volume: {level_db:.2f}dB ({strip.chain.get_description(1)})", None, None, 1)
            else:
                self.set_title(f"Volume: -∞dB ({strip.chain.get_description(1)})", None, None, 1)
        elif symbol == "balance":
            strip.gui_mixer.set_title(f"Balance: {int(value * 100)}% ({strip.chain.get_description(1)})", None, None, 1)

    def update_control_rec(self, state):
        """ Function to handle audio recorder status
        """
        for strip in self.chain_strips:
            self.pending_refresh_queue.add((strip, "record"))

    def update_control_play(self, handle, state):
        """ Function to handle audio play status
        """
        for strip in self.chain_strips:
            self.pending_refresh_queue.add((strip, "play"))

    def update_active_chain(self, active_chain_id, send=False):
        """ Function to handle active chain changes
        Args:
            chain_id: Active chain id
            send: True to set chain manager active chain
        """

        if send:
            self.chain_manager.set_active_chain_by_id(active_chain_id)
        self.highlight_chain(active_chain_id)
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
            for strip in self.chain_strips:
                if strip.chain and strip.chain.is_midi():
                    if flags & (1 << strip.chain.zmop_index):
                        strip.canvas.itemconfigure(strip.pedals[index], state=tkinter.NORMAL)
                    else:
                        strip.canvas.itemconfig(strip.pedals[index], state=tkinter.HIDDEN)
        except Exception as e:
            logging.warning(e)

    def midi_pc_cb(self, izmip, chan, num):
        if zynthian_gui_config.midi_prog_change_zs3 or self.launcher_mode:
            return
        for strip in self.chain_strips:
            if strip.chain and strip.chain.midi_chan == chan:
                strip.draw_fader_text()

    def cb_load_zs3(self, zs3_id):
        self.refresh_mixer_controls()
        self.set_title()

    def all_notes_off_cb(self, chan=None):
        for strip in self.chain_strips:
            if strip.chain and strip.chain.is_midi() and (chan is None or strip.chain.midi_chan == chan):
                for i in range(0, 4):
                    strip.canvas.itemconfig(strip.pedals[i], state=tkinter.HIDDEN)

    def highlight_launcher(self, phrase=None):
        if not self.launcher_mode:
            return
        if phrase is None:
            phrase = self.zynseq.phrase
        self.left_canvas.itemconfig("launcher_pad", outline="")
        self.right_canvas.itemconfig("launcher_pad", outline="")
        try:
            self.highlighted_strip.launchers[phrase].highlight()
        except:
            pass

        # Scroll to ensure launcher is visible - use coords relative to launcher view
        launcher_top = phrase * self.launcher_height
        launcher_bottom = launcher_top + self.launcher_height
        view_top = self._scroll_y
        view_bottom = view_top + self.fader_height

        if launcher_top < view_top:
            # Scroll up
            new_y = launcher_top - 0.15 * self.launcher_height
        elif launcher_bottom > view_bottom:
            # Scroll down
            new_y = launcher_bottom + 0.15 * self.launcher_height - self.legend_y + self.launcher_y
        else:
            return  # already fully visible
        self.scroll_canvas(None, new_y, self.shown)

    def audio_recorder_arm_cb(self, channel, mixbus, value):
        pos = self.chain_manager.get_pos_by_mixer_chan(channel, mixbus)
        try:
            self.chain_strips[pos].draw_control("record")
        except:
            pass

    def launcher_play_state_cb(self, phrase, chan):
        if not self.launcher_mode:
            return
        if chan == 32:
            self.chain_strips[-1].launchers[phrase].draw()
        else:
            for strip in self.chain_strips:
                if strip.chain.midi_chan == chan:
                    strip.launchers[phrase].draw()

    def topbar_bold_touch_action(self):
        self.toggle_launcher_mode()

    def toggle_menu(self):
        if self.shown:
            # Chain options selected
            self.zyngui.screens['chain_manager'].select_chain_options_node()
            self.zyngui.toggle_screen("chain_manager")
        elif self.zyngui.get_current_screen() == "option":
            self.zyngui.close_screen()

    def item_menu(self):
        if self.launcher_mode and self.zynseq.phrase < self.zynseq.phrases:
            # Launcher Options
            self.phrase_menu()
        else:
            # Current processor selected
            self.zyngui.screens['chain_manager'].select_node(proc=self.chain_manager.active_chain.current_processor)
            self.zyngui.show_screen('chain_manager')

    # --------------------------------------------------------------------------
    # Selection and scrolling
    # --------------------------------------------------------------------------

    def highlight_chain(self, chain_id):
        """ Highlights chain, redrawing strips if required
        """

        if not self.chain_strips:
            return
        try:
            active_index = self.chain_manager.get_chain_index(chain_id)
            self.highlighted_strip = self.chain_strips[active_index]
            self.left_canvas.itemconfig("legend", fill=self.fader_bg_color)
            self.right_canvas.itemconfig("legend", fill=self.fader_bg_color)
            self.left_canvas.itemconfig("fader_overlay", fill=self.fader_color)
            self.right_canvas.itemconfig("fader_overlay", fill=self.fader_color)
        except:
            active_index = len(self.chain_strips) - 1
            self.highlighted_strip = self.chain_strips[active_index]

        self.left_canvas.itemconfig("legend", fill=self.fader_bg_color)
        self.right_canvas.itemconfig("legend", fill=self.fader_bg_color)
        self.right_canvas.itemconfig("legend_strip_main", fill=self.main_legend_bg_color)
        self.left_canvas.itemconfig("legend_strip_bus", fill=self.bus_legend_bg_color)
        self.right_canvas.itemconfig("legend_strip_bus", fill=self.bus_legend_bg_color)
        self.highlighted_strip.canvas.itemconfig(self.highlighted_strip.legend_strip_bg, fill=self.legend_bg_color_hl)
        self.left_canvas.itemconfig("fader_overlay", fill=self.fader_color)
        self.right_canvas.itemconfig("fader_overlay", fill=self.fader_color)
        if self.highlighted_strip.chain.is_audio():
            self.highlighted_strip.canvas.itemconfig(self.highlighted_strip.fader_overlay, fill=self.fader_color_hl)
        self.highlight_launcher()

        # Scroll to ensure chain is visible
        if active_index >= self.chain_manager.get_pinned_pos():
            return
        strip_left = active_index * self.strip_width
        strip_right = strip_left + self.strip_width
        canvas_width = self.left_canvas.winfo_width()
        view_left = self.left_canvas.canvasx(0)
        view_right = view_left + canvas_width
        try:
            content_width = self.left_canvas.bbox("all")[2]
        except:
            return # No content yet

        if content_width <= canvas_width:
            # Nothing to scroll
            return
        if strip_left < view_left:
            # Scroll left
            new_x = strip_left - 0.3 * self.strip_width
        elif strip_right > view_right:
            # Scroll right
            new_x = strip_right - canvas_width + 0.3 * self.strip_width
        else:
            return  # already fully visible
        self.scroll_canvas(new_x / content_width, None, self.shown)

    def scroll_canvas(self, target_x=None, target_y=None, smooth=True):
        """ Scroll the view
        Args:
            target_x: Target x-axis offset ratio (None to ignore)
            target_y: Target y-axis offset absolute (None to ignore)
            smooth: True to scroll smoothly
        Note: Horizontal scrolling is done with view move for smooth DPM behaviour. Vertical scrolling is done by moving the launcher pads.
        TODO: Should we separate these? We use the same callback here so slight optimisation in combining.
        """

        self._scroll_gen += 1
        gen = self._scroll_gen
        dx = dy = 0
        steps = 30
        delay = 10

        def step(i=0):
            if gen != self._scroll_gen:
                return # new scroll job started superceeding this job
            if i >= steps:
                # Ensure exact final position
                send_sig = False
                if target_x is not None:
                    self.left_canvas.xview_moveto(target_x)
                    left_chain = min(self.scrollable_strips - self.visible_chains, max(0, int(target_x * self.scrollable_strips + 0.4)))
                    if self._left_chain != left_chain:
                        self._left_chain = left_chain
                        send_sig = True
                if target_y is not None:
                    dy0 = self._scroll_y - target_y
                    self.left_canvas.move("launcher", 0, dy0)
                    self.right_canvas.move("launcher", 0, dy0)
                    self._scroll_y = target_y
                    # Calculate top left chain/phrase
                    top_phrase = int(target_y / self.launcher_height + 0.4)
                    if self._top_phrase != top_phrase:
                        self._top_phrase = top_phrase
                        send_sig = True
                if send_sig:
                    zynsigman.send(zynsigman.S_GUI, zynsigman.SS_GUI_VIEW_POS, left_chain=self._left_chain, top_phrase=self._top_phrase)
                return
            if target_x is not None:
                self.left_canvas.xview_moveto(start_x + dx * (i + 1))
            if target_y is not None:
                self.left_canvas.move("launcher", 0, dy)
                self.right_canvas.move("launcher", 0, dy)
                self._scroll_y -= dy
            self.right_canvas.after(delay, step, i + 1)

        if target_x is not None:
            try:
                start_x = self.left_canvas.xview()[0]
            except:
                return
            target_x = max(0.0, min(target_x, 1.0))
            dx = (target_x - start_x) / steps
        if target_y is not None:
            # Reverse direction to move objects, not view
            target_y = max(-3, min(target_y, self.launcher_total_height - self.fader_height + 12))
            dy = (self._scroll_y - target_y) / steps
        if smooth:
            step()
        else:
            step(steps)

    def on_press(self, event):
        self.press_event = event
        self.start_xview = event.widget.xview()[0]
        self.start_yview = event.widget.yview()[0]
        self.dragging = False

    def on_motion(self, event):
        if not self.press_event:
            return
        # Check threshold
        dx = self.press_event.x - event.x
        dy = self.press_event.y - event.y
        if not self.dragging:
            if self.launcher_mode and self.press_event.widget == self.right_canvas and abs(dy) > DRAG_THRESHOLD:
                self.dragging = True
            elif self.press_event.widget == self.left_canvas and self.press_event.y > self.legend_y and abs(dx) > DRAG_THRESHOLD:
                self.dragging = True
            else:
                return
        try:
            sr = event.widget.bbox("all")
            # Horizontal Move
            if self.press_event.widget == self.left_canvas:
                sr_w = sr[2] - sr[0]
                canvas_w = event.widget.winfo_width()
                if sr_w > canvas_w:
                    d_fract_x = dx / float(sr_w)
                    xview = self.start_xview + d_fract_x
                    self.scroll_canvas(target_x=xview, smooth=False)
             # Vertical Move
            elif self.press_event.widget == self.right_canvas:
                if not self.launcher_mode:
                    return
                if self.moving_phrase:
                    #TODO: Improve view edge handling
                    dP = int(dy / self.launcher_height)
                    if dP > 0:
                        self.arrow_up()
                        self.press_event.y = event.y
                    elif dP < 0:
                        self.arrow_down()
                        self.press_event.y = event.y
                else:
                    self.scroll_canvas(0, self._scroll_y + dy, False)
                    self.press_event.y = event.y
        except Exception as e:
            pass

    def on_release(self, event):
        self.press_event = None
        self.dragging = False

    def on_wheel(self, event):
        """ Handle mouse wheel event
        Args:
            event: Mouse event
        Note: Use modifier key to alter behaviour
        """

        if event.y < self.launcher_y:
            return
        if event.num == 4:
            if event.state or event.y > self.legend_y:
                self.arrow_right()
            elif self.launcher_mode:
                self.arrow_up()
        else:
            if event.state or event.y > self.legend_y:
                self.arrow_left()
            elif self.launcher_mode:
                self.arrow_down()

    # --------------------------------------------------------------------------
    # Launcher Functionality
    # --------------------------------------------------------------------------

    def set_launcher_mode(self, launcher_mode=None):
        if launcher_mode is None:
            launcher_mode = self.launcher_mode
        if not self.chain_strips:
            self.launcher_mode = False
        else:
            self.launcher_mode = launcher_mode

        for strip in self.chain_strips:
            strip.set_launcher_mode(launcher_mode)

        if self.launcher_mode:
            self.refresh_launchers()
            self.left_canvas.itemconfig("fader", state=tkinter.HIDDEN)
            self.right_canvas.itemconfig("fader", state=tkinter.HIDDEN)
            self.left_canvas.itemconfig("fader_horizontal", state=tkinter.NORMAL)
            self.right_canvas.itemconfig("fader_horizontal", state=tkinter.NORMAL)
            self.left_canvas.tag_lower("launcher")
            self.right_canvas.tag_lower("launcher")
            self.left_canvas.itemconfig("launcher", state=tkinter.NORMAL)
            self.right_canvas.itemconfig("launcher", state=tkinter.NORMAL)
            self.highlight_launcher()
        else:
            self.left_canvas.itemconfig("fader", state=tkinter.NORMAL)
            self.right_canvas.itemconfig("fader", state=tkinter.NORMAL)
            self.left_canvas.itemconfig("fader_horizontal", state=tkinter.HIDDEN)
            self.right_canvas.itemconfig("fader_horizontal", state=tkinter.HIDDEN)
            self.left_canvas.itemconfig("launcher", state=tkinter.HIDDEN)
            self.right_canvas.itemconfig("launcher", state=tkinter.HIDDEN)
        zynsigman.send(zynsigman.S_GUI, zynsigman.SS_GUI_LAUNCHER_MODE, mode=launcher_mode)

    def toggle_launcher_mode(self):
        self.set_launcher_mode(not self.launcher_mode)

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
        title = f"Phrase options ({name})"
        options["> Manipulate this phrase"] = None
        if repeat == 0:
            options["Duration (DISABLED)"] = repeat
        else:
            if repeat == 255:
                options["Duration (AUTO)"] = repeat
            else:
                if repeat == 1:
                    unit = "bar"
                else:
                    unit = "bars"
                options[f"Duration ({repeat} {unit})"] = repeat
            if follow_action == zynseq.FOLLOW_ACTION_NONE:
                options[f"Follow action (NONE)"] = 0
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
                options[f"Tempo ({info['tempo']:.1f})"] = info['tempo']
                options["Remove tempo"] = self.zynseq.phrase
            if "bpb" not in info or not info["bpb"]:
                options[f"Beats per bar (NONE)"] = 0
            else:
                options[f"Beats per bar ({info['bpb']})"] = info["bpb"]
        options[f"Edit name ({name})"] = name
        options["> Manipulate global phrases"] = None
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
            self.build_launchers()
            self.zyngui.show_screen("launcher")
        elif option.startswith("Insert phrase"):
            self.zynseq.insert_phrase(self.zynseq.scene, params)
            self.build_launchers()
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
            labels = ["DISABLED", "AUTO", "1 bar"]
            for i in range(2, 255):
                labels.append(f"{i} bars")
            if params == 255:
                value = 1
            elif params:
                value = params + 1
            else:
                value = 0
            option_screen.enable_param_editor(option_screen, "duration", {
                'name': 'Duration',
                'value': value,
                'labels': labels,
            }, assert_cb=self.cb_assert_param_editor)
        elif option.startswith("Beats per bar"):
            labels = []
            for i in range(1, 25):
                labels.append(f"{i}")
            option_screen.enable_param_editor(option_screen, "bpb", {
                'name': 'Beats per bar',
                'value_min': 1,
                'value_max': 24,
                'labels': labels,
                'value': params
            }, assert_cb=self.cb_assert_param_editor)
        elif option.startswith("Follow action"):
            labels = ["NONE"]
            if self.zynseq.phrase < self.zynseq.phrases - 1:
                labels.append("NEXT")
            if self.zynseq.phrase > 0:
                labels.append("PREV")
            option_screen.enable_param_editor(option_screen, "follow", {
                "name": "Follow action",
                "labels": labels,
                "value": params
            }, assert_cb=self.cb_assert_param_editor)

    def remove_phrase(self, phrase):
        self.zynseq.remove_phrase(self.zynseq.scene, phrase)
        self.build_launchers()
        self.zyngui.show_screen("launcher")

    def drag_launcher(self, dy):
        logging.warning(dy)

    def edit_pattern(self):
        pated = self.zyngui.screens['pattern_editor']
        pated.refresh_sequence_info()
        pated.load_pattern(self.zynseq.libseq.getPattern(self.zynseq.scene, self.zynseq.phrase, self.zynseq.chan, 0, 0))
        #pated.enable_sequence()
        self.zyngui.show_screen("pattern_editor")
        return True

    def edit_clip(self):
        if self.highlighted_strip.chain.chain_id == 0:
            self.item_menu()
            return True
        if type(self.highlighted_strip.chain.midi_chan) is int and self.highlighted_strip.chain.midi_chan < zynseq.PHRASE_CHANNEL:
            if self.highlighted_strip.chain.midi_chan > 15:
                proc = self.highlighted_strip.chain.get_processors()[0]
                proc.engine.set_phrase(proc, self.zynseq.phrase)
                self.zyngui.chain_control(self.highlighted_strip.chain.chain_id, proc)
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
            case "bpb":
                #self.zynseq.set_sequence_param(self.zynseq.scene, phrase, chan, "bpb", zctrl.value)
                self.zynseq.libseq.setPhraseBPB(self.zynseq.scene, phrase, zctrl.value)
                self.zynseq.refresh_state()
            case "duration":
                if zctrl.value == 1:
                    value = 255
                elif zctrl.value > 1:
                    value = zctrl.value - 1
                else:
                    value = 0
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, chan, "repeat", value)
            case "follow":
                match zctrl.value2label[str(zctrl.value)]:
                    case "NONE":
                        followAction = zynseq.FOLLOW_ACTION_NONE
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
        if self.moving_phrase:
            self.end_moving_phrase()
            return True
        elif type == "S":
            if self.launcher_mode:
                if self.zynseq.phrase < self.zynseq.phrases:
                    self.highlighted_strip.launchers[self.zynseq.phrase].on_clip_short_press()
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

        if swi == 0:
            if t == "S":
                if self.highlighted_strip is not None:
                    self.highlighted_strip.toggle_solo()
                return True
        elif swi == 1:
            if self.moving_phrase:
                self.end_moving_phrase()
                return True
            if t == "S":
                if self.highlighted_strip is not None and not self.back_action():
                    self.highlighted_strip.toggle_mute()
                return True
            elif t == "B":
                self.toggle_launcher_mode()
                return True
        elif swi == 2:
            if t == "S":
                if self.launcher_mode:
                    self.zyngui.show_screen("tempo")
                else:
                    self.zyngui.screens["chain_options"].insert_chain()
                return True
        elif swi == 3:
            return self.switch_select(t)

        return False

    def cuia_v5_zynpot_switch(self, params):
        i = params[0]
        t = params[1].upper()
        if t == 'S':
            if i == 2:
                self.zyngui.screens["chain_options"].insert_chain()
            else:
                self.zyngui.zynswitch_short(i)
            return True
        # Bold knob#2 => chain options
        elif t == 'B' and i == 2:
            self.zyngui.show_screen("chain_options")
            return True
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
                self.chain_strips[-1].nudge_volume(dval)

        # Knob#4 moves chain selection
        elif i == 3:
            if self.moving_phrase:
                if dval < 0:
                    self.arrow_up(-dval)
                elif dval > 0:
                    self.arrow_down(-dval)
            else:
                self.chain_manager.next_chain(dval)

    def arrow_left(self):
        """ Function to handle CUIA ARROW_LEFT
        """
        self.chain_manager.previous_chain()

    def arrow_right(self):
        """ Function to handle CUIA ARROW_RIGHT
        """
        self.chain_manager.next_chain()

    def arrow_up(self, nudge=1):
        """ Function to handle CUIA ARROW_UP
        """
        if self.launcher_mode:
            if self.zynseq.phrase > 0:
                if self.moving_phrase:
                    self.zynseq.swap_phrase(self.zynseq.scene, self.zynseq.phrase, self.zynseq.phrase - nudge)
                    self.build_launchers()
                    self.highlight_launcher()
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
                        self.build_launchers()
                        self.highlight_launcher()
                else:
                    self.select_launcher(self.zynseq.phrase - nudge)
        else:
            if self.highlighted_strip is not None:
                self.highlighted_strip.nudge_volume(nudge)

    def backbutton_short_touch_action(self):
        if not self.back_action():
            self.zyngui.back_screen()

    def select_launcher(self, phrase=None):
        """ Selects the current launcher

        Args:
            phrase: Index of phrase to select (None for current phrase)
        """

        if phrase is None:
            phrase = self.zynseq.phrase
        if phrase < 0:
            phrase = 0
        elif phrase >= self.zynseq.phrases:
            phrase = self.zynseq.phrases - 1
        if phrase == self.zynseq.phrase:
            return
        self.zynseq.select_phrase(phrase)

    def end_moving_phrase(self):
        if zynthian_gui_config.enable_touch_navigation:
            self.show_back_button(False)
        self.moving_phrase = False
        self.strip_drag_start = None
        self.refresh_launchers()

    # CUIA and alt mode management

    def get_alt_mode(self):
        return self.alt_mode

    def cuia_toggle_alt_mode(self, params=None):
        self.alt_mode = not self.alt_mode
        self.zyngui.set_global_alt_mode(self.alt_mode)
        return True

    def cuia_chain_control(self, params=None):
        if self.alt_mode:
            chain_id = 0
        else:
            chain_id = self.chain_manager.active_chain.chain_id
        self.zyngui.chain_control(chain_id)
        return True

    def update_wsleds(self, leds):
        # ALT mode only!
        if not self.alt_mode:
            return

        wsl = self.zyngui.wsleds

        # ALT button
        wsl.set_led(leds[0], wsl.wscolor_active2)

        # CTRL button
        wsl.set_led(leds[15], wsl.wscolor_active2)

# --------------------------------------------------------------------------
