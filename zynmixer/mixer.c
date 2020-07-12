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
	jack_port_t * port_a; // Jack input port A
	jack_port_t * port_b; // Jack input port B
	float level; // Current fader level 0..1
	float reqlevel; // Requested fader level 0..1
	float balance; // Current balance -1..+1
	float reqbalance; // Requested balance -1..+1
	float dpmA; // Current peak programme A-leg
	float dpmB; // Current peak programme B-leg
	float holdA; // Current peak hold level A-leg
	float holdB; // Current peak hold level B-leg
	int mute; // 1 if muted
	int routed; // 1 if source routed to channel
};

jack_client_t * g_pJackClient;
struct dynamic g_dynamic[MAX_CHANNELS];
struct dynamic g_mainOutput;
int g_bDpm = 1;
unsigned int g_nDampingCount = 0;
unsigned int g_nHoldCount = 0;

static int onJackProcess(jack_nframes_t nFrames, void *pArgs)
{
	jack_default_audio_sample_t *pInA, *pInB, *pOutA, *pOutB;

	pOutA = jack_port_get_buffer(g_mainOutput.port_a, nFrames);
	pOutB = jack_port_get_buffer(g_mainOutput.port_b, nFrames);
	memset(pOutA, 0.0, nFrames * sizeof(jack_default_audio_sample_t));
	memset(pOutB, 0.0, nFrames * sizeof(jack_default_audio_sample_t));

	unsigned int frame, chan;
	float curLevelA, curLevelB, reqLevelA, reqLevelB, fDeltaA, fDeltaB, fSampleA, fSampleB;
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

			if(g_dynamic[chan].mute)
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

			pInA = jack_port_get_buffer(g_dynamic[chan].port_a, nFrames);
			pInB = jack_port_get_buffer(g_dynamic[chan].port_b, nFrames);

			// Iterate samples scaling each and adding to output and set DPM if any samples louder than current DPM
			for(frame = 0; frame < nFrames; frame++)
			{
				fSampleA = pInA[frame] * curLevelA;
				pOutA[frame] += fSampleA;
				fSampleB = pInB[frame] * curLevelB;
				pOutB[frame] += fSampleB;
				curLevelA += fDeltaA;
				curLevelB += fDeltaB;
				if(g_bDpm)
				{
					fSampleA = fabs(fSampleA);
					if(fSampleA > g_dynamic[chan].dpmA)
						g_dynamic[chan].dpmA = fSampleA;
					fSampleB = fabs(fSampleB);
					if(fSampleB > g_dynamic[chan].dpmB)
						g_dynamic[chan].dpmB = fSampleB;
				}
			}
			// Update peak hold and scale DPM for damped release
			if(g_bDpm)
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
					g_dynamic[chan].dpmA *= 0.9;
					g_dynamic[chan].dpmB *= 0.9;
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

	for(frame = 0; frame < nFrames; frame++)
	{
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
		g_nHoldCount = 200;
	}
	if(g_nDampingCount == 0)
	{
		g_mainOutput.dpmA *= 0.9;
		g_mainOutput.dpmB *= 0.9;
		g_nDampingCount = 10;
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
		if(jack_port_connected(g_dynamic[chan].port_a) > 0 && (jack_port_connected(g_dynamic[chan].port_a) > 0))
			g_dynamic[chan].routed = 1;
		else
			g_dynamic[chan].routed = 0;
	}
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
	for(size_t chan = 0; chan < MAX_CHANNELS; ++chan)
	{
		g_dynamic[chan].level = 0.0;
		g_dynamic[chan].reqlevel = 0.8;
		g_dynamic[chan].balance = 0.0;
		g_dynamic[chan].reqbalance = 0.0;
		g_dynamic[chan].mute = 0;
		char sName[10];
		sprintf(sName, "input_%02da", chan);
		if (!(g_dynamic[chan].port_a = jack_port_register(g_pJackClient, sName, JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0)))
		{
			fprintf(stderr, "libzynmixer cannot register %s\n", sName);
			exit(1);
		}
		sprintf(sName, "input_%02db", chan);
		if (!(g_dynamic[chan].port_b = jack_port_register(g_pJackClient, sName, JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0)))
		{
			fprintf(stderr, "libzynmixer cannot register %s\n", sName);
			exit(1);
		}
	}
	#ifdef DEBUG
	fprintf(stderr,"libzynmixer created input ports\n");
	#endif

	// Create output ports
	if(!(g_mainOutput.port_a = jack_port_register(g_pJackClient, "output_a", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0)))
	{
		fprintf(stderr, "libzynmixer cannot register output A\n");
		exit(1);
	}
	if(!(g_mainOutput.port_b = jack_port_register(g_pJackClient, "output_b", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0)))
	{
		fprintf(stderr, "libzynmixer cannot register output B\n");
		exit(1);
	}
	g_mainOutput.level = 0.0;
	g_mainOutput.reqlevel = 0.8;
	g_mainOutput.balance = 0.0;
	g_mainOutput.reqbalance = 0.0;
	g_mainOutput.mute = 0;
	g_mainOutput.routed = 1;

	#ifdef DEBUG
	fprintf(stderr,"libzynmixer registered output ports\n");
	#endif

	// Register the cleanup function to be called when library exits
	//atexit(end);

	// Register the callbacks
	jack_set_process_callback(g_pJackClient, onJackProcess, 0);
	jack_set_port_connect_callback(g_pJackClient, onJackConnect, 0);

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
		g_mainOutput.reqlevel = level;
	else
		g_dynamic[channel].reqlevel = level;
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
	if(channel >= MAX_CHANNELS)
		g_mainOutput.reqbalance = balance;
	else
		g_dynamic[channel].reqbalance = balance;
}

float getBalance(int channel)
{
	if(channel >= MAX_CHANNELS)
		return g_mainOutput.reqbalance;
	return g_dynamic[channel].reqbalance;
}

void setMute(int channel, int mute)
{
	if(channel >= MAX_CHANNELS)
		g_mainOutput.mute = mute;
	else
		g_dynamic[channel].mute = mute;
}

int getMute(int channel)
{
	if(channel >= MAX_CHANNELS)
		return g_mainOutput.mute;
	return g_dynamic[channel].mute;
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

int isChannelRouted(int channel)
{
	if(channel >= MAX_CHANNELS)
		return 0;
	return g_dynamic[channel].routed;
}

static float convertToDBFS(float raw) {
	if(raw <= 0)
		return -200;
	float fValue = 20 * log10f(raw);
	if(fValue < -200)
		fValue = -200;
	return fValue;
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
