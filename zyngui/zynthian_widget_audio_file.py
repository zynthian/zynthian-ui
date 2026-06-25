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

# Zynthian specific modules
from zynlibs.zynseq import zynseq
from zyngine.zynthian_signal_manager import zynsigman
from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base

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

        self.bg_color = zynthian_gui_config.color_bg
        self.waveform_color = zynthian_gui_config.color_info
        self.playcur_color = zynthian_gui_config.color_on
        self.bg_crop_color = zynthian_gui_config.color_variant(zynthian_gui_config.color_panel_bg, 30)
        #self.bmarker_color = zynthian_gui_config.color_hl
        self.bmarker_color = zynthian_gui_config.color_tx
        self.font_info = tkinter.font.Font(font=("DejaVu Sans Mono", int(1.0 * zynthian_gui_config.font_size)))

        self.widget_canvas = tkinter.Canvas(self,
                                            bd=0,
                                            highlightthickness=0,
                                            relief='flat',
                                            bg=zynthian_gui_config.color_bg)
        self.widget_canvas.grid(sticky='news')

        self.loading_text = self.widget_canvas.create_text(
            0, 0,
            anchor=tkinter.CENTER,
            font=(zynthian_gui_config.font_family, int(1.5 * zynthian_gui_config.font_size)),
            justify=tkinter.CENTER,
            fill=zynthian_gui_config.color_tx_off,
            text="No file loaded"
        )
        self.playing_cursor_line = self.widget_canvas.create_line(
            0, 0, 0, self.height,
            fill=self.playcur_color,
            width=2,
            tags="overlay"
        )
        self.crop_start_rect = self.widget_canvas.create_rectangle(
            0, 0, 0, self.height,
            fill=self.bg_crop_color,
            stipple="gray50",
            tags="overlay"
        )
        self.crop_end_rect = self.widget_canvas.create_rectangle(
            self.width, 0, self.width, self.height,
            fill=self.bg_crop_color,
            stipple="gray50",
            tags="overlay"
        )
        self.info_rect = self.widget_canvas.create_rectangle(
            0,
            self.height,
            self.width,
            self.height,
            width=0,
            fill=zynthian_gui_config.color_panel_bg
        )
        self.info_text = self.widget_canvas.create_text(
            self.width - int(0.5 * zynthian_gui_config.font_size),
            self.height,
            anchor=tkinter.SE,
            justify=tkinter.RIGHT,
            width=self.width,
            font=self.font_info,
            fill=zynthian_gui_config.color_panel_tx,
            text="",
            state=tkinter.HIDDEN,
            tags="overlay"
        )
        self.widget_canvas.bind('<ButtonPress-1>', self.on_canvas_press)
        self.widget_canvas.bind('<B1-Motion>', self.on_canvas_drag)
        self.widget_canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

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
        self.widget_canvas.itemconfig("overlay", state=tkinter.HIDDEN)
        self.widget_canvas.itemconfig("waveform", state=tkinter.HIDDEN)
        super().on_size(event)
        self.widget_canvas.configure(width=self.width, height=self.height)
        self.widget_canvas.coords(self.loading_text, self.width // 2, self.height // 2)
        self.widget_canvas.coords(self.info_rect, 0, self.waveform_height, self.width, self.height)
        self.widget_canvas.coords(self.info_text, self.width - zynthian_gui_config.font_size // 2, self.height)
        self.widget_canvas.itemconfig(self.info_text, width=self.width)

        if self.channels:
            y0 = self.waveform_height // self.channels
            for chan in range(self.channels):
                coords = self.widget_canvas.coords(f"waveform_bg_{chan}")
                if len(coords) > 2:
                    coords[2] = self.width
                    self.widget_canvas.coords(f"waveform_bg_{chan}", coords)
                v_offset = chan * y0
                self.widget_canvas.coords(f"zero_{chan}", 0, v_offset + y0 // 2, self.width, v_offset + y0 // 2)

        self.waveform_height = self.height - self.font_info.metrics("linespace")
        self.refresh_waveform = True

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
                self.widget_canvas.delete("waveform")
                self.widget_canvas.itemconfig("overlay", state=tkinter.HIDDEN)
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
                    self.widget_canvas.create_rectangle(0, v_offset, self.width, v_offset + y0, fill=self.bg_color, tags=("waveform", f"waveform_bg_{chan}"), state=tkinter.HIDDEN)
                    # fill = zynthian_gui_config.LAUNCHER_COLOUR[chan // 2 % 16]["rgb"]
                    self.widget_canvas.create_line(0, v_offset + y0 // 2, self.width, v_offset + y0 // 2, fill="grey", tags=("waveform", f"zero_{chan}"), state=tkinter.HIDDEN)
                    self.widget_canvas.create_line(0, 0, 0, 0, fill=self.waveform_color, tags=("waveform", f"waveform{chan}"), state=tkinter.HIDDEN)
                self.offset = 0
                self.auto_offset = 0
                if self.clip_info:
                    self.get_clippy_values()
                else:
                    self.crop_start = 0
                    self.crop_end = self.frames
            except MemoryError:
                logging.warning(f"Failed to show waveform - file too large")
                self.widget_canvas.itemconfig(self.loading_text, text="Can't display waveform")
                self.sf = None
            except Exception as e:
                logging.warning(f"Failed to show waveform: {e}")
                self.widget_canvas.itemconfig(self.loading_text, text="No file loaded", state=tkinter.NORMAL)
                self.sf = None
            self.refreshing = False
            self.refresh_waveform = True
        else:
            self.widget_canvas.itemconfig(f"waveform", state=tkinter.HIDDEN)
            self.widget_canvas.itemconfig(f"overlay", state=tkinter.HIDDEN)
            self.widget_canvas.delete("beat_markers")
            self.widget_canvas.itemconfig(self.loading_text, text="No file loaded", state=tkinter.NORMAL)
            self.frames = 0
            self.sf = None

    def draw_waveform(self, start, length, gain=1.0):
        if self.sf is None:
            self.widget_canvas.itemconfig(f"waveform", state=tkinter.HIDDEN)
            self.widget_canvas.itemconfig(f"overlay", state=tkinter.HIDDEN)
            self.widget_canvas.delete("beat_markers")
            self.widget_canvas.itemconfig(self.loading_text, text="No file loaded", state=tkinter.NORMAL)
            return

        length = min(self.frames, length)
        start = min(start, (self.frames - length))
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
            for chan in range(self.channels):
                # For each audio channel
                v1[0:] = [0.0] * self.channels
                v2[0:] = [0.0] * self.channels
                frame = offset1
                while int(frame) < int(offset2):
                    # Find peak audio within block of audio represented by this x-axis pixel
                    av = a_data[int(frame)][chan] * self.v_zoom
                    if av < v1[chan]:
                        v1[chan] = av
                    if av > v2[chan]:
                        v2[chan] = av
                    frame += step
                y1 = int(y_offsets[chan] + v1[chan] * y0)
                y2 = int(y_offsets[chan] + v2[chan] * y0)
                data[chan] += [x, y1, x, y2]

        for chan in range(self.channels):
            # Plot each point on the graph as series of vertical lines spanning max and min peaks of audio represented by each x-axis pixel
            self.widget_canvas.coords(f"waveform{chan}", data[chan])
        self.widget_canvas.itemconfig(f"waveform", state=tkinter.NORMAL)
        self.widget_canvas.itemconfig(self.loading_text, state=tkinter.HIDDEN)
        self.widget_canvas.tag_lower(self.loading_text)
        self.widget_canvas.tag_raise("overlay")
        self.widget_canvas.itemconfig(f"overlay", state=tkinter.NORMAL)

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
                    self.widget_canvas.coords(self.crop_start_rect, 0, 0, x1, h)
                    self.widget_canvas.coords(self.crop_end_rect, x2, 0, self.width, h)
                    # Beat markers
                    self.widget_canvas.delete("beat_markers")
                    if self.beats > 0:  #  and self.warp
                        # Get Beats Per Bar
                        beats_per_bar = self.zyngui.state_manager.zynseq.get_sequence_param(self.clip_info[0], self.clip_info[1], zynseq.PHRASE_CHANNEL, "bpb")
                        if beats_per_bar < 1:
                            beats_per_bar = self.zyngui.state_manager.zynseq.bpb
                        for i in range(1, self.beats):
                            x = x1 + i * (x2 - x1) // self.beats
                            if i % beats_per_bar == 0:
                                dash = None
                            else:
                                dash = (2, 2)
                            self.widget_canvas.create_line(x, 0, x, h, fill=self.bmarker_color, dash=dash, tags="beat_markers")
                        #self.widget_canvas.tag_raise("beat_markers")
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
                        x = int(f * current_frame)
                        self.widget_canvas.coords(self.playing_cursor_line, x, 0, x, h)
                refresh_info = True

            if refresh_info:
                time = self.duration
                n = (self.width // self.font_info.measure("x")) - 12
                fname = (self.fname[:n-3] + '...') if len(self.fname) > n else (self.fname + ' ')
                self.widget_canvas.itemconfigure(self.info_text, text=f"{fname}[{self.format_time(time)}]", state=tkinter.NORMAL)

        except Exception as e:
            # logging.error(e)
            logging.exception(traceback.format_exc())

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
