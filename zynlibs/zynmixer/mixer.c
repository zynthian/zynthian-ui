/*
 * ******************************************************************
 * ZYNTHIAN PROJECT: Audio Mixer Library
 *
 * Library providing stereo audio summing mixer
 *
 * Copyright (C) 2019-2026 Brian Walton <brian@riban.co.uk>
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
#include <stdatomic.h> // provides atomic (thread safe) access to variables

#include "mixer.h"

// #define DEBUG

#ifndef MAX_CHANNELS
#define MAX_CHANNELS 99
#endif

pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
pthread_t g_eventThread;   // ID of low priority event thread
int g_nRunning = 1;        // Set to 0 to exit event thread
uint8_t g_sendCount = 0;   // Quantity of effect sends
uint8_t g_lastStrip = 1;   // Highest index of any strips (one-based)
uint8_t g_lastSend  = 1;   // Highest index of any send (one-based)
uint8_t g_solo      = 0;   // Quantity of channels with solo asserted
uint8_t g_pfl       = 0;   // Quantity of channels with PFL asserted
#ifndef MIXBUS
double g_xfader      = 0.0; // Global crossfader phase / angle value for AB mixing
float g_xf_gain_A    = 0.0; // Crossfade A gain
float g_reqxf_gain_A = 1.0; // Requested crossfade A gain
float g_xf_gain_B    = 1.0; // Crossfade B gain
float g_reqxf_gain_B = 0.0; // Requested crossfade B gain
#else
jack_port_t* g_pflInPortA;  // Pointer to PFL trunk port A
jack_port_t* g_pflInPortB;  // Pointer to PFL trunk port B
float g_pflLevel     = 1.0; // PFL volumne level
#endif
jack_port_t* g_soloPortA;  // Pointer to solo trunk port A
jack_port_t* g_soloPortB;  // Pointer to solo trunk port B
jack_port_t* g_pflOutPortA;// Pointer to PFL output port A
jack_port_t* g_pflOutPortB;// Pointer to PFL output port B

_Atomic jack_nframes_t g_nCleanFrame = 0; // frames since jack epockh to trigger channel cleanup (0 for none)
_Atomic jack_nframes_t g_nNextFrame = 0; // Frames since jack epoch

// Structure describing a channel strip
struct channel_strip {
    jack_port_t* inPortA;  // Jack input port A
    jack_port_t* inPortB;  // Jack input port B
    jack_port_t* outPortA; // Jack output port A
    jack_port_t* outPortB; // Jack output port B
    _Atomic float gain;            // Current gain 0..10
    _Atomic float level;           // Current fader level 0..1
    _Atomic float reqlevel;        // Requested fader level 0..1
    _Atomic float balance;         // Current balance -1..+1
    _Atomic float reqbalance;      // Requested balance -1..+1
    _Atomic float send[MAX_CHANNELS]; // Current fx send levels
    _Atomic float dpmA;            // Current peak programme A-leg
    _Atomic float dpmB;            // Current peak programme B-leg
    _Atomic float holdA;           // Current peak hold level A-leg
    _Atomic float holdB;           // Current peak hold level B-leg
    _Atomic float dpmAlast;        // Last peak programme A-leg
    _Atomic float dpmBlast;        // Last peak programme B-leg
    _Atomic float holdAlast;       // Last peak hold level A-leg
    _Atomic float holdBlast;       // Last peak hold level B-leg
    _Atomic uint8_t mute;          // 1 if muted
    _Atomic uint8_t mono;          // 1 if mono
    _Atomic uint8_t solo;          // 1 if solo
    _Atomic uint8_t ms;            // 1 if MS decoding
    _Atomic uint8_t phase;         // 1 if channel B phase reversed
    _Atomic uint8_t pfl;           // 1 if PFL
#ifndef MIXBUS
    _Atomic uint8_t ABMixGroup;    // AB mix-group: 0 => None, 1 => A, 2 => B
#endif
    _Atomic uint8_t sendMode[MAX_CHANNELS]; // 0: post-fader send, 1: pre-fader send
    _Atomic uint8_t normalise;     // 1 if channel normalised to main output
    _Atomic uint8_t inRouted;      // 1 if source routed to channel
    _Atomic uint8_t outRouted;     // 1 if output routed
    _Atomic uint8_t enable_dpm;    // 1 to enable calculation of peak meter
};

struct fx_send {
    jack_port_t* outPortA; // Jack output port A
    jack_port_t* outPortB; // Jack output port B
    jack_default_audio_sample_t* bufferA; // Holds audio samples
    jack_default_audio_sample_t* bufferB; // Holds audio samples
    _Atomic float level;           // Current fader level 0..1
};

jack_client_t* g_jackClient;
_Atomic(struct channel_strip*) g_channelStrips[MAX_CHANNELS];
_Atomic(struct channel_strip*) g_channelStripsRemoved[MAX_CHANNELS]; // Pointers to removed channel strips
#ifndef MIXBUS
_Atomic(struct fx_send*) g_fxSends[MAX_CHANNELS];
_Atomic(struct fx_send*) g_fxSendsRemoved[MAX_CHANNELS]; // Pointers to removed sends
#endif
_Atomic unsigned int g_nDampingCount  = 0;
_Atomic unsigned int g_nDampingPeriod = 10; // Quantity of cycles between applying DPM damping decay
_Atomic unsigned int g_nHoldCount     = 0;
_Atomic float g_fDpmDecay             = 0.9;             // Factor to scale for DPM decay - defines resolution of DPM decay
jack_nframes_t g_samplerate                     = 48000; // Jack samplerate used to calculate damping factor
jack_nframes_t g_buffersize                     = 1024;  // Jack buffer size used to calculate damping factor
jack_default_audio_sample_t* g_soloBufferA    = NULL;  // Ponter to buffer used for solo bus
jack_default_audio_sample_t* g_soloBufferB    = NULL;  // Ponter to buffer used for solo bus
jack_default_audio_sample_t* g_pflBufferA    = NULL;  // Ponter to buffer used for PFL bus
jack_default_audio_sample_t* g_pflBufferB    = NULL;  // Ponter to buffer used for PFL bus
#ifdef MIXBUS
jack_default_audio_sample_t* g_mainNormaliseBufferA    = NULL;  // Ponter to main output normalised buffer used for normalising effects sends to main mixbus
jack_default_audio_sample_t* g_mainNormaliseBufferB    = NULL;  // Ponter to main output normalised buffer used for normalising effects sends to main mixbus
#endif

static float convertToDBFS(float raw) {
    if (raw <= 0)
        return -200;
    float fValue = 20 * log10f(raw);

    if (fValue < -200)
        fValue = -200;
    return fValue;
}

void _doRemoveStrip(uint8_t chan) {
    struct channel_strip* pstrip = g_channelStripsRemoved[chan];
    jack_port_unregister(g_jackClient, pstrip->inPortA);
    jack_port_unregister(g_jackClient, pstrip->inPortB);
    jack_port_unregister(g_jackClient, pstrip->outPortA);
    jack_port_unregister(g_jackClient, pstrip->outPortB);
    free(pstrip);
    g_channelStripsRemoved[chan] = NULL;
}

#ifndef MIXBUS
void _doRemoveSend(uint8_t send) {
    struct fx_send* pstrip = g_fxSendsRemoved[send];
    jack_port_unregister(g_jackClient, pstrip->outPortA);
    jack_port_unregister(g_jackClient, pstrip->outPortB);
    free(pstrip);
    g_channelStripsRemoved[send] = NULL;
}
#endif

void* eventThreadFn(void* param) {
    while (g_nRunning) {
        if (g_nCleanFrame && g_nNextFrame > g_nCleanFrame) {
            pthread_mutex_lock(&mutex);
            for (uint8_t chan = 0; chan < MAX_CHANNELS; chan++) {
                if (g_channelStripsRemoved[chan])
                    _doRemoveStrip(chan);
#ifndef MIXBUS
                if (g_fxSendsRemoved[chan])
                    _doRemoveSend(chan);
#endif
            }
            pthread_mutex_unlock(&mutex);
            g_nCleanFrame = 0;
        }
        usleep(10000);
    }
}

static int onJackProcess(jack_nframes_t frames, void* args) {
    jack_default_audio_sample_t *pPflInA, *pPflInB, *pPflOutA, *pPflOutB, *pSoloA, *pSoloB, *pInA, *pInB, *pChanOutA, *pChanOutB;
    unsigned int frame;
    float curLevelA, curLevelB, reqLevelA, reqLevelB, fDeltaA, fDeltaB, fSampleA, fSampleB, fSampleM, fpreFaderSampleA, fpreFaderSampleB;

/*  Solo / PFL
    The chain mixer has a pair of buffers (A/B) that are cleared at start of period, then populated with samples of any inputs that are solo.
    These buffers are pushed to its solo ouptut ports.
    The mixbus mixer has a pair of buffers (A/B) that are populated from its solo input ports, then summed with samples of any inputs that are solo. (Avoid chan 0.)
    These buffers are pushed to the solo monitor outputs (default is main outputs).
    PFL is treated similarly
*/

    if (g_solo) {
        pSoloA = jack_port_get_buffer(g_soloPortA, frames);
        pSoloB = jack_port_get_buffer(g_soloPortB, frames);
    }
    pPflOutA = jack_port_get_buffer(g_pflOutPortA, frames);
    pPflOutB = jack_port_get_buffer(g_pflOutPortB, frames);

