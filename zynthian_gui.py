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

import sys
import signal
import alsaseq
import liblo
from tkinter import *
from tkinter import font as tkFont
from ctypes import *
from time import sleep
from datetime import datetime
from string import Template
from subprocess import check_output
from threading  import Thread

from zyngine import *
from zyngine.zynthian_engine import osc_port as zyngine_osc_port

from zyncoder import *
from zyncoder.zyncoder import lib_zyncoder, lib_zyncoder_init

from zyngine.zynthian_midi import *
from zyngine.zynthian_zcmidi import *

#-------------------------------------------------------------------------------
# Define some Constants and Parameters for the GUI
#-------------------------------------------------------------------------------

width=320
height=240

#Initial Screen
splash_image="./img/zynthian_logo_boot.gif"

# Original Colors
bgcolor="#002255"
bg2color="#2c5aa0"
bg3color="#5f7aa2"
bordercolor="#0064fa"
textcolor="#0064fa"
lightcolor="#f8cf2b"

# New Colors Inspired in ZynAddSubFX new GUI => https://github.com/fundamental/zyn-ui-two
color_bg="#232c36"
color_tx="#becfe4"
color_panel_bg="#3a424d"
#color_panel_bd="#3a424d"
color_panel_bd=color_bg
color_panel_tx="#becfe4"
color_header_bg="#333a42"
color_header_tx="#a9b8c4"
color_ctrl_bg_off="#434f59"
color_ctrl_bg_on="#00828c" #007272
color_ctrl_tx="#00cff7"
color_ctrl_tx2="#00cca5"
color_btn_bg="#505e6c"
color_btn_tx="#becfe4"

#bg2color=bgcolor_ctrl_off
#bg3color=bgcolor_ctrl_on
#bordercolor=bgcolor
#textcolor=color_panel_txt
#lightcolor=color_ctrl_txt

#-------------------------------------------------------------------------------
# Controller positions
#-------------------------------------------------------------------------------
ctrl_pos=[
	[-1,25],
	[-1,133],
	[243,25],
	[243,133]
]

#-------------------------------------------------------------------------------
# Get Zynthian Hardware Version
#-------------------------------------------------------------------------------
try:
	with open("../zynthian_hw_version.txt","r") as fh:
		hw_version=fh.read()
		print("HW version "+str(hw_version))
except:
	hw_version="PROTOTYPE-4"
	print("No HW version file. Default to PROTOTYPE-4.")

#-------------------------------------------------------------------------------
# GPIO pin assignment (wiringPi)
#-------------------------------------------------------------------------------

if hw_version=="PROTOTYPE-1":		# First Prototype => Generic Plastic Case
	zyncoder_pin_a=[27,21,3,7]
	zyncoder_pin_b=[25,26,4,0]
	zynswitch_pin=[23,None,2,None]
	select_ctrl=2
elif hw_version=="PROTOTYPE-2":		# No GPIO Expander (only 2 switches)
	zyncoder_pin_a=[25,26,4,0]
	zyncoder_pin_b=[27,21,3,7]
	zynswitch_pin=[23,None,2,None]
	select_ctrl=2
elif hw_version=="PROTOTYPE-3":		# Controller RBPi connector downside
	zyncoder_pin_a=[27,21,3,7]
	zyncoder_pin_b=[25,26,4,0]
	zynswitch_pin=[107,23,106,2]
	select_ctrl=3
elif hw_version=="PROTOTYPE-4":		# Controller RBPi connector downside
	zyncoder_pin_a=[26,25,0,4]
	zyncoder_pin_b=[21,27,7,3]
	zynswitch_pin=[107,23,106,2]
	select_ctrl=3
elif hw_version=="PROTOTYPE-EMU":	# Desktop Development & Emulation
	zyncoder_pin_a=[4,5,6,7]
	zyncoder_pin_b=[8,9,10,11]
	zynswitch_pin=[0,1,2,3]
	select_ctrl=3
else:								# Default to PROTOTYPE-3
	zyncoder_pin_a=[26,25,0,4]
	zyncoder_pin_b=[21,27,7,3]
	zynswitch_pin=[107,23,106,2]
	select_ctrl=2

