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
import signal
import alsaseq
import logging
import liblo
import tkinter
from ctypes import *
from time import sleep
from string import Template
from json import JSONDecoder
from datetime import datetime
from threading  import Thread
from tkinter import font as tkFont
from os.path import isfile, isdir, join
from subprocess import check_output, Popen, PIPE

from zyngine import *
from zyngine.zynthian_engine import osc_port as zyngine_osc_port

from zyncoder import *
from zyncoder.zyncoder import lib_zyncoder, lib_zyncoder_init

from zyngine.zynthian_midi import *
from zyngine.zynthian_zcmidi import *

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
	log_level=logging.WARNING

if os.environ.get('ZYNTHIAN_RAISE_EXCEPTIONS'):
	raise_exceptions=int(os.environ.get('ZYNTHIAN_RAISE_EXCEPTIONS'))
elif raise_exceptions not in globals():
	raise_exceptions=False

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
if hw_version!="PROTOTYPE-EMU":
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
	hw_version="PROTOTYPE-4"
	logging.error("No HW version file. Default to PROTOTYPE-4.")

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
# Desktop Development & Emulation
elif hw_version=="PROTOTYPE-EMU":
	zyncoder_pin_a=[4,5,6,7]
	zyncoder_pin_b=[8,9,10,11]
	zynswitch_pin=[0,1,2,3]
	select_ctrl=3
# Default to PROTOTYPE-3
else:
	zyncoder_pin_a=[26,25,0,4]
	zyncoder_pin_b=[21,27,7,3]
	zynswitch_pin=[107,23,106,2]
	select_ctrl=2