#ifdef MIXBUS
    // Clear the mixbus output buffers to allow them to be directly populated with effects return normalisd frames.
    memset(g_mainNormaliseBufferA, 0.0, frames * sizeof(jack_default_audio_sample_t));
    memset(g_mainNormaliseBufferB, 0.0, frames * sizeof(jack_default_audio_sample_t));
    // Populate solo buffers from trunk
    if (g_solo) {
        memcpy(g_soloBufferA, pSoloA, frames * sizeof(jack_default_audio_sample_t));
        memcpy(g_soloBufferB, pSoloB, frames * sizeof(jack_default_audio_sample_t));
    }

    // Populate PFL output buffers from trunk
    pPflInA = jack_port_get_buffer(g_pflInPortA, frames);
    pPflInB = jack_port_get_buffer(g_pflInPortB, frames);
    memcpy(pPflOutA, pPflInA, frames * sizeof(jack_default_audio_sample_t));
    memcpy(pPflOutB, pPflInB, frames * sizeof(jack_default_audio_sample_t));

#else
    // Clear solo send buffers
    if (g_solo) {
        memset(pSoloA, 0.0, frames * sizeof(jack_default_audio_sample_t));
        memset(pSoloB, 0.0, frames * sizeof(jack_default_audio_sample_t));
        g_soloBufferA = pSoloA; // We will populate the trunk directly
        g_soloBufferB = pSoloB;
    }
    // Clear PFL buffers
    memset(pPflOutA, 0.0, frames * sizeof(jack_default_audio_sample_t));
    memset(pPflOutB, 0.0, frames * sizeof(jack_default_audio_sample_t));
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
        struct channel_strip *strip = atomic_load_explicit(&g_channelStrips[chan], memory_order_acquire);
        if (strip == NULL)
            continue;

        // Only process connected inputs and mixbuses
        if (strip->inRouted
#ifdef MIXBUS
            || chan == 0
#endif
        ) {
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
 
 #ifndef MIXBUS
                // AB mixing (Cross-Fader)
                if (strip->ABMixGroup == 1) {
                    reqLevelA *= g_reqxf_gain_A;
                    reqLevelB *= g_reqxf_gain_A;
                    curLevelA *= g_xf_gain_A;
                    curLevelB *= g_xf_gain_A;
                }
                else if (strip->ABMixGroup == 2) {
                    reqLevelA *= g_reqxf_gain_B;
                    reqLevelB *= g_reqxf_gain_B;
                    curLevelA *= g_xf_gain_B;
                    curLevelB *= g_xf_gain_B;
                }
#endif

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
                    if (g_solo) {
                        fSampleA = g_soloBufferA[frame];
                        fSampleB = g_soloBufferB[frame];
                    } else {
                        fSampleA = pInA[frame] + g_mainNormaliseBufferA[frame];
                        fSampleB = pInB[frame] + g_mainNormaliseBufferB[frame];
                    }
                } else {
                    fSampleA = pInA[frame];
                    fSampleB = pInB[frame];
                }
