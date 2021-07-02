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

    visible: true
    title: root.selector.selector_path_element

    property alias view: view.view
    property alias model: view.model
    property alias delegate: view.delegate
    property alias currentIndex: view.currentIndex

    //TODO: Bind the base selector type to qml?
    property alias selector: view.selector
    signal itemActivated(int index)
    signal itemActivatedSecondary(int index)

    bottomPadding: Kirigami.Units.smallSpacing
    Component.onCompleted: view.forceActiveFocus()
    onFocusChanged: {
        if (focus) {
            view.forceActiveFocus()
        }
    }
    header: Kirigami.Heading {
		level: 2
		text: root.title
		visible: false
	}

    contentItem: //RowLayout {
        SelectorView {
            id: view
            //Layout.fillHeight: true
            //Layout.maximumWidth: Math.floor(root.width / 4) * 3
            //Layout.minimumWidth: Layout.maximumWidth
            onItemActivated: root.itemActivated(index)
            onItemActivatedSecondary: toor.itemActivatedSecondary(index)
        }

/*
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
                    paused: !zynthian.is_loading
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
    }*/
}