#-------------------------------------------------------------------------------
# Controller GUI Class
#-------------------------------------------------------------------------------
class zynthian_controller:
	width=ctrl_width
	height=ctrl_height
	trw=ctrl_width-6
	trh=13

	ctrl=None
	midi_ctrl=None
	osc_path=None
	values=None
	ticks=None
	n_values=127
	max_value=127
	inverted=False
	step=1
	mult=1
	val0=0
	value=0
	value_plot=0
	scale_plot=1
	value_print=None
	value_font_size=14

	shown=False
	frame=None
	rectangle=None
	triangle=None
	arc=None
	value_text=None
	label_title=None

	def __init__(self, indx, frm, tit, chan, ctrl, val=0, max_val=127):
		self.index=indx
		self.main_frame=frm
		self.row=ctrl_pos[indx][0]
		self.col=ctrl_pos[indx][1]
		self.sticky=ctrl_pos[indx][2]
		self.plot_value=self.plot_value_arc
		self.erase_value=self.erase_value_arc
		# Create Canvas
		self.canvas= tkinter.Canvas(self.main_frame,
			width=self.width,
			height=self.height-1,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg = color_panel_bg)
		# Setup Controller and Zyncoder
		self.config(tit,chan,ctrl,val,max_val)
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
				self.value_print=self.values[i]
			except Exception as err:
				logging.error("zynthian_controller.calculate_plot_values() => %s" % (err))
				self.value_plot=self.value
				self.value_print="ERR"
		else:
			self.value_plot=self.value
			self.value_print=self.val0+self.value
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
		elif self.midi_ctrl!=0:
			self.rectangle_bg=self.canvas.create_rectangle((x1, y1, x1+lx, y2), fill=color_ctrl_bg_off, width=0)
			self.rectangle=self.canvas.create_rectangle((x1, y1, x2, y2), fill=color_ctrl_bg_on, width=0)
		if self.value_text:
			self.canvas.itemconfig(self.value_text, text=str(self.value_print))
		else:
			self.value_text=self.canvas.create_text(x1+self.trw/2-1, y1-self.trh, width=self.trw, justify=CENTER, fill=color_ctrl_tx, font=(font_family,self.value_font_size), text=str(self.value_print))

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
		elif self.midi_ctrl!=0:
			self.triangle_bg=self.canvas.create_polygon((x1, y1, x1+self.trw, y1, x1+self.trw, y1-self.trh), fill=color_ctrl_bg_off)
			self.triangle=self.canvas.create_polygon((x1, y1, x2, y1, x2, y2), fill=color_ctrl_bg_on)
		if self.value_text:
			self.canvas.itemconfig(self.value_text, text=str(self.value_print))
		else:
			self.value_text=self.canvas.create_text(x1+self.trw/2-1, y1-self.trh-8, width=self.trw, justify=CENTER, fill=color_ctrl_tx, font=(font_family,self.value_font_size), text=str(self.value_print))

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
		if (not self.arc and self.midi_ctrl!=0) or not self.value_text:
			x1=0.2*self.trw
			y1=self.height-int(0.7*self.trw)-6
			x2=x1+0.7*self.trw
			y2=self.height-6
		if self.arc:
			self.canvas.itemconfig(self.arc, extent=degd)
		elif self.midi_ctrl!=0:
			self.arc=self.canvas.create_arc(x1, y1, x2, y2, style=tkinter.ARC, outline=color_ctrl_bg_on, width=thickness, start=deg0, extent=degd)
		if self.value_text:
			self.canvas.itemconfig(self.value_text, text=str(self.value_print))
		else:
			self.value_text=self.canvas.create_text(x1+(x2-x1)/2-1, y1-(y1-y2)/2, width=x2-x1, justify=tkinter.CENTER, fill=color_ctrl_tx, font=(font_family,self.value_font_size), text=str(self.value_print))

	def erase_value_arc(self):
		if self.arc:
			self.canvas.delete(self.arc)
			self.arc=None
		x2=self.width
		y2=self.height
		if self.frame:
			self.canvas.coords(self.frame,(self.x, self.y, x2, self.y, x2, y2, self.x, y2))
		else:
			self.frame=self.canvas.create_polygon((self.x, self.y, x2, self.y, x2, y2, self.x, y2), outline=color_panel_bd, fill=color_panel_bg)

	def erase_frame(self):
		if self.frame:
			self.canvas.delete(self.frame)
			self.frame=None

		if self.value_text:
			self.canvas.delete(self.value_text)
			self.value_text=None

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
			if maxlen>4:
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
			self.value_font_size=14
		#Update font config in text object
		if self.value_text:
			self.canvas.itemconfig(self.value_text, font=(font_family,self.value_font_size))

	def config(self, tit, chan, ctrl, val, max_val=127):
		#print("CONFIG CONTROLLER "+str(self.index)+" => "+tit)
		self.chan=chan
		self.ctrl=ctrl
		self.inverted=False
		self.step=1
		self.mult=1
		self.val0=0
		self.ticks=None
		self.set_title(tit)

		#Type of Controller: OSC/MD, MIDI
		if isinstance(ctrl, str):
			ctrl=Template(ctrl)
			self.midi_ctrl=None
			self.osc_path=ctrl.substitute(ch=chan)
		else:
			self.midi_ctrl=ctrl
			self.osc_path=None

		#Controller "Range" is specified in max_val. There are different formats:
		# + String => labels separated by "|"
		if isinstance(max_val,str):
			self.values=max_val.split('|')
		# + List ...
		elif isinstance(max_val,list):
			# + List of Lists => list of values, list of labels
			if isinstance(max_val[0],list):
				self.values=max_val[0]
				self.ticks=max_val[1]
				if self.ticks[0]>self.ticks[1]:
					self.inverted=True
			# + Simple List => list of values
			else:
				self.values=max_val
		# + Scalar (integer)
		elif max_val>0:
			self.values=None
			self.max_value=self.n_values=max_val

		#Calculate some controller parameters
		if self.values:
			self.n_values=len(self.values)
			self.step=max(1,int(16/self.n_values));
			self.max_value=128-self.step;
			try:
				val=self.ticks[self.values.index(val)]
			except:
				val=int(self.values.index(val)*self.max_value/(self.n_values-1))
		elif not self.midi_ctrl:
			self.mult=max(1,int(128/self.n_values));

		#If "List Selection Controller" => step one option by rotary tick
		if self.midi_ctrl==0:
			self.mult=4
			self.val0=1
		#If many "ticks" => use adaptative step size based on rotary speed
		elif self.n_values>=96:
			self.step=0

		#Check value limits
		if val>self.max_value:
			val=self.max_value

		#Calculate scale parameter for plotting
		if self.ticks:
			self.scale_plot=self.max_value/abs(self.ticks[0]-self.ticks[self.n_values-1])
		elif self.n_values>1:
			self.scale_plot=self.max_value/(self.n_values-1)
		else:
			self.scale_plot=self.max_value

		#print("values: "+str(self.values))
		#print("ticks: "+str(self.ticks))
		#print("inverted: "+str(self.inverted))
		#print("n_values: "+str(self.n_values))
		#print("max_value: "+str(self.max_value))
		#print("step: "+str(self.step))
		#print("mult: "+str(self.mult))
		#print("val0: "+str(self.val0))
		#print("value: "+str(val))

		self.calculate_value_font_size()
		self.set_value(val)
		self.setup_zyncoder()
		
	def setup_zyncoder(self):
		self.init_value=None
		try:
			if self.osc_path:
				#print("Setup zyncoder "+str(self.index)+": "+self.osc_path)
				osc_path_char=c_char_p(self.osc_path.encode('UTF-8'))
				if zyngui.osc_target:
					liblo.send(zyngui.osc_target, self.osc_path)
			else:
				#print("Setup zyncoder "+str(self.index)+": "+str(self.midi_ctrl))
				osc_path_char=None

			if self.inverted:
				pin_a=zyncoder_pin_b[self.index]
				pin_b=zyncoder_pin_a[self.index]
			else:
				pin_a=zyncoder_pin_a[self.index]
				pin_b=zyncoder_pin_b[self.index]
			lib_zyncoder.setup_zyncoder(self.index,pin_a,pin_b,self.chan,self.midi_ctrl,osc_path_char,int(self.mult*self.value),int(self.mult*(self.max_value-self.val0)),self.step)
		except Exception as err:
			logging.error("zynthian_controller.setup_zyncoder() => %s" % (err))

	def set_value(self, v, set_zyncoder=False):
		if (v>self.max_value):
			v=self.max_value
		if (v!=self.value):
			self.value=v
			#print("RENCODER VALUE: " + str(self.index) + " => " + str(v))
			if self.shown:
				if set_zyncoder:
					if self.mult>1: v=self.mult*v
					if v>0: v=v-1
					lib_zyncoder.set_value_zyncoder(self.index,c_uint(v))
				self.plot_value()
			return True

	def set_init_value(self, v):
		if self.init_value is None:
			self.init_value=v
			self.set_value(v,True)
			logging.debug("RENCODER INIT VALUE "+str(self.index)+": "+str(v))

	def read_zyncoder(self):
		val=lib_zyncoder.get_value_zyncoder(self.index)
		#print("RENCODER RAW VALUE: " + str(self.index) + " => " + str(val))
		if self.mult>1:
			val=int((val+1)/self.mult)
		return self.set_value(val)

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
		self.listbox.bind('<<ListboxSelect>>', lambda event :self.click_listbox())

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
		self.select_listbox(self.index)
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
			self.zselector.config(self.selector_caption,0,0,self.index,len(self.list_data))
			self.zselector.show()
		else:
			self.zselector=zynthian_controller(select_ctrl,self.main_frame,self.selector_caption,0,0,self.index,len(self.list_data))

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
		_sel=self.zselector.value
		self.zselector.read_zyncoder()
		sel=self.zselector.value
		if (_sel!=sel):
			self.select_listbox(sel)

	def select_listbox(self,index):
		self.index=index
		self.listbox.selection_clear(0,tkinter.END)
		self.listbox.selection_set(index)
		self.listbox.see(index)

	def click_listbox(self):
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

