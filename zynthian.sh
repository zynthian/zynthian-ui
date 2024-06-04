#!/bin/bash
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Start Script
# 
# Start all services needed by zynthian and the zynthian UI
# 
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
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
	source "$ZYNTHIAN_SYS_DIR/scripts/zynthian_envars_extended.sh"

	if [ -z "$ZYNTHIAN_SCRIPT_MIDI_PROFILE" ]; then
		source "$ZYNTHIAN_MY_DATA_DIR/midi-profiles/default.sh"
	else
		source "$ZYNTHIAN_SCRIPT_MIDI_PROFILE"
	fi

	if [ -f "$ZYNTHIAN_CONFIG_DIR/zynthian_custom_config.sh" ]; then
		source "$ZYNTHIAN_CONFIG_DIR/zynthian_custom_config.sh"
	fi
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


function splash_zynthian_message() {
	zynthian_message=$1

	img_fpath=$2
	[ "$img_fpath" ] || img_fpath="$ZYNTHIAN_CONFIG_DIR/img/fb_zynthian_boot.png"

	# Generate a splash image with the message...
	img_w=`identify -format '%w' $img_fpath`
	img_h=`identify -format '%h' $img_fpath`
	if [[ "${#zynthian_message}" > "40" ]]; then
			font_size=$(expr $img_w / 36)
	else
			font_size=$(expr $img_w / 28)
	fi
	strlen=$(expr ${#zynthian_message} \* $font_size / 2)
	pos_x=$(expr $img_w / 2 - $strlen / 2)
	pos_y=$(expr $img_h \* 10 / 100)
	[[ "$pos_x" > "0" ]] || pos_x=5
	convert -strip -family \"$ZYNTHIAN_UI_FONT_FAMILY\" -pointsize $font_size -fill white -draw "text $pos_x,$pos_y \"$zynthian_message\"" $img_fpath $ZYNTHIAN_CONFIG_DIR/img/fb_zynthian_message.png

	# Display error image
	xloadimage -fullscreen -onroot $ZYNTHIAN_CONFIG_DIR/img/fb_zynthian_message.png
}


function splash_zynthian_error() {
	# Generate an error splash image...
	splash_zynthian_message "$1" "$ZYNTHIAN_CONFIG_DIR/img/fb_zynthian_error.png"
}


function splash_zynthian_error_exit_ip() {
	# Grab exit code if set
	zynthian_error=$1
	[ "$zynthian_error" ] || zynthian_error="???"

	case $zynthian_error in
		1)
			message="Software"
		;;
		200)
			message="Zyncore"
		;;
		201)
			message="Control I/O"
		;;
		202)
			message="Audio/MIDI"
		;;
		203)
			message="CV/Gate"
		;;
		*)
			message="ErrCode $zynthian_error"
		;;
	esac

	# Get the IP
	#zynthian_ip=`ip route get 1 | awk '{print $NF;exit}'`
	zynthian_ip=$(hostname -I | cut -d " " -f1)

	# Format the message
	zynthian_message="IP:$zynthian_ip    $message"

	# Generate an error splash image with the IP & exit code...
	splash_zynthian_message "$zynthian_message" "$ZYNTHIAN_CONFIG_DIR/img/fb_zynthian_error.png"
}

function splash_zynthian_last_message() {
	xloadimage -fullscreen -onroot $ZYNTHIAN_CONFIG_DIR/img/fb_zynthian_message.png
}

function start_wifi_ap() {
	readarray -t connected_devices <<< $(nmcli --terse c show | cut -d : -f 4 | tr -s '\n' | tr -s 'lo\n')
	if [[ "${#connected_devices[*]}" < "2" ]]; then
		nmcli radio wifi on
		nmcli con up "zynthian-ap"
	fi
}

powersave_control.sh off

#------------------------------------------------------------------------------
# Run Hardware Test
#------------------------------------------------------------------------------

export ZYNTHIAN_HW_TEST=""
if [ -n "${ZYNTHIAN_HW_TEST}" ]; then
	echo "Running hardware test:  $ZYNTHIAN_HW_TEST"
	result=$($ZYNTHIAN_SYS_DIR/sbin/zynthian_hw_test.py $ZYNTHIAN_HW_TEST | tail -1)
	res=${result%:*}
	message=${result#*:}
	if [[ "$res" == "OK" ]]; then
		splash_zynthian_message "$result"
	else
		splash_zynthian_error "$message"
	fi
	sleep 3600
	exit
fi

#------------------------------------------------------------------------------
# Test splash screen generator
#------------------------------------------------------------------------------

#splash_zynthian_message "Testing Splash Screen Generator..."
#sleep 10
#exit

#------------------------------------------------------------------------------
# If needed, generate splash screen images
#------------------------------------------------------------------------------

if [ ! -d $ZYNTHIAN_CONFIG_DIR/img ]; then
	$ZYNTHIAN_SYS_DIR/sbin/generate_fb_splash.sh
fi

#------------------------------------------------------------------------------
# Build zyncore if needed
#------------------------------------------------------------------------------

if [ ! -f "$ZYNTHIAN_DIR/zyncoder/build/libzyncore.so" ]; then
	splash_zynthian_message "Building zyncore. Please wait..."
	load_config_env
	$ZYNTHIAN_DIR/zyncoder/build.sh
fi

#------------------------------------------------------------------------------
# Detect first boot
#------------------------------------------------------------------------------

if [[ "$(systemctl is-enabled first_boot)" == "enabled" ]]; then
	echo "Running first boot..."
	splash_zynthian_message "Configuring your zynthian. Time to relax before the waves..."
	sleep 1800
	splash_zynthian_error "It takes too long! Bad sdcard/image, poor power supply..."
	sleep 3600000
	exit
fi

#------------------------------------------------------------------------------
# Run Zynthian-UI
#------------------------------------------------------------------------------

splash_zynthian
load_config_env

while true; do

	# Start Zynthian GUI & Synth Engine
	cd $ZYNTHIAN_UI_DIR
	./zynthian_main.py
	status=$?

	# Proccess output status
	case $status in
		0)
			#splash_zynthian_message "Powering Off..."
			splash_zynthian_last_message
			poweroff
			backlight_control.sh off
			break
		;;
		100)
			#splash_zynthian_message "Rebooting..."
			splash_zynthian_last_message
			reboot
			break
		;;
		101)
			#splash_zynthian_message "Exiting..."
			splash_zynthian_last_message
			backlight_control.sh off
			break
		;;
		102)
			#splash_zynthian_message "Restarting UI..."
			splash_zynthian_last_message
			load_config_env
			sleep 10
		;;
		*)
			splash_zynthian_error_exit_ip $status
			load_config_env
			start_wifi_ap
			sleep 10
		;;
	esac
done

#------------------------------------------------------------------------------
