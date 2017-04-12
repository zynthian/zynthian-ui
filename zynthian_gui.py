#!/usr/bin/python3
# -*- coding: utf-8 -*-
#********************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Classes and Main Program for Zynthian GUI, the official User 
# Interface of Zynthian Box.
# 
# Copyright (C) 2015-2016 Fernando Moyano <jofemodo@zynthian.org>
#
#********************************************************************
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
#********************************************************************

import os
import sys
import copy
import signal
import alsaseq
import logging
import liblo
import tkinter
from ctypes import *
from time import sleep
from string import Template
from datetime import datetime
from threading  import Thread, Lock
from tkinter import font as tkFont
from os.path import isfile, isdir, join
from json import JSONEncoder, JSONDecoder
from subprocess import check_output, Popen, PIPE

from zyncoder import *
from zyncoder.zyncoder import lib_zyncoder, lib_zyncoder_init

from zyngine import *
#from zyngine.zynthian_controller import *
#from zyngine.zynthian_zcmidi import *
#from zyngine.zynthian_midi import *

import zynautoconnect

try:
	from zynthian_gui_config import *
except:
	print("Config file 'zynthian_gui_config.py' not found. Using defaults.")

#-------------------------------------------------------------------------------
# Configure logging
#-------------------------------------------------------------------------------

if os.environ.get('ZYNTHIAN_LOG_LEVEL'):
	log_level=int(os.environ.get('ZYNTHIAN_LOG_LEVEL'))
elif log_level not in globals():
	log_level=logging.DEBUG

if os.environ.get('ZYNTHIAN_RAISE_EXCEPTIONS'):
	raise_exceptions=int(os.environ.get('ZYNTHIAN_RAISE_EXCEPTIONS'))
elif raise_exceptions not in globals():
	raise_exceptions=True

# Set root logging level
logging.basicConfig(stream=sys.stderr, level=log_level)

# Reduce log level for other modules
logging.getLogger("urllib3").setLevel(logging.WARNING)

#-------------------------------------------------------------------------------
# Create Top Level Window with Fixed Size
#-------------------------------------------------------------------------------

top = tkinter.Tk()
# Screen Size
try:
	if not width: width = top.winfo_screenwidth()
	if not height: height = top.winfo_screenheight()
except:
	width = 320
	height = 240
# Adjust Root Window Geometry
top.geometry(str(width)+'x'+str(height))
top.maxsize(width,height)
top.minsize(width,height)
if hw_version and hw_version!="PROTOTYPE-EMU" and hw_version!="DUMMIES":
	top.config(cursor="none")

#-------------------------------------------------------------------------------
# Define some Constants and Parameters for the GUI
#-------------------------------------------------------------------------------

# Topbar Height
if not topbar_height: topbar_height=24

# Controller Size
ctrl_width=int(width/4)
ctrl_height=int((height-topbar_height)/2)

# Controller Positions
ctrl_pos=[
	(1,0,"nw"),
	(2,0,"sw"),
	(1,2,"ne"),
	(2,2,"se")
]

# Color Scheme
if not color_bg: color_bg="#000000"
if not color_tx: color_tx="#ffffff"
if not color_on: color_on="#ff0000"
if not color_panel_bg: color_panel_bg="#3a424d"
color_panel_bd=color_bg
color_panel_tx=color_tx
color_header_bg=color_bg
color_header_tx=color_tx
color_ctrl_bg_off="#5a626d"
color_ctrl_bg_on=color_on
color_ctrl_tx=color_tx
color_ctrl_tx_off="#e0e0e0"

# Fonts
#font_family="Helvetica" #=> the original ;-)
#font_family="Economica" #=> small
#font_family="Orbitron" #=> Nice, but too strange
#font_family="Abel" #=> Quite interesting, also "Strait"
if not font_family: font_family="Audiowide"
if not font_topbar: font_topbar=(font_family,11)
if not font_listbox: font_listbox=(font_family,10)
if not font_ctrl_title_maxsize: font_ctrl_title_maxsize=11

# Wiring layout
if hw_version:
	logging.info("HW version "+str(hw_version))
else:
	logging.info("No HW version file. Only touch interface available.")

#-------------------------------------------------------------------------------
# Wiring layout => GPIO pin assignment (wiringPi numbering)
#-------------------------------------------------------------------------------

# First Prototype => Generic Plastic Case
if hw_version=="PROTOTYPE-1":
	zyncoder_pin_a=[27,21,3,7]
	zyncoder_pin_b=[25,26,4,0]
	zynswitch_pin=[23,None,2,None]
	select_ctrl=2
# Controller RBPi connector downside, controller 1 reversed
elif hw_version=="PROTOTYPE-2":
	zyncoder_pin_a=[27,21,4,0]
	zyncoder_pin_b=[25,26,3,7]
	zynswitch_pin=[23,107,2,106]
	select_ctrl=3
# Controller RBPi connector upside
elif hw_version=="PROTOTYPE-3":
	zyncoder_pin_a=[27,21,3,7]
	zyncoder_pin_b=[25,26,4,0]
	zynswitch_pin=[107,23,106,2]
	select_ctrl=3
# Controller RBPi connector downside (Holger's way)
elif hw_version=="PROTOTYPE-3H":
	zyncoder_pin_a=[21,27,7,3]
	zyncoder_pin_b=[26,25,0,4]
	zynswitch_pin=[107,23,106,2]
	select_ctrl=3
# Controller RBPi connector upside / Controller Singles
elif hw_version=="PROTOTYPE-4":
	zyncoder_pin_a=[26,25,0,4]
	zyncoder_pin_b=[21,27,7,3]
	zynswitch_pin=[107,23,106,2]
	select_ctrl=3
# Controller RBPi connector downside / Controller Singles Inverted
elif hw_version=="PROTOTYPE-4B":
	zyncoder_pin_a=[25,26,4,0]
	zyncoder_pin_b=[27,21,3,7]
	zynswitch_pin=[23,107,2,106]
	select_ctrl=3
# Kees layout, for display Waveshare 3.2
elif hw_version=="PROTOTYPE-KEES":
	zyncoder_pin_a=[27,21,4,5]
	zyncoder_pin_b=[25,26,31,7]
	zynswitch_pin=[23,107,6,106]
	select_ctrl=3
# Controller RBPi connector upside / Controller Singles / Switches throw GPIO expander
elif hw_version=="PROTOTYPE-5":
	zyncoder_pin_a=[26,25,0,4]
	zyncoder_pin_b=[21,27,7,3]
	zynswitch_pin=[107,105,106,104]
	select_ctrl=3
# Desktop Development & Emulation
elif hw_version=="PROTOTYPE-EMU":
	zyncoder_pin_a=[4,5,6,7]
	zyncoder_pin_b=[8,9,10,11]
	zynswitch_pin=[0,1,2,3]
	select_ctrl=3
# No HW Controllers => Dummy Controllers
elif hw_version=="DUMMIES":
	zyncoder_pin_a=[0,0,0,0]
	zyncoder_pin_b=[0,0,0,0]
	zynswitch_pin=[0,0,0,0]
	select_ctrl=3
# No HW Controllers
elif hw_version==None:
	zyncoder_pin_a=None
	zyncoder_pin_b=None
	zynswitch_pin=None
	select_ctrl=3
# Default to PROTOTYPE-3
else:
	zyncoder_pin_a=[26,25,0,4]
	zyncoder_pin_b=[21,27,7,3]
	zynswitch_pin=[107,23,106,2]
	select_ctrl=3