#else
                fSampleA = pInA[frame];
                fSampleB = pInB[frame];
#endif
                // Handle gain
                fSampleA *= strip->gain;
                fSampleB *= strip->gain;

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
                if (strip->solo) {
                    g_soloBufferA[frame] += fSampleA;
                    g_soloBufferB[frame] += fSampleB;
                }
                if (strip->pfl) {
                    pPflOutA[frame] += fpreFaderSampleA;
                    pPflOutB[frame] += fpreFaderSampleB;
                }
#ifdef MIXBUS
                // Add frames to main mixbus normalise buffer
                if (strip->normalise) {
                    g_mainNormaliseBufferA[frame] += fSampleA;
                    g_mainNormaliseBufferB[frame] += fSampleB;
                }
                // Set PFL output level
                if (chan == 0) {
                    pPflOutA[frame] *= g_pflLevel;
                    pPflOutB[frame] *= g_pflLevel;
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
                strip->dpmA = g_fDpmDecay * strip->dpmA;
                strip->dpmB = g_fDpmDecay * strip->dpmB;
            }
        } else {
            if (strip->enable_dpm) {
                strip->dpmA  = 0.0f;
                strip->dpmB  = 0.0f;
                strip->holdA = 0.0f;
                strip->holdB = 0.0f;
            }
            if (strip->outRouted) {
                // Silence channel outputs
                pChanOutA = jack_port_get_buffer(strip->outPortA, frames);
                pChanOutB = jack_port_get_buffer(strip->outPortB, frames);
                memset(pChanOutA, 0.0, frames * sizeof(jack_default_audio_sample_t));
                memset(pChanOutB, 0.0, frames * sizeof(jack_default_audio_sample_t));
            }
        }
    }

