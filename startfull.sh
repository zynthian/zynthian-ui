#!/bin/sh

export DISPLAY=:0
export QT_QUICK_CONTROLS_MOBILE=1
export QT_SCALE_FACTOR=1.2

python3 zynthian_qt_gui.py
