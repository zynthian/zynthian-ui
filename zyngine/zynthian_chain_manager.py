# -*- coding: utf-8 -*-
# ****************************************************************************
# ZYNTHIAN PROJECT: Zynthian Chain Manager (zynthian_chain_manager)
#
# zynthian chain manager
#
# Copyright (C) 2015-2024 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <riban@zynthian.org>
#
# ****************************************************************************
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
# ****************************************************************************

import logging

# Zynthian specific modules
import zynautoconnect
from zyncoder.zyncore import lib_zyncore

from zyngine import *
from zyngine import zynthian_lv2
from zyngine.zynthian_chain import *
from zyngine.zynthian_engine_jalv import *
from zyngine.zynthian_engine_pianoteq import *
from zyngine.zynthian_signal_manager import zynsigman
from zyngine.zynthian_processor import zynthian_processor
from zyngui import zynthian_gui_config

# ----------------------------------------------------------------------------
# Some variables & definitions
# ----------------------------------------------------------------------------

MAX_NUM_MIDI_CHANS = 16
# TODO: Get this from zynmixer
MAX_NUM_MIXER_CHANS = 16
# TODO: Get this from lib_zyncore
MAX_NUM_ZMOPS = 16
MAX_NUM_MIDI_DEVS = 24
ZMIP_CTRL_INDEX = 26
ZMIP_INT_INDEX = 27

engine2class = {
    "SL": zynthian_engine_sooperlooper,
    "ZY": zynthian_engine_zynaddsubfx,
    "FS": zynthian_engine_fluidsynth,
    "SF": zynthian_engine_sfizz,
    "LS": zynthian_engine_linuxsampler,
    "BF": zynthian_engine_setbfree,
    "AE": zynthian_engine_aeolus,
    "AP": zynthian_engine_audioplayer,
    'PD': zynthian_engine_puredata,
    'MD': zynthian_engine_modui,
    'JV': zynthian_engine_jalv,
    'PT': zynthian_engine_pianoteq,
    'IR': zynthian_engine_inet_radio
}

# ----------------------------------------------------------------------------
# Zynthian Chain Manager Class
# ----------------------------------------------------------------------------


