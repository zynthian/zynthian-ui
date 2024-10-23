# -*- coding: utf-8 -*-
# ********************************************************************
# ZYNTHIAN PROJECT: Zynthian Autoconnector
#
# Autoconnect Jack clients
#
# Copyright (C) 2015-2024 Fernando Moyano <jofemodo@zynthian.org>
#
# ********************************************************************
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
# ********************************************************************

import os
import re
import usb
import jack
import logging
import json
from time import sleep
from threading import Thread, Lock

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore
from zyngui import zynthian_gui_config
import zynconf

# -------------------------------------------------------------------------------
# Configure logging
# -------------------------------------------------------------------------------

log_level = int(os.environ.get('ZYNTHIAN_LOG_LEVEL', logging.WARNING))

logger = logging.getLogger(__name__)
logger.setLevel(log_level)

# if log_level==logging.DEBUG:
# import inspect

# -------------------------------------------------------------------------------
# Fake port class
# -------------------------------------------------------------------------------


class fake_port:
    def __init__(self, name):
        self.name = name
        self.short_name = name
        self.aliases = [name, name]

    def set_alias(self, alias):
        pass

    def unset_alias(self, alias):
        pass


# -------------------------------------------------------------------------------
# Define some Constants and Global Variables
# -------------------------------------------------------------------------------

MAIN_MIX_CHAN = 17 				# TODO: Get this from mixer

jclient = None					# JACK client
thread = None					# Thread to check for changed MIDI ports
lock = None						# Manage concurrence
exit_flag = False				# True to exit thread
paused_flag = False				# True id autoconnect task is paused
state_manager = None			# State Manager object
chain_manager = None			# Chain Manager object
xruns = 0						# Quantity of xruns since startup or last reset
# True to perform MIDI connect on next port check cycle
deferred_midi_connect = False
# True to perform audio connect on next port check cycle
deferred_audio_connect = False
# List of hardware MIDI  source ports (including network, aubionotes, etc.)
hw_midi_src_ports = []
# List of hardware MIDI destination ports (including network, aubionotes, etc.)
hw_midi_dst_ports = []
hw_audio_dst_ports = []			# List of physical audio output ports
# Map of all audio target port names to use as sidechain inputs, indexed by jack client regex
sidechain_map = {}
# List of currently active audio destination port names not to autoroute, e.g. sidechain inputs
sidechain_ports = []

# These variables are initialized in the init() function. These are "example values".
max_num_devs = 16     			# Max number of MIDI devices
max_num_chains = 16  		 	# Max number of chains
devices_in = []       			# List of MIDI input devices
devices_in_mode = []  			# List of MIDI input devices modes
devices_out = []      			# List of MIDI output devices
devices_out_name = []           # List of MIDI output devices names

# zyn_routed_* are used to avoid changing routes made by other jack clients
# Map of lists of audio sources routed by zynautoconnect, indexed by destination
zyn_routed_audio = {}
# Map of lists of MIDI sources routed by zynautoconnect, indexed by destination
zyn_routed_midi = {}

# Processors sending control feedback (connected to zynmidirouter:ctrl_in)
ctrl_fb_procs = []

# Map of user friendly names indexed by device uid (alias[0])
midi_port_names = {}

# ------------------------------------------------------------------------------

# MIDI port helper functions


def get_port_friendly_name(uid):
    """Get port friendly name

    uid : Port uid (alias 2)
    returns : Friendly name or None if not set
    """

    if uid in midi_port_names:
        return midi_port_names[uid]
    return None


def set_port_friendly_name(port, friendly_name=None):
    """Set the friendly name for a JACK port

    port : JACK port object
    friendly_name : New friendly name (optional) Default:Reset to ALSA name 
    """

    global midi_port_names

    if len(port.aliases) < 1:
        return

    try:
        alias1 = port.aliases[0]
        if friendly_name is None:
            # Reset name
            if alias1 in midi_port_names:
                midi_port_names.pop(alias1)
            alias1, friendly_name = build_midi_port_name(port)
        else:
            midi_port_names[alias1] = friendly_name
        while len(port.aliases) > 1:
            port.unset_alias(port.aliases[1])
        port.set_alias(friendly_name)
    except:
        pass


def get_ports(name, is_input=None):
    return jclient.get_ports(name, is_input=is_input)


def dev_in_2_dev_out(zmip):
    """Get index of output devices from its input device index

    zmip : Input port index
    returns : Output port index or None if not found
    """

    try:
        name = devices_in[zmip].aliases[0].replace("IN", "OUT")
        for i, port in enumerate(devices_out):
            if port.aliases[0] == name:
                return i
    except:
        return None


