# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Widget Class for "Zynthian Audio Player" (zynaudioplayer#one)
#
# Copyright (C) 2015-2024 Fernando Moyano <jofemodo@zynthian.org>
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
from math import modf, sqrt
from os.path import basename
from threading import Thread

# Zynthian specific modules
from zynlibs.zynaudioplayer import *
from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base
from zyngui import zynthian_gui_config
from zyngui.multitouch import MultitouchTypes

# ------------------------------------------------------------------------------
# Zynthian Widget Class for "zynaudioplayer"
# ------------------------------------------------------------------------------


class zynthian_widget_audioplayer(zynthian_widget_base.zynthian_widget_base):

    # MAX_FRAMES = 2880000

    def __init__(self, parent):
        super().__init__(parent)
        self.refreshing = False
        self.play_pos = 0.0
        self.loop_start = 0.0
        self.loop_end = 1.0
        self.crop_start = 0.0
        self.crop_end = 1.0
        self.cue_pos = 0.0
        self.cue = None
        self.speed = 1.0
        self.filename = "?"
        self.duration = 0.0
        self.bg_color = "black"
        self.waveform_color = "white"
        self.zoom = 1
        self.v_zoom = 1
        self.refresh_waveform = False  # True to force redraw of waveform on next refresh
        self.offset = 0  # Frames from start of file that waveform display starts
        self.channels = 0  # Quantity of channels in audio
        self.frames = 0  # Quantity of frames in audio
        self.info = None
        self.images = []
        self.waveform_height = 1  # ratio of height for y offset of zoom overview display
        self.tap_time = 0
        self.swipe_dir = 0
        self.swipe_speed = 0
        self.swipe_friction = 0.75

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
        self.play_line = self.widget_canvas.create_line(
            0,
            0,
            0,
            self.height,
            fill=zynthian_gui_config.color_on,
            tags="overlay"
        )
        self.loop_start_line = self.widget_canvas.create_line(
            0,
            0,
            0,
            self.height,
            fill=zynthian_gui_config.color_ml,
            tags="overlay"
        )
        self.loop_end_line = self.widget_canvas.create_line(
            self.width,
            0,
            self.width,
            self.height,
            fill=zynthian_gui_config.color_ml,
            tags="overlay"
        )
        self.crop_start_rect = self.widget_canvas.create_rectangle(
            0,
            0,
            0,
            self.height,
            fill="black",
            stipple="gray50",
            tags="overlay"
        )
        self.crop_end_rect = self.widget_canvas.create_rectangle(
            self.width,
            0,
            self.width,
            self.height,
            fill="black",
            stipple="gray50",
            tags="overlay"
        )
        self.zoom_rect = self.widget_canvas.create_rectangle(
            0,
            self.height,
            self.width,
            self.height,
            width=0,
            fill="dark grey",
            tags="overlay"
        )
        self.info_text = self.widget_canvas.create_text(
            self.width - int(0.5 * zynthian_gui_config.font_size),
            self.height,
            anchor=tkinter.SE,
            justify=tkinter.RIGHT,
            width=self.width,
            font=("DejaVu Sans Mono", int(1.5 * zynthian_gui_config.font_size)),
            fill=zynthian_gui_config.color_panel_tx,
            text="",
            state=tkinter.HIDDEN,
            tags="overlay"
        )
        self.widget_canvas.bind('<ButtonPress-1>', self.on_canvas_press)
        self.widget_canvas.bind('<B1-Motion>', self.on_canvas_drag)
        self.widget_canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.widget_canvas.bind("<Button-4>", self.cb_canvas_wheel)
        self.widget_canvas.bind("<Button-5>", self.cb_canvas_wheel)
        self.zyngui.multitouch.tag_bind(
            self.widget_canvas, None, "gesture", self.on_gesture)
        self.cue_points = []  # List of cue points [pos, name] indexed by lib's list

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

        self.widget_canvas.coords(
            self.loading_text, self.width // 2, self.height // 2)
        self.widget_canvas.coords(
            self.info_text, self.width - zynthian_gui_config.font_size // 2, self.height)
        self.widget_canvas.itemconfig(self.info_text, width=self.width)

        for chan in range(self.channels):
            coords = self.widget_canvas.coords(f"waveform_bg_{chan}")
            if len(coords) > 2:
                coords[2] = self.width
                self.widget_canvas.coords(f"waveform_bg_{chan}", coords)

        font = tkinter.font.Font(family="DejaVu Sans Mono", size=int(
            1.5 * zynthian_gui_config.font_size))
        self.waveform_height = self.height - font.metrics("linespace")
        self.refresh_waveform = True

    def view_offset_delta(self, dx):
        offset = self.processor.controllers_dict['view offset'].value - \
            self.duration * dx / self.width / self.zoom
        offset = max(0, offset)
        offset = min(self.duration - self.duration / self.zoom, offset)
        self.processor.controllers_dict['view offset'].set_value(offset, False)
        self.refresh_waveform = True

    def swipe_nudge(self, dts):
        if dts:
            self.swipe_speed += max(-500, min(0.1 * self.swipe_dir / dts, 500))
        # logging.debug(f"SWIPE NUDGE {dts} => SWIPE_SPEED = {self.swipe_speed}")

    def swipe_update(self):
        if self.swipe_speed:
            abs_speed = abs(self.swipe_speed)
            if abs_speed > 12:
                self.view_offset_delta(self.swipe_speed)
                self.swipe_speed *= self.swipe_friction
                # logging.debug(f"SWIPE UPDATE => SWIPE_SPEED = {self.swipe_speed}")
            else:
                self.swipe_speed = 0

    def on_gesture(self, gtype, value):
        if gtype == MultitouchTypes.GESTURE_H_DRAG:
            self.view_offset_delta(value)
        elif gtype == MultitouchTypes.GESTURE_H_PINCH:
            self.on_horizontal_pinch(value)
        elif gtype == MultitouchTypes.GESTURE_V_PINCH:
            self.on_vertical_pinch(value)

    def on_horizontal_pinch(self, value):
        zctrl = self.processor.controllers_dict['zoom']
        zctrl.set_value(zctrl.value + 4 * value / self.width * zctrl.value)
        self.refresh_waveform = True

    def on_vertical_pinch(self, value):
        v_zoom = self.processor.controllers_dict['amp zoom'].value + \
            value / self.height
        v_zoom = min(v_zoom, 4.0)
        v_zoom = max(v_zoom, 0.1)
        self.processor.controllers_dict['amp zoom'].set_value(v_zoom)
        self.refresh_waveform = True

    def on_canvas_press(self, event):
        if self.frames == 0:
            return
        f = self.width / self.frames * self.zoom
        pos = (event.x / f + self.offset) / self.samplerate
        max_delta = 0.02 * self.duration / self.zoom
        if event.y > 0.8 * self.height:
            self.drag_marker = "view offset"
            pos = self.duration * event.x / self.width
            self.processor.controllers_dict[self.drag_marker].set_value(pos)
            return
        elif event.time - self.tap_time < 200:
            self.on_canvas_double_tap(event)
        else:
            self.drag_marker = None
            for symbol in ['position', 'loop start', 'loop end', 'crop start', 'crop end']:
                if abs(pos - self.processor.controllers_dict[symbol].value) < max_delta:
                    self.drag_marker = symbol
                    break
            if self.drag_marker is None:
                for i, cue in enumerate(self.cue_points):
                    if abs(pos - cue[0]) < max_delta:
                        self.processor.controllers_dict['cue'].set_value(i+1)
                        self.drag_marker = 'cue pos'
                        break
            if self.drag_marker is None:
                self.drag_marker = "drag view"
                self.swipe_dir = 0
                self.swipe_speed = 0
                self.drag_start = event
            self.tap_time = event.time

    def on_canvas_drag(self, event):
        if self.drag_marker and self.frames:
            if self.drag_marker == "view offset":
                pos = self.duration * event.x / self.width
                self.processor.controllers_dict[self.drag_marker].set_value(
                    pos)
            elif self.drag_marker == "drag view":
                dx = int(event.x - self.drag_start.x)
                self.drag_start = event
                if dx:
                    pos = self.processor.controllers_dict['view offset'].value - \
                        self.duration * dx / self.width / self.zoom
                    pos = max(0, pos)
                    pos = min(self.duration - self.duration / self.zoom, pos)
                    self.processor.controllers_dict["view offset"].set_value(
                        pos)
                    self.swipe_dir = dx
            else:
                f = self.width / self.frames * self.zoom
                pos = (event.x / f + self.offset) / self.samplerate
                if self.drag_marker in self.processor.controllers_dict:
                    self.processor.controllers_dict[self.drag_marker].set_value(
                        pos)
                else:
                    id = zynaudioplayer.add_cue_point(
                        self.processor.handle, pos) + 1
                    if id > 0:
                        self.processor.controllers_dict['cue'].value_min = 1
                        self.processor.controllers_dict['cue'].value_max = id
                        self.processor.controllers_dict['cue'].set_value(id)
                        self.processor.controllers_dict['cue pos'].set_value(
                            pos)
                        self.update_cue_markers()

    # Function to handle end of mouse drag
    def on_canvas_release(self, event):
        if self.drag_marker == "drag view":
            dts = (event.time - self.drag_start.time)/1000
            self.swipe_nudge(dts)
        self.drag_start = None
        self.drag_marker = None

    def on_canvas_double_tap(self, event):
        options = {
            '> LOOP': None,
            'Loop start': event,
            'Loop end': event,
            '> CROP': None,
            'Crop start': event,
            'Crop end': event,
            '> CUE POINTS': None
        }
        f = self.width / self.frames * self.zoom
        pos = (event.x / f + self.offset) / self.samplerate
        options[f'Add cue marker at {pos:.3f}'] = event
        x = self.processor.controllers_dict['beats'].value
        if x:
            options[f'Add {x} evenly distributed cue markers'] = ['beats', x]
        if self.cue_points:
            options[f'Remove all cue markers'] = ['remove']
        options['> EXISTING CUES'] = None
        for i, cue in enumerate(self.cue_points):
            if cue[1]:
                options[f"Remove marker {cue[1]} at {cue[0]:.3f}"] = cue
            else:
                options[f"Remove marker {i+1} at {cue[0]:.3f}"] = cue
        self.zyngui.screens['option'].config(
            'Add marker', options, self.update_marker)
        self.zyngui.show_screen('option')

    def update_cue_markers(self):
        # Remove visual markers
        for i in range(len(self.cue_points)):
            self.widget_canvas.delete(f"cueline{i+1}")
            self.widget_canvas.delete(f"cuetxt{i+1}")
        # Rebuild list of markers
        self.cue_points = []
        i = 0
        while True:
            pos = zynaudioplayer.get_cue_point_position(
                self.processor.handle, i)
            if pos < 0.0:
                break
            name = zynaudioplayer.get_cue_point_name(self.processor.handle, i)
            self.widget_canvas.create_line(
                0,
                0,
                0,
                self.height,
                fill=zynthian_gui_config.color_info,
                tags=["overlay", "cues", f"cueline{i+1}", f"cue{i+1}"]
            )
            self.widget_canvas.create_text(
                0,
                0,
                anchor=tkinter.NE,
                justify=tkinter.RIGHT,
                font=("DejaVu Sans Mono", int(
                    0.8 * zynthian_gui_config.font_size)),
                fill=zynthian_gui_config.color_panel_tx,
                text=f"{i+1}",
                tags=["overlay", "cues", f"cuetxt{i+1}", f"cue{i+1}"]
            )
            self.cue_points.append([pos, name])
            i += 1
        self.cue_pos = None
        self.cue = None

    def update_marker(self, option, event):
        if isinstance(event, list):
            if event[0] == 'remove':
                zynaudioplayer.clear_cue_points(self.processor.handle)
                self.update_cue_markers()

            elif event[0] == 'beats':
                zynaudioplayer.clear_cue_points(self.processor.handle)
                for i in range(event[1]):
                    pos = self.processor.controllers_dict['crop start'].value + (
                        self.crop_end - self.crop_start) / self.samplerate / event[1] * i
                    id = zynaudioplayer.add_cue_point(
                        self.processor.handle, pos) + 1
                    if id > 0:
                        self.processor.controllers_dict['cue'].value_min = 1
                        self.processor.controllers_dict['cue'].value_max = id
                        self.processor.controllers_dict['cue'].set_value(id)
                        self.processor.controllers_dict['cue pos'].set_value(
                            pos)
            else:
                # Event is a cue marker to be removed
                id = zynaudioplayer.remove_cue_point(
                    self.processor.handle, event[0])
                if id < 0:
                    return
                count = zynaudioplayer.get_cue_point_count(
                    self.processor.handle)
                self.processor.controllers_dict['cue'].value_max = count
                if count == 0:
                    self.processor.controllers_dict['cue'].value_min = 0
                if self.processor.controllers_dict['cue'].value >= count:
                    self.processor.controllers_dict['cue'].set_value(count - 1)
            self.update_cue_markers()
        else:
            self.drag_marker = option.lower()
            self.on_canvas_drag(event)

    def get_monitors(self):
        self.monitors = self.processor.engine.get_monitors_dict(
            self.processor.handle)

    def load_file(self):
        try:
            self.refreshing = True
            self.info = None
            self.widget_canvas.delete("waveform")
            self.widget_canvas.itemconfig("overlay", state=tkinter.HIDDEN)
            self.widget_canvas.itemconfig(
                self.loading_text, text="Creating waveform...")
            self.sf = soundfile.SoundFile(self.filename)
            self.channels = self.sf.channels
            self.samplerate = self.sf.samplerate
            self.frames = self.sf.seek(0, soundfile.SEEK_END)
            if self.samplerate:
                self.duration = self.frames / self.samplerate
            else:
                self.duration = 0.0
            y0 = self.waveform_height // self.channels
            for chan in range(self.channels):
                v_offset = chan * y0
                self.widget_canvas.create_rectangle(0, v_offset, self.width, v_offset + y0, fill=zynthian_gui_config.PAD_COLOUR_GROUP[chan // 2 % len(
                    zynthian_gui_config.PAD_COLOUR_GROUP)], tags=("waveform", f"waveform_bg_{chan}"), state=tkinter.HIDDEN)
                self.widget_canvas.create_line(
                    0, v_offset + y0 // 2, self.width, v_offset + y0 // 2, fill="grey", tags="waveform", state=tkinter.HIDDEN)
                self.widget_canvas.create_line(0, 0, 0, 0, fill=self.waveform_color, tags=(
                    "waveform", f"waveform{chan}"), state=tkinter.HIDDEN)
            self.update_cue_markers()
            frames = self.frames / 2
            labels = ['x1']
            values = [1]
            z = 1
            while frames > self.width:
                z *= 2
                labels.append(f"x{z}")
                values.append(z)
                frames /= 2
            zctrl = self.processor.controllers_dict['zoom']
            zctrl.set_options(
                {'labels': labels, 'ticks': values, 'value_max': values[-1]})

        except MemoryError:
            logging.warning(f"Failed to show waveform - file too large")
            self.widget_canvas.itemconfig(
                self.loading_text, text="Can't display waveform")
        except Exception as e:
            self.widget_canvas.itemconfig(
                self.loading_text, text="No file loaded")
        self.refreshing = False
        self.refresh_waveform = True
        self.update()

    def draw_waveform(self, start, length):
        self.widget_canvas.itemconfig(
            self.loading_text, text="Creating waveform...")
        if not self.channels:
            self.widget_canvas.itemconfig(
                self.loading_text, text="No audio in file")
            return
        start = max(0, start)
        start = min(self.frames, start)
        length = min(self.frames - start, length)
        steps_per_peak = 16
        data = [[] for i in range(self.channels)]
        large_file = self.frames * self.channels > 24000000

        y0 = self.waveform_height // self.channels
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
            self.widget_canvas.itemconfig(
                self.loading_text, text="Audio too short")
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
        self.widget_canvas.tag_lower(self.loading_text)
        self.widget_canvas.tag_raise("overlay")

        self.refresh_waveform = False

    def refresh_gui(self):
        if self.refreshing:
            return
        self.refreshing = True
        self.swipe_update()
        try:
            if self.v_zoom != self.processor.controllers_dict['amp zoom'].value:
                self.v_zoom = self.processor.controllers_dict['amp zoom'].value
                self.refresh_waveform = True

            if self.filename != self.monitors["filename"]:
                self.filename = self.monitors["filename"]
                waveform_thread = Thread(
                    target=self.load_file, name="waveform image")
                waveform_thread.start()
                self.refreshing = False
                return

            if self.duration == 0.0:
                self.refreshing = False
                self.widget_canvas.itemconfig(
                    self.loading_text, text="No audio in file")
                return

            refresh_markers = False
            loop_start = int(
                self.samplerate * self.processor.controllers_dict['loop start'].value)
            loop_end = int(self.samplerate *
                           self.processor.controllers_dict['loop end'].value)
            crop_start = int(
                self.samplerate * self.processor.controllers_dict['crop start'].value)
            crop_end = int(self.samplerate *
                           self.processor.controllers_dict['crop end'].value)
            cue_pos = int(self.samplerate *
                          self.processor.controllers_dict['cue pos'].value)
            selected_cue = self.processor.controllers_dict['cue'].value
            pos_time = self.processor.controllers_dict['position'].value
            pos = int(pos_time * self.samplerate * self.speed)
            refresh_info = False

            offset = int(self.samplerate *
                         self.processor.controllers_dict['view offset'].value)
            if self.zoom != self.processor.controllers_dict['zoom'].value:
                centre = offset + 0.5 * self.frames / self.zoom
                zoom = self.processor.controllers_dict['zoom'].value
                if zoom:
                    self.zoom = zoom
                if self.processor.controllers_dict['zoom range'].value == 0:
                    offset = int(centre - 0.5 * self.frames / self.zoom)
                self.refresh_waveform = True

            if self.loop_start != loop_start:
                self.loop_start = loop_start
                if self.loop_start < offset or self.loop_start > offset + self.frames // self.zoom:
                    offset = int(self.loop_start - 0.25 *
                                 self.frames / self.zoom)
                refresh_markers = True

            if self.loop_end != loop_end:
                self.loop_end = loop_end
                if self.loop_end < offset or self.loop_end > offset + self.frames // self.zoom:
                    offset = int(self.loop_end - 0.75 *
                                 self.frames / self.zoom)
                refresh_markers = True

            if self.crop_start != crop_start:
                self.crop_start = crop_start
                if self.crop_start < offset or self.crop_start > offset + self.frames // self.zoom:
                    offset = int(self.crop_start - 0.25 *
                                 self.frames / self.zoom)
                refresh_markers = True

            if self.crop_end != crop_end:
                self.crop_end = crop_end
                if self.crop_end < offset or self.crop_end > offset + self.frames // self.zoom:
                    offset = int(self.crop_end - 0.75 *
                                 self.frames / self.zoom)
                refresh_markers = True

            if self.speed != self.monitors['speed']:
                self.speed = self.monitors['speed']
                refresh_info = True

            if self.play_pos != pos:
                self.play_pos = pos
                if pos < offset or pos > offset + self.frames // self.zoom:
                    if self.processor.controllers_dict['varispeed'].value < 0.0:
                        offset = pos - self.frames // self.zoom
                    else:
                        offset = max(0, pos)
                refresh_markers = True

            if self.cue != selected_cue:
                self.cue = selected_cue
                refresh_markers = True

            if self.cue_pos != cue_pos:
                self.cue_pos = cue_pos
                if cue_pos < offset or cue_pos > offset + self.frames // self.zoom:
                    offset = max(0, cue_pos)
                if self.cue_points and self.cue:
                    self.cue_points[self.cue -
                                    1][0] = self.processor.controllers_dict['cue pos'].value
                refresh_markers = True

            offset = max(0, offset)
            offset = int(min(self.frames - self.frames / self.zoom, offset))
            if offset != self.offset:
                self.offset = offset
                if self.processor.controllers_dict['zoom range'].value == 0:
                    self.processor.controllers_dict['view offset'].set_value(
                        offset / self.samplerate, False)
                self.refresh_waveform = True

            if self.refresh_waveform:
                self.draw_waveform(offset, int(self.frames / self.zoom))
                refresh_markers = True

            if refresh_markers and self.frames:
                h = self.waveform_height
                f = self.width / self.frames * self.zoom
                x = int(f * (self.loop_start - self.offset))
                self.widget_canvas.coords(self.loop_start_line, x, 0, x, h)
                x = int(f * (self.loop_end - self.offset))
                self.widget_canvas.coords(self.loop_end_line, x, 0, x, h)
                x = int(f * (self.crop_start - self.offset))
                self.widget_canvas.coords(self.crop_start_rect, 0, 0, x, h)
                x = int(f * (self.crop_end - self.offset))
                self.widget_canvas.coords(
                    self.crop_end_rect, x, 0, self.width, h)
                x = int(f * (pos - self.offset))
                self.widget_canvas.coords(self.play_line, x, 0, x, h)

                self.widget_canvas.itemconfig(f"cues", fill="white")
                for i, cue in enumerate(self.cue_points):
                    x = int(f * (self.samplerate * cue[0] - self.offset))
                    self.widget_canvas.coords(f"cueline{i+1}", x, 0, x, h)
                    self.widget_canvas.coords(f"cuetxt{i+1}", x, 0)
                    if i + 1 == self.cue:
                        self.widget_canvas.itemconfig(
                            f"cue{i+1}", fill=zynthian_gui_config.color_info)
                refresh_info = True

            if self.info is None or self.info != self.processor.controllers_dict['info'].value:
                self.widget_canvas.itemconfig("waveform", state=tkinter.NORMAL)
                self.widget_canvas.itemconfig("overlay", state=tkinter.NORMAL)
                self.info = self.processor.controllers_dict['info'].value
                refresh_info = True

            if refresh_info:
                zoom_offset = self.width * offset // self.frames
                self.widget_canvas.coords(self.zoom_rect, zoom_offset, self.waveform_height,
                                          zoom_offset + max(1, self.width // self.zoom), self.height)
                if self.info == 1:
                    time = (self.crop_end - self.crop_start) / \
                        self.samplerate / self.speed
                    self.widget_canvas.itemconfigure(
                        self.info_text, text=f"Duration: {self.format_time(time)}", state=tkinter.NORMAL)
                elif self.info == 2:
                    time = max(0, pos - self.crop_start) / \
                        self.samplerate / self.speed
                    self.widget_canvas.itemconfigure(
                        self.info_text, text=f"Position: {self.format_time(time)}", state=tkinter.NORMAL)
                elif self.info == 3:
                    time = max(0, self.crop_end - pos) / \
                        self.samplerate / self.speed
                    self.widget_canvas.itemconfigure(
                        self.info_text, text=f"Remaining: {self.format_time(time)}", state=tkinter.NORMAL)
                elif self.info == 4:
                    time = (self.loop_end - self.loop_start) / \
                        self.samplerate / self.speed
                    self.widget_canvas.itemconfigure(
                        self.info_text, text=f"Loop length: {self.format_time(time)}", state=tkinter.NORMAL)
                elif self.info == 5:
                    self.widget_canvas.itemconfig(
                        self.info_text, text=f"Samplerate: {self.samplerate}", state=tkinter.NORMAL)
                elif self.info == 6:
                    self.widget_canvas.itemconfig(
                        self.info_text, text=f"CODEC: {self.monitors['codec']}", state=tkinter.NORMAL)
                elif self.info == 7:
                    self.widget_canvas.itemconfig(
                        self.info_text, text=f"Filename: {basename(self.filename)}", state=tkinter.NORMAL)
                else:
                    self.widget_canvas.itemconfig(
                        self.info_text, state=tkinter.HIDDEN)

        except Exception as e:
            # logging.error(e)
            logging.exception(traceback.format_exc())

        self.refreshing = False

    def format_time(self, time):
        return f"{int(time / 60):02d}:{int(time % 60):02d}.{int(modf(time)[0] * 1000):03}"

    def cb_canvas_wheel(self, event):
        try:
            if event.num == 5 or event.delta == -120:
                if event.state == 1:  # Shift
                    self.processor.controllers_dict['loop start'].nudge(-1)
                elif event.state == 5:  # Shift+Ctrl
                    self.processor.controllers_dict['loop end'].nudge(-1)
                elif event.state == 4:  # Ctrl
                    self.processor.controllers_dict['zoom'].nudge(-1)
                elif event.state == 8:  # Alt
                    self.offset = max(
                        0, self.offset - self.frames // self.zoom // 10)
                    self.refresh_waveform = True
                else:
                    self.processor.controllers_dict['position'].nudge(-1)
            elif event.num == 4 or event.delta == 120:
                if event.state == 1:  # Shift
                    self.processor.controllers_dict['loop start'].nudge(1)
                elif event.state == 5:  # Shift+Ctrl
                    self.processor.controllers_dict['loop end'].nudge(1)
                elif event.state == 4:  # Ctrl
                    self.processor.controllers_dict['zoom'].nudge(1)
                elif event.state == 8:  # Alt
                    self.offset = min(self.frames - self.frames // self.zoom,
                                      self.offset + self.frames // self.zoom // 10)
                    self.refresh_waveform = True
                else:
                    self.processor.controllers_dict['position'].nudge(1)
        except Exception as e:
            logging.debug("Failed to change value")

    # -------------------------------------------------------------------------
    # CUIA & LEDs methods
    # -------------------------------------------------------------------------

    def cuia_stop(self, param=None):
        if self.zyngui.alt_mode:
            return False
        zynaudioplayer.stop_playback(self.processor.handle)
        zynaudioplayer.set_position(self.processor.handle, 0.0)
        return True

    def cuia_toggle_play(self, param=None):
        if self.zyngui.alt_mode:
            return False
        if zynaudioplayer.get_playback_state(self.processor.handle):
            zynaudioplayer.stop_playback(self.processor.handle)
        else:
            zynaudioplayer.start_playback(self.processor.handle)
        return True

    def update_wsleds(self, leds):
        if self.zyngui.alt_mode:
            return
        wsl = self.zyngui.wsleds
        if self.processor.handle == self.zyngui.state_manager.audio_player.handle:
            color_default = wsl.wscolor_default
        else:
            color_default = wsl.wscolor_active2
        # REC Button
        if self.zyngui.state_manager.audio_recorder.status:
            wsl.set_led(leds[1], wsl.wscolor_red)
        else:
            wsl.set_led(leds[1], color_default)
        # STOP button
        wsl.set_led(leds[2], color_default)
        # PLAY button:
        if zynaudioplayer.get_playback_state(self.processor.handle):
            wsl.set_led(leds[3], wsl.wscolor_green)
        else:
            wsl.set_led(leds[3], color_default)

# ------------------------------------------------------------------------------