#-------------------------------------------------------------------------------
# Zynthian Info GUI Class
#-------------------------------------------------------------------------------
class zynthian_gui_info:
	shown=False

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
	commands=None
	thread=None
	child_pid=None
	last_action=None

	def __init__(self):
		super().__init__('Action', True)
		self.commands=None
		self.thread=None
    
	def fill_list(self):
		if not self.list_data:
			self.list_data=[]
			self.list_data.append((self.update_software,0,"Update Zynthian Software"))
			self.list_data.append((self.update_library,0,"Update Zynthian Library"))
			#self.list_data.append((self.update_system,0,"Update Operating System"))
			self.list_data.append((self.network_info,0,"Network Info"))
			self.list_data.append((self.test_audio,0,"Test Audio"))
			self.list_data.append((self.test_midi,0,"Test MIDI"))
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

	def is_service_active(self, service):
		cmd="systemctl is-active "+str(service)
		try:
			result=check_output(cmd, shell=True).decode('utf-8','ignore')
		except Exception as e:
			result="ERROR: "+str(e)
		#print("Is service "+str(service)+" active? => "+str(result))
		if result.strip()=='active': return True
		else: return False

	def execute_commands(self):
		zyngui.start_loading()
		for cmd in self.commands:
			logging.info("Executing Command: "+cmd)
			zyngui.add_info("\nExecuting:\n"+cmd)
			try:
				result=check_output(cmd, shell=True).decode('utf-8','ignore')
			except Exception as e:
				result="ERROR: "+str(e)
			logging.info(result)
			zyngui.add_info("\nResult:\n"+str(result))
		self.commands=None
		zyngui.hide_info_timer(3000)
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
			logging.info("Executing Command: "+cmd)
			zyngui.add_info("\nExecuting: "+cmd)
			try:
				proc=Popen(cmd.split(" "), stdout=PIPE, stderr=PIPE)
				self.child_pid=proc.pid
				zyngui.add_info("\nPID: "+str(self.child_pid))
				(output, error)=proc.communicate()
				self.child_pid=None
				if error:
					result="ERROR: "+str(error)
				else:
					result=output
			except Exception as e:
				result="ERROR: "+str(e)
			logging.info(result)
			zyngui.add_info("\n"+str(result))
		self.commands=None
		zyngui.hide_info_timer(3000)
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
			logging.info("Killing process "+str(self.child_pid))
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
# Zynthian Engine Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_engine(zynthian_selector):
	zyngine=None

	engine_info={
		"ZY": ("ZynAddSubFX","ZynAddSubFX - Synthesizer"),
		"FS": ("FluidSynth","FluidSynth - Sampler"),
		"LS": ("LinuxSampler","LinuxSampler - Sampler"),
		"BF": ("setBfree","setBfree - Hammond Emulator"),
		#"CP": ("Carla","Carla - Plugin Host"),
		#"MH": ("MODHost","MODHost - Plugin Host"),
		"MD": ("MOD-UI","MOD-UI - Plugin Host")
	}
	engine_order=["ZY","LS","FS","BF","MD"]

	def __init__(self):
		super().__init__('Engine', True)
		self.zyngine=None
    
	def fill_list(self):
		if not self.list_data:
			self.list_data=[]
			i=0
			for en in self.engine_order:
				ei=self.engine_info[en]
				self.list_data.append((ei[0],i,ei[1],en))
				i=i+1
			super().fill_list()

	def select_action(self, i):
		zyngui.set_engine(self.list_data[i][0])
		if zyngui.zyngine.max_chan<=1:
			zyngui.screens['chan'].fill_list()
			zyngui.screens['chan'].select_action(0)
		else:
			zyngui.show_screen('chan')

	def set_select_path(self):
		self.select_path.set("Engine")

	def set_engine(self, name, wait=0):
		if self.zyngine:
			if self.zyngine.name==name:
				return True
			else:
				self.zyngine.stop()
		if name=="ZynAddSubFX" or name=="ZY":
			self.zyngine=zynthian_engine_zynaddsubfx(zyngui)
		elif name=="LinuxSampler" or name=="LS":
			self.zyngine=zynthian_engine_linuxsampler(zyngui)
		elif name=="FluidSynth" or name=="FS":
			self.zyngine=zynthian_engine_fluidsynth(zyngui)
		elif name=="setBfree" or name=="BF":
			self.zyngine=zynthian_engine_setbfree(zyngui)
		elif name=="Carla" or name=="CP":
			self.zyngine=zynthian_engine_carla(zyngui)
		elif name=="MODHost" or name=="MH":
			self.zyngine=zynthian_engine_modhost(zyngui)
		elif name=="MOD-UI" or name=="MD":
			self.zyngine=zynthian_engine_modui(zyngui)
		else:
			self.zyngine=None
			return False
		if wait>0: sleep(wait)
		return True