def set_midi_port_names(port_names):
    """Set port friendly names from map

    port_names - Map of friendly names indexed by uid
    """

    global midi_port_names
    midi_port_names = port_names.copy()
    for port in hw_midi_src_ports + hw_midi_dst_ports:
        try:
            port.aliases[1] = port_names[port.aliases[0]]
        except:
            pass


def get_port_aliases(midi_port):
    """Get port alias for a MIDI port

    midi_port : Jack MIDI port
    returns : List of aliases or port name if alias not set
    """

    try:
        return midi_port.aliases[0], midi_port.aliases[1]
    except:
        return midi_port.name, midi_port.name


def get_port_from_name(name):
    """Get a JACK port from its name

    name : Port name
    returns : JACK port or None if not found
    """

    try:
        return jclient.get_port_by_name(name)
    except:
        return None


def get_midi_in_uid(idev):
    """Get the UID of an input port
    idev - Index of ZMIP port
    returns - Port UID (aliases[0]) or None if not connected
    """

    try:
        return devices_in[idev].aliases[0]
    except:
        return None


def get_midi_in_devid(idev):
    """Get the ALSA name of the port connected to ZMIP port

    idev : Index of ZMIP port
    returns : ALSA name or None if not found
    """

    try:
        return devices_in[idev].aliases[0].split('/', 1)[1]
    except:
        return None


def get_midi_out_dev(idev):
    """Get the jack port connected from ZMOP port

    idev : Index of ZMOP port
    returns : Jack port or None if not found
    """

    try:
        return devices_out[idev]
    except:
        return None


def get_midi_in_devid_by_uid(uid, mapped=False):
    """Get the index of the ZMIP connected to physical input

    uid : The uid name of the port (jack alias [0])
    mapped : True to use physical port mapping
    """

    for i, port in enumerate(devices_in):
        try:
            if mapped:
                if port.aliases[0] == uid:
                    return i
            else:
                uid_parts = uid.split('/', 1)
                if len(uid_parts) > 1:
                    if uid_parts[1] == port.aliases[0].split('/', 1)[1]:
                        return i
                elif port.aliases[0] == uid:
                    return i
        except:
            pass
    return None


def get_midi_in_dev_mode(idev):
    """Get mode for a midi input device

    returns: mode (1=ACTI, 0=MULTI, None if idev out of range)
    """
    if 0 <= idev < len(devices_in_mode):
        return devices_in_mode[idev]
    else:
        return None


def update_midi_in_dev_mode(idev):
    """Update mode cache for a midi input device

    idev : midi input device index
    """
    if 0 <= idev < len(devices_in_mode):
        devices_in_mode[idev] = lib_zyncore.zmip_get_flag_active_chain(idev)


def update_midi_in_dev_mode_all():
    """Update mode cache for all midi input devices"""

    for idev in range(len(devices_in_mode)):
        devices_in_mode[idev] = lib_zyncore.zmip_get_flag_active_chain(idev)


def reset_midi_in_dev_all():
    """Set all MIDI input devices to Active Chain mode and route to all chains"""

    for zmip in range(len(devices_in_mode)):
        lib_zyncore.zmip_set_flag_active_chain(zmip, 1)
        devices_in_mode[zmip] = 1
        for zmop in range(16):
            lib_zyncore.zmop_set_route_from(zmop, zmip, 1)


# ------------------------------------------------------------------------------
# Audio port helpers

def add_sidechain_ports(jackname):
    """Add ports that should be treated as sidechain inputs

    jackname : Jack client name of processor
    """

    client_name = jackname[:-3]
    if client_name in sidechain_map:
        for port_name in sidechain_map[client_name]:
            if f"{jackname}:{port_name}" not in sidechain_ports:
                sidechain_ports.append(f"{jackname}:{port_name}")


def remove_sidechain_ports(jackname):
    """Removes ports that are treated as sidechain inputs

    jackname : Jack client name of processor"""

    if not jackname:
        return
    client_name = jackname[:-3]
    if client_name in sidechain_map:
        for port_name in sidechain_map[client_name]:
            try:
                sidechain_ports.remove(f"{jackname}:{port_name}")
            except:
                pass


def get_sidechain_portnames(jackname=None):
    """Get list of sidechain input port names for a given jack client

    jackname : Name of jack client (Default: Get sidechain inputs for all processors)
    returns : List of jack port names
    """

    if jackname is None:
        return sidechain_ports.copy()
    result = []
    for portname in sidechain_ports:
        try:
            if portname.split(':')[0] == jackname:
                result.append(portname)
        except:
            pass
    return result


