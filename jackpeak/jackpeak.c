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
	if (!(g_pInputPort[0] = jack_port_register(g_pJackClient, "Input A", JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0))) {
		fprintf(stderr, "libjackpeak cannot register input port A\n");
		exit(1);
	}
	if (!(g_pInputPort[1] = jack_port_register(g_pJackClient, "Input B", JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0))) {
		fprintf(stderr, "libjackpeak cannot register input port B\n");
		exit(1);
	}
	#ifdef DEBUG
	fprintf(stderr,"libjackpeak created input ports\n");
	#endif

	// Register the cleanup function to be called when program exits
	atexit(endJackpeak);

	// Register the callback to calculate peak sample
	jack_set_process_callback(g_pJackClient, onJackProcess, 0);

	if (jack_activate(g_pJackClient)) {
		fprintf(stderr, "libjackpeak cannot activate client\n");
		exit(1);
	}
	return 1;
}

void endJackpeak() {
	disconnectAll(CHANNEL_ALL);
	jack_client_close(g_pJackClient);
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
	return fPeak;
}

float getPeak(unsigned int channel, float damping, unsigned int db) {
	float fPeak = 0;
	if(damping > 1)
		damping = 1; // ensure signal does not increase (1 = no decay)
	if(channel <= CHANNEL_ALL) {
		fPeak = getPeakRaw(channel);
		if(fPeak <= g_fDamped[channel] - damping)
			fPeak -= damping;
		if(fPeak < 0.0f)
			fPeak = 0.0f;
		g_fDamped[channel] = fPeak;
	}
	if(db) {
		if(fPeak == 0)
			fPeak = -200;
		else
			fPeak = 20 * log10f(fPeak);
		if(fPeak < -200)
			fPeak = -200;
	}
	return fPeak;
}

void connect(const char* source, unsigned int input) {
	if(input > 2) {
		fprintf(stderr, "Invalid input %d\n", input);
		return;
	}
	jack_port_t *pPort = jack_port_by_name(g_pJackClient, source);
	if (pPort == NULL) {
		fprintf(stderr, "Can't find source port '%s'\n", source);
		return;
	}

	int j;
	for(j = 0; j < 2; ++j) {
		if(input == j || input == CHANNEL_ALL) {
			#ifdef DEBUG
			fprintf(stderr,"Connecting '%s' to '%s'...\n", jack_port_name(pPort), jack_port_name(g_pInputPort[j]));
			#endif
			if (jack_connect(g_pJackClient, jack_port_name(pPort), jack_port_name(g_pInputPort[j]))) {
				fprintf(stderr, "Cannot connect port '%s' to '%s'\n", jack_port_name(pPort), jack_port_name(g_pInputPort[j]));
			}
		}
	}
}

void disconnect(const char* source, unsigned int input) {
	if(input > 2) {
		fprintf(stderr, "Invalid input %d\n", input);
		return;
	}
	jack_port_t *pPort = jack_port_by_name(g_pJackClient, source);
	if (pPort == NULL) {
		fprintf(stderr, "Can't find source port '%s'\n", source);
		return;
	}

	int j;
	for(j = 0; j < 2; ++j) {
		if(input == j || input == CHANNEL_ALL) {
			#ifdef DEBUG
			fprintf(stderr,"Disconnecting '%s' from '%s'...\n", jack_port_name(pPort), jack_port_name(g_pInputPort[j]));
			#endif
			if (jack_disconnect(g_pJackClient, jack_port_name(pPort), jack_port_name(g_pInputPort[j]))) {
				fprintf(stderr, "Cannot connect port '%s' to '%s'\n", jack_port_name(pPort), jack_port_name(g_pInputPort[j]));
			}
		}
	}
}

void disconnectAll(unsigned int input) {
	const char **ppPorts;
	unsigned int i, j;
	for(j = 0; j < 2; ++j) {
		if(input == j || input == CHANNEL_ALL) {
			if (g_pInputPort[j] != NULL ) {
				ppPorts = jack_port_get_all_connections(g_pJackClient, g_pInputPort[j]);
				for (i=0; ppPorts && ppPorts[i]; i++) {
					jack_disconnect(g_pJackClient, ppPorts[i], jack_port_name(g_pInputPort[j]));
				}
			}
		}
	}
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