#-------------------------------------------------------------------------------
# Controller GUI Class
#-------------------------------------------------------------------------------
class zynthian_gui_controller:
	width=ctrl_width
	height=ctrl_height
	trw=ctrl_width-6
	trh=13

	def __init__(self, indx, frm, zctrl):
		self.zctrl=None
		self.values=None
		self.ticks=None
		self.n_values=127
		self.max_value=127
		self.inverted=False
		self.step=1
		self.mult=1
		self.val0=0
		self.value=0
		self.scale_plot=1
		self.scale_print=1
		self.value_plot=0
		self.value_print=None
		self.value_font_size=14

		self.shown=False
		self.rectangle=None
		self.triangle=None
		self.arc=None
		self.value_text=None
		self.label_title=None
		self.midi_icon=None

		self.index=indx
		self.main_frame=frm
		self.row=ctrl_pos[indx][0]
		self.col=ctrl_pos[indx][1]
		self.sticky=ctrl_pos[indx][2]
		self.plot_value=self.plot_value_arc
		self.erase_value=self.erase_value_arc
		# Create Canvas
		self.canvas=tkinter.Canvas(self.main_frame,
			width=self.width,
			height=self.height-1,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg = color_panel_bg)
		# Bind canvas events
		self.canvas.bind("<Button-1>",self.cb_canvas_push)
		self.canvas.bind("<ButtonRelease-1>",self.cb_canvas_release)
		self.canvas.bind("<B1-Motion>",self.cb_canvas_motion)
		# Setup Controller and Zyncoder
		self.config(zctrl)
		# Show Controller
		self.show()

	def show(self):
		#print("SHOW CONTROLLER "+str(self.ctrl)+" => "+str(self.shown))
		if not self.shown:
			self.shown=True
			self.canvas.grid(row=self.row,column=self.col,sticky=self.sticky)
			self.plot_value()

	def hide(self):
		if self.shown:
			self.shown=False
			self.canvas.grid_forget()

	def calculate_plot_values(self):
		if self.value>self.max_value: self.value=self.max_value
		elif self.value<0: self.value=0
		if self.values:
			try:
				if self.ticks:
					if self.inverted:
						for i in reversed(range(self.n_values)):
							if self.value<=self.ticks[i]:
								break
						self.value_plot=self.scale_plot*(self.max_value+self.step-self.ticks[i])
					else:
						for i in range(self.n_values):
							if self.value<=self.ticks[i]:
								break
						self.value_plot=self.scale_plot*self.ticks[i]
				else:
					i=int(self.n_values*self.value/(self.max_value+self.step))
					self.value_plot=self.scale_plot*i
				val=self.values[i]
				self.zctrl.set_value(val)
				self.value_print=str(val)
			except Exception as err:
				logging.error("Calc Error => %s" % (err))
				self.value_plot=self.value
				self.value_print="ERR"
		else:
			self.value_plot=self.value
			if self.zctrl.midi_cc==0:
				val=self.val0+self.value
				self.zctrl.set_value(val)
				self.value_print=str(val)
			else:
				val=self.zctrl.value_min+self.value*self.scale_print
				self.zctrl.set_value(val)
				if self.format_print:
					self.value_print=self.format_print.format(val)
				else:
					self.value_print=str(int(val))
		#print("VALUE: %s" % self.value)
		#print("VALUE PLOT: %s" % self.value_plot)
		#print("VALUE PRINT: %s" % self.value_print)

	def plot_value_rectangle(self):
		self.calculate_plot_values()
		x1=6
		y1=self.height-5
		lx=self.trw-4
		ly=2*self.trh
		y2=y1-ly
		if self.max_value>0:
			x2=x1+lx*self.value_plot/self.max_value
		else:
			x2=x1
		if self.rectangle:
				self.canvas.coords(self.rectangle,(x1, y1, x2, y2))
		elif self.zctrl.midi_cc!=0:
			self.rectangle_bg=self.canvas.create_rectangle((x1, y1, x1+lx, y2), fill=color_ctrl_bg_off, width=0)
			self.rectangle=self.canvas.create_rectangle((x1, y1, x2, y2), fill=color_ctrl_bg_on, width=0)
		if self.value_text:
			self.canvas.itemconfig(self.value_text, text=value_print)
		else:
			self.value_text=self.canvas.create_text(x1+self.trw/2-1, y1-self.trh, width=self.trw, justify=CENTER, fill=color_ctrl_tx, font=(font_family,self.value_font_size), text=self.value_print)

	def erase_value_rectangle(self):
		if self.rectangle:
			self.canvas.delete(self.rectangle_bg)
			self.canvas.delete(self.rectangle)
			self.rectangle_bg=self.rectangle=None
		if self.value_text:
			self.canvas.delete(self.value_text)
			self.value_text=None

	def plot_value_triangle(self):
		self.calculate_plot_values()
		x1=2
		y1=int(0.8*self.height)+self.trh
		if self.max_value>0:
			x2=x1+self.trw*self.value_plot/self.max_value
			y2=y1-self.trh*self.value_plot/self.max_value
		else:
			x2=x1
			y2=y1
		if self.triangle:
				#self.canvas.coords(self.triangle_bg,(x1, y1, x1+self.trw, y1, x1+self.trw, y1-self.trh))
				self.canvas.coords(self.triangle,(x1, y1, x2, y1, x2, y2))
		elif self.zctrl.midi_cc!=0:
			self.triangle_bg=self.canvas.create_polygon((x1, y1, x1+self.trw, y1, x1+self.trw, y1-self.trh), fill=color_ctrl_bg_off)
			self.triangle=self.canvas.create_polygon((x1, y1, x2, y1, x2, y2), fill=color_ctrl_bg_on)
		if self.value_text:
			self.canvas.itemconfig(self.value_text, text=self.value_print)
		else:
			self.value_text=self.canvas.create_text(x1+self.trw/2-1, y1-self.trh-8, width=self.trw, justify=CENTER, fill=color_ctrl_tx, font=(font_family,self.value_font_size), text=self.value_print)

	def erase_value_triangle(self):
		if self.triangle:
			self.canvas.delete(self.triangle_bg)
			self.canvas.delete(self.triangle)
			self.triangle_bg=self.triangle=None
		if self.value_text:
			self.canvas.delete(self.value_text)
			self.value_text=None

	def plot_value_arc(self):
		self.calculate_plot_values()
		thickness=12
		degmax=300
		deg0=90+degmax/2
		if self.max_value>0:
			degd=-degmax*self.value_plot/self.max_value
		else:
			degd=0
		if (not self.arc and self.zctrl.midi_cc!=0) or not self.value_text:
			x1=0.2*self.trw
			y1=self.height-int(0.7*self.trw)-6
			x2=x1+0.7*self.trw
			y2=self.height-6
		if self.arc:
			self.canvas.itemconfig(self.arc, extent=degd)
		elif self.zctrl.midi_cc!=0:
			self.arc=self.canvas.create_arc(x1, y1, x2, y2, style=tkinter.ARC, outline=color_ctrl_bg_on, width=thickness, start=deg0, extent=degd)
		if self.value_text:
			self.canvas.itemconfig(self.value_text, text=self.value_print)
		else:
			self.value_text=self.canvas.create_text(x1+(x2-x1)/2-1, y1-(y1-y2)/2, width=x2-x1, justify=tkinter.CENTER, fill=color_ctrl_tx, font=(font_family,self.value_font_size), text=self.value_print)

	def erase_value_arc(self):
		if self.arc:
			self.canvas.delete(self.arc)
			self.arc=None
		x2=self.width
		y2=self.height

	def plot_midi_icon(self):
		if not self.midi_icon:
			self.midi_icon = self.canvas.create_text(
				self.width/2, 
				self.height-8, 
				width=16, 
				justify=tkinter.CENTER, 
				fill=color_ctrl_tx,
				font=(font_family,7),
				text=str(self.zctrl.midi_cc))
		else:
			self.canvas.itemconfig(self.midi_icon, text=str(self.zctrl.midi_cc))

	def erase_midi_icon(self):
		if self.midi_icon:
			self.canvas.itemconfig(self.midi_icon, text="")

	def set_midi_icon(self):
		if self.zctrl.midi_cc and self.zctrl.midi_cc>0:
			self.plot_midi_icon()
		else:
			self.erase_midi_icon()

	def set_title(self, tit):
		self.title=str(tit)
		#Calculate the font size ...
		max_fs=font_ctrl_title_maxsize
		words=self.title.split()
		n_words=len(words)
		maxnumchar=max([len(w) for w in words])
		rfont=tkFont.Font(family=font_family,size=max_fs)
		maxlen=rfont.measure(self.title)
		l=790
		if maxlen<ctrl_width and maxnumchar<11:
			font_size=int(l/maxlen)
		elif n_words==1:
			font_size=int(l/maxlen) # *2
		elif n_words==2:
			maxlen=max([rfont.measure(w) for w in words])
			font_size=int(l/maxlen)
		elif n_words==3:
			maxlen=max([rfont.measure(w) for w in [words[0]+' '+words[1], words[1]+' '+words[2]]])
			maxlen=rfont.measure(words[0]+' '+words[1])
			font_size=int(l/maxlen)
			max_fs=max_fs-1
		elif n_words>=4:
			maxlen=max([rfont.measure(w) for w in [words[0]+' '+words[1], words[2]+' '+words[3]]])
			font_size=int(l/maxlen)
			max_fs=max_fs-1
		font_size=min(max_fs,max(7,font_size))
		#logging.debug("TITLE %s => MAXLEN=%d, FONTSIZE=%d" % (self.title,maxlen,font_size))
		#Set title label
		if not self.label_title:
			self.label_title = tkinter.Label(self.canvas,
				text=self.title,
				font=(font_family,font_size),
				wraplength=self.width-6,
				justify=tkinter.LEFT,
				bg=color_panel_bg,
				fg=color_panel_tx)
			self.label_title.place(x=3, y=4, anchor=tkinter.NW)
		else:
			self.label_title.config(text=self.title,font=(font_family,font_size))

	def calculate_value_font_size(self):
		if self.values:
			rfont=tkFont.Font(family=font_family,size=10)
			maxlen=len(max(self.values, key=len))
			if maxlen>3:
				maxlen=max([rfont.measure(w) for w in self.values])
			#print("LONGEST VALUE: %d" % maxlen)
			if maxlen>100:
				self.value_font_size=7
			elif maxlen>85:
				self.value_font_size=8
			elif maxlen>70:
				self.value_font_size=9
			elif maxlen>55:
				self.value_font_size=10
			elif maxlen>40:
				self.value_font_size=11
			elif maxlen>30:
				self.value_font_size=12
			elif maxlen>20:
				self.value_font_size=13
			else:
				self.value_font_size=14
		else:
			if self.format_print:
				maxlen=max(len(self.format_print.format(self.zctrl.value_min)),len(self.format_print.format(self.zctrl.value_max)))
			else:
				maxlen=max(len(str(self.zctrl.value_min)),len(str(self.zctrl.value_max)))
			if maxlen>5:
				self.value_font_size=8
			elif maxlen>4:
				self.value_font_size=9
			elif maxlen>3:
				self.value_font_size=10
			else:
				if self.zctrl.value_min>=0 and self.zctrl.value_max<200:
					self.value_font_size=14
				else:
					self.value_font_size=13
		#Update font config in text object
		if self.value_text:
			self.canvas.itemconfig(self.value_text, font=(font_family,self.value_font_size))

	def config(self, zctrl):
		#print("CONFIG CONTROLLER %s => %s" % (self.index,zctrl.name))
		self.zctrl=zctrl
		self.step=1
		self.mult=1
		self.val0=0
		self.values=None
		self.ticks=None
		self.value=None
		self.inverted=False
		self.scale_print=1
		self.scale_value=1
		self.format_print=None
		self.set_title(zctrl.short_name)
		self.set_midi_icon()

		logging.debug("ZCTRL '%s': %s (%s -> %s), %s, %s" % (zctrl.short_name,zctrl.value,zctrl.value_min,zctrl.value_max,zctrl.labels,zctrl.ticks))

		#List of values (value selector)
		if isinstance(zctrl.labels,list):
			self.values=zctrl.labels
			self.n_values=len(self.values)
			self.step=max(1,int(16/self.n_values))
			self.max_value=128-self.step;
			if isinstance(zctrl.ticks,list):
				self.ticks=zctrl.ticks
				try:
					if self.ticks[0]>self.ticks[1]:
						self.inverted=True
				except:
					logging.error("Ticks list is too short")
			try:
				val=self.ticks[self.values.index(zctrl.value)]
			except:
				try:
					val=int(self.values.index(zctrl.value)*self.max_value/(self.n_values-1))
				except:
					val=self.max_value
		#Numeric value
		else:
			#"List Selection Controller" => step 1 element by rotary tick
			if zctrl.midi_cc==0:
				self.max_value=self.n_values=zctrl.value_max
				self.scale_print=1
				self.mult=4
				self.val0=1
				val=zctrl.value
			else:
				r=zctrl.value_max-zctrl.value_min
				#Integer < 127
				if isinstance(r,int) and r<=127:
					self.max_value=self.n_values=r
					self.scale_print=1
					self.mult=max(1,int(128/self.n_values))
					val=zctrl.value-zctrl.value_min
				#Integer > 127 || Float
				else:
					self.max_value=self.n_values=127
					self.scale_print=r/self.max_value
					if self.scale_print<0.013:
						self.format_print="{0:.2f}"
					elif self.scale_print<0.13:
						self.format_print="{0:.1f}"
					val=(zctrl.value-zctrl.value_min)/self.scale_print
				#If many values => use adaptative step size based on rotary speed
				if self.n_values>=96:
					self.step=0

		#Calculate scale parameter for plotting
		if self.ticks:
			self.scale_plot=self.max_value/abs(self.ticks[0]-self.ticks[self.n_values-1])
		elif self.n_values>1:
			self.scale_plot=self.max_value/(self.n_values-1)
		else:
			self.scale_plot=self.max_value

		self.calculate_value_font_size()
		self.set_value(val)
		self.setup_zyncoder()

		#logging.debug("values: "+str(self.values))
		#logging.debug("ticks: "+str(self.ticks))
		#logging.debug("inverted: "+str(self.inverted))
		#logging.debug("n_values: "+str(self.n_values))
		#logging.debug("max_value: "+str(self.max_value))
		#logging.debug("step: "+str(self.step))
		#logging.debug("mult: "+str(self.mult))
		#logging.debug("val0: "+str(self.val0))
		#logging.debug("value: "+str(self.value))

	def zctrl_sync(self):
		#List of values (value selector)
		if self.values:
			try:
				val=self.ticks[self.values.index(self.zctrl.value)]
			except:
				val=int(self.values.index(self.zctrl.value)*self.max_value/(self.n_values-1))
		#Numeric value
		else:
			#"List Selection Controller" => step 1 element by rotary tick
			if self.zctrl.midi_cc==0:
				val=self.zctrl.value
			else:
				val=(self.zctrl.value-self.zctrl.value_min)/self.scale_print
		#Set value & Update zyncoder
		self.set_value(val,True)

	def setup_zyncoder(self):
		self.init_value=None
		try:
			if self.zctrl.osc_path:
				#logging.debug("Setup zyncoder %d => %s" % (self.index,self.zctrl.osc_path))
				midi_cc=None
				osc_path_char=c_char_p(self.zctrl.osc_path.encode('UTF-8'))
				if zyngui.osc_target:
					liblo.send(zyngui.osc_target, self.zctrl.osc_path)
			elif self.zctrl.graph_path:
				#logging.debug("Setup zyncoder %d => %s" % (self.index,self.zctrl.graph_path))
				midi_cc=None
				osc_path_char=None
			else:
				#logging.debug("Setup zyncoder %d => %s" % (self.index,self.zctrl.midi_cc))
				midi_cc=self.zctrl.midi_cc
				osc_path_char=None
			if hw_version and lib_zyncoder:
				if self.inverted:
					pin_a=zyncoder_pin_b[self.index]
					pin_b=zyncoder_pin_a[self.index]
				else:
					pin_a=zyncoder_pin_a[self.index]
					pin_b=zyncoder_pin_b[self.index]
				lib_zyncoder.setup_zyncoder(self.index,pin_a,pin_b,self.zctrl.midi_chan,midi_cc,osc_path_char,int(self.mult*self.value),int(self.mult*(self.max_value-self.val0)),self.step)
		except Exception as err:
			logging.error("%s" % err)

	def set_value(self, v, set_zyncoder=False):
		if v>self.max_value:
			v=self.max_value
		elif v<0:
			v=0
		if self.value is None or self.value!=v:
			self.value=v
			#logging.debug("CONTROL %d VALUE => %s" % (self.index,v))
			if self.shown:
				if set_zyncoder and hw_version and lib_zyncoder:
					if self.mult>1: v=self.mult*v
					lib_zyncoder.set_value_zyncoder(self.index,c_uint(int(v)))
				self.plot_value()
			return True

	def set_init_value(self, v):
		if self.init_value is None:
			self.init_value=v
			self.set_value(v,True)
			logging.debug("INIT VALUE %s => %s" % (self.index,v))

	def read_zyncoder(self):
		if hw_version and lib_zyncoder:
			val=lib_zyncoder.get_value_zyncoder(self.index)
			#logging.debug("ZYNCODER %d RAW VALUE => %s" % (self.index,val))
		else:
			val=self.value*self.mult-self.val0
		if self.mult>1:
			val=int((val+1)/self.mult)
		return self.set_value(val)

	def cb_canvas_push(self,event):
		self.canvas_push_ts=datetime.now()
		self.canvas_motion_y0=event.y
		self.canvas_motion_x0=event.x
		self.canvas_motion_dy=0
		self.canvas_motion_dx=0
		self.canvas_motion_count=0
		#logging.debug("CONTROL %d PUSH => %s" % (self.index, self.canvas_push_ts))

	def cb_canvas_release(self,event):
		dts=(datetime.now()-self.canvas_push_ts).total_seconds()
		motion_rate=self.canvas_motion_count/dts
		logging.debug("CONTROL %d RELEASE => %s, %s" % (self.index, dts, motion_rate))
		if motion_rate<10:
			if dts<0.3:
				zyngui.zynswitch_defered('S',self.index)
			elif dts>=0.3 and dts<2:
				zyngui.zynswitch_defered('B',self.index)
			elif dts>=2:
				zyngui.zynswitch_defered('L',self.index)
		elif self.canvas_motion_dx>20:
			zyngui.zynswitch_defered('X',self.index)
		elif self.canvas_motion_dx<-20:
			zyngui.zynswitch_defered('Y',self.index)

	def cb_canvas_motion(self,event):
		dts=(datetime.now()-self.canvas_push_ts).total_seconds()
		if dts>0.1:
			dy=self.canvas_motion_y0-event.y
			if dy!=0:
				#logging.debug("CONTROL %d MOTION Y => %d, %d: %d" % (self.index, event.y, dy, self.value+dy))
				if self.inverted:
					self.set_value(self.value-dy, True)
				else:
					self.set_value(self.value+dy, True)
				self.canvas_motion_y0=event.y
				if self.canvas_motion_dy+dy!=0:
					self.canvas_motion_count=self.canvas_motion_count+1
				self.canvas_motion_dy=dy
			dx=event.x-self.canvas_motion_x0
			if dx!=0:
				#logging.debug("CONTROL %d MOTION X => %d, %d" % (self.index, event.x, dx))
				if abs(self.canvas_motion_dx-dx)>0:
					self.canvas_motion_count=self.canvas_motion_count+1
				self.canvas_motion_dx=dx