#ifndef MIXBUS
    g_xf_gain_A = g_reqxf_gain_A;
    g_xf_gain_B = g_reqxf_gain_B;
#endif

    if (g_nDampingCount == 0)
        g_nDampingCount = g_nDampingPeriod;
    else
        --g_nDampingCount;
    if (g_nHoldCount == 0)
        g_nHoldCount = g_nDampingPeriod * 20;
    else
        --g_nHoldCount;

    ++g_nNextFrame;
    return 0;
}

void print_dpm_info(uint8_t chan) {
    // Debug helper to print current DPM state
    struct channel_strip *strip = atomic_load_explicit(&g_channelStrips[chan], memory_order_acquire);
    if (strip)
        fprintf(stderr, "A: %f\nB: %f\nHold A: %f\nHold B: %f\n%s\nHold count: %u\nDamping period: %u\n",
            strip->dpmA,
            strip->dpmB,
            strip->holdA,
            strip->holdB,
            strip->enable_dpm?"Enabled":"Disabled",
            g_nHoldCount,
            g_nDampingPeriod
        );
}

void onJackConnect(jack_port_id_t source, jack_port_id_t dest, int connect, void* args) {
    for (uint8_t chan = 0; chan < MAX_CHANNELS; chan++) {
        struct channel_strip *strip = atomic_load_explicit(&g_channelStrips[chan], memory_order_acquire);
        if (strip == NULL)
            continue;
        if (jack_port_connected(strip->inPortA) > 0 || (jack_port_connected(strip->inPortB) > 0))
            strip->inRouted = 1;
        else
            strip->inRouted = 0;
        if (jack_port_connected(strip->outPortA) > 0 || (jack_port_connected(strip->outPortB) > 0))
            strip->outRouted = 1;
        else
            strip->outRouted = 0;
    }
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
    free(g_soloBufferA);
    free(g_soloBufferB);
    g_soloBufferA = malloc(sizeof(jack_nframes_t) * g_buffersize);
    g_soloBufferB = malloc(sizeof(jack_nframes_t) * g_buffersize);
#ifdef MIXBUS
    free(g_mainNormaliseBufferA);
    free(g_mainNormaliseBufferB);
    g_mainNormaliseBufferA = malloc(sizeof(jack_nframes_t) * g_buffersize);
    g_mainNormaliseBufferB = malloc(sizeof(jack_nframes_t) * g_buffersize);
#else
    for (uint8_t chan = 0; chan < MAX_CHANNELS; ++chan) {
        if (g_fxSends[chan]) {
            //!@todo Do not cache jack_port_get_buffer
            g_fxSends[chan]->bufferA = jack_port_get_buffer(g_fxSends[chan]->outPortA, g_buffersize);
            g_fxSends[chan]->bufferB = jack_port_get_buffer(g_fxSends[chan]->outPortB, g_buffersize);
        }
    }
#endif
    return 0;
}

