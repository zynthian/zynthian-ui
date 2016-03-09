#!/usr/bin/python3
# -*- coding: utf-8 -*-
#********************************************************************
# ZYNTHIAN PROJECT: Zynthian Autoconnector for Jack Audio
# 
# Autoconnect Jack-MIDI devices
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
import os
import jack
from time import sleep

#------------------------------------------------------------------------------

#Refresh time
refresh_time = 2

#Synth Engine List
engine_list = [
	"zynaddsubfx",
	"fluidsynth",
	"LinuxSampler",
	"setBfree",
	"Carla",
	"MIDI Channel Filter",
	"MIDI Join"
]

#Input Black List
hw_black_list = [
	"Midi Through"
]

#------------------------------------------------------------------------------

def jack_connect(odev,idev):
	try:
		jclient.connect(odev,idev)
	except:
		pass

def midi_autoconnect():
	print("Autoconnecting Jack ...")

	#Get Physical MIDI-devices ...
	hw_out=jclient.get_ports(is_output=True, is_physical=True, is_midi=True)
	if len(hw_out)==0:
		hw_out=[]
	#Add ttymidi device ...
	tty_out=jclient.get_ports("ttymidi",is_output=True, is_physical=False, is_midi=True)
	try:
		hw_out.append(tty_out[0])
	except:
		pass

	#print("Physical Devices: " + str(hw_out))

	#Remove HW Black-listed
	for hw in hw_out:
		for i,v in enumerate(hw_black_list):
			if v in str(hw):
				hw_out.pop(i)

	#Get Synth Engines
	engines=[]
	for engine in engine_list:
		devs=jclient.get_ports(engine, is_input=True, is_midi=True, is_physical=False)
		try:
			dev=devs[0]
			if dev.shortname=='osc':
				dev=devs[1]
			#print("Engine "+str(dev)+" found")
			engines.append(dev)
		except:
			#print("Engine "+str(devs[0])+" is not present")
			pass

	#print("Engine Devices: " + str(engines))

	#Get Zynthian GUI devices
	zyngui_out=jclient.get_ports("Zynthian_gui", is_output=True, is_midi=True)
	zyngui_in=jclient.get_ports("Zynthian_gui", is_input=True, is_midi=True)

	#Get Zynthian Controller device
	zyncoder_out=jclient.get_ports("Zynthian_rencoder", is_output=True, is_midi=True)

	#Connect Physical devices to Synth Engines and Zynthian GUI
	for hw in hw_out:
		#print("Connecting HW "+str(hw))
		if len(zyngui_in)>0:
			jack_connect(hw,zyngui_in[0])
		if not zynthian_seq:
			for engine in engines:
				#print("Connecting HW "+str(hw)+" => "+str(engine))
				jack_connect(hw,engine)

	#Connect Zynthian_gui and Zynthian_rencoder to engines
	for engine in engines:
		if len(zyngui_out)>0:
			jack_connect(zyngui_out[0],engine)
		if len(zyncoder_out)>0:
			jack_connect(zyncoder_out[0],engine)

#------------------------------------------------------------------------------

#Sequencer Config?
if os.environ.get('ZYNTHIAN_SEQ') or (len(sys.argv)>1 and sys.argv[1]=='seq'):
	zynthian_seq=True
else:
	zynthian_seq=False

jclient=jack.Client("Zynthian_autoconnect")

#Main loop
while True:
	try:
		midi_autoconnect()
	except Exception as err:
		print("ERROR Autoconnecting: "+str(err))
		pass
	sleep(refresh_time)

#------------------------------------------------------------------------------