#-------------------------------------------------------------------------------
# Zynthian Load/Save Snapshot GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_snapshot(zynthian_selector):
	snapshot_dir=os.getcwd()+"/my-data/snapshots"
	action="LOAD"
	engine=""

	def __init__(self):
		super().__init__('Snapshot', True)
		self.action="LOAD"
		self.engine=""
        
	def fill_list(self):
		if self.engine: prefix=self.engine+"-"
		else: prefix=None
		self.list_data=[("NEW",0,"New",self.engine)]
		i=1
		if self.action=="SAVE" or (not self.engine and isfile(join(self.snapshot_dir,"default.zss"))):
			self.list_data.append((join(self.snapshot_dir,"default.zss"),i,"Default",self.engine))
			i=i+1
		for f in sorted(os.listdir(self.snapshot_dir)):
			if isfile(join(self.snapshot_dir,f)) and f[-4:].lower()=='.zss' and f!="default.zss" and ((prefix and f[0:len(prefix)]==prefix) or not prefix):
				title=str.replace(f[:-4], '_', ' ')
				engine=f[0:2]
				#print("snapshot list => %s (%s)" % (title,engine))
				self.list_data.append((join(self.snapshot_dir,f),i,title,engine))
				i=i+1
		super().fill_list()

	def show(self):
		if self.action=="SAVE":
			if zyngui.zyngine:
				self.engine=zyngui.zyngine.nickname
			else:
				self.action="LOAD"
				self.engine=""
		super().show()
		
	def load(self, engine=""):
		self.action="LOAD"
		self.engine=engine
		self.show()

	def save(self):
		self.action="SAVE"
		self.show()
		
	def get_new_fpath(self, engine):
		n=0;
		for i in range(-1,-len(self.list_data),-1):
			try:
				if self.list_data[i][3]==engine:
					n=int(self.list_data[i][2][3:])
					break
			except:
				pass
		fname=engine + '-' + '{0:03d}'.format(n+1) + '.zss'
		fpath=join(self.snapshot_dir,fname)
		return fpath

	def get_snapshot_engine(self, fpath):
		try:
			with open(fpath,"r") as fh:
				json=fh.read()
		except:
			logging.error("Can't load snapshot '%s'" % fpath)
			return False
		try:
			status=JSONDecoder().decode(json)
			engine=status['engine_nick']
			logging.debug("Snapshot engine => %s" % (engine))
			return engine
		except:
			logging.error("Invalid snapshot format => %s" % (fpath))
			return False

	def load_snapshot(self, fname):
		fpath=join(self.snapshot_dir,fname)
		engine=self.get_snapshot_engine(fpath)
		if engine:
			#Start engine if needed
			if not zyngui.zyngine or zyngui.zyngine.nickname!=engine:
				zyngui.set_engine(engine,2)
			#Load snapshot in engine
			zyngui.zyngine.load_snapshot(fpath)
			#Show control screen
			zyngui.show_screen('control')
			return True

	def select_action(self, i):
		fpath=self.list_data[i][0]
		engine=self.list_data[i][3]
		if self.action=="LOAD":
			if fpath=='NEW':
				if zyngui.zyngine and zyngui.zyngine.nickname==engine:
					zyngui.zyngine.clean()
					zyngui.show_screen('chan')
				else:
					zyngui.show_screen('engine')
			else:
				engine=self.get_snapshot_engine(fpath)
				if not zyngui.zyngine or zyngui.zyngine.nickname!=engine:
					zyngui.set_engine(engine,2)
				zyngui.zyngine.load_snapshot(fpath)
				#if zyngui.active_screen in ['admin', 'engine']: zyngui.show_screen('chan')
				#else: zyngui.show_active_screen()
				zyngui.show_screen('control')
		elif self.action=="SAVE":
			if fpath=='NEW':
				fpath=self.get_new_fpath(engine)
			zyngui.zyngine.save_snapshot(fpath)
			zyngui.show_active_screen()

	def next(self):
		if self.action=="SAVE": self.action="LOAD"
		elif self.action=="LOAD": self.action="SAVE"
		self.show()

	def set_select_path(self):
		title=self.action.lower().title()
		if self.engine:
			try:
				title=title + " " + zyngui.screens['engine'].engine_info[self.engine][0]
			except:
				pass
		self.select_path.set(title)