int init() {
    for (uint8_t chan = 0; chan < MAX_CHANNELS; ++chan) {
        g_channelStrips[chan] = NULL;
        g_channelStripsRemoved[chan] = NULL;
#ifndef MIXBUS
        g_fxSends[chan] = NULL;
        g_fxSendsRemoved[chan] = NULL;
#endif
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

    int ports_ok = 0;
   // Solo ports
#ifdef MIXBUS
    unsigned long solo_port_flags = JackPortIsInput;
#else
    unsigned long solo_port_flags = JackPortIsOutput;
#endif
    ports_ok |= !(g_soloPortA = jack_port_register(g_jackClient, "solo_a", JACK_DEFAULT_AUDIO_TYPE, solo_port_flags, 0));
    ports_ok |= !(g_soloPortB = jack_port_register(g_jackClient, "solo_b", JACK_DEFAULT_AUDIO_TYPE, solo_port_flags, 0));
    g_soloBufferA = malloc(sizeof(jack_nframes_t) * g_buffersize);
    g_soloBufferB = malloc(sizeof(jack_nframes_t) * g_buffersize);

    ports_ok |= !(g_pflOutPortA = jack_port_register(g_jackClient, "pfl_out_a", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0));
    ports_ok |= !(g_pflOutPortB = jack_port_register(g_jackClient, "pfl_out_b", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0));

#ifdef MIXBUS
    // PFL ports
    ports_ok |= !(g_pflInPortA = jack_port_register(g_jackClient, "pfl_in_a", JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0));
    ports_ok |= !(g_pflInPortB = jack_port_register(g_jackClient, "pfl_in_b", JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0));
#endif

    // Check all ports have been created
    if (ports_ok) {
        if(g_soloPortA)
            jack_port_unregister(g_jackClient, g_soloPortA);
        else
            fprintf(stderr, "libzynmixer: Cannot register %s\n", "solo_a");
        if(g_soloPortB)
            jack_port_unregister(g_jackClient, g_soloPortB);
        else
            fprintf(stderr, "libzynmixer: Cannot register %s\n", "solo_b");
        if(g_pflOutPortA)
            jack_port_unregister(g_jackClient, g_pflOutPortA);
        else
            fprintf(stderr, "libzynmixer: Cannot register %s\n", "pfl_out_a");
        if(g_pflOutPortB)
            jack_port_unregister(g_jackClient, g_pflOutPortB);
        else
            fprintf(stderr, "libzynmixer: Cannot register %s\n", "pfl_out_b");
#ifdef MIXBUS
        if(g_pflInPortA)
            jack_port_unregister(g_jackClient, g_pflInPortA);
        else
            fprintf(stderr, "libzynmixer: Cannot register %s\n", "pfl_in_a");
        if(g_pflInPortB)
            jack_port_unregister(g_jackClient, g_pflInPortB);
        else
            fprintf(stderr, "libzynmixer: Cannot register %s\n", "pfl_in_b");
#endif
        return -1;
    }

    #ifdef MIXBUS
    int8_t id = addStrip(); // Main mixbus
    id = addStrip(); // Aux mixbus
    setLevel(id, 1.0); // Default unity gain for aux bus
    setNormalise(id, 1);
    g_mainNormaliseBufferA = malloc(sizeof(jack_nframes_t) * g_buffersize);
    g_mainNormaliseBufferB = malloc(sizeof(jack_nframes_t) * g_buffersize);
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

    fprintf(stderr, "Started %s\n", jackname);
    return 1;
}

void end() {
    g_nRunning = 0;
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
    free(g_soloBufferA);
    free(g_soloBufferB);
#ifdef MIXBUS
    free(g_mainNormaliseBufferA);
    free(g_mainNormaliseBufferB);
#endif
    for (uint8_t chan = 0; chan < MAX_CHANNELS; ++chan) {
        free(g_channelStrips[chan]);
        free(g_channelStripsRemoved[chan]);
#ifndef MIXBUS
        free(g_fxSends[chan]);
        free(g_fxSendsRemoved[chan]);
#endif
    }
    fprintf(stderr, "zynmixer ended\n");
}

void setGain(uint8_t channel, float gain) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL || gain < 0.0f)
        return;
    g_channelStrips[channel]->gain = gain;
}

