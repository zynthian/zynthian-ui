/* -*- coding: utf-8 -*-
******************************************************************************
ZYNTHIAN PROJECT: Zynthian Qt GUI

Main Class and Program for Zynthian GUI

Copyright (C) 2021 Marco Martin <mart@kde.org>

******************************************************************************

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License as
published by the Free Software Foundation; either version 2 of
the License, or any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

For a full copy of the GNU General Public License see the LICENSE.txt file.

******************************************************************************
*/

import QtQuick 2.1
import QtQuick.Layouts 1.4
import QtQuick.Controls 2.2 as QQC2
import QtQuick.Window 2.1
import org.kde.kirigami 2.6 as Kirigami

import "components" as ZComponents

Kirigami.ApplicationWindow {
    id: root

    width: screen.width
    height: screen.height

    pageStack.defaultColumnWidth: root.width
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None
    pageStack.initialPage: ZComponents.MainRowLayout {
        id: mainRowLayout
        ZComponents.SelectorPage {
            id: mainPage
            implicitWidth: mainRowLayout.width
            selector: zynthian.main
        }
        ZComponents.SelectorPage {
            id: layersPage
            implicitWidth: mainRowLayout.width/3
            header.visible: true
            selector: zynthian.layer
        }
        ZComponents.SelectorPage {
            id: banksPage
            leftPadding: 0
            rightPadding: 0
            implicitWidth: mainRowLayout.width/3
            header.visible: true
            selector: zynthian.bank
        }
        ZComponents.SelectorPage {
            id: presetsPage
            implicitWidth: mainRowLayout.width/3
            header.visible: true
            selector: zynthian.preset
        }
        ControlPage {
            id: controlPage
            implicitWidth: mainRowLayout.width
        }
    }

    //[mainPage, layersPage, banksPage, presetsPage, controlPage]

    CustomTheme {}

    // FIXME: this stuff with a newer Kirigami should be done with a PageRouter?
    function ensureVisible(page) {
        mainRowLayout.activateItem(page)
    }

    function makeLastVisible(page) {
        mainRowLayout.ensureLastVisibleItem(page)
    }

    Connections {
        target: zynthian
        onCurrent_screenChanged: {
            switch(zynthian.current_screen) {
            case "main":
                makeLastVisible(mainPage);
                ensureVisible(mainPage);
                break;
            case "layer":
                makeLastVisible(presetsPage);
                ensureVisible(layersPage);
                break;
            case "bank":
                makeLastVisible(presetsPage);
                ensureVisible(banksPage);
                break;
            case "preset":
                makeLastVisible(controlPage);
                ensureVisible(presetsPage);
                break;
            case "control":
                makeLastVisible(controlPage);
                break;
            default:
                print("Non managed screen " + zynthian.current_screen)
                break;
            }
        }
        onCurrent_modal_screenChanged: {
            switch (zynthian.current_modal_screen) {
            case "engine":
                root.pageStack.layers.push(Qt.resolvedUrl("./LayerCreation.qml"));
                break;
            case "layer_options":
                root.pageStack.layers.push(Qt.resolvedUrl("./LayerOptionsPage.qml"));
                break;
            case "snapshot":
                root.pageStack.layers.push(Qt.resolvedUrl("./SnapshotPage.qml"));
                break;
            case "audio_recorder":
                root.pageStack.layers.push(Qt.resolvedUrl("./AudioRecorderPage.qml"));
                break;
            case "midi_recorder":
                root.pageStack.layers.push(Qt.resolvedUrl("./MidiRecorderPage.qml"));
                break;
            case "admin":
                root.pageStack.layers.push(Qt.resolvedUrl("./AdminPage.qml"));
                break;
            case "confirm":
                confirmDialog.open();
                break;
            case "":
                root.pageStack.layers.clear()
                break;
            default:
                print("Non managed modal screen " + zynthian.current_modal_screen)
                break;
            }
        }
    }


    QQC2.Dialog {
        id: confirmDialog
        standardButtons: QQC2.Dialog.Yes | QQC2.Dialog.No
        x: root.width / 2 - width / 2
        y: root.height / 2 - height / 2
        dim: true
        width: Math.round(Math.max(implicitWidth, root.width * 0.8))
        height: Math.round(Math.max(implicitHeight, root.height * 0.8))
        contentItem: Kirigami.Heading {
            level: 2
            text: zynthian.confirm.text
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
        onAccepted: zynthian.confirm.accept()
        onRejected: zynthian.confirm.reject()
    }

    footer: QQC2.ToolBar {
        contentItem: RowLayout {
            QQC2.ToolButton {
                Layout.fillWidth: true
                text: qsTr("Back")
                enabled: mainRowLayout.currentPage > 0 || root.pageStack.layers.depth > 1
                onClicked: {
                    if (root.pageStack.layers.depth > 1) {
                        if (root.pageStack.layers.currentItem.hasOwnProperty("currentIndex")
                            && root.pageStack.layers.currentItem.currentIndex > 0
                        ) {
                            root.pageStack.layers.currentItem.currentIndex -= 1;
                        } else {
                            root.pageStack.layers.pop();
                        }
                    } else {
                        mainRowLayout.goToPreviousPage();
                    }
                }
            }
            QQC2.ToolButton {
                Layout.fillWidth: true
                text: qsTr("Layers")
                onClicked: root.ensureVisible(layersPage)
            }
            QQC2.ToolButton {
                Layout.fillWidth: true
                text: mainRowLayout.currentPage === 1 ? qsTr("Favorites") : qsTr("Presets")
                enabled: presetsPage.visible
                checkable: mainRowLayout.currentPage === 1
                checked: mainRowLayout.currentPage === 1 && zynthian.preset.show_only_favorites
                onCheckedChanged: {
                    if (mainRowLayout.currentPage === 1) {
                        zynthian.preset.show_only_favorites = checked
                    } else {
                        root.ensureVisible(presetsPage)
                    }
                }
            }
            QQC2.ToolButton {
                Layout.fillWidth: true
                text: qsTr("Edit")
                enabled: controlPage.visible
                onClicked: root.ensureVisible(controlPage)
            }
            /*QQC2.ToolButton {
                Layout.fillWidth: true
                text: qsTr("Quit")
                onClicked: Qt.quit();
            }*/
        }
    }
}

