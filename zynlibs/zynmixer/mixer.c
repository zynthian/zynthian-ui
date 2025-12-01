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

#include <math.h>    //provides fabs isinf
#include <pthread.h> //provides multithreading
#include <stdio.h>   //provides printf
#include <stdlib.h>  //provides exit
#include <string.h>  // provides memset
#include <unistd.h>  // provides sleep

#include "mixer.h"

#include "tinyosc.h" // provides OSC
#include <arpa/inet.h> // provides inet_pton

// #define DEBUG

#ifndef MAX_CHANNELS
#define MAX_CHANNELS 99
#endif
#define MAX_OSC_CLIENTS 5

pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
char g_oscbuffer[1024];  // Used to send OSC messages
char g_oscpath[64];      //!@todo Ensure path length is sufficient for all paths, e.g. /mixer/channel/xx/fader
int g_oscfd = -1;        // File descriptor for OSC socket
int g_bOsc  = 0;         // True if OSC client subscribed
pthread_t g_eventThread; // ID of low priority event thread
int g_sendEvents = 1;    // Set to 0 to exit event thread
uint8_t g_sendCount = 0; // Quantity of effect sends
uint8_t g_lastStrip = 1; // Highest index of any strips (one-based)
uint8_t g_lastSend  = 1; // Highest index of any send (one-based)

// Structure describing a channel strip
struct channel_strip {
    jack_port_t* inPortA;  // Jack input port A
    jack_port_t* inPortB;  // Jack input port B
    jack_port_t* outPortA; // Jack output port A
    jack_port_t* outPortB; // Jack output port B
    float level;           // Current fader level 0..1
    float reqlevel;        // Requested fader level 0..1
    float balance;         // Current balance -1..+1
    float reqbalance;      // Requested balance -1..+1
    float send[MAX_CHANNELS]; // Current fx send levels
    float dpmA;            // Current peak programme A-leg
    float dpmB;            // Current peak programme B-leg
    float holdA;           // Current peak hold level A-leg
    float holdB;           // Current peak hold level B-leg
    float dpmAlast;        // Last peak programme A-leg
    float dpmBlast;        // Last peak programme B-leg
    float holdAlast;       // Last peak hold level A-leg
    float holdBlast;       // Last peak hold level B-leg
    uint8_t mute;          // 1 if muted
    uint8_t mono;          // 1 if mono
    uint8_t ms;            // 1 if MS decoding
    uint8_t phase;         // 1 if channel B phase reversed
    uint8_t sendMode[MAX_CHANNELS]; // 0: post-fader send, 1: pre-fader send
    uint8_t normalise;     // 1 if channel normalised to main output
    uint8_t inRouted;      // 1 if source routed to channel
    uint8_t outRouted;     // 1 if output routed
    uint8_t enable_dpm;    // 1 to enable calculation of peak meter
};

struct fx_send {
    jack_port_t* outPortA; // Jack output port A
    jack_port_t* outPortB; // Jack output port B
    jack_default_audio_sample_t* bufferA; // Holds audio samples
    jack_default_audio_sample_t* bufferB; // Holds audio samples
    float level;           // Current fader level 0..1
};

jack_client_t* g_jackClient;
struct channel_strip* g_channelStrips[MAX_CHANNELS];
#ifndef MIXBUS
struct fx_send* g_fxSends[MAX_CHANNELS];
#endif
unsigned int g_nDampingCount  = 0;
unsigned int g_nDampingPeriod = 10; // Quantity of cycles between applying DPM damping decay
unsigned int g_nHoldCount     = 0;
float g_fDpmDecay             = 0.9;             // Factor to scale for DPM decay - defines resolution of DPM decay
struct sockaddr_in g_oscClient[MAX_OSC_CLIENTS]; // Array of registered OSC clients
char g_oscdpm[20];
jack_nframes_t g_samplerate                     = 48000; // Jack samplerate used to calculate damping factor
jack_nframes_t g_buffersize                     = 1024;  // Jack buffer size used to calculate damping factor
#ifdef MIXBUS
jack_default_audio_sample_t* g_mainNoramliseBufferA    = NULL;  // Ponter to main output normalised buffer used for normalising effects sends to main mixbus
jack_default_audio_sample_t* g_mainNoramliseBufferB    = NULL;  // Ponter to main output normalised buffer used for normalising effects sends to main mixbus
#endif

static float convertToDBFS(float raw) {
    if (raw <= 0)
        return -200;
    float fValue = 20 * log10f(raw);

    if (fValue < -200)
        fValue = -200;
    return fValue;
}

