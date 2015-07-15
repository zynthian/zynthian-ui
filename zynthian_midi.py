#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Zynthian GUI: zynthian_midi.py

MIDI functionality for Zynthian GUI

author: José Fernandom Moyano (ZauBeR)
email: fernando@zauber.es
created: 2015-05-18
modified:  2015-07-11
"""

import alsaseq
import alsamidi

class zynthian_midi:

	bank_msb_selected=0;
	bank_lsb_selected=0;
	prg_selected=0;

	def __init__(self,client_name="Zynthian_gui"):
		alsaseq.client(client_name,1,1,True)
		#alsaseq.connectto(0,130,0)
		alsaseq.start()

	def set_midi_control(self,ctrl,val):
		alsaseq.output((alsaseq.SND_SEQ_EVENT_CONTROLLER, 1, 0, 0, (0, 0), (0, 0), (0, 0), (0, 0, 0, 0, ctrl, val)))

	def set_midi_bank_msb(self,msb):
		print("Set MIDI Bank MSB: " + str(msb))
		self.bank_msb_selected=msb
		self.set_midi_control(0,msb)

	def set_midi_bank_lsb(self,lsb):
		print("Set MIDI Bank LSB: " + str(lsb))
		self.bank_lsb_selected=lsb
		self.set_midi_control(32,lsb)

	def set_midi_prg(self,prg):
		print("Set MIDI Program: " + str(prg))
		self.prg_selected=prg
		event=alsamidi.pgmchangeevent(0, prg)
		alsaseq.output(event)

