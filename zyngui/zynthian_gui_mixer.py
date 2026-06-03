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
from threading import Timer
from PIL import Image, ImageTk, ImageDraw, ImageFont
from os.path import basename, splitext

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq
from zynlibs.zynaudioplayer import *
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_base import zynthian_gui_base
from zyngui.zynthian_gui_dpm import zynthian_gui_dpm
from zyngine.zynthian_signal_manager import zynsigman

logging.getLogger('PIL').setLevel(logging.WARNING)


# --------------------------------------------------------------
# Zynthian sequence launcher button class
# This provides a UI element that represents a launcher button
# --------------------------------------------------------------

LOOP_INFO_WIDTH = 0.2
DRAG_THRESHOLD = 5
SPEAKER_ICON = "\uf028"
MICROPHONE_ICON = "\uf130"
QUAVER_ICON = "\u266b"
SLIDERS_ICON = "\uf1de"

CHANNEL_CHARS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P'
                 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', 'Γ', 'Δ', 'Λ', 'Π', 'Σ', 'Ω']
                 # 'Θ', 'Ξ', 'Φ', 'Ψ',


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
        self.height = height
        self.width = width
        self.chain = chain
        self.phrase = phrase

        chain_id = self.chain.chain_id
        if chain_id == 0:
            loop_info_width = int(LOOP_INFO_WIDTH * self.width)
        else:
            loop_info_width = 0

        self.x = x + loop_info_width
        self.y = y

        tags = ("launcher", "launcher_show", f"strip_{chain_id}", f"launcher_{chain_id}_{phrase}")
        # Launcher pad (background)
        self.pad = self.canvas.create_rectangle(self.x, self.y, self.x + self.width - 1, self.y + self.height - 1,
                                                width=2,
                                                fill=zynthian_gui_config.color_panel_bg,
                                                tags=(*tags, "launcher_pad"))
        if chain_id == 0:
            line_width = int(0.3 * loop_info_width)
            # Loop indicators
            self.loop1_top = self.canvas.create_rectangle(x, self.y, x + line_width, self.y + self.height // 2,
                                                    width=0,
                                                    fill="#50FF50",
                                                    tags=("launcher",),
                                                    state=tkinter.HIDDEN)
            self.loop1_bottom = self.canvas.create_rectangle(x, self.y + self.height // 2, x + line_width, self.y + self.height,
                                                    width=0,
                                                    fill="#50FF50",
                                                    tags=("launcher",),
                                                    state=tkinter.HIDDEN)
            self.loop1_text = self.canvas.create_text(x, self.y + self.height // 2 - 1,
                                                    anchor=tkinter.NW,
                                                    fill=self.gui_mixer.legend_txt_color,
                                                    font=self.gui_mixer.font_clip_state,
                                                    tags=("launcher",),
                                                    state=tkinter.HIDDEN)
            x += loop_info_width // 2
            self.loop2_top = self.canvas.create_rectangle(x, self.y, x + line_width, self.y + self.height // 2,
                                                    width=0,
                                                    fill="#50FF50",
                                                    tags=("launcher",),
                                                    state=tkinter.HIDDEN)
            self.loop2_bottom = self.canvas.create_rectangle(x, self.y + self.height // 2, x + line_width, self.y + self.height,
                                                    width=0,
                                                    fill="#50FF50",
                                                    tags=("launcher",),
                                                    state=tkinter.HIDDEN)
            self.loop2_text = self.canvas.create_text(x + line_width // 2, self.y + self.height // 2 - 1,
                                                    anchor=tkinter.N,
                                                    fill=self.gui_mixer.legend_txt_color,
                                                    font=self.gui_mixer.font_clip_state,
                                                    tags=("launcher",),
                                                    state=tkinter.HIDDEN)
        # Play state text
        self.play_state = self.canvas.create_text(self.x + self.width - 3,  self.y - 3, text="",
                                                  anchor=tkinter.NE,
                                                  font=self.gui_mixer.font_clip_state,
                                                  tags=(*tags, "launcher_play_state"))
        # Title text
        self.title = self.canvas.create_text(self.x + self.width // 2, self.y + 0.5 * self.height, text="",
                                             anchor=tkinter.CENTER,
                                             font=self.gui_mixer.font_clip_title,
                                             fill=self.gui_mixer.legend_txt_color,
                                             tags=(*tags, "launcher_title"))
        # Play mode image
        self.mode_icon = self.canvas.create_image(self.x + 3, self.y + 2,
                                                  anchor=tkinter.NW,
                                                  tags=(*tags, "launcher_mode_icon"))
        # Play mode text
        self.mode_text = self.canvas.create_text(self.x + 4, self.y - 2,
                                                 anchor=tkinter.NW,
                                                 fill=self.gui_mixer.legend_txt_color,
                                                 font=self.gui_mixer.font_clip_state,
                                                 tags=(*tags, "launcher_mode_text"))
        # Timesig text
        self.timesig = self.canvas.create_text(self.x + 4, self.y + self.height,
                                               anchor=tkinter.SW,
                                               fill=self.gui_mixer.legend_txt_color,
                                               font=self.gui_mixer.font_timebase,
                                               tags=(*tags, "launcher_timesig"))
        # Tempo text
        self.tempo = self.canvas.create_text(self.x + self.width - 1, self.y + self.height,
                                             anchor=tkinter.SE,
                                             fill=self.gui_mixer.legend_txt_color,
                                             justify=tkinter.RIGHT,
                                             font=self.gui_mixer.font_timebase,
                                             tags=(*tags, "launcher_tempo"))

        self.canvas.tag_bind(f"launcher_{chain_id}_{phrase}", '<ButtonRelease-1>', self.on_clip_release)

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

    def get_clippy_file(self):
        try:
            return self.chain.get_clippy_processor().controllers_dict[f"file {self.phrase + 1}"].get_value()
        except:
            return None

    def get_clippy_timesig(self):
        try:
            return self.chain.get_clippy_processor().controllers_dict[f"beats {self.phrase + 1}"].get_value() // 4
        except:
            return None

    def draw(self):
        """ Update the launcher button elements"""

        mode_text = ""
        timesig_text = ""
        tempo_text = ""
        color_mode = self.gui_mixer.legend_txt_color
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
            # If not asigned name => generate default name on-the-fly
            if not name:
                if self.chain.chain_id == 0:
                    # Main chain
                    name = f"{self.phrase + 1}"
                else:
                    # QUESTION: Is MIDI chan same as group? ANSWER: Only until arranger is reinstated. => Understood! ;-)
                    name = f"{CHANNEL_CHARS[self.chain.midi_chan]}{self.phrase + 1}"


            disabled = state_seq["repeat"] == 0
            empty = False

            # Moving phrase
            if self.gui_mixer.moving_phrase and self.phrase == self.gui_mixer.zynseq.phrase:
                if self.phrase == 0:
                    title = f"⇓ {name[:6]}"
                elif self.phrase == self.gui_mixer.zynseq.phrases - 1:
                    title = f"⇑ {name[:6]}"
                else:
                    title = f"⇕ {name[:6]}"
            # Normal draw
            else:
                title = name[:7]

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
                    if self.get_clippy_file():
                        empty = False
                        timesig = self.get_clippy_timesig()
                        if timesig is not None:
                            timesig_text = str(timesig)
                        else:
                            timesig_text = "1"
                    else:
                        empty = True
                        timesig = "1"

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

                # Side Loop Info
                loop_info = self.gui_mixer.zynseq.get_phrase_loop_info_all(self.phrase)
                self.canvas.itemconfig(self.loop1_top, state=tkinter.HIDDEN)
                self.canvas.itemconfig(self.loop1_bottom, state=tkinter.HIDDEN)
                self.canvas.itemconfig(self.loop2_text, state=tkinter.HIDDEN)
                self.canvas.itemconfig(self.loop2_top, state=tkinter.HIDDEN)
                self.canvas.itemconfig(self.loop2_bottom, state=tkinter.HIDDEN)
                self.canvas.itemconfig(self.loop2_text, state=tkinter.HIDDEN)
                if loop_info:
                    for i, linfo in enumerate(reversed(loop_info)):
                        if i == 0:
                            loop_top = self.loop1_top
                            loop_bottom = self.loop1_bottom
                            loop_text = self.loop1_text
                            c1 = c2 = "#5050FF"
                        elif i == 1:
                            loop_top = self.loop2_top
                            loop_bottom = self.loop2_bottom
                            loop_text = self.loop2_text
                            c1 = c2 = "#40C040"
                        else:
                            logging.warning("Loop at level {i} not displayable!")
                        if state_seq["followAction"] == zynseq.FOLLOW_ACTION_NONE:
                            c2 = "#" + "".join(f"{int(int(c1[i:i+2],16)*0.85):02x}" for i in (1,3,5))
                        if linfo[0] == self.phrase:
                            self.canvas.itemconfig(loop_top, state=tkinter.NORMAL, fill=c1)
                            repeat = state_seq["followRepeat"]
                            if repeat:
                                ltext = f"{repeat}"
                            else:
                                ltext = "∞"
                            self.canvas.itemconfig(loop_text, state=tkinter.NORMAL, text=ltext)
                        elif linfo[0] - linfo[1] == self.phrase:
                            self.canvas.itemconfig(loop_bottom, state=tkinter.NORMAL, fill=c2)
                        else:
                            self.canvas.itemconfig(loop_top, state=tkinter.NORMAL, fill=c1)
                            self.canvas.itemconfig(loop_bottom, state=tkinter.NORMAL, fill=c2)

                # Duration in bars) => 255=auto
                try:
                    if state_seq["repeat"] == 255:
                        #mode_text = "a"
                        pass
                    elif state_seq["repeat"] > 0:
                        mode_text = f"{state_seq['repeat']}"
                except:
                    pass

                # Flow info
                match state_seq["followAction"]:
                    case zynseq.FOLLOW_ACTION_NONE:
                        mode_text += "↻"
                    case zynseq.FOLLOW_ACTION_RELATIVE:
                        offset = state_seq["followParam"]
                        if offset < 0:
                            mode_text += "↑"
                        elif offset == 0:
                            mode_text += "↻"
                        elif offset == 1:
                            mode_text += f"↓"
                        elif offset > 1:
                            mode_text += f"↓{offset}"

                # Timesig (Beats per Bar)
                try:
                    if state_seq["bpb"]:
                        timesig_text = f"{state_seq['bpb']}/4"
                except:
                    pass

                # Tempo info
                if "tempo" in state_seq:
                    tempo = state_seq["tempo"]
                    if tempo:
                        tempo_text = f"{tempo:.1f}"

            if disabled:
                color = zynthian_gui_config.PAD_COLOUR_DISABLED
                color_mode = zynthian_gui_config.PAD_COLOUR_STATE_DISABLED
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
                        color_mode = zynthian_gui_config.PAD_COLOUR_STATE_DISABLED
                        color_text = zynthian_gui_config.PAD_COLOUR_STATE_DISABLED
                        color_state = zynthian_gui_config.PAD_COLOUR_STATE_DISABLED
                        state_text = "?"
        except:
            #logging.exception(traceback.format_exc())
            title = ""
            color = zynthian_gui_config.PAD_COLOUR_DISABLED
            color_mode = zynthian_gui_config.PAD_COLOUR_STATE_DISABLED
            color_text = zynthian_gui_config.PAD_COLOUR_STATE_DISABLED
            color_state = zynthian_gui_config.PAD_COLOUR_STATE_DISABLED
            state_text = ""

        self.canvas.itemconfig(self.pad, fill=color)
        if len(title) > 3:
            font_title = self.gui_mixer.font_clip_title_small
        else:
            font_title = self.gui_mixer.font_clip_title
        self.canvas.itemconfig(self.title, text=title, fill=color_text, font=font_title)
        self.canvas.itemconfig(self.play_state, text=state_text, fill=color_state)
        if self.chain.chain_id:
            # Chain sequence launcher
            self.canvas.itemconfig(self.mode_text, text=mode_text, fill=color_text, state=tkinter.NORMAL)
            self.canvas.itemconfig(self.timesig, text=timesig_text, fill=color_text, state=tkinter.NORMAL)
            self.canvas.itemconfig(self.tempo, state=tkinter.HIDDEN)
            self.canvas.itemconfig(self.mode_icon, state=tkinter.HIDDEN)
        else:
            # Phrase launcher
            self.canvas.itemconfig(self.mode_text, text=mode_text, fill=color_mode, state=tkinter.NORMAL)
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

    bg_images = {} # Dict of background images, indexed by (width, length)

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
        self.over_id = None

        self.chain = chain
        if self.chain.chain_id == 0:
            self.chan = 32
        else:
            self.chan = self.chain.midi_chan

        self.button_height = self.gui_mixer.button_height
        self.legend_height = self.gui_mixer.legend_height
        self.balance_height = self.gui_mixer.balance_height
        self.balance_width = (self.width - 2) / 2 # Width of each half of the balance indicator
        self.toggle_y = parent.toggle_y
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
        self.dpm_scale_width = int(self.dpm_width * 0.7)
        self.dpm_length = self.gui_mixer.fader_height
        self.dpm_y0 = self.fader_y

        self.fader_width = self.width - self.dpm_width * 2 - self.dpm_scale_width
        if self.chain.chain_id == 0:
            self.fader_width -= parent.loop_info_width
        self.dpm_b_x0 = x + self.width - self.dpm_width
        self.dpm_scale_x0 = self.dpm_b_x0 - self.dpm_scale_width
        self.dpm_a_x0 = self.dpm_scale_x0 - self.dpm_width

        self.fader_press_event = None
        self.launchers = [] # List of launcher button objects, indexed by phrase

        #Create GUI elements
        id = self.chain.chain_id

        # Block background to hide scrolling launchers, etc.
        self.audio_bg = self.canvas.create_rectangle(x, self.toggle_y, x + self.width, parent.launcher_y, fill=self.gui_mixer.button_bgcol, width=0)
        # Fader background defines height of fader
        self.fader_bg = self.canvas.create_rectangle(x, self.fader_y, x + self.width, self.legend_y, fill=self.gui_mixer.fader_bg_color, width=0, tags=("fader", f"fader_{id}"))
        # Audio mixer elements
        if self.chain.zynmixer_proc:
            # Toggle 1 button
            self.toggle = self.canvas.create_rectangle(x, self.toggle_y, x + self.width, self.mute_y, fill=self.gui_mixer.button_bgcol, width=0,
                                                tags=(f"toggle_{id}",))
            self.toggle_text = self.canvas.create_text(x + self.width / 2, self.toggle_y + self.button_height * 0.5, text="S", fill=self.gui_mixer.button_txcol, font=self.gui_mixer.font,
                                                tags=(f"toggle_{id}",))

            # Mute button
            self.mute = self.canvas.create_rectangle(x, self.mute_y, x + self.width, self.balance_y, fill=self.gui_mixer.button_bgcol, width=0, tags=(f"mute_{id}",))
            self.mute_text = self.canvas.create_text(x + self.width / 2, self.mute_y + self.button_height * 0.5, text="M", fill=self.gui_mixer.button_txcol, font=self.gui_mixer.font, tags=(f"mute_{id}",))

            # Balance indicator
            self.balance_bg = self.canvas.create_rectangle(self.x + 1, self.balance_y, self.x + self.width - 1, self.fader_y, fill=self.gui_mixer.balance_bg_color, width=0, tags=(f"balance_{id}",))
            self.balance_fg = self.canvas.create_rectangle(self.centre_x - 1, self.balance_y, self.centre_x + 1, self.fader_y, fill=self.gui_mixer.balance_fg_color, width=0, tags=(f"balance_{id}",))
            # Fader
            self.fader_overlay = self.canvas.create_rectangle(x, self.fader_y, x + self.fader_width, self.legend_y, fill=self.gui_mixer.fader_color, width=0, tags=("fader", "fader_overlay", f"fader_{id}"))
            self.fader_horizontal = self.canvas.create_rectangle(x, self.fader_y, x + self.width, self.fader_y + self.balance_height, fill=self.gui_mixer.fader_color, width=0, tags=("fader_horizontal",), state=tkinter.HIDDEN)

            # DPM
            if self.chain.chain_id:
                dpm_tags = ("dpm")
            else:
                dpm_tags = ("dpm_0")
            self.dpm_bg = self.canvas.create_rectangle(self.dpm_scale_x0, self.dpm_y0, x + self.width , self.dpm_y0 + self.dpm_length, width=0, fill=self.gui_mixer.fader_bg_color)
            self.dpm_scale = self.canvas.create_image(self.dpm_scale_x0, self.dpm_y0, anchor="nw", image=self.get_bg_img("dpm", self.dpm_width, self.dpm_length))
            if self.chain.chain_id == 0:
                self.dpm_labels = self.canvas.create_image(self.dpm_a_x0, self.dpm_y0, anchor="ne", image=self.get_bg_img("dpm_lbl", parent.loop_info_width, self.dpm_length))
            self.dpm_a = zynthian_gui_dpm(self.canvas, self.dpm_a_x0, self.dpm_y0, self.dpm_width, self.dpm_length, tags=dpm_tags, main=chain.chain_id==0)
            self.dpm_b = zynthian_gui_dpm(self.canvas, self.dpm_b_x0, self.dpm_y0, self.dpm_width, self.dpm_length, tags=dpm_tags, main=chain.chain_id==0)

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
        self.legend_strip_bg = self.canvas.create_rectangle(x, self.gui_mixer.legend_y, x + self.width, self.gui_mixer.legend_y + self.legend_height - 2, width=0, fill=self.gui_mixer.legend_bg_color, tags=tags)
        self.legend_strip_txt = self.canvas.create_text(self.centre_x, self.gui_mixer.legend_y + self.legend_height / 2, fill=self.gui_mixer.legend_txt_color, text="-", tags=(f"legend_strip_{id}",), font=self.gui_mixer.font)
        self.legend_strip_midi_bg = self.canvas.create_rectangle(x, self.gui_mixer.legend_y + self.legend_height - 2, x + self.width, self.gui_mixer.legend_y + self.legend_height, width=0, fill=self.gui_mixer.legend_bg_color, tags=tags)

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
        self.canvas.tag_bind(f"toggle_{id}", "<ButtonRelease-1>", self.on_toggle_release)
        self.canvas.tag_bind(f"legend_strip_{id}", "<ButtonRelease-1>", self.on_strip_release)

        self.draw_control()

    def set_launcher_mode(self, mode):
        try:
            if mode:
                self.canvas.coords(self.dpm_bg, self.dpm_a_x0, 0, self.x + self.width, self.balance_y)
                self.dpm_a.move(self.dpm_a_x0, 0, self.dpm_width, self.balance_y)
                self.dpm_b.move(self.dpm_b_x0, 0, self.dpm_width, self.balance_y)
                self.canvas.itemconfig(self.dpm_scale, state=tkinter.HIDDEN)
                if self.chain.chain_id == 0:
                    self.canvas.itemconfig(self.dpm_labels, state=tkinter.HIDDEN)
                #self.canvas.coords(self.toggle, self.x, self.toggle_y, self.dpm_a_x0, self.mute_y)
                #self.canvas.coords(self.mute, self.x, self.mute_y, self.dpm_a_x0, self.balance_y)
            else:
                self.canvas.coords(self.dpm_bg, self.dpm_a_x0, self.dpm_y0, self.x + self.width, self.dpm_y0 + self.dpm_length)
                self.dpm_a.move(self.dpm_a_x0, self.dpm_y0, self.dpm_width, self.dpm_length)
                self.dpm_b.move(self.dpm_b_x0, self.dpm_y0, self.dpm_width, self.dpm_length)
                self.canvas.itemconfig(self.dpm_scale, state=tkinter.NORMAL)
                if self.chain.chain_id == 0:
                    self.canvas.itemconfig(self.dpm_labels, state=tkinter.NORMAL)
                #self.canvas.coords(self.toggle, self.x, self.toggle_y, self.x + self.width, self.mute_y)
                #self.canvas.coords(self.mute, self.x, self.mute_y, self.x + self.width, self.balance_y)
        except:
            pass # meters not yet created?

    def get_bg_img(self, id, width, height):
        """ Get the tri-colour background image
        Args:
            id: An id for the type of image, e.g. fader
            width: Width in pixels
            height: Height in pixels
        Returns: Background image
        """

        key = (id, width, height)
        if key in self.bg_images:
            return self.bg_images[key]

        c = self.gui_mixer.fader_bg_color
        #c = "#222222"
        r,g,b = tuple(int(c[i:i+2], 16) for i in (1, 3, 5))
        img = Image.new("RGB", (width, height), (r, g, b))
        pixels = img.load()

        def db_to_norm(db):
            db = max(-50, min(0, db))
            return (db + 50) / 50

        c_low = (0, 200, 0)
        c_zero = (200, 200, 200)
        c_mid = (200, 200, 0)
        c_high = (240, 0, 0)
        font = ImageFont.truetype("DejaVuSans.ttf", int(width * 0.6))
        for db in (-40, -30, -20, -16, -13, -10, -7, -4, -1):
            y = min(height - 1, height - int(db_to_norm(db) * height))
            c = c_zero if db == -10 else c_high if db >=-3 else c_mid if db >= -10 else c_low
            if id == "dpm":
                if db != -10:
                    for x in range(width):
                        pixels[x, y] = c
            elif id == "dpm_lbl":
                fill = f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"
                draw = ImageDraw.Draw(img)
                if db == -10:
                    draw.text((width, y), "0", fill=fill, font=font, anchor="rm")
                else:
                    draw.text((width - 1, y), f"{db+10:+}", fill=fill, font=font, anchor="rm")

        self.bg_images[key] = ImageTk.PhotoImage(img)
        return self.bg_images[key]

    def draw_dpm(self):
        """ Function to draw the DPM level meter for a mixer strip
        """

        dpm = self.chain.zynmixer_proc.zynmixer.dpm[self.chain.zynmixer_proc.mixer_chan]
        self.dpm_a.refresh(dpm.a, dpm.a_hold, dpm.mono)
        self.dpm_b.refresh(dpm.b, dpm.b_hold, dpm.mono)
        if self.chain.chain_id == 0 and (dpm.a_hold >= 0 or dpm.b_hold >= 0):
            self.canvas.itemconfig(self.mute_text, fill="#FF0000")
            if self.over_id is not None:
                self.canvas.after_cancel(self.over_id)
            self.over_id = self.canvas.after(4000, lambda: self.canvas.itemconfig(self.mute_text, fill=self.gui_mixer.button_txcol))


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

    def draw_toggle(self):
        txcolor = self.gui_mixer.button_txcol
        font = self.gui_mixer.font
        text = self.chain.zynmixer_proc.controllers_dict[zynthian_gui_config.mixer_toggle].name
        if zynthian_gui_config.mixer_toggle == "solo" and self.chain.zynmixer_proc.eng_code == "MR" and self.chain.chain_id == 0:
            # Main mixbus so use the global solo state
            toggle_val = self.state_manager.zynmixer_bus.get_global_solo() > 0
        else:
            toggle_val = self.chain.zynmixer_proc.controllers_dict[zynthian_gui_config.mixer_toggle].value
        if toggle_val:
            bgcolor = self.gui_mixer.toggle_color
        else:
            bgcolor = self.gui_mixer.button_bgcol

        self.canvas.itemconfig(self.toggle, fill=bgcolor)
        self.canvas.itemconfig(self.toggle_text, text=text, font=font, fill=txcolor)

    def draw_mute(self):
        txcolor = self.gui_mixer.button_txcol
        font = self.gui_mixer.font_icons
        if self.chain.zynmixer_proc.controllers_dict["mute"].value:
            bgcolor = self.gui_mixer.mute_color
            text = "\uf32f"
        else:
            bgcolor = self.gui_mixer.button_bgcol
            text = SPEAKER_ICON

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
                strip_txt = "Main"
            else:
                if self.chain.is_generator():
                    if self.chain.midi_chan is not None and 15 < self.chain.midi_chan < 32:
                        strip_txt = f"{SPEAKER_ICON} {CHANNEL_CHARS[self.chain.midi_chan]}"
                    else:
                        strip_txt = SPEAKER_ICON
                elif self.chain.is_midi():
                    if self.chain.audio_thru:
                        strip_txt = f"{MICROPHONE_ICON}{QUAVER_ICON}"   # Add microphone icon for MIDI+Audio chains
                    else:
                        strip_txt = f"{QUAVER_ICON} "
                    if 0 <= self.chain.midi_chan < 16:
                        strip_txt += f"{self.chain.midi_chan + 1}"
                    elif self.chain.midi_chan == 0xffff:
                        strip_txt += f"All"
                    else:
                        strip_txt += f"Err"
                elif self.chain.is_audio():
                    if self.chain.zynmixer_proc.eng_code == "MI":
                        strip_txt = MICROPHONE_ICON
                    else:
                        strip_txt = SLIDERS_ICON
                        try:
                            strip_txt = f"{SLIDERS_ICON} {int(self.chain.title.split(' ')[-1])}"
                        except:
                            strip_txt = SLIDERS_ICON
                else:
                    strip_txt = ""
                    # procs = self.chain.get_processor_count() - 1
            self.canvas.itemconfig(self.legend_strip_txt, text=strip_txt, font=self.gui_mixer.font)
            self.draw_fader_text()

        if self.chain.zynmixer_proc:
            if control in [None, 'level']:
                self.draw_level()

            if control in [None, zynthian_gui_config.mixer_toggle]:
                self.draw_toggle()

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

    def set_toggle(self, value):
        """ Function to set toggle 1 control
        value: Togle 1 control value (True/False)
        """
        if self.chain.zynmixer_proc:
            self.chain.zynmixer_proc.controllers_dict[zynthian_gui_config.mixer_toggle].set_value(value)

    def toggle_mute(self):
        """ Function to toggle mute
        """
        if self.chain.zynmixer_proc:
            self.set_mute(int(not self.chain.zynmixer_proc.controllers_dict['mute'].value))

    def toggle_toggle(self):
        """ Function to toggle the toggle 1 control
        """
        if self.chain.zynmixer_proc:
            self.set_toggle(int(not self.chain.zynmixer_proc.controllers_dict[zynthian_gui_config.mixer_toggle].value))

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

    def on_toggle_release(self, event):
        """ Function to handle toggle 1 button release
        event: Mouse event
        """
        self.toggle_toggle()


