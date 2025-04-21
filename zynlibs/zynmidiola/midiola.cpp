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
    7-bit modes half data resolution. 14-bit modes allow full 8-bit resolution.
    14-bit modes send DMX value when LSB recieved. LSB is single bit set by CC value > 63.
    NRPN supports absolute and relative control.
    Maximum 32 consecutive DMX512 universes supported but may start at any universe.
 */

#define VERSION "0.1.0"
#define MAX_MIDI_UNIVERSE 32 // Defines quantity of universe data buffers

#include <stdlib.h>
#include <unistd.h>
#include <ola/DmxBuffer.h>
#include <ola/client/StreamingClient.h>
#include <jack/jack.h>     // provides JACK interface
#include <jack/midiport.h> // provides JACK MIDI interface
#include <getopt.h> // provides command line parseing
#include <stdarg.h> // provides vfprintf
#include <string.h> // provides strcmp

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

bool g_enableNote = false; // True to listen for MIDI note-on command
bool g_enableCC = false; // True to listen for MIDI CC command
uint8_t g_universeBase = 1;  // First DMX universe
uint8_t g_universe = 1;  // Current DMX universe
uint8_t g_bufferIndex = 0; // Index of dmx buffer used by current universe
uint8_t g_mode = MIDI_MODE_CC7; // MIDI mode
uint16_t g_midiChannels = 0xffff; // Bitwise flags for enabled MIDI channels
uint8_t g_verbose = 2; // Level of verbosity (0: silent, 1: errors, 2: info, 3: debug)
uint16_t g_nrpnParam = 0; // NRPN parameter being adjusted [0..16383]
uint8_t g_nrpnVal = 0; // NRPN value [0..255]
uint16_t g_slot = 0; // DMX slot being adjusted [0..511]
jack_port_t* g_midiInputPort;  // Pointer to the JACK input port
jack_client_t* g_jackClient = NULL;  // Pointer to the JACK client
ola::DmxBuffer g_dmxBuffer[MAX_MIDI_UNIVERSE];  // DMX data buffer for universe
ola::client::StreamingClient* g_olaClient = NULL; // Pointer to the OLA client
const char* modeNames[] = {"cc7", "cc14", "nrpn7", "nrpn14"};

void debug(const char *format, ...) {
    if (g_verbose > 2) {
        va_list args;
        va_start(args, format);
        vfprintf(stderr, format, args);
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
        fprintf(stderr, "ERROR: ");
        vfprintf(stderr, format, args);
        va_end(args);
    }
}

void help() {
    info("Usage: zynmidiola [options]\n\n"
        "Options:\n"
        "  -h --help        Show this help.\n"
        "  -u --universe    First universe (default: 1).\n"
        "  -n --note        Listen for MIDI note-on (disabled by default).\n"
        "  -c --cc          Listen for MIDI CC (enabled by default but disabled if not specified when note-on is enabled).\n"
        "  -x --exclude     Do not listen on MIDI channel (1..16 Can be provided multiple times).\n"
        "  -m --mode        MIDI mode:\n"
        "    cc7   : CC 0..127 control slots 1..128. MIDI channel = universe (default).\n"
        "    cc14  : CC 0..31 (MSB) 32..63 (LSB) control slots 1..32. MIDI channel = universe. Sent when LSB received.\n"
        "    nrpn7 : NRPN 0..511 control slots 1..512 in first universe, NRPN 512..1023 control second universe, etc. MIDI channel offsets universe (x32).\n"
        "    nrpn14: Same as nrpn7 with 8-bit DMX data, sent when LSB is received from CC38.\n"
        "  -v --version     Show version."
        "  -V --verbose     Set verbose level:\n"
        "    0: Silent\n"
        "    1: Show errors\n"
        "    2: Show info (default)\n"
        "    3: Show debug\n"
    );
}

