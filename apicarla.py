#!/usr/bin/python3
# -*- coding: utf-8 -*-

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
