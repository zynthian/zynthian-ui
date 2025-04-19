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
    4 modes of operation are supported: 7/14-bit, CC/NRPN.
    Only DMX512 universe 1 is currently supported.
 */

//!@todo Implement multiple universe
//!@todo Implement data inc/dec

#include <stdlib.h>
#include <unistd.h>
#include <ola/DmxBuffer.h>
#include <ola/client/StreamingClient.h>
#include <jack/jack.h>     // provides JACK interface
#include <jack/midiport.h> // provides JACK MIDI interface
#include <getopt.h> // provides command line parseing
#include <stdarg.h> // provides vfprintf

enum MIDI_MODE {
    MIDI_MODE_CC7       = 0,
    MIDI_MODE_CC14      = 1,
    MIDI_MODE_NRPN7     = 2,
    MIDI_MODE_NRPN14    = 3
};

enum MIDI_COMMAND {
    MIDI_CMD_DATA_MSB   = 6,
    MIDI_CMD_DATA_LSB   = 38,
    MIDI_CMD_INC        = 96,
    MIDI_CMD_DEC        = 97,
    MIDI_CMD_NRPN_LSB   = 98,
    MIDI_CMD_NRPN_MSB   = 99,
    MIDI_CMD_NULL       = 127
};

uint8_t g_universe = 1;  // First DMX universe
uint8_t g_mode = 0; // MIDI mode
uint8_t g_verbose = 2; // Level of verbosity (0: silent, 1: errors, 2: info, 3: debug)
uint16_t g_nrpnParam = 0x3fff; // NRPN parameter being adjusted
uint16_t g_nrpnVal = 0; // NRPN value
jack_port_t* g_midiInputPort;  // Pointer to the JACK input port
jack_client_t* g_jackClient = NULL;  // Pointer to the JACK client
ola::DmxBuffer g_dmxBuffer;  // DMX data buffer for universe
ola::client::StreamingClient* g_olaClient = NULL; // Pointer to the OLA client
const char* modeNames[] = {"CC 7-bit", "CC 14-bit", "NRPN 7-bit", "NRPN 14-bit"};

void debug(const char *format, ...) {
    if (g_verbose > 2) {
        va_list args;
        va_start(args, format);
        vfprintf(stdout, format, args);
        va_end(args);
    }
}

void info(const char *format, ...) {
    if (g_verbose > 1) {
        va_list args;
        va_start(args, format);
        vfprintf(stdout, format, args);
        va_end(args);
    }
}

void error(const char *format, ...) {
    if (g_verbose) {
        va_list args;
        va_start(args, format);
        vfprintf(stderr, format, args);
        va_end(args);
    }
}

void help() {
    info("Usage: zynmidiola [options]\n\n"
        "Options:\n"
        "  -m --mode MIDI mode [0..3]\n");
    for (uint8_t mode = 0; mode < 4; ++mode)
        info("      %u: %s\n", mode, modeNames[mode]);
    info(
        "  -u --universe First universe [Default: 1]\n"
        "  -v --verbose Set vebose level:\n"
        "    0: Silent\n"
        "    1: Show errors\n"
        "    2: Show info [default]\n"
        "    3: Show debug\n"
        "  -h --help Show this help\n"
    );
}

bool parseCommandLine(int argc, char* argv[]) {
    option longopts[] = {
        {"mode", optional_argument, NULL, 'm'}, 
        {"universe", optional_argument, NULL, 'u'},
        {"verbose", optional_argument, NULL, 'v'},
        {"help", optional_argument, NULL, 'h'}, 
        {0}};
    while (1) {
        const int opt = getopt_long(argc, argv, "m:u:v:h:", longopts, 0);
        if (opt == -1) {
            break;
        }
        switch (opt) {
            case 'm':
                g_mode = atoi(optarg);
                if (g_mode > 3) {
                    error("Invalid mode. Range 0..3\n");
                    exit(1);
                }
                break;
            case 'u':
                g_universe = atoi(optarg);
                break;
            case 'v':
                g_verbose = atoi(optarg);
                break;
            default:
                help();
                exit(0);
        }
    }
    return false;
}

