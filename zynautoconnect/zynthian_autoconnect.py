# -*- coding: utf-8 -*-
#********************************************************************
# ZYNTHIAN PROJECT: Zynthian Autoconnector
# 
# Autoconnect Jack clients
# 
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
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

import os, re
import jack, alsa_midi
import logging
from time import sleep
from threading  import Thread, Lock
import usb

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
aclient = None					# ALSA client
thread = None					# Thread to check for changed MIDI ports
exit_flag = False				# True to exit thread
paused_flag = False				# True id autoconnect task is paused
state_manager = None			# State Manager object
chain_manager = None			# Chain Manager object
xruns = 0						# Quantity of xruns since startup or last reset
deferred_midi_connect = False 	# True to perform MIDI connect on next port check cycle
deferred_audio_connect = False 	# True to perform audio connect on next port check cycle

max_num_devs = 16				# Maximum quantity of hardware inputs
devices_in = [None for i in range(max_num_devs)]	# List of hardware inputs
devices_out = [None for i in range(max_num_devs)]	# List of hardware outputs

# zyn_routed_* are used to avoid changing routes made by other jack clients
zyn_routed_audio = {}			# Map of lists of audio sources routed by zynautoconnect, indexed by destination
zyn_routed_midi = {}			# Map of lists of MIDI sources routed by zynautoconnect, indexed by destination

host_usb_connected = False		# True if connected to host USB

midi_port_names = {}			# Map of user friendly names indexed by device uid (alias[0])
#------------------------------------------------------------------------------

### MIDI port helper functions ###

def get_friendly_name(uid):
	"""Get port friendly name
	
	uid : Port uid (alias 2)
	returns : Friendly name or None if not set
	"""
	
	if uid in midi_port_names:
		return midi_port_names[uid]
	return None

def get_ports(name, is_input=None):
	return jclient.get_ports(name, is_input=is_input)

def dev_in_2_dev_out(zmip):
	"""Get index of output devices from its input device index

	zmip : Input port index
	returns : Output port index or None if not found
	"""
	
	try:
		return devices_out.index(jclient.get_port_by_name(devices_in[zmip].name.replace("capture", "playback")))
	except:
		return None

def set_midi_port_names(port_names):
	global midi_port_names
	midi_port_names = port_names.copy()

def get_port_aliases(midi_port):
	"""Get port alias for a MIDI port
	
	midi_port : Jack MIDI port
	returns : List of aliases or port name if alias not set
	"""

	try:
		return (midi_port.aliases[0], midi_port.aliases[1])
	except:
		return (midi_port.name, midi_port.name)

def get_port_from_name(name):
	"""Get a JACK port from its name
	
	name : Port name
	returns : JACK port or None if not found
	"""

	try:
		return jclient.get_port_by_name(name)
	except:
		return None

def get_midi_in_devid(idev):
	"""Get the ALSA name of the port connected to ZMIP port
	
	idev : Index of ZMIP port
	returns : ALSA name or None if not found
	"""

	try:
		return devices_in[idev].name.split('] (capture): ')[1]
	except:
		return None


def get_midi_out_devid(idev):
	"""Get the ALSA name of the port connected from ZMOP port
	
	idev : Index of ZMOP port
	returns : ALSA name or None if not found
	"""

	try:
		return devices_out[idev].name.split('] (playback): ')[1]
	except:
		return None

def get_midi_in_devid_by_uid(uid):
	"""Get the index of the ZMIP connected to physical input
	
	name : The uid name of the port (jack alias [0])
	"""

	for i, port in enumerate(devices_in):
		if port and port.aliases[0] == uid:
			return i
	return None


def get_midi_out_devid_by_uid(uid):
	"""Get the index of the ZMOP connected to physical output
	
	name : The uid name of the port (jack alias [0])
	"""

	for i, port in enumerate(devices_out):
		if port and port.aliases[0] == uid:
			return i
	return None


#------------------------------------------------------------------------------

