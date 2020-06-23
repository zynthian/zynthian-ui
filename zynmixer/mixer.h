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

//-----------------------------------------------------------------------------
// Library Initialization
//-----------------------------------------------------------------------------

/** @brief  Initialises library
*   @retval int 1 on success, 0 on fail
*/
int init();

/** @brief  Destroy library
*/
void end();

/** @brief  Set channel level
*   @param  channel Index of channel
*   @param  level Channel level (0..1)
*   @note   Channel > MAX_CHANNELS will set master fader level
*/
void setLevel(int channel, float level);

/** @brief  Get channel level
*   @param  channel Index of channel
*   @retval float Channel level (0..1)
*   @note   Channel > MAX_CHANNELS will retrived master fader level
*/
float getLevel(int channel);

/** @brief  Set channel balance
*   @param  channel Index of channel
*   @param  pan Channel pan (-1..1)
*   @note   Channel > MAX_CHANNELS will set master balance
*/
void setBalance(int channel, float pan);

/** @brief  Get channel balance
*   @param  channel Index of channel
*   @retval float Channel pan (-1..1)
*   @note   Channel > MAX_CHANNELS will retrived master balance
*/
float getBalance(int channel);
