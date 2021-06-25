# This Python file uses the following encoding: utf-8
import os
from pathlib import Path
import sys

from PySide2.QtCore import Qt, QObject, Slot, Signal, Property, QUrl, QAbstractListModel, QModelIndex, QByteArray, QStringListModel
from PySide2.QtGui import QGuiApplication
from PySide2.QtQml import QQmlApplicationEngine

#HACK
sys.path.insert(1, '/zynthian/zynthian-ui/')
from zyncoder import *
from zyngine import zynthian_layer

class ControllerWrapper(QObject):
    def __init__(self, parent=None):
        super(ControllerWrapper, self).__init__(parent)
        self.controller = None

    def set_controller(self, controller):
        self.controller = controller
        self.controller_changed.emit()

    def get_name(self):
        if self.controller:
            return self.controller.name
        else:
            return "None"

    def get_value(self):
        if self.controller:
            return self.controller.value
        else:
            return 0

    def get_value_max(self):
        if self.controller:
            return self.controller.value_max
        else:
            return 0

    def get_value_type(self):
        if self.controller:
            if self.controller.is_toggle:
                return "bool"
            elif self.controller.is_interger:
                return "int"
            elif self.controller.is_logaritmic:
                return "log"
            else:
                return "real"
        else:
            return "int"

    controller_changed = Signal()

    name = Property(str, get_name, notify = controller_changed)
    value = Property(float, get_value, notify = controller_changed)
    value_max = Property(float, get_value_max, notify = controller_changed)
    value_type = Property(str, get_value_type, notify = controller_changed)

class ControlWrapper(QObject):

    def __init__(self, zyngui, parent=None):
        super(ControlWrapper, self).__init__(parent)

        self.zyngui = zyngui
        self.curlayer = zyngui.curlayer
        self.control = zyngui.screens['control']
        self.screen_names_model = QStringListModel()
        self.controller_wrapper_1 = ControllerWrapper()
        self.controller_wrapper_2 = ControllerWrapper()
        self.controller_wrapper_3 = ControllerWrapper()
        self.controller_wrapper_4 = ControllerWrapper()

    active_screen_index_changed = Signal()
    controller_1_changed = Signal()
    controller_2_changed = Signal()
    controller_3_changed = Signal()
    controller_4_changed = Signal()

    def get_active_screen_index(self):
        return self.zyngui.curlayer.active_screen_index

    def set_active_screen_index(self, index):
        self.zyngui.curlayer.set_active_screen_index(index)

        l = []
        for key in self.zyngui.curlayer.ctrl_screens_dict.keys():
            l.append(key)

        print(l[index])
        print(self.zyngui.curlayer.ctrl_screens_dict[l[index]])

        print(self.zyngui.curlayer.ctrl_screens_dict[l[index]][0].name)
        self.controller_wrapper_1.set_controller(self.zyngui.curlayer.ctrl_screens_dict[l[index]][0])
        self.controller_wrapper_2.set_controller(self.zyngui.curlayer.ctrl_screens_dict[l[index]][1])
        self.controller_wrapper_3.set_controller(self.zyngui.curlayer.ctrl_screens_dict[l[index]][2])
        self.controller_wrapper_4.set_controller(self.zyngui.curlayer.ctrl_screens_dict[l[index]][3])

        self.active_screen_index_changed.emit()

    def get_screen_names(self):
        print(self.zyngui.curlayer.ctrl_screens_dict.keys())
        l = []
        for key in self.zyngui.curlayer.ctrl_screens_dict.keys():
            l.append(key)
        self.screen_names_model.setStringList(l)
        return self.screen_names_model

    def get_controller_1(self):
        return self.controller_wrapper_1

    def get_controller_2(self):
        return self.controller_wrapper_2

    def get_controller_3(self):
        return self.controller_wrapper_3

    def get_controller_4(self):
        return self.controller_wrapper_4

    active_screen_index = Property(int, get_active_screen_index, set_active_screen_index, notify = active_screen_index_changed)
    screen_names = Property(QObject, get_screen_names)

    controller1 = Property(QObject, get_controller_1, notify = controller_1_changed)
    controller2 = Property(QObject, get_controller_2, notify = controller_2_changed)
    controller3 = Property(QObject, get_controller_3, notify = controller_3_changed)
    controller4 = Property(QObject, get_controller_4, notify = controller_4_changed)