float getGain(uint8_t channel) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return 0.0f;
    return g_channelStrips[channel]->gain;
}

void setLevel(uint8_t channel, float level) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return;
    g_channelStrips[channel]->reqlevel = level;
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

void setSolo(uint8_t channel, uint8_t solo) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return;
    solo = solo?1:0;
    if (g_channelStrips[channel]->solo == solo)
        return;
    g_channelStrips[channel]->solo = solo;
    if (solo)
        ++g_solo;
    else
        --g_solo;
}

uint8_t getSolo(uint8_t channel) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return 0;
    return g_channelStrips[channel]->solo;
}

void toggleSolo(uint8_t channel) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return;
    uint8_t solo;
    solo = g_channelStrips[channel]->mute;
    if (solo)
        setSolo(channel, 0);
    else
        setSolo(channel, 1);
}

void clearSolo() {
    for (uint8_t channel = 0; channel < MAX_CHANNELS; ++channel) {
        if (g_channelStrips[channel])
            g_channelStrips[channel]->solo = 0;
    }
    g_solo = 0;
}

uint8_t getGlobalSolo() {
    return g_solo;
}

void setPfl(uint8_t channel, uint8_t pfl) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return;
    pfl = pfl?1:0;
    if (g_channelStrips[channel]->pfl == pfl)
        return;
    g_channelStrips[channel]->pfl = pfl;
    if (pfl)
        ++g_pfl;
    else
        --g_pfl;
}

uint8_t getPfl(uint8_t channel) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return 0;
    return g_channelStrips[channel]->pfl;
}

void togglePFL(uint8_t channel) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return;
    uint8_t pfl;
    pfl = g_channelStrips[channel]->mute;
    if (pfl)
        setPfl(channel, 0);
    else
        setPfl(channel, 1);
}

void clearPfl() {
    for (uint8_t channel = 0; channel < MAX_CHANNELS; ++channel) {
        if (g_channelStrips[channel])
            g_channelStrips[channel]->pfl = 0;
    }
    g_pfl = 0;
}

uint8_t getGlobalPfl() {
    return g_pfl;
}

#ifndef MIXBUS

void setGlobalXFader(float val) {
    if (val < 0.0f)
        g_xfader = 0.0f;
    else if (val > 1.0f)
        g_xfader = 1.0f;
    else
        g_xfader = val;
    // Calculate Constant-Power CrossFader gains
    g_reqxf_gain_A = cos(M_PI_2 * g_xfader);
    g_reqxf_gain_B = sin(M_PI_2 * g_xfader);
    // Linear CrossFader gains
    //g_reqxf_gain_A = 1.0f - g_xfader;
    //g_reqxf_gain_B = g_xfader;
}

float getGlobalXFader() {
    return g_xfader;
}

void setABMixGroup(uint8_t channel, uint8_t ab) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return;
    if (ab > 2) ab = 2;
    g_channelStrips[channel]->ABMixGroup = ab;
}

uint8_t getABMixGroup(uint8_t channel) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return 0;
    return g_channelStrips[channel]->ABMixGroup;
}
#else
void setPflLevel(float level) {
    g_pflLevel = level;
}

float getPflLevel() {
    return g_pflLevel;
}
#endif

void setPhase(uint8_t channel, uint8_t phase) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return;
    g_channelStrips[channel]->phase = phase;
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
    setGain(channel, 1.0);
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
        return -200.0f;
    if (leg)
        return convertToDBFS(g_channelStrips[channel]->dpmB);
    return convertToDBFS(g_channelStrips[channel]->dpmA);
}

float getDpmHold(uint8_t channel, uint8_t leg) {
    if (channel >= MAX_CHANNELS || g_channelStrips[channel] == NULL)
        return -200.0f;
    if (leg)
        return convertToDBFS(g_channelStrips[channel]->holdB);
    return convertToDBFS(g_channelStrips[channel]->holdA);
}

void updateDpmStates(dpm_struct* values, uint8_t count) {
    if (count == 0 || count >= MAX_CHANNELS)
        count = MAX_CHANNELS - 1;
    for (uint8_t i = 0; i < count; ++i) {
        if (i < g_lastStrip) {
            values[i].a = getDpm(i, 0);
            values[i].b = getDpm(i, 1);
            values[i].aHold = getDpmHold(i, 0);
            values[i].bHold = getDpmHold(i, 1);
            values[i].mono = getMono(i);
        } else {
            memset(values + i, 0, sizeof(dpm_struct));
        }
    }
}

