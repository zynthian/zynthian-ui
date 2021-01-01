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
from PIL import Image, ImageTk
from threading import Timer
from subprocess import run,PIPE

# Zynthian specific modules
from . import zynthian_gui_config

import time

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

		# Main Frame
		self.main_frame = tkinter.Frame(zynthian_gui_config.top,
			width = self.width,
			height = self.height,
			bg = zynthian_gui_config.color_bg)

		# Canvas
		self.canvas = tkinter.Canvas(self.main_frame,
			height = self.height,
			width = self.width,
			bg="black",
			bd=0,
			highlightthickness=0)
		self.canvas.bind('<ButtonRelease-1>', self.onRelease)
		self.canvas.bind('<Button-1>', self.onPress)
		
		# Instruction text
		self.instruction_text = self.canvas.create_text(self.width / 2,
			self.height / 2 - zynthian_gui_config.font_size * 2,
			font=(zynthian_gui_config.font_family,zynthian_gui_config.font_size,"normal"),
			fill="white",
			text="Touch to start calibration")

		# Countdown timer
		self.countdown_text = self.canvas.create_text(self.width / 2,
			self.height / 2,
			font=(zynthian_gui_config.font_family,zynthian_gui_config.font_size,"normal"),
			fill="red",
			text="Closing in 5s")
		self.timer = Timer(interval=1, function=self.onTimer)
		
		# Coordinate transform matrix
		self.transform_matrix = [1,0,0, 0,1,0, 0,0,1]
		self.identify_matrix = [1,0,0, 0,1,0, 0,0,1]
		self.display_points = [point(self.width * 0.15, self.height * 0.15), point(self.width * 0.85, self.height * 0.15), point(self.width * 0.85, self.height * 0.85), point(self.width * 0.15, self.height * 0.85)]
		self.touch_points = [point(), point(), point(), point()]
		self.touch_min = point()
		self.touch_max = point()

		# Crosshair
		self.index = 0 # Index of current calibration point (0=NW, 1=NE, 2=SE, 3=SW)
		self.crosshair_size = self.width / 20 # half width of cross hairs
		self.crosshair_vertical = self.canvas.create_line(
			self.display_points[self.index].x, self.display_points[self.index].y - self.crosshair_size,
			self.display_points[self.index].x, self.display_points[self.index].y - self.crosshair_size,
			fill="white", state=tkinter.HIDDEN, tags="crosshairs")
		self.crosshair_horizontal = self.canvas.create_line(
			self.display_points[self.index].x - self.crosshair_size, self.display_points[self.index].y,
			self.display_points[self.index].x + self.crosshair_size, self.display_points[self.index].y,
			fill="white", state=tkinter.HIDDEN, tags="crosshairs")
		#TODO: Add circle to crosshairs?

		self.canvas.pack()
		self.device_name = None # Name of selected device
		self.devices = {} # Dictionary of device properties indexed by device name

	
	#	Handle touch event
	#	event: Event including x,y coordinates
	def onPress(self, event):
		self.countdown = 5 # Reset countdown timer when screen touched
		if not self.device_name:
			self.index = 0
			self.detectTouchscreens()
			for device in self.devices:
				self.setCalibration(device, self.identify_matrix)
				#TODO: Reset any devices that we don't use back to their previous state
	
	
	#	Handle touch release event
	#	event: Event including x,y coordinates
	def onRelease(self, event):
		self.countdown = 5 # Reset countdown timer when screen touched
		if not self.device_name:
			for device in self.devices:
				last_touch = self.getLastTouch(device)
				if last_touch.x != 0 or last_touch.y != 0:
					self.device_name = device
				else:
					self.setCalibration(device, self.devices[device]["ctm"]) # Reset calibration of other devices that we changed during detection
			if self.device_name:
				self.canvas.itemconfig(self.instruction_text, text="%s\nTouch (drag and) release on each crosshair"%(self.device_name))
				self.index = 0
				self.drawCross()
			return
		if self.index < 4:
			self.touch_points[self.index].x = event.x
			self.touch_points[self.index].y = event.y
			self.index += 1
		if self.index > 3:
			# Get average coords for corners of touch rectangle
			touch_min_x = (self.touch_points[0].x + self.touch_points[3].x) / 2
			touch_max_x = (self.touch_points[1].x + self.touch_points[2].x) / 2
			touch_min_y = (self.touch_points[0].y + self.touch_points[1].y) / 2
			touch_max_y = (self.touch_points[2].y + self.touch_points[3].y) / 2
			# Check for rotation
			a = self.width * 0.7 / (touch_max_x - touch_min_x)
			if touch_min_x < touch_max_x:
				c = (self.width * 0.15 - a * touch_min_x) / self.width
			else:
				c = (self.width * 0.15 - a * touch_min_x) / self.width
			e = self.height * 0.7 / (touch_max_y - touch_min_y)
			if touch_min_y < touch_max_y:
				f = (self.height * 0.15 - e * touch_min_y) / self.height
			else:
				f = (self.height * 0.15 - e * touch_min_y) / self.height
			self.transform_matrix[0] = a
			self.transform_matrix[2] = c
			self.transform_matrix[4] = e
			self.transform_matrix[5] = f
			self.setCalibration(self.device_name, self.transform_matrix, True)
			#TODO: Allow user to check calibration
			self.hide()
		self.drawCross()

	
	#	Draws the crosshairs for touch registration for current index (0..3)
	def drawCross(self):
		if self.index > 3:
			return
		self.canvas.coords(self.crosshair_vertical,
			self.display_points[self.index].x, self.display_points[self.index].y - self.crosshair_size,
			self.display_points[self.index].x, self.display_points[self.index].y + self.crosshair_size)
		self.canvas.coords(self.crosshair_horizontal,
			self.display_points[self.index].x - self.crosshair_size, self.display_points[self.index].y,
			self.display_points[self.index].x + self.crosshair_size, self.display_points[self.index].y)
		self.canvas.itemconfig("crosshairs", state=tkinter.NORMAL)


	#	Get last touch coordinates from device
	#	Returns point object with last touch coordinates
	def getLastTouch(self, device):
		try:
			result = run(["xinput", "--query-state", device], stdout=PIPE).stdout.decode()
			a = result.find("valuator[0]")
			b = result.find("\n", a)
			x = int(result[a+12:b])
			a = result.find("valuator[1]")
			b = result.find("\n", a)
			y = int(result[a+12:b])
		except:
			logging.warning("Failed to detect touchscreen last touch")
			return point(0,0)
		return point(x,y)

	#	Populate list of touchscreens with relevant properties
	def detectTouchscreens(self):
		self.devices = {}
		result = run(["xinput", "--list", "--name-only"], stdout=PIPE).stdout.decode().split("\n")
		# Get properties and check for calibration option
		for device in result:
			if device == "":
				continue
			properties = run(["xinput", "--list", "--long", device], stdout=PIPE).stdout.decode()
			if properties.find("master pointer") > 0:
				continue; # Don't want the master device
			if properties.find("Type: XITouchClass") > 0:
				config = {}
				status = run(["xinput", "--query-state", device], stdout=PIPE).stdout.decode()
				a = properties.find("Abs MT Position X")
				b = properties.find("Range:", a)
				c = properties.find("\n",b)
				d = properties[b+7:c]
				e = d.split(" - ")
				min_x = float(e[0])
				max_x = float(e[1])
				a = properties.find("Abs MT Position Y")
				b = properties.find("Range:", a)
				c = properties.find("\n",b)
				d = properties[b+7:c]
				e = d.split(" - ")
				min_y = float(e[0])
				max_y = float(e[1])
				config["min"] = point(min_x,min_y)
				config["max"] = point(max_x,max_y)
				config["ctm"] = self.getMatrix(device)
				self.devices[device] = config


	#	Get the current calibration settings for a device
	#	device: Name or ID of device
	#	Returns: Coordinate Transformation Matrix or None on error
	def getMatrix(self, device):
		result = run(["xinput", "--list-props", device], stdout=PIPE).stdout.decode()
		a = result.find("Coordinate Transformation Matrix")
		b = result.find(":", a)
		c = result.find("\n", b)
		if not (b > a and c > b):
			return None
		str_matrix = result[b+2:c].split(",")
		if len(str_matrix) != 9:
			return None
		matrix = []
		try:
			for value in str_matrix:
				matrix.append(float(value))
		except:
			return None
		return matrix




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
			proc = run(["xinput", "--set-prop", device, "Coordinate Transformation Matrix",
				str(matrix[0]), str(matrix[1]), str(matrix[2]), str(matrix[3]), str(matrix[4]), str(matrix[5]), str(matrix[6]), str(matrix[7]), str(matrix[8])])
			if write_file:
				# Create config file
				f = open("/etc/X11/xorg.conf.d/99-calibration.conf", "w")
				f.write('Section "InputClass"\n')
				f.write('	Identifier "calibration"\n')
				f.write('	MatchProduct "%s"\n'%(device))
				f.write('	Option "TransformationMatrix" "%f %f %f %f %f %f 0 0 1"\n' % (matrix[0], matrix[1], matrix[2], matrix[3], matrix[4], matrix[5]))
				f.write('EndSection\n')
				f.close()
		except Exception as e:
			logging.warning("Failed to set touchscreen calibration", e)
	

	#	Hide display
	def hide(self):
		if self.shown:
			self.canvas.itemconfig("crosshairs", state=tkinter.HIDDEN)
			self.canvas.itemconfig(self.instruction_text, text="Touch screen to detect and start calibration")
			self.shown=False
			self.timer.cancel()
			self.main_frame.grid_forget()
			self.zyngui.show_screen(self.zyngui.active_screen)


	# 	Show display
	def show(self):
		if not self.shown:
			self.shown=True
			self.device_name = None
			self.canvas.itemconfig(self.countdown_text, text="Closing in 5s")
			self.countdown= 5
			self.index = 0
			self.main_frame.grid()
			self.onTimer()


	#	Handle one second timer trigger
	def onTimer(self):
		if self.shown:
			self.canvas.itemconfig(self.countdown_text, text="Closing in %ds" % (self.countdown))
			if self.countdown <= 0:
				self.hide()
			else:
				self.timer = Timer(interval=1, function=self.onTimer)
				self.timer.start()
				self.countdown -= 1


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
