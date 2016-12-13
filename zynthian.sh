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

#export ZYNTHIAN_LOG_LEVEL=10			# 10=DEBUG, 20=INFO, 30=WARNING, 40=ERROR, 50=CRITICAL
#export ZYNTHIAN_RAISE_EXCEPTIONS=0
export ZYNTHIAN_DIR="/zynthian"
export FRAMEBUFFER="/dev/fb1"

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
	if [ -c $FRAMEBUFFER ]; then
		cat ./img/fb1_zynthian.raw > $FRAMEBUFFER
	fi  
}

function splash_zynthian_error() {
	if [ -c $FRAMEBUFFER ]; then
		cat ./img/fb1_zynthian_error.raw > $FRAMEBUFFER
	fi  
}

function a2j_midi_start() {
	# Start alsa2jack midi router
	while [ 1 ]; do 
		/usr/bin/a2jmidid --export-hw
		sleep 1
	done
}

function a2j_midi_stop() {
	# Stop alsa2jack midi router
	killall a2jmidid
}

function alsa_in_start() {
	# Start alsa_in audio input
	while [ 1 ]; do 
		/usr/bin/alsa_in -d hw:2
		sleep 1
	done
}

function alsa_in_stop() {
	# Stop alsa_in audio input
	killall alsa_in
}

function aubionotes_start() {
	# Start aubionotes (audio => MIDI)
	while [ 1 ]; do 
		/usr/bin/aubionotes -O complex -t 0.5 -s -88  -p yinfft -l 0.5
		sleep 1
	done
}

function aubionotes_stop() {
	# Stop aubionotes (audio => MIDI)
	killall aubionotes
}

function zynthian_stop() {
	if [ ! -z "$ZYNTHIAN_AUBIO" ]; then
		aubionotes_stop
		alsa_in_stop
	fi
	a2j_midi_stop
}

#------------------------------------------------------------------------------
# Main Program
#------------------------------------------------------------------------------

cd $ZYNTHIAN_DIR/zynthian-ui

screentouch_on
screensaver_off

a2j_midi_start &
if [ ! -z "$ZYNTHIAN_AUBIO" ]; then
	alsa_in_start &
	aubionotes_start &
fi

while true; do
	# Start Zynthian GUI & Synth Engine
	./zynthian_gui.py
	status=$?

	# Proccess output status
	case $status in
		0)
			splash_zynthian
			zynthian_stop
			screentouch_off
			poweroff
			break
		;;
		100)
			splash_zynthian
			zynthian_stop
			screentouch_off
			reboot
			break
		;;
		101)
			splash_zynthian
			zynthian_stop
			break
		;;
		102)
			splash_zynthian
			sleep 1
		;;
		*)
			splash_zynthian_error
			sleep 3
		;;
	esac  
done

#------------------------------------------------------------------------------