void sendOscFloat(const char* path, float value) {
    if (g_oscfd == -1)
        return;
    for (int i = 0; i < MAX_OSC_CLIENTS; ++i) {
        if (g_oscClient[i].sin_addr.s_addr == 0)
            continue;
        int len = tosc_writeMessage(g_oscbuffer, sizeof(g_oscbuffer), path, "f", value);
        sendto(g_oscfd, g_oscbuffer, len, MSG_CONFIRM | MSG_DONTWAIT, (const struct sockaddr*)&g_oscClient[i], sizeof(g_oscClient[i]));
    }
}

void sendOscInt(const char* path, int value) {
    if (g_oscfd == -1)
        return;
    for (int i = 0; i < MAX_OSC_CLIENTS; ++i) {
        if (g_oscClient[i].sin_addr.s_addr == 0)
            continue;
        int len = tosc_writeMessage(g_oscbuffer, sizeof(g_oscbuffer), path, "i", value);
        sendto(g_oscfd, g_oscbuffer, len, MSG_CONFIRM | MSG_DONTWAIT, (const struct sockaddr*)&g_oscClient[i], sizeof(g_oscClient[i]));
    }
}

void* eventThreadFn(void* param) {
    while (g_sendEvents) {
        if (g_bOsc) {
            for (unsigned int chan = 0; chan < MAX_CHANNELS; ++chan) {
                if (g_channelStrips[chan]) {
                    if ((int)(100000 * g_channelStrips[chan]->dpmAlast) != (int)(100000 * g_channelStrips[chan]->dpmA)) {
                        sprintf(g_oscdpm, "/mixer/channel/%d/dpma", chan);
                        sendOscFloat(g_oscdpm, convertToDBFS(g_channelStrips[chan]->dpmA));
                        g_channelStrips[chan]->dpmAlast = g_channelStrips[chan]->dpmA;
                    }
                    if ((int)(100000 * g_channelStrips[chan]->dpmBlast) != (int)(100000 * g_channelStrips[chan]->dpmB)) {
                        sprintf(g_oscdpm, "/mixer/channel/%d/dpmb", chan);
                        sendOscFloat(g_oscdpm, convertToDBFS(g_channelStrips[chan]->dpmB));
                        g_channelStrips[chan]->dpmBlast = g_channelStrips[chan]->dpmB;
                    }
                    if ((int)(100000 * g_channelStrips[chan]->holdAlast) != (int)(100000 * g_channelStrips[chan]->holdA)) {
                        sprintf(g_oscdpm, "/mixer/channel/%d/holda", chan);
                        sendOscFloat(g_oscdpm, convertToDBFS(g_channelStrips[chan]->holdA));
                        g_channelStrips[chan]->holdAlast = g_channelStrips[chan]->holdA;
                    }
                    if ((int)(100000 * g_channelStrips[chan]->holdBlast) != (int)(100000 * g_channelStrips[chan]->holdB)) {
                        sprintf(g_oscdpm, "/mixer/channel/%d/holdb", chan);
                        sendOscFloat(g_oscdpm, convertToDBFS(g_channelStrips[chan]->holdB));
                        g_channelStrips[chan]->holdBlast = g_channelStrips[chan]->holdB;
                    }
                }
            }
        }
        usleep(10000);
    }
}

