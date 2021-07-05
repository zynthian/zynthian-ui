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

import QtQuick 2.10
import QtQuick.Layouts 1.4
import QtQuick.Controls 2.2 as QQC2
import org.kde.kirigami 2.4 as Kirigami

MainRowLayout {
    id: root
    width: 500
    height: 200
    Repeater {
        model: 10
        Rectangle {
            id: rectangle
            property string title: "Page " + index
            color: index == root.currentIndex ? "red" : "green"
            radius: 20
            implicitWidth: Math.floor(root.width / 3)
            ColumnLayout {
                anchors.centerIn: parent
                QQC2.Button {
                    text: "Grow"
                    onClicked: rectangle.implicitWidth += 10
                }
            }
        }
    }
}