#-------------------------------------------------------------------------------
# Zynthian Listbox Selector GUI Class
#-------------------------------------------------------------------------------
class zynthian_selector:
	# Listbox Size
	lb_width=width-2*ctrl_width
	lb_height=height-topbar_height

	wide=False
	shown=False
	index=0
	list_data=[]
	selector_caption=None
	zselector=None
	
	loading_imgs=[]
	loading_index=0
	loading_item=None

	def __init__(self, selcap='Select', wide=False):
		self.shown=False
		self.wide=wide
			
		if self.wide:
			self.lb_width=width-ctrl_width
		else:
			self.lb_width=width-2*ctrl_width-2

		# Main Frame
		self.main_frame = tkinter.Frame(top,
			width=width,
			height=height,
			bg=color_bg)

		# Topbar's frame
		self.tb_frame = tkinter.Frame(self.main_frame, 
			width=width,
			height=topbar_height,
			bg=color_bg)
		self.tb_frame.grid(row=0, column=0, columnspan=3)
		self.tb_frame.grid_propagate(False)

		# Topbar's Select Path
		self.select_path = tkinter.StringVar()
		self.label_select_path = tkinter.Label(self.tb_frame,
			font=font_topbar,
			textvariable=self.select_path,
			#wraplength=80,
			justify=tkinter.LEFT,
			bg=color_header_bg,
			fg=color_header_tx)
		self.label_select_path.grid(sticky="wns")
		# Setup Topbar's Callback
		self.label_select_path.bind("<Button-1>", self.cb_topbar)

		# ListBox's frame
		self.lb_frame = tkinter.Frame(self.main_frame,
			width=self.lb_width,
			height=self.lb_height,
			bg=color_bg)
		if self.wide:
			if select_ctrl>1:
				self.lb_frame.grid(row=1, column=0, rowspan=2, columnspan=2, padx=(0,2), sticky="w")
			else:
				self.lb_frame.grid(row=1, column=1, rowspan=2, columnspan=2, padx=(2,0), sticky="e")
		else:
			if select_ctrl>1:
				self.lb_frame.grid(row=1, column=1, rowspan=2, padx=(2,2), sticky="w")
			else:
				self.lb_frame.grid(row=1, column=1, rowspan=2, padx=(2,2), sticky="e")
		#self.lb_frame.columnconfigure(0, weight=10)
		self.lb_frame.rowconfigure(0, weight=10)
		self.lb_frame.grid_propagate(False)

		# ListBox
		self.listbox = tkinter.Listbox(self.lb_frame,
			font=font_listbox,
			bd=7,
			highlightthickness=0,
			relief='flat',
			bg=color_panel_bg,
			fg=color_panel_tx,
			selectbackground=color_ctrl_bg_on,
			selectforeground=color_ctrl_tx,
			selectmode=tkinter.BROWSE)
		self.listbox.grid(sticky="wens")
		# Bind listbox events
		self.listbox.bind("<Button-1>",self.cb_listbox_push)
		self.listbox.bind("<ButtonRelease-1>",self.cb_listbox_release)
		self.listbox.bind("<B1-Motion>",self.cb_listbox_motion)

		# Canvas for loading image animation
		self.loading_canvas = tkinter.Canvas(self.main_frame,
			width=ctrl_width,
			height=ctrl_height-1,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg = color_bg)
		self.loading_canvas.grid(row=1,column=2,sticky="ne")

		# Loading Image Animation
		self.loading_imgs=[]
		for i in range(13):
			self.loading_imgs.append(tkinter.PhotoImage(file="./img/zynthian_gui_loading.gif", format="gif -index "+str(i)))
		self.loading_item=self.loading_canvas.create_image(4, 4, image = self.loading_imgs[0], anchor=tkinter.NW)

		# Selector Controller Caption
		self.selector_caption=selcap

		# Update Title
		self.set_select_path()

	def show(self):
		if not self.shown:
			self.shown=True
			self.main_frame.grid()
		self.fill_list()
		self.select()
		self.set_selector()
		self.set_select_path()

	def hide(self):
		if self.shown:
			self.shown=False
			self.main_frame.grid_forget()

	def is_shown(self):
		try:
			self.main_frame.grid_info()
			return True
		except:
			return False

	def refresh_loading(self):
		if self.shown:
			try:
				if zyngui.loading:
					self.loading_index=self.loading_index+1
					if self.loading_index>13: self.loading_index=0
					self.loading_canvas.itemconfig(self.loading_item, image=self.loading_imgs[self.loading_index])
				else:
					self.reset_loading()
			except:
				self.reset_loading()

	def reset_loading(self, force=False):
		if self.loading_index>0 or force:
			self.loading_index=0
			self.loading_canvas.itemconfig(self.loading_item, image=self.loading_imgs[0])

	def fill_listbox(self):
		self.listbox.delete(0, tkinter.END)
		if not self.list_data:
			self.list_data=[]
		for item in self.list_data:
			self.listbox.insert(tkinter.END, item[2])

	def set_selector(self):
		if self.zselector:
			self.zselector_ctrl.set_options({ 'midi_cc':0, 'value_max':len(self.list_data), 'value':self.index })
			self.zselector.config(self.zselector_ctrl)
			self.zselector.show()
		else:
			self.zselector_ctrl=zynthian_controller(None,self.selector_caption,self.selector_caption,{ 'midi_cc':0, 'value_max':len(self.list_data), 'value':self.index })
			self.zselector=zynthian_gui_controller(select_ctrl,self.main_frame,self.zselector_ctrl)

	def fill_list(self):
		self.fill_listbox()
		self.select(self.index)
		#self.set_selector()

	def get_cursel(self):
		cursel=self.listbox.curselection()
		if (len(cursel)>0):
			index=int(cursel[0])
		else:
			index=0
		return index

	def zyncoder_read(self):
		if self.zselector:
			self.zselector.read_zyncoder()
			if (self.index!=self.zselector.value):
				self.select_listbox(self.zselector.value)

	def select_listbox(self,index):
		self.listbox.selection_clear(0,tkinter.END)
		self.listbox.selection_set(index)
		if index>self.index: self.listbox.see(index+1)
		elif index<self.index: self.listbox.see(index-1)
		else: self.listbox.see(index)
		self.index=index

	def click_listbox(self, index=None):
		if index is not None:
			self.select_listbox(index)
		else:
			self.index=self.get_cursel()
		self.select_action(self.index)

	def switch_select(self):
		self.click_listbox()

	def select(self, index=None):
		if index==None: index=self.index
		self.select_listbox(index)

	def select_action(self, index):
		pass

	def set_select_path(self):
		pass

	def cb_topbar(self,event):
		zyngui.zynswitch_defered('S',1)

	def cb_listbox_push(self,event):
		self.listbox_push_ts=datetime.now()
		#logging.debug("LISTBOX PUSH => %s" % (self.listbox_push_ts))

	def cb_listbox_release(self,event):
		dts=(datetime.now()-self.listbox_push_ts).total_seconds()
		#logging.debug("LISTBOX RELEASE => %s" % dts)
		if dts<0.3:
			zyngui.zynswitch_defered('S',3)

	def cb_listbox_motion(self,event):
		dts=(datetime.now()-self.listbox_push_ts).total_seconds()
		if dts>0.1:
			#logging.debug("LISTBOX MOTION => %d" % self.index)
			self.zselector.set_value(self.get_cursel(), True)