#-------------------------------------------------------------------------------
# Zynthian MIDI Channel Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_chan(zynthian_selector):
	max_chan=16

	def __init__(self, max_chan=16):
		self.max_chan=max_chan
		super().__init__('Channel', True)
    
	def fill_list(self):
		self.list_data=[]
		for i in range(self.max_chan):
			self.list_data.append((str(i+1),i,str(i+1)+">"+zyngui.zyngine.get_path(i)))
			#instr=zynmidi.get_midi_instr(i)
			#self.list_data.append((str(i+1),i,"Chan #"+str(i+1)+" -> Bank("+str(instr[0])+","+str(instr[1])+") Prog("+str(instr[2])+")"))
		super().fill_list()

	def show(self):
		self.index=zyngui.zyngine.get_midi_chan()
		super().show()

	def select_action(self, i):
		zyngui.zyngine.set_midi_chan(i)
		# If there is an instrument selection for the active channel ...
		if zyngui.zyngine.get_instr_name():
			zyngui.show_screen('control')
		else:
			zyngui.show_screen('bank')
			# If there is only one bank, jump to instrument selection
			if len(zyngui.zyngine.bank_list)==1:
				zyngui.screens['bank'].select_action(0)

	def next(self):
		if zyngui.zyngine.next_chan():
			zyngui.screens['bank'].fill_list()
			zyngui.screens['instr'].fill_list()
			zyngui.screens['control'].fill_list()
			self.index=zyngui.zyngine.get_midi_chan()
			self.select_listbox(self.index)
			return True
		return False

	def set_select_path(self):
		self.select_path.set(zyngui.zyngine.name)

#-------------------------------------------------------------------------------
# Zynthian Bank Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_bank(zynthian_selector):

	def __init__(self):
		super().__init__('Bank', True)
    
	def fill_list(self):
		zyngui.zyngine.load_bank_list()
		self.list_data=zyngui.zyngine.bank_list
		super().fill_list()

	def show(self):
		self.index=zyngui.zyngine.get_bank_index()
		super().show()

	def select_action(self, i):
		zyngui.zyngine.set_bank(i)
		zyngui.show_screen('instr')
		# If there is only one instrument, jump to instrument control
		if len(zyngui.zyngine.instr_list)==1:
			zyngui.screens['instr'].select_action(0)

	def set_select_path(self):
		self.select_path.set(zyngui.zyngine.nickname + "#" + str(zyngui.zyngine.get_midi_chan()+1))

#-------------------------------------------------------------------------------
# Zynthian Instrument Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_instr(zynthian_selector):

	def __init__(self):
		super().__init__('Instrument', True)
      
	def fill_list(self):
		zyngui.zyngine.load_instr_list()
		self.list_data=zyngui.zyngine.instr_list
		super().fill_list()

	def show(self):
		self.index=zyngui.zyngine.get_instr_index()
		super().show()

	def select_action(self, i):
		zyngui.zyngine.set_instr(i)
		zyngui.show_screen('control')

	def set_select_path(self):
		self.select_path.set(zyngui.zyngine.get_fullpath())

