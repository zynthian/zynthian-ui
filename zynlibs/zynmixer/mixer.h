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

#include <jack/jack.h>
#include <stdint.h> //provides fixed width integer types

typedef struct {
    float a;
    float b;
    float aHold;
    float bHold;
    uint8_t mono;
} dpm_struct;

#define XFADE_NONE     0
#define XFADE_A        1
#define XFADE_B        2

//-----------------------------------------------------------------------------
// Library Initialization
//-----------------------------------------------------------------------------

/** @brief  Initialises library
 *   @retval int 1 on success, 0 on fail
 */
int init() __attribute__((constructor));

/** @brief  Destroy library
 */
void end();

/** @brief  Set channel gain
 *   @param  channel Index of channel
 *   @param  level Channel gain (Normalised: 0=-inf, 1.0=0dB, 2.0=+6dB, etc.)
 */
void setGain(uint8_t channel, float gain);

/** @brief  Get channel gain
 *   @param  channel Index of channel
 *   @retval float Channel gain (Normalised: 0=-inf, 1.0=0dB, 2.0=+6dB, etc.)
 */
float getGain(uint8_t channel);

/** @brief  Set channel level
 *   @param  channel Index of channel
 *   @param  level Channel level (Normalised fader position: 0=-inf, 0.70=0dB, 1.0=+10dB. See levelToDb())
 */
void setLevel(uint8_t channel, float level);

/** @brief  Get channel level
 *   @param  channel Index of channel
 *   @retval float Channel level (Normalised fader position: 0=-inf, 0.70=0dB, 1.0=+10dB. See levelToDb())
 */
float getLevel(uint8_t channel);

/** @brief  Convert fader position to gain in dB using the fader law
 *   @param  level Fader position (0..1.0)
 *   @retval float Gain in dB (-200 for silence)
 */
float levelToDb(float level);

/** @brief  Convert gain in dB to fader position using the fader law
 *   @param  db Gain in dB
 *   @retval float Fader position (0..1.0)
 */
float dbToLevel(float db);

/** @brief  Set channel balance
 *   @param  channel Index of channel
 *   @param  pan Channel pan (Normalised: -1.0=full left, 1.0=full right)
 */
void setBalance(uint8_t channel, float pan);

/** @brief  Get channel balance
 *   @param  channel Index of channel
 *   @retval float Channel pan (Normalised: -1.0=full left, 1.0=full right)
 */
float getBalance(uint8_t channel);

/** @brief  Set channel mute state
 *   @param  channel Index of channel
 *   @param  mute Mute status (0: Unmute, 1: Mute)
 */
void setMute(uint8_t channel, uint8_t mute);

/** @brief  Get channel mute state
 *   @param  channel Index of channel
 *   @retval  uint8_t Mute status (0: Unmute, 1: Mute)
 */
uint8_t getMute(uint8_t channel);

/** @brief  Toggles channel mute
 *   @param  channel Index of channel
 */
void toggleMute(uint8_t channel);

/** @brief  Set channel solo state
 *   @param  channel Index of channel
 *   @param  solo Solo status (0: Unsolo, 1: Solo)
 */
void setSolo(uint8_t channel, uint8_t solo);

/** @brief  Get channel solo state
 *   @param  channel Index of channel
 *   @retval  uint8_t Solo status (0: Unsolo, 1: Solo)
 */
uint8_t getSolo(uint8_t channel);

/** @brief  Toggles channel solo
   @param  channel Index of channel
 */
void toggleSolo(uint8_t channel);

/** @brief  Clear solo from all channel
*/
void clearSolo();

/** @brief  Get global solo
    @retval uint8_t Quantity of channels with solo asserted
*/
uint8_t getGlobalSolo();

#ifndef MIXBUS

/** @brief  Get global CrossFader
 *  @param  val Global CrossFader value. 0 = 100% A. 1 = 100% B. 0.5 = 50% AB mix.
 */
void setGlobalXFader(float val);

/** @brief  Get global CrossFader
 *    @retval uint8_t Global CrossFader value
 */
float getGlobalXFader();

/** @brief  Set channel AB mix-group (CrossFader group)
 *   @param  channel Index of channel
 *   @param  ab (0: None, 1: A, 2: B)
 */
void setABMixGroup(uint8_t channel, uint8_t ab);

/** @brief  Get channel AB mix-group (CrossFader group)
 *   @param  channel Index of channel
 *   @retval uint8_t Channel AB mix-group (0: None, 1: A, 2: B)
 */
uint8_t getABMixGroup(uint8_t channel);

/** @brief  Set PFL volume level
    @param  level PFL volume level
 */
 void setPflLevel(float level);

 /** @brief Get PFL volume level
    @retval float PFL volume level
 */
 float getPflLevel();
#endif

/** @brief  Set channel mono state
 *   @param  channel Index of channel
 *   @param  mono (0: Stereo, 1: Mono)
 */
void setMono(uint8_t channel, uint8_t mono);

/** @brief  Get channel mono state
 *   @param  channel Index of channel
 *   @retval uint8_t Channel mono state (0: Stereo, 1: Mono)
 */
uint8_t getMono(uint8_t channel);

