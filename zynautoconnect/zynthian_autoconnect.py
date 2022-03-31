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
from zyncoder.zyncore import get_lib_zyncore
from zyngui import zynthian_gui_config

#-------------------------------------------------------------------------------
# Configure logging
#-------------------------------------------------------------------------------

log_level=int(os.environ.get('ZYNTHIAN_LOG_LEVEL',logging.WARNING))

logger=logging.getLogger(__name__)
logger.setLevel(log_level)

#if log_level==logging.DEBUG:
#	import inspect

#-------------------------------------------------------------------------------
# Define some Constants and Global Variables
#-------------------------------------------------------------------------------

refresh_time = 2
jclient = None
thread = None
exit_flag = False

lib_zyncore = get_lib_zyncore()

last_hw_str = None
max_num_devs = 16
devices_in = [None for i in range(max_num_devs)]

#------------------------------------------------------------------------------

def get_port_alias_id(midi_port):
	try:
		alias_id='_'.join(midi_port.aliases[0].split('-')[5:])
	except:
		alias_id=midi_port.name
	return alias_id


#Dirty hack for having MIDI working with PureData & CSound: #TODO => Improve it!!
def get_fixed_midi_port_name(port_name):
	if port_name=="pure_data":
		port_name = "Pure Data"

	elif port_name=="csound6":
		port_name = "Csound"

	return port_name

#------------------------------------------------------------------------------

