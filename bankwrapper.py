# This Python file uses the following encoding: utf-8
import os
from pathlib import Path
import sys

from PySide2.QtCore import Qt, QObject, Slot, QUrl, QAbstractListModel, QModelIndex, QByteArray
from PySide2.QtGui import QGuiApplication
from PySide2.QtQml import QQmlApplicationEngine

#HACK
sys.path.insert(1, '/zynthian/zynthian-ui/')
from zyncoder import *
from zyngine import zynthian_layer

class BankListModel(QAbstractListModel):
    ENGINE_NAME = Qt.UserRole + 1
    BANK_NAME = Qt.UserRole + 2
    PRESET_PATH = Qt.UserRole + 3

    def __init__(self, zyngui, parent=None):
        super(BankListModel, self).__init__(parent)

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
            BankListModel.ENGINE_NAME : QByteArray(b'engine_name'),
            BankListModel.BANK_NAME : QByteArray(b'bank_name'),
            BankListModel.PRESET_PATH : QByteArray(b'preset_path'),
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
        if role == BankListModel.ENGINE_NAME:
            return layer.engine.name
        elif role == BankListModel.BANK_NAME:
            return layer.bank_name
        elif role == BankListModel.PRESET_PATH:
            return layer.get_presetpath()
        else:
            return None


class BankController(QObject):

    def __init__(self, zyngui, parent=None):
        super(BankController, self).__init__(parent)
        self.zyngui = zyngui



