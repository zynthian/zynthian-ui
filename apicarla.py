#!/usr/bin/python3
# -*- coding: utf-8 -*-
#********************************************************************
# ZYNTHIAN PROJECT: Zynthian Carla API testing
# 
# Testing Carla API
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

from time import sleep
from carla.carla_backend import *

carla = CarlaHostDLL("/usr/local/lib/carla/libcarla_standalone2.so")
carla.set_engine_option(ENGINE_OPTION_PROCESS_MODE, ENGINE_PROCESS_MODE_PATCHBAY,"yes")
carla.engine_init("JACK", "carla-zynthian")
#carla.engine_init_bridge("zyncar", "zrtcar", "nrtcar", "nrtcar1", "carla-zynthian")
carla.load_project("/home/txino/Zauber/zynthian/zynthian-data/carla/kars_int.carxp")

# call idle at regular intervals to dispatch osc and gui events

i=0
while i<10000:
	carla.engine_idle()
	sleep(0.01)
	i+=1

# when done:
carla.engine_close()