#-------------------------------------------------------------------------------
# Controller GUI Class
#-------------------------------------------------------------------------------
class zynthian_controller:
	width=77
	height=106
	trw=70
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
	value_print=""

	shown=False
	frame=None
	rectangle=None
	triangle=None
	arc=None
	value_text=None
	label_title=None

	def __init__(self, indx, cnv, tit, chan, ctrl, val=0, max_val=127):
		self.index=indx
		self.canvas=cnv
		self.x=ctrl_pos[indx][0]
		self.y=ctrl_pos[indx][1]
		self.plot_value=self.plot_value_arc
		self.erase_value=self.erase_value_arc
		self.config(tit,chan,ctrl,val,max_val)
		self.show()

	def show(self):
		if not self.shown:
			self.shown=True
			self.plot_frame()
			self.plot_value()
			self.label_title.place(x=self.x+3, y=self.y+4, anchor=NW)

	def hide(self):
		if self.shown:
			self.shown=False
			self.erase_frame()
			self.erase_value()
			self.label_title.place_forget()

	def plot_frame(self):
		x2=self.x+self.width
		y2=self.y+self.height
		if self.frame:
			self.canvas.coords(self.frame,(self.x, self.y, x2, self.y, x2, y2, self.x, y2))
		else:
			self.frame=self.canvas.create_polygon((self.x, self.y, x2, self.y, x2, y2, self.x, y2), outline=color_panel_bd, fill=color_panel_bg)

	def erase_frame(self):
		if self.frame:
			self.canvas.delete(self.frame)
			self.frame=None

	def calculate_plot_values(self):
		if self.value>self.max_value: self.value=self.max_value
		elif self.value<0: self.value=0
		if self.values:
			try:
				if self.ticks:
					if self.inverted:
						for i in reversed(range(self.n_values)):
							if self.value<self.ticks[i]:
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
				#print("PLOT VALUE: "+str(self.value)+"/"+str(self.max_value)+", "+str(i)+"/"+str(self.n_values)+", "+str(self.value_plot))
			except Exception as err:
				print(err)
				self.value_plot=self.value
				self.value_print="ERR"
		else:
			self.value_plot=self.value
			self.value_print=self.val0+self.value

	def plot_value_rectangle(self):
		self.calculate_plot_values()
		x1=self.x+6
		y1=self.y+self.height-5
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
			self.value_text=self.canvas.create_text(x1+self.trw/2-1, y1-self.trh, width=self.trw, justify=CENTER, fill=color_ctrl_tx, font=("Helvetica",14), text=str(self.value_print))

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
		x1=self.x+2
		y1=self.y+int(0.8*self.height)+self.trh
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
			self.value_text=self.canvas.create_text(x1+self.trw/2-1, y1-self.trh-8, width=self.trw, justify=CENTER, fill=color_ctrl_tx, font=("Helvetica",14), text=str(self.value_print))

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
			x1=self.x+0.2*self.trw
			y1=self.y+self.height-int(0.7*self.trw)-6
			x2=x1+0.7*self.trw
			y2=self.y+self.height-6
		if self.arc:
			self.canvas.itemconfig(self.arc, extent=degd)
		elif self.midi_ctrl!=0:
			self.arc=self.canvas.create_arc(x1, y1, x2, y2, style=ARC, outline=color_ctrl_bg_on, width=thickness, start=deg0, extent=degd)
		if self.value_text:
			self.canvas.itemconfig(self.value_text, text=str(self.value_print))
		else:
			self.value_text=self.canvas.create_text(x1+(x2-x1)/2-1, y1-(y1-y2)/2, width=x2-x1, justify=CENTER, fill=color_ctrl_tx, font=("Helvetica",14), text=str(self.value_print))

	def erase_value_arc(self):
		if self.arc:
			self.canvas.delete(self.arc)
			self.arc=None
		if self.value_text:
			self.canvas.delete(self.value_text)
			self.value_text=None

	def set_title(self, tit):
		self.title=str(tit)
		#maxlen=max([len(w) for w in self.title.split()])
		rfont=tkFont.Font(family="Helvetica",size=10)
		maxlen=max([rfont.measure(w) for w in self.title.split()])
		if maxlen<40:
			maxlen=rfont.measure(self.title)
		#font_size=12-int((maxlen-58)/6)
		if maxlen>86:
			font_size=7
		elif maxlen>79:
			font_size=8
		elif maxlen>72:
			font_size=9
		elif maxlen>65:
			font_size=10
		#elif maxlen>58:
		#	font_size=11
		else:
			font_size=11
		#self.title=self.title+" > "+str(font_size)
		if not self.label_title:
			self.label_title = Label(self.canvas,
				text=self.title,
				font=("Helvetica",font_size),
				wraplength=self.width-6,
				justify=LEFT,
				bg=color_panel_bg,
				fg=color_panel_tx)
		else:
			self.label_title.config(text=self.title,font=("Helvetica",font_size))

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
		if isinstance(ctrl, Template):
			self.midi_ctrl=None
			self.osc_path=ctrl.substitute(part=chan)
		else:
			self.midi_ctrl=ctrl
			self.osc_path=None
		if isinstance(max_val,str):
			self.values=max_val.split('|')
		elif isinstance(max_val,list):
			if isinstance(max_val[0],list):
				self.values=max_val[0]
				self.ticks=max_val[1]
				if self.ticks[0]>self.ticks[1]:
					self.inverted=True
			else:
				self.values=max_val
		elif max_val>0:
			self.values=None
			self.max_value=self.n_values=max_val
		if self.values:
			self.n_values=len(self.values)
			self.step=max(1,int(16/self.n_values));
			self.max_value=128-self.step;
			val=int(self.values.index(val)*self.max_value/(self.n_values-1))
		if self.midi_ctrl==0:
			self.mult=4
			self.val0=1
		if val>self.max_value:
			val=self.max_value
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

		self.set_value(val)
		self.setup_zyncoder()
		
	def setup_zyncoder(self):
		self.init_value=None
		try:
			if self.osc_path:
				print("SETUP RENCODER "+str(self.index)+": "+self.osc_path)
				osc_path_char=c_char_p(self.osc_path.encode('UTF-8'))
				if zyngui.osc_target:
					liblo.send(zyngui.osc_target, self.osc_path)
			else:
				print("SETUP RENCODER "+str(self.index)+": "+str(self.midi_ctrl))
				osc_path_char=None

			if self.inverted:
				pin_a=zyncoder_pin_b[self.index]
				pin_b=zyncoder_pin_a[self.index]
			else:
				pin_a=zyncoder_pin_a[self.index]
				pin_b=zyncoder_pin_b[self.index]
			lib_zyncoder.setup_zyncoder(self.index,pin_a,pin_b,self.chan,self.midi_ctrl,osc_path_char,self.mult*self.value,self.mult*(self.max_value-self.val0),self.step)
		except Exception as err:
			print(err)
			pass

	def set_value(self, v, set_zyncoder=False):
		if (v>self.max_value):
			v=self.max_value
		if (v!=self.value):
			self.value=v
			if self.shown:
				if set_zyncoder:
					lib_zyncoder.set_value_zyncoder(self.index,v)
				self.plot_value()

	def set_init_value(self, v):
		if self.init_value is None:
			self.init_value=v
			self.set_value(v,True)
			print("RENCODER INIT VALUE "+str(self.index)+": "+str(v))

	def read_zyncoder(self):
		val=lib_zyncoder.get_value_zyncoder(self.index)
		val=int(val/self.mult)
		self.set_value(val)
		#print ("RENCODER VALUE: " + str(self.index) + " => " + str(val))

