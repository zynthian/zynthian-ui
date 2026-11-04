import tkinter
import logging
from zyngui import zynthian_widget_base
from zyngui import zynthian_widget_drawbar
from zyngine.zynthian_engine_setbfree import *
from zyngui import zynthian_gui_config

class zynthian_widget_setbfree(zynthian_widget_drawbar.zynthian_widget_drawbar):
    pass

    def __init__(self, parent):
        super().__init__(parent)
        self.drawbars = ['DB 16',
                         'DB 5 1/3',
                         'DB 8',
                         'DB 4',
                         'DB 2 2/3',
                         'DB 2',
                         'DB 1 3/5',
                         'DB 1 1/3',
                         'DB 1']