#-------------------------------------------------------------------------------
# Zynthian Info GUI Class
#-------------------------------------------------------------------------------
class zynthian_gui_info:

	def __init__(self):
		self.shown=False
		self.canvas = tkinter.Canvas(top,
			width = width,
			height = height,
			bd=1,
			highlightthickness=0,
			relief='flat',
			bg = color_bg)

		self.text = tkinter.StringVar()
		self.label_text = tkinter.Label(self.canvas,
			font=(font_family,10,"normal"),
			textvariable=self.text,
			#wraplength=80,
			justify=tkinter.LEFT,
			bg=color_bg,
			fg=color_tx)
		self.label_text.place(x=1, y=0, anchor=tkinter.NW)

	def clean(self):
		self.text.set("")

	def set(self, text):
		self.text.set(text)

	def add(self, text):
		self.text.set(self.text.get()+text)

	def hide(self):
		if self.shown:
			self.shown=False
			self.canvas.grid_forget()

	def show(self, text):
		self.text.set(text)
		if not self.shown:
			self.shown=True
			self.canvas.grid()

	def zyncoder_read(self):
		pass

	def refresh_loading(self):
		pass

#-------------------------------------------------------------------------------
# Zynthian Admin GUI Class
#-------------------------------------------------------------------------------
class zynthian_gui_admin(zynthian_selector):

	def __init__(self):
		self.commands=None
		self.thread=None
		self.child_pid=None
		self.last_action=None
		super().__init__('Action', True)
    
	def fill_list(self):
		self.list_data=[]
		self.list_data.append((self.update_software,0,"Update Zynthian Software"))
		self.list_data.append((self.update_library,0,"Update Zynthian Library"))
		#self.list_data.append((self.update_system,0,"Update Operating System"))
		self.list_data.append((self.network_info,0,"Network Info"))
		self.list_data.append((self.test_audio,0,"Test Audio"))
		self.list_data.append((self.test_midi,0,"Test MIDI"))
		if self.is_process_running("jack_capture"):
			self.list_data.append((self.stop_recording,0,"Stop Recording"))
		else:
			self.list_data.append((self.start_recording,0,"Start Recording"))
		if self.is_service_active("wpa_supplicant"):
			self.list_data.append((self.stop_wifi,0,"Stop WIFI"))
		else:
			self.list_data.append((self.start_wifi,0,"Start WIFI"))
		if self.is_service_active("touchosc2midi"):
			self.list_data.append((self.stop_touchosc2midi,0,"Stop TouchOSC bridge"))
		else:
			self.list_data.append((self.start_touchosc2midi,0,"Start TouchOSC bridge"))
		if self.is_service_active("aubionotes"):
			self.list_data.append((self.stop_aubionotes,0,"Stop Audio->MIDI"))
		else:
			self.list_data.append((self.start_aubionotes,0,"Start Audio->MIDI"))
		self.list_data.append((self.restart_gui,0,"Restart GUI"))
		#self.list_data.append((self.exit_to_console,0,"Exit to Console"))
		self.list_data.append((self.reboot,0,"Reboot"))
		self.list_data.append((self.power_off,0,"Power Off"))
		super().fill_list()

	def select_action(self, i):
		self.last_action=self.list_data[i][0]
		self.last_action()

	def set_select_path(self):
		self.select_path.set("Admin")

	def is_process_running(self, procname):
		cmd="ps -e | grep %s" % procname
		try:
			result=check_output(cmd, shell=True).decode('utf-8','ignore')
			if len(result)>3: return True
			else: return False
		except Exception as e:
			return False

	def is_service_active(self, service):
		cmd="systemctl is-active %s" % service
		try:
			result=check_output(cmd, shell=True).decode('utf-8','ignore')
		except Exception as e:
			result="ERROR: %s" % e
		#print("Is service "+str(service)+" active? => "+str(result))
		if result.strip()=='active': return True
		else: return False

	def execute_commands(self):
		zyngui.start_loading()
		for cmd in self.commands:
			logging.info("Executing Command: %s" % cmd)
			zyngui.add_info("\nExecuting:\n%s" % cmd)
			try:
				result=check_output(cmd, shell=True).decode('utf-8','ignore')
			except Exception as e:
				result="ERROR: %s" % e
			logging.info(result)
			zyngui.add_info("\nResult:\n%s" % result)
		self.commands=None
		zyngui.hide_info_timer(5000)
		zyngui.stop_loading()
		self.fill_list()

	def start_command(self,cmds):
		if not self.commands:
			logging.info("Starting Command Sequence ...")
			self.commands=cmds
			self.thread=Thread(target=self.execute_commands, args=())
			self.thread.daemon = True # thread dies with the program
			self.thread.start()

	def killable_execute_commands(self):
		#zyngui.start_loading()
		for cmd in self.commands:
			logging.info("Executing Command: %s" % cmd)
			zyngui.add_info("\nExecuting: %s" % cmd)
			try:
				proc=Popen(cmd.split(" "), stdout=PIPE, stderr=PIPE)
				self.child_pid=proc.pid
				zyngui.add_info("\nPID: %s" % self.child_pid)
				(output, error)=proc.communicate()
				self.child_pid=None
				if error:
					result="ERROR: %s" % error
				else:
					result=output
			except Exception as e:
				result="ERROR: %s" % e
			logging.info(result)
			zyngui.add_info("\n %s" % result)
		self.commands=None
		zyngui.hide_info_timer(5000)
		#zyngui.stop_loading()
		self.fill_list()

	def killable_start_command(self,cmds):
		if not self.commands:
			logging.info("Starting Command Sequence ...")
			self.commands=cmds
			self.thread=Thread(target=self.killable_execute_commands, args=())
			self.thread.daemon = True # thread dies with the program
			self.thread.start()

	def kill_command(self):
		if self.child_pid:
			logging.info("Killing process %s" % self.child_pid)
			os.kill(self.child_pid, signal.SIGTERM)
			self.child_pid=None
			if self.last_action==self.test_midi:
				check_output("systemctl stop a2jmidid", shell=True)
				zyngui.zyngine.all_sounds_off()

	def update_software(self):
		logging.info("UPDATE SOFTWARE")
		zyngui.show_info("UPDATE SOFTWARE")
		self.start_command(["cd ./sys-scripts;./update_zynthian.sh"])

	def update_library(self):
		logging.info("UPDATE LIBRARY")
		zyngui.show_info("UPDATE LIBRARY")
		self.start_command(["cd ./sys-scripts;./update_zynthian_data.sh"])

	def update_system(self):
		logging.info("UPDATE SYSTEM")
		zyngui.show_info("UPDATE SYSTEM")
		self.start_command(["cd ./sys-scripts;./update_system.sh"])

	def network_info(self):
		logging.info("NETWORK INFO")
		zyngui.show_info("NETWORK INFO:")
		self.start_command(["ifconfig | awk '/inet addr/{print substr($2,6)}'"])

	def test_audio(self):
		logging.info("TESTING AUDIO")
		zyngui.show_info("TEST AUDIO")
		self.killable_start_command(["mpg123 ./data/audio/test.mp3"])

	def test_midi(self):
		logging.info("TESTING MIDI")
		zyngui.show_info("TEST MIDI")
		check_output("systemctl start a2jmidid", shell=True)
		self.killable_start_command(["aplaymidi -p 14 ./data/mid/test.mid"])

	def start_recording(self):
		logging.info("RECORDING STARTED...")
		try:
			cmd=os.environ.get('ZYNTHIAN_SYS_DIR')+"/sbin/jack_capture.sh --zui"
			#logging.info("COMMAND: %s" % cmd)
			rec_proc=Popen(cmd,shell=True,env=os.environ)
			sleep(0.5)
			check_output("echo play | jack_transport", shell=True)
		except Exception as e:
			logging.error("ERROR STARTING RECORDING: %s" % e)
			zyngui.show_info("ERROR STARTING RECORDING:\n %s" % e)
			zyngui.hide_info_timer(5000)
		self.fill_list()

	def stop_recording(self):
		logging.info("STOPPING RECORDING...")
		check_output("echo stop | jack_transport", shell=True)
		while self.is_process_running("jack_capture"):
			sleep(1)
		self.fill_list()

	def start_wifi(self):
		logging.info("STARTING WIFI")
		check_output("systemctl start wpa_supplicant", shell=True)
		check_output("ifup wlan0", shell=True)
		self.fill_list()

	def stop_wifi(self):
		logging.info("STOPPING WIFI")
		check_output("systemctl stop wpa_supplicant", shell=True)
		check_output("ifdown wlan0", shell=True)
		self.fill_list()

	def start_touchosc2midi(self):
		logging.info("STARTING touchosc2midi")
		check_output("systemctl start touchosc2midi", shell=True)
		self.fill_list()

	def stop_touchosc2midi(self):
		logging.info("STOPPING touchosc2midi")
		check_output("systemctl stop touchosc2midi", shell=True)
		self.fill_list()

	def start_aubionotes(self):
		logging.info("STARTING aubionotes")
		check_output("systemctl start aubionotes", shell=True)
		self.fill_list()

	def stop_aubionotes(self):
		logging.info("STOPPING aubionotes")
		check_output("systemctl stop aubionotes", shell=True)
		self.fill_list()

	def restart_gui(self):
		logging.info("RESTART GUI")
		zyngui.exit(102)

	def exit_to_console(self):
		logging.info("EXIT TO CONSOLE")
		zyngui.exit(101)

	def reboot(self):
		logging.info("REBOOT")
		zyngui.exit(100)

	def power_off(self):
		logging.info("POWER OFF")
		zyngui.exit(0)