# ------------------------------------------------------------------------------


def request_audio_connect(fast=False):
    """Request audio connection graph refresh

    fast : True for fast update (default=False to trigger on next 2s cycle
    """

    # if paused_flag:
    # return
    if fast:
        audio_autoconnect()
    else:
        global deferred_audio_connect
        deferred_audio_connect = True


def request_midi_connect(fast=False):
    """Request MIDI connection graph refresh

    fast : True for fast update (default=False to trigger on next 2s cycle
    """

    # if paused_flag:
    # return
    if fast:
        update_hw_midi_ports()
        midi_autoconnect()
    else:
        global deferred_midi_connect
        deferred_midi_connect = True


def find_usb_gadget_device():
    for devid in ["fe980000", "1000480000"]:
        if os.path.isdir(f"/sys/bus/platform/devices/{devid}.usb/gadget.0"):
            return devid
    return None


def is_host_usb_connected():
    """Check if the USB host (e.g. USB-Type B connection) is connected

    returns : True if connected to USB host (not necessarily a MIDI port!)
    """

    usb_gadget_devid = find_usb_gadget_device()
    if usb_gadget_devid:
        try:
            with open(f"/sys/bus/platform/devices/{usb_gadget_devid}.usb/udc/{usb_gadget_devid}.usb/state") as f:
                if f.read() != "configured\n":
                    return False
            with open(f"/sys/class/udc/{usb_gadget_devid}.usb/device/gadget.0/suspended") as f:
                if f.read() == "1\n":
                    return False
        except:
            return False
        return True
    return False


def add_hw_port(port):
    """Add a hardware port to the global list

    port - Jack port object to add
    returns - True if added, i.e. list has changed
    """

    global hw_midi_src_ports, hw_midi_dst_ports
    if port.is_input and port not in hw_midi_dst_ports:
        hw_midi_dst_ports.append(port)
        return True
    elif port.is_output and port not in hw_midi_src_ports:
        hw_midi_src_ports.append(port)
        return True
    return False


def remove_hw_port(port):
    """Remove a hardware port from the global list

    port - Jack port object to remove
    returns - True if removed, i.e. list has changed
    """

    global hw_midi_src_ports, hw_midi_dst_ports
    if port.is_input and port in hw_midi_dst_ports:
        hw_midi_dst_ports.remove(port)
        return True
    elif port.is_output and port in hw_midi_src_ports:
        hw_midi_src_ports.remove(port)
        return True
    return False


def update_hw_midi_ports(force=False):
    """Update lists of external (hardware) source and destination MIDI ports

    force - True to force update of port names / aliases
    returns - True if changed since last call
    """

    # Get Mutex Lock
    if not acquire_lock():
        return

    global hw_midi_src_ports, hw_midi_dst_ports

    # -----------------------------------------------------------
    # Get Input/Output MIDI Ports:
    #  - sources including physical inputs are jack outputs
    #  - destinations including physical outputs are jack inputs
    # -----------------------------------------------------------

    hw_port_fingerprint = hw_midi_src_ports + hw_midi_dst_ports

    # List of physical MIDI source ports
    hw_midi_src_ports = jclient.get_ports(
        is_output=True, is_physical=True, is_midi=True)

    # List of physical MIDI destination ports
    hw_midi_dst_ports = jclient.get_ports(
        is_input=True, is_physical=True, is_midi=True)

    # Treat some virtual MIDI ports as hardware
    for port_name in ("QmidiNet:in", "jackrtpmidid:rtpmidi_in", "jacknetumpd:netump_in", "RtMidiIn Client:TouchOSC Bridge", "ZynMaster:midi_in", "ZynMidiRouter:seq_in"):
        try:
            ports = jclient.get_ports(port_name, is_midi=True, is_input=True)
            hw_midi_dst_ports += ports
        except:
            pass
    for port_name in ("QmidiNet:out", "jackrtpmidid:rtpmidi_out", "jacknetumpd:netump_out", "RtMidiOut Client:TouchOSC Bridge", "aubio"):
        try:
            ports = jclient.get_ports(port_name, is_midi=True, is_output=True)
            hw_midi_src_ports += ports
        except:
            pass

    update = False
    host_usb_connected = is_host_usb_connected()
    fingerprint = hw_port_fingerprint.copy()
    for port in hw_midi_src_ports + hw_midi_dst_ports:
        if port.name.startswith("a2j:Midi Through"):
            remove_hw_port(port)
        elif len(port.aliases) > 0 and port.aliases[0].startswith("USB:f_midi") and not host_usb_connected:
            remove_hw_port(port)
        elif port not in hw_port_fingerprint or force:
            update_midi_port_aliases(port)
            update = True
        else:
            fingerprint.remove(port)
    update |= len(fingerprint) != 0

    release_lock()
    return update


