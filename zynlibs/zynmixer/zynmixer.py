#!/usr/bin/python3
# -*- coding: utf-8 -*-
#********************************************************************
# ZYNTHIAN PROJECT: Zynmixer Python Wrapper
#
# A Python wrapper for zynmixer library
#
# Copyright (C) 2019-2021 Brian Walton <riban@zynthian.org>
#
#********************************************************************
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the LICENSE.txt file.
#
#********************************************************************

from ctypes import *
from os.path import dirname, realpath
import unicodedata

#-------------------------------------------------------------------------------
# Zynmixer Library Wrapper
#-------------------------------------------------------------------------------

lib_zynmixer=None

#	Function to initialize library
#	returns: Library object or None if library not initialized
def init():
	global lib_zynmixer
	try:
		lib_zynmixer=cdll.LoadLibrary(dirname(realpath(__file__))+"/build/libzynmixer.so")
		lib_zynmixer.init()
		lib_zynmixer.getLevel.restype = c_float
		lib_zynmixer.getBalance.restype = c_float
		lib_zynmixer.getDpm.restype = c_float
		lib_zynmixer.getDpmHold.restype = c_float
	except Exception as e:
		lib_zynmixer=None
		print("Can't init zynmixer library: %s" % str(e))
	return lib_zynmixer

#	Function to get instance of library
#	returns: Library object or None if library not initialized
def get_lib_zynmixer():
	return lib_zynmixer

#	Function to set fader level for a channel
#	channel: Index of channel
#	level: Fader value (0..+1)
def set_level(channel, level):
	if lib_zynmixer:
		lib_zynmixer.setLevel(channel, c_float(level))

#	Function to set balance for a channel
#	channel: Index of channel
#	balance: Balance value (-1..+1)
def set_balance(channel, balance):
	if lib_zynmixer:
		lib_zynmixer.setBalance(channel, c_float(balance))

#	Function to get fader level for a channel
#	channel: Index of channel
#	returns: Fader level (0..+1)
def get_level(channel):
	if lib_zynmixer:
		return lib_zynmixer.getLevel(channel)
	return 0

#	Function to get balance for a channel
#	channel: Index of channel
#	returns: Balance value (-1..+1)
def get_balance(channel):
	if lib_zynmixer:
		return lib_zynmixer.getBalance(channel)
	return 0

#	Function to set mute for a channel
#	channel: Index of channel
#	mute: Mute state (True to mute)
def	set_mute(channel, mute):
	if lib_zynmixer:
		lib_zynmixer.setMute(channel, mute)

#	Function to get mute for a channel
#	channel: Index of channel
#	returns: Mute state (True if muted)
def	get_mute(channel):
	if lib_zynmixer:
		return lib_zynmixer.getMute(channel)
	else:
		return True

#	Function to toggle mute of a channel
#	channel: Index of channel
def toggle_mute(channel):
	if lib_zynmixer:
		lib_zynmixer.toggleMute(channel)

#	Function to set phase reversal for a channel
#	channel: Index of channel
#	phase: Phase reversal state (True to reverse)
def	set_phase(channel, phase):
	if lib_zynmixer:
		lib_zynmixer.setPhase(channel, phase)

#	Function to get phase reversal for a channel
#	channel: Index of channel
#	returns: Phase reversal state (True if phase reversed)
def	get_phase(channel):
	if lib_zynmixer:
		return lib_zynmixer.getPhase(channel)
	else:
		return True

#	Function to toggle phase reversal of a channel
#	channel: Index of channel
def toggle_phase(channel):
	if lib_zynmixer:
		lib_zynmixer.togglePhase(channel)

#	Function to set solo for a channel
#	channel: Index of channel
#	solo: Solo state (True to solo)
def	set_solo(channel, solo):
	if lib_zynmixer:
		lib_zynmixer.setSolo(channel, solo)

#	Function to get solo for a channel
#	channel: Index of channel
#	returns: Solo state (True if solo)
def	get_solo(channel):
	if lib_zynmixer:
		return lib_zynmixer.getSolo(channel) == 1
	else:
		return True

#	Function to toggle mute of a channel
#	channel: Index of channel
def toggle_solo(channel):
	if lib_zynmixer:
		if get_solo(channel):
			set_solo(channel, False)
		else:
			set_solo(channel, True)

#	Function to mono a channel
#	channel: Index of channel
#	mono: Mono state (True to solo)
def	set_mono(channel, mono):
	if lib_zynmixer:
		lib_zynmixer.setMono(channel, mono)

#	Function to get mono for a channel
#	channel: Index of channel
#	returns: Mono state (True if mono)
def	get_mono(channel):
	if lib_zynmixer:
		return lib_zynmixer.getMono(channel) == 1
	else:
		return True

#	Function to toggle mono of a channel
#	channel: Index of channel
def toggle_mono(channel):
	if lib_zynmixer:
		if get_mono(channel):
			set_mono(channel, False)
		else:
			set_mono(channel, True)

#	Function to reset parameters of a channel to default
#	channel: Index of channel
def reset(channel):
	if lib_zynmixer:
		lib_zynmixer.reset(channel)

#	Function to check if channel has audio routed to its input
#	channel: Index of channel
#	returns: True if routed
def is_channel_routed(channel):
	if lib_zynmixer:
		return (lib_zynmixer.isChannelRouted(channel) != 0)
	return False

#	Function to get peak programme level for a channel
#	channel: Index of channel
#	leg: 0 for A-leg (left), 1 for B-leg (right)
#	returns: Peak programme level
def get_dpm(channel, leg):
	if lib_zynmixer:
		return lib_zynmixer.getDpm(channel, leg)
	return -200.0

#	Function to get peak programme hold level for a channel
#	channel: Index of channel
#	leg: 0 for A-leg (left), 1 for B-leg (right)
#	returns: Peak programme hold level
def get_dpm_hold(channel, leg):
	if lib_zynmixer:
		return lib_zynmixer.getDpmHold(channel, leg)
	return -200.0

#	Function to enable or disable digital peak meters
#	enable: True to enable
def enable_dpm(enable):
	if enable:
		lib_zynmixer.enableDpm(1)
	else:
		lib_zynmixer.enableDpm(0)

#	Function to add OSC client registration
#	client: IP address of OSC client
def add_osc_client(client):
	if lib_zynmixer:
		lib_zynmixer.addOscClient(c_char_p(client.encode('utf-8')))

#	Function to remove OSC client registration
#	client: IP address of OSC client
def remove_osc_client(client):
	if lib_zynmixer:
		lib_zynmixer.removeOscClient(c_char_p(client.encode('utf-8')))

#-------------------------------------------------------------------------------
