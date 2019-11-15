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
from threading  import Thread, Lock
from collections import OrderedDict

# Zynthian specific modules
from zyngui import zynthian_gui_config

#-------------------------------------------------------------------------------
# Configure logging
#-------------------------------------------------------------------------------

logger=logging.getLogger(__name__)
logger.setLevel(logging.ERROR)
#logger.setLevel(logging.DEBUG)

#-------------------------------------------------------------------------------
# Define some Constants and Global Variables
#-------------------------------------------------------------------------------

refresh_time = 2
jclient = None
thread = None
exit_flag = False

last_hw_str = None

#------------------------------------------------------------------------------

def get_port_alias_id(midi_port):
	try:
		alias_id='_'.join(midi_port.aliases[0].split('-')[5:])
	except:
		alias_id=midi_port.name
	return alias_id

#------------------------------------------------------------------------------

def midi_autoconnect(force=False):
	global last_hw_str

	#Get Mutex Lock 
	acquire_lock()

	logger.info("ZynAutoConnect: MIDI ...")

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
	if zynthian_gui_config.midi_aubionotes_enabled:
		aubio_out=jclient.get_ports("aubio", is_output=True, is_physical=False, is_midi=True)
		try:
			hw_out.append(aubio_out[0])
		except:
			pass

	#Add TouchOSC input ports ...
	if zynthian_gui_config.midi_touchosc_enabled:
		rtmidi_out=jclient.get_ports("RtMidiOut Client", is_output=True, is_physical=False, is_midi=True)
		for port in rtmidi_out:
			try:
				hw_out.append(port)
			except:
				pass                    

	#logger.debug("Input Device Ports: {}".format(hw_out))
	#logger.debug("Output Device Ports: {}".format(hw_in))

	#Calculate device list fingerprint (HW & virtual)
	hw_str=""
	for hw in hw_out:
		hw_str += hw.name + "\n"
	for hw in hw_in:
		hw_str += hw.name + "\n"


	#Get Network (qmidinet) MIDI input/output ports ...
	if zynthian_gui_config.midi_network_enabled:
		try:
			qmidinet_out=jclient.get_ports("QmidiNet", is_output=True, is_physical=False, is_midi=True)
			#logger.debug("QMidiNet Input Port: {}".format(qmidinet_out))
			for qmp in qmidinet_out:
				hw_str += qmp.name + "\n"
		except:
			pass

		try:
			qmidinet_in=jclient.get_ports("QmidiNet", is_input=True, is_physical=False, is_midi=True)
			#logger.debug("QMidiNet Output Port: {}".format(qmidinet_in))
			for qmp in qmidinet_in:
				hw_str += qmp.name + "\n"
		except:
			pass

	#Get Engines list from UI
	zyngine_list=zynthian_gui_config.zyngui.screens["engine"].zyngines

	#Get Engines MIDI input ports
	engines_in=[]
	for k, zyngine in zyngine_list.items():
		#logger.debug("zyngine: {}".format(zyngine.jackname))
		port_name = zyngine.jackname

		#Dirty hack for having MIDI working with PureData: #TODO => Improve it!!
		if port_name=="pure_data_0":
			#force = True
			port_name = "Pure Data"

		#Dirty hack for having MIDI working with CSound: #TODO => Improve it!!
		if port_name=="csound6":
			#force = True
			port_name = "Csound"

		ports = jclient.get_ports(port_name, is_input=True, is_midi=True, is_physical=False)
		try:
			port=ports[0]

			#Dirty hack for zynaddsubfx: #TODO => Improve it!!!
			if port.shortname=='osc':
				port=ports[1]

			#logger.debug("Engine {}:{} found".format(zyngine.jackname,port.short_name))
			#List of tuples => [port, active_channels]
			engines_in.append([port, zyngine.get_active_midi_channels()])
		except:
			#logger.warning("Engine {} is not present".format(zyngine.jackname))
			pass

	#logger.debug("Synth Engine Ports: {}".format(engines_in))

	#Check for new devices (HW and virtual)...
	if not force and hw_str==last_hw_str:
		last_hw_str = hw_str
		#Release Mutex Lock
		release_lock()
		return
	else:
		last_hw_str = hw_str

	#Get Synth Engines MIDI output ports
	engines_out=[]
	for k, zyngine in zyngine_list.items():
		#logger.debug("zyngine: {}".format(zyngine.jackname))
		ports=jclient.get_ports(zyngine.jackname, is_output=True, is_midi=True, is_physical=False)
		try:
			port=ports[0]
			#logger.debug("Engine {}:{} found".format(zyngine.jackname,port.short_name))
			#List of tuples => [port, active_channels]
			engines_out.append([port, zyngine.get_active_midi_channels()])
		except:
			#logger.warning("Engine {} is not present".format(zyngine.jackname))
			pass

	#logger.debug("Synth Engine Ports: {}".format(engines_out))

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

	#Connect Engine's Controller-FeedBack to ZynMidiRouter:ctrl_in
	try:
		for eop in engines_out:
			jclient.connect(eop[0],zmr_in['ctrl_in'])
	except:
		pass

	#Connect ZynMidiRouter to engines
	for eip in engines_in:
		if eip[1] is None:
			try:
				jclient.connect(zmr_out['main_out'],eip[0])
			except:
				pass
			for ch in range(0,16):
				try:
					jclient.disconnect(zmr_out['ch{}_out'.format(ch)],eip[0])
				except:
					pass
		else:
			try:
				jclient.disconnect(zmr_out['main_out'],eip[0])
			except:
				pass
			for ch in range(0,16):
				if ch in eip[1]:
					try:
						jclient.connect(zmr_out['ch{}_out'.format(ch)],eip[0])
					except:
						pass
				else:
					try:
						jclient.disconnect(zmr_out['ch{}_out'.format(ch)],eip[0])
					except:
						pass

	#Connect ZynMidiRouter:main_out to enabled MIDI-OUT ports
	for hw in hw_in:
		try:
			if get_port_alias_id(hw) in zynthian_gui_config.enabled_midi_out_ports:
				jclient.connect(zmr_out['midi_out'],hw)
			else:
				jclient.disconnect(zmr_out['midi_out'],hw)
		except:
			pass

	#Connect ZynMidiRouter:net_out to QMidiNet Output Port
	try:
		jclient.connect(zmr_out['net_out'],qmidinet_in[0])
	except:
		pass

	#Connect ZynMidiRouter:ctrl_out to enabled MIDI-FB ports (MIDI-Controller FeedBack)
	for hw in hw_in:
		try:
			if get_port_alias_id(hw) in zynthian_gui_config.enabled_midi_fb_ports:
				jclient.connect(zmr_out['ctrl_out'],hw)
			else:
				jclient.disconnect(zmr_out['ctrl_out'],hw)
		except:
			pass

	#Release Mutex Lock
	release_lock()