void parseCommandLine(int argc, char* argv[]) {
    option longopts[] = {
        {"mode", optional_argument, NULL, 'm'}, 
        {"universe", optional_argument, NULL, 'u'},
        {"cc", optional_argument, NULL, 'c'},
        {"note", optional_argument, NULL, 'n'},
        {"verbose", optional_argument, NULL, 'V'},
        {"version", optional_argument, NULL, 'v'},
        {"exclude", optional_argument, NULL, 'x'},
        {"help", optional_argument, NULL, 'h'}, 
        {NULL, 0, 0, 0}};
    while (1) {
        const int opt = getopt_long(argc, argv, "cnhvm:u:V:x:", longopts, 0);
        if (opt == -1) {
            break;
        }
        switch (opt) {
            case ':':
                error("Expected value for %c\n", optopt);
                exit(1);
            case 'm':
                g_mode = -1;
                if (optarg) {
                    for (uint8_t i = 0; i < 4; ++i) {
                        if (strcmp(optarg, modeNames[i]) == 0) {
                            g_mode = i;
                            break;
                        }
                    }
                }
                if (g_mode <= MIDI_MODE_NRPN14)
                    break;
                error("Invalid mode. Expects: cc7, cc14, nrpn7 or nrpn14\n");
                exit(1);
            case 'u':
                if(optarg) {
                    g_universe = atoi(optarg);
                    g_universeBase = g_universe;
                    break;
                }
                error("Invalid universe. Must be number.\n");
                exit(1);
            case 'c':
                g_enableCC = true;
                break;
            case 'n':
                g_enableNote = true;
                break;
            case 'x':
                if(optarg) {
                    long chan = atoi(optarg);
                    if (chan < 1 || chan > 16) {
                        error("Exclude MIDI channel must be between 1..16.\n");
                        exit(1);
                    }
                    uint16_t mask = 1 << (chan - 1);
                    mask = ~mask;
                    g_midiChannels &= mask;
                } else {
                    error("Need to supply option to -x parameter\n");
                }
                break;
            case 'V':
                if(optarg && (g_verbose = atoi(optarg)) <= 3)
                    break;
                error("Verbose must be in range 0..3\n");
                exit(1);
            case 'v':
                info("midiola version %s\n", VERSION);
                exit(0);
            default:
                help();
                exit(0);
        }
    }
}