void cc7(uint8_t channel, uint8_t cc, uint8_t val) {
    /*  @brief  Handle 7-bit (immediate) CC message
        @param  channel MIDI channel [0..15]
        @param  cc MIDI CC [0..127]
        @param  val MIDI value [0..127]
        @note   DMX Slots 1..128 populated by CC 0..127. Universe is MIDI channel + universe base. 
        @note   DMX value is half resolution.
    */

    g_dmxBuffer.SetChannel(cc, val);
    g_olaClient->SendDmx(g_universe, g_dmxBuffer);
    //!@todo Implement multiple universes
}

void cc14(uint8_t channel, uint8_t cc, uint8_t val) {
    /*  @brief  Handle 14-bit CC message
        @param  channel MIDI channel [0..15]
        @param  cc MIDI CC [0..127]
        @param  val MIDI value [0..127]
        @note   DMX Slots 1..32 populated by CC 0..31 (MSB) + 32..63 (LSB). 
        @note   Slot offset is MIDI channel * 32, e.g. MIDI channel 0: slots 1..32, MIDI channel 1: slots 33..64.
        @note   DMX value only set when LSB received.
    */

    uint8_t offset = cc % 32;
    uint8_t base = channel * 32;
    uint8_t slot = offset + base;
    uint8_t lsb = (cc % 64) > 31;
    uint8_t curVal = g_dmxBuffer.Get(slot);
    if (lsb) {
        if (val > 63)
            curVal |= 0x01;
        else
            curVal &= 0xfe;
    } else {
        curVal &= 0x01;
        curVal |= (val << 1);
    }
    g_dmxBuffer.SetChannel(slot, curVal);
    if (lsb)
        g_olaClient->SendDmx(g_universe, g_dmxBuffer);
}

void nrpnCC7(uint8_t channel, uint8_t cc, uint8_t val) {
    /*  @brief  Handle NRPN 7-bit CC message
        @param  channel MIDI channel [0..15]
        @param  cc MIDI CC [0..127]
        @param  val MIDI value [0..127]
        @note   DMX Universe 0, slots 1..512 populated by MIDI channel 0, NRPN parameters 0..511. 
        @note   DMX Universe 1, slots 1..512 populated by MIDI channel 0, NRPN parameters 512..1023, etc. 
        @note   DMX Universe 32..63 populated by MIDI channel 1, etc. 
        @note   Maximum 512 universes.
    */

    switch(cc) {
        case MIDI_CMD_NRPN_LSB:
            g_nrpnParam = (g_nrpnParam & 0x3f80) | val;
            debug("NRPN param: %u\n", g_nrpnParam);
            break;
        case MIDI_CMD_NRPN_MSB:
            g_nrpnParam = (g_nrpnParam & 0x7f) | (val << 7);
            debug("NRPN param: %u\n", g_nrpnParam);
            break;
        case MIDI_CMD_DATA_MSB:
            if (((g_nrpnParam & 0x3f80) == 0x3f80) || (((g_nrpnParam & 0x7f) == 0x7f)))
                return;
            uint16_t slot = g_nrpnParam % 512;
            debug("NRPN param: %u slot: %u val: %u\n", g_nrpnParam, slot, val);
            g_dmxBuffer.SetChannel(slot, val);
            g_olaClient->SendDmx(g_universe, g_dmxBuffer);
    }
}

