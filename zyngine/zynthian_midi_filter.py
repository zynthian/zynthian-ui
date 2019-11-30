#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Parser for MIDI filter script language
#
# Valid rule formats:
# -------------------------------------
#  IGNORE [CH#??] EV[#??]
#  MAP [CH#??] EV[#??] => [CH#??] EV[#??]
#  CLEAN [CH#??] EV[#??]
#
# Valid event types (EV): 
# -------------------------------------
#  NON => Note-On
#  NOFF => Note-Off
#  PC#?? => Program Change (??=program number)
#  KP => Key Press (after-touch)
#  CP => Channel Press (after-touch)
#  PB => Pitch Bending
#  CC#?? => Continuous Controller Change (??=controller number)
# 
# Valid numeric expressions:
# -------------------------------------
#  5			=> a single number
#  5,6,7 		=> a list of numbers
#  5:7			=> a range of numbers, including both limitters
#  1,2,3:5	=> a mix of lists and ranges
#
# *****************************************************************************
#
# Copyright (C) 2017 Fernando Moyano <jofemodo@zynthian.org>
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

import os
import sys
import logging

sys.path.append(os.environ.get('ZYNTHIAN_UI_DIR'))

# Zynthian specific modules
from zyncoder import *

#------------------------------------------------------------------------------
# Parser related classes
#------------------------------------------------------------------------------

class MidiFilterException(Exception):
	pass

class MidiFilterArgs:

	EVENT_TYPES=("NON","NOFF","KP","CC","PB","PC","CP")
	SINGLE_ARG_TYPES=("PB","CP")
	EVENT_TYPE_CODES={
		# Channel 3-bytes-messages
		"NON": 0x9,		# Note-On
		"NOFF": 0x8, 	# Note-Off
		"KP": 0xA,		# Key Press
		"CC": 0xB,		# Control Change
		"PB": 0xE,		# Pitch Bending
		# Channel 2-bytes-messages
		"PC": 0xC,		# Program Change
		"CP": 0xD		# Channel Press
	}


	def __init__(self, args, args0=None):
		self.ch_list = None
		self.ev_type = None
		self.ev_list = None

		n_args = len(args)
		if n_args>2:
			raise MidiFilterException("Too many arguments (%s)" % n_args)

		res = []
		for arg in args:
			res.append(self.parse_arg(arg))

		if n_args==1:
			if args0 is None:
				self.ch_list = range(0,16)
			else:
				self.ch_list = args0.ch_list
			self.ev_type = res[0][0]
			self.ev_list = res[0][1]

		elif n_args==2:
			if res[0][0]!="CH":
				raise MidiFilterException("Expected Channel")
			self.ch_list = res[0][1]
			self.ev_type = res[1][0]
			self.ev_list = res[1][1]

		if self.ev_type not in self.EVENT_TYPES:
			raise MidiFilterException("Invalid Event Type (%s)" % self.ev_type)


	def parse_arg(self, arg):
		parts = arg.split("#")
		arg_type = parts[0]

		n_parts=len(parts)
		if n_parts>2 or (arg_type in self.SINGLE_ARG_TYPES and n_parts>1) or (arg_type=="CH" and n_parts==1):
			raise MidiFilterException("Invalid argument format (%s)" % arg)

		if n_parts==2:
			values = []
			ranges = parts[1].split(",")

			for r in ranges:
				rparts = r.split(":")
				n_rparts = len(rparts)
				if n_rparts==1:
					values.append(int(r))
				elif n_rparts==2:
					for i in range(int(rparts[0]),int(rparts[1])+1):
						values.append(i)
				elif n_rparts>2:
					raise MidiFilterException("Invalid range format (%s)" % r)

		elif arg_type not in (self.SINGLE_ARG_TYPES):
			values = range(0,128)

		else:
			values=[0]

		return [parts[0],values]


