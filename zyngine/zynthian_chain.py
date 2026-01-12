# -*- coding: utf-8 -*-
# *****************************************************************************
# ZYNTHIAN PROJECT: Zynthian Chain (zynthian_chain)
#
# zynthian chain
#
# Copyright (C) 2015-2025 Fernando Moyano <jofemodo@zynthian.org>
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

import ctypes
import logging

# Zynthian specific modules
import zynautoconnect
from zyngine.zynthian_processor import zynthian_processor
from zyncoder.zyncore import lib_zyncore

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
        # Synth/generator/special slots (should be single slot)
        self.synth_slots = []
        self.audio_slots = []  # Audio subchain (list of lists of processors)

        self.chain_id = chain_id  # Chain's ID
        # Chain's MIDI channel - None for purely audio chain, 0xffff for *All Chains*
        self.midi_chan = midi_chan
        self.zmop_index = None
        self.midi_thru = midi_thru  # True to pass MIDI if chain empty
        self.audio_thru = audio_thru  # True to pass audio if chain empty
        self.zynmixer_proc = None  # zynmixer (MI/MR) processor
        self.midi_in = []
        self.midi_out = []
        self.audio_in = []
        self.audio_out = []

        self.status = ""  # Arbitary status text => THIS IS NOT USED AT ALL, RIGHT?

        self.current_processor = None  # Selected processor object
        self.title = None  # User defined title for chain
        self.midi_routes = {}  # Map of MIDI routes indexed by jackname
        self.audio_routes = {}  # Map of audio routes indexed by jackname
        self.zctrls = []  # List of selected zctrls
        self.reset()

    def reset(self):
        """ Resets chain, removing all processors

        types : list of processor types for pass-through
        stop_engines : True to stop unused engines
        Does not change midi/audio thru
        """

        if self.chain_id == 0:
            # Main mix bus
            self.title = "Main"
            self.audio_in = []
            # Default use first two physical audio outputs
            self.audio_out = ["^system:playback_1$|^system:playback_2$"]
            self.audio_thru = True
        else:
            self.title = ""
            if self.zynmixer_proc and self.zynmixer_proc.eng_code == "MR":
                self.audio_in = [] # We don't want any direct audio input connections to buses
            elif self.audio_thru:
                self.audio_in = [1, 2] # Default is to route first 2 audio inputs to audio chains
            self.audio_out = [0]

        if self.is_midi():
            lib_zyncore.zmop_reset_note_range_transpose(self.zmop_index)

        self.free_zmop()
        self.midi_out = []

        try:
            self.current_processor = self.audio_slots[0][0]
            self.current_processor.reset()
        except:
            self.current_processor = None
        self.rebuild_graph()

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
        elif self.is_audio():
            return "Audio Effect"
        elif self.is_midi():
            return "MIDI Tool"
        else:
            return "Empty"

    # ----------------------------------------------------------------------------
    # Chain Management
    # ----------------------------------------------------------------------------

    def set_zmop_options(self):
        if self.zmop_index is not None and len(self.synth_slots) > 0:
            # IMPORTANT!!! Synth chains drop CC & PC messages
            # logging.info(f"Dropping MIDI CC & PC from chain {self.chain_id}")
            lib_zyncore.zmop_set_flag_droppc(self.zmop_index, 1)
            lib_zyncore.zmop_set_flag_dropcc(self.zmop_index, 1)
        else:
            # Audio & MIDI chains doesn't drop CC & PC messages
            # logging.info(f"Routing MIDI CC & PC to chain {self.chain_id}")
            lib_zyncore.zmop_set_flag_droppc(self.zmop_index, 0)
            lib_zyncore.zmop_set_flag_dropcc(self.zmop_index, 0)

    def set_zmop_index(self, iz):
        """Set chain zmop index

        iz : 0...16 (TODO: get maximum number of chains from lib_zyncore!)
        """
        self.free_zmop()
        if iz is not None and iz >= 0:
            self.zmop_index = iz
            self.midi_in = [f"ZynMidiRouter:ch{iz}_out"]
            lib_zyncore.zmop_reset_cc_route(iz)
            if self.midi_chan is not None:
                if 0 <= self.midi_chan < 16:
                    lib_zyncore.zmop_set_midi_chan(iz, self.midi_chan)
                elif self.midi_chan == 0xffff:
                    lib_zyncore.zmop_set_midi_chan_all(iz)

    def free_zmop(self):
        """If already using a zmop, release and reset it
        """
        if self.zmop_index is not None and self.zmop_index >= 0:
            lib_zyncore.zmop_reset_midi_chans(self.zmop_index)
        self.zmop_index = None
        self.midi_in = []

    def set_midi_chan(self, chan):
        """Set chain (and its processors) MIDI channel

        chan : MIDI channel 0..15, 0xffff or None
        """

        self.midi_chan = chan
        if self.zmop_index is not None and self.zmop_index >= 0 and self.midi_chan is not None:
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

        if self.title:
            return self.title
        else:
            return self.get_description_parts()[0]

    def get_description_parts(self, basepath=False, preset=False):
        """Get chain description parts, using synth or first processor

            - basepath: use engine's basepath or name
            - preset: include the selected preset
        """
        parts = []

        if self.title:
            parts.append(self.title)
        elif self.chain_id == 0:
            parts.append("Main")
        elif not self.synth_slots and self.audio_thru:
            if self.zynmixer_proc and self.zynmixer_proc.eng_code == "MR":
                parts.append(f"Effect Return {self.zynmixer_proc.mixer_chan}")
            else:
                parts.append("Audio Input " + ','.join([str(i) for i in self.audio_in]))

        if self.synth_slots:
            proc = self.synth_slots[0][0]
        elif self.get_slot_count("Audio Effect"):
            proc = self.get_processors("Audio Effect")[0]
        elif self.get_slot_count("MIDI Tool"):
            proc = self.get_processors("MIDI Tool")[0]
        else:
            proc = None

        if proc:
            if basepath:
                parts.append(proc.get_basepath())
            else:
                name = proc.get_name()
                if name:
                    parts.append(name)
            if preset:
                preset_name = proc.get_preset_name()
                if preset_name:
                    parts.append(preset_name)

        if not parts:
            if self.synth_slots:
                chain_type = "Synth"
            elif self.is_audio():
                chain_type = "Audio"
            elif self.is_midi():
                chain_type = "MIDI"
            else:
                chain_type = "Chain"
            parts.append(f"{chain_type} Chain {self.chain_id}")

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

        # TODO: This is called too frequently
        if not zynautoconnect.acquire_lock():
            return

        self.audio_routes = {}
        # Add audio effects chain routes
        first_slot_sources = []
        if self.synth_slots:
            for proc in self.synth_slots[-1]:
                first_slot_sources.append(proc.get_jackname())
        elif self.zynmixer_proc and self.zynmixer_proc.eng_code == "MR":
            for am_slot in self.audio_slots:
                if am_slot[0].eng_code in ("MI", "MR"):
                    first_slot_sources = [f"zynmixer_chan:send_{am_slot[0].mixer_chan:02d}"]
                    break
        elif self.audio_thru:
            first_slot_sources = self.get_input_pairs()
        prev_slot_sources = first_slot_sources

        for slot in self.audio_slots:
            sources = []
            for processor in slot:
                jackname = processor.get_jackname()
                if jackname.startswith("zynmixer"):
                    jackname += f":output_{processor.mixer_chan:02d}"
                sources.append(jackname)
            if sources:
                for jackname in sources:
                    if jackname.startswith("zynmixer"):
                        jackname = jackname.replace("output_", "input_")
                    self.audio_routes[jackname] = prev_slot_sources.copy()
                prev_slot_sources = sources

        # Add special processor inputs
        if self.is_synth():
            processor = self.synth_slots[0][0]
            if processor.type == "Special":
                sources = self.get_input_pairs()
                self.audio_routes[processor.get_jackname()] = sources

        # Connect end of chain
        # Use end of post fader chain

        for output in self.get_audio_out():
            self.audio_routes[output] = prev_slot_sources.copy()

        zynautoconnect.release_lock()

    def get_input_pairs(self):
        """Get jack regexp for pairs of system:capture ports

        Returns : List of regexps
        """

        if self.chain_id == 0:
            return self.audio_in.copy()
        sources = []
        input_ports = zynautoconnect.get_audio_capture_ports()
        for i in range(0, len(self.audio_in), 2):
            a = self.audio_in[i]
            if a > len(input_ports):
                continue
            if i < len(self.audio_in) - 1:
                b = self.audio_in[i + 1]
                sources.append(f"^{input_ports[a-1].name}$|^{input_ports[b-1].name}$")
            else:
                sources.append(f"^{input_ports[a-1].name}$")
        return sources

    def rebuild_midi_graph(self):
        """Build dictionary of lists of sources mapped by destination"""

        if not zynautoconnect.acquire_lock():
            return

        self.midi_routes = {}
        for i, slot in enumerate(self.midi_slots):
            if i == 0:
                continue  # Chain inputs are handled by autoconnect
            for processor in slot:
                sources = []
                for prev_proc in self.midi_slots[i - 1]:
                    sources.append(prev_proc.get_jackname())
                self.midi_routes[processor.get_jackname()] = sources

        sources = []
        if len(self.midi_slots):
            for prev_proc in self.midi_slots[-1]:
                sources.append(prev_proc.get_jackname())
        if self.synth_slots:
            for proc in self.synth_slots[0]:
                # TODO: Should always use engine's get_jackname? => proc.get_jackname(True)
                dst_jackname = proc.engine.get_jackname()
                self.midi_routes[dst_jackname] = sources
                # Special Engines can generate MIDI output too!!
                if proc.type == "Special":
                    sources = [dst_jackname]
        elif len(self.midi_slots) == 0 and self.midi_thru:
            sources = self.midi_in
        for output in self.midi_out:
            self.midi_routes[output] = sources
        # Feed output of MIDI chain to all audio processors - ideally this should only feed processors with
        # MIDI inputs but it is probably as simple to let autoconnect deal with that.
        for slot in self.audio_slots:
            for proc in slot:
                if proc.eng_code not in ["MI", "MR"]:
                    self.midi_routes[proc.engine.jackname] = sources
        zynautoconnect.release_lock()

    def rebuild_graph(self):
        """Build dictionary of lists of destinations mapped by source"""

        self.rebuild_midi_graph()
        self.rebuild_audio_graph()

    def get_audio_out(self):
        """Get list of audio playback port names"""

        return self.audio_out.copy()

    def toggle_audio_out(self, out):
        """Toggle chain audio output

        out : Jack port regex or chain id of destination to toggle
        """

        if out not in self.audio_out:
            self.audio_out.append(out)
        else:
            try:
                self.audio_out.remove(out)
            except:
                pass
        logging.debug(f"Toggling Audio Output: {out}")

        self.rebuild_audio_graph()
        zynautoconnect.request_audio_connect(True)

    def toggle_audio_in(self, input):
        """Toggle chain audio in (physcial capture port)

        input : Index of physical audio input (1-based)
        """

        if input in self.audio_in:
            self.audio_in.remove(input)
        else:
            self.audio_in.append(input)

        self.rebuild_audio_graph()
        zynautoconnect.request_audio_connect(True)

    def get_midi_out(self):
        return self.midi_out

    def toggle_midi_out(self, dest):
        """ Set/unset a MIDI output route
        dest : destination ID. A jack port name/alias (string) or a chain ID (integer)
        """

        if dest not in self.midi_out:
            self.midi_out.append(dest)
        else:
            self.midi_out.remove(dest)

        self.rebuild_midi_graph()
        zynautoconnect.request_midi_connect(True)

    def is_audio(self):
        """Returns True if chain has audio output"""

        return self.zynmixer_proc is not None

    def is_midi(self):
        """Returns True if chain has MIDI input"""

        return self.zmop_index is not None

    def is_synth(self):
        """Returns True if chain contains synth processor"""

        return self.zmop_index and len(self.synth_slots) != 0

    def is_generator(self):
        """Returns True if chain is a generator => """

        return self.zynmixer_proc and self.synth_slots and self.synth_slots[0][0].type == "Audio Generator"

    def is_special(self):
        """Returns True if chain is a special chain => """

        return self.zynmixer_proc and self.synth_slots and self.synth_slots[0][0].type == "Special"

    def is_mixbus(self):
        """Returns True if chain is an Aux Mixbus chain"""

        return self.zynmixer_proc and not self.synth_slots and self.zynmixer_proc.eng_code == "MR"

    def is_audio_in(self):
        """Returns True if chain is a pure audio input"""

        return self.zynmixer_proc and not self.synth_slots and self.zynmixer_proc.eng_code == "MI"

    def set_solo(self, value):
        """Sets solo state in zynmixer, if audio chain"""
        try:
            self.zynmixer_proc.controllers_dict["solo"].set_value(value)
        except:
            pass

    def toggle_solo(self):
        """Toggles solo state in zynmixer, if audio chain"""
        try:
            self.zynmixer_proc.controllers_dict["solo"].toggle()
        except:
            pass

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
        elif type == "MIDI Synth":
            return len(self.synth_slots)
        else:
            return 0

    def get_processor_count(self, type=None, slot=None):
        """Get quantity of processors in chain (slot)

        type : processor type to filter results (Default: whole chain)
        slot : Index of slot or None for whole chain (Default: whole chain)
        Returns : Quantity of processors in (sub)chain or slot
        """

        count = 0
        if type is None:
            if slot is None or slot < 0:
                for j in self.midi_slots + self.synth_slots + self.audio_slots:
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

    def get_processors_by_id(self):
        procs = self.get_processors()
        procs_by_id = {}
        for proc in procs:
            procs_by_id[proc.id] = proc
        return procs_by_id

    def insert_processor(self, processor, slot=None):
        """Insert a processor in the chain

        processor : processor object to insert
        slot : Position (slot) to insert within subchain (Default: new slot at end of subchain, pre-fader)
        """

        slots = self.get_slots_by_type(processor.type)
        if len(slots) == 0:
            # Chain is empty so create a new slot for the processor
            slots.append([processor])
        else:
            if slot is None:
                # Add processor to a new slot at end position in subchain
                slots.append([processor])
            elif slot < 0:
                # Insert into new slot at start of chain
                slots.insert(0, [processor])
            elif slot >= len(slots):
                # Invalid slot so append to end of chain
                slots.append([processor])
            else:
                # If mixer slot, insert before
                try:
                    if slots[slot][0].eng_code in ("MI", "MR"):
                        slots.insert(slot, [])
                except:
                    pass
                # Add parallel processor to existing slot
                slots[slot].append(processor)

        processor.set_chain(self)
        if processor.engine:
            processor.engine.add_processor(processor)
        processor.set_midi_chan(self.midi_chan)

        if self.current_processor is None:
            self.current_processor = processor

        self.set_zmop_options()

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
                    new_processor.set_midi_chan(self.midi_chan)
                    # TODO: Should we rebuild graph?
                    zynautoconnect.request_audio_connect(True)
                    zynautoconnect.request_midi_connect(True)
                    if self.current_processor == old_processor:
                        self.current_processor = new_processor
                    return True
        return False

    def remove_processor(self, processor):
        """Remove a processor from chain

        processor : processor object to remove
        Returns : True on success
        """

        if self.chain_id == 0 and processor.eng_code == "MR":
            return False

        slot = self.get_slot(processor)
        if slot is None:
            logging.error("processor is not in chain!")
            return False

        logging.debug("Removing processor {}".format(processor.get_jackname()))

        slots = self.get_slots_by_type(processor.type)
        slots[slot].remove(processor)
        if len(slots[slot]) == 0:
            slots.pop(slot)

        processor.set_chain(None)
        if processor.engine:
            processor.engine.remove_processor(processor)

        self.set_zmop_options()
        self.rebuild_graph()
        self.purge_zctrls()

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
        return True

    def remove_all_processors(self):
        """Remove all processors from chain

        stop_engines : True to stop the processors' worker engines
        """

        self.clean_zctrls()
        for processor in self.get_processors():
            self.remove_processor(processor)

    def nudge_processor(self, processor, up):
        try:
            slots = self.get_slots_by_type(processor.type)
            cur_slot = self.get_slot(processor)
            parallel = len(slots[cur_slot]) > 1
            is_mixer_strip = processor.eng_code in ("MI", "MR")

            if up:
                if not parallel and cur_slot == 0:
                    return False
                if is_mixer_strip:
                    slots.pop(cur_slot)
                    slots.insert(cur_slot - 1, [processor])
                elif parallel:
                    slots[cur_slot].remove(processor)
                    if slots[cur_slot][0].eng_code in ("MI", "MR"):
                        slots.insert(cur_slot - 1, [processor])
                    else:
                        slots.insert(cur_slot, [processor])
                elif cur_slot > 0:
                    slots.pop(cur_slot)
                    if slots[cur_slot - 1][0].eng_code in ("MI", "MR"):
                        slots.insert(cur_slot - 1, [processor])
                    else:
                        slots[cur_slot - 1].append(processor)
                else:
                    return False
            else:
                if not parallel and cur_slot + 1 >= len(slots):
                    return False
                if is_mixer_strip:
                    slots.pop(cur_slot)
                    slots.insert(cur_slot + 1, [processor])
                elif parallel:
                    slots[cur_slot].remove(processor)
                    slots.insert(cur_slot + 1, [processor])
                else:
                    slots.pop(cur_slot)
                    if slots[cur_slot][0].eng_code in ("MI", "MR"):
                        slots.insert(cur_slot + 1, [processor])
                    else:
                        slots[cur_slot].append(processor)

            self.rebuild_graph()
        except:
            logging.error("Failed to move processor")
        return True

    def swap_processors(self, processor1, processor2):
        """Swap two processors in chain

        processor1 : First processor object to swap
        processor2 : Second processor object to swap
        Returns : True on success
        """

        if processor1.type != processor2.type or processor1.type:
            logging.error(
                "Can only swap MIDI or AudioFX processors of same type")
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
        """Returns the slot index which contains processor or None if processor is not in chain"""

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
    # Chain zctrls Management
    # ------------------------------------------------------------------------

    def clean_zctrls(self):
        self.zctrls = []

    def purge_zctrls(self):
        if not self.zctrls:
            return
        purged_zctrls = []
        procs_by_id = self.get_processors_by_id()
        for zctrl in self.zctrls:
            if zctrl.processor in procs_by_id:
                purged_zctrls.append(zctrl)
        self.zctrls = purged_zctrls

    def toggle_zctrl(self, zctrl):
        try:
            self.zctrls.remove(zctrl)
        except:
            self.zctrls.append(zctrl)

    def set_zctrls_state(self, state):
        self.zctrls = []
        procs_by_id = self.get_processors_by_id()
        for s in state:
            try:
                proc = procs_by_id[s[0]]
                self.zctrls.append(proc.controllers_dict[s[1]])
            except Exception as e:
                logging.error(f"Can't restore chain zctrl from state => {s}")

    def get_zctrls_state(self):
        state = []
        for zctrl in self.zctrls:
            state.append((zctrl.processor.id, zctrl.symbol))
        return state

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
                slot_state[processor.id] = processor.eng_code
            if slot_state:
                slots_states.append(slot_state)

        # Get ZMOP CC route state
        cc_route_ct = (ctypes.c_uint8 * 128)()
        if self.zmop_index is not None and self.zmop_index >= 0:
            lib_zyncore.zmop_get_cc_route(self.zmop_index, cc_route_ct)
        cc_route = []
        for cc, ccr in enumerate(cc_route_ct):
            if ccr:
                cc_route.append(cc)

        state = {
            "title": self.title,
            "midi_chan": self.midi_chan,
            "midi_thru": self.midi_thru,
            "audio_thru": self.audio_thru,
            "zmop_index": self.zmop_index,
            "cc_route": cc_route,
            "slots": slots_states,
            "zctrls": self.get_zctrls_state()
        }

        return state
