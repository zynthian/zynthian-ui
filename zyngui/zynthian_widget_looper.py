#!/usr/bin/python3

# Copyright (C) 2022 Robert Amstadt <bob@looperlative.com>

# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.

# THE SOFTWARE IS PROVIDED “AS IS” AND ROBERT AMSTADT DISCLAIMS ALL WARRANTIES WITH
# REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
# AND FITNESS. IN NO EVENT SHALL ROBERT AMSTADT BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING
# FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT,
# NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION
# WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.


# Usage:
#
# This UI is intended to be used with a looping plugin.  The assumption is that tracks are
# named with a numeric digit and letter.  For example, these are valid track names: 1A, 2B, 3A.
#
# For each track, there will be a monitor output that indicates the tracks current state.
# These outputs are named: "track_status_" followed by the track name.  For example, one
# output might be "track_status_1A".  The value in that status is mapped to following
# possible conditions:
#
# 1	Track empty
# 2	Track recording
# 3	Track overdubbing
# 4	Track playing
# 5	Track stopped
# 6	Track replacing
#
# The monitor output "track_numout" indicates the numeric part of the track name of the
# current track.
#
# The monitor output beginning with "part_" and ending with a number indicates the
# letter portion of the track name where 1=A, 2=B, etc.  "part_1" would indicate the
# alphabetic part of the track name for the track number 1.
#
# "position" indicates the current position in seconds for the current track.
# "length" indicates the current length in seconds for the current track.

import tkinter
import re
import string
import logging
from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base
from math import trunc


class zynthian_widget_looper(zynthian_widget_base.zynthian_widget_base):
    def __init__(self, parent):
        super().__init__(parent)

    def set_processor(self, processor):
        super().set_processor(processor)
        self.create_gui()

    def create_gui(self):
        self.get_monitors()

        k = self.monitors.keys()
        tracks = []
        for i in k:
            m = re.search('track_status_([0-9A-Z]+)', i)
            if m:
                tracks.append(m.group(1))
        self.tracks = sorted(tracks)

        fsize = self.width // 15

        self.current_track_indicator = tkinter.Label(self,
                                                     font=('Audiowide', fsize),
                                                     text='Tr ??:',
                                                     bg=zynthian_gui_config.color_bg,
                                                     fg='#fff')
        self.current_pos_indicator = tkinter.Label(self,
                                                   font=('Helvetical',
                                                         fsize, 'bold'),
                                                   text='0.0',
                                                   bg=zynthian_gui_config.color_bg,
                                                   fg='#fff')
        self.current_len_indicator = tkinter.Label(self,
                                                   font=('Helvetical',
                                                         fsize, 'bold'),
                                                   text='0.0',
                                                   bg=zynthian_gui_config.color_bg,
                                                   fg='#fff')

        self.record_indicators = []
        self.play_indicators = []
        self.stop_indicators = []
        self.track_names = []

        i = 0
        for i in range(len(self.tracks)):
            rv = tkinter.Label(self,
                               text='\uf111',
                               bg=zynthian_gui_config.color_bg,
                               fg='#999')
            self.record_indicators.append(rv)
            rv.grid(row=i, column=2)

            rv = tkinter.Label(self,
                               text='\u25B6',
                               bg=zynthian_gui_config.color_bg,
                               fg='#999')
            self.play_indicators.append(rv)
            rv.grid(row=i, column=3)

            rv = tkinter.Label(self,
                               text='\u25A0',
                               bg=zynthian_gui_config.color_bg,
                               fg='#999')
            self.stop_indicators.append(rv)
            rv.grid(row=i, column=4)

            rv = tkinter.Label(self,
                               text='Track {}'.format(self.tracks[i]),
                               font=('Audiowide', fsize),
                               bg=zynthian_gui_config.color_bg,
                               fg='#fff')
            self.track_names.append(rv)
            rv.grid(row=i, column=0, sticky='w')

        self.rowconfigure(i+1, weight=1)
        self.columnconfigure(1, weight=1)
        self.current_track_indicator.grid(row=i+1, column=0, sticky='sw')
        self.current_pos_indicator.grid(
            row=i+1, column=1, columnspan=4, sticky='sw', padx=(2, 2))
        self.current_len_indicator.grid(row=i+1, column=5, sticky='se')

    def on_size(self, event):
        if event.width == self.width and event.height == self.height:
            return
        super().on_size(event)

        fsize = self.width // 15
        self.current_track_indicator.configure(font=('Audiowide', fsize))
        self.current_pos_indicator.configure(
            font=('Helvetical', fsize, 'bold'))
        self.current_len_indicator.configure(
            font=('Helvetical', fsize, 'bold'))

    def refresh_gui(self):
        try:
            curtracknum = "{}".format(int(self.monitors["track_numout"]))
            curpart = string.ascii_uppercase[int(
                self.monitors["part_" + curtracknum])-1]
            curtrack = curtracknum + curpart

            tpos = self.monitors["position"]
            tlen = self.monitors["length"]

            self.current_track_indicator.configure(
                text="Tr {}:".format(curtrack))
            self.current_pos_indicator.configure(text="{:5.1f}".format(tpos))
            self.current_len_indicator.configure(text="{:5.1f}".format(tlen))

            i = 0
            for t in self.tracks:
                status = trunc(self.monitors["track_status_" + t])
                if status == 1:
                    self.record_indicators[i].configure(fg="#999")
                    self.play_indicators[i].configure(fg="#999")
                    self.stop_indicators[i].configure(fg="#999")
                elif status == 2:
                    self.record_indicators[i].configure(fg="#f00")
                    self.play_indicators[i].configure(fg="#999")
                    self.stop_indicators[i].configure(fg="#999")
                elif status == 3:
                    self.record_indicators[i].configure(fg="#f00")
                    self.play_indicators[i].configure(fg="#0f0")
                    self.stop_indicators[i].configure(fg="#999")
                elif status == 4:
                    self.record_indicators[i].configure(fg="#999")
                    self.play_indicators[i].configure(fg="#0f0")
                    self.stop_indicators[i].configure(fg="#999")
                elif status == 5:
                    self.record_indicators[i].configure(fg="#999")
                    self.play_indicators[i].configure(fg="#999")
                    self.stop_indicators[i].configure(fg="#f00")
                elif status == 6:
                    self.record_indicators[i].configure(fg="#f00")
                    self.play_indicators[i].configure(fg="#0f0")
                    self.stop_indicators[i].configure(fg="#999")

                if t == curtrack:
                    self.track_names[i].configure(fg="#ff0")
                else:
                    self.track_names[i].configure(fg="#fff")

                i = i + 1
        except KeyError:
            logging.debug("KeyError ignored")
