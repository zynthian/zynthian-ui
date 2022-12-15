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

import os
import jack
import logging
from time import sleep
from threading  import Thread, Lock
from collections import OrderedDict

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore
from zyngui import zynthian_gui_config

#-------------------------------------------------------------------------------
# Configure logging
#-------------------------------------------------------------------------------

log_level = int(os.environ.get('ZYNTHIAN_LOG_LEVEL',logging.WARNING))

logger = logging.getLogger(__name__)
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
state_manager = None
chain_manager = None


last_hw_str = None
max_num_devs = 16
devices_in = [None for i in range(max_num_devs)]

#------------------------------------------------------------------------------

def get_port_alias_id(midi_port):
	try:
		alias_id = '_'.join(midi_port.aliases[0].split('-')[5:])
	except:
		alias_id = midi_port.name
	return alias_id


#Dirty hack for having MIDI working with PureData & CSound: #TODO => Improve it!!
def get_fixed_midi_port_name(port_name):
	if port_name == "pure_data":
		port_name = "Pure Data"

	elif port_name == "csound6":
		port_name = "Csound"

	elif port_name == "mod-monitor":
		port_name = "mod-host"

	return port_name


def get_all_connections_by_name(name):
	try:
		return jclient.get_all_connections(jclient.get_port_by_name(name))
	except:
		return []


# Connects the output port (port_from) to a list of input ports (ports_to), 
# disconnecting the output port from any other input port.
def connect_only(port_from, ports_to):
	# Get jack ports from strings if needed
	if isinstance(port_from, str):
		port_from = jclient.get_port_by_name(port_from)
	for i, pt in enumerate(ports_to):
		if isinstance(pt, str):
			ports_to[i] = jclient.get_port_by_name(pt)
	# Connect/disconnect
	for port_to in ports_to:
		already_connected = False
		for p in jclient.get_all_connections(port_from):
			if p==port_to:
				already_connected = True
			elif p not in ports_to:
				jclient.disconnect(port_from, p)
		if not already_connected:
			jclient.connect(port_from, port_to)


