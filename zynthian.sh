#!/bin/bash
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Start Script
# 
# Start all services needed by zynthian and the zynthian UI
# 
# Copyright (C) 2015-2016 Fernando Moyano <jofemodo@zynthian.org>
#
#******************************************************************************
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
#******************************************************************************

ZYNTHIAN_DIR="/home/pi/zynthian"

#------------------------------------------------------------------------------
# Some Functions
#------------------------------------------------------------------------------

function screentouch_on() {
	# Export GPIO for Backlight Control (old version of PiTFT driver uses GPIO#252)
	echo 508 > /sys/class/gpio/export
	# Turn On Display (Backlight)
	echo 'in' > /sys/class/gpio/gpio508/direction
	#echo '1' > /sys/class/gpio/gpio508/value
}

function screentouch_off() {
	# Turn Off Display (Backlight)
	echo 'out' > /sys/class/gpio/gpio508/direction
	#echo '0' > /sys/class/gpio/gpio508/value
}

function screensaver_off() {
	# Don't activate screensaver
	xset s off
	# Disable DPMS (Energy Star) features.
	xset -dpms
	# Don't blank the video device
	xset s noblank
}

function splash_zynthian() {
	if [ -c /dev/fb1 ]; then
		cat ./img/fb1_zynthian.raw > /dev/fb1
	fi  
}

function splash_zynthian_error() {
	if [ -c /dev/fb1 ]; then
		cat ./img/fb1_zynthian_error.raw > /dev/fb1
	fi  
}

function jack_audio_start() {
	# Start jack-audio server
	/usr/bin/jackd -dalsa -dhw:0 -r48000 -p128 -n2 &
}

function jack_audio_stop() {
	# Stop jack-audio server
	killall a2jmidid
}

function a2j_midi_start() {
	# Start alsa2jack midi router
	/usr/bin/a2jmidid --export-hw &
}

function a2j_midi_stop() {
	# Stop alsa2jack midi router
	killall a2jmidid
}

function autoconnector_start() {
	# Start Autoconnector
	./zynthian_autoconnect_jack.py > /var/log/zynthian_autoconnect.log 2>&1 &
	#2>&1 &
}

function autoconnector_stop() {
	killall zynthian_autoconnect_jack.py
}

function ttymidi_start() {
	# Start ttymidi (MIDI UART interface)
	./software/ttymidi/ttymidi -s /dev/ttyAMA0 -b 38400 &
}

function ttymidi_stop() {
	killall ttymidi
}

#------------------------------------------------------------------------------
# Main Program
#------------------------------------------------------------------------------

cd $ZYNTHIAN_DIR/zynthian-ui

jack_audio_start

screentouch_on
screensaver_off

autoconnector_start
ttymidi_start

sleep 2

a2j_midi_start

# Start Zynthian GUI & Synth Engine
./zynthian_gui.py
status=$?

if test $status -eq 0
then
	splash_zynthian
	a2j_midi_stop
	jack_audio_stop
	ttymidi_stop
	autoconnector_stop
	screentouch_off
	poweroff
else
	splash_zynthian_error
fi

#------------------------------------------------------------------------------