static int onJackProcess(jack_nframes_t frames, void* args) {
    jack_default_audio_sample_t *pInA, *pInB, *pOutA, *pOutB, *pChanOutA, *pChanOutB, *pMainOutA, *pMainOutB;
    unsigned int frame;
    float curLevelA, curLevelB, reqLevelA, reqLevelB, fDeltaA, fDeltaB, fSampleA, fSampleB, fSampleM, fpreFaderSampleA, fpreFaderSampleB;

    pthread_mutex_lock(&mutex);

#ifdef MIXBUS
    // Clear the main mixbus output buffers to allow them to be directly populated with effects return normalisd frames.
    memset(g_mainNoramliseBufferA, 0.0, frames * sizeof(jack_default_audio_sample_t));
    memset(g_mainNoramliseBufferB, 0.0, frames * sizeof(jack_default_audio_sample_t));
#else
    // Clear send buffers.
    for (uint8_t send = 0; send < MAX_CHANNELS; ++send) {
        if (g_fxSends[send]) {
            memset(g_fxSends[send]->bufferA, 0.0, frames * sizeof(jack_default_audio_sample_t));
            memset(g_fxSends[send]->bufferB, 0.0, frames * sizeof(jack_default_audio_sample_t));
        }
    }
#endif

    // Process each channel in reverse order (so that main mixbus is last)
    uint8_t chan = g_lastStrip;
    while (chan--) {
        struct channel_strip* strip = g_channelStrips[chan];
        if (strip == NULL)
            continue;

        // Only process connected inputs and mixbuses
        if (strip->inRouted) {
            // Calculate current (last set) balance
            if (strip->balance > 0.0)
                curLevelA = strip->level * (1 - strip->balance);
            else
                curLevelA = strip->level;
            if (strip->balance < 0.0)
                curLevelB = strip->level * (1 + strip->balance);
            else
                curLevelB = strip->level;

            // Calculate mute and target level and balance (that we will fade to over this cycle period to avoid abrupt change clicks)
            //!@todo Crossfade send levels
            if (strip->mute) {
                strip->level = 0; // We can set this here because we have the data and will iterate towards 0 over this frame
                reqLevelA             = 0.0;
                reqLevelB             = 0.0;
            } else {
                if (strip->reqbalance > 0.0)
                    reqLevelA = strip->reqlevel * (1 - strip->reqbalance);
                else
                    reqLevelA = strip->reqlevel;
                if (strip->reqbalance < 0.0)
                    reqLevelB = strip->reqlevel * (1 + strip->reqbalance);
                else
                    reqLevelB = strip->reqlevel;
                strip->level   = strip->reqlevel;
                strip->balance = strip->reqbalance;
            }

            // Calculate the step change for each leg to apply on each sample in buffer for fade between last and this period's level
            fDeltaA = (reqLevelA - curLevelA) / frames;
            fDeltaB = (reqLevelB - curLevelB) / frames;

            // **Apply processing to audio samples**
            pInA = jack_port_get_buffer(strip->inPortA, frames);
            pInB = jack_port_get_buffer(strip->inPortB, frames);

            if (strip->outRouted) {
                // Direct output so prepare output audio buffers
                pChanOutA = jack_port_get_buffer(strip->outPortA, frames);
                pChanOutB = jack_port_get_buffer(strip->outPortB, frames);
                memset(pChanOutA, 0.0, frames * sizeof(jack_default_audio_sample_t));
                memset(pChanOutB, 0.0, frames * sizeof(jack_default_audio_sample_t));
            } else {
                pChanOutA = pChanOutB = NULL;
            }
            // Iterate samples, scaling each and adding to output and set DPM if any samples louder than current DPM
            for (frame = 0; frame < frames; ++frame) {
#ifdef MIXBUS
                if (chan == 0) {
                    fSampleA = pInA[frame] + g_mainNoramliseBufferA[frame];
                    fSampleB = pInB[frame] + g_mainNoramliseBufferB[frame];
                } else {
                    fSampleA = pInA[frame];
                    fSampleB = pInB[frame];
                }
#else
                fSampleA = pInA[frame];
                fSampleB = pInB[frame];
#endif

                // Handle channel phase reverse
                if (strip->phase)
                    fSampleB = -fSampleB;

                // Decode M+S
                if (strip->ms) {
                    fSampleM = fSampleA + fSampleB;
                    fSampleB = fSampleA - fSampleB;
                    fSampleA = fSampleM;
                }

                // Handle mono
                if (strip->mono) {
                    fSampleA = (fSampleA + fSampleB) / 2.0;
                    fSampleB = fSampleA;
                }

                // Apply level adjustment
                fpreFaderSampleA = fSampleA;
                fpreFaderSampleB = fSampleB;
                fSampleA *= curLevelA;
                fSampleB *= curLevelB;

                // Check for error
                if (isinf(fSampleA))
                    fSampleA = 1.0;
                if (isinf(fSampleB))
                    fSampleB = 1.0;
                if (isinf(fpreFaderSampleA))
                    fpreFaderSampleA = 1.0;
                if (isinf(fpreFaderSampleB))
                    fpreFaderSampleB = 1.0;

                // Write sample to output buffer
                if (pChanOutA) {
                    pChanOutA[frame] += fSampleA;
                    pChanOutB[frame] += fSampleB;
                }
#ifdef MIXBUS
                // Add frames to main mixbus normalise buffer
                if (strip->normalise) {
                    g_mainNoramliseBufferA[frame] += fSampleA;
                    g_mainNoramliseBufferB[frame] += fSampleB;
                }
#else
                // Add fx send output frames only for input channels
                for (uint8_t send = 0; send < g_lastSend; ++send) {
                    if (g_fxSends[send]) {
                        if (strip->sendMode[send] == 0) {
                            g_fxSends[send]->bufferA[frame] += fSampleA * strip->send[send] * g_fxSends[send]->level;
                            g_fxSends[send]->bufferB[frame] += fSampleB * strip->send[send] * g_fxSends[send]->level;
                        } else if (strip->sendMode[send] == 1) {
                            g_fxSends[send]->bufferA[frame] += fpreFaderSampleA * strip->send[send] * g_fxSends[send]->level;
                            g_fxSends[send]->bufferB[frame] += fpreFaderSampleB * strip->send[send] * g_fxSends[send]->level;
                        }
                        if(isinf(g_fxSends[send]->bufferA[frame]))
                            g_fxSends[send]->bufferA[frame] = 1.0;
                        if(isinf(g_fxSends[send]->bufferB[frame]))
                            g_fxSends[send]->bufferB[frame] = 1.0;
                    }
                }
#endif
                curLevelA += fDeltaA;
                curLevelB += fDeltaB;

                // Process DPM
                if (strip->enable_dpm) {
                    fSampleA = fabs(fSampleA);
                    if (fSampleA > strip->dpmA)
                        strip->dpmA = fSampleA;
                    fSampleB = fabs(fSampleB);
                    if (fSampleB > strip->dpmB)
                        strip->dpmB = fSampleB;

                    // Update peak hold and scale DPM for damped release
                    if (strip->dpmA > strip->holdA)
                        strip->holdA = strip->dpmA;
                    if (strip->dpmB > strip->holdB)
                        strip->holdB = strip->dpmB;
                }
            }
            if (g_nHoldCount == 0) {
                // Only update peak hold each g_nHoldCount cycles
                strip->holdA = strip->dpmA;
                strip->holdB = strip->dpmB;
            }
            if (g_nDampingCount == 0) {
                // Only update damping release each g_nDampingCount cycles
                strip->dpmA *= g_fDpmDecay;
                strip->dpmB *= g_fDpmDecay;
            }
        } else if (strip->enable_dpm) {
            strip->dpmA  = -200.0;
            strip->dpmB  = -200.0;
            strip->holdA = -200.0;
            strip->holdB = -200.0;
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

    pthread_mutex_unlock(&mutex);
    return 0;
}

void onJackConnect(jack_port_id_t source, jack_port_id_t dest, int connect, void* args) {
    pthread_mutex_lock(&mutex);
    for (uint8_t chan = 0; chan < MAX_CHANNELS; chan++) {
        if (g_channelStrips[chan] == NULL)
            continue;
        if (jack_port_connected(g_channelStrips[chan]->inPortA) > 0 || (jack_port_connected(g_channelStrips[chan]->inPortB) > 0))
            g_channelStrips[chan]->inRouted = 1;
        else
            g_channelStrips[chan]->inRouted = 0;
        if (jack_port_connected(g_channelStrips[chan]->outPortA) > 0 || (jack_port_connected(g_channelStrips[chan]->outPortB) > 0))
            g_channelStrips[chan]->outRouted = 1;
        else
            g_channelStrips[chan]->outRouted = 0;
    }
    pthread_mutex_unlock(&mutex);
}

int onJackSamplerate(jack_nframes_t nSamplerate, void* arg) {
    if (nSamplerate == 0)
        return 0;
    g_samplerate     = nSamplerate;
    g_nDampingPeriod = g_fDpmDecay * nSamplerate / g_buffersize / 15;
    return 0;
}

int onJackBuffersize(jack_nframes_t nBuffersize, void* arg) {
    if (nBuffersize == 0)
        return 0;
    g_buffersize     = nBuffersize;
    g_nDampingPeriod = g_fDpmDecay * g_samplerate / g_buffersize / 15;
    pthread_mutex_lock(&mutex);
#ifdef MIXBUS
    free(g_mainNoramliseBufferA);
    free(g_mainNoramliseBufferB);
    g_mainNoramliseBufferA = malloc(sizeof(jack_nframes_t) * g_buffersize);
    g_mainNoramliseBufferB = malloc(sizeof(jack_nframes_t) * g_buffersize);
#else
    for (uint8_t chan = 0; chan < MAX_CHANNELS; ++chan) {
        if (g_fxSends[chan]) {
            g_fxSends[chan]->bufferA = jack_port_get_buffer(g_fxSends[chan]->outPortA, g_buffersize);
            g_fxSends[chan]->bufferB = jack_port_get_buffer(g_fxSends[chan]->outPortB, g_buffersize);
        }
    }
#endif
    pthread_mutex_unlock(&mutex);
    return 0;
}

int init() {
    for (uint8_t chan = 0; chan < MAX_CHANNELS; ++chan) {
        g_channelStrips[chan] = NULL;
#ifndef MIXBUS
        g_fxSends[chan] = NULL;
#endif
    }

    // Initialsize OSC
    g_oscfd = socket(AF_INET, SOCK_DGRAM, 0);
    for (uint8_t i = 0; i < MAX_OSC_CLIENTS; ++i) {
        memset(g_oscClient[i].sin_zero, '\0', sizeof g_oscClient[i].sin_zero);
        g_oscClient[i].sin_family      = AF_INET;
        g_oscClient[i].sin_port        = htons(1370);
        g_oscClient[i].sin_addr.s_addr = 0;
    }

    // Register with Jack server
    char* sServerName = NULL;
    jack_status_t nStatus;
    jack_options_t nOptions = JackNoStartServer;
    #ifdef MIXBUS
    const char* jackname = "zynmixer_bus";
    #else
    const char* jackname = "zynmixer_chan";
    #endif
    if ((g_jackClient = jack_client_open(jackname, nOptions, &nStatus, sServerName)) == 0) {
        fprintf(stderr, "libzynmixer: Failed to start channel jack client: %d\n", nStatus);
        exit(1);
    }
#ifdef DEBUG
    fprintf(stderr, "libzynmixer: Registering as '%s'.\n", jack_get_client_name(g_pJackClient));
#endif

#ifdef MIXBUS
    // Create main mixbus channel strip
    addStrip();
    g_mainNoramliseBufferA = malloc(sizeof(jack_nframes_t) * g_buffersize);
    g_mainNoramliseBufferB = malloc(sizeof(jack_nframes_t) * g_buffersize);
#endif

#ifdef DEBUG
    fprintf(stderr, "libzynmixer: Created channel strips\n");
#endif

    // Register the cleanup function to be called when library exits
    atexit(end);

    // Register the callbacks
    jack_set_process_callback(g_jackClient, onJackProcess, NULL);
    jack_set_port_connect_callback(g_jackClient, onJackConnect, NULL);
    jack_set_sample_rate_callback(g_jackClient, onJackSamplerate, NULL);
    jack_set_buffer_size_callback(g_jackClient, onJackBuffersize, NULL);


    if (jack_activate(g_jackClient)) {
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

#ifdef MIXBUS
    fprintf(stderr, "Started libzynmixer_bus\n");
#else
    fprintf(stderr, "Started libzynmixer_chan\n");
#endif
    return 1;
}

void end() {
    g_sendEvents = 0;
    void* status;
    pthread_join(g_eventThread, &status);

    //Soft mute output
    setLevel(0, 0.0);
    usleep(100000);

    // Close links with jack server
    if (g_jackClient) {
        jack_deactivate(g_jackClient);
        jack_client_close(g_jackClient);
    }

    // Release dynamically created resources
#ifdef MIXBUS
    free(g_mainNoramliseBufferA);
    free(g_mainNoramliseBufferB);
#endif
    for (uint8_t chan = 0; chan < MAX_CHANNELS; ++chan) {
        free(g_channelStrips[chan]);
#ifndef MIXBUS
        free(g_fxSends[chan]);
#endif
    }
    fprintf(stderr, "zynmixer ended\n");
}

void setLevel(uint8_t channel, float level) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return;
    g_channelStrips[channel]->reqlevel = level;
    sprintf(g_oscpath, "/mixer/channel/%d/fader", channel);
    sendOscFloat(g_oscpath, level);
}

float getLevel(uint8_t channel) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return 0.0f;
    return g_channelStrips[channel]->reqlevel;
}

void setBalance(uint8_t channel, float balance) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return;
    if (fabs(balance) > 1)
        return;
    g_channelStrips[channel]->reqbalance = balance;
    sprintf(g_oscpath, "/mixer/channel/%d/balance", channel);
    sendOscFloat(g_oscpath, balance);
}

