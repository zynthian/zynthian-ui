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

        lib_zyncore_init()

        # ------------------------------------------------------------------------------
        # Initialize state manager
        # ------------------------------------------------------------------------------

        self.state_manager = zynthian_state_manager.zynthian_state_manager()

        # ------------------------------------------------------------------------------
        # Start autoconnect
        # ------------------------------------------------------------------------------

        autoconnect.start(self.state_manager)

        # ------------------------------------------------------------------------------
        # Main loop
        # ------------------------------------------------------------------------------

        self.running = True
        try:
            while self.running:
                sleep(0.2)
        except KeyboardInterrupt:
            # Use a guarded shutdown so a Ctrl+C exits cleanly instead of
            # propagating an uncaught KeyboardInterrupt traceback.
            logging.info("Caught keyboard interrupt, stopping headless engine...")
            self.stop()

    def stop(self):
        """Cleanly stop the headless engine and its subsystems."""
        self.running = False
        try:
            autoconnect.stop()
        except Exception as e:
            logging.error(f"Error stopping autoconnect: {e}")
        try:
            self.state_manager.stop()
        except Exception as e:
            logging.error(f"Error stopping state manager: {e}")


if __name__ == "__main__":
    zyn_headless()
