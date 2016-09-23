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

function scaling_governor_performance() {
	for cpu in /sys/devices/system/cpu/cpu[0-9]*; do 
		echo -n performance | tee $cpu/cpufreq/scaling_governor
	done
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
	#/usr/bin/jackd -P 70 -t 2000 -s -d alsa -d hw:0 -r 44100 -p 256 -n 2
	#/usr/bin/jackd -P 70 -t 2000 -s -d alsa -d hw:0 -r 44100 -p 256 -n 2 -X seq
	/usr/bin/jackd -P 70 -t 2000 -s -d alsa -d hw:0 -r 44100 -p 256 -n 2 -X raw
}

function jack_audio_stop() {
	# Stop jack-audio server
	killall jackd
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

function autoconnector_start() {
	# Start Autoconnector
	./zynthian_autoconnect_jack.py > /dev/null 2>&1
	#./zynthian_autoconnect_jack.py > /var/log/zynthian_autoconnect.log 2>&1
}

function autoconnector_stop() {
	killall zynthian_autoconnect_jack.py
}

function ttymidi_start() {
	# Start ttymidi (MIDI UART interface)
	while [ 1 ]; do 
		/usr/local/bin/ttymidi -s /dev/ttyAMA0 -b 38400
		sleep 1
	done
}

function ttymidi_stop() {
	killall ttymidi
}

function zynthian_stop() {
	autoconnector_stop
	if [ ! -z "$ZYNTHIAN_AUBIO" ]; then
		aubionotes_stop
		alsa_in_stop
	fi
	a2j_midi_stop
	ttymidi_stop
	jack_audio_stop
}

#------------------------------------------------------------------------------
# Main Program
#------------------------------------------------------------------------------

cd $ZYNTHIAN_DIR/zynthian-ui

screentouch_on
screensaver_off
scaling_governor_performance

jack_audio_start &
ttymidi_start &
#a2j_midi_start &
if [ ! -z "$ZYNTHIAN_AUBIO" ]; then
	alsa_in_start &
	aubionotes_start &
fi
autoconnector_start &

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
