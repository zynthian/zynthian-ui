#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Touchscreen Calibration Class
# 
# Copyright (C) 2020 Brian Walton <brian@riban.co.uk>
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

import tkinter
import logging
import tkinter.font as tkFont
from threading import Timer, Thread
from subprocess import run,PIPE
from datetime import datetime # Only to timestamp config file updates
from evdev import InputDevice, ecodes
from select import select
import os

# Zynthian specific modules
from . import zynthian_gui_config

# Little class to represent x,y coordinates
class point:
	x = 0.0
	y = 0.0
	def __init__(self, x=0, y=0):
		self.x = x
		self.y = y

#------------------------------------------------------------------------------
# Zynthian Touchscreen Calibration GUI Class
#------------------------------------------------------------------------------


# Class implements zynthian touchscreen calibration
class zynthian_gui_touchscreen_calibration:

	# Function to initialise class
	def __init__(self):
		self.shown=False
		self.zyngui=zynthian_gui_config.zyngui
		self.height = zynthian_gui_config.display_height
		self.width = zynthian_gui_config.display_width
		self.debounce = 0.5 * self.height # Touches cannot be closer than this

		# Main Frame
		self.main_frame = tkinter.Frame(zynthian_gui_config.top,
			width = self.width,
			height = self.height,
			bg = zynthian_gui_config.color_bg,
			cursor="none")

		# Canvas
		self.canvas = tkinter.Canvas(self.main_frame,
			height = self.height,
			width = self.width,
			bg="black",
			bd=0,
			highlightthickness=0)
		
		# Instruction text
		self.instruction_text = self.canvas.create_text(self.width / 2,
			self.height / 2 - zynthian_gui_config.font_size * 2,
			font=(zynthian_gui_config.font_family,zynthian_gui_config.font_size,"normal"),
			fill="white",
			text="Touch each crosshair")
		self.device_text = self.canvas.create_text(self.width / 2,
			self.height - zynthian_gui_config.font_size * 2,
			font=(zynthian_gui_config.font_family,zynthian_gui_config.font_size,"normal"),
			fill="white")

		# Countdown timer
		self.countdown_text = self.canvas.create_text(self.width / 2,
			self.height / 2,
			font=(zynthian_gui_config.font_family,zynthian_gui_config.font_size,"normal"),
			fill="red")
		self.timer = Timer(interval=1, function=self.onTimer)
		self.timeout = 15 # Period in seconds after last touch until sceen closes with no change
		self.pressed = False # True if screen pressed
		
		# Coordinate transform matrix
		self.identify_matrix = [1,0,0, 0,1,0, 0,0,1]
		self.display_points = [point(self.width * 0.15, self.height * 0.15), point(self.width * 0.85, self.height * 0.85)]
		self.touch_points = [point(), point()]
		
		# Crosshair
		self.index = 0 # Index of current calibration point (0=NW, 1=SE)
		self.crosshair_size = self.width / 20 # half width of cross hairs
		self.crosshair_circle = self.canvas.create_oval(
			self.display_points[self.index].x - self.crosshair_size * 0.8, self.display_points[self.index].y - self.crosshair_size * 0.8,
			self.display_points[self.index].x + self.crosshair_size * 0.8, self.display_points[self.index].y + self.crosshair_size * 0.8,
			width=3, outline="white", tags=("crosshairs","crosshairs_circles"))
		self.crosshair_inner_circle = self.canvas.create_oval(
			self.display_points[self.index].x - self.crosshair_size * 0.2, self.display_points[self.index].y - self.crosshair_size * 0.2,
			self.display_points[self.index].x + self.crosshair_size * 0.2, self.display_points[self.index].y + self.crosshair_size * 0.2,
			width=3, outline="white", tags=("crosshairs","crosshairs_circles"))
		self.crosshair_vertical = self.canvas.create_line(
			self.display_points[self.index].x, self.display_points[self.index].y - self.crosshair_size,
			self.display_points[self.index].x, self.display_points[self.index].y - self.crosshair_size,
			width=3, fill="white", tags=("crosshairs","crosshairs_lines"))
		self.crosshair_horizontal = self.canvas.create_line(
			self.display_points[self.index].x - self.crosshair_size, self.display_points[self.index].y,
			self.display_points[self.index].x + self.crosshair_size, self.display_points[self.index].y,
			width=3, fill="white", tags=("crosshairs","crosshairs_lines"))
		
		self.canvas.pack()
		self.device_name = None # Name of selected device
		self.ctm = [0.0 for i in range(9)] # Coordinate Transformation Matrix


	#	Run xinput
	#	args: List of arguments to pass to xinput
	#	Returns: Output of xinput as string
	#	Credit: https://github.com/reinderien/xcalibrate
	def xinput(self, *args):
		return run(args=('/usr/bin/xinput', *args),
			stdout=PIPE, check=True,
			universal_newlines=True).stdout


	#	Tread waiting for first touch to detect touch interface
	def detectDevice(self):
		# Populate list of absolute x/y devices
		devices = []
		for filename in os.listdir("/dev/input"):
			if filename.startswith("event"):
				device = InputDevice("/dev/input/%s" % (filename))
				if ecodes.EV_ABS in device.capabilities().keys():
					devices.append(device)
		# Loop until we get a touch button event or the view hides
		running = True
		while running and self.shown:
			r, w, x = select(devices, [], []) # Wait for any of the devices to trigger an event
			for device in r: # Iterate through all devices that have triggered events
				for event in device.read(): # Iterate through all events from each device
					if event.code == ecodes.BTN_TOUCH: #TODO: Handle other button press - can we use ecode.BTN?
						self.setDevice(device.name)
						self.canvas.bind('<Button-1>', self.onPress)
						self.canvas.bind('<ButtonRelease-1>', self.onRelease)
						running = False


	#	Set the device to configure
	#	name: Device name
	def setDevice(self, name):
		#TODO: The evdev name and xinput name do not necessarily match - we could use evdev to set values
		self.device_name = name
		self.canvas.itemconfig(self.device_text, text=name)
		#TODO: Do we need to set ctm here?
		props = self.xinput('--list-props', name)
		ctm_start = props.find('Coordinate Transformation Matrix')
		ctm_end = props.find("\n", ctm_start)
		if ctm_start < 0 or ctm_end < 0:
			return
		ctm_start += 40
		node_start = props.find('Device Node')
		node_start = props.find('"', node_start)
		node_end = props.find('"', node_start + 1)
		if node_start < 0 or node_end < 0:
			return
		self.ctm = [float(x) for x in props[ctm_start:ctm_end].split(', ')]
		
	
	#	Handle touch press event
	#	event: Event including x,y coordinates
	def onPress(self, event):
		#TODO: First calibration does not stop countdown
		self.canvas.itemconfig("crosshairs_lines", fill="red")
		self.canvas.itemconfig("crosshairs_circles", outline="red")
		self.pressed = True


	#	Handle touch release event
	#	event: Event including x,y coordinates
	def onRelease(self, event):
		self.canvas.itemconfig("crosshairs_lines", fill="white")
		self.canvas.itemconfig("crosshairs_circles", outline="white")
		self.pressed = False
		self.countdown = self.timeout
		if not self.device_name:
				return
		if self.index < 2:
			# More points to acquire
			self.touch_points[self.index].x = event.x
			self.touch_points[self.index].y = event.y
			self.index += 1
		if self.index > 1:
			# Debounce
			if abs(self.touch_points[0].x - self.touch_points[1].x) < self.debounce and abs(self.touch_points[0].y - self.touch_points[1].y) < self.debounce:
				self.index = 0
			else:
				min_x = self.touch_points[0].x
				max_x = self.touch_points[1].x
				min_y = self.touch_points[0].y
				max_y = self.touch_points[1].y
				if min_x == max_x or min_y == max_y:
					return #TODO: Check if this condition causes issue elsewhere
				# Check for rotation
				a = self.width * 0.7 / (max_x - min_x)
				if min_x < max_x:
					c = (self.width * 0.15 - a * min_x) / self.width
				else:
					c = (self.width * 0.15 - a * min_x) / self.width
				e = self.height * 0.7 / (max_y - min_y)
				if min_y < max_y:
					f = (self.height * 0.15 - e * min_y) / self.height
				else:
					f = (self.height * 0.15 - e * min_y) / self.height
				self.setCalibration(self.device_name, [a, 0, c, 0, e, f, 0, 0, 1], True)
				#TODO: Allow user to check calibration
				self.hide()
				return
		self.drawCross()

	
	#	Draws the crosshairs for touch registration for current index (0..1)
	def drawCross(self):
		if self.index > 1:
			return
		self.canvas.coords(self.crosshair_vertical,
			self.display_points[self.index].x, self.display_points[self.index].y - self.crosshair_size,
			self.display_points[self.index].x, self.display_points[self.index].y + self.crosshair_size)
		self.canvas.coords(self.crosshair_horizontal,
			self.display_points[self.index].x - self.crosshair_size, self.display_points[self.index].y,
			self.display_points[self.index].x + self.crosshair_size, self.display_points[self.index].y)
		self.canvas.coords(self.crosshair_circle,
			self.display_points[self.index].x - self.crosshair_size * 0.8, self.display_points[self.index].y - self.crosshair_size * 0.8,
			self.display_points[self.index].x + self.crosshair_size * 0.8, self.display_points[self.index].y + self.crosshair_size * 0.8)
		self.canvas.coords(self.crosshair_inner_circle,
			self.display_points[self.index].x - self.crosshair_size * 0.2, self.display_points[self.index].y - self.crosshair_size * 0.2,
			self.display_points[self.index].x + self.crosshair_size * 0.2, self.display_points[self.index].y + self.crosshair_size * 0.2)
		self.canvas.itemconfig("crosshairs", state=tkinter.NORMAL)


	#	Apply screen calibration
	#	device: Name or ID of device to calibrate
	#	matrix: Transform matrix as 9 element array (3x3)
	#	write_file: True to write configuration to file (default: false)
	def setCalibration(self, device, matrix, write_file=False):
		try:
			logging.debug("Touchscreen calibration %s matrix [%f %f %f %f %f %f %f %f %f]", 
				device,
				matrix[0],
				matrix[1],
				matrix[2],
				matrix[3],
				matrix[4],
				matrix[5],
				matrix[6],
				matrix[7],
				matrix[8])
			self.xinput("--set-prop", device, "Coordinate Transformation Matrix",
				str(matrix[0]), str(matrix[1]), str(matrix[2]), str(matrix[3]), str(matrix[4]), str(matrix[5]), str(matrix[6]), str(matrix[7]), str(matrix[8]))
			if write_file:
				# Update config file
				try:
					f = open("/etc/X11/xorg.conf.d/99-calibration.conf", "r")
					config = f.read()
					section_start = config.find('Section "InputClass"')
					while section_start >= 0:
						section_end = config.find('EndSection', section_start)
						if section_end > section_start and config.find('MatchProduct "%s'%(device), section_start, section_end) > section_start:
							tm_start = config.find('Option "TransformationMatrix"', section_start, section_end)
							tm_end = config.find('\n', tm_start, section_end)
							if tm_start > section_start and tm_end > tm_start:
								f = open("/etc/X11/xorg.conf.d/99-calibration.conf", "w")
								f.write(config[:tm_start + 29])
								f.write(' "%f %f %f %f %f %f %f %f %f"' % (matrix[0], matrix[1], matrix[2], matrix[3], matrix[4], matrix[5], matrix[6], matrix[7], matrix[8]))
								f.write(' # updated %s'%(datetime.now()))
								f.write(config[tm_end:])
								f.close()
								return
				except:
					pass # File probably does not yet exist
				# If we got here then we need to append this device to config
				f = open("/etc/X11/xorg.conf.d/99-calibration.conf", "a")
				f.write('\nSection "InputClass" # Created %s\n'%(datetime.now()))
				f.write('	Identifier "calibration"\n')
				f.write('	MatchProduct "%s"\n'%(device))
				f.write('	Option "TransformationMatrix" "%f %f %f %f %f %f %f %f %f"\n' % (matrix[0], matrix[1], matrix[2], matrix[3], matrix[4], matrix[5], matrix[6], matrix[7], matrix[8]))
				f.write('EndSection\n')
				f.close()
		except Exception as e:
			logging.warning("Failed to set touchscreen calibration", e)
	

	#	Hide display
	def hide(self):
		if self.shown:
			self.shown=False
			self.timer.cancel()
			self.main_frame.grid_forget()
			self.zyngui.show_screen(self.zyngui.active_screen)


	# 	Show display
	def show(self):
		if not self.shown:
			self.shown=True
			self.device_name = None
			self.canvas.itemconfig(self.countdown_text, text="Closing in %ds" % (self.timeout))
			self.canvas.itemconfig(self.device_text, text="")
			self.countdown = self.timeout
			self.index = 0
			self.drawCross()
			self.main_frame.grid()
			self.onTimer()
			self.detect_thread = Thread(target=self.detectDevice, args=(), daemon=True)
			self.detect_thread.start()


	#	Handle one second timer trigger
	def onTimer(self):
		if self.shown:
			self.canvas.itemconfig(self.countdown_text, text="Closing in %ds" % (self.countdown))
			if self.countdown <= 0:
				self.hide()
				return
			if not self.pressed:
				self.countdown -= 1
			self.timer = Timer(interval=1, function=self.onTimer)
			self.timer.start()


	#	Handle zyncoder read - called by parent when zyncoders updated
	def zyncoder_read(self):
		pass


	#	Handle refresh loading - called by parent during screen load
	def refresh_loading(self):
		pass

	
	#	Handle physical switch press
	#	type: Switch duration type (default: short)
	def switch_select(self, type='S'):
		pass


	#	Handle BACK button action
	def back_action(self):
		self.hide()
		return self.zyngui.active_screen

#-------------------------------------------------------------------------------
