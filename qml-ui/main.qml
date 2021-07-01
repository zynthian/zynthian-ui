/**
 *  SPDX-FileCopyrightText: 2021 Marco Martin <mart@kde.org>
 *
 *  SPDX-License-Identifier: LGPL-2.0-or-later
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
    pageStack.initialPage: [mainPage, layersPage, banksPage, presetsPage, controlPage]

    // FIXME: this stuff with a newer Kirigami should be done with a PageRouter?
    function ensureVisible(page) {
        let path = [mainPage, layersPage, banksPage, presetsPage, controlPage];
        let pageIndex = path.indexOf(page);
        if (pageIndex < 0) {
            print("Unknown page " + page.title);
            return;
        }
        if (!page.visible) {
            var i;
            for (i in path) {
                let otherPage = path[i];
                if (!otherPage.visible) {
                    pageStack.push(otherPage);
                }
                if (page == otherPage) {
                    break;
                }
            }
        }
        pageStack.currentIndex = pageIndex;
    }

    function makeLastVisible(page) {
        ensureVisible(page);
        pageStack.pop(page);
    }

    Connections {
        target: zynthian
        onCurrent_screenChanged: {
            switch(zynthian.current_screen) {
            case "main":
                makeLastVisible(mainPage);
                break;
            case "layer":
                makeLastVisible(layersPage);
                break;
            case "bank":
                makeLastVisible(banksPage);
                break;
            case "preset":
                makeLastVisible(presetsPage);
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

    ZComponents.SelectorPage {
        id: mainPage
        selector: zynthian.main
    }
    ZComponents.SelectorPage {
        id: layersPage
        selector: zynthian.layer
    }
    ZComponents.SelectorPage {
        id: banksPage
        selector: zynthian.bank
    }
    ZComponents.SelectorPage {
        id: presetsPage
        selector: zynthian.preset
    }
    ControlPage {
        id: controlPage
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
                enabled: root.pageStack.currentIndex > 0 || root.pageStack.layers.depth > 1
                onClicked: {
                    if (root.pageStack.layers.depth > 1) {
                        if (root.pageStack.layers.currentItem.hasOwnProperty("currentIndex")
                            && root.pageStack.layers.currentItem.currentIndex > 0
                        ) {
                            root.pageStack.layers.currentItem.currentIndex -= 1;
                        } else {
                            root.pageStack.layers.pop()
                        }
                    } else {
                        root.pageStack.currentIndex -= 1;
                    }
                }
            }
            QQC2.ToolButton {
                Layout.fillWidth: true
                text: qsTr("Layers")
                enabled: layersPage.visible
                onClicked: root.ensureVisible(layersPage)
            }
            QQC2.ToolButton {
                Layout.fillWidth: true
                text: qsTr("Favorites")
                enabled: presetsPage.visible
                checkable: true
                checked: zynthian.preset.show_only_favorites
                onCheckedChanged: zynthian.preset.show_only_favorites = checked
            }
            QQC2.ToolButton {
                Layout.fillWidth: true
                text: qsTr("Control")
                enabled: controlPage.visible
                onClicked: root.ensureVisible(controlPage)
            }
        }
    }
}