void nrpnCC14(uint8_t channel, uint8_t cc, uint8_t val) {
    /*  @brief  Handle NRPN 14-bit CC message
        @param  channel MIDI channel [0..15]
        @param  cc MIDI CC [0..127]
        @param  val MIDI value [0..127]
        @note   DMX Universe 0, slots 1..512 populated by NRPN parameters 0..511. 
        @note   DMX Universe 1, slots 1..512 populated by NRPN parameters 512..1023. 
        @note   DMX value only sent after LSB received. 
        @note   Maximum 32 universes.
    */

    switch(cc) {
        case MIDI_CMD_NRPN_LSB:
            g_nrpnParam = (g_nrpnParam & 0x3f80) | val;
            debug("NRPN param: %u\n", g_nrpnParam);
            break;
        case MIDI_CMD_NRPN_MSB:
            g_nrpnParam = (g_nrpnParam & 0x7f) | (val << 7);
            debug("NRPN param: %u\n", g_nrpnParam);
            break;
        case MIDI_CMD_DATA_MSB:
            g_nrpnVal = ((g_nrpnVal & 0x7f) | (val << 7));
            debug("NRPN param: %u val: %u\n", g_nrpnParam, g_nrpnVal);
            break;
        case MIDI_CMD_DATA_LSB:
            g_nrpnVal = ((g_nrpnVal & 0x3f80) | val);
            //if (((g_nrpnParam & 0x3f80) == 0x3f80) || (((g_nrpnParam & 0x7f) == 0x7f)))
            //    return;
            uint16_t slot = g_nrpnParam % 512;
            debug("NRPN param: %u slot: %u val: %u\n", g_nrpnParam, slot, g_nrpnVal);
            g_dmxBuffer.SetChannel(slot, g_nrpnVal & 0xFF);
            g_olaClient->SendDmx(g_universe, g_dmxBuffer);
            break;
    }
}

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
            uint8_t val = midiEvent.buffer[2];
            switch (g_mode) {
                case MIDI_MODE_CC7:
                    cc7(chan, cc, val);
                    break;
                case MIDI_MODE_CC14:
                    cc14(chan, cc, val);
                    break;
                case MIDI_MODE_NRPN7:
                    nrpnCC7(chan, cc, val);
                    break;
                case MIDI_MODE_NRPN14:
                    nrpnCC14(chan, cc, val);
                    break;
            }
        }
    }
    return 0;
}

int main(int argc, char* argv[]) {
    parseCommandLine(argc, argv);

    info("Starting zynmidiola - JACK MIDI to Openlighting interface\n");
    info("  Mode: %u (%s)\n  Universe: %u\n", g_mode, modeNames[g_mode], g_universe);
    debug("  Debug enabled\n");

    // Create a OLA client.
    ola::client::StreamingClient olaClient((ola::client::StreamingClient::Options()));
    g_olaClient = &olaClient;

    // Setup OLA, connect to the server
    if (!olaClient.Setup()) {
        error("ERROR: Failed to setup OLA client\n");
        exit(1);
    }
    // Initalise buffers and send to universe
    g_dmxBuffer.Blackout();
    olaClient.SendDmx(g_universe, g_dmxBuffer);

    // Create JACK client
    char* serverName = NULL;
    jack_status_t jackStatus;
    if ((g_jackClient = jack_client_open("zynmidiola", JackNoStartServer, &jackStatus, serverName)) == 0) {
        error("ERROR: Failed to start jack client: %d\n", jackStatus);
        exit(1);
    }
    // Create MIDI input port
    if (!(g_midiInputPort = jack_port_register(g_jackClient, "input", JACK_DEFAULT_MIDI_TYPE, JackPortIsInput | JackPortIsPhysical, 0))) {
        error("ERROR: Cannot register input port\n");
        exit(1);
    }
    // Register JACK callbacks
    jack_set_process_callback(g_jackClient, onJackProcess, 0);
    if (jack_activate(g_jackClient)) {
        error("ERROR: Cannot activate client\n");
        exit(1);
    }

    info("Listening for MIDI\n");
    while (true) {
        usleep(25000); // Do nothing in program loop
    }

    return 0;
}