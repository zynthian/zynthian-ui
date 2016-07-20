#!/bin/bash
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Emulator Start Script
# 
# Start all services needed by zynthian emulator
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

function scaling_governor_performance() {
	for cpu in /sys/devices/system/cpu/cpu[0-9]*; do 
		echo -n performance | tee $cpu/cpufreq/scaling_governor
	done
}

function jack_audio_start() {
	# Start jack-audio server
	/usr/bin/jackd -P70 -p16 -t2000 -s -dalsa -dhw:0 -r44100 -p256 -n2
	#/usr/bin/jackd -P70 -p16 -t2000 -s -dalsa -dhw:0 -r44100 -p256 -n2 -Xseq
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

sudo xauth merge /home/pi/.Xauthority

scaling_governor_performance

jack_audio_start &
ttymidi_start &
a2j_midi_start &
if [ ! -z "$ZYNTHIAN_AUBIO" ]; then
	alsa_in_start &
	aubionotes_start &
fi
autoconnector_start &

while true; do
	# Start Zynthian GUI & Synth Engine
	cd ../zynthian-emuface
	./zynthian_emuface.py
	status=$?

	# Proccess output status
	case $status in
		0)
			zynthian_stop
			break
		;;
		100)
			zynthian_stop
			break
		;;
		101)
			zynthian_stop
			break
		;;
		102)
			sleep 1
		;;
		*)
			sleep 3
		;;
	esac  
done

#------------------------------------------------------------------------------