#-------------------------------------------------------------------------------
# Zynthian Splash GUI Class
#-------------------------------------------------------------------------------
class zynthian_splash:
	def __init__(self, tms=1000):
		# Add Background Image inside a Canvas
		self.canvas = Canvas(
			width = width,
			height = height,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg = color_bg)
		self.splash_img = PhotoImage(file = "./img/zynthian_gui_splash.gif")
		self.canvas.create_image(0, 0, image = self.splash_img, anchor = NW)
		self.show(tms)

	def hide(self):
		self.canvas.pack_forget()

	def show(self, tms=2000):
		self.canvas.pack(expand = YES, fill = BOTH)
		top.after(tms, self.hide)

#-------------------------------------------------------------------------------
# Zynthian Info GUI Class
#-------------------------------------------------------------------------------
class zynthian_info:
	shown=False

	def __init__(self):
		self.canvas = Canvas(
			width = 70*width/100,
			height = 70*height/100,
			bd=1,
			highlightthickness=0,
			relief='flat',
			bg = color_bg)

		self.text = StringVar()
		self.label_text = Label(self.canvas,
			font=("Helvetica",10,"normal"),
			textvariable=self.text,
			#wraplength=80,
			justify=LEFT,
			bg=color_bg,
			fg=color_tx)
		self.label_text.place(x=1, y=0, anchor=NW)

	def clean(self):
		self.text.set("")

	def set(self, text):
		self.text.set(text)

	def add(self, text):
		self.text.set(self.text.get()+text)

	def hide(self):
		if self.shown:
			self.shown=False
			self.canvas.pack_forget()

	def show(self, text):
		self.text.set(text)
		if not self.shown:
			self.shown=True
			self.canvas.pack(expand = YES, fill = BOTH)

