#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian Widget Class for "Zynthian Audio Player" (zynaudioplayer#one)
# 
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
# Copyright (C) 2015-2023 Brian Walton <riban@zynthian.org>
#
#******************************************************************************
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
#******************************************************************************

from threading import Thread
import tkinter
import logging
import soundfile
from math import modf, sqrt
from os.path import basename

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base
from zyngui import zynthian_gui_config

#------------------------------------------------------------------------------
# Zynthian Widget Class for "zynaudioplayer"
#------------------------------------------------------------------------------

class zynthian_widget_audioplayer(zynthian_widget_base.zynthian_widget_base):


	def __init__(self, parent):
		super().__init__(parent)
		self.refreshing = False
		self.play_pos = 0.0
		self.loop_start = 0.0
		self.loop_end = 1.0
		self.crop_start = 0.0
		self.crop_end = 1.0
		self.filename = "?"
		self.duration = 0.0
		self.bg_color = "black"
		self.waveform_color = "white"
		self.zoom = 1
		self.refresh_waveform = False # True to force redraw of waveform on next refresh
		self.offset = 0 # Frames from start of file that waveform display starts
		self.channels = 0 # Quantity of channels in audio
		self.frames = 0 # Quantity of frames in audio
		self.limit_factor = 1500000 # Used to limit the quantity of frames processed in large data sets
		self.info = None
		self.images=[]
		self.zoom_height = 0.94 # ratio of height for y offset of zoom overview display
		self.v_zoom = 1.0 # vertical zoom factor

		self.widget_canvas = tkinter.Canvas(self,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg=zynthian_gui_config.color_bg)
		self.widget_canvas.grid(sticky='news')

		self.widget_canvas.bind('<ButtonPress-1>', self.on_canvas_press)
		self.widget_canvas.bind('<ButtonRelease-1>', self.on_canvas_release)
		self.widget_canvas.bind('<B1-Motion>', self.on_canvas_drag)

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
			text="Creating\nwaveform..."
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
			anchor = tkinter.SE,
			justify=tkinter.RIGHT,
			width=self.width,
			font=("DejaVu Sans Mono", int(1.5 * zynthian_gui_config.font_size)),
			fill=zynthian_gui_config.color_panel_tx,
			text="",
			state = "hidden",
			tags = "overlay"
		)
		self.widget_canvas.bind("<Button-4>",self.cb_canvas_wheel)
		self.widget_canvas.bind("<Button-5>",self.cb_canvas_wheel)

	def on_size(self, event):
		if event.width == self.width and event.height == self.height:
			return
		super().on_size(event)
		self.widget_canvas.configure(width=self.width, height=self.height)

		self.widget_canvas.coords(self.loading_text, self.width // 2, self.height // 2)
		self.widget_canvas.coords(self.info_text, self.width - zynthian_gui_config.font_size // 2, self.height)
		self.widget_canvas.itemconfig(self.info_text, width=self.width)
		self.refresh_waveform = True


	def on_canvas_press(self, event):
		self.zoom_drag_x = event.x
		self.zoom_drag_y = event.y
		f = self.width / self.frames * self.zoom
		pos = (event.x / f + self.offset) / self.samplerate
		self.duration / self.zoom
		max_delta = 0.02 * self.duration / self.zoom
		self.drag_mode = None
		if event.y > 0.8 * self.height:
			self.drag_mode = 'z'
		else:
			for symbol in ['position', 'loop start', 'loop end', 'crop start', 'crop end']:
				if abs(pos - self.layer.controllers_dict[symbol].value) < max_delta:
					self.drag_mode = symbol
					break


	def on_canvas_release(self, event):
		if self.drag_mode is None:
			f = self.width / self.frames * self.zoom
			pos = (event.x / f + self.offset) / self.samplerate
			if event.x < self.width / 3:
				self.layer.controllers_dict['loop start'].set_value(pos)
			elif event.x > 2 * self.width / 3:
				self.layer.controllers_dict['loop end'].set_value(pos)


	def on_canvas_drag(self, event):
		if self.drag_mode is None:
			if abs(event.x - self.zoom_drag_x) > self.width // 40:
				self.drag_mode = 'x'
			elif abs(event.y - self.zoom_drag_y) > self.width // 40:
				self.drag_mode = 'y'
			else:
				return
		if self.drag_mode == 'x':
			self.offset += int(self.frames * (self.zoom_drag_x - event.x) / self.width / self.zoom)
			self.offset = max(0, self.offset)
			self.offset = min(self.frames - self.frames // self.zoom, self.offset)
			self.zoom_drag_x = event.x
			self.refresh_waveform = True
		elif self.drag_mode == 'y':
			self.v_zoom += (self.zoom_drag_y - event.y) / self.height
			self.v_zoom = min(self.v_zoom, 4.0)
			self.v_zoom = max(self.v_zoom, 0.1)
			self.zoom_drag_y = event.y
			self.refresh_waveform = True
		elif self.drag_mode == 'z':
			delta = event.x - self.zoom_drag_x
			zctrl = self.layer.controllers_dict['zoom']
			zctrl.set_value(zctrl.value + 4 * delta / self.width * self.zoom)
			self.zoom_drag_x = event.x
		else:
			f = self.width / self.frames * self.zoom
			pos = (event.x / f + self.offset) / self.samplerate
			self.layer.controllers_dict[self.drag_mode].set_value(pos)


	def get_monitors(self):
		self.monitors = self.layer.engine.get_monitors_dict(self.layer.handle)


	def get_player_index(self):
		return self.layer.handle

	def load_file(self):
		self.info = None
		self.widget_canvas.delete("waveform")
		self.widget_canvas.itemconfig("overlay", state=tkinter.HIDDEN)
		try:
			with soundfile.SoundFile(self.filename) as snd:
				self.audio_data = snd.read()
				self.channels = snd.channels
				self.samplerate = snd.samplerate
				self.frames = len(self.audio_data)
				if self.samplerate:
					self.duration = self.frames / self.samplerate
				else:
					self.duration = 0.0
			y0 = self.zoom_height * self.height // self.channels
			for chan in range(self.channels):
				v_offset = chan * y0
				self.widget_canvas.create_rectangle(0, v_offset, self.width, v_offset + y0, fill=zynthian_gui_config.PAD_COLOUR_GROUP[chan // 2 % len(zynthian_gui_config.PAD_COLOUR_GROUP)], tags="waveform", state=tkinter.HIDDEN)
				self.widget_canvas.create_line(0, v_offset + y0 // 2, self.width, v_offset + y0 // 2, fill="grey", tags="waveform", state=tkinter.HIDDEN)
				self.widget_canvas.create_line(0,0,0,0, fill=self.waveform_color, tags=("waveform", f"waveform{chan}"), state=tkinter.HIDDEN)
			self.widget_canvas.tag_raise("waveform")
			self.widget_canvas.tag_raise("overlay")
		except Exception as e:
			logging.warning(e)
		self.refreshing = False
		self.refresh_waveform = True
		self.update()


	def draw_waveform(self, start, length):
		if not self.channels:
			return
		start = max(0, start)
		start = min(self.frames, start)
		length = min(self.frames - start, length)
		limit = max(1, length // self.limit_factor)
		
		frames_per_pixel = length / self.width
		step = frames_per_pixel / limit
		y0 = self.height * self.zoom_height // self.channels

		for chan in range(self.channels):
			pos = start
			data = []
			v_offset = chan * y0
			for x in range(self.width):
				offset = pos
				if self.channels == 1:
					v1 = v2 = self.audio_data[int(offset)]
				else:
					v1 = v2 = self.audio_data[int(offset)][chan]
				while offset < pos + frames_per_pixel and offset < len(self.audio_data):
					if self.channels == 1:
						sample = self.audio_data[int(offset)]
					else:
						sample = self.audio_data[int(offset)][chan]
					if v1 < sample:
						v1 = sample
					if v2 > sample:
						v2 = sample
					offset += step
				v1 *= self.v_zoom
				v1 = min(1.0, v1)
				v1 = max(-1.0, v1)
				v2 *= self.v_zoom
				v2 = min(1.0, v2)
				v2 = max(-1.0, v2)
				y1 = v_offset + int((y0 * (1 + v1)) / 2)
				y2 = v_offset + int((y0 * (1 + v2)) / 2)
				data += [x, y1, x, y2]
				pos += frames_per_pixel
			self.widget_canvas.coords(f"waveform{chan}", data)
		self.refresh_waveform = False


	def refresh_gui(self):
		if self.refreshing:
			return
		self.refreshing = True
		try:
			if self.filename != self.monitors["filename"] or self.frames != self.frames:
				self.filename = self.monitors["filename"]
				waveform_thread = Thread(target=self.load_file, name="waveform image")
				waveform_thread.start()
				return

			if self.duration == 0.0:
				self.refreshing = False
				return

			refresh_markers = False
			loop_start = int(self.samplerate * self.monitors["loop start"])
			loop_end = int(self.samplerate * self.monitors["loop end"])
			crop_start = int(self.samplerate * self.monitors["crop start"])
			crop_end = int(self.samplerate * self.monitors["crop end"])
			pos_time = self.monitors["pos"]
			pos = int(pos_time * self.samplerate)
			refresh_info = False

			if self.monitors["offset"] is not None and self.monitors["offset"] != self.offset:
				offset = self.monitors["offset"]
				self.zoom = self.monitors["zoom"]
			else:
				offset = self.offset
			if self.zoom != self.monitors["zoom"]:
				centre = offset + 0.5 * self.frames / self.zoom
				self.zoom = self.monitors["zoom"]
				offset = int(centre - 0.5 * self.frames / self.zoom)
				self.refresh_waveform = True

			if self.loop_start != loop_start:
				self.loop_start = loop_start
				if self.loop_start < offset or self.loop_start > offset + self.frames // self.zoom:
					offset = int(self.loop_start - 0.25 * self.frames / self.zoom)
				refresh_markers = True

			if self.loop_end != loop_end:
				self.loop_end = loop_end
				if self.loop_end < offset or self.loop_end > offset + self.frames // self.zoom:
					offset = int(self.loop_end - 0.75 * self.frames / self.zoom)
				refresh_markers = True

			if self.crop_start != crop_start:
				self.crop_start = crop_start
				if self.crop_start < offset or self.crop_start > offset + self.frames // self.zoom:
					offset = int(self.crop_start - 0.25 * self.frames / self.zoom)
				refresh_markers = True

			if self.crop_end != crop_end:
				self.crop_end = crop_end
				if self.crop_end < offset or self.crop_end > offset + self.frames // self.zoom:
					offset = int(self.crop_end - 0.75 * self.frames / self.zoom)
				refresh_markers = True

			if self.play_pos != pos:
				self.play_pos = pos
				if pos < offset  or pos > offset + self.frames // self.zoom:
					offset = max(0, pos)
				refresh_markers = True

			offset = max(0, offset)
			offset = min(self.frames - self.frames // self.zoom, offset)
			if offset != self.offset:
				self.offset = offset
				self.refresh_waveform = True

			if self.refresh_waveform:
				self.draw_waveform(offset, self.frames // self.zoom)
				refresh_markers = True

			if refresh_markers:
				h = int(self.zoom_height * self.height)
				f = self.width / self.frames * self.zoom
				x = int(f * (self.loop_start - self.offset))
				self.widget_canvas.coords(self.loop_start_line, x, 0, x, h)
				x = int(f * (self.loop_end - self.offset))
				self.widget_canvas.coords(self.loop_end_line, x, 0, x, h)
				x = int(f * (self.crop_start - self.offset))
				self.widget_canvas.coords(self.crop_start_rect, 0, 0, x, h)
				x = int(f * (self.crop_end - self.offset))
				self.widget_canvas.coords(self.crop_end_rect, x, 0, self.width, h)
				x = int(f * (pos - self.offset))
				self.widget_canvas.coords(self.play_line, x, 0, x, h)
				refresh_info = True


			if self.monitors["info"] != self.info:
				self.widget_canvas.itemconfig("waveform", state=tkinter.NORMAL)
				self.widget_canvas.itemconfig("overlay", state=tkinter.NORMAL)
				self.info = self.monitors["info"]
				refresh_info = True

			if refresh_info:
				zoom_offset = self.width * offset // self.frames
				self.widget_canvas.coords(self.zoom_rect, zoom_offset, int(self.zoom_height * self.height), zoom_offset + max(1, self.width // self.zoom), self.height)
				if self.info == 1:
					time = (self.crop_end - self.crop_start) / self.samplerate
					self.widget_canvas.itemconfigure(self.info_text, text=f"Duration: {self.format_time(time)}", state=tkinter.NORMAL)
				elif self.info == 2:
					time = max(0, pos - self.crop_start) / self.samplerate
					self.widget_canvas.itemconfigure(self.info_text, text=f"Position: {self.format_time(time)}", state=tkinter.NORMAL)
				elif self.info == 3:
					time = max(0, self.crop_end - pos) / self.samplerate
					self.widget_canvas.itemconfigure(self.info_text, text=f"Remaining: {self.format_time(time)}", state=tkinter.NORMAL)
				elif self.info == 4:
					time = (self.loop_end - self.loop_start) / self.samplerate
					self.widget_canvas.itemconfigure(self.info_text, text=f"Loop length: {self.format_time(time)}", state=tkinter.NORMAL)
				elif self.info == 5:
					self.widget_canvas.itemconfig(self.info_text, text=f"Samplerate: {self.samplerate}", state=tkinter.NORMAL)
				elif self.info == 6:
					self.widget_canvas.itemconfig(self.info_text, text=f"CODEC: {self.monitors['codec']}", state=tkinter.NORMAL)
				elif self.info == 7:
					self.widget_canvas.itemconfig(self.info_text, text=f"Filename: {basename(self.filename)}", state=tkinter.NORMAL)
				else:
					self.widget_canvas.itemconfig(self.info_text, state=tkinter.HIDDEN)

		except Exception as e:
			logging.error(e)
		
		self.refreshing = False


	def format_time(self, time):
		return f"{int(time / 60):02d}:{int(time % 60):02d}.{int(modf(time)[0] * 1000):03}"


	def cb_canvas_wheel(self, event):
		try:
			if event.num == 5 or event.delta == -120:
				if event.state == 1: # Shift
					self.layer.controllers_dict['loop start'].nudge(-1)
				elif event.state == 5: # Shift+Ctrl
					self.layer.controllers_dict['loop end'].nudge(-1)
				elif event.state == 4: # Ctrl
					self.layer.controllers_dict['zoom'].nudge(-1)
				elif event.state == 8: # Alt
					self.offset = max(0, self.offset - self.frames // self.zoom // 10)
					self.refresh_waveform = True
				else:
					self.layer.controllers_dict['position'].nudge(-1)
			elif event.num == 4 or event.delta == 120:
				if event.state == 1: # Shift
					self.layer.controllers_dict['loop start'].nudge(1)
				elif event.state == 5: # Shift+Ctrl
					self.layer.controllers_dict['loop end'].nudge(1)
				elif event.state == 4: # Ctrl
					self.layer.controllers_dict['zoom'].nudge(1)
				elif event.state == 8: # Alt
					self.offset = min(self.frames - self.frames // self.zoom, self.offset + self.frames // self.zoom // 10)
					self.refresh_waveform = True
				else:
					self.layer.controllers_dict['position'].nudge(1)
		except Exception as e:
			logging.debug("Failed to change value")


	def cuia_toggle_record(self):
		if self.zyngui.audio_recorder.get_status():
			self.layer.controllers_dict['record'].set_value("stopped")
		else:
			self.layer.controllers_dict['record'].set_value("recording")


	def cuia_stop(self):
		i = self.get_player_index()
		self.layer.engine.player.stop_playback(i)
		self.layer.engine.player.set_position(i, 0.0)


	def cuia_toggle_play(self):
		i = self.get_player_index()
		if self.layer.engine.player.get_playback_state(i):
			self.layer.engine.player.stop_playback(i)
		else:
			self.layer.engine.player.start_playback(i)


	def update_wsleds(self, wsleds):
		wsl = self.zyngui.wsleds
		i = self.get_player_index()
		if i == 16:
			color_default = wsl.wscolor_default
		else:
			color_default = wsl.wscolor_active2
		# REC Button
		if self.zyngui.audio_recorder.get_status():
			wsl.wsleds.setPixelColor(wsleds[0], wsl.wscolor_red)
		else:
			wsl.wsleds.setPixelColor(wsleds[0], color_default)
		# STOP button
		wsl.wsleds.setPixelColor(wsleds[1], color_default)
		# PLAY button:
		if self.layer.engine.player.get_playback_state(i):
			wsl.wsleds.setPixelColor(wsleds[2], wsl.wscolor_green)
		else:
			wsl.wsleds.setPixelColor(wsleds[2], color_default)


#------------------------------------------------------------------------------