def midi_autoconnect():
    """Connect all expected MIDI routes"""

    # Get Mutex Lock
    if not acquire_lock():
        return

    global deferred_midi_connect
    deferred_midi_connect = False

    # logger.info("ZynAutoConnect: MIDI ...")
    global zyn_routed_midi

    # Create graph of required chain routes as sets of sources indexed by destination
    required_routes = {}
    all_midi_dst = jclient.get_ports(is_input=True, is_midi=True)
    for dst in all_midi_dst:
        required_routes[dst.name] = set()

    # Connect MIDI Input Devices to ZynMidiRouter ports (zmips)
    busy_idevs = []
    for hwsp in hw_midi_src_ports:
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
                    logger.debug(
                        f"Connected MIDI-in device {devnum}: {hwsp.name}")
                    break
        if devnum is not None:
            required_routes[f"ZynMidiRouter:dev{devnum}_in"].add(hwsp.name)
            busy_idevs.append(devnum)

    # Delete disconnected input devices from list and unload driver
    for i in range(0, max_num_devs):
        if i not in busy_idevs and devices_in[i] is not None:
            logger.debug(
                f"Disconnected MIDI-in device {i}: {devices_in[i].name}")
            devices_in[i] = None
            state_manager.ctrldev_manager.unload_driver(i)

    # Connect MIDI Output Devices
    busy_odevs = []
    for hwdp in hw_midi_dst_ports:
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
                    devices_out_name[devnum] = hwdp.aliases[0]
                    logger.debug(
                        f"Connected MIDI-out device {devnum}: {hwdp.name}")
                    break
        if devnum is not None:
            required_routes[hwdp.name].add(f"ZynMidiRouter:dev{devnum}_out")
            busy_odevs.append(devnum)

    # Delete disconnected output devices from list
    for i in range(0, max_num_devs):
        if i not in busy_odevs and devices_out[i] is not None:
            logger.debug(
                f"Disconnected MIDI-out device {i}: {devices_out[i].name}")
            devices_out[i] = None
            devices_out_name[i] = None

    # Chain MIDI routing
    # TODO: Handle processors with multiple MIDI ports
    for chain_id, chain in chain_manager.chains.items():
        # Add chain internal routes
        routes = chain_manager.get_chain_midi_routing(chain_id)
        for dst in list(routes):
            if isinstance(dst, int):
                # Destination is a chain
                route = routes.pop(dst)
                dst_chain = chain_manager.get_chain(dst)
                if dst_chain:
                    if dst_chain.midi_slots:
                        for proc in dst_chain.midi_slots[0]:
                            routes[proc.engine.get_jackname()] = route
                    elif dst_chain.synth_slots:
                        proc = dst_chain.synth_slots[0][0]
                        routes[proc.engine.get_jackname()] = route

        for dst_name in routes:
            dst_ports = jclient.get_ports(
                re.escape(dst_name), is_input=True, is_midi=True)
            if not dst_ports:
                # Try to get destiny port by alias
                try:
                    dst_ports = [jclient.get_port_by_name(dst_name)]
                except:
                    pass
            if dst_ports:
                for src_name in routes[dst_name]:
                    src_ports = jclient.get_ports(
                        src_name, is_output=True, is_midi=True)
                    if src_ports:
                        required_routes[dst_ports[0].name].add(
                            src_ports[0].name)

        # Add chain MIDI outputs
        if chain.midi_slots and chain.midi_thru:
            dests = []
            for out in chain.midi_out:
                if out in chain_manager.chains:
                    chain_midi_first_procs = chain_manager.get_processors(
                        out, "MIDI Tool", 0)
                    if not chain_midi_first_procs:
                        chain_midi_first_procs = chain_manager.get_processors(
                            out, "Synth", 0)
                    for processor in chain_midi_first_procs:
                        for dst in jclient.get_ports(processor.get_jackname(True), is_midi=True, is_input=True):
                            dests.append(dst.name)
                else:
                    pass
                    # dests.append(out)
            for processor in chain.midi_slots[-1]:
                src_ports = jclient.get_ports(processor.get_jackname(True), is_midi=True, is_output=True)
                if src_ports:
                    for dst in dests:
                        required_routes[dst].add(src_ports[0].name)

        # Add MIDI router outputs
        if chain.is_midi():
            src_ports = jclient.get_ports(
                f"ZynMidiRouter:ch{chain.zmop_index}_out", is_midi=True, is_output=True)
            if src_ports:
                for dst_proc in chain.get_processors(slot=0):
                    dst_ports = jclient.get_ports(
                        dst_proc.get_jackname(True), is_midi=True, is_input=True)
                    if dst_ports:
                        src = src_ports[0]
                        dst = dst_ports[0]
                        required_routes[dst.name].add(src.name)

    # Add zynseq to MIDI input devices
    idev = state_manager.get_zmip_step_index()
    if devices_in[idev] is None:
        src_ports = jclient.get_ports(
            "zynseq:output", is_midi=True, is_output=True)
        if src_ports:
            devices_in[idev] = src_ports[0]
            update_midi_port_aliases(src_ports[0])
    # Connect zynseq output to ZynMidiRouter:step_in
    required_routes["ZynMidiRouter:step_in"].add("zynseq:output")

    # Add SMF player to MIDI input devices
    idev = state_manager.get_zmip_seq_index()
    if devices_in[idev] is None:
        src_ports = jclient.get_ports(
            "zynsmf:midi_out", is_midi=True, is_output=True)
        if src_ports:
            devices_in[idev] = src_ports[0]
            update_midi_port_aliases(src_ports[0])
    # Connect zynsmf output to ZynMidiRouter:seq_in
    required_routes["ZynMidiRouter:seq_in"].add("zynsmf:midi_out")

    # Connect chain's MIDI output to zynsmf input => Implement chain selection to record from zynsmf?
    for i in range(max_num_chains):
        required_routes["zynsmf:midi_in"].add(f"ZynMidiRouter:ch{i}_out")

    # Add CV/Gate to MIDI input devices
    idev = state_manager.get_zmip_int_index()
    if devices_in[idev] is None:
        devices_in[idev] = fake_port("CV/Gate")

    # Add engine's controller-feedback to ZynMidiRouter:ctrl_in
    # Each engine sending controller feedback should use a different zmip
    # Only setBfree is using this, so we have just one: "ctrl_in"
    for proc in chain_manager.processors.values():
        if proc.engine.options["ctrl_fb"]:
            try:
                ports = jclient.get_ports(proc.get_jackname(
                    True), is_midi=True, is_output=True)
                required_routes["ZynMidiRouter:ctrl_in"].add(ports[0].name)
                ctrl_fb_procs.append(proc)
                # logging.debug(f"Routed controller feedback from {proc.get_jackname(True)}")
            except Exception as e:
                # logging.error(f"Can't route controller feedback from {proc.get_name()} => {e}")
                pass

    # Remove from control feedback list those processors removed from chains
    for i, proc in enumerate(ctrl_fb_procs):
        if proc.id not in chain_manager.processors:
            del ctrl_fb_procs[i]

    # Connect ZynMidiRouter:step_out to ZynthStep input
    required_routes["zynseq:input"].add("ZynMidiRouter:step_out")

    # Connect ZynMidiRouter:ctrl_out to enabled MIDI-FB ports (MIDI-Controller FeedBack)
    # TODO => We need a new mechanism for this!! Or simply use the ctrldev drivers
    # for port in hw_midi_dst_ports:
    # if get_port_aliases(port)[0] in zynthian_gui_config.enabled_midi_fb_ports:
    # required_routes[port.name].add("ZynMidiRouter:ctrl_out")

    # Remove mod-ui routes
    for dst in list(required_routes.keys()):
        if dst.startswith("effect_"):
            required_routes.pop(dst)
    # Workaround for mod-host auto routing
    try:
        port = jclient.get_port_by_name("mod-host:midi_in")
        current_routes = jclient.get_all_connections(port)
        for src in current_routes:
            if not src.name.startswith("ZynMidiRouter"):
                jclient.disconnect(src, port)
    except:
        pass

    # Connect and disconnect routes
    for dst, sources in required_routes.items():
        if dst not in zyn_routed_midi:
            zyn_routed_midi[dst] = []
        try:
            current_routes = jclient.get_all_connections(dst)
        except Exception as e:
            current_routes = []
            logging.warning(e)
        for src in current_routes:
            if src.name in sources:
                sources.remove(src.name)
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
                zyn_routed_midi[dst].append(src)
            except:
                pass

    # Load driver if driver has autoload flag set
    for i in range(0, max_num_devs):
        if i in busy_idevs and devices_in[i] is not None:
            state_manager.ctrldev_manager.load_driver(i)

    # Release Mutex Lock
    release_lock()