def replicate_connections_to(port1, port2):
	if isinstance(port1, str):
		port1 = jclient.get_port_by_name(port1)
	if isinstance(port2, str):
		port2 = jclient.get_port_by_name(port2)
	con1 = jclient.get_all_connections(port1)
	con2 = jclient.get_all_connections(port2)
	for p in con1:
		if p not in con2:
			jclient.connect(p, port2)
		else:
			con2.remove(p)
	for p in con2:
			jclient.disconnect(p, port2)


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

	# List of physical MIDI source ports
	hw_src_ports = jclient.get_ports(is_output=True, is_physical=True, is_midi=True)
	enabled_hw_src_ports = []
	for port in hw_src_ports:
		if port.name not in zynthian_gui_config.disabled_midi_in_ports:
			enabled_hw_src_ports.append(port)

	# List of physical MIDI destination ports
	hw_dst_ports = jclient.get_ports(is_input=True, is_physical=True, is_midi=True)
	# Remove a2j MIDI through (which would cause howl-round)
	try:
		a2j_thru = jclient.get_ports("a2j:Midi Through", is_input=True, is_physical=True, is_midi=True)[0]
		hw_dst_ports.pop(hw_dst_ports.index(a2j_thru))
	except:
		pass
	enabled_hw_dst_ports = []
	for port in hw_dst_ports:
		try:
			port_alias_id = get_port_alias_id(port)
			if port_alias_id in zynthian_gui_config.enabled_midi_out_ports:
				enabled_hw_dst_ports.append(port)
		except:
			pass

	# Add Zynmaster input
	zmip = jclient.get_ports("ZynMaster:midi_in", is_input=True, is_physical=False, is_midi=True)
	try:
		port_alias_id = get_port_alias_id(zmip[0])
		enabled_hw_dst_ports.append(zmip[0])
	except:
		pass

	# Treat Aubio as physical MIDI destination port
	aubio_out = jclient.get_ports("aubio", is_output=True, is_physical=False, is_midi=True)
	try:
		hw_src_ports.append(aubio_out[0])
	except:
		pass

	# List of MIDI over IP destination ports
	nw_dst_ports = []
	enabled_nw_dst_ports = []
	for port_name in ("QmidiNet:in_1", "jackrtpmidid:rtpmidi_in", "RtMidiIn Client:TouchOSC Bridge"):
		ports = jclient.get_ports(port_name, is_midi=True, is_input=True)
		nw_dst_ports += ports
		try:
			port_alias_id = get_port_alias_id(ports[0])
			if port_alias_id in zynthian_gui_config.enabled_midi_out_ports:
				enabled_nw_dst_ports.append(ports[0])
		except:
			pass

	nw_src_ports = []
	enabled_nw_src_ports = []
	for port_name in ("QmidiNet:out_1", "jackrtpmidid:rtpmidi_out", "RtMidiIn Client:TouchOSC Bridge"):
		ports = jclient.get_ports(port_name, is_midi=True, is_output=True)
		nw_src_ports += ports
		try:
			port_alias_id = get_port_alias_id(ports[0])
			if port_alias_id in zynthian_gui_config.enabled_midi_in_ports:
				enabled_nw_src_ports.append(ports[0])
		except:
			pass

	if not force:
		# Check if physical (hardware) interfaces have changed, e.g. USB plug
		hw_str = "" # Hardware device fingerprint
		for hw in hw_src_ports:
			hw_str += hw.name + "\n"
		for hw in hw_dst_ports:
			hw_str += hw.name + "\n"
		if hw_str == last_hw_str:
			release_lock() # Release Mutex Lock
			return
		else:
			last_hw_str = hw_str
	
	# Chain MIDI routing
	#TODO: Handle processors with multiple MIDI ports

	# Create graph of required chain routes as sets of sources indexed by destination
	required_routes = {}

	all_midi_dst = jclient.get_ports(is_input=True, is_midi=True)
	for dst in all_midi_dst:
		required_routes[dst.name] = set()

	for chain_id, chain in chain_manager.chains.items():
		# Add chain internal routes
		routes = chain_manager.get_chain_midi_routing(chain_id)
		for dst_name in routes:
			dst_ports = jclient.get_ports(dst_name, is_input=True, is_midi=True)
		
			for src_name in routes[dst_name]:
				src_ports = jclient.get_ports(src_name, is_output=True, is_midi=True)
				if src_ports and dst_ports:
					src = src_ports[0]
					dst = dst_ports[0]
					required_routes[dst.name].add(src.name)

		# Add chain MIDI outputs
		if chain.midi_slots and chain.midi_thru:
			dests = []
			for out in chain.midi_out:
				if out == "MIDI-OUT":
					dests += enabled_hw_dst_ports
				elif out == "NET-OUT":
					dests += enabled_nw_dst_ports
				elif out in chain_manager.chains:
					for processor in chain_manager.get_processors(out, "MIDI Tool", 0):
						try:
							dests += jclient.get_ports(processor.get_jackname(True), is_midi=True, is_input=True)
						except:
							pass
				else:
					dests += jclient.get_ports(out, is_midi=True, is_input=True)
			for processor in chain.midi_slots[-1]:
				src = jclient.get_ports(processor.get_jackname(True), is_midi=True, is_output=True)[0]
				for dst in dests:
					required_routes[dst.name].add(src.name)

		# Add MIDI router outputs
		if chain.is_midi():
			src_ports = jclient.get_ports(f"ZynMidiRouter:ch{chain.midi_chan}_out", is_midi=True, is_output=True)
			if src_ports:
				for dst_proc in chain.get_processors(slot=0):
					dst_ports = jclient.get_ports(dst_proc.get_jackname(True), is_midi=True, is_input=True)
					if dst_ports:
						src = src_ports[0]
						dst = dst_ports[0]
						required_routes[dst.name].add(src.name)

	#TODO Feedback ports

	# Add MIDI Input Devices
	for src in enabled_hw_src_ports:
		devnum = None
		port_alias_id = get_port_alias_id(src) #TODO: Why use port alias?
		try:
			#if the device is already registered, takes the number
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
				dst = f"ZynMidiRouter:dev{devnum}_in"
				required_routes[dst].add(src.name)
		except Exception as e:
			#logger.debug("Exception {}".format(e))
			pass

	#Connect RTP-MIDI output to ZynMidiRouter:net_in
	if zynthian_gui_config.midi_rtpmidi_enabled:
		required_routes["ZynMidiRouter:net_in"].add("jackrtpmidid:rtpmidi_out")

	#Connect QMidiNet output to ZynMidiRouter:net_in
	if zynthian_gui_config.midi_network_enabled:
		required_routes["ZynMidiRouter:net_in"].add("QmidiNet:out_1")

	#Connect TouchOSC output to ZynMidiRouter:net_in
	if zynthian_gui_config.midi_touchosc_enabled:
		required_routes["ZynMidiRouter:net_in"].add("RtMidiOut Client:TouchOSC Bridge")

	#Connect zynseq (stepseq) output to ZynMidiRouter:step_in
	required_routes["ZynMidiRouter:step_in"].add("zynseq:output")

	#Connect zynsmf output to ZynMidiRouter:seq_in
	required_routes["ZynMidiRouter:seq_in"].add("zynsmf:midi_out")

	#Connect ZynMidiRouter:main_out to zynsmf input
	try:
		required_routes["zynsmf:midi_in"].add("ZynMidiRouter:main_out")
	except:
		pass

	#Connect Engine's Controller-FeedBack to ZynMidiRouter:ctrl_in
	"""TODO
	for efbp in engines_fb:
		required_routes["ZynMidiRouter:ctrl_in"].add(efbp)
	"""

	if zynthian_gui_config.midi_filter_output:
		# Add MIDI OUT
		for port in enabled_hw_dst_ports:
			# Connect ZynMidiRouter:midi_out to...
			required_routes[port.name].add("ZynMidiRouter:midi_out")
		# ...enabled Network MIDI Output Ports
		for port in enabled_nw_dst_ports:
			# Connect ZynMidiRouter:net_out to...
			required_routes[port.name].add("ZynMidiRouter:net_out")
	# When "Send All MIDI to Output" is disabled, zynseq & zynsmf are routed directly
	else:
		# When midi_out is disabled need to route zynseq & zynsmf directly (not via ZynMidiRouter)
		for port in enabled_hw_dst_ports:
			# Connect zynseq (stepseq) output to...
			required_routes[port.name].add("zynseq:output")
			# Connect zynsmf output to...
			required_routes[port.name].add("zynsmf:midi_out")

		# ...enabled Network MIDI Output Ports
		for port in enabled_nw_dst_ports:
			# Connect zynseq (stepseq) output to ...
			required_routes[port.name].add("zynseq:output")
			# Connect zynsmf output to ...
			required_routes[port.name].add("zynsmf:midi_out")

	#Connect ZynMidiRouter:step_out to ZynthStep input
	required_routes["zynseq:input"].add("ZynMidiRouter:step_out")

	#Connect ZynMidiRouter:ctrl_out to enabled MIDI-FB ports (MIDI-Controller FeedBack)
	for port in hw_dst_ports:
		if get_port_alias_id(port) in zynthian_gui_config.enabled_midi_fb_ports:
			required_routes[port.name].add("ZynMidiRouter:ctrl_out")

	# Remove mod-ui routes
	for dst in required_routes.keys():
		if dst.startswith("effect_"):
			required_routes.pop(dst)

	# Connect and disconnect routes
	for dst, sources in required_routes.items():
		try:
			current_routes = jclient.get_all_connections(dst)
			for src in current_routes:
				if src.name in sources:
					continue
				jclient.disconnect(src.name, dst)
			for src in sources:
				try:
					jclient.connect(src, dst)
				except:
					pass
		except:
			pass

	#Release Mutex Lock
	release_lock()

