/*
 * ******************************************************************
 * ZYNTHIAN PROJECT: Jackpeak Library
 *
 * Library to monitor for peak audio level from a Jack connected source
 *
 * Copyright (C) 2019 Brian Walton <brian@riban.co.uk>
 * Derived from code by Nicholas J. Humfrey
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
#include <math.h> //provides fabs

#include "jackpeak.h"

#define DEBUG

jack_port_t * g_pInputPort[2];
jack_client_t *g_pJackClient = NULL;
float g_fPeak[2] = {0.0f, 0.0f};
float g_fDamped[3] = {0.0f, 0.0f, 0.0f};
float g_fHold[3] = {0.0f, 0.0f, 0.0f};
float g_fDampingFactor = 0.1f;
unsigned int g_nHoldMax = 10;
unsigned int g_nHoldCount[3] = {0, 0, 0};

int initJackpeak() {
	// Register with Jack server
	char *sServerName = NULL;
	jack_status_t nStatus;
	jack_options_t nOptions = JackNoStartServer;

	if ((g_pJackClient = jack_client_open("jackpeak", nOptions, &nStatus, sServerName)) == 0) {
		fprintf(stderr, "libjackpeak failed to start jack client: %d\n", nStatus);
		exit(1);
	}
	#ifdef DEBUG
	fprintf(stderr,"libjackpeak registering as '%s'.\n", jack_get_client_name(g_pJackClient));
	#endif

	// Create input ports
	if (!(g_pInputPort[0] = jack_port_register(g_pJackClient, "input_a", JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0))) {
		fprintf(stderr, "libjackpeak cannot register input port A\n");
		exit(1);
	}
	if (!(g_pInputPort[1] = jack_port_register(g_pJackClient, "input_b", JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0))) {
		fprintf(stderr, "libjackpeak cannot register input port B\n");
		exit(1);
	}
	#ifdef DEBUG
	fprintf(stderr,"libjackpeak created input ports\n");
	#endif

	// Register the cleanup function to be called when program exits
	// It raises a segmentation fault on exit, so it's disabled
	//atexit(endJackpeak);

	// Register the callback to calculate peak sample
	jack_set_process_callback(g_pJackClient, onJackProcess, 0);

	if (jack_activate(g_pJackClient)) {
		fprintf(stderr, "libjackpeak cannot activate client\n");
		exit(1);
	}
	return 1;
}

void endJackpeak() {
	if (g_pJackClient)
		jack_client_close(g_pJackClient);
}

void setDecay(float factor) {
    if(factor > 1)
        factor = 1;
    else if(factor < 0)
        factor = 0;
    g_fDampingFactor = factor;
}

void setHoldCount(unsigned int count) {
    g_nHoldMax = count;
}

float getPeakRaw(unsigned int channel) {
	float fPeak = 0;
	if (channel < CHANNEL_ALL) {
		fPeak = g_fPeak[channel];
		g_fPeak[channel] = 0;
	} else if (channel == CHANNEL_ALL) {
		fPeak = g_fPeak[CHANNEL_A];
		g_fPeak[CHANNEL_A] = 0;
		if (fPeak < g_fPeak[CHANNEL_B])
			fPeak = g_fPeak[CHANNEL_B];
		g_fPeak[CHANNEL_B] = 0;
	}
	if(channel <= CHANNEL_ALL) {
        if(g_fHold[channel] < fPeak) {
            g_fHold[channel] = fPeak;
            g_nHoldCount[channel] = g_nHoldMax;
        }
        else if(g_nHoldCount[channel] )
            --g_nHoldCount[channel];
        else
            g_fHold[channel] = fPeak;
	}
	return fPeak;
}

float getPeak(unsigned int channel) {
    float fPeak = 0;
    if(channel <= CHANNEL_ALL) {
        fPeak = getPeakRaw(channel);
        if(fPeak < g_fDamped[channel] * g_fDampingFactor)
            fPeak = g_fDamped[channel] * g_fDampingFactor;
        if(fPeak < 0.0f)
            fPeak = 0.0f;
        g_fDamped[channel] = fPeak;
    }
    return convertToDBFS(fPeak);
}

float getHold(unsigned int channel) {
    if(channel > CHANNEL_ALL)
        return -200;
    return(convertToDBFS(g_fHold[channel]));
}

static int onJackProcess(jack_nframes_t nFrames, void *pArgs)
{
	if (g_pInputPort[0] == NULL && g_pInputPort[1] == NULL) {
		return 0;
	}
	jack_default_audio_sample_t *pSamples;

	// Get largest magnitude audio samples from this batch of samples
	unsigned int i, j;
	for(j = 0; j < 2; ++j) {
		pSamples = (jack_default_audio_sample_t *) jack_port_get_buffer(g_pInputPort[j], nFrames);
		for (i = 0; i < nFrames; i++) {
			const float fSample = fabs(pSamples[i]);
			if (fSample > g_fPeak[j]) {
				g_fPeak[j] = fSample;
			}
		}
	}
	return 0;
}

static float convertToDBFS(float raw) {
    if(raw <= 0)
        return -200;
    float fValue = 20 * log10f(raw);
    if(fValue < -200)
        fValue = -200;
    return fValue;
}