#-------------------------------------------------------------------------------
# Zynthian Listbox GUI Class
#-------------------------------------------------------------------------------
class zynthian_gui_list:
	width=160
	height=224
	lb_width=18
	lb_height=10
	lb_x=width/2+1
	wide=False
	shown=False
	index=0
	list_data=[]

	def __init__(self, image_bg=None, wide=False):
		list_data=[]

		if wide:
			self.wide=True
			self.width=236
			self.lb_width=28
			if select_ctrl>1:
				self.lb_x=0
			else:
				self.lb_x=317-self.width

		# Create Canvas
		self.canvas = Canvas(
			width = width,
			height = height,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg = color_bg)

		# Add Background Image inside a Canvas
		if (image_bg):
			self.canvas.create_image(0, 0, image = image_bg, anchor = NW)

		#self.plot_frame()

		# Add ListBox
		self.listbox = Listbox(self.canvas,
			width=self.lb_width,
			height=self.lb_height,
			font=("Helvetica",11),
			bd=7,
			highlightthickness=0,
			relief='flat',
			bg=color_panel_bg,
			fg=color_panel_tx,
			selectbackground=color_ctrl_bg_on,
			selectforeground=color_ctrl_tx,
			selectmode=BROWSE)
		self.listbox.place(x=self.lb_x, y=height, anchor=SW)
		self.listbox.bind('<<ListboxSelect>>', lambda event :self.click_listbox())

		# Add Select Path (top-left)
		self.select_path = StringVar()
		self.label_select_path = Label(self.canvas,
			font=("Helvetica",12,"bold"),
			textvariable=self.select_path,
			#wraplength=80,
			justify=LEFT,
			bg=color_bg,
			fg=color_tx)
		self.label_select_path.place(x=1, y=0, anchor=NW)
		
		self.show()

	def hide(self):
		if self.shown:
			self.shown=False
			self.canvas.pack_forget()

	def show(self):
		if not self.shown:
			self.shown=True
			self.canvas.pack(expand = YES, fill = BOTH)
			self.select_listbox(self.index)
			self.set_select_path()

	def is_shown(self):
		try:
			self.canvas.pack_info()
			return True
		except:
			return False

	def plot_frame(self):
		if self.wide:
			if select_ctrl>1:
				rx=0
				rx2=self.width
			else:
				rx=320-self.width
				rx2=320
		else:
			rx=(width-self.width)/2
			rx2=width-rx-1
		ry=height-self.height
		ry2=height-1
		self.canvas.create_polygon((rx, ry, rx2, ry, rx2, ry2, rx, ry2), outline=color_panel_bd, fill=color_panel_bg)

	def get_list_data(self):
		self.list_data=[]

	def fill_list(self):
		self.get_list_data()
		self._fill_list()

	def _fill_list(self):
		self.listbox.delete(0, END)
		if not self.list_data:
			self.list_data=[]
		for item in self.list_data:
			self.listbox.insert(END, item[2])
		self.select(0)

	def get_cursel(self):
		cursel=self.listbox.curselection()
		if (len(cursel)>0):
			self.index=int(cursel[0])
		else:
			self.index=0
		return self.index

	def select_listbox(self,index):
		self.listbox.selection_clear(0,END)
		self.listbox.selection_set(index)
		self.listbox.see(index)

	def click_listbox(self):
		index=self.get_cursel()
		self.select_action(index)

	def switch_select(self):
		self.click_listbox()

	def select(self, index):
		self.index=index
		self.select_listbox(index)

	def set_select_path(self):
		pass

#-------------------------------------------------------------------------------
# Zynthian Admin GUI Class
#-------------------------------------------------------------------------------
class zynthian_admin(zynthian_gui_list):
	zselector=None
	commands=None
	thread=None

	def __init__(self):
		super().__init__(gui_bg_logo,True)
		self.label_title = Label(self.canvas,
			text="Admin",
			font=("Helvetica",13,"bold"),
			justify=LEFT,
			bg=color_bg,
			fg=color_tx)
		#self.label_title.place(x=84,y=-2,anchor=NW)
		self.label_title.place(x=4,y=-2,anchor=NW)
		self.fill_list()
		self.zselector=zynthian_controller(select_ctrl,self.canvas,"Action",0,0,0,len(self.list_data))
    
	def get_list_data(self):
		self.list_data=(
			(self.update_software,0,"Update Zynthian Software"),
			(self.update_library,0,"Update Zynthian Library"),
			(self.update_system,0,"Update Operating System"),
			(self.connect_to_pc,0,"Connect to PC"),
			(self.exit_to_console,0,"Exit to Console"),
			(self.reboot,0,"Reboot"),
			(self.power_off,0,"Power Off")
		)

	def show(self):
		super().show()
		if self.zselector:
			self.zselector.config("Action",0,0,self.get_cursel(),len(self.list_data))
			#self.zselector.config("Action",0,0,len(self.list_data))

	def select_action(self, i):
		self.list_data[i][0]()

	def zyncoder_read(self):
		_sel=self.zselector.value
		self.zselector.read_zyncoder()
		sel=self.zselector.value
		if (_sel!=sel):
			#print('Pre-select Admin Action ' + str(sel))
			self.select_listbox(sel)
			
	def execute_commands(self):
		for cmd in self.commands:
			print("Executing Command: "+cmd)
			zyngui.add_info("\nExecuting: "+cmd)
			try:
				result=check_output(cmd, shell=True).decode('utf-8','ignore')
			except Exception as e:
				result="ERROR: "+str(e)
			print(result)
			zyngui.add_info("\n"+str(result))
		zyngui.hide_info_timer(3000)
		self.commands=None

	def start_command(self,cmds):
		if not self.commands:
			print("Starting Command Sequence ...")
			self.commands=cmds
			self.thread=Thread(target=self.execute_commands, args=())
			self.thread.daemon = True # thread dies with the program
			self.thread.start()

	def update_software(self):
		print("UPDATE SOFTWARE")
		zyngui.show_info("UPDATE SOFTWARE")
		self.start_command(["su pi -c ./sys-scripts/update_zynthian.sh"])

	def update_library(self):
		print("UPDATE LIBRARY")
		zyngui.show_info("UPDATE LIBRARY")
		self.start_command(["su pi -c ./sys-scripts/update_zynthian_data.sh"])

	def update_system(self):
		print("UPDATE SYSTEM")
		zyngui.show_info("UPDATE SYSTEM")
		self.start_command(["./sys-scripts/update_system.sh"])

	def connect_to_pc(self):
		print("CONNECT TO PC")
		zyngui.show_info("OPEN REVERSE SSH")
		self.start_command(["ifconfig"])

	def exit_to_console(self):
		print("EXIT TO CONSOLE")
		sys.exit(101)

	def reboot(self):
		print("REBOOT")
		sys.exit(100)

	def power_off(self):
		print("POWER OFF")
		sys.exit(0)

