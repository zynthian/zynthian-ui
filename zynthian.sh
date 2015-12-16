#!/bin/bash

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

function autoconnector_start() {
	# Start Autoconnector
	./zynthian_autoconnect.py > /var/log/zynthian_autoconnect.log 2>&1 &
	#2>&1 &
}

function ttymidi_start() {
	# Start ttymidi (MIDI UART interface)
	./software/ttymidi/ttymidi -s /dev/ttyAMA0 -b 38400 &
}

#------------------------------------------------------------------------------
# Main Program
#------------------------------------------------------------------------------

cd $ZYNTHIAN_DIR

screentouch_on
screensaver_off

autoconnector_start
ttymidi_start

# Start Zynthian GUI & Synth Engine
./zynthian_gui.py
status=$?

if test $status -eq 0
then
	splash_zynthian
	screentouch_off
	poweroff
else
	splash_zynthian_error
fi

#------------------------------------------------------------------------------