class MidiFilterRule:

	def __init__(self, rule, set_rules=True):
		self.rule_type=None
		self.args=[]
		self.parse_rule(rule, set_rules)


	def parse_rule(self, rule, set_rules=True):
		# Check that the rule has only 1 line
		parts=rule.split("\n")
		if len(parts)>1:
			raise MidiFilterException("Invalid rule format. Multi-line rules are not allowed.")

		# Parse rule type: IGNORE | MAP | CLEAN
		parts=rule.split()
		self.rule_type=parts[0]

		# IGNORE rule ...
		if self.rule_type=="IGNORE" or self.rule_type=="CLEAN":
			if len(parts)>3:
				raise MidiFilterException("Invalid rule format. Too many parts.")
			# Parse arguments
			self.args.append(MidiFilterArgs(parts[1:3]))
		# MAP rule ...
		elif self.rule_type=="MAP":
			try:
				arrow_i = parts.index("=>")
				# Parse arguments
				self.args.append(MidiFilterArgs(parts[1:arrow_i]))
				self.args.append(MidiFilterArgs(parts[arrow_i+1:],self.args[0]))
				
				n0 = len(self.args[0].ch_list)
				n1 = len(self.args[1].ch_list)
				if n0>1 and n1==1:
					self.args[1].ch_list = self.args[1].ch_list * n0
				elif n0!=n1:
					raise Exception("MAP rule channel lists can't be matched ({}=>{})".format(n0,n1))
				logging.debug("Mapping {} channels to {} ...".format(n0, n1))

				m0 = len(self.args[0].ev_list)
				m1 = len(self.args[1].ev_list)
				if m1==1:
					self.args[1].ev_list = self.args[1].ev_list * m0
				elif m0!=m1:
					raise Exception("MAP rule event lists can't be matched ({}=>{}".format(m0,m1))
				logging.debug("Mapping {} events to {} ...".format(m0, m1))

			except Exception as e:
				raise MidiFilterException("Invalid MAP rule format (%s): %s" % (rule, e))
		else:
			raise MidiFilterException("Invalid RULE type (%s)" % self.rule_type)

		if set_rules:
			self.set_rules()


	def set_rules(self, set_rules=True):
		n_rules=0
		if self.rule_type=="IGNORE" or self.rule_type=="CLEAN":
			for ch in self.args[0].ch_list:
				ev_type=MidiFilterArgs.EVENT_TYPE_CODES[self.args[0].ev_type]
				for ev_num in self.args[0].ev_list:
					n_rules += 1
					logging.debug("%s CH#%s %s#%s" % (self.rule_type,ch,self.args[0].ev_type,ev_num))
					if set_rules:
						if self.rule_type=="IGNORE":
							zyncoder.lib_zyncoder.set_midi_filter_event_ignore(ev_type, ch, ev_num)
						elif self.rule_type=="CLEAN":
							zyncoder.lib_zyncoder.del_midi_filter_event_map(ev_type, ch, ev_num)

		elif self.rule_type=="MAP":
			
			for ch1,ch2 in zip(self.args[0].ch_list,self.args[1].ch_list):
				ev1_type=MidiFilterArgs.EVENT_TYPE_CODES[self.args[0].ev_type]
				ev2_type=MidiFilterArgs.EVENT_TYPE_CODES[self.args[1].ev_type]
				for ev1_num,ev2_num in zip(self.args[0].ev_list,self.args[1].ev_list):
					n_rules += 1
					logging.debug("MAP CH#%s %s#%s => CH#%s %s#%s" % (ch1,self.args[0].ev_type,ev1_num,ch2,self.args[1].ev_type,ev2_num))
					if set_rules:
						zyncoder.lib_zyncoder.set_midi_filter_event_map(ev1_type, ch1, ev1_num, ev2_type, ch2, ev2_num)

		return n_rules


	def del_rules(self, del_rules=True):
		n_rules=0
		for ch in self.args[0].ch_list:
			ev_type=MidiFilterArgs.EVENT_TYPE_CODES[self.args[0].ev_type]
			for ev_num in self.args[0].ev_list:
				n_rules += 1
				logging.debug("CLEAN CH#%s %s#%s" % (ch,self.args[0].ev_type,ev_num))
				if del_rules:
					zyncoder.lib_zyncoder.del_midi_filter_event_map(ev_type, ch, ev_num)
		return n_rules