#-------------------------------------------------------------------------------
# Zynthian Instrument Controller GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_control(zynthian_selector):
	mode=None
	zcontrollers_config=None
	zcontroller_map={}
	zcontrollers=[]

	def __init__(self):
		super().__init__('Controllers',False)
		self.mode=None
		self.zcontrollers_config=None
		self.zcontroller_map={}
		self.zcontrollers=[]
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
			for zc in self.zcontrollers: zc.hide()
			if self.zselector: self.zselector.hide()

	def fill_list(self):
		if self.list_data!=zyngui.zyngine.get_ctrl_list():
			self.list_data=zyngui.zyngine.get_ctrl_list()
			super().fill_list()

	def set_selector(self):
		if self.mode=='select': super().set_selector()

	def set_controller_config(self):
		#self.zcontrollers_config=self.list_data[self.index][0]
		self.zcontrollers_config=zyngui.zyngine.get_ctrl_config(self.index)
		midi_chan=zyngui.zyngine.get_midi_chan()
		for i in range(0,4):
			try:
				if self.zcontrollers_config and i<len(self.zcontrollers_config):
					cfg=self.zcontrollers_config[i]
					#indx, tit, chan, ctrl, val, max_val=127
					self.set_controller(i,cfg[0],midi_chan,cfg[1],cfg[2],cfg[3])
				elif i<len(self.zcontrollers):
					self.zcontrollers[i].hide()
			except Exception as e:
				logging.error("set_controller_config(%d) => %s" % (i,e))
				self.zcontrollers[i].hide()

	def set_controller(self, i, tit, chan, ctrl, val, max_val=127):
		try:
			self.zcontrollers[i].config(tit,chan,ctrl,val,max_val)
			self.zcontrollers[i].show()
		except:
			self.zcontrollers.append(zynthian_controller(i,self.main_frame,tit,chan,ctrl,val,max_val))
		self.zcontroller_map[ctrl]=self.zcontrollers[i]

	def set_mode_select(self):
		self.mode='select'
		for i in range(0,4):
			self.zcontrollers[i].hide()
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
		self.set_controller_config()
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
		if self.mode=='control' and self.zcontrollers_config:
			for i, ctrl in enumerate(self.zcontrollers_config):
				#print('Read Control ' + str(self.zcontrollers[i].title))
				if self.zcontrollers[i].read_zyncoder():
					zyngui.zyngine.set_ctrl_value(ctrl,self.zcontrollers[i].value_print)
		elif self.mode=='select':
			_sel=self.zselector.value
			self.zselector.read_zyncoder()
			sel=self.zselector.value
			if (_sel!=sel):
				#print('Pre-select Parameter ' + str(sel))
				self.select_listbox(sel)

	def refresh_controller_value(self, ctrl, val=None):
		if self.mode=='control' and self.zcontrollers_config:
			if isinstance(ctrl,int):
				i=ctrl
				zyngui.zyngine.send_ctrl_value(self.zcontrollers_config[i],val)
				self.zcontrollers[i].set_value(val,True)
				zyngui.zynread_wait_flag=True
			else:
				for i, ctrl_i in enumerate(self.zcontrollers_config):
					if ctrl==ctrl_i:
						zyngui.zyngine.send_ctrl_value(ctrl,val)
						self.zcontrollers[i].set_value(val,True)
						zyngui.zynread_wait_flag=True

	def get_controller_value(self, ctrl):
		if self.mode=='control' and self.zcontrollers_config:
			if isinstance(ctrl,int):
				return self.zcontrollers_config[ctrl][2]
			else:
				for i, ctrl_i in enumerate(self.zcontrollers_config):
					if ctrl==ctrl_i:
						return ctrl[2]

	def set_select_path(self):
		self.select_path.set(zyngui.zyngine.get_fullpath())

#-------------------------------------------------------------------------------
# Zynthian X-Y Controller GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_control_xy():
	canvas=None
	hline=None
	vline=None

	shown=False

	x=width/2
	xvalue_min=0
	xvalue_max=127
	xvalue=64
	xctrl=None

	y=height/2
	yvalue_min=0
	yvalue_max=127
	yvalue=64
	yctrl=None

	def __init__(self):
		# Create Main Canvas
		self.canvas= tkinter.Canvas(top,
			width=width,
			height=height,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg=color_bg)
		# Setup Canvas Callback
		self.canvas.bind("<B1-Motion>", self.cb_canvas)
		# Create Cursor
		self.hline=self.canvas.create_line(0,self.y,width,self.y,fill="#ff0000")
		self.vline=self.canvas.create_line(self.x,0,self.x,width,fill="#ff0000")
		# Show
		self.show()

	def show(self):
		if not self.shown:
			self.shown=True
			self.canvas.grid()
			self.refresh()

	def hide(self):
		if self.shown:
			self.shown=False
			self.canvas.grid_forget()

	def set_ranges(self, xv_min, xv_max, yv_min, yv_max):
		self.xvalue_min=xv_min
		self.xvalue_max=xv_max
		self.yvalue_min=yv_min
		self.yvalue_max=yv_max

	def set_controllers(self, xctrl, yctrl):
		self.xctrl=xctrl
		self.yctrl=yctrl
		self.get_controller_values()

	def get_controller_values(self):
		self.xvalue=zyngui.screens['control'].get_controller_value(self.xctrl)
		self.yvalue=zyngui.screens['control'].get_controller_value(self.yctrl)
		self.x=int(self.xvalue*width/self.xvalue_max)
		self.y=int(self.yvalue*height/self.yvalue_max)
		self.canvas.coords(self.hline,0,self.y,width,self.y)
		self.canvas.coords(self.vline,self.x,0,self.x,width)

	def refresh(self):
		self.xvalue=int(self.x*self.xvalue_max/width)
		self.yvalue=int(self.y*self.yvalue_max/height)
		self.canvas.coords(self.hline,0,self.y,width,self.y)
		self.canvas.coords(self.vline,self.x,0,self.x,width)
		zyngui.screens['control'].refresh_controller_value(self.xctrl, self.xvalue)
		zyngui.screens['control'].refresh_controller_value(self.yctrl, self.yvalue)

	def cb_canvas(self, event):
		logging.debug("XY controller => %s, %s" % (event.x, event.y))
		self.x=event.x
		self.y=event.y
		self.refresh()

	def zyncoder_read(self):
		pass

	def refresh_loading(self):
		pass

