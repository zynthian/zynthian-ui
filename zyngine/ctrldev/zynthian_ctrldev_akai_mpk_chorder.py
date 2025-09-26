#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for Akai MPK mini MK3
# A simple chorder implemented with mididings.
#
# Copyright (C) 2015-2025 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <brian@riban.co.uk>
#
# ******************************************************************************
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
# ******************************************************************************

import logging
import multiprocessing as mp

# Zynthian specific modules
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_base


# ------------------------------------------------------------------------------------------------------------------
# Basic Chorder with mididings for the Akai MPK mini MK3
# ------------------------------------------------------------------------------------------------------------------

class zynthian_ctrldev_akai_mpk_chorder(zynthian_ctrldev_base):

    dev_ids = ["MPK mini 3 IN 1"]
    driver_description = "Basic chorder example using mididings for RT midi processing. Use pads to change chord type."
    unroute_from_chains = 0b0000001000000000  # Unroute channel 10 (akai MPK mini's pads)
    autoload_flag = False

    # List of chords
    chords = [
        (4, 7),
        (3, 7),
        (4, 7, 11),
        (3, 7, 11),
        (3, 7, 10),
        (3, 7, 9),
        (5, 9),
        (2, 7)
    ]
    # IPC => multiprocessing.Value() object to share an integer variable (chord index) across processes
    chord = mp.Value('i', 0)

    def midiproc_task(self):
        self.midiproc_task_reset_signal_handlers()

        import jack
        import struct
        from threading import Event

        # First 4 bits of status byte:
        NOTEON = 0x9
        NOTEOFF = 0x8

        client = jack.Client(self.midiproc_jackname)
        inport = client.midi_inports.register('in_1')
        outport = client.midi_outports.register('out_1')
        event = Event()

        @client.set_process_callback
        def process(frames):
            chord = self.chords[self.chord.value]
            outport.clear_buffer()
            for offset, indata in inport.incoming_midi_events():
                outport.write_midi_event(offset, indata)  # pass through
                if len(indata) == 3:
                    status, pitch, vel = struct.unpack('3B', indata)
                    if status >> 4 in (NOTEON, NOTEOFF) and (status & 0xF) != 9:
                        for i in chord:
                            try:
                                outport.write_midi_event(offset, (status, pitch + i, vel))
                            except:
                                pass

        @client.set_shutdown_callback
        def shutdown(status, reason):
            logging.debug('JACK-CLIENT shutdown:', reason, status)
            event.set()

        with client:
            event.wait()

    def midi_event(self, ev):
        evtype = (ev[0] >> 4) & 0x0F
        evchan = ev[0] & 0x0F
        # Use the Akai MPK mini's pads (channel 10) for selecting the chord =>
        if evchan == 9 and evtype == 0x9:
            note = ev[1] & 0x7F
            if 36 <= note <= 43:
                self.chord.value = note - 36
                logging.debug(f"CHORD => {self.chords[note - 36]}")
                return True

# ------------------------------------------------------------------------------