#-------------------------------------------------------------------------------
# Zynthian Engine Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_engine(zynthian_gui_list):
	zselector=None
	zyngine=None

	def __init__(self):
		super().__init__(gui_bg_logo,True)
		self.label_title = Label(self.canvas,
			text="Engine",
			font=("Helvetica",13,"bold"),
			justify=LEFT,
			bg=color_bg,
			fg=color_tx)
		#self.label_title.place(x=84,y=-2,anchor=NW)
		self.label_title.place(x=4,y=-2,anchor=NW)
		self.fill_list()
		self.zselector=zynthian_controller(select_ctrl,self.canvas,"Engine",0,0,1,len(self.list_data))
		#self.set_select_path()
    
	def get_list_data(self):
		self.list_data=(
			("ZynAddSubFX",0,"ZynAddSubFX - Synthesizer"),
			("LinuxSampler",1,"LinuxSampler - Sampler"),
			("setBfree",2,"setBfree - Hammond Emulator"),
			("Carla",3,"Carla - Plugin Host"),
			("FluidSynth",4,"FluidSynth - Sampler")
		)

	def show(self):
		super().show()
		if self.zselector:
			self.zselector.config("Engine",0,0,self.get_cursel(),len(self.list_data))
			#self.zselector.config("Engine",0,0,len(self.list_data))

	def select_action(self, i):
		zyngui.set_engine(self.list_data[i][0])
		zyngui.show_screen('chan')
		
	def set_engine(self,name):
		if self.zyngine:
			if self.zyngine.name==name:
				return False
			else:
				self.zyngine.stop()
		if name=="ZynAddSubFX":
			self.zyngine=zynthian_engine_zynaddsubfx(zyngui)
		elif name=="setBfree":
			self.zyngine=zynthian_engine_setbfree(zyngui)
		elif name=="LinuxSampler":
			self.zyngine=zynthian_engine_linuxsampler(zyngui)
		elif name=="Carla":
			self.zyngine=zynthian_engine_carla(zyngui)
		elif name=="FluidSynth":
			self.zyngine=zynthian_engine_fluidsynth(zyngui)
		else:
			return False
		return True

	def zyncoder_read(self):
		_sel=self.zselector.value
		self.zselector.read_zyncoder()
		sel=self.zselector.value
		if (_sel!=sel):
			#print('Pre-select Engine ' + str(sel))
			self.select_listbox(sel)

	def set_select_path(self):
		pass
		#self.select_path.set("Zynthian")

#-------------------------------------------------------------------------------
# Zynthian MIDI Channel Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_chan(zynthian_gui_list):
	zselector=None
	max_chan=10

	def __init__(self, max_chan=10):
		super().__init__(gui_bg, True)
		self.max_chan=max_chan
		self.fill_list()
		self.index=zyngui.zyngine.get_midi_chan()
		self.zselector=zynthian_controller(select_ctrl,self.canvas,"Channel",0,0,self.index+1,len(self.list_data))
		self.set_select_path()
    
	def get_list_data(self):
		self.list_data=[]
		for i in range(self.max_chan):
			self.list_data.append((str(i+1),i,str(i+1)+">"+zyngui.zyngine.get_path(i)))
			#instr=zynmidi.get_midi_instr(i)
			#self.list_data.append((str(i+1),i,"Chan #"+str(i+1)+" -> Bank("+str(instr[0])+","+str(instr[1])+") Prog("+str(instr[2])+")"))

	def show(self):
		self.fill_list()
		self.index=zyngui.zyngine.get_midi_chan()
		super().show()
		if self.zselector:
			self.zselector.config("Channel",0,0,self.index,len(self.list_data))
		self.select_listbox(self.index)

	def select_action(self, i):
		zyngui.zyngine.set_midi_chan(i)
		zyngui.screens['bank'].fill_list()
		zyngui.screens['instr'].fill_list()
		# If there is only one bank, jump to instrument selection
		if len(zyngui.screens['bank'].list_data)==1:
			zyngui.screens['bank'].select_action(0)
		else:
			zyngui.show_screen('bank')

	def next(self):
		if zyngui.zyngine.next_chan():
			zyngui.screens['bank'].fill_list()
			zyngui.screens['instr'].fill_list()
			self.index=zyngui.zyngine.get_midi_chan()
			self.select_listbox(self.index)
			return True
		return False

	def zyncoder_read(self):
		_sel=self.zselector.value
		self.zselector.read_zyncoder()
		sel=self.zselector.value
		if (_sel!=sel):
			#print('Pre-select MIDI Chan ' + str(sel))
			self.select_listbox(sel)

	def set_select_path(self):
		self.select_path.set(zyngui.zyngine.name)