float getBalance(uint8_t channel) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return 0.0f;
    return g_channelStrips[channel]->reqbalance;
}

void setMute(uint8_t channel, uint8_t mute) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return;
    g_channelStrips[channel]->mute = mute;
    sprintf(g_oscpath, "/mixer/channel/%d/mute", channel);
    sendOscInt(g_oscpath, mute);
}

uint8_t getMute(uint8_t channel) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return 0;
    return g_channelStrips[channel]->mute;
}

void toggleMute(uint8_t channel) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return;
    uint8_t mute;
    mute = g_channelStrips[channel]->mute;
    if (mute)
        setMute(channel, 0);
    else
        setMute(channel, 1);
}

void setPhase(uint8_t channel, uint8_t phase) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return;
    g_channelStrips[channel]->phase = phase;
    sprintf(g_oscpath, "/mixer/channel/%d/phase", channel);
    sendOscInt(g_oscpath, phase);
}

uint8_t getPhase(uint8_t channel) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return 0;
    return g_channelStrips[channel]->phase;
}

void setSendMode(uint8_t channel, uint8_t send, uint8_t mode) {
    if (channel >= MAX_CHANNELS || send >= MAX_CHANNELS || g_channelStrips[channel] == NULL || mode > 1)
        return;
    g_channelStrips[channel]->sendMode[send] = mode;
    sprintf(g_oscpath, "/mixer/channel/%d/sendmode_%d", channel, send);
    sendOscInt(g_oscpath, mode);
}