void enableDpm(uint8_t enable) {
    struct channel_strip* pChannel;
    for (uint8_t chan = 0; chan < MAX_CHANNELS; ++chan) {
        if (g_channelStrips[chan] == NULL)
            continue;
#ifdef MIXBUS
        if (chan == 0)
            g_channelStrips[chan]->enable_dpm = 1;
        else if (chan == 1)
            g_channelStrips[chan]->enable_dpm = 0;
        else
#endif
        g_channelStrips[chan]->enable_dpm = enable;
        // Silence disabled DPMs
        if (!g_channelStrips[chan]->enable_dpm) {
            g_channelStrips[chan]->dpmA  = 0.0f;
            g_channelStrips[chan]->dpmB  = 0.0f;
            g_channelStrips[chan]->holdA = 0.0f;
            g_channelStrips[chan]->holdB = 0.0f;
        }
    }
}

int8_t addStrip() {
    uint8_t chan;
    for (chan = 0; chan < MAX_CHANNELS; ++chan) {
        if (g_channelStrips[chan] || g_channelStripsRemoved[chan])
            continue;
        struct channel_strip* strip = malloc(sizeof(struct channel_strip));
        if (strip == NULL) {
            fprintf(stderr, "Failed to allocate memory for channel strip.\n");
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
        strip->gain       = 1.0;
        strip->level      = 0.0;
        strip->reqlevel   = 0.8;
        strip->balance    = 0.0;
        strip->reqbalance = 0.0;
        strip->mute       = 0;
        strip->mono       = 0;
        strip->solo       = 0;
        strip->pfl        = 0;
        strip->ms         = 0;
        strip->phase      = 0;
        #ifndef MIXBUS
        strip->ABMixGroup = 0;
        #endif
        strip->normalise  = 0;
        strip->inRouted   = 0;
        strip->outRouted  = 0;
        strip->enable_dpm = 1;
        for (uint8_t send = 0; send < MAX_CHANNELS; ++send) {
            strip->send[send] = 0.0;
            strip->sendMode[send] = 0;
        }
        strip->dpmA = strip->holdA = 0.0f;
        strip->dpmB = strip->holdB = 0.0f;
        strip->dpmAlast  = 100.0f;
        strip->dpmBlast  = 100.0f;
        strip->holdAlast = 100.0f;
        strip->holdBlast = 100.0f;
        atomic_store(&g_channelStrips[chan], strip);

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
    pthread_mutex_lock(&mutex);
    g_channelStripsRemoved[chan] = atomic_exchange(&g_channelStrips[chan], NULL);
    g_nCleanFrame = g_nNextFrame;
    pthread_mutex_unlock(&mutex);

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
        if (g_fxSends[send] == NULL && g_fxSendsRemoved[send] == NULL) {
            struct fx_send* psend = malloc(sizeof(struct fx_send));
            if (!psend) {
                fprintf(stderr, "Failed to allocated memory for effect send %d\n", send);
                return -1;
            }
            char name[11];
            sprintf(name, "send_%02da", send + 2);
            if (!(psend->outPortA = jack_port_register(g_jackClient, name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0))) {
                free(psend);
                psend = NULL;
                fprintf(stderr, "libzynmixer: Cannot register %s\n", name);
                return -1;
            }
            sprintf(name, "send_%02db", send + 2);
            if (!(psend->outPortB = jack_port_register(g_jackClient, name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0))) {
                jack_port_unregister(g_jackClient, psend->outPortA);
                free(psend);
                fprintf(stderr, "libzynmixer: Cannot register %s\n", name);
                return -1;
            }
            //!@todo Do not cache jack_port_get_buffer
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
    send -= 2; // We expose sends at 2-based so need to decrement to access array
    if (send >= MAX_CHANNELS || g_fxSends[send] == NULL)
        return 1;
    pthread_mutex_lock(&mutex);
    g_fxSendsRemoved[send] = atomic_exchange(&g_fxSends[send], NULL);
    g_nCleanFrame = g_nNextFrame;
    pthread_mutex_unlock(&mutex);
    --g_sendCount;

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

uint8_t getLastChannel() { return g_lastStrip; }

