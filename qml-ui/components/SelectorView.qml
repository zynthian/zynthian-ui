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


QQC2.ScrollView {
    id: root

    property alias view: view
    property alias model: view.model
    property alias delegate: view.delegate
    property alias currentIndex: view.currentIndex

    property string selectorId
    //TODO: Bind the base selector type to qml?
    readonly property QtObject selector: selectorId.length > 0 ? zynthian[selectorId] : null
    signal currentScreenIdRequested()
    signal itemActivated(int index)
    signal itemActivatedSecondary(int index)

    Component.onCompleted: view.forceActiveFocus()
    onActiveFocusChanged: {
        if (activeFocus) {
			root.currentScreenIdRequested();
            view.forceActiveFocus()
        }
    }

    leftPadding: 1
    rightPadding: 1
    topPadding: Kirigami.Units.gridUnit/2
    bottomPadding: Kirigami.Units.gridUnit/2

    QQC2.ScrollBar.horizontal.visible: false

    ListView {
        id: view
        keyNavigationEnabled: true
        keyNavigationWraps: true
        clip: true
        currentIndex: root.selector.current_index

        onActiveFocusChanged: {
            if (activeFocus) {
                root.currentScreenIdRequested();
            }
        }

        model: root.selector.selector_list

        delegate: Kirigami.BasicListItem {
            width: view.width
            label: model.display
            reserveSpaceForIcon: false

            checkable: false
            checked: root.currentIndex === index
            highlighted: root.currentIndex === index
            activeBackgroundColor: view.activeFocus ? Kirigami.Theme.highlightColor : Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g, Kirigami.Theme.highlightColor.b, 0.4)
            onClicked: {
                let oldCurrent_screen_id = zynthian.current_screen_id;
                root.selector.current_index = index;
                root.selector.activate_index(index);
                root.itemActivated(index)
                // if the activation didn't explicitly ask for a new screen, set the current as this
                if (zynthian.current_screen_id === oldCurrent_screen_id) {
                    root.currentScreenIdRequested()
                }
            }
            onPressAndHold: {
                let oldCurrent_screen_id = zynthian.current_screen_id;
                root.selector.current_index = index;
                root.selector.activate_index_secondary(index);
                root.itemActivatedSecondary(index)
                if (zynthian.current_screen_id === oldCurrent_screen_id) {
                    root.currentScreenIdRequested()
                }
            }
        }
    }

    background: Rectangle {
        color: Kirigami.Theme.backgroundColor
        border.color: view.activeFocus
            ? Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g, Kirigami.Theme.highlightColor.b, 0.5)
            : Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.3)
        radius: Kirigami.Units.gridUnit/2
    }
}