uint8_t getSendMode(uint8_t channel, uint8_t send) {
    if (channel >= MAX_CHANNELS || send >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return 0;
    return g_channelStrips[channel]->sendMode[send];
}

void togglePhase(uint8_t channel) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return;
    if (g_channelStrips[channel]->phase)
        g_channelStrips[channel]->phase = 0;
    else
        g_channelStrips[channel]->phase = 1;
}

void setSend(uint8_t channel, uint8_t send, float level) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL || send >= MAX_CHANNELS)
        return;
    g_channelStrips[channel]->send[send] = level;
    sprintf(g_oscpath, "/mixer/channel/%d/send_%d", channel, send);
    sendOscFloat(g_oscpath, level);
}

float getSend(uint8_t channel, uint8_t send) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL || send >= MAX_CHANNELS)
        return 0.0f;
    return g_channelStrips[channel]->send[send];
}

void setNormalise(uint8_t channel, uint8_t enable) {
#ifndef MIXBUS
    fprintf(stderr, "Normalisation not implemented in channel strips\n");
    return;
#endif
    if (channel == 0 || channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return;
    g_channelStrips[channel]->normalise = enable;
    sprintf(g_oscpath, "/mixer/channel/%d/normalise", channel);
    sendOscInt(g_oscpath, enable);
}

uint8_t getNormalise(uint8_t channel) {
#ifndef MIXBUS
    fprintf(stderr, "Normalisation not implemented in channel strips\n");
    return 0;
#endif
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return 0;
    return g_channelStrips[channel]->normalise;
}

void setMono(uint8_t channel, uint8_t mono) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return;
    g_channelStrips[channel]->mono = (mono != 0);
    sprintf(g_oscpath, "/mixer/channel/%d/mono", channel);
    sendOscInt(g_oscpath, mono);
}

