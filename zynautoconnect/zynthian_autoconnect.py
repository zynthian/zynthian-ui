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
	hw_out = jclient.get_ports(is_output=True, is_physical=True, is_midi=True)
	if len(hw_out) == 0:
		hw_out = []

	# List of physical MIDI destination ports
	hw_in = jclient.get_ports(is_input=True, is_physical=True, is_midi=True)
	if len(hw_in) == 0:
		hw_in = []

	# Treat Aubio as physical MIDI destination port
	if zynthian_gui_config.midi_aubionotes_enabled:
		aubio_out = jclient.get_ports("aubio", is_output=True, is_physical=False, is_midi=True)
		try:
			hw_out.append(aubio_out[0])
		except:
			pass

	# List of MIDI over IP destination ports
	nw_out = []
	for port_name in ("QmidiNet:in_1", "jackrtpmidid:rtpmidi_in", "RtMidiIn Client:TouchOSC Bridge"):
		nw_out += jclient.get_ports(port_name, is_midi=True, is_input=True)

	#logger.debug("Input Device Ports: {}".format(hw_out))
	#logger.debug("Output Device Ports: {}".format(hw_in))

	# Calculate hardware device fingerprint
	hw_str = ""
	for hw in hw_out:
		hw_str += hw.name + "\n"
	for hw in hw_in:
		hw_str += hw.name + "\n"

	# Only autoroute if forced or physica devices have changed
	if not force and hw_str == last_hw_str:
		release_lock() # Release Mutex Lock
		#logger.info("ZynAutoConnect: MIDI Shortened ...")
		return
	else:
		last_hw_str = hw_str

	# MIDI routing within chains - connects all MIDI ports within each chain
	# Also connects chain inputs and outputs
	#TODO: Handle processors with multiple MIDI ports
	for chain_id, chain in chain_manager.chains.items():
		routes = chain_manager.get_chain_midi_routing(chain_id)
		for dst_name in routes:
			dst_ports = jclient.get_ports(dst_name, is_input=True, is_midi=True)
			cur_dests = {} # List of currently routed source ports, indexed by destination port name
			for port in dst_ports:
				cur_dests[port.name] = jclient.get_all_connections(port)
		
			for src_name in routes[dst_name]:
				src_ports = jclient.get_ports(src_name, is_output=True, is_midi=True)
				try:
					src = src_ports[0]
					dst = dst_ports[0]
					if dst.name in cur_dests and src in cur_dests[dst.name]:
						# Already routed
						cur_dests[dst.name].remove(src)
					else:
						jclient.connect(src, dst)
				except Exception as e:
					pass
		
			# Disconnect unused routes
			for dst in cur_dests:
				for src in cur_dests[dst]:
					try:
						jclient.disconnect(src, dst) #TODO: Disconnecting chain output - should be done later
					except Exception as e:
						logging.warning("Failed to disconnect MIDI %s from %s - %s", src, dst, e)

		# Chain outputs - connects each chain's end MIDI outputs to configured destinations
		#TODO: This should be conslidate in chain routing because chain already does this
		if chain.midi_slots and chain.midi_thru:
			dests = []
			for out in chain.midi_out:
				if out == "MIDI-OUT":
					dests += hw_out
				elif out == "NET-OUT":
					dests += nw_out
				elif out in chain_manager.chains:
					for processor in chain_manager.get_processors(out, "MIDI Tool", 0):
						try:
							dests += jclient.get_ports(processor.get_jackname(), is_midi=True, is_input=True)
						except:
							pass
				else:
					dests += jclient.get_ports(out, is_midi=True, is_input=True)
			for processor in chain.midi_slots[-1]:
				src_port = jclient.get_ports(processor.get_jackname(), is_midi=True, is_output=True)[0]
				cur_dests = jclient.get_all_connections(src_port)
				#TODO: This only uses first port
				for dst in dests:
					if dst not in cur_dests:
						try:
							jclient.connect(src_port, dst)
						except:
							pass
					else:
						cur_dests.remove(dst)
				for dst in cur_dests:
					try:
						jclient.disconnect(src_port, dst)
					except:
						pass

	# Disconnect unexpected inter-chain connections
	for chain_id, chain in chain_manager.chains.items():
		unexpected_chains = []
		for id in chain_manager.chains:
			if id not in chain.midi_out:
				unexpected_chains.append(id)
		for id in unexpected_chains:
			for dst_proc in chain_manager.get_processors(id, "MIDI Tool", 0):
				for src_proc in chain.get_processors("MIDI Tool", chain.get_slot_count("MIDI Tool") - 1):
					try:
						src_port = jclient.get_ports(src_proc.get_jackname(), is_midi=True, is_output=True)[0]
						dst_port = jclient.get_ports(dst_proc.get_jackname(), is_midi=True, is_input=True)[0]
						jclient.disconnect(src_port, dst_port)
					except:
						pass

	#TODO Feedback ports

	#Get Zynthian Midi Router MIDI ports
	zmr_out = OrderedDict()
	for p in jclient.get_ports("ZynMidiRouter", is_output=True, is_midi=True):
		zmr_out[p.shortname] = p
	zmr_in = OrderedDict()
	for p in jclient.get_ports("ZynMidiRouter", is_input=True, is_midi=True):
		zmr_in[p.shortname] = p

	#------------------------------------
	# Build MIDI-input routed ports dict
	#------------------------------------

	# Add engines_in
	routed_in = {}

	# Add Zynmaster input
	zmip = jclient.get_ports("ZynMaster:midi_in", is_input=True, is_physical=False, is_midi=True)
	try:
		port_alias_id = get_port_alias_id(zmip[0])
		enabled_hw_ports = { port_alias_id: zmip[0] }
		routed_in["MIDI-OUT"] = [zmip[0]]
	except:
		enabled_hw_ports = {}
		routed_in["MIDI-OUT"] = []

	# Add enabled Hardware ports 
	for hwp in hw_in:
		try:
			port_alias_id = get_port_alias_id(hwp)
			if port_alias_id in zynthian_gui_config.enabled_midi_out_ports:
				enabled_hw_ports[port_alias_id] = hwp
				routed_in["MIDI-OUT"].append(hwp)
		except:
			pass

	# Add enabled Network ports
	enabled_nw_ports = {}
	routed_in["NET-OUT"] = []
	for nwp in ("QmidiNet:in_1", "jackrtpmidid:rtpmidi_in", "RtMidiIn Client:TouchOSC Bridge"):
		zmip = jclient.get_ports(nwp, is_input=True, is_physical=False, is_midi=True)
		try:
			port_alias_id = get_port_alias_id(zmip[0])
			if port_alias_id in zynthian_gui_config.enabled_midi_out_ports:
				enabled_nw_ports[port_alias_id] = zmip[0]
				routed_in["NET-OUT"].append(zmip[0])
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
			jclient.connect("QmidiNet:out_1", zmr_in['net_in'])
		except:
			pass

	#Connect TouchOSC output to ZynMidiRouter:net_in
	if zynthian_gui_config.midi_touchosc_enabled:
		try:
			jclient.connect("RtMidiOut Client:TouchOSC Bridge", zmr_in['net_in'])
		except:
			pass

	#Connect zynseq (stepseq) output to ZynMidiRouter:step_in
	try:
		jclient.connect("zynseq:output", zmr_in['step_in'])
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
	"""TODO
	try:
		for efbp in engines_fb:
			jclient.connect(efbp,zmr_in['ctrl_in'])
	except:
		pass
	"""

	#logger.debug("Connecting ZynMidiRouter to engines ...")

	# Set "Drop Program Change" flag for each MIDI chan
	for processor in chain_manager.get_processors():
		if processor.midi_chan is not None and processor.midi_chan < 16:
			lib_zyncore.zmop_chain_set_flag_droppc(processor.midi_chan, int(processor.engine.options['drop_pc']))

	# When "Send All MIDI to Output" is enabled, zynseq & zynsmf are routed thru ZynMidiRouter:midi_out
	if zynthian_gui_config.midi_filter_output:

		# ... enabled Hardware MIDI Output Ports
		for paid, hwport in enabled_hw_ports.items():
			# Connect ZynMidiRouter:midi_out to ...
			try:
				jclient.connect(zmr_out['midi_out'], hwport)
			except:
				pass
			# Disconnect zynseq (stepseq) output from ...
			try:
				jclient.disconnect("zynseq:output", hwport)
			except:
				pass
			#Disconnect zynsmf output from ...
			try:
				jclient.disconnect("zynsmf:midi_out", hwport)
			except:
				pass

		# ... enabled Network MIDI Output Ports
		for paid, nwport in enabled_nw_ports.items():
			# Connect ZynMidiRouter:net_out to ...
			try:
				jclient.connect(zmr_out['net_out'], nwport)
			except:
				pass
			# Disconnect zynseq (stepseq) output from ...
			try:
				jclient.disconnect("zynseq:output", nwport)
			except:
				pass
			#Disconnect zynsmf output from ...
			try:
				jclient.disconnect("zynsmf:midi_out", nwport)
			except:
				pass

	# When "Send All MIDI to Output" is disabled, zynseq & zynsmf are routed directly
	else:

		# ... enabled Hardware MIDI Output Ports
		for paid, hwport in enabled_hw_ports.items():
			# Disconnect ZynMidiRouter:midi_out from ...
			try:
				jclient.disconnect(zmr_out['midi_out'], hwport)
			except:
				pass
			# Connect zynseq (stepseq) output to ...
			try:
				jclient.connect("zynseq:output", hwport)
			except:
				pass
			# Connect zynsmf output to ...
			try:
				jclient.connect("zynsmf:midi_out", hwport)
			except:
				pass

		# ... enabled Network MIDI Output Ports
		for paid, nwport in enabled_nw_ports.items():
			# Disconnect ZynMidiRouter:net_out from ...
			try:
				jclient.disconnect(zmr_out['net_out'], nwport)
			except:
				pass
			# Connect zynseq (stepseq) output to ...
			try:
				jclient.connect("zynseq:output", nwport)
			except:
				pass
			# Connect zynsmf output to ...
			try:
				jclient.connect("zynsmf:midi_out", nwport)
			except:
				pass



	#Connect ZynMidiRouter:step_out to ZynthStep input
	try:
		jclient.connect(zmr_out['step_out'], "zynseq:input")
	except:
		pass

	#Connect ZynMidiRouter:ctrl_out to enabled MIDI-FB ports (MIDI-Controller FeedBack)
	for hw in hw_in:
		try:
			if get_port_alias_id(hw) in zynthian_gui_config.enabled_midi_fb_ports:
				jclient.connect(zmr_out['ctrl_out'], hw)
			else:
				jclient.disconnect(zmr_out['ctrl_out'], hw)
		except:
			pass

	# Disconnect hardware inputs from mod-ui
	for sport in hw_out:
		try:
			jclient.disconnect(sport, 'mod-host:midi_in')
		except:
			pass


	#Release Mutex Lock
	release_lock()