def audio_autoconnect(force=False):

	if not force:
		logger.info("ZynAutoConnect: Escaped for Audio ...")
		return

	#Get Mutex Lock 
	acquire_lock()

	logger.info("ZynAutoConnect: Audio ...")

	#Get Audio Input Ports (ports receiving audio => inputs => you write on it!!)
	input_ports=get_audio_input_ports()

	#Disconnect Monitor from System Output
	mon_in=jclient.get_ports("mod-monitor", is_output=True, is_audio=True)
	try:
		jclient.disconnect(mon_in[0],input_ports['system'][0])
		jclient.disconnect(mon_in[1],input_ports['system'][1])
	except:
		pass

	#Get layers list from UI
	layers_list=zynthian_gui_config.zyngui.screens["layer"].layers

	#Connect Synth Engines to assigned outputs
	for i, layer in enumerate(layers_list):
		ports=jclient.get_ports(layer.get_jackname(), is_output=True, is_audio=True, is_physical=False)
		if ports:
			if len(ports)==1:
				ports.append(ports[0])

			logger.debug("Autoconnecting Engine {} ...".format(layer.get_jackname()))
			
			#Connect to assigned ports and disconnect from the rest ...
			for ao in input_ports:
				if ao in layer.get_audio_out():
					try:
						logger.debug(" => Connecting to {}".format(ao))
						jclient.connect(ports[0],input_ports[ao][0])
						jclient.connect(ports[1],input_ports[ao][1])
					except:
						pass

				else:
					try:
						jclient.disconnect(ports[0],input_ports[ao][0])
						jclient.disconnect(ports[1],input_ports[ao][1])
					except:
						pass

	#Setup dpmeter connections if enabled ...
	if not zynthian_gui_config.show_cpu_status:
		#Prepare for setup dpmeter connections
		dpmeter_out = jclient.get_ports("jackpeak", is_input=True, is_audio=True)
		dpmeter_conports_1=jclient.get_all_connections("jackpeak:input_a")
		dpmeter_conports_2=jclient.get_all_connections("jackpeak:input_b")
		sysout_conports_1 = jclient.get_all_connections("system:playback_1")
		sysout_conports_2 = jclient.get_all_connections("system:playback_2")

		#Disconnect ports from dpmeter (those that are not connected to System Out, if any ...)
		for cp in dpmeter_conports_1:
			if cp not in sysout_conports_1:
				try:
					jclient.disconnect(cp,dpmeter_out[0])
				except:
					pass
		for cp in dpmeter_conports_2:
			if cp not in sysout_conports_2:
				try:
					jclient.disconnect(cp,dpmeter_out[1])
				except:
					pass

		#Connect ports to dpmeter (those currently connected to System Out)
		for cp in sysout_conports_1:
			try:
				jclient.connect(cp,dpmeter_out[0])
			except:
				pass
		for cp in sysout_conports_2:
			try:
				jclient.connect(cp,dpmeter_out[1])
			except:
				pass

	#Get System Capture ports => jack output ports!!
	system_capture=jclient.get_ports(is_output=True, is_audio=True, is_physical=True)
	if len(system_capture)>0:

		#Connect system capture to effect root layers ...
		root_layers=zynthian_gui_config.zyngui.screens["layer"].get_fxchain_roots()
		for rl in root_layers:
			#Get Root Layer Input ports ...
			rl_in=jclient.get_ports(rl.jackname, is_input=True, is_audio=True)
			#Connect System Capture to Root Layer ports
			if len(rl_in)>0:
				try:
					jclient.connect(system_capture[0],rl_in[0])
					jclient.connect(system_capture[1],rl_in[0])
				except:
					pass


		if zynthian_gui_config.midi_aubionotes_enabled:
			#Get Aubio Input ports ...
			aubio_in=jclient.get_ports("aubio", is_input=True, is_audio=True)
			#Connect System Capture to Aubio ports
			if len(aubio_in)>0:
				try:
					jclient.connect(system_capture[0],aubio_in[0])
					jclient.connect(system_capture[1],aubio_in[0])
				except:
					pass

	#Release Mutex Lock
	release_lock()