def request_audio_connect(fast = False):
	"""Request audio connection graph refresh

	fast : True for fast update (default=False to trigger on next 2s cycle
	"""

	#if paused_flag:
	#	return
	if fast:
		audio_autoconnect()
	else:
		global deferred_audio_connect
		deferred_audio_connect = True

def request_midi_connect(fast = False):
	"""Request MIDI connection graph refresh

	fast : True for fast update (default=False to trigger on next 2s cycle
	"""

	#if paused_flag:
	#	return
	if fast:
		midi_autoconnect()
	else:
		global deferred_midi_connect
		deferred_midi_connect = True

def is_host_usb_connected():
	"""Check if the USB host (e.g. USB-Type B connection) is connected

	returns : True if connected to USB host		
	"""

	with open("/sys/class/udc/fe980000.usb/device/gadget/suspended") as f:
		return f.read() != "1\n"

def midi_autoconnect():
	"""Connect all expected MIDI routes"""

	#Get Mutex Lock
	if not acquire_lock():
		return

	global deferred_midi_connect
	deferred_midi_connect = False

	#logger.info("ZynAutoConnect: MIDI ...")
	global zyn_routed_midi

	# Update aliases used to persistently uniquely identify physical ports
	update_midi_port_aliases()
	
	#-----------------------------------------------------------
	# Get Input/Output MIDI Ports: 
	#  - sources including physical inputs are jack outputs
	#  - destinations including physical outputs are jack inputs
	#-----------------------------------------------------------

	# List of physical MIDI source ports
	hw_src_ports = jclient.get_ports(is_output=True, is_physical=True, is_midi=True)

	# Remove host USB if not connected
	if not host_usb_connected:
		try:
			f_midi = jclient.get_ports("^a2j:f_midi \[.*] \(capture\)", is_output=True, is_physical=True, is_midi=True)[0]
			hw_src_ports.remove(f_midi)
		except:
			pass

	# Remove a2j MIDI through (we don't currently use it but may want to enable in future)
	try:
		a2j_thru = jclient.get_ports("^a2j:Midi Through", is_output=True, is_physical=True, is_midi=True)[0]
		hw_src_ports.remove(a2j_thru)
	except:
		pass

	# List of physical MIDI destination ports
	hw_dst_ports = jclient.get_ports(is_input=True, is_physical=True, is_midi=True)

	# Remove host USB if not connected
	if not host_usb_connected:
		try:
			f_midi = jclient.get_ports("^a2j:f_midi \[.*] \(capture\)", is_input=True, is_physical=True, is_midi=True)[0]
			hw_dst_ports.remove(f_midi)
		except:
			pass

	# Remove a2j MIDI through (we don't want this - it can lead to howl-round)
	try:
		a2j_thru = jclient.get_ports("^a2j:Midi Through", is_input=True, is_physical=True, is_midi=True)[0]
		hw_dst_ports.remove(a2j_thru)
	except:
		pass

	# Treat some virtual MIDI ports as hardware
	for port_name in ("QmidiNet:in_1", "jackrtpmidid:rtpmidi_in", "RtMidiIn Client:TouchOSC Bridge", "ZynMaster:midi_in"):
		try:
			ports = jclient.get_ports(port_name, is_midi=True, is_input=True)
			hw_dst_ports += ports
		except:
			pass
	for port_name in ("QmidiNet:out_1", "jackrtpmidid:rtpmidi_out", "RtMidiOut Client:TouchOSC Bridge", "aubio"):
		try:
			ports = jclient.get_ports(port_name, is_midi=True, is_output=True)
			hw_src_ports += ports
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
		# logger.debug("Connecting MIDI Input {}".format(hwsp))
		try:
			# Device is already registered, takes the number
			devnum = devices_in.index(hwsp)
		except:
			# else register it, taking the first free port
			for i in range(max_num_devs):
				if devices_in[i] is None:
					devnum = i
					devices_in[devnum] = hwsp
					logger.debug(f"Connected MIDI-in device {devnum}: {hwsp.name}")
					break
		if devnum is not None:
			required_routes[f"ZynMidiRouter:dev{devnum}_in"].add(hwsp.name)
			busy_idevs.append(devnum)

	# Delete disconnected input devices from list
	for i in range(0, max_num_devs):
		if i not in busy_idevs and devices_in[i] is not None:
			logger.debug(f"Disconnected MIDI-in device {i}: {devices_in[i].name}")
			devices_in[i] = None
			if state_manager.ctrldev_manager.unload_driver(i):
				lib_zyncore.zmip_set_route_extdev(i, 1)


	# Connect MIDI Output Devices
	busy_idevs = []
	for hwdp in hw_dst_ports:
		devnum = None
		# logger.debug("Connecting MIDI Output {}".format(hwdp))
		try:
			# if the device is already registered, takes the number
			devnum = devices_out.index(hwdp)
		except:
			# else register it, taking the first free port
			for i in range(max_num_devs):
				if devices_out[i] is None:
					devnum = i
					devices_out[devnum] = hwdp
					logger.debug("fConnected MIDI-out device {dev_num}: {hwdp.name}")
					break
		if devnum is not None:
			required_routes[hwdp.name].add(f"ZynMidiRouter:dev{devnum}_out")
			busy_idevs.append(devnum)

	# Delete disconnected output devices from list
	for i in range(0, max_num_devs):
		if i not in busy_idevs and devices_out[i] is not None:
			logger.debug(f"Disconnected MIDI-out device {i}: {devices_out[i].name}")
			devices_out[i] = None

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
				if out in chain_manager.chains:
					for processor in chain_manager.get_processors(out, "MIDI Tool", 0):
						for dst in jclient.get_ports(processor.get_jackname(True), is_midi=True, is_input=True):
							dests.append(dst.name)
				else:
					dests.append(out)
			for processor in chain.midi_slots[-1]:
				src = jclient.get_ports(processor.get_jackname(True), is_midi=True, is_output=True)[0]
				for dst in dests:
					required_routes[dst].add(src.name)

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
	#TODO: Do we want to retain MIDI THRU now that we have MIDI chains that can pass thru with per device filtering?
	lib_zyncore.set_midi_thru(zynthian_gui_config.midi_filter_output)

	# Route MIDI-THRU output to enabled output ports
	for port in hw_dst_ports:
		# Connect ZynMidiRouter:midi_out to...
		required_routes[port.name].add("ZynMidiRouter:midi_out")

	#Connect ZynMidiRouter:step_out to ZynthStep input
	required_routes["zynseq:input"].add("ZynMidiRouter:step_out")

	#Connect ZynMidiRouter:ctrl_out to enabled MIDI-FB ports (MIDI-Controller FeedBack)
	for port in hw_dst_ports:
		if get_port_aliases(port)[0] in zynthian_gui_config.enabled_midi_fb_ports:
			required_routes[port.name].add("ZynMidiRouter:ctrl_out")

	# Remove mod-ui routes
	for dst in list(required_routes.keys()):
		if dst.startswith("effect_"):
			required_routes.pop(dst)


	### Connect and disconnect routes ###
	for dst, sources in required_routes.items():
		try:
			current_routes = jclient.get_all_connections(dst)
		except Exception as e:
			current_routes = []
			logging.warning(e)
		for src in current_routes:
			if src.name in sources:
				continue
			if src.name in zyn_routed_midi[dst]:
				try:
					jclient.disconnect(src, dst)
				except:
					pass
				zyn_routed_midi[dst].remove(src.name)
		for src in sources:
			try:
				jclient.connect(src, dst)
				if dst not in zyn_routed_midi:
					zyn_routed_midi[dst] = [src]
				else:
					zyn_routed_midi[dst].append(src)
			except:
				pass

	#Release Mutex Lock
	release_lock()

