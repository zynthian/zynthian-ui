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
import liblo
import ctypes

# Zynthian specific modules
from zyncoder import *


class zynthian_controller:

	def __init__(self, engine, symbol, name=None, options=None):
		self.engine=engine
		self.symbol=symbol
		if name:
			self.name=self.short_name=name
		else:
			self.name=self.short_name=symbol
		self.value=0
		self.value_default=0
		self.value_min=0
		self.value_mid=64
		self.value_max=127
		self.value_range=127
		self.labels=None
		self.ticks=None
		self.is_toggle=False
		self.is_integer=False

		self.midi_chan=None
		self.midi_cc=None
		self.osc_port=None
		self.osc_path=None
		self.graph_path=None

		self.midi_learn_chan=None
		self.midi_learn_cc=None

		self.label2value=None
		self.value2label=None

		if options:
			self.set_options(options)

	def set_options(self, options):
		if 'symbol' in options:
			self.symbol=options['symbol']
		if 'name' in options:
			self.name=options['name']
		if 'short_name' in options:
			self.short_name=options['short_name']
		if 'value' in options:
			self.value=options['value']
		if 'value_default' in options:
			self.value_default=options['value_default']
		if 'value_min' in options:
			self.value_min=options['value_min']
		if 'value_max' in options:
			self.value_max=options['value_max']
		if 'labels' in options:
			self.labels=options['labels']
		if 'ticks' in options:
			self.ticks=options['ticks']
		if 'is_toggle' in options:
			self.is_toggle=options['is_toggle']
		if 'is_integer' in options:
			self.is_integer=options['is_integer']
		if 'midi_chan' in options:
			self.midi_chan=options['midi_chan']
		if 'midi_cc' in options:
			self.midi_cc=options['midi_cc']
		if 'osc_port' in options:
			self.osc_port=options['osc_port']
		if 'osc_path' in options:
			self.osc_path=options['osc_path']
		if 'graph_path' in options:
			self.graph_path=options['graph_path']
		self._configure()

	def _configure(self):
		#Configure Selector Controller
		if self.ticks and self.labels:
			#Calculate min, max and range
			if self.ticks[0]<=self.ticks[-1]:
				self.value_min=self.ticks[0]
				self.value_max=self.ticks[-1]
			else:
				self.value_min=self.ticks[-1]
				self.value_max=self.ticks[0]
			#Generate dictionary for fast conversion labels=>values
			self.label2value={}
			self.value2label={}
			for i in range(len(self.labels)):
				self.label2value[str(self.labels[i])]=self.ticks[i]
				self.value2label[str(self.ticks[i])]=self.labels[i]
		#Common configuration
		self.value_range=self.value_max-self.value_min
		self.value_mid=self.value_min+self.value_range/2
		self._set_value(self.value)
		if self.value_default is None:
			self.value_default=self.value

	def setup_controller(self, chan, cc, val, maxval=127):
		self.midi_chan=chan

		# OSC Path / MIDI CC
		if isinstance(cc,str):
			self.osc_path=cc
		else:
			self.midi_cc=cc

		self.value_min=0
		self.value_max=127
		self.value=val
		# Numeric
		if isinstance(maxval,int):
			self.value_max=maxval
		# Selector
		elif isinstance(maxval,str):
			self.labels=maxval.split('|')
		elif isinstance(maxval,list):
			if isinstance(maxval[0],list):
				self.labels=maxval[0]
				self.ticks=maxval[1]
			else:
				self.labels=maxval
		self._configure()

	def set_midi_chan(self, chan):
		self.midi_chan=chan

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
		
		if self.labels:
			val=self.get_value2label()
			if self.ticks:
				minval=[self.labels, self.ticks]
				maxval=None
			else:
				minval=self.labels
				maxval=None
		else:
			val=self.value
			minval=self.value_min
			maxval=self.value_max
		return [tit,chan,ctrl,val,minval,maxval]

	def get_value(self):
		return self.value

	def _set_value(self, val, force_sending=False):
		if isinstance(val, str):
			self.value=self.get_label2value(val)
			return

		elif self.is_toggle:
			if val<self.value_mid:
				self.value=self.value_min
			else:
				self.value=self.value_max
			return

		elif self.ticks:
			#TODO Do something here?
			pass

		elif self.is_integer:
			val=int(val)

		if val>self.value_max:
			self.value=self.value_max
		elif val<self.value_min:
			self.value=self.value_min
		else:
			self.value=val

	def set_value(self, val, force_sending=False):
		self._set_value(val)

		# Send value ...
		if self.engine:
			try:
				self.engine.send_controller_value(self)
			except:
				if force_sending:
					try:
						if self.osc_path:
							sval=self.get_ctrl_osc_val()
							liblo.send(self.engine.osc_target,self.osc_path,sval)
						elif self.midi_cc>0:
							sval=self.get_ctrl_midi_val()
							self.engine.zyngui.zynmidi.set_midi_control(self.midi_chan,self.midi_cc,sval)
						logging.debug("Sending controller '%s' value => %s (%s)" % (self.symbol,val,sval))
					except:
						logging.warning("Can't send controller '%s' value" % self.symbol)

	def get_value2label(self, val=None):
		if val is None:
			val=self.value
		try:
			if self.ticks:
				if self.ticks[0]>self.ticks[-1]:
					for i in reversed(range(len(self.labels))):
						if val<=self.ticks[i]:
							return self.labels[i]
						return self.labels[0]
				else:
					for i in range(len(self.labels)-1):
						if val<self.ticks[i+1]:
							return self.labels[i]
						return self.labels[i+1]
			elif self.labels:
				i=int((val-self.value_min)*(len(self.labels)-1)/self.value_range)
				return self.labels[i]
			else:
				return val
		except Exception as e:
			logging.error(e)

	def get_label2value(self, label):
		try:
			if self.ticks:
				return self.label2value[str(label)]
			elif self.labels:
				i=self.labels.index(label)
				if i>=0:
					return self.value_min+i*self.value_range/(len(self.labels)-1)
			else:
				logging.error("No labels defined")
		except Exception as e:
			logging.error(e)

	def get_ctrl_midi_val(self):
		try:
			val=int(127*(self.value-self.value_min)/(self.value_max-self.value_min))
		except Exception as e:
			logging.error(e)
			val=0
		return val

	def get_ctrl_osc_val(self):
		if self.labels and len(self.labels)==2:
			if self.value=='on': return True
			elif self.value=='off': return False
		return self.value

	#--------------------------------------------------------------------------
	# Snapshots
	#--------------------------------------------------------------------------

	def get_snapshot(self):
		snapshot = {
			'value': self.value
		}

		# MIDI learning info
		if self.midi_learn_chan is not None and self.midi_learn_cc is not None:
			snapshot['midi_learn_chan'] = self.midi_learn_chan
			snapshot['midi_learn_cc'] = self.midi_learn_cc
			# Specific ZynAddSubFX slot info
			try:
				snapshot['slot_i'] = self.slot_i
			except:
				pass

		return snapshot

	def restore_snapshot(self, snapshot):
		if isinstance(snapshot, dict):
			self.set_value(snapshot['value'], True)
			if 'midi_learn_chan' in snapshot and 'midi_learn_cc' in snapshot:
				# Specific ZynAddSubFX slot info
				if 'slot_i' in snapshot:
					self.slot_i = snapshot['slot_i']
				# Restore MIDI-learn
				self.set_midi_learn(int(snapshot['midi_learn_chan']), int(snapshot['midi_learn_cc']))
		else:
			self.set_value(snapshot,True)

	#--------------------------------------------------------------------------
	# MIDI Learning
	#--------------------------------------------------------------------------

	def midi_learn(self):
		# Learn only if there is a working engine ...
		if self.engine:
			logging.info("MIDI learn: %s" % self.symbol)
			
			# If already learned, unlearn
			if self.midi_learn_cc:
				self.midi_unlearn()

			# If not a CC-mapped controller, delegate to engine's MIDI-learning implementation
			if not self.midi_cc:
				try:
					self.engine.midi_learn(self)
				except:
					logging.error("MIDI Learn NOT IMPLEMENTED!")

			# Call GUI method
			self.engine.zyngui.set_midi_learn(self)


	def midi_unlearn(self):
		# Unlearn only if there is a working engine and something to unlearn ...
		if self.engine and self.midi_learn_chan is not None and self.midi_learn_cc is not None:
			logging.info("MIDI Unlearn: %s" % self.symbol)
			unlearned=False

			# If standard MIDI-CC controller, delete MIDI router map
			if self.midi_cc:
				try:
					if zyncoder.lib_zyncoder.del_midi_filter_cc_swap(ctypes.c_ubyte(self.midi_learn_chan), ctypes.c_ubyte(self.midi_learn_cc)):
						logging.info("Deleted MIDI filter CC map: %s, %s" % (self.midi_learn_chan, self.midi_learn_cc))
						unlearned=True
					else:
						logging.error("Can't delete MIDI filter CC swap map: Call returned 0")
				except:
					logging.error("Can't delete MIDI filter CC swap map: %s, %s" % (self.midi_learn_chan, self.midi_learn_cc))

			# Else delegate to engine's MIDI-learning implementation
			else:
				try:
					if self.engine.midi_unlearn(self):
						unlearned=True
				except:
					logging.error("MIDI Unlearn => NOT IMPLEMENTED!")

			# If success unlearning ...
			if unlearned:

				# Clear variables
				self.midi_learn_chan=None
				self.midi_learn_cc=None

				# Call GUI method
				try:
					self.engine.zyngui.unset_midi_learn()
				except:
					pass

				# MIDI Unlearning success
				return True

			# Else unlearning failure
			else:
				return False

		#If	not engine or nothing to unlearn, return success
		return True


	def set_midi_learn(self, chan, cc):
		if self.engine:
			self.midi_unlearn()
			self.cb_midi_learn(chan,cc)

			if not self.midi_cc:
				try:
					self.engine.set_midi_learn(self)
				except:
					logging.error("Set MIDI learn => NOT IMPLEMENTED!")


	def cb_midi_learn(self, chan, cc):
		# Learn only if there is a working engine ...
		if self.engine:
			logging.info("MIDI-CC bond '%s' => %d, %d" % (self.symbol,chan,cc))

			# If standard MIDI-CC controller, create MIDI router map
			if self.midi_cc:
				try:
					if zyncoder.lib_zyncoder.set_midi_filter_cc_swap(ctypes.c_ubyte(chan), ctypes.c_ubyte(cc), ctypes.c_ubyte(self.midi_chan), ctypes.c_ubyte(self.midi_cc)):
						logging.info("Set MIDI filter CC map: (%s, %s) => (%s, %s)" % (chan, cc, self.midi_chan, self.midi_cc))
					else:
						logging.error("Can't set MIDI filter CC swap map: call returned 0")
						return False
				except Exception as e:
					logging.error("Can't set MIDI filter CC swap map: (%s, %s) => (%s, %s) => %s" % (self.midi_learn_chan, self.midi_learn_cc, self.midi_chan, self.midi_cc, e))
					return False

			# MIDI learning success
			self.midi_learn_chan=chan
			self.midi_learn_cc=cc

			# Call GUI method ...
			try:
				self.engine.zyngui.unset_midi_learn()
			except:
				pass

		#If	not engine or MIDI learning success, return True
		return True


	def midi_control_change(self, val):
		value=self.value_min+val*self.value_range/127
		self.set_value(value)
		#Refresh GUI controller in screen when needed ...
		try:
			if self.engine.zyngui.active_screen=='control' and self.engine.zyngui.screens['control'].mode=='control':
				self.engine.zyngui.screens['control'].set_controller_value(self)
		except Exception as e:
			logging.debug(e)


#******************************************************************************