/** @brief  Toggles channel mono
 *   @param  channel Index of channel
 */
void toggleMono(uint8_t channel);

/** @brief  Set channel MS decode mode
 *   @param  channel Index of channel
 *   @param  enable (0: Stereo, 1: MS decode)
 */
void setMS(uint8_t channel, uint8_t enable);

/** @brief  Get channel MS decode mode
 *   @param  channel Index of channel
 *   @retval uint8_t MS decode mode (0: Stereo, 1: MS decode)
 */
uint8_t getMS(uint8_t channel);

/** @brief  Toggles channel M+S
 *   @param  channel Index of channel
 */
void toggleMS(uint8_t channel);

/** @brief  Set channel phase state
 *   @param  channel Index of channel
 *   @param  phase (0: Normal, 1: Phase reversed)
 */
void setPhase(uint8_t channel, uint8_t phase);

/** @brief  Get channel phase state
 *   @param  channel Index of channel
 *   @retval uint8_t Channel phase state (0: Normal, 1: Phase reversed)
 */
uint8_t getPhase(uint8_t channel);

/** @brief  Toggles channel phase
 *   @param  channel Index of channel
 */
void togglePhase(uint8_t channel);

/** @brief  Set channel send mode
 *   @param  channel Index of channel
 *   @param  send Index of send
 *   @param  mode (0: Post-fader, 1: Pre-fader)
 */
void setSendMode(uint8_t channel, uint8_t send, uint8_t mode);

/** @brief  Get channel send mode
 *   @param  channel Index of channel
 *   @param  send Index of send
 *   @retval uint8_t Channel send mode (0: Pre-fader, 1: Post-fader, 2: Post-pan)
 */
uint8_t getSendMode(uint8_t channel, uint8_t send);

/** @brief  Set channel fx send level
 *   @param  channel Index of channel
 *   @param  send Index of fx send
 *   @param  level Channel level (Normalised: 0=-inf, 1.0=0dB)
 */
void setSend(uint8_t channel, uint8_t send, float level);

/** @brief  Get channel fx send level
 *   @param  channel Index of channel
 *   @param  send Index of fx send
 *   @retval float Channel send level (Normalised: 0=-inf, 1.0=0dB)
 */
float getSend(uint8_t channel, uint8_t send);

/** @brief  Set internal normalisation of channel
 *   @param  channel Index of channel
 *   @param  enable 1 to enable internal normalisation when channel direct output not routed
 */
void setNormalise(uint8_t channel, uint8_t enable);

/** @brief  Get internal normalisation of channel
 *   @param  channel Index of channel
 *   @retval uint8_t 1 if channel normalised
 */
uint8_t getNormalise(uint8_t channel);

/** @brief  Reset a channel to default settings
 *   @param  channel Index of channel
 */
void reset(uint8_t channel);

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

/** @brief  Update DPM states
 *  @param  values Pointer to array of structure to hold DPM, hold, and mono status for each channel
 *  @param  count Quantity of channels to update or 0 for all
 */
void updateDpmStates(dpm_struct* values, uint8_t count);

/** @brief  Configure meter ballistics and fader law
 *   @param  rangeDb Linear dB span of the DPM scale, i.e. dB below 0dBFS that maps to the bottom of the meter [Default: 60.0]
 *   @param  decayDbPerS DPM decay rate in dB per second [Default: 30.0]
 *   @param  holdS Peak hold time in seconds [Default: 2.0]
 *   @param  faderHeadroomDb Gain in dB at top of fader throw, i.e. how far above unity (fader "0dB") the fader goes. Equal to minus the fader "0dB" reference, e.g. 10.0 for a -10dB reference [Default: 10.0]
 *   @retval uint8_t 1 on success, 0 if any parameter is out of range (configuration is then unchanged)
 *   @note   Call before adding strips. Defaults are used until called
 */
uint8_t setMeterConfig(float rangeDb, float decayDbPerS, float holdS, float faderHeadroomDb);

/** @brief  Enable / disable peak programme metering
 *   @param enable 1 to enable, 0 to disable
 *   @note  DPM increase CPU processing so may be disabled if this causes issues (like xruns)
 *   @note  Main mixbus is always enabled 
 */
void enableDpm(uint8_t enable);

/** Add a channel strip
 *  @retval int8_t Index of channel strip or -1 on failure
 */
int8_t addStrip();

/** @brief  Remove a channel strip
 *  @param  chan Index of channel strip to remove
 *  @retval int8_t Index of strip removed or -1 on failure
 */
int8_t removeStrip(uint8_t chan);

/** Add an effect send
 *  @retval int8_t Index of send or -1 on failure
 */
int8_t addSend();

/** @brief  Remove an effect send
 *  @param  send Index of send to remove
 *  @retval int8_t 0 on success, 1 on failure
 */
uint8_t removeSend(uint8_t send);

/** @brief Get maximum quantity of channels
 *   @retval size_t Maximum quantity of channels
 */
uint8_t getMaxChannels();

/** @brief Get index of highest numbered channel
 *   @retval size_t Index of last channel
 */
uint8_t getLastChannel();

/** @brief Get quantity of effect sends
 *  @retval uint8_t Quantity of effect sends
 */
uint8_t getSendCount();

