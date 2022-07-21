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
#	1	Track empty
#	2	Track recording
#	3	Track overdubbing
#	4	Track playing
#	5	Track stopped
#	6	Track replacing
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

		self.widget_canvas = tkinter.Canvas(self,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg=zynthian_gui_config.color_bg)
		self.widget_canvas.grid(sticky='news')

		self.get_monitors()

		k = self.monitors.keys()
		tracks = []
		for i in k:
			m = re.search('track_status_([0-9A-Z]+)', i)
			if m:
				tracks.append(m.group(1))
		self.tracks = sorted(tracks)

		l_shapes = trunc(self.width / 12)
		l_grid = trunc(l_shapes * 1.5)
		l_offset = trunc((l_grid - l_shapes) / 2)
		fsize = trunc(l_shapes * 0.8)

		rv = self.widget_canvas.create_text(l_offset, self.height - l_grid, anchor="nw",
										 font=('Audiowide', fsize), text="Tr ??:",
										 fill="#fff")
		self.current_track_indicator = rv
		rv = self.widget_canvas.create_text(self.width - l_offset - 5 * fsize, self.height - l_grid,
										 anchor="ne", font=('Helvetica', fsize, 'bold'),
										 text="0.0", fill="#fff")
		self.current_pos_indicator = rv
		rv = self.widget_canvas.create_text(self.width - l_offset, self.height - l_grid, anchor="ne",
										 font=('Helvetica', fsize, 'bold'), text="0.0",
										 fill="#fff")
		self.current_len_indicator = rv

		self.record_indicators = []
		self.play_indicators = []
		self.stop_indicators = []
		self.track_names = []

		for i in range(len(self.tracks)):
			xg = trunc(self.width / 2)
			yg = i * l_grid
			x0 = xg + l_offset
			y0 = yg + l_offset
			rv = self.widget_canvas.create_oval(x0, y0, x0 + l_shapes, y0 + l_shapes,
											 outline="#f00", fill="#f00", width = 1)
			self.record_indicators.append(rv)

			xg = xg + l_grid
			x0 = xg + l_offset
			triangle = [x0, y0, x0, y0 + l_shapes, x0 + l_shapes, y0 + trunc(l_shapes / 2)]
			rv = self.widget_canvas.create_polygon(triangle, outline="#0f0", fill="#0f0", width = 1)
			self.play_indicators.append(rv)

			xg = xg + l_grid
			x0 = xg + l_offset
			rv = self.widget_canvas.create_rectangle(x0, y0, x0 + l_shapes, y0 + l_shapes,
												  outline="#f00", fill="#f00", width = 1)
			self.stop_indicators.append(rv)

			x0 = l_offset
			y0 = yg + trunc(l_grid / 2)
			t = "Track " + self.tracks[i]
			rv = self.widget_canvas.create_text(x0, y0, anchor="w",
											 font=('Audiowide', fsize), text=t, fill="#fff")
			self.track_names.append(rv)


	def on_size(self, event):
		if event.width == self.width and event.height == self.height:
			return
		super().on_size(event)
		self.widget_canvas.configure(width=self.width, height=self.height)

		l_shapes = trunc(self.width / 12)
		l_grid = trunc(l_shapes * 1.5)
		l_offset = trunc((l_grid - l_shapes) / 2)
		fsize = trunc(l_shapes * 0.8)


	def refresh_gui(self):
		try:
			curtracknum = "{}".format(int(self.monitors["track_numout"]))
			curpart = string.ascii_uppercase[int(self.monitors["part_" + curtracknum])-1]
			curtrack = curtracknum + curpart

			tpos = self.monitors["position"]
			tlen = self.monitors["length"]

			self.widget_canvas.itemconfig(self.current_track_indicator, text="Tr {}:".format(curtrack))
			self.widget_canvas.itemconfig(self.current_pos_indicator, text="{:5.1f}".format(tpos))
			self.widget_canvas.itemconfig(self.current_len_indicator, text="{:5.1f}".format(tlen))

			i = 0
			for t in self.tracks:
				status = trunc(self.monitors["track_status_" + t])
				if status == 1:
					self.widget_canvas.itemconfig(self.record_indicators[i], fill="#000")
					self.widget_canvas.itemconfig(self.play_indicators[i], fill="#000")
					self.widget_canvas.itemconfig(self.stop_indicators[i], fill="#000")
				elif status == 2:
					self.widget_canvas.itemconfig(self.record_indicators[i], fill="#f00")
					self.widget_canvas.itemconfig(self.play_indicators[i], fill="#000")
					self.widget_canvas.itemconfig(self.stop_indicators[i], fill="#000")
				elif status == 3:
					self.widget_canvas.itemconfig(self.record_indicators[i], fill="#f00")
					self.widget_canvas.itemconfig(self.play_indicators[i], fill="#0f0")
					self.widget_canvas.itemconfig(self.stop_indicators[i], fill="#000")
				elif status == 4:
					self.widget_canvas.itemconfig(self.record_indicators[i], fill="#000")
					self.widget_canvas.itemconfig(self.play_indicators[i], fill="#0f0")
					self.widget_canvas.itemconfig(self.stop_indicators[i], fill="#000")
				elif status == 5:
					self.widget_canvas.itemconfig(self.record_indicators[i], fill="#000")
					self.widget_canvas.itemconfig(self.play_indicators[i], fill="#000")
					self.widget_canvas.itemconfig(self.stop_indicators[i], fill="#f00")
				elif status == 6:
					self.widget_canvas.itemconfig(self.record_indicators[i], fill="#f00")
					self.widget_canvas.itemconfig(self.play_indicators[i], fill="#0f0")
					self.widget_canvas.itemconfig(self.stop_indicators[i], fill="#000")

				if t == curtrack:
					self.widget_canvas.itemconfig(self.track_names[i], fill="#ff0")
				else:
					self.widget_canvas.itemconfig(self.track_names[i], fill="#fff")

				i = i + 1
		except KeyError:
			logging.debug("KeyError ignored")
