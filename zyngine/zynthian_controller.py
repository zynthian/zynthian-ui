# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Controller (zynthian_controller)
# 
# zynthian controller
# 
# Copyright (C) 2015-2017 Fernando Moyano <jofemodo@zynthian.org>
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

import logging

class zynthian_controller:
	engine=None
	symbol=None
	name=None
	short_name=None

	value=None
	value_default=None
	value_min=None
	value_max=None
	value_mult=None
	spoints_labels=None
	spoints_values=None

	midi_chan=None
	midi_cc=None
	osc_port=None
	osc_path=None
	graph_path=None

	def __init__(self, engine, symbol, name=None, options=None):
		self.engine=engine
		self.symbol=symbol
		if name:
			self.name=self.short_name=name
		else:
			self.name=symbol
		if options:
			self.set_options(options)
		if self.value_type is None:
			self.value_type='integer'

	def set_options(self, options):
		if short_name in options:
			self.short_name=short_name
		if value in options:
			self.value=options['value']
		if value_type in options:
			self.value_type=options['value_type']
		if value_default in options:
			self.value_default=options['value_default']
		if value_min in options:
			self.value_min=options['value_min']
		if value_max in options:
			self.value_max=options['value_max']
		if value_mult in options:
			self.value_mult=options['value_mult']
		if spoints_labels in options:
			self.spoints_labels=options['spoint_labels']
		if spoints_values in options:
			self.spoints_values=options['spoint_values']
		if midi_chan in options:
			self.midi_chan=options['midi_chan']
		if midi_cc in options:
			self.midi_cc=options['midi_cc']
		if osc_port in options:
			self.osc_port=options['osc_port']
		if osc_path in options:
			self.osc_path=options['osc_path']
		if graph_path in options:
			self.graph_path=options['graph_path']

	def set_midi_controller(self, chan, cc, val):
		self.midi_chan=chan
		self.midi_cc=cc
		self.value=self.value_default=val
		self.value_min=0
		self.value_max=127
		self.value_mult=1

	def get_ctrl_array(self):
		tit=self.short_name
		if self.midi_chan:
			chan=self.midi_chan
		else:
			chan=0
		if self.midi_cc:
			ctrl=self.midi_cc
		elif self.osc_path:
			ctrl=self.osc_path
		elif self.graph_path:
			ctrl=self.graph_path
		val=self.value
		if self.spoints_labels:
			max_val='|'.join(spoints)
		else:
			r=self.value_max-self.value_min
			if self.value_type=='interger' and r<128:
				max_val=r
			else:
				max_val=127
		return [tit,chan,ctrl,val,max_val]

	def set_value(self, val, force_sending=False):
		# Validate value?? => Not by now ...
		self.value=val
		# Send value ...
		self.engine.set_ctrl_value(self, val)
		if force_sending:
			if self.osc_path:
				liblo.send(self.engine.osc_target,self.osc_path,self.get_ctrl_osc_val(ctrl[2],ctrl[3]))
			elif self.midi_cc:
				self.zyngui.zynmidi.set_midi_control(self.midi_chan,ctrl[1],self.get_ctrl_midi_val(ctrl[2],ctrl[3]))

	def get_ctrl_midi_val(self):
		if isinstance(self.value,int):
			return self.value
		#CONTINUAR AKI!!
		if isinstance(maxval,str):
			values=maxval.split('|')
		elif isinstance(maxval,list):
			if isinstance(maxval[0],list): 
				values=maxval[0]
				ticks=maxval[1]
			else: values=maxval
		elif max_val>0:
			values=None
			max_value=n_values=maxval
		if values:
			n_values=len(values)
			step=max(1,int(16/n_values));
			max_value=128-step;
			try:
				val=ticks[values.index(val)]
			except:
				val=int(values.index(val)*max_value/(n_values-1))
		if val>max_value:
			val=max_value
		return val

	def get_ctrl_osc_val(self, val, maxval):
		if maxval=='off|on':
			if val=='on': return True
			elif val=='off': return False
		return val

	def midi_learn(self):
		logging.info("MIDI Learn: %s => NOT IMPLEMENTED!" % self.symbol)

	def midi_unlearn(self):
		logging.info("MIDI Unlearn: %s => NOT IMPLEMENTED!" % self.symbol)