def audio_autoconnect():
    # Get Mutex Lock
    if not acquire_lock():
        return

    global deferred_audio_connect
    deferred_audio_connect = False

    # Workaround for mod-monitor auto routing
    for port in hw_audio_dst_ports:
        for i in range(1, 3):
            try:
                jclient.disconnect(f"mod-monitor:out_{i}", port)
            except:
                pass

    # Create graph of required chain routes as sets of sources indexed by destination
    required_routes = {}

    all_audio_dst = jclient.get_ports(is_input=True, is_audio=True)
    for dst in all_audio_dst:
        required_routes[dst.name] = set()

    # Chain audio routing
    for chain_id in chain_manager.chains:
        routes = chain_manager.get_chain_audio_routing(chain_id)
        normalise = 0 in chain_manager.chains[chain_id].audio_out and chain_manager.chains[0].fader_pos == 0 and len(
            chain_manager.chains[chain_id].audio_slots) == chain_manager.chains[chain_id].fader_pos
        state_manager.zynmixer.normalise(
            chain_manager.chains[chain_id].mixer_chan, normalise)
        for dst in list(routes):
            if isinstance(dst, int):
                # Destination is a chain
                route = routes.pop(dst)
                dst_chain = chain_manager.get_chain(dst)
                if dst_chain:
                    if dst_chain.audio_slots and dst_chain.fader_pos:
                        for proc in dst_chain.audio_slots[0]:
                            routes[proc.get_jackname()] = route
                    elif dst_chain.is_synth():
                        proc = dst_chain.synth_slots[0][0]
                        if proc.type == "Special":
                            routes[proc.get_jackname()] = route
                    else:
                        if dst == 0:
                            for name in list(route):
                                if name.startswith('zynmixer:output'):
                                    # Use mixer internal normalisation
                                    route.remove(name)
                        routes[f"zynmixer:input_{dst_chain.mixer_chan + 1:02d}"] = route
        for dst in routes:
            if dst in sidechain_ports:
                # This is an exact match so we do want to route exactly this
                dst_ports = jclient.get_ports(
                    f"^{dst}$", is_input=True, is_audio=True)
            else:
                # This may be a client name that will return all input ports, including side-chain inputs
                dst_ports = jclient.get_ports(
                    dst, is_input=True, is_audio=True)
                # Remove side-chain (no route) destinations
                for port in list(dst_ports):
                    if port.name in sidechain_ports:
                        dst_ports.remove(port)
            dst_count = len(dst_ports)

            for src_name in routes[dst]:
                src_ports = jclient.get_ports(
                    src_name, is_output=True, is_audio=True)
                # Auto mono/stereo routing
                source_count = len(src_ports)
                if source_count and dst_count:
                    for i in range(min(2, max(source_count, dst_count))):
                        src = src_ports[min(i, source_count - 1)]
                        dst = dst_ports[min(i, dst_count - 1)]
                        required_routes[dst.name].add(src.name)

    # Connect metronome to aux
    required_routes[f"zynmixer:input_{MAIN_MIX_CHAN}a"].add("zynseq:metronome")
    required_routes[f"zynmixer:input_{MAIN_MIX_CHAN}b"].add("zynseq:metronome")

    # Connect global audio player to aux
    if state_manager.audio_player and state_manager.audio_player.jackname:
        ports = jclient.get_ports(
            state_manager.audio_player.jackname, is_output=True, is_audio=True)
        required_routes[f"zynmixer:input_{MAIN_MIX_CHAN}a"].add(ports[0].name)
        required_routes[f"zynmixer:input_{MAIN_MIX_CHAN}b"].add(ports[1].name)

    # Connect inputs to aubionotes
    if zynthian_gui_config.midi_aubionotes_enabled:
        capture_ports = get_audio_capture_ports()
        for port in jclient.get_ports("aubio", is_input=True, is_audio=True):
            for i in state_manager.aubio_in:
                try:
                    required_routes[port.name].add(capture_ports[i - 1].name)
                except:
                    pass

    # Remove mod-ui routes
    for dst in list(required_routes.keys()):
        if dst.startswith("effect_"):
            required_routes.pop(dst)

    # Replicate main output to headphones
    hp_ports = jclient.get_ports(
        "Headphones:playback", is_input=True, is_audio=True)
    if len(hp_ports) >= 2:
        required_routes[hp_ports[0].name] = required_routes[hw_audio_dst_ports[0].name]
        required_routes[hp_ports[1].name] = required_routes[hw_audio_dst_ports[1].name]

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

    # Release Mutex Lock
    release_lock()


