from zyncoder.zyncore import lib_zyncore_init
from zyngui import zynthian_gui_config
from zyngine import zynthian_state_manager
import autoconnect

import logging
from time import sleep


class zyn_headless:

    def __init__(self):

        # ------------------------------------------------------------------------------
        # Initialize and config control I/O subsystem: switches, analog I/O, ...
        # ------------------------------------------------------------------------------
        try:
            lib_zyncore = lib_zyncore_init()
            zynthian_gui_config.num_zynswitches = lib_zyncore.get_num_zynswitches()
            zynthian_gui_config.last_zynswitch_index = lib_zyncore.get_last_zynswitch_index()
            zynthian_gui_config.num_zynpots = lib_zyncore.get_num_zynpots()
            zynthian_gui_config.config_zynswitch_timing()
            zynthian_gui_config.config_custom_switches()
            zynthian_gui_config.config_zynaptik()
            zynthian_gui_config.config_zyntof()
        except Exception as e:
            logging.error(
                "ERROR configuring control I/O subsytem: {}".format(e))

        self.state_manager = zynthian_state_manager.zynthian_state_manager()
        self.chain_manager = self.state_manager.chain_manager

        if zynthian_gui_config.restore_last_state:
            snapshot_loaded = self.state_manager.load_snapshot(
                "/zynthian/zynthian-my-data/snapshots/last_state.zss")

        self.state_manager.init_midi()
        self.state_manager.init_midi_services()
        autoconnect.autoconnect()

        while True:
            sleep(1)


zh = zyn_headless()
