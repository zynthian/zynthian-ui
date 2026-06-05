#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver
# A simple note filter implemented as a python jack client.
#
# Copyright (C) 2015-2026 Fernando Moyano <jofemodo@zynthian.org>
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
# A midiproc note filter that can be toggled from ctrldev driver code
# ------------------------------------------------------------------------------------------------------------------

class zynthian_ctrldev_notes_filter(zynthian_ctrldev_base):

    dev_ids = ["*"]
    driver_description = "A note filter controlled that can be toggled from the ctrldev driver code"
    unroute_from_chains = False  # Route all MIDI channel to chains
    autoload_flag = False

    # IPC => multiprocessing.Value() object to share an integer variable across processes
    filter_enabled = mp.Value('i', 0)

    def midiproc_task(self, jackname):
        zynthian_ctrldev_base.midiproc_task_reset_signal_handlers()

        import jack
        import struct
        from threading import Event

        # First 4 bits of status byte:
        NOTEON = 0x9
        NOTEOFF = 0x8

        client = jack.Client(jackname)
        inport = client.midi_inports.register('in_1')
        outport = client.midi_outports.register('out_1')
        event = Event()

        @client.set_process_callback
        def process(frames):
            filter_enabled =
            outport.clear_buffer()
            if self.filter_enabled.value:
               return
            for offset, indata in inport.incoming_midi_events():
                outport.write_midi_event(offset, indata)  # pass through
                # 3-bytes events
                if len(indata) == 3:
                    status, pitch, vel = struct.unpack('3B', indata)
                    # Note events in MIDI channel 1
                    if status >> 4 in (NOTEON, NOTEOFF) and (status & 0xF) == 0:
                        try:
                            outport.write_midi_event(offset, (status, pitch, vel))
                        except:
                            pass

        @client.set_shutdown_callback
        def shutdown(status, reason):
            logging.debug('JACK-CLIENT shutdown:', reason, status)
            event.set()

        with client:
            event.wait()

    # HERE YOU SHOULD IMEPLEMENT THE REST OF DRIVER METHODS

    def enable_note_filter(self):
        self.filter_enabled = 1

    def disable_note_filter(self):
        self.filter_enabled = 0

    def midi_event(self, ev):
        evtype = (ev[0] >> 4) & 0x0F
        evchan = ev[0] & 0x0F
        # Process midi events normally

        # [YOUR CODE FOR PROCESSING MIDI EVENTS]

        return False

# ------------------------------------------------------------------------------