def midi_autoconnect(force=False):
	global last_hw_str

	#Get Mutex Lock 
	acquire_lock()

	#logger.info("ZynAutoConnect: MIDI ...")

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


	#Add Aubio MIDI out port ...
	if zynthian_gui_config.midi_aubionotes_enabled:
		aubio_out=jclient.get_ports("aubio", is_output=True, is_physical=False, is_midi=True)
		try:
			hw_out.append(aubio_out[0])
		except:
			pass

	#Add TouchOSC out ports ...
	if zynthian_gui_config.midi_touchosc_enabled:
		rtmidi_out=jclient.get_ports("TouchOSC Bridge", is_output=True, is_physical=False, is_midi=True)
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

	#Check for new devices (HW and virtual)...
	if not force and hw_str==last_hw_str:
		#Release Mutex Lock
		release_lock()
		#logger.info("ZynAutoConnect: MIDI Shortened ...")
		return
	else:
		last_hw_str = hw_str

	#Get Engines list from UI
	zyngine_list=zynthian_gui_config.zyngui.screens["engine"].zyngines

	#Get Engines MIDI input, output & feedback ports:
	engines_in={}
	engines_out=[]
	engines_fb=[]
	for k, zyngine in zyngine_list.items():
		if not zyngine.jackname or zyngine.nickname=="MD":
			continue

		if zyngine.type in ("MIDI Synth", "MIDI Tool", "Special"):
			port_name = get_fixed_midi_port_name(zyngine.jackname)
			#logger.debug("Zyngine Port Name: {}".format(port_name))

			ports = jclient.get_ports(port_name, is_input=True, is_midi=True, is_physical=False)
			try:
				#logger.debug("Engine {}:{} found".format(zyngine.jackname,ports[0].short_name))
				engines_in[zyngine.jackname]=ports[0]
			except:
				#logger.warning("Engine {} is not present".format(zyngine.jackname))
				pass

			ports = jclient.get_ports(port_name, is_output=True, is_midi=True, is_physical=False)
			try:
				#logger.debug("Engine {}:{} found".format(zyngine.jackname,ports[0].short_name))
				if zyngine.type=="MIDI Synth":
					engines_fb.append(ports[0])
				else:
					engines_out.append(ports[0])
			except:
				#logger.warning("Engine {} is not present".format(zyngine.jackname))
				pass

	#logger.debug("Synth Engine Input Ports: {}".format(engines_in))
	#logger.debug("Synth Engine Output Ports: {}".format(engines_out))
	#logger.debug("Synth Engine Feedback Ports: {}".format(engines_fb))

	#Get Zynthian Midi Router MIDI ports
	zmr_out=OrderedDict()
	for p in jclient.get_ports("ZynMidiRouter", is_output=True, is_midi=True):
		zmr_out[p.shortname]=p
	zmr_in=OrderedDict()
	for p in jclient.get_ports("ZynMidiRouter", is_input=True, is_midi=True):
		zmr_in[p.shortname]=p

	#logger.debug("ZynMidiRouter Input Ports: {}".format(zmr_out))
	#logger.debug("ZynMidiRouter Output Ports: {}".format(zmr_in))


	# MIDI-Input-routed ports: engines_in
	routed_in = {}
	for pn, port in engines_in.items():
		routed_in[pn] = [port]
	
	# Add Zynmaster and Network ports
	routed_in.update({
		"MIDI-OUT": ["ZynMaster:midi_in"],
		"NET-OUT": ["QmidiNet:in_1", "jackrtpmidid:rtpmidi_in"]
	})

	# Add enabled Hardware MIDI Output Ports ...
	enabled_hw_ports = {}
	for hw in hw_in:
		try:
			port_alias_id = get_port_alias_id(hw)
			if port_alias_id in zynthian_gui_config.enabled_midi_out_ports:
				enabled_hw_ports[port_alias_id] = hw
				routed_in["MIDI-OUT"].append(hw)
		except:
			pass

	#------------------------------------
	# Auto-Connect MIDI Ports
	#------------------------------------

	#Connect MIDI Input Devices
	for hw in hw_out:
		devnum = None
		port_alias_id = get_port_alias_id(hw)
		#logger.debug("Connecting MIDI Input {} => {}".format(hw,zmr_in['main_in']))
		try:
			#If the device is marked as disabled, disconnect from all dev ports
			if port_alias_id in zynthian_gui_config.disabled_midi_in_ports:
				for i in range(16):
					jclient.disconnect(hw,zmr_in['dev{}_in'.format(i)])
			 #else ...
			else:
				#if the device already is registered, takes the number
				if port_alias_id in devices_in:
					devnum = devices_in.index(port_alias_id)
				#else registers it, taking the first free port
				else:
					for i in range(16):
						if devices_in[i] is None:
							devnum = i
							devices_in[devnum] = port_alias_id
							break
				if devnum is not None:
					jclient.connect(hw,zmr_in['dev{}_in'.format(devnum)])
		except Exception as e:
			#logger.debug("Exception {}".format(e))
			pass

	#logger.debug("Connecting RTP-MIDI & QMidiNet to ZynMidiRouter:net_in ...")

	#Connect RTP-MIDI output to ZynMidiRouter:net_in
	if zynthian_gui_config.midi_rtpmidi_enabled:
		try:
			jclient.connect("jackrtpmidid:rtpmidi_out", zmr_in['net_in'])
		except:
			pass

	#Connect QMidiNet output to ZynMidiRouter:net_in
	if zynthian_gui_config.midi_network_enabled:
		try:
			jclient.connect("QmidiNet:out_1",zmr_in['net_in'])
		except:
			pass

	#Connect ZynthStep output to ZynMidiRouter:step_in
	try:
		jclient.connect("zynthstep:output", zmr_in['step_in'])
	except:
		pass

	#Connect zynsmf output to ZynMidiRouter:seq_in
	try:
		jclient.connect("zynsmf:midi_out", zmr_in['seq_in'])
	except:
		pass

	#Connect ZynMidiRouter:main_out to zynsmf input
	try:
		jclient.connect(zmr_out['main_out'], "zynsmf:midi_in")
	except:
		pass

	#Connect Engine's Controller-FeedBack to ZynMidiRouter:ctrl_in
	try:
		for efbp in engines_fb:
			jclient.connect(efbp,zmr_in['ctrl_in'])
	except:
		pass

	#logger.debug("Connecting ZynMidiRouter to engines ...")

	#Get layers list from UI
	layers_list=zynthian_gui_config.zyngui.screens["layer"].layers

	#Connect MIDI chain elements
	for i, layer in enumerate(layers_list):
		if layer.get_midi_jackname() and layer.engine.type in ("MIDI Tool", "Special"):
			sport_name = get_fixed_midi_port_name(layer.get_midi_jackname())
			sports=jclient.get_ports(sport_name, is_output=True, is_midi=True, is_physical=False)
			if sports:
				#Connect to assigned ports and disconnect from the rest ...
				for mi,dports in routed_in.items():
					#logger.debug(" => Probing {} => {}".format(sport_name, mi))
					if mi in layer.get_midi_out():
						for dport in dports:
							#logger.debug(" => Connecting {} => {}".format(sport_name, mi))
							try:
								jclient.connect(sports[0],dport)
							except:
								pass
							try:
								jclient.disconnect(zmr_out['ch{}_out'.format(layer.midi_chan)], dport)
							except:
								pass
					else:
						for dport in dports:
							try:
								jclient.disconnect(sports[0], dport)
							except:
								pass


	#Connect ZynMidiRouter to MIDI-chain roots
	midichain_roots = zynthian_gui_config.zyngui.screens["layer"].get_midichain_roots()

	# => Get Root-engines info
	root_engine_info = {}
	for mcrl in midichain_roots:
		for mcprl in zynthian_gui_config.zyngui.screens["layer"].get_midichain_pars(mcrl):
			if mcprl.get_midi_jackname():
				jackname = mcprl.get_midi_jackname()
				if jackname in root_engine_info:
					root_engine_info[jackname]['chans'].append(mcprl.midi_chan)
				else:
					port_name = get_fixed_midi_port_name(jackname)
					ports=jclient.get_ports(port_name, is_input=True, is_midi=True, is_physical=False)
					if ports:
						root_engine_info[jackname] = {
							'port': ports[0],
							'chans': [mcprl.midi_chan]
						}

	for jn, info in root_engine_info.items():
		#logger.debug("MIDI ROOT ENGINE INFO: {} => {}".format(jn, info))
		if None in info['chans']:
			try:
				jclient.connect(zmr_out['main_out'], info['port'])
			except:
				pass
		else:
			for ch in range(0,16):
				try:
					if ch in info['chans']:
						jclient.connect(zmr_out['ch{}_out'.format(ch)], info['port'])
					else:
						jclient.disconnect(zmr_out['ch{}_out'.format(ch)], info['port'])
				except:
					pass

	# Set "Drop Program Change" flag for each MIDI chan
	for layer in zynthian_gui_config.zyngui.screens["layer"].root_layers:
		if layer.midi_chan is not None:
			lib_zyncore.zmop_chain_set_flag_droppc(layer.midi_chan, int(layer.engine.options['drop_pc']))


	if zynthian_gui_config.midi_filter_output:
		
		#Connect ZynMidiRouter:midi_out to enabled Hardware MIDI Output Ports
		for paid,hwport in enabled_hw_ports.items():
			try:
				jclient.connect(zmr_out['midi_out'],hwport)
			except:
				pass

		#Connect ZynMidiRouter:midi_out to ZynMaster:midi_in
		try:
			jclient.connect(zmr_out['midi_out'],"ZynMaster:midi_in")
		except:
			pass

		#Connect ZynMidiRouter:net_out to QMidiNet input
		if zynthian_gui_config.midi_network_enabled:
			try:
				jclient.connect(zmr_out['net_out'],"QmidiNet:in_1")
			except:
				pass
		#Connect ZynMidiRouter:net_out to RTP-MIDI input
		if zynthian_gui_config.midi_rtpmidi_enabled:
			try:
				jclient.connect(zmr_out['net_out'],"jackrtpmidid:rtpmidi_in")
			except:
				pass
	else:
		#Connect ZynMidiRouter:midi_out to enabled Hardware MIDI Output Ports
		for paid,hwport in enabled_hw_ports.items():
			try:
				jclient.disconnect(zmr_out['midi_out'],hwport)
			except:
				pass

		#Disconnect ZynMidiRouter:midi_out from ZynMaster:midi_in
		try:
			jclient.disconnect(zmr_out['midi_out'],"ZynMaster:midi_in")
		except:
			pass
		#Disconnect ZynMidiRouter:net_out from QMidiNet input
		if zynthian_gui_config.midi_network_enabled:
			try:
				jclient.disconnect(zmr_out['net_out'],"QmidiNet:in_1")
			except:
				pass
		#Disconnect ZynMidiRouter:net_out from RTP-MIDI input
		if zynthian_gui_config.midi_rtpmidi_enabled:
			try:
				jclient.disconnect(zmr_out['net_out'],"jackrtpmidid:rtpmidi_in")
			except:
				pass

	#Connect ZynMidiRouter:step_out to ZynthStep input
	try:
		jclient.connect(zmr_out['step_out'], "zynthstep:input")
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
		#logger.debug("ZynAutoConnect: Audio Escaped ...")
		return

	#Get Mutex Lock 
	acquire_lock()

	#logger.info("ZynAutoConnect: Audio ...")

	#Get Audio Input Ports (ports receiving audio => inputs => you write on it!!)
	input_ports=get_audio_input_ports(True)

	#Get System Playback Ports
	playback_ports = get_audio_playback_ports()

	#Disconnect Monitor from System Output
	mon_in=jclient.get_ports("mod-monitor", is_output=True, is_audio=True)
	try:
		jclient.disconnect(mon_in[0],'system:playback_1')
		jclient.disconnect(mon_in[1],'system:playback_2')
	except:
		pass

	#Get layers list from UI
	layers_list=zynthian_gui_config.zyngui.screens["layer"].layers

	#Connect Synth Engines to assigned outputs
	for layer_index, layer in enumerate(layers_list):
		if not layer.get_audio_jackname() or layer.engine.type=="MIDI Tool":
			continue

		layer_playback = [jn for jn in layer.get_audio_out() if jn.startswith("zynmixer:input_") or jn.startswith("system:playback_")]
		nlpb = len(layer_playback)
		
		ports=jclient.get_ports(layer.get_audio_jackname(), is_output=True, is_audio=True, is_physical=False)
		if len(ports)>0:
			#logger.debug("Connecting Layer {} ...".format(layer.get_jackname()))
			np = len(ports)
			#logger.debug("Num of {} Audio Ports: {}".format(layer.get_jackname(), np))

			#Connect layer to routed playback ports and disconnect from the rest ...
			if len(playback_ports)>0:
				npb = min(nlpb,len(ports))
				for j, pbp in enumerate(playback_ports):
					if pbp.name in layer_playback:
						for k, lop in enumerate(ports):
							if k%npb==j%npb:
								#logger.debug("Connecting {} to {} ...".format(lop.name, pbp.name))
								try:
									jclient.connect(lop, pbp)
								except:
									pass
							else:
								#logger.debug("Disconnecting {} from {} ...".format(lop.name, pbp.name))
								try:
									jclient.disconnect(lop, pbp)
								except:
									pass
					else:
						for lop in ports:
							#logger.debug("Disconnecting {} from {} ...".format(lop.name, pbp.name))
							try:
								jclient.disconnect(lop, pbp)
							except:
								pass

			#Connect to routed layer input ports and disconnect from the rest ...
			for ao in input_ports:
				nip = len(input_ports[ao])
				jrange = list(range(max(np, nip)))
				if ao in layer.get_audio_out():
					#logger.debug("Connecting to {} : {}".format(ao,jrange))
					for j in jrange:
						try:
							psrc = ports[j%np]
							pdest = input_ports[ao][j%nip]
							#logger.debug("   ... {} => {}".format(psrc.name, pdest.name))
							jclient.connect(psrc, pdest)
						except:
							pass
				else:
					#logger.debug("Disconnecting from {} : {}".format(ao,jrange))
					for j in jrange:
						try:
							psrc = ports[j%np]
							pdest = input_ports[ao][j%nip]
							#logger.debug("   ... {} => {}".format(psrc.name, pdest.name))
							jclient.disconnect(psrc, pdest)
						except:
							pass

		#Connect MIDI-Input on Audio-FXs, if it exist ... (i.e. x42 AutoTune)
		if layer.engine.type=="Audio Effect":
			midi_ports=jclient.get_ports(layer.get_midi_jackname(), is_input=True, is_midi=True, is_physical=False)
			if len(midi_ports)>0:
				try:
					jclient.connect("ZynMidiRouter:ch{}_out".format(layer.midi_chan), midi_ports[0])
				except:
					pass


	# Connect mixer to main output
	try:
		jclient.connect("zynmixer:output_a", "system:playback_1")
		jclient.connect("zynmixer:output_b", "system:playback_2")
	except:
		pass
	# Connect mixer to headphones
	try:
		jclient.connect("zynmixer:output_a", "Headphones:playback_1")
		jclient.connect("zynmixer:output_b", "Headphones:playback_2")
	except:
		pass

	# Connect mixer to dpm
	if not zynthian_gui_config.show_cpu_status:
		try:
			jclient.connect("zynmixer:output_a", "jackpeak:input_a")
			jclient.connect("zynmixer:output_b", "jackpeak:input_b")
		except:
			pass

	#Get System Capture ports => jack output ports!!
	capture_ports = get_audio_capture_ports()
	if len(capture_ports)>0:

		root_layers = zynthian_gui_config.zyngui.screens["layer"].get_fxchain_roots()
		#Connect system capture ports to FX-layers root ...
		for rl in root_layers:
			if not rl.get_audio_jackname() or layer.engine.type!="Audio Effect":
				continue

			# Connect to FX-layers roots and their "pars" (parallel layers)
			for rlp in zynthian_gui_config.zyngui.screens["layer"].get_fxchain_pars(rl):
				#Get Root Layer Input ports ...
				rlp_in = jclient.get_ports(rlp.get_audio_jackname(), is_input=True, is_audio=True)
				if len(rlp_in)>0:
					nsc = min(len(rlp.get_audio_in()),len(rlp_in))
		
					#Connect System Capture to Root Layer ports
					for j, scp in enumerate(capture_ports):
						if scp.name in rlp.get_audio_in():
							for k, rlp_inp in enumerate(rlp_in):
								if k%nsc==j%nsc:
									#logger.debug("Connecting {} to {} ...".format(scp.name, layer.get_audio_jackname()))
									try:
										jclient.connect(scp, rlp_inp)
									except:
										pass
								else:
									try:
										jclient.disconnect(scp, rlp_inp)
									except:
										pass
								# Limit to 2 input ports 
								#if k>=1:
								#	break

						else:
							for rlp_inp in rlp_in:
								try:
									jclient.disconnect(scp, rlp_inp)
								except:
									pass

		if zynthian_gui_config.midi_aubionotes_enabled:
			#Get Aubio Input ports ...
			aubio_in = jclient.get_ports("aubio", is_input=True, is_audio=True)
			if len(aubio_in)>0:
				nip = len(aubio_in)
				#Connect System Capture to Aubio ports
				j=0
				for scp in capture_ports:
					try:
						jclient.connect(scp, aubio_in[j%nip])
					except:
						pass
					j += 1

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