def audio_autoconnect(force=False):
	if not force:
		return

	#Get Mutex Lock
	acquire_lock()

	# Get System Playback Ports
	system_playback_ports = jclient.get_ports("system:playback", is_input=True, is_audio=True, is_physical=True)

	# Create graph of required chain routes as sets of sources indexed by destination
	required_routes = {}

	all_audio_dst = jclient.get_ports(is_input=True, is_audio=True)
	for dst in all_audio_dst:
		required_routes[dst.name] = set()

	# Chain audio routing
	for chain_id, chain in chain_manager.chains.items():
		routes = chain_manager.get_chain_audio_routing(chain_id)
		if "zynmixer:return" in routes and "zynmixer:send" in routes["zynmixer:return"]:
			routes["zynmixer:return"].remove("zynmixer:send")
		for dest in routes:
			dst_ports = jclient.get_ports(dest, is_input=True, is_audio=True)
			dest_count = len(dst_ports)

			for src_name in routes[dest]:
				src_ports = jclient.get_ports(src_name, is_output=True, is_audio=True)
				source_count = len(src_ports)
				if source_count and dest_count:
					for i in range(max(source_count, dest_count)):
						src = src_ports[min(i, source_count - 1)]
						dst = dst_ports[min(i, dest_count - 1)]
						required_routes[dst.name].add(src.name)

	# Connect metronome to aux
	required_routes["zynmixer:input_17a"].add("zynseq:metronome")
	required_routes["zynmixer:input_17b"].add("zynseq:metronome")

	# Connect mixer to the System Output
	try:
		#TODO: Support configurable output routing
		required_routes[system_playback_ports[0].name].add("zynmixer:output_a")
		required_routes[system_playback_ports[1].name].add("zynmixer:output_b")
	except:
		pass

	#Get System Capture ports => jack output ports!!
	capture_ports = get_audio_capture_ports()
	capture_ports += jclient.get_ports('zynmixer:send')
	if zynthian_gui_config.midi_aubionotes_enabled:
		#Get Aubio Input ports...
		aubio_in = jclient.get_ports("aubio", is_input=True, is_audio=True)
		if len(aubio_in) > 0:
			nip = len(aubio_in)
			#Connect System Capture to Aubio ports
			j = 0
			for scp in capture_ports:
				required_routes[aubio_in[j % nip]].add(scp)

	# Remove mod-ui routes
	for dst in required_routes.keys():
		if dst.startswith("effect_"):
			required_routes.pop(dst)

	# Connect and disconnect routes
	for dst, sources in required_routes.items():
		current_routes = jclient.get_all_connections(dst)
		for src in current_routes:
			if src.name in sources:
				continue
			jclient.disconnect(src.name, dst)
		for src in sources:
			try:
				jclient.connect(src, dst)
			except:
				pass

	# Replicate System Output connections to Headphones
	hp_ports = jclient.get_ports("Headphones:playback", is_input=True, is_audio=True)
	if len(hp_ports) >= 2:
		replicate_connections_to(system_playback_ports[0], hp_ports[0])
		replicate_connections_to(system_playback_ports[1], hp_ports[1])

	#Release Mutex Lock
	release_lock()