#-------------------------------------------------------------------------------
# Zynthian Bank Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_bank(zynthian_gui_list):
	zselector=None

	def __init__(self):
		super().__init__(gui_bg, True)
		self.fill_list()
		self.index=zyngui.zyngine.get_bank_index()
		self.zselector=zynthian_controller(select_ctrl,self.canvas,"Bank",0,0,self.index+1,len(self.list_data))
		self.set_select_path()
    
	def get_list_data(self):
		self.list_data=zyngui.zyngine.bank_list

	def show(self):
		self.index=zyngui.zyngine.get_bank_index()
		super().show()
		if self.zselector:
			self.zselector.config("Bank",0,0,self.index,len(self.list_data))

	def select_action(self, i):
		zyngui.zyngine.set_bank(i)
		zyngui.screens['instr'].fill_list()
		zyngui.show_screen('instr')

	def zyncoder_read(self):
		_sel=self.zselector.value
		self.zselector.read_zyncoder()
		sel=self.zselector.value
		if (_sel!=sel):
			#print('Pre-select Bank ' + str(sel))
			self.select_listbox(sel)

	def set_select_path(self):
		self.select_path.set(zyngui.zyngine.nickname + "#" + str(zyngui.zyngine.get_midi_chan()+1))

#-------------------------------------------------------------------------------
# Zynthian Instrument Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_instr(zynthian_gui_list):
	zselector=None

	def __init__(self):
		super().__init__(gui_bg, True)
		self.fill_list()
		self.index=zyngui.zyngine.get_instr_index()
		self.zselector=zynthian_controller(select_ctrl,self.canvas,"Intrument",0,0,self.index+1,len(self.list_data))
		self.set_select_path()
      
	def get_list_data(self):
		self.list_data=zyngui.zyngine.instr_list

	def show(self):
		self.index=zyngui.zyngine.get_instr_index()
		super().show()
		if self.zselector:
			self.zselector.config("Instrument",0,0,self.index,len(self.list_data))

	def select_action(self, i):
		zyngui.zyngine.set_instr(i)
		#Send OSC message to get feedback on instrument loaded
		if isinstance(zyngui.zyngine,zynthian_engine_zynaddsubfx):
			try:
				liblo.send(zyngui.zyngine.osc_target, "/volume")
				zyngui.zyngine.osc_server.recv()
			except:
				zyngui.show_screen('control')
			zyngui.screens['control'].fill_list()
		else:
			zyngui.screens['control'].fill_list()
			zyngui.screens['control'].set_mode_control()
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
# Zynthian Instrument Controller GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_control(zynthian_gui_list):
	mode=None

	def __init__(self):
		super().__init__(gui_bg)
		# Controllers
		midi_chan=zyngui.get_midi_chan()
		self.zcontrollers_config=zyngui.zyngine.default_ctrl_config
		self.zcontrollers=(
			#indx, cnv, x, y, tit, chan, ctrl, val=0, max_val=127
			zynthian_controller(0,self.canvas,self.zcontrollers_config[0][0],midi_chan,self.zcontrollers_config[0][1],self.zcontrollers_config[0][2],self.zcontrollers_config[0][3]),
			zynthian_controller(1,self.canvas,self.zcontrollers_config[1][0],midi_chan,self.zcontrollers_config[1][1],self.zcontrollers_config[1][2],self.zcontrollers_config[1][3]),
			zynthian_controller(2,self.canvas,self.zcontrollers_config[2][0],midi_chan,self.zcontrollers_config[2][1],self.zcontrollers_config[2][2],self.zcontrollers_config[2][3]),
			zynthian_controller(3,self.canvas,self.zcontrollers_config[3][0],midi_chan,self.zcontrollers_config[3][1],self.zcontrollers_config[3][2],self.zcontrollers_config[3][3])
		)
		# Init Controllers Map
		self.zcontroller_map={}
		for zc in self.zcontrollers:
			self.zcontroller_map[zc.ctrl]=zc

	def show(self):
		self.zcontrollers_config=zyngui.zyngine.get_instr_ctrl_config()
		super().show()

	def hide(self):
		if self.shown:
			super().hide()
			for zc in self.zcontrollers:
				zc.hide()

	def set_controller_config(self, cfg):
		midi_chan=zyngui.get_midi_chan()
		for i in range(0,4):
			try:
				#indx, tit, chan, ctrl, val, max_val=127
				self.set_controller(i,cfg[i][0],midi_chan,cfg[i][1],cfg[i][2],cfg[i][3])
			except:
				pass

	def set_controller(self, i, tit, chan, ctrl, val, max_val=127):
		try:
			del self.zcontroller_map[self.zcontrollers[i].ctrl]
		except:
			pass
		#tit, chan, ctrl, val, max_val=127
		self.zcontrollers[i].config(tit,chan,ctrl,val,max_val)
		self.zcontrollers[i].show()
		self.zcontroller_map[self.zcontrollers[i].ctrl]=self.zcontrollers[i]

	def get_list_data(self):
		self.list_data=zyngui.zyngine.map_list

	def _fill_list(self):
		super()._fill_list()
		if self.mode=='select':
			self.set_controller(select_ctrl,"Controllers",0,0,self.index,len(self.list_data))

	def set_mode_select(self):
		self.mode='select'
		for i in range(0,4):
			self.zcontrollers[i].hide()
		#self.index=1
		self.set_controller(select_ctrl,"Controllers",0,0,self.index,len(self.list_data))
		self.listbox.config(selectbackground=color_ctrl_bg_on)
		self.select(self.index)
		self.set_select_path()

	def set_mode_control(self):
		self.mode='control'
		self.zcontrollers[select_ctrl].hide()
		self.set_controller_config(self.zcontrollers_config)
		self.listbox.config(selectbackground=color_ctrl_bg_off)
		self.set_select_path()

	def select_action(self, i):
		self.zcontrollers_config=self.list_data[i][0]
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
		if self.mode=='control':
			for zc in self.zcontrollers:
				#print('Read Control ' + str(zc.title))
				zc.read_zyncoder()
		elif self.mode=='select':
			_sel=self.zcontrollers[select_ctrl].value
			self.zcontrollers[select_ctrl].read_zyncoder()
			sel=self.zcontrollers[select_ctrl].value
			if (_sel!=sel):
				#print('Pre-select Parameter ' + str(sel))
				self.select_listbox(sel)

	def set_select_path(self):
		self.select_path.set(zyngui.zyngine.get_fullpath())


