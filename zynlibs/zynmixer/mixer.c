/*
 * ******************************************************************
 * ZYNTHIAN PROJECT: Audio Mixer Library
 *
 * Library to mix channels to stereo output
 *
 * Copyright (C) 2019-2022 Brian Walton <brian@riban.co.uk>
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

#include <stdio.h> //provides printf
#include <stdlib.h> //provides exit
#include <string.h> // provides memset
#include <math.h> //provides fabs
#include <unistd.h> // provides sleep
#include <pthread.h> //provides multithreading

#include "mixer.h"

#include "tinyosc.h"
#include <arpa/inet.h> // provides inet_pton

char g_oscbuffer[1024]; // Used to send OSC messages
char g_oscpath[20]; //!@todo Ensure path length is sufficient for all paths, e.g. /mixer/faderxxx
int g_oscfd = -1; // File descriptor for OSC socket
int g_bOsc = 0; // True if OSC client subscribed
pthread_t g_eventThread; // ID of low priority event thread
int g_sendEvents = 1; // Set to 0 to exit event thread

#define DEBUG

#define MAX_CHANNELS 17
#define MAIN_CHANNEL 256
#define MAX_OSC_CLIENTS 5

struct dynamic
{
    jack_port_t * portA; // Jack input port A
    jack_port_t * portB; // Jack input port B
    float level; // Current fader level 0..1
    float reqlevel; // Requested fader level 0..1
    float balance; // Current balance -1..+1
    float reqbalance; // Requested balance -1..+1
    float dpmA; // Current peak programme A-leg
    float dpmB; // Current peak programme B-leg
    float holdA; // Current peak hold level A-leg
    float holdB; // Current peak hold level B-leg
    int mute; // 1 if muted
    int solo; // 1 if solo
    int mono; // 1 if mono
    int phase; // 1 if channel B phase reversed
    int routed; // 1 if source routed to channel
};

jack_client_t * g_pJackClient;
struct dynamic g_dynamic[MAX_CHANNELS];
struct dynamic g_mainOutput;
jack_port_t * g_mainSendA;
jack_port_t * g_mainSendB;
jack_port_t * g_mainReturnA;
jack_port_t * g_mainReturnB;
int g_mainReturnRoutedA = 0;
int g_mainReturnRoutedB = 0;
int g_bDpm = 1;
unsigned int g_nDampingCount = 0;
unsigned int g_nDampingPeriod = 10; // Quantity of cycles between applying DPM damping decay
unsigned int g_nHoldCount = 0;
float g_fDpmDecay = 0.9; // Factor to scale for DPM decay - defines resolution of DPM decay
struct sockaddr_in g_oscClient[MAX_OSC_CLIENTS]; // Array of registered OSC clients
char g_oscdpm[20];


static float convertToDBFS(float raw) {
    if(raw <= 0)
        return -200;
    float fValue = 20 * log10f(raw);
    if(fValue < -200)
        fValue = -200;
    return fValue;
}

void sendOscFloat(const char* path, float value)
{
    if(g_oscfd == -1)
        return;
    for(int i = 0; i < MAX_OSC_CLIENTS; ++i)
    {
        if(g_oscClient[i].sin_addr.s_addr == 0)
            continue;
        int len = tosc_writeMessage(g_oscbuffer, sizeof(g_oscbuffer), path, "f", value);
        sendto(g_oscfd, g_oscbuffer, len, MSG_CONFIRM|MSG_DONTWAIT, (const struct sockaddr *) &g_oscClient[i], sizeof(g_oscClient[i]));
    }
}

void sendOscInt(const char* path, int value)
{
    if(g_oscfd == -1)
        return;
    for(int i = 0; i < MAX_OSC_CLIENTS; ++i)
    {
        if(g_oscClient[i].sin_addr.s_addr == 0)
            continue;
        int len = tosc_writeMessage(g_oscbuffer, sizeof(g_oscbuffer), path, "i", value);
        sendto(g_oscfd, g_oscbuffer, len, MSG_CONFIRM|MSG_DONTWAIT, (const struct sockaddr *) &g_oscClient[i], sizeof(g_oscClient[i]));
    }
}

void* eventThreadFn(void * param) {
    while(g_sendEvents) {
        if(g_nDampingCount == 0) {
            for(unsigned int chan = 0; chan < MAX_CHANNELS; chan++) {
                sprintf(g_oscdpm, "/mixer/dpm%da", chan);
                sendOscFloat(g_oscdpm, convertToDBFS(g_dynamic[chan].holdA));
                sprintf(g_oscdpm, "/mixer/dpm%db", chan);
                sendOscFloat(g_oscdpm, convertToDBFS(g_dynamic[chan].holdB));
                sendOscFloat("/mixer/dpmA", convertToDBFS(g_mainOutput.holdA));
                sendOscFloat("/mixer/dpmB", convertToDBFS(g_mainOutput.holdB));
            }
        }
        usleep(10000);
    }
    pthread_exit(NULL);
}

static int onJackProcess(jack_nframes_t nFrames, void *pArgs)
{
    jack_default_audio_sample_t *pInA, *pInB, *pOutA, *pOutB, *pSendA, *pSendB, *pReturnA, *pReturnB;

    pOutA = jack_port_get_buffer(g_mainOutput.portA, nFrames);
    pOutB = jack_port_get_buffer(g_mainOutput.portB, nFrames);
    memset(pOutA, 0.0, nFrames * sizeof(jack_default_audio_sample_t));
    memset(pOutB, 0.0, nFrames * sizeof(jack_default_audio_sample_t));

    pSendA = jack_port_get_buffer(g_mainSendA, nFrames);
    pSendB = jack_port_get_buffer(g_mainSendB, nFrames);
    memset(pSendA, 0.0, nFrames * sizeof(jack_default_audio_sample_t));
    memset(pSendB, 0.0, nFrames * sizeof(jack_default_audio_sample_t));

    unsigned int frame, chan;
    float curLevelA, curLevelB, reqLevelA, reqLevelB, fDeltaA, fDeltaB, fSampleA, fSampleB, fSampleM;
    // Apply gain adjustment to each channel and sum to main output
    for(chan = 0; chan < MAX_CHANNELS; chan++)
    {
        if(isChannelRouted(chan))
        {
            if(g_dynamic[chan].balance > 0.0)
                curLevelA = g_dynamic[chan].level * (1 - g_dynamic[chan].balance);
            else
                curLevelA = g_dynamic[chan].level;
            if(g_dynamic[chan].balance < 0.0)
                curLevelB = g_dynamic[chan].level * (1 + g_dynamic[chan].balance);
            else
                curLevelB = g_dynamic[chan].level;

            if(g_dynamic[chan].mute || g_mainOutput.solo && g_dynamic[chan].solo != 1)
            {
                g_dynamic[chan].level = 0; // We can set this here because we have the data and will iterate towards 0 over this frame
                reqLevelA = 0.0;
                reqLevelB = 0.0;
            }
            else
            {
                if(g_dynamic[chan].reqbalance > 0.0)
                    reqLevelA = g_dynamic[chan].reqlevel * (1 - g_dynamic[chan].reqbalance);
                else
                    reqLevelA = g_dynamic[chan].reqlevel;
                if(g_dynamic[chan].reqbalance < 0.0)
                    reqLevelB = g_dynamic[chan].reqlevel * (1 + g_dynamic[chan].reqbalance);
                else
                    reqLevelB = g_dynamic[chan].reqlevel;
                g_dynamic[chan].level = g_dynamic[chan].reqlevel;
                g_dynamic[chan].balance = g_dynamic[chan].reqbalance;
            }

            // Calculate the step change for each leg to apply on each sample in buffer
            fDeltaA = (reqLevelA - curLevelA) / nFrames;
            fDeltaB = (reqLevelB - curLevelB) / nFrames;

            pInA = jack_port_get_buffer(g_dynamic[chan].portA, nFrames);
            pInB = jack_port_get_buffer(g_dynamic[chan].portB, nFrames);

            // Iterate samples scaling each and adding to output and set DPM if any samples louder than current DPM
            if(g_dynamic[chan].mono)
            {
                for(frame = 0; frame < nFrames; frame++)
                {
                    fSampleM = pInA[frame];
                    if(g_dynamic[chan].phase)
                        fSampleM -= pInB[frame];
                    else
                        fSampleM += pInB[frame];
                    fSampleA = fSampleM * curLevelA / 2;
                    fSampleB = fSampleM * curLevelB / 2;
                    pSendA[frame] += fSampleA;
                    pSendB[frame] += fSampleB;
                    curLevelA += fDeltaA;
                    curLevelB += fDeltaB;
                    if(g_bDpm || g_bOsc)
                    {
                        fSampleA = fabs(fSampleA);
                        if(fSampleA > g_dynamic[chan].dpmA)
                            g_dynamic[chan].dpmA = fSampleA;
                        fSampleB = fabs(fSampleB);
                        if(fSampleB > g_dynamic[chan].dpmB)
                            g_dynamic[chan].dpmB = fSampleB;
                    }
                }
            }
            else
            {
                for(frame = 0; frame < nFrames; frame++)
                {
                    fSampleA = pInA[frame] * curLevelA;
                    pSendA[frame] += fSampleA;
                    if(g_dynamic[chan].phase)
                        fSampleB = -pInB[frame] * curLevelB;
                    else
                        fSampleB = pInB[frame] * curLevelB;
                    pSendB[frame] += fSampleB;
                    curLevelA += fDeltaA;
                    curLevelB += fDeltaB;
                    if(g_bDpm || g_bOsc)
                    {
                        fSampleA = fabs(fSampleA);
                        if(fSampleA > g_dynamic[chan].dpmA)
                            g_dynamic[chan].dpmA = fSampleA;
                        fSampleB = fabs(fSampleB);
                        if(fSampleB > g_dynamic[chan].dpmB)
                            g_dynamic[chan].dpmB = fSampleB;
                    }
                }
            }
            // Update peak hold and scale DPM for damped release
            if(g_bDpm || g_bOsc)
            {
                if(g_dynamic[chan].dpmA > g_dynamic[chan].holdA)
                    g_dynamic[chan].holdA = g_dynamic[chan].dpmA;
                if(g_dynamic[chan].dpmB > g_dynamic[chan].holdB)
                    g_dynamic[chan].holdB = g_dynamic[chan].dpmB;
                if(g_nHoldCount == 0)
                {
                    // Only update peak hold each g_nHoldCount cycles
                    g_dynamic[chan].holdA = g_dynamic[chan].dpmA;
                    g_dynamic[chan].holdB = g_dynamic[chan].dpmB;
                }
                if(g_nDampingCount == 0)
                {
                    // Only update damping release each g_nDampingCount cycles
                    g_dynamic[chan].dpmA *= g_fDpmDecay;
                    g_dynamic[chan].dpmB *= g_fDpmDecay;
                }
            }
        }
    }

    // Main outputs use similar processing to each channel so see above for comments
    if(g_mainOutput.balance > 0.0)
        curLevelA = g_mainOutput.level * (1 - g_mainOutput.balance);
    else
        curLevelA = g_mainOutput.level;
    if(g_mainOutput.balance < 0.0)
        curLevelB = g_mainOutput.level * (1 + g_mainOutput.balance);
    else
        curLevelB = g_mainOutput.level;

    if(g_mainOutput.mute)
    {
        g_mainOutput.level = 0;
        reqLevelA = 0.0;
        reqLevelB = 0.0;
    }
    else
    {
        if(g_mainOutput.reqbalance > 0.0)
            reqLevelA = g_mainOutput.reqlevel * (1 - g_mainOutput.reqbalance);
        else
            reqLevelA = g_mainOutput.reqlevel;
        if(g_mainOutput.reqbalance < 0.0)
            reqLevelB = g_mainOutput.reqlevel * (1 + g_mainOutput.reqbalance);
        else
            reqLevelB = g_mainOutput.reqlevel;
        g_mainOutput.level = g_mainOutput.reqlevel;
        g_mainOutput.balance = g_mainOutput.reqbalance;
    }

    fDeltaA = (reqLevelA - curLevelA) / nFrames;
    fDeltaB = (reqLevelB - curLevelB) / nFrames;

    pReturnA = jack_port_get_buffer(g_mainReturnA, nFrames);
    pReturnB = jack_port_get_buffer(g_mainReturnB, nFrames);

    for(frame = 0; frame < nFrames; frame++)
    {
        if(g_mainReturnRoutedA)
            pOutA[frame] = pReturnA[frame];
        else
            pOutA[frame] = pSendA[frame];
        if(g_mainReturnRoutedB)
            pOutB[frame] = pReturnB[frame];
        else
            pOutB[frame] = pSendB[frame];
       
        if(g_mainOutput.mono)
        {
            fSampleM = (pOutA[frame] + pOutB[frame]) / 2;
            pOutA[frame] = fSampleM;
            pOutB[frame] = fSampleM;
        }
        pOutA[frame] *= curLevelA;
        pOutB[frame] *= curLevelB;
        curLevelA += fDeltaA;
        curLevelB += fDeltaB;
        fSampleA = fabs(pOutA[frame]);
        if(fSampleA > g_mainOutput.dpmA)
            g_mainOutput.dpmA = fSampleA;
        fSampleB = fabs(pOutB[frame]);
        if(fSampleB > g_mainOutput.dpmB)
            g_mainOutput.dpmB = fSampleB;
    }

    if(g_mainOutput.dpmA > g_mainOutput.holdA)
        g_mainOutput.holdA = g_mainOutput.dpmA;
    if(g_mainOutput.dpmB > g_mainOutput.holdB)
        g_mainOutput.holdB = g_mainOutput.dpmB;
    if(g_nHoldCount == 0)
    {
        g_mainOutput.holdA = g_mainOutput.dpmA;
        g_mainOutput.holdB = g_mainOutput.dpmB;
        g_nHoldCount = g_nDampingPeriod * 20;
    }
    if(g_nDampingCount == 0)
    {
        g_mainOutput.dpmA *= g_fDpmDecay;
        g_mainOutput.dpmB *= g_fDpmDecay;
        g_nDampingCount = g_nDampingPeriod;
    }

    // Damping and hold counts are used throughout cycle so update at end of cycle
    --g_nDampingCount;
    --g_nHoldCount;

    return 0;
}

void onJackConnect(jack_port_id_t source, jack_port_id_t dest, int connect, void* args)
{
    unsigned int chan;
    for(chan = 0; chan < MAX_CHANNELS; chan++)
    {
        if(jack_port_connected(g_dynamic[chan].portA) > 0 || (jack_port_connected(g_dynamic[chan].portB) > 0))
            g_dynamic[chan].routed = 1;
        else
            g_dynamic[chan].routed = 0;
    }
    g_mainReturnRoutedA = jack_port_connected(g_mainReturnA) > 0;
    g_mainReturnRoutedB = jack_port_connected(g_mainReturnB) > 0;
}

int onJackSamplerate(jack_nframes_t nSamplerate, void *arg)
{
    g_nDampingPeriod = g_fDpmDecay * jack_get_sample_rate(g_pJackClient) / jack_get_buffer_size(g_pJackClient) / 15;
    return 0;
}

int onJackBuffersize(jack_nframes_t nBuffersize, void *arg)
{
    g_nDampingPeriod = g_fDpmDecay * jack_get_sample_rate(g_pJackClient) / jack_get_buffer_size(g_pJackClient) / 15;
    return 0;
}

int init()
{
    // Initialsize OSC
    g_oscfd = socket(AF_INET, SOCK_DGRAM, 0);
    for(int i = 0; i < MAX_OSC_CLIENTS; ++i)
    {
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
    fprintf(stderr,"libzynmixer: Registering as '%s'.\n", jack_get_client_name(g_pJackClient));
    #endif

    // Create input ports
    for(size_t chan = 0; chan < MAX_CHANNELS; ++chan)
    {
        g_dynamic[chan].level = 0.0;
        g_dynamic[chan].reqlevel = 0.8;
        g_dynamic[chan].balance = 0.0;
        g_dynamic[chan].reqbalance = 0.0;
        g_dynamic[chan].mute = 0;
        g_dynamic[chan].phase = 0;
        char sName[10];
        sprintf(sName, "input_%02da", chan + 1);
        if (!(g_dynamic[chan].portA = jack_port_register(g_pJackClient, sName, JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0)))
        {
            fprintf(stderr, "libzynmixer: Cannot register %s\n", sName);
            exit(1);
        }
        sprintf(sName, "input_%02db", chan + 1);
        if (!(g_dynamic[chan].portB = jack_port_register(g_pJackClient, sName, JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0)))
        {
            fprintf(stderr, "libzynmixer: Cannot register %s\n", sName);
            exit(1);
        }
    }
    if (!(g_mainReturnA = jack_port_register(g_pJackClient, "return_a", JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0)))
    {
        fprintf(stderr, "libzynmixer: Cannot register return_a\n");
        exit(1);
    }
    if (!(g_mainReturnB = jack_port_register(g_pJackClient, "return_b", JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0)))
    {
        fprintf(stderr, "libzynmixer: Cannot register return_b\n");
        exit(1);
    }

    #ifdef DEBUG
    fprintf(stderr,"libzynmixer: Created input ports\n");
    #endif

    // Create output ports
    if(!(g_mainOutput.portA = jack_port_register(g_pJackClient, "output_a", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0)))
    {
        fprintf(stderr, "libzynmixer: Cannot register output A\n");
        exit(1);
    }
    if(!(g_mainOutput.portB = jack_port_register(g_pJackClient, "output_b", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0)))
    {
        fprintf(stderr, "libzynmixer: Cannot register output B\n");
        exit(1);
    }
    if(!(g_mainSendA = jack_port_register(g_pJackClient, "send_a", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0)))
    {
        fprintf(stderr, "libzynmixer: Cannot register send A\n");
        exit(1);
    }
    if(!(g_mainSendB = jack_port_register(g_pJackClient, "send_b", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0)))
    {
        fprintf(stderr, "libzynmixer: Cannot register send B\n");
        exit(1);
    }
    g_mainOutput.level = 0.0;
    g_mainOutput.reqlevel = 0.8;
    g_mainOutput.balance = 0.0;
    g_mainOutput.reqbalance = 0.0;
    g_mainOutput.mute = 0;
    g_mainOutput.phase = 0;
    g_mainOutput.routed = 1;

    #ifdef DEBUG
    fprintf(stderr,"libzynmixer: Registered output ports\n");
    #endif

    // Register the cleanup function to be called when library exits
    atexit(end);

    // Register the callbacks
    jack_set_process_callback(g_pJackClient, onJackProcess, 0);
    jack_set_port_connect_callback(g_pJackClient, onJackConnect, 0);
    jack_set_sample_rate_callback(g_pJackClient, onJackSamplerate, 0);
    jack_set_buffer_size_callback(g_pJackClient, onJackBuffersize, 0);

    if(jack_activate(g_pJackClient)) {
        fprintf(stderr, "libzynmixer: Cannot activate client\n");
        exit(1);
    }

    #ifdef DEBUG
    fprintf(stderr,"libzynmixer: Activated client\n");
    #endif

    // Configure and start event thread
    pthread_attr_t attr;
    pthread_attr_init(&attr);
    pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_JOINABLE);
    if(pthread_create(&g_eventThread, &attr, eventThreadFn, NULL)) {
        fprintf(stderr, "zynmixer error: failed to create event thread\n");
        return 0;
    }

    return 1;
}

void end() {
    if(g_pJackClient)
    {
        // Mute output and wait for soft mute to occur before closing link with jack server
        setLevel(MAIN_CHANNEL, 0.0);
        usleep(100000);
        jack_client_close(g_pJackClient);
    }
    g_sendEvents = 0;
    void* status;
    pthread_join(g_eventThread, &status);
}

void setLevel(int channel, float level)
{
    if(channel >= MAX_CHANNELS) {
        channel = MAIN_CHANNEL;
        g_mainOutput.reqlevel = level;
    }
    else
        g_dynamic[channel].reqlevel = level;
    sprintf(g_oscpath, "/mixer/fader%d", channel);
    sendOscFloat(g_oscpath, level);
}

float getLevel(int channel)
{
    if(channel >= MAX_CHANNELS)
        return g_mainOutput.reqlevel;
    return g_dynamic[channel].reqlevel;
}

void setBalance(int channel, float balance)
{
    if(fabs(balance) > 1)
        return;
    if(channel >= MAX_CHANNELS) {
        channel = MAIN_CHANNEL;
        g_mainOutput.reqbalance = balance;
    }
    else
        g_dynamic[channel].reqbalance = balance;
    sprintf(g_oscpath, "/mixer/balance%d", channel);
    sendOscFloat(g_oscpath, balance);
}

float getBalance(int channel)
{
    if(channel >= MAX_CHANNELS)
        return g_mainOutput.reqbalance;
    return g_dynamic[channel].reqbalance;
}

void setMute(int channel, int mute)
{
    if(channel >= MAX_CHANNELS) {
        channel = MAX_CHANNELS;
        g_mainOutput.mute = mute;
    }
    else
        g_dynamic[channel].mute = mute;
    sprintf(g_oscpath, "/mixer/mute%d", channel);
    sendOscInt(g_oscpath, mute);
}

int getMute(int channel)
{
    if(channel >= MAX_CHANNELS)
        return g_mainOutput.mute;
    return g_dynamic[channel].mute;
}

void setPhase(int channel, int phase)
{
    if(channel >= MAX_CHANNELS) {
        channel = MAIN_CHANNEL;
        g_mainOutput.phase = phase;
    }
    else
        g_dynamic[channel].phase = phase;
    sprintf(g_oscpath, "/mixer/phase%d", channel);
    sendOscInt(g_oscpath, phase);
}

int getPhase(int channel)
{
    if(channel >= MAX_CHANNELS)
        return g_mainOutput.phase;
    return g_dynamic[channel].phase;
}

void setSolo(int channel, int solo)
{
    if(channel >= MAX_CHANNELS)
    {
        for(int nChannel = 0; nChannel < MAX_CHANNELS; ++nChannel)
        {
            g_dynamic[nChannel].solo = 0;
            sprintf(g_oscpath, "/mixer/solo%d", nChannel);
            sendOscInt(g_oscpath, 0);
        }
    }
    else
    {
        g_dynamic[channel].solo = solo;
        sprintf(g_oscpath, "/mixer/solo%d", channel);
        sendOscInt(g_oscpath, solo);
    }
    // g_mainOutput.solo indicates overall summary of solo status, i.e. 1 if any channel solo enabled
    g_mainOutput.solo = 0;
    for(int nChannel = 0; nChannel < MAX_CHANNELS; ++ nChannel)
        g_mainOutput.solo |= g_dynamic[nChannel].solo;
    sprintf(g_oscpath, "/mixer/solo%d", MAIN_CHANNEL);
    sendOscInt(g_oscpath, g_mainOutput.solo);
}

int getSolo(int channel)
{
    if(channel >= MAX_CHANNELS)
        return g_mainOutput.solo;
    return g_dynamic[channel].solo;
}

void toggleMute(int channel)
{
    int mute;
    if(channel >= MAX_CHANNELS)
        mute = g_mainOutput.mute;
    else
        mute = g_dynamic[channel].mute;
    if(mute)
        setMute(channel, 0);
    else
        setMute(channel, 1);
}

void togglePhase(int channel)
{
    int phase;
    if(channel >= MAX_CHANNELS)
        phase = g_mainOutput.phase;
    else
        phase = g_dynamic[channel].phase;
    if(phase)
        setPhase(channel, 0);
    else
        setPhase(channel, 1);
}


void setMono(int channel, int mono){
    if(channel >= MAX_CHANNELS) {
        channel = MAIN_CHANNEL;
        g_mainOutput.mono = (mono != 0);
    }
    else
        g_dynamic[channel].mono = (mono != 0);
    sprintf(g_oscpath, "/mixer/mono%d", channel);
    sendOscInt(g_oscpath, mono);
}

int getMono(int channel)
{
    if(channel >= MAX_CHANNELS)
        return g_mainOutput.mono;
    return g_dynamic[channel].mono;
}

void reset(int channel)
{
    if(channel >= MAX_CHANNELS)
        channel = MAIN_CHANNEL;
    setLevel(channel, 0.8);
    setBalance(channel, 0.0);
    setMute(channel, 0);
    setMono(channel, 0);
    setPhase(channel, 0);
    setSolo(channel, 0);
}

int isChannelRouted(int channel)
{
    if(channel >= MAX_CHANNELS)
        return 0;
    return g_dynamic[channel].routed;
}

float getDpm(int channel, int leg)
{
    if(channel >= MAX_CHANNELS)
    {
        if(leg)
            return convertToDBFS(g_mainOutput.dpmB);
        return convertToDBFS(g_mainOutput.dpmA);
    }
    if(leg)
        return convertToDBFS(g_dynamic[channel].dpmB);
    return convertToDBFS(g_dynamic[channel].dpmA);
}

float getDpmHold(int channel, int leg)
{
    if(channel >= MAX_CHANNELS)
    {
        if(leg)
            return convertToDBFS(g_mainOutput.holdB);
        return convertToDBFS(g_mainOutput.holdA);
    }
    if(leg)
        return convertToDBFS(g_dynamic[channel].holdB);
    return convertToDBFS(g_dynamic[channel].holdA);
}

void enableDpm(int enable)
{
    g_bDpm = enable;
    if(g_bDpm == 0)
    {
        for(unsigned int chan = 0; chan < MAX_CHANNELS; ++chan)
        {
            g_dynamic[chan].dpmA = 0;
            g_dynamic[chan].dpmB = 0;
            g_dynamic[chan].holdA = 0;
            g_dynamic[chan].holdB = 0;
        }
    }
}

int addOscClient(const char* client)
{
    for(int i = 0; i < MAX_OSC_CLIENTS; ++i)
    {
        if(g_oscClient[i].sin_addr.s_addr != 0)
            continue;
        if(inet_pton(AF_INET, client, &(g_oscClient[i].sin_addr)) != 1)
        {
            g_oscClient[i].sin_addr.s_addr = 0;
            fprintf(stderr, "libzynmixer: Failed to register client %s\n", client);
            return -1;
        }
        fprintf(stderr, "libzynmixer: Added OSC client %d: %s\n", i, client);
        for(int nChannel = 0; nChannel < MAX_CHANNELS; ++nChannel)
        {
            setBalance(nChannel, getBalance(nChannel));
            setLevel(nChannel, getLevel(nChannel));
            setMono(nChannel, getMono(nChannel));
            setMute(nChannel, getMute(nChannel));
            setPhase(nChannel, getPhase(nChannel));
            setSolo(nChannel, getSolo(nChannel));
        }
        setBalance(MAIN_CHANNEL, getBalance(MAIN_CHANNEL));
        setLevel(MAIN_CHANNEL, getLevel(MAIN_CHANNEL));
        setMono(MAIN_CHANNEL, getMono(MAIN_CHANNEL));
        setMute(MAIN_CHANNEL, getMute(MAIN_CHANNEL));
        setPhase(MAIN_CHANNEL, getPhase(MAIN_CHANNEL));
        setSolo(MAIN_CHANNEL, getSolo(MAIN_CHANNEL));
        g_bOsc = 1;
        return i;
    }
    fprintf(stderr, "libzynmixer: Not adding OSC client %s - Maximum client count reached [%d]\n", client, MAX_OSC_CLIENTS);
    return -1;
}

void removeOscClient(const char* client)
{
    char pClient[sizeof(struct in_addr)];
    if(inet_pton(AF_INET, client, pClient) != 1)
        return;
    g_bOsc = 0;
    for(int i = 0; i < MAX_OSC_CLIENTS; ++i)
    {
        if(memcmp(pClient, &g_oscClient[i].sin_addr.s_addr, 4) == 0)
        {
            g_oscClient[i].sin_addr.s_addr = 0;
            fprintf(stderr, "libzynmixer: Removed OSC client %d: %s\n", i, client);
        }
        if(g_oscClient[i].sin_addr.s_addr != 0)
            g_bOsc = 1;
    }
}