def get_audio_capture_ports():
	return jclient.get_ports("system", is_output=True, is_audio=True, is_physical=True)


def get_audio_playback_ports():
	ports = jclient.get_ports("zynmixer", is_input=True, is_audio=True, is_physical=False)
	return ports + jclient.get_ports("system", is_input=True, is_audio=True, is_physical=True)


def get_audio_input_ports(exclude_system_playback=False):
	res=OrderedDict()
	try:
		for aip in jclient.get_ports(is_input=True, is_audio=True, is_physical=False):
			parts=aip.name.split(':')
			client_name=parts[0]
			if client_name in ["jack_capture","jackpeak","Headphones"] or client_name[:7]=="effect_":
				continue
			if client_name=="system" or client_name=="zynmixer":
				if exclude_system_playback:
					continue
				else:
					client_name = aip.name
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
	#if log_level==logging.DEBUG:
	#	calframe = inspect.getouterframes(inspect.currentframe(), 2)
	#	logger.debug("Waiting for lock, requested from '{}'...".format(format(calframe[1][3])))
	lock.acquire()
	#logger.debug("... lock acquired!!")



def release_lock():
	#if log_level==logging.DEBUG:
	#	calframe = inspect.getouterframes(inspect.currentframe(), 2)
	#	logger.debug("Lock released from '{}'".format(calframe[1][3]))
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
	lock=Lock()

	# Start Autoconnect Thread
	thread=Thread(target=autoconnect_thread, args=())
	thread.daemon = True # thread dies with the program
	thread.name = "autoconnect"
	thread.start()


def stop():
	global exit_flag
	exit_flag=True
	acquire_lock()
	audio_disconnect_sysout()
	release_lock()
	jclient.deactivate()


def is_running():
	global thread
	return thread.is_alive()


def cb_jack_xrun(delayed_usecs: float):
	logger.warning("Jack Audio XRUN!")
	zynthian_gui_config.zyngui.status_info['xrun'] = True


def get_jackd_cpu_load():
	return jclient.cpu_load()


def get_jackd_samplerate():
	return jclient.samplerate


def get_jackd_blocksize():
	return jclient.blocksize





#------------------------------------------------------------------------------
