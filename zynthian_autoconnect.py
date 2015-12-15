#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Zynthian Tools > midi_autoconnect.py

Daemon-script that autoconnect midi devices.
It connects every input to every ouput.

author: José Fernandom Moyano (ZauBeR)
email: fernando@zauber.es
created: 2015-02-22
modified:  2015-07-11
"""

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
