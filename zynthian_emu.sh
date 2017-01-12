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

ZYNTHIAN_DIR="/zynthian"

#------------------------------------------------------------------------------
# Some Functions
#------------------------------------------------------------------------------

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

function zynthian_start() {
	if [ ! -z "$ZYNTHIAN_AUBIO" ]; then
		alsa_in_start &
		aubionotes_start &
	fi
}

function zynthian_stop() {
	if [ ! -z "$ZYNTHIAN_AUBIO" ]; then
		aubionotes_stop
		alsa_in_stop
	fi
}

#------------------------------------------------------------------------------
# Main Program
#------------------------------------------------------------------------------

cd $ZYNTHIAN_DIR/zynthian-ui

zynthian_start

while true; do
	# Start Zynthian GUI & Synth Engine
	cd ../zynthian-emuface
	./zynthian_emuface.py
	status=$?

	# Proccess output status
	case $status in
		0)
			zynthian_stop
			#poweroff
			break
		;;
		100)
			zynthian_stop
			#reboot
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
