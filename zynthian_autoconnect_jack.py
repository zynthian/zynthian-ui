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
	"Carla"
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
	print("Autoconnecting Jack Midi ...")

	#Get Physical MIDI-devices ...
	hw_out=jclient.get_ports(is_output=True, is_physical=True, is_midi=True)
	if len(hw_out)==0:
		hw_out=[]
	#Add ttymidi device ...
	tty_out=jclient.get_ports("ttymidi", is_output=True, is_physical=False, is_midi=True)
	try:
		hw_out.append(tty_out[0])
	except:
		pass
	#Add aubio device ...
	if zynthian_aubio:
		aubio_out=jclient.get_ports("aubio", is_output=True, is_physical=False, is_midi=True)
		try:
			hw_out.append(aubio_out[0])
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

	#Get Zynthian Controller device
	zyncoder_out=jclient.get_ports("Zyncoder", is_output=True, is_midi=True)
	zyncoder_in=jclient.get_ports("Zyncoder", is_input=True, is_midi=True)

	#Connect Physical devices to Synth Engines and Zyncoder
	for hw in hw_out:
		#print("Connecting HW "+str(hw))
		if len(zyncoder_in)>0:
			jack_connect(hw,zyncoder_in[0])
		if not zynthian_seq:
			for engine in engines:
				#print("Connecting HW "+str(hw)+" => "+str(engine))
				jack_connect(hw,engine)

	#Connect Zyncoder to engines
	if len(zyncoder_out)>0:
		for engine in engines:
			jack_connect(zyncoder_out[0],engine)

def audio_autoconnect():
	print("Autoconnecting Jack Audio ...")

	if zynthian_aubio:
		#Get Alsa Input ...
		alsa_rec=jclient.get_ports("alsa_in", is_output=True, is_audio=True)
		aubio_in=jclient.get_ports("aubio", is_input=True, is_audio=True)
		if len(alsa_rec)>0 and len(aubio_in)>0:
			try:
				jack_connect(alsa_rec[0],aubio_in[0])
			except:
				print("Failed capture audio connection")

	#Get System Output ...
	sys_out=jclient.get_ports(is_audio=True, is_terminal=True)
	if len(sys_out)==0:
		return

	#Connect Synth Engines to System Output
	for engine in engine_list:
		devs=jclient.get_ports(engine, is_output=True, is_audio=True, is_physical=False)
		if devs:
			try:
				jack_connect(devs[0],sys_out[0])
				jack_connect(devs[1],sys_out[1])
			except:
				print("Failed output audio connection")

#------------------------------------------------------------------------------

#Sequencer Config?
if os.environ.get('ZYNTHIAN_SEQ') or (len(sys.argv)>1 and sys.argv[1]=='seq'):
	zynthian_seq=True
else:
	zynthian_seq=False

#Aubio Config?
if os.environ.get('ZYNTHIAN_AUBIO') or (len(sys.argv)>1 and sys.argv[1]=='aubio'):
	zynthian_aubio=True
else:
	zynthian_aubio=False


jclient=jack.Client("Zynthian_autoconnect")

#Main loop
while True:
	try:
		midi_autoconnect()
		audio_autoconnect()
	except Exception as err:
		print("ERROR Autoconnecting: "+str(err))
		pass
	sleep(refresh_time)

#------------------------------------------------------------------------------
