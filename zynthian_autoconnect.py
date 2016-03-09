#!/usr/bin/python
# -*- coding: utf-8 -*-
#********************************************************************
# ZYNTHIAN PROJECT: Zynthian Autoconnector for Alsa Audio System
# 
# Autoconnect Alsa-MIDI devices
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
import os
import sys
from re import findall
from time import sleep
from subprocess import check_output

#------------------------------------------------------------------------------

#Refresh time
refresh_time = 2

#Synth Engine List
synth_engine_list = (
	"ZynAddSubFX",
	"FluidSynth",
	"LinuxSampler",
	"setBfree"
)

#------------------------------------------------------------------------------

def midi_autoconnect():
	#Get Midi Devices from aconnect
	midi_inputs=check_output("aconnect -li", shell=True)
	midi_outputs=check_output("aconnect -lo", shell=True)

	#Parse Alsa Midi Client Numbers
	input_clients = findall("client ([\d]+): '([^']+)'", midi_inputs)
	output_clients = findall("client ([\d]+): '([^']+)'", midi_outputs)

	#Connect every input to every output
	for ic in input_clients:
		for oc in output_clients:
			if int(ic[0])>0 and int(oc[0])>0 and int(ic[0])!=14 and int(oc[0])!=14 and ic[0]!=oc[0]:
				command=""
				if ic[1]=='Zynthian_gui':
					if oc[1] in synth_engine_list:
						command="aconnect "+ic[0]+":1 "+oc[0]
				elif ic[1]=='Zynthian_rencoder':
					if oc[1] in synth_engine_list:
						command="aconnect "+ic[0]+" "+oc[0]
				elif ic[1]=='ttymidi':
					if oc[1] in synth_engine_list or oc[1]=='Zynthian_gui':
						command="aconnect "+ic[0]+" "+oc[0]
				elif ic[1]=='PCR':
					if oc[1] in synth_engine_list:
						command="aconnect "+ic[0]+":1 "+oc[0]
				elif oc[1]!="ttymidi":
					if (not zynthian_seq and oc[1] in synth_engine_list) or oc[1]=='Zynthian_gui':
						command="aconnect "+ic[0]+" "+oc[0]
				if command:
					try:
						print "Connecting " + ic[0] + " to " + oc[0] + " => " + command
						check_output(command, shell=True)
					except:
						pass

	return

#------------------------------------------------------------------------------

#Sequencer Config?
if os.environ.get('ZYNTHIAN_SEQ') or (len(sys.argv)>1 and sys.argv[1]=='seq'):
	zynthian_seq=True
else:
	zynthian_seq=False

#Load midi_snd_seq Driver
#command="modprobe snd-seq-midi"
#check_output(command, shell=True)

#Main loop
while True:
	try:
		midi_autoconnect()
	except:
		pass
	sleep(refresh_time)

#------------------------------------------------------------------------------