#-------------------------------------------------------------------------------
# Zynthian OSC Browser GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_osc_browser(zynthian_gui_list):
	mode=None
	osc_path=None

	def __init__(self):
		super().__init__(gui_bg, True)
		self.fill_list()
		self.index=1
		self.zselector=zynthian_controller(select_ctrl,self.canvas,"Path",0,0,self.index+1,len(self.list_data))
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
			self.osc_path="/part"+str(zyngui.get_midi_chan())+"/"
		else:
			self.osc_path=self.osc_path+path
		liblo.send(zyngui.osc_target, "/path-search",self.osc_path,"")
		print("OSC /path-search "+self.osc_path)

	def select_action(self, i):
		path=self.list_data[i][0]
		tnode=self.list_data[i][1]
		title=self.list_data[i][2]
		print("SELECT PARAMETER: %s (%s)" % (title,tnode))
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
	midi_chan=0

	amidi=None
	zynmidi=None
	zyngine=None
	screens={}
	active_screen=None
	screens_sequence=("admin","engine","chan","bank","instr","control")

	dtsw={}
	polling=False
	osc_target=None
	osc_server=None

	def __init__(self):
		# Controls Initialization (Rotary and Switches)
		try:
			global lib_zyncoder
			lib_zyncoder_init(zyngine_osc_port)
			lib_zyncoder=zyncoder.get_lib_zyncoder()
			#self.amidi=zynthian_midi("Zynthian_gui")
			self.zynmidi=zynthian_zcmidi()
			self.zynswitches_init()
		except Exception as e:
			print("ERROR initializing GUI: %s" % str(e))
		# GUI Objects Initialization
		#self.screens['splash']=zynthian_splash(1000)
		self.screens['admin']=zynthian_admin()
		self.screens['info']=zynthian_info()
		self.screens['engine']=zynthian_gui_engine()
		# Show first screen and start polling
		self.show_screen('engine')
		self.start_polling()

	def get_midi_chan(self):
		if self.zyngine:
			return self.zyngine.get_midi_chan()
		else:
			return None;

	def hide_screens(self,exclude=None):
		if not exclude:
			exclude=self.active_screen
		for screen_name,screen in self.screens.items():
			if screen_name!=exclude:
				screen.hide();

	def show_active_screen(self):
		self.screens[self.active_screen].show()
		self.hide_screens()

	def show_screen(self,screen=None):
		if screen:
			self.active_screen=screen
		self.show_active_screen()

	def show_info(self, text, tms=None):
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
       
	def set_engine(self,name):
		if self.screens['engine'].set_engine(name):
			self.zyngine=self.screens['engine'].zyngine
			self.screens['chan']=zynthian_gui_chan(self.zyngine.max_chan)
			self.screens['bank']=zynthian_gui_bank()
			self.screens['instr']=zynthian_gui_instr()
			self.screens['control']=zynthian_gui_control()

	# Init GPIO Switches
	def zynswitches_init(self):
		ts=datetime.now()
		print("SWITCHES INIT!")
		for i,pin in enumerate(zynswitch_pin):
			self.dtsw[i]=ts
			lib_zyncoder.setup_zynswitch(i,pin)
			print("SETUP GPIO SWITCH "+str(i)+" => "+str(pin))

	def zynswitches(self):
		for i in range(len(zynswitch_pin)):
			dtus=lib_zyncoder.get_zynswitch_dtus(i)
			if dtus>0:
				#print("Switch "+str(i)+" dtus="+str(dtus))
				if dtus>300000:
					if dtus>2000000:
						print('Looooooooong Switch '+str(i))
						self.zynswitch_long(i)
						return
					if self.zynswitch_double(i):
						return
					print('Bold Switch '+str(i))
					self.zynswitch_bold(i)
					return
				print('Short Switch '+str(i))
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
			pass
		elif i==3:
			if self.active_screen=='chan':
				self.screens['chan'].switch_select()
				print("PATH="+self.zyngine.get_fullpath())
				if self.zyngine.get_instr_index():
					self.screens['control'].set_mode_control()
					self.show_screen('control')
			else:
				self.screens[self.active_screen].switch_select()

	def zynswitch_short(self,i):
		if i==0:
			if self.active_screen=='control':
				if self.screens['chan'].next():
					print("Next Chan")
					self.screens['control'].hide()
					self.screens['control'].fill_list()
					self.screens['control'].set_mode_control()
					self.show_screen('control')
				else:
					self.zynswitch_bold(i)
			else:
				self.zynswitch_bold(i)
		elif i==1:
			if self.active_screen=='control' and self.screens['control'].mode=='select':
				self.screens['control'].set_mode_control()
			else:
				j=self.screens_sequence.index(self.active_screen)-1
				if j<0:
					j=1
				screen_back=self.screens_sequence[j]
				# If there is only one bank, jump to channel selection
				if screen_back=='bank' and len(self.screens['bank'].list_data)==1:
					screen_back='chan'
				#print("BACK TO SCREEN "+str(j)+" => "+screen_back)
				self.show_screen(screen_back)
		elif i==2:
			pass
		elif i==3:
			if self.active_screen=='control' and self.screens['control'].mode=='control':
				self.screens['control'].next()
				print("Next Control Screen")
			else:
				self.zynswitch_bold(i)

	def zynswitch_double(self,i):
		self.dtsw[i]=datetime.now()
		for j in range(4):
			if j==i:
				continue
			if abs((self.dtsw[i]-self.dtsw[j]).total_seconds())<0.3:
				dswstr=str(i)+'+'+str(j)
				print('Double Switch '+dswstr)
				if dswstr=='1+3' or dswstr=='3+1':
					self.show_screen('admin')
				return True

	def start_polling(self):
		self.polling=True
		self.poll_count=0
		if lib_zyncoder:
			self.zyncoder_read()
		if self.amidi:
			self.midi_read()
		self.osc_read()

	def stop_polling(self):
		self.polling=False

	def midi_read(self):
		while alsaseq.inputpending():
			event = alsaseq.input()
			chan = event[7][0]
			if event[0]==alsaseq.SND_SEQ_EVENT_CONTROLLER and chan==self.get_midi_chan() and self.active_screen=='control': 
				ctrl = event[7][4]
				val = event[7][5]
				#print ("MIDI CTRL " + str(ctrl) + ", CH" + str(chan) + " => " + str(val))
				if ctrl in self.screens['control'].zcontroller_map.keys():
					self.screens['control'].zcontroller_map[ctrl].set_value(val,True)
		if self.polling:
			top.after(40, self.midi_read)

	def zyncoder_read(self):
		self.screens[self.active_screen].zyncoder_read()
		self.zynswitches()
		if self.polling:
			top.after(40, self.zyncoder_read)

	def osc_read(self):
		if self.zyngine and self.zyngine.osc_server:
			while self.zyngine.osc_server.recv(0):
				pass
		if self.polling:
			top.after(40, self.osc_read)

	def cb_osc_load_instr(self, path, args):
		#self.screens['osc_browser'].get_osc_paths('root')
		self.screens['control'].set_mode_control()
		self.show_screen('control')

	def cb_osc_paths(self, path, args, types, src):
		if isinstance(zyngui.zyngine,zynthian_engine_zynaddsubfx):
			zyngui.zyngine.cb_osc_paths(path, args, types, src)
			self.screens['control'].list_data=zyngui.zyngine.osc_paths_data
			self.screens['control']._fill_list()

	def cb_osc_bank_view(self, path, args):
		pass

	def cb_osc_ctrl(self, path, args):
		#print ("OSC CTRL: " + path + " => "+str(args[0]))
		if path in self.screens['control'].zcontroller_map.keys():
			self.screens['control'].zcontroller_map[path].set_init_value(args[0])

#-------------------------------------------------------------------------------
# Create Top Level Window with Fixed Size
#-------------------------------------------------------------------------------

top = Tk()
top.geometry(str(width)+'x'+str(height))
top.maxsize(width,height)
top.minsize(width,height)
if hw_version!="PROTOTYPE-EMU":
	top.config(cursor="none")

#-------------------------------------------------------------------------------
# GUI & Synth Engine initialization
#-------------------------------------------------------------------------------

# Image Loading
#gui_bg_logo = PhotoImage(file = "./img/zynthian_bg_logo_left.gif")
gui_bg_logo = None
gui_bg = None

zyngui=zynthian_gui()

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
	print("Catch SIGTERM ...")
	zyngui.zyngine.stop()
	top.destroy()

signal.signal(signal.SIGTERM, sigterm_handler)

#-------------------------------------------------------------------------------
# TKinter Main Loop
#-------------------------------------------------------------------------------

top.mainloop()

#-------------------------------------------------------------------------------