def audio_autoconnect():

	#Get Mutex Lock
	if not acquire_lock():
		return

	global deferred_audio_connect
	deferred_audio_connect = False

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

	# Connect inputs to aubionotes
	if zynthian_gui_config.midi_aubionotes_enabled:
		capture_ports = get_audio_capture_ports()
		#Get Aubio Input ports...
		aubio_in = jclient.get_ports("aubio", is_input=True, is_audio=True)
		nip = len(aubio_in)
		if nip:
			#Connect System Capture to Aubio ports
			for i, scp in enumerate(capture_ports):
				required_routes[aubio_in[i % nip].name].add(scp.name)

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
		try:
			current_routes = jclient.get_all_connections(dst)
		except Exception as e:
			current_routes = []
			logging.warning(e)
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
	res = {}
	try:
		for aip in jclient.get_ports(is_input=True, is_audio=True, is_physical=False):
			parts = aip.name.split(':')
			client_name = parts[0]
			if client_name in ["jack_capture", "Headphones", "mod-monitor"] or client_name[:7] == "effect_":
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


def build_midi_port_name(port):
	try:
		name = port.shortname.split(':')[-1].strip()
		alsa_client_id = int(port.shortname.split('[')[1].split(']')[0])
		# USB ports
		card_id = aclient.get_client_info(alsa_client_id).card_id
		with open(f"/proc/asound/card{card_id}/usbbus", "r") as f:
			usbbus = f.readline()
		tmp = re.findall(r'\d+', usbbus)
		bus = int(tmp[0])
		address = int(tmp[1])
		usb_port_nos = usb.core.find(bus=bus, address=address).port_numbers
		uid = f"{bus}"
		for i in usb_port_nos:
			uid += f".{i}"
		uid = f"USB:{uid} {name}"
	except:
		uid = name
	if port.is_input:
		uid += " OUT"
	else:
		uid += " IN"
	return uid, name