def audio_autoconnect(force=False):
	if not force:
		#logger.debug("ZynAutoConnect: Audio Escaped ...")
		return

	#Get Mutex Lock
	#logger.info("Acquiring lock ...")
	acquire_lock()
	#logger.info("Lock acquired!!")

	#Get Audio Input Ports (ports receiving audio => inputs => you write on it!!)
	input_ports = get_audio_input_ports(True)

	# Get System Playback Ports
	system_playback_ports = jclient.get_ports("system:playback", is_input=True, is_audio=True, is_physical=True)

	#Get Zynmixer Playback Ports
	zynmixer_playback_ports = jclient.get_ports("zynmixer", is_input=True, is_audio=True, is_physical=False)
	
	#Get Zynmixer Playback Ports
	playback_ports = zynmixer_playback_ports + system_playback_ports

	# Disconnect mod-ui from System Output
	mon_out = jclient.get_ports("mod-monitor", is_output=True, is_audio=True)
	try:
		jclient.disconnect(mon_out[0], 'system:playback_1')
		jclient.disconnect(mon_out[1], 'system:playback_2')
	except:
		pass

	# Chain audio routing
	for chain_id in chain_manager.chains:
		routes = chain_manager.get_chain_audio_routing(chain_id)
		if "zynmixer:return" in routes and "zynmixer:send" in routes["zynmixer:return"]:
			routes["zynmixer:return"].remove("zynmixer:send")
		for dest in routes:
			dst_ports = jclient.get_ports(dest, is_input=True, is_audio=True)
			dest_count = len(dst_ports)
			cur_dests = {}
			for port in dst_ports:
				cur_dests[port.name] = jclient.get_all_connections(port)

			for src_name in routes[dest]:
				src_ports = jclient.get_ports(src_name, is_output=True, is_audio=True)
				source_count = len(src_ports)
				if source_count and dest_count:
					for i in range(max(source_count, dest_count)):
						try:
							src = src_ports[min(i, source_count - 1)]
							dst = dst_ports[min(i, dest_count - 1)]
							if dst.name in cur_dests and src in cur_dests[dst.name]:
								cur_dests[dst.name].remove(src)
							else:
								jclient.connect(src, dst)
						except Exception as e:
							logging.warning("Failed to connect audio %s to %s - %s", src, dst, e)
		
			# Disconnect unused routes
			for dst in cur_dests:
				for src in cur_dests[dst]:
					try:
						jclient.disconnect(src, dst)
					except Exception as e:
						logging.warning("Failed to disconnect audio %s from %s - %s", src, dst, e)

	# Clear unused mixer inputs
	for chan in range(16):
		if chain_manager.midi_chan_2_chain[chan] is None:
			for dst in jclient.get_ports("zynmixer:input_{:02d}".format(chan + 1)):
				for src in jclient.get_all_connections(dst):
					jclient.disconnect(src, dst)

	# Connect metronome to aux
	try:
		jclient.connect("zynseq:metronome", "zynmixer:input_17a")
		jclient.connect("zynseq:metronome", "zynmixer:input_17b")
	except:
		pass

	# Connect mixer to the System Output
	try:
		#TODO: Support configurable output routing
		jclient.connect("zynmixer:output_a", system_playback_ports[0])
		jclient.connect("zynmixer:output_b", system_playback_ports[1])
	except:
		pass

	# Replicate System Output connections to Headphones
	hp_ports = jclient.get_ports("Headphones:playback", is_input=True, is_audio=True)
	if len(hp_ports)>=2:
		replicate_connections_to(system_playback_ports[0], hp_ports[0])
		replicate_connections_to(system_playback_ports[1], hp_ports[1])

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
				try:
					jclient.connect(scp, aubio_in[j % nip])
				except:
					pass
				j += 1

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
				aout_ports += ["zynmixer:input_{:02d}a".format(layer.midi_chan + 1), "zynmixer:input_{:02d}b".format(layer.midi_chan + 1)]
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
	lock.release()


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