class MidiFilterScript:

	def __init__(self, script=None, set_rules=True):
		self.rules={}
		if script:
			self.parse_script(script, set_rules)


	def parse_script(self, script, set_rules=True):
		self.rules={}
		if isinstance(script,str):
			script=script.split("\n")
		elif not isinstance(script,list) and not isinstance(script,tuple):
			raise MidiFilterException("Script must be a String or a List of Strings")
		for rule in script:
			rule=rule.strip()
			if len(rule)>0:
				# Ignore commented rules
				if rule[0:2]=='//':
					continue
				if len(rule)>8:
					self.rules[rule]=MidiFilterRule(rule, set_rules)
				else:
					raise MidiFilterException("Script Rule is too short to be valid")


	#Selectively remove only the rules set by the script
	def clean(self):
		for rule in self.rules:
			self.rules[rule].del_rules()


	def clean_all(self):
		zyncoder.lib_zyncoder.reset_midi_filter_event_map()


#------------------------------------------------------------------------------
# UnitTest
#------------------------------------------------------------------------------

import unittest

class TestMidiFilterRule(unittest.TestCase):

	def test_absurde_rules(self):
		#Bad rules
		with self.assertRaises(MidiFilterException):
			MidiFilterRule("ABSURDE CH#1,2,3:8 PB#7,8", False)


	def test_ignore_rules(self):
		#Good rules
		mfr=MidiFilterRule("IGNORE CH#3 CC#5", False)
		self.assertTrue(mfr.set_rules()==1)
		mfr=MidiFilterRule("IGNORE CH#3,5,7 PB", False)
		self.assertTrue(mfr.set_rules()==3)
		mfr=MidiFilterRule("IGNORE CH#3:8 CC#1:3", False)
		self.assertTrue(mfr.set_rules()==18)
		mfr=MidiFilterRule("IGNORE CH#1,2,3:8 CC#1:3,7,8", False)
		self.assertTrue(mfr.set_rules()==40)
		#Bad rules
		with self.assertRaises(MidiFilterException):
			MidiFilterRule("IGNORE XH#1,2,3:8 PB#7,8", False)
		with self.assertRaises(MidiFilterException):
			MidiFilterRule("IGNORE CH#1,2,3:8 XB#7,8", False)
		with self.assertRaises(MidiFilterException):
			MidiFilterRule("IGNORE CH#1,2,3:8 PB#7,8", False)
		with self.assertRaises(MidiFilterException):
			MidiFilterRule("IGNORE CH#1,2,3:8 CP#1:3", False)


	def test_map_rules(self):
		#Good rules
		mfr=MidiFilterRule("MAP CH#1 CC#5 => CC#7", False)
		self.assertTrue(mfr.set_rules()==1)
		mfr=MidiFilterRule("MAP CH#3 CC#5 => CH#4 CC#7", False)
		self.assertTrue(mfr.set_rules()==1)
		mfr=MidiFilterRule("MAP CH#0 CC#71 => CH#1 PB")
		self.assertTrue(mfr.set_rules()==1)
		mfr=MidiFilterRule("MAP CH#3,5,7 CC#5,3 => CH#4,7,8 CC#9,10", False)
		self.assertTrue(mfr.set_rules()==6)
		mfr=MidiFilterRule("MAP CH#3:8 CC#1:3 => CH#4:9 CC#3:5", False)
		self.assertTrue(mfr.set_rules()==18)
		mfr=MidiFilterRule("MAP CH#1,2,3:8 CC#1:3,7,8 => CH#5:10,11,12 CC#1,2,4:6", False)
		self.assertTrue(mfr.set_rules()==40)
		mfr=MidiFilterRule("MAP CH#0:15 CC#45 => CH#15 CC#76", False)
		self.assertTrue(mfr.set_rules()==16)
		#Bad rules
		with self.assertRaises(MidiFilterException):
			MidiFilterRule("MAP XH#1,2,3:8 PB#7,8 => JK#76", False)
		with self.assertRaises(MidiFilterException):
			MidiFilterRule("MAP CH#1,2,3:8 PB#7,8 => CH#4:11 CC#2,5", False)
		with self.assertRaises(MidiFilterException):
			MidiFilterRule("MAP CH#2,3:8 CC#7,8 => CH#4:11 CC#2,5", False)


if __name__ == '__main__':
	# Set root logging level
	logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

	zyncoder.lib_zyncoder_init()
	unittest.main()