class zynthian_chain_manager:

    # Subsignals are defined inside each module. Here we define chain_manager subsignals:
    SS_SET_ACTIVE_CHAIN = 1
    SS_MOVE_CHAIN = 2

    engine_info = None
    single_processor_engines = ["BF", "MD", "PT", "PD", "AE", "CS", "SL"]

    def __init__(self, state_manager):
        """ Create an instance of a chain manager

        Manages chains of audio and MIDI processors.
        Each chain consists of zero or more slots.
        Each slot may contain one or more processors.

        state_manager : State manager object
        """

        logging.info("Creating chain manager")

        self.state_manager = state_manager

        self.chains = {}  # Map of chain objects indexed by chain id
        self.ordered_chain_ids = []  # List of chain IDs in display order
        self.zyngine_counter = 0  # Appended to engine names for uniqueness
        self.zyngines = {}  # List of instantiated engines
        self.processors = {}  # Dictionary of processor objects indexed by UID
        self.active_chain_id = None  # Active chain id
        self.midi_chan_2_chain_ids = [list() for _ in range(MAX_NUM_MIDI_CHANS)]  # Chain IDs mapped by MIDI channel

        self.absolute_midi_cc_binding = {}  # Map of list of zctrls indexed by 24-bit ZMOP,CHAN,CC
        self.chain_midi_cc_binding = {}  # Map of list of zctrls indexed by 16-bit CHAIN,CC
        self.chan_midi_cc_binding = {}  # Map of list of zctrls indexed by 16-bit CHAN,CC

        # Map of lists of currently held (sustained) zctrls, indexed by cc number - first element indicates pedal state
        self.held_zctrls = {
            64: [False],
            66: [False],
            67: [False],
            69: [False]
        }

    # ------------------------------------------------------------------------
    # Engine Management
    # ------------------------------------------------------------------------

    @classmethod
    def get_engine_info(cls):
        """Get engine config from file and add extra info"""

        # Get engines info from file, including standalone engines.
        # Yes, names aren't good. They should be refactored!
        eng_info = zynthian_lv2.get_engines()

        # Don't recalculate if info not changed
        if eng_info == cls.engine_info:
            return cls.engine_info

        cls.engine_info = eng_info
        # Look for an engine class for each one
        for key, info in cls.engine_info.items():
            try:
                info['ENGINE'] = engine2class[key[0:2]]
                #logging.debug(f"Found engine class for {key}")
            except:
                logging.error(f"Engine {key} has been disabled. Can't find an engine class for it.")
                info['ENGINE'] = None
                info['ENABLED'] = False

        # Complete Pianoteq config
        pt_info = get_pianoteq_binary_info()
        if pt_info:
            cls.engine_info['PT']['TITLE'] = pt_info['name']
            if pt_info['api']:
                cls.engine_info['PT']['ENGINE'] = zynthian_engine_pianoteq
            else:
                cls.engine_info['PT']['ENGINE'] = zynthian_engine_pianoteq6

        return cls.engine_info

    @classmethod
    def save_engine_info(cls):
        """Save the engine config to file"""

        zynthian_lv2.save_engines()

    # ------------------------------------------------------------------------
    # Chain Management
    # ------------------------------------------------------------------------

    def add_chain(self, chain_id, midi_chan=None, midi_thru=False, audio_thru=False, mixer_chan=None, title="", chain_pos=None, fast_refresh=True):
        """Add a chain

        chain_id: UID of chain (None to get next available)
        midi_chan : MIDI channel associated with chain
        midi_thru : True to enable MIDI thru for empty chain (Default: False)
        audio_thru : True to enable audio thru for empty chain (Default: False)
        mixer_chan : Mixer channel (Default: None)
        zmop_index : MIDI router output (Default: None)
        title : Chain title (Default: None)
        chain_pos : Position to insert chain (Default: End)
        fast_refresh : False to trigger slow autoconnect (Default: Fast autoconnect)
        Returns : Chain ID or None if chain could not be created
        """

        self.state_manager.start_busy("add_chain", "Adding Chain")

        # If not chain ID has been specified, create new unique chain ID
        if chain_id is None:
            chain_id = 1
            while chain_id in self.chains:
                chain_id += 1


        # If Main chain ...
        if chain_id == 0:  # main
            midi_thru = False
            audio_thru = True
            mixer_chan = self.state_manager.zynmixer.MAX_NUM_CHANNELS - 1

        # If the chain already exists, update and return
        if chain_id in self.chains:
            self.chains[chain_id].midi_thru = midi_thru
            self.chains[chain_id].audio_thru = audio_thru
            self.state_manager.end_busy("add_chain")
            return self.chains[chain_id]

        # Create chain instance
        chain = zynthian_chain(chain_id, midi_chan, midi_thru, audio_thru)
        if not chain:
            return None
        self.chains[chain_id] = chain

        # Setup chain
        chain.set_title(title)
        # If a mixer_chan is specified (restore from state), setup mixer_chan
        if mixer_chan is not None:
            chain.set_mixer_chan(mixer_chan)
        # else, if audio_thru enabled, setup a mixer_chan
        elif audio_thru:
            chain.set_mixer_chan(self.get_next_free_mixer_chan())

        # Setup MIDI routing
        if isinstance(midi_chan, int):
            chain.set_zmop_index(self.get_next_free_zmop_index())
        if chain.zmop_index is not None and self.state_manager.ctrldev_manager is not None:
            # Enable all MIDI inputs by default
            # TODO: Should we allow user to define default routing?
            for zmip in range(MAX_NUM_MIDI_DEVS):
                unroute = zmip in self.state_manager.ctrldev_manager.drivers and self.state_manager.ctrldev_manager.drivers[zmip].unroute_from_chains
                lib_zyncore.zmop_set_route_from(chain.zmop_index, zmip, not unroute)

        # Set MIDI channel
        self.set_midi_chan(chain_id, midi_chan)

        # Add to chain index (sorted!)
        if chain_pos is None:
            chain_pos = self.get_chain_index(0)
        self.ordered_chain_ids.insert(chain_pos, chain_id)

        chain.rebuild_graph()
        zynautoconnect.request_audio_connect(fast_refresh)
        zynautoconnect.request_midi_connect(fast_refresh)

        logging.debug(f"ADDED CHAIN {chain_id} => midi_chan={chain.midi_chan}, mixer_chan={chain.mixer_chan}, zmop_index={chain.zmop_index}")
        #logging.debug(f"ordered_chain_ids = {self.ordered_chain_ids}")
        #logging.debug(f"midi_chan_2_chain_ids = {self.midi_chan_2_chain_ids}")

        self.active_chain_id = chain_id
        self.state_manager.end_busy("add_chain")
        return chain_id

    def add_chain_from_state(self, chain_id, chain_state):
        if 'title' in chain_state:
            title = chain_state['title']
        else:
            title = ""
        if 'midi_chan' in chain_state:
            midi_chan = chain_state['midi_chan']
        else:
            midi_chan = None
        if 'midi_thru' in chain_state:
            midi_thru = chain_state['midi_thru']
        else:
            midi_thru = False
        if 'audio_thru' in chain_state:
            audio_thru = chain_state['audio_thru']
        else:
            audio_thru = False
        if 'mixer_chan' in chain_state:
            mixer_chan = chain_state['mixer_chan']
        else:
            mixer_chan = None

        # This doen't have any effect because zmop_index is not restored
        #if 'zmop_index' in chain_state:
        #    zmop_index = chain_state['zmop_index']
        #else:
        #    zmop_index = None

        self.add_chain(chain_id, midi_chan=midi_chan, midi_thru=midi_thru, audio_thru=audio_thru, mixer_chan=mixer_chan, title=title, fast_refresh=False)

        # Set CC route state
        zmop_index = self.chains[chain_id].zmop_index
        if 'cc_route' in chain_state and zmop_index is not None and zmop_index >= 0:
            cc_route_ct = (ctypes.c_uint8 * 128)()
            for ccnum, ccr in enumerate(chain_state['cc_route']):
                cc_route_ct[ccnum] = ccr
            lib_zyncore.zmop_set_cc_route(zmop_index, cc_route_ct)

    def remove_chain(self, chain_id, stop_engines=True, fast_refresh=True):
        """Removes a chain or resets main chain

        chain_id : ID of chain to remove
        stop_engines : True to stop unused engines
        fast_refresh : False to trigger slow autoconnect (Default: Fast autoconnect)
        Returns : True on success
        """

        if chain_id not in self.chains:
            return False
        self.state_manager.start_busy("remove_chain", "Removing Chain")
        chain_pos = self.get_chain_index(chain_id)
        chains_to_remove = [chain_id]  # List of associated chains that shold be removed simultaneously
        chain = self.chains[chain_id]
        if chain.synth_slots:
            if chain.synth_slots[0][0].eng_code in ["BF", "AE"]:
                # TODO: We remove all setBfree and Aeolus chains but maybe we should allow chain manipulation
                for id, ch in self.chains.items():
                    if ch != chain and ch.synth_slots and ch.synth_slots[0][0].eng_code == chain.synth_slots[0][0].eng_code:
                        chains_to_remove.append(id)

        for chain_id in chains_to_remove:
            chain = self.chains[chain_id]
            if isinstance(chain.midi_chan, int):
                if chain.midi_chan < MAX_NUM_MIDI_CHANS:
                    self.midi_chan_2_chain_ids[chain.midi_chan].remove(chain_id)
                    lib_zyncore.ui_send_ccontrol_change(chain.midi_chan, 120, 0)
                elif chain.midi_chan == 0xffff:
                    for mc in range(16):
                        self.midi_chan_2_chain_ids[mc].remove(chain_id)
                        lib_zyncore.ui_send_ccontrol_change(mc, 120, 0)

            if chain.mixer_chan is not None:
                mute = self.state_manager.zynmixer.get_mute(chain.mixer_chan)
                self.state_manager.zynmixer.set_mute(chain.mixer_chan, True, True)

            for processor in chain.get_processors():
                self.remove_processor(chain_id, processor, False, False)

            chain.reset()
            if chain_id != 0:
                if chain.mixer_chan is not None:
                    self.state_manager.zynmixer.reset(chain.mixer_chan)
                    self.state_manager.audio_recorder.unarm(chain.mixer_chan)
                self.chains.pop(chain_id)
                self.state_manager.zynmixer.set_mute(chain.mixer_chan, False, True)
                del chain
                if chain_id in self.ordered_chain_ids:
                    self.ordered_chain_ids.remove(chain_id)
            elif chain.mixer_chan is not None:
                self.state_manager.zynmixer.set_mute(chain.mixer_chan, mute, True)

        zynautoconnect.request_audio_connect(fast_refresh)
        zynautoconnect.request_midi_connect(fast_refresh)
        if stop_engines:
            self.stop_unused_engines()
        if self.active_chain_id not in self.chains:
            if chain_pos + 1 >= len(self.ordered_chain_ids):
                chain_pos -= 1
            self.set_active_chain_by_index(chain_pos)
        self.state_manager.end_busy("remove_chain")
        return True

    def remove_all_chains(self, stop_engines=True):
        """Remove all chains

        stop_engines : True to stop orphaned engines
        Returns : True if all chains removed
        Note: Main chain is retained but reset
        """

        success = True
        for chain in list(self.chains.keys()):
            success &= self.remove_chain(chain, stop_engines, fast_refresh=False)
        return success

    def move_chain(self, offset, chain_id=None):
        """Move a chain's position

        chain_id - Chain id
        offset - Position to move to relative to current position (+/-)
        """

        if chain_id is None:
            chain_id = self.active_chain_id
        if chain_id and chain_id in self.ordered_chain_ids:
            index = self.ordered_chain_ids.index(chain_id)
            pos = index + offset
            pos = min(pos, len(self.ordered_chain_ids) - 2)
            pos = max(pos, 0)
            self.ordered_chain_ids.insert(pos, self.ordered_chain_ids.pop(index))
            zynsigman.send(zynsigman.S_CHAIN_MAN, self.SS_MOVE_CHAIN)

    def get_chain_count(self):
        """Get the quantity of chains"""

        return len(self.chains)

    def get_chain(self, chain_id):
        """Get a chain object by id"""

        try:
            return self.chains[chain_id]
        except:
            return None

    def get_chain_by_index(self, index):
        """Get a chain object by the index"""

        try:
            return self.chains[self.ordered_chain_ids[index]]
        except:
            return None

    def get_chain_by_position(self, pos, audio=True, midi=True, synth=True):
        """Get a chain by its (display) position

        pos : Display position (0..no of chains)
        audio_only : True to include audio chains
        midi : True to include MIDI chains
        synth : True to include synth chains
        returns : Chain object or None if not found
        """

        if audio and midi and synth:
            if pos < len(self.ordered_chain_ids):
                return self.chains[self.ordered_chain_ids[pos]]
            else:
                return None

        for chain_id in self.ordered_chain_ids:
            chain = self.chains[chain_id]
            if chain.is_midi() == midi or chain.is_audio() == audio or chain.is_synth == synth:
                if pos == 0:
                    return self.chains[chain_id]
                pos -= 1

        return None

    def get_chain_id_by_index(self, index):
        """Get a chain ID by the index"""

        try:
            return self.ordered_chain_ids[index]
        except:
            return None

    def get_chain_id_by_mixer_chan(self, chan):
        """Get a chain by the mixer channel"""

        for chain_id, chain in self.chains.items():
            if chain.mixer_chan is not None and chain.mixer_chan == chan:
                return chain_id
        return None


    # ------------------------------------------------------------------------
    # Chain Input/Output and Routing Management
    # ------------------------------------------------------------------------

    def get_chain_audio_inputs(self, chain_id):
        """Get list of audio inputs for a chain"""

        if chain_id in self.chains:
            return self.chains[chain_id].audio_in
        return []

    def set_chain_audio_inputs(self, chain_id, inputs):
        """Set chain's audio inputs

        chain_id : Chain id
        inputs : List of jack sources or aliases (None to reset)
        """
        if chain_id in self.chains:
            if inputs:
                self.chains[chain_id].audio_in = inputs
            else:
                self.chains[chain_id].audio_in = ["SYSTEM"]
            self.chains[chain_id].rebuild_audio_graph()

    def get_chain_audio_ouputs(self, chain_id):
        """Get list of audio outputs for a chain"""

        if chain_id in self.chains:
            return self.chains[chain_id].audio_out
        return []

    def set_chain_audio_outputs(self, chain_id, outputs):
        """Set chain's audio outputs

        chain_id : Chain id
        outputs : List of jack destinations or aliases (None to reset)
        """
        if chain_id in self.chains:
            if outputs:
                self.chains[chain_id].audio_out = outputs
            else:
                self.chains[chain_id].audio_out = [0]
            self.chains[chain_id].rebuild_audio_graph()

    def enable_chain_audio_thru(self, chain_id, enable=True):
        """Enable/disable audio pass-through

        enable : True to pass chain's audio input to output when chain is empty
        """
        if chain_id in self.chains and self.chains[chain_id].audio_thru != enable:
            self.chains[chain_id].audio_thru = enable
            self.chains[chain_id].rebuild_audio_graph()

    def get_chain_audio_routing(self, chain_id):
        """Get dictionary of lists of destinations mapped by source"""

        if chain_id in self.chains:
            return self.chains[chain_id].audio_routes
        return{}

    def get_chain_midi_inputs(self, chain_id):
        """Get list of MIDI inputs for a chain"""

        if chain_id in self.chains:
            return self.chains[chain_id].midi_in
        return []

    def set_chain_midi_inputs(self, chain_id, inputs):
        """Set chain's MIDI inputs

        chain_id : Chain id
        inputs : List of jack sources or aliases (None to reset)
        """
        if chain_id in self.chains:
            if inputs:
                self.chains[chain_id].midi_in = inputs
            else:
                self.chains[chain_id].midi_in = ["MIDI-IN"]
            self.chains[chain_id].rebuild_midi_graph()

    def get_chain_midi_ouputs(self, chain_id):
        """Get list of MIDI outputs for a chain"""

        if chain_id in self.chains:
            return self.chains[chain_id].midi_out
        return []

    def set_chain_midi_outputs(self, chain_id, outputs):
        """Set chain's MIDI outputs

        chain_id : Chain id
        outputs : List of jack destinations or aliases (None to reset)
        """
        if chain_id in self.chains:
            if outputs:
                self.chains[chain_id].midi_out = outputs
            else:
                self.chains[chain_id].midi_out = ["MIDI-OUT", "NET-OUT"]
            self.chains[chain_id].rebuild_midi_graph()

    def enable_chain_midi_thru(self, chain_id, enable=True):
        """Enable/disable MIDI pass-through

        enable : True to pass chain's MIDI input to output when chain is empty
        """
        if chain_id in self.chains and self.chains[chain_id].midi_thru != enable:
            self.chains[chain_id].midi_thru = enable
            self.chains[chain_id].rebuild_midi_graph()

    def get_chain_midi_routing(self, chain_id):
        """Get dictionary of lists of destinations mapped by source"""

        if chain_id in self.chains:
            return self.chains[chain_id].midi_routes
        return{}

    def will_midi_howl(self, src_id, dst_id, node_list=None):
        """Checks if adding a connection will cause a MIDI howl-round loop

        src_id : Chain ID of the source chain
        dst_id : Chain ID of the destination chain
        node_list : Do not use - internal function parameter
        Returns : True if adding the route will cause howl-round feedback loop
        """

        if dst_id not in self.chains:
            return False
        if src_id is not None:
            # src_id only provided on first call (not re-entrant cycles)
            if src_id not in self.chains:
                return False
            node_list = [src_id]  # Init node_list on first call
        if dst_id in node_list:
            return True
        node_list.append(dst_id)
        for chain_id in self.chains[dst_id].midi_out:
            if chain_id in self.chains:
                if self.will_midi_howl(None, chain_id, node_list):
                    return True
                node_list.append(chain_id)
        return False

    def will_audio_howl(self, src_id, dst_id, node_list=None):
        """Checks if adding a connection will cause an audio howl-round loop

        src_id : Chain ID of the source chain
        dst_id : Chain ID of the destination chain
        node_list : Do not use - internal function parameter
        Returns : True if adding the route will cause howl-round feedback loop
        """

        if dst_id not in self.chains:
            return False
        if src_id is not None:
            # src_id only provided on first call (not re-entrant cycles)
            if src_id not in self.chains:
                return False
            node_list = [src_id]  # Init node_list on first call
        if dst_id in node_list:
            return True
        node_list.append(dst_id)
        for chain_id in self.chains[dst_id].audio_out:
            if chain_id in self.chains:
                if self.will_audio_howl(None, chain_id, node_list):
                    return True
                node_list.append(chain_id)
        return False

    # ------------------------------------------------------------------------
    # Chain Selection
    # ------------------------------------------------------------------------

    def set_active_chain_by_id(self, chain_id=None):
        """Select the active chain

        chain_id : ID of chain (Default: Reassert current active channel)
        Returns : ID of active chain
        """

        if chain_id is None:
            chain_id = self.active_chain_id

        try:
            chain = self.chains[chain_id]
        except:
            chain = None

        # If no better candidate, set active the first chain (Main)
        if chain is None:
            chain = next(iter(self.chains.values()))
            chain_id = chain.chain_id

        self.active_chain_id = chain_id
        zynsigman.send_queued(zynsigman.S_CHAIN_MAN, self.SS_SET_ACTIVE_CHAIN, active_chain=self.active_chain_id)

        # If chain receives MIDI, set the active chain in ZynMidiRouter (lib_zyncore)
        if isinstance(chain.zmop_index, int):
            try:
                lib_zyncore.set_active_chain(chain.zmop_index)
                # Re-assert pedals on new active chain
                if isinstance(chain.midi_chan, int):
                    if 0 <= chain.midi_chan < 16:
                        chan = chain.midi_chan
                    else:
                        # If chain receives *ALL CHANNELS* use channel 0 to re-assert pedals
                        chan = 0
                    for pedal_cc in self.held_zctrls:
                        if self.held_zctrls[pedal_cc][0]:
                            lib_zyncore.write_zynmidi_ccontrol_change(chan, pedal_cc, 127)
                            # TODO: Check if zctrl gets added to self.held_zctrls
            except Exception as e:
                logging.error(e)

        return self.active_chain_id

    def set_active_chain_by_object(self, chain_object):
        """Select the active chain

        chain_object : Chain object
        Returns : ID of active chain
        """

        for id in self.chains:
            if self.chains[id] == chain_object:
                self.set_active_chain_by_id(id)
                break
        return self.active_chain_id

    def set_active_chain_by_index(self, index):
        """Select the active chain by index

        index : Index of chain in ordered_chain_ids
        Returns : ID of active chain
        """

        if index < len(self.ordered_chain_ids):
            return self.set_active_chain_by_id(self.ordered_chain_ids[index])
        else:
            return self.set_active_chain_by_id(0)


    def next_chain(self, nudge=1):
        """Set active the next chain from the ordered list

        nudge : Quantity of chains to step (may be negative, default: 1)
        Returns : Chain ID
        """

        index = self.get_chain_index(self.active_chain_id)
        index += nudge
        index = min(index, len(self.ordered_chain_ids) - 1)
        index = max(index, 0)
        return self.set_active_chain_by_index(index)

    def previous_chain(self, nudge=1):
        """Set active the previous chain from the ordered list

        nudge : Quantity of chains to step (may be negative, default: 1)
        Returns : Chain ID
        """

        return self.next_chain(-nudge)

    def get_active_chain(self):
        """Get the active chain object or None if no active chain"""

        if self.active_chain_id in self.chains:
            return self.chains[self.active_chain_id]
        return None

    def get_chain_index(self, chain_id):
        """Get the index of a chain from its displayed order

        chain_id : Chain id
        returns : Index or 0 if not found
        """

        if chain_id in self.ordered_chain_ids:
            return self.ordered_chain_ids.index(chain_id)
        return 0

    # ------------------------------------------------------------------------
    # Processor Management
    # ------------------------------------------------------------------------

    def get_available_processor_id(self):
        """Get the next available processor ID"""

        proc_ids = list(self.processors)
        if proc_ids:
            proc_ids.sort()
            for x,y in enumerate(proc_ids):
                if proc_ids[x-1] + 1 < y:
                    return proc_ids[x-1]+1
            return proc_ids[-1] + 1
        else:
            return 1

    def add_processor(self, chain_id, eng_code, parallel=False, slot=None, proc_id=None, post_fader=False, fast_refresh=True):
        """Add a processor to a chain

        chain : Chain ID
        eng_code : Engine's code
        parallel : True to add in parallel (same slot) else create new slot (Default: series)
        slot : Slot (position) within subchain (0..last slot, Default: last slot)
        proc_id : Processor UID (Default: Use next available ID)
        post_fader : True to move the fader position
        fast_refresh : False to trigger slow autoconnect (Default: Fast autoconnect)
        Returns : processor object or None on failure
        """

        if chain_id not in self.chains:
            logging.error(f"Chain '{chain_id}' doesn't exist!")
            return None
        if eng_code not in self.engine_info:
            if eng_code != 'None':
                logging.error(f"Engine '{eng_code}' not found!")
            return None
        if proc_id is None:
            proc_id = self.get_available_processor_id()  # TODO: Derive next available processor id from self.processors
        elif proc_id in self.processors:
            logging.error(f"Processor '{proc_id}' already exist!")
            return None

        if self.state_manager.is_busy():
            self.state_manager.start_busy("add_processor", None, f"adding {eng_code} to chain {chain_id}")
        else:
            self.state_manager.start_busy("add_processor", "Adding Processor", f"adding {eng_code} to chain {chain_id}")

        logging.debug(f"Adding processor '{eng_code}' with ID '{proc_id}'")
        processor = zynthian_processor(eng_code, self.engine_info[eng_code], proc_id)
        chain = self.chains[chain_id]
        self.processors[proc_id] = processor  # Add proc early to allow engines to add more as required, e.g. Aeolus
        if chain.insert_processor(processor, parallel, slot):
            if not parallel and not post_fader and processor.type == "Audio Effect":
                chain.fader_pos += 1
            # TODO: Fails to detect MIDI only chains in snapshots
            if chain.mixer_chan is None and processor.type != "MIDI Tool":
                chain.mixer_chan = self.get_next_free_mixer_chan()
            engine = self.start_engine(processor, eng_code)
            if engine:
                chain.rebuild_graph()
                # Update group chains
                for src_chain in self.chains.values():
                    if chain_id in src_chain.audio_out:
                        src_chain.rebuild_graph()
                zynautoconnect.request_audio_connect(fast_refresh)
                zynautoconnect.request_midi_connect(fast_refresh)
                # Success!! => Return processor
                self.state_manager.end_busy("add_processor")
                return processor
            else:
                chain.remove_processor(processor)
                logging.error(f"Failed to start engine '{eng_code}'!")
        else:
            logging.error(f"Failed to insert processor '{proc_id}' in chain '{chain_id}', slot '{slot}'!")
        # Failed!! => Remove processor from list
        del self.processors[proc_id]
        self.state_manager.end_busy("add_processor")
        return None

    def nudge_processor(self, chain_id, processor, up):
        if (chain_id not in self.chains):
            return None
        chain = self.chains[chain_id]
        if chain.nudge_processor(processor, up):
            for src_chain in self.chains.values():
                if chain_id in src_chain.audio_out:
                    src_chain.rebuild_graph()

        if chain.mixer_chan is not None:
            # Audio chain so mute main output whilst making change (blunt but effective)
            mute = self.state_manager.zynmixer.get_mute(255)
            self.state_manager.zynmixer.set_mute(255, True, False)
            zynautoconnect.request_audio_connect(True)
            self.state_manager.zynmixer.set_mute(255, mute, False)
        zynautoconnect.request_midi_connect(True)

    def remove_processor(self, chain_id, processor, stop_engine=True, autoroute=True):
        """Remove a processor from a chain

        chain : Chain id
        processor : Instance of processor
        stop_engine : True to stop unused engine
        autoroute : True to trigger immediate autoconnect (Default: No autoconnect)
        Returns : True on success
        """

        if chain_id not in self.chains:
            logging.error(f"Chain {chain_id} doesn't exist!")
            return False

        if not isinstance(processor, zynthian_processor):
            logging.error(f"Invalid processor instance '{processor}' can't be removed from chain {chain_id}!")
            return False

        if self.state_manager.is_busy():
            self.state_manager.start_busy("remove_processor", None, f"removing {processor.get_basepath()} from chain {chain_id}")
        else:
            self.state_manager.start_busy("remove_processor", "Removing Processor", f"removing {processor.get_basepath()} from chain {chain_id}")
        for param in processor.controllers_dict:
            self.remove_midi_learn(processor, param)

        id = None
        for i, p in self.processors.items():
            if processor == p:
                id = i
                break
        success = self.chains[chain_id].remove_processor(processor)
        if success:
            try:
                self.processors.pop(id)
            except:
                pass
            if stop_engine:
                self.stop_unused_engines()

            if autoroute:
                # Update chain routing (may have effected lots of chains)
                for chain in self.chains.values():
                    chain.rebuild_graph()
                zynautoconnect.request_audio_connect()
                zynautoconnect.request_midi_connect()

        self.state_manager.end_busy("remove_processor")
        return success

    def get_slot_count(self, chain_id, type=None):
        """Get the quantity of slots in a chain

        id : Chain id
        type : Processor type to filter result (Default: all types)
        Returns : Quantity of slots in chain or subchain
        """

        if chain_id not in self.chains:
            return 0
        return self.chains[chain_id].get_slot_count(type)

    def get_processor_count(self, chain_id=None, type=None, slot=None):
        """Get the quantity of processors in a slot

        chain_id : Chain id (Default: all processors in all chains)
        type : Processor type to filter result (Default: all types)
        slot : Index of slot or None for whole chain (Default: whole chain)
        Returns : Quantity of processors in (sub)chain or slot
        """

        if chain_id is None:
            count = 0
            for chain in self.chains:
                count += self.chains[chain].get_processor_count(type, slot)
                return count
        if chain_id not in self.chains:
            return 0
        return self.chains[chain_id].get_processor_count(type, slot)


    def get_processor_id(self, processor):
        """Get processor uid from processor object

        processor : Processor object
        Returns : Processor UID or None if not found
        """

        for uid, proc in self.processors.items():
            if proc == processor:
                return uid
        return None

    def get_processors(self, chain_id=None, type=None, slot=None):
        """Get a list of processors in (sub)chain (slot)

        chain_id : Chain id (Default: all processors)
        type : Processor type to filter result (Default: all types)
        slot : Index of slot or None for whole chain (Default: whole chain)
        Returns : List of processor objects
        """

        if chain_id is None:
            processors = []
            for chain in self.chains:
                processors += (self.chains[chain].get_processors(type, slot))
            return processors
        if chain_id not in self.chains:
            return []
        return self.chains[chain_id].get_processors(type, slot)

    # ------------------------------------------------------------------------
    # Engine Management
    # ------------------------------------------------------------------------

    def start_engine(self, processor, eng_code):
        """Starts or reuse an existing engine

        processor : processor owning engine
        eng_code : Engine short code
        Returns : engine object
        """

        if eng_code not in self.engine_info:
            logging.error(f"Engine '{eng_code}' not found!")
            return None

        if eng_code in self.zyngines:
            # Engine already started
            zyngine = self.zyngines[eng_code]
        else:
            # Start new engine instance
            info = self.engine_info[eng_code]
            zynthian_engine_class = info["ENGINE"]
            if eng_code[0:3] == "JV/":
                eng_key = f"JV/{self.zyngine_counter}"
                zyngine = zynthian_engine_class(eng_code, self.state_manager, False)
            elif eng_code == "SF":
                eng_key = f"{eng_code}/{self.zyngine_counter}"
                zyngine = zynthian_engine_class(self.state_manager)
            else:
                eng_key = eng_code
                zyngine = zynthian_engine_class(self.state_manager)

            self.zyngines[eng_key] = zyngine
            self.zyngine_counter += 1

        processor.set_engine(zyngine)
        return zyngine

    def stop_unused_engines(self):
        """Stop engines that are not used by any processors"""
        for eng_key in list(self.zyngines.keys()):
            if not self.zyngines[eng_key].processors:
                logging.debug(f"Stopping Unused Engine '{eng_key}' ...")
                self.state_manager.set_busy_details(f"stopping engine {self.zyngines[eng_key].get_name()}")
                self.zyngines[eng_key].stop()
                del self.zyngines[eng_key]

    def stop_unused_jalv_engines(self):
        """Stop JALV engines that are not used by any processors"""
        for eng_key in list(self.zyngines.keys()):
            if len(self.zyngines[eng_key].processors) == 0 and eng_key[0:3] == "JV/":
                logging.debug(f"Stopping Unused Jalv Engine '{eng_key}'...")
                self.state_manager.set_busy_details(f"stopping engine {self.zyngines[eng_key].get_name()}")
                self.zyngines[eng_key].stop()
                del self.zyngines[eng_key]

    def filtered_engines_by_cat(self, etype, all=False):
        """Get dictionary of engine info filtered by type and indexed by catagory
            etype: type of engine
            all: include "disabled" engine too
        """
        result = {}
        if etype in zynthian_lv2.engines_by_type:
            for eng_cat in zynthian_lv2.engine_categories[etype]:
                result[eng_cat] = {}
            for eng_code, info in zynthian_lv2.engines_by_type[etype].items():
                eng_cat = info["CAT"]
                hide_if_single_proc = eng_code not in self.single_processor_engines or eng_code not in self.zyngines
                if (info["ENABLED"] or all) and hide_if_single_proc:
                    result[eng_cat][eng_code] = info
        return result

    def get_next_jackname(self, jackname, sanitize=True):
        """Get the next available jackname

        jackname : stub of jackname
        """

        try:
            # Jack, when listing ports, accepts regular expressions as the jack name.
            # So, for avoiding problems, jack names shouldn't contain regex characters.
            if sanitize:
                jackname = re.sub("[\_]{2,}", "_", re.sub("[\s\'\*\(\)\[\]]", "_", jackname))
            names = set()
            for processor in self.get_processors():
                jn = processor.get_jackname()
                if jn is not None and jn.startswith(jackname):
                    names.add(jn)
            i = 1
            while f"{jackname}-{i:02}" in names:
                i += 1
            return f"{jackname}-{i:02}"
        except Exception as e:
            logging.error(e)
            return f"{jackname}-00"

    # ------------------------------------------------------------------------
    # State Management
    # ------------------------------------------------------------------------

    def get_state(self):
        """Get dictionary of chain slot states indexed by chain id"""

        state = {}
        for chain_id in self.ordered_chain_ids:
            state[chain_id] = self.chains[chain_id].get_state()
        return state

    def get_zs3_processor_state(self):
        """Get dictionary of ZS3 processors indexed by processor id"""

        state = {}
        for id, processor in self.processors.items():
            state[id] = {
                "bank_info": processor.bank_info,
                "preset_info": processor.preset_info,
                "controllers": processor.controllers_dict
            }
        #TODO: Remove superfluous parameters
        return state

    def set_state(self, state):
        """Create chains from state

        state : List of chain states
        Returns : True on success
        """

        self.state_manager.start_busy("set_chain_state", None, "loading chains")

        # Clean all chains but don't stop unused engines
        self.remove_all_chains(False)

        # Reusing Jalv engine instances raise problems (audio routing & jack names, etc..),
        # so we stop Jalv engines!
        self.stop_unused_jalv_engines()  # TODO: Can we factor this out? => Not yet!!

        for chain_id, chain_state in state.items():
            chain_id = int(chain_id)
            self.add_chain_from_state(chain_id, chain_state)
            if "slots" in chain_state:
                for slot_state in chain_state["slots"]:
                    # slot_state is a dict of proc_id:proc_type for procs in this slot
                    for index, proc_id in enumerate(slot_state):
                        # Use index to identify first proc in slot (add in series) - others are added in parallel
                        if index:
                            self.add_processor(chain_id, slot_state[proc_id], CHAIN_MODE_PARALLEL, proc_id=int(proc_id), fast_refresh=False)
                        else:
                            self.add_processor(chain_id, slot_state[proc_id], CHAIN_MODE_SERIES, proc_id=int(proc_id), fast_refresh=False)
            if "fader_pos" in chain_state:
                self.chains[chain_id].fader_pos = chain_state["fader_pos"]

        self.state_manager.end_busy("set_chain_state")

    def restore_presets(self):
        """Restore presets in active chain"""

        for processor in self.get_processors(self.active_chain_id):
            processor.restore_preset()

    # ----------------------------------------------------------------------------
    # MIDI CC
    # ----------------------------------------------------------------------------

    def add_midi_learn(self, chan, midi_cc, zctrl, zmip=None):
        """Adds a midi learn configuration

        chan : MIDI channel to bind (None to not bind to MIDI channel)
        midi_cc : CC number of CC message
        zctrl : Controller object
        zmip : ZMIP of absolute learn device (Optional: Default - do not learn absolute)
        """

        if zctrl is None:
            return
        self.remove_midi_learn(zctrl.processor, zctrl.symbol)
        if zmip is None:
            if zctrl.processor:
                if zctrl.processor.midi_chan is not None:
                    key = (chan << 16) | (midi_cc << 8)
                    if key in self.chan_midi_cc_binding:
                        self.chan_midi_cc_binding[key].append(zctrl)
                    else:
                        self.chan_midi_cc_binding[key] = [zctrl]
                if zctrl.processor.chain_id is not None:
                    key = (zctrl.processor.chain_id << 16) | (midi_cc << 8)
                    if key in self.chain_midi_cc_binding:
                        self.chain_midi_cc_binding[key].append(zctrl)
                    else:
                        self.chain_midi_cc_binding[key] = [zctrl]
        else:
            # Absolute mapping
            key = (zmip << 24) | (chan << 16) | (midi_cc << 8)
            if key in self.absolute_midi_cc_binding:
                if zctrl not in self.absolute_midi_cc_binding[key]:
                    self.absolute_midi_cc_binding[key].append(zctrl)
            else:
                self.absolute_midi_cc_binding[key] = [zctrl]

        #TODO: Handle MD midi learn
            """
            #logging.debug(f"ADDING GLOBAL MIDI LEARN => MIDI CHANNEL {chan}, CC#{midi_cc}")
            if zctrl.processor.eng_code == "MD":
                # Add native MIDI learn #TODO: Should / can we still use native midi learn?
                zctrl.processor.engine.set_midi_learn(zctrl, chan, midi_cc)
            """


    def remove_midi_learn(self, proc, symbol):
        """Remove a midi learn configuration

        proc : Processor object
        symbol : Control symbol
        """

        if not proc or symbol not in proc.controllers_dict:
            return
        zctrl = proc.controllers_dict[symbol]

        for key in list(self.absolute_midi_cc_binding):
            zctrls = self.absolute_midi_cc_binding[key]
            if zctrl in zctrls:
                zctrls.remove(zctrl)
            if not zctrls:
                self.absolute_midi_cc_binding.pop(key)
        for key in list(self.chan_midi_cc_binding):
            zctrls = self.chan_midi_cc_binding[key]
            if zctrl in zctrls:
                zctrls.remove(zctrl)
            if not zctrls:
                self.chan_midi_cc_binding.pop(key)
        for key in list(self.chain_midi_cc_binding):
            zctrls = self.chain_midi_cc_binding[key]
            if zctrl in zctrls:
                zctrls.remove(zctrl)
            if not zctrls:
                self.chain_midi_cc_binding.pop(key)

        """
        if proc.eng_code == "MD":
            # Remove native MIDI learn
            proc.engine.midi_unlearn(zctrl)
        return
        """

    def get_midi_learn_from_zctrl(self, zctrl):
        for key, zctrls in self.absolute_midi_cc_binding.items():
            if zctrl in zctrls:
                return [key, True]
        for key, zctrls in self.chain_midi_cc_binding.items():
            if zctrl in zctrls:
                return [key, False]
        for key, zctrls in self.chan_midi_cc_binding.items():
            if zctrl in zctrls:
                return [key, False] #TODO: This isn't right!

    def midi_control_change(self, zmip, midi_chan, cc_num, cc_val):
        """Send MIDI CC message to relevant chain

        zmip : Index of MIDI input device
        midi_chan : MIDI channel
        cc_num : CC number
        cc_val : CC value
        """

        # Handle bank change (CC0/32)
        # TODO: Validate and optimise bank change code
        if zynthian_gui_config.midi_bank_change:
            for chain_id in self.midi_chan_2_chain_ids[midi_chan]:
                chain = self.chains[chain_id]
                if cc_num == 0:
                    for processor in chain.get_processors():
                        processor.midi_bank_msb(cc_val)
                        break
                    return
                elif cc_num == 32:
                    for processor in chain.get_processors():
                        processor.midi_bank_lsb(cc_val)
                        break
                    return

        # Handle controller feedback from setBfree engine => setBfree sends feedback in channel 0
        # Each engine sending feedback should use a separated zmip, currently only setBfree does.
        if zmip == ZMIP_CTRL_INDEX:
            #logging.debug(f"MIDI CONTROL FEEDBACK {midi_chan}, {cc_num} => {cc_val}")
            try:
                for proc in zynautoconnect.ctrl_fb_procs:
                    key = (proc.midi_chan << 16) | (cc_num << 8)
                    zctrls = self.chan_midi_cc_binding[key]
                    for zctrl in zctrls:
                        #logging.debug(f"CONTROLLER FEEDBACK {zctrl.symbol} ({proc.midi_chan}) => {cc_val}")
                        zctrl.midi_control_change(cc_val, send=False)
            except:
                pass
            return

        # Handle absolute CC binding
        try:
            key = (zmip << 24) | (midi_chan << 16) | (cc_num << 8)
            zctrls = self.absolute_midi_cc_binding[key]
            for zctrl in zctrls:
                zctrl.midi_control_change(cc_val)
        except:
            pass

        # Handle active chain CC binding
        if zynautoconnect.get_midi_in_dev_mode(zmip):
            try:
                key = (self.active_chain_id << 16) | (cc_num << 8)
                zctrls = self.chain_midi_cc_binding[key]
                for zctrl in zctrls:
                    zctrl.midi_control_change(cc_val)
                    self.handle_pedals(cc_num, cc_val, zctrl)
            except:
                pass
        # Handle channel CC binding
        else:
            try:
                key = (midi_chan << 16) | (cc_num << 8)
                zctrls = self.chan_midi_cc_binding[key]
                for zctrl in zctrls:
                    zctrl.midi_control_change(cc_val)
                    self.handle_pedals(cc_num, cc_val, zctrl)
            except:
                pass

    def handle_pedals(self, cc_num, cc_val, zctrl):
        """Handle pedal CC

        cc_num : CC number
        cc_val : CC value
        zctrl : zctrl to process
        """

        if cc_num in self.held_zctrls:
            if cc_val >= 64:
                if zctrl not in self.held_zctrls[cc_num]:
                    self.held_zctrls[cc_num].append(zctrl)
                self.held_zctrls[cc_num][0] = True
            else:
                self.held_zctrls[cc_num][0] = False
                while len(self.held_zctrls[cc_num]) > 1:
                    self.held_zctrls[cc_num].pop().midi_control_change(cc_val)

    def clean_midi_learn(self, obj):
        """Clean MIDI learn from controls

        obj : Object to clean [chain_id, processor, zctrl] (Default: active chain)
        """

        if obj == None:
            obj = self.active_chain_id
        if obj == None:
            return

        if isinstance(obj, zynthian_controller):
            self.remove_midi_learn(obj.processor, obj.symbol)

        elif isinstance(obj, zynthian_processor):
            for symbol in obj.controllers_dict:
                self.remove_midi_learn(obj, symbol)

        elif isinstance(obj, str):
            for proc in self.get_processors(obj):
                for symbol in proc.controllers_dict:
                    self.remove_midi_learn(proc, symbol)

    # ----------------------------------------------------------------------------
    # MIDI Program Change (when ZS3 is disabled!)
    # ----------------------------------------------------------------------------

    def set_midi_prog_preset(self, midi_chan, midi_prog):
        """Send MIDI PC message to relevant chain

        midi_chan : MIDI channel
        midi_prog : Program change value
        """

        changed = False
        for processor in self.get_processors(type="MIDI Synth"):
            try:
                mch = processor.midi_chan
                if mch is None or mch == midi_chan:
                    # TODO This is really DIRTY!!
                    # Fluidsynth engine => ignore Program Change on channel 10
                    if processor.engine.nickname == "FS" and mch == 9:
                        continue
                    changed |= processor.set_preset(midi_prog, True)
            except Exception as e:
                logging.error(f"Can't set preset for CH#{midi_chan}:PC#{midi_prog} => {e}")
        return changed

    def set_midi_chan(self, chain_id, midi_chan):
        """Set chain MIDI channel

        chain_id : Chain ID
        midi_chan : MIDI channel
        """

        if chain_id not in self.chains:
            return
        chain = self.chains[chain_id]

        # Remove current midi_chan(s) from dictionary
        if isinstance(chain.midi_chan, int):
            midi_chans = []
            # Single MIDI channel
            if 0 <= chain.midi_chan < MAX_NUM_MIDI_CHANS:
                midi_chans = [chain.midi_chan]
            # ALL MIDI channels
            elif chain.midi_chan == 0xffff:
                midi_chans = list(range(MAX_NUM_MIDI_CHANS))
            # Remove from dictionary
            for mc in midi_chans:
                try:
                    self.midi_chan_2_chain_ids[mc].remove(chain_id)
                except:
                    pass

        # Add new midi_chan(s) to dictionary
        if isinstance(midi_chan, int):
            midi_chans = []
            # Single MIDI channel
            if 0 <= midi_chan < MAX_NUM_MIDI_CHANS:
                midi_chans = [midi_chan]
            # ALL MIDI channels
            elif midi_chan == 0xffff:
                midi_chans = list(range(MAX_NUM_MIDI_CHANS))
            # Add to dictionary
            for mc in midi_chans:
                try:
                    self.midi_chan_2_chain_ids[mc].append(chain_id)
                    #logging.debug(f"Adding chain ID {chain_id} to MIDI channel {mc}")
                except:
                    pass

        chain.set_midi_chan(midi_chan)

    def get_free_midi_chans(self):
        """Get list of unused MIDI channels"""

        free_chans = list(range(MAX_NUM_MIDI_CHANS))
        try:
            free_chans.remove(zynthian_gui_config.master_midi_channel)
        except:
            pass
        for chain_id in self.chains:
            try:
                free_chans.remove(self.chains[chain_id].midi_chan)
            except:
                pass
        return free_chans

    def get_next_free_midi_chan(self, chan=0):
        """Get next unused MIDI channel

        chan : MIDI channel to search from (Default: 0)
        """

        free_chans = self.get_free_midi_chans()
        if chan is None:
            chan = 0
        for i in range(chan, MAX_NUM_MIDI_CHANS):
            if i in free_chans:
                return i
        for i in range(chan):
            if i in free_chans:
                return i
        raise Exception("No available free MIDI channels!")

    def get_num_chains_midi_chan(self, chan):
        """Get num of chains with MIDI channel

        chan : MIDI channel to search
        """

        try:
            return len(self.midi_chan_2_chain_ids[chan])
        except:
            return 0

    def get_free_mixer_chans(self):
        """Get list of unused mixer channels"""

        free_chans = list(range(MAX_NUM_MIXER_CHANS))
        for chain in self.chains:
            try:
                free_chans.remove(self.chains[chain].mixer_chan)
            except:
                pass
        return free_chans

    def get_next_free_mixer_chan(self, chan=0):
        """Get next unused mixer channel

        chan : mixer channel to search from (Default: 0)
        """

        free_chans = self.get_free_mixer_chans()
        for i in range(chan, MAX_NUM_MIXER_CHANS):
            if i in free_chans:
                return i
        for i in range(chan):
            if i in free_chans:
                return i
        raise Exception("No available free mixer channels!")

    def get_next_free_zmop_index(self):
        """Get next unused zmop index
        """

        busy_zmops = [0] * MAX_NUM_ZMOPS
        for chain_id in self.chains:
            try:
                busy_zmops[self.chains[chain_id].zmop_index] = 1
            except:
                pass
        for i in range(0, MAX_NUM_ZMOPS):
            if not busy_zmops[i]:
                return i
        return None

    def get_synth_processor(self, midi_chan):
        """Get a synth processor on MIDI channel
           If several synth chains in the same MIDI channel, take the first one.

        chan : MIDI channel
        Returns : Processor or None on failure
        """
        for chain_id in self.midi_chan_2_chain_ids[midi_chan]:
            processors = self.get_processors(chain_id, "MIDI Synth")
            if len(processors) > 0:
                return processors[0]
        return None

    def get_synth_preset_name(self, midi_chan):
        """Get the preset name for a synth on MIDI channel
           If several synth chains in the same MIDI channel, take the first one.

        chan : MIDI channel
        Returns : Preset name or None on failure
        """
        proc = self.get_synth_processor(midi_chan)
        if proc:
            return proc.get_preset_name()
        return None

    # ---------------------------------------------------------------------------
    # Extended Config
    # ---------------------------------------------------------------------------

    def get_zyngines_state(self):
        """Get state model for engines extended configuration as a dictionary"""

        # TODO: Although this relates to zyngine it may be advantageous to move to processor state
        state = {}
        for zyngine in self.zyngines.values():
            state[zyngine.nickname] = zyngine.get_extended_config()
        return state

# -----------------------------------------------------------------------------

# Call class method to get engine info into the "engine_info" class variable
zynthian_chain_manager.get_engine_info()

# -----------------------------------------------------------------------------
