# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Widget Class for audio file selectors
#
# Copyright (C) 2015-2026 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <riban@zynthian.org>
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

import os

import logging
import tkinter
import soundfile
import traceback
from math import modf, pow
from threading import Thread
from os.path import basename

import numpy as np
from OpenGL.GL import *
from OpenGL.arrays import vbo
from pyopengltk import OpenGLFrame

# Zynthian specific modules
from zynlibs.zynseq import zynseq
from zyngine.zynthian_signal_manager import zynsigman
from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base


def hexcolor_to_opengl(hex_str):
    """Converts '#RRGGBB' string into an OpenGL list [R, G, B] between 0.0 and 1.0"""
    # Remove the '#' character if present
    hex_str = hex_str.lstrip('#')

    # Slice the string into pairs and convert to integers, then divide by 255
    r = int(hex_str[0:2], 16) / 255.0
    g = int(hex_str[2:4], 16) / 255.0
    b = int(hex_str[4:6], 16) / 255.0

    return [r, g, b]


class WaveformCanvas(OpenGLFrame):

    def __init__(self, *args, **kwargs):
        self.channels = 0
        self.n_vertex = 0
        self.positions = None
        self.colors = None
        self.vbo_positions = None
        self.vbo_colors = None
        self.touched = False

        self.bg_color = hexcolor_to_opengl(zynthian_gui_config.color_bg)
        self.waveform_color1 = hexcolor_to_opengl(zynthian_gui_config.color_variant(zynthian_gui_config.color_hl, -60))
        self.waveform_color2 = hexcolor_to_opengl(zynthian_gui_config.color_hl)
        self.playcur_color = hexcolor_to_opengl(zynthian_gui_config.color_on)
        self.bg_crop_color = hexcolor_to_opengl(zynthian_gui_config.color_variant(zynthian_gui_config.color_panel_bg, 25))
        #self.bmarker_color = hexcolor_to_opengl(zynthian_gui_config.color_hl)
        self.bmarker_color = hexcolor_to_opengl(zynthian_gui_config.color_tx)
        self.axis_color = hexcolor_to_opengl(zynthian_gui_config.color_variant(zynthian_gui_config.color_tx, -80))

        super().__init__(*args, **kwargs)

    def initgl(self):
        """Configures the native fixed-function GPU state."""
        glClearColor(*self.bg_color, 1.0)

        # Enable needed features
        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_COLOR_ARRAY)

        # Enable native depth hardware sorting
        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LESS)

        # Turn on hardware line smoothing (anti-aliasing)
        #glEnable(GL_LINE_SMOOTH)
        #glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)

        # Enable blending (Required for line smoothing transparency blending)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def init_vbo(self, nchans):
        self.width = self.winfo_width()
        self.height = self.winfo_height()
        if nchans == 0:
            return
        # Num Vertex = lines (axis + waveform + markers) + 2 x crop rects + 1 x cursor rect
        nv = 2 * (nchans + nchans * self.width + self.width // 16) + 8 + 4
        if self.positions is None or nchans != self.channels or nv != self.n_vertex:
            self.channels = nchans
            self.n_vertex = nv
            self.n_vertex_waveform = 2 * self.channels * self.width
            self.n_vertex_markers = 2 * self.width // 16
            #logging.debug(f"INITIALIZING VERTEX ARRAY => {self.n_vertex}")

            # Create pure Python NumPy arrays for Positions [X, Y, Z] => initialized to 0.0
            self.positions = np.zeros((self.n_vertex, 3), dtype=np.float32)
            # Create NumPy array for Colors [R, G, B] => Initialized to black
            self.colors = np.zeros((self.n_vertex, 3), dtype=np.float32)

            # Axis for each channel...
            i0 = 0
            i1 = self.channels * 2
            y_coords = []
            yaxix = -1.0 + 1.0 / self.channels
            for ch in range(self.channels):
                y_coords.append(yaxix)
                yaxix += 2.0 / self.channels
            logging.debug(f"AXIS Y POS => {y_coords}")
            self.positions[i0:i1:2, 0] = -1
            self.positions[i0+1:i1:2, 0] = 1
            self.positions[i0:i1, 1] = np.repeat(y_coords, 2)
            self.positions[i0:i1, 2] = 0.5
            self.colors[i0:i1] = self.waveform_color2    #self.axis_color

            # Waveform x coords => Evenly space X across the screen (-1.0 to 1.0) and repeat each point twice per channel
            i0 = i1
            i1 += self.n_vertex_waveform
            x_coords = np.linspace(-1.0, 1.0, self.width, dtype=np.float32)
            self.positions[i0:i1, 0] = np.repeat(x_coords, 2 * self.channels)
            self.colors[i0:i1:2] = self.waveform_color1
            self.colors[i0+1:i1:2] = self.waveform_color2

            # Markers, crop rectangle & cursor colors
            i0 = i1
            i1 += self.n_vertex_markers
            self.colors[i0:i1] = self.bmarker_color
            self.colors[-12:-4] = self.bg_crop_color
            self.colors[-4:] = self.playcur_color

            # Instantiate your VBOs inside the valid graphic device bounds
            self.vbo_positions = vbo.VBO(self.positions, usage='GL_DYNAMIC_DRAW')
            self.vbo_colors = vbo.VBO(self.colors, usage='GL_DYNAMIC_DRAW')

    def set_wave_data(self, ydata):
        try:
            i0 = self.channels * 2
            i1 = i0 + self.n_vertex_waveform
            self.positions[i0:i1, 1] = (2 * np.array(ydata, dtype=np.float32) / self.height) - 1.0
            self.touched = True
            #np.set_printoptions(threshold=100000)
            #logging.debug(f"X POS => {self.positions[:, 0]}")
            #logging.debug(f"Y POS => {self.positions[:, 1]}")
        except Exception as e:
            logging.error(f"Can't set wave data ... => {e}")

    def set_beat_markers(self, xdata, coldata):
        try:
            #logging.debug(f"SETTING MARKERS X:\n{xdata}")
            #logging.debug(f"SETTING MARKERS COLORS:\n {coldata}")
            i0 = self.channels * 2 + self.n_vertex_waveform
            i1 = i0 + 2 * len(xdata)
            i2 = i0 + self.n_vertex_markers
            self.positions[i0:i1:, 0] = 2 * (np.repeat(xdata, 2)/self.width) - 1.0
            self.positions[i0:i1:2, 1] = 1.0
            self.positions[i0+1:i1:2, 1] = -1.0
            self.positions[i0:i1:, 2] = -0.75
            self.positions[i1:i2] = 0
            colmatrix = np.array(coldata, dtype=np.float32)
            self.colors[i0:i1] = np.repeat(colmatrix, 2, axis=0)
            self.touched = True
        except Exception as e:
            logging.error(f"Can't set beat markers ... => {e}")

    def set_crop_markers(self, x1, x2):
        try:
            x1 = (2 * x1 / self.width) - 1.0
            x2 = (2 * x2 / self.width) - 1.0
            self.positions[-12:-4, 0] = [-1.0, -1.0, x1, x1, x2, x2, 1.0, 1.0]
            self.positions[-12:-4, 1] = [-1.0, 1.0, 1.0, -1.0, -1.0, 1.0, 1.0, -1.0]
            self.positions[-12:-4, 2] = 0.5
            self.touched = True
        except Exception as e:
            logging.error(f"Can't set crop markers ... => {e}")

    def set_cursor_pos(self, xpos):
        try:
            x = (2 * xpos / self.width) - 1.0
            w = 2 / self.width
            x1 = x - w
            x2 = x + w
            self.positions[-4:, 0] = [x1, x1, x2, x2]
            self.positions[-4:, 1] = [-1.0, 1.0, 1.0, -1.0]
            self.positions[-4:, 2] = -1
            #logging.debug(f"CURSOR POSTIION => {self.positions[-4:]}")
            self.touched = True
        except Exception as e:
            logging.error(f"Can't set cursor position ... => {e}")

    def redraw(self):
        if self.vbo_positions is None or self.vbo_colors is None:
            return

        if self.touched:
            self.vbo_positions.set_array(self.positions)
            self.touched = False

            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

            # Bind VBOs and point the pipeline to them (None = start at byte 0)
            self.vbo_positions.bind()
            glVertexPointer(3, GL_FLOAT, 0, None)

            self.vbo_colors.bind()
            glColorPointer(3, GL_FLOAT, 0, None)

            # Draw axis, waveform vertical lines and markersout of VRAM in one single batch instruction
            glDrawArrays(GL_LINES, 0, self.n_vertex - 12)

            # Draw Crop & Cursor Quads
            glDrawArrays(GL_QUADS, self.n_vertex - 12, 12)

            # Clean up bindings for this frame
            self.vbo_colors.unbind()
            self.vbo_positions.unbind()

            #glFlush()

# ------------------------------------------------------------------------------
# Zynthian Widget Class for audio file selectors
# ------------------------------------------------------------------------------

class zynthian_widget_audio_file(zynthian_widget_base.zynthian_widget_base):

    # MAX_FRAMES = 2880000

    def __init__(self, parent):
        super().__init__(parent)

        # Take only half height
        self.rows //= 2

        self.zctrl = None
        self.fpath = ""
        self.fname = ""
        self.sf = None
        self.channels = 0  # Quantity of channels in audio
        self.frames = 0  # Quantity of frames in audio
        self.samplerate = None
        self.duration = 0.0

        self.refreshing = False # Flag to avoid multiple threads refreshing waveform
        self.refresh_waveform = False  # True to force redraw of waveform on next refresh
        self.update_markers = False  # True to force update markers on next refresh
        self.waveform_height = 1  # ratio of height for y offset of zoom overview display
        self.offset = 0  # Frames from start of file that waveform display starts
        self.auto_offset = 0 # 1 to calc offset from crop_start. 2 to calc offest from crop_end.
        self.zoom = 1
        self.v_zoom = 1
        self.crop_start = 0
        self.crop_end = 0
        self.beats = 0
        self.warp = False
        self.gain = 1
        self.last_progress = 0

        self.bmarker_color1 = hexcolor_to_opengl(zynthian_gui_config.color_tx)
        self.bmarker_color2 = hexcolor_to_opengl(zynthian_gui_config.color_variant(zynthian_gui_config.color_tx, -80))

        self.font_info = tkinter.font.Font(font=("DejaVu Sans Mono", int(1.0 * zynthian_gui_config.font_size)))

        self.widget_canvas = WaveformCanvas(self,
                                            bd=0,
                                            highlightthickness=0,
                                            relief='flat',
                                            bg=zynthian_gui_config.color_bg)
        self.widget_canvas.bind('<ButtonPress-1>', self.on_canvas_press)
        self.widget_canvas.bind('<B1-Motion>', self.on_canvas_drag)
        self.widget_canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.widget_canvas.grid(sticky='news')

    def set_processor(self, processor):
        super().set_processor(processor)
        if self.zyngui_control.widget_zctrl:
            self.zctrl = self.zyngui_control.widget_zctrl
        else:
            try:
                note = self.processor.engine.selected_phrase + 1
                self.zctrl = self.processor.controllers_dict[f"file {note}"]
            except:
                for zctrl in self.processor.controllers_dict.values():
                    if zctrl.is_path:
                        self.zctrl = zctrl
                        break
        self.clip_info = self.get_clippy_info()

    def show(self):
        self.refreshing = False
        super().show()
        if self.clip_info:
            zynsigman.register_queued(zynsigman.S_AUDIO_RECORDER, zynsigman.SS_AUDIO_RECORDER_STATE, self.audio_recorder_cb)

    def hide(self):
        if self.clip_info:
            zynsigman.unregister(zynsigman.S_AUDIO_RECORDER, zynsigman.SS_AUDIO_RECORDER_STATE, self.audio_recorder_cb)
        super().hide()

    def on_size(self, event):
        if event.width == self.width and event.height == self.height:
            return
        super().on_size(event)
        #self.waveform_height = self.height - self.font_info.metrics("linespace")
        self.waveform_height = self.height

    def on_canvas_press(self, event):
        pass

    def on_canvas_drag(self, event):
        pass

    def on_canvas_release(self, event):
        pass

    def load_file(self):
        # Run as background thread
        if self.fpath:
            self.refreshing = True
            try:
                self.sf = soundfile.SoundFile(self.fpath)
                self.channels = self.sf.channels
                self.samplerate = self.sf.samplerate
                self.frames = self.sf.seek(0, soundfile.SEEK_END)
                if self.samplerate:
                    self.duration = self.frames / self.samplerate
                else:
                    self.duration = 0.0
                if self.channels:
                    y0 = self.waveform_height // self.channels
                else:
                    y0 = self.waveform_height
                for chan in range(self.channels):
                    v_offset = chan * y0
                    #self.widget_canvas.create_rectangle(0, v_offset, self.width, v_offset + y0, fill=self.bg_color, tags=("waveform", f"waveform_bg_{chan}"), state=tkinter.HIDDEN)
                    ## fill = zynthian_gui_config.LAUNCHER_COLOUR[chan // 2 % 16]["rgb"]
                    #self.widget_canvas.create_line(0, v_offset + y0 // 2, self.width, v_offset + y0 // 2, fill="grey", tags=("waveform", f"zero_{chan}"), state=tkinter.HIDDEN)
                    #self.widget_canvas.create_line(0, 0, 0, 0, fill=self.waveform_color, tags=("waveform", f"waveform{chan}"), state=tkinter.HIDDEN)
                self.offset = 0
                self.auto_offset = 0
                logging.debug(f"LOADING FILE {self.fpath} => {self.frames} frames")
                if self.clip_info:
                    self.get_clippy_values()
                else:
                    self.crop_start = 0
                    self.crop_end = self.frames
            except MemoryError:
                logging.warning(f"Failed to show waveform - file too large")
                #self.widget_canvas.itemconfig(self.loading_text, text="Can't display waveform")
                self.sf = None
            except Exception as e:
                logging.warning(f"Failed to show waveform: {e}")
                #self.widget_canvas.itemconfig(self.loading_text, text="No file loaded", state=tkinter.NORMAL)
                self.sf = None
            self.refreshing = False
            self.refresh_waveform = True
        else:
            #self.widget_canvas.itemconfig(self.loading_text, text="No file loaded", state=tkinter.NORMAL)
            self.channels = 0
            self.frames = 0
            self.sf = None

    def draw_waveform(self, start, length, gain=1.0):
        if self.sf is None:
            #self.widget_canvas.itemconfig(self.loading_text, text="No file loaded", state=tkinter.NORMAL)
            return

        length = min(self.frames, length)
        start = min(start, (self.frames - length))
        steps_per_peak = 16
        large_file = self.frames * self.channels > 24000000

        if self.channels:
            y0 = self.waveform_height // self.channels
        else:
            y0 = self.waveform_height
        y_offsets = []
        for i in range(self.channels):
            y_offsets.append(y0 * (i + 0.5))
        y0 = int(pow(1.26, gain) * y0 / 2)

        if large_file:
            frames_per_pixel = length // self.width
            # Limit read blocks for larger files
            block_size = min(frames_per_pixel, 1024)
            offset1 = 0
            offset2 = block_size
            step = max(1, block_size // steps_per_peak)
        else:
            self.sf.seek(start)
            a_data = self.sf.read(length, always_2d=True)
            frames_per_pixel = len(a_data) / self.width
            step = max(1, frames_per_pixel / steps_per_peak)
            # Limit read blocks for larger files
            block_size = min(frames_per_pixel, 1024)

        ydata = [0] * 2 * self.channels * self.width
        pos = 0
        for x in range(self.width):
            # For each x-axis pixel
            if large_file:
                self.sf.seek(start + x * frames_per_pixel)
                a_data = self.sf.read(block_size, always_2d=True)
                if len(a_data) == 0:
                    break
                offset2 = len(a_data)
            else:
                offset1 = x * frames_per_pixel
                offset2 = offset1 + frames_per_pixel
            for chan in range(self.channels):
                # For each audio channel
                v1 = [0.0] * self.channels
                v2 = [0.0] * self.channels
                frame = offset1
                while int(frame) < int(offset2):
                    # Find peak audio within block of audio represented by this x-axis pixel
                    av = a_data[int(frame)][chan] * self.v_zoom
                    if av < v1[chan]:
                        v1[chan] = av
                    if av > v2[chan]:
                        v2[chan] = av
                    frame += step
                ymin = y_offsets[chan] + v1[chan] * y0
                ymax = y_offsets[chan] + v2[chan] * y0
                if v2[chan] == 0:
                    ydata[pos] = ymax
                    ydata[pos + 1] = ymin
                else:
                    ydata[pos] = ymin
                    ydata[pos + 1] = ymax
                pos += 2

        self.widget_canvas.set_wave_data(ydata)

    def refresh_gui(self):
        if not self.zctrl:
            return
        self.refreshing = True

        refresh_info = False

        if "zoom" in self.monitors and self.zoom != self.monitors["zoom"]:
            self.zoom = self.monitors["zoom"]
            self.refresh_waveform = True

        if "offset" in self.monitors:
            if self.offset != self.monitors["offset"]:
                self.offset = self.monitors["offset"]
                self.refresh_waveform = True
                self.auto_offset = 0
        else:
            if self.auto_offset == 0:
                self.auto_offset = 1

        if "crop_start" in self.monitors and self.crop_start != self.monitors["crop_start"]:
                self.crop_start = self.monitors["crop_start"]
                self.update_markers = True
                self.refresh_waveform = True
                if self.auto_offset:
                    self.auto_offset = 1

        if "crop_end" in self.monitors and self.crop_end != self.monitors["crop_end"]:
                self.crop_end = self.monitors["crop_end"]
                self.update_markers = True
                self.refresh_waveform = True
                if self.auto_offset:
                    self.auto_offset = 2

        if "warp" in self.monitors and self.warp != self.monitors["warp"]:
                self.warp = self.monitors["warp"]
                self.update_markers = True

        if "beats" in self.monitors and self.beats != self.monitors["beats"]:
                self.beats = self.monitors["beats"]
                self.update_markers = True

        if "gain" in self.monitors and self.gain != self.monitors["gain"]:
                self.gain = self.monitors["gain"]
                self.refresh_waveform = True

        try:
            if self.zctrl and self.fpath != self.zctrl.value:
                # Audio file changed so reload waveform from file audio data
                self.fpath = self.zctrl.value
                self.fname = basename(self.fpath)
                waveform_thread = Thread(target=self.load_file, name="waveform image")
                waveform_thread.start()
                return

            self.widget_canvas.init_vbo(self.channels)

            if self.refresh_waveform:
                length = self.frames // self.zoom
                if self.auto_offset == 1:
                    # Centre on start crop marker
                    self.offset = self.crop_start - length // 2
                elif self.auto_offset == 2:
                    # Centre on end crop marker
                    self.offset = self.crop_end - length // 2
                # Ensure whoe waveform can be drawn
                self.offset = min(self.offset, self.frames - length)
                self.offset = max(self.offset, 0)
                self.draw_waveform(self.offset, length, self.gain)
                refresh_info = True
                self.update_markers = True
                self.refresh_waveform = False

            if self.frames:
                h = self.waveform_height
                f = self.width / self.frames * self.zoom
                if self.update_markers:
                    # Crop markers
                    x1 = int(f * (self.crop_start - self.offset))
                    x2 = int(f * (self.crop_end - self.offset))
                    self.widget_canvas.set_crop_markers(x1, x2)
                    # Beat markers
                    xdata = []
                    coldata = []
                    if self.beats > 0:  #  and self.warp
                        # Get Beats Per Bar
                        beats_per_bar = self.zyngui.state_manager.zynseq.get_sequence_param(self.clip_info[0], self.clip_info[1], zynseq.PHRASE_CHANNEL, "bpb")
                        if beats_per_bar < 1:
                            beats_per_bar = self.zyngui.state_manager.zynseq.bpb
                        dx = (x2 - x1) // self.beats
                        if dx > 4:
                            if dx < 16:
                                n = self.beats // beats_per_bar
                                plot_beats = False
                            else:
                                n = self.beats
                                plot_beats = True
                            for i in range(1, n):
                                x = x1 + i * (x2 - x1) // n
                                if plot_beats:
                                    if i % beats_per_bar == 0:
                                        col = self.bmarker_color1
                                    else:
                                        col = self.bmarker_color2
                                else:
                                    col = self.bmarker_color1
                                xdata.append(x)
                                coldata.append(col)
                        self.widget_canvas.set_beat_markers(xdata, coldata)
                # Playing cursor (implemented for clippy)
                if self.clip_info:
                    # Playing cursor
                    clip_state = self.zyngui.state_manager.zynseq.libseq.getPlayState(self.clip_info[0], self.clip_info[1], self.clip_info[2])
                    if clip_state == 1:
                        progress = self.zyngui.state_manager.zynseq.progress[self.zctrl.processor.midi_chan]
                    else:
                        progress = 0
                    if self.last_progress != progress or self.update_markers:
                        self.last_progress = progress
                        current_frame = self.crop_start + int(progress * (self.crop_end - self.crop_start) / 100) - self.offset
                        self.widget_canvas.set_cursor_pos(f * current_frame)
                refresh_info = True

            if refresh_info:
                time = self.duration
                n = (self.width // self.font_info.measure("x")) - 12
                fname = (self.fname[:n-3] + '...') if len(self.fname) > n else (self.fname + ' ')
                #self.widget_canvas.itemconfigure(self.info_text, text=f"{fname}[{self.format_time(time)}]", state=tkinter.NORMAL)

        except Exception as e:
            # logging.error(e)
            logging.exception(traceback.format_exc())

        self.widget_canvas.tkExpose(None)
        self.update_markers = False
        self.refreshing = False

    @staticmethod
    def format_time(time):
        return f"{int(time / 60):02d}:{int(time % 60):02d}.{int(modf(time)[0] * 1000):03}"

    # -------------------------------------------------------------------------
    # Audio recorder signal callback
    # -------------------------------------------------------------------------

    def audio_recorder_cb(self, state):
        if self.clip_info:
            #self.zyngui.state_manager.audio_recorder.status:
            try:
                self.processor.controllers_dict['record'].set_value(state, False)
            except:
                logging.error("Clippy processor doesn't have a record controller!")
            # Manage stop recording => load recorded sample!
            if not state:
                fpath = self.zyngui.state_manager.audio_recorder.filename
                if os.path.isfile(fpath):
                    self.zctrl.set_value(fpath)

    # -------------------------------------------------------------------------
    # CUIA & LEDs methods
    # -------------------------------------------------------------------------

    def get_clippy_info(self):
        if self.processor.eng_code == "CL":
            midi_chan = self.processor.midi_chan
            scene = self.zyngui.state_manager.zynseq.scene
            try:
                symparts = self.zctrl.symbol.split(" ")
                #symbol = symparts[0]  # should be "file"!
                note = int(symparts[1])
                phrase = note - 1
            except Exception as e:
                logging.error(f"Can't determine clippy sample index for '{self.zctrl.symbol}' => {e}")
                return None
            return (scene, phrase, midi_chan)
        else:
            return None

    def get_clippy_values(self):
        if self.clip_info:
            try:
                zctrls = self.processor.controllers_dict
                note = self.clip_info[1] + 1
                self.zoom = zctrls[f"zoom {note}"].value
                self.crop_start = zctrls[f"crop_start {note}"].value
                self.crop_end = zctrls[f"crop_end {note}"].value
                self.warp = zctrls[f"warp {note}"].value
                self.beats = zctrls[f"beats {note}"].value
                self.gain = zctrls[f"gain {note}"].value
                self.processor.engine.reset_monitors()
                self.update_markers = True
            except Exception as e:
                logging.error(f"Can't get clip audio values for clip {self.clip_info} => {e}")

    def cuia_toggle_record(self, param=None):
        # Handle transport for clippy
        if self.clip_info:
            self.zyngui.state_manager.audio_recorder.toggle_recording()
            return True
        return False

    def cuia_stop(self, param=None):
        # Handle transport for clippy
        if self.clip_info:
            self.zyngui.state_manager.zynseq.libseq.setPlayState(self.clip_info[0], self.clip_info[1], self.clip_info[2], 0)
            return True
        return False

    def cuia_toggle_play(self, param=None):
        # Handle transport for clippy
        if self.clip_info:
            self.zyngui.state_manager.zynseq.libseq.togglePlayState(self.clip_info[0], self.clip_info[1], self.clip_info[2])
            return True
        return False

    def update_wsleds(self, leds):
        # Handle LEDs for clippy
        if self.clip_info:
            wsl = self.zyngui.wsleds
            color_default = wsl.wscolor_active2
            # REC Button
            if self.zyngui.state_manager.audio_recorder.status:
                wsl.set_led(leds[1], wsl.wscolor_red)
            else:
                wsl.set_led(leds[1], color_default)
            # STOP button:
            wsl.set_led(leds[2], color_default)
            # PLAY button:
            play_state = self.zyngui.state_manager.zynseq.libseq.getPlayState(self.clip_info[0], self.clip_info[1], self.clip_info[2])
            if play_state in (2, 3, 4, 5):
                wsl.blink(leds[3], wsl.wscolor_green)
            elif play_state == 1:
                wsl.set_led(leds[3], wsl.wscolor_green)
            else:  # play_state == 0:`
                wsl.set_led(leds[3], color_default)


# ------------------------------------------------------------------------------
