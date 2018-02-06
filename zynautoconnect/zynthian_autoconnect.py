# -*- coding: utf-8 -*-
#********************************************************************
# ZYNTHIAN PROJECT: Zynthian Autoconnector
# 
# Autoconnect Jack clients
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
import copy
import logging
from time import sleep
from threading  import Thread

#-------------------------------------------------------------------------------
# Configure logging
#-------------------------------------------------------------------------------

logger=logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

#-------------------------------------------------------------------------------
# Define some Constants and Global Variables
#-------------------------------------------------------------------------------

#Synth Engine List
engine_list = [
	"zynaddsubfx",
	"fluidsynth",
	"LinuxSampler",
	"setBfree",
	"Pianoteq60"
	#"mod-host"
]

#Input Black List
hw_black_list = [
	#"Midi Through"
]

#List of monitored engines
monitored_engines = []

refresh_time=2
jclient=None
thread=None
exit_flag=False

#Aubio Config?
if os.environ.get('ZYNTHIAN_AUBIONOTES'):
	zynthian_aubionotes=True
else:
	zynthian_aubionotes=False


#TouchOSC Config?
if os.environ.get('ZYNTHIAN_TOUCHOSC'):
	zynthian_touchosc=True
else:
	zynthian_touchosc=False

#------------------------------------------------------------------------------

def midi_autoconnect():
	logger.info("Autoconnecting Midi ...")

	#Get Physical MIDI-devices ...
	hw_out=jclient.get_ports(is_output=True, is_physical=True, is_midi=True)
	if len(hw_out)==0:
		hw_out=[]
	#Add MIDI-IN (ttymidi) device ...
	ttymidi_out=jclient.get_ports("ttymidi", is_output=True, is_physical=False, is_midi=True)
	try:
		hw_out.append(ttymidi_out[0])
	except:
		pass
	#Add aubio device ...
	if zynthian_aubionotes:
		aubio_out=jclient.get_ports("aubio", is_output=True, is_physical=False, is_midi=True)
		try:
			hw_out.append(aubio_out[0])
		except:
			pass
	#Add TouchOSC devices ...
	if zynthian_touchosc:
		rtmidi_out=jclient.get_ports("RtMidiOut Client", is_output=True, is_physical=False, is_midi=True)
		for port in rtmidi_out:
			try:
				hw_out.append(port)
			except:
				pass                    

	#Remove HW Black-listed
	for i,hw in enumerate(hw_out):
		for v in hw_black_list:
			#logger.debug("Element %s => %s " % (i,v) )
			if v==str(hw.name.split(':')[0]):
				hw_out.pop(i)

	#logger.debug("Physical Devices: " + str(hw_out))

	#Get Synth Engines
	engines=[]
	for engine in engine_list:
		#logger.debug("engine: "+engine)
		devs=jclient.get_ports(engine, is_input=True, is_midi=True, is_physical=False)
		try:
			dev=devs[0]
			if dev.shortname=='osc':
				dev=devs[1]
			#logger.debug("Engine "+str(dev)+" found")
			engines.append(dev)
		except:
			#logger.warning("Engine "+str(devs[0])+" is not present")
			pass

	#logger.debug("Engine Devices: " + str(engines))

	#Get Zynthian Controller device
	zyncoder_out=jclient.get_ports("Zyncoder", is_output=True, is_midi=True)
	zyncoder_in=jclient.get_ports("Zyncoder", is_input=True, is_midi=True)

	#Connect Physical devices to Synth Engines and Zyncoder
	for hw in hw_out:
		if len(zyncoder_in)>0:
			#logger.debug("Connecting HW "+str(hw)+" => "+str(zyncoder_in[0]))
			try:
				jclient.connect(hw,zyncoder_in[0])
			except:
				pass

			# This is not needed anymore because zyncoder forward all the MIDI messages
			'''
			for engine in engines:
				#logger.debug("Connecting HW "+str(hw)+" => "+str(engine))
				try:
					jclient.connect(hw,engine)
				except:
					pass
			'''

	#Connect Zyncoder to engines
	if len(zyncoder_out)>0:
		for engine in engines:
			try:
				jclient.connect(zyncoder_out[0],engine)
			except:
				pass

		#Connect Zyncoder to MIDI-OUT (ttymidi)
		ttymidi_in=jclient.get_ports("ttymidi", is_input=True, is_physical=False, is_midi=True)
		try:
			jclient.connect(zyncoder_out[0],ttymidi_in[0])
		except:
			pass


