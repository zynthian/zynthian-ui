from zyngine import zynthian_state_manager
from zyngui import zynthian_gui_config

class zyn_headless:

    def __init__(self):
        self.state_manager = zynthian_state_manager.zynthian_state_manager()
        self.chain_manager = self.state_manager.chain_manager

        if zynthian_gui_config.restore_last_state:
            snapshot_loaded = self.screens['snapshot'].load_last_state_snapshot()

        self.state_manager.init_midi()
        self.state_manager.init_midi_services()
        self.state_manager.zynautoconnect()

	    # Run autoconnect if needed
        self.state_manager.zynautoconnect_do()

zh = zyn_headless()