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

#include <jack/jack.h>
#include <stdint.h> //provides fixed width integer types

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
void setLevel(uint8_t channel, float level);

/** @brief  Get channel level
 *   @param  channel Index of channel
 *   @retval float Channel level (0..1)
 *   @note   Channel > MAX_CHANNELS will retrived master fader level
 */
float getLevel(uint8_t channel);

/** @brief  Set channel balance
 *   @param  channel Index of channel
 *   @param  pan Channel pan (-1..1)
 *   @note   Channel > MAX_CHANNELS will set master balance
 */
void setBalance(uint8_t channel, float pan);

/** @brief  Get channel balance
 *   @param  channel Index of channel
 *   @retval float Channel pan (-1..1)
 *   @note   Channel > MAX_CHANNELS will retrived master balance
 */
float getBalance(uint8_t channel);

/** @brief  Set mute state of channel
 *   @param  channel Index of channel
 *   @param  mute Mute status (0: Unmute, 1: Mute)
 */
void setMute(uint8_t channel, uint8_t mute);

/** @brief  Get mute state of channel
 *   @param  channel Index of channel
 *   @retval  uint8_t Mute status (0: Unmute, 1: Mute)
 */
uint8_t getMute(uint8_t channel);

/** @brief  Set solo state of channel
 *   @param  channel Index of channel
 *   @param  solo Solostatus (0: Normal, 1: Solo)
 */
void setSolo(uint8_t channel, uint8_t solo);

/** @brief  Get solo state of channel
 *   @param  channel Index of channel
 *   @retval  uint8_t Solo status (0: Normal, 1: solo)
 */
uint8_t getSolo(uint8_t channel);

/** @brief  Toggles mute of a channel
 *   @param  channel Index of channel
 */
void toggleMute(uint8_t channel);

/** @brief  Set mono state of channel
 *   @param  channel Index of channel
 *   @param  mono (0: Stereo, 1: Mono)
 */
void setMono(uint8_t channel, uint8_t mono);

/** @brief  Get mono state of channel
 *   @param  channel Index of channel
 *   @retval uint8_t Channel mono state (0: Stereo, 1: mono)
 */
uint8_t getMono(uint8_t channel);

/** @brief  Enable MS decode mode
 *   @param  channel Index of channel
 *   @param  enable (0: Stereo, 1: MS decode)
 */
void setMS(uint8_t channel, uint8_t enable);

/** @brief  Get MS decode mode
 *   @param  channel Index of channel
 *   @retval uint8_t MS decode mode (0: Stereo, 1: MS decode)
 */
uint8_t getMS(uint8_t channel);

/** @brief  Set phase state of channel
 *   @param  channel Index of channel
 *   @param  phase (0: in phase, 1: phase reversed)
 */
void setPhase(uint8_t channel, uint8_t phase);

/** @brief  Get phase state of channel
 *   @param  channel Index of channel
 *   @retval uint8_t Channel phase state (0: in phase, 1: phase reversed)
 */
uint8_t getPhase(uint8_t channel);

/** @brief  Set internal normalisation of channel
 *   @param  channel Index of channel
 *   @param  enable 1 to enable internal normalisation when channel direct output not routed
 */
void setNormalise(uint8_t channel, uint8_t enable);

/** @brief  Get internal normalisation of channel
 *   @param  channel Index of channel
 *   @retval uint8_t 1 if channel normalised
 */
uint8_t getNormalise(uint8_t channel, uint8_t enable);

/** @brief  Reset a channel to default settings
 *   @param  channel Index of channel
 */
void reset(uint8_t channel);

/** @brief  Check if channel has source routed
 *   @param  channel Index of channel
 *   @retval uint8_t 1 if channel has source routed. 0 if no source routed to channel.
 */
uint8_t isChannelRouted(uint8_t channel);

/** @brief  Check if channel has output routed
 *   @param  channel Index of channel
 *   @retval uint8_t 1 if channel has output routed. 0 if not routed.
 */
uint8_t isChannelOutRouted(uint8_t channel);

/** @brief  Get DPM level
 *   @param  channel Index of channel
 *   @param  leg 0 for A leg (left), 1 for B leg (right)
 *   @retval float DPM level
 */
float getDpm(uint8_t channel, uint8_t leg);

/** @brief  Get DPM hold level
 *   @param  channel Index of channel
 *   @param  leg 0 for A leg (left), 1 for B leg (right)
 *   @retval float DPM hold level
 */
float getDpmHold(uint8_t channel, uint8_t leg);

/** @brief  Get DPM state for a set of channels
 *   @param  start Index of the first channel
 *   @param  end Index of the last channel
 *   @param  values Pointer to array of floats to hold DPM, hold, and mono status for each channel
 */
void getDpmStates(uint8_t start, uint8_t end, float* values);

/** @brief  Enable / disable peak programme metering
 *   @param  start Index of first channel
 *   @param  end Index of last channel
 *   @param  enable 1 to enable, 0 to disable
 *   @note   DPM increase CPU processing so may be disabled if this causes issues (like xruns)
 */
void enableDpm(uint8_t start, uint8_t end, uint8_t enable);

/** @brief  Adds client to list of registered OSC clients
 *   @param  client IP address of client
 *   @retval int Index of client or -1 on failure
 *   @note   Clients get all updates including DPM
 */
int addOscClient(const char* client);

/** @brief  Removes client from list of registered OSC clients
 *   @param  client IP address of client
 */
void removeOscClient(const char* client);

/** @brief Get maximum quantity of channels
 *   @retval size_t Maximum quantity of channels
 */
uint8_t getMaxChannels();