def get_hw_audio_dst_ports():
    return hw_audio_dst_ports


# Connect mixer to the ffmpeg recorder
def audio_connect_ffmpeg(timeout=2.0):
    t = 0
    while t < timeout:
        try:
            # TODO: Do we want post fader, post effects feed?
            jclient.connect(
                f"zynmixer:output_{MAIN_MIX_CHAN}a", "ffmpeg:input_1")
            jclient.connect(
                f"zynmixer:output_{MAIN_MIX_CHAN}b", "ffmpeg:input_2")
            return
        except:
            sleep(0.1)
            t += 0.1


def get_audio_capture_ports():
    """Get list of hardware audio inputs"""

    return jclient.get_ports("system", is_output=True, is_audio=True, is_physical=True)


def build_midi_port_name(port):
    """Get default uid and friendly name for a port

    port - Jack port object
    returns - Tuple (uid, name)
    """

    if port.name.startswith("ttymidi:MIDI"):
        return port.name, "DIN-5 MIDI"
    elif port.name.startswith("ZynMaster"):
        return port.name, "CV/Gate"
    elif port.name.startswith("zynseq"):
        return port.name, "Step-Sequencer"
    elif port.name.startswith("zynsmf"):
        return port.name, "MIDI player"
    elif port.name.startswith("ZynMidiRouter:seq_in"):
        return port.name, "Router Feedback"
    elif port.name.startswith("jacknetumpd:netump_"):
        return f"NET:ump_{port.name[19:]}", "NetUMP"
    elif port.name.startswith("jackrtpmidid:rtpmidi_"):
        return f"NET:rtp_{port.name[21:]}", "RTP MIDI"
    elif port.name.startswith("QmidiNet:"):
        return f"NET:qmidi_{port.name[9:]}", "QmidiNet"
    elif port.name.endswith(" Client:TouchOSC Bridge"):
        return f"NET:touchosc_{port.name.split()[0][6:]}", "TouchOSC"
    elif port.name.startswith("aubio:midi_out"):
        return f"AUBIO:in", "Audio\u2794MIDI"
    elif port.name.startswith("BLE_MIDI:"):
        return port.aliases[0], port.aliases[1]

    idx = 0

    if port.aliases and (port.aliases[0].startswith("in-hw-") or port.aliases[0].startswith("out-hw-")):
        # Uninitiated port
        try:
            # USB ports
            io, hw, card, slot, idx, port_name = port.aliases[0].split('-', 5)
            with open(f"/proc/asound/card{card}/midi0", "r") as f:
                config = f.readlines()
                port_name = config[0].strip()
                n_inputs = 0
                n_outputs = 0
                for line in config:
                    if line.startswith("Input"):
                        n_inputs += 1
                    elif line.startswith("Output"):
                        n_outputs += 1
            if port_name == "f_midi":
                port_name = "USB HOST"
                if port.is_output:
                    uid = "USB:f_midi OUT 1"
                else:
                    uid = "USB:f_midi IN 1"
            else:
                with open(f"/proc/asound/card{card}/usbbus", "r") as f:
                    usbbus = f.readline()
                tmp = re.findall(r'\d+', usbbus)
                bus = int(tmp[0])
                address = int(tmp[1])
                usb_port_nos = usb.core.find(
                    bus=bus, address=address).port_numbers
                uid = f"{bus}"
                for i in usb_port_nos:
                    uid += f".{i}"
                uid = f"USB:{uid}/{port_name}"
                if port.is_input and n_inputs > 1:
                    port_name = f"{port_name} {int(idx) + 1}"
                elif port.is_output and n_outputs > 1:
                    port_name = f"{port_name} {int(idx) + 1}"

        except:
            uid = port.name
        if port.is_input:
            uid += f" OUT {int(idx) + 1}"
        else:
            uid += f" IN {int(idx) + 1}"
        return uid, port_name
    elif len(port.aliases) > 1:
        return port.aliases[0], port.aliases[1]
    elif len(port.aliases) > 0:
        return port.aliases[0], port.shortname
    else:
        return port.name, port.shortname


