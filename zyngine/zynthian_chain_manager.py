# -*- coding: utf-8 -*-
# ****************************************************************************
# ZYNTHIAN PROJECT: Zynthian Chain Manager (zynthian_chain_manager)
#
# zynthian chain manager
#
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
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
from time import sleep

# Zynthian specific modules
from zyngine import *
from zyngine.zynthian_processor import zynthian_processor
from zyngine.zynthian_engine_pianoteq import *
from zyngine.zynthian_engine_jalv import *
from zyngine.zynthian_chain import *
from zyngui import zynthian_gui_config #TODO: Factor out UI


# ----------------------------------------------------------------------------
# Zynthian Chain Manager Class
# ----------------------------------------------------------------------------

class zynthian_chain_manager():

    single_layer_engines = ["BF", "MD", "PT", "PD", "AE", "CS", "SL"]

    def __init__(self, state_manager):
        """ Create an instance of a chain manager

        Manages chains of audio and MIDI processors.
        Each chain consists of zero or more slots.
        Each slot may contain one or more processors.

        state_manager : State manager object
        """

        logging.warning("Creating chain manager")
        self.state_manager = state_manager
        self.chains = {}  # Map of chain objects indexed by chain id
        self.chain_ids_ordered = [] # List of chain IDs in order (excluding "main")
        self.zyngine_counter = 0 # Appended to engine names for uniqueness
        self.zyngines = OrderedDict()  # List of instantiated engines
        self.processors = {} # Dictionary of processor objects indexed by UID
        self.active_chain_id = None # Active chain id
        self.midi_chan_2_chain = [None] * 16  # Chains mapped by MIDI channel

        self.update_engine_info()
        self.add_chain("main", enable_audio_thru=True)

    def update_engine_info(self):
        """Update dictionary of available engines"""

        self.engine_info = OrderedDict([
            ["SL", ("SooperLooper", "SooperLooper",
                "Audio Effect", None, zynthian_engine_sooperlooper, True)],
            ["ZY", ("ZynAddSubFX", "ZynAddSubFX - Synthesizer",
                "MIDI Synth", None, zynthian_engine_zynaddsubfx, True)],
            ["FS", ("FluidSynth", "FluidSynth - SF2 Player",
                "MIDI Synth", None, zynthian_engine_fluidsynth, True)],
            ["SF", ("Sfizz", "Sfizz - SFZ Player",
                "MIDI Synth", None, zynthian_engine_sfizz, True)],
            ["LS", ("LinuxSampler", "LinuxSampler - SFZ/GIG Player",
                "MIDI Synth", None, zynthian_engine_linuxsampler, True)],
            ["BF", ("setBfree", "setBfree - Hammond Emulator",
                "MIDI Synth", None, zynthian_engine_setbfree, True)],
            ["AE", ("Aeolus", "Aeolus - Pipe Organ Emulator",
                "MIDI Synth", None, zynthian_engine_aeolus, True)],
            ["AP", ("AudioPlayer", "Audio File Player",
                "Special", None, zynthian_engine_audioplayer, True)],
            ['PD', ("PureData", "PureData - Visual Programming",
                "Special", None, zynthian_engine_puredata, True)],
            #['CS', ("CSound", "CSound Audio Language", "Special", None, zynthian_engine_csound, False)],
            ['MD', ("MOD-UI", "MOD-UI - Plugin Host",
                "Special", None, zynthian_engine_modui, True)]
        ])

        pt_info = get_pianoteq_binary_info()
        if pt_info:
            if pt_info['api']:
                self.engine_info['PT'] = ('Pianoteq', pt_info['name'], "MIDI Synth", None, zynthian_engine_pianoteq, True)
            else:
                self.engine_info['PT'] = ('Pianoteq', pt_info['name'], "MIDI Synth", None, zynthian_engine_pianoteq6, True)

        for plugin_name, plugin_info in get_jalv_plugins().items():
            engine = 'JV/{}'.format(plugin_name)
            self.engine_info[engine] = ( plugin_name, plugin_name,
                plugin_info['TYPE'], plugin_info.get('CLASS', None),
                zynthian_engine_jalv, plugin_info['ENABLED'])

    # ------------------------------------------------------------------------
    # Chain Management
    # ------------------------------------------------------------------------

    def add_chain(self, chain_id, midi_chan=None,
        enable_midi_thru=False, enable_audio_thru=False):
        """Add a chain

        chain_id: UID of chain (None to get next available)
        midi_chan : MIDI channel associated with chain
        enable_midi_thru : True to enable MIDI thru for empty chain (Default: False)
        enable_audio_thru : True to enable audio thru for empty chain (Default: False)
        Returns : Chain ID or None if chain could not be created
        """

        if chain_id is None:
            # Create new unique chain ID
            id = 0
            while f"{id:02}" in self.chains:
                id += 1
            chain_id = f"{id:02}"
        if chain_id == "main":
            enable_midi_thru = False
            enable_audio_thru = True
        if chain_id in self.chains:
            self.chains[chain_id].midi_thru = enable_midi_thru
            self.chains[chain_id].audio_thru = enable_audio_thru
            return self.chains[chain_id]
        else:
            chain = zynthian_chain(midi_chan, enable_midi_thru, enable_audio_thru)
            if chain:
                self.chains[chain_id] = chain

        self.set_midi_chan(chain_id, midi_chan)
        if enable_audio_thru:
            if chain_id == "main":
                chain.set_mixer_chan(256)
            else:
                chain.set_mixer_chan(self.get_next_free_mixer_chan())
        self.set_active_chain_by_id(chain_id)
        self.update_chain_ids_ordered()
        self.state_manager.autoconnect(True)
        return chain_id

    def remove_chain(self, chain_id, stop_engines=True):
        """Removes a chain or resets "main" chain

        chain_id : ID of chain to remove
        stop_engines : True to stop unused engines
        Returns : True on success
        """

        if chain_id not in self.chains:
            return False
        chains_to_remove = [chain_id] # List of associated chains that shold be removed simultaneously
        chain = self.chains[chain_id]
        if chain.synth_slots and chain.synth_slots[0][0].type_code in ["BF", "AE"]:
            #TODO: We remove all setBfree and Aeolus chains but maybe we should allow chain manipulation
            for id, ch in self.chains.items():
                if ch != chain and ch.synth_slots and ch.synth_slots[0][0].type_code == chain.synth_slots[0][0].type_code:
                    chains_to_remove.append(id)

        for chain_id in chains_to_remove:
            chain = self.chains[chain_id]
            midi_chan = chain.midi_chan
            if chain.mixer_chan is not None:
                self.state_manager.zynmixer.set_mute(chain.mixer_chan, True, True)
            if isinstance(midi_chan, int) and midi_chan < 16:
                self.midi_chan_2_chain[midi_chan] = None
            for processor in chain.get_processors():
                try:
                    self.processors.pop(processor.id)
                except Exception as e:
                    pass
            chain.reset()
            if chain.mixer_chan is not None:
                self.state_manager.zynmixer.reset(chain.mixer_chan)
            if chain_id != "main":
                self.chains.pop(chain_id)
                del chain
        if stop_engines:
            self.stop_unused_engines()
        self.update_chain_ids_ordered()
        self.state_manager.autoconnect(True)
        if self.active_chain_id not in self.chains:
            self.next_chain()
        return True

    def remove_all_chains(self, stop_engines=True):
        """Remove all chains

        stop_engines : True to stop orphaned engines
        Returns : True if all chains removed
        Note: Chain "main" is retained but reset
        """

        success = True
        for chain in list(self.chains.keys()):
            success &= self.remove_chain(chain, stop_engines)
        return success

    def get_chain_count(self):
        """Get the quantity of chains"""

        return len(self.chains)

    def get_chain(self, chain_id):
        """Get a chain object by id"""

        if chain_id in self.chains:
            return self.chains[chain_id]
        return None

    def get_chain_id_by_processor(self, processor):
        """Get ID of chain that contains processor
        
        processor : Processor object
        Returns : Chain ID or None if not found
        """

        for chain_id in self.chains:
            for proc in self.get_processors(chain_id):
                if processor == proc:
                    return chain_id

    def update_chain_ids_ordered(self):
        """Update list of chain IDs in mixer & midi channel order (excluding "main")"""

        chains = {}
        for chain_id, chain in self.chains.items():
            if chain_id != "main":
                try:
                    midi_chan = f"{chain.midi_chan:02d}"
                except:
                    midi_chan = "X"
                try:
                    mixer_chan = f"{chain.mixer_chan:02d}"
                except:
                    mixer_chan = "X"
                chains[f"{midi_chan} {mixer_chan}"] = chain_id
        sorted_keys = sorted(chains)
        self.chain_ids_ordered = []
        for key in sorted_keys:
            self.chain_ids_ordered.append(chains[key])
        return self.chain_ids_ordered

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
                self.chains[chain_id].audio_out = ["mixer"]
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

    # ------------------------------------------------------------------------
    # 
    # Chain Management
    # ------------------------------------------------------------------------

    def set_active_chain_by_id(self, chain_id=None):
        """Select the active chain

        chain_id : ID of chain (Default: Reassert current active channel)
        Returns : ID of active chain
        """

        if chain_id == None:
            chain_id = self.active_chain_id
        try:
            chain = self.chains[chain_id]
            self.active_chain_id = chain_id
            # Update active MIDI channel
            if zynthian_gui_config.midi_single_active_channel:
                midi_chan = chain.midi_chan
                if isinstance(midi_chan, int) and midi_chan < 16:
                    get_lib_zyncore().set_midi_active_chan(midi_chan)
                else:
                    # Check if currently selected channel is valid
                    midi_chan = get_lib_zyncore().get_midi_active_chan()
                    if midi_chan >= 0 and midi_chan < 16 and self.midi_chan_2_chain[midi_chan]:
                        return
                    # Find a MIDI chain
                    for chain in self.chains.values():
                        if chain.is_midi():
                            get_lib_zyncore().set_midi_active_chan(chain.midi_chan)
                            break
            else:
                get_lib_zyncore().set_midi_active_chan(-1)
        except:
            pass
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

    def next_chain(self, nudge=1):
        """Select the next chain as active

        nudge : Quantity of chains to step (may be negative, default: 1)
        Returns : Index of selected chain
        """

        chain_keys = self.chain_ids_ordered + ["main"]
        try:
            index = chain_keys.index(self.active_chain_id) + nudge
        except:
            index = 0

        if index >= len(chain_keys):
            chain_id = chain_keys[-1]
        elif index <= 0:
            chain_id = chain_keys[0]
        else:
            chain_id = chain_keys[index]
        return self.set_active_chain_by_id(chain_id)

    def previous_chain(self, nudge=1):
        """Select the previous chain as active

        nudge : Quantity of chains to step (may be negative, default: 1)
        Returns : Index of selected chain
        """
        return self.next_chain(-nudge)

    def get_active_chain(self):

        """Get the active chain object or None if no active chain"""
        if self.active_chain_id in self.chains:
            return self.chains[self.active_chain_id]
        return None

    def will_route_howl(self, src_id, dst_id, node_list=None):
        """Checks if adding a connection will cause a howl-round loop
        
        src_id : Chain ID of the source chain
        dst_id : Chain ID of the destination chain
        node_list : Do not use - internal function parameter
        Returns : True if adding the route will cause howl-round feedback loop
        """

        if dst_id not in self.chains:
            return False
        if src_id:
            # src_id only provided on first call (not re-entrant cycles)
            if src_id not in self.chains:
                return False
            node_list = [src_id] # Init node_list on first call
        if dst_id in node_list:
            return True
        node_list.append(dst_id)
        for chain_id in self.chains[dst_id].midi_out:
            if chain_id in self.chains:
                if self.will_route_howl(None, chain_id, node_list):
                    return True
                node_list.append(chain_id)
        return False

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

    def add_processor(self, chain_id, type, parallel=False, slot=None, proc_id=None):
        """Add a processor to a chain

        chain : Chain ID
        type : Engine type
        parallel : True to add in parallel (same slot) else create new slot (Default: series)
        slot : Slot (position) within subchain (0..last slot, Default: last slot)
        proc_id : Processor UID (Default: Use next available ID)
        Returns : processor object or None on failure
        """

        if (chain_id not in self.chains or type not in self.engine_info
            or proc_id is not None and proc_id in self.processors):
            return None
        if proc_id is None:
            proc_id = self.get_available_processor_id() #TODO: Derive next available processor id from self.processors
        elif proc_id in self.processors:
            return None
        processor = zynthian_processor(type, self.engine_info[type], proc_id)
        chain = self.chains[chain_id]
        self.processors[proc_id] = processor # Add proc early to allow engines to add more as required, e.g. Aeolus
        if chain.insert_processor(processor, parallel, slot):
            if chain.mixer_chan is None and processor.type != "MIDI Tool": #TODO: Fails to detect MIDI only chains in snapshots
                chain.mixer_chan = self.get_next_free_mixer_chan()
            engine = self.start_engine(processor, type)
            if engine:
                chain.rebuild_graph()
                self.state_manager.autoconnect(True)
                return processor
        del self.processors[proc_id] # Failed so remove processor from list
        return None

    def remove_processor(self, chain_id, processor, stop_engine=True):
        """Remove a processor from a chain

        chain : Chain id
        processor : Instance of processor
        stop_engine : True to stop unused engine
        Returns : True on success
        """

        if chain_id not in self.chains:
            return False
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
        self.state_manager.autoconnect(True)
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

    def start_engine(self, processor, engine):
        """Starts or reuse an existing engine

        processor : processor owning engine
        engine : Engine nickname (short code)
        Returns : engine object
        """

        if engine in self.engine_info and engine not in self.zyngines:
            info = self.engine_info[engine]
            zynthian_engine_class = info[4]
            if engine[0:3] == "JV/":
                engine = "JV/{}".format(self.zyngine_counter)
                self.zyngines[engine] = zynthian_engine_class(
                    info[0], info[2], self.state_manager, False)
            elif engine in ["SF"]:
                engine = "{}/{}".format(engine, self.zyngine_counter)
                self.zyngines[engine] = zynthian_engine_class(self.state_manager)
            else:
                self.zyngines[engine] = zynthian_engine_class(self.state_manager)

        processor.set_engine(self.zyngines[engine])
        self.zyngine_counter += 1
        return self.zyngines[engine]

    def stop_unused_engines(self):
        """Stop engines that are not used by any processors"""

        for engine in list(self.zyngines.keys()):
            if not self.zyngines[engine].layers:
                logging.debug("Stopping Unused Engine '{}' ...".format(engine))
                self.zyngines[engine].stop()
                del self.zyngines[engine]

    def stop_unused_jalv_engines(self):
        """Stop JALV engines that are not used by any processors"""
        for engine in list(self.zyngines.keys()):
            if len(self.zyngines[engine].layers) == 0 and engine[0:3] in ("JV/"):
                self.zyngines[engine].stop()
                del self.zyngines[engine]

    def filtered_engines_by_cat(self, type):
        """Get dictionary of engine info filtered by type and indexed by catagory"""
        result = OrderedDict()
        for eng, info in self.engine_info.items():
            eng_type = info[2]
            cat = info[3]
            enabled = info[5]
            if enabled and (eng_type == type or type is None) and (eng not in self.single_layer_engines or eng not in self.zyngines):
                if cat not in result:
                    result[cat] = OrderedDict()
                result[cat][eng] = info
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
            while "{}-{:02d}".format(jackname, i) in names:
                i += 1
            return "{}-{:02d}".format(jackname, i)
        except Exception as e:
            logging.error(e)
            return "{}-00".format(jackname)

    # ------------------------------------------------------------------------
    # State Management
    # ------------------------------------------------------------------------

    def get_state(self):
        """Get dictionary of chain slot states indexed by chain id"""

        state = {}
        for chain_id, chain in self.chains.items():
            state[chain_id] = chain.get_state()
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

        # Clean all chains but don't stop unused engines
        self.remove_all_chains(False)

        # Reusing Jalv engine instances raise problems (audio routing & jack names, etc..),
        # so we stop Jalv engines!
        self.stop_unused_jalv_engines() #TODO: Can we factor this out?

        for chain_id, chain_state in state.items():
            midi_chan = None
            midi_thru = False
            audio_thru = False
            if 'midi_chan' in chain_state:
                midi_chan = chain_state['midi_chan']
                del chain_state['midi_chan']
            if 'midi_thru' in chain_state:
                midi_thru = chain_state['midi_thru']
                del chain_state['midi_thru']
            if 'audio_thru' in chain_state:
                audio_thru = chain_state['audio_thru']
                del chain_state['audio_thru']
            self.add_chain(chain_id, midi_chan, midi_thru, audio_thru)
            chain = self.get_chain(chain_id)
            if chain:
                chain.set_state(chain_state)

            if "slots" in chain_state:
                for slot_state in chain_state["slots"]:
                    # slot_state is a dict of proc_id:proc_type for procs in this slot
                    for index, proc_id in enumerate(slot_state):
                        # Use index to identify first proc in slot (add in series) - others are added in parallel
                        if index:
                            self.add_processor(chain_id, slot_state[proc_id], CHAIN_MODE_PARALLEL, proc_id=int(proc_id))
                        else:
                            self.add_processor(chain_id, slot_state[proc_id], CHAIN_MODE_SERIES, proc_id=int(proc_id))

    def restore_presets(self):
        """Restore presets in active chain"""

        for processor in self.get_processors(self.active_chain_id):
            processor.restore_preset()

	#----------------------------------------------------------------------------
	# MIDI CC & Program Change (when ZS3 is disabled!)
	#----------------------------------------------------------------------------

    def midi_control_change(self, chan, ccnum, ccval):
        """Send MIDI CC message to relevant chain
        
        chan : MIDI channel
        ccnum : CC number
        ccval : CC value
        """

        chain = self.midi_chan_2_chain[chan]
        if not chain:
            return
        if zynthian_gui_config.midi_bank_change and ccnum==0:
            for processor in chain.get_processors():
                processor.midi_bank_msb(ccval)
        elif zynthian_gui_config.midi_bank_change and ccnum==32:
            for processor in chain.get_processors():
                processor.midi_bank_lsb(ccval)
        else:
            for processor in chain.get_processors():
                processor.midi_control_change(chan, ccnum, ccval)
            self.state_manager.alsa_mixer_processor.midi_control_change(chan, ccnum, ccval)


    def set_midi_prog_preset(self, midich, prognum):
        """Send MIDI PC message to relevant chain
        
        chan : MIDI channel
        ccnum : CC number
        prognum : PC value
        """
        changed = False
        for processor in self.processors.values():
            try:
                mch = processor.midi_chan
                if mch is None or mch == midich:
                    # TODO This is really DIRTY!!
                    # Fluidsynth engine => ignore Program Change on channel 10
                    if processor.engine.nickname == "FS" and mch == 9:
                        continue
                    changed |= processor.set_preset(prognum, True)
            except Exception as e:
                logging.error("Can't set preset for CH#{}:PC#{} => {}".format(midich, prognum, e))
        return changed

    def set_midi_chan(self, chain_id, midi_chan):
        """Set chain MIDI channel

        chain_id : Chain ID
        midi_chan : MIDI channel
        """

        if chain_id not in self.chains:
            return
        chain = self.chains[chain_id]
        try:
            self.midi_chan_2_chain[chain.midi_chan] = None
        except:
            pass
        try:
            self.midi_chan_2_chain[midi_chan] = chain
        except:
            pass
        chain.set_midi_chan(midi_chan)
        self.update_chain_ids_ordered()

    def get_free_mixer_chans(self):
        """Get list of unused mixer channels"""

        free_chans = list(range(16))
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
        for i in range(chan, 16):
            if i in free_chans:
                return i
        for i in range(chan):
            if i in free_chans:
                return i
        raise Exception("No available free mixer channels!")

    def get_free_midi_chans(self):
        """Get list of unused MIDI channels"""

        free_chans = list(range(16))
        for chain in self.chains:
            try:
                free_chans.remove(self.chains[chain].midi_chan)
            except:
                pass
        return free_chans

    def get_next_free_midi_chan(self, chan=0):
        """Get next unused MIDI channel
        
        chan : MIDI channel to search from (Default: 0)
        """

        free_chans = self.get_free_midi_chans()
        for i in range(chan, 16):
            if i in free_chans:
                return i
        for i in range(chan):
            if i in free_chans:
                return i
        raise Exception("No available free MIDI channels!")

    # ---------------------------------------------------------------------------
    # Extended Config
    # ---------------------------------------------------------------------------

    def get_zyngines_state(self):
        """Get state model for engines extended configuration as a dictionary"""

        #TODO: Although this relates to zyngine it may be advantageous to move to processor state
        state = {}
        for zyngine in self.zyngines.values():
            state[zyngine.nickname] = zyngine.get_extended_config()
        return state