# ------------------------------------------------------------------------------
# Zynthian Mixer GUI Class
# ------------------------------------------------------------------------------

class zynthian_gui_mixer(zynthian_gui_base):

    def __init__(self):
        super().__init__()

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

        self.pated = None
        self.clipboard = None
        self.wsleds_i_clipboard = None

        self.update_layout()
        self.tts_title = "Mixer"

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

        self.strip_width = int(self.width / (self.visible_chains + 0.2))
        self.loop_info_width = int(LOOP_INFO_WIDTH * self.strip_width)
        self.button_height = int(self.height * 0.07)
        self.legend_height = int(self.height * 0.08)
        self.balance_height = int(self.height * 0.03)
        self.toggle_y = 0
        self.mute_y = self.toggle_y + self.button_height
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
        self.mute_color = "#CC0000"
        self.toggle_color = "#D0D000"
        self.mono_color = "#B0B0B0"
        font_size = min(int(0.5 * self.legend_height), int(0.25 * self.width))
        self.font = (zynthian_gui_config.font_family, font_size)
        self.font_fader = (zynthian_gui_config.font_family, int(0.9 * font_size))
        self.font_clip_state = (zynthian_gui_config.font_family, int(0.6 * font_size))
        self.font_clip_title = (zynthian_gui_config.font_family, int(0.8 * font_size))
        self.font_clip_title_small = ("sans-serif", int(0.65 * font_size))
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
        self.right_canvas.configure(width= int(self.strip_width * self.chain_manager.get_pinned_count() + self.loop_info_width))
        self.scrollable_strips = len(self.chain_manager.chains) - self.chain_manager.get_pinned_count()
        div = self.chain_manager.get_pinned_pos()
        x0 = 0
        canvas = self.left_canvas
        for idx, chain in enumerate(list(self.chain_manager.chains.values())):
            # Pinned chains goes to right canvas
            if idx == div:
                x0 = 0
                canvas = self.right_canvas
            # Main strip includes the loop_info area
            if chain.chain_id == 0:
                width = self.strip_width + self.loop_info_width
            else:
                width = self.strip_width
            # Create the strip objects
            strip = zynthian_gui_mixer_strip(self, canvas, x0, width, self.height, chain)
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
        self.right_canvas.tag_lower("launcher")
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
            zynsigman.register(zynsigman.S_MIXER, zynsigman.SS_ZYNMIXER_SET_VALUE, self.update_control)
            zynsigman.register_queued(zynsigman.S_MIDI, zynsigman.SS_MIDI_CC, self.midi_cc_cb)
            zynsigman.register_queued(zynsigman.S_MIDI, zynsigman.SS_MIDI_PC, self.midi_pc_cb)
            zynsigman.register_queued(zynsigman.S_STATE_MAN, zynsigman.SS_LOAD_ZS3, self.load_zs3_cb)
            zynsigman.register_queued(zynsigman.S_STATE_MAN, zynsigman.SS_ALL_NOTES_OFF, self.all_notes_off_cb)
            zynsigman.register_queued(zynsigman.S_CHAIN_MAN, zynsigman.SS_SET_ACTIVE_CHAIN, self.update_active_chain)
            zynsigman.register_queued(zynsigman.S_CHAIN_MAN, zynsigman.SS_RENAME_CHAIN, self.cb_rename_chain)
            zynsigman.register_queued(zynsigman.S_AUDIO_RECORDER, zynsigman.SS_AUDIO_RECORDER_STATE, self.update_control_rec)
            zynsigman.register_queued(zynsigman.S_AUDIO_RECORDER, zynsigman.SS_AUDIO_RECORDER_ARM, self.audio_recorder_arm_cb)
            zynsigman.register_queued(zynsigman.S_AUDIO_PLAYER, zynsigman.SS_AUDIO_PLAYER_STATE, self.update_control_play)
            zynsigman.register_queued(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_SELECT_PHRASE, self.highlight_launcher)
            zynsigman.register_queued(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_TEMPO, self.set_tempo)
            zynsigman.register_queued(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_TIMESIG, self.set_bpb)
            zynsigman.register_queued(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_PLAY_STATE, self.launcher_play_state_cb)
            zynsigman.register_queued(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_STATE, self.refresh_launchers)

        # Setup pattern editor and clipboard functionality
        self.pated = self.zyngui.screens["pattern_editor"]
        self.clipboard = self.pated.clipboard
        self.wsleds_i_clipboard = self.pated.wsleds_i_clipboard
        self.switch_i_clipboard = self.pated.switch_i_clipboard

        return True

    def hide(self):
        """ Function to handle hiding display
        """
        if self.shown:
            if not self.zyngui.osc_clients:
                self.zyngui.state_manager.zynmixer_chan.enable_dpm(False)
                self.zyngui.state_manager.zynmixer_bus.enable_dpm(False)
            zynsigman.unregister(zynsigman.S_MIXER, zynsigman.SS_ZYNMIXER_SET_VALUE, self.update_control)
            zynsigman.unregister(zynsigman.S_MIDI, zynsigman.SS_MIDI_CC, self.midi_cc_cb)
            zynsigman.unregister(zynsigman.S_MIDI, zynsigman.SS_MIDI_PC, self.midi_pc_cb)
            zynsigman.unregister(zynsigman.S_STATE_MAN, zynsigman.SS_LOAD_ZS3, self.load_zs3_cb)
            zynsigman.unregister(zynsigman.S_STATE_MAN, zynsigman.SS_ALL_NOTES_OFF, self.all_notes_off_cb)
            zynsigman.unregister(zynsigman.S_CHAIN_MAN, zynsigman.SS_SET_ACTIVE_CHAIN, self.update_active_chain)
            zynsigman.unregister(zynsigman.S_CHAIN_MAN, zynsigman.SS_RENAME_CHAIN, self.cb_rename_chain)
            zynsigman.unregister(zynsigman.S_AUDIO_RECORDER, zynsigman.SS_AUDIO_RECORDER_STATE, self.update_control_rec)
            zynsigman.unregister(zynsigman.S_AUDIO_RECORDER, zynsigman.SS_AUDIO_RECORDER_ARM, self.audio_recorder_arm_cb)
            zynsigman.unregister(zynsigman.S_AUDIO_PLAYER, zynsigman.SS_AUDIO_PLAYER_STATE, self.update_control_play)
            zynsigman.unregister(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_SELECT_PHRASE, self.highlight_launcher)
            zynsigman.unregister(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_TEMPO, self.set_tempo)
            zynsigman.unregister(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_TIMESIG, self.set_bpb)
            zynsigman.unregister(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_PLAY_STATE, self.launcher_play_state_cb)
            zynsigman.unregister(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_STATE, self.refresh_launchers)
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
        if symbol == zynthian_gui_config.mixer_toggle and strip.chain.chain_id == 0:
            for s in self.chain_strips:
                self.pending_refresh_queue.add((s, symbol))
        else:
            self.pending_refresh_queue.add((strip, symbol))
        if symbol == "level":
            #value = strip.zctrls["level"].value
            if value > 0:
                level_db = f"{20 * log10(value):.2f}dB"
            else:
                level_db = "-∞"
            self.set_title(f"Volume: {level_db} ({strip.chain.get_description(1)})", None, None, 1)
            if self.zyngui.tts:
                self.zyngui.tts.announce(f"Fader: {level_db}")
        elif symbol == "balance":
            bal = f"{int(value * 100):+}%"
            #strip.gui_mixer.set_title(f"Balance: {int(value * 100)}% ({strip.chain.get_description(1)})", None, None, 1)
            strip.gui_mixer.set_title(f"Balance: {bal} ({strip.chain.get_name()})", None, None, 1)
            if self.zyngui.tts:
                self.zyngui.tts.announce(f"Balance: {bal}")

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

    def load_zs3_cb(self, zs3_id):
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

    def topbar_short_touch_action(self):
        self.toggle_launcher_mode()

    def item_menu(self):
        if self.launcher_mode and self.zynseq.phrase < self.zynseq.phrases:
            # Launcher Options
            self.phrase_menu()
        else:
            self.zyngui.chain_control()
            self.zyngui.screens['chain_control'].select_subscreen("chain_options", show_chain=True)

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

        # Highlight the active MIDI chain
        try:
            active_midi_index = self.chain_manager.get_chain_index(self.chain_manager.active_midi_chain.chain_id)
            active_midi_strip = self.chain_strips[active_midi_index]
            active_midi_strip.canvas.itemconfig(active_midi_strip.legend_strip_midi_bg, fill=self.legend_bg_color_hl)
        except:
            pass

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
            self.left_canvas.itemconfig("launcher_show", state=tkinter.NORMAL)
            self.right_canvas.itemconfig("launcher_show", state=tkinter.NORMAL)
            self.highlight_launcher()
            if self.shown:
                self.zyngui.current_screen = "launcher"
            self.tts_title = "Launcher"
        else:
            self.left_canvas.itemconfig("fader", state=tkinter.NORMAL)
            self.right_canvas.itemconfig("fader", state=tkinter.NORMAL)
            self.left_canvas.itemconfig("fader_horizontal", state=tkinter.HIDDEN)
            self.right_canvas.itemconfig("fader_horizontal", state=tkinter.HIDDEN)
            self.left_canvas.itemconfig("launcher_show", state=tkinter.HIDDEN)
            self.right_canvas.itemconfig("launcher_show", state=tkinter.HIDDEN)
            if self.shown:
                self.zyngui.current_screen = "mixer"
            self.tts_title = "Mixer"
        zynsigman.send(zynsigman.S_GUI, zynsigman.SS_GUI_LAUNCHER_MODE, mode=launcher_mode)
        if self.shown and self.zyngui.tts:
            self.zyngui.tts.announce(f"View: {self.tts_title}")

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
        follow_phrase = phrase + info["followParam"]
        title = f"Phrase options"
        if name:
            title += f": {name}"
        #options["> Phrase Options"] = None
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
                options[f"Automate => NONE"] = 0
            elif follow_action == zynseq.FOLLOW_ACTION_RELATIVE:
                offset, follow_name = self.get_follow_info(follow_phrase)
                flags = info["playFlags"]
                options[f"Automate => {follow_name}"] = offset
                if follow_phrase < phrase:
                    loop_count = info["followRepeat"]
                    if loop_count:
                        options[f"  Loop count ({loop_count})"] = loop_count
                    else:
                        options[f"  Loop count (∞)"] = loop_count
                loop_info = self.zynseq.get_phrase_loop_info()
                if loop_info:
                    if loop_info[2] > 0:
                        if flags:
                            skip_loops = ",".join(str(i + 1) for i in range(loop_info[2]) if not (flags >> i) & 1)
                        else:
                            skip_loops = "ALL"
                        if skip_loops == "":
                            skip_loops = "NONE"
                    else:
                        if flags & 1:
                            skip_loops = "NONE"
                        else:
                            skip_loops = "ALL"
                    options[f"  Loops to play ({skip_loops})"] = flags
            if 'tempo' not in info or info['tempo'] == 0.0:
                options[f"Tempo (NONE)"] = False
            else:
                options[f"Tempo ({info['tempo']:.1f})"] = info['tempo']
                options["Remove tempo"] = self.zynseq.phrase
            if "bpb" not in info or not info["bpb"]:
                options[f"Beats per bar (NONE)"] = 0
            else:
                options[f"Beats per bar ({info['bpb']})"] = info["bpb"]
        if name:
            options[f"Rename ({name})"] = name
        else:
            options[f"Rename"] = ""
        options["> EDIT"] = None
        options["Insert phrase"] = phrase
        options["Clone phrase"] = phrase
        if self.zynseq.phrases > 1:
            options["Move phrase"] = phrase
            options["Delete phrase"] = phrase

        self.zyngui.screens['option'].config(title, options, self.phrase_menu_cb, close_on_select=False)
        self.zyngui.show_screen('option')

    def get_phrase_title(self, phrase):
        title = self.zynseq.state["scenes"][self.zynseq.scene]["phrases"][phrase]["name"]
        if not title:
            title = chr(ord('A') + phrase)
        return title

    def get_follow_info(self, phrase):
        """ Get the offset and text representing the follow action
        Args:
            phrase: Index of phrase
        Returns: Tuple (offset, title)
        """

        offset = phrase - self.zynseq.phrase
        match offset:
            case 0:
                title = "NONE"
            case -1:
                title = f"{self.get_phrase_title(phrase)} (PREV)"
            case 1:
                title = f"{self.get_phrase_title(phrase)} (NEXT)"
            case _:
                title = f"{self.get_phrase_title(phrase)} ({offset:+})"
                if offset < 0:
                    title = "LOOP from " + title
                elif offset > 1:
                    title = "JUMP to " + title

        return (offset, title)

    def phrase_menu_cb(self, option, params):
        option_screen = self.zyngui.screens["option"]
        if option.startswith("Rename"):
            self.zyngui.show_keyboard(self.rename_phrase, params, 8)
        elif option.startswith("Append phrase"):
            self.zynseq.insert_phrase(self.zynseq.scene, self.zynseq.phrases)
            self.build_launchers()
            self.zyngui.show_screen("launcher")
        elif option.startswith("Insert phrase"):
            self.zynseq.insert_phrase(self.zynseq.scene, params)
            self.build_launchers()
            self.zyngui.show_screen("launcher")
        elif option.startswith("Clone phrase"):
            self.zynseq.duplicate_phrase(self.zynseq.scene, params)
            self.zynseq.phrase += 1
            self.build_launchers()
            self.moving_phrase = True
            self.zyngui.show_screen("launcher")
        elif option.startswith("Delete phrase"):
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
        elif option.startswith("Automate"):
            ticks = []
            labels = []
            for phrase in range(self.zynseq.phrases):
                offset, title = self.get_follow_info(phrase)
                ticks.append(offset)
                labels.append(title)
            option_screen.enable_param_editor(option_screen, "automate", {
                "name": "Automate",
                "labels": labels,
                "ticks": ticks,
                "value": params
            }, assert_cb=self.cb_assert_param_editor)
        elif option.startswith("  Loops to play"):
            val = params
            loop_info = self.zynseq.get_phrase_loop_info()
            options = {}
            if loop_info:
                if loop_info[2] > 0:
                    for i in range(loop_info[2]):
                        if val & 1:
                            options[f"\u2610 {i + 1}"] = (i, params, True)
                        else:
                            options[f"\u2612 {i + 1}"] = (i, params, False)
                        val >>= 1
                elif loop_info[2] == 0:
                    if val & 1:
                        options[f"\u2612 Skip Always"] = (0, params, True)
                    else:
                        options[f"\u2610 Skip Always"] = (0, params, False)
            if options:
                self.zyngui.screens['option'].config("Loops to play", options, self.play_flag_cb, close_on_select=False)
                self.zyngui.show_screen('option')
        elif option.startswith("  Loop count"):
            ticks = [0]
            labels = ["∞"]
            for i in range(2, 33):
                ticks.append(i)
                labels.append(f"{i}")
            option_screen.enable_param_editor(option_screen, "loop_count", {
                "name": "Loop count",
                "ticks": ticks,
                "labels": labels,
                "value": params
            }, assert_cb=self.cb_assert_param_editor)

    def play_flag_cb(self, option, params):
        if params[2]:
            # Reset flag
            flags = params[1] & ~(1 << params[0])
        else:
            # Set flag
            flags = params[1] | (1 << params[0])
        self.zynseq.set_sequence_param(self.zynseq.scene, self.zynseq.phrase, zynseq.PHRASE_CHANNEL, "playFlags", flags)
        self.phrase_menu_cb("  Loops to play", flags)

    def remove_phrase(self, phrase):
        self.zynseq.remove_phrase(self.zynseq.scene, phrase)
        self.build_launchers()
        self.zyngui.show_screen("launcher")

    def drag_launcher(self, dy):
        logging.warning(dy)

    def edit_pattern(self):
        self.pated.refresh_sequence_info()
        self.pated.load_pattern(self.zynseq.libseq.getPattern(self.zynseq.scene, self.zynseq.phrase, self.zynseq.chan, 0, 0))
        #pated.enable_sequence()
        self.zyngui.show_screen("pattern_editor")
        return True

    def edit_clip(self):
        if self.highlighted_strip.chain.chain_id == 0:
            self.item_menu()
            return True
        chain = self.highlighted_strip.chain
        if type(chain.midi_chan) is int and chain.midi_chan < zynseq.PHRASE_CHANNEL:
            if chain.midi_chan > 15:
                cl_proc = chain.get_processors()[0]
                chain.set_current_processor(cl_proc)
                cl_proc.engine.set_phrase(cl_proc, self.zynseq.phrase)
                self.zyngui.chain_control(chain.chain_id)
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
                    # Warp clips in this phrase to match tempo ...
                    self.zyngui.state_manager.start_busy("clippy_rewarp_phrase", "Re-warping audio clips...")
                    self.chain_manager.zyngines["CL"].rewarp_phrase(phrase)
                    self.zyngui.state_manager.end_busy("clippy_rewarp_phrase")
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
            case "automate":
                if zctrl.value == 0:
                    followAction = zynseq.FOLLOW_ACTION_NONE
                    followParam = 0
                else:
                    followAction = zynseq.FOLLOW_ACTION_RELATIVE
                    followParam = zctrl.value
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, chan, "followAction", followAction)
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, chan, "followParam", followParam)
                if followParam < 0:
                    # Set (unset) loop contents to automate NEXT
                    for p in range(phrase + followParam, phrase):
                        if self.zynseq.state["scenes"][self.zynseq.scene]["phrases"][p]["followAction"] == zynseq.FOLLOW_ACTION_NONE:
                            self.zynseq.set_sequence_param(self.zynseq.scene, p, zynseq.PHRASE_CHANNEL, "followAction", zynseq.FOLLOW_ACTION_RELATIVE)
                            self.zynseq.set_sequence_param(self.zynseq.scene, p, zynseq.PHRASE_CHANNEL, "followParam", 1)
            case "loop_count":
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, chan, "followRepeat", zctrl.value)

    # --------------------------------------------------------------------------
    # Physical UI Control Management: Pots & switches
    # --------------------------------------------------------------------------

    def get_selected_pattern(self):
        if self.zynseq.phrase < self.zynseq.phrases and self.highlighted_strip\
           and self.highlighted_strip.chain.chain_id > 0\
           and type(self.highlighted_strip.chain.midi_chan) is int\
           and self.highlighted_strip.chain.midi_chan < 16:
            return self.zynseq.libseq.getPattern(self.zynseq.scene, self.zynseq.phrase, self.zynseq.chan, 0, 0)
        return None

    def switch_select(self, type='S'):
        """ Function to handle SELECT button press
        type: Button press duration ["S"=Short, "B"=Bold, "L"=Long]

        returns True if event is managed, False if it's not
        """

        if super().switch_select(type):
            return True
        elif type == "S":
            if self.moving_phrase:
                self.end_moving_phrase()
                return True
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
        else:
            self.toggle_launcher_mode()
            return True

    def switch(self, swi, t):
        """ Function to handle switches press
        swi: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
        t: Press type ["S"=Short, "B"=Bold, "L"=Long]

        returns True if action fully handled or False if parent action should be triggered
        """

        match swi:
            case 0:
                if t == "S":
                    if self.highlighted_strip is not None:
                        self.highlighted_strip.toggle_toggle()
                    return True
                elif t == "B":
                    self.zyngui.show_screen("chain_manager")
                    return True
            case 1:
                if t == "B":
                    self.zyngui.show_screen("main_menu")
                    return True
            case 2:
                if t == "S":
                    if self.highlighted_strip is not None:
                        self.highlighted_strip.toggle_mute()
                    return True
                elif t == "B":
                    if self.launcher_mode:
                        self.zyngui.show_screen("tempo")
                        return True
            case 3:
                return self.switch_select(t)

        # ALT mode => Use F1-F4 as copy/paste buttons
        if self.launcher_mode and self.alt_mode\
           and self.switch_i_clipboard and swi in self.switch_i_clipboard:
            # Currently only pattern clips! => TODO Extend to audio clips!
            pattern = self.get_selected_pattern()
            if pattern :
                index = self.switch_i_clipboard.index(swi)
                if t == "S":
                    self.pated.paste_pattern(index, pattern)
                    self.zynseq.refresh_state()
                    self.refresh_launchers()
                    return True
                elif t == "B":
                    src_info = [self.zynseq.phrase, self.highlighted_strip.chan, pattern]
                    self.pated.copy_pattern(index, src_info)
                    return True

        return False

    def cuia_v5_zynpot_switch(self, params):
        i = params[0]
        t = params[1].upper()
        match i:
            case 0:
                if t == 'S':
                    if self.highlighted_strip is not None:
                        self.highlighted_strip.toggle_toggle()
                    return True
                elif t =='B':
                    self.zyngui.chain_control()
                    self.zyngui.screens["chain_control"].subscreen.select_mixer_processor(1)
                    return True
            case 1:
                if t == 'S':
                    if self.highlighted_strip is not None:
                        self.highlighted_strip.toggle_mute()
                    return True
            case 2:
                if t == 'S':
                    self.zyngui.cuia_add_chain()
                    return True
            case 3:
                self.switch_select(t)
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

        # Launcher's vertical cursor move (across phrases)
        elif self.launcher_mode and i == zynthian_gui_config.layout["ctrl_order"][2]:
            if dval < 0:
                self.arrow_up(-dval)
            else:
                self.arrow_down(-dval)
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
            self.chain_strips[-1].nudge_volume(dval)

        # Knob#4 moves chain selection
        elif i == 3:
            if self.launcher_mode and self.moving_phrase:
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

        if super().arrow_up():
            return
        if self.launcher_mode:
            if self.zynseq.phrase > 0:
                if self.moving_phrase:
                    self.zynseq.nudge_phrase(self.zynseq.scene, self.zynseq.phrase, False)
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

        if super().arrow_down():
            return
        if self.launcher_mode:
            if self.zynseq.phrase < self.zynseq.phrases:
                if self.moving_phrase:
                    if self.zynseq.phrase < self.zynseq.phrases - 1:
                        self.zynseq.nudge_phrase(self.zynseq.scene, self.zynseq.phrase, True)
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

        # Copy/paste buttons => Only available for pattern clips
        if self.launcher_mode and self.wsleds_i_clipboard:
            pattern = self.get_selected_pattern()
            if pattern:
                for i, wsli in enumerate(self.wsleds_i_clipboard):
                    if self.clipboard[i] is not None:
                        if self.clipboard[i][2] == pattern:
                            wsl.blink(leds[wsli], wsl.wscolor_red)
                        else:
                            wsl.blink(leds[wsli], wsl.wscolor_active2)
                    else:
                        wsl.set_led(leds[wsli], wsl.wscolor_active2)

    def tts_info(self, params=None):
        if not self.zyngui.tts:
            return
        self.zyngui.tts.announce(f"View: {self.tts_title}", replace="True", interrupt=True)
        chain = self.chain_manager.active_chain
        if chain:
            if chain.chain_id:
                idx = self.chain_manager.get_chain_index(chain.chain_id) + 1
                self.zyngui.tts.announce(f"Chain {idx}.", False, False, False)
            else:
                self.zyngui.tts.announce(f"Main chain.", False, False, False)
            if self.launcher_mode:
                self.zyngui.tts.announce(f"Phrase: {self.zynseq.phrase + 1}.", False, False, False)
            self.zyngui.tts.announce(f"Title: {chain.get_title()}.", False, False, False)
            if chain.is_midi():
                if chain.midi_chan < 16:
                    self.zyngui.tts.announce(f"MIDI channel: {chain.midi_chan + 1}", False, False, False)
                else:
                    self.zyngui.tts.announce(f"MIDI channel: ALL", False, False, False)
            if chain.is_synth():
                self.zyngui.tts.announce("Synth chain.", False, False, False)
            elif chain.is_generator():
                self.zyngui.tts.announce("Generator chain.", False, False, False)
            elif chain.is_special():
                self.zyngui.tts.announce("Special chain.", False, False, False)
            elif chain.is_mixbus():
                self.zyngui.tts.announce("Mixbus chain.", False, False, False)
            elif chain.is_audio():
                self.zyngui.tts.announce("Audio chain.", False, False, False)

# --------------------------------------------------------------------------
