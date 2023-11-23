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

log_level = int(os.environ.get('ZYNTHIAN_LOG_LEVEL', logging.WARNING))

logger = logging.getLogger(__name__)
logger.setLevel(log_level)

#if log_level==logging.DEBUG:
#	import inspect

#-------------------------------------------------------------------------------
# Define some Constants and Global Variables
#-------------------------------------------------------------------------------

jclient = None					# JACK client
thread = None					# Thread to check for changed MIDI ports
exit_flag = False				# True to exit thread
state_manager = None			# State Manager object
chain_manager = None			# Chain Manager object
xruns = 0						# Quantity of xruns since startup or last reset
deferred_midi_connect = False 	# True to perform MIDI connect on next port check cycle
deferred_audio_connect = False 	# True to perform audio connect on next port check cycle

last_hw_str = None				# Fingerprint of MIDI ports used to check for change of ports
max_num_devs = 16				# Maximum quantity of hardware inputs
devices_in = [None for i in range(max_num_devs)]		# List of hardware inputs
devices_in_name = [None for i in range(max_num_devs)]	# List of hardware input names
devices_out = [None for i in range(max_num_devs)]	# List of hardware outputs
devices_out_name = [None for i in range(max_num_devs)]	# List of hardware output names

zyn_routed_audio = {}			# Map of lists of audio sources routed by zynautoconnect, indexed by destination
zyn_routed_midi = {}			# Map of lists of MIDI sources routed by zynautoconnect, indexed by destination

mididev_changed = False			# Flag mididev changes

#------------------------------------------------------------------------------

def get_port_alias_id(midi_port):
	"""Get port alias for a MIDI port
	
	midi_port : Jack MIDI port
	#TODO: Can we lose this?
	"""

	try:
		alias_id = '_'.join(midi_port.aliases[0].split('-')[5:])
	except:
		alias_id = midi_port.name

	if midi_port.is_input:
		postfix = "OUT"
	else:
		postfix = "IN"

	if alias_id.startswith("ttymidi:"):
		alias_id = f"DIN-5 MIDI-{postfix}"
	elif alias_id.startswith("a2j:"):
		alias_id = f"ALSA MIDI-{postfix}"
	elif alias_id == "f_midi":
		alias_id = f"USB MIDI-{postfix}"
	elif alias_id == "ZynMaster:midi_in":
		alias_id = "CV/Gate Out"
	elif alias_id == "aubio":
		alias_id = "Audio => MIDI"

	return alias_id


def get_midi_in_devid(idev):
	if idev > 0 and idev <= len(devices_in):
		return devices_in[idev - 1]
	else:
		return None


def get_midi_out_devid(idev):
	if idev > 0 and idev <= len(devices_out):
		return devices_out[idev - 1]
	else:
		return None


def set_mididev_changed(flag):
	global mididev_changed
	mididev_changed = flag


def get_mididev_changed():
	return mididev_changed

#------------------------------------------------------------------------------

def request_audio_connect(fast = False):
	"""Request audio connection graph refresh

	fast : True for fast update (default=False to trigger on next 2s cycle
	"""

	global deferred_audio_connect
	if fast:
		audio_autoconnect()
	else:
		deferred_audio_connect = True

def request_midi_connect(fast = False):
	"""Request MIDI connection graph refresh

	fast : True for fast update (default=False to trigger on next 2s cycle
	"""

	global deferred_midi_connect
	if fast:
		midi_autoconnect()
	else:
		deferred_midi_connect = True

