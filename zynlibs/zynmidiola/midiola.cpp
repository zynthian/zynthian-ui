/*
 * ******************************************************************
 * ZYNTHIAN PROJECT: Openlighting MIDI interface
 *
 * Application to convert JACK MIDI to OLA DMX
 *
 * Copyright (C) 2025 Brian Walton <brian@riban.co.uk>
 *
 * ******************************************************************
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License as
 * published by the Free Software Foundation; either version 2 of
 * the License, or any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * For a full copy of the GNU General Public License see the LICENSE.txt file.
 *
 * ******************************************************************
 */

#include <stdlib.h>
#include <unistd.h>
#include <ola/DmxBuffer.h>
#include <ola/Logging.h>
#include <ola/client/StreamingClient.h>
#include <iostream>
#include <jack/jack.h>     // provides JACK interface
#include <jack/midiport.h> // provides JACK MIDI interface

uint8_t g_nUniverse = 1;  // universe to use for sending data
jack_port_t* g_pInputPort;  // Pointer to the JACK input port
jack_client_t* g_pJackClient = NULL;  // Pointer to the JACK client
ola::DmxBuffer buffer;  // DMX data buffers for universe
ola::client::StreamingClient* g_pOlaClient = NULL; // Pointer to the OLA client

int onJackProcess(jack_nframes_t nFrames, void* args) {
    // Process MIDI input
    void* pInputBuffer = jack_port_get_buffer(g_pInputPort, nFrames);
    jack_midi_event_t midiEvent;
    jack_nframes_t nCount = jack_midi_get_event_count(pInputBuffer);
    for (jack_nframes_t frame = 0; frame < nCount; ++frame) {
        if (jack_midi_event_get(&midiEvent, pInputBuffer, frame))
            continue;
        if ((midiEvent.buffer[0] & 0xb0) == 0xb0) {
            // MIDI CC
            uint8_t chan = midiEvent.buffer[0] & 0x0f;
            uint8_t cc = midiEvent.buffer[1];
            // DMX universe 1 is controlled by MIDI channels 1..2, CC 0..127 (in banks of 32 LSB + 32 MSB) (512 slots)
            // Slots 0..31 populated by CC 0..31 + 32..63. Slots 32..63 populated by CC 64..95 + 96..127.
            uint8_t offset = cc % 32;
            uint8_t base = (cc / 64) * 32;
            uint8_t slot = offset + base;
            uint8_t lsb = (cc % 64) > 31;
            uint8_t val = buffer.Get(slot);
            if (lsb) {
                // LSB CC only used to set bit 0 (wasteful but MIDI 1.0 is only 7-bit)
                if (midiEvent.buffer[2])
                    val |= 0x01;
                else
                    val &= 0xfe;
            } else {
                val &= 0x01;
                val |= (midiEvent.buffer[2] << 1);
            }
            fprintf(stderr, "MIDI CC %d val %d. Sending DMX %d to %d\n", cc, midiEvent.buffer[2], val, slot);
            buffer.SetChannel(slot, val);
            g_pOlaClient->SendDmx(g_nUniverse, buffer); //!@todo This will probably not be realtime safe
            fprintf(stderr, "  Done!\n");
        }
    }
    return 0;
}

int main(int, char *[]) {
    // Create a OLA client.
    ola::client::StreamingClient olaClient((ola::client::StreamingClient::Options()));
    g_pOlaClient = &olaClient;

    // Setup OLA, connect to the server
    if (!olaClient.Setup()) {
        fprintf(stderr, "Failed to setup OLA client\n");
        exit(1);
    }
    // Initalise buffers and send to universe
    buffer.Blackout();
    g_pOlaClient->SendDmx(g_nUniverse, buffer);

    // Create JACK client
    char* sServerName = NULL;
    jack_status_t nStatus;
    jack_options_t nOptions = JackNoStartServer;
    if ((g_pJackClient = jack_client_open("zynmidiola", nOptions, &nStatus, sServerName)) == 0) {
        fprintf(stderr, "ERROR: Failed to start jack client: %d\n", nStatus);
        exit(1);
    }
    // Create MIDI input port
    if (!(g_pInputPort = jack_port_register(g_pJackClient, "input", JACK_DEFAULT_MIDI_TYPE, JackPortIsInput | JackPortIsPhysical, 0))) {
        fprintf(stderr, "ERROR: Cannot register input port\n");
        exit(1);
    }
    // Register JACK callbacks
    jack_set_process_callback(g_pJackClient, onJackProcess, 0);
    if (jack_activate(g_pJackClient)) {
        fprintf(stderr, "ERROR: Cannot activate client\n");
        exit(1);
    }

    while (true) {
        usleep(25000); // Do nothing in program loop
    }

    return 0;
}