uint8_t getMono(uint8_t channel) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return 0;
    return g_channelStrips[channel]->mono;
}

void toggleMono(uint8_t channel) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return;
    if (g_channelStrips[channel]->mono)
        g_channelStrips[channel]->mono = 0;
    else
        g_channelStrips[channel]->mono = 1;
}

void setMS(uint8_t channel, uint8_t enable) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return;
    g_channelStrips[channel]->ms = enable != 0;
    sprintf(g_oscpath, "/mixer/channel/%d/ms", channel);
    sendOscInt(g_oscpath, enable);
}

uint8_t getMS(uint8_t channel) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return 0;
    return g_channelStrips[channel]->ms;
}

void toggleMS(uint8_t channel) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return;
    if (g_channelStrips[channel]->ms)
        g_channelStrips[channel]->ms = 0;
    else
        g_channelStrips[channel]->ms = 1;
}

void reset(uint8_t channel) {
    setLevel(channel, 0.8);
    setBalance(channel, 0.0);
    setMute(channel, 0);
    setMono(channel, 0);
    setPhase(channel, 0);
    for (uint8_t send = 0; send < MAX_CHANNELS; ++send) {
        setSend(channel, send, 0.0);
        setSendMode(channel, send, 0);
    }
}

float getDpm(uint8_t channel, uint8_t leg) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return 0.0f;
    if (leg)
        return convertToDBFS(g_channelStrips[channel]->dpmB);
    return convertToDBFS(g_channelStrips[channel]->dpmA);
}

float getDpmHold(uint8_t channel, uint8_t leg) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return 0.0f;
    if (leg)
        return convertToDBFS(g_channelStrips[channel]->holdB);
    return convertToDBFS(g_channelStrips[channel]->holdA);
}

