/*
 * ******************************************************************
 * ZYNTHIAN PROJECT: Jackpeak Library
 *
 * Library to monitor for peak audio level from a Jack connected source
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

#include <jack/jack.h>

enum PEAK_CHANNEL {
	CHANNEL_A = 0,
	CHANNEL_B = 1,
	CHANNEL_ALL = 2
};

//-----------------------------------------------------------------------------
// Library Initialization
//-----------------------------------------------------------------------------

/** @brief  Initialises library
*   @retval int 1 on success, 0 on fail
*/
int initJackpeak();

/** @brief  Destroy library
*/
void endJackpeak();

/** @brief  Get raw peak value since last request
*   @param  channel Audio channel to read
*	@retval	float Peak value since last read [0..1]
*/
float getPeakRaw(unsigned int channel);

/** @brief  Get damped peak value since last request
*   @param  channel Audio channel to read
*   @param  damping Maximum raw value to decay with each call to getPeak
*   @param  db True to convert value to dB
*	@retval float Peak or decaying value since last read [0..1 | 0..-200]
*/
float getPeak(unsigned int channel, float damping, unsigned int db);

/**	@brief	Connect a Jack source
*	@param	source Jack source name
*	@param	Input [CHANNEL_A | CHANNEL_B | CHANNEL_ALL]
*/
void connect(const char* source, unsigned int input);

/**	@brief	Disconnect a Jack source
*	@param	source Jack source name
*	@param	input [CHANNEL_A | CHANNEL_B | CHANNEL_ALL]
*/
void disconnect(const char* source, unsigned int input);

/**	@brief	Disconnect all Jack sources
*	@param	input [CHANNEL_A | CHANNEL_B | CHANNEL_ALL]
*/
void disconnectAll(unsigned int input);

/**	@brief	Callback to handle jack process
	@param	nFrames Quantity of frames available
	@param	pArgs Pointer to arguments
*/
static int onJackProcess(jack_nframes_t nframes, void *arg);