def midi_autoconnect():
	"""Connect all expected MIDI routes"""

	#Get Mutex Lock 
	if not acquire_lock():
		return
	
	#logger.info("ZynAutoConnect: MIDI ...")
	global zyn_routed_midi

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
			if port_alias_id.replace(" ", "_") in zynthian_gui_config.enabled_midi_out_ports:
				enabled_hw_dst_ports.append(port)
		except:
			pass

	# Add Zynmaster (CV/gate output))
	zmip = jclient.get_ports("ZynMaster:midi_in", is_input=True, is_physical=False, is_midi=True)
	try:
		enabled_hw_dst_ports.append(zmip[0])
	except:
		pass

	# Treat Aubio as physical MIDI source port
	aubio_out = jclient.get_ports("aubio", is_output=True, is_physical=False, is_midi=True)
	try:
		hw_src_ports.append(aubio_out[0])
	except:
		pass

	# Create graph of required chain routes as sets of sources indexed by destination
	required_routes = {}
	all_midi_dst = jclient.get_ports(is_input=True, is_midi=True)
	for dst in all_midi_dst:
		required_routes[dst.name] = set()

	# Connect MIDI Input Devices to ZynMidiRouter ports (zmips)
	busy_idevs = []
	for hwsp in hw_src_ports:
		devnum = None
		port_alias_id = get_port_alias_id(hwsp)
		if port_alias_id:
			# logger.debug("Connecting MIDI Input {}".format(hwsp))
			# Device is already registered, takes the number
			try:
				devnum = devices_in.index(port_alias_id)
			# else register it, taking the first free port
			except:
				for i in range(max_num_devs):
					if devices_in[i] is None:
						devnum = i
						devices_in[devnum] = port_alias_id
						devices_in_name[devnum] = hwsp.name
						logger.debug("Connected MIDI-in device {}: {}".format(devnum, port_alias_id))
						break
			if devnum is not None:
				dst = f"ZynMidiRouter:dev{devnum}_in"
				required_routes[dst].add(hwsp.name)
				busy_idevs.append(devnum)
				set_mididev_changed(True)

	# Delete disconnected input devices from list
	for i in range(0, max_num_devs):
		if i not in busy_idevs and devices_in[i] is not None:
			devices_in[i] = None
			devices_in_name[i] = None
			set_mididev_changed(True)
			logger.debug("Disconnected MIDI-in device {}: {}".format(i, devices_in[i]))

	# Connect MIDI Output Devices
	busy_idevs = []
	for hwdp in hw_dst_ports:
		devnum = None
		port_alias_id = get_port_alias_id(hwdp)
		if port_alias_id:
			# logger.debug("Connecting MIDI Output {}".format(hwdp))
			# if the device is already registered, takes the number
			try:
				devnum = devices_out.index(port_alias_id)
			# else register it, taking the first free port
			except:
				for i in range(max_num_devs):
					if devices_out[i] is None:
						devnum = i
						devices_out[devnum] = port_alias_id
						devices_out_name[devnum] = hwdp.name
						logger.debug("Connected MIDI-out device {}: {}".format(devnum, port_alias_id))
						break
			if devnum is not None:
				src = f"ZynMidiRouter:dev{devnum}_out"
				required_routes[hwdp.name].add(src)
				busy_idevs.append(devnum)
				set_mididev_changed(True)

	# Delete disconnected output devices from list
	for i in range(0, max_num_devs):
		if i not in busy_idevs and devices_out[i] is not None:
			devices_out[i] = None
			devices_out_name[i] = None
			set_mididev_changed(True)
			logger.debug("Disconnected MIDI-out device {}: {}".format(i, devices_out[i]))

	# List MIDI over IP destination ports
	nw_dst_ports = []
	enabled_nw_dst_ports = []
	for port_name in ("QmidiNet:in_1", "jackrtpmidid:rtpmidi_in", "RtMidiIn Client:TouchOSC Bridge"):
		ports = jclient.get_ports(port_name, is_midi=True, is_input=True)
		nw_dst_ports += ports
		try:
			port_alias_id = get_port_alias_id(ports[0])
			if port_alias_id.replace(" ", "_") in zynthian_gui_config.enabled_midi_out_ports:
				enabled_nw_dst_ports.append(ports[0])
		except:
			pass

	# List MIDI over IP source ports
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

	# Chain MIDI routing
	#TODO: Handle processors with multiple MIDI ports

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
				if out == "NET-OUT":
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
	required_routes["zynsmf:midi_in"].add("ZynMidiRouter:main_out")

	# Add MIDI synth engine's controller-feedback to ZynMidiRouter:ctrl_in
	for processor in chain_manager.processors.values():
		if processor.type == "MIDI Synth":
			try:
				ports = jclient.get_ports(processor.get_jackname(True), is_midi=True, is_output=True)
				required_routes["ZynMidiRouter:ctrl_in"].add(ports[0].name)
			except:
				pass

	# => Set MIDI THRU
	lib_zyncore.set_midi_thru(zynthian_gui_config.midi_filter_output)

	# Route MIDI-THRU output to enabled output ports
	for port in enabled_hw_dst_ports:
		# Connect ZynMidiRouter:midi_out to...
		required_routes[port.name].add("ZynMidiRouter:midi_out")

	# Route MIDI-THRU output to network enabled output ports
	for port in enabled_nw_dst_ports:
		# Connect ZynMidiRouter:net_out to...
		required_routes[port.name].add("ZynMidiRouter:net_out")

	#Connect ZynMidiRouter:step_out to ZynthStep input
	required_routes["zynseq:input"].add("ZynMidiRouter:step_out")

	#Connect ZynMidiRouter:ctrl_out to enabled MIDI-FB ports (MIDI-Controller FeedBack)
	for port in hw_dst_ports:
		if get_port_alias_id(port) in zynthian_gui_config.enabled_midi_fb_ports:
			required_routes[port.name].add("ZynMidiRouter:ctrl_out")

	# Remove mod-ui routes
	for dst in list(required_routes.keys()):
		if dst.startswith("effect_"):
			required_routes.pop(dst)

	# Connect and disconnect routes
	for dst, sources in required_routes.items():
		if dst not in zyn_routed_midi:
			zyn_routed_midi[dst] = sources
		else:
			zyn_routed_midi[dst] = zyn_routed_midi[dst].union(sources)
		current_routes = jclient.get_all_connections(dst)
		for src in current_routes:
			if src.name in sources:
				continue
			if src.name in zyn_routed_midi[dst]:
				try:
					jclient.disconnect(src.name, dst)
				except:
					pass
				zyn_routed_midi[dst].remove(src.name)
		for src in sources:
			try:
				jclient.connect(src, dst)
				zyn_routed_midi[dst].append(src.name)
			except:
				pass

	#Release Mutex Lock
	release_lock()