#-------------------------------------------------------------------------------
# Zynthian Load/Save Snapshot GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_snapshot(zynthian_selector):
	snapshot_dir=os.getcwd()+"/my-data/snapshots"

	def __init__(self):
		self.action="LOAD"
		super().__init__('Snapshot', True)
        
	def fill_list(self):
		self.list_data=[("NEW",0,"New")]
		i=1
		if self.action=="SAVE" or isfile(join(self.snapshot_dir,"default.zss")):
			self.list_data.append((join(self.snapshot_dir,"default.zss"),i,"Default"))
			i=i+1
		for f in sorted(os.listdir(self.snapshot_dir)):
			if isfile(join(self.snapshot_dir,f)) and f[-4:].lower()=='.zss' and f!="default.zss":
				title=str.replace(f[:-4], '_', ' ')
				#print("snapshot list => %s" % title)
				self.list_data.append((join(self.snapshot_dir,f),i,title))
				i=i+1
		super().fill_list()

	def show(self):
		if not zyngui.curlayer:
			self.action=="LOAD"
		super().show()
		
	def load(self):
		self.action="LOAD"
		self.show()

	def save(self):
		self.action="SAVE"
		self.show()
		
	def get_new_fpath(self):
		try:
			n=int(self.list_data[-1][2][3:])
		except:
			n=0;
		fname='{0:04d}'.format(n+1) + '.zss'
		fpath=join(self.snapshot_dir,fname)
		return fpath

	def select_action(self, i):
		fpath=self.list_data[i][0]
		if self.action=="LOAD":
			if fpath=='NEW':
				zyngui.screens['layer'].reset()
				zyngui.show_screen('layer')
			else:
				zyngui.screens['layer'].load_snapshot(fpath)
				#zyngui.show_screen('control')
		elif self.action=="SAVE":
			if fpath=='NEW':
				fpath=self.get_new_fpath()
			zyngui.screens['layer'].save_snapshot(fpath)
			zyngui.show_active_screen()

	def next(self):
		if self.action=="SAVE": self.action="LOAD"
		elif self.action=="LOAD": self.action="SAVE"
		self.show()

	def set_select_path(self):
		title=self.action.lower().title()
		self.select_path.set(title)

#-------------------------------------------------------------------------------
# Zynthian Layer Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_layer(zynthian_selector):

	def __init__(self):
		self.layers=[]
		self.curlayer=None
		self.add_layer_eng=None
		super().__init__('Layer', True)

	def reset(self):
		self.remove_all_layers()
		self.layers=[]
		self.curlayer=None
		self.index=0
		self.fill_list()

	def fill_list(self):
		self.list_data=[]
		#Add list of layers
		for i,layer in enumerate(self.layers):
			self.list_data.append((str(i+1),i,layer.get_fullpath()))
		#Add "New Layer" and "Clean" entry
		self.list_data.append(('NEW',len(self.list_data),"New Layer"))
		self.list_data.append(('RESET',len(self.list_data),"Remove All"))
		super().fill_list()

	def select_action(self, i):
		self.index=i
		if self.list_data[self.index][0]=='NEW':
			self.add_layer()
		elif self.list_data[self.index][0]=='RESET':
			self.reset()
		else:
			self.curlayer=self.layers[self.index]
			zyngui.set_curlayer(self.curlayer)
			# If there is an preset selection for the active layer ...
			if self.curlayer.get_preset_name():
				zyngui.show_screen('control')
			else:
				zyngui.show_screen('bank')
				# If there is only one bank, jump to preset selection
				if len(self.curlayer.bank_list)==1:
					zyngui.screens['bank'].select_action(0)

	def next(self):
		self.index=self.index+1;
		if self.index>=len(self.layers):
			self.index=0
		self.select_listbox(self.index)
		self.select_action(self.index)

	def get_num_layers(self):
		return len(self.layers)

	def add_layer(self):
		self.add_layer_eng=None
		zyngui.show_modal('engine')

	def add_layer_engine(self, eng):
		self.add_layer_eng=eng
		if eng.nickname=='MD':
			self.add_layer_midich(None)
		elif eng.nickname=='BF':
			self.add_layer_midich(0)
			self.add_layer_midich(1,False)
			self.add_layer_midich(2,False)
		else:
			zyngui.screens['midich'].set_mode("ADD")
			zyngui.show_modal('midich')

	def add_layer_midich(self, midich, select=True):
		if self.add_layer_eng:
			self.layers.append(zynthian_layer(self.add_layer_eng,midich,zyngui))
			self.fill_list()
			if select:
				self.index=len(self.layers)-1
				self.select_action(self.index)

	def remove_layer(self, i, cleanup_unused_engines=True):
		if i>=0 and i<len(self.layers):
			self.layers[i].reset()
			del self.layers[i]
			if len(self.layers)==0:
				self.index=0
				self.curlayer=None
			elif self.index>(len(self.layers)-1):
				self.index=len(self.layers)-1
				self.curlayer=self.layers[self.index]
			else:
				self.curlayer=self.layers[self.index-1]
			self.fill_list()
			self.set_selector()
			if cleanup_unused_engines:
				zyngui.screens['engine'].clean_unused_engines()

	def remove_all_layers(self, cleanup_unused_engines=True):
		while len(self.layers)>0:
			self.remove_layer(0, False)
		if cleanup_unused_engines:
			zyngui.screens['engine'].clean_unused_engines()

	#def refresh(self):
	#	self.curlayer.refresh()

	def set_midi_chan_preset(self, midich, preset_index):
		for layer in self.layers:
			mch=layer.get_midi_chan()
			if mch is None or mch==midich:
				#TODO => Pass PROGRAM CHANGE to Linuxsampler, MOD-UI, etc.
				layer.set_preset(preset_index,True)

	def set_select_path(self):
		self.select_path.set("Layer List")

	#-------------------------------------------------------------------------------
	# Snapshot Save & Load
	#-------------------------------------------------------------------------------

	def save_snapshot(self, fpath):
		try:
			snapshot={
				'index':self.index,
				'layers':[]
			}
			for layer in self.layers:
				snapshot['layers'].append(layer.get_snapshot())
			json=JSONEncoder().encode(snapshot)
			logging.info("Saving snapshot %s => \n%s" % (fpath,json))
		except Exception as e:
			logging.error("Can't generate snapshot: %s" %e)
			return False
		try:
			with open(fpath,"w") as fh:
				fh.write(json)
		except Exception as e:
			logging.error("Can't save snapshot '%s': %s" % (fpath,e))
			return False
		return True

	def load_snapshot(self, fpath):
		try:
			with open(fpath,"r") as fh:
				json=fh.read()
				logging.info("Loading snapshot %s => \n%s" % (fpath,json))
		except Exception as e:
			logging.error("Can't load snapshot '%s': %s" % (fpath,e))
			return False
		try:
			snapshot=JSONDecoder().decode(json)
			self.remove_all_layers(False)
			for lss in snapshot['layers']:
				engine=zyngui.screens['engine'].start_engine(lss['engine_nick'],1)
				self.layers.append(zynthian_layer(engine,lss['midi_chan'],zyngui))
				self.layers[-1].restore_snapshot(lss)
			self.fill_list()
			self.index=snapshot['index']
			self.select_action(self.index)
			zyngui.screens['engine'].clean_unused_engines()
		except Exception as e:
			logging.error("Invalid snapshot format: %s" % e)
			return False
		return True

#-------------------------------------------------------------------------------
# Zynthian Layer Options GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_layer_options(zynthian_selector):

	def __init__(self):
		super().__init__('Option', True)
		self.layer_index=None

	def fill_list(self):
		self.list_data=[]
		eng=zyngui.screens['layer'].layers[self.layer_index].engine.nickname
		if eng in ['ZY','LS','FS']:
			self.list_data.append((self.midi_chan,0,"MIDI Chan"))
		self.list_data.append((self.remove_layer,0,"Remove Layer"))
		super().fill_list()

	def show(self):
		self.layer_index=zyngui.screens['layer'].get_cursel()
		self.index=0
		super().show()

	def select_action(self, i):
		self.list_data[i][0]()

	def set_select_path(self):
		self.select_path.set("Layer Options")

	def midi_chan(self):
		zyngui.screens['midich'].set_mode("SET")
		zyngui.screens['midich'].index=zyngui.screens['layer'].layers[self.layer_index].midi_chan
		zyngui.show_modal('midich')

	def remove_layer(self):
		zyngui.screens['layer'].remove_layer(self.layer_index)
		zyngui.show_screen('layer')

