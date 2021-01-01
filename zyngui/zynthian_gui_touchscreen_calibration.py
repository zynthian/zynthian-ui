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
		
		# Instruction text
		self.instruction_text = self.canvas.create_text(self.width / 2,
			self.height / 2 - zynthian_gui_config.font_size * 2,
			font=(zynthian_gui_config.font_family,zynthian_gui_config.font_size,"normal"),
			fill="white",
			text="Touch each cross as it appears")

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
		self.display_points = [point(self.width * 0.15, self.height * 0.15), point(self.width * 0.5, self.height * 0.85), point(self.width * 0.85, self.height * 0.5)]
		self.touch_points = [point(), point(), point()]
		self.touch_min = point()
		self.touch_max = point()

		# Crosshair
		self.index = 0 # Index of current calibration point (0=NE, 1=S, 2=E)
		self.crosshair_size = self.width / 20 # half width of cross hairs
		self.crosshair_vertical = self.canvas.create_line(
			self.display_points[self.index].x, self.display_points[self.index].y - self.crosshair_size,
			self.display_points[self.index].x, self.display_points[self.index].y - self.crosshair_size,
			fill="white")
		self.crosshair_horizontal = self.canvas.create_line(
			self.display_points[self.index].x - self.crosshair_size, self.display_points[self.index].y,
			self.display_points[self.index].x + self.crosshair_size, self.display_points[self.index].y,
			fill="white")
		#TODO: Add circle to crosshairs?

		self.canvas.pack()
		self.device_name = None

	
	#	Handle touch release event
	#	event: Event including x,y coordinates
	def onRelease(self, event):
		self.countdown = 5 # Reset countdown timer when screen touched
		if(self.index < 3):
			self.touch_points[self.index].x = event.x
			self.touch_points[self.index].y = event.y
		self.index += 1
		if self.index > 2:
			if self.calcCalibrationMatrix():
				self.setCalibration(self.transform_matrix, True)
			#TODO: Allow user to check calibration
			self.hide()
		self.drawCross()

	
	#	Draws the crosshairs for touch registration for current index (0..2)
	def drawCross(self):
		if self.index > 2:
			return
		self.canvas.coords(self.crosshair_vertical,
			self.display_points[self.index].x, self.display_points[self.index].y - self.crosshair_size,
			self.display_points[self.index].x, self.display_points[self.index].y + self.crosshair_size)
		self.canvas.coords(self.crosshair_horizontal,
			self.display_points[self.index].x - self.crosshair_size, self.display_points[self.index].y,
			self.display_points[self.index].x + self.crosshair_size, self.display_points[self.index].y)


	#	Get the name and parameters for the first touchscreen detected
	#	TODO: Allow configuration of other touchscreens, not just first
	def getFirstTouchscreen(self):
		self.device_name = None
		result = run(["xinput", "--list", "--name-only"], stdout=PIPE).stdout.decode().split("\n")
		# Get properties and check for calibration option
		try:
			for device in result:
				if device == "":
					continue
				properties = run(["xinput", "--list", "--long", device], stdout=PIPE).stdout.decode()
				if properties.find("master pointer") > 0:
					continue; # Don't want the master device
				if properties.find("Type: XITouchClass") > 0:
					a = properties.find("Abs MT Position X")
					b = properties.find("Range:", a)
					c = properties.find("\n",b)
					d = properties[b+7:c]
					e = d.split(" - ")
					self.touch_min.x = float(e[0])
					self.touch_max.x = float(e[1])
					a = properties.find("Abs MT Position Y")
					b = properties.find("Range:", a)
					c = properties.find("\n",b)
					d = properties[b+7:c]
					e = d.split(" - ")
					self.touch_min.y = float(e[0])
					self.touch_max.y = float(e[1])
					self.device_name = device
		except Exception as e:
			logging.warning("Failed to find touchscreen for calibration", e)


	# 	Calculate calibration matrix from previously populated display and touch points
	#	Returns: True on success
	def calcCalibrationMatrix(self):
		Divider = (((self.touch_points[0].x - self.touch_points[2].x) * (self.touch_points[1].y - self.touch_points[2].y)) -
			((self.touch_points[1].x - self.touch_points[2].x) * (self.touch_points[0].y - self.touch_points[2].y)))
		if Divider == 0:
			return False
		self.transform_matrix[0] = (((self.display_points[0].x - self.display_points[2].x) * (self.touch_points[1].y - self.touch_points[2].y)) - 
			((self.display_points[1].x - self.display_points[2].x) * (self.touch_points[0].y - self.touch_points[2].y)))
		self.transform_matrix[1] = (((self.touch_points[0].x - self.touch_points[2].x) * (self.display_points[1].x - self.display_points[2].x)) - 
			((self.display_points[0].x - self.display_points[2].x) * (self.touch_points[1].x - self.touch_points[2].x)))
		self.transform_matrix[2] = ((self.touch_points[2].x * self.display_points[1].x - self.touch_points[1].x * self.display_points[2].x) * self.touch_points[0].y +
			(self.touch_points[0].x * self.display_points[2].x - self.touch_points[2].x * self.display_points[0].x) * self.touch_points[1].y +
			(self.touch_points[1].x * self.display_points[0].x - self.touch_points[0].x * self.display_points[1].x) * self.touch_points[2].y)
		self.transform_matrix[3] = (((self.display_points[0].y - self.display_points[2].y) * (self.touch_points[1].y - self.touch_points[2].y)) - 
			((self.display_points[1].y - self.display_points[2].y) * (self.touch_points[0].y - self.touch_points[2].y)))
		self.transform_matrix[4] = (((self.touch_points[0].x - self.touch_points[2].x) * (self.display_points[1].y - self.display_points[2].y)) - 
			((self.display_points[0].y - self.display_points[2].y) * (self.touch_points[1].x - self.touch_points[2].x)))
		self.transform_matrix[5] = ((self.touch_points[2].x * self.display_points[1].y - self.touch_points[1].x * self.display_points[2].y) * self.touch_points[0].y +
			(self.touch_points[0].x * self.display_points[2].y - self.touch_points[2].x * self.display_points[0].y) * self.touch_points[1].y +
			(self.touch_points[1].x * self.display_points[0].y - self.touch_points[0].x * self.display_points[1].y) * self.touch_points[2].y)
		return True


	#	Apply screen calibration
	#	matrix: Transorm matrix as 9 element array (3x3)
	#	write_file: True to write configuration to file (default: false)
	def setCalibration(self, matrix, write_file=False):
		try:
			proc = run(["xinput", "--set-prop", self.device_name, "Coordinate Transformation Matrix",
				str(matrix[0]), str(matrix[1]), str(matrix[2]), str(matrix[3]), str(matrix[4]), str(matrix[5]), "0", "0", "1"])
			#logging.debug("***setCalibration: ", proc.args)
			if write_file:
				# Create config file
				f = open("/etc/X11/xorg.conf.d/99-calibration.conf", "w")
				f.write('Section "InputClass"\n')
				f.write('	Identifier "calibration"\n')
				f.write('	MatchProduct "%s"\n'%(self.device_name))
				f.write('	Option "TransformationMatrix" "%f %f %f %f %f %f 0 0 1"\n' % (matrix[0], matrix[1], matrix[2], matrix[3], matrix[4], matrix[5]))
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
			self.canvas.itemconfig(self.countdown_text, text="Closing in 5s")
			self.countdown= 5
			self.getFirstTouchscreen()
			if not self.device_name:
				logging.warning("No touchscreen detected")
				self.hide() #TODO: This does not close screen
				return
			self.setCalibration(self.identify_matrix) # Clear calibration
			self.index = 0
			self.drawCross()
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
