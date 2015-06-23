#!/usr/bin/python
#------------------------------------------------------------------------------
# midi_autoconnect.py: Daemon-script that autoconnect midi devices.
#                      It connects every input to every ouput.
#------------------------------------------------------------------------------
# Author: Jose Fernando Moyano Dominguez (ZauBeR) 
# Email:  fernando@zauber.es
# Web:    http://zauber.es
# Date:   2015-02-22
#------------------------------------------------------------------------------
# This Software is free. Do whatever you want with it! ;-)
#------------------------------------------------------------------------------

from subprocess import check_output
from re import findall
from time import sleep

#------------------------------------------------------------------------------

#Refresh time
refresh_time = 2

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
					if (oc[1]=='ZynAddSubFX'):
						command="aconnect "+ic[0]+":1 "+oc[0]
				elif (ic[1]=='Zynthian_rencoder'):
					if (oc[1]=='ZynAddSubFX'):
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
