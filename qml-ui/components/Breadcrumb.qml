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

QQC2.ToolBar {
    id: root
    property alias leftHeaderControl: leftHeaderControl.contentItem
    property alias rightHeaderControl: rightHeaderControl.contentItem
    property QQC2.StackView layerManager
    readonly property Item pageRow: layerManager.currentItem

    contentItem: RowLayout {
        QQC2.Control {
            id: leftHeaderControl
            Layout.fillHeight: true
            visible: contentItem !== null
        }
        Flickable {
            id: breadcrumbFlickable
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentHeight: height
            contentWidth: breadcrumbLayout.width

            RowLayout {
                id: breadcrumbLayout
                spacing: 0
                Repeater {
                    model: root.pageRow.visibleItems.length
                    QQC2.ToolButton {
                        id: toolButton
                        text: (index > 0 ? "> " : "") + root.pageRow.visibleItems[index].title
                        // HACK to hide home button as there is already one
                        visible: index > 0 || root.layerManager.depth > 1
                        checked: root.pageRow.currentIndex === index
                        opacity: checked ? 1 : 0.8
                        checkable: false
                        font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.2
                        Connections {
                            target: breadcrumbFlickable
                            onWidthChanged: toolButton.ensureBounds()
                        }
                        function ensureBounds() {
                            if (!checked || breadcrumbFlickable.width === 0) {
                                return;
                            }

                            if (x < breadcrumbFlickable.contentX) {
                                breadcrumbSlideAnim.stop();
                                breadcrumbSlideAnim.from = breadcrumbFlickable.contentX;
                                breadcrumbSlideAnim.to = x;
                                breadcrumbSlideAnim.start();
                            } else if (x + width - breadcrumbFlickable.contentX >  breadcrumbFlickable.width) {
                                breadcrumbSlideAnim.stop();
                                breadcrumbSlideAnim.from = breadcrumbFlickable.contentX;
                                breadcrumbSlideAnim.to = Math.min(breadcrumbLayout.width - breadcrumbFlickable.width, x - breadcrumbFlickable.width + width);

                                breadcrumbSlideAnim.start();
                            }
                        }
                        onClicked: {
                            root.pageRow.currentIndex = index
                        }
                        onCheckedChanged: {
                            if (checked) {
                                ensureBounds();
                            }
                        }
                    }
                }
            }
            NumberAnimation {
                id: breadcrumbSlideAnim
                target: breadcrumbFlickable
                property: "contentX"
                duration: Kirigami.Units.longDuration
                easing.type: Easing.InOutQuad
            }
        }
        Kirigami.Separator {
            Layout.fillHeight: true
            visible: !breadcrumbFlickable.atXEnd
        }
        QQC2.Control {
            id: rightHeaderControl
            Layout.fillHeight: true
            visible: contentItem !== null
        }
    }
}
