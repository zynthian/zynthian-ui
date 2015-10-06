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

	bank_msb_selected=[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0];
	bank_lsb_selected=[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0];
	prg_selected=[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0];

	def __init__(self, client_name="Zynthian_gui"):
		alsaseq.client(client_name,1,1,True)
		#alsaseq.connectto(0,130,0)
		alsaseq.start()

	def set_midi_control(self, chan,ctrl,val):
		alsaseq.output((alsaseq.SND_SEQ_EVENT_CONTROLLER, 1, 0, 0, (0, 0), (0, 0), (0, 0), (0, 0, 0, 0, ctrl, val)))

	def set_midi_bank_msb(self, chan, msb):
		print("Set MIDI CH " + str(chan) + ", Bank MSB: " + str(msb))
		self.bank_msb_selected[chan]=msb
		self.set_midi_control(chan,0,msb)

	def get_midi_bank_msb(self, chan):
		return self.bank_msb_selected[chan]

	def set_midi_bank_lsb(self, chan, lsb):
		print("Set MIDI CH " + str(chan) + ", Bank LSB: " + str(lsb))
		self.bank_lsb_selected[chan]=lsb
		self.set_midi_control(chan,32,lsb)

	def get_midi_bank_lsb(self, chan):
		return self.bank_lsb_selected[chan]

	def set_midi_prg(self, chan, prg):
		print("Set MIDI CH " + str(chan) + ", Program: " + str(prg))
		self.prg_selected[chan]=prg
		event=alsamidi.pgmchangeevent(chan, prg)
		alsaseq.output(event)

	def get_midi_prg(self, chan):
		return self.prg_selected[chan]

	def set_midi_instr(self, chan, msb, lsb, prg):
		print("Set MIDI CH " + str(chan) + ", Bank MSB: " + str(msb) + ", Bank LSB: " + str(lsb) + ", Program: " + str(prg))
		self.bank_msb_selected[chan]=msb
		self.bank_lsb_selected[chan]=lsb
		self.prg_selected[chan]=prg
		self.set_midi_control(chan,0,msb)
		self.set_midi_control(chan,32,lsb)
		event=alsamidi.pgmchangeevent(chan, prg)
		alsaseq.output(event)

	def get_midi_instr(self, chan):
		return [self.bank_msb_selected[chan],self.bank_lsb_selected[chan],self.prg_selected[chan]]