def get_midi_port_aliases():
	aliases = {}
	for port in jclient.get_ports(is_midi=True):
		try: #TODO: Do not include default names
			aliases[port.aliases[0]] = port.aliases[1]
		except:
			pass
	return aliases


def update_midi_port_aliases():
	"""Ensure all physical jack ports have uid and friendly name in aliases 0 & 1
	"""

	#TODO: Optimise - should not rebuild all on every iteration
	for port in jclient.get_ports(is_physical=True, is_midi=True):
		try:
			alias1 = port.name
			alias2 = None
			# Static ports
			if port.name == "ttymidi:MIDI_in":
				alias2 = "DIN-5 MIDI IN"
			elif port.name == "ttymidi:MIDI_out":
				alias2 = "DIN-5 MIDI OUT"
			elif port.name.endswith(" (capture): f_midi"):
				alias1 = "f_midi:in"
				alias2 = "USB HOST IN"
			elif port.name.endswith("(playback): f_midi"):
				alias1 = "f_midi:out"
				alias2 = "USB HOST OUT"
			# Dynamic ports
			elif port.name.endswith("Bluetooth"):
				continue
			else:
				alias1, alias2 = (build_midi_port_name(port))

			# Clear current aliases - blunt!
			for alias in port.aliases:
				port.unset_alias(alias)

			# Set aliases
			port.set_alias(alias1)
			if alias1 in midi_port_names: # User defined names
				port.set_alias(midi_port_names[alias1])
			else:
				if alias2:
					port.set_alias(alias2)
				else:
					port.set_alias(alias1)
		except:
			logging.warning(f"Unable to set alias for port {port.name}")

	set_midi_port_alias("aubio:midi_out_1", "AUBIO:in", "Audio\u2794MIDI")
	set_midi_port_alias("jackrtpmidid:rtpmidi_out", "NET:rtp_in", "RTP MIDI IN")
	set_midi_port_alias("jackrtpmidid:rtpmidi_in", "NET:rtp_out", "RTP MIDI OUT")
	set_midi_port_alias("QmidiNet:out_1", "NET:qmidi_in", "QMIDI IN")
	set_midi_port_alias("QmidiNet:in_1", "NET:qmidi_out", "QMIDI OUT")
	set_midi_port_alias("RtMidiOut Client:TouchOSC Bridge", "NET:touchosc_in", "TouchOSC IN")
	set_midi_port_alias("RtMidiIn Client:TouchOSC Bridge", "NET:touchosc_out", "TouchOSC OUT")