def get_port_friendly_names():
    return midi_port_names


def update_midi_port_aliases(port):
    """Set the uid and friendly name of port in aliases 0 & 1

    port - JACK port object
    returns - True if port aliases have changed
    """

    try:
        alias1, alias2 = (build_midi_port_name(port))
        if len(port.aliases) == 2 and port.aliases[0] == alias1 and port.aliases[1] == alias2:
            return False

        # Clear current aliases - blunt!
        for alias in port.aliases:
            port.unset_alias(alias)

        # Set aliases
        port.set_alias(alias1)
        if alias1 in midi_port_names:  # User defined names
            port.set_alias(midi_port_names[alias1])
        else:
            if alias2:
                port.set_alias(alias2)
            else:
                port.set_alias(alias1)
    except:
        logging.warning(f"Unable to set alias for port {port.name}")
        return False
    return True


def autoconnect():
    """Connect expected routes and disconnect unexpected routes"""
    update_hw_midi_ports()
    midi_autoconnect()
    audio_autoconnect()


def get_hw_src_ports():
    return hw_midi_src_ports


def get_hw_dst_ports():
    return hw_midi_dst_ports


def auto_connect_thread():
    """Thread to run autoconnect, checking if physical (hardware) interfaces have changed, e.g. USB plug"""

    deferred_timeout = 2  # Period to run deferred connect (in seconds)
    # Delay between loop cycles (in seconds) - allows faster exit from thread
    deferred_inc = 0.1
    deferred_count = 5  # Run at startup
    do_audio = False
    do_midi = False

    while not exit_flag:
        if not paused_flag:
            try:
                if deferred_count > deferred_timeout:
                    deferred_count = 0
                    # Check if hardware MIDI ports changed, e.g. USB inserted/removed
                    if update_hw_midi_ports():
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

    # if log_level==logging.DEBUG:
    # calframe = inspect.getouterframes(inspect.currentframe(), 2)
    # logger.debug("Waiting for lock, requested from '{}'...".format(format(calframe[1][3])))
    try:
        lock.acquire()
    except:
        return False
    # logger.debug("... lock acquired!!")
    return True


