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

from subprocess import check_output
from re import findall
from time import sleep

#------------------------------------------------------------------------------

#Refresh time
refresh_time = 2

#Synth Engine List
synth_engine_list = (
	"ZynAddSubFX",
	"FluidSynth"
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
			if (int(ic[0])>0 and int(oc[0])>0 and int(ic[0])!=14 and int(oc[0])!=14 and ic[0]!=oc[0]):
				command=""
				if (ic[1]=='Zynthian_gui'):
					if (oc[1] in synth_engine_list):
						command="aconnect "+ic[0]+":1 "+oc[0]
				elif (ic[1]=='Zynthian_rencoder'):
					if (oc[1] in synth_engine_list):
						command="aconnect "+ic[0]+" "+oc[0]
				elif (ic[1]=='PCR'):
					command="aconnect "+ic[0]+":1 "+oc[0]
				else:
					command="aconnect "+ic[0]+" "+oc[0]

				if (command):
					try:
						print "Connecting " + ic[0] + " to " + oc[0] + " => " + command
						check_output(command, shell=True)
					except:
						pass

	return

#------------------------------------------------------------------------------

#Main loop
while True:
	try:
		midi_autoconnect()
	except:
		pass
	sleep(refresh_time)

#------------------------------------------------------------------------------
