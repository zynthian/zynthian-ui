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
from zyngui import zynthian_gui_config

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
		self.shown = False
		self.zyngui=zynthian_gui_config.zyngui
		self.height = zynthian_gui_config.display_height
		self.width = zynthian_gui_config.display_width
		self.debounce = 0.5 * self.height # Clicks cannot be closer than this

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
				
		# Coordinate transform matrix
		self.display_points = [point(self.width * 0.15, self.height * 0.15),
			point(self.width * 0.85, self.height * 0.85),
			point(self.width * 0.5, self.height * 0.5)]
		self.touch_points = [point(), point()] # List of touch point results
		
		# Crosshair target
		self.index = 2 # Index of current calibration point (0=NW, 1=SE, 2=CENTRE)
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

		# Countdown timer
		self.countdown_text = self.canvas.create_text(self.width / 2,
			self.height / 2 - self.crosshair_size - zynthian_gui_config.font_size - 2,
			font=(zynthian_gui_config.font_family, zynthian_gui_config.font_size, "normal"),
			fill="red")
		self.timer = Timer(interval=1, function=self.onTimer)
		self.timeout = 15 # Period in seconds after last touch until sceen closes with no change
		self.pressed = False # True if screen pressed

		# Instruction text
		self.instruction_text = self.canvas.create_text(self.width / 2,
			self.height / 2 + self.crosshair_size + 2 + zynthian_gui_config.font_size * 2,
			font=(zynthian_gui_config.font_family, zynthian_gui_config.font_size, "normal"),
			fill="white",
			text="Touch crosshairs using a stylus")
		self.device_text = self.canvas.create_text(self.width / 2,
			self.height - zynthian_gui_config.font_size * 2,
			font=(zynthian_gui_config.font_family, zynthian_gui_config.font_size, "normal"),
			fill="white")

		self.device_name = None # libinput name of selected device
		

	#	Run xinput
	#	args: List of arguments to pass to xinput
	#	Returns: Output of xinput as string
	#	Credit: https://github.com/reinderien/xcalibrate
	def xinput(self, *args):
		try:
			return run(args=('/usr/bin/xinput', *args),
				stdout=PIPE, check=True,
				universal_newlines=True).stdout
		except:
			return ""


	#	Thread waiting for first touch to detect touch interface
	def detectDevice(self):
		# Populate list of absolute x/y devices
		devices = []
		for filename in os.listdir("/dev/input"):
			if filename.startswith("event"):
				device = InputDevice("/dev/input/%s" % (filename))
				if ecodes.EV_ABS in device.capabilities().keys():
					devices.append(device)
		# Loop until we get a touch button event or the view hides
		self.running = True
		while self.running and self.shown:
			r, w, x = select(devices, [], []) # Wait for any of the devices to trigger an event
			if self.running:
				for device in r: # Iterate through all devices that have triggered events
					for event in device.read(): # Iterate through all events from each device
						if event.code == ecodes.BTN_TOUCH:
							if event.value:
								self.canvas.itemconfig("crosshairs_lines", fill="red")
								self.canvas.itemconfig("crosshairs_circles", outline="red")
								self.pressed = True
								self.countdown = self.timeout
								self.setDevice(device.name, device.path)
							else:
								self.canvas.itemconfig("crosshairs_lines", fill="white")
								self.canvas.itemconfig("crosshairs_circles", outline="white")
								self.pressed = False
								self.countdown = self.timeout
								if self.device_name:
									self.index = 0
									self.drawCross()
									self.canvas.bind('<Button-1>', self.onPress)
									self.canvas.bind('<ButtonRelease-1>', self.onRelease)
									self.running = False


	#	Set the device to configure
	#	name: evdev device name
	#	path: Path to device, e.g. '/dev/input/event0'
	#	Returns: True on success
	def setDevice(self, name, path):
		# Transform evdev name to libinput name
		props = None
		for libinput_name in self.xinput("--list", "--name-only").split("\n"):
			props_temp = self.xinput('--list-props', libinput_name)
			if props_temp.find(path) != -1:
				props = props_temp
				break
		if not props:
			return False
		self.device_name = libinput_name
		self.canvas.itemconfig(self.device_text, text=name)
		props = self.xinput('--list-props', self.device_name)
		ctm_start = props.find('Coordinate Transformation Matrix')
		ctm_end = props.find("\n", ctm_start)
		if ctm_start < 0 or ctm_end < 0:
			return False
		ctm_start += 40
		node_start = props.find('Device Node')
		node_start = props.find('"', node_start)
		node_end = props.find('"', node_start + 1)
		if node_start < 0 or node_end < 0:
			return False
		# Store CTM to allow restore if we cancel calibration
		self.ctm = []
		for value in props[ctm_start:ctm_end].split(", "):
			self.ctm.append(float(value))
		self.node = props[node_start:node_end] # Get node name to allow mapping between evdev and xinput names
		self.setCalibration(self.device_name, [1,0,0,0,1,0,0,0,1]) # Reset calibration to allow absolute acquisition
		return True


	#	Handle touch press event
	#	event: Event including x,y coordinates (optional)
	def onPress(self, event=None):
		if self.device_name and not self.pressed:
			self.canvas.itemconfig("crosshairs_lines", fill="red")
			self.canvas.itemconfig("crosshairs_circles", outline="red")
			self.pressed = True


	#	Handle touch release event
	#	event: Event including x,y coordinates
	def onRelease(self, event):
		self.canvas.itemconfig("crosshairs_lines", fill="white")
		self.canvas.itemconfig("crosshairs_circles", outline="white")
		if not self.pressed:
			return
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
				x0 = self.touch_points[0].x
				x1 = self.touch_points[1].x
				y0 = self.touch_points[0].y
				y1 = self.touch_points[1].y
				if x0 == x1 or y0 == y1:
					self.index = 0
					self.drawCross()
					return
				# Acquisition complete - calculate calibration data
				min_x = min(x0, x1)
				max_x = max(x0, x1)
				min_y = min(y0, y1)
				max_y = max(y0, y1)
				dx = max_x - min_x
				dy = max_y - min_y
				if x0 < x1:
					if y0 < y1:
						# No rotation
						a = self.width * 0.7 / dx # Scaling factor of x-axis from pointer x coord
						b = 0 # Scaling factor of y-axis from pointer x coord
						c = (0.15 * self.width / a - min_x) / self.width # Offset to add to x-axis
						d = 0 # Scaling factor of x-axis from pointer y coord
						e = self.height * 0.7 / dy # Scaling factor of y-axis from pointer y coord
						f = (0.15 * self.height / e - min_y) / self.width # Offset to add to y-axis
					else:
						# Rotated 90 CW
						a = 0
						b = -self.height * 0.7 / dy
						c = 1 + (0.15 * self.height / b + min_y) / self.height
						d = self.width * 0.7 / dx
						e = 0
						f = (0.15 * self.width / d - min_x) / self.width
				else:
					if y0 < y1:
						# Rotated 90 CCW (270 CW)
						a = 0
						b = self.height * 0.7 / dy
						c = (0.15 * self.height / b - min_y) / self.height
						d = -self.width * 0.7 / dx
						e = 0
						f = 1 + (0.15 * self.width / d + min_x) / self.width
					else:
						# Rotated 180
						a = -self.width * 0.7 / dx
						b = 0
						c = 1 + (0.15 * self.width / a + min_x) / self.width
						d = 0
						e = -self.height * 0.7 / dy
						f = 1 + (0.15 * self.height / e + min_y) / self.height

				self.ctm = [a, b, c, d, e, f, 0, 0, 1]
				self.setCalibration(self.device_name, self.ctm, True)

				#TODO: Allow user to check calibration

				self.zyngui.zynswitch_defered('S',1)
				return

		self.drawCross()

	
	#	Draws the crosshairs for touch registration for current index (0=NW,1=SE,2=CENTRE)
	def drawCross(self):
		if self.index > 2:
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


	#	Apply screen calibration
	#	device: libinput name or ID of device to calibrate
	#	matrix: Transform matrix as 9 element array (3x3)
	#	write_file: True to write configuration to file (default: false)
	def setCalibration(self, device, matrix, write_file=False):
		try:
			logging.debug("Calibration touchscreen '%s' with matrix [%f %f %f %f %f %f %f %f %f]", 
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
				# Update exsting config in file
				"""
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
						section_start = config.find('Section "InputClass"', section_end)
				except:
					pass # File probably does not yet exist
				"""
				# If we got here then we need to append this device to config
				# For the record it is with deep reservation that I code this duplicate writing of files - I was only follwing orders!
				try:
					os.mkdir(os.environ.get("ZYNTHIAN_CONFIG_DIR") + "/touchscreen/")
				except:
					pass # directory already exists
				with open(os.environ.get("ZYNTHIAN_CONFIG_DIR") + "/touchscreen/" + os.environ.get("DISPLAY_NAME"), "w") as f:
					f.write('Section "InputClass" # Created %s\n'%(datetime.now()))
					f.write('	Identifier "calibration"\n')
					f.write('	MatchProduct "%s"\n'%(device))
					f.write('	Option "TransformationMatrix" "%f %f %f %f %f %f %f %f %f"\n' % (matrix[0], matrix[1], matrix[2], matrix[3], matrix[4], matrix[5], matrix[6], matrix[7], matrix[8]))
					f.write('EndSection\n')
				with open("/etc/X11/xorg.conf.d/99-calibration.conf", "w") as f:
					f.write('Section "InputClass" # Created %s\n'%(datetime.now()))
					f.write('	Identifier "calibration"\n')
					f.write('	MatchProduct "%s"\n'%(device))
					f.write('	Option "TransformationMatrix" "%f %f %f %f %f %f %f %f %f"\n' % (matrix[0], matrix[1], matrix[2], matrix[3], matrix[4], matrix[5], matrix[6], matrix[7], matrix[8]))
					f.write('EndSection\n')
		except Exception as e:
			logging.warning("Failed to set touchscreen calibration", e)


	#	Hide display
	def hide(self):
		if self.shown:
			self.timer.cancel()
			self.running = False
			self.setCalibration(self.device_name, self.ctm)
			self.main_frame.grid_forget()
			self.shown=False


	# 	Show display
	def show(self):
		if not self.shown:
			self.shown=True
			self.device_name = None
			self.ctm = [1,0,0,0,1,0,0,0,1]
			self.canvas.unbind('<Button-1>')
			self.canvas.unbind('<ButtonRelease-1>')
			self.canvas.itemconfig(self.countdown_text, text="Closing in %ds" % (self.timeout))
			self.canvas.itemconfig(self.device_text, text="")
			self.countdown = self.timeout
			self.index = 2
			self.drawCross()
			self.main_frame.grid()
			self.onTimer()
			self.detect_thread = Thread(target=self.detectDevice, args=(), daemon=True)
			self.detect_thread.name = "touchscreen calibrate"
			self.detect_thread.start()


	#	Handle one second timer trigger
	def onTimer(self):
		if self.shown:
			self.canvas.itemconfig(self.countdown_text, text="Closing in %ds" % (self.countdown))
			if self.countdown <= 0:
				self.zyngui.zynswitch_defered('S',1)
				return
			if not self.pressed:
				self.countdown -= 1
			self.timer = Timer(interval=1, function=self.onTimer)
			self.timer.start()


	#	Handle zyncoder read - called by parent when zyncoders updated
	def zynpot_cb(self, i, dval):
		pass


	#	Handle refresh loading - called by parent during screen load
	def refresh_loading(self):
		pass

	
	#	Handle physical switch press
	#	type: Switch duration type (default: short)
	def switch_select(self, type='S'):
		pass


#-------------------------------------------------------------------------------