void getDpmStates(uint8_t start, uint8_t end, float* values) {
    if (start > end) {
        uint8_t tmp = start;
        start       = end;
        end         = tmp;
    }
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
    struct channel_strip* pChannel;
    if (start > end) {
        uint8_t tmp = start;
        start       = end;
        end         = tmp;
    }
    if (start >= MAX_CHANNELS)
        start = MAX_CHANNELS - 1;
    if (end >= MAX_CHANNELS)
        end = MAX_CHANNELS - 1;
    for (uint8_t chan = start; chan <= end; ++chan) {
        if (g_channelStrips[chan] == NULL)
            continue;
        g_channelStrips[chan]->enable_dpm = enable;
        if (g_channelStrips[chan] == 0) {
            g_channelStrips[chan]->dpmA  = 0;
            g_channelStrips[chan]->dpmB  = 0;
            g_channelStrips[chan]->holdA = 0;
            g_channelStrips[chan]->holdB = 0;
        }
    }
}

int8_t addStrip() {
    uint8_t chan;
    for (chan = 0; chan < MAX_CHANNELS; ++chan) {
        if (g_channelStrips[chan])
            continue;
        struct channel_strip* strip = malloc(sizeof(struct channel_strip));
        if (strip == NULL) {
            fprintf(stderr, "Failed to allocate memory for ne channel strip.\n");
            return -1;
        }
        char name[11];
        sprintf(name, "input_%02da", chan);

        if (!(strip->inPortA = jack_port_register(g_jackClient, name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0))) {
            fprintf(stderr, "libzynmixer: Cannot register %s\n", name);
            free(strip);
            return -1;
        }
        sprintf(name, "input_%02db", chan);
        if (!(strip->inPortB = jack_port_register(g_jackClient, name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0))) {
            fprintf(stderr, "libzynmixer: Cannot register %s\n", name);
            jack_port_unregister(g_jackClient, strip->inPortA);
            free(strip);
            return -1;
        }
        sprintf(name, "output_%02da", chan);
        if (!(strip->outPortA = jack_port_register(g_jackClient, name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0))) {
            fprintf(stderr, "libzynmixer: Cannot register %s\n", name);
            jack_port_unregister(g_jackClient, strip->inPortA);
            jack_port_unregister(g_jackClient, strip->inPortB);
            free(strip);
            return -1;
        }
        sprintf(name, "output_%02db", chan);
        if (!(strip->outPortB = jack_port_register(g_jackClient, name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0))) {
            fprintf(stderr, "libzynmixer: Cannot register %s\n", name);
            jack_port_unregister(g_jackClient, strip->inPortA);
            jack_port_unregister(g_jackClient, strip->inPortB);
            jack_port_unregister(g_jackClient, strip->outPortA);
            free(strip);
            return -1;
        }
        strip->level      = 0.0;
        strip->reqlevel   = 0.8;
        strip->balance    = 0.0;
        strip->reqbalance = 0.0;
        strip->mute       = 0;
        strip->mono       = 0;
        strip->ms         = 0;
        strip->phase      = 0;
        strip->normalise  = 0;
        strip->inRouted   = 0;
        strip->outRouted  = 0;
        strip->enable_dpm = 0;
        for (uint8_t send = 0; send < MAX_CHANNELS; ++send) {
            strip->send[send] = 0.0;
            strip->sendMode[send] = 0;
        }
        strip->dpmA = strip->holdA = 0.0;
        strip->dpmB = strip->holdB = 0.0;
        strip->dpmAlast  = 100.0;
        strip->dpmBlast  = 100.0;
        strip->holdAlast = 100.0;
        strip->holdBlast = 100.0;
        pthread_mutex_lock(&mutex);
        g_channelStrips[chan] = strip;
        pthread_mutex_unlock(&mutex);

        if (chan >= g_lastStrip)
            g_lastStrip = chan + 1;
        return chan;
    }
    return -1;
}

int8_t removeStrip(uint8_t chan) {
#ifdef MIXBUS
    if (chan == 0) {
        fprintf(stderr, "Cannot remove main mixbus\n");
        return -1;
    }
#endif
    if (chan >= MAX_CHANNELS || g_channelStrips[chan] == NULL)
        return -1;
    struct channel_strip* pstrip = g_channelStrips[chan];
    pthread_mutex_lock(&mutex);
    g_channelStrips[chan] = NULL;
    pthread_mutex_unlock(&mutex);
    jack_port_unregister(g_jackClient, pstrip->inPortA);
    jack_port_unregister(g_jackClient, pstrip->inPortB);
    jack_port_unregister(g_jackClient, pstrip->outPortA);
    jack_port_unregister(g_jackClient, pstrip->outPortB);
    free(pstrip);
    for (uint8_t g_lastStrip = MAX_CHANNELS - 1; g_lastStrip > 0; --g_lastStrip) {
        if (g_channelStrips[g_lastStrip])
            break;
    }
    return chan;
}

