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
from zyngine.zynthian_processor import *
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

        state_manager - State manager object
        """

        logging.warning("Creating chain manager")
        self.state_manager = state_manager
        self.chains = {}  # Map of chain objects indexed by chain id
        self.zyngine_counter = 0 # Appended to engine names for uniqueness
        self.zyngines = OrderedDict()  # List of instantiated engines
        self.active_chain = None # Active chain id
        self.midi_chan_2_chain = []  # Chains mapped by MIDI channel
        for i in range(16):
            self.midi_chan_2_chain.append(set())

        self.update_engine_info()
        self.add_chain("main", enable_audio_thru=True)

    def update_engine_info(self):
        """Update dictionary of available engines"""

        self.engine_info = OrderedDict([
            ["SL", ("SooperLooper", "SooperLooper",
                "Audio Effect", None, zynthian_engine_sooperlooper, True)],
            ["MX", ("Mixer", "ALSA Mixer",
                "MIXER", None, zynthian_engine_alsa_mixer, True)],
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
        if check_pianoteq_binary():
            pianoteq_title = "Pianoteq {}.{} {}{}".format(
                PIANOTEQ_VERSION[0],
                PIANOTEQ_VERSION[1],
                PIANOTEQ_PRODUCT,
                " (Demo)" if PIANOTEQ_TRIAL else "")
            self.engine_info['PT'] = (PIANOTEQ_NAME, pianoteq_title,
                "MIDI Synth", None, zynthian_engine_pianoteq, True)

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

        chain_id - Chain id
        midi_chan - Optional MIDI channel associated with chain (may be None)
        enable_midi_thru - True to enable MIDI thru for empty chain (Default: False)
        enable_audio_thru - True to enable audio thru for empty chain (Default: False)
        Returns - Chain object or None if chain could not be created
        """

        if chain_id in self.chains:
            return self.chains[chain_id]
        chain = zynthian_chain(midi_chan, enable_midi_thru, enable_audio_thru)
        if chain:
            self.chains[chain_id] = chain
        if midi_chan is not None and midi_chan < 16:
            self.midi_chan_2_chain[midi_chan].add(chain)
        self.active_chain = chain_id
        try:
            zynautoconnect.autoconnect(True)
        except:
            pass # May be before zynautoconnect started
        return chain

    def remove_chain(self, chain_id, stop_engines=True):
        """Removes a chain or resets "main" chain

        chain_id - ID of chain to remove
        stop_engines - True to stop unused engines
        Returns - True on success
        """

        if chain_id not in self.chains:
            return False
        chain = self.chains[chain_id]
        midi_chan = chain.midi_chan
        if midi_chan is not None and midi_chan < 16:
            try:
                self.midi_chan_2_chain[midi_chan].remove(chain)
            except:
                pass
        chain.reset()
        if stop_engines:
            self.stop_unused_engines()
        if chain_id != "main":
            self.chains.pop(chain_id)
            del chain
        return True

    def remove_all_chains(self, stop_engines=True):
        """Remove all chains

        stop_engines - True to stop orphaned engines
        Returns - True if all chains removed
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
        
        chain_id - Chain id
        inputs - List of jack sources or aliases (None to reset)
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
        
        chain_id - Chain id
        outputs - List of jack destinations or aliases (None to reset)
        """
        if chain_id in self.chains:
            if outputs:
                self.chains[chain_id].audio_out = outputs
            else:
                self.chains[chain_id].audio_out = ["MIXER"]
            self.chains[chain_id].rebuild_audio_graph()

    def enable_chain_audio_thru(self, chain_id, enable=True):
        """Enable/disable audio pass-through
        
        enable - True to pass chain's audio input to output when chain is empty 
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
        
        chain_id - Chain id
        inputs - List of jack sources or aliases (None to reset)
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
        
        chain_id - Chain id
        outputs - List of jack destinations or aliases (None to reset)
        """
        if chain_id in self.chains:
            if outputs:
                self.chains[chain_id].midi_out = outputs
            else:
                self.chains[chain_id].midi_out = ["MIDI-OUT", "NET-OUT"]
            self.chains[chain_id].rebuild_midi_graph()

    def enable_chain_midi_thru(self, chain_id, enable=True):
        """Enable/disable MIDI pass-through
        
        enable - True to pass chain's MIDI input to output when chain is empty 
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
    # Active Chain Management
    # ------------------------------------------------------------------------

    def set_active_chain_by_id(self, chain_id):
        """Select the active chain

        chain_id - ID of chain
        Returns - ID of active chain
        """

        if chain_id in self.chains:
            self.active_chain = chain_id
            # TODO: Select in lower-level module
        return self.active_chain

    def set_active_chain_by_object(self, chain_object):
        """Select the active chain
        
        chain_object - Chain object
        Returns - ID of active chain
        """

        for id in self.chains:
            if self.chains[id] == chain_object:
                self.set_active_chain_by_id(id)
                break
        return self.active_chain

    def next_chain(self):
        """Select the next chain as active

        Returns - Index of selected chain
        """

        chain_keys = sorted(self.chains)
        try:
            index = chain_keys.index(self.active_chain) + 1
        except:
            index = 0

        if len(chain_keys) > index:
            self.select_chain(chain_keys[index])
        return self.active_chain

    def previous_chain(self):
        """Select the previous chain as active
        Returns - Index of selected chain
        """

        chain_keys = sorted(self.chains)
        try:
            index = chain_keys.index(self.active_chain) - 1
        except:
            index = 0

        if len(chain_keys) > index and index >= 0:
            self.select_chain(chain_keys[index])
        return self.active_chain

    def get_active_chain(self):
        """Get the active chain object or None if no active chain"""
        if self.active_chain in self.chains:
            return self.chains[self.active_chain]
        return None

    # ------------------------------------------------------------------------
    # Processor Management
    # ------------------------------------------------------------------------

    def add_processor(self, chain_id, type, mode=CHAIN_MODE_SERIES, slot=None):
        """Add a processor to a chain

        chain - Chain ID
        type - Engine type
        mode - Chain mode [CHAIN_MODE_SERIES|CHAIN_MODE_PARALLEL]
        slot - Slot (position) within chain (0..last slot, Default: last slot)
        Returns - processor object or None on failure
        """

        if chain_id not in self.chains or type not in self.engine_info:
            return None
        processor = zynthian_processor.zynthian_processor(self.engine_info[type])
        chain = self.chains[chain_id]
        if chain.insert_processor(processor, mode, slot):
            engine = self.start_engine(processor, type)
            if engine:
                chain.generate_jackname_dict()
                chain.rebuild_graph()
                zynautoconnect.autoconnect(True)
                return processor
        del chain_id
        return None

    def remove_processor(self, chain_id, processor, stop_engine=True):
        """Remove a processor from a chain

        chain - Chain id
        processor - Instance of processor
        stop_engine - True to stop unused engine
        Returns - True on success
        """

        if chain_id not in self.chains:
            return False
        success = self.chains[chain_id].remove_processor(processor)
        if success and stop_engine:
            self.stop_unused_engines()
        zynautoconnect.autoconnect(True)
        return success

    def get_slot_count(self, chain_id, type=None):
        """Get the quantity of slots in a chain
        
        id - Chain id
        type - Processor type to filter result (Default: all types)
        Returns - Quantity of slots in chain or subchain
        """

        if chain_id not in self.chains:
            return 0
        return self.chains[chain_id].get_slot_count(type)

    def get_processor_count(self, chain_id=None, type=None, slot=None):
        """Get the quantity of processors in a slot
        
        chain_id - Chain id (Default: all processors)
        type - Processor type to filter result (Default: all types)
        slot - Index of slot or None for whole chain (Default: whole chain)
        Returns - Quantity of processors in (sub)chain or slot
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

        chain_id - Chain id (Default: all processors)
        type - Processor type to filter result (Default: all types)
        slot - Index of slot or None for whole chain (Default: whole chain)
        Returns - List of processor objects
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

        processor - processor owning engine
        engine - Engine nickname (short code)
        Returns - engine object
        """

        if engine in self.engine_info and engine not in self.zyngines:
            info = self.engine_info[engine]
            zynthian_engine_class = info[4]
            if engine[0:3] == "JV/":
                engine = "JV/{}".format(self.zyngine_counter)
                self.zyngines[engine] = zynthian_engine_class(
                    info[0], info[2], self, False)
            elif engine in ["SF"]:
                engine = "{}/{}".format(engine, self.zyngine_counter)
                self.zyngines[engine] = zynthian_engine_class()
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
            if len(self.zyngines[engine].layers) == 0 and engine[0:3] in ("JV/", "AP/"):
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
        
        jackname - stub of jackname
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
        for chain in self.chains:
            state[chain] = self.chains[chain].get_state()
        return state

    def set_state(self, state):
        """Create chains from state

        state - List of chain states
        Returns - True on success
        """

        #TODO: Cleare chains and create as required
        # Restore layer state, step 0 => bank list
        for i, lss in enumerate(state):
            self.chains[i].restore_state_0(lss)

        # Restore layer state, step 1 => Restore Bank & Preset Status
        for i, lss in enumerate(state):
            self.chains[i].restore_state_1(lss)

        # Restore layer state, step 2 => Restore Controllers Status
        for i, lss in enumerate(state):
            self.chains[i].restore_state_2(lss)

    def restore_presets(self):
        """Restore presets in active chain"""
        for processor in self.get_processors(self.active_chain):
            processor.restore_preset()

	#----------------------------------------------------------------------------
	# MIDI CC & Program Change (when ZS3 is disabled!)
	#----------------------------------------------------------------------------

    def midi_control_change(self, chan, ccnum, ccval):
        """Send MIDI CC message to relevant chain
        
        chan - MIDI channel
        ccnum - CC number
        ccval - CC value
        """

        if zynthian_gui_config.midi_bank_change and ccnum==0:
            for chain in self.midi_chan_2_chain[chan]:
                for processor in chain.get_processors():
                    processor.midi_bank_msb(ccval)
        elif zynthian_gui_config.midi_bank_change and ccnum==32:
            for chain in self.midi_chan_2_chain[chan]:
                for processor in chain.get_processors():
                    processor.midi_bank_lsb(ccval)
        else:
            for chain in self.midi_chan_2_chain[chan]:
                for processor in chain.get_processors():
                  processor.midi_control_change(chan, ccnum, ccval)
            #TODO: self.amixer_layer.midi_control_change(chan, ccnum, ccval)


    def set_midi_prog_preset(self, midich, prognum):
        """Send MIDI PC message to relevant chain
        
        chan - MIDI channel
        ccnum - CC number
        prognum - PC value
        """
        changed = False
        for chain in self.chains.values():
            try:
                mch = chain.midi_chan
                if mch is None or mch == midich:
                    # TODO This is really DIRTY!!
                    # Fluidsynth engine => ignore Program Change on channel 10
                    if chain.engine.nickname == "FS" and mch == 9:
                        continue
                    changed |= chain.set_preset(prognum, True)
            except Exception as e:
                logging.error("Can't set preset for CH#{}:PC#{} => {}".format(midich, prognum, e))
        return changed

    def get_free_midi_chans(self):
        """Get list of unused MIDI channels"""

        free_chans = list(range(16))
        for chain in self.chains:
            try:
                free_chans.remove(self.chains[chain].midi_chan)
            except:
                pass
        return free_chans

    def get_next_free_midi_chan(self, chan):
        """Get next unused MIDI channel
        
        chan - MIDI channel to search from
        """

        free_chans = self.get_free_midi_chans()
        for i in range(chan, 16):
            if i in free_chans:
                return i
        raise Exception("No available free MIDI channels!")
