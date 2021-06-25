/**
 *
 *  SPDX-FileCopyrightText: 2021 Marco Martin <mart@kde.org>
 *
 *  SPDX-License-Identifier: LGPL-2.0-or-later
 */

import QtQuick 2.10
import QtQuick.Layouts 1.4
import QtQuick.Controls 2.2 as QQC2
import org.kde.kirigami 2.4 as Kirigami


Kirigami.Page {
    id: root

    property alias view: view
    property alias model: view.model
    property alias delegate: view.delegate

    Component.onCompleted: view.forceActiveFocus()
    onFocusChanged: {
        if (focus) {
            view.forceActiveFocus()
        }
    }

    contentItem: RowLayout {
        Card {
            leftPadding: 0
            rightPadding: 0
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentItem: QQC2.ScrollView {
                QQC2.ScrollBar.horizontal.visible: false
                ListView {
                    id: view
                    keyNavigationEnabled: true
                    keyNavigationWraps: true
                    clip: true
                }
            }
        }
        ColumnLayout {
            Layout.fillHeight: true
            Layout.maximumWidth: Math.floor(root.width / 4)
            Card {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.maximumHeight: width / (gif.sourceSize.width / gif.sourceSize.height)

                contentItem: AnimatedImage {
                    id: gif
                    source: "./img/zynthian_gui_loading.gif"
                    paused: true
                }
            }
            Card {
                Layout.fillWidth: true
                Layout.fillHeight: true
                QQC2.Button {
                    anchors.centerIn: parent
                    text: "Quit"
                    onClicked: Qt.quit();
                }
            }
        }
    }
}