def audio_autoconnect():
	logger.info("Autoconnecting Audio ...")

	#Get System Output ...
	#sys_out=jclient.get_ports(is_audio=True, is_terminal=True)
	sys_out=jclient.get_ports(is_input=True, is_audio=True, is_physical=True)

	#Get Monitor Output & Input ...
	mon_out=jclient.get_ports("mod-monitor", is_input=True, is_audio=True)
	mon_in=jclient.get_ports("mod-monitor", is_output=True, is_audio=True)

	if len(sys_out)>0:
		#Disconnect Monitor from System Output
		if len(mon_out)>0:
			try:
				jclient.disconnect(mon_in[0],sys_out[0])
				jclient.disconnect(mon_in[1],sys_out[1])
			except:
				pass

		#Connect Synth Engines to System Output
		for engine in engine_list:
			devs=jclient.get_ports(engine, is_output=True, is_audio=True, is_physical=False)
			if devs:
				dev_name=str(devs[0].name).split(':')[0]
				#logger.error("Autoconnecting Engine => %s" % dev_name)
				#logger.info("Autoconnecting Engine => %s" % dev_name)
				if len(mon_out)>0 and dev_name.lower() in monitored_engines:
					try:
						jclient.connect(devs[0],mon_out[0])
						jclient.connect(devs[1],mon_out[1])
					except:
						pass
					try:
						jclient.disconnect(devs[0],sys_out[0])
						jclient.disconnect(devs[1],sys_out[1])
					except:
						pass
				else:
					try:
						jclient.connect(devs[0],sys_out[0])
						jclient.connect(devs[1],sys_out[1])
					except:
						pass
					if len(mon_out)>0:
						try:
							jclient.disconnect(devs[0],mon_out[0])
							jclient.disconnect(devs[1],mon_out[1])
						except:
							pass

	if zynthian_aubionotes:
		#Get System Capture and Aubio Input ports ...
		sys_input=jclient.get_ports(is_output=True, is_audio=True, is_physical=True)
		aubio_in=jclient.get_ports("aubio", is_input=True, is_audio=True)
		#Connect System Capture to Aubio ports
		if len(sys_input)>0 and len(aubio_in)>0:
			try:
				jclient.connect(sys_input[0],aubio_in[0])
				jclient.connect(sys_input[1],aubio_in[0])
			except:
				pass

def autoconnect():
	midi_autoconnect()
	audio_autoconnect()

def autoconnect_thread():
	while not exit_flag:
		try:
			autoconnect()
		except Exception as err:
			logger.error("ERROR Autoconnecting: "+str(err))
		sleep(refresh_time)

def start(rt=2):
	global refresh_time, exit_flag, jclient, thread
	refresh_time=rt
	exit_flag=False
	try:
		jclient=jack.Client("Zynthian_autoconnect")
	except Exception as e:
		logger.error("Failed to connect with Jack Server: %s" % (str(e)))
	thread=Thread(target=autoconnect_thread, args=())
	thread.daemon = True # thread dies with the program
	thread.start()

def stop():
	global exit_flag
	exit_flag=True

# Monitored Engines Stuff

def reset_monitored_engines():
	monitored_engines.clear()

def set_monitored_engines(engines):
	monitored_engines.clear()
	for eng in engines:
		monitored_engines.append(eng.lower())

def set_monitored_engine(engine):
	engine=engine.lower()
	if engine not in monitored_engines:
		monitored_engines.append(engine)

def unset_monitored_engine(engine):
	engine=engine.lower()
	if engine in monitored_engines:
		monitored_engines.remove(engine)

def is_monitored_engine(engine):
	engine=engine.lower()
	if engine in monitored_engines:
		return True
	else:
		return False

#------------------------------------------------------------------------------
