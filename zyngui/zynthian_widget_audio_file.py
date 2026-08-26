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

import moderngl
import numpy as np
from moderngl_window.context.tk.window import ModernglTkWindow

# Zynthian specific modules
from zynlibs.zynseq import zynseq
from zyngine.zynthian_signal_manager import zynsigman
from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base



def hexcolor_to_opengl(hex_str):
    hex_str = hex_str.lstrip('#')
    r = int(hex_str[0:2], 16) / 255.0
    g = int(hex_str[2:4], 16) / 255.0
    b = int(hex_str[4:6], 16) / 255.0
    return [r, g, b]


class WaveformCanvas(ModernglTkWindow):  # Hereda directamente del widget oficial

    def __init__(self, *args, **kwargs):
        # 1. Forzar/asegurar ciertos nombres de variables que ModernGL-Window espera nativamente
        self.ctx = None
        self.prog = None
        self.vbo = None
        self.vao = None

        self.channels = 0
        self.n_vertex = 0
        self.vbo_data = None
        self.touched = False

        # Configuración de colores
        self.bg_color = hexcolor_to_opengl(zynthian_gui_config.color_bg)
        self.waveform_color1 = hexcolor_to_opengl(zynthian_gui_config.color_variant(zynthian_gui_config.color_hl, -60))
        self.waveform_color2 = hexcolor_to_opengl(zynthian_gui_config.color_hl)
        self.playcur_color = hexcolor_to_opengl(zynthian_gui_config.color_on)
        self.bg_crop_color = hexcolor_to_opengl(zynthian_gui_config.color_variant(zynthian_gui_config.color_panel_bg, 25))
        self.bmarker_color = hexcolor_to_opengl(zynthian_gui_config.color_tx)
        self.axis_color = hexcolor_to_opengl(zynthian_gui_config.color_variant(zynthian_gui_config.color_tx, -80))

        super().__init__(*args, **kwargs)
        #self.animate = True

        # 4. Enlazar el evento de redimensionado nativo de Tkinter
        self.bind("<Configure>", self.on_resize)

    def initgl(self):
        #self.tkMakeCurrent()

        # PI4/PI5 FIX: Bind to the desktop compatibility layer
        # Version 140 corresponds directly to OpenGL 3.1 Desktop
        #self.ctx = moderngl.create_context(require=140)
        # GLSL 140 SHADERS (Native desktop fallback for Pi 4 & Pi 5)
        # We replace 'in' with 'attribute' for inputs, and 'out' with 'varying' for pipelines
        _vertex_shader = """
            #version 140

            attribute vec3 in_position;
            attribute vec3 in_color;
            varying vec3 v_color;

            void main() {
                gl_Position = vec4(in_position, 1.0);
                v_color = in_color;
            }
        """
        _fragment_shader = """
            #version 140

            varying vec3 v_color;

            // In GLSL 140, we can use gl_FragColor directly or define a targeted out vec4
            out vec4 f_color;

            void main() {
                f_color = vec4(v_color, 1.0);
            }
        """

        self.ctx = moderngl.create_context(require=130)
        vertex_shader = """
            #version 300 es
            precision mediump float;

            in vec3 in_position;
            in vec3 in_color;
            out vec3 v_color;

            void main() {
                gl_Position = vec4(in_position, 1.0);
                v_color = in_color;
            }

        """
        fragment_shader = """
            #version 300 es
            precision mediump float;

            in vec3 v_color;
            out vec4 f_color;

            void main() {
                f_color = vec4(v_color, 1.0);
            }
        """
        self.ctx.clear_color = (*self.bg_color, 1.0)
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.depth_func = '<'

        # Mezcla/Blending para el suavizado
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)

        self.prog = self.ctx.program(vertex_shader=vertex_shader, fragment_shader=fragment_shader)

    def on_resize(self, event):
        self.width = self.winfo_width()    #event.width
        self.height = self.winfo_height()  #event.height
        if self.ctx:
            self.ctx.viewport = (0, 0, self.width, self.height)

    def init_channels(self, nchans=None):
        if nchans is None:
            nchans = self.channels
        if not self.ctx:
            return False
        if nchans == 0:
            self.channels = 0
            self.n_vertex = 0
            self.n_vertex_waveform = 0
            self.n_vertex_markers = 0
            self.vbo_data = None
            if self.vbo:
                self.vbo.release()
                self.vbo = None
            self.vao = None
            self.touched = True
            return True
        # Num Vertex = 2 * (Chans * Axis + Chans * Waveform + Beat Markers) + Crop Markers + Cursor
        nv = 2 * (nchans + nchans * self.width + self.width // 16) + 12 + 6
        if self.vbo_data is None or nchans != self.channels or nv != self.n_vertex:
            self.channels = nchans
            self.n_vertex = nv
            self.n_vertex_waveform = 2 * self.channels * self.width
            self.n_vertex_markers = 2 * self.width // 16

            # Vertex data matrix
            self.vbo_data = np.zeros(self.n_vertex, dtype=[
                ('pos', 'f4', 3),
                ('col', 'f4', 3)
            ])

            # Initialize axis lines data
            i0 = 0
            i1 = self.channels * 2
            y_coords = []
            yaxix = -1.0 + 1.0 / self.channels
            for ch in range(self.channels):
                y_coords.append(yaxix)
                yaxix += 2.0 / self.channels
            self.vbo_data['pos'][i0:i1:2, 0] = -1.0
            self.vbo_data['pos'][i0+1:i1:2, 0] = 1.0
            self.vbo_data['pos'][i0:i1, 1] = np.repeat(y_coords, 2)
            self.vbo_data['pos'][i0:i1, 2] = 0.5
            self.vbo_data['col'][i0:i1] = self.waveform_color2

            # Initialize waveform X coords
            i0 = i1
            i1 += self.n_vertex_waveform
            x_coords = np.linspace(-1.0, 1.0, self.width, dtype=np.float32)
            self.vbo_data['pos'][i0:i1, 0] = np.repeat(x_coords, 2 * self.channels)
            self.vbo_data['col'][i0:i1:2] = self.waveform_color1
            self.vbo_data['col'][i0+1:i1:2] = self.waveform_color2

            # Initialize markers & cursor
            i0 = i1
            i1 += self.n_vertex_markers
            self.vbo_data['col'][i0:i1] = self.bmarker_color
            self.vbo_data['col'][-18:-6] = self.bg_crop_color
            self.vbo_data['col'][-6:] = self.playcur_color

            # Create VBO & VAO in ModernGL
            if self.vbo:
                self.vbo.release()

            self.vbo = self.ctx.buffer(self.vbo_data.tobytes(), dynamic=True)
            self.vao = self.ctx.vertex_array(
                self.prog,
                [(self.vbo, '3f 3f', 'in_position', 'in_color')],
            )
            self.touched = True
        return True

    def set_wave_data(self, ydata):
        try:
            i0 = self.channels * 2
            i1 = i0 + self.n_vertex_waveform
            self.vbo_data['pos'][i0:i1, 1] = (2 * np.array(ydata, dtype=np.float32) / self.height) - 1.0
            self.touched = True
        except Exception as e:
            logging.error(f"Can't set wave data ... => {e}")

    def set_beat_markers(self, xdata, coldata):
        try:
            i0 = self.channels * 2 + self.n_vertex_waveform
            i1 = i0 + 2 * len(xdata)
            i2 = i0 + self.n_vertex_markers
            if  i1 > i0:
                self.vbo_data['pos'][i0:i1:, 0] = 2 * (np.repeat(xdata, 2)/self.width) - 1.0
                self.vbo_data['pos'][i0:i1:2, 1] = 1.0
                self.vbo_data['pos'][i0+1:i1:2, 1] = -1.0
                self.vbo_data['pos'][i0:i1:, 2] = -0.75
                colmatrix = np.array(coldata, dtype=np.float32)
                self.vbo_data['col'][i0:i1] = np.repeat(colmatrix, 2, axis=0)
            self.vbo_data['pos'][i1:i2] = 0
            self.touched = True
        except Exception as e:
            logging.error(f"Can't set beat markers ... => {e}")

    def set_crop_markers(self, x1, x2):
        try:
            x1 = (2 * x1 / self.width) - 1.0
            x2 = (2 * x2 / self.width) - 1.0
            self.vbo_data['pos'][-18:-6, 0] = np.array([-1.0, -1.0, x1, x1, x1, -1.0, 1.0, 1.0, x2, x2, x2, 1.0], dtype=np.float32)
            self.vbo_data['pos'][-18:-6, 1] = np.array([-1.0, 1.0, -1.0, -1.0, 1.0, 1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0], dtype=np.float32)
            self.vbo_data['pos'][-18:-6, 2] = 0.5
            self.touched = True
        except Exception as e:
            logging.error(f"Can't set crop markers ... => {e}")

    def set_cursor_pos(self, xpos):
        try:
            x = (2 * xpos / self.width) - 1.0
            w = 2 / self.width
            x1 = x - w
            x2 = x + w
            self.vbo_data['pos'][-6:, 0] = np.array([x1, x1, x2, x2, x2, x1], dtype=np.float32)
            self.vbo_data['pos'][-6:, 1] = np.array([-1.0, 1.0, -1.0, -1.0, 1.0, 1.0], dtype=np.float32)
            self.vbo_data['pos'][-6:, 2] = -1
            self.touched = True
        except Exception as e:
            logging.error(f"Can't set cursor position ... => {e}")

    def redraw(self):
        if self.touched:
            if self.vbo:
                self.vbo.write(self.vbo_data.tobytes())
            self.ctx.clear()
            if self.vao:
                # Dibujar líneas
                self.vao.render(moderngl.LINES, first=0, vertices=self.n_vertex - 18)
                # Dibujar Quads using native Triangles
                self.vao.render(moderngl.TRIANGLES, first=self.n_vertex - 18, vertices=18)
            self.touched = False

    def update(self):
        """Forces a single, immediate frame refresh when animate=False."""
        if self.touched:
            # 1. Bind the OpenGL rendering context to this X11 frame container
            self.tkMakeCurrent()
            # 2. Manually invoke your standard frame drawing logic
            self.redraw()
            # 3. Force the GPU to flush instructions and swap the front/back buffers
            self.tkSwapBuffers()

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
        self.vzoom = 1
        self.crop_start = 0
        self.crop_end = 0
        self.beats = 0
        self.warp = False
        self.gain = 1
        self.last_cursor_pos = 0

        self.bmarker_color1 = hexcolor_to_opengl(zynthian_gui_config.color_tx)
        self.bmarker_color2 = hexcolor_to_opengl(zynthian_gui_config.color_variant(zynthian_gui_config.color_tx, -80))
        self.font_info = tkinter.font.Font(font=("DejaVu Sans Mono", int(1.0 * zynthian_gui_config.font_size)))

        self.rowconfigure(0, weight=1)     # Row 0 (Canvas) expands to fill all remaining space
        self.rowconfigure(1, weight=0)     # Row 1 (Label) stays locked to its content height
        self.columnconfigure(0, weight=1)  # Expand fully horizontally

        self.widget_canvas = WaveformCanvas(self,
                                            bd=0,
                                            highlightthickness=0,
                                            relief='flat',
                                            bg=zynthian_gui_config.color_bg)
        self.widget_canvas.bind('<ButtonPress-1>', self.on_canvas_press)
        self.widget_canvas.bind('<B1-Motion>', self.on_canvas_drag)
        self.widget_canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.widget_canvas.grid(row=0, column=0, sticky='news')

        self.info_text_var = tkinter.StringVar()
        self.info_text_var.set("No waveform loaded")
        self.info_text = tkinter.Label(self,
                                       textvar=self.info_text_var,
                                       bg=zynthian_gui_config.color_panel_bg,
                                       fg=zynthian_gui_config.color_tx,
                                       font=self.font_info,
                                       anchor=tkinter.E,
                                       padx=5, pady=2)
        self.info_text.grid(row=1, column=0, sticky='news')

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
            self.info_text_var.set("Loading waveform ...")
            try:
                self.sf = soundfile.SoundFile(self.fpath)
                self.channels = self.sf.channels
                self.samplerate = self.sf.samplerate
                self.frames = self.sf.seek(0, soundfile.SEEK_END)
                if self.samplerate:
                    self.duration = self.frames / self.samplerate
                else:
                    self.duration = 0.0
                self.offset = 0
                self.auto_offset = 0
                logging.debug(f"LOADING FILE {self.fpath} => {self.frames} frames")
                if self.clip_info:
                    self.get_clippy_values()
                else:
                    self.crop_start = 0
                    self.crop_end = self.frames
            except MemoryError:
                logging.warning(f"Failed to display waveform: File too large!")
                self.info_text_var.set("File too large!")
                self.sf = None
            except Exception as e:
                logging.warning(f"Failed to display waveform: {e}")
                self.info_text_var.set("Can't show waveform!")
                self.sf = None
            self.refreshing = False
            self.refresh_waveform = True
        else:
            self.info_text_var.set("Can't show waveform!")
            self.channels = 0
            self.frames = 0
            self.sf = None

    def draw_waveform(self, start, length, vzoom=1.0):
        if self.sf is None:
            self.info_text_var.set("Can't show waveform!")
            return

        length = min(self.frames, length)
        start = min(start, (self.frames - length))
        steps_per_peak = 16
        large_file = self.frames * self.channels > 24000000

        self.waveform_height = self.widget_canvas.winfo_height()
        if self.channels:
            y0 = self.waveform_height // self.channels
        else:
            y0 = self.waveform_height
        y_offsets = []
        for i in range(self.channels):
            y_offsets.append(y0 * (i + 0.5))
        y0 = int(vzoom * y0 / 2)

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
                    av = a_data[int(frame)][chan]
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
        if not self.zctrl and self.processor.eng_code != "AP":
            return

        self.refreshing = True
        refresh_info = False

        zoom = offset = crop_start = crop_end = warp = beats = gain = vzoom = cursor_pos = None
        # Get clippy parameters
        if self.processor.eng_code == "CL":
            if "zoom" in self.monitors:
                zoom = self.monitors["zoom"]
            if "offset" in self.monitors:
                offset = self.monitors["offset"]
            if "crop_start" in self.monitors:
                crop_start = self.monitors["crop_start"]
            if "crop_end" in self.monitors:
                crop_end = self.monitors["crop_end"]
            if "warp" in self.monitors:
                warp = self.monitors["warp"]
            if "beats" in self.monitors:
                beats = self.monitors["beats"]
            if "gain" in self.monitors:
                gain = self.monitors["gain"]
                vzoom = pow(1.26, gain)       # Calculate vzoom from gain in dB
            if self.frames and self.clip_info:
                clip_state = self.zyngui.state_manager.zynseq.libseq.getPlayState(self.clip_info[0], self.clip_info[1], self.clip_info[2])
                if clip_state == 1:
                    cursor_pos = self.zyngui.state_manager.zynseq.progress[self.zctrl.processor.midi_chan] / 100.0
                else:
                    cursor_pos = 0.0
        # Get ZynSampler parameters
        elif self.processor.eng_code == "AP" and self.samplerate:
            zoom = self.processor.controllers_dict['zoom'].value
            offset = int(self.samplerate * self.processor.controllers_dict['view offset'].value)
            crop_start = self.processor.controllers_dict['crop start'].value
            crop_end = self.processor.controllers_dict['crop end'].value
            #crop_start = self.processor.controllers_dict['loop start'].value
            #crop_end = self.processor.controllers_dict['loop end'].value
            #cue_pos = int(self.samplerate * self.processor.controllers_dict['cue pos'].value)
            #selected_cue = self.processor.controllers_dict['cue'].value
            beats = 0
            gain = self.processor.controllers_dict['gain'].value    # Linear gain
            vzoom = gain * self.processor.controllers_dict['amp zoom'].value
            dur = crop_end - crop_start
            if dur > 0:
                cursor_pos = (self.processor.controllers_dict['position'].value - crop_start) / dur
            else:
                cursor_pos = 0
            crop_start = int(self.samplerate * crop_start)
            crop_end = int(self.samplerate * crop_end)

        # Process parameter changes
        if zoom is not None and zoom != self.zoom:
            self.zoom = zoom
            self.refresh_waveform = True
        if offset is not None and offset != self.offset:
            self.offset = offset
            self.refresh_waveform = True
            self.auto_offset = 0
        elif self.auto_offset == 0:
            self.auto_offset = 1
        if crop_start is not None and crop_start != self.crop_start:
            self.crop_start = crop_start
            self.update_markers = True
            self.refresh_waveform = True
            if self.auto_offset:
                self.auto_offset = 1
        if crop_end is not None and crop_end != self.crop_end:
            self.crop_end = crop_end
            self.update_markers = True
            self.refresh_waveform = True
            if self.auto_offset:
                self.auto_offset = 2
        if warp is not None and warp != self.warp:
            self.warp = warp
            self.update_markers = True
        if beats is not None and beats != self.beats:
            self.beats = beats
            self.update_markers = True
        if gain is not None and gain != self.gain:
            self.gain = gain
        if vzoom is not None and vzoom != self.vzoom:
            self.vzoom = vzoom
            self.refresh_waveform = True

        try:
            # Path zctrl => Clippy and others
            if self.zctrl:
                fpath = self.zctrl.value
            # Filename in monitors => ZynSampler
            elif "filename" in self.monitors:
                fpath = self.monitors["filename"]
            else:
                fpath = None

            # Audio file changed so reload waveform from file audio data
            if fpath and self.fpath != fpath:
                self.fpath = fpath
                self.fname = basename(self.fpath)
                waveform_thread = Thread(target=self.load_file, name="load_waveform")
                waveform_thread.start()
                self.refreshing = False
                return

            if not self.widget_canvas.init_channels(self.channels):
                self.refreshing = False
                return

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
                self.draw_waveform(self.offset, length, self.vzoom)
                refresh_info = True
                self.update_markers = True
                self.refresh_waveform = False

            if self.frames:
                h = self.waveform_height
                f = self.width / self.frames * self.zoom
                if self.update_markers:
                    # Crop markers
                    x1 = f * (self.crop_start - self.offset)
                    x2 = f * (self.crop_end - self.offset)
                    self.widget_canvas.set_crop_markers(x1, x2)
                    # Beat markers
                    xdata = []
                    coldata = []
                    if self.beats > 0:  #  and self.warp
                        # Get Beats Per Bar
                        if self.clip_info:
                            beats_per_bar = self.zyngui.state_manager.zynseq.get_sequence_param(self.clip_info[0], self.clip_info[1], zynseq.PHRASE_CHANNEL, "bpb")
                            if beats_per_bar < 1:
                                beats_per_bar = self.zyngui.state_manager.zynseq.bpb
                        else:
                            beats_per_bar = self.zyngui.state_manager.zynseq.bpb
                            #beats_per_bar = 4
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
                # Playing cursor
                if cursor_pos is not None and (self.last_cursor_pos != cursor_pos or self.update_markers):
                    self.last_cursor_pos = cursor_pos
                    current_frame = self.crop_start + int(cursor_pos * (self.crop_end - self.crop_start)) - self.offset
                    self.widget_canvas.set_cursor_pos(f * current_frame)

                refresh_info = True

            if refresh_info:
                time = self.duration
                n = (self.width // self.font_info.measure("x")) - 12
                fname = (self.fname[:n-3] + '...') if len(self.fname) > n else (self.fname + ' ')
                self.info_text_var.set(f"{fname}[{self.format_time(time)}]")

        except Exception as e:
            # logging.error(e)
            logging.exception(traceback.format_exc())

        self.update_markers = False
        self.refreshing = False
        self.widget_canvas.update()

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
    # ZynSampler integration
    # -------------------------------------------------------------------------

    def get_monitors(self):
        if self.processor.eng_code == "AP":
            self.monitors = self.processor.engine.get_monitors_dict(self.processor.handle)
        else:
            super().get_monitors()

    # -------------------------------------------------------------------------
    # Clippy integration
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

    # -------------------------------------------------------------------------
    # CUIA & LEDs methods
    # -------------------------------------------------------------------------

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