int8_t addSend() {
#ifdef MIXBUS
    fprintf(stderr, "Effects sends not implemented in mixbus\n");
#else
    for (uint8_t send = 0; send < MAX_CHANNELS; ++send) {
        if (g_fxSends[send] == NULL) {
            struct fx_send* psend = malloc(sizeof(struct fx_send));
            if (!psend) {
                fprintf(stderr, "Failed to allocated memory for effect send %d\n", send);
                return -1;
            }
            char name[11];
            sprintf(name, "send_%02da", send + 1);
            if (!(psend->outPortA = jack_port_register(g_jackClient, name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0))) {
                free(psend);
                psend = NULL;
                fprintf(stderr, "libzynmixer: Cannot register %s\n", name);
                return -1;
            }
            sprintf(name, "send_%02db", send + 1);
            if (!(psend->outPortB = jack_port_register(g_jackClient, name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0))) {
                jack_port_unregister(g_jackClient, psend->outPortA);
                free(psend);
                fprintf(stderr, "libzynmixer: Cannot register %s\n", name);
                return -1;
            }
            psend->bufferA = jack_port_get_buffer(psend->outPortA, g_buffersize);
            psend->bufferB = jack_port_get_buffer(psend->outPortB, g_buffersize);
            psend->level = 1.0;
            pthread_mutex_lock(&mutex);
            g_fxSends[send] = psend;
            ++g_sendCount;
            pthread_mutex_unlock(&mutex);
            if (send >= g_lastSend)
                g_lastSend = send + 1;
            return send + 1;
        }
    }
    fprintf(stderr, "Exceeded maximum quantity of sends (%d).\n", MAX_CHANNELS);
#endif
    return -1;
}

uint8_t removeSend(uint8_t send) {
#ifdef MIXBUS
    fprintf(stderr, "Effects sends not implemented in mixbus\n");
    return 1;
#else
    --send; // We expose sends at 1-based so need to decrement to access array
    if (send >= MAX_CHANNELS || g_fxSends[send] == NULL)
        return 1;
    struct fx_send* pstrip = g_fxSends[send];
    pthread_mutex_lock(&mutex);
    g_fxSends[send] = NULL;
    --g_sendCount;
    pthread_mutex_unlock(&mutex);
    jack_port_unregister(g_jackClient, pstrip->outPortA);
    jack_port_unregister(g_jackClient, pstrip->outPortB);
    free(pstrip);
    for (g_lastSend = MAX_CHANNELS - 1; g_lastSend > 0; --g_lastSend) {
        if (g_fxSends[g_lastSend])
            break;
    }
    return 0;
#endif
}


uint8_t getSendCount() {
    return g_sendCount;
}

uint8_t getMaxChannels() { return MAX_CHANNELS; }

int addOscClient(const char* client) {
    for (uint8_t i = 0; i < MAX_OSC_CLIENTS; ++i) {
        if (g_oscClient[i].sin_addr.s_addr != 0)
            continue;
        if (inet_pton(AF_INET, client, &(g_oscClient[i].sin_addr)) != 1) {
            g_oscClient[i].sin_addr.s_addr = 0;
            fprintf(stderr, "libzynmixer: Failed to register client %s\n", client);
            return -1;
        }
        fprintf(stderr, "libzynmixer: Added OSC client %d: %s\n", i, client);
        for (int chan = 0; chan < MAX_CHANNELS; ++chan) {
            setBalance(chan, getBalance(chan));
            setLevel(chan, getLevel(chan));
            setMono(chan, getMono(chan));
            setMute(chan, getMute(chan));
            setPhase(chan, getPhase(chan));
#ifndef MIXBUS
            for (uint8_t send = 0; send < MAX_CHANNELS; ++send) {
                if (g_fxSends[send]) {
                    setSend(chan, send, getSend(chan, send));
                    setSendMode(chan, send, getSendMode(chan, send));
                }
            }
#endif
            g_channelStrips[chan]->dpmAlast  = 100.0;
            g_channelStrips[chan]->dpmBlast  = 100.0;
            g_channelStrips[chan]->holdAlast = 100.0;
            g_channelStrips[chan]->holdBlast = 100.0;
        }
        g_bOsc = 1;
        return i;
    }
    fprintf(stderr, "libzynmixer: Not adding OSC client %s - Maximum client count reached [%d]\n", client, MAX_OSC_CLIENTS);
    return -1;
}

void removeOscClient(const char* client) {
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
