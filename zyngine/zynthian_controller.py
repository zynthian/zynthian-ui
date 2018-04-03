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
		self.value_max=127
		self.value_mult=1
		self.labels=None
		self.values=None
		self.ticks=None
		self.value2label=None
		self.label2value=None

		self.midi_chan=None
		self.midi_cc=None
		self.osc_port=None
		self.osc_path=None
		self.graph_path=None

		self.midi_learn_chan=None
		self.midi_learn_cc=None

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
		if 'value_mult' in options:
			self.value_mult=options['value_mult']
		if 'labels' in options:
			self.labels=options['labels']
		if 'values' in options:
			self.values=options['values']
		if 'ticks' in options:
			self.ticks=options['ticks']
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
		#Generate dictionaries for fast conversion labels<=>values
		if self.values and self.labels:
			self.value2label={}
			self.label2value={}
			for i in range(len(self.labels)):
				self.label2value[str(self.labels[i])]=self.values[i]
				self.value2label[str(self.values[i])]=self.labels[i]

	def setup_controller(self, chan, cc, val, maxval=127):
		self.midi_chan=chan
		self.value=self.value_default=val
		self.value_min=0
		self.value_mult=1
		# OSC Path / MIDI CC
		if isinstance(cc,str):
			self.osc_path=cc
		else:
			self.midi_cc=cc
		# Numeric / Selector
		if isinstance(maxval,int):
			self.value_max=maxval
		elif isinstance(maxval,str):
			self.labels=maxval.split('|')
			#self.value_max=len(self.labels)-1
		elif isinstance(maxval,list):
			if isinstance(maxval[0],list):
				self.labels=maxval[0]
				self.ticks=maxval[1]
				#self.value_max=self.ticks[-1]
			else:
				self.labels=maxval
				self.value_max=len(maxval)-1

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
		val=self.value
		if self.labels:
			if self.ticks:
				minval=[self.labels, self.ticks]
				maxval=None
			else:
				minval=self.labels
				maxval=None
		else:
			minval=self.value_min
			maxval=self.value_max
		return [tit,chan,ctrl,val,minval,maxval]

	def get_value(self):
		return self.value

	def set_value(self, val, force_sending=False):
		#TODO Validate Value: Range!
		self.value=val
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

	def get_value2label(self, val):
		if self.value2label:
			try:
				return self.value2label[str(val)]
			except:
				return None
		else:
			return val

	def get_label2value(self, val=None):
		if val==None:
			val=self.value
		if self.label2value:
			try:
				return self.label2value[str(val)]
			except:
				return None
		else:
			return val

	def get_ctrl_midi_val(self):
		try:
			if isinstance(self.labels,list):
				if self.ticks:
					vi=self.labels.index(self.value)
					val=int(self.ticks[vi])
					if val>=128:
						val=127
					#logging.debug("LABEL INDEX => %s" % vi)
				else:
					n_values=len(self.labels)
					step=max(1,int(16/n_values));
					max_value=128-step;
					val=int(self.labels.index(self.value)*max_value/(n_values-1))
			else:
				val=int(127*(self.value-self.value_min)/(self.value_max-self.value_min))
		except Exception as e:
			val=0
			logging.debug("EXCEPTION => %s" % e)
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


#******************************************************************************