void cc7(uint8_t channel, uint8_t cc, uint8_t val) {
    /*  @brief  Handle 7-bit (immediate) CC message
        @param  channel MIDI channel [0..15]
        @param  cc MIDI CC [0..127]
        @param  val MIDI value [0..127]
        @note   DMX Slots 1..128 populated by CC 0..127. Universe is MIDI channel + universe base. 
        @note   DMX value is half resolution.
    */

    g_universe = channel + g_universeBase;
    g_bufferIndex = channel;
    val <<= 1;
    g_dmxBuffer[g_bufferIndex].SetChannel(cc, val);
    g_olaClient->SendDmx(g_universe, g_dmxBuffer[g_bufferIndex]);
    debug("Universe: %u slot %u value %u\n", g_universe, cc + 1, val);
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

    if (cc > 65)
        return;

    uint8_t offset = cc % 32;
    uint8_t base = channel * 32;
    g_slot = offset + base;
    uint8_t curVal = g_dmxBuffer[g_bufferIndex].Get(g_slot);
    if (cc > 31) {
        //LSB
        if (val > 63)
            curVal |= 0x01;
        else
            curVal &= 0xfe;
        g_dmxBuffer[g_bufferIndex].SetChannel(g_slot, curVal);
        g_olaClient->SendDmx(g_universe, g_dmxBuffer[g_bufferIndex]);
    } else {
        //MSB
        curVal &= 0x01;
        curVal |= (val << 1);
        g_dmxBuffer[g_bufferIndex].SetChannel(g_slot, curVal);
    }
    debug("Universe: %u slot %u value %u\n", g_universe, g_slot + 1, curVal);
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
            g_slot = g_nrpnParam % 512;
            g_bufferIndex = g_nrpnParam / 512;
            g_universe = g_bufferIndex + g_universeBase;
            debug("NRPN param: %u universe: %u slot: %u\n", g_nrpnParam, g_universe, g_slot + 1);
            break;
        case MIDI_CMD_NRPN_MSB:
            g_nrpnParam = (g_nrpnParam & 0x7f) | (val << 7);
            g_slot = g_nrpnParam % 512;
            g_bufferIndex = g_nrpnParam / 512;
            g_universe = g_bufferIndex + g_universeBase;
            debug("NRPN param: %u universe: %u slot: %u\n", g_nrpnParam, g_universe, g_slot + 1);
            break;
        case MIDI_CMD_DATA_MSB:
            g_nrpnVal = val << 1;
            g_dmxBuffer[g_bufferIndex].SetChannel(g_slot, g_nrpnVal);
            g_olaClient->SendDmx(g_universe, g_dmxBuffer[g_bufferIndex]);
            debug("NRPN param: %u universe: %u slot: %u val: %u\n", g_nrpnParam, g_universe, g_slot + 1, g_nrpnVal);
            break;
        case MIDI_CMD_INC:
            if (g_nrpnVal < 255) {
                g_dmxBuffer[g_bufferIndex].SetChannel(g_slot, ++g_nrpnVal);
                g_olaClient->SendDmx(g_universe, g_dmxBuffer[g_bufferIndex]);
                debug("NRPN param: %u universe: %u slot: %u val: %u\n", g_nrpnParam, g_universe, g_slot + 1, g_nrpnVal);
            }
            break;
        case MIDI_CMD_DEC:
            g_slot = g_nrpnParam % 512;
            if (g_nrpnVal > 0) {
                g_dmxBuffer[g_bufferIndex].SetChannel(g_slot, --g_nrpnVal);
                g_olaClient->SendDmx(g_universe, g_dmxBuffer[g_bufferIndex]);
                debug("NRPN param: %u universe: %u slot: %u val: %u\n", g_nrpnParam, g_universe, g_slot + 1, g_nrpnVal);
            }
            break;
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
            g_slot = g_nrpnParam % 512;
            g_bufferIndex = g_nrpnParam / 512;
            g_universe = g_bufferIndex + g_universeBase;
            debug("NRPN param: %u universe: %u slot: %u\n", g_nrpnParam, g_universe, g_slot + 1);
            break;
        case MIDI_CMD_NRPN_MSB:
            g_nrpnParam = (g_nrpnParam & 0x7f) | (val << 7);
            g_slot = g_nrpnParam % 512;
            g_bufferIndex = g_nrpnParam / 512;
            g_universe = g_bufferIndex + g_universeBase;
            debug("NRPN param: %u universe: %u slot: %u\n", g_nrpnParam, g_universe, g_slot + 1);
            break;
        case MIDI_CMD_DATA_MSB:
            g_nrpnVal = (g_nrpnVal & 0x01) | (val << 1);
            debug("NRPN param: %u val: %u\n", g_nrpnParam, g_nrpnVal);
            break;
        case MIDI_CMD_DATA_LSB:
            if (val > 63)
                g_nrpnVal |= 0x01;
            else
                g_nrpnVal &= 0xfe;
            g_dmxBuffer[g_bufferIndex].SetChannel(g_slot, g_nrpnVal);
            g_olaClient->SendDmx(g_universe, g_dmxBuffer[g_bufferIndex]);
            debug("NRPN param: %u universe: %u slot: %u val: %u\n", g_nrpnParam, g_universe, g_slot + 1, g_nrpnVal);
            break;
        case MIDI_CMD_INC:
            if (g_nrpnVal < 255) {
                g_dmxBuffer[g_bufferIndex].SetChannel(g_slot, ++g_nrpnVal);
                g_olaClient->SendDmx(g_universe, g_dmxBuffer[g_bufferIndex]);
                debug("NRPN param: %u slot: %u val: %u\n", g_nrpnParam, g_slot + 1, g_nrpnVal);
            }
            break;
        case MIDI_CMD_DEC:
            if (g_nrpnVal > 0) {
                g_dmxBuffer[g_bufferIndex].SetChannel(g_slot, --g_nrpnVal);
                g_olaClient->SendDmx(g_universe, g_dmxBuffer[g_bufferIndex]);
                debug("NRPN param: %u slot: %u val: %u\n", g_nrpnParam, g_slot + 1, g_nrpnVal);
            }
            break;
    }
}

