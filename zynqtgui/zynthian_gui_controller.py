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
import math
import liblo
import ctypes
import tkinter
import logging
from time import sleep
from string import Template
from datetime import datetime

# Zynthian specific modules
from zyncoder import *
from zyngine import zynthian_controller
from . import zynthian_gui_config

#------------------------------------------------------------------------------
# Controller GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_controller:

	def __init__(self, indx, zctrl):
		self.zyngui=zynthian_gui_config.zyngui
		self.zctrl=None
		self.n_values=127
		self.max_value=127
		self.inverted=False
		self.selmode = False
		self.logarithmic = False
		self.step=1
		self.mult=1
		self.val0=0
		self.value=0
		self.scale_plot=1
		self.scale_value=1
		self.value_plot=0
		self.value_print=None
		self.value_font_size=14


		self.rectangle=None
		self.triangle=None
		self.arc=None
		self.value_text=None
		self.label_title=None
		self.midi_bind=None
		self.refresh_plot_value = False

		self.index=indx
		self.row=zynthian_gui_config.ctrl_pos[indx][0]
		self.col=zynthian_gui_config.ctrl_pos[indx][1]
		self.sticky=zynthian_gui_config.ctrl_pos[indx][2]

		# Setup Controller and Zyncoder
		self.config(zctrl)
		self.show()


	def show(self):
		return


	def set_midi_bind(self):
		if self.zctrl.midi_cc==0:
			#self.erase_midi_bind()
			self.midi_bind = "/{}".format(self.zctrl.value_range)
		elif self.zyngui.midi_learn_mode:
			self.midi_bind = "??"
		elif self.zyngui.midi_learn_zctrl and self.zctrl==self.zyngui.midi_learn_zctrl:
			self.midi_bind = "??"
		elif self.zctrl.midi_learn_cc and self.zctrl.midi_learn_cc>0:
			midi_cc = self.zctrl.midi_learn_cc
			if not self.zyngui.is_single_active_channel():
				midi_cc = "{}#{}".format(self.zctrl.midi_learn_chan+1,midi_cc)
			self.midi_bind = midi_cc
		elif self.zctrl.midi_cc and self.zctrl.midi_cc>0:
			#midi_cc = self.zctrl.midi_cc
			swap_info= zyncoder.lib_zyncoder.get_midi_filter_cc_swap(self.zctrl.midi_chan, self.zctrl.midi_cc)
			midi_chan = swap_info >> 8
			midi_cc = swap_info & 0xFF
			if not self.zyngui.is_single_active_channel():
				midi_cc = "{}#{}".format(midi_chan+1,midi_cc)
			self.midi_bind = midi_cc


	def set_title(self, tit):
		self.title = str(tit)

	def config(self, zctrl):
		#logging.debug("CONFIG CONTROLLER %s => %s" % (self.index,zctrl.name))
		self.zctrl=zctrl
		self.step=1
		self.mult=1
		self.val0=0
		self.value=None
		self.n_values=127
		self.inverted=False
		self.selmode = False
		self.logarithmic = zctrl.is_logarithmic
		self.scale_value=1
		self.format_print=None
		self.set_title(zctrl.short_name)
		self.set_midi_bind()

		logging.debug("ZCTRL '%s': %s (%s -> %s), %s, %s" % (zctrl.short_name,zctrl.value,zctrl.value_min,zctrl.value_max,zctrl.labels,zctrl.ticks))

		#List of values (value selector)
		if isinstance(zctrl.labels,list):
			self.n_values=len(zctrl.labels)
			if isinstance(zctrl.ticks,list):
				if zctrl.ticks[0]>zctrl.ticks[-1]:
					self.inverted=True
				if (isinstance(zctrl.midi_cc, int) and zctrl.midi_cc>0):
					self.max_value=127
					self.step=max(1,int(16/self.n_values))
					val=zctrl.value-zctrl.value_min
				else:
					self.selmode = True
					self.max_value = self.n_values-1
					self.mult = max(4,int(32/self.n_values))
					val=zctrl.get_value2index()

					#if zctrl.value_range>32:
						#self.step = max(4,int(zctrl.value_range/(self.n_values*4)))
						#self.max_value = zctrl.value_range + self.step*4
					#else:
					#	self.mult=max(4,int(32/self.n_values))
					#	self.max_value = zctrl.value_range + 1
			else:
				self.max_value=127;
				self.step=max(1,int(16/self.n_values))
				val=zctrl.value-zctrl.value_min

		#Numeric value
		else:
			#"List Selection Controller" => step 1 element by rotary tick
			if zctrl.midi_cc==0:
				self.max_value=self.n_values=zctrl.value_max
				self.val0=1
				val=zctrl.value

				#If many values => use adaptative step size based on rotary speed
				if self.n_values>=96:
					self.step=0
					self.mult=1
				else:
					self.mult=4

			else:
				if zctrl.is_integer:
					#Integer < 127
					if zctrl.value_range<=127:
						self.max_value=self.n_values=zctrl.value_range
						self.mult=max(1,int(128/self.n_values))
						val=zctrl.value-zctrl.value_min
					#Integer > 127
					else:
						#Not MIDI controller
						if zctrl.midi_cc is None:
							self.max_value=self.n_values=zctrl.value_range
							self.scale_value=1
							val=(zctrl.value-zctrl.value_min)
						#MIDI controller
						else:
							self.max_value=self.n_values=127
							self.scale_value=r/self.max_value
							val=(zctrl.value-zctrl.value_min)/self.scale_value
				#Float
				else:
					self.max_value=self.n_values=200
					self.format_print="{0:.3g}"
					if self.logarithmic:
						self.scale_value = self.zctrl.value_max/self.zctrl.value_min
						self.log_scale_value = math.log(self.scale_value)
						val = self.n_values*math.log(zctrl.value/zctrl.value_min)/self.log_scale_value
					else:
						self.scale_value = zctrl.value_range/self.max_value
						val = (zctrl.value-zctrl.value_min)/self.scale_value

				#If many values => use adaptative step size based on rotary speed
				if self.n_values>=96:
					self.step=0

		#Calculate scale parameter for plotting
		if self.selmode:
			self.scale_plot=self.max_value/(self.n_values-1)
		elif zctrl.ticks:
			self.scale_plot=self.max_value/zctrl.value_range
		elif self.n_values>1:
			self.scale_plot=self.max_value/(self.n_values-1)
		else:
			self.scale_plot=self.max_value

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


	def zctrl_sync(self, set_zyncoder=True):
		#List of values (value selector)
		if self.selmode:
			val=self.zctrl.get_value2index()
		if self.zctrl.labels:
			#logging.debug("ZCTRL SYNC LABEL => {}".format(self.zctrl.get_value2label()))
			val=self.zctrl.get_label2value(self.zctrl.get_value2label())
		#Numeric value
		else:
			#"List Selection Controller" => step 1 element by rotary tick
			if self.zctrl.midi_cc==0:
				val=self.zctrl.value
			elif self.logarithmic:
				val = self.n_values*math.log(self.zctrl.value/self.zctrl.value_min)/self.log_scale_value
			else:
				val = (self.zctrl.value-self.zctrl.value_min)/self.scale_value
		#Set value & Update zyncoder
		self.set_value(val, set_zyncoder, False)
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
			if set_zyncoder and zyncoder.lib_zyncoder:
				if self.mult>1: v = self.mult*v
				zyncoder.lib_zyncoder.set_value_zyncoder(self.index,ctypes.c_uint(int(v)),int(send_zyncoder))
				#logging.debug("set_value_zyncoder {} ({}, {}) => {}".format(self.index, self.zctrl.symbol,self.zctrl.midi_cc,v))
			return True


	def set_init_value(self, v):
		if self.init_value is None:
			self.init_value=v
			self.set_value(v,True)
			logging.debug("INIT VALUE %s => %s" % (self.index,v))


	def read_zyncoder(self):
		if zyncoder.lib_zyncoder:
			val=zyncoder.lib_zyncoder.get_value_zyncoder(self.index)
			#logging.debug("ZYNCODER %d (%s), RAW VALUE => %s" % (self.index,self.title,val))
		else:
			val=self.value*self.mult-self.val0

		if self.mult>1:
			val = int((val+1)/self.mult)

		return self.set_value(val)


	def cb_canvas_wheel(self,event):
		if event.num == 5 or event.delta == -120:
			self.set_value(self.value - 1, True)
		if event.num == 4 or event.delta == 120:
			self.set_value(self.value + 1, True)

#------------------------------------------------------------------------------
