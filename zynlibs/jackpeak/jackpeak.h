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

/** @brief  Set decay rate
*   @param  factor Factor by which meter level decreases each read [0..1]
*   @note   Example: Set factor to 0.1 to decrease level (0.1 x level) each time getPeak() is called.
*   @note   Factor of 1 will keep level same. Factor higher than 1 will be taken as factor = 1.
*/
void setDecay(float factor);

/** @brief  Set the peak hold indication count
*   @param  count Quantity of reads that the peak hold value will persist
*   @note   The peak hold value is the highest sample value in past _count_ calls to getPeak().
*/
void setHoldCount(unsigned int count);

/** @brief  Get raw peak value since last request
*   @param  channel Audio channel to read
*	@retval	float Peak value since last read [0..1]
*/
float getPeakRaw(unsigned int channel);

/** @brief  Get damped peak value in dBFS since last request
*   @param  channel Audio channel to read
*	@retval float Peak or decaying value since last read [0..1 | 0..-200]
*/
float getPeak(unsigned int channel);

/** @brief  Get peak hold value in dBFS
*   @param  channel Audio channel hold to read
*   @retval float Highest value in past _count_ calls to getPeak()
*/
float getHold(unsigned int channel);

/**	@brief	Callback to handle jack process
	@param	nFrames Quantity of frames available
	@param	pArgs Pointer to arguments
*/
static int onJackProcess(jack_nframes_t nframes, void *arg);

/** @brief  Convert raw level (0..1) to dBFS (0..-200)
*   @param  raw Raw level [0..1]
*   @retval float dBFS level
*/
static float convertToDBFS(float raw);