int onJackProcess(jack_nframes_t frames, void* args) {
    // Process MIDI input
    uint8_t cmd, chan, cc, val;
    void* midiBuffer = jack_port_get_buffer(g_midiInputPort, frames);
    jack_midi_event_t midiEvent;
    jack_nframes_t count = jack_midi_get_event_count(midiBuffer);
    for (jack_nframes_t eventIndex = 0; eventIndex < count; ++eventIndex) {
        if (jack_midi_event_get(&midiEvent, midiBuffer, eventIndex))
            continue;
        cmd = midiEvent.buffer[0] & 0xf0;
        //debug("Rx MIDI event %u/%u: %02x\n", eventIndex + 1, count, cmd);
        if (g_enableCC && cmd== 0xb0) {
            // MIDI CC
            chan = midiEvent.buffer[0] & 0x0f;
            if (((1 << chan) & g_midiChannels) == 0)
                continue;
            cc = midiEvent.buffer[1];
            val = midiEvent.buffer[2];
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
        } else if (g_enableNote && (cmd == 0x90)) {
            // MIDI Note-on
            chan = midiEvent.buffer[0] & 0x0f;
            if (((1 << chan) & g_midiChannels) == 0)
                continue;
            cc = midiEvent.buffer[1];
            val = midiEvent.buffer[2];
            cc7(chan, cc, val);
        }
    }
    return 0;
}

int main(int argc, char* argv[]) {
    parseCommandLine(argc, argv);
    if (!g_enableNote && !g_enableCC)
        g_enableCC = true;

    info("Starting zynmidiola - JACK MIDI to Openlighting interface\n");
    info("  Mode: %s\n", modeNames[g_mode]);
    info("  First universe: %u\n", g_universeBase);
    info("  Enabled MIDI channels: ");
    bool comma = false;
    for (uint8_t chan = 0; chan < 16; ++chan) {
        if ((1 << chan) & g_midiChannels) {
            if (comma)
                info(", %u", chan + 1);
            else {
                info("%u", chan + 1);
                comma = true;
            }
        }
    }
    info("\n");
    debug("  Debug enabled\n");

    // Create a OLA client.
    ola::client::StreamingClient olaClient((ola::client::StreamingClient::Options()));
    g_olaClient = &olaClient;

    // Setup OLA, connect to the server
    if (!olaClient.Setup()) {
        error("Failed to setup OLA client\n");
        exit(1);
    }
    // Initalise buffers and send to universe
    debug("Initalising DMX buffers\n");
    for (uint8_t universe = 0; universe < MAX_MIDI_UNIVERSE; ++universe) {
        g_dmxBuffer[g_bufferIndex].Blackout();
        olaClient.SendDmx(g_universe, g_dmxBuffer[g_bufferIndex]);
    }

    // Create JACK client
    char* serverName = NULL;
    jack_status_t jackStatus;
    if ((g_jackClient = jack_client_open("zynmidiola", JackNoStartServer, &jackStatus, serverName)) == 0) {
        error("Failed to start jack client: %d\n", jackStatus);
        exit(1);
    }
    // Create MIDI input port
    if (!(g_midiInputPort = jack_port_register(g_jackClient, "input", JACK_DEFAULT_MIDI_TYPE, JackPortIsInput | JackPortIsPhysical, 0))) {
        error("Cannot register input port\n");
        exit(1);
    }
    // Register JACK callbacks
    jack_set_process_callback(g_jackClient, onJackProcess, 0);
    if (jack_activate(g_jackClient)) {
        error("Cannot activate client\n");
        exit(1);
    }

    if (g_enableCC)
        info("Listening for MIDI CC\n");
    if (g_enableNote)
        info("Listening for MIDI Note-On\n");

    while (true) {
        usleep(25000); // Do nothing in program loop
    }

    return 0;
}