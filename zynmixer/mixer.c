/*
 * ******************************************************************
 * ZYNTHIAN PROJECT: Audio Mixer Library
 *
 * Library to mix channels to stereo output
 *
 * Copyright (C) 2019 Brian Walton <brian@riban.co.uk>
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

#include "mixer.h"

#define DEBUG

#define MAX_CHANNELS 16

struct dynamic
{
	float level;
	float reqlevel;
	float balance;
	float reqbalance;
};

jack_port_t * g_pInputPort[MAX_CHANNELS * 2];
jack_port_t * g_pOutputPort[2];
jack_client_t * g_pJackClient;
struct dynamic g_dynamic[MAX_CHANNELS];
struct dynamic g_master;

static int onJackProcess(jack_nframes_t nFrames, void *pArgs)
{
	jack_default_audio_sample_t *pInA, *pInB, *pOutA, *pOutB;

	pOutA = jack_port_get_buffer(g_pOutputPort[0], nFrames);
	pOutB = jack_port_get_buffer(g_pOutputPort[1], nFrames);
	memset(pOutA, 0.0, nFrames * sizeof(jack_default_audio_sample_t));
	memset(pOutB, 0.0, nFrames * sizeof(jack_default_audio_sample_t));

	unsigned int i,j;
	for(j = 0; j < MAX_CHANNELS; j++)
	{
		float fFactorA = g_master.level * g_dynamic[j].level * (g_dynamic[j].balance - 1) / -2;
		float fFactorB = g_master.level * g_dynamic[j].level * (g_dynamic[j].balance + 1) / 2;
		pInA = jack_port_get_buffer(g_pInputPort[j*2], nFrames);
		pInB = jack_port_get_buffer(g_pInputPort[j*2+1], nFrames);
		for (i = 0; i < nFrames; i++)
		{
			pOutA[i] += pInA[i] * fFactorA;
			pOutB[i] += pInB[i] * fFactorB;
		}
		float fDiff = g_dynamic[j].reqlevel - g_dynamic[j].level;
		if(fabs(fDiff) > 0.001)
			g_dynamic[j].level += fDiff / 10;
		else
			g_dynamic[j].level = g_dynamic[j].reqlevel;
		fDiff = g_dynamic[j].reqbalance - g_dynamic[j].balance;
		if(fabs(fDiff) > 0.001)
			g_dynamic[j].balance += fDiff / 10;
		else
			g_dynamic[j].balance = g_dynamic[j].reqbalance;

	}
	float fDiff = g_master.reqlevel - g_master.level;
	if(fabs(fDiff) > 0.001)
		g_master.level += fDiff / 10;
	else
		g_master.level = g_master.reqlevel;
	fDiff = g_master.reqbalance - g_master.balance;
	if(fabs(fDiff) > 0.001)
		g_master.balance += fDiff / 10;
	else
		g_master.balance = g_master.reqbalance;
	return 0;
}

int init()
{
	// Register with Jack server
	char *sServerName = NULL;
	jack_status_t nStatus;
	jack_options_t nOptions = JackNoStartServer;

	if ((g_pJackClient = jack_client_open("zynmixer", nOptions, &nStatus, sServerName)) == 0) {
		fprintf(stderr, "libzynmixer failed to start jack client: %d\n", nStatus);
		exit(1);
	}
	#ifdef DEBUG
	fprintf(stderr,"libzynmixer registering as '%s'.\n", jack_get_client_name(g_pJackClient));
	#endif

	// Create input ports
	for(size_t nPort = 0; nPort < MAX_CHANNELS; ++nPort)
	{
		g_dynamic[nPort].level = 1.0;
		g_dynamic[nPort].reqlevel = 1.0;
		g_dynamic[nPort].balance = 0.0;
		g_dynamic[nPort].reqbalance = 0.0;
		char sName[10];
		sprintf(sName, "input_a%02d", nPort);
		if (!(g_pInputPort[nPort * 2] = jack_port_register(g_pJackClient, sName, JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0)))
		{
			fprintf(stderr, "libzynmixer cannot register %s\n", sName);
			exit(1);
		}
		sprintf(sName, "input_b%02d", nPort);
		if (!(g_pInputPort[nPort * 2 + 1] = jack_port_register(g_pJackClient, sName, JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0)))
		{
			fprintf(stderr, "libzynmixer cannot register %s\n", sName);
			exit(1);
		}
	}
	#ifdef DEBUG
	fprintf(stderr,"libzynmixer created input ports\n");
	#endif

	// Create output ports
	if(!(g_pOutputPort[0] = jack_port_register(g_pJackClient, "output_a", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0)))
	{
		fprintf(stderr, "libzynmixer cannot register output A\n");
		exit(1);
	}
	if(!(g_pOutputPort[1] = jack_port_register(g_pJackClient, "output_b", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0)))
	{
		fprintf(stderr, "libzynmixer cannot register output B\n");
		exit(1);
	}
	g_master.level = 1.0;
	g_master.reqlevel = 1.0;
	g_master.balance = 0.0;
	g_master.reqbalance = 0.0;

	#ifdef DEBUG
	fprintf(stderr,"libzynmixer registered output ports\n");
	#endif

	// Register the cleanup function to be called when program exits
	//atexit(end);

	// Register the callback to calculate peak sample
	jack_set_process_callback(g_pJackClient, onJackProcess, 0);

	if(jack_activate(g_pJackClient)) {
		fprintf(stderr, "libzynmixer cannot activate client\n");
		exit(1);
	}

	#ifdef DEBUG
	fprintf(stderr,"libzynmixer activated client\n");
	#endif

	return 1;
}

void end() {
	if(g_pJackClient)
		jack_client_close(g_pJackClient);
}

void setLevel(int channel, float level)
{
	if(channel >= MAX_CHANNELS)
		g_master.reqlevel = level;
	else
		g_dynamic[channel].reqlevel = level;
}

float getLevel(int channel)
{
	if(channel >= MAX_CHANNELS)
		return g_master.reqlevel;
	return g_dynamic[channel].reqlevel;
}

void setBalance(int channel, float balance)
{
	if(fabs(balance) > 1)
		return;
	if(channel >= MAX_CHANNELS)
		g_master.reqbalance = balance;
	else
		g_dynamic[channel].reqbalance = balance;
}

float getBalance(int channel)
{
	if(channel >= MAX_CHANNELS)
		return g_master.reqbalance;
	return g_dynamic[channel].reqbalance;
}
