#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian Widget Class for "Zynthian Audio Player" (zynaudioplayer#one)
# 
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
# Copyright (C) 2015-2022 Brian Walton <riban@zynthian.org>
#
# Depends on https://github.com/bbc/audiowaveform
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
from PIL import Image, ImageTk
import os
import logging

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base

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
		self.filename = "?"
		self.duration = 0.0
		self.samplerate = 44100
		self.bg_color = "000000"
		self.waveform_color = "6070B0"
		self.image = None
		self.image_hires = None
		self.loading_image = False
		self.zoom = 1.0
		self.offset_factor = 0

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
			text="Creating\nwaveform..."
		)
		
		self.waveform = self.widget_canvas.create_image(
			0,
			0,
			anchor=tkinter.NW,
			state=tkinter.HIDDEN
		)

		self.play_line = self.widget_canvas.create_line(
			0,
			0,
			0,
			self.height,
			fill=zynthian_gui_config.color_on
		)

		self.loop_start_line = self.widget_canvas.create_line(
			0,
			0,
			0,
			self.height,
			fill=zynthian_gui_config.color_ml,
			#state=tkinter.HIDDEN # loop markers currently disabled
		)

		self.loop_end_line = self.widget_canvas.create_line(
			self.width,
			0,
			self.width,
			self.height,
			fill=zynthian_gui_config.color_ml,
			#state=tkinter.HIDDEN # loop markers currently disabled
		)

		self.info_text = self.widget_canvas.create_text(
			self.width-int(0.5 * zynthian_gui_config.font_size),
			self.height,
			anchor = tkinter.SE,
			justify=tkinter.RIGHT,
			width=self.width,
			font=(zynthian_gui_config.font_family, int(1.5 * zynthian_gui_config.font_size)),
			fill=zynthian_gui_config.color_panel_tx,
			text="00:00"
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
		if self.image:
			try:
				self.img = ImageTk.PhotoImage(self.image.resize((self.width, self.height)))
				self.widget_canvas.itemconfigure(self.waveform, image=self.img, state=tkinter.NORMAL)
			except:
				if self.image:
					self.image.close()
					self.image = None
				self.widget_canvas.itemconfigure(self.loading_text, text="Cannot\ndisplay\nwaveform")


	def get_monitors(self):
		self.monitors = self.layer.engine.get_monitors_dict(self.layer.midi_chan)


	def get_player_index(self):
		return self.layer.midi_chan if self.layer.midi_chan < 16 else 16


	def refresh_gui(self):
		if self.refreshing:
			return
		self.refreshing = True
		try:
			dur = self.monitors["duration"]
			pos = self.monitors["pos"]

			if self.monitors["zoom"] and self.zoom != self.monitors["zoom"]:
				self.zoom = self.monitors["zoom"]
				self.offset_factor = max(0, (pos - dur / self.zoom / 2) / dur)
				self.offset_factor = min(self.offset_factor, 1 - 1 / self.zoom)
				if self.image:
					x = int(self.offset_factor * self.image.width)
					w = int(self.image.width / self.zoom)
					self.img = ImageTk.PhotoImage(self.image.crop((x, 0, x + w, 800)).resize((self.width, self.height)))
					self.widget_canvas.itemconfigure(self.waveform, image=self.img, state=tkinter.NORMAL)
					self.play_pos = self.loop_start = self.loop_end = -1 # Force redraw of markers

			if self.play_pos != pos:
				self.play_pos = pos
				if dur:
					x = int(self.width * self.zoom * (pos / dur - self.offset_factor))
				else:
					x = 0
				self.widget_canvas.coords(self.play_line, x, 0, x, self.height)

			loop_start = self.monitors["loop start"]
			if self.loop_start != loop_start:
				self.loop_start = loop_start
				if dur:
					x = int(self.width * self.zoom * (loop_start / dur - self.offset_factor))
				else:
					x = 0
				self.widget_canvas.coords(self.loop_start_line, x, 0, x, self.height)

			loop_end = self.monitors["loop end"]
			if self.loop_end != loop_end:
				self.loop_end = loop_end
				if dur:
					x = int(self.width * self.zoom * (loop_end / dur - self.offset_factor))
				else:
					x = 0
				self.widget_canvas.coords(self.loop_end_line, x, 0, x, self.height)

			if self.filename != self.monitors["filename"] or self.duration != dur:
				if(dur):
					waveform_thread = Thread(target=self.load_image, name="waveform image")
					waveform_thread.start()
				else:
					self.widget_canvas.itemconfigure(self.loading_text, text="No\nfile\nloaded")
					self.widget_canvas.itemconfigure(self.waveform, state=tkinter.HIDDEN)
			if self.duration != dur:
				self.duration = dur
				sr = self.monitors["samplerate"]
				self.widget_canvas.itemconfigure(self.info_text, text="{:02d}:{:02d} ({:d})".format(int(dur / 60), int(dur % 60), sr), state=tkinter.NORMAL)
	
		except Exception as e:
			logging.error(e)
		
		self.refreshing = False


	def load_image(self):
		if self.loading_image:
			return
		self.loading_image = True
		self.widget_canvas.itemconfigure(self.waveform, state=tkinter.HIDDEN)
		self.widget_canvas.itemconfigure(self.loading_text, text="Creating\nwaveform...")
		waveform_png = "{}.png".format(self.monitors["filename"])
		self.filename = self.monitors["filename"]
		try:
			self.image = Image.open(waveform_png)
			rebuild = os.path.getmtime(self.filename) > os.path.getmtime(waveform_png)
		except:
			rebuild = True

		if rebuild:
			if self.image:
				self.image.close()
			self.image = None
			cmd = 'audiowaveform -i "{}" -o "{}" --split-channels -w {} -h {} --zoom auto --background-color {} --waveform-color {} --no-axis-labels > /dev/null 2>&1'.format(
				self.filename,
				waveform_png,
				1024,
				800,
				#self.bg_color,
				"444444",
				self.waveform_color
			)
			os.system(cmd)
		try:
			if self.image is None:
				self.image = Image.open(waveform_png)
			self.img = ImageTk.PhotoImage(self.image.resize((self.width, self.height)))
			self.widget_canvas.itemconfigure(self.waveform, image=self.img, state=tkinter.NORMAL)
		except:
			if self.image:
				self.image.close()
				self.image = None
			self.widget_canvas.itemconfigure(self.loading_text, text="Cannot\ndisplay\nwaveform")

		# Rebuild image with high resolution
		if rebuild and self.image:
			frames = self.duration * self.monitors["samplerate"]
			width = int(min(frames / 60, 150000))

			cmd = 'audiowaveform -i "{}" -o "{}" --split-channels -w {} -h {} --zoom auto --background-color {} --waveform-color {} --no-axis-labels > /dev/null 2>&1'.format(
				self.filename,
				waveform_png,
				width,
				800,
				self.bg_color,
				self.waveform_color
			)
			os.system(cmd)
		try:
			self.image = Image.open(waveform_png)
			self.img = ImageTk.PhotoImage(self.image.resize((self.width, self.height)))
			self.widget_canvas.itemconfigure(self.waveform, image=self.img, state=tkinter.NORMAL)
		except:
			if self.image:
				self.image.close()
				self.image = None
			self.widget_canvas.itemconfigure(self.loading_text, text="Cannot\ndisplay\nwaveform")

		self.loading_image = False
	

	def cb_canvas_wheel(self, event):
		try:
			if event.num == 5 or event.delta == -120:
				self.layer.controllers_dict['position'].nudge(-1)
			if event.num == 4 or event.delta == 120:
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
