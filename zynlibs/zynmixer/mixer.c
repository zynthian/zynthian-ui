/*
 * ******************************************************************
 * ZYNTHIAN PROJECT: Audio Mixer Library
 *
 * Library providing stereo audio summing mixer
 *
 * Copyright (C) 2019-2024 Brian Walton <brian@riban.co.uk>
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

#include <stdio.h>   //provides printf
#include <stdlib.h>  //provides exit
#include <string.h>  // provides memset
#include <math.h>    //provides fabs isinf
#include <unistd.h>  // provides sleep
#include <pthread.h> //provides multithreading

#include "mixer.h"

#include "tinyosc.h"
#include <arpa/inet.h> // provides inet_pton

char g_oscbuffer[1024];  // Used to send OSC messages
char g_oscpath[20];      //!@todo Ensure path length is sufficient for all paths, e.g. /mixer/faderxxx
int g_oscfd = -1;        // File descriptor for OSC socket
int g_bOsc = 0;          // True if OSC client subscribed
pthread_t g_eventThread; // ID of low priority event thread
int g_sendEvents = 1;    // Set to 0 to exit event thread
int g_solo = 0;          // True if any channel solo enabled

// #define DEBUG

#define MAX_CHANNELS 17
#define MAX_OSC_CLIENTS 5

struct dynamic {
    jack_port_t *inPortA;  // Jack input port A
    jack_port_t *inPortB;  // Jack input port B
    jack_port_t *outPortA; // Jack output port A
    jack_port_t *outPortB; // Jack output port B
    float level;           // Current fader level 0..1
    float reqlevel;        // Requested fader level 0..1
    float balance;         // Current balance -1..+1
    float reqbalance;      // Requested balance -1..+1
    float dpmA;            // Current peak programme A-leg
    float dpmB;            // Current peak programme B-leg
    float holdA;           // Current peak hold level A-leg
    float holdB;           // Current peak hold level B-leg
    uint8_t mute;          // 1 if muted
    uint8_t solo;          // 1 if solo
    uint8_t mono;          // 1 if mono
    uint8_t ms;            // 1 if MS decoding
    uint8_t phase;         // 1 if channel B phase reversed
    uint8_t normalise;     // 1 if channel normalised to main output (when output not routed)
    uint8_t inRouted;      // 1 if source routed to channel
    uint8_t outRouted;     // 1 if output routed
    uint8_t enable_dpm;    // 1 to enable calculation of peak meter
};

jack_client_t *g_pJackClient;
struct dynamic g_dynamic[MAX_CHANNELS];
struct dynamic g_dynamic_last[MAX_CHANNELS]; // Previous values used to thin OSC updates
unsigned int g_nDampingCount = 0;
unsigned int g_nDampingPeriod = 10; // Quantity of cycles between applying DPM damping decay
unsigned int g_nHoldCount = 0;
float g_fDpmDecay = 0.9;                         // Factor to scale for DPM decay - defines resolution of DPM decay
struct sockaddr_in g_oscClient[MAX_OSC_CLIENTS]; // Array of registered OSC clients
char g_oscdpm[20];
jack_nframes_t g_samplerate = 44100; // Jack samplerate used to calculate damping factor
jack_nframes_t g_buffersize = 1024;  // Jack buffer size used to calculate damping factor
jack_default_audio_sample_t* pNormalisedBufferA = NULL; // Pointer to buffer for normalised audio
jack_default_audio_sample_t* pNormalisedBufferB = NULL; // Pointer to buffer for normalised audio

static float convertToDBFS(float raw) {
    if (raw <= 0)
        return -200;
    float fValue = 20 * log10f(raw);

    if (fValue < -200)
        fValue = -200;
    return fValue;
}

void sendOscFloat(const char *path, float value) {
    if (g_oscfd == -1)
        return;
    for (int i = 0; i < MAX_OSC_CLIENTS; ++i) {
        if (g_oscClient[i].sin_addr.s_addr == 0)
            continue;
        int len = tosc_writeMessage(g_oscbuffer, sizeof(g_oscbuffer), path, "f", value);
        sendto(g_oscfd, g_oscbuffer, len, MSG_CONFIRM | MSG_DONTWAIT, (const struct sockaddr *)&g_oscClient[i], sizeof(g_oscClient[i]));
    }
}

void sendOscInt(const char *path, int value) {
    if (g_oscfd == -1)
        return;
    for (int i = 0; i < MAX_OSC_CLIENTS; ++i) {
        if (g_oscClient[i].sin_addr.s_addr == 0)
            continue;
        int len = tosc_writeMessage(g_oscbuffer, sizeof(g_oscbuffer), path, "i", value);
        sendto(g_oscfd, g_oscbuffer, len, MSG_CONFIRM | MSG_DONTWAIT, (const struct sockaddr *)&g_oscClient[i], sizeof(g_oscClient[i]));
    }
}

void *eventThreadFn(void *param) {
    while (g_sendEvents) {
        if (g_bOsc) {
            for (unsigned int chan = 0; chan < MAX_CHANNELS; chan++) {
                if ((int)(100000 * g_dynamic_last[chan].dpmA) != (int)(100000 * g_dynamic[chan].dpmA)) {
                    sprintf(g_oscdpm, "/mixer/dpm%da", chan);
                    sendOscFloat(g_oscdpm, convertToDBFS(g_dynamic[chan].dpmA));
                    g_dynamic_last[chan].dpmA = g_dynamic[chan].dpmA;
                }
                if ((int)(100000 * g_dynamic_last[chan].dpmB) != (int)(100000 * g_dynamic[chan].dpmB)) {
                    sprintf(g_oscdpm, "/mixer/dpm%db", chan);
                    sendOscFloat(g_oscdpm, convertToDBFS(g_dynamic[chan].dpmB));
                    g_dynamic_last[chan].dpmB = g_dynamic[chan].dpmB;
                }
                if ((int)(100000 * g_dynamic_last[chan].holdA) != (int)(100000 * g_dynamic[chan].holdA)) {
                    sprintf(g_oscdpm, "/mixer/hold%da", chan);
                    sendOscFloat(g_oscdpm, convertToDBFS(g_dynamic[chan].holdA));
                    g_dynamic_last[chan].holdA = g_dynamic[chan].holdA;
                }
                if ((int)(100000 * g_dynamic_last[chan].holdB) != (int)(100000 * g_dynamic[chan].holdB)) {
                    sprintf(g_oscdpm, "/mixer/hold%db", chan);
                    sendOscFloat(g_oscdpm, convertToDBFS(g_dynamic[chan].holdB));
                    g_dynamic_last[chan].holdB = g_dynamic[chan].holdB;
                }
            }
        }
        usleep(10000);
    }
    pthread_exit(NULL);
}

static int onJackProcess(jack_nframes_t nFrames, void *pArgs) {
    jack_default_audio_sample_t *pInA, *pInB, *pOutA, *pOutB, *pChanOutA, *pChanOutB;

    unsigned int frame, chan;
    float curLevelA, curLevelB, reqLevelA, reqLevelB, fDeltaA, fDeltaB, fSampleA, fSampleB, fSampleM;

    // Clear the normalisation buffer. This will be populated by each channel then used in final channel iteration
    memset(pNormalisedBufferA, 0.0, nFrames * sizeof(jack_default_audio_sample_t));
    memset(pNormalisedBufferB, 0.0, nFrames * sizeof(jack_default_audio_sample_t));

    // Process each channel
    for (chan = 0; chan < MAX_CHANNELS; chan++) {
        if (isChannelRouted(chan) || (chan == (MAX_CHANNELS - 1))) {
            //**Calculate processing levels**

            // Calculate current (last set) balance
            if (g_dynamic[chan].balance > 0.0)
                curLevelA = g_dynamic[chan].level * (1 - g_dynamic[chan].balance);
            else
                curLevelA = g_dynamic[chan].level;
            if (g_dynamic[chan].balance < 0.0)
                curLevelB = g_dynamic[chan].level * (1 + g_dynamic[chan].balance);
            else
                curLevelB = g_dynamic[chan].level;

            // Calculate mute and target level and balance (that we will fade to over this cycle period to avoid abrupt change clicks)
            if (g_dynamic[chan].mute || g_solo && (chan < MAX_CHANNELS - 1) && g_dynamic[chan].solo != 1) {
                // Do not mute aux if solo enabled
                g_dynamic[chan].level = 0; // We can set this here because we have the data and will iterate towards 0 over this frame
                reqLevelA = 0.0;
                reqLevelB = 0.0;
            } else {
                if (g_dynamic[chan].reqbalance > 0.0)
                    reqLevelA = g_dynamic[chan].reqlevel * (1 - g_dynamic[chan].reqbalance);
                else
                    reqLevelA = g_dynamic[chan].reqlevel;
                if (g_dynamic[chan].reqbalance < 0.0)
                    reqLevelB = g_dynamic[chan].reqlevel * (1 + g_dynamic[chan].reqbalance);
                else
                    reqLevelB = g_dynamic[chan].reqlevel;
                g_dynamic[chan].level = g_dynamic[chan].reqlevel;
                g_dynamic[chan].balance = g_dynamic[chan].reqbalance;
            }

            // Calculate the step change for each leg to apply on each sample in buffer for fade between last and this period's level
            fDeltaA = (reqLevelA - curLevelA) / nFrames;
            fDeltaB = (reqLevelB - curLevelB) / nFrames;

            // **Apply processing to audio samples**

            pInA = jack_port_get_buffer(g_dynamic[chan].inPortA, nFrames);
            pInB = jack_port_get_buffer(g_dynamic[chan].inPortB, nFrames);

            if(isChannelOutRouted(chan)) {
                // Direct output so create audio buffers
                pChanOutA = jack_port_get_buffer(g_dynamic[chan].outPortA, nFrames);
                pChanOutB = jack_port_get_buffer(g_dynamic[chan].outPortB, nFrames);
                memset(pChanOutA, 0.0, nFrames * sizeof(jack_default_audio_sample_t));
                memset(pChanOutB, 0.0, nFrames * sizeof(jack_default_audio_sample_t));
            } else {
                pChanOutA = pChanOutB = NULL;
            }

            // Iterate samples, scaling each and adding to output and set DPM if any samples louder than current DPM
            for (frame = 0; frame < nFrames; frame++) {
                if (chan == MAX_CHANNELS - 1) {
                    // Mix channel input and normalised channels mix
                    fSampleA = (pInA[frame] + pNormalisedBufferA[frame]);
                    fSampleB = (pInB[frame] + pNormalisedBufferB[frame]);
                } else {
                    fSampleA = pInA[frame];
                    fSampleB = pInB[frame];
                }
                // Handle channel phase reverse
                if (g_dynamic[chan].phase)
                    fSampleB = -fSampleB;

                // Decode M+S
                if (g_dynamic[chan].ms) {
                    fSampleM = fSampleA + fSampleB;
                    fSampleB = fSampleA - fSampleB;
                    fSampleA = fSampleM;
                }

                // Handle mono
                if (g_dynamic[chan].mono) {
                    fSampleA = (fSampleA + fSampleB) / 2.0;
                    fSampleB = fSampleA;
                }

                // Apply level adjustment
                fSampleA *= curLevelA;
                fSampleB *= curLevelB;

                // Check for error
                if (isinf(fSampleA))
                    fSampleA = 1.0;
                if (isinf(fSampleB))
                    fSampleB = 1.0;

                // Write sample to output buffer
                if(pChanOutA) {
                    pChanOutA[frame] += fSampleA;
                    pChanOutB[frame] += fSampleB;
                }
                // Write normalised samples
                if (chan < MAX_CHANNELS - 1 && g_dynamic[chan].normalise) {
                    pNormalisedBufferA[frame] += fSampleA;
                    pNormalisedBufferB[frame] += fSampleB;
                }

                curLevelA += fDeltaA;
                curLevelB += fDeltaB;

                // Process DPM
                if (g_dynamic[chan].enable_dpm) {
                    fSampleA = fabs(fSampleA);
                    if (fSampleA > g_dynamic[chan].dpmA)
                        g_dynamic[chan].dpmA = fSampleA;
                    fSampleB = fabs(fSampleB);
                    if (fSampleB > g_dynamic[chan].dpmB)
                        g_dynamic[chan].dpmB = fSampleB;

                    // Update peak hold and scale DPM for damped release
                    if (g_dynamic[chan].dpmA > g_dynamic[chan].holdA)
                        g_dynamic[chan].holdA = g_dynamic[chan].dpmA;
                    if (g_dynamic[chan].dpmB > g_dynamic[chan].holdB)
                        g_dynamic[chan].holdB = g_dynamic[chan].dpmB;
                }
            }
            if (g_nHoldCount == 0) {
                // Only update peak hold each g_nHoldCount cycles
                g_dynamic[chan].holdA = g_dynamic[chan].dpmA;
                g_dynamic[chan].holdB = g_dynamic[chan].dpmB;
            }
            if (g_nDampingCount == 0) {
                // Only update damping release each g_nDampingCount cycles
                g_dynamic[chan].dpmA *= g_fDpmDecay;
                g_dynamic[chan].dpmB *= g_fDpmDecay;
            }
        } else if (g_dynamic[chan].enable_dpm) {
            g_dynamic[chan].dpmA = -200.0;
            g_dynamic[chan].dpmB = -200.0;
            g_dynamic[chan].holdA = -200.0;
            g_dynamic[chan].holdB = -200.0;
        }
    }

    if (g_nDampingCount == 0)
        g_nDampingCount = g_nDampingPeriod;
     else
        --g_nDampingCount;
    if (g_nHoldCount == 0)
        g_nHoldCount = g_nDampingPeriod * 20;
    else
        --g_nHoldCount;

    return 0;
}

void onJackConnect(jack_port_id_t source, jack_port_id_t dest, int connect, void *args) {
    uint8_t chan;
    for (chan = 0; chan < MAX_CHANNELS; chan++) {
        if (jack_port_connected(g_dynamic[chan].inPortA) > 0 || (jack_port_connected(g_dynamic[chan].inPortB) > 0))
            g_dynamic[chan].inRouted = 1;
        else
            g_dynamic[chan].inRouted = 0;
        if (jack_port_connected(g_dynamic[chan].outPortA) > 0 || (jack_port_connected(g_dynamic[chan].outPortB) > 0))
            g_dynamic[chan].outRouted = 1;
        else
            g_dynamic[chan].outRouted = 0;
    }
}

int onJackSamplerate(jack_nframes_t nSamplerate, void *arg) {
    if (nSamplerate == 0)
        return 0;
    g_samplerate = nSamplerate;
    g_nDampingPeriod = g_fDpmDecay * nSamplerate / g_buffersize / 15;
    return 0;
}

int onJackBuffersize(jack_nframes_t nBuffersize, void *arg) {
    if (nBuffersize == 0)
        return 0;
    g_buffersize = nBuffersize;
    g_nDampingPeriod = g_fDpmDecay * g_samplerate / g_buffersize / 15;
    free(pNormalisedBufferA);
    free(pNormalisedBufferB);
    pNormalisedBufferA = malloc(nBuffersize * sizeof(jack_default_audio_sample_t));
    pNormalisedBufferB = malloc(nBuffersize * sizeof(jack_default_audio_sample_t));
    return 0;
}

int init() {
    // Initialsize OSC
    g_oscfd = socket(AF_INET, SOCK_DGRAM, 0);
    for (uint8_t i = 0; i < MAX_OSC_CLIENTS; ++i) {
        memset(g_oscClient[i].sin_zero, '\0', sizeof g_oscClient[i].sin_zero);
        g_oscClient[i].sin_family = AF_INET;
        g_oscClient[i].sin_port = htons(1370);
        g_oscClient[i].sin_addr.s_addr = 0;
    }

    // Register with Jack server
    char *sServerName = NULL;
    jack_status_t nStatus;
    jack_options_t nOptions = JackNoStartServer;

    if ((g_pJackClient = jack_client_open("zynmixer", nOptions, &nStatus, sServerName)) == 0) {
        fprintf(stderr, "libzynmixer: Failed to start jack client: %d\n", nStatus);
        exit(1);
    }
#ifdef DEBUG
    fprintf(stderr, "libzynmixer: Registering as '%s'.\n", jack_get_client_name(g_pJackClient));
#endif

    // Create input ports
    for (size_t chan = 0; chan < MAX_CHANNELS; ++chan) {
        g_dynamic[chan].level = 0.0;
        g_dynamic[chan].reqlevel = 0.8;
        g_dynamic[chan].balance = 0.0;
        g_dynamic[chan].reqbalance = 0.0;
        g_dynamic[chan].mute = 0;
        g_dynamic[chan].ms = 0;
        g_dynamic[chan].phase = 0;
        g_dynamic[chan].enable_dpm = 1;
        g_dynamic[chan].normalise = 1;
        char sName[11];
        sprintf(sName, "input_%02lda", chan + 1);
        if (!(g_dynamic[chan].inPortA = jack_port_register(g_pJackClient, sName, JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0))) {
            fprintf(stderr, "libzynmixer: Cannot register %s\n", sName);
            exit(1);
        }
        sprintf(sName, "input_%02ldb", chan + 1);
        if (!(g_dynamic[chan].inPortB = jack_port_register(g_pJackClient, sName, JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0))) {
            fprintf(stderr, "libzynmixer: Cannot register %s\n", sName);
            exit(1);
        }
        sprintf(sName, "output_%02lda", chan + 1);
        if (!(g_dynamic[chan].outPortA = jack_port_register(g_pJackClient, sName, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0))) {
            fprintf(stderr, "libzynmixer: Cannot register %s\n", sName);
            exit(1);
        }
        sprintf(sName, "output_%02ldb", chan + 1);
        if (!(g_dynamic[chan].outPortB = jack_port_register(g_pJackClient, sName, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0))) {
            fprintf(stderr, "libzynmixer: Cannot register %s\n", sName);
            exit(1);
        }
        g_dynamic_last[chan].dpmA = 100.0;
        g_dynamic_last[chan].dpmB = 100.0;
        g_dynamic_last[chan].holdA = 100.0;
        g_dynamic_last[chan].holdB = 100.0;
    }

#ifdef DEBUG
    fprintf(stderr, "libzynmixer: Created input ports\n");
#endif

    // Register the cleanup function to be called when library exits
    atexit(end);

    // Register the callbacks
    jack_set_process_callback(g_pJackClient, onJackProcess, 0);
    jack_set_port_connect_callback(g_pJackClient, onJackConnect, 0);
    jack_set_sample_rate_callback(g_pJackClient, onJackSamplerate, 0);
    jack_set_buffer_size_callback(g_pJackClient, onJackBuffersize, 0);

    if (jack_activate(g_pJackClient)) {
        fprintf(stderr, "libzynmixer: Cannot activate client\n");
        exit(1);
    }

#ifdef DEBUG
    fprintf(stderr, "libzynmixer: Activated client\n");
#endif

    // Configure and start event thread
    pthread_attr_t attr;
    pthread_attr_init(&attr);
    pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_JOINABLE);
    if (pthread_create(&g_eventThread, &attr, eventThreadFn, NULL)) {
        fprintf(stderr, "zynmixer error: failed to create event thread\n");
        return 0;
    }

    fprintf(stderr, "Started libzynmixer\n");

    return 1;
}

void end() {
    if (g_pJackClient) {
        // Mute output and wait for soft mute to occur before closing link with jack server
        setLevel(MAX_CHANNELS - 1, 0.0);
        usleep(100000);
        // jack_client_close(g_pJackClient);
    }
    g_sendEvents = 0;
    free(pNormalisedBufferA);
    free(pNormalisedBufferB);

    void *status;
    pthread_join(g_eventThread, &status);
}

void setLevel(uint8_t channel, float level) {
    if (channel >= MAX_CHANNELS)
        channel = MAX_CHANNELS - 1;
    else
        g_dynamic[channel].reqlevel = level;
    sprintf(g_oscpath, "/mixer/fader%d", channel);
    sendOscFloat(g_oscpath, level);
}

float getLevel(uint8_t channel) {
    if (channel >= MAX_CHANNELS)
        channel = MAX_CHANNELS - 1;
    return g_dynamic[channel].reqlevel;
}

void setBalance(uint8_t channel, float balance) {
    if (fabs(balance) > 1)
        return;
    if (channel >= MAX_CHANNELS)
        channel = MAX_CHANNELS - 1;
    g_dynamic[channel].reqbalance = balance;
    sprintf(g_oscpath, "/mixer/balance%d", channel);
    sendOscFloat(g_oscpath, balance);
}

float getBalance(uint8_t channel) {
    if (channel >= MAX_CHANNELS)
        channel = MAX_CHANNELS - 1;
    return g_dynamic[channel].reqbalance;
}

void setMute(uint8_t channel, uint8_t mute) {
    if (channel >= MAX_CHANNELS)
        channel = MAX_CHANNELS - 1;
    g_dynamic[channel].mute = mute;
    sprintf(g_oscpath, "/mixer/mute%d", channel);
    sendOscInt(g_oscpath, mute);
}

uint8_t getMute(uint8_t channel) {
    if (channel >= MAX_CHANNELS)
        channel = MAX_CHANNELS - 1;
    return g_dynamic[channel].mute;
}

void setPhase(uint8_t channel, uint8_t phase) {
    if (channel >= MAX_CHANNELS) 
        channel = MAX_CHANNELS - 1;
    g_dynamic[channel].phase = phase;
    sprintf(g_oscpath, "/mixer/phase%d", channel);
    sendOscInt(g_oscpath, phase);
}

uint8_t getPhase(uint8_t channel) {
    if (channel >= MAX_CHANNELS)
        return 0;
    if (channel >= MAX_CHANNELS)
        channel = MAX_CHANNELS - 1;
    return g_dynamic[channel].phase;
}

void setNormalise(uint8_t channel, uint8_t enable) {
    if (channel >= MAX_CHANNELS)
        channel = MAX_CHANNELS - 1;
    g_dynamic[channel].normalise = enable;
    sprintf(g_oscpath, "/mixer/normalise%d", channel);
    sendOscInt(g_oscpath, enable);
}

uint8_t getNormalise(uint8_t channel, uint8_t enable) {
    if (channel >= MAX_CHANNELS)
        return 0;
    if (channel >= MAX_CHANNELS)
         channel = MAX_CHANNELS - 1;
    return g_dynamic[channel].normalise;
}

void setSolo(uint8_t channel, uint8_t solo) {
    if (channel + 1 >= MAX_CHANNELS) {
        // Setting main mixbus solo will disable all channel solos
        for (uint8_t nChannel = 0; nChannel < MAX_CHANNELS - 1; ++nChannel) {
            g_dynamic[nChannel].solo = 0;
            sprintf(g_oscpath, "/mixer/solo%d", nChannel);
            sendOscInt(g_oscpath, 0);
        }
    } else {
        g_dynamic[channel].solo = solo;
        sprintf(g_oscpath, "/mixer/solo%d", channel);
        sendOscInt(g_oscpath, solo);
    }
    // Set the global solo flag if any channel solo is enabled
    g_solo = 0;
    for (uint8_t nChannel = 0; nChannel < MAX_CHANNELS - 1; ++nChannel)
        g_solo |= g_dynamic[nChannel].solo;
    sprintf(g_oscpath, "/mixer/solo%d", MAX_CHANNELS - 1);
    sendOscInt(g_oscpath, g_solo);
}

uint8_t getSolo(uint8_t channel) {
    if (channel >= MAX_CHANNELS)
        channel = MAX_CHANNELS - 1;
    return g_dynamic[channel].solo;
}

void toggleMute(uint8_t channel) {
    uint8_t mute;
    if (channel >= MAX_CHANNELS)
        channel = MAX_CHANNELS - 1;
    mute = g_dynamic[channel].mute;
    if (mute)
        setMute(channel, 0);
    else
        setMute(channel, 1);
}

void togglePhase(uint8_t channel) {
    uint8_t phase;
    if (channel >= MAX_CHANNELS)
        channel = MAX_CHANNELS - 1;
    phase = g_dynamic[channel].phase;
    if (phase)
        setPhase(channel, 0);
    else
        setPhase(channel, 1);
}

void setMono(uint8_t channel, uint8_t mono) {
    if (channel >= MAX_CHANNELS)
        channel = MAX_CHANNELS - 1;
    g_dynamic[channel].mono = (mono != 0);
    sprintf(g_oscpath, "/mixer/mono%d", channel);
    sendOscInt(g_oscpath, mono);
}

uint8_t getMono(uint8_t channel) {
    if (channel >= MAX_CHANNELS)
        channel = MAX_CHANNELS - 1;
    return g_dynamic[channel].mono;
}

void setMS(uint8_t channel, uint8_t enable) {
    if (channel >= MAX_CHANNELS)
        channel = MAX_CHANNELS - 1;
    g_dynamic[channel].ms = enable != 0;
}

uint8_t getMS(uint8_t channel) {
    if (channel >= MAX_CHANNELS)
        channel = MAX_CHANNELS - 1;
    return g_dynamic[channel].ms;
}

void reset(uint8_t channel) {
    if (channel >= MAX_CHANNELS)
        channel = MAX_CHANNELS - 1;
    setLevel(channel, 0.8);
    setBalance(channel, 0.0);
    setMute(channel, 0);
    setMono(channel, 0);
    setPhase(channel, 0);
    setSolo(channel, 0);
}

uint8_t isChannelRouted(uint8_t channel) {
    if (channel >= MAX_CHANNELS)
        return 0;
    return g_dynamic[channel].inRouted;
}

uint8_t isChannelOutRouted(uint8_t channel) {
    if (channel >= MAX_CHANNELS)
        return 0;
    return g_dynamic[channel].outRouted;
}

float getDpm(uint8_t channel, uint8_t leg) {
    if (channel >= MAX_CHANNELS)
        channel = MAX_CHANNELS - 1;
    if (leg)
        return convertToDBFS(g_dynamic[channel].dpmB);
    return convertToDBFS(g_dynamic[channel].dpmA);
}

float getDpmHold(uint8_t channel, uint8_t leg) {
    if (channel >= MAX_CHANNELS)
        channel = MAX_CHANNELS - 1;
    if (leg)
        return convertToDBFS(g_dynamic[channel].holdB);
    return convertToDBFS(g_dynamic[channel].holdA);
}

void getDpmStates(uint8_t start, uint8_t end, float *values) {
    if (start > end) {
        uint8_t tmp = start;
        start = end;
        end = tmp;
    }
    if (end > MAX_CHANNELS)
        end = MAX_CHANNELS;
    if (start > MAX_CHANNELS)
        start = MAX_CHANNELS;
    uint8_t count = end - start + 1;
    while (count--) {
        *(values++) = getDpm(start, 0);
        *(values++) = getDpm(start, 1);
        *(values++) = getDpmHold(start, 0);
        *(values++) = getDpmHold(start, 1);
        *(values++) = getMono(start);
        ++start;
    }
}

void enableDpm(uint8_t start, uint8_t end, uint8_t enable) {
    struct dynamic *pChannel;
    if (start > end) {
        uint8_t tmp = start;
        start = end;
        end = tmp;
    }
    if (start >= MAX_CHANNELS)
        start = MAX_CHANNELS - 1;
    if (end >= MAX_CHANNELS)
        end = MAX_CHANNELS - 1;
    for (uint8_t channel = start; channel <= end; ++channel) {
        pChannel = &(g_dynamic[channel]);
        pChannel->enable_dpm = enable;
        if (enable == 0) {
            pChannel->dpmA = 0;
            pChannel->dpmB = 0;
            pChannel->holdA = 0;
            pChannel->holdB = 0;
        }
    }
}

int addOscClient(const char *client) {
    for (uint8_t i = 0; i < MAX_OSC_CLIENTS; ++i) {
        if (g_oscClient[i].sin_addr.s_addr != 0)
            continue;
        if (inet_pton(AF_INET, client, &(g_oscClient[i].sin_addr)) != 1) {
            g_oscClient[i].sin_addr.s_addr = 0;
            fprintf(stderr, "libzynmixer: Failed to register client %s\n", client);
            return -1;
        }
        fprintf(stderr, "libzynmixer: Added OSC client %d: %s\n", i, client);
        for (int nChannel = 0; nChannel < MAX_CHANNELS; ++nChannel) {
            setBalance(nChannel, getBalance(nChannel));
            setLevel(nChannel, getLevel(nChannel));
            setMono(nChannel, getMono(nChannel));
            setMute(nChannel, getMute(nChannel));
            setPhase(nChannel, getPhase(nChannel));
            setSolo(nChannel, getSolo(nChannel));
            g_dynamic_last[nChannel].dpmA = 100.0;
            g_dynamic_last[nChannel].dpmB = 100.0;
            g_dynamic_last[nChannel].holdA = 100.0;
            g_dynamic_last[nChannel].holdB = 100.0;
        }
        g_bOsc = 1;
        return i;
    }
    fprintf(stderr, "libzynmixer: Not adding OSC client %s - Maximum client count reached [%d]\n", client, MAX_OSC_CLIENTS);
    return -1;
}

void removeOscClient(const char *client) {
    char pClient[sizeof(struct in_addr)];
    if (inet_pton(AF_INET, client, pClient) != 1)
        return;
    g_bOsc = 0;
    for (uint8_t i = 0; i < MAX_OSC_CLIENTS; ++i) {
        if (memcmp(pClient, &g_oscClient[i].sin_addr.s_addr, 4) == 0) {
            g_oscClient[i].sin_addr.s_addr = 0;
            fprintf(stderr, "libzynmixer: Removed OSC client %d: %s\n", i, client);
        }
        if (g_oscClient[i].sin_addr.s_addr != 0)
            g_bOsc = 1;
    }
}

uint8_t getMaxChannels() {
    return MAX_CHANNELS;
}
