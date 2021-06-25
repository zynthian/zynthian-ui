# This Python file uses the following encoding: utf-8
import os
from pathlib import Path
import sys

from PySide2.QtGui import QGuiApplication
from PySide2.QtQml import QQmlApplicationEngine

#HACK
sys.path.insert(1, '/zynthian/zynthian-ui/')
from zyncoder import *
from zyngine import zynthian_layer

from layerswrapper import LayersWrapper

if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()

    layers_wrapper = LayersWrapper()
    engine.rootContext().setContextProperty("layers_wrapper", layers_wrapper)

    engine.load(os.fspath(Path(__file__).resolve().parent / "ui/main.qml"))

    if not engine.rootObjects():
        sys.exit(-1)
    sys.exit(app.exec_())
