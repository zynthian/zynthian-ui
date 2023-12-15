# -*- coding: utf-8 -*-
# *****************************************************************************
# ZYNTHIAN PROJECT: Zynthian Chain (zynthian_chain)
#
# zynthian chain
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <riban@zynthian.org>
#
# *****************************************************************************
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
# *****************************************************************************

import logging

# Zynthian specific modules
import zynautoconnect
from zyncoder.zyncore import lib_zyncore

CHAIN_MODE_SERIES = 0
CHAIN_MODE_PARALLEL = 1


class zynthian_chain:

    # ------------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------------

    def __init__(self, chain_id, midi_chan=None, midi_thru=False, audio_thru=False):
        """ Create an instance of a chain

        A chain contains zero or more slots.
        Each slot may contain one or more processing processors.
        Processors receive audio/MIDI input from the previous slot.
        Processors in first slot use the chain's audio/MIDI input.
        An empty chain with audio input configured is pass-through.
        An empty chain with MIDI input configured is pass-through.
        Pass-through disabled by default.

        midi_chan : Optional MIDI channel for chain input / control
        midi_thru : True to enable MIDI thru for empty chain
        audio_thru : True to enable audio thru for empty chain
        """

        # Each slot contains a list of parallel processors
        self.midi_slots = []  # Midi subchain (list of lists of processors)
        self.audio_slots = []  # Audio subchain (list of lists of processors)
        self.synth_slots = []  # Synth/generator/special slots (should be single slot)

        self.chain_id = chain_id  # Chain's ID
        self.midi_chan = midi_chan  # Chain's MIDI channel - None for purely audio chain, 0xffff for *All Chains*
        self.mixer_chan = None
        self.zmop_index = None
        self.midi_thru = midi_thru  # True to pass MIDI if chain empty
        self.audio_thru = audio_thru  # True to pass audio if chain empty
        self.midi_in = []
        self.midi_out = []
        self.audio_in = []
        self.audio_out = []

        self.status = ""  # Arbitary status text
        self.current_processor = None  # Selected processor object
        self.title = None  # User defined title for chain
        self.midi_routes = {}  # Map of MIDI routes indexed by jackname
        self.audio_routes = {}  # Map of audio routes indexed by jackname
        self.reset()

    def reset(self):
        """ Resets chain, removing all processors

        types : list of processor types for pass-through
        stop_engines : True to stop unused engines
        Does not change midi/audio thru
        """

        if self.chain_id == 0:
            self.title = "Main"
        else:
            self.title = ""

        if isinstance(self.midi_chan, int) and 0 <= self.midi_chan < 16:
            lib_zyncore.reset_midi_filter_note_range(self.midi_chan)
            lib_zyncore.reset_midi_filter_clone(self.midi_chan)

        self.free_zmop()
        self.midi_out = []

        self.audio_in = [1, 2]
        self.audio_out = ["mixer"]
        # main mixbus chain
        if self.mixer_chan and self.mixer_chan > 15:
            self.audio_in = ["zynmixer:send"]
            self.audio_out = ["zynmixer:return"]
            self.audio_thru = True

        self.current_processor = None
        self.remove_all_processors()

    def get_slots_by_type(self, type):
        """Get the list of slots

        type : Processor tye
        Returns : Slot list object
        """
        if type == "MIDI Tool":
            return self.midi_slots
        elif type == "Audio Effect":
            return self.audio_slots
        else:
            return self.synth_slots

    def get_type(self):
        if self.synth_slots:
            return "MIDI Synth"
        elif self.get_slot_count("Audio Effect"):
            return "Audio Effect"
        elif self.get_slot_count("MIDI Tool"):
            return "MIDI Tool"
        else:
            return "Empty"

    # ----------------------------------------------------------------------------
    # Chain Management
    # ----------------------------------------------------------------------------

    def set_mixer_chan(self, chan):
        """Set chain mixer channel

        chan : Mixer channel 0..15, 255 or None
        """

        self.mixer_chan = chan
        if chan == 255:
            self.audio_in = ["zynmixer:send"]
            self.audio_out = ["zynmixer:return"]
            self.audio_thru = True

        self.rebuild_audio_graph()

    def set_zmop_options(self):
        if self.zmop_index is not None and (len(self.synth_slots) > 0 or len(self.audio_slots) > 0):
            #logging.info(f"Dropping MIDI CC & PC from chain {self.chain_id}")
            lib_zyncore.zmop_set_flag_droppc(self.zmop_index, 1)
            lib_zyncore.zmop_set_flag_dropcc(self.zmop_index, 1)
        else:
            #logging.info(f"Routing MIDI CC & PC to chain {self.chain_id}")
            lib_zyncore.zmop_set_flag_droppc(self.zmop_index, 0)
            lib_zyncore.zmop_set_flag_dropcc(self.zmop_index, 0)

    def set_zmop_index(self, iz):
        """Set chain zmop index

        iz : 0...16 (TODO: get maximum number of chains from lib_zyncore!)
        """
        self.free_zmop()
        if isinstance(iz, int) and iz >= 0:
            self.zmop_index = iz
            self.midi_in = [f"ZynMidiRouter:ch{iz}_out"]
            if isinstance(self.midi_chan, int):
                if 0 <= self.midi_chan < 16:
                    lib_zyncore.zmop_set_midi_chan(iz, self.midi_chan)
                elif self.midi_chan == 0xffff:
                    lib_zyncore.zmop_set_midi_chan_all(iz)

    def free_zmop(self):
        """If already using a zmop, release and reset it
        """
        if isinstance(self.zmop_index, int) and self.zmop_index >= 0:
            lib_zyncore.zmop_reset_midi_chans(self.zmop_index)
        self.zmop_index = None
        self.midi_in = []

    def set_midi_chan(self, chan):
        """Set chain (and its processors) MIDI channel

        chan : MIDI channel 0..15 or None
        """

        if self.midi_chan == lib_zyncore.get_midi_active_chan():
            lib_zyncore.set_midi_active_chan(chan)
        self.midi_chan = chan
        if isinstance(self.zmop_index, int) and self.zmop_index >= 0 and isinstance(self.midi_chan, int):
            if 0 <= self.midi_chan < 16:
                lib_zyncore.zmop_set_midi_chan(self.zmop_index, self.midi_chan)
            elif self.midi_chan == 0xffff:
                lib_zyncore.zmop_set_midi_chan_all(self.zmop_index)
        for processor in self.get_processors():
            processor.set_midi_chan(chan)

    def set_title(self, title):
        """ Set user defined title
        
        title : Chain title (None to use processor title
        """

        self.title = title

    def get_title(self):
        """Get chain title

        Returns : User defined chain title or processor title if not set
        """

        if title:
            return self.title
        else:
            return self.get_description_parts()[0]

    def get_description_parts(self, basepath=False, preset=False):
        """Get chain description parts, using synth or first processor

            - basepath: use engine's basepath or name
            - preset: include the selected preset
        """
        parts = []
        try:
            if self.title:
                parts.append(self.title)
            elif self.chain_id == 0:
                parts.append("Main")
            elif self.audio_thru:
                parts.append("Audio Input " + ','.join([str(i) for i in self.audio_in]))

            if self.synth_slots:
                proc = self.synth_slots[0][0]
            elif self.get_slot_count("Audio Effect"):
                proc = self.get_processors("Audio Effect")[0]
            elif self.get_slot_count("MIDI Tool"):
                proc = self.get_processors("MIDI Tool")[0]

            if proc:
                if basepath:
                    parts.append(proc.get_basepath())
                else:
                    parts.append(proc.get_name())
                if preset:
                    preset_name = proc.get_preset_name()
                    if preset_name:
                        parts.append(preset_name)
            elif not parts:
                parts.append(f"Chain {self.chain_id}")
        except:
            pass
        return parts

    def get_description(self, n_lines=None):
        """Get chain description text

            n_lines: Max number of lines. None is "All"
        """
        parts = self.get_description_parts(basepath=False, preset=True)
        return "\n".join(parts[:n_lines])


    def get_name(self):
        """Get chain name (short title)

        Returns : User defined chain title or default processor name if not set
        """
        parts = self.get_description_parts(basepath=True, preset=False)
        if parts:
            return parts[0]
        else:
            return ""



    # ----------------------------------------------------------------------------
    # Routing Graph
    # ----------------------------------------------------------------------------

    def rebuild_audio_graph(self):
        """Build dictionary of lists of sources mapped by destination"""

        #TODO: This is called too frequently
        #TODO: Handle side-chaining - maybe manually curate list of sidechain destinations
        if not zynautoconnect.acquire_lock():
            return

        self.audio_routes = {}
        # Add effects chain routes
        for i, slot in enumerate(self.audio_slots):
            for processor in slot:
                sources = []
                if i == 0:
                    # First slot fed from synth or chain input
                    if self.synth_slots:
                        for proc in self.synth_slots[-1]:
                            sources.append(proc.get_jackname())
                    elif self.audio_thru:
                        sources = self.get_input_pairs()
                    self.audio_routes[processor.get_jackname()] = sources
                else:
                    for prev_proc in self.audio_slots[i - 1]:
                        sources.append(prev_proc.get_jackname())
                    self.audio_routes[processor.get_jackname()] = sources

        # Add special processor inputs
        if self.synth_slots and self.synth_slots[0]:
            processor = self.synth_slots[0][0]
            if processor.type == "Special":
                sources = self.get_input_pairs()
                self.audio_routes[processor.get_jackname()] = sources

        if self.mixer_chan is not None:
            mixer_source = []
            if self.audio_slots:
                # Routing from last audio processor
                for source in self.audio_slots[-1]:
                    mixer_source.append(source.get_jackname())
            elif self.synth_slots:
                # Routing from synth processor
                for proc in self.synth_slots[0]:
                    mixer_source.append(proc.get_jackname())
            elif self.audio_thru:
                # Routing from capture ports
                mixer_source = self.get_input_pairs()
            for output in self.get_audio_out():
                try:
                    self.audio_routes[output.get_jackname()] = mixer_source
                except:
                    self.audio_routes[output] = mixer_source
            if "mixer" not in self.audio_out:
                self.audio_routes["zynmixer:input_{:02d}".format(self.mixer_chan + 1)] = []

        zynautoconnect.release_lock()

    def get_input_pairs(self):
        """Get jack regexp for pairs of system:capture ports
        
        Returns : List of regexps
        """
        
        if self.audio_in == ["zynmixer:send"]:
            return self.audio_in.copy()
        sources = []
        for i in range(0, len(self.audio_in), 2):
            a = self.audio_in[i]
            if i < len(self.audio_in) - 1:
                b = self.audio_in[i + 1]
                sources.append(f"system:capture_({a}|{b})$")
            else:
                sources.append(f"system:capture_({a})$")
        return sources


    def rebuild_midi_graph(self):
        """Build dictionary of lists of sources mapped by destination"""

        if not zynautoconnect.acquire_lock():
            return
 
        self.midi_routes = {}
        for i, slot in enumerate(self.midi_slots):
            if i == 0:
                continue # Chain inputs are handled by autoconnect
            for processor in slot:
                sources = []
                for prev_proc in self.midi_slots[i - 1]:
                    sources.append(prev_proc.get_jackname())
                self.midi_routes[processor.get_jackname()] = sources

        if self.synth_slots:
            sources = []
            if len(self.midi_slots):
                for prev_proc in self.midi_slots[-1]:
                    sources.append(prev_proc.get_jackname())
                for proc in self.synth_slots[0]:
                    self.midi_routes[proc.engine.jackname] = sources
        elif len(self.midi_slots) == 0 and self.midi_thru:
            for output in self.midi_out:
                self.midi_routes[output] = self.midi_in

        zynautoconnect.release_lock()

    def rebuild_graph(self):
        """Build dictionary of lists of destinations mapped by source"""

        self.rebuild_midi_graph()
        self.rebuild_audio_graph()

    def get_audio_out(self):
        """Get list of audio playback ports"""

        audio_out = []
        for output in self.audio_out:
            if output == "mixer":
                if self.mixer_chan < 17:
                    audio_out.append("zynmixer:input_{:02d}".format(self.mixer_chan + 1))
                else:
                    audio_out.append("zynmixer:return")
            else:
                audio_out.append(output)
        return audio_out


    def toggle_audio_out(self, processor):
        """Toggle processor audio output

        processor : Porcessor ID or "mixer" or "system"
        """

        if processor not in self.audio_out:
            self.audio_out.append(processor)
        else:
            try:
                self.audio_out.remove(processor)
            except:
                pass
        logging.debug(f"Toggling Audio Output: {processor}")

        self.rebuild_audio_graph()
        zynautoconnect.request_audio_connect()

    def toggle_audio_in(self, input):
        """Toggle processor audio in
        
        input : Index of audio input
        """

        if input in self.audio_in:
            self.audio_in.remove(input)
        else:
            self.audio_in.append(input)

        self.rebuild_audio_graph()
        zynautoconnect.request_audio_connect()

    def get_midi_out(self):
        return self.midi_out

    def toggle_midi_out(self, jackname):
        if jackname not in self.midi_out:
            self.midi_out.append(jackname)
        else:
            self.midi_out.remove(jackname)

        self.rebuild_midi_graph()
        zynautoconnect.request_midi_connect()

    def is_audio(self):
        """Returns True if chain is processes audio"""

        return self.mixer_chan is not None
        # or self.audio_thru or len(self.audio_slots) > 0 or len(self.synth_slots) > 0

    def is_midi(self):
        """Returns True if chain processes MIDI"""

        return isinstance(self.midi_chan, int)
        # or self.midi_thru or len(self.midi_slots) > 0

    # ---------------------------------------------------------------------------
    # Processor management
    # ---------------------------------------------------------------------------

    def get_slot_count(self, type=None):
        """Get quantity of slots in chain

        type : processor type ['MIDI Tool'|'Audio Effect', etc.] (Default: None=whole chain)
        Returns : Quantity of slots in chain (section)
        """

        if type is None:
            return len(self.midi_slots) + len(self.audio_slots) + len(self.synth_slots)
        elif type == "MIDI Tool":
            return len(self.midi_slots)
        elif type == "Audio Effect":
            return len(self.audio_slots)
        else:
            return len(self.synth_slots)

    def get_processor_count(self, type=None, slot=None):
        """Get quantity of processors in chain (slot)

        type : processor type to filter results (Default: whole chain)
        slot : Index of slot or None for whole chain (Default: whole chain)
        Returns : Quantity of processors in (sub)chain or slot
        """

        count = 0
        if type is None:
            if slot is None or slot < 0:
                for j in self.midi_slots +self.synth_slots + self.audio_slots:
                    count += len(j)
        else:
            slots = self.get_slots_by_type(type)

            if slot is None or slot < 0:
                for j in slots:
                    count += len(j)
            else:
                if slot < slots:
                    count = len(slots[slot])
        return count

    def get_processors(self, type=None, slot=None):
        """Get list of processor objects in chain

        type : processor type to filter result (Default: All processors)
        slot : Index of slot or None for whole chain
        Returns : List of processor objects
        """

        processors = []
        if type is None:
            if slot is None:
                for j in self.midi_slots + self.synth_slots + self.audio_slots:
                    processors += j
                return processors
            if slot < len(self.midi_slots):
                return self.midi_slots[slot]
            slot -= len(self.midi_slots)
            if slot < len(self.synth_slots):
                return self.synth_slots[slot]
            slot -= len(self.synth_slots)
            if slot < len(self.audio_slots):
                return self.audio_slots[slot]
        else:
            slots = self.get_slots_by_type(type) 
            if slot is None or slot < 0:
                for j in slots:
                    processors += j
            else:
                if slot < len(slots):
                    processors = slots[slot]
        return processors

    def insert_processor(self, processor, parallel=False, slot=None):
        """Insert a processor in the chain

        processor : processor object to insert
        parallel : True to add in parallel (same slot) else create new slot (Default: series)
        slot : Position (slot) to insert within subchain (Default: End of chain)
        Returns : True if processor added to chain
        """

        slots = self.get_slots_by_type(processor.type)
        if len(slots) == 0:
            slots.append([processor])
        else:
            if slot is None or slot < 0 or slot > len(slots):
                slot = len(slots) - 1
            if parallel:
                slots[slot].append(processor)
            else:
                slots.insert(slot + 1, [processor])

        processor.set_chain_id(self.chain_id)
        processor.set_midi_chan(self.midi_chan)

        self.set_zmop_options()
        self.current_processor = processor
        return True

    def replace_processor(self, old_processor, new_processor):
        """Replace a processor within a chain

        old_processor : processor object to replace
        new_processor : processor object to add to chain
        Returns : True if processor was replaced
        """

        slots = self.get_slots_by_type(old_processor.type)
        for i, slot in enumerate(slots):
            for j, processor in enumerate(slot):
                if processor == old_processor:
                    self.slots[i][j] = new_processor
                    self.remove_processor(old_processor)
                    self.rebuild_graph()
                    new_processor.set_midi_chan(self.midi_chan)
                    zynautoconnect.request_audio_connect()
                    zynautoconnect.request_midi_connect()
                    if self.current_processor == old_processor:
                        self.current_processor = new_processor
                    return True
        return False

    def remove_processor(self, processor):
        """Remove a processor from chain

        processor : processor object to remove
        Returns : True on success
        """

        slot = self.get_slot(processor)
        if slot is None:
            logging.error("processor is not in chain!")
            return False

        logging.debug("Removing processor {}".format(processor.get_jackname()))

        slots = self.get_slots_by_type(processor.type)
        slots[slot].remove(processor)
        if len(slots[slot]) == 0:
            slots.pop(slot)

        processor.set_chain_id(None)
        if processor.engine:
            processor.engine.remove_processor(processor)

        self.set_zmop_options()
        self.rebuild_graph()

        if processor == self.current_processor:
            if slots:
                self.current_processor = slots[0][0]
            elif self.synth_slots:
                self.current_processor = self.synth_slots[0][0]
            elif self.audio_slots:
                self.current_processor = self.audio_slots[0][0]
            elif self.midi_slots:
                self.current_processor = self.midi_slots[0][0]
            else:
                self.current_processor = None

        #del processor => I don't think this is needed nor right?? (Jofemodo)
        return True

    def remove_all_processors(self):
        """Remove all processors from chain

        stop_engines : True to stop the processors' worker engines
        """

        for processor in self.get_processors():
            self.remove_processor(processor)

    def move_processor(self, processor, slot):
        """Move processor to different slot

        processor : Processor object
        slot : Index of slot to move process to
        Fails if slot does not exist
        """

        try:
            slots = self.get_slots_by_type(processor.type)
            if slot < 0:
                slots.insert(0, [])
                slot = 0
            elif slot >= len(slots):
                slots.append([])
            cur_slot = self.get_slot(processor)
            slots[cur_slot].remove(processor)
            slots[slot].append(processor)
            while [] in slots:
                slots.remove([])
            self.rebuild_graph()
            zynautoconnect.request_audio_connect()
            zynautoconnect.request_midi_connect()
        except:
            logging.error("Failed to move processor")

    def swap_processors(self, processor1, processor2):
        """Swap two processors in chain

        processor1 : First processor object to swap
        processor2 : Second processor object to swap
        Returns : True on success
        """

        if processor1.type != processor2.type or processor1.type:
            logging.error("Can only swap MIDI or AudioFX processors of same type")
            return False
        slot1 = slot2 = None
        par1 = par2 = None
        slots = self.get_slots_by_type(processor1.type)
        for s, slot in enumerate(slots):
            for u, processor in enumerate(slot):
                if processor1 == processor:
                    slot1 = s
                    par1 = u
                if processor2 == processor:
                    slot2 = s
                    par2 = u

        if par1 == None or par2 == None or slot1 == None or slot2 == None:
            logging.error("processor not found")
            return False
        slots[slot1][par1] = processor2
        slots[slot2][par2] = processor1
        self.rebuild_graph()
        return True

    def get_slot(self, processor):
        """Returns the slot which contains processor or None if processor is not in chain"""

        slots = self.get_slots_by_type(processor.type)
        for i, slot in enumerate(slots):
            for u in slot:
                if processor == u:
                    return i
        return None

    def set_current_processor(self, processor):
        if processor in self.get_processors():
            self.current_processor = processor

    # ------------------------------------------------------------------------
    # State Management
    # ------------------------------------------------------------------------

    def get_state(self):
        """List of slot states

        Each list entry is a list of processor states
        """

        slots_states = []
        for slot in self.midi_slots + self.synth_slots + self.audio_slots:
            slot_state = {}
            for processor in slot:
                slot_state[processor.id] = processor.type_code
            if slot_state:
                slots_states.append(slot_state)

        state = {
            "title": self.title,
            "midi_chan": self.midi_chan,
            "midi_thru": self.midi_thru,
            "audio_thru": self.audio_thru,
            "mixer_chan": self.mixer_chan,
            "zmop_index": self.zmop_index,
            "slots": slots_states
        }

        return state
