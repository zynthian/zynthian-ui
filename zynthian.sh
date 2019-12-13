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

#------------------------------------------------------------------------------
# Some Functions
#------------------------------------------------------------------------------

function load_config_env() {
	if [ -d "$ZYNTHIAN_CONFIG_DIR" ]; then
		source "$ZYNTHIAN_CONFIG_DIR/zynthian_envars.sh"
	else
		source "$ZYNTHIAN_SYS_DIR/scripts/zynthian_envars.sh"
	fi

	if [ ! -z "$ZYNTHIAN_SCRIPT_MIDI_PROFILE" ]; then
		source "$ZYNTHIAN_SCRIPT_MIDI_PROFILE"
	else
		source "$ZYNTHIAN_MY_DATA_DIR/midi-profiles/default.sh"
	fi

	if [ -f "$ZYNTHIAN_CONFIG_DIR/zynthian_custom_config.sh" ]; then
		source "$ZYNTHIAN_CONFIG_DIR/zynthian_custom_config.sh"
	fi
}

function backlight_on() {
	# Turn On Display Backlight
	#echo 0 > /sys/class/backlight/soc:backlight/bl_power
	#echo 0 > /sys/class/backlight/fb_ili9486/bl_power
	echo 0 > /sys/class/backlight/*/bl_power
}

function backlight_off() {
	# Turn Off Display Backlight
	#echo 1 > /sys/class/backlight/soc:backlight/bl_power
	#echo 1 > /sys/class/backlight/fb_ili9486/bl_power
	echo 1 > /sys/class/backlight/*/bl_power
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
		cat $ZYNTHIAN_CONFIG_DIR/img/fb_zynthian_boot.raw > $FRAMEBUFFER
	fi  
}

function splash_zynthian_error() {
	if [ -c $FRAMEBUFFER ]; then
		#cat $ZYNTHIAN_CONFIG_DIR/img/fb_zynthian_error.raw > $FRAMEBUFFER
		zynthian_ip=`ip route get 1 | awk '{print $NF;exit}'`
		convert -pointsize 14 -fill black -draw "text 110,225 \"IP: $zynthian_ip\"" $ZYNTHIAN_UI_DIR/img/zynthian_logo_error.png $ZYNTHIAN_CONFIG_DIR/img/zynthian_logo_error_ip.png
		xloadimage -fullscreen -onroot $ZYNTHIAN_CONFIG_DIR/img/zynthian_logo_error_ip.png
	fi  
}

#------------------------------------------------------------------------------
# Main Program
#------------------------------------------------------------------------------

cd $ZYNTHIAN_UI_DIR

backlight_on
screensaver_off

while true; do
	#Load Config Environment
	load_config_env

	# Start Zynthian GUI & Synth Engine
	./zynthian_gui.py
	status=$?

	# Proccess output status
	case $status in
		0)
			splash_zynthian
			poweroff
			break
		;;
		100)
			splash_zynthian
			reboot
			break
		;;
		101)
			splash_zynthian
			backlight_off
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