#-------------------------------------------------------------------------------
# Zynthian Engine Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_engine(zynthian_selector):

	engine_info={
		"ZY": ("ZynAddSubFX","ZynAddSubFX - Synthesizer"),
		"FS": ("FluidSynth","FluidSynth - Sampler"),
		"LS": ("LinuxSampler","LinuxSampler - Sampler"),
		"BF": ("setBfree","setBfree - Hammond Emulator"),
		"MD": ("MOD-UI","MOD-UI - Plugin Host")
	}
	engine_order=["ZY","LS","FS","BF","MD"]

	def __init__(self):
		self.zyngines={}
		super().__init__('Engine', True)
    
	def fill_list(self):
		self.index=0
		if not self.list_data:
			self.list_data=[]
			i=0
			for en in self.engine_order:
				ei=self.engine_info[en]
				self.list_data.append((en,i,ei[1],ei[0]))
				i=i+1
			super().fill_list()
		else:
			self.select(self.index)

	def select_action(self, i):
		try:
			zyngui.screens['layer'].add_layer_engine(self.start_engine(self.list_data[i][0]))
		except Exception as e:
			logging.error("Can't add layer %s => %s" % (self.list_data[i][2],e))

	def start_engine(self, eng, wait=0):
		if eng not in self.zyngines:
			if eng=="ZY":
				self.zyngines[eng]=zynthian_engine_zynaddsubfx(zyngui)
			elif eng=="LS":
				self.zyngines[eng]=zynthian_engine_linuxsampler(zyngui)
			elif eng=="FS":
				self.zyngines[eng]=zynthian_engine_fluidsynth(zyngui)
			elif eng=="BF":
				self.zyngines[eng]=zynthian_engine_setbfree(zyngui)
			elif eng=="MD":
				self.zyngines[eng]=zynthian_engine_modui(zyngui)
			else:
				return None
			if wait>0:
				sleep(wait)
			zynautoconnect.autoconnect()
		else:
			pass
			#TODO => Check Engine Name and Status
		return self.zyngines[eng]

	def stop_engine(self, eng, wait=0):
		if eng in self.zyngines:
			self.zyngines[eng].stop()
			del self.zyngines[eng]
			if wait>0:
				sleep(wait)

	def clean_unused_engines(self):
		for eng in list(self.zyngines.keys()):
			if len(self.zyngines[eng].layers)==0:
				self.zyngines[eng].stop()
				self.zyngines.pop(eng, None)

	def get_engine_info(self, eng):
		return self.engine_info[eng]

	def set_select_path(self):
		self.select_path.set("Engine")

#-------------------------------------------------------------------------------
# Zynthian MIDI Channel Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_midich(zynthian_selector):

	def __init__(self, max_chan=16):
		self.mode='ADD'
		self.max_chan=max_chan
		super().__init__('Channel', True)

	def set_mode(self, mode):
		self.mode=mode

	def fill_list(self):
		self.list_data=[]
		for i in range(self.max_chan):
			self.list_data.append((str(i+1),i,"MIDI CH#"+str(i+1)))
		super().fill_list()

	def show(self):
		super().show()

	def select_action(self, i):
		if self.mode=='ADD':
			zyngui.screens['layer'].add_layer_midich(self.list_data[i][1])
		elif self.mode=='SET':
			layer_index=zyngui.screens['layer_options'].layer_index
			zyngui.screens['layer'].layers[layer_index].set_midi_chan(self.list_data[i][1])
			zyngui.show_screen('layer')

	def set_select_path(self):
		self.select_path.set("MIDI Channel")

#-------------------------------------------------------------------------------
# Zynthian Bank Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_bank(zynthian_selector):

	def __init__(self):
		super().__init__('Bank', True)
    
	def fill_list(self):
		zyngui.curlayer.load_bank_list()
		self.list_data=zyngui.curlayer.bank_list
		super().fill_list()

	def show(self):
		self.index=zyngui.curlayer.get_bank_index()
		logging.debug("BANK INDEX => %s" % self.index)
		super().show()

	def select_action(self, i):
		zyngui.curlayer.set_bank(i)
		zyngui.show_screen('preset')
		# If there is only one preset, jump to instrument control
		if len(zyngui.curlayer.preset_list)==1:
			zyngui.screens['preset'].select_action(0)

	def set_select_path(self):
		if zyngui.curlayer:
			self.select_path.set(zyngui.curlayer.get_bankpath())

#-------------------------------------------------------------------------------
# Zynthian Instrument Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_preset(zynthian_selector):

	def __init__(self):
		super().__init__('Preset', True)
      
	def fill_list(self):
		zyngui.curlayer.load_preset_list()
		self.list_data=zyngui.curlayer.preset_list
		super().fill_list()

	def show(self):
		self.index=zyngui.curlayer.get_preset_index()
		super().show()

	def select_action(self, i):
		zyngui.curlayer.set_preset(i)
		zyngui.show_screen('control')

	def set_select_path(self):
		if zyngui.curlayer:
			self.select_path.set(zyngui.curlayer.get_fullpath())

#-------------------------------------------------------------------------------
# Zynthian Instrument Controller GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_control(zynthian_selector):
	mode=None

	ctrl_screens={}
	zcontrollers=[]
	screen_name=None

	zgui_controllers=[]
	zgui_controllers_map={}

	def __init__(self):
		super().__init__('Controllers',False)
		# Create Lock object to avoid concurrence problems
		self.lock=Lock();
		# Create "pusher" canvas => used in mode "select"
		self.pusher= tkinter.Frame(self.main_frame,
			width=ctrl_width,
			height=ctrl_height-1,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg = color_bg)

	def show(self):
		super().show()
		self.click_listbox()

	def hide(self):
		if self.shown:
			super().hide()
			for zc in self.zgui_controllers: zc.hide()
			if self.zselector: self.zselector.hide()

	def fill_list(self):
		self.list_data=[]
		i=0
		for cscr in zyngui.curlayer.get_ctrl_screens():
			self.list_data.append((cscr,i,cscr))
			i=i+1
		self.index=zyngui.curlayer.get_active_screen_index()
		super().fill_list()

	def set_selector(self):
		if self.mode=='select': super().set_selector()

	#def get_controllers(self):
	#	return 

	def set_controller_screen(self):
		#Get Mutex Lock 
		self.lock.acquire()
		#Get controllers for the current screen
		zyngui.curlayer.set_active_screen_index(self.index)
		self.zcontrollers=zyngui.curlayer.get_active_screen()
		#Setup GUI Controllers
		if self.zcontrollers:
			logging.debug("SET CONTROLLER SCREEN %s" % (zyngui.curlayer.ctrl_screen_active))
			#Configure zgui_controllers
			i=0
			for ctrl in self.zcontrollers:
				try:
					#logging.debug("CONTROLLER ARRAY %d => %s" % (i,ctrl.name))
					self.set_zcontroller(i,ctrl)
					i=i+1
				except Exception as e:
					if raise_exceptions:
						raise e
					else:
						logging.error("Controller %s (%d) => %s" % (ctrl.short_name,i,e))
						self.zgui_controllers[i].hide()
			#Hide rest of GUI controllers
			for i in range(i,len(self.zgui_controllers)):
				self.zgui_controllers[i].hide()
		#Hide All GUI controllers
		else:
			for zgui_controller in self.zgui_controllers:
				zgui_controller.hide()
		#Release Mutex Lock
		self.lock.release()

	def set_zcontroller(self, i, ctrl):
		if i < len(self.zgui_controllers):
			self.zgui_controllers[i].config(ctrl)
			self.zgui_controllers[i].show()
		else:
			self.zgui_controllers.append(zynthian_gui_controller(i,self.main_frame,ctrl))
		self.zgui_controllers_map[ctrl]=self.zgui_controllers[i]

	def set_mode_select(self):
		self.mode='select'
		for i in range(0,4):
			self.zgui_controllers[i].hide()
		if select_ctrl>1:
			self.pusher.grid(row=2,column=0)
		else:
			self.pusher.grid(row=2,column=2)
		self.set_selector()
		self.listbox.config(selectbackground=color_ctrl_bg_on, selectforeground=color_ctrl_tx, fg=color_ctrl_tx)
		#self.listbox.config(selectbackground=color_ctrl_bg_off, selectforeground=color_ctrl_tx, fg=color_ctrl_tx_off)
		self.select(self.index)
		self.set_select_path()

	def set_mode_control(self):
		self.mode='control'
		if self.zselector: self.zselector.hide()
		self.pusher.grid_forget();
		self.set_controller_screen()
		self.listbox.config(selectbackground=color_ctrl_bg_on, selectforeground=color_ctrl_tx, fg=color_ctrl_tx)
		self.set_select_path()

	def select_action(self, i):
		self.set_mode_control()

	def next(self):
		self.index+=1
		if self.index>=len(self.list_data):
			self.index=0
		self.select(self.index)
		self.click_listbox()
		return True

	def switch_select(self):
		if self.mode=='control':
			self.set_mode_select()
		elif self.mode=='select':
			self.click_listbox()

	def zyncoder_read(self):
		#Get Mutex Lock
		self.lock.acquire()
		#Read Controller
		if self.mode=='control' and self.zcontrollers:
			for i, ctrl in enumerate(self.zcontrollers):
				#print('Read Control ' + str(self.zgui_controllers[i].title))
				self.zgui_controllers[i].read_zyncoder()
		elif self.mode=='select':
			super().zyncoder_read()
		#Release Mutex Lock
		self.lock.release()

	def get_zgui_controller(self, zctrl):
		for zgui_controller in self.zgui_controllers:
			if zgui_controller.zctrl==zctrl:
				return zgui_controller

	def get_zgui_controller_by_index(self, i):
		return self.zgui_controllers[i]

	def set_controller_value(self, zctrl, val=None):
		if val is not None:
			zctrl.set_value(val)
		for zgui_controller in self.zgui_controllers:
			if zgui_controller.zctrl==zctrl:
				zgui_controller.zctrl_sync()

	def set_controller_value_by_index(self, i, val=None):
		zgui_controller=self.zgui_controllers[i]
		if val is not None:
			zgui_controller.zctrl.set_value(val)
		zgui_controller.zctrl_sync()

	def get_controller_value(self, zctrl):
		for i in self.zgui_controllers:
			if self.zgui_controllers[i].zctrl==zctrl:
				return zctrl.get_value()

	def get_controller_value_by_index(self, i):
		return self.zgui_controllers[i].zctrl.get_value()

	def midi_learn(self, i):
		if self.mode=='control':
			zyngui.curlayer.midi_learn(self.zgui_controllers[i].zctrl)

	def midi_unlearn(self, i):
		if self.mode=='control':
			zyngui.curlayer.midi_unlearn(self.zgui_controllers[i].zctrl)

	def cb_listbox_release(self,event):
		if self.mode=='select':
			super().cb_listbox_release(event)
		else:
			dts=(datetime.now()-self.listbox_push_ts).total_seconds()
			#logging.debug("LISTBOX RELEASE => %s" % dts)
			if dts<0.3:
				zyngui.start_loading()
				self.click_listbox()
				zyngui.stop_loading()

	def cb_listbox_motion(self,event):
		if self.mode=='select':
			super().cb_listbox_motion(event)
		else:
			dts=(datetime.now()-self.listbox_push_ts).total_seconds()
			if dts>0.1:
				index=self.get_cursel()
				if index!=self.index:
					#logging.debug("LISTBOX MOTION => %d" % self.index)
					zyngui.start_loading()
					self.select_listbox(self.get_cursel())
					zyngui.stop_loading()
					sleep(0.04)

	def set_select_path(self):
		if zyngui.curlayer:
			self.select_path.set(zyngui.curlayer.get_fullpath())