def audio_disconnect_sysout():
	sysout_ports=jclient.get_ports("system", is_input=True, is_audio=True)
	for sop in sysout_ports:
		conports = jclient.get_all_connections(sop)
		for cp in conports:
			try:
				jclient.disconnect(cp, sop)
			except:
				pass


def get_audio_input_ports():
	res=OrderedDict()
	try:
		for aip in jclient.get_ports(is_input=True, is_audio=True, is_physical=False):
			parts=aip.name.split(':')
			client_name=parts[0]
			if client_name[:7]=="effect_" or client_name=="jack_capture" or client_name=="jackpeak":
				continue
			if client_name not in res:
				res[client_name]=[aip]
				#logger.debug("AUDIO INPUT PORT: {}".format(client_name))
			else:
				res[client_name].append(aip)
	except:
		pass
	return res


def autoconnect(force=False):
	midi_autoconnect(force)
	audio_autoconnect(force)


def autoconnect_thread():
	while not exit_flag:
		try:
			autoconnect()
		except Exception as err:
			logger.error("ZynAutoConnect ERROR: {}".format(err))
		sleep(refresh_time)


def acquire_lock():
	lock.acquire()


def release_lock():
	lock.release()


def start(rt=2):
	global refresh_time, exit_flag, jclient, thread, lock
	refresh_time=rt
	exit_flag=False

	try:
		jclient=jack.Client("Zynthian_autoconnect")
		jclient.set_xrun_callback(cb_jack_xrun)
		jclient.activate()
	except Exception as e:
		logger.error("ZynAutoConnect ERROR: Can't connect with Jack Audio Server ({})".format(e))

	# Create Lock object (Mutex) to avoid concurrence problems
	lock=Lock();

	# Start Autoconnect Thread
	thread=Thread(target=autoconnect_thread, args=())
	thread.daemon = True # thread dies with the program
	thread.start()


def stop():
	global exit_flag
	exit_flag=True
	acquire_lock()
	audio_disconnect_sysout()
	release_lock()


def is_running():
	global thread
	return thread.is_alive()


def cb_jack_xrun(delayed_usecs: float):
	logger.error("Jack Audio XRUN!")
	zynthian_gui_config.zyngui.status_info['xrun'] = True


def get_jack_cpu_load():
	return jclient.cpu_load()


#------------------------------------------------------------------------------