def audio_autoconnect():

	#Get Mutex Lock
	if not acquire_lock():
		return
	
	# Get System Playback Ports
	system_playback_ports = jclient.get_ports("system:playback", is_input=True, is_audio=True, is_physical=True)

	# Create graph of required chain routes as sets of sources indexed by destination
	required_routes = {}

	all_audio_dst = jclient.get_ports(is_input=True, is_audio=True)
	for dst in all_audio_dst:
		required_routes[dst.name] = set()

	# Chain audio routing
	for chain_id in chain_manager.chains:
		routes = chain_manager.get_chain_audio_routing(chain_id)
		#if "zynmixer:return" in routes and "zynmixer:send" in routes["zynmixer:return"]:
		#	routes["zynmixer:return"].remove("zynmixer:send")
		for dst in routes:
			dst_ports = jclient.get_ports(dst, is_input=True, is_audio=True)
			dst_count = len(dst_ports)

			for src_name in routes[dst]:
				src_ports = jclient.get_ports(src_name, is_output=True, is_audio=True)
				source_count = len(src_ports)
				if source_count and dst_count:
					for i in range(max(source_count, dst_count)):
						src = src_ports[min(i, source_count - 1)]
						dst = dst_ports[min(i, dst_count - 1)]
						required_routes[dst.name].add(src.name)

	# Connect metronome to aux
	required_routes["zynmixer:input_17a"].add("zynseq:metronome")
	required_routes["zynmixer:input_17b"].add("zynseq:metronome")

	# Connect global audio player to aux
	if state_manager.audio_player:
		ports = jclient.get_ports(state_manager.audio_player.jackname, is_output=True, is_audio=True)
		required_routes["zynmixer:input_17a"].add(ports[0].name)
		required_routes["zynmixer:input_17b"].add(ports[1].name)

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
	for dst in list(required_routes.keys()):
		if dst.startswith("effect_"):
			required_routes.pop(dst)

	# Replicate main output to headphones
	hp_ports = jclient.get_ports("Headphones:playback", is_input=True, is_audio=True)
	if len(hp_ports) >= 2:
		required_routes[hp_ports[0]] = required_routes[system_playback_ports[0].name]
		required_routes[hp_ports[1]] = required_routes[system_playback_ports[1].name]


	# Connect and disconnect routes
	for dst, sources in required_routes.items():
		if dst not in zyn_routed_audio:
			zyn_routed_audio[dst] = sources
		else:
			zyn_routed_audio[dst] = zyn_routed_audio[dst].union(sources)
		current_routes = jclient.get_all_connections(dst)
		for src in current_routes:
			if src.name in sources:
				continue
			if src.name in zyn_routed_audio[dst]:
				try:
					jclient.disconnect(src.name, dst)
				except:
					pass
				zyn_routed_audio[dst].remove(src.name)
		for src in sources:
			try:
				jclient.connect(src, dst)
				zyn_routed_audio[dst].append(src.name)
			except:
				pass

	#Release Mutex Lock
	release_lock()


def get_audio_input_ports(exclude_system_playback=False):
	"""Get list of audio destinations acceptable to be routed to

	exclude_system_playback : True to exclude playback destinations
	TODO : Used for side-chaining but could be done better
	"""
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