#-------------------------------------------------------------------------------
# Zynthian X-Y Controller GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_control_xy():
	canvas=None
	hline=None
	vline=None
	shown=False

	def __init__(self):
		# Init X vars
		self.padx=24
		self.width=width-2*self.padx
		self.x=self.width/2
		self.xgui_controller=None
		self.xvalue_max=127
		self.xvalue=64

		# Init X vars
		self.pady=18
		self.height=height-2*self.pady
		self.y=self.height/2
		self.ygui_controller=None
		self.yvalue_max=127
		self.yvalue=64

		# Main Frame
		self.main_frame = tkinter.Frame(top,
			width=width,
			height=height,
			bg=color_panel_bg)

		# Create Canvas
		self.canvas= tkinter.Canvas(self.main_frame,
			width=self.width,
			height=self.height,
			#bd=0,
			highlightthickness=0,
			relief='flat',
			bg=color_bg)
		self.canvas.grid(padx=(self.padx,self.padx),pady=(self.pady,self.pady))

		# Setup Canvas Callback
		self.canvas.bind("<B1-Motion>", self.cb_canvas)

		# Create Cursor
		self.hline=self.canvas.create_line(0,self.y,width,self.y,fill=color_on)
		self.vline=self.canvas.create_line(self.x,0,self.x,width,fill=color_on)

		# Show
		self.show()

	def show(self):
		if not self.shown:
			self.shown=True
			self.main_frame.grid()
			self.refresh()

	def hide(self):
		if self.shown:
			self.shown=False
			self.main_frame.grid_forget()

	def set_controllers(self, xctrl, yctrl):
		self.xgui_controller=zyngui.screens['control'].get_zgui_controller_by_index(xctrl)
		self.ygui_controller=zyngui.screens['control'].get_zgui_controller_by_index(yctrl)
		self.xvalue_max=self.xgui_controller.max_value
		self.yvalue_max=self.ygui_controller.max_value
		self.get_controller_values()

	def get_controller_values(self):
		xv=self.xgui_controller.value
		if xv!=self.xvalue:
			self.xvalue=xv
			self.x=int(self.xvalue*width/self.xvalue_max)
			self.canvas.coords(self.vline,self.x,0,self.x,width)
		yv=self.ygui_controller.value
		if yv!=self.yvalue:
			self.yvalue=yv
			self.y=int(self.yvalue*height/self.yvalue_max)
			self.canvas.coords(self.hline,0,self.y,width,self.y)

	def refresh(self):
		self.xvalue=int(self.x*self.xvalue_max/self.width)
		self.yvalue=int(self.y*self.yvalue_max/self.height)
		self.canvas.coords(self.hline,0,self.y,width,self.y)
		self.canvas.coords(self.vline,self.x,0,self.x,width)
		if self.xgui_controller is not None:
			self.xgui_controller.set_value(self.xvalue,True)
		if self.ygui_controller is not None:
			self.ygui_controller.set_value(self.yvalue,True)

	def cb_canvas(self, event):
		#logging.debug("XY controller => %s, %s" % (event.x, event.y))
		self.x=event.x
		self.y=event.y
		self.refresh()

	def zyncoder_read(self):
		zyngui.screens['control'].zyncoder_read()
		self.get_controller_values()

	def refresh_loading(self):
		pass

#-------------------------------------------------------------------------------
# Zynthian OSC Browser GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_osc_browser(zynthian_selector):
	mode=None
	osc_path=None

	def __init__(self):
		super().__init__("OSC Path", True)
		self.mode=None
		self.osc_path=None
		self.index=1
		self.set_select_path()

	def get_list_data(self):
		pass

	def show(self):
		self.index=1
		super().show()

	def select_action(self, i):
		pass

	def get_osc_paths(self, path=''):
		self.list_data=[]
		if path=='root':
			self.osc_path="/part"+str(zyngui.curlayer.get_midi_chan())+"/"
		else:
			self.osc_path=self.osc_path+path
		liblo.send(zyngui.osc_target, "/path-search",self.osc_path,"")
		logging.debug("OSC /path-search "+self.osc_path)

	def select_action(self, i):
		path=self.list_data[i][0]
		tnode=self.list_data[i][1]
		title=self.list_data[i][2]
		logging.info("SELECT PARAMETER: %s (%s)" % (title,tnode))
		if tnode=='dir':
			self.get_osc_paths(path)
		elif tnode=='ctrl':
			parts=self.osc_path.split('/')
			if len(parts)>1:
				title=parts[-2]+" "+title
			zyngui.screens['control'].zcontrollers_config[2]=(title[:-2],self.osc_path+path,64,127) #TODO
			liblo.send(zyngui.osc_target, self.osc_path+path)
			zyngui.show_screen('control')
		elif tnode=='bool':
			#TODO: Toogle the value!!
			liblo.send(zyngui.osc_target, self.osc_path+path,True)
			zyngui.show_screen('control')

	def set_select_path(self):
		self.select_path.set(zyngui.zyngine.get_fullpath())