#-------------------------------------------------------------------------------
# Zynthian OSC Browser GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_osc_browser(zynthian_selector):
	mode=None
	osc_path=None

	def __init__(self):
		super().__init__("OSC Browser", True)
		self.mode=None
		self.osc_path=None
		self.index=1
		self.zselector=zynthian_controller(select_ctrl,self.canvas,"Path",0,0,self.index,len(self.list_data))
		self.set_select_path()

	def get_list_data(self):
		pass

	def show(self):
		self.index=1
		super().show()
		if self.zselector:
			self.zselector.config("Path",0,0,self.index,len(self.list_data))

	def select_action(self, i):
		pass

	def get_osc_paths(self, path=''):
		self.list_data=[]
		if path=='root':
			self.osc_path="/part"+str(zyngui.zyngine.get_midi_chan())+"/"
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

	def zyncoder_read(self):
		_sel=self.zselector.value
		self.zselector.read_zyncoder()
		sel=self.zselector.value
		if (_sel!=sel):
			#print('Pre-select Bank ' + str(sel))
			self.select_listbox(sel)

	def set_select_path(self):
		self.select_path.set(zyngui.zyngine.get_fullpath())


#-------------------------------------------------------------------------------
# Zynthian Main GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui:
	amidi=None
	zynmidi=None
	zyngine=None
	screens={}
	active_screen=None
	modal_screen=None
	screens_sequence=("admin","engine","chan","bank","instr","control")

	dtsw={}
	polling=False
	osc_target=None
	osc_server=None

	loading=0
	loading_thread=None
	zyncoder_thread=None
	zynread_wait_flag=False
	exit_flag=False
	exit_code=0

	def __init__(self):
		# Initialize Controllers (Rotary and Switches), MIDI and OSC
		try:
			global lib_zyncoder
			lib_zyncoder_init(zyngine_osc_port)
			lib_zyncoder=zyncoder.get_lib_zyncoder()
			#self.amidi=zynthian_midi("Zynthian_gui")
			self.zynmidi=zynthian_zcmidi()
			self.zynswitches_init()
		except Exception as e:
			logging.error("ERROR initializing GUI: %s" % e)
		# Create initial GUI Screens
		self.screens['admin']=zynthian_gui_admin()
		self.screens['info']=zynthian_gui_info()
		self.screens['engine']=zynthian_gui_engine()
		self.screens['snapshot']=zynthian_gui_snapshot()

	def start(self):
		# Show initial screen => Engine selection
		self.show_screen('engine')
		# Start polling threads
		self.start_polling()
		self.start_loading_thread()
		self.start_zyncoder_thread()
		# Try to load "default snapshot" or show "load snapshot" popup
		if not self.screens['snapshot'].load_snapshot('default.zss'):
			self.load_snapshot("",autoclose=True)

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
		if self.active_screen=='instr' and len(self.zyngine.instr_list)<=1:
			self.active_screen='control'
		self.show_active_screen()

	def show_screen(self,screen=None):
		if screen:
			self.active_screen=screen
		self.show_active_screen()

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

	def load_snapshot(self, engine="", autoclose=False):
		self.modal_screen='snapshot'
		self.screens['snapshot'].load(engine)
		if not autoclose or len(self.screens['snapshot'].list_data)>1:
			self.hide_screens(exclude='snapshot')
		else:
			self.show_screen('engine')

	def save_snapshot(self):
		self.modal_screen='snapshot'
		self.screens['snapshot'].save()
		self.hide_screens(exclude='snapshot')

	def show_control_xy(self, xctrl, yctrl):
		self.modal_screen='control_xy'
		self.screens['control_xy'].set_controllers(xctrl, yctrl)
		self.screens['control_xy'].show()
		self.hide_screens(exclude='control_xy')

	def set_engine(self, name, wait=0):
		self.start_loading()
		if self.screens['engine'].set_engine(name,wait):
			self.zyngine=self.screens['engine'].zyngine
			zynautoconnect.autoconnect()
			self.screens['chan']=zynthian_gui_chan(self.zyngine.max_chan)
			self.screens['bank']=zynthian_gui_bank()
			self.screens['instr']=zynthian_gui_instr()
			self.screens['control']=zynthian_gui_control()
			self.screens['control_xy']=zynthian_gui_control_xy()
		else:
			self.zyngine=None
			try:
				del self.screens['chan']
				del self.screens['bank']
				del self.screens['instr']
				del self.screens['control']
				del self.screens['control_xy']
			except: pass
		self.stop_loading()

	# -------------------------------------------------------------------
	# Switches
	# -------------------------------------------------------------------

	# Init GPIO Switches
	def zynswitches_init(self):
		ts=datetime.now()
		logging.info("SWITCHES INIT...")
		for i,pin in enumerate(zynswitch_pin):
			self.dtsw[i]=ts
			lib_zyncoder.setup_zynswitch(i,pin)
			logging.info("SETUP GPIO SWITCH "+str(i)+" => "+str(pin))

	def zynswitches(self):
		for i in range(len(zynswitch_pin)):
			dtus=lib_zyncoder.get_zynswitch_dtus(i)
			if dtus>0:
				#print("Switch "+str(i)+" dtus="+str(dtus))
				if dtus>300000:
					if dtus>2000000:
						logging.info('Looooooooong Switch '+str(i))
						self.zynswitch_long(i)
						return
					# Double switches must be bold!!! => by now ...
					if self.zynswitch_double(i):
						return
					logging.info('Bold Switch '+str(i))
					self.zynswitch_bold(i)
					return
				logging.info('Short Switch '+str(i))
				self.zynswitch_short(i)

	def zynswitch_long(self,i):
		if i==0:
			pass
		elif i==1:
			self.show_screen('admin')
		elif i==2:
			pass
		elif i==3:
			self.screens['admin'].power_off()

	def zynswitch_bold(self,i):
		if i==0:
			if 'chan' in self.screens and self.active_screen!='chan':
				self.show_screen('chan')
			else:
				self.show_screen('engine')
		elif i==1:
			self.show_screen("engine")
		elif i==2:
			self.load_snapshot()
		elif i==3:
			self.screens[self.active_screen].switch_select()

	def zynswitch_short(self,i):
		if i==0:
			if self.active_screen=='control':
				if self.screens['chan'].next():
					logging.info("Next Chan")
					self.show_screen('control')
				else:
					self.zynswitch_bold(i)
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
				# Else, go back to screen-1
				else:
					j=self.screens_sequence.index(self.active_screen)-1
					if j<0: j=1
					screen_back=self.screens_sequence[j]
				# If there is only one instrument, go back to bank selection
				if screen_back=='instr' and len(self.zyngine.instr_list)<=1:
					screen_back='bank'
				# If there is only one bank, go back to channel selection
				if screen_back=='bank' and len(self.zyngine.bank_list)<=1:
					screen_back='chan'
				# If there is only one chan, go back to engine selection
				if screen_back=='chan' and self.zyngine.max_chan<=1:
					screen_back='engine'
				#logging.debug("BACK TO SCREEN "+str(j)+" => "+screen_back)
				self.show_screen(screen_back)
		elif i==2:
			if self.modal_screen!='snapshot':
				if self.active_screen=='admin' or self.active_screen=='engine':
					self.load_snapshot()
				else:
					self.load_snapshot(self.zyngine.nickname)
			else:
				self.screens['snapshot'].next()
		elif i==3:
			if self.modal_screen:
				self.screens[self.modal_screen].switch_select()
			elif self.active_screen=='control' and self.screens['control'].mode=='control':
				self.screens['control'].next()
				logging.info("Next Control Screen")
			else:
				self.zynswitch_bold(i)

	# TODO => revise this!!!
	def zynswitch_double(self,i):
		self.dtsw[i]=datetime.now()
		for j in range(4):
			if j==i: continue
			if abs((self.dtsw[i]-self.dtsw[j]).total_seconds())<0.3:
				dswstr=str(i)+'+'+str(j)
				logging.info('Double Switch '+dswstr)
				self.show_control_xy(i,j)
				return True

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
			if not self.loading:
				try:
					if self.modal_screen:
						self.screens[self.modal_screen].zyncoder_read()
					else:
						self.screens[self.active_screen].zyncoder_read()
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

	def stop_loading(self):
		self.loading=self.loading-1
		if self.loading<0: self.loading=0

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
			while True:
				ev=lib_zyncoder.read_zynmidi()
				if ev==0: break
				evtype = (ev & 0xF0)>>4
				chan = ev & 0x0F
				if evtype==0xC:
					pgm = (ev & 0xF00)>>8
					logging.info("MIDI PROGRAM CHANGE " + str(pgm) + ", CH" + str(chan))
					self.zyngine.set_instr(pgm,chan,False)
					if not self.modal_screen and chan==self.zyngine.get_midi_chan():
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
					if chan==self.zyngine.get_midi_chan() and self.active_screen=='control': 
						ctrl = event[7][4]
						val = event[7][5]
						#print ("MIDI CTRL " + str(ctrl) + ", CH" + str(chan) + " => " + str(val))
						if ctrl in self.screens['control'].zcontroller_map.keys():
							self.screens['control'].zcontroller_map[ctrl].set_value(val,True)
				elif event[0]==alsaseq.SND_SEQ_EVENT_PGMCHANGE:
					pgm = event[7][4]
					val = event[7][5]
					logging.info("MIDI PROGRAM CHANGE " + str(pgm) + ", CH" + str(chan) + " => " + str(val))
					self.zyngine.set_instr(pgm,chan,False)
					if not self.modal_screen and chan==self.zyngine.get_midi_chan():
						self.show_screen('control')
		except Exception as err:
			logging.error("zynthian_gui.amidi_read() => %s" % err)
		if self.polling:
			top.after(40, self.amidi_read)

	def zyngine_refresh(self):
		try:
			if self.exit_flag:
				sys.exit(self.exit_code)
			if self.zyngine and not self.loading:
				self.zyngine.refresh()
		except Exception as err:
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
		if path in self.screens['control'].zcontroller_map.keys():
			self.screens['control'].zcontroller_map[path].set_init_value(args[0])


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
	zyngui.zyngine.stop()
	top.destroy()

signal.signal(signal.SIGTERM, sigterm_handler)

#-------------------------------------------------------------------------------
# TKinter Main Loop
#-------------------------------------------------------------------------------

top.mainloop()

#-------------------------------------------------------------------------------
