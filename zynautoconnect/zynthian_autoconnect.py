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
from collections import OrderedDict

# Zynthian specific modules
from zyngui import zynthian_gui_config

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
	"Pianoteq60",
	"Pianoteq61",
	"Pianoteq62",
	"Pure Data",
	"mod-host"
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

def get_port_alias_id(midi_port):
	try:
		alias_id='_'.join(midi_port.aliases[0].split('-')[5:])
	except:
		alias_id=midi_port.name
	return alias_id

#------------------------------------------------------------------------------

def midi_autoconnect():
	logger.info("Autoconnecting Midi ...")

	#------------------------------------
	# Get Input/Output MIDI Ports: 
	#  - outputs are inputs for jack
	#  - inputs are outputs for jack
	#------------------------------------

	#Get Physical MIDI input ports ...
	hw_out=jclient.get_ports(is_output=True, is_physical=True, is_midi=True)
	if len(hw_out)==0:
		hw_out=[]

	#Get Physical MIDI output ports ...
	hw_in=jclient.get_ports(is_input=True, is_physical=True, is_midi=True)
	if len(hw_in)==0:
		hw_in=[]

	#Add Aubio MIDI input port ...
	if zynthian_aubionotes:
		aubio_out=jclient.get_ports("aubio", is_output=True, is_physical=False, is_midi=True)
		try:
			hw_out.append(aubio_out[0])
		except:
			pass
	#Add TouchOSC input ports ...
	if zynthian_touchosc:
		rtmidi_out=jclient.get_ports("RtMidiOut Client", is_output=True, is_physical=False, is_midi=True)
		for port in rtmidi_out:
			try:
				hw_out.append(port)
			except:
				pass                    

	#logger.debug("Input Device Ports: {}".format(hw_out))
	#logger.debug("Output Device Ports: {}".format(hw_in))

	#Get Network (qmidinet) MIDI input/output ports ...
	qmidinet_out=jclient.get_ports("QmidiNet", is_output=True, is_physical=False, is_midi=True)
	qmidinet_in=jclient.get_ports("QmidiNet", is_input=True, is_physical=False, is_midi=True)

	#logger.debug("QMidiNet Input Port: {}".format(qmidinet_out))
	#logger.debug("QMidiNet Output Port: {}".format(qmidinet_in))

	#Get Synth Engines MIDI output ports
	engines_in=[]
	for engine_name in engine_list:
		#logger.debug("engine: "+engine)
		ports=jclient.get_ports(engine_name, is_input=True, is_midi=True, is_physical=False)
		try:
			port=ports[0]
			if port.shortname=='osc':
				port=ports[1]
			#logger.debug("Engine {}:{} found".format(engine_name,port.short_name))
			engines_in.append(port)
		except:
			#logger.warning("Engine {} is not present".format(engine_name))
			pass

	#logger.debug("Synth Engine Ports: {}".format(engines_in))

	#Get Zynthian Midi Router MIDI ports
	zmr_out=OrderedDict()
	for p in jclient.get_ports("ZynMidiRouter", is_output=True, is_midi=True):
		zmr_out[p.shortname]=p
	zmr_in=OrderedDict()
	for p in jclient.get_ports("ZynMidiRouter", is_input=True, is_midi=True):
		zmr_in[p.shortname]=p

	#logger.debug("ZynMidiRouter Input Ports: {}".format(zmr_out))
	#logger.debug("ZynMidiRouter Output Ports: {}".format(zmr_in))

	#------------------------------------
	# Auto-Connect MIDI Ports
	#------------------------------------

	#Connect "Not Disabled" Input Device Ports to ZynMidiRouter:main_in
	for hw in hw_out:
		#logger.debug("Connecting MIDI Input {} => {}".format(hw,zmr_in['main_in'])
		try:
			if get_port_alias_id(hw) in zynthian_gui_config.disabled_midi_in_ports:
				jclient.disconnect(hw,zmr_in['main_in'])
			else:
				jclient.connect(hw,zmr_in['main_in'])
		except:
			pass

	#Connect QMidiNet Input Port to ZynMidiRouter:net_in
	try:
		jclient.connect(qmidinet_out[0],zmr_in['net_in'])
	except:
		pass

	#Connect ZynMidiRouter:main_out to engines
	for eip in engines_in:
		try:
			jclient.connect(zmr_out['main_out'],eip)
		except:
			pass

	#Connect ZynMidiRouter:main_out to enabled MIDI-OUT ports
	for hw in hw_in:
		try:
			if get_port_alias_id(hw) in zynthian_gui_config.enabled_midi_out_ports:
				jclient.connect(zmr_out['main_out'],hw)
			else:
				jclient.disconnect(zmr_out['main_out'],hw)
		except:
			pass

	#Connect ZynMidiRouter:net_out to QMidiNet Output Port
	try:
		jclient.connect(zmr_out['net_out'],qmidinet_in[0])
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
				#logger.error("Autoconnecting Engine => {}".format(dev_name))
				#logger.info("Autoconnecting Engine => {}".format(dev_name))
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
			logger.error("ERROR Autoconnecting: {}".format(err))
		sleep(refresh_time)

def start(rt=2):
	global refresh_time, exit_flag, jclient, thread
	refresh_time=rt
	exit_flag=False
	try:
		jclient=jack.Client("Zynthian_autoconnect")
	except Exception as e:
		logger.error("Failed to connect with Jack Server: {}".format(e))
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