def release_lock():
    """Release mutex lock"""

    # if log_level==logging.DEBUG:
    # calframe = inspect.getouterframes(inspect.currentframe(), 2)
    # logger.debug("Lock released from '{}'".format(calframe[1][3]))
    try:
        lock.release()
    except:
        logging.warning("Attempted to release unlocked mutex")


def init():
    global num_devs_in, num_devs_out, max_num_devs, max_num_chains
    global devices_in, devices_out, devices_out_name

    num_devs_in = state_manager.get_num_midi_devs_in()
    num_devs_out = state_manager.get_num_midi_devs_out()
    max_num_devs = state_manager.get_max_num_midi_devs()
    max_num_chains = state_manager.get_num_zmop_chains()

    logging.info(f"Initializing {num_devs_in} slots for MIDI input devices")
    while len(devices_in) < num_devs_in:
        devices_in.append(None)
    while len(devices_in_mode) < num_devs_in:
        devices_in_mode.append(None)
    logging.info(f"Initializing {num_devs_out} slots for MIDI output devices")
    while len(devices_out) < num_devs_out:
        devices_out.append(None)
        devices_out_name.append(None)

    update_midi_in_dev_mode_all()


def start(sm):
    """Initialise autoconnect and start MIDI port checker

    sm : State manager object
    """

    global exit_flag, jclient, thread, lock, chain_manager, state_manager, hw_audio_dst_ports, sidechain_map

    if jclient:
        return  # Already started

    exit_flag = False
    state_manager = sm
    chain_manager = sm.chain_manager

    try:
        jclient = jack.Client("Zynthian_autoconnect")
        jclient.set_xrun_callback(cb_jack_xrun)
        jclient.activate()
    except Exception as e:
        logger.error(
            f"ZynAutoConnect ERROR: Can't connect with Jack Audio Server ({e})")

    init()

    # Get System Playback Ports
    hw_audio_dst_ports = jclient.get_ports(
        "system:playback", is_input=True, is_audio=True, is_physical=True)

    try:
        with open(f"{zynconf.config_dir}/sidechain.json", "r") as file:
            sidechain_map = json.load(file)
    except Exception as e:
        logger.error(f"Cannot load sidechain map ({e})")

    # Create Lock object (Mutex) to avoid concurrence problems
    lock = Lock()

    # Start port change checking thread
    thread = Thread(target=auto_connect_thread, args=())
    thread.daemon = True  # thread dies with the program
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

    hw_audio_dst_ports = []

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
        logger.warning(
            f"Jack Audio XRUN! =>count: {xruns}, delay: {delayed_usecs}us")
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


# ------------------------------------------------------------------------------