# Connect mixer to the ffmpeg recorder
def audio_connect_ffmpeg(timeout=2.0):
	t = 0
	while t < timeout:
		try:
			jclient.connect("zynmixer:output_a", "ffmpeg:input_1")
			jclient.connect("zynmixer:output_b", "ffmpeg:input_2")
			return
		except:
			sleep(0.1)
			t += 0.1


def get_audio_capture_ports():
	"""Get list of hardware audio inputs"""

	return jclient.get_ports("system", is_output=True, is_audio=True, is_physical=True)


def autoconnect():
	"""Connect expected routes and disconnect unexpected routes"""
	midi_autoconnect()
	audio_autoconnect()


def auto_connect_thread():
	"""Thread to run autoconnect, checking if physical (hardware) interfaces have changed, e.g. USB plug"""

	global last_hw_str, deferred_midi_connect, deferred_audio_connect

	deferred_timeout = 2 # Period to run deferred connect (in seconds)
	deferred_inc = 0.1 # Delay between loop cycles (in seconds)
	deferred_count = 0
	do_audio = False
	do_midi = False

	while not exit_flag:
		try:
			if deferred_count > deferred_timeout:
				deferred_count = 0

				hw_str = "" # Hardware device fingerprint
				hw_src_ports = jclient.get_ports(is_output=True, is_physical=True, is_midi=True)
				for hw in hw_src_ports:
					hw_str += hw.name + "\n"
				hw_dst_ports = jclient.get_ports(is_input=True, is_physical=True, is_midi=True)
				for hw in hw_dst_ports:
					hw_str += hw.name + "\n"
				if hw_str != last_hw_str:
					last_hw_str = hw_str
					do_midi = True

				if deferred_midi_connect:
					do_midi = True

				if deferred_audio_connect:
					do_audio = True

			if do_midi:
				midi_autoconnect()
				do_midi = False
				deferred_midi_connect = False

			if do_audio:
				audio_autoconnect()
				do_audio = False
				deferred_audio_connect = False

		except Exception as err:
			logger.error("ZynAutoConnect ERROR: {}".format(err))

		sleep(deferred_inc)
		deferred_count += deferred_inc


def acquire_lock():
	"""Acquire mutex lock
	
	Returns : True on success or False if lock not available
	"""

	#if log_level==logging.DEBUG:
	#	calframe = inspect.getouterframes(inspect.currentframe(), 2)
	#	logger.debug("Waiting for lock, requested from '{}'...".format(format(calframe[1][3])))
	try:
		lock.acquire()
	except:
		return False
	#logger.debug("... lock acquired!!")
	return True


def release_lock():
	"""Release mutex lock"""

	#if log_level==logging.DEBUG:
	#	calframe = inspect.getouterframes(inspect.currentframe(), 2)
	#	logger.debug("Lock released from '{}'".format(calframe[1][3]))
	try:
		lock.release()
	except:
		logging.warning("Attempted to release unlocked mutex")


def start(sm):
	"""Initialise autoconnect and start MIDI port checker
	
	sm : State manager object
	"""

	global refresh_time, exit_flag, jclient, thread, lock, chain_manager, state_manager
	if jclient:
		return # Already started
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

	# Start port change checking thread
	thread = Thread(target=auto_connect_thread, args=())
	thread.daemon = True # thread dies with the program
	thread.name = "Autoconnect"
	thread.start()


def stop():
	"""Reset state and stop autoconnect thread"""

	global exit_flag, jclient, thread, lock
	exit_flag = True
	if thread:
		thread.join()
		thread = None

	if acquire_lock():
		release_lock()
		lock = None

	if jclient:
		jclient.deactivate()
		jclient = None


def is_running():
	"""Check if autoconnect thread is running
	
	Returns : True if running"""

	global thread
	if thread:
		return thread.is_alive()
	return False


def cb_jack_xrun(delayed_usecs: float):
	"""Jack xrun callback

	delayed_usecs : Period of delay caused by last jack xrun
	"""

	if not state_manager.power_save_mode:
		global xruns
		xruns += 1
		logger.warning(f"Jack Audio XRUN! =>count: {xruns}, delay: {delayed_usecs}us")
		state_manager.status_xrun = True


def get_jackd_cpu_load():
	"""Get the JACK CPU load"""

	return jclient.cpu_load()


def get_jackd_samplerate():
	"""Get JACK samplerate"""

	return jclient.samplerate


def get_jackd_blocksize():
	"""Get JACK block size"""

	return jclient.blocksize


#------------------------------------------------------------------------------
