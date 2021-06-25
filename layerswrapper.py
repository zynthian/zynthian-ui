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

class LayersListModel(QAbstractListModel):
    ENGINE_NAME = Qt.UserRole + 1
    BANK_NAME = Qt.UserRole + 2
    PRESET_PATH = Qt.UserRole + 3

    def __init__(self, zyngui, parent=None):
        super(LayersListModel, self).__init__(parent)

        self.zyngui = zyngui
        self.layers_manager = zyngui.screens['layer']

    @Slot('int')
    def set_current_layer(self, row):
        if row > len(self.layers_manager.root_layers) or row < 0:
            return

        layer = self.layers_manager.root_layers[row]
        self.zyngui.layer_control(layer)

    def roleNames(self):
        keys = {
            LayersListModel.ENGINE_NAME : QByteArray(b'engine_name'),
            LayersListModel.BANK_NAME : QByteArray(b'bank_name'),
            LayersListModel.PRESET_PATH : QByteArray(b'preset_path'),
            }
        return keys

    def rowCount(self, index):
        return len(self.layers_manager.root_layers)

    def data(self, index, role):
        if not index.isValid():
            return None

        if index.row() > len(self.layers_manager.root_layers):
            return None

        layer = self.layers_manager.root_layers[index.row()]
        if role == LayersListModel.ENGINE_NAME:
            return layer.engine.name
        elif role == LayersListModel.BANK_NAME:
            return layer.bank_name
        elif role == LayersListModel.PRESET_PATH:
            return layer.get_presetpath()
        else:
            return None




class LayerWrapper(QObject):
    def __init__(self, parent=None):
        super(LayerWrapper, self).__init__(parent)
        self.layer = None;
        self.bank_list_model = QStringListModel()
        self.preset_list_model = QStringListModel()

    def set_layer(self, layer):
        self.layer = layer
        self.bank_list_changed.emit()
        self.preset_name_changed.emit()
        self.preset_list_changed.emit()


    def get_bank_list(self):
        l = []

        for item in self.layer.bank_list:
            l.append(item[2])

        self.bank_list_model.setStringList(l)
        return self.bank_list_model


    def get_preset_name():
        return self.layer.preset_name


    def get_preset_list(self):
        l = []

        for item in self.layer.preset_list:
            l.append(item[2])

        self.preset_list_model.setStringList(l)

        return self.preset_list_model


    bank_list_changed = Signal()
    preset_name_changed = Signal()
    preset_list_changed = Signal()

    bank_list = Property(QObject, get_bank_list, notify = bank_list_changed)
    preset_name = Property(QObject, get_preset_name, notify = preset_name_changed)
    preset_list = Property(QObject, get_preset_list, notify = preset_list_changed)



class LayersController(QObject):
    def __init__(self, zyngui, parent=None):
        super(LayersController, self).__init__(parent)
        self.zyngui = zyngui
        self.layers_manager = zyngui.screens['layer']
        self.control = zyngui.screens['control']

        self.curlayer_wrapper = LayerWrapper(self)
        self.root_layers_model = LayersListModel(self)


    def get_root_layers_model(self):
        return self.root_layers_model


    def get_curlayer(self):
        self.curlayer_wrapper.layer = self.zyngui.curlayer
        return self.curlayer_wrapper


    def set_curlayer_index(self, index):
        if index > len(self.layers_manager.root_layers) or index < 0:
            return

        layer = self.layers_manager.root_layers[index]
        self.zyngui.layer_control(layer)
        self.curlayer_wrapper.layer = self.zyngui.curlayer


    @Slot('void')
    def debug_info(self):
        print(self.zyngui.curlayer.bank_list[0])
        print(self.zyngui.curlayer.preset_list[0])
        print(self.zyngui.curlayer.bank_list[0][2])
        print(self.zyngui.curlayer.preset_list[0][2])

    curlayer_changed = Signal()

    root_layers_model = Property(QObject, get_root_layers_model, constant = True)
    curlayer = Property(QObject, get_curlayer, notify = curlayer_changed)


