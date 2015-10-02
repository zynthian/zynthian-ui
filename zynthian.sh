#!/bin/bash

# Export GPIO for Backlight Control (old version of PiTFT driver uses GPIO#252)
echo 508 > /sys/class/gpio/export

# Turn On Display (Backlight)
echo 'in' > /sys/class/gpio/gpio508/direction
#echo '1' > /sys/class/gpio/gpio508/value

# Don't activate screensaver
xset s off
# Disable DPMS (Energy Star) features.
xset -dpms
# Don't blank the video device
xset s noblank

# Start Autoconnector
./zynthian_autoconnect.py > /var/log/zynthian_autoconnect.log 2>&1 &
#2>&1 &

# Start ttymidi (MIDI UART interface)
./software/ttymidi/ttymidi -s /dev/ttyAMA0 -b 38400 &

# Start Zynthian GUI & Synth Engine
./zynthian_gui.py

# Turn Off Display (Backlight)
echo 'out' > /sys/class/gpio/gpio508/direction
#echo '0' > /sys/class/gpio/gpio508/value
