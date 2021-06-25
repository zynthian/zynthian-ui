/**
 *
 *  SPDX-FileCopyrightText: 2021 Marco Martin <mart@kde.org>
 *
 *  SPDX-License-Identifier: LGPL-2.0-or-later
 */

import QtQuick 2.1
import QtQuick.Layouts 1.4
import QtQuick.Controls 2.2 as QQC2
import org.kde.kirigami 2.4 as Kirigami


Card {
    id: root

    Layout.fillWidth: true
    Layout.fillHeight: true
    property alias title: title.text
    property alias subtitle: subtitle.text
    property real max
    property real value
    property string type

    contentItem: ColumnLayout {
        Kirigami.Heading {
            id: title
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            level: 2
        }
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            QQC2.Dial {
                anchors {
                    fill: parent
                    margins: Kirigami.Units.largeSpacing
                }
                value: root.value
                from: 0
                to: root.max
                scale: root.type !== "bool"
                enabled: root.type !== "bool"
                Kirigami.Heading {
                    anchors.centerIn: parent
                    text: parent.value.toPrecision(2)
                }
                Behavior on value {
                    NumberAnimation {
                        duration: Kirigami.Units.longDuration
                    }
                }
                Behavior on scale {
                    NumberAnimation {
                        duration: Kirigami.Units.longDuration
                    }
                }
            }
            QQC2.Switch {
                anchors.fill: parent
                scale: root.type === "bool"
                enabled: root.type === "bool"
                checked: root.value
                Behavior on scale {
                    NumberAnimation {
                        duration: Kirigami.Units.longDuration
                    }
                }
                Kirigami.Heading {
                    anchors {
                        horizontalCenter: parent.horizontalCenter
                        bottom: parent.bottom
                        bottomMargin: parent.height / 5
                    }
                    text: parent.checked ? "ON" : "OFF"
                }
            }
        }
        QQC2.Label {
            id: subtitle
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
        }
    }
}
