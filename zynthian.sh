#!/bin/bash

# don't activate screensaver
xset s off
# disable DPMS (Energy Star) features.
xset -dpms
# don't blank the video device
xset s noblank

# Start Autoconnector
./zynthian_autoconnect.py &

# Start Zynthian GUI & Synth Engine
./zynthian_gui.py
