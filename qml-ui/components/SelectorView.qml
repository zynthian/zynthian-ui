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


QQC2.ScrollView {
    id: root

    property alias view: view
    property alias model: view.model
    property alias delegate: view.delegate
    property alias currentIndex: view.currentIndex

    //TODO: Bind the base selector type to qml?
    property QtObject selector
    signal itemActivated(int index)
    signal itemActivatedSecondary(int index)

    Component.onCompleted: view.forceActiveFocus()
    onFocusChanged: {
        if (focus) {
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

        model: root.selector.selector_list
        delegate: Kirigami.BasicListItem {
            width: view.width
            label: model.display
            reserveSpaceForIcon: false

            checkable: false
            checked: root.currentIndex === index
            onClicked: {
                root.selector.current_index = index;
                root.selector.activate_index(index);
                root.itemActivated(index)
            }
            onPressAndHold: {
                root.selector.current_index = index;
                root.selector.activate_index_secondary(index);
                root.itemActivatedSecondary(index)
            }
        }
    }
    background:  Card {}
}

