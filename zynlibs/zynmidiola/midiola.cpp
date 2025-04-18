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

    This application acts as a JACK client, providing a single MIDI input port.
    MIDI CC recieved on channels 1..8 are sent to Openlighting service to drive DMX512.
    Only universe 1 is currently supported.
    MIDI channel 1 controls DMX512 slots 0..63. Channel 2, slots 64..127. Chan 3, 128..191. Chan4, 192..255.
    CC 0..31 control slots 0..31 most significant 7 bits. CC 32..63 control slots 0..31 least significant bit.
    Any non-zero value in slots 32..63 will set the least significant bit of the corresponding DMX512 slot.

    | MIDI Channel | MIDI CC  | DMX Slot | Value mask |
    | ------------ | -------- | -------- | ---------- |
    | 1 (0)        | 0..31    | 1..32    | 0xfe       |
    | 1 (0)        | 32..63   | 1..32    | 0x01       |
    | 1 (0)        | 64..93   | 33..64   | 0xfe       |
    | 1 (0)        | 94..127  | 33..64   | 0x01       |
    | 1 (0)        | 128..159 | 65..96   | 0xfe       |
    | 1 (0)        | 160..191 | 65..96   | 0x01       |
    | 1 (0)        | 192..223 | 97..128  | 0xfe       |
    | 1 (0)        | 224..255 | 97..128  | 0x01       |
    | 2 (1)        | 0..31    | 129..160 | 0xfe       |
    | 2 (1)        | 32..63   | 129..160 | 0x01       |
    | 2 (1)        | 64..93   | 161..192 | 0xfe       |
    | 2 (1)        | 94..127  | 161..192 | 0x01       |
    | 2 (1)        | 128..159 | 193..224 | 0xfe       |
    | 2 (1)        | 160..191 | 193..224 | 0x01       |
    | 2 (1)        | 192..223 | 225..256 | 0xfe       |
    | 2 (1)        | 224..255 | 225..256 | 0x01       |
    | 3 (2)        | 0..31    | 257..288 | 0xfe       |
    | 3 (2)        | 32..63   | 257..288 | 0x01       |
    | 3 (2)        | 64..93   | 289..320 | 0xfe       |
    | 3 (2)        | 94..127  | 289..320 | 0x01       |
    | 3 (2)        | 128..159 | 321..352 | 0xfe       |
    | 3 (2)        | 160..191 | 321..352 | 0x01       |
    | 3 (2)        | 192..223 | 353..284 | 0xfe       |
    | 3 (2)        | 224..255 | 353..284 | 0x01       |
    | 4 (3)        | 0..31    | 285..416 | 0xfe       |
    | 4 (3)        | 32..63   | 285..416 | 0x01       |
    | 4 (3)        | 64..93   | 417..448 | 0xfe       |
    | 4 (3)        | 94..127  | 417..448 | 0x01       |
    | 4 (3)        | 128..159 | 449..480 | 0xfe       |
    | 4 (3)        | 160..191 | 449..480 | 0x01       |
    | 4 (3)        | 192..223 | 481..512 | 0xfe       |
    | 4 (3)        | 224..255 | 481..512 | 0x01       |

 */

#include <stdlib.h>
#include <unistd.h>
#include <ola/DmxBuffer.h>
#include <ola/client/StreamingClient.h>
#include <jack/jack.h>     // provides JACK interface
#include <jack/midiport.h> // provides JACK MIDI interface

uint8_t g_universe = 1;  // Universe to use for sending data
jack_port_t* g_midiInputPort;  // Pointer to the JACK input port
jack_client_t* g_jackClient = NULL;  // Pointer to the JACK client
ola::DmxBuffer g_dmxBuffer;  // DMX data buffers for universe
ola::client::StreamingClient* g_olaClient = NULL; // Pointer to the OLA client

int onJackProcess(jack_nframes_t frames, void* args) {
    // Process MIDI input
    void* midiBuffer = jack_port_get_buffer(g_midiInputPort, frames);
    jack_midi_event_t midiEvent;
    jack_nframes_t count = jack_midi_get_event_count(midiBuffer);
    for (jack_nframes_t frame = 0; frame < count; ++frame) {
        if (jack_midi_event_get(&midiEvent, midiBuffer, frame))
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
            uint8_t val = g_dmxBuffer.Get(slot);
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
            g_dmxBuffer.SetChannel(slot, val);
            g_olaClient->SendDmx(g_universe, g_dmxBuffer); //!@todo This will probably not be realtime safe
        }
    }
    return 0;
}

int main(int, char *[]) {
    // Create a OLA client.
    ola::client::StreamingClient olaClient((ola::client::StreamingClient::Options()));
    g_olaClient = &olaClient;

    // Setup OLA, connect to the server
    if (!olaClient.Setup()) {
        fprintf(stderr, "Failed to setup OLA client\n");
        exit(1);
    }
    // Initalise buffers and send to universe
    g_dmxBuffer.Blackout();
    olaClient.SendDmx(g_universe, g_dmxBuffer);

    // Create JACK client
    char* serverName = NULL;
    jack_status_t jackStatus;
    if ((g_jackClient = jack_client_open("zynmidiola", JackNoStartServer, &jackStatus, serverName)) == 0) {
        fprintf(stderr, "ERROR: Failed to start jack client: %d\n", jackStatus);
        exit(1);
    }
    // Create MIDI input port
    if (!(g_midiInputPort = jack_port_register(g_jackClient, "input", JACK_DEFAULT_MIDI_TYPE, JackPortIsInput | JackPortIsPhysical, 0))) {
        fprintf(stderr, "ERROR: Cannot register input port\n");
        exit(1);
    }
    // Register JACK callbacks
    jack_set_process_callback(g_jackClient, onJackProcess, 0);
    if (jack_activate(g_jackClient)) {
        fprintf(stderr, "ERROR: Cannot activate client\n");
        exit(1);
    }

    while (true) {
        usleep(25000); // Do nothing in program loop
    }

    return 0;
}