#-------------------------------------------------------------------------------
# Zynthian Main GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui:
	amidi=None
	zynmidi=None
	screens={}
	active_screen=None
	modal_screen=None
	screens_sequence=("admin","layer","bank","preset","control")
	curlayer=None

	dtsw={}
	polling=False
	osc_target=None
	osc_server=None

	loading=0
	loading_thread=None
	zyncoder_thread=None
	zynread_wait_flag=False
	zynswitch_defered_event=None
	exit_flag=False
	exit_code=0

	def __init__(self):
		# Initialize Controllers (Rotary and Switches), MIDI and OSC
		try:
			global lib_zyncoder
			zyngine_osc_port=6693
			lib_zyncoder_init(zyngine_osc_port)
			lib_zyncoder=zyncoder.get_lib_zyncoder()
			#self.amidi=zynthian_midi("Zynthian_gui")
			self.zynmidi=zynthian_zcmidi()
			self.zynswitches_init()
		except Exception as e:
			logging.error("ERROR initializing GUI: %s" % e)

	def start(self):
		# Create initial GUI Screens
		self.screens['admin']=zynthian_gui_admin()
		self.screens['info']=zynthian_gui_info()
		self.screens['snapshot']=zynthian_gui_snapshot()
		self.screens['layer']=zynthian_gui_layer()
		self.screens['layer_options']=zynthian_gui_layer_options()
		self.screens['engine']=zynthian_gui_engine()
		self.screens['midich']=zynthian_gui_midich()
		self.screens['bank']=zynthian_gui_bank()
		self.screens['preset']=zynthian_gui_preset()
		self.screens['control']=zynthian_gui_control()
		self.screens['control_xy']=zynthian_gui_control_xy()
		# Show initial screen => Channel list
		self.show_screen('layer')
		# Start polling threads
		self.start_polling()
		self.start_loading_thread()
		self.start_zyncoder_thread()
		# Try to load "default snapshot" or show "load snapshot" popup
		if not self.screens['layer'].load_snapshot('default.zss'):
			self.load_snapshot(autoclose=True)

	def stop(self):
		self.screens['layer'].reset()

	def hide_screens(self,exclude=None):
		if not exclude:
			exclude=self.active_screen
		for screen_name,screen in self.screens.items():
			if screen_name!=exclude:
				screen.hide();

	def show_active_screen(self):
		self.screens[self.active_screen].show()
		self.hide_screens()
		self.modal_screen=None

	def refresh_screen(self):
		if self.active_screen=='preset' and len(self.curlayer.preset_list)<=1:
			self.active_screen='control'
		self.show_active_screen()

	def show_screen(self,screen=None):
		if screen:
			self.active_screen=screen
		self.show_active_screen()

	def show_modal(self, screen):
		self.modal_screen=screen
		self.screens[screen].show()
		self.hide_screens(exclude=screen)

	def show_info(self, text, tms=None):
		self.modal_screen='info'
		self.screens['info'].show(text)
		self.hide_screens(exclude='info')
		if tms:
			top.after(tms, self.hide_info)

	def add_info(self, text):
		self.screens['info'].add(text)

	def hide_info_timer(self, tms=3000):
		top.after(tms, self.hide_info)

	def hide_info(self):
		self.screens['info'].hide()
		self.show_screen()

	def load_snapshot(self, autoclose=False):
		self.modal_screen='snapshot'
		self.screens['snapshot'].load()
		if not autoclose or len(self.screens['snapshot'].list_data)>1:
			self.hide_screens(exclude='snapshot')
		else:
			self.show_screen('layer')

	def save_snapshot(self):
		self.modal_screen='snapshot'
		self.screens['snapshot'].save()
		self.hide_screens(exclude='snapshot')

	def show_control_xy(self, xctrl, yctrl):
		self.modal_screen='control_xy'
		self.screens['control_xy'].set_controllers(xctrl, yctrl)
		self.screens['control_xy'].show()
		self.hide_screens(exclude='control_xy')
		self.active_screen='control'
		self.screens['control'].set_mode_control()
		logging.debug("SHOW CONTROL-XY => %d, %d" % (xctrl, yctrl))

	def set_curlayer(self, layer):
		self.start_loading()
		self.curlayer=layer
		self.screens['bank'].fill_list()
		self.screens['preset'].fill_list()
		self.screens['control'].fill_list()
		self.stop_loading()

	def get_curlayer_wait(self):
		#Try until layer is ready
		for j in range(100):
			if self.curlayer:
				return self.curlayer
			else:
				sleep(0.1)

	# -------------------------------------------------------------------
	# Switches
	# -------------------------------------------------------------------

	# Init GPIO Switches
	def zynswitches_init(self):
		if hw_version and lib_zyncoder:
			ts=datetime.now()
			logging.info("SWITCHES INIT...")
			for i,pin in enumerate(zynswitch_pin):
				self.dtsw[i]=ts
				lib_zyncoder.setup_zynswitch(i,pin)
				logging.info("SETUP GPIO SWITCH "+str(i)+" => "+str(pin))

	def zynswitches(self):
		if hw_version and lib_zyncoder:
			for i in range(len(zynswitch_pin)):
				dtus=lib_zyncoder.get_zynswitch_dtus(i)
				if dtus>0:
					#print("Switch "+str(i)+" dtus="+str(dtus))
					if dtus>300000:
						if dtus>2000000:
							self.zynswitch_long(i)
							return
						# Double switches must be bold!!! => by now ...
						if self.zynswitch_double(i):
							return
						self.zynswitch_bold(i)
						return
					self.zynswitch_short(i)

	def zynswitch_long(self,i):
		logging.info('Looooooooong Switch '+str(i))
		self.start_loading()
		if i==0:
			pass
		elif i==1:
			self.show_screen('admin')
		elif i==2:
			pass
		elif i==3:
			self.screens['admin'].power_off()
		self.stop_loading()

	def zynswitch_bold(self,i):
		logging.info('Bold Switch '+str(i))
		self.start_loading()
		if i==0 and self.active_screen!='layer':
			self.show_screen('layer')
		elif i==1 and self.active_screen!='bank':
			self.show_screen('bank')
		elif i==2:
			self.save_snapshot()
		elif i==3:
			if self.active_screen=='layer':
				self.show_modal('layer_options')
			else:
				self.screens[self.active_screen].switch_select()
		self.stop_loading()
		
	def zynswitch_short(self,i):
		logging.info('Short Switch '+str(i))
		self.start_loading()
		if i==0:
			if self.active_screen=='control':
				if self.screens['layer'].get_num_layers()>1:
					logging.info("Next layer")
					self.screens['layer'].next()
					self.show_screen('control')
				else:
					self.show_screen('layer')
			else:
				self.zynswitch_bold(i)
		elif i==1:
			# If in controller map selection, back to instrument control
			if self.active_screen=='control' and self.screens['control'].mode=='select':
				self.screens['control'].set_mode_control()
			else:
				# If modal screen, back to active screen
				if self.modal_screen:
					if self.modal_screen=='info':
						self.screens['admin'].kill_command()
					screen_back=self.active_screen
					logging.debug("CLOSE MODAL => " + self.modal_screen)
				# Else, go back to screen-1
				else:
					j=self.screens_sequence.index(self.active_screen)-1
					if j<0: j=1
					screen_back=self.screens_sequence[j]
				# If there is only one preset, go back to bank selection
				if screen_back=='preset' and len(self.curlayer.preset_list)<=1:
					screen_back='bank'
				# If there is only one bank, go back to layer selection
				if screen_back=='bank' and len(self.curlayer.bank_list)<=1:
					screen_back='layer'
				logging.debug("BACK TO SCREEN => "+screen_back)
				self.show_screen(screen_back)
		elif i==2:
			if self.modal_screen!='snapshot':
				self.load_snapshot()
			else:
				self.screens['snapshot'].next()
		elif i==3:
			if self.modal_screen:
				self.screens[self.modal_screen].switch_select()
			elif self.active_screen=='control' and self.screens['control'].mode=='control':
				self.screens['control'].next()
				logging.info("Next Control Screen")
			else:
				self.screens[self.active_screen].switch_select()
		self.stop_loading()

	def zynswitch_double(self,i):
		self.dtsw[i]=datetime.now()
		for j in range(4):
			if j==i: continue
			if abs((self.dtsw[i]-self.dtsw[j]).total_seconds())<0.3:
				self.start_loading()
				dswstr=str(i)+'+'+str(j)
				logging.info('Double Switch '+dswstr)
				self.show_control_xy(i,j)
				self.stop_loading()
				return True

	def zynswitch_X(self,i):
		logging.info('X Switch %d' % i)
		if self.active_screen=='control' and self.screens['control'].mode=='control':
			self.screens['control'].midi_learn(i)

	def zynswitch_Y(self,i):
		logging.info('Y Switch %d' % i)
		if self.active_screen=='control' and self.screens['control'].mode=='control':
			self.screens['control'].midi_unlearn(i)

	# -------------------------------------------------------------------
	# Switch Defered Event
	# -------------------------------------------------------------------

	def zynswitch_defered(self, t, i):
		self.zynswitch_defered_event=(t,i)

	def zynswitch_defered_exec(self):
		if self.zynswitch_defered_event is not None:
			#Copy event and clean variable
			event=copy.deepcopy(self.zynswitch_defered_event)
			self.zynswitch_defered_event=None
			#Process event
			if event[0]=='S':
				self.zynswitch_short(event[1])
			elif event[0]=='B':
				self.zynswitch_bold(event[1])
			elif event[0]=='L':
				self.zynswitch_long([1])
			elif event[0]=='X':
				self.zynswitch_X(event[1])
			elif event[0]=='Y':
				self.zynswitch_Y(event[1])

	# -------------------------------------------------------------------
	# Threads
	# -------------------------------------------------------------------

	def start_zyncoder_thread(self):
		if lib_zyncoder:
			self.zyncoder_thread=Thread(target=self.zyncoder_read, args=())
			self.zyncoder_thread.daemon = True # thread dies with the program
			self.zyncoder_thread.start()

	def zyncoder_read(self):
		while not self.exit_flag:
			if not self.loading: #TODO Es necesario???
				try:
					if self.modal_screen:
						self.screens[self.modal_screen].zyncoder_read()
					else:
						self.screens[self.active_screen].zyncoder_read()
					self.zynswitch_defered_exec()
					self.zynswitches()
				except Exception as err:
					if raise_exceptions:
						raise err
					else:
						logging.warning("zynthian_gui.zyncoder_read() => %s" % err)
			sleep(0.04)
			if self.zynread_wait_flag:
				sleep(0.3)
				self.zynread_wait_flag=False

	def start_loading_thread(self):
		self.loading_thread=Thread(target=self.loading_refresh, args=())
		self.loading_thread.daemon = True # thread dies with the program
		self.loading_thread.start()

	def start_loading(self):
		self.loading=self.loading+1
		if self.loading<1: self.loading=1
		#logging.debug("START LOADING %d" % self.loading)

	def stop_loading(self):
		self.loading=self.loading-1
		if self.loading<0: self.loading=0
		#logging.debug("STOP LOADING %d" % self.loading)

	def reset_loading(self):
		self.loading=0

	def loading_refresh(self):
		while not self.exit_flag:
			try:
				if self.modal_screen:
					self.screens[self.modal_screen].refresh_loading()
				else:
					self.screens[self.active_screen].refresh_loading()
			except Exception as err:
				logging.error("zynthian_gui.loading_refresh() => %s" % err)
			sleep(0.1)

	def exit(self, code=0):
		self.exit_flag=True
		self.exit_code=code

	# -------------------------------------------------------------------
	# Polling
	# -------------------------------------------------------------------
	
	def start_polling(self):
		self.polling=True
		if self.amidi:
			self.amidi_read()
		else:
			self.zynmidi_read()
		self.zyngine_refresh()

	def stop_polling(self):
		self.polling=False

	def after(self, msec, func):
		top.after(msec, func)

	def zynmidi_read(self):
		try:
			while lib_zyncoder:
				ev=lib_zyncoder.read_zynmidi()
				if ev==0: break
				evtype = (ev & 0xF0)>>4
				chan = ev & 0x0F
				if evtype==0xC:
					pgm = (ev & 0xF00)>>8
					logging.info("MIDI PROGRAM CHANGE " + str(pgm) + ", CH" + str(chan))
					self.screens['layer'].set_midi_chan_preset(chan, pgm)
					if not self.modal_screen and chan==self.curlayer.get_midi_chan():
						self.show_screen('control')
		except Exception as err:
			logging.error("zynthian_gui.zynmidi_read() => %s" % err)
		if self.polling:
			top.after(40, self.zynmidi_read)

	def amidi_read(self):
		try:
			while alsaseq.inputpending():
				event = alsaseq.input()
				chan = event[7][0]
				logging.debug("MIDI EVENT " + str(event[0]))
				if event[0]==alsaseq.SND_SEQ_EVENT_CONTROLLER:
					if chan==self.curlayer.get_midi_chan() and self.active_screen=='control': 
						ctrl = event[7][4]
						val = event[7][5]
						#print ("MIDI CTRL " + str(ctrl) + ", CH" + str(chan) + " => " + str(val))
						if ctrl in self.screens['control'].zgui_controllers_map.keys():
							self.screens['control'].zgui_controllers_map[ctrl].set_value(val,True)
				elif event[0]==alsaseq.SND_SEQ_EVENT_PGMCHANGE:
					pgm = event[7][4]
					val = event[7][5]
					logging.info("MIDI PROGRAM CHANGE " + str(pgm) + ", CH" + str(chan) + " => " + str(val))
					self.screens['layer'].set_midi_chan_preset(chan, pgm)
					if not self.modal_screen and chan==self.curlayer.get_midi_chan():
						self.show_screen('control')
		except Exception as err:
			logging.error("zynthian_gui.amidi_read() => %s" % err)
		if self.polling:
			top.after(40, self.amidi_read)

	def zyngine_refresh(self):
		try:
			if self.exit_flag:
				self.stop()
				sys.exit(self.exit_code)
			elif self.curlayer and not self.loading:
				self.curlayer.refresh()
		except Exception as err:
			if raise_exceptions:
				raise err
			else:
				logging.error("zynthian_gui.zyngine_refresh() => %s" % err)
		if self.polling:
			top.after(160, self.zyngine_refresh)

	# -------------------------------------------------------------------
	# OSC callbacks
	# -------------------------------------------------------------------

	def cb_osc_paths(self, path, args, types, src):
		if isinstance(zyngui.zyngine,zynthian_engine_zynaddsubfx):
			zyngui.zyngine.cb_osc_paths(path, args, types, src)
			self.screens['control'].list_data=zyngui.zyngine.osc_paths_data
			self.screens['control'].fill_list()

	def cb_osc_bank_view(self, path, args):
		pass

	def cb_osc_ctrl(self, path, args):
		#print ("OSC CTRL: " + path + " => "+str(args[0]))
		if path in self.screens['control'].zgui_controllers_map.keys():
			self.screens['control'].zgui_controllers_map[path].set_init_value(args[0])

	# -------------------------------------------------------------------
	# All Sounds Off => PANIC!
	# -------------------------------------------------------------------

	def all_sounds_off(self):
		for chan in range(16):
			self.zynmidi.set_midi_control(chan, 120, 0)


#-------------------------------------------------------------------------------
# GUI & Synth Engine initialization
#-------------------------------------------------------------------------------

zynautoconnect.start()
zyngui=zynthian_gui()
zyngui.start()

#-------------------------------------------------------------------------------
# Reparent Top Window using GTK XEmbed protocol features
#-------------------------------------------------------------------------------

def flushflush():
	for i in range(1000):
		print("FLUSHFLUSHFLUSHFLUSHFLUSHFLUSHFLUSH")
	top.after(200, flushflush)

if hw_version=="PROTOTYPE-EMU":
	top_xid=top.winfo_id()
	print("Zynthian GUI XID: "+str(top_xid))
	if len(sys.argv)>1:
		parent_xid=int(sys.argv[1])
		print("Parent XID: "+str(parent_xid))
		top.geometry('-10000-10000')
		top.overrideredirect(True)
		top.wm_withdraw()
		flushflush()
		top.after(1000, top.wm_deiconify)

#-------------------------------------------------------------------------------
# Catch SIGTERM
#-------------------------------------------------------------------------------

def sigterm_handler(_signo, _stack_frame):
	logging.info("Catch SIGTERM ...")
	zyngui.stop()
	top.destroy()

signal.signal(signal.SIGTERM, sigterm_handler)

#-------------------------------------------------------------------------------
# TKinter Main Loop
#-------------------------------------------------------------------------------

top.mainloop()
#zyngui.stop()

#-------------------------------------------------------------------------------
