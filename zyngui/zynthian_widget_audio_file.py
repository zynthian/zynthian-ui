# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Widget Class for audio file selectors
#
# Copyright (C) 2015-2025 Fernando Moyano <jofemodo@zynthian.org>
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

import logging
import tkinter
import soundfile
import traceback
from math import modf
from threading import Thread

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base

# ------------------------------------------------------------------------------
# Zynthian Widget Class for audio file selectors
# ------------------------------------------------------------------------------


class zynthian_widget_audio_file(zynthian_widget_base.zynthian_widget_base):

    # MAX_FRAMES = 2880000

    def __init__(self, parent):
        super().__init__(parent)

        # Geometry vars set accurately during resize
        self.rows = self.zyngui_control.layout['rows'] // 2

        self.refreshing = False
        self.zctrl = None
        self.path = ""
        self.duration = 0.0
        self.bg_color = zynthian_gui_config.color_bg
        self.waveform_color = zynthian_gui_config.color_info
        self.zoom = 1
        self.v_zoom = 1
        self.refresh_waveform = False  # True to force redraw of waveform on next refresh
        self.offset = 0  # Frames from start of file that waveform display starts
        self.channels = 0  # Quantity of channels in audio
        self.frames = 0  # Quantity of frames in audio
        self.sf = None
        self.waveform_height = 1  # ratio of height for y offset of zoom overview display
        self.widget_canvas = tkinter.Canvas(self,
                                            bd=0,
                                            highlightthickness=0,
                                            relief='flat',
                                            bg=zynthian_gui_config.color_bg)
        self.widget_canvas.grid(sticky='news')

        self.loading_text = self.widget_canvas.create_text(
            0,
            0,
            anchor=tkinter.CENTER,
            font=(
                zynthian_gui_config.font_family,
                int(1.5 * zynthian_gui_config.font_size)
            ),
            justify=tkinter.CENTER,
            fill=zynthian_gui_config.color_tx_off,
            text="No file loaded"
        )
        self.zoom_rect = self.widget_canvas.create_rectangle(
            0,
            self.height,
            self.width,
            self.height,
            width=0,
            fill=zynthian_gui_config.color_panel_bg,
            #state=tkinter.HIDDEN
        )
        self.info_text = self.widget_canvas.create_text(
            self.width - int(0.5 * zynthian_gui_config.font_size),
            self.height,
            anchor=tkinter.SE,
            justify=tkinter.RIGHT,
            width=self.width,
            font=("DejaVu Sans Mono", int(1.3 * zynthian_gui_config.font_size)),
            fill=zynthian_gui_config.color_panel_tx,
            text="",
            state=tkinter.HIDDEN,
            tags="overlay"
        )
        self.widget_canvas.bind('<ButtonPress-1>', self.on_canvas_press)
        self.widget_canvas.bind('<B1-Motion>', self.on_canvas_drag)
        self.widget_canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

    def show(self):
        self.refreshing = False
        super().show()

    def hide(self):
        super().hide()

    def on_size(self, event):
        if event.width == self.width and event.height == self.height:
            return
        super().on_size(event)
        self.widget_canvas.configure(width=self.width, height=self.height)
        self.widget_canvas.coords(self.loading_text, self.width // 2, self.height // 2)
        self.widget_canvas.coords(self.info_text, self.width - zynthian_gui_config.font_size // 2, self.height)
        self.widget_canvas.itemconfig(self.info_text, width=self.width)

        for chan in range(self.channels):
            coords = self.widget_canvas.coords(f"waveform_bg_{chan}")
            if len(coords) > 2:
                coords[2] = self.width
                self.widget_canvas.coords(f"waveform_bg_{chan}", coords)

        font = tkinter.font.Font(family="DejaVu Sans Mono", size=int(1.3 * zynthian_gui_config.font_size))
        self.waveform_height = self.height - font.metrics("linespace")
        self.refresh_waveform = True

    def on_canvas_press(self, event):
        pass

    def on_canvas_drag(self, event):
        pass

    def on_canvas_release(self, event):
        pass

    def load_file(self):
        # Run as background thread
        if self.path:
            try:
                self.refreshing = True
                self.widget_canvas.delete("waveform")
                self.widget_canvas.itemconfig("overlay", state=tkinter.HIDDEN)
                self.sf = soundfile.SoundFile(self.path)
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
                    y0 = self.waveform_height;
                for chan in range(self.channels):
                    v_offset = chan * y0
                    self.widget_canvas.create_rectangle(0, v_offset, self.width, v_offset + y0, fill=self.bg_color, tags=("waveform", f"waveform_bg_{chan}"), state=tkinter.HIDDEN)
                    # fill = zynthian_gui_config.LAUNCHER_COLOUR[chan // 2 % 16]["rgb"]
                    self.widget_canvas.create_line(0, v_offset + y0 // 2, self.width, v_offset + y0 // 2, fill="grey", tags="waveform", state=tkinter.HIDDEN)
                    self.widget_canvas.create_line(0, 0, 0, 0, fill=self.waveform_color, tags=("waveform", f"waveform{chan}"), state=tkinter.HIDDEN)
                #self.update_cue_markers()
                frames = self.frames / 2
                labels = ['x1']
                values = [1]
                z = 1
                while frames > self.width:
                    z *= 2
                    labels.append(f"x{z}")
                    values.append(z)
                    frames /= 2
                #zctrl = self.processor.controllers_dict['zoom']
                #zctrl.set_options({'labels': labels, 'ticks': values, 'value_max': values[-1]}
                self.draw_waveform(0, self.frames)

            except MemoryError:
                logging.warning(f"Failed to show waveform - file too large")
                self.widget_canvas.itemconfig(self.loading_text, text="Can't display waveform")
                self.sf = None
            except Exception as e:
                self.widget_canvas.itemconfig(self.loading_text, text="No file loaded", state=tkinter.NORMAL)
                self.sf = None
            self.refreshing = False
            self.refresh_waveform = True
        else:
            self.widget_canvas.itemconfig(f"waveform", state=tkinter.HIDDEN)
            self.widget_canvas.itemconfig(f"overlay", state=tkinter.HIDDEN)
            self.widget_canvas.itemconfig(self.loading_text, text="No file loaded", state=tkinter.NORMAL)
            self.sf = None

        self.update()

    def draw_waveform(self, start, length):
        if self.sf is None:
            self.widget_canvas.itemconfig(f"waveform", state=tkinter.HIDDEN)
            self.widget_canvas.itemconfig(f"overlay", state=tkinter.HIDDEN)
            self.widget_canvas.itemconfig(self.loading_text, text="No file loaded", state=tkinter.NORMAL)
            return

        start = min(self.frames, max(0, start))
        length = min(self.frames - start, length)
        steps_per_peak = 16
        data = [[] for i in range(self.channels)]
        large_file = self.frames * self.channels > 24000000

        if self.channels:
            y0 = self.waveform_height // self.channels
        else:
            y0 = self.waveform_height
        y_offsets = []
        for i in range(self.channels):
            y_offsets.append(y0 * (i + 0.5))
        y0 //= 2

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
            frames_per_pixel = len(a_data) // self.width
            step = max(1, frames_per_pixel // steps_per_peak)
            # Limit read blocks for larger files
            block_size = min(frames_per_pixel, 1024)

        if frames_per_pixel < 1:
            self.refresh_waveform = False
            self.widget_canvas.itemconfig(self.loading_text, text="Audio too short")
            return

        v1 = [0.0 for i in range(self.channels)]
        v2 = [0.0 for i in range(self.channels)]

        for x in range(self.width):
            # For each x-axis pixel
            if large_file:
                self.sf.seek(start + x * frames_per_pixel)
                a_data = self.sf.read(block_size, always_2d=True)
                if len(a_data) == 0:
                    break
            else:
                offset1 = x * frames_per_pixel
                offset2 = offset1 + frames_per_pixel
            for channel in range(self.channels):
                # For each audio channel
                v1[0:] = [0.0] * self.channels
                v2[0:] = [0.0] * self.channels
                for frame in range(offset1, offset2, step):
                    # Find peak audio within block of audio represented by this x-axis pixel
                    av = a_data[frame][channel] * self.v_zoom
                    if av < v1[channel]:
                        v1[channel] = av
                    if av > v2[channel]:
                        v2[channel] = av
                data[channel] += (x, y_offsets[channel] + int(v1[channel] * y0),
                                  x, y_offsets[channel] + int(v2[channel] * y0))

        for chan in range(self.channels):
            # Plot each point on the graph as series of vertical lines spanning max and min peaks of audio represented by each x-axis pixel
            self.widget_canvas.coords(f"waveform{chan}", data[chan])
        self.widget_canvas.itemconfig(f"waveform", state=tkinter.NORMAL)
        self.widget_canvas.itemconfig(self.loading_text, state=tkinter.HIDDEN)
        self.widget_canvas.tag_lower(self.loading_text)
        self.widget_canvas.tag_raise("overlay")
        self.widget_canvas.itemconfig(f"overlay", state=tkinter.NORMAL)

    def refresh_gui(self):
        if self.refreshing:
            return
        self.refreshing = True
        refresh_info = False

        try:
            if self.zctrl != self.zyngui_control.widget_zctrl:
                self.zctrl = self.zyngui_control.widget_zctrl
            else:
                self.zctrl = None
                return

            if self.path != self.zctrl.value:
                self.path = self.zctrl.value
                waveform_thread = Thread(target=self.load_file, name="waveform image")
                waveform_thread.start()
                return

            if self.refresh_waveform:
                self.draw_waveform(self.offset, int(self.frames / self.zoom))
                refresh_info = True
                self.refresh_waveform = False

            if refresh_info:
                zoom_offset = self.width * self.offset // self.frames
                self.widget_canvas.coords(self.zoom_rect, zoom_offset, self.waveform_height,
                                          zoom_offset + max(1, self.width // self.zoom), self.height)
                time = self.duration
                self.widget_canvas.itemconfigure(self.info_text, text=f"Duration: {self.format_time(time)}", state=tkinter.NORMAL)

        except Exception as e:
            # logging.error(e)
            logging.exception(traceback.format_exc())

        self.refreshing = False

    def format_time(self, time):
        return f"{int(time / 60):02d}:{int(time % 60):02d}.{int(modf(time)[0] * 1000):03}"

    # -------------------------------------------------------------------------
    # CUIA & LEDs methods
    # -------------------------------------------------------------------------

    def cuia_stop(self, param=None):
        #TODO: Handle transport
        return False

    def cuia_toggle_play(self, param=None):
        #TODO: Handle transport
        return False

    def update_wsleds(self, leds):
        #TODO: Handle LEDs
        return

# ------------------------------------------------------------------------------