def audio_connect_aux(source_name):
	ports = jclient.get_ports(source_name, is_output=True, is_audio=True)
	if ports:
		try:
			if len(ports) > 1:
				jclient.connect(ports[0], "zynmixer:input_17a")
				jclient.connect(ports[1], "zynmixer:input_17b")
			else:
				jclient.connect(ports[0], "zynmixer:input_17a")
				jclient.connect(ports[0], "zynmixer:input_17b")
		except Exception as e:
			logging.error("Can't connect {} to audio aux ports".format(source_name), e)


def audio_disconnect_sysout():
	sysout_ports=jclient.get_ports("system", is_input=True, is_audio=True)
	for sop in sysout_ports:
		conports = jclient.get_all_connections(sop)
		for cp in conports:
			try:
				jclient.disconnect(cp, sop)
			except:
				pass


def get_layer_audio_out_ports(layer):
	aout_ports = []
	for p in layer.get_audio_out():
		if p == "system":
			aout_ports += ["system:playback_1", "system:playback_2"]
		elif p == "mixer":
			if layer.midi_chan >= 17:
				aout_ports += ["zynmixer:return_a", "zynmixer:return_b"]
			else:
				aout_ports += [f"zynmixer:input_{layer.midi_chan + 1:02d}a", f"zynmixer:input_{layer.midi_chan + 1:02d}b"]
		elif p == "mod-ui":
			aout_ports += ["zynmixer:input_moduia", "zynmixer:input_moduib"]
		else:
			aout_ports.append(p)
	return list(dict.fromkeys(aout_ports).keys()) 


def get_audio_input_ports(exclude_system_playback=False):
	res = OrderedDict()
	try:
		for aip in jclient.get_ports(is_input=True, is_audio=True, is_physical=False):
			parts = aip.name.split(':')
			client_name = parts[0]
			if client_name in ["jack_capture","Headphones","mod-monitor"] or client_name[:7] == "effect_":
				continue
			if client_name == "system" or client_name == "zynmixer":
				if exclude_system_playback:
					continue
				else:
					client_name = aip.name
			if client_name not in res:
				res[client_name] = [aip]
				#logger.debug("AUDIO INPUT PORT: {}".format(client_name))
			else:
				res[client_name].append(aip)
	except:
		pass
	return res


def get_audio_capture_ports():
	return jclient.get_ports("system", is_output=True, is_audio=True, is_physical=True)


def get_audio_playback_ports():
	ports = jclient.get_ports("zynmixer", is_input=True, is_audio=True, is_physical=False)
	return ports + jclient.get_ports("system", is_input=True, is_audio=True, is_physical=True)


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
	try:
		lock.release()
	except:
		logging.warning("Attempted to release unlocked mutex")


def start(sm):
	global refresh_time, exit_flag, jclient, thread, lock, chain_manager, state_manager
	refresh_time = 2
	exit_flag = False
	state_manager = sm
	chain_manager = sm.chain_manager

	try:
		jclient = jack.Client("Zynthian_autoconnect")
		jclient.set_xrun_callback(cb_jack_xrun)
		jclient.activate()
	except Exception as e:
		logger.error("ZynAutoConnect ERROR: Can't connect with Jack Audio Server ({})".format(e))

	# Create Lock object (Mutex) to avoid concurrence problems
	lock = Lock()

	# Start Autoconnect Thread
	thread = Thread(target=autoconnect_thread, args=())
	thread.daemon = True # thread dies with the program
	thread.name = "autoconnect"
	thread.start()


def stop():
	global exit_flag
	exit_flag = True
	acquire_lock()
	audio_disconnect_sysout()
	release_lock()
	jclient.deactivate()


def is_running():
	global thread
	return thread.is_alive()


def cb_jack_xrun(delayed_usecs: float):
	logger.warning("Jack Audio XRUN! => delayed {}us".format(delayed_usecs))
	state_manager.status_info['xrun'] = True


def get_jackd_cpu_load():
	return jclient.cpu_load()


def get_jackd_samplerate():
	return jclient.samplerate


def get_jackd_blocksize():
	return jclient.blocksize


#------------------------------------------------------------------------------