def set_midi_port_alias(port_name, alias1, alias2=None, force=False):
	global midi_port_names

	try:
		port = jclient.get_port_by_name(port_name)
		if len(port.aliases) > 1 and not force:
			return
		for a in port.aliases:
			port.unset_alias(a)
		port.set_alias(alias1)
		if alias2 is None:
			if alias1 in midi_port_names:
				alias2 = midi_port_names[alias1]
			else:
				alias2 = alias1
		port.set_alias(alias2)
		midi_port_names[alias1] = alias2
	except:
		pass

def set_port_friendly_name(port, friendly_name=None):
	"""Set the friendly name for a JACK port
	
	port : JACK port object
	friendly_name : New friendly name (optional) Default:Reset to port shortname 
	"""

	global midi_port_names

	try:
		if len(port.aliases) < 1:
			return
		if len(port.aliases) > 1:
			port.unset_alias(port.aliases[1])
		if friendly_name is None:
			friendly_name = port.shortname
		port.set_alias(friendly_name)
		midi_port_names[port.aliases[0]] = friendly_name
	except:
		pass


def set_port_friendly_name_from_uid(uid, friendly_name):
	for port in jclient.get_ports():
		if len(port.aliases) and port.aliases[0] == uid:
			set_port_friendly_name(port, friendly_name)
			break


def autoconnect():
	"""Connect expected routes and disconnect unexpected routes"""
	midi_autoconnect()
	audio_autoconnect()


def auto_connect_thread():
	"""Thread to run autoconnect, checking if physical (hardware) interfaces have changed, e.g. USB plug"""

	global host_usb_connected

	deferred_timeout = 2 # Period to run deferred connect (in seconds)
	deferred_inc = 0.1 # Delay between loop cycles (in seconds) - allows faster exit from thread
	deferred_count = 5 # Run at startup
	do_audio = False
	do_midi = False
	last_hw_devs = None # Fingerprint of MIDI ports used to check for change of ports
	last_hw_change = 0

	while not exit_flag:
		if not paused_flag:
			try:
				if deferred_count > deferred_timeout:
					deferred_count = 0
					# Check if hardware MIDI ports changed, e.g. USB inserted/removed
					hw_devs = jclient.get_ports(is_midi=True, is_physical=True)
					if last_hw_devs != hw_devs:
						last_hw_devs = hw_devs
						do_midi = True
					# Check if connection to host USB changed
					hms = is_host_usb_connected()
					if host_usb_connected != hms:
						host_usb_connected = hms
						do_midi = True
					# Check if requested to run midi connect (slow)
					if deferred_midi_connect:
						do_midi = True
					# Check if requested to run audio connect (slow)
					if deferred_audio_connect:
						do_audio = True

				if do_midi:
					midi_autoconnect()
					do_midi = False

				if do_audio:
					audio_autoconnect()
					do_audio = False

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

	global refresh_time, exit_flag, jclient, aclient, thread, lock, chain_manager, state_manager
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
		logger.error(f"ZynAutoConnect ERROR: Can't connect with Jack Audio Server ({e})")
	
	try:
		aclient = alsa_midi.SequencerClient("Zynthian_autoconnect")
	except Exception as e:
		logger.error(f"ZynAutoConnect ERROR: Can't connect with ALSA ({e})")

	# Create Lock object (Mutex) to avoid concurrence problems
	lock = Lock()

	# Set aliases for static MIDI ports
	set_midi_port_alias("ZynMaster:midi_in", "ZynMaster:midi_in", "CV/Gate OUT") 
	set_midi_port_alias("ZynMaster:midi_out", "ZynMaster:midi_out", "CV/Gate IN") 
	
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

def pause():
	global paused_flag
	paused_flag = True

def resume():
	global paused_flag
	paused_flag = False

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

	if not state_manager.power_save_mode and not paused_flag:
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
