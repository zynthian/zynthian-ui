#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Controller Class
# 
# Copyright (C) 2015-2016 Fernando Moyano <jofemodo@zynthian.org>
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

import sys
import logging
import liblo
import tkinter
import ctypes
from time import sleep
from string import Template
from datetime import datetime
from tkinter import font as tkFont

# Zynthian specific modules
from zyncoder import *
from zyngine import zynthian_controller
from . import zynthian_gui_config

#------------------------------------------------------------------------------
# Controller GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_controller:

	def __init__(self, indx, frm, zctrl):
		self.width=zynthian_gui_config.ctrl_width
		self.height=zynthian_gui_config.ctrl_height
		self.trw=zynthian_gui_config.ctrl_width-6
		self.trh=int(0.1*zynthian_gui_config.ctrl_height)

		self.zyngui=zynthian_gui_config.zyngui
		self.zctrl=None
		self.n_values=127
		self.max_value=127
		self.inverted=False
		self.step=1
		self.mult=1
		self.val0=0
		self.value=0
		self.scale_plot=1
		self.scale_value=1
		self.value_plot=0
		self.value_print=None
		self.value_font_size=14

		self.shown=False
		self.rectangle=None
		self.triangle=None
		self.arc=None
		self.value_text=None
		self.label_title=None
		self.midi_bind=None

		self.index=indx
		self.main_frame=frm
		self.row=zynthian_gui_config.ctrl_pos[indx][0]
		self.col=zynthian_gui_config.ctrl_pos[indx][1]
		self.sticky=zynthian_gui_config.ctrl_pos[indx][2]
		self.plot_value=self.plot_value_arc
		self.erase_value=self.erase_value_arc
		# Create Canvas
		self.canvas=tkinter.Canvas(self.main_frame,
			width=self.width,
			height=self.height-1,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg = zynthian_gui_config.color_panel_bg)
		# Bind canvas events
		self.canvas.bind("<Button-1>",self.cb_canvas_push)
		self.canvas.bind("<ButtonRelease-1>",self.cb_canvas_release)
		self.canvas.bind("<B1-Motion>",self.cb_canvas_motion)
		self.canvas.bind("<Button-4>",self.cb_canvas_wheel)
		self.canvas.bind("<Button-5>",self.cb_canvas_wheel)
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


	def set_hl(self):
		try:
			self.canvas.itemconfig(self.arc, outline=zynthian_gui_config.color_hl)
		except:
			pass


	def unset_hl(self):
		try:
			self.canvas.itemconfig(self.arc, outline=zynthian_gui_config.color_ctrl_bg_on)
		except:
			pass


	def calculate_plot_values(self):

		if self.value>self.max_value:
			self.value=self.max_value

		elif self.value<0:
			self.value=0

		if self.zctrl.labels:
			valplot=None

			#DIRTY HACK => It should be improved!! 
			if self.zctrl.value_min<0:
				val=self.zctrl.value_min+self.value
			else:
				val=self.value

			try:
				if self.zctrl.ticks:
					if self.inverted:
						for i in reversed(range(self.n_values)):
							if val<=self.zctrl.ticks[i]:
								break
						valplot=self.scale_plot*(self.max_value-self.zctrl.ticks[i])
						val=self.zctrl.ticks[i]
					else:
						for i in range(self.n_values-1):
							if val<self.zctrl.ticks[i+1]:
								valplot=self.scale_plot*(self.zctrl.ticks[i]-self.zctrl.ticks[0])
								break
						if valplot==None:
							i+=1
							valplot=self.scale_plot*(self.zctrl.ticks[i]-self.zctrl.ticks[0])
						val=self.zctrl.ticks[i]
				else:
					i=int(self.n_values*val/(self.max_value+self.step))
					#logging.debug("i => %s=int(%s*%s/(%s+%s))" % (i,self.n_values,val,self.max_value,self.step))
					valplot=self.scale_plot*i

				self.value_plot=valplot
				self.value_print=self.zctrl.labels[i]
				#self.zctrl.set_value(self.value)
				self.zctrl.set_value(val)

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
				val=self.zctrl.value_min+self.value*self.scale_value
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
			self.rectangle_bg=self.canvas.create_rectangle((x1, y1, x1+lx, y2), fill=zynthian_gui_config.color_ctrl_bg_off, width=0)
			self.rectangle=self.canvas.create_rectangle((x1, y1, x2, y2), fill=zynthian_gui_config.color_ctrl_bg_on, width=0)
		if self.value_text:
			self.canvas.itemconfig(self.value_text, text=value_print)
		else:
			self.value_text=self.canvas.create_text(x1+self.trw/2-1, y1-self.trh, width=self.trw,
				justify=CENTER,
				fill=zynthian_gui_config.color_ctrl_tx,
				font=(zynthian_gui_config.font_family,self.value_font_size),
				text=self.value_print)


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
			self.triangle_bg=self.canvas.create_polygon((x1, y1, x1+self.trw, y1, x1+self.trw, y1-self.trh), fill=zynthian_gui_config.color_ctrl_bg_off)
			self.triangle=self.canvas.create_polygon((x1, y1, x2, y1, x2, y2), fill=zynthian_gui_config.color_ctrl_bg_on)
		if self.value_text:
			self.canvas.itemconfig(self.value_text, text=self.value_print)
		else:
			self.value_text=self.canvas.create_text(x1+self.trw/2-1, y1-self.trh-8, width=self.trw,
				justify=CENTER,
				fill=zynthian_gui_config.color_ctrl_tx,
				font=(zynthian_gui_config.font_family,self.value_font_size),
				text=self.value_print)


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
		thickness=1.1*zynthian_gui_config.font_size
		degmax=300
		deg0=90+degmax/2
		if self.max_value!=0:
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
			self.arc=self.canvas.create_arc(x1, y1, x2, y2, 
				style=tkinter.ARC,
				outline=zynthian_gui_config.color_ctrl_bg_on,
				width=thickness,
				start=deg0,
				extent=degd)
		if self.value_text:
			self.canvas.itemconfig(self.value_text, text=self.value_print)
		else:
			self.value_text=self.canvas.create_text(x1+(x2-x1)/2-1, y1-(y1-y2)/2, width=x2-x1,
				justify=tkinter.CENTER,
				fill=zynthian_gui_config.color_ctrl_tx,
				font=(zynthian_gui_config.font_family,self.value_font_size),
				text=self.value_print)


	def erase_value_arc(self):
		if self.arc:
			self.canvas.delete(self.arc)
			self.arc=None
		x2=self.width
		y2=self.height


	def plot_midi_bind(self, midi_cc, color=zynthian_gui_config.color_ctrl_tx):
		if not self.midi_bind:
			self.midi_bind = self.canvas.create_text(
				self.width/2,
				self.height-8,
				width=int(3*0.9*zynthian_gui_config.font_size),
				justify=tkinter.CENTER,
				fill=color,
				font=(zynthian_gui_config.font_family,int(0.7*zynthian_gui_config.font_size)),
				text=str(midi_cc))
		else:
			self.canvas.itemconfig(self.midi_bind, text=str(midi_cc), fill=color)


	def erase_midi_bind(self):
		if self.midi_bind:
			self.canvas.itemconfig(self.midi_bind, text="")


	def set_midi_bind(self):
		if self.zctrl.midi_cc==0:
			#self.erase_midi_bind()
			self.plot_midi_bind("/{}".format(self.zctrl.value_range))
		elif self.zyngui.midi_learn_mode:
			self.plot_midi_bind("??",zynthian_gui_config.color_ml)
		elif self.zyngui.midi_learn_zctrl and self.zctrl==self.zyngui.midi_learn_zctrl:
			self.plot_midi_bind("??",zynthian_gui_config.color_hl)
		elif self.zctrl.midi_cc and self.zctrl.midi_cc>0:
			midi_cc=zyncoder.lib_zyncoder.get_midi_filter_cc_swap(self.zctrl.midi_chan, self.zctrl.midi_cc)
			self.plot_midi_bind(midi_cc)
		elif self.zctrl.midi_learn_cc and self.zctrl.midi_learn_cc>0:
			midi_cc=zyncoder.lib_zyncoder.get_midi_filter_cc_swap(self.zctrl.midi_learn_chan, self.zctrl.midi_learn_cc)
			if not midi_cc:
				midi_cc=self.zctrl.midi_learn_cc
			self.plot_midi_bind(midi_cc)
		else:
			self.erase_midi_bind()


	def set_title(self, tit):
		self.title=str(tit)
		#Calculate the font size ...
		max_fs=int(1.0*zynthian_gui_config.font_size)
		words=self.title.split()
		n_words=len(words)
		maxnumchar=max([len(w) for w in words])
		rfont=tkFont.Font(family=zynthian_gui_config.font_family,size=max_fs)
		if n_words==1:
			maxlen=rfont.measure(self.title)
		elif n_words==2:
			maxlen=max([rfont.measure(w) for w in words])
		elif n_words==3:
			maxlen=max([rfont.measure(w) for w in [words[0]+' '+words[1], words[1]+' '+words[2]]])
			max_fs=max_fs-1
		elif n_words>=4:
			maxlen=max([rfont.measure(w) for w in [words[0]+' '+words[1], words[2]+' '+words[3]]])
			max_fs=max_fs-1
		fs=int((zynthian_gui_config.ctrl_width-6)*max_fs/maxlen)
		fs=min(max_fs,max(int(0.7*zynthian_gui_config.font_size),fs))
		#logging.debug("TITLE %s => MAXLEN=%d, FONTSIZE=%d" % (self.title,maxlen,fs))
		#Set title label
		if not self.label_title:
			self.label_title = tkinter.Label(self.canvas,
				text=self.title,
				font=(zynthian_gui_config.font_family,fs),
				wraplength=self.width-6,
				justify=tkinter.LEFT,
				bg=zynthian_gui_config.color_panel_bg,
				fg=zynthian_gui_config.color_panel_tx)
			self.label_title.place(x=3, y=4, anchor=tkinter.NW)
		else:
			self.label_title.config(text=self.title,font=(zynthian_gui_config.font_family,fs))


	def calculate_value_font_size(self):
		if self.zctrl.labels:
			maxlen=len(max(self.zctrl.labels, key=len))
			if maxlen>3:
				rfont=tkFont.Font(family=zynthian_gui_config.font_family,size=zynthian_gui_config.font_size)
				maxlen=max([rfont.measure(w) for w in self.zctrl.labels])
			#print("LONGEST VALUE: %d" % maxlen)
			if maxlen>100:
				font_scale=0.7
			elif maxlen>85:
				font_scale=0.8
			elif maxlen>70:
				font_scale=0.9
			elif maxlen>55:
				font_scale=1.0
			elif maxlen>40:
				font_scale=1.1
			elif maxlen>30:
				font_scale=1.2
			elif maxlen>20:
				font_scale=1.3
			else:
				font_scale=1.4
		else:
			if self.format_print:
				maxlen=max(len(self.format_print.format(self.zctrl.value_min)),len(self.format_print.format(self.zctrl.value_max)))
			else:
				maxlen=max(len(str(self.zctrl.value_min)),len(str(self.zctrl.value_max)))
			if maxlen>5:
				font_scale=0.8
			elif maxlen>4:
				font_scale=0.9
			elif maxlen>3:
				font_scale=1.1
			else:
				if self.zctrl.value_min>=0 and self.zctrl.value_max<200:
					font_scale=1.4
				else:
					font_scale=1.3
		#Calculate value font size
		self.value_font_size=int(font_scale*zynthian_gui_config.font_size)
		#Update font config in text object
		if self.value_text:
			self.canvas.itemconfig(self.value_text, font=(zynthian_gui_config.font_family,self.value_font_size))


	def config(self, zctrl):
		#print("CONFIG CONTROLLER %s => %s" % (self.index,zctrl.name))
		self.zctrl=zctrl
		self.step=1
		self.mult=1
		self.val0=0
		self.value=None
		self.n_values=127
		self.inverted=False
		self.scale_value=1
		self.format_print=None
		self.set_title(zctrl.short_name)
		self.set_midi_bind()

		logging.debug("ZCTRL '%s': %s (%s -> %s), %s, %s" % (zctrl.short_name,zctrl.value,zctrl.value_min,zctrl.value_max,zctrl.labels,zctrl.ticks))

		#List of values (value selector)
		if isinstance(zctrl.labels,list):
			self.n_values=len(zctrl.labels)
			val=zctrl.value-zctrl.value_min
			if isinstance(zctrl.ticks,list):
				if zctrl.ticks[0]>zctrl.ticks[-1]:
					self.inverted=True
				if (isinstance(zctrl.midi_cc, int) and zctrl.midi_cc>0):
					self.max_value=127
					self.step=max(1,int(16/self.n_values))
				else:
					if zctrl.value_range>32:
						self.step = max(4,int(zctrl.value_range/(self.n_values*4)))
						self.max_value = zctrl.value_range + self.step*4
					else:
						self.mult=max(4,int(32/self.n_values))
						self.max_value = zctrl.value_range + 1
			else:
				self.max_value=127;
				self.step=max(1,int(16/self.n_values))

		#Numeric value
		else:
			#"List Selection Controller" => step 1 element by rotary tick
			if zctrl.midi_cc==0:
				self.max_value=self.n_values=zctrl.value_max
				self.mult=4
				self.val0=1
				val=zctrl.value
			else:
				r=zctrl.value_max-zctrl.value_min
				#Integer < 127
				if isinstance(r,int) and r<=127:
					self.max_value=self.n_values=r
					self.mult=max(1,int(128/self.n_values))
					val=zctrl.value-zctrl.value_min
				#Integer > 127 || Float
				else:
					self.max_value=self.n_values=127
					self.scale_value=r/self.max_value
					if self.scale_value<0.013:
						self.format_print="{0:.2f}"
					elif self.scale_value<0.13:
						self.format_print="{0:.1f}"
					val=(zctrl.value-zctrl.value_min)/self.scale_value
				#If many values => use adaptative step size based on rotary speed
				if self.n_values>=96:
					self.step=0

		#Calculate scale parameter for plotting
		if zctrl.ticks:
			self.scale_plot=self.max_value/zctrl.value_range
		elif self.n_values>1:
			self.scale_plot=self.max_value/(self.n_values-1)
		else:
			self.scale_plot=self.max_value

		self.calculate_value_font_size()
		self.set_value(val)
		self.setup_zyncoder()

		#logging.debug("labels: "+str(zctrl.labels))
		#logging.debug("ticks: "+str(zctrl.ticks))
		#logging.debug("value_min: "+str(zctrl.value_min))
		#logging.debug("value_max: "+str(zctrl.value_max))
		#logging.debug("range: "+str(zctrl.value_range))
		#logging.debug("inverted: "+str(self.inverted))
		#logging.debug("n_values: "+str(self.n_values))
		#logging.debug("max_value: "+str(self.max_value))
		#logging.debug("step: "+str(self.step))
		#logging.debug("mult: "+str(self.mult))
		#logging.debug("scale_plot: "+str(self.scale_plot))
		#logging.debug("val0: "+str(self.val0))
		#logging.debug("value: "+str(self.value))


	def zctrl_sync(self):
		#List of values (value selector)
		if self.zctrl.labels:
			#logging.debug("ZCTRL SYNC LABEL => {}".format(self.zctrl.get_value2label()))
			val=self.zctrl.get_label2value(self.zctrl.get_value2label())
		#Numeric value
		else:
			#"List Selection Controller" => step 1 element by rotary tick
			if self.zctrl.midi_cc==0:
				val=self.zctrl.value
			else:
				val=(self.zctrl.value-self.zctrl.value_min)/self.scale_value
		#Set value & Update zyncoder
		self.set_value(val, True, False)
		#logging.debug("ZCTRL SYNC {} => {}".format(self.title, val))


	def setup_zyncoder(self):
		self.init_value=None
		try:
			if isinstance(self.zctrl.osc_path,str):
				#logging.debug("Setup zyncoder %d => %s" % (self.index,self.zctrl.osc_path))
				midi_cc=None
				zyn_osc_path="{}:{}".format(self.zctrl.osc_port,self.zctrl.osc_path)
				osc_path_char=ctypes.c_char_p(zyn_osc_path.encode('UTF-8'))
				#if zctrl.engine.osc_target:
				#	liblo.send(zctrl.engine.osc_target, self.zctrl.osc_path)
			elif isinstance(self.zctrl.graph_path,str):
				#logging.debug("Setup zyncoder %d => %s" % (self.index,self.zctrl.graph_path))
				midi_cc=None
				osc_path_char=None
			else:
				#logging.debug("Setup zyncoder %d => %s" % (self.index,self.zctrl.midi_cc))
				midi_cc=self.zctrl.midi_cc
				osc_path_char=None
			if zyncoder.lib_zyncoder:
				if self.inverted:
					pin_a=zynthian_gui_config.zyncoder_pin_b[self.index]
					pin_b=zynthian_gui_config.zyncoder_pin_a[self.index]
				else:
					pin_a=zynthian_gui_config.zyncoder_pin_a[self.index]
					pin_b=zynthian_gui_config.zyncoder_pin_b[self.index]
				zyncoder.lib_zyncoder.setup_zyncoder(self.index,pin_a,pin_b,self.zctrl.midi_chan,midi_cc,osc_path_char,int(self.mult*self.value),int(self.mult*(self.max_value-self.val0)),self.step)
		except Exception as err:
			logging.error("%s" % err)


	def set_value(self, v, set_zyncoder=False, send_zyncoder=True):
		if v>self.max_value:
			v=self.max_value
		elif v<0:
			v=0
		if self.value is None or self.value!=v:
			self.value=v
			#logging.debug("CONTROL %d VALUE => %s" % (self.index,self.value))
			if self.shown:
				if set_zyncoder and zyncoder.lib_zyncoder:
					if self.mult>1: v=self.mult*v
					zyncoder.lib_zyncoder.set_value_zyncoder(self.index,ctypes.c_uint(int(v)),int(send_zyncoder))
				self.plot_value()
			return True


	def set_init_value(self, v):
		if self.init_value is None:
			self.init_value=v
			self.set_value(v,True)
			logging.debug("INIT VALUE %s => %s" % (self.index,v))


	def read_zyncoder(self):
		if zyncoder.lib_zyncoder:
			val=zyncoder.lib_zyncoder.get_value_zyncoder(self.index)
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
				self.zyngui.zynswitch_defered('S',self.index)
			elif dts>=0.3 and dts<2:
				self.zyngui.zynswitch_defered('B',self.index)
			elif dts>=2:
				self.zyngui.zynswitch_defered('L',self.index)
		elif self.canvas_motion_dx>20:
			self.zyngui.zynswitch_defered('X',self.index)
		elif self.canvas_motion_dx<-20:
			self.zyngui.zynswitch_defered('Y',self.index)


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


	def cb_canvas_wheel(self,event):
		if event.num == 5 or event.delta == -120:
			self.set_value(self.value - 1, True)
		if event.num == 4 or event.delta == 120:
			self.set_value(self.value + 1, True)

#------------------------------------------------------------------------------
