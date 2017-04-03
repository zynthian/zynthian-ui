#!/usr/bin/python3
# -*- coding: utf-8 -*-
#********************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI configuration
# 
# Copyright (C) 2015-2016 Fernando Moyano <jofemodo@zynthian.org>
#
#********************************************************************
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
#********************************************************************

import logging

#********************************************************************

# Log level and debuging
#log_level=logging.DEBUG
log_level=logging.WARNING
raise_exceptions=False

# Wiring layout
hw_version="PROTOTYPE-4"

# Screen Size => Autodetect if None
width=320
height=240

# Topbar Height
topbar_height=24

# Color Scheme
color_bg="#000000"
color_tx="#ffffff"
color_on="#ff0000"
color_panel_bg="#3a424d"

# Fonts
#font_family="Helvetica" #=> the original ;-)
#font_family="Economica" #=> small
#font_family="Orbitron" #=> Nice, but too strange
#font_family="Abel" #=> Quite interesting, also "Strait"
font_family="Audiowide"
font_topbar=(font_family,11)
font_listbox=(font_family,10)
font_ctrl_title_maxsize=11
