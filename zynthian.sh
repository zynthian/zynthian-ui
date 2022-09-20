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
	if [ -f /sys/class/backlight/*/bl_power ]; then
		echo 0 > /sys/class/backlight/*/bl_power
	fi
}

function backlight_off() {
	# Turn Off Display Backlight
	#echo 1 > /sys/class/backlight/soc:backlight/bl_power
	#echo 1 > /sys/class/backlight/fb_ili9486/bl_power
	if [ -f /sys/class/backlight/*/bl_power ]; then
		echo 1 > /sys/class/backlight/*/bl_power
	fi
}

function screensaver_off() {
	# Don't activate screensaver
	xset s off
	# Disable DPMS (Energy Star) features.
	xset -dpms
	# Don't blank the video device
	xset s noblank
}


function raw_splash_zynthian() {
	if [ -c $FRAMEBUFFER ]; then
		cat $ZYNTHIAN_CONFIG_DIR/img/fb_zynthian_boot.raw > $FRAMEBUFFER
	fi  
}


function raw_splash_zynthian_error() {
	if [ -c $FRAMEBUFFER ]; then
		cat $ZYNTHIAN_CONFIG_DIR/img/fb_zynthian_error.raw > $FRAMEBUFFER
	fi  
}


function splash_zynthian() {
	xloadimage -fullscreen -onroot $ZYNTHIAN_CONFIG_DIR/img/fb_zynthian_boot.png
}


function splash_zynthian_error() {
	#Grab exit code if set
	zynthian_error=$1
	[ "$zynthian_error" ] || zynthian_error="???"
	#Get the IP
	#zynthian_ip=`ip route get 1 | awk '{print $NF;exit}'`
	zynthian_ip=`ip route get 1 | sed 's/^.*src \([^ ]*\).*$/\1/;q'`

	#Generate an error image with the IP ...
	img_fpath="$ZYNTHIAN_CONFIG_DIR/img/fb_zynthian_error.png"
	img_w=`identify -format '%w' $img_fpath`
	img_h=`identify -format '%h' $img_fpath`
	pos_x=$(expr $img_w \* 100 / 350)
	pos_y=$(expr $img_h \* 100 / 110)
	font_size=$(expr $img_w / 24)
	convert -strip -pointsize $font_size -fill white -draw "text $pos_x,$pos_y \"Exit:$zynthian_error     IP:$zynthian_ip\"" $img_fpath $ZYNTHIAN_CONFIG_DIR/img/fb_zynthian_error_ip.png
	
	#Display error image
	xloadimage -fullscreen -onroot $ZYNTHIAN_CONFIG_DIR/img/fb_zynthian_error_ip.png
}

#------------------------------------------------------------------------------
# Main Program
#------------------------------------------------------------------------------

cd $ZYNTHIAN_UI_DIR

backlight_on
splash_zynthian
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
			sleep 10 #FIXME: Long wait to work around slow stopping threads causing xruns after restart
		;;
		*)
			splash_zynthian_error $status
			sleep 3
		;;
	esac
done

#------------------------------------------------------------------